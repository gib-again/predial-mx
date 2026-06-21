"""Tests del parseo de resultados batch v3 (ruteo a fallback)."""

import glob
import json

import pytest

from src.extraction.batch_v3 import _result_from_line


def _line(custom_id, content=None, status=200, error=None):
    resp = {"status_code": status}
    if content is not None:
        resp["body"] = {"choices": [{"message": {"content": content}}],
                        "usage": {"prompt_tokens": 100, "completion_tokens": 50}}
    return {"custom_id": custom_id, "response": resp, "error": error}


CID = "guanajuato|11020|2022|penjamo"

_OTRO = json.dumps({
    "predial": {"tarifas": [{
        "ambito": "general", "base_gravable": "valor_catastral",
        "esquema": {"tipo_esquema": "otro_no_clasificado",
                    "categoria": "estructura_no_estandar",
                    "descripcion_estructural": "no encaja", "tabla_cruda": []},
    }], "comentarios": ""},
    "_meta": None,
})


class TestResultFromLine:
    def test_error_line_none(self):
        assert _result_from_line("guanajuato", _line(CID, error={"code": "x"})) is None

    def test_http_no_200_none(self):
        assert _result_from_line("guanajuato", _line(CID, content="{}", status=500)) is None

    def test_invalid_json_none(self):
        assert _result_from_line("guanajuato", _line(CID, content="no es json")) is None

    def test_bad_custom_id_none(self):
        assert _result_from_line("guanajuato", _line("malformado", content=_OTRO)) is None

    def test_otro_no_clasificado_va_a_fallback(self):
        # otro_no_clasificado → None (lo toma el fallback síncrono con cascada)
        assert _result_from_line("guanajuato", _line(CID, content=_OTRO)) is None

    def test_resultado_valido_real(self):
        # Usa un JSON real extraído (no-null, no-otro) como contenido del batch.
        from src.extraction.llm_extract_v3 import _should_attempt_rescue, PredialOutputV3
        cand = None
        for f in glob.glob("data/guanajuato/json_predial/**/*.json", recursive=True):
            d = json.load(open(f, encoding="utf-8"))
            if d.get("predial") is None:
                continue
            try:
                out = PredialOutputV3.model_validate({"predial": d["predial"], "_meta": None})
            except Exception:
                continue
            if not _should_attempt_rescue(out):
                cand = d
                break
        if cand is None:
            pytest.skip("no hay JSON v3 real no-otro disponible")
        content = json.dumps({"predial": cand["predial"], "_meta": None})
        r = _result_from_line("guanajuato", _line(CID, content=content))
        assert r is not None
        assert r.output is not None
        assert r.fuente == "txt"
        assert r.archivo == "GTO_PREDIAL_2022_penjamo.json"
