"""
Adaptador de Baja California para predial-mx.

7 municipios. PDFs del PO via API JSON del indice full-text (1 PDF = 1 ley
municipal, una seccion del tomo de fin de anio). PDFs grandes (incluyen Tabla
de Valores Catastrales); escaneos 2010-2022 (OCR page-limited), nativos 2023+.

Pipeline: download (API indice) -> ocr (adaptativo, primeras pp) -> master
          (inventario) -> segment (recorte predial) -> extract (LLM v3).

Esquema dominante: tasas_diferenciadas (sobretasas "al millar" por tipo de
predio) con minimo en UMA; la tasa base remite a la Ley de Hacienda Municipal.
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.bajacalifornia import config


@register
class BajacaliforniaAdapter(EstadoAdapter):

    @property
    def slug(self) -> str:
        return config.ESTADO_SLUG

    @property
    def prefijo(self) -> str:
        return config.PREFIJO

    @property
    def estado_nombre(self) -> str:
        return config.ESTADO_NOMBRE

    @property
    def needs_ocr(self) -> bool:
        return config.NEEDS_OCR

    @property
    def ejercicio_range(self) -> range:
        return range(config.YEAR_MIN, config.YEAR_MAX + 1)

    def download(self, **kwargs) -> Path:
        from src.estados.bajacalifornia.download import run_download
        return run_download(self)

    def run_ocr(self, **kwargs):
        """OCR adaptativo + page-limited: solo escaneos, primeras pp."""
        from src.estados.bajacalifornia.ocr import run_ocr
        return run_ocr(
            self,
            year=kwargs.get("year"),
            force_reocr=kwargs.get("force_reocr", False),
        )

    def build_master(self) -> Path:
        from src.estados.bajacalifornia.segment import run_build_master
        return run_build_master(self)

    def extract_predial_sections(self, **kwargs) -> Path:
        from src.estados.bajacalifornia.segment import run_extract_sections
        return run_extract_sections(self, year=kwargs.get("year"))
