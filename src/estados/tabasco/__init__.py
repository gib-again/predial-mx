"""
Adaptador de Tabasco para predial-mx.

17 municipios. Ley de Hacienda Municipal del Estado de Tabasco, Art. 94.
Tarifa uniforme estatal: 5 rangos progresivos, cuota fija en pesos nominales.
Tabla sin cambios 2010-2025. Única variación: mínimo SM→UMA en 2017.
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.tabasco import config


@register
class TabascoAdapter(EstadoAdapter):

    slug = config.ESTADO_SLUG
    prefijo = config.PREFIJO
    estado_nombre = config.ESTADO_NOMBRE
    needs_ocr = config.NEEDS_OCR
    year_min = config.YEAR_MIN
    year_max = config.YEAR_MAX

    def download(self, data_dir: Path | None = None, **kwargs):
        print("Tabasco: No requiere descarga (tarifa hardcoded de Ley de Hacienda Municipal).")
        return None

    def build_master(self, data_dir: Path | None = None, **kwargs):
        print("Tabasco: No requiere master (tarifa uniforme en 17 municipios).")
        return None

    def extract_predial_sections(self, data_dir: Path | None = None, **kwargs):
        print("Tabasco: No requiere segmentación (tarifa hardcoded).")
        return None

    def run_llm_extraction(self, batch_mode: bool = False, **kwargs):
        """Override: genera JSONs directamente desde tarifa_base."""
        from src.estados.tabasco.pipeline import run
        return run()

    def run_validation(self, **kwargs):
        """Validación: verifica JSONs y coherencia de mínimos por año."""
        import json
        json_dir = Path("data/tabasco/json")
        if not json_dir.exists():
            print("Tabasco: No hay JSONs. Ejecuta primero --steps extract.")
            return

        count = 0
        errors = 0
        for jf in sorted(json_dir.rglob("*.json")):
            count += 1
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                assert data["cve_ent"] == "27"
                ej = data["ejercicio"]
                p = data["predial"]
                assert p["n_rangos"] == 5

                # Tabla no cambia: verificar cuotas fijas
                assert p["rangos"][0]["cuota_fija_pesos"] == 0.00
                assert p["rangos"][1]["cuota_fija_pesos"] == 70.00
                assert p["rangos"][4]["cuota_fija_pesos"] == 610.00

                # Verificar unidad de mínimo
                minimo = p["minimo_anual"]
                if ej < 2017:
                    assert minimo["unidad"] == "SM_diario"
                else:
                    assert minimo["unidad"] == "UMA_diaria"

                # Verificar que mínimo urbano > mínimo rústico
                assert minimo["urbano_pesos"] > minimo["rustico_pesos"]

            except Exception as e:
                errors += 1
                print(f"  [ERROR] {jf.name}: {e}")

        print(f"  Tabasco: {count} JSONs verificados, {errors} errores.")
