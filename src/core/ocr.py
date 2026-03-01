"""
Wrapper de Tesseract OCR para PDFs escaneados.

Flujo:
  1. Detectar si un PDF necesita OCR (usando pdf_utils.is_scanned_pdf)
  2. Convertir páginas a imágenes
  3. Aplicar Tesseract con configuración para español
  4. Generar PDF con texto embebido (searchable PDF)

Dependencias del sistema:
  - tesseract-ocr (apt install tesseract-ocr)
  - tesseract-ocr-spa (apt install tesseract-ocr-spa)
"""

import subprocess
from pathlib import Path

from src.core.pdf_utils import is_scanned_pdf


def check_tesseract_available() -> bool:
    """Verifica que Tesseract esté instalado y accesible."""
    try:
        result = subprocess.run(
            ["tesseract", "--version"],
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
    except FileNotFoundError:
        return False


def ocr_pdf(pdf_path: Path, out_path: Path, lang: str = "spa") -> Path:
    """
    Aplica OCR a un PDF escaneado y genera un PDF con texto embebido.

    Usa Tesseract vía línea de comandos para generar un searchable PDF.

    Args:
        pdf_path: PDF escaneado de entrada.
        out_path: Ruta para el PDF con texto embebido.
        lang: Idioma de Tesseract (default: 'spa' para español).

    Returns:
        Ruta al PDF generado.

    Raises:
        RuntimeError: Si Tesseract no está instalado o falla.
    """
    if not check_tesseract_available():
        raise RuntimeError(
            "Tesseract no está instalado. "
            "Instalar con: apt install tesseract-ocr tesseract-ocr-spa"
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Tesseract puede procesar PDFs directamente con el flag --pdf
    # Necesita el sufijo sin extensión para el output
    out_stem = str(out_path).removesuffix(".pdf")

    result = subprocess.run(
        [
            "tesseract",
            str(pdf_path),
            out_stem,
            "-l", lang,
            "pdf",
        ],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Tesseract falló para {pdf_path.name}:\n{result.stderr}"
        )

    return out_path


def process_directory(pdf_raw_dir: Path, pdf_ocr_dir: Path, lang: str = "spa"):
    """
    Procesa todos los PDFs en pdf_raw_dir que necesiten OCR.

    Solo aplica OCR a PDFs que parecen escaneados (según is_scanned_pdf).
    Los que ya tienen texto se copian directamente o se ignoran.

    Args:
        pdf_raw_dir: Directorio con PDFs originales.
        pdf_ocr_dir: Directorio de salida para PDFs con OCR.
        lang: Idioma de Tesseract.
    """
    if not pdf_raw_dir.exists():
        print(f"  [WARN] No existe {pdf_raw_dir}")
        return

    pdf_files = sorted(pdf_raw_dir.rglob("*.pdf")) + sorted(pdf_raw_dir.rglob("*.PDF"))
    if not pdf_files:
        print(f"  No se encontraron PDFs en {pdf_raw_dir}")
        return

    print(f"  Encontrados {len(pdf_files)} PDFs para revisar OCR.")

    processed = 0
    skipped = 0
    errors = 0

    for pdf_path in pdf_files:
        # Mantener estructura de subdirectorios
        relative = pdf_path.relative_to(pdf_raw_dir)
        out_path = pdf_ocr_dir / relative

        if out_path.exists():
            skipped += 1
            continue

        if not is_scanned_pdf(pdf_path):
            skipped += 1
            continue

        try:
            print(f"    OCR: {pdf_path.name}")
            ocr_pdf(pdf_path, out_path, lang=lang)
            processed += 1
        except Exception as e:
            print(f"    [ERROR] {pdf_path.name}: {e}")
            errors += 1

    print(f"  OCR completado: {processed} procesados, {skipped} saltados, {errors} errores")
