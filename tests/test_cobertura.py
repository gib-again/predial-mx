"""Tests para la capa de cobertura (placeholders) + detector cobertura_incompleta."""

from src.hitl.cobertura import EXCLUIDOS, estados_cobertura
from src.hitl.detectors import det_cobertura_incompleta


class TestEstadosCobertura:
    def test_excluye_oaxaca_y_hardcoded(self):
        ec = estados_cobertura()
        assert "oaxaca" not in ec
        for h in ("chihuahua", "colima", "edomex", "sinaloa", "tabasco"):
            assert h not in ec
        # incluye Grupo A segmentables
        for a in ("coahuila", "guanajuato", "jalisco", "queretaro", "sanluispotosi",
                  "sonora", "tamaulipas", "yucatan"):
            assert a in ec

    def test_excluidos_set(self):
        assert "oaxaca" in EXCLUIDOS


def _placeholder(hint=None, razon="sin_extraccion"):
    return {
        "predial": None,
        "_meta": {"modelo": "placeholder_cobertura", "razon": razon},
        "_meta_v3": {"cvegeo": "11021", "estado": "guanajuato", "anio": 2024},
        "_meta_cobertura": {"placeholder": True, "hint_focus_huerfano": hint},
    }


class TestDetectorCobertura:
    def test_placeholder_emite_sev2(self):
        rows = det_cobertura_incompleta(_placeholder(), "guanajuato", "moroleon",
                                        2024, "p.json", estado="Guanajuato",
                                        municipio="Moroleon", cvegeo="11021")
        assert len(rows) == 1
        assert rows[0].severidad == "SEV2"
        assert rows[0].detector == "cobertura_incompleta"
        assert rows[0].cvegeo == "11021"

    def test_con_hint_incluye_pista(self):
        hint = {"texto_crudo": "XICRU", "score": 0.8, "source_pdf": "x.pdf"}
        rows = det_cobertura_incompleta(_placeholder(hint), "guanajuato", "xichu",
                                        2017, "p.json", estado="Guanajuato",
                                        municipio="Xichu", cvegeo="11042")
        assert "XICRU" in rows[0].senal

    def test_sin_ley_resuelto_no_surfacea(self):
        rows = det_cobertura_incompleta(_placeholder(razon="sin_ley"), "guanajuato",
                                        "moroleon", 2024, "p.json")
        assert rows == []

    def test_no_placeholder_ignorado(self):
        doc = {"predial": {"tarifas": []}, "_meta_cobertura": {}}
        assert det_cobertura_incompleta(doc, "guanajuato", "x", 2024, "p.json") == []

    def test_extraccion_fallida_real_null_sev1(self):
        # JSON real (no placeholder) con predial=null → SEV1 extraccion_fallida.
        doc = {"predial": None, "_meta": {"modelo": "gpt-5.4", "razon": "valido_3x_fallido"},
               "_meta_v3": {"cvegeo": "11017", "razon": "valido_3x_fallido"}}
        rows = det_cobertura_incompleta(doc, "guanajuato", "irapuato", 2023, "p.json",
                                        estado="Guanajuato", municipio="Irapuato", cvegeo="11017")
        assert len(rows) == 1
        assert rows[0].severidad == "SEV1"
        assert rows[0].detector == "extraccion_fallida"
