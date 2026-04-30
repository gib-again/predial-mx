#!/usr/bin/env python3
"""Convierte JSONs hardcoded (data/{colima,edomex,sinaloa,tabasco}/...) al
schema_v2 y los persiste en predial-mx-v2/{estado}/.

Uso:
    python -m scripts.convert_hardcoded_to_v2 --all
    python -m scripts.convert_hardcoded_to_v2 --estado colima
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from src.core.adapters_hardcoded import (
    adapt_colima,
    adapt_edomex,
    adapt_sinaloa,
    adapt_tabasco,
)
from src.extraction.schema_v2 import (
    CuotaFijaEscalonadaSchema,
    ProgresivoSchema,
)


def _validate_v2(predial_dict: dict) -> tuple[bool, str]:
    """Valida que predial_dict parsee como ProgresivoSchema o CuotaFijaEscalonadaSchema.
    Retorna (ok, msg). msg vacío si ok."""
    tipo = predial_dict.get("tipo_esquema")
    Variant = {"progresivo": ProgresivoSchema,
               "cuota_fija_escalonada": CuotaFijaEscalonadaSchema}.get(tipo)
    if Variant is None:
        return False, f"tipo_esquema inesperado: {tipo!r}"
    try:
        Variant.model_validate(predial_dict)
        return True, ""
    except ValidationError as e:
        errs = e.errors()
        msg = errs[0].get("msg", str(e))[:200] if errs else str(e)[:200]
        return False, msg


# Estados persistibles a predial-mx-v2/. Chihuahua queda excluido (in-memory only).
SRC_DIRS: dict[str, Path] = {
    "colima":  Path("data/colima/json_predial"),
    "edomex":  Path("data/edomex/json_predial"),
    "sinaloa": Path("data/sinaloa/json_predial"),
    "tabasco": Path("data/tabasco/json"),  # ojo: distinto de json_predial
}

PREFIJOS: dict[str, str] = {
    "colima":  "COL",
    "edomex":  "MEX",
    "sinaloa": "SIN",
    "tabasco": "TAB",
}

ADAPTERS = {
    "colima":  adapt_colima,
    "edomex":  adapt_edomex,
    "sinaloa": adapt_sinaloa,
    "tabasco": adapt_tabasco,
}


def _convert_estado(estado: str, dest_root: Path, dry_run: bool) -> tuple[int, int, list[str]]:
    src_dir = SRC_DIRS[estado]
    if not src_dir.exists():
        print(f"  [{estado}] directorio fuente no existe: {src_dir}")
        return 0, 0, []

    adapter = ADAPTERS[estado]
    prefijo = PREFIJOS[estado]
    dest_dir = dest_root / estado
    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    n_ok = 0
    n_skip = 0
    errors: list[str] = []

    for src_path in sorted(src_dir.rglob("*.json")):
        try:
            src = json.loads(src_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"{src_path.name}: read failed ({e})")
            n_skip += 1
            continue

        try:
            v2_doc = adapter(src)
        except Exception as e:
            errors.append(f"{src_path.name}: adapter failed ({e})")
            n_skip += 1
            continue

        ok, msg = _validate_v2(v2_doc["predial"])
        if not ok:
            errors.append(f"{src_path.name}: {msg}")
            n_skip += 1
            continue

        anio = src["ejercicio"]
        slug = src["slug"]
        out_name = f"{prefijo}_PREDIAL_{anio}_{slug}.json"
        out_path = dest_dir / out_name
        if not dry_run:
            out_path.write_text(
                json.dumps(v2_doc, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        n_ok += 1

    return n_ok, n_skip, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--estado", choices=list(SRC_DIRS), help="Convertir un estado.")
    ap.add_argument("--all", action="store_true", help="Convertir todos los estados.")
    ap.add_argument("--dest", default="predial-mx-v2",
                    help="Raíz de salida (default: predial-mx-v2).")
    ap.add_argument("--dry-run", action="store_true",
                    help="No escribir archivos; solo reportar.")
    args = ap.parse_args()

    if not (args.all or args.estado):
        ap.error("Debes pasar --all o --estado <slug>.")

    estados = list(SRC_DIRS) if args.all else [args.estado]
    dest_root = Path(args.dest)

    total_ok = 0
    total_skip = 0
    all_errors: list[tuple[str, str]] = []

    for estado in estados:
        print(f"\n[{estado}] convirtiendo desde {SRC_DIRS[estado]} -> {dest_root / estado}/")
        n_ok, n_skip, errors = _convert_estado(estado, dest_root, args.dry_run)
        print(f"  OK: {n_ok}  SKIP: {n_skip}")
        for err in errors[:10]:
            print(f"    ! {err}")
        if len(errors) > 10:
            print(f"    ... ({len(errors) - 10} más)")
        total_ok += n_ok
        total_skip += n_skip
        all_errors.extend((estado, e) for e in errors)

    print(f"\n=== Total: OK={total_ok}  SKIP={total_skip}  Errores={len(all_errors)} ===")


if __name__ == "__main__":
    main()
