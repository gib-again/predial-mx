"""LLM extraction v2 — usa schema_v2 (discriminated union) como response model.

DEPRECADO: usar llm_extract_v3 para nuevas extracciones.
Utilidades schema-agnostic viven en llm_utils.py.

API pública:
  extraer_municipio(estado, cvegeo, anios) -> list[ExtractionResult]
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from src.core.constants import PREFIJOS_ESTADO
from src.extraction.schema_v2 import (
    OtroNoClasificadoSchema,
    PredialOutputV2,
)
from src.extraction.llm_utils import (  # noqa: F401 — re-exported for legacy consumers
    OPENAI_MODEL,
    OPENAI_MODEL_FALLBACK,
    ROOT,
    _P00_DESCRIPCION_SIGNALS,
    _REOCR_IMPROVEMENT_FACTOR,
    _REOCR_MIN_CHARS,
    _apply_pdf_override,
    _find_focus_paths,
    _format_validation_error,
    _get_client,
    _load_overrides,
    _parse_paginas,
    _patch_schema_for_openai,
    _resolve_cvegeo,
)

# ── Rutas ──

OUTPUT_ROOT = ROOT / "predial-mx-v2"

_schema_cache: dict | None = None


def _build_openai_schema() -> dict:
    """Convierte PredialOutputV2 a JSON Schema strict de OpenAI."""
    global _schema_cache
    if _schema_cache is not None:
        return _schema_cache

    schema = to_strict_json_schema(PredialOutputV2)
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
    _schema_cache = schema
    return schema


# ── Prompts ──

SYSTEM_PROMPT_V2 = """\
Eres un modelo experto en extracción de información de leyes de ingresos municipales mexicanas.
Tu tarea es transcribir y estructurar la mecánica del IMPUESTO PREDIAL en una de SIETE variantes
mutuamente excluyentes. NO interpretes ni corrijas la ley.

═══ ELIGE EXACTAMENTE UNA VARIANTE (campo `predial.tipo_esquema`) ═══

1) tarifa_millar
   Catálogo de tasas al millar por categoría de predio (urbano, rústico, edificado/baldío,
   industrial). Filas categóricas SIN rangos de valor catastral.
   Si hay cuota fija ADEMÁS de la tasa al millar ("$150 más 3.5 al millar"), usa
   `cuota_fija_adicional` en cada fila.
   NO usar si la tabla tiene columnas LIMITE INFERIOR / LIMITE SUPERIOR (rangos de
   valor catastral) — eso es progresivo, cuota_fija_escalonada o mixto.

2) progresivo
   Brackets de valor catastral con CUOTA FIJA + TASA MARGINAL sobre el excedente.
   REQUISITO ESTRICTO: al menos un bracket debe tener `tasa_marginal > 0`.
   Si todos los `tasa_marginal` son 0 → NO es progresivo, es `cuota_fija_escalonada`.

3) tasa_unica
   Una sola tasa uniforme sobre el valor catastral o sobre la superficie del predio.
   Exactamente UNA entrada en `tabla`. Soporta tres patrones:

   3a) Tasa al millar/porcentaje sobre valor catastral:
       `unidad="al_millar"` | `"al_ciento"` | `"porcentaje"`,
       `base_calculo="valor_catastral"`.

   3b) Tasa única + cuota fija adicional ("$50 + 1.5 al millar anual"):
       Llena `cuota_fija_adicional` (objeto con `monto`, `periodicidad`, `unidad`)
       además de `tasa` y `unidad`. NO es `mixto` — sigue siendo tasa única
       porque la mecánica es uniforme (no hay brackets ni categorías).

   3c) Cuota por superficie ("$0.15 por m²", "$10 por hectárea"):
       `unidad="por_metro_cuadrado"` o `"por_hectarea"`,
       `base_calculo="superficie_m2"` o `"superficie_ha"`,
       `tasa` = monto en pesos por unidad de superficie. Esta variante es
       distinta a tasa al millar; úsala cuando el documento literalmente
       diga "X centavos/pesos por metro cuadrado" o equivalente.

4) cuota_fija_simple
   Una sola cuota fija anual SIN rangos ni categorías. Exactamente UNA entrada.

   Si además existe una tarifa SECUNDARIA menor (frutos civiles sobre rentas,
   predios agropecuarios al millar) que NO es la mecánica predominante del
   predial, documéntala como string en `tarifas_secundarias` (lista). NO
   migres a `mixto` solo por tener una tarifa secundaria pequeña — `mixto`
   está reservado para estructuras donde la heterogeneidad es PARTE de la
   mecánica principal.

5) cuota_fija_escalonada
   Brackets de valor catastral donde cada rango paga un MONTO FIJO (pesos), NO una tasa.
   2+ filas; montos no decrecientes; sin huecos ni overlaps.
   Si la ley sólo da el monto sin tasa marginal en cada rango → ESTA es la variante.
   Si CUALQUIER bracket usa unidad distinta a pesos (ej. último renglón es "al millar"
   o "% del valor catastral"), reclasificar como `mixto`. Un descenso brusco entre
   montos (ej. $110 → $0.10) suele indicar cambio de unidad oculto: revisar el texto
   y reclasificar a mixto en lugar de transcribir el número desnudo.

6) mixto
   Estructura tarifaria HETEROGÉNEA en unidades. Dos patrones canónicos:

   Patrón A (multi-columna heterogéneo): rangos de valor catastral × varias columnas
   categóricas (HABITACIONAL / NO HABITACIONAL, CON BARDA / SIN BARDA, urbano /
   rústico, etc.) donde alguna FILA usa unidad distinta a las otras. Ejemplo típico:
   3 primeras filas con cuotas fijas en pesos ("94.80", "142.20", "213.30") y
   última fila con tasas al millar ("1.58 al millar", "3.15 al millar"). NO es
   tarifa_millar — la presencia de columnas LIMITE INFERIOR/SUPERIOR la descarta.

   Patrón B (escalonada con outlier final): N–1 brackets de cuota fija en pesos +
   un último bracket abierto que cobra una tasa al millar o un porcentaje sobre
   valor catastral. Ejemplo: 14 filas con "cuota fija anual $X" + fila 15
   "100,000.01 En adelante  0.10 % del Valor catastral".

   Codificación: cada bracket → FilaMixta con `n_rango`, `inferior`, `superior` y
   `columnas` (lista de ColumnaValor). Cada ColumnaValor lleva `nombre` (categoría
   en snake_case, p.ej. "habitacional"; usa "general" si la tabla es de una sola
   columna), `valor` (número decimal), `tipo` ("cuota_fija" | "tasa_millar" |
   "tasa_marginal" | "tasa_porcentual") y `unidad` ("pesos" | "al_millar" |
   "porcentaje"). `comentarios` OBLIGATORIO describiendo qué columnas/filas son
   heterogéneas.

   REGLA DECISIVA: si la tabla tiene rangos por valor catastral Y al menos una
   fila o columna usa unidad distinta a las otras, es `mixto` — NO `tarifa_millar`
   ni `cuota_fija_escalonada`.

7) otro_no_clasificado (ESCAPE HATCH)
   Sólo si NINGUNA variante encaja, o el segmento llegó vacío/truncado.
   Exige `categoria` (estructura_no_estandar | segmento_vacio | error_segmentacion |
   municipio_sin_impuesto) y `descripcion_estructural` no vacía.

   Casos legítimos donde ESTE es el output correcto:
     • `municipio_sin_impuesto`: el documento explícitamente remite a otra ley
       (ej. "el impuesto predial se rige por la Ley General de Hacienda
       Municipal del Estado de X"). NO inventar mecánica.
     • `segmento_vacio`: el chunk llegó sin contenido tarifario por error de
       segmentación o de OCR.
     • `estructura_no_estandar`: el documento describe una mecánica que
       genuinamente no encaja (ej. base de cálculo es renta civil del predio,
       no valor catastral, sin tabla extraíble).

   Antes de caer aquí por "esquema raro", revisa si encaja en `mixto` con
   `comentarios` explicativos: por ejemplo, una mecánica de "rentas civiles"
   acompañada de "tasa al millar para predios agropecuarios" puede codificarse
   en `mixto` con una sola FilaMixta y comentarios que documenten la
   peculiaridad. `otro_no_clasificado` es el último recurso.

═══ REGLAS DE BRACKETS (progresivo, cuota_fija_escalonada, mixto) ═══

  • `inferior` estrictamente creciente entre rangos.
  • SIN huecos: `superior[i] == inferior[i+1]`. NO uses la convención centavera
    "$0.01–$N.00, $N.01–$M.00"; NORMALIZA a límites contiguos: "0–N, N–M, M–...".
  • Sólo el ÚLTIMO bracket puede tener `superior = null` ("en adelante").
  • `inferior >= 0` en el primer bracket.

═══ TARIFAS PARALELAS (regla crítica) ═══

Si el artículo establece DOS o más tarifas SEPARADAS para grupos distintos
(ej: una tabla con brackets para "predios urbanos" y por separado una tasa
única "4 al millar" para "predios rústicos", o "10 al millar" para
"agropecuarios"), NO MEZCLES los brackets en un solo `tabla`. Eso viola la
regla "sólo el último bracket puede tener superior=null" porque ambas tarifas
tendrían su propia fila "en adelante".

Procede así:
  • Elige la tarifa PREDOMINANTE (la que tiene más estructura — típicamente la
    de brackets por valor catastral) como `tabla` principal.
  • Describe la(s) tarifa(s) secundaria(s) textualmente en `comentarios`,
    citando la tasa, el grupo aplicable y el artículo de la ley
    (ej: "Art. 3: predios rústicos pagan 4 al millar anual sobre valor
    catastral; no se incluye en la tabla principal por ser tarifa paralela").
  • Si las dos tarifas se aplican a la MISMA población (no son alternativas
    sino acumulables), úsa `cuota_fija_adicional` en cada fila o, si la
    estructura es realmente híbrida en cada bracket, ColumnaValor adicionales.

═══ CONVENCIONES DE VALORES ═══

  • Todos los montos en PESOS MEXICANOS. Strip `$`, comas, espacios.
  • `tasa_marginal` y `tasa_millar` como decimales (0.00023, no "0.023%").
  • "En adelante", "sin límite", "y más" → `superior = null`.
  • `minimo_predial`: monto en pesos, periodicidad y unidad. `null` si no aplica.

═══ CAMPO `_meta` ═══

Establece SIEMPRE `_meta = null`. La metadata se llena del lado del orquestador.

═══ IGNORAR ═══

  • Descuentos, recargos, condonaciones, bonificaciones.
  • Tablas de "VALORES UNITARIOS DE TERRENO Y CONSTRUCCIÓN" (catastro, no tarifa).
  • Predios ejidales que pagan sobre producción agrícola (no inmueble).

═══ DOCUMENTAR (no ignorar) ═══

  • Frutos civiles / impuesto sobre rentas: si NO es la mecánica principal,
    documéntalos en `tarifas_secundarias` (cuota_fija_simple) o en
    `comentarios` (otras variantes). Si ES la mecánica principal pero no hay
    tabla estructural extraíble, usa `mixto` con `comentarios` explicativos
    o `otro_no_clasificado / estructura_no_estandar` como último recurso.
  • Tasa al millar para predios agropecuarios paralela a la tarifa principal:
    si la tarifa principal es estructurada (brackets / categorías), describe
    la paralela en `comentarios`. Si la principal es plana, considera
    `cuota_fija_simple` con `tarifas_secundarias`.

Devuelve un único objeto JSON con clave "predial" en la raíz y `_meta=null`.
"""

USER_TEMPLATE_V2 = """\
Sección "Del Impuesto Predial" del municipio de {MUNICIPIO}, {ESTADO}, ejercicio fiscal {ANIO}.

Extrae SOLO la mecánica de cálculo. Ignora descuentos, recargos y bonificaciones.

===== TEXTO =====
{TEXTO}
===== FIN =====
"""

USER_RETRY_TEMPLATE = """\
Tu extracción anterior FALLÓ la validación con este error:

{ERROR}

Re-extrae el mismo texto teniendo cuenta:
  • Si todos los `tasa_marginal` son 0 → usa `cuota_fija_escalonada` con `monto = cuota_fija`.
  • Si los rangos vienen como "0.01–N.00, N.01–M.00" NORMALIZA a contiguos "0–N, N–M".
  • `superior=null` SOLO en el último rango. Los demás deben tener un número.
  • Si el validador rechazó por "montos no decrecientes" y el bracket problemático
    tiene un valor mucho menor al anterior (≥10×), revisa si en el texto fuente
    ese bracket está expresado en otra unidad (al millar o % del valor catastral).
    Si es así, reclasifica TODO como `mixto`: cada bracket pasa a FilaMixta con
    una sola columna, y la `unidad` de esa columna refleja la real (pesos en los
    primeros, "porcentaje" o "al_millar" en los outliers).
  • Si la tabla es multi-columna por categoría de predio (habitacional vs no
    habitacional, con barda vs sin barda, urbano vs rústico, etc.) y al menos
    una fila usa "al millar" o "%" mientras otras usan cuota fija en pesos, NO
    es `tarifa_millar` ni `cuota_fija_escalonada` — es `mixto` con una FilaMixta
    por bracket y una ColumnaValor por categoría.
  • Si el validador rechazó porque un bracket NO-último tiene `superior=null`,
    es probable que estés mezclando DOS tarifas paralelas (ej. urbanos con
    brackets + rústicos con tasa única). Elige la tarifa con brackets como
    `tabla` principal y describe la otra en `comentarios`.
  • Si la tarifa es "$X por m²" o "$X por hectárea" (cuota por superficie),
    usa `tasa_unica` con `unidad="por_metro_cuadrado"` o `"por_hectarea"`,
    `base_calculo="superficie_m2"` o `"superficie_ha"`. NO uses `cuota_fija_simple`
    para esto — la cuota varía con el tamaño del predio.
  • Si la mecánica es una tasa única + cuota fija fija ("$50 + 1.5 al millar"),
    usa `tasa_unica` con `cuota_fija_adicional` poblado. NO confundir con `mixto`.
  • Si hay UNA cuota fija plana como mecánica principal y existe una tarifa
    secundaria menor (frutos civiles, agropecuarios), usa `cuota_fija_simple`
    con `tarifas_secundarias` (lista de strings descriptivos), NO `mixto`.
  • Si ninguna variante encaja realmente, usa `otro_no_clasificado` con la categoría
    correcta y `descripcion_estructural` no vacía.

Texto original (sin cambios):

===== TEXTO =====
{TEXTO}
===== FIN =====
"""


# ── Llamada LLM ──

@dataclass
class _LLMCall:
    output: PredialOutputV2 | None
    error: str | None
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    modelo: str


def _call_llm(messages: list[dict], model: str | None = None) -> _LLMCall:
    """Llamada estándar (text-only) con structured output strict."""
    return _call_llm_completions(messages, model=model)


def _call_llm_vision(
    system_prompt: str,
    user_text: str,
    image_data_urls: list[str],
    model: str | None = None,
) -> _LLMCall:
    """Llamada multimodal: texto + N imágenes (data URLs base64) → JSON estricto.

    Útil cuando el TXT pre-extraído está vacío/corrupto pero el PDF original
    es legible visualmente. Usa por defecto el modelo de fallback (gpt-5.4)
    porque mini no soporta vision con la misma fidelidad.
    """
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
                    "name": "PredialOutputV2",
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
        parsed = PredialOutputV2.model_validate(data)
    except ValidationError as e:
        return _LLMCall(None, _format_validation_error(e), tokens_in, tokens_out, tokens_cached, modelo)

    return _LLMCall(parsed, None, tokens_in, tokens_out, tokens_cached, modelo)


# ── Extracción por archivo ──

@dataclass
class ExtractionResult:
    estado: str
    cvegeo: str
    anio: int
    slug: str
    archivo: str
    output: PredialOutputV2 | None
    requiere_revision: bool
    razon: str | None
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    intentos: int
    modelo_usado: str = OPENAI_MODEL
    escalado: bool = False
    out_path: Path | None = None
    fuente: str = "txt"          # "txt" | "pdf_reocr" | "pdf_vision"
    usado_reocr: bool = False
    usado_vision: bool = False


# ── Cascada re-OCR → visión (rescue para casos con texto fuente vacío/truncado) ──

def _should_attempt_rescue(result_output: PredialOutputV2 | None) -> bool:
    """Determina si vale la pena gastar tokens/CPU en OCR/vision rescue.

    Activa cuando:
      - 3 intentos LLM fallaron (output is None) → último recurso
      - El resultado es otro_no_clasificado de cualquier categoría EXCEPTO
        si la descripcion_estructural sugiere que es legítimamente "sin
        tarifa real" (P-00).
    """
    if result_output is None:
        return True
    pred = result_output.predial
    if not isinstance(pred, OtroNoClasificadoSchema):
        return False  # Clasificación válida → no tocar

    desc = (pred.descripcion_estructural or "").lower()
    if any(s in desc for s in _P00_DESCRIPCION_SIGNALS):
        return False  # P-00: documento legítimamente sin tarifa

    # Cualquier otro otro_no_clasificado → intentar rescate (cubre P-03 que
    # antes quedaba afuera por categoria=estructura_no_estandar).
    return True


def _attempt_ocr_rescue(
    pdf_path: Path,
    estado_pretty: str,
    municipio_pretty: str,
    anio: int,
    texto_original_len: int,
) -> _LLMCall | None:
    """Re-OCR agresivo del PDF; si rescata texto, reinvoca el LLM.

    Returns:
        _LLMCall si el re-OCR produjo texto suficiente Y la nueva llamada
        valida un esquema NO-otro_no_clasificado. None si no rescata.
    """
    from src.core.ocr_utils import aggressive_reocr

    new_text = aggressive_reocr(pdf_path, dpi=600, lang="spa+lat", psm=6)
    if not new_text or len(new_text) < _REOCR_MIN_CHARS:
        return None
    if texto_original_len > 0 and len(new_text) < texto_original_len * _REOCR_IMPROVEMENT_FACTOR:
        return None

    user_msg = USER_TEMPLATE_V2.format(
        MUNICIPIO=municipio_pretty,
        ESTADO=estado_pretty,
        ANIO=anio,
        TEXTO=new_text,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_V2},
        {"role": "user", "content": user_msg},
    ]
    call = _call_llm(messages, model=OPENAI_MODEL)
    return call


def _attempt_vision_rescue(
    pdf_path: Path,
    estado_pretty: str,
    municipio_pretty: str,
    anio: int,
) -> _LLMCall | None:
    """Envía hasta 6 páginas del PDF como imágenes al modelo full con visión."""
    from src.core.ocr_utils import pdf_pages_to_base64

    image_urls = pdf_pages_to_base64(pdf_path, pages=None, dpi=150, max_pages=6)
    if not image_urls:
        return None

    user_text = (
        f'Sección "Del Impuesto Predial" del municipio de {municipio_pretty}, '
        f'{estado_pretty}, ejercicio fiscal {anio}.\n\n'
        f"El TXT pre-extraído estaba truncado o vacío. Las imágenes adjuntas "
        f"son las páginas del PDF original (focus_predial). Extrae la mecánica "
        f"de cálculo del predial siguiendo las reglas del system prompt."
    )
    return _call_llm_vision(
        system_prompt=SYSTEM_PROMPT_V2,
        user_text=user_text,
        image_data_urls=image_urls,
        model=OPENAI_MODEL_FALLBACK,
    )


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
) -> ExtractionResult:
    archivo = f"{prefijo}_PREDIAL_{anio}_{slug}.json"

    txt_path, pdf_path = _find_focus_paths(estado, prefijo, anio, slug, cvegeo=cvegeo)

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

    user_msg = USER_TEMPLATE_V2.format(
        MUNICIPIO=municipio_pretty,
        ESTADO=estado_pretty,
        ANIO=anio,
        TEXTO=texto,
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT_V2},
        {"role": "user", "content": user_msg},
    ]

    # Modelo de primer intento: mini por default, full si force_full_model=True
    primary_model = OPENAI_MODEL_FALLBACK if force_full_model else OPENAI_MODEL
    r1 = _call_llm(messages, model=primary_model)
    total_in, total_out, total_cached = r1.tokens_in, r1.tokens_out, r1.tokens_cached

    intentos = 1
    final_call: _LLMCall | None = r1
    error_history: list[str] = []
    escalado = force_full_model  # si arrancamos con full, ya está "escalado"

    if r1.output is None:
        # Retry con mismo modelo + error específico
        error_history.append(f"e1={r1.error}")
        retry_msg = USER_RETRY_TEMPLATE.format(ERROR=r1.error, TEXTO=texto)
        messages_retry = [
            {"role": "system", "content": SYSTEM_PROMPT_V2},
            {"role": "user", "content": retry_msg},
        ]
        r2 = _call_llm(messages_retry, model=primary_model)
        total_in += r2.tokens_in; total_out += r2.tokens_out; total_cached += r2.tokens_cached
        intentos = 2
        final_call = r2

        if r2.output is None and not force_full_model:
            # Escalación: tercer intento con modelo de fallback (gpt-5.4 full).
            # Si ya arrancamos con full (force_full_model), no hay a dónde escalar.
            error_history.append(f"e2={r2.error}")
            escalation_msg = USER_RETRY_TEMPLATE.format(
                ERROR=(f"Intento previo (mini) falló con: {r2.error}\n"
                       f"Intento aún anterior falló con: {r1.error}"),
                TEXTO=texto,
            )
            messages_escalate = [
                {"role": "system", "content": SYSTEM_PROMPT_V2},
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

    if (
        enable_rescue
        and pdf_path is not None
        and _should_attempt_rescue(final_call.output if final_call else None)
    ):
        # Re-OCR rescue
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
            usado_reocr = True
            total_in += r_reocr.tokens_in
            total_out += r_reocr.tokens_out
            total_cached += r_reocr.tokens_cached
            # Aceptar el rescue solo si validó Y no es otro_no_clasificado
            if r_reocr.output is not None:
                is_otro = isinstance(r_reocr.output.predial, OtroNoClasificadoSchema)
                if not is_otro:
                    final_call = r_reocr
                    fuente = "pdf_reocr"
                    intentos += 1
                else:
                    error_history.append("reocr_devolvió_otro_no_clasificado")
            else:
                error_history.append(f"reocr_invalid={r_reocr.error}")

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
                usado_vision = True
                total_in += r_vision.tokens_in
                total_out += r_vision.tokens_out
                total_cached += r_vision.tokens_cached
                if r_vision.output is not None:
                    is_otro = isinstance(r_vision.output.predial, OtroNoClasificadoSchema)
                    if not is_otro:
                        final_call = r_vision
                        fuente = "pdf_vision"
                        escalado = True  # vision usa modelo full
                        intentos += 1
                    else:
                        error_history.append("vision_devolvió_otro_no_clasificado")
                else:
                    error_history.append(f"vision_invalid={r_vision.error}")

    # ── Construcción del ExtractionResult final ──
    if final_call is not None and final_call.output is not None:
        is_otro = isinstance(final_call.output.predial, OtroNoClasificadoSchema)
        if fuente == "pdf_reocr":
            razon = "rescate_via_reocr"
        elif fuente == "pdf_vision":
            razon = "rescate_via_vision"
        elif is_otro:
            razon = "clasificado_como_otro_no_clasificado"
        elif escalado:
            razon = f"escalado_a_{OPENAI_MODEL_FALLBACK}_tras_2x_mini_fallido"
        else:
            razon = None

        return ExtractionResult(
            estado=estado, cvegeo=cvegeo, anio=anio, slug=slug, archivo=archivo,
            output=final_call.output,
            requiere_revision=is_otro,
            razon=razon,
            tokens_in=total_in, tokens_out=total_out, tokens_cached=total_cached,
            intentos=intentos, modelo_usado=final_call.modelo, escalado=escalado,
            fuente=fuente, usado_reocr=usado_reocr, usado_vision=usado_vision,
        )

    # Todo falló
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
    )


def _save_result(result: ExtractionResult) -> Path:
    out_dir = OUTPUT_ROOT / result.estado
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
    payload["_meta_v2"] = {
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
) -> list[ExtractionResult]:
    """Extrae predial v2 para un municipio en los años indicados.

    Args:
        estado: Slug del estado (ej: "yucatan", "coahuila", "tamaulipas").
        cvegeo: Clave INEGI de 5 dígitos (ej: "31021" para Chichimilá, Yucatán).
        anios: Iterable de años (ej: [2010, 2022, 2023] o range(2010, 2026)).
        slug_override: Slug explícito a usar para localizar el TXT y nombrar el
            JSON de salida. Útil cuando el slug del filename difiere del slug
            que arroja el catálogo INEGI (ej. "suma_de_hidalgo" vs catálogo
            "suma"). Si es None, se resuelve vía catálogo.

    Returns:
        Lista de ExtractionResult, uno por año procesado. JSONs guardados en
        `predial-mx-v2/{estado}/{archivo}.json`. NO sobrescribe v1.

    Logging:
        Imprime por archivo el tipo_esquema, intentos, tokens (in/out/cached) y
        flag de requiere_revision si aplica.
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
    print(f"[v2] {estado.upper()} cvegeo={cvegeo} ({municipio_pretty})  modelo={arranque_modelo}"
          f"{' [FORCE_FULL]' if force_full_model else ''}")
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
        )
        out_path = _save_result(r)
        r.out_path = out_path

        tipo = r.output.predial.tipo_esquema if r.output else "—"
        flag = "  [REVISAR]" if r.requiere_revision else ""
        esc = f"  [ESCALADO→{r.modelo_usado}]" if r.escalado else ""
        rescue = ""
        if r.usado_vision:
            rescue = "  [VISION]"
        elif r.usado_reocr:
            rescue = "  [REOCR]"
        print(
            f"    tipo={tipo:25s}  intentos={r.intentos}  fuente={r.fuente}  "
            f"tokens(in={r.tokens_in}, out={r.tokens_out}, cached={r.tokens_cached})"
            f"{esc}{rescue}{flag}"
        )
        if r.razon:
            print(f"    razon: {r.razon}")
        print(f"    saved: {out_path.relative_to(ROOT)}")
        results.append(r)

    # Resumen
    total_in = sum(r.tokens_in for r in results)
    total_out = sum(r.tokens_out for r in results)
    total_cached = sum(r.tokens_cached for r in results)
    n_revision = sum(1 for r in results if r.requiere_revision)
    print(
        f"[v2] resumen: {len(results)} archivos | "
        f"tokens(in={total_in}, out={total_out}, cached={total_cached}) | "
        f"requiere_revision={n_revision}"
    )

    return results


if __name__ == "__main__":
    # Smoke test: Chichimilá, Yucatán (CVEGEO 31021), años 2010, 2022, 2023.
    extraer_municipio("yucatan", "31021", [2010, 2022, 2023])
