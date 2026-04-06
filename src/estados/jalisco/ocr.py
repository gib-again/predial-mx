"""
OCR para PDFs de Jalisco.

Migrado de:
  - 40_pdf_to_ocr.py           → ocr_skip (skip_text=True, primera pasada)
  - 41_pdf_to_ocr_force.py     → ocr_force (force_ocr=True, para escaneos)
  - 42_pdf_to_ocr_patch.py     → ocr_patch (re-OCR selectivo)

Jalisco usa ocrmypdf en lugar de Tesseract directo, con tres pasadas:
  1. skip: embebe OCR donde no hay texto (rápido, no modifica texto existente)
  2. force: re-OCR completo para PDFs escaneados que la pasada 1 no resolvió
  3. patch: re-OCR selectivo basado en resultados de validación

La prioridad de PDFs para la segmentación es: _forceocr > _ocr > original.
"""

import csv
from pathlib import Path



def _check_ocrmypdf_available():
    """Verifica que ocrmypdf esté instalado."""
    try:
        import ocrmypdf  # noqa: F401
        return True
    except ImportError:
        return False


def _ocr_single(input_pdf: Path, output_pdf: Path, lang: str = "spa+eng",
                force: bool = False) -> str:
    """
    Aplica OCR a un PDF. Retorna status string.

    Args:
        force: Si True, fuerza re-OCR incluso donde ya hay texto.
    """
    import ocrmypdf

    try:
        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        ocrmypdf.ocr(
            str(input_pdf),
            str(output_pdf),
            language=lang,
            rotate_pages=True,
            deskew=True,
            optimize=0,
            progress_bar=False,
            force_ocr=force,
            skip_text=not force,
        )
        return "ok"
    except Exception as e:
        # Limpiar archivo corrupto si quedó
        if output_pdf.exists():
            output_pdf.unlink()
        return f"error:{type(e).__name__}"


def run_ocr(adapter) -> Path:
    """
    Ejecuta OCR en dos pasadas sobre todos los PDFs descargados.

    Pasada 1 (skip): Solo embebe texto donde no existe.
    Pasada 2 (force): Re-OCR completo para los que fallaron o son escaneos puros.

    Output va a pdf_ocr/, NO junto a los originales en pdf_raw/.
    La prioridad para segmentación será: pdf_ocr/{stem}_forceocr.pdf > _ocr.pdf > pdf_raw/original.pdf

    Returns:
        Path al CSV log de OCR.
    """
    if not _check_ocrmypdf_available():
        raise RuntimeError(
            "ocrmypdf no está instalado. Instalar con: pip install ocrmypdf"
        )

    meta_dir = adapter.meta_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    downloads_csv = meta_dir / "ingresos_downloads.csv"
    ocr_log_csv = meta_dir / "ocr_log.csv"

    if not downloads_csv.exists():
        raise FileNotFoundError(f"No existe {downloads_csv}. Ejecuta 'download' primero.")

    from src.estados.jalisco.config import OCR_LANG

    # Cargar lista de PDFs descargados
    with downloads_csv.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r.get("status") in ("ok", "already_exists")]

    print(f"  {len(rows)} PDFs para procesar con OCR.")

    log_rows = []

    for i, row in enumerate(rows, 1):
        municipio = row["municipio"]
        anio = int(row["anio"])
        input_path = Path(row["file_local"])

        if not input_path.exists():
            log_rows.append({
                "municipio": municipio, "anio": anio,
                "input_pdf": str(input_path), "ocr_pdf": "", "force_pdf": "",
                "status_ocr_skip": "missing_input", "status_ocr_force": "",
            })
            continue

        # Output en pdf_ocr/ con misma estructura de año
        ocr_subdir = pdf_ocr_dir / str(anio)
        ocr_subdir.mkdir(parents=True, exist_ok=True)

        ocr_path = ocr_subdir / (input_path.stem + "_ocr.pdf")
        force_path = ocr_subdir / (input_path.stem + "_forceocr.pdf")

        # ── Pasada 1: skip ──
        if ocr_path.exists():
            status_skip = "already_exists"
        else:
            print(f"    [{i}/{len(rows)}] OCR skip: {municipio} {anio}")
            status_skip = _ocr_single(input_path, ocr_path, lang=OCR_LANG, force=False)

        # ── Pasada 2: force (solo si el PDF tiene poco texto) ──
        if force_path.exists():
            status_force = "already_exists"
        else:
            from src.core.pdf_utils import is_scanned_pdf
            check_path = ocr_path if ocr_path.exists() else input_path
            if is_scanned_pdf(check_path, threshold=100):
                print(f"    [{i}/{len(rows)}] OCR force: {municipio} {anio}")
                status_force = _ocr_single(input_path, force_path, lang=OCR_LANG, force=True)
            else:
                status_force = "not_needed"

        log_rows.append({
            "municipio": municipio,
            "anio": anio,
            "input_pdf": str(input_path),
            "ocr_pdf": str(ocr_path),
            "force_pdf": str(force_path),
            "status_ocr_skip": status_skip,
            "status_ocr_force": status_force,
        })

    # Guardar log
    fieldnames = ["municipio", "anio", "input_pdf", "ocr_pdf", "force_pdf",
                  "status_ocr_skip", "status_ocr_force"]
    with ocr_log_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log_rows)

    ok_skip = sum(1 for r in log_rows if r["status_ocr_skip"] in ("ok", "already_exists"))
    ok_force = sum(1 for r in log_rows if r["status_ocr_force"] in ("ok", "already_exists"))
    print(f"  OCR completado: skip={ok_skip}, force={ok_force} → {ocr_log_csv}")

    return ocr_log_csv
