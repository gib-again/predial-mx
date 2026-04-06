"""
Localizador de sección predial vía LLM (gpt-4.1-mini).

Usado como fallback cuando los patrones regex no encuentran la sección predial
dentro de una ley de ingresos. Envía el texto completo (con marcadores de
posición) a un modelo barato y pide que identifique los límites de la sección.

Costo estimado: ~$0.001 por llamada (~1.5K tokens input).

Uso directo:
    from src.core.llm_locator import locate_predial_llm
    result = locate_predial_llm(text, "leon", 2024, "guanajuato")
    if result.found:
        section = text[result.start_char:result.end_char]
"""

from __future__ import annotations

import csv
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from openai import OpenAI

# ── Configuración ──

LLM_LOCATOR_MODEL = os.environ.get("OPENAI_LOCATOR_MODEL", "gpt-4.1-mini")

# Límite de texto para enviar completo (por encima se usa resumen por páginas)
_MAX_FULL_TEXT_CHARS = 40_000

# Intervalo entre marcadores de posición
_MARKER_INTERVAL = 500

# ── Cliente OpenAI (reutiliza el patrón de llm_extract.py) ──

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "Variable de entorno OPENAI_API_KEY no definida. "
                "Definir con: export OPENAI_API_KEY='sk-...'"
            )
        _client = OpenAI(api_key=api_key)
    return _client


# ── Resultado ──

@dataclass
class LocatorResult:
    """Resultado de la localización LLM de la sección predial."""
    found: bool
    start_char: int = -1
    end_char: int = -1
    method: str = ""              # "llm_locator"
    confidence: float = 0.0
    section_title: str = ""
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0


# ── Prompt ──

_SYSTEM_PROMPT = """\
Eres un experto en legislación fiscal mexicana. Tu tarea es localizar la \
sección del IMPUESTO PREDIAL (o su equivalente: "impuesto sobre la propiedad \
urbana, suburbana y rústica", "impuesto sobre el patrimonio", etc.) dentro \
del texto de una ley de ingresos municipal.

El texto contiene marcadores de posición con formato [POS:NNNN] insertados \
cada ~500 caracteres. Usa estos marcadores para indicar dónde EMPIEZA y \
TERMINA la sección predial.

Responde ÚNICAMENTE con JSON válido:
{
  "start_marker": "POS:NNNN",
  "end_marker": "POS:NNNN",
  "confidence": 0.85,
  "section_title": "DEL IMPUESTO PREDIAL"
}

Si NO encuentras la sección predial, responde:
{"start_marker": "", "end_marker": "", "confidence": 0.0, "section_title": ""}

Reglas:
- confidence: 0.0 a 1.0. Usa >0.8 si el título es claro, 0.5-0.8 si deduces \
por contexto, <0.5 si es ambiguo.
- start_marker: el marcador POS más cercano ANTES del inicio de la sección.
- end_marker: el marcador POS más cercano DESPUÉS del fin de la sección.
- La sección incluye artículos con tasas, tarifas, tablas y bases gravables."""

_USER_TEMPLATE = """\
Municipio: {municipio}
Ejercicio fiscal: {ejercicio}
Estado: {estado}

--- TEXTO DE LA LEY ---
{text}"""


# ── Funciones auxiliares ──

def _insert_markers(text: str) -> str:
    """Inserta marcadores [POS:NNNN] cada _MARKER_INTERVAL caracteres."""
    parts: list[str] = []
    for i in range(0, len(text), _MARKER_INTERVAL):
        parts.append(f"[POS:{i}]")
        parts.append(text[i:i + _MARKER_INTERVAL])
    return "".join(parts)


def _parse_marker(marker_str: str) -> int:
    """Extrae posición numérica de un marcador 'POS:NNNN'."""
    if not marker_str:
        return -1
    m = re.search(r"(\d+)", marker_str)
    return int(m.group(1)) if m else -1


def _summarize_by_pages(text: str, chars_per_page: int = 3500) -> str:
    """Para textos largos, genera resumen por página con marcadores."""
    pages: list[str] = []
    for i, start in enumerate(range(0, len(text), chars_per_page)):
        chunk = text[start:start + chars_per_page]
        # Tomar primeras y últimas ~150 chars como resumen
        summary = chunk[:150]
        if len(chunk) > 300:
            summary += " [...] " + chunk[-150:]
        pages.append(f"[POS:{start}] --- Página {i + 1} ---\n{summary}")
    return "\n\n".join(pages)


# ── Log CSV ──

_LOG_FIELDS = [
    "timestamp", "estado", "municipio", "ejercicio",
    "input_tokens", "output_tokens", "confidence",
    "found", "model", "cost_usd_est",
]


def _log_call(
    log_dir: Path | None,
    estado: str,
    municipio: str,
    ejercicio: int,
    result: LocatorResult,
):
    """Registra cada llamada al locator en un CSV para auditoría de costos."""
    if log_dir is None:
        return
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "llm_locator_log.csv"
    is_new = not log_path.exists()

    # Estimación de costo (gpt-4.1-mini: $0.40/M input, $1.60/M output)
    cost = (result.input_tokens * 0.40 + result.output_tokens * 1.60) / 1_000_000

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "estado": estado,
        "municipio": municipio,
        "ejercicio": ejercicio,
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "confidence": f"{result.confidence:.2f}",
        "found": result.found,
        "model": result.model,
        "cost_usd_est": f"{cost:.6f}",
    }

    with log_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_LOG_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


# ── Función principal ──

def locate_predial_llm(
    text: str,
    municipio: str,
    ejercicio: int,
    estado: str,
    log_dir: Path | None = None,
) -> LocatorResult:
    """
    Localiza la sección predial en el texto de una ley usando LLM.

    Args:
        text: Texto completo de la ley de ingresos.
        municipio: Nombre o slug del municipio.
        ejercicio: Año fiscal.
        estado: Slug del estado.
        log_dir: Directorio para guardar log CSV (None = sin log).

    Returns:
        LocatorResult con posiciones de caracteres y confianza.
    """
    if not text.strip():
        return LocatorResult(found=False)

    # Preparar texto con marcadores
    if len(text) <= _MAX_FULL_TEXT_CHARS:
        marked_text = _insert_markers(text)
    else:
        marked_text = _summarize_by_pages(text)

    user_msg = _USER_TEMPLATE.format(
        municipio=municipio,
        ejercicio=ejercicio,
        estado=estado,
        text=marked_text,
    )

    client = _get_client()

    try:
        response = client.chat.completions.create(
            model=LLM_LOCATOR_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.0,
            max_completion_tokens=256,
        )
    except Exception as e:
        print(f"    [locator] Error LLM: {e}")
        return LocatorResult(found=False)

    # Parsear respuesta
    choice = response.choices[0]
    raw = (choice.message.content or "").strip()

    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0

    try:
        # Limpiar posible markdown fence
        clean = re.sub(r"^```(?:json)?\s*", "", raw)
        clean = re.sub(r"\s*```$", "", clean)
        data = json.loads(clean)
    except (json.JSONDecodeError, TypeError):
        print(f"    [locator] JSON inválido: {raw[:100]}")
        result = LocatorResult(
            found=False, model=LLM_LOCATOR_MODEL,
            input_tokens=input_tokens, output_tokens=output_tokens,
        )
        _log_call(log_dir, estado, municipio, ejercicio, result)
        return result

    confidence = float(data.get("confidence", 0.0))
    start_char = _parse_marker(data.get("start_marker", ""))
    end_char = _parse_marker(data.get("end_marker", ""))
    section_title = data.get("section_title", "")

    # Validar posiciones
    found = (
        confidence > 0.0
        and start_char >= 0
        and end_char > start_char
        and end_char <= len(text)
    )

    result = LocatorResult(
        found=found,
        start_char=start_char if found else -1,
        end_char=end_char if found else -1,
        method="llm_locator" if found else "",
        confidence=confidence,
        section_title=section_title,
        model=LLM_LOCATOR_MODEL,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )

    _log_call(log_dir, estado, municipio, ejercicio, result)
    return result
