"""
Adaptador de Guanajuato para predial-mx.

46 municipios. PDFs del PO obtenidos vía API REST (múltiples PDFs por año).
PDFs frecuentemente escaneados → requiere OCR avanzado (ocrmypdf a 300 DPI).
Esquema dominante: tarifa_millar (tasas al millar por tipo de predio).
Nombre oficial del impuesto: "Impuesto Predial".

Pipeline: download (API) → OCR (ocrmypdf) → segment (2 niveles) → extract (structured output + fallback PDF)

Diferencias con otros estados en la extracción LLM:
  - Structured output (JSON Schema enforced) para garantizar formato
  - Fallback progresivo: TXT primero → si inválido, PDF vía visión (+1 página)
  - PDFs híbridos: texto digital + tablas imagen → OCR solo con flags seguros
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.guanajuato import config


@register
class GuanajuatoAdapter(EstadoAdapter):

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
        """Descarga PDFs del PO vía API REST."""
        from src.estados.guanajuato.download import run_download
        return run_download(self)

    def build_master(self) -> Path:
        """
        En Guanajuato, 'build_master' = ejecutar OCR.
        Los PDFs crudos son escaneos → necesitan OCR antes de segmentar.
        """
        from src.estados.guanajuato.ocr import run_ocr
        return run_ocr(self)

    def run_ocr(self):
        """OCR adaptativo con ocrmypdf (skip + force)."""
        from src.estados.guanajuato.ocr import run_ocr
        return run_ocr(self)

    def extract_predial_sections(self) -> Path:
        """Segmentación en 2 niveles: localizar leyes → extraer predial."""
        from src.estados.guanajuato.segment import run_segment
        return run_segment(self)
        
    def audit_pre_consolidation(self):
        """Auditoría pre-consolidación: identifica JSONs que requieren revisión manual."""
        from src.core.audit import run_audit
        run_audit(self.json_dir, self.prefijo, self.qa_dir, self.meta_dir)
        