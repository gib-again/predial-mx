"""LLM extraction v2 — usa schema_v2 (discriminated union) como response model.

Diferencias vs `src/core/llm_extract.py` (v1):
  - response_format = PredialOutputV2 (Pydantic) en lugar del dict-schema v1.
  - Reintento ÚNICO basado en el error específico de validación.
  - Output a `predial-mx-v2/{estado}/{archivo}.json` (NO sobrescribe v1).
  - Marca `requiere_revision` cuando el resultado es `otro_no_clasificado`
    o cuando ambos intentos fallan validación.
  - Logging por archivo de tokens (input/output/cached).

API pública:
  extraer_municipio(estado, cvegeo, anios) -> list[ExtractionResult]
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from openai import OpenAI
from openai.lib._pydantic import to_strict_json_schema
from pydantic import ValidationError

from src.core.constants import PREFIJOS_ESTADO
from src.core.text_utils import slugify
from src.extraction.schema_v2 import (
    OtroNoClasificadoSchema,
    PredialOutputV2,
)

# ── Rutas y configuración ──

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "catalogs" / "municipios_inegi.csv"
OUTPUT_ROOT = ROOT / "predial-mx-v2"

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
OPENAI_MODEL_FALLBACK = os.environ.get("OPENAI_MODEL_FALLBACK", "gpt-5.4")

_client: OpenAI | None = None
_schema_cache: dict | None = None


def _patch_schema_for_openai(node):
    """Recursivamente normaliza el schema para el modo strict de OpenAI:
       - `oneOf` → `anyOf` (strict mode no permite oneOf)
       - elimina `discriminator` (no permitido)
       - elimina `default`, `title`, `minItems`, `maxItems` (descriptivos no usados)
    """
    if isinstance(node, dict):
        if "oneOf" in node:
            node["anyOf"] = node.pop("oneOf")
        for k in ("discriminator", "default", "title"):
            node.pop(k, None)
        for v in node.values():
            _patch_schema_for_openai(v)
    elif isinstance(node, list):
        for item in node:
            _patch_schema_for_openai(item)
    return node


def _build_openai_schema() -> dict:
    """Convierte PredialOutputV2 a JSON Schema strict de OpenAI:
       - `tabla_cruda` (genérico `list[dict]`) se tipa como `{descripcion, valores}` por fila
       - `oneOf` → `anyOf`, sin `discriminator`, sin `default`/`title` (no permitidos en strict)
    Tras la inferencia, `PredialOutputV2.model_validate` acepta el resultado.
    """
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


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY no definida en el entorno")
        _client = OpenAI(api_key=api_key)
    return _client


# ── Mapeo CVEGEO → slug, nombre ──

_CVEGEO_CACHE: dict[str, tuple[str, str]] = {}


def _resolve_cvegeo(cvegeo: str) -> tuple[str, str]:
    """Devuelve (slug, NOM_MUN) a partir del CVEGEO INEGI (5 dígitos)."""
    cve = str(cvegeo).zfill(5)
    if cve in _CVEGEO_CACHE:
        return _CVEGEO_CACHE[cve]

    with CATALOG.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row["CVEGEO"] == cve:
                nom = row["NOM_MUN"]
                pair = (slugify(nom), nom)
                _CVEGEO_CACHE[cve] = pair
                return pair
    raise KeyError(f"CVEGEO {cve} no encontrado en {CATALOG}")


# ── Localizar source ──

def _find_focus_paths(estado: str, prefijo: str, anio: int, slug: str) -> tuple[Path | None, Path | None]:
    base = ROOT / "data" / estado / "focus_predial"
    name = f"{prefijo}_PREDIAL_{anio}_{slug}"
    primary = base / str(anio)
    txt = primary / f"{name}.txt"
    pdf = primary / f"{name}.pdf"
    if not txt.exists():
        for hit in base.rglob(f"{name}.txt"):
            txt = hit
            break
    if not pdf.exists():
        for hit in base.rglob(f"{name}.pdf"):
            pdf = hit
            break
    return (txt if txt.exists() else None, pdf if pdf.exists() else None)


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
   Una sola tasa uniforme sobre el valor catastral. Exactamente UNA entrada en `tabla`.

4) cuota_fija_simple
   Una sola cuota fija anual SIN rangos ni categorías. Exactamente UNA entrada.

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
  • Frutos civiles (impuesto sobre rentas).
  • Predios ejidales que pagan sobre producción.

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


def _format_validation_error(e: ValidationError) -> str:
    parts = []
    for err in e.errors()[:6]:
        loc = ".".join(str(p) for p in err["loc"])
        parts.append(f"  • {loc}: {err['msg']}")
    return "\n".join(parts)


def _call_llm(messages: list[dict], model: str | None = None) -> _LLMCall:
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


def _extract_one(
    *,
    estado: str,
    estado_pretty: str,
    cvegeo: str,
    anio: int,
    slug: str,
    municipio_pretty: str,
    prefijo: str,
) -> ExtractionResult:
    archivo = f"{prefijo}_PREDIAL_{anio}_{slug}.json"

    txt_path, _pdf_path = _find_focus_paths(estado, prefijo, anio, slug)

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

    r1 = _call_llm(messages, model=OPENAI_MODEL)
    total_in, total_out, total_cached = r1.tokens_in, r1.tokens_out, r1.tokens_cached

    if r1.output is not None:
        is_otro = isinstance(r1.output.predial, OtroNoClasificadoSchema)
        return ExtractionResult(
            estado=estado, cvegeo=cvegeo, anio=anio, slug=slug, archivo=archivo,
            output=r1.output,
            requiere_revision=is_otro,
            razon=("clasificado_como_otro_no_clasificado" if is_otro else None),
            tokens_in=total_in, tokens_out=total_out, tokens_cached=total_cached,
            intentos=1, modelo_usado=r1.modelo, escalado=False,
        )

    # Retry con mini + error específico
    retry_msg = USER_RETRY_TEMPLATE.format(ERROR=r1.error, TEXTO=texto)
    messages_retry = [
        {"role": "system", "content": SYSTEM_PROMPT_V2},
        {"role": "user", "content": retry_msg},
    ]
    r2 = _call_llm(messages_retry, model=OPENAI_MODEL)
    total_in += r2.tokens_in
    total_out += r2.tokens_out
    total_cached += r2.tokens_cached

    if r2.output is not None:
        is_otro = isinstance(r2.output.predial, OtroNoClasificadoSchema)
        return ExtractionResult(
            estado=estado, cvegeo=cvegeo, anio=anio, slug=slug, archivo=archivo,
            output=r2.output,
            requiere_revision=is_otro,
            razon=("clasificado_como_otro_no_clasificado" if is_otro else None),
            tokens_in=total_in, tokens_out=total_out, tokens_cached=total_cached,
            intentos=2, modelo_usado=r2.modelo, escalado=False,
        )

    # Escalación: tercer intento con modelo de fallback (gpt-5.4 full).
    escalation_msg = USER_RETRY_TEMPLATE.format(
        ERROR=f"Intento previo (mini) falló con: {r2.error}\nIntento aún anterior falló con: {r1.error}",
        TEXTO=texto,
    )
    messages_escalate = [
        {"role": "system", "content": SYSTEM_PROMPT_V2},
        {"role": "user", "content": escalation_msg},
    ]
    r3 = _call_llm(messages_escalate, model=OPENAI_MODEL_FALLBACK)
    total_in += r3.tokens_in
    total_out += r3.tokens_out
    total_cached += r3.tokens_cached

    if r3.output is not None:
        is_otro = isinstance(r3.output.predial, OtroNoClasificadoSchema)
        razon = (
            "clasificado_como_otro_no_clasificado_tras_escalacion"
            if is_otro
            else f"escalado_a_{OPENAI_MODEL_FALLBACK}_tras_2x_mini_fallido"
        )
        return ExtractionResult(
            estado=estado, cvegeo=cvegeo, anio=anio, slug=slug, archivo=archivo,
            output=r3.output,
            requiere_revision=is_otro,
            razon=razon,
            tokens_in=total_in, tokens_out=total_out, tokens_cached=total_cached,
            intentos=3, modelo_usado=r3.modelo, escalado=True,
        )

    return ExtractionResult(
        estado=estado, cvegeo=cvegeo, anio=anio, slug=slug, archivo=archivo,
        output=None,
        requiere_revision=True,
        razon=(
            f"valido_3x_fallido | mini_e1={r1.error} | "
            f"mini_e2={r2.error} | full_e3={r3.error}"
        ),
        tokens_in=total_in, tokens_out=total_out, tokens_cached=total_cached,
        intentos=3, modelo_usado=r3.modelo, escalado=True,
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
        "fuente": "txt",
        "modelo": result.modelo_usado,
    }
    payload["_meta_v2"] = {
        "intentos": result.intentos,
        "requiere_revision": result.requiere_revision,
        "escalado": result.escalado,
        "razon": result.razon,
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

def extraer_municipio(estado: str, cvegeo: str, anios: Iterable[int]) -> list[ExtractionResult]:
    """Extrae predial v2 para un municipio en los años indicados.

    Args:
        estado: Slug del estado (ej: "yucatan", "coahuila", "tamaulipas").
        cvegeo: Clave INEGI de 5 dígitos (ej: "31021" para Chichimilá, Yucatán).
        anios: Iterable de años (ej: [2010, 2022, 2023] o range(2010, 2026)).

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

    slug, municipio_pretty = _resolve_cvegeo(cvegeo)

    results: list[ExtractionResult] = []
    print(f"[v2] {estado.upper()} cvegeo={cvegeo} ({municipio_pretty})  modelo={OPENAI_MODEL}")
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
        )
        out_path = _save_result(r)
        r.out_path = out_path

        tipo = r.output.predial.tipo_esquema if r.output else "—"
        flag = "  [REVISAR]" if r.requiere_revision else ""
        esc = f"  [ESCALADO→{r.modelo_usado}]" if r.escalado else ""
        print(
            f"    tipo={tipo:25s}  intentos={r.intentos}  "
            f"tokens(in={r.tokens_in}, out={r.tokens_out}, cached={r.tokens_cached}){esc}{flag}"
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
