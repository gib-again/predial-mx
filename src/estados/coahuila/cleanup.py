# Script para eliminar JSONs con esquema mixto/desconocido o con anomalías según el summary de Coahuila.
# Útil para limpiar el dataset antes de re run de extracción LLM, asegurando que solo se procesen leyes con esquemas claros y sin anomalías.
# Requiere el summary CSV/TSV generado en la etapa de extracción LLM,

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable, Dict, Any


BAD_SCHEMES = {"mixto", "desconocido"}


def detect_delimiter(file_path: Path) -> str:
    """
    Detecta si el archivo está separado por tabs o comas.
    Tu head sugiere tabs aunque el filename sea .csv.
    """
    sample = file_path.read_text(encoding="utf-8", errors="replace")[:4096]
    # Heurística simple y robusta:
    tabs = sample.count("\t")
    commas = sample.count(",")
    return "\t" if tabs >= commas else ","


def iter_rows(summary_path: Path) -> Iterable[Dict[str, Any]]:
    delim = detect_delimiter(summary_path)
    with summary_path.open("r", encoding="utf-8", errors="replace", newline="") as f:
        reader = csv.DictReader(f, delimiter=delim)
        for row in reader:
            # Normaliza claves por si hay BOM o espacios
            clean = { (k or "").strip().lstrip("\ufeff"): (v or "") for k, v in row.items() }
            yield clean


def is_bad(row: Dict[str, Any]) -> bool:
    tipo = (row.get("tipo_esquema") or "").strip().lower()
    anom = (row.get("anomalias") or "").strip()
    return (tipo in BAD_SCHEMES) or (anom != "")


def path_from_json_path(value: str, project_root: Path) -> Path:
    p = Path(value)
    if not p.is_absolute():
        p = project_root / p
    return p


def main():
    ap = argparse.ArgumentParser(description="Elimina JSONs con esquema mixto/desconocido o con anomalías según summary.")
    ap.add_argument("--summary", default="data/coahuila/meta/coahuila_predial_summary.csv",
                    help="Ruta al summary CSV/TSV")
    ap.add_argument("--root", default=".", help="Raíz del proyecto (para resolver rutas relativas)")
    ap.add_argument("--dry-run", action="store_true", help="Solo imprime lo que haría (recomendado primero)")
    ap.add_argument("--delete", action="store_true",
                    help="Borra de verdad. Si no pones esto, NO borra nada (aunque no pongas --dry-run).")
    ap.add_argument("--quarantine", default="",
                    help="Si se especifica, en vez de borrar mueve a esta carpeta (ej: data/coahuila/qa/quarantine_json)")
    args = ap.parse_args()

    summary_path = Path(args.summary)
    project_root = Path(args.root).resolve()
    quarantine_dir = Path(args.quarantine).resolve() if args.quarantine else None

    if not summary_path.exists():
        raise FileNotFoundError(f"No existe summary: {summary_path}")

    to_act = []
    total = 0
    for row in iter_rows(summary_path):
        total += 1
        if is_bad(row):
            jp = (row.get("json_path") or "").strip()
            if not jp:
                continue
            p = path_from_json_path(jp, project_root)
            to_act.append((row, p))

    print(f"Filas totales en summary: {total}")
    print(f"Registros marcados para eliminar/mover: {len(to_act)}")
    print(f"Modo: {'DRY-RUN' if args.dry_run or not args.delete else 'EJECUCIÓN REAL'}")
    if quarantine_dir:
        print(f"Acción: MOVER a cuarentena -> {quarantine_dir}")
    else:
        print("Acción: BORRAR archivos")

    missing = 0
    acted = 0

    if quarantine_dir:
        quarantine_dir.mkdir(parents=True, exist_ok=True)

    for row, p in to_act:
        municipio = (row.get("municipio_slug") or row.get("municipio") or "").strip()
        anio = (row.get("anio") or "").strip()
        tipo = (row.get("tipo_esquema") or "").strip()
        anom = (row.get("anomalias") or "").strip()

        if not p.exists():
            print(f"[MISSING] {p} | {municipio} {anio} | tipo={tipo} | anom={anom}")
            missing += 1
            continue

        if args.dry_run or not args.delete:
            print(f"[PLAN] {p} | {municipio} {anio} | tipo={tipo} | anom={anom}")
            continue

        # Ejecución real
        if quarantine_dir:
            # Mantén un subpath por año si existe en el path
            # (esto solo es “nice to have”)
            target = quarantine_dir / p.name
            # evita colisiones
            if target.exists():
                target = quarantine_dir / f"{p.stem}__DUP__{anio}{p.suffix}"
            p.replace(target)
            print(f"[MOVED] {p} -> {target}")
        else:
            p.unlink()
            print(f"[DELETED] {p}")

        acted += 1

    print("\nResumen:")
    print(f"  Marcados: {len(to_act)}")
    print(f"  Actuados: {acted}")
    print(f"  Missing:  {missing}")


if __name__ == "__main__":
    main()
