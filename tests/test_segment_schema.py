"""Tests para src/core/segment_schema.py — esquema único de segment.csv."""

from src.core.segment_schema import (
    SEGMENT_FIELDS,
    STATUS_IDENTIDAD,
    STATUS_NO_LOCALIZADA,
    STATUS_OK,
    SegmentRow,
    canonicalize_segment_row,
    is_canonical,
    read_segment_csv,
    write_segment_csv,
)


class TestWriteRead:
    def test_roundtrip_dataclass(self, tmp_path):
        path = tmp_path / "segment.csv"
        rows = [
            SegmentRow(
                cvegeo="05030", estado_slug="coahuila", municipio_slug="saltillo",
                municipio_raw="SALTILLO", anio=2016, status=STATUS_OK,
                source_pdf="data/coahuila/pdf_raw/2016/x.pdf",
                ley_page_start=13, predial_page_start=15, predial_page_end=17,
            ),
            SegmentRow(
                cvegeo="", estado_slug="coahuila", municipio_slug="",
                municipio_raw="TEXTO OCR BASURA", anio=2016,
                status=STATUS_IDENTIDAD,
            ),
        ]
        write_segment_csv(rows, path)
        out = read_segment_csv(path)
        assert len(out) == 2
        assert out[0]["cvegeo"] == "05030"
        assert out[0]["municipio_slug"] == "saltillo"
        assert out[0]["status"] == STATUS_OK
        assert out[1]["status"] == STATUS_IDENTIDAD
        assert out[1]["cvegeo"] == ""

    def test_header_is_canonical_order(self, tmp_path):
        path = tmp_path / "segment.csv"
        write_segment_csv([SegmentRow(cvegeo="05030")], path)
        header = path.read_text(encoding="utf-8").splitlines()[0]
        assert header == ",".join(SEGMENT_FIELDS)

    def test_dict_input_extra_cols_ignored(self, tmp_path):
        path = tmp_path / "segment.csv"
        write_segment_csv([{"cvegeo": "05030", "columna_rara": "x"}], path)
        out = read_segment_csv(path)
        assert out[0]["cvegeo"] == "05030"
        assert "columna_rara" not in out[0]


class TestAliasNormalization:
    def test_legacy_aliases_mapped(self, tmp_path):
        # CSV legado con ejercicio/slug/pdf_used en vez de canónicos.
        path = tmp_path / "segment.csv"
        path.write_text(
            "ejercicio,slug,pdf_used,predial_page_start\n"
            "2016,saltillo,x.pdf,15\n",
            encoding="utf-8",
        )
        out = read_segment_csv(path)
        assert out[0]["anio"] == "2016"
        assert out[0]["municipio_slug"] == "saltillo"
        assert out[0]["source_pdf"] == "x.pdf"

    def test_canonical_not_overwritten_by_alias(self, tmp_path):
        path = tmp_path / "segment.csv"
        path.write_text(
            "anio,ejercicio,municipio_slug,slug\n"
            "2016,1999,saltillo,otro\n",
            encoding="utf-8",
        )
        out = read_segment_csv(path)
        assert out[0]["anio"] == "2016"
        assert out[0]["municipio_slug"] == "saltillo"


class TestCanonicalizeSegmentRow:
    def test_cve_mun_resolves(self):
        # Guanajuato/Tamaulipas traen cve_mun → cvegeo = cve_ent+cve_mun.
        r = canonicalize_segment_row(
            "guanajuato", {"cve_mun": "021", "ejercicio": "2018", "predial_page_start": "5"}
        )
        assert r.cvegeo == "11021"
        assert r.municipio_slug == "moroleon"
        assert r.status == STATUS_OK

    def test_invalid_cve_mun_placeholder(self):
        # cve_mun "???" no debe propagar un cvegeo basura ("11???").
        r = canonicalize_segment_row(
            "guanajuato",
            {"cve_mun": "???", "municipio": "MOROLEÓN, GUANAJGATO BASURA OCR", "ejercicio": "2018"},
        )
        assert r.cvegeo == ""
        assert r.status == STATUS_IDENTIDAD
        assert "MOROLE" in r.municipio_raw  # texto crudo preservado para auditoría

    def test_name_resolution_fallback(self):
        # Estado sin cve_mun (resuelve por slug).
        r = canonicalize_segment_row(
            "coahuila", {"slug": "saltillo", "ejercicio": "2016", "predial_page_start": "15"}
        )
        assert r.cvegeo == "05030"
        assert r.status == STATUS_OK

    def test_focus_file_counts_as_located(self):
        # GTO extrae de la ley completa: sin predial_page_start pero con txt_file.
        r = canonicalize_segment_row(
            "guanajuato",
            {"cve_mun": "021", "ejercicio": "2018", "predial_page_start": "", "txt_file": "x.txt"},
        )
        assert r.status == STATUS_OK

    def test_no_content_is_no_localizada(self):
        r = canonicalize_segment_row(
            "coahuila",
            {"slug": "saltillo", "ejercicio": "2016", "predial_page_start": "", "txt_file": ""},
        )
        assert r.cvegeo == "05030"
        assert r.status == STATUS_NO_LOCALIZADA

    def test_idempotent_trusts_existing_cvegeo(self):
        # Segunda pasada sobre fila ya canónica (con cvegeo, sin cve_mun) es estable.
        first = canonicalize_segment_row(
            "guanajuato", {"cve_mun": "021", "ejercicio": "2018", "predial_page_start": "5"}
        )
        from dataclasses import asdict
        second = canonicalize_segment_row("guanajuato", asdict(first))
        assert second.cvegeo == first.cvegeo == "11021"
        assert second.status == first.status


class TestIsCanonical:
    def test_canonical(self, tmp_path):
        path = tmp_path / "segment.csv"
        write_segment_csv([SegmentRow(cvegeo="05030")], path)
        assert is_canonical(path) is True

    def test_legacy(self, tmp_path):
        path = tmp_path / "segment.csv"
        path.write_text("ejercicio,slug\n2016,saltillo\n", encoding="utf-8")
        assert is_canonical(path) is False

    def test_missing(self, tmp_path):
        assert is_canonical(tmp_path / "nope.csv") is False
