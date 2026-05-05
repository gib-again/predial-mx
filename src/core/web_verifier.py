"""Verificación web de huecos del panel mediante OpenAI Responses API + web_search.

Para cada (cve_mun, anio) sin extracción, llama a un modelo con búsqueda web
nativa para corroborar:
  - Si la Ley de Ingresos del municipio existe.
  - Si hay un PDF descargable y dónde.
  - Por qué el pipeline no la encontró (no_publicada, error_url_boletin, etc.).

Output estructurado por verificación:
    {
      "existe_ley": bool,
      "url_pdf": str | None,
      "fuente": str | None,           # dominio (boletinoficial.sonora.gob.mx, etc.)
      "razon_bloqueo": str,           # no_publicada | pdf_no_disponible | ...
      "confianza": str,               # high | medium | low
      "comentario": str,
    }

API: usa `client.responses.create` con `tools=[{"type": "web_search"}]`.
Modelo default: env `OPENAI_WEB_VERIFIER_MODEL` o `gpt-5.4`.
"""

from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "OPENAI_API_KEY no definida. Agregar al .env "
                "antes de invocar el verificador web."
            )
        _client = OpenAI(api_key=api_key)
    return _client


# ── JSON Schema para la respuesta estructurada ──

VERIFY_JSON_SCHEMA: dict[str, Any] = {
    "name": "verificacion_ley_municipal",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "existe_ley": {
                "type": "boolean",
                "description": (
                    "True si encontraste evidencia confiable de que la Ley "
                    "de Ingresos del municipio para el ejercicio fiscal "
                    "existe (publicada en cualquier fuente)."
                ),
            },
            "url_pdf": {
                "type": ["string", "null"],
                "description": (
                    "URL directa al PDF si la encontraste; null si no."
                ),
            },
            "fuente": {
                "type": ["string", "null"],
                "description": (
                    "Dominio principal de la fuente (ej. "
                    "'boletinoficial.sonora.gob.mx', 'archive.org', "
                    "'congresoson.gob.mx')."
                ),
            },
            "razon_bloqueo": {
                "type": "string",
                "enum": [
                    "no_publicada",
                    "pdf_no_disponible",
                    "error_url_boletin",
                    "ley_de_hacienda_vigente",
                    "agrupada_con_otros_municipios",
                    "sin_evidencia",
                    "otro",
                ],
                "description": (
                    "Por qué el pipeline no extrajo este (muni, año). "
                    "'no_publicada' = el congreso no aprobó ley para ese "
                    "año (gap real); 'pdf_no_disponible' = ley existe pero "
                    "PDF no accesible; 'error_url_boletin' = el discoverer "
                    "asoció URL incorrecta; 'ley_de_hacienda_vigente' = "
                    "se rige por una Ley de Hacienda municipal; "
                    "'agrupada_con_otros_municipios' = aparece en un "
                    "boletín colectivo; 'sin_evidencia' = búsqueda web no "
                    "arrojó resultados concluyentes."
                ),
            },
            "confianza": {
                "type": "string",
                "enum": ["high", "medium", "low"],
            },
            "comentario": {
                "type": "string",
                "description": (
                    "Texto libre con detalles de lo encontrado: nombres "
                    "de leyes referenciadas, fechas de publicación, "
                    "fuentes consultadas. Máx ~600 chars."
                ),
            },
        },
        "required": [
            "existe_ley", "url_pdf", "fuente",
            "razon_bloqueo", "confianza", "comentario",
        ],
        "additionalProperties": False,
    },
}


_PROMPT_TEMPLATE = """Investiga si la **Ley de Ingresos del Municipio de \
{municipio_nom}, {estado_nom}, México** para el ejercicio fiscal **{anio}** \
fue publicada y dónde puede consultarse.

Pasos sugeridos:
1. Busca en el sitio del Boletín Oficial del estado.
2. Busca en repositorios alternativos (sitio del congreso, sitio municipal, \
archive.org, ordenjuridico.gob.mx, scjn.gob.mx).
3. Si encuentras el PDF, reporta la URL directa.
4. Si NO encuentras la Ley de Ingresos puntual de {anio}, verifica si el \
municipio se rige por una Ley de Hacienda municipal vigente (válida varios años).

Reporta el resultado en JSON estructurado siguiendo el schema. Sé conservador: \
si la evidencia es ambigua marca confianza=low. Si NO encuentras evidencia \
de la ley, usa razon_bloqueo='sin_evidencia' o 'no_publicada' según el caso."""


_SYSTEM_PROMPT = (
    "Eres un investigador especializado en legislación fiscal municipal "
    "mexicana. Buscas Leyes de Ingresos publicadas en boletines oficiales "
    "estatales y otras fuentes legales. Reportas hallazgos en JSON "
    "estructurado, con citas precisas a las fuentes."
)


def verify_gap(
    municipio_nom: str,
    anio: int,
    *,
    estado_nom: str = "Sonora",
    model: str | None = None,
    max_search_results: int = 5,
) -> dict:
    """Verifica un (municipio, anio) sin extracción usando web_search nativo.

    Args:
        municipio_nom: nombre oficial del municipio (ej. "Hermosillo").
        anio: ejercicio fiscal a verificar (ej. 2014).
        estado_nom: nombre del estado (default Sonora).
        model: override del modelo (default env OPENAI_WEB_VERIFIER_MODEL
            o "gpt-5.4").
        max_search_results: hint para el tool web_search (no garantizado).

    Returns:
        Dict con campos del schema VERIFY_JSON_SCHEMA + 'raw_response'.
        Si la llamada falla, retorna {'error': ..., 'raw_response': None}.
    """
    client = _get_client()
    model_id = (
        model
        or os.environ.get("OPENAI_WEB_VERIFIER_MODEL")
        or "gpt-5.4"
    )

    prompt = _PROMPT_TEMPLATE.format(
        municipio_nom=municipio_nom,
        estado_nom=estado_nom,
        anio=anio,
    )

    try:
        resp = client.responses.create(
            model=model_id,
            input=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            tools=[{"type": "web_search"}],
            text={
                "format": {
                    "type": "json_schema",
                    "name": VERIFY_JSON_SCHEMA["name"],
                    "schema": VERIFY_JSON_SCHEMA["schema"],
                    "strict": True,
                }
            },
        )
    except Exception as e:
        return {
            "error": f"{type(e).__name__}: {e}",
            "raw_response": None,
            "existe_ley": False,
            "url_pdf": None,
            "fuente": None,
            "razon_bloqueo": "otro",
            "confianza": "low",
            "comentario": f"API error: {e}",
        }

    raw_text = _extract_output_text(resp)
    if not raw_text:
        return {
            "error": "empty_response",
            "raw_response": None,
            "existe_ley": False,
            "url_pdf": None,
            "fuente": None,
            "razon_bloqueo": "otro",
            "confianza": "low",
            "comentario": "Modelo no devolvió texto.",
        }

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as e:
        return {
            "error": f"json_decode: {e}",
            "raw_response": raw_text,
            "existe_ley": False,
            "url_pdf": None,
            "fuente": None,
            "razon_bloqueo": "otro",
            "confianza": "low",
            "comentario": f"JSON inválido en respuesta: {raw_text[:200]}",
        }

    data["raw_response"] = raw_text
    # Tokens (best-effort — varía por SDK version)
    usage = getattr(resp, "usage", None)
    if usage is not None:
        data["tokens_input"] = getattr(usage, "input_tokens", None)
        data["tokens_output"] = getattr(usage, "output_tokens", None)
    return data


def _extract_output_text(resp) -> str:
    """Extrae texto de la respuesta de Responses API.

    El SDK expone resp.output_text (string concatenado de los outputs de
    tipo 'message'). Si no, recorre resp.output a mano.
    """
    # Conveniencia: openai>=1.50 expone output_text
    txt = getattr(resp, "output_text", None)
    if txt:
        return txt

    # Fallback: recorrer resp.output → buscar el primer mensaje con content text.
    output = getattr(resp, "output", None) or []
    for item in output:
        item_type = getattr(item, "type", None) or (
            item.get("type") if isinstance(item, dict) else None
        )
        if item_type != "message":
            continue
        content = getattr(item, "content", None) or (
            item.get("content") if isinstance(item, dict) else []
        )
        for c in content or []:
            c_type = getattr(c, "type", None) or (
                c.get("type") if isinstance(c, dict) else None
            )
            if c_type in ("output_text", "text"):
                t = getattr(c, "text", None) or (
                    c.get("text") if isinstance(c, dict) else None
                )
                if t:
                    return t
    return ""
