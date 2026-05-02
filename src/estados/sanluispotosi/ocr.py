"""
OCR adaptativo para PDFs del Periódico Oficial de SLP.

La mayoría de los PDFs SLP 2017+ son nativos con texto seleccionable y NO
requieren OCR. Sólo 2012-2016 y 2019 son escaneos con muy poco texto en la
capa nativa (~100-300 chars/página, vs ~1500-3000 en los nativos).

Estrategia:
  1. Para cada PDF en pdf_raw/, samplear chars/página (ignorando portada).
  2. Si chars/página >= THRESHOLD: saltar (texto nativo, OCR innecesario).
  3. Si chars/página <  THRESHOLD: --force-ocr → pdf_ocr/{año}/{stem}_ocr.pdf

La segmentación posterior prefiere automáticamente la versión OCR'd cuando
existe (vía `_resolve_best_pdf` en segment.py).

Configuración OCR (compatible Windows + Linux), idéntica a Guanajuato:
  - --force-ocr para reemplazar la capa de texto pobre
  - --deskew + --rotate-pages
  - SIN --remove-background ni --clean (requieren unpaper, no en Windows)

Dependencias:
  Windows: Tesseract (con paquete spa) + Ghostscript + ocrmypdf
  Linux:   apt install tesseract-ocr tesseract-ocr-spa ghostscript; pip install ocrmypdf
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

import fitz  # PyMuPDF


# Umbral en chars/página promedio. Por encima → texto nativo; por debajo → escaneo.
# Calibrado contra datos reales SLP:
#   2024 alaquines: ~2960 chars/página (nativo)
#   2018 alaquines: ~2000 chars/página (nativo)
#   2015 alaquines:  ~261 chars/página (escaneo) → OCR
#   2019 alaquines:   ~96 chars/página (escaneo) → OCR
SCAN_THRESHOLD_CHARS_PER_PAGE = 300

# Páginas a samplear (saltando portada+sumario que tienen menos texto).
SAMPLE_PAGE_START = 3
SAMPLE_PAGE_END = 8


def _check_ocrmypdf_available() -> bool:
    try:
        import ocrmypdf  # noqa: F401
        return True
    except ImportError:
        return False


def needs_ocr_pdf(pdf_path: Path) -> tuple[bool, float]:
    """
    Detecta si un PDF necesita OCR (texto nativo insuficiente).

    Muestrea las páginas SAMPLE_PAGE_START..SAMPLE_PAGE_END (1-indexed) y
    calcula el promedio de chars. Retorna (needs_ocr, avg_chars_per_page).
    """
    try:
        with fitz.open(pdf_path) as doc:
            n_pages = doc.page_count
            if n_pages == 0:
                return True, 0.0
            start = min(SAMPLE_PAGE_START - 1, n_pages - 1)
            end = min(SAMPLE_PAGE_END, n_pages)
            total = sum(len(doc[i].get_text("text") or "") for i in range(start, end))
            n_sampled = end - start
            avg = total / n_sampled if n_sampled > 0 else 0.0
    except Exception:
        return True, 0.0  # Si no se puede abrir, intentar OCR
    return avg < SCAN_THRESHOLD_CHARS_PER_PAGE, avg


def _ocr_single(input_pdf: Path, output_pdf: Path) -> str:
    """Aplica force-OCR a un PDF. Retorna 'ok' o 'error:...'."""
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ocrmypdf",
        "--language", "spa",
        "--force-ocr",
        "--invalidate-digital-signatures",
        "--deskew",
        "--rotate-pages",
        "--optimize", "0",
        "--tesseract-timeout", "300",
        "--jobs", "4",
        "--output-type", "pdf",
        str(input_pdf),
        str(output_pdf),
    ]

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600,
        )
        # 0 = éxito, 6 = "already has text" (no debería con --force-ocr),
        # 15 = "completed with warnings" (normal con PDFs tagged/híbridos).
        if result.returncode in (0, 6, 15):
            return "ok"
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


def run_ocr(adapter, year: str | None = None, force_reocr: bool = False) -> Path:
    """
    Ejecuta OCR adaptativo sobre los PDFs descargados.

    Solo procesa PDFs cuyo promedio de chars/página esté por debajo del
    umbral (escaneos). Los nativos (2017+) se saltan, ahorrando ~80 % del
    tiempo de OCR.

    Args:
        adapter: Adaptador SLP.
        year: Si se pasa, sólo procesa ese año (filtro pdf_raw/{year}/).
        force_reocr: Si True, regenera el OCR aunque el output ya exista.
    """
    if not _check_ocrmypdf_available():
        raise RuntimeError(
            "ocrmypdf no está instalado.\n"
            "  pip install ocrmypdf\n"
            "  Windows: instalar Tesseract (con paquete spa) + Ghostscript\n"
            "  Linux: apt install tesseract-ocr tesseract-ocr-spa ghostscript"
        )

    pdf_raw_dir = adapter.pdf_raw_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    meta_dir = adapter.meta_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    ocr_log_csv = meta_dir / "ocr_log.csv"

    print("═══ San Luis Potosí: OCR adaptativo ═══")
    print(f"    Threshold: {SCAN_THRESHOLD_CHARS_PER_PAGE} chars/página promedio")
    if year:
        print(f"    Filtro de año: {year}")

    # Listar PDFs por año
    pdf_files: list[Path] = []
    if not pdf_raw_dir.exists():
        print("    pdf_raw/ no existe. Ejecuta 'download' primero.")
        return ocr_log_csv

    for year_dir in sorted(pdf_raw_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        if year and year_dir.name != str(year):
            continue
        pdf_files.extend(sorted(year_dir.glob("*.pdf")))

    if not pdf_files:
        print("    No se encontraron PDFs.")
        return ocr_log_csv

    print(f"    Total PDFs candidatos: {len(pdf_files)}")

    log_rows: list[dict] = []
    n_native = 0
    n_processed = 0
    n_skipped_existing = 0
    n_errors = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        ejercicio = pdf_path.parent.name
        ocr_subdir = pdf_ocr_dir / ejercicio
        ocr_path = ocr_subdir / (pdf_path.stem + "_ocr.pdf")

        needs, avg = needs_ocr_pdf(pdf_path)
        decision = "scan" if needs else "native"

        row = {
            "ejercicio": ejercicio,
            "input_pdf": pdf_path.name,
            "ocr_pdf": ocr_path.name,
            "avg_chars_per_page": round(avg, 1),
            "decision": decision,
            "status": "",
        }

        if not needs:
            row["status"] = "skipped:native"
            n_native += 1
        else:
            if ocr_path.exists() and not force_reocr:
                row["status"] = "already_exists"
                n_skipped_existing += 1
            else:
                if ocr_path.exists():
                    ocr_path.unlink(missing_ok=True)
                print(f"    [{i}/{len(pdf_files)}] OCR ({avg:.0f} c/p): {pdf_path.name}")
                status = _ocr_single(pdf_path, ocr_path)
                row["status"] = status
                if status == "ok":
                    n_processed += 1
                else:
                    n_errors += 1
                    print(f"      → {status}")

        log_rows.append(row)

    # Guardar log
    fieldnames = [
        "ejercicio", "input_pdf", "ocr_pdf",
        "avg_chars_per_page", "decision", "status",
    ]
    with ocr_log_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log_rows)

    print("\n  ── Resumen OCR ──")
    print(f"  Nativos (saltados):  {n_native}")
    print(f"  OCR procesados:      {n_processed}")
    print(f"  Ya OCR'd (saltados): {n_skipped_existing}")
    print(f"  Errores:             {n_errors}")
    print(f"  Log: {ocr_log_csv}")
    return ocr_log_csv
