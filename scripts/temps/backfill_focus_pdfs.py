"""Backfill one-shot de PDFs faltantes en `data/<estado>/focus_predial/`.

Convención del proyecto (ver `src/estados/CLAUDE.md`): cada `segment.py`
debe producir TANTO el TXT como el PDF correspondiente en
`focus_predial/<año>/<PREFIJO>_PREDIAL_<año>_<slug>.{txt,pdf}`. Yucatán
históricamente solo produjo TXTs (1,462 archivos sin PDF, 2.7% cobertura);
otros estados tienen unos pocos cabos sueltos por races/errores
puntuales.

Este script regenera los PDFs faltantes:

  - **Yucatán**: lee `data/yucatan/meta/segment.csv` (page ranges
    `predial_page_start`/`predial_page_end`) y extrae las páginas del PDF
    fuente en `data/yucatan/pdf_raw/<source_pdf>` con
    `src.core.segment_utils.save_focus_pdf`.
  - **Mérida (caso especial)**: copia el PDF completo desde
    `data/yucatan/pdf_raw/merida/merida_hacienda_<año>.pdf`.
  - **Otros estados**: lista los TXTs sin PDF homónimo pero NO los regenera
    automáticamente (no tienen segment.csv estandarizado en todos los
    casos); imprime un reporte para revisión manual.

Uso:
  python -m scripts.temps.backfill_focus_pdfs               # all states
  python -m scripts.temps.backfill_focus_pdfs --estado yucatan
  python -m scripts.temps.backfill_focus_pdfs --dry-run     # solo reporta
"""

from __future__ import annotations

import argparse
import csv
import shutil
from collections import defaultdict
from pathlib import Path

from src.core.segment_utils import save_focus_pdf

DATA_ROOT = Path("data")
ESTADOS_LLM = [
    "coahuila", "guanajuato", "jalisco", "oaxaca", "queretaro",
    "sanluispotosi", "sonora", "tamaulipas", "yucatan",
]


def _txts_sin_pdf(estado: str) -> list[Path]:
    """Lista TXTs en focus_predial que no tienen PDF homónimo."""
    fp = DATA_ROOT / estado / "focus_predial"
    if not fp.exists():
        return []
    faltantes = []
    for txt in fp.rglob("*.txt"):
        pdf = txt.with_suffix(".pdf")
        if not pdf.exists():
            faltantes.append(txt)
    return faltantes


def backfill_yucatan(dry_run: bool = False) -> tuple[int, int, int]:
    """Regenera PDFs faltantes en yucatan/focus_predial usando segment.csv.

    Returns: (n_intentos, n_ok, n_skip)
    """
    seg_csv = DATA_ROOT / "yucatan" / "meta" / "segment.csv"
    pdf_raw = DATA_ROOT / "yucatan" / "pdf_raw"
    focus = DATA_ROOT / "yucatan" / "focus_predial"

    if not seg_csv.exists():
        print(f"  [SKIP] no existe {seg_csv}")
        return (0, 0, 0)

    n_intentos = n_ok = n_skip = 0
    by_source: dict[str, int] = defaultdict(int)

    with seg_csv.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("predial_found") != "true":
                continue
            txt_name = row["txt_file"]
            txt_path = focus / row["ejercicio"] / txt_name
            pdf_dst = txt_path.with_suffix(".pdf")
            if pdf_dst.exists():
                n_skip += 1
                continue
            if not txt_path.exists():
                # TXT marcado en segment.csv pero no en disco — saltar.
                continue
            try:
                p_start = int(row["predial_page_start"])
                p_end = int(row["predial_page_end"])
            except (ValueError, KeyError):
                continue
            src_pdf = pdf_raw / row["source_pdf"].replace("\\", "/")
            n_intentos += 1
            if dry_run:
                continue
            if save_focus_pdf(src_pdf, p_start, p_end, pdf_dst):
                n_ok += 1
                by_source[row["source_pdf"]] += 1
            else:
                # Probable: PDF source faltante o páginas inválidas.
                pass

    # Mérida: copiar PDFs completos.
    merida_raw = pdf_raw / "merida"
    merida_ok = 0
    if merida_raw.exists():
        for txt in focus.rglob("*_merida.txt"):
            pdf_dst = txt.with_suffix(".pdf")
            if pdf_dst.exists():
                continue
            # Extraer año del nombre del archivo (YUC_PREDIAL_YYYY_merida.txt).
            parts = txt.stem.split("_")
            try:
                anio = next(p for p in parts if p.isdigit() and len(p) == 4)
            except StopIteration:
                continue
            src = merida_raw / f"merida_hacienda_{anio}.pdf"
            if not src.exists():
                # Replicas: usa 2022 como source.
                src = merida_raw / "merida_hacienda_2022.pdf"
            if src.exists():
                n_intentos += 1
                if dry_run:
                    continue
                try:
                    shutil.copy2(src, pdf_dst)
                    merida_ok += 1
                    n_ok += 1
                except Exception:
                    pass

    print(f"  Yucatán: intentos={n_intentos} ok={n_ok} ya_existian={n_skip} "
          f"(mérida_copied={merida_ok})")
    return (n_intentos, n_ok, n_skip)


def reporte_otros_estados(estado: str) -> int:
    """Imprime TXTs sin PDF en estados distintos a yucatán (no regenera)."""
    faltantes = _txts_sin_pdf(estado)
    if faltantes:
        print(f"  {estado}: {len(faltantes)} TXTs sin PDF homónimo "
              f"(no se regeneran automáticamente — requieren inspección)")
        for p in faltantes[:5]:
            print(f"    {p}")
        if len(faltantes) > 5:
            print(f"    … y {len(faltantes) - 5} más")
    return len(faltantes)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--estado", help="Solo un estado (default: todos).")
    ap.add_argument("--dry-run", action="store_true",
                    help="Reporta lo que haría sin escribir archivos.")
    args = ap.parse_args()

    estados = [args.estado] if args.estado else ESTADOS_LLM

    print(f"Modo: {'dry-run (sin escribir)' if args.dry_run else 'escribiendo PDFs'}")
    print()

    n_total = 0
    if "yucatan" in estados:
        print("== Yucatán (con segment.csv) ==")
        _, n_ok, _ = backfill_yucatan(dry_run=args.dry_run)
        n_total += n_ok

    otros = [e for e in estados if e != "yucatan"]
    if otros:
        print()
        print("== Otros estados (reporte de TXTs huérfanos) ==")
        for est in otros:
            reporte_otros_estados(est)

    print()
    if not args.dry_run:
        print(f"Total PDFs regenerados: {n_total}")
        print("Verifica cobertura con:")
        print("  python -m scripts.temps.backfill_focus_pdfs --dry-run")


if __name__ == "__main__":
    main()
