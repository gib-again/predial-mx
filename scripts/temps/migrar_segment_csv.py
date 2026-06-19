"""Migra los ``segment.csv`` existentes al esquema único canónico (con ``cvegeo``).

Lee ``data/{estado}/meta/segment.csv`` (formato legado por-estado), resuelve
``cvegeo`` vía catálogo INEGI (usando ``config.ALIASES``), une ``ley_page_start``
del master donde aplique, y reescribe en el esquema canónico
(``segment_schema.SEGMENT_FIELDS``).

Es una reescritura de outputs (sin API).  Idempotente.

Uso:
  python -m scripts.temps.migrar_segment_csv --dry-run
  python -m scripts.temps.migrar_segment_csv
  python -m scripts.temps.migrar_segment_csv --estado coahuila
"""

from __future__ import annotations

import argparse
import importlib
from pathlib import Path

from src.core.constants import CVE_ENT_ESTADO
from src.core.segment_schema import (
    STATUS_IDENTIDAD,
    STATUS_NO_LOCALIZADA,
    canonicalize_segment_rows,
    read_segment_csv,
    write_segment_csv,
)

DATA = Path("data")


def _estados_con_segment() -> list[str]:
    return [e for e in CVE_ENT_ESTADO if (DATA / e / "meta" / "segment.csv").exists()]


def _aliases(estado_slug: str) -> dict[str, str]:
    try:
        mod = importlib.import_module(f"src.estados.{estado_slug}.config")
        return dict(getattr(mod, "ALIASES", {}) or {})
    except Exception:
        return {}


def migrate_estado(estado_slug: str, dry_run: bool) -> tuple[int, int]:
    path = DATA / estado_slug / "meta" / "segment.csv"
    rows = read_segment_csv(path)
    canon = canonicalize_segment_rows(estado_slug, rows, aliases=_aliases(estado_slug))
    n = len(canon)
    n_id = sum(1 for r in canon if r.status == STATUS_IDENTIDAD)
    n_nl = sum(1 for r in canon if r.status == STATUS_NO_LOCALIZADA)
    n_ley = sum(1 for r in canon if str(r.ley_page_start).strip())
    print(
        f"  {estado_slug:14s} filas={n:4d}  cvegeo_ok={n - n_id:4d}  "
        f"identidad_no_resuelta={n_id:3d}  no_localizada={n_nl:3d}  ley_page={n_ley:4d}"
    )
    if not dry_run:
        write_segment_csv(canon, path)
    return n, n_id


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--estado", help="Migrar un solo estado")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    estados = [args.estado] if args.estado else _estados_con_segment()
    total = total_id = 0
    for e in estados:
        n, nid = migrate_estado(e, args.dry_run)
        total += n
        total_id += nid
    print(f"\nTotal filas={total}  identidad_no_resuelta={total_id}")
    if args.dry_run:
        print("(dry-run: nada escrito)")


if __name__ == "__main__":
    main()
