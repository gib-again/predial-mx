"""Tests para src/core/validation.py — semántica schema_v2.

Las anomalías ya no son strings heurísticos del estilo `tipo_X_sin_filas`; ahora
el sistema reclasifica vía discriminated union y emite:
  - `reclasificado_de_X_a_Y` cuando el `tipo_esquema` declarado difiere del
    que realmente validó (incluye el bug progresivo→cuota_fija_escalonada).
  - `otro_no_clasificado_<categoria>` cuando ninguna variante validó.
"""

from src.core.validation import (
    apply_interanual_rules,
    check_predial_structure,
    reclasificar,
)
from src.extraction.schema_v2 import (
    CuotaFijaEscalonadaSchema,
    OtroNoClasificadoSchema,
    ProgresivoSchema,
    TarifaMillarSchema,
)


class TestCheckPredialStructure:
    """check_predial_structure delega en reclasificar y devuelve el dict v1-shape."""

    def test_tarifa_millar_valido(self):
        predial = {
            "tipo_esquema": "tarifa_millar",
            "esquema_valido": True,
            "comentarios": "",
            "tabla_tarifa_millar": [
                {
                    "grupo": "urbano",
                    "clave": "urb",
                    "descripcion": "Predios urbanos",
                    "tasa_millar": 2.3,
                },
            ],
            "tabla_progresiva": [],
            "tabla_tasa_unica": [],
            "tabla_cuota_fija": [],
        }
        result = check_predial_structure(predial)
        assert result["tipo_esquema"] == "tarifa_millar"
        assert result["esquema_valido"] is True
        assert result["n_tarifa_rows"] == 1
        assert result["anomalias"] == []

    def test_progresivo_valido(self):
        predial = {
            "tipo_esquema": "progresivo",
            "comentarios": "",
            "tabla_progresiva": [
                {"n_rango": "1", "inferior": "0.01", "superior": "100,000.00",
                 "cuota_fija": "0", "tasa_marginal": "0.001"},
                {"n_rango": "2", "inferior": "100,000.01", "superior": "En Adelante",
                 "cuota_fija": "100", "tasa_marginal": "0.002"},
            ],
        }
        result = check_predial_structure(predial)
        assert result["tipo_esquema"] == "progresivo"
        assert result["n_prog_rows"] == 2
        assert result["anomalias"] == []

    def test_progresivo_con_zero_tasa_reclasifica_a_escalonada(self):
        """El bug clave: tipo=progresivo con tasa_marginal=0 en todos →
        reclasificado a cuota_fija_escalonada con anomalia explícita."""
        predial = {
            "tipo_esquema": "progresivo",
            "comentarios": "",
            "tabla_progresiva": [
                {"n_rango": "1", "inferior": "0.01", "superior": "10,000.00",
                 "cuota_fija": "$100", "tasa_marginal": "0"},
                {"n_rango": "2", "inferior": "10,000.01", "superior": "En Adelante",
                 "cuota_fija": "$200", "tasa_marginal": "0"},
            ],
        }
        result = check_predial_structure(predial)
        assert result["tipo_esquema"] == "cuota_fija_escalonada"
        assert result["esquema_valido"] is True
        assert result["n_cuota_fija_rows"] == 2
        assert any(
            "reclasificado_de_progresivo_a_cuota_fija_escalonada" in a
            for a in result["anomalias"]
        )

    def test_sin_tablas_es_otro_no_clasificado(self):
        predial = {
            "tipo_esquema": "tarifa_millar",
            "comentarios": "",
            "tabla_tarifa_millar": [],
            "tabla_progresiva": [],
        }
        result = check_predial_structure(predial)
        assert result["tipo_esquema"] == "otro_no_clasificado"
        assert result["esquema_valido"] is False
        assert any("otro_no_clasificado_segmento_vacio" in a for a in result["anomalias"])

    def test_solape_brackets_cae_a_otro_no_clasificado(self):
        """Brackets con overlap real (>1 peso) no se snapean: validación falla
        en todas las variantes y cae al escape hatch."""
        predial = {
            "tipo_esquema": "progresivo",
            "tabla_progresiva": [
                {"n_rango": "1", "inferior": "0.01", "superior": "100,000.00",
                 "cuota_fija": "10", "tasa_marginal": "0.001"},
                {"n_rango": "2", "inferior": "90,000.00", "superior": "200,000.00",
                 "cuota_fija": "50", "tasa_marginal": "0.002"},
            ],
        }
        result = check_predial_structure(predial)
        assert result["tipo_esquema"] == "otro_no_clasificado"
        assert any("otro_no_clasificado" in a for a in result["anomalias"])

    def test_tipo_invalido_y_sin_tablas_cae_a_otro_no_clasificado(self):
        predial = {
            "tipo_esquema": "inventado",
            "esquema_valido": True,
        }
        result = check_predial_structure(predial)
        assert result["tipo_esquema"] == "otro_no_clasificado"
        assert result["esquema_valido"] is False


class TestReclasificar:
    """Comportamiento de la función reclasificar pública."""

    def test_returns_progresivo_instance(self):
        predial = {
            "tipo_esquema": "progresivo",
            "tabla_progresiva": [
                {"n_rango": "1", "inferior": "0", "superior": "1000",
                 "cuota_fija": "0", "tasa_marginal": "0.005"},
                {"n_rango": "2", "inferior": "1000", "superior": None,
                 "cuota_fija": "5", "tasa_marginal": "0.01"},
            ],
        }
        out = reclasificar(predial)
        assert isinstance(out, ProgresivoSchema)

    def test_returns_cuota_fija_escalonada_when_tasa_marginal_zero(self):
        predial = {
            "tipo_esquema": "progresivo",
            "tabla_progresiva": [
                {"n_rango": "1", "inferior": "0", "superior": "1000",
                 "cuota_fija": "100", "tasa_marginal": "0"},
                {"n_rango": "2", "inferior": "1000", "superior": None,
                 "cuota_fija": "200", "tasa_marginal": "0"},
            ],
        }
        out = reclasificar(predial)
        assert isinstance(out, CuotaFijaEscalonadaSchema)

    def test_prefers_declared_when_multiple_variants_match(self):
        """Cuando progresivo y cuota_fija_escalonada validan simultáneamente
        (tasa_marginal>0 y cuota_fija no-decreciente), gana el declarado."""
        predial = {
            "tipo_esquema": "progresivo",
            "tabla_progresiva": [
                {"n_rango": "1", "inferior": "0", "superior": "1000",
                 "cuota_fija": "10", "tasa_marginal": "0.005"},
                {"n_rango": "2", "inferior": "1000", "superior": None,
                 "cuota_fija": "20", "tasa_marginal": "0.01"},
            ],
        }
        out = reclasificar(predial)
        assert isinstance(out, ProgresivoSchema)

    def test_returns_otro_no_clasificado_when_no_variant_matches(self):
        predial = {
            "tipo_esquema": "desconocido",
            "comentarios": "",
        }
        out = reclasificar(predial)
        assert isinstance(out, OtroNoClasificadoSchema)
        assert out.categoria == "segmento_vacio"
        assert "Ninguna variante validó" in out.descripcion_estructural

    def test_otro_no_clasificado_captures_tabla_cruda(self):
        """Si hay tablas v1 pero ninguna variante valida, tabla_cruda recibe el volcado."""
        predial = {
            "tipo_esquema": "progresivo",
            "tabla_progresiva": [
                {"n_rango": "1", "inferior": "100", "superior": "50",
                 "cuota_fija": "10", "tasa_marginal": "0.001"},
            ],
        }
        out = reclasificar(predial)
        assert isinstance(out, OtroNoClasificadoSchema)
        assert out.categoria == "estructura_no_estandar"
        assert any(row.get("_tabla") == "tabla_progresiva" for row in out.tabla_cruda)

    def test_tarifa_millar_passthrough(self):
        predial = {
            "tipo_esquema": "tarifa_millar",
            "tabla_tarifa_millar": [
                {"grupo": "urbano", "clave": "urb", "descripcion": "x", "tasa_millar": 1.5},
            ],
        }
        out = reclasificar(predial)
        assert isinstance(out, TarifaMillarSchema)
        assert out.tabla[0].tasa_millar == 1.5


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

    def test_otro_no_clasificado_omite_cambio_esquema(self):
        """Cambios entre variantes reales y otro_no_clasificado no deben flaggear
        cambio_esquema (no hay clasificación confiable que comparar)."""
        rows = [
            {"municipio_slug": "x", "anio": 2018,
             "tipo_esquema": "progresivo", "esquema_valido": True,
             "n_tarifa_rows": 0, "n_prog_rows": 5, "anomalias": []},
            {"municipio_slug": "x", "anio": 2019,
             "tipo_esquema": "otro_no_clasificado", "esquema_valido": False,
             "n_tarifa_rows": 0, "n_prog_rows": 0, "anomalias": []},
        ]
        apply_interanual_rules(rows)
        assert not any("cambio_esquema" in a for a in rows[1]["anomalias"])
