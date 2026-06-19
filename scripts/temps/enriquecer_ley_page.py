"""Rellena ley_page_start + source_pdf (resolvable) en segment.csv de QRO y SLP.

§5 del plan: estos dos estados no traían `ley_page_start`, así que el botón
"inicio de la ley" no podía renderizar.  Casos:

- **Querétaro** (tomos compartidos multi-parte): el master `muni_starts.csv` ya
  localiza el inicio de cada ley (start_part, start_page).  Se une por (cvegeo,
  año) y se rellena `ley_page_start` = start_page y `source_pdf` = ruta real de
  esa parte (el doc_id base no es un archivo servible).
- **San Luis Potosí** (un PDF por ley): `ley_page_start` = 1 (lo fija la regla
  ONE_LEY_PER_PDF de segment_schema); aquí sólo se reescribe `source_pdf` al
  path completo bajo pdf_raw/ para que el PDF sea servible.

Reescritura de output (sin API).  Idempotente.  --dry-run para inspeccionar.

Uso:
  python -m scripts.temps.enriquecer_ley_page --dry-run
  python -m scripts.temps.enriquecer_ley_page
"""

from __future__ import annotations

import argparse
import csv
import importlib
from pathlib import Path

from src.core.catalog import resolve_cvegeo
from src.core.segment_schema import read_segment_csv, write_segment_csv

DATA = Path("data")


def _qro_ley_map() -> dict[tuple[str, str], tuple[str, str]]:
    """(cvegeo, anio) -> (ley_page_start, source_pdf_part_path) para Querétaro."""
    cfg = importlib.import_module("src.estados.queretaro.config")
    aliases = dict(getattr(cfg, "ALIASES", {}) or {})
    pdf_raw = DATA / "queretaro" / "pdf_raw"
    out: dict[tuple[str, str], tuple[str, str]] = {}
    ms = DATA / "queretaro" / "meta" / "muni_starts.csv"
    if not ms.exists():
        return out
    with ms.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            cvegeo = resolve_cvegeo("queretaro", r.get("municipio", ""), aliases)
            anio = str(r.get("ejercicio", "")).strip()
            if not cvegeo or not anio:
                continue
            parts = [p for p in (r.get("parts", "") or "").split(";") if p]
            try:
                sp = int(r.get("start_part", 1))
            except ValueError:
                sp = 1
            part = parts[sp - 1] if 0 < sp <= len(parts) else (parts[0] if parts else "")
            source_pdf = str((pdf_raw / part).as_posix()) if part else ""
            out[(cvegeo, anio)] = (str(r.get("start_page", "")).strip(), source_pdf)
    return out


def enrich_queretaro(dry_run: bool) -> None:
    seg_path = DATA / "queretaro" / "meta" / "segment.csv"
    rows = read_segment_csv(seg_path)
    ley = _qro_ley_map()
    n_ley = n_pdf = n_miss = 0
    for r in rows:
        hit = ley.get((r.get("cvegeo", ""), str(r.get("anio", ""))))
        if not hit:
            n_miss += 1
            continue
        start_page, source_pdf = hit
        if start_page:
            r["ley_page_start"] = start_page
            n_ley += 1
        if source_pdf:
            r["source_pdf"] = source_pdf
            n_pdf += 1
    print(f"  queretaro: {len(rows)} filas | ley_page_start={n_ley} | "
          f"source_pdf={n_pdf} | sin match={n_miss}")
    if not dry_run:
        write_segment_csv(rows, seg_path)


def enrich_sanluispotosi(dry_run: bool) -> None:
    seg_path = DATA / "sanluispotosi" / "meta" / "segment.csv"
    raw_dir = DATA / "sanluispotosi" / "pdf_raw"
    ocr_dir = DATA / "sanluispotosi" / "pdf_ocr"
    rows = read_segment_csv(seg_path)
    n_pdf = n_ley = n_miss = 0
    for r in rows:
        if not str(r.get("ley_page_start", "")).strip():
            r["ley_page_start"] = 1  # un PDF por ley
            n_ley += 1
        sp = r.get("source_pdf", "")
        # Reescribir nombre suelto → ruta completa servible (pdf_raw o pdf_ocr,
        # según los _ocr.pdf escaneados).
        if sp and not sp.startswith("data/"):
            anio = str(r.get("anio", "")).strip()
            name = Path(sp).name
            cand = next(
                (d / anio / name for d in (raw_dir, ocr_dir) if (d / anio / name).exists()),
                None,
            )
            if cand is not None:
                r["source_pdf"] = str(cand.as_posix())
                n_pdf += 1
            else:
                n_miss += 1
    print(f"  sanluispotosi: {len(rows)} filas | ley_page_start(=1)={n_ley} | "
          f"source_pdf reescrito={n_pdf} | sin archivo={n_miss}")
    if not dry_run:
        write_segment_csv(rows, seg_path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    enrich_queretaro(args.dry_run)
    enrich_sanluispotosi(args.dry_run)
    if args.dry_run:
        print("(dry-run: nada escrito)")


if __name__ == "__main__":
    main()
