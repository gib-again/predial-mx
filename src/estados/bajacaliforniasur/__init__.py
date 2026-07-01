"""
Adaptador de Baja California Sur para predial-mx.

5 municipios. Caso atipico: el predial NO esta en una ley anual sino en la
**Ley de Hacienda Municipal** (una por municipio, tasas diferenciadas al millar
por tipo de predio + minimo en UMA/SM). Fuente: Word digital (sin OCR) de
cbcs.gob.mx (vigente) y ordenjuridico.gob.mx (baseline ~2009).

Pipeline (hardcoded versionado):
  download  -> baja las 10 Leyes de Hacienda (5 munis x 2 versiones)
  segment   -> escribe focus_predial/{anio}/ (texto predial de la version vigente)
               + segment.csv canonico (80 filas)
  extract   -> build.run_build: extrae las ~8 versiones unicas (LLM v3
               tasas_diferenciadas) y expande version->anios -> json_predial/

Esquema dominante: tasas_diferenciadas. Transiciones: Loreto FY2022 (firme);
Los Cabos / Mulege con anio placeholder marcado para revision HITL.
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.bajacaliforniasur import config


@register
class BajacaliforniasurAdapter(EstadoAdapter):

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
        from src.estados.bajacaliforniasur.download import run_download
        return run_download(self, force=kwargs.get("force", False))

    def build_master(self) -> Path:
        # No hay "master" de PDFs; la fuente son las Leyes de Hacienda versionadas.
        from src.estados.bajacaliforniasur.leyes import LEYES_DIR
        return LEYES_DIR

    def extract_predial_sections(self, **kwargs) -> Path:
        from src.estados.bajacaliforniasur.segment import run_segment
        return run_segment(self, year=kwargs.get("year"))

    def run_llm_extraction(self, batch_mode: bool = False, force: bool = False, **kwargs):
        """BCS no extrae por-anio: extrae versiones unicas y expande (build)."""
        from src.estados.bajacaliforniasur.build import run_build
        return run_build(self, force=force)
