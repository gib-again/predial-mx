"""
Adaptador de Colima para predial-mx.

10 municipios. Leyes de Hacienda Municipales individuales (Decretos 268-277, 2002).
Tablas de predial idénticas en los 10 municipios para 2010-2025.
Pipeline: genera JSONs directamente desde tarifa hardcoded + series SM/UMA.
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.colima import config


@register
class ColimaAdapter(EstadoAdapter):

    slug = config.ESTADO_SLUG
    prefijo = config.PREFIJO
    estado_nombre = config.ESTADO_NOMBRE
    needs_ocr = config.NEEDS_OCR
    year_min = config.YEAR_MIN
    year_max = config.YEAR_MAX

    def download(self, data_dir: Path | None = None, **kwargs):
        print("Colima: No requiere descarga (tarifa hardcoded de leyes de hacienda municipales).")
        return None

    def build_master(self, data_dir: Path | None = None, **kwargs):
        print("Colima: No requiere master (tarifa uniforme en 10 municipios).")
        return None

    def extract_predial_sections(self, data_dir: Path | None = None, **kwargs):
        print("Colima: No requiere segmentación (tarifa hardcoded).")
        return None

    def run_llm_extraction(self, batch_mode: bool = False, **kwargs):
        """Override: genera JSONs directamente desde tarifa_base, sin LLM."""
        from src.estados.colima.pipeline import run
        return run()

    def run_validation(self, **kwargs):
        """Validación: verifica JSONs y coherencia SM/UMA por año."""
        import json
        json_dir = Path("data/colima/json")
        if not json_dir.exists():
            print("Colima: No hay JSONs. Ejecuta primero --steps extract.")
            return

        count = 0
        errors = 0
        for jf in sorted(json_dir.rglob("*.json")):
            count += 1
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                assert data["cve_ent"] == "06"
                ej = data["ejercicio"]
                p = data["predial"]
                assert p["urbano_edificado"]["n_rangos"] == 26
                assert p["rustico"]["n_rangos"] == 9
                # Verificar unidad correcta por año
                if ej < 2017:
                    assert p["urbano_edificado"]["cuota_fija_unidad"] == "SM_diario"
                else:
                    assert p["urbano_edificado"]["cuota_fija_unidad"] == "UMA_diaria"
            except Exception as e:
                errors += 1
                print(f"  [ERROR] {jf.name}: {e}")

        print(f"  Colima: {count} JSONs verificados, {errors} errores.")
