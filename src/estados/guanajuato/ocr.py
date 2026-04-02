"""
OCR para PDFs del Periódico Oficial de Guanajuato.

Particularidad de Guanajuato:
  Los PDFs son HÍBRIDOS: el texto legal (artículos, párrafos) suele ser digital
  buscable, pero las TABLAS y FIGURAS (donde están las tasas y tarifas del
  predial) son IMÁGENES escaneadas. Por eso usamos --force-ocr para TODOS
  los PDFs: re-OCR completo que captura tanto texto como tablas.

Configuración OCR (compatible Windows + Linux):
  - --force-ocr: OCR completo (no skip). Necesario para tablas imagen.
  - --deskew: corregir inclinación del escaneo.
  - --rotate-pages: auto-rotar páginas.
  - SIN --remove-background: requiere unpaper, no disponible en Windows.
  - SIN --clean: requiere unpaper, no disponible en Windows.
  - SIN --image-dpi: solo aplica a inputs imagen, no PDFs.

Nota: ocrmypdf retorna exit code 15 cuando el PDF tiene warnings
(tagged PDF, pages already have text). Esto es NORMAL y el OCR
sí se ejecuta correctamente. Se trata como éxito.

Archivos generados:
  data/guanajuato/pdf_ocr/{ejercicio}/{stem}_ocr.pdf

Dependencias:
  Windows:
    - Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
      (instalar con idioma español: tesseract-ocr-spa)
    - Ghostscript: https://ghostscript.com/releases/gsdnld.html
    - pip install ocrmypdf
  Linux:
    apt install tesseract-ocr tesseract-ocr-spa ghostscript
    pip install ocrmypdf
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from src.estados.guanajuato import config


def _check_ocrmypdf_available() -> bool:
    try:
        import ocrmypdf  # noqa: F401
        return True
    except ImportError:
        return False


def _ocr_single(input_pdf: Path, output_pdf: Path) -> str:
    """
    Aplica OCR a un PDF con configuración cross-platform.

    Siempre usa --force-ocr porque los PDFs son híbridos: texto digital
    en artículos pero tablas de tarifas como imágenes.

    Retorna status string: "ok" o "error:...".
    """
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ocrmypdf",
        "--language", config.OCR_LANG,
        "--force-ocr",
        "--invalidate-digital-signatures",
        "--deskew",
        "--rotate-pages",
        "--optimize", "0",
        "--tesseract-timeout", "300",
        "--jobs", str(config.OCR_JOBS),
        "--output-type", "pdf",
        str(input_pdf),
        str(output_pdf),
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hora máximo por PDF
        )

        if result.returncode in (0, 6, 15):
            # 0  = éxito limpio
            # 6  = "already has text" (no debería pasar con --force-ocr)
            # 15 = "completed with warnings" (normal en PDFs tagged/híbridos)
            return "ok"
        else:
            if output_pdf.exists():
                output_pdf.unlink()
            err_msg = (result.stderr or result.stdout or "unknown")[:300]
            return f"error:rc{result.returncode}:{err_msg}"

    except subprocess.TimeoutExpired:
        if output_pdf.exists():
            output_pdf.unlink()
        return "error:timeout"
    except Exception as e:
        if output_pdf.exists():
            output_pdf.unlink()
        return f"error:{type(e).__name__}"


def run_ocr(adapter) -> Path:
    """
    Ejecuta OCR sobre todos los PDFs descargados.

    Estrategia: --force-ocr para TODOS los PDFs.
    Los PDFs de Guanajuato son híbridos (texto digital + tablas imagen),
    y las tablas son la parte crítica para el proyecto.

    Returns:
        Path al CSV log de OCR.
    """
    if not _check_ocrmypdf_available():
        raise RuntimeError(
            "ocrmypdf no está instalado.\n"
            "  pip install ocrmypdf\n"
            "  Windows: instalar Tesseract + Ghostscript (ver README)\n"
            "  Linux: apt install tesseract-ocr tesseract-ocr-spa ghostscript"
        )

    pdf_raw_dir = adapter.pdf_raw_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    meta_dir = adapter.meta_dir
    meta_dir.mkdir(parents=True, exist_ok=True)

    ocr_log_csv = meta_dir / "ocr_log.csv"

    # Encontrar todos los PDFs raw (deduplicar para Windows case-insensitivity)
    pdf_files = sorted(pdf_raw_dir.rglob("*.pdf")) + sorted(pdf_raw_dir.rglob("*.PDF"))
    seen: set[str] = set()
    unique: list[Path] = []
    for p in pdf_files:
        key = str(p).lower()
        if key not in seen:
            seen.add(key)
            unique.append(p)
    pdf_files = unique

    if not pdf_files:
        print("  No se encontraron PDFs en pdf_raw/")
        return ocr_log_csv

    print(f"  {len(pdf_files)} PDFs para procesar con OCR.")

    log_rows: list[dict] = []
    processed = 0
    skipped = 0
    errors = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        relative = pdf_path.relative_to(pdf_raw_dir)
        ejercicio = relative.parts[0] if relative.parts else ""

        ocr_subdir = pdf_ocr_dir / ejercicio
        ocr_subdir.mkdir(parents=True, exist_ok=True)

        ocr_path = ocr_subdir / (pdf_path.stem + "_ocr.pdf")

        row = {
            "ejercicio": ejercicio,
            "input_pdf": str(pdf_path),
            "ocr_pdf": str(ocr_path),
            "status": "",
        }

        if ocr_path.exists():
            row["status"] = "already_exists"
            skipped += 1
        else:
            print(f"    [{i}/{len(pdf_files)}] OCR: {pdf_path.name}")
            status = _ocr_single(pdf_path, ocr_path)
            row["status"] = status
            if status == "ok":
                processed += 1
            else:
                errors += 1
                print(f"      {status}")

        log_rows.append(row)

    # Guardar log
    fieldnames = ["ejercicio", "input_pdf", "ocr_pdf", "status"]
    with ocr_log_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log_rows)

    print(f"\n  OCR completado: {processed} procesados, {skipped} ya existían, {errors} errores")
    print(f"  Log: {ocr_log_csv}")
    return ocr_log_csv
