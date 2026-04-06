"""
Utilidades compartidas para localizar la sección de predial dentro de una ley.

Cada estado maneja el Nivel 1 (localizar cada ley en el PDF). Este módulo
resuelve el Nivel 2: dado el texto de una ley, encontrar dónde empieza
y termina la sección del impuesto predial.

Uso:
    from src.core.segment_utils import find_predial_section, PatternSpec

    result = find_predial_section(
        text=law_text,
        start_specs=[PatternSpec(re.compile(r"..."), "seccion_predial"), ...],
        end_specs=[PatternSpec(re.compile(r"..."), "seccion_segunda"), ...],
        blacklist_patterns=[re.compile(r"FACILIDADES", re.I)],
        max_chars=15_000,
        fallback_chars=30_000,
    )
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable


@dataclass
class PatternSpec:
    """Especificación de un patrón de búsqueda con su etiqueta."""
    pattern: re.Pattern
    label: str


@dataclass
class SegmentResult:
    """Resultado de localizar la sección predial."""
    found: bool
    method: str = ""
    start_char: int = -1
    end_char: int = -1
    confidence: float = 0.0


def find_predial_section(
    text: str,
    start_specs: list[PatternSpec],
    end_specs: list[PatternSpec],
    blacklist_patterns: list[re.Pattern] | None = None,
    context_validator: Callable[[str, re.Match, str], bool] | None = None,
    max_chars: int = 15_000,
    min_chars: int = 200,
    fallback_chars: int = 0,
    min_end_distance: int = 200,
    blacklist_context_chars: int = 800,
    llm_fallback: bool = False,
    llm_context: dict | None = None,
) -> SegmentResult:
    """
    Localiza la sección predial dentro del texto de una ley de ingresos.

    Args:
        text: Texto completo de la ley.
        start_specs: Patrones de inicio ordenados por prioridad. Se prueban
            en orden; para cada patrón se itera con finditer y se valida.
        end_specs: Patrones de fin. Se busca el match más cercano después
            del inicio (respetando min_end_distance).
        blacklist_patterns: Si alguno matchea en los N chars antes del inicio,
            se descarta ese match de inicio.
        context_validator: Función opcional (text, match, method) → bool.
            Permite validación específica por estado (ej: verificar que
            "Artículo" aparezca dentro de 300 chars después del match).
        max_chars: Si no se encuentra fin, se limita a estos chars desde inicio.
        min_chars: Segmento mínimo aceptable.
        fallback_chars: Si > 0, y no se encuentra inicio, retorna los primeros
            N chars como fallback.
        min_end_distance: Ignora matches de fin que estén muy cerca del inicio.
        blacklist_context_chars: Cuántos chars antes del match revisar para blacklist.
        llm_fallback: Si True, intenta localizar vía LLM (gpt-4.1-mini) cuando
            los patrones regex fallan, antes de recurrir al fallback ciego.
        llm_context: Dict con claves {municipio, ejercicio, estado, log_dir}
            requerido si llm_fallback=True. Se pasa a locate_predial_llm().

    Returns:
        SegmentResult con posiciones y método usado.
    """
    if not text or not start_specs:
        if fallback_chars > 0:
            end = min(fallback_chars, len(text))
            return SegmentResult(
                found=True, method="fallback", start_char=0,
                end_char=end, confidence=0.3,
            )
        return SegmentResult(found=False)

    blacklist_patterns = blacklist_patterns or []

    # ── Buscar inicio ──
    start_pos = None
    method = ""

    for spec in start_specs:
        for m in spec.pattern.finditer(text):
            pos = m.start()

            # Blacklist: revisar contexto previo
            ctx_start = max(0, pos - blacklist_context_chars)
            context_before = text[ctx_start:pos]
            if any(bp.search(context_before) for bp in blacklist_patterns):
                continue

            # Context validator (estado-específico)
            if context_validator and not context_validator(text, m, spec.label):
                continue

            start_pos = pos
            method = spec.label
            break

        if start_pos is not None:
            break

    # ── Sin inicio → LLM fallback → blind fallback → fallo ──
    if start_pos is None:
        # Intentar localización LLM si está habilitada
        if llm_fallback and llm_context:
            from src.core.llm_locator import locate_predial_llm

            loc = locate_predial_llm(
                text=text,
                municipio=llm_context.get("municipio", ""),
                ejercicio=llm_context.get("ejercicio", 0),
                estado=llm_context.get("estado", ""),
                log_dir=llm_context.get("log_dir"),
            )
            if loc.found and loc.confidence >= 0.6:
                return SegmentResult(
                    found=True,
                    method="llm_locator",
                    start_char=loc.start_char,
                    end_char=loc.end_char,
                    confidence=min(loc.confidence, 0.8),
                )

        if fallback_chars > 0:
            end = min(fallback_chars, len(text))
            return SegmentResult(
                found=True, method="fallback",
                start_char=0, end_char=end, confidence=0.3,
            )
        return SegmentResult(found=False)

    # ── Buscar fin ──
    end_pos = None
    remaining = text[start_pos:]

    candidates: list[int] = []
    for spec in end_specs:
        em = spec.pattern.search(remaining)
        if em and em.start() > min_end_distance:
            candidates.append(start_pos + em.start())

    if candidates:
        end_pos = min(candidates)
    else:
        end_pos = min(start_pos + max_chars, len(text))

    # Validar tamaño mínimo
    if end_pos - start_pos < min_chars:
        end_pos = min(start_pos + max_chars, len(text))

    return SegmentResult(
        found=True,
        method=method,
        start_char=start_pos,
        end_char=end_pos,
        confidence=1.0 if method != "fallback" else 0.3,
    )
