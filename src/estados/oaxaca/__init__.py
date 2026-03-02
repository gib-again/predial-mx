"""
Adaptador de Oaxaca para predial-mx.

570 municipios. PDFs del PO obtenidos vía búsqueda HTML + descarga directa.
Múltiples PDFs por año, publicados durante todo el año (no solo enero/febrero).
PDFs con marca de agua "DOCUMENTO SOLO PARA CONSULTA" → requiere OCR obligatorio.
Formato dos columnas, orientación variable (portrait/landscape).

Esquema predial dominante: tasa_unica (0.5% anual sobre valor catastral)
con mínimos en UMA por tipo de suelo y cuotas por m² para fraccionamiento.

Pipeline: download (HTML) → OCR (ocrmypdf) → segment (2 niveles) → extract (structured output + fallback PDF)

Diferencias con Guanajuato:
  - 570 municipios (vs 46): catálogo de municipios dinámico, no hardcodeado.
  - Estructura PDF: año/mes/filename (vs solo año).
  - Marca de agua pesada que degrada OCR → mayor dependencia de PDF vision fallback.
  - Publicación durante todo el año (no solo enero-febrero).
  - Sección predial usa "Sección Primera/Única. Predial" (patrón distinto).
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.oaxaca import config


@register
class OaxacaAdapter(EstadoAdapter):

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
        """Descarga PDFs del PO vía búsqueda HTML + descarga directa."""
        from src.estados.oaxaca.download import run_download
        return run_download(self)

    def build_master(self) -> Path:
        """
        En Oaxaca, 'build_master' = ejecutar OCR.
        Los PDFs con marca de agua necesitan OCR antes de segmentar.
        """
        from src.estados.oaxaca.ocr import run_ocr
        return run_ocr(self)

    def run_ocr(self):
        """OCR con ocrmypdf (force-ocr para watermark)."""
        from src.estados.oaxaca.ocr import run_ocr
        return run_ocr(self)

    def extract_predial_sections(self) -> Path:
        """Segmentación en 2 niveles: localizar leyes → extraer predial."""
        from src.estados.oaxaca.segment import run_segment
        return run_segment(self)
