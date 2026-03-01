from __future__ import annotations

import argparse
import shutil
from pathlib import Path


STATE_SLUG = "jalisco"
STATE_PREFIX = "JAL"


def parse_args():
    parser = argparse.ArgumentParser(
        description="Reorganiza archivos de jal_migrate al formato estandarizado en data/jalisco."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=Path("jal_migrate"),
        help="Ruta raíz de la estructura actual.",
    )
    parser.add_argument(
        "--dest-root",
        type=Path,
        default=Path("data") / STATE_SLUG,
        help="Ruta raíz de destino para el estado.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo muestra qué haría, sin mover archivos.",
    )
    parser.add_argument(
        "--copy",
        action="store_true",
        help="Copia en vez de mover.",
    )
    return parser.parse_args()


def normalize_ext(path: Path) -> str:
    return path.suffix.lower()


def build_destination(source_root: Path, dest_root: Path, src_file: Path) -> Path:
    """
    Espera rutas tipo:
      source_root / <categoria> / <municipio> / <anio> / <archivo>

    Categorías soportadas:
      - json_predial
      - pdf_predial
      - txt_predial
      - pdf_raw   (incluye OCR si el nombre termina con _ocr.pdf)
    """
    rel = src_file.relative_to(source_root)
    parts = rel.parts

    if len(parts) != 4:
        raise ValueError(
            f"Estructura inesperada (se esperaban 4 niveles relativos): {src_file}"
        )

    category, muni_slug, year, filename = parts
    ext = normalize_ext(src_file)
    lower_name = src_file.name.lower()

    if category == "json_predial":
        dest_dir = dest_root / "json_predial" / year
        dest_name = f"{STATE_PREFIX}_PREDIAL_{year}_{muni_slug}.json"

    elif category == "pdf_predial":
        dest_dir = dest_root / "focus_predial" / year
        dest_name = f"{STATE_PREFIX}_PREDIAL_{year}_{muni_slug}.pdf"

    elif category == "txt_predial":
        dest_dir = dest_root / "focus_predial" / year
        dest_name = f"{STATE_PREFIX}_PREDIAL_{year}_{muni_slug}.txt"

    elif category == "pdf_raw":
        if ext != ".pdf":
            raise ValueError(f"Archivo no soportado en pdf_raw: {src_file}")

        if lower_name.endswith("_ocr.pdf"):
            dest_dir = dest_root / "pdf_ocr" / year
            dest_name = f"{STATE_PREFIX}_RAW_{year}_{muni_slug}_ocr.pdf"
        else:
            dest_dir = dest_root / "pdf_raw" / year
            dest_name = f"{STATE_PREFIX}_RAW_{year}_{muni_slug}.pdf"

    else:
        raise ValueError(f"Categoría no soportada: {category}")

    return dest_dir / dest_name


def collect_files(source_root: Path) -> list[Path]:
    categories = ["json_predial", "pdf_predial", "txt_predial", "pdf_raw"]
    files = []

    for category in categories:
        cat_dir = source_root / category
        if not cat_dir.exists():
            print(f"[WARN] No existe la carpeta: {cat_dir}")
            continue

        for path in cat_dir.rglob("*"):
            if path.is_file():
                files.append(path)

    return sorted(files)


def transfer_file(src: Path, dst: Path, do_copy: bool, dry_run: bool) -> None:
    if dry_run:
        action = "COPY" if do_copy else "MOVE"
        print(f"[{action}] {src} -> {dst}")
        return

    dst.parent.mkdir(parents=True, exist_ok=True)

    if do_copy:
        shutil.copy2(src, dst)
    else:
        shutil.move(str(src), str(dst))


def main():
    args = parse_args()

    source_root = args.source_root
    dest_root = args.dest_root
    dry_run = args.dry_run
    do_copy = args.copy

    if not source_root.exists():
        raise FileNotFoundError(f"No existe source_root: {source_root}")

    files = collect_files(source_root)

    moved = 0
    skipped_existing = 0
    skipped_collision = 0
    errors = 0

    planned_destinations: set[Path] = set()

    for src_file in files:
        try:
            dst_file = build_destination(source_root, dest_root, src_file)

            # Evita colisiones dentro de la misma corrida
            if dst_file in planned_destinations:
                skipped_collision += 1
                print(f"[SKIP collision] {src_file} -> {dst_file}")
                continue

            # Evita duplicados si ya existe el destino
            if dst_file.exists():
                skipped_existing += 1
                print(f"[SKIP existing] {src_file} -> {dst_file}")
                continue

            # Evita mover sobre sí mismo
            if src_file.resolve() == dst_file.resolve():
                skipped_existing += 1
                print(f"[SKIP same file] {src_file}")
                continue

            transfer_file(src_file, dst_file, do_copy=do_copy, dry_run=dry_run)
            planned_destinations.add(dst_file)
            moved += 1

        except Exception as e:
            errors += 1
            print(f"[ERROR] {src_file}: {e}")

    print("\nResumen")
    print("-------")
    print(f"Procesados:          {len(files)}")
    print(f"Movidos/Copiados:    {moved}")
    print(f"Omitidos por existe: {skipped_existing}")
    print(f"Omitidos colisión:   {skipped_collision}")
    print(f"Errores:             {errors}")


if __name__ == "__main__":
    main()