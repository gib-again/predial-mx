"""Reubica el corpus v3 al layout por-año bajo data/.

  predial-mx-v3/{estado}/{PREFIJO}_PREDIAL_{anio}_{slug}.json
    → data/{estado}/json_predial/{anio}/{mismo archivo}

  predial-mx-v3-hitl/{estado}/...   → data/{estado}/json_predial_hitl/{anio}/...

Es un movimiento de archivos (sin API, sin re-extraer).  Idempotente: si el
destino ya existe y es idéntico, omite; si la fuente ya no existe, no hace nada.

Uso:
  python -m scripts.temps.migrar_corpus_v3 --dry-run
  python -m scripts.temps.migrar_corpus_v3
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from src.core.constants import json_predial_dir, json_predial_hitl_dir
from src.core.corpus import parse_fname

ROOT = Path(".")
LEGACY_V3 = ROOT / "predial-mx-v3"
LEGACY_HITL = ROOT / "predial-mx-v3-hitl"


def _migrate_root(legacy_root: Path, dest_fn, dry_run: bool) -> tuple[int, int]:
    moved = skipped = 0
    if not legacy_root.exists():
        return 0, 0
    for est_dir in sorted(p for p in legacy_root.iterdir() if p.is_dir()):
        estado = est_dir.name
        for src in sorted(est_dir.glob("*.json")):
            parsed = parse_fname(src)
            if not parsed:
                print(f"  [skip] nombre no parseable: {src.name}")
                skipped += 1
                continue
            anio, _ = parsed
            dst = dest_fn(estado, anio) / src.name
            if dst.exists():
                skipped += 1
                continue
            if not dry_run:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dst))
            moved += 1
    return moved, skipped


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    mv3, sk3 = _migrate_root(LEGACY_V3, json_predial_dir, args.dry_run)
    print(f"v3 canónico:  movidos={mv3}  omitidos={sk3}")
    mvh, skh = _migrate_root(LEGACY_HITL, json_predial_hitl_dir, args.dry_run)
    print(f"v3 HITL:      movidos={mvh}  omitidos={skh}")
    if args.dry_run:
        print("(dry-run: nada movido)")
    else:
        # Limpiar carpetas legadas vacías
        for legacy in (LEGACY_V3, LEGACY_HITL):
            if legacy.exists() and not any(legacy.rglob("*.json")):
                shutil.rmtree(legacy, ignore_errors=True)
                print(f"  removido directorio legado vacío: {legacy}")


if __name__ == "__main__":
    main()
