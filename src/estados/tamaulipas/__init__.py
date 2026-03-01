"""
Adaptador de Tamaulipas para predial-mx.

43 municipios. PDFs consolidados del PO (uno por año).
Esquema dominante: tarifa_millar (tasas al millar por tipo de predio).
Nombre oficial del impuesto: "Impuesto Sobre la Propiedad Urbana, Suburbana y Rústica".
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.tamaulipas import config


@register
class TamaulipasAdapter(EstadoAdapter):

    slug = config.ESTADO_SLUG
    prefijo = config.PREFIJO
    estado_nombre = config.ESTADO_NOMBRE
    needs_ocr = config.NEEDS_OCR
    year_min = config.YEAR_MIN
    year_max = config.YEAR_MAX

    def download(self, data_dir: Path | None = None, **kwargs):
        from src.estados.tamaulipas.download import download_all
        d = data_dir or Path("data/tamaulipas")
        return download_all(data_dir=d, **kwargs)

    def build_master(self, data_dir: Path | None = None, **kwargs):
        # Tamaulipas no necesita master separado: el PDF consolidado
        # ya contiene todas las leyes. segment_all hace ambos niveles.
        print("Tamaulipas: build_master no es necesario (PDF consolidado).")
        return

    def extract_predial_sections(self, data_dir: Path | None = None, **kwargs):
        from src.estados.tamaulipas.segment import segment_all
        d = data_dir or Path("data/tamaulipas")
        return segment_all(data_dir=d, **kwargs)
