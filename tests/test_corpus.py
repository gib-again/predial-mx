"""Tests para src/core/corpus.py — acceso centralizado al corpus v3."""

from src.core import corpus


class TestParseFname:
    def test_valid(self):
        assert corpus.parse_fname("COAH_PREDIAL_2016_saltillo.json") == (2016, "saltillo")

    def test_multiword(self):
        assert corpus.parse_fname("GTO_PREDIAL_2024_apaseo_el_alto.json") == (
            2024, "apaseo_el_alto")

    def test_invalid(self):
        assert corpus.parse_fname("no_es_predial.json") is None


class TestResolveJson:
    def test_missing_returns_none(self):
        # Regresión: antes devolvía Path("") == Path('.'), que es truthy y
        # .exists()==True (cwd) → falsos positivos de "ya existe".
        assert corpus.resolve_json("coahuila", 9999, "municipio_inexistente") is None

    def test_missing_is_falsy(self):
        assert not corpus.resolve_json("coahuila", 9999, "nope")
