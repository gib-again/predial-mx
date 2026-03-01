"""
Script para eliminar JSONs con esquema_valido=False según un CSV summary.

Uso:
Dry-run (simulación, no borra nada):
python scripts/delete_invalid_jsons_from_summary.py

Para borrar de verdad:
python scripts/delete_invalid_jsons_from_summary.py --apply
"""

from __future__ import annotations

import csv
import argparse
from pathlib import Path


FALSE_VALUES = {"false", "0", "no", "n", "f", ""}


def parse_bool_like(value: str) -> bool:
    """Interpreta strings tipo True/False."""
    if value is None:
        return False
    v = str(value).strip().lower()
    if v in FALSE_VALUES:
        return False
    return v in {"true", "1", "yes", "y", "t"}


def main():
    parser = argparse.ArgumentParser(
        description="Elimina JSONs con esquema_valido=False desde un summary CSV."
    )
    parser.add_argument(
        "--summary",
        #Ajusta esta ruta de acuerdo al estado que quieras revisar. Por ejemplo, para Tamaulipas sería:
        default=r"data/tamaulipas/meta/tamaulipas_predial_summary.csv",
        help="Ruta al CSV summary",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Si se incluye, borra archivos. Si no, solo simula (dry-run).",
    )
    args = parser.parse_args()

    summary_path = Path(args.summary)
    if not summary_path.exists():
        raise FileNotFoundError(f"No existe el summary: {summary_path}")

    # Asumimos que ejecutas desde la raíz del repo (predial-mx)
    repo_root = Path.cwd()

    to_delete = []
    missing = []
    rows_total = 0
    invalid_rows = 0

    with summary_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"esquema_valido", "json_path"}
        missing_cols = required - set(reader.fieldnames or [])
        if missing_cols:
            raise ValueError(f"Faltan columnas requeridas en CSV: {missing_cols}")

        for row in reader:
            rows_total += 1
            esquema_valido = parse_bool_like(row.get("esquema_valido", ""))

            if esquema_valido:
                continue

            invalid_rows += 1
            raw_path = (row.get("json_path") or "").strip()
            if not raw_path:
                continue

            # Normaliza rutas Windows (backslashes) a Path
            json_path = Path(raw_path.replace("\\", "/"))

            # Si viene relativa (como en tu CSV), la resolvemos desde raíz del repo
            if not json_path.is_absolute():
                json_path = repo_root / json_path

            if json_path.exists():
                to_delete.append((json_path, row))
            else:
                missing.append((json_path, row))

    print("=" * 60)
    print(f"Summary: {summary_path}")
    print(f"Filas totales: {rows_total}")
    print(f"Filas con esquema_valido=False: {invalid_rows}")
    print(f"Archivos encontrados para borrar: {len(to_delete)}")
    print(f"Archivos NO encontrados: {len(missing)}")
    print("=" * 60)

    # Muestra ejemplos
    if to_delete:
        print("\nEjemplos a borrar:")
        for p, row in to_delete[:10]:
            print(f"  - {p}  ({row.get('municipio_slug','?')} {row.get('anio','?')})")

    if missing:
        print("\nEjemplos NO encontrados:")
        for p, row in missing[:10]:
            print(f"  - {p}  ({row.get('municipio_slug','?')} {row.get('anio','?')})")

    if not args.apply:
        print("\n[DRY-RUN] No se borró nada.")
        print("Para borrar de verdad, ejecuta con: --apply")
        return

    deleted = 0
    errors = 0

    for p, _row in to_delete:
        try:
            p.unlink()
            deleted += 1
        except Exception as e:
            errors += 1
            print(f"[ERROR] No se pudo borrar {p}: {e}")

    print("\n" + "=" * 60)
    print(f"Borrados: {deleted}")
    print(f"Errores: {errors}")
    print("=" * 60)


if __name__ == "__main__":
    main()    