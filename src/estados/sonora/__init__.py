"""
Adaptador de Sonora para predial-mx.

72 municipios. PDFs del Boletín Oficial publicados en boletines especiales
de finales de diciembre del año N-1 (cada sección romana = 1 municipio).

Pipeline:
  download (scrape índice Joomla + descarga por sección) →
  ocr (adaptativo: solo PDFs con < 300 chars/página promedio) →
  segment (recorte sección predial) →
  extract (LLM con structured output + fallback PDF visión).

Esquema dominante: cuota fija + tasa al millar por rangos de valor catastral
(coexistencia tarifa_millar + progresivo); rústicos por hectárea; UMA desde 2017.
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.sonora import config


@register
class SonoraAdapter(EstadoAdapter):

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
        """Descarga incremental: lee source_documents.csv y baja los faltantes.

        Requiere `discover` previo. El método antiguo `run_download` (descarga
        ciega filtrada por /diciembre/) se mantiene como `run_download_legacy`
        en download.py para retrocompat.
        """
        from src.estados.sonora.download import descargar_documentos_faltantes
        return descargar_documentos_faltantes(self)

    def run_ocr(self, **kwargs):
        """OCR. Soporta:
        - source_csv (preferido v3): solo PDFs en source_documents.csv
        - default: adaptativo por chars/pág
        """
        from src.estados.sonora.ocr import run_ocr
        return run_ocr(
            self,
            year=kwargs.get("year"),
            force_reocr=kwargs.get("force_reocr", False),
            source_csv=kwargs.get("source_csv"),
            clean_watermark=kwargs.get("clean_watermark", False),
            threshold=kwargs.get("threshold"),
            limit=kwargs.get("limit"),
        )

    def discover_leyes(self, **kwargs):
        """Discovery HTML estructurado de todas las leyes en índice anual."""
        from src.estados.sonora.discoverer import descubrir_leyes
        return descubrir_leyes(self)

    def build_master(self) -> Path:
        from src.estados.sonora.segment import run_build_master
        return run_build_master(self)

    def extract_predial_sections(self, **kwargs) -> Path:
        from src.estados.sonora.segment import run_extract_sections
        return run_extract_sections(self, year=kwargs.get("year"))
