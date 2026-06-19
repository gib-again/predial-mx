"""LLM extraction v3 — multi-tarifa + transcripción fiel de tasas.

Extractor canónico.  Usa schema_v3 (PredialOutputV3) y prompts_v3.
Utilidades schema-agnostic viven en llm_utils.py.

API pública:
  extraer_municipio(estado, cvegeo, anios) -> list[ExtractionResult]
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from src.core.constants import PREFIJOS_ESTADO, json_predial_dir
from src.extraction.llm_utils import (
    OPENAI_MODEL,
    OPENAI_MODEL_FALLBACK,
    ROOT,
    _P00_DESCRIPCION_SIGNALS,
    _REOCR_IMPROVEMENT_FACTOR,
    _REOCR_MIN_CHARS,
    _find_focus_paths,
    _format_validation_error,
    _get_client,
    _load_overrides,
    _parse_paginas,
    _patch_schema_for_openai,
    _resolve_cvegeo,
)
from src.extraction.prompts_v3 import (
    SYSTEM_PROMPT_V3,
    USER_RETRY_TEMPLATE_V3,
    USER_TEMPLATE_V3,
)
from src.extraction.schema_v3 import OtroNoClasificadoSchema, PredialOutputV3

# ── Rutas ──
# El corpus v3 se persiste en data/{estado}/json_predial/{anio}/ vía
# json_predial_dir() (ver src/core/constants.py).

# ── Schema OpenAI (v3) ──

_schema_cache_v3: dict | None = None


def _build_openai_schema() -> dict:
    """Convierte PredialOutputV3 a JSON Schema strict de OpenAI."""
    global _schema_cache_v3
    if _schema_cache_v3 is not None:
        return _schema_cache_v3

    schema = to_strict_json_schema(PredialOutputV3)
    defs = schema.get("$defs", {})
    if "OtroNoClasificadoSchema" in defs:
        props = defs["OtroNoClasificadoSchema"].get("properties", {})
        if "tabla_cruda" in props:
            props["tabla_cruda"]["items"] = {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "descripcion": {
                        "type": "string",
                        "description": "Descripción libre de la fila tal como aparece.",
                    },
                    "valores": {
                        "type": "string",
                        "description": (
                            "Valores observados serializados como string "
                            "(ej. 'inferior=0.01; superior=10000; cuota=100')."
                        ),
                    },
                },
                "required": ["descripcion", "valores"],
            }

    _patch_schema_for_openai(schema)
    _schema_cache_v3 = schema
    return schema


# ── Llamada LLM ──


@dataclass
class _LLMCall:
    output: PredialOutputV3 | None
    error: str | None
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    modelo: str


def _call_llm(messages: list[dict], model: str | None = None) -> _LLMCall:
    return _call_llm_completions(messages, model=model)


def _call_llm_vision(
    system_prompt: str,
    user_text: str,
    image_data_urls: list[str],
    model: str | None = None,
) -> _LLMCall:
    user_content: list[dict] = [{"type": "text", "text": user_text}]
    for url in image_data_urls:
        user_content.append({"type": "image_url", "image_url": {"url": url}})
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_content},
    ]
    return _call_llm_completions(messages, model=model or OPENAI_MODEL_FALLBACK)


def _call_llm_completions(messages: list[dict], model: str | None = None) -> _LLMCall:
    client = _get_client()
    schema = _build_openai_schema()
    modelo = model or OPENAI_MODEL
    try:
        completion = client.chat.completions.create(
            model=modelo,
            messages=messages,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "PredialOutputV3",
                    "strict": True,
                    "schema": schema,
                },
            },
        )
    except Exception as e:
        return _LLMCall(None, f"api_error: {type(e).__name__}: {e}", 0, 0, 0, modelo)

    msg = completion.choices[0].message
    usage = completion.usage
    tokens_in = usage.prompt_tokens if usage else 0
    tokens_out = usage.completion_tokens if usage else 0
    tokens_cached = 0
    if usage and getattr(usage, "prompt_tokens_details", None):
        tokens_cached = getattr(usage.prompt_tokens_details, "cached_tokens", 0) or 0

    if getattr(msg, "refusal", None):
        return _LLMCall(None, f"refusal: {msg.refusal}", tokens_in, tokens_out, tokens_cached, modelo)

    raw = msg.content
    if not raw:
        return _LLMCall(None, "respuesta_vacia", tokens_in, tokens_out, tokens_cached, modelo)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        return _LLMCall(None, f"json_decode: {e}", tokens_in, tokens_out, tokens_cached, modelo)

    try:
        parsed = PredialOutputV3.model_validate(data)
    except ValidationError as e:
        return _LLMCall(None, _format_validation_error(e), tokens_in, tokens_out, tokens_cached, modelo)

    return _LLMCall(parsed, None, tokens_in, tokens_out, tokens_cached, modelo)


# ── Rescue helpers ──


def _any_otro(output: PredialOutputV3) -> bool:
    return any(
        isinstance(t.esquema, OtroNoClasificadoSchema)
        for t in output.predial.tarifas
    )


def _should_attempt_rescue(result_output: PredialOutputV3 | None) -> bool:
    """Activa rescue si ANY tarifa es otro_no_clasificado (salvo P-00 legítimo)."""
    if result_output is None:
        return True
    for t in result_output.predial.tarifas:
        if not isinstance(t.esquema, OtroNoClasificadoSchema):
            continue
        desc = (t.esquema.descripcion_estructural or "").lower()
        if not any(s in desc for s in _P00_DESCRIPCION_SIGNALS):
            return True
    return False


def _attempt_ocr_rescue(
    pdf_path: Path,
    estado_pretty: str,
    municipio_pretty: str,
    anio: int,
    texto_original_len: int,
) -> tuple[_LLMCall, dict] | None:
    """Re-OCR agresivo + LLM v3. Devuelve (call, provenance_fragment) o None."""
    from src.core.ocr_utils import aggressive_reocr

    new_text = aggressive_reocr(pdf_path, dpi=600, lang="spa+lat", psm=6)
    if not new_text or len(new_text) < _REOCR_MIN_CHARS:
        return None
    if texto_original_len > 0 and len(new_text) < texto_original_len * _REOCR_IMPROVEMENT_FACTOR:
        return None

    user_msg = USER_TEMPLATE_V3.format(
        MUNICIPIO=municipio_pretty,
        ESTADO=estado_pretty,
        ANIO=anio,
        TEXTO=new_text,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_V3},
        {"role": "user", "content": user_msg},
    ]
    call = _call_llm(messages, model=OPENAI_MODEL)

    provenance = {
        "archivo_pdf": str(pdf_path.relative_to(ROOT)),
        "paginas": None,
    }
    return (call, provenance)


def _attempt_vision_rescue(
    pdf_path: Path,
    estado_pretty: str,
    municipio_pretty: str,
    anio: int,
) -> tuple[_LLMCall, dict] | None:
    """Envía hasta 6 páginas como imágenes. Devuelve (call, provenance_fragment) o None."""
    from src.core.ocr_utils import pdf_pages_to_base64

    image_urls = pdf_pages_to_base64(pdf_path, pages=None, dpi=150, max_pages=6)
    if not image_urls:
        return None

    pages_used = list(range(1, len(image_urls) + 1))

    user_text = (
        f'Sección "Del Impuesto Predial" del municipio de {municipio_pretty}, '
        f'{estado_pretty}, ejercicio fiscal {anio}.\n\n'
        f"El TXT pre-extraído estaba truncado o vacío. Las imágenes adjuntas "
        f"son las páginas del PDF original (focus_predial). Extrae la mecánica "
        f"de cálculo del predial siguiendo las reglas del system prompt.\n\n"
        f"RECUERDA: output = lista de tarifas en predial.tarifas. "
        f"Tasas fieles (sin reescalar), unidad OBLIGATORIO."
    )
    call = _call_llm_vision(
        system_prompt=SYSTEM_PROMPT_V3,
        user_text=user_text,
        image_data_urls=image_urls,
        model=OPENAI_MODEL_FALLBACK,
    )

    provenance = {
        "archivo_pdf": str(pdf_path.relative_to(ROOT)),
        "paginas": pages_used,
    }
    return (call, provenance)


# ── Extracción por archivo ──


@dataclass
class ExtractionResult:
    estado: str
    cvegeo: str
    anio: int
    slug: str
    archivo: str
    output: PredialOutputV3 | None
    requiere_revision: bool
    razon: str | None
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    intentos: int
    modelo_usado: str = OPENAI_MODEL
    escalado: bool = False
    out_path: Path | None = None
    fuente: str = "txt"
    usado_reocr: bool = False
    usado_vision: bool = False
    procedencia: dict | None = None


def _hint_block(hint_tipo_esquema: str = "", hint_notas: str = "") -> str:
    """Bloque de pista del revisor para sesgar (no forzar) la extracción.

    Es un prior fuerte: el LLM debe verificarlo, no obedecerlo ciegamente.  Los
    validadores Pydantic siguen corriendo; si el resultado contradice la pista se
    marca igual.
    """
    parts = []
    if hint_tipo_esquema:
        parts.append(
            f"El revisor humano cree que el tipo de esquema es «{hint_tipo_esquema}». "
            "Trátalo como hipótesis fuerte y verifícala contra el texto; si el texto "
            "claramente indica otro esquema, usa el correcto."
        )
    if hint_notas:
        parts.append(f"Nota del revisor: {hint_notas}")
    if not parts:
        return ""
    return "PISTA DEL REVISOR (prior, verifícala):\n" + "\n".join(parts) + "\n\n"


def _extract_one(
    *,
    estado: str,
    estado_pretty: str,
    cvegeo: str,
    anio: int,
    slug: str,
    municipio_pretty: str,
    prefijo: str,
    enable_rescue: bool = True,
    force_full_model: bool = False,
    hint_tipo_esquema: str = "",
    hint_notas: str = "",
    force_vision: bool = False,
) -> ExtractionResult:
    archivo = f"{prefijo}_PREDIAL_{anio}_{slug}.json"

    txt_path, pdf_path = _find_focus_paths(estado, prefijo, anio, slug, cvegeo=cvegeo)

    # Detectar override para procedencia
    is_override = False
    override_paginas: list[int] | None = None
    if cvegeo:
        overrides = _load_overrides(estado)
        ov = overrides.get((anio, str(cvegeo).zfill(5)))
        if ov:
            is_override = True
            override_paginas = _parse_paginas(ov.get("paginas", ""))

    if txt_path is None:
        return ExtractionResult(
            estado=estado, cvegeo=cvegeo, anio=anio, slug=slug, archivo=archivo,
            output=None, requiere_revision=True,
            razon="texto_fuente_no_encontrado",
            tokens_in=0, tokens_out=0, tokens_cached=0, intentos=0,
        )

    texto = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
    if not texto:
        return ExtractionResult(
            estado=estado, cvegeo=cvegeo, anio=anio, slug=slug, archivo=archivo,
            output=None, requiere_revision=True,
            razon="texto_fuente_vacio",
            tokens_in=0, tokens_out=0, tokens_cached=0, intentos=0,
        )

    hint_prefix = _hint_block(hint_tipo_esquema, hint_notas)
    user_msg = hint_prefix + USER_TEMPLATE_V3.format(
        MUNICIPIO=municipio_pretty,
        ESTADO=estado_pretty,
        ANIO=anio,
        TEXTO=texto,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_V3},
        {"role": "user", "content": user_msg},
    ]

    primary_model = OPENAI_MODEL_FALLBACK if force_full_model else OPENAI_MODEL
    r1 = _call_llm(messages, model=primary_model)
    total_in, total_out, total_cached = r1.tokens_in, r1.tokens_out, r1.tokens_cached

    intentos = 1
    final_call: _LLMCall | None = r1
    error_history: list[str] = []
    escalado = force_full_model

    if r1.output is None:
        error_history.append(f"e1={r1.error}")
        retry_msg = USER_RETRY_TEMPLATE_V3.format(ERROR=r1.error, TEXTO=texto)
        messages_retry = [
            {"role": "system", "content": SYSTEM_PROMPT_V3},
            {"role": "user", "content": retry_msg},
        ]
        r2 = _call_llm(messages_retry, model=primary_model)
        total_in += r2.tokens_in; total_out += r2.tokens_out; total_cached += r2.tokens_cached
        intentos = 2
        final_call = r2

        if r2.output is None and not force_full_model:
            error_history.append(f"e2={r2.error}")
            escalation_msg = USER_RETRY_TEMPLATE_V3.format(
                ERROR=(f"Intento previo (mini) falló con: {r2.error}\n"
                       f"Intento aún anterior falló con: {r1.error}"),
                TEXTO=texto,
            )
            messages_escalate = [
                {"role": "system", "content": SYSTEM_PROMPT_V3},
                {"role": "user", "content": escalation_msg},
            ]
            r3 = _call_llm(messages_escalate, model=OPENAI_MODEL_FALLBACK)
            total_in += r3.tokens_in; total_out += r3.tokens_out; total_cached += r3.tokens_cached
            intentos = 3
            final_call = r3
            escalado = True

            if r3.output is None:
                error_history.append(f"full_e3={r3.error}")
        elif r2.output is None and force_full_model:
            error_history.append(f"e2={r2.error}")

    # ── Cascada de rescate (re-OCR → visión) ──
    fuente = "txt"
    usado_reocr = False
    usado_vision = False
    rescue_provenance: dict | None = None

    if (
        enable_rescue
        and pdf_path is not None
        and (force_vision or _should_attempt_rescue(final_call.output if final_call else None))
    ):
        # Re-OCR rescue (se omite con force_vision: el revisor pidió ir directo a visión)
        r_reocr = None
        if not force_vision:
            try:
                r_reocr = _attempt_ocr_rescue(
                    pdf_path=pdf_path,
                    estado_pretty=estado_pretty,
                    municipio_pretty=municipio_pretty,
                    anio=anio,
                    texto_original_len=len(texto),
                )
            except Exception as e:
                r_reocr = None
                error_history.append(f"reocr_exception={type(e).__name__}: {e}")

        if r_reocr is not None:
            reocr_call, reocr_prov = r_reocr
            usado_reocr = True
            total_in += reocr_call.tokens_in
            total_out += reocr_call.tokens_out
            total_cached += reocr_call.tokens_cached
            if reocr_call.output is not None and not _any_otro(reocr_call.output):
                final_call = reocr_call
                fuente = "pdf_reocr"
                rescue_provenance = reocr_prov
                intentos += 1
            elif reocr_call.output is not None:
                error_history.append("reocr_devolvió_otro_no_clasificado")
            else:
                error_history.append(f"reocr_invalid={reocr_call.error}")

        # Vision rescue (si re-OCR no rescató)
        if fuente == "txt":
            try:
                r_vision = _attempt_vision_rescue(
                    pdf_path=pdf_path,
                    estado_pretty=estado_pretty,
                    municipio_pretty=municipio_pretty,
                    anio=anio,
                )
            except Exception as e:
                r_vision = None
                error_history.append(f"vision_exception={type(e).__name__}: {e}")

            if r_vision is not None:
                vision_call, vision_prov = r_vision
                usado_vision = True
                total_in += vision_call.tokens_in
                total_out += vision_call.tokens_out
                total_cached += vision_call.tokens_cached
                if vision_call.output is not None and not _any_otro(vision_call.output):
                    final_call = vision_call
                    fuente = "pdf_vision"
                    rescue_provenance = vision_prov
                    escalado = True
                    intentos += 1
                elif vision_call.output is not None:
                    error_history.append("vision_devolvió_otro_no_clasificado")
                else:
                    error_history.append(f"vision_invalid={vision_call.error}")

    # ── Procedencia ──
    if fuente in ("pdf_reocr", "pdf_vision") and rescue_provenance:
        procedencia = {
            "archivo_pdf": rescue_provenance["archivo_pdf"],
            "archivo_txt": None,
            "paginas": rescue_provenance["paginas"],
            "fuente_ganadora": fuente,
            "origen_override": is_override,
        }
    else:
        procedencia = {
            "archivo_pdf": str(pdf_path.relative_to(ROOT)) if pdf_path else None,
            "archivo_txt": str(txt_path.relative_to(ROOT)) if txt_path else None,
            "paginas": override_paginas if is_override else None,
            "fuente_ganadora": "txt",
            "origen_override": is_override,
        }

    # ── Resultado final ──
    if final_call is not None and final_call.output is not None:
        has_otro = _any_otro(final_call.output)
        if fuente == "pdf_reocr":
            razon = "rescate_via_reocr"
        elif fuente == "pdf_vision":
            razon = "rescate_via_vision"
        elif has_otro:
            razon = "clasificado_como_otro_no_clasificado"
        elif escalado:
            razon = f"escalado_a_{OPENAI_MODEL_FALLBACK}_tras_2x_mini_fallido"
        else:
            razon = None

        return ExtractionResult(
            estado=estado, cvegeo=cvegeo, anio=anio, slug=slug, archivo=archivo,
            output=final_call.output,
            requiere_revision=has_otro,
            razon=razon,
            tokens_in=total_in, tokens_out=total_out, tokens_cached=total_cached,
            intentos=intentos, modelo_usado=final_call.modelo, escalado=escalado,
            fuente=fuente, usado_reocr=usado_reocr, usado_vision=usado_vision,
            procedencia=procedencia,
        )

    return ExtractionResult(
        estado=estado, cvegeo=cvegeo, anio=anio, slug=slug, archivo=archivo,
        output=None,
        requiere_revision=True,
        razon="valido_3x_fallido | " + " | ".join(error_history),
        tokens_in=total_in, tokens_out=total_out, tokens_cached=total_cached,
        intentos=intentos,
        modelo_usado=final_call.modelo if final_call else OPENAI_MODEL,
        escalado=escalado,
        fuente=fuente, usado_reocr=usado_reocr, usado_vision=usado_vision,
        procedencia=procedencia,
    )


def _save_result(result: ExtractionResult) -> Path:
    out_dir = json_predial_dir(result.estado, result.anio)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / result.archivo

    if result.output is not None:
        payload = result.output.model_dump(by_alias=True, mode="json", exclude_none=False)
    else:
        payload = {"predial": None, "_meta": None}

    payload["_meta"] = {
        "fuente": result.fuente,
        "modelo": result.modelo_usado,
    }
    payload["_meta_v3"] = {
        "intentos": result.intentos,
        "requiere_revision": result.requiere_revision,
        "escalado": result.escalado,
        "razon": result.razon,
        "usado_reocr": result.usado_reocr,
        "usado_vision": result.usado_vision,
        "tokens": {
            "input": result.tokens_in,
            "output": result.tokens_out,
            "cached": result.tokens_cached,
        },
        "cvegeo": result.cvegeo,
        "estado": result.estado,
        "anio": result.anio,
        "procedencia": result.procedencia,
    }

    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


# ── Función pública ──


def extraer_municipio(
    estado: str,
    cvegeo: str,
    anios: Iterable[int],
    slug_override: str | None = None,
    force_full_model: bool = False,
    hint_tipo_esquema: str = "",
    hint_notas: str = "",
    force_vision: bool = False,
) -> list[ExtractionResult]:
    """Extrae predial v3 para un municipio en los años indicados.

    Args:
        estado: Slug del estado (ej: "coahuila", "jalisco").
        cvegeo: Clave INEGI de 5 dígitos.
        anios: Iterable de años.
        slug_override: Slug explícito si difiere del catálogo INEGI.
        force_full_model: Arrancar con modelo full (gpt-5.4) en vez de mini.

    Returns:
        Lista de ExtractionResult. JSONs en `data/{estado}/json_predial/{anio}/`.
    """
    estado = estado.lower()
    if estado not in PREFIJOS_ESTADO:
        raise KeyError(f"Estado '{estado}' no registrado en PREFIJOS_ESTADO")
    prefijo = PREFIJOS_ESTADO[estado]
    estado_pretty = estado.capitalize()

    slug_catalog, municipio_pretty = _resolve_cvegeo(cvegeo)
    slug = slug_override or slug_catalog

    results: list[ExtractionResult] = []
    arranque_modelo = OPENAI_MODEL_FALLBACK if force_full_model else OPENAI_MODEL
    print(
        f"[v3] {estado.upper()} cvegeo={cvegeo} ({municipio_pretty})  modelo={arranque_modelo}"
        f"{' [FORCE_FULL]' if force_full_model else ''}"
    )
    for anio in anios:
        print(f"  -- {anio} --")
        r = _extract_one(
            estado=estado,
            estado_pretty=estado_pretty,
            cvegeo=cvegeo,
            anio=anio,
            slug=slug,
            municipio_pretty=municipio_pretty,
            prefijo=prefijo,
            force_full_model=force_full_model,
            hint_tipo_esquema=hint_tipo_esquema,
            hint_notas=hint_notas,
            force_vision=force_vision,
        )
        out_path = _save_result(r)
        r.out_path = out_path

        if r.output:
            n_tarifas = len(r.output.predial.tarifas)
            tipos = ", ".join(t.esquema.tipo_esquema for t in r.output.predial.tarifas)
        else:
            n_tarifas = 0
            tipos = "—"
        flag = "  [REVISAR]" if r.requiere_revision else ""
        esc = f"  [ESCALADO->{r.modelo_usado}]" if r.escalado else ""
        rescue = ""
        if r.usado_vision:
            rescue = "  [VISION]"
        elif r.usado_reocr:
            rescue = "  [REOCR]"
        print(
            f"    tarifas={n_tarifas}  tipos=[{tipos}]  intentos={r.intentos}  "
            f"fuente={r.fuente}  "
            f"tokens(in={r.tokens_in}, out={r.tokens_out}, cached={r.tokens_cached})"
            f"{esc}{rescue}{flag}"
        )
        if r.razon:
            print(f"    razon: {r.razon}")
        print(f"    saved: {out_path.relative_to(ROOT)}")
        results.append(r)

    total_in = sum(r.tokens_in for r in results)
    total_out = sum(r.tokens_out for r in results)
    total_cached = sum(r.tokens_cached for r in results)
    n_revision = sum(1 for r in results if r.requiere_revision)
    print(
        f"[v3] resumen: {len(results)} archivos | "
        f"tokens(in={total_in}, out={total_out}, cached={total_cached}) | "
        f"requiere_revision={n_revision}"
    )

    return results


if __name__ == "__main__":
    extraer_municipio("yucatan", "31021", [2010, 2022, 2023])
