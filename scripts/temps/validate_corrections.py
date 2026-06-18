#!/usr/bin/env python3
"""
Valida JSONs corregidos manualmente contra schema v3 (default) o v2.

Uso:
    # Solo validar (no copia nada)
    python -m scripts.validate_corrections {estado} --source json_corregidos/

    # Validar y copiar los válidos a json_predial/
    python -m scripts.validate_corrections {estado} --source json_corregidos/ --apply

    # Forzar validación v2
    python -m scripts.validate_corrections {estado} --source dir/ --schema v2
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

from src.estados import get_adapter


def validate_and_apply(
    estado: str,
    source_dir: Path,
    apply: bool = False,
    schema: str = "v3",
) -> int:
    """
    Valida JSONs en source_dir contra PredialSchema (Pydantic).

    Args:
        estado: Slug del estado
        source_dir: Carpeta con JSONs corregidos (puede tener subcarpetas por año)
        apply: Si True, copia los JSONs válidos a json_predial/

    Returns:
        Número de errores encontrados
    """
    adapter = get_adapter(estado)
    json_dir = adapter.json_dir
    prefijo = adapter.prefijo

    json_files = sorted(source_dir.rglob(f"{prefijo}_PREDIAL_*.json"))
    if not json_files:
        json_files = sorted(source_dir.rglob("*.json"))

    if not json_files:
        print(f"  No se encontraron JSONs en {source_dir}")
        return 0

    if schema == "v3":
        from src.extraction.schema_v3 import PredialV3 as ValidatorModel
    else:
        from src.core.schemas import PredialSchema as ValidatorModel

    print(f"  Validando {len(json_files)} JSONs de {source_dir} (schema {schema})")

    ok_count = 0
    err_count = 0
    to_copy: list[tuple[Path, Path]] = []

    for jf in json_files:
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
            predial_data = data.get("predial", data)
            ValidatorModel(**predial_data)

            # Determinar destino
            parts = jf.stem.split("_", 3)
            if len(parts) >= 4:
                anio = parts[2]
                dest = json_dir / anio / jf.name
            else:
                dest = json_dir / jf.name

            to_copy.append((jf, dest))
            ok_count += 1
            print(f"    OK: {jf.name}")

        except json.JSONDecodeError as e:
            err_count += 1
            print(f"    ERROR (JSON inválido): {jf.name} → {e}")
        except Exception as e:
            err_count += 1
            print(f"    ERROR (validación): {jf.name} → {e}")

    print(f"\n  Resultado: {ok_count} válidos, {err_count} con errores")

    if err_count > 0:
        print("  ⚠ Hay errores. Corrige los JSONs antes de aplicar.")
        if apply:
            print("  --apply cancelado por errores.")
            return err_count

    if apply and to_copy:
        copied = 0
        for src, dest in to_copy:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            copied += 1
        print(f"\n  Copiados: {copied} JSONs a {json_dir}")
        print("  Corre 'audit' de nuevo para actualizar el reporte.")
    elif apply:
        print("  Nada que copiar.")
    else:
        print("\n  [DRY RUN] Usa --apply para copiar los JSONs válidos.")

    return err_count


def main():
    parser = argparse.ArgumentParser(
        description="Valida JSONs corregidos manualmente y los copia a json_predial/",
    )
    parser.add_argument("estado", help="Slug del estado (ej: guanajuato)")
    parser.add_argument(
        "--source", required=True, type=Path,
        help="Carpeta con JSONs corregidos (ej: json_corregidos/)",
    )
    parser.add_argument(
        "--apply", action="store_true",
        help="Copiar JSONs válidos a json_predial/ (sin esto solo valida)",
    )
    parser.add_argument(
        "--schema", choices=["v2", "v3"], default="v3",
        help="Schema de validación (default: v3)",
    )

    args = parser.parse_args()

    if not args.source.exists():
        print(f"  [ERROR] No existe: {args.source}")
        sys.exit(1)

    errors = validate_and_apply(args.estado, args.source, apply=args.apply, schema=args.schema)
    sys.exit(1 if errors > 0 else 0)


if __name__ == "__main__":
    main()
