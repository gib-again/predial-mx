"""
Adaptador de Durango para predial-mx.

39 municipios. Grupo A: la tasa al millar del predial se fija en la Ley de
Ingresos Municipal anual de cada municipio. FASE 1 (2018-2025): fuente = Congreso
del Estado (congresodurango.gob.mx), PDFs digitales individuales por municipio
(sin OCR). FASE 2 (2010-2017, pendiente): gacetas escaneadas del PO con OCR.

Pipeline estandar Grupo A: download (Congreso) -> master -> segment (recorte
predial) -> extract (LLM v3) -> validate (HITL).
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.durango import config


@register
class DurangoAdapter(EstadoAdapter):

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
        from src.estados.durango.download import run_download
        return run_download(self, year=kwargs.get("year"))

    def build_master(self) -> Path:
        from src.estados.durango.segment import run_build_master
        return run_build_master(self)

    def extract_predial_sections(self, **kwargs) -> Path:
        from src.estados.durango.segment import run_extract_sections
        return run_extract_sections(self, year=kwargs.get("year"))
