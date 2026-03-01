"""
Adaptador de Jalisco para el pipeline de extracción de predial.

Pipeline: download (API) → OCR (ocrmypdf) → master (locate) → segment (extract) → LLM → validate

Diferencias con Coahuila:
  - Download via REST API (no HTML scraping)
  - OCR obligatorio (ocrmypdf con 2 pasadas)
  - Master = locate sections (por página, no por offset)
  - Segment = extract (recortar PDF/TXT)
  - PDFs individuales por municipio-año (no tomos compartidos)
"""

from pathlib import Path

from src.estados.base import EstadoAdapter
from src.estados import register
from src.estados.jalisco.config import (
    ESTADO_SLUG,
    PREFIJO,
    ESTADO_NOMBRE,
    NEEDS_OCR,
    YEAR_MIN,
    YEAR_MAX,
)


@register
class JaliscoAdapter(EstadoAdapter):

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
        from src.estados.jalisco.download import run_download
        return run_download(self)

    def build_master(self) -> Path:
        """En Jalisco, 'master' = localizar secciones de predial en cada PDF."""
        from src.estados.jalisco.segment import run_locate_sections
        return run_locate_sections(self)

    def extract_predial_sections(self) -> Path:
        """Recorta PDF + extrae TXT de las secciones localizadas."""
        from src.estados.jalisco.segment import run_extract_sections
        return run_extract_sections(self)

    def run_ocr(self):
        """OCR con ocrmypdf (skip + force)."""
        from src.estados.jalisco.ocr import run_ocr
        return run_ocr(self)
