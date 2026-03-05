"""
Elimina archivos .json dentro de data/jalisco (recursivamente) si:
  - Algún campo 'tasa_millar' o 'tarifa_millar' es estrictamente mayor a 19, O
  - Algún campo 'tipo_esquema' tiene el valor 'desconocido', O
  - Algún campo 'tipo_esquema' tiene el valor 'tasa_unica'.
"""

import json
import os
from pathlib import Path

# Valores de tipo_esquema que provocan eliminación
ESQUEMAS_INVALIDOS = {"desconocido", "tasa_unica", "mixto"}


def contiene_tasa_mayor_a_19(data, umbral: float = 19.0) -> bool:
    """
    Recorre recursivamente un objeto JSON y retorna True si encuentra
    algún valor de 'tasa_millar' o 'tarifa_millar' estrictamente mayor al umbral.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key in ("tasa_millar", "tarifa_millar"):
                if isinstance(value, (int, float)) and value > umbral:
                    return True
            if isinstance(value, (dict, list)):
                if contiene_tasa_mayor_a_19(value, umbral):
                    return True
    elif isinstance(data, list):
        for item in data:
            if contiene_tasa_mayor_a_19(item, umbral):
                return True
    return False


def esquema_invalido(data) -> str | None:
    """
    Recorre recursivamente un objeto JSON y retorna el valor de 'tipo_esquema'
    si es uno de los esquemas inválidos, o None si no se encuentra ninguno.
    """
    if isinstance(data, dict):
        for key, value in data.items():
            if key == "tipo_esquema" and value in ESQUEMAS_INVALIDOS:
                return value
            if isinstance(value, (dict, list)):
                result = esquema_invalido(value)
                if result is not None:
                    return result
    elif isinstance(data, list):
        for item in data:
            result = esquema_invalido(item)
            if result is not None:
                return result
    return None


def motivo_eliminacion(data, umbral: float = 19.0) -> str | None:
    """Retorna el motivo de eliminación, o None si el archivo debe conservarse."""
    razones = []
    if contiene_tasa_mayor_a_19(data, umbral):
        razones.append(f"tasa_millar/tarifa_millar > {umbral}")
    esquema = esquema_invalido(data)
    if esquema:
        razones.append(f'tipo_esquema = "{esquema}"')
    return " | ".join(razones) if razones else None


def procesar_directorio(base_dir: str, umbral: float = 19.0, dry_run: bool = False):
    base_path = Path(base_dir)
    if not base_path.exists():
        print(f"[ERROR] El directorio '{base_dir}' no existe.")
        return

    archivos_revisados = 0
    archivos_eliminados = 0
    archivos_con_error = 0

    for json_path in sorted(base_path.rglob("*.json")):
        archivos_revisados += 1
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  [ADVERTENCIA] No se pudo leer '{json_path}': {e}")
            archivos_con_error += 1
            continue

        motivo = motivo_eliminacion(data, umbral)
        if motivo:
            if dry_run:
                print(f"  [DRY-RUN] Se eliminaría: {json_path}  ({motivo})")
            else:
                os.remove(json_path)
                print(f"  [ELIMINADO] {json_path}  ({motivo})")
            archivos_eliminados += 1
        else:
            print(f"  [OK]        {json_path}")

    print("\n" + "=" * 60)
    print(f"Archivos revisados : {archivos_revisados}")
    print(f"Archivos {'que se eliminarían' if dry_run else 'eliminados'}: {archivos_eliminados}")
    print(f"Archivos con error : {archivos_con_error}")
    if dry_run:
        print("\n(Modo DRY-RUN activo — ningún archivo fue eliminado)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            "Elimina .json en data/jalisco donde:\n"
            "  - tasa_millar o tarifa_millar > umbral, O\n"
            '  - tipo_esquema == "desconocido", O\n'
            '  - tipo_esquema == "tasa_unica"'
            '  - tipo_esquema == "mixto"'
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--dir",
        default=r"data\jalisco",
        help="Directorio raíz de búsqueda (default: data\\jalisco)",
    )
    parser.add_argument(
        "--umbral",
        type=float,
        default=19.0,
        help="Umbral estricto para tasas (default: 19).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra qué se eliminaría, sin borrar nada.",
    )
    args = parser.parse_args()

    print(f"Directorio : {args.dir}")
    print(f"Umbral     : > {args.umbral}")
    print(f"Esquemas inválidos : {sorted(ESQUEMAS_INVALIDOS)}")
    print(f"Modo       : {'DRY-RUN' if args.dry_run else 'ELIMINACIÓN REAL'}")
    print("=" * 60)

    procesar_directorio(args.dir, umbral=args.umbral, dry_run=args.dry_run)