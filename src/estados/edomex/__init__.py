"""
Adaptador del Estado de México para predial-mx.

125 municipios. Código Financiero del Estado de México y Municipios, Art. 109.
Tarifa uniforme estatal con 13 rangos progresivos, cuota fija en pesos nominales.
Dos periodos: tabla 2009 (ejercicio 2010), tabla 2010 (ejercicios 2011-2025).
"""

from pathlib import Path

from src.estados import register
from src.estados.base import EstadoAdapter
from src.estados.edomex import config


@register
class EdoMexAdapter(EstadoAdapter):

    slug = config.ESTADO_SLUG
    prefijo = config.PREFIJO
    estado_nombre = config.ESTADO_NOMBRE
    needs_ocr = config.NEEDS_OCR
    year_min = config.YEAR_MIN
    year_max = config.YEAR_MAX

    def download(self, data_dir: Path | None = None, **kwargs):
        print("EdoMex: No requiere descarga (tarifa hardcoded del Código Financiero).")
        return None

    def build_master(self, data_dir: Path | None = None, **kwargs):
        print("EdoMex: No requiere master (tarifa uniforme en 125 municipios).")
        return None

    def extract_predial_sections(self, data_dir: Path | None = None, **kwargs):
        print("EdoMex: No requiere segmentación (tarifa hardcoded).")
        return None

    def run_llm_extraction(self, batch_mode: bool = False, **kwargs):
        """Override: genera JSONs directamente desde tarifa_base, sin LLM."""
        from src.estados.edomex.pipeline import run
        return run()

    def run_validation(self, **kwargs):
        """Validación: verifica JSONs y coherencia de tabla por ejercicio."""
        import json
        json_dir = Path("data/edomex/json")
        if not json_dir.exists():
            print("EdoMex: No hay JSONs. Ejecuta primero --steps extract.")
            return

        count = 0
        errors = 0
        for jf in sorted(json_dir.rglob("*.json")):
            count += 1
            try:
                data = json.loads(jf.read_text(encoding="utf-8"))
                assert data["cve_ent"] == "15"
                ej = data["ejercicio"]
                p = data["predial"]
                assert p["n_rangos"] == 13

                # Verificar cuota fija del rango 1 según periodo
                r1_cuota = p["rangos"][0]["cuota_fija_pesos"]
                if ej <= 2010:
                    assert r1_cuota == 150.00, f"Rango 1 cuota 2010: esperado 150, got {r1_cuota}"
                else:
                    assert r1_cuota == 170.00, f"Rango 1 cuota 2011+: esperado 170, got {r1_cuota}"

                # Verificar tasa baldíos
                baldio = p["baldio_urbano_mayor_200m2"]
                if ej >= 2017:
                    assert baldio["aplica"] is True
                    assert baldio["tasa_adicional"] == 0.15
                else:
                    assert baldio["aplica"] is False

            except Exception as e:
                errors += 1
                print(f"  [ERROR] {jf.name}: {e}")

        print(f"  EdoMex: {count} JSONs verificados, {errors} errores.")
