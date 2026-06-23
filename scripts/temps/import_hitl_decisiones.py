"""Recoge los archivos de decisiones de los asistentes y los une al log central.

Cada asistente trabaja un estado y produce su propio
``decisiones/hitl_decisiones_<estado>.csv`` (que OneDrive sincroniza de vuelta).
Como los estados son disjuntos y el log es append-only (la fila más reciente por
``id`` gana), la unión es solo concatenar — sin conflictos de llave.

Este script es idempotente: re-correrlo no duplica filas (dedup por
id+timestamp+revisor).

Uso:
    # un archivo, una carpeta, o varios (se escanean *.csv recursivamente):
    python -m scripts.temps.import_hitl_decisiones "C:/.../HITL_COAHUILA/decisiones"
    python -m scripts.temps.import_hitl_decisiones kitA/decisiones kitB/decisiones
    python -m scripts.temps.import_hitl_decisiones --dry-run "C:/.../decisiones"

Después de importar, aplica con:
    python -m scripts.temps.aplicar_decisiones_hitl --dry-run
    python -m scripts.temps.aplicar_decisiones_hitl
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from pathlib import Path

from src.hitl.decisiones import DECISION_FIELDS, DECISIONES_CSV


def _gather_files(inputs: list[str]) -> list[Path]:
    """Resuelve archivos/carpetas a una lista de CSV de decisiones."""
    files: list[Path] = []
    for raw in inputs:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.rglob("hitl_decisiones*.csv")))
        elif p.is_file():
            files.append(p)
        else:
            print(f"  AVISO: no existe, lo salto: {p}")
    # Evita re-importar el propio log central si lo pasan por error.
    return [f for f in files if f.resolve() != DECISIONES_CSV.resolve()]


def _read_rows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _key(row: dict) -> tuple:
    return (row.get("id", ""), row.get("timestamp", ""), row.get("revisor", ""))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("inputs", nargs="+", help="archivos o carpetas de decisiones")
    ap.add_argument("--dry-run", action="store_true", help="muestra qué haría, sin escribir")
    args = ap.parse_args()

    files = _gather_files(args.inputs)
    if not files:
        print("Nada que importar (no se hallaron archivos de decisiones).")
        return

    existing = _read_rows(DECISIONES_CSV) if DECISIONES_CSV.exists() else []
    seen = {_key(r) for r in existing}

    nuevas: list[dict] = []
    por_estado: Counter = Counter()
    for f in files:
        rows = _read_rows(f)
        n_file = 0
        for r in rows:
            if not (r.get("id") or "").strip():
                continue
            if _key(r) in seen:
                continue
            seen.add(_key(r))
            nuevas.append(r)
            por_estado[r.get("estado_slug", "?")] += 1
            n_file += 1
        print(f"  {f}: {len(rows)} filas, {n_file} nuevas")

    print(f"\nResumen: {len(nuevas)} decisiones nuevas "
          f"(log central ya tenía {len(existing)}).")
    for est, n in sorted(por_estado.items()):
        print(f"  {est}: +{n}")

    if not nuevas:
        print("Nada nuevo que agregar.")
        return
    if args.dry_run:
        print("\n(dry-run) No se escribió nada.  Quita --dry-run para aplicar.")
        return

    DECISIONES_CSV.parent.mkdir(parents=True, exist_ok=True)
    is_new = not DECISIONES_CSV.exists()
    with DECISIONES_CSV.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=DECISION_FIELDS, extrasaction="ignore")
        if is_new:
            w.writeheader()
        w.writerows(nuevas)
    print(f"\nAgregadas {len(nuevas)} filas a {DECISIONES_CSV}.")
    print("Siguiente: python -m scripts.temps.aplicar_decisiones_hitl --dry-run")


if __name__ == "__main__":
    main()
