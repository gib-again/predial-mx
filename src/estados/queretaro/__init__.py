"""
Adaptador de Querétaro para el pipeline de extracción de predial.

Pipeline: download (índices+PDFs) → master (detect munis) → segment (predial pages) → LLM → validate

Diferencias con otros estados:
  - Download: parsea índices del PO "La Sombra de Arteaga", genera URLs por template
  - No necesita OCR (PDFs digitales)
  - Master = detectar inicio de leyes municipales en tomos compartidos
  - Segment = scoring de páginas + focus con anclas de tabla
  - Originalmente se extraían tablas manualmente (scripts 75); ahora usa LLM batch
"""

from pathlib import Path

from src.estados.base import EstadoAdapter
from src.estados import register
from src.estados.queretaro.config import (
    ESTADO_SLUG,
    PREFIJO,
    ESTADO_NOMBRE,
    NEEDS_OCR,
    YEAR_MIN,
    YEAR_MAX,
)


@register
class QueretaroAdapter(EstadoAdapter):

    @property
    def slug(self) -> str:
        return ESTADO_SLUG

    @property
    def prefijo(self) -> str:
        return PREFIJO

    @property
    def estado_nombre(self) -> str:
        return ESTADO_NOMBRE

    @property
    def needs_ocr(self) -> bool:
        return NEEDS_OCR

    @property
    def ejercicio_range(self) -> range:
        return range(YEAR_MIN, YEAR_MAX + 1)

    def download(self) -> Path:
        from src.estados.queretaro.download import run_download
        return run_download(self)

    def build_master(self) -> Path:
        """Detecta inicio de leyes municipales en los PDFs descargados."""
        from src.estados.queretaro.segment import run_build_master
        return run_build_master(self)

    def extract_predial_sections(self) -> Path:
        """Localiza y extrae sección de predial por scoring + anclas."""
        from src.estados.queretaro.segment import run_extract_sections
        return run_extract_sections(self)
