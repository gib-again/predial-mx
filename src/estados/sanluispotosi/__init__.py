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

    def download(self, **kwargs) -> Path:
        """
        Pipeline de descarga multi-fuente:

          1. Ruta B: PO con rango ancho (recupera huecos parciales 2012-2020/22).
          2. Ruta A: Congreso del Estado SLP via Playwright (rescata 2010-2011).
          3. Ruta C: Wayback Machine (best effort para IDs irrecuperables).

        Args (kwargs):
            mode (str): "wide" (default, recomendado) o "per_year" (legacy).
            routes (list[str] | None): subconjunto de ["po", "congreso", "wayback"].
                Default: ["po"] solamente. Las otras rutas se invocan de forma
                explícita por el usuario o por el pipeline orquestador.
            target_years (list[int] | None): para Congreso/Wayback, restringir años.
            force_reocr: ignorado en download (solo aplica a OCR).
        """
        from src.estados.sanluispotosi.download import run_download

        mode = kwargs.get("mode", "wide")
        routes = kwargs.get("routes") or ["po"]
        target_years = kwargs.get("target_years")

        last_index = None
        if "po" in routes:
            last_index = run_download(self, mode=mode)

        if "congreso" in routes:
            from src.estados.sanluispotosi.download_congreso import (
                run_download_congreso,
            )
            last_index = run_download_congreso(self, target_years=target_years)

        if "wayback" in routes:
            from src.estados.sanluispotosi.download_wayback import (
                run_download_wayback,
            )
            last_index = run_download_wayback(self, target_years=target_years)

        return last_index or self.meta_dir / "ley_ingresos_index.csv"

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
