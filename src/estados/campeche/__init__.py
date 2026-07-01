"""
Adaptador de Campeche para predial-mx.

13 municipios. Grupo B diferenciado: el predial vive en la **Ley de Hacienda de
los Municipios del Estado de Campeche** (un solo documento estatal, Art. 26 =
tabla de tarifas por municipio y uso de suelo, en porcentaje). PDF digital
(sin OCR). El minimo/descuentos/exenciones viven en la Ley de Ingresos anual.

Pipeline (hardcoded versionado, como BCS pero un solo documento por version):
  download  -> baja las versiones de la Ley de Hacienda (baseline_2010, actual_2022)
  segment   -> focus_predial/{anio}/ (bloque de tarifa del municipio segun la
               version vigente) + segment.csv canonico
  extract   -> build.run_build: extrae los bloques unicos (LLM v3
               tasas_diferenciadas, porcentaje) y expande version->anios.

Esquema: tasas_diferenciadas (porcentaje). Tasas mayormente estables; unico
cambio Carmen FY2016 (Decreto 30). Seybaplaya/Dzitbalche nuevos (~2021, HITL).
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.campeche import config


@register
class CampecheAdapter(EstadoAdapter):

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
        from src.estados.campeche.download import run_download
        return run_download(self, force=kwargs.get("force", False))

    def build_master(self) -> Path:
        return Path("data") / config.ESTADO_SLUG / "leyes_hacienda"

    def extract_predial_sections(self, **kwargs) -> Path:
        from src.estados.campeche.segment import run_segment
        return run_segment(self, year=kwargs.get("year"))

    def run_llm_extraction(self, batch_mode: bool = False, force: bool = False, **kwargs):
        """Campeche no extrae por-anio: extrae bloques unicos y expande (build)."""
        from src.estados.campeche.build import run_build
        return run_build(self, force=force)
