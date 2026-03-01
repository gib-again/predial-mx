"""
Adaptador de Coahuila para el pipeline de extracción de predial.

Implementa los métodos abstractos de EstadoAdapter:
  - download()                  → Scraping del PO (ASP + DataTables)
  - build_master()              → Master CSV con patch 2017
  - extract_predial_sections()  → Localización de sección predial
"""

from pathlib import Path

from src.estados.base import EstadoAdapter
from src.estados import register
from src.estados.coahuila.config import (
    ESTADO_SLUG,
    PREFIJO,
    ESTADO_NOMBRE,
    NEEDS_OCR,
)
from src.core.constants import EJERCICIO_INI, EJERCICIO_FIN


@register
class CoahuilaAdapter(EstadoAdapter):

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
        return range(EJERCICIO_INI, EJERCICIO_FIN + 1)

    def download(self) -> Path:
        from src.estados.coahuila.download import run_download
        return run_download(self)

    def build_master(self) -> Path:
        from src.estados.coahuila.segment import run_build_master
        return run_build_master(self)

    def extract_predial_sections(self) -> Path:
        from src.estados.coahuila.segment import run_extract_sections
        return run_extract_sections(self)
