"""Tests para src/hitl/decisiones.py — capa append-only de decisiones HITL."""

from src.hitl import decisiones


class TestAppendLoad:
    def test_append_and_latest(self, tmp_path):
        log = tmp_path / "hitl_decisiones.csv"
        decisiones.append_decision(
            id="abc123", decision="ignorar", cvegeo="05030",
            estado_slug="coahuila", municipio_slug="saltillo", anio=2016,
            revisor="tester", path=log,
        )
        latest = decisiones.load_latest(log)
        assert "abc123" in latest
        assert latest["abc123"]["decision"] == "ignorar"
        assert latest["abc123"]["cvegeo"] == "05030"

    def test_latest_wins(self, tmp_path):
        log = tmp_path / "hitl_decisiones.csv"
        decisiones.append_decision(id="x", decision="reextraer", revisor="t", path=log)
        decisiones.append_decision(id="x", decision="confirmar_ok", revisor="t", path=log)
        latest = decisiones.load_latest(log)
        assert latest["x"]["decision"] == "confirmar_ok"
        # ambas filas quedan en el log (append-only / trazabilidad)
        assert len(decisiones.load_all(log)) == 2

    def test_sub_opcion_persisted(self, tmp_path):
        log = tmp_path / "hitl_decisiones.csv"
        decisiones.append_decision(
            id="y", decision="confirmar_ok", sub_opcion="cambio_menor",
            revisor="t", path=log,
        )
        assert decisiones.load_latest(log)["y"]["sub_opcion"] == "cambio_menor"

    def test_empty_when_missing(self, tmp_path):
        assert decisiones.load_latest(tmp_path / "nope.csv") == {}
        assert decisiones.load_all(tmp_path / "nope.csv") == []
