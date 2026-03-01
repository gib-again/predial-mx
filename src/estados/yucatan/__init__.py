"""
Adaptador de Yucatán para el pipeline de extracción de predial.

Pipeline: download (índices+diarios DO) → master (segmentar leyes) → segment (predial) → LLM → validate

Diferencias con otros estados:
  - Download: parsea índices anuales del DO, descarga diarios por fecha
  - No necesita OCR (PDFs digitales con texto nativo)
  - Master = segmentar tomos en leyes individuales por municipio (regex encabezados)
  - Segment = localizar sección predial dentro de cada ley
  - Usa PyMuPDF (fitz) en lugar de pdfplumber
"""

from pathlib import Path

from src.estados.base import EstadoAdapter
from src.estados import register
from src.estados.yucatan.config import (
    ESTADO_SLUG,
    PREFIJO,
    ESTADO_NOMBRE,
    NEEDS_OCR,
    YEAR_MIN,
    YEAR_MAX,
)


@register
class YucatanAdapter(EstadoAdapter):

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
        from src.estados.yucatan.download import run_download
        return run_download(self)

    def build_master(self) -> Path:
        """Segmenta diarios del DO en leyes individuales por municipio."""
        from src.estados.yucatan.segment import run_build_master
        return run_build_master(self)

    def extract_predial_sections(self) -> Path:
        """Localiza sección predial dentro de cada ley y genera TXT + PDF."""
        from src.estados.yucatan.segment import run_extract_sections
        return run_extract_sections(self)
