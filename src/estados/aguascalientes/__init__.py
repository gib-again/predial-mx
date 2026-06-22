"""
Adaptador de Aguascalientes para predial-mx.

11 municipios.  PDFs del PO obtenidos via API JSON (cada PDF = una ley municipal).
PDFs digitales con texto extraible (sin OCR).
Nombre oficial del impuesto: "Impuesto sobre la Propiedad Raiz" o "Impuesto Predial".

Pipeline: download (API JSON) -> segment (predial section) -> extract (LLM v3)
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.aguascalientes import config


@register
class AguascalientesAdapter(EstadoAdapter):

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
        from src.estados.aguascalientes.download import run_download
        return run_download(self)

    def build_master(self) -> Path:
        return self.meta_dir / "catalogo_leyes.csv"

    def extract_predial_sections(self, **kwargs) -> Path:
        from src.estados.aguascalientes.segment import run_segment
        return run_segment(self, **kwargs)
