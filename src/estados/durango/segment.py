"""
Segmentacion de las Leyes de Ingresos Municipales de Durango.

Modelo: 1 PDF = 1 ley municipal completa (Congreso). Un solo nivel. PDFs
digitales (sin OCR). Se localiza la seccion del Impuesto Predial y se recorta
hasta el siguiente impuesto (Traslacion de Dominio / Adquisicion de Inmuebles).

Genera:
  data/durango/focus_predial/{anio}/DGO_PREDIAL_{anio}_{slug}.txt + .pdf
  data/durango/meta/predial_master.csv
  data/durango/meta/segment.csv
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import fitz  # PyMuPDF

from src.core.segment_utils import (
    HITL_EXTRA_FIELDS,
    PatternSpec,
    find_predial_section,
    hitl_extra_columns,
)
from src.estados.durango import config

FALLBACK_PAGES = 10

_START_SPECS = [
    # 1) Encabezado de seccion/capitulo + IMPUESTO PREDIAL + ARTICULO
    PatternSpec(re.compile(
        r"(?:CAP[IÍ]TULO|SECCI[OÓ]N)[^\n]{0,60}\n?[^\n]{0,40}"
        r"(?:DEL\s+)?IMPUESTO\s+PREDIAL[\s\S]{0,200}?ART[IÍ]CULO\s+\d+",
        re.IGNORECASE,
    ), "capitulo_predial_articulo"),
    # 2) ARTICULO N + "el impuesto predial se causara/pagara/calculara"
    PatternSpec(re.compile(
        r"ART[IÍ]CULO\s+\d+[°ºo.\s-]*[\s\S]{0,80}?"
        r"impuesto\s+predial[\s\S]{0,60}?(?:se\s+(?:causar|pagar|calcular|determinar)|tasa|al\s+millar)",
        re.IGNORECASE,
    ), "articulo_predial_tasa"),
    # 3) Encabezado generico DEL IMPUESTO PREDIAL
    PatternSpec(re.compile(r"(?:DEL\s+)?IMPUESTO\s+PREDIAL\b", re.IGNORECASE),
                "impuesto_predial_generico"),
]

_END_SPECS = [
    PatternSpec(re.compile(
        r"(?:DEL\s+)?IMPUESTO\s+SOBRE\s+(?:LA\s+)?(?:TRASLACI[OÓ]N\s+DE\s+DOMINIO|"
        r"ADQUISICI[OÓ]N)\s+DE\s+(?:BIENES\s+)?INMUEBLES", re.IGNORECASE),
        "traslacion_adquisicion"),
    PatternSpec(re.compile(r"IMPUESTO\s+SOBRE\s+(?:LOS\s+)?ESPECT[AÁ]CULOS", re.IGNORECASE),
                "espectaculos"),
    PatternSpec(re.compile(r"CAP[IÍ]TULO\s+(?:III|IV|TERCERO|CUARTO)\b", re.IGNORECASE),
                "siguiente_capitulo"),
]


def _ctx_validator(text: str, match: re.Match, method: str) -> bool:
    # Rechazar matches en sumario/portada (primeros chars).
    return match.start() >= 400


def _slug_from_filename(pdf: Path) -> str | None:
    parts = pdf.stem.split("_")
    if len(parts) < 4 or parts[0] != config.PREFIJO or parts[1] != "RAW":
        return None
    try:
        int(parts[2])
    except ValueError:
        return None
    return "_".join(parts[3:]) or None


def _iter_pdfs(pdf_raw: Path, year: str | None):
    if not pdf_raw.exists():
        return
    for ydir in sorted(pdf_raw.iterdir()):
        if not ydir.is_dir() or (year and ydir.name != str(year)):
            continue
        try:
            ej = int(ydir.name)
        except ValueError:
            continue
        for pdf in sorted(ydir.glob("*.pdf")):
            yield ej, pdf


def _pages_text(doc):
    parts, offsets, cur = [], [], 0
    for i in range(len(doc)):
        offsets.append((i, cur))
        t = doc[i].get_text("text") or ""
        parts.append(t)
        cur += len(t) + 1
    return "\n".join(parts), offsets


def _char_to_page(idx, offsets, n):
    page = 0
    for p, start in offsets:
        if start <= idx:
            page = p
        else:
            break
    return min(page, n - 1)


_SEGMENT_FIELDS = [
    "ejercicio", "slug", "source_pdf", "focus_file", "segment_method",
    "page_start", "page_end", "char_start", "char_end", "txt_chars",
    "confidence", "error_class", "error_detail",
    *[f for f in HITL_EXTRA_FIELDS if f not in {"char_start", "char_end", "confidence"}],
]


def run_build_master(adapter) -> Path:
    meta = Path("data") / config.ESTADO_SLUG / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    master = meta / "predial_master.csv"
    rows = []
    for ej, pdf in _iter_pdfs(Path("data") / config.ESTADO_SLUG / "pdf_raw", None):
        slug = _slug_from_filename(pdf)
        if not slug:
            continue
        try:
            with fitz.open(str(pdf)) as d:
                n = len(d)
        except Exception:
            n = 0
        rows.append({"ejercicio": ej, "slug": slug, "source_pdf": pdf.name, "num_pages": n})
    with master.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ejercicio", "slug", "source_pdf", "num_pages"])
        w.writeheader()
        w.writerows(rows)
    print(f"  Master: {master} ({len(rows)} PDFs)")
    return master


def run_extract_sections(adapter, year: str | None = None) -> Path:
    base = Path("data") / config.ESTADO_SLUG
    pdf_raw, focus_dir, meta = base / "pdf_raw", base / "focus_predial", base / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    segment_csv = meta / "segment.csv"

    print("=== Durango: segmentacion predial ===")
    rows = []
    stats = {"total": 0, "found": 0, "fallback": 0, "errors": 0}

    for ej, pdf in _iter_pdfs(pdf_raw, year):
        slug = _slug_from_filename(pdf)
        if not slug:
            continue
        stats["total"] += 1
        yfocus = focus_dir / str(ej)
        yfocus.mkdir(parents=True, exist_ok=True)
        txt_out = yfocus / f"{config.PREFIJO}_PREDIAL_{ej}_{slug}.txt"
        pdf_out = yfocus / f"{config.PREFIJO}_PREDIAL_{ej}_{slug}.pdf"
        try:
            doc = fitz.open(str(pdf))
        except Exception as e:
            stats["errors"] += 1
            rows.append({**hitl_extra_columns(), "ejercicio": ej, "slug": slug,
                         "source_pdf": pdf.name, "focus_file": "", "segment_method": "",
                         "page_start": "", "page_end": "", "char_start": "", "char_end": "",
                         "txt_chars": 0, "confidence": 0, "error_class": "open_error",
                         "error_detail": str(e)[:150]})
            continue
        try:
            full, offsets = _pages_text(doc)
            n = len(doc)
            if not full.strip():
                stats["errors"] += 1
                rows.append({**hitl_extra_columns(), "ejercicio": ej, "slug": slug,
                             "source_pdf": pdf.name, "focus_file": "", "segment_method": "",
                             "page_start": "", "page_end": "", "char_start": "", "char_end": "",
                             "txt_chars": 0, "confidence": 0, "error_class": "empty_text",
                             "error_detail": "sin capa de texto"})
                continue
            res = find_predial_section(
                text=full, start_specs=_START_SPECS, end_specs=_END_SPECS,
                context_validator=_ctx_validator, max_chars=18_000, min_chars=300,
                fallback_chars=0,
            )
            if res.found:
                seg = full[res.start_char:res.end_char].strip()
                ps = _char_to_page(res.start_char, offsets, n)
                pe = min(_char_to_page(max(res.end_char - 1, 0), offsets, n) + 1, n)
                method, conf = res.method, res.confidence
                stats["fallback" if method.endswith("_unvalidated") else "found"] += 1
            else:
                ps = min(2, n - 1)
                pe = min(ps + FALLBACK_PAGES, n)
                seg = "\n".join(doc[p].get_text("text") or "" for p in range(ps, pe)).strip()
                method, conf = f"fallback_{pe - ps}pp", 0.3
                stats["fallback"] += 1
            header = (f"# Estado: {config.ESTADO_NOMBRE}\n# Municipio (slug): {slug}\n"
                      f"# Ejercicio: {ej}\n# Fuente: {pdf.name}\n"
                      f"# Paginas predial: {ps + 1}-{pe}\n# Metodo: {method}\n\n")
            txt_out.write_text(header + seg, encoding="utf-8")
            out_doc = fitz.open()
            try:
                for p in range(ps, min(pe, n)):
                    out_doc.insert_pdf(doc, from_page=p, to_page=p)
                out_doc.save(str(pdf_out))
            finally:
                out_doc.close()
            rows.append({**hitl_extra_columns(res if res.found else None),
                         "ejercicio": ej, "slug": slug, "source_pdf": pdf.name,
                         "focus_file": txt_out.name, "segment_method": method,
                         "page_start": ps + 1, "page_end": pe,
                         "char_start": res.start_char if res.found else "",
                         "char_end": res.end_char if res.found else "",
                         "txt_chars": len(header) + len(seg), "confidence": round(conf, 3),
                         "error_class": "" if res.found else "fallback", "error_detail": ""})
        finally:
            doc.close()

    with segment_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_SEGMENT_FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"  Total {stats['total']} | exacta {stats['found']} | fallback {stats['fallback']} "
          f"| errores {stats['errors']}")
    print(f"  Bitacora: {segment_csv}")
    return segment_csv
