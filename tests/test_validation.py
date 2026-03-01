"""Tests para src/core/validation.py"""

from src.core.validation import check_predial_structure, apply_interanual_rules


class TestCheckPredialStructure:
    """Validaciones estructurales de un JSON de predial."""

    def test_valid_tarifa_millar(self):
        predial = {
            "tipo_esquema": "tarifa_millar",
            "esquema_valido": True,
            "comentarios": "",
            "tabla_tarifa_millar": [
                {"grupo": "urbano", "clave": "urb", "descripcion": "Predios urbanos",
                 "tasa_millar": 2.3, "cuota_fija": 0.0}
            ],
            "tabla_progresiva": [],
            "tabla_tasa_unica": [],
            "tabla_cuota_fija": [],
        }
        result = check_predial_structure(predial)
        assert result["anomalias"] == []
        assert result["n_tarifa_rows"] == 1

    def test_tarifa_millar_sin_filas(self):
        predial = {
            "tipo_esquema": "tarifa_millar",
            "esquema_valido": True,
            "comentarios": "",
            "tabla_tarifa_millar": [],
            "tabla_progresiva": [],
        }
        result = check_predial_structure(predial)
        assert "tipo_tarifa_millar_sin_filas" in result["anomalias"]

    def test_progresivo_con_tarifa_no_vacia(self):
        predial = {
            "tipo_esquema": "progresivo",
            "esquema_valido": True,
            "comentarios": "",
            "tabla_tarifa_millar": [{"grupo": "x", "clave": "x", "descripcion": "x",
                                     "tasa_millar": 1.0, "cuota_fija": 0}],
            "tabla_progresiva": [{"n_rango": "1", "inferior": "$0.01",
                                  "superior": "$100,000.00", "cuota_fija": "$10.00",
                                  "tasa_marginal": "0.001"}],
        }
        result = check_predial_structure(predial)
        assert "tipo_progresivo_con_tabla_tarifa_no_vacia" in result["anomalias"]

    def test_tipo_esquema_invalido(self):
        predial = {
            "tipo_esquema": "inventado",
            "esquema_valido": True,
        }
        result = check_predial_structure(predial)
        assert "tipo_esquema_invalido" in result["anomalias"]

    def test_esquema_valido_no_bool(self):
        predial = {
            "tipo_esquema": "tarifa_millar",
            "esquema_valido": "si",
            "tabla_tarifa_millar": [{"grupo": "g", "clave": "c", "descripcion": "d",
                                     "tasa_millar": 1.0, "cuota_fija": 0}],
        }
        result = check_predial_structure(predial)
        assert "esquema_valido_no_bool" in result["anomalias"]

    def test_desconocido_con_tablas(self):
        predial = {
            "tipo_esquema": "desconocido",
            "esquema_valido": False,
            "comentarios": "ambiguo",
            "tabla_tarifa_millar": [{"grupo": "g", "clave": "c", "descripcion": "d",
                                     "tasa_millar": 1.0}],
            "tabla_progresiva": [],
        }
        result = check_predial_structure(predial)
        assert "tipo_desconocido_con_tablas_no_vacias" in result["anomalias"]

    def test_mixto_sin_comentarios(self):
        predial = {
            "tipo_esquema": "mixto",
            "esquema_valido": True,
            "comentarios": "",
            "tabla_tarifa_millar": [{"grupo": "g", "clave": "c", "descripcion": "d",
                                     "tasa_millar": 1.0}],
            "tabla_progresiva": [],
        }
        result = check_predial_structure(predial)
        assert "tipo_mixto_sin_comentarios" in result["anomalias"]

    def test_prog_solape(self):
        predial = {
            "tipo_esquema": "progresivo",
            "esquema_valido": True,
            "tabla_tarifa_millar": [],
            "tabla_progresiva": [
                {"n_rango": "1", "inferior": "$0.01", "superior": "$100,000.00",
                 "cuota_fija": "$10", "tasa_marginal": "0.001"},
                {"n_rango": "2", "inferior": "$90,000.00", "superior": "$200,000.00",
                 "cuota_fija": "$50", "tasa_marginal": "0.002"},
            ],
        }
        result = check_predial_structure(predial)
        solape_flags = [a for a in result["anomalias"] if "solape" in a]
        assert len(solape_flags) > 0


class TestInteranualRules:

    def test_cambio_esquema(self):
        rows = [
            {"municipio_slug": "saltillo", "anio": 2020,
             "tipo_esquema": "progresivo", "esquema_valido": True,
             "n_tarifa_rows": 0, "n_prog_rows": 5, "anomalias": []},
            {"municipio_slug": "saltillo", "anio": 2021,
             "tipo_esquema": "tarifa_millar", "esquema_valido": True,
             "n_tarifa_rows": 3, "n_prog_rows": 0, "anomalias": []},
        ]
        apply_interanual_rules(rows)
        assert any("cambio_esquema" in a for a in rows[1]["anomalias"])

    def test_cambio_brusco_filas(self):
        rows = [
            {"municipio_slug": "torreon", "anio": 2019,
             "tipo_esquema": "progresivo", "esquema_valido": True,
             "n_tarifa_rows": 0, "n_prog_rows": 5, "anomalias": []},
            {"municipio_slug": "torreon", "anio": 2020,
             "tipo_esquema": "progresivo", "esquema_valido": True,
             "n_tarifa_rows": 0, "n_prog_rows": 15, "anomalias": []},
        ]
        apply_interanual_rules(rows)
        assert any("cambio_brusco" in a for a in rows[1]["anomalias"])

    def test_no_anomalia_si_consistente(self):
        rows = [
            {"municipio_slug": "monclova", "anio": 2018,
             "tipo_esquema": "tarifa_millar", "esquema_valido": True,
             "n_tarifa_rows": 3, "n_prog_rows": 0, "anomalias": []},
            {"municipio_slug": "monclova", "anio": 2019,
             "tipo_esquema": "tarifa_millar", "esquema_valido": True,
             "n_tarifa_rows": 3, "n_prog_rows": 0, "anomalias": []},
        ]
        apply_interanual_rules(rows)
        assert rows[1]["anomalias"] == []
