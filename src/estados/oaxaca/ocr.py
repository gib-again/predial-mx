"""
OCR para PDFs del Periódico Oficial de Oaxaca.

Particularidades de Oaxaca:
  - Los PDFs tienen marca de agua grande "DOCUMENTO SOLO PARA CONSULTA"
    que degrada la calidad del OCR.
  - Formato dos columnas en muchas páginas.
  - Orientación landscape en tablas y anexos.
  - El texto bajo la marca de agua suele ser legible pero el OCR
    confunde caracteres con la marca superpuesta.

Estrategia OCR:
  - --force-ocr: Obligatorio. El texto existente es poco confiable bajo watermark.
  - --deskew: Corregir inclinación del escaneo.
  - --rotate-pages: Auto-rotar páginas landscape.
  - SIN --remove-background: No disponible en Windows (requiere unpaper).
  - SIN --clean: No disponible en Windows (requiere unpaper).
  - --optimize 0: Sin optimización para preservar calidad.
  - --tesseract-timeout 300: Timeout generoso por páginas de dos columnas.

Nota sobre la marca de agua:
  La marca de agua diagonal es el principal obstáculo. En Linux,
  --remove-background + --clean podrían mejorar resultados. En Windows,
  estas opciones no están disponibles. El fallback a visión PDF
  (en la fase de extracción LLM) compensa la baja calidad del OCR
  en tablas parcialmente cubiertas por la marca de agua.

Archivos generados:
  data/oaxaca/pdf_ocr/{año}/{mes}/{stem}_ocr.pdf
  data/oaxaca/meta/ocr_log.csv
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

from src.estados.oaxaca import config


def _check_ocrmypdf_available() -> bool:
    try:
        import ocrmypdf  # noqa: F401
        return True
    except ImportError:
        return False


def _ocr_single(input_pdf: Path, output_pdf: Path) -> str:
    """
    Aplica OCR a un PDF con configuración cross-platform.

    Usa --force-ocr porque los PDFs tienen watermark que contamina
    el texto existente, y las tablas con cuotas/tasas son frecuentemente
    imágenes escaneadas.

    Retorna status string: "ok" o "error:...".
    """
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ocrmypdf",
        "--language", config.OCR_LANG,
        "--force-ocr",
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

    Los PDFs de Oaxaca tienen estructura:
      pdf_raw/{año}/{mes}/{filename}.pdf
    y se genera:
      pdf_ocr/{año}/{mes}/{filename}_ocr.pdf

    La estructura año/mes se preserva porque Oaxaca publica
    PDFs durante todo el año.

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

    print("═══ Oaxaca: OCR ═══")
    print(f"  {len(pdf_files)} PDFs para procesar con OCR.")

    log_rows: list[dict] = []
    processed = 0
    skipped = 0
    errors = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        # Preservar estructura relativa: año/mes/filename
        relative = pdf_path.relative_to(pdf_raw_dir)
        ocr_path = pdf_ocr_dir / relative.parent / (pdf_path.stem + "_ocr.pdf")
        ocr_path.parent.mkdir(parents=True, exist_ok=True)

        ejercicio = relative.parts[0] if relative.parts else ""

        row = {
            "ejercicio": ejercicio,
            "input_pdf": str(pdf_path),
            "ocr_pdf": str(ocr_path),
            "status": "",
        }

        if ocr_path.exists() and ocr_path.stat().st_size > 0:
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
