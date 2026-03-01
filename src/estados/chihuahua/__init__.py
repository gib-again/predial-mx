"""
Adaptador de Chihuahua para predial-mx.

67 municipios. Tarifa estatal uniforme (Código Municipal, Arts. 148-149).
No requiere descarga de PDFs, OCR ni segmentación.
Pipeline: genera JSONs directamente desde tarifa hardcoded.
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.chihuahua import config


@register
class ChihuahuaAdapter(EstadoAdapter):

    slug = config.ESTADO_SLUG
    prefijo = config.PREFIJO
    estado_nombre = config.ESTADO_NOMBRE
    needs_ocr = config.NEEDS_OCR
    year_min = config.YEAR_MIN
    year_max = config.YEAR_MAX

    # ── Chihuahua usa tarifa estatal uniforme ─────────────────
    # No hay PDFs que descargar ni segmentar.
    # Los pasos download, master, segment son no-ops.
    # extract genera JSONs directamente desde tarifa_base.py.

    def download(self, data_dir: Path | None = None, **kwargs):
        print("Chihuahua: No requiere descarga (tarifa estatal del Código Municipal).")
        return None

    def build_master(self, data_dir: Path | None = None, **kwargs):
        print("Chihuahua: No requiere master (tarifa estatal uniforme).")
        return None

    def extract_predial_sections(self, data_dir: Path | None = None, **kwargs):
        print("Chihuahua: No requiere segmentación (tarifa hardcoded).")
        return None

    def run_llm_extraction(self, batch_mode: bool = False, **kwargs):
        """Override: genera JSONs directamente desde tarifa_base, sin LLM."""
        from src.estados.chihuahua.pipeline import run
        return run()

    def run_validation(self, **kwargs):
        """Validación: verifica que los JSONs existan y sean consistentes."""
        json_dir = Path("data/chihuahua/json")
        if not json_dir.exists():
            print("Chihuahua: No hay JSONs. Ejecuta primero --steps extract.")
            return

        import json
        count = 0
        errors = 0
        for jf in sorted(json_dir.rglob("*.json")):
            count += 1
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                assert data["cve_ent"] == "08"
                assert data["predial"]["urbano"]["n_rangos"] == 5
            except Exception as e:
                errors += 1
                print(f"  [ERROR] {jf.name}: {e}")

        print(f"  Chihuahua: {count} JSONs verificados, {errors} errores.")