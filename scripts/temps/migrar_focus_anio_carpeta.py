"""Reubica focus_predial cuyo año-de-carpeta != año-del-nombre.

Bug GTO (corregido en segment.py): los focus se guardaban en
focus_predial/{año_publicación}/ pero nombrados por ejercicio (publicación+1),
así que carpeta y nombre divergían.  La extracción lo toleraba (rglob) pero la
UI (localizar_archivos busca en focus_predial/{ejercicio}/) no encontraba el
focus.

Este script mueve cada archivo a la carpeta = año del nombre (ejercicio), que
es el que usa segment.csv (anio) y la UI.  No re-segmenta ni toca contenido.
Idempotente; no sobrescribe destinos existentes (reporta conflictos).

Uso:
  python -m scripts.temps.migrar_focus_anio_carpeta --dry-run
  python -m scripts.temps.migrar_focus_anio_carpeta            # default: guanajuato
  python -m scripts.temps.migrar_focus_anio_carpeta --estado guanajuato
"""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path

_NAME_YEAR = re.compile(r"_PREDIAL_(\d{4})_")


def migrate(estado: str, dry_run: bool) -> None:
    base = Path("data") / estado / "focus_predial"
    if not base.exists():
        print(f"  {estado}: sin focus_predial")
        return
    moved = conflict = 0
    for f in sorted(base.rglob("*")):
        if not f.is_file():
            continue
        try:
            folder = int(f.parent.name)
        except ValueError:
            continue
        m = _NAME_YEAR.search(f.name)
        if not m:
            continue
        name_year = int(m.group(1))
        if name_year == folder:
            continue
        dst = base / str(name_year) / f.name
        if dst.exists():
            conflict += 1
            continue
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(f), str(dst))
        moved += 1
    # Limpiar carpetas vacías
    if not dry_run:
        for d in sorted(base.iterdir(), reverse=True):
            if d.is_dir() and not any(d.iterdir()):
                d.rmdir()
    print(f"  {estado}: movidos={moved}  conflictos(destino_existe)={conflict}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--estado", default="guanajuato")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    migrate(args.estado, args.dry_run)
    if args.dry_run:
        print("(dry-run: nada movido)")


if __name__ == "__main__":
    main()
