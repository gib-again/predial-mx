"""
Durango FASE 3 — segmentacion 2-niveles de las gacetas OCR'd del PO.

Prueba de concepto: FY2015 (gacetas de pub 2014). Cada ley municipal es una
seccion consecutiva de paginas dentro de una gaceta; el encabezado corrido
("LEY DE INGRESOS DEL MUNICIPIO DE {X}" repetido en cada pagina) identifica al
municipio (con ruido OCR). Algoritmo:
  1. Por cada gaceta del anio de pub, leer pagina por pagina y asignar municipio
     via el encabezado corrido (fuzzy match contra el catalogo).
  2. Agrupar paginas consecutivas por municipio -> secciones de ley.
  3. Por municipio, quedarse con la seccion mas larga (la ley completa).
  4. Dentro de la seccion, localizar el predial (find_predial_section) -> focus.

Salida: focus_predial/{fy}/DGO_PREDIAL_{fy}_{slug}.txt (+ .pdf)
        meta/segment_fase3_{fy}.csv (reporte de cobertura)

Uso:  python -m scripts.temps.durango_fase3_segment --fy 2015 --pub 2014
"""

from __future__ import annotations

import argparse
import csv
import difflib
import glob
import re
import unicodedata
from pathlib import Path

import fitz  # PyMuPDF

from src.core.segment_utils import find_predial_section
from src.estados.durango import config
from src.estados.durango.segment import _END_SPECS, _START_SPECS

DATA = Path("data") / "durango"


def _norm(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Za-z]", "", s).lower()


_NORM_TO_SLUG = {_norm(name): slug for _c, name, slug in config.MUNICIPIOS}
_NORM_NAMES = list(_NORM_TO_SLUG)

_RE_HEADER = re.compile(
    r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+([A-ZÁÉÍÓÚÑ.\s]{3,30}?)"
    r"(?:,|\s+PARA|\s+DURANGO|\s+DEL\s+ESTADO|\n)", re.IGNORECASE)


def _muni_de_pagina(text: str) -> str | None:
    """Slug del municipio segun el encabezado corrido (fuzzy, tolera OCR)."""
    m = _RE_HEADER.search(" ".join(text.upper().split()))
    if not m:
        return None
    n = _norm(m.group(1))
    if not n:
        return None
    if n in _NORM_TO_SLUG:
        return _NORM_TO_SLUG[n]
    cand = difflib.get_close_matches(n, _NORM_NAMES, n=1, cutoff=0.8)
    return _NORM_TO_SLUG[cand[0]] if cand else None


def _secciones(pdf: fitz.Document) -> list[tuple[str, int, int]]:
    """(slug, page_start, page_end_excl) de cada corrida consecutiva de municipio."""
    seq: list[tuple[int, str | None]] = []
    for i in range(len(pdf)):
        seq.append((i, _muni_de_pagina(pdf[i].get_text("text") or "")))
    # rellenar huecos (paginas sin header) con el municipio anterior
    last: str | None = None
    filled: list[str | None] = []
    for _i, slug in seq:
        if slug:
            last = slug
        filled.append(last)
    # agrupar consecutivos
    runs: list[tuple[str, int, int]] = []
    cur = None
    start = 0
    for i, slug in enumerate(filled):
        if slug != cur:
            if cur:
                runs.append((cur, start, i))
            cur, start = slug, i
    if cur:
        runs.append((cur, start, len(filled)))
    return runs


def run(fy: int, pub: int) -> None:
    gazettes = sorted(glob.glob(str(DATA / "pdf_ocr" / str(pub) / "*_ocr.pdf")))
    print(f"=== Durango FASE 3 segment: FY{fy} (gacetas pub {pub}, {len(gazettes)}) ===")

    # Por municipio: la mejor seccion (mas paginas) entre todas las gacetas.
    best: dict[str, tuple[int, str, int, int]] = {}  # slug -> (npags, gaceta, ps, pe)
    for g in gazettes:
        try:
            doc = fitz.open(g)
        except Exception:
            continue
        try:
            for slug, ps, pe in _secciones(doc):
                npags = pe - ps
                if npags < 3:  # secciones muy chicas = referencia/indice, no ley
                    continue
                if slug not in best or npags > best[slug][0]:
                    best[slug] = (npags, g, ps, pe)
        finally:
            doc.close()

    rows = []
    focus_dir = DATA / "focus_predial" / str(fy)
    focus_dir.mkdir(parents=True, exist_ok=True)
    n_predial = 0
    for slug, (npags, g, ps, pe) in sorted(best.items()):
        doc = fitz.open(g)
        try:
            full = "\n".join(doc[p].get_text("text") or "" for p in range(ps, pe))
        finally:
            doc.close()
        res = find_predial_section(text=full, start_specs=_START_SPECS,
                                   end_specs=_END_SPECS, max_chars=18_000,
                                   min_chars=200, fallback_chars=0)
        if res.found:
            seg = full[res.start_char:res.end_char].strip()
            method = res.method
            n_predial += 1
        else:
            seg = full[:12000]
            method = "fallback_seccion"
        header = (f"# Estado: Durango\n# Municipio (slug): {slug}\n# Ejercicio: {fy}\n"
                  f"# Fuente: {Path(g).name} pp {ps+1}-{pe} ({npags}pp)\n"
                  f"# Metodo predial: {method}\n\n")
        (focus_dir / f"DGO_PREDIAL_{fy}_{slug}.txt").write_text(header + seg, encoding="utf-8")
        rows.append({"slug": slug, "gaceta": Path(g).name, "pp": f"{ps+1}-{pe}",
                     "npags": npags, "predial": method})

    meta = DATA / "meta" / f"segment_fase3_{fy}.csv"
    with meta.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["slug", "gaceta", "pp", "npags", "predial"])
        w.writeheader()
        w.writerows(rows)
    falta = [s for _c, _n, s in config.MUNICIPIOS if s not in best]
    print(f"  Municipios con ley: {len(best)}/39 | con predial: {n_predial}")
    print(f"  Faltan: {falta}")
    print(f"  Reporte: {meta}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fy", type=int, default=2015)
    ap.add_argument("--pub", type=int, default=2014)
    ap.add_argument("--args", default="")  # tolerar invocacion via skill
    a = ap.parse_args()
    run(a.fy, a.pub)
