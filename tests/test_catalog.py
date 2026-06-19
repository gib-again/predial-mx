"""Tests para src/core/catalog.py — resolución canónica de identidad."""

import pytest

from src.core import catalog


# ── build_cvegeo ──

class TestBuildCvegeo:
    def test_basic(self):
        assert catalog.build_cvegeo("11", "021") == "11021"

    def test_zero_pads(self):
        assert catalog.build_cvegeo("5", "1") == "05001"
        assert catalog.build_cvegeo("5", "30") == "05030"


# ── cvegeo → nombre / slug ──

class TestCvegeoToNombre:
    def test_saltillo(self):
        assert catalog.cvegeo_to_nombre("05030") == "Saltillo"

    def test_guadalajara(self):
        assert catalog.cvegeo_to_nombre("14039") == "Guadalajara"

    def test_moroleon(self):
        assert catalog.cvegeo_to_nombre("11021") == "Moroleon"

    def test_unknown_returns_empty(self):
        assert catalog.cvegeo_to_nombre("99999") == ""

    def test_int_like_padded(self):
        # acepta cvegeo sin zero-pad
        assert catalog.cvegeo_to_nombre("5030") == "Saltillo"


class TestCvegeoToSlug:
    def test_saltillo(self):
        assert catalog.cvegeo_to_slug("05030") == "saltillo"

    def test_unknown_returns_empty(self):
        assert catalog.cvegeo_to_slug("99999") == ""


class TestResolveCvegeoPair:
    def test_pair(self):
        assert catalog.resolve_cvegeo_pair("05030") == ("saltillo", "Saltillo")

    def test_unknown_raises(self):
        with pytest.raises(KeyError):
            catalog.resolve_cvegeo_pair("99999")


# ── resolve_cvegeo (nombre/slug crudo → cvegeo) ──

class TestResolveCvegeo:
    def test_exact_name(self):
        assert catalog.resolve_cvegeo("coahuila", "Saltillo") == "05030"

    def test_uppercase_no_accent(self):
        assert catalog.resolve_cvegeo("guanajuato", "MOROLEON") == "11021"

    def test_slug_input(self):
        assert catalog.resolve_cvegeo("jalisco", "guadalajara") == "14039"

    def test_ocr_garbage_returns_empty(self):
        # El bug Moroleón: header OCR completo no debe matchear como identidad.
        garbage = "MOROLEÓN, GUANAJGATO, PARA EL EJERCICIO FISCAL DEL AÑO 2018 CAPÍTULO PRIMERO"
        assert catalog.resolve_cvegeo("guanajuato", garbage) == ""

    def test_unknown_estado_returns_empty(self):
        assert catalog.resolve_cvegeo("noexiste", "Saltillo") == ""

    def test_aliases(self):
        # NOM_CAB "Ciudad Acuña" → slug de NOM_MUN "Acuña" (Coahuila 05002)
        cvegeo = catalog.resolve_cvegeo(
            "coahuila", "Ciudad Acuña", aliases={"ciudad_acuna": "acuna"}
        )
        assert cvegeo == catalog.resolve_cvegeo("coahuila", "Acuña")
        assert cvegeo != ""


class TestMatchMunicipio:
    def test_exact_method(self):
        res = catalog.match_municipio("coahuila", "Saltillo")
        assert res.method == "exact"
        assert res.cve_mun == "030"
