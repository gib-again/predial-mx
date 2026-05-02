"""
Adaptador de San Luis Potosí para predial-mx.

58 municipios. PDFs del PO obtenidos vía API JSON pública (1 PDF = 1 ley
municipal completa). PDFs nativos con texto seleccionable → no requiere OCR.

Pipeline: download (API) → master (inventario) → segment (recorte predial)
          → extract (LLM con structured output + fallback PDF visión).

Esquema dominante: tarifa_millar (tasas al millar anual sobre valor catastral),
en algunos años con cuota mínima en SMGZ (pre-2016) o UMA (post-2016).
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.sanluispotosi import config


@register
class SanluispotosiAdapter(EstadoAdapter):

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

    def download(self) -> Path:
        from src.estados.sanluispotosi.download import run_download
        return run_download(self)

    def run_ocr(self, **kwargs):
        """OCR adaptativo: sólo procesa PDFs escaneados (chars/pág < threshold)."""
        from src.estados.sanluispotosi.ocr import run_ocr
        return run_ocr(
            self,
            year=kwargs.get("year"),
            force_reocr=kwargs.get("force_reocr", False),
        )

    def build_master(self) -> Path:
        from src.estados.sanluispotosi.segment import run_build_master
        return run_build_master(self)

    def extract_predial_sections(self, **kwargs) -> Path:
        from src.estados.sanluispotosi.segment import run_extract_sections
        return run_extract_sections(self, year=kwargs.get("year"))
