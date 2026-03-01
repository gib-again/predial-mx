"""Tests para src/core/text_utils.py"""

import pytest
from pathlib import Path
from src.core.text_utils import (
    norm,
    norm_light,
    slugify,
    parse_predial_filename,
    parse_monto_to_float,
)


# ── norm() ──

class TestNorm:
    def test_basic(self):
        assert norm("Saltillo") == "SALTILLO"

    def test_accents(self):
        assert norm("Acuña") == "ACUNA"
        assert norm("Querétaro") == "QUERETARO"

    def test_enie(self):
        assert norm("Año") == "ANO"

    def test_none(self):
        assert norm(None) == ""

    def test_whitespace(self):
        assert norm("  San Pedro  ") == "SAN PEDRO"


# ── slugify() ──

class TestSlugify:
    def test_basic(self):
        assert slugify("Saltillo") == "saltillo"

    def test_spaces(self):
        assert slugify("San Pedro de las Colonias") == "san_pedro_de_las_colonias"

    def test_accents(self):
        assert slugify("Acuña") == "acuna"

    def test_empty(self):
        assert slugify("") == "sin_municipio"


# ── parse_predial_filename() ──

class TestParseFilename:
    def test_coahuila(self):
        path = Path("COAH_PREDIAL_2016_saltillo.txt")
        anio, slug, nombre = parse_predial_filename(path, "COAH")
        assert anio == 2016
        assert slug == "saltillo"
        assert nombre == "Saltillo"

    def test_multi_word(self):
        path = Path("COAH_PREDIAL_2018_san_pedro_de_las_colonias.json")
        anio, slug, nombre = parse_predial_filename(path, "COAH")
        assert anio == 2018
        assert slug == "san_pedro_de_las_colonias"
        assert nombre == "San Pedro De Las Colonias"

    def test_jalisco(self):
        path = Path("JAL_PREDIAL_2020_guadalajara.txt")
        anio, slug, nombre = parse_predial_filename(path, "JAL")
        assert anio == 2020
        assert slug == "guadalajara"

    def test_wrong_prefix_raises(self):
        path = Path("COAH_PREDIAL_2016_saltillo.txt")
        with pytest.raises(ValueError, match="Prefijo esperado"):
            parse_predial_filename(path, "JAL")

    def test_short_name_raises(self):
        path = Path("COAH_PREDIAL.txt")
        with pytest.raises(ValueError):
            parse_predial_filename(path, "COAH")


# ── parse_monto_to_float() ──

class TestParseMontoToFloat:
    """Casos derivados directamente del script 25_json_consistency.py original."""

    def test_us_format(self):
        assert parse_monto_to_float("$620,100.00") == 620100.00

    def test_european_format(self):
        assert parse_monto_to_float("$183.818,00") == 183818.00

    def test_miles_no_decimal(self):
        assert parse_monto_to_float("60,000") == 60000.0

    def test_european_decimal(self):
        assert parse_monto_to_float("$0,01") == 0.01

    def test_simple_decimal(self):
        assert parse_monto_to_float("142.63") == 142.63

    def test_none(self):
        assert parse_monto_to_float(None) is None

    def test_int_passthrough(self):
        assert parse_monto_to_float(100) == 100.0

    def test_float_passthrough(self):
        assert parse_monto_to_float(3.14) == 3.14

    def test_empty_string(self):
        assert parse_monto_to_float("") is None

    def test_no_digits(self):
        assert parse_monto_to_float("$") is None

    def test_negative(self):
        assert parse_monto_to_float("-1,500.00") == -1500.00

    def test_small_us(self):
        assert parse_monto_to_float("$0.01") == 0.01

    def test_large_european(self):
        # 1.234.567,89 → 1234567.89
        assert parse_monto_to_float("1.234.567,89") == 1234567.89
