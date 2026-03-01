"""
Adaptador de Sinaloa para predial-mx.

18 municipios. Ley de Hacienda Municipal del Estado de Sinaloa, Art. 35-36.
Tarifa uniforme estatal con 11 rangos, actualización anual por INPC.
Columnas separadas para predios construidos y baldíos.
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.sinaloa import config


@register
class SinaloaAdapter(EstadoAdapter):

    slug = config.ESTADO_SLUG
    prefijo = config.PREFIJO
    estado_nombre = config.ESTADO_NOMBRE
    needs_ocr = config.NEEDS_OCR
    year_min = config.YEAR_MIN
    year_max = config.YEAR_MAX

    def download(self, data_dir: Path | None = None, **kwargs):
        print("Sinaloa: No requiere descarga (tarifa hardcoded + INPC).")
        return None

    def build_master(self, data_dir: Path | None = None, **kwargs):
        print("Sinaloa: No requiere master (tarifa uniforme en 18 municipios).")
        return None

    def extract_predial_sections(self, data_dir: Path | None = None, **kwargs):
        print("Sinaloa: No requiere segmentación (tarifa hardcoded).")
        return None

    def run_llm_extraction(self, batch_mode: bool = False, **kwargs):
        """Override: genera JSONs desde tarifa_base actualizada por INPC."""
        from src.estados.sinaloa.pipeline import run
        return run()

    def run_validation(self, **kwargs):
        """Validación: verifica JSONs, coherencia de factores y tablas publicadas."""
        import json
        json_dir = Path("data/sinaloa/json")
        if not json_dir.exists():
            print("Sinaloa: No hay JSONs. Ejecuta primero --steps extract.")
            return

        # Published verification data (R1 lim_sup from PDFs)
        published_r1_sup = {
            2010: 32_082.79,
            2014: 37_386.51,
            2015: 38_944.70,
            2016: 39_807.25,
            2017: 41_123.00,
            2019: 45_919.55,
        }

        count = 0
        errors = 0
        for jf in sorted(json_dir.rglob("*.json")):
            count += 1
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                assert data["cve_ent"] == "25"
                ej = data["ejercicio"]
                p = data["predial"]["urbano"]
                assert p["n_rangos"] == 11

                # Verify against published table if available
                if ej in published_r1_sup:
                    computed = p["rangos"][0]["lim_sup"]
                    expected = published_r1_sup[ej]
                    diff = abs(computed - expected)
                    if diff > 1.0:  # Allow <$1 rounding
                        raise AssertionError(
                            f"R1 lim_sup: computed={computed}, "
                            f"published={expected}, diff={diff:.2f}"
                        )

                # Verify tasas don't change
                assert p["rangos"][0]["tasa_construido_millar"] == 2.50
                assert p["rangos"][-1]["tasa_construido_millar"] == 6.57
                assert p["rangos"][0]["tasa_baldio_millar"] == 4.50
                assert p["rangos"][-1]["tasa_baldio_millar"] == 9.07

            except Exception as e:
                errors += 1
                print(f"  [ERROR] {jf.name}: {e}")

        print(f"  Sinaloa: {count} JSONs verificados, {errors} errores.")
