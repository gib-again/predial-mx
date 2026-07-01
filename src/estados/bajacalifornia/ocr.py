"""
OCR adaptativo y *page-limited* para PDFs del Periodico Oficial de BC.

Los PDFs de BC son tomos por seccion (una ley municipal) de 230-440 paginas,
porque incluyen la Tabla de Valores Catastrales Unitarios completa. La seccion
de tasas del impuesto predial vive en las primeras ~20 paginas. Por eso, para
los escaneos (2010-2022) NO se OCR'a el tomo entero: se recorta a las primeras
``config.OCR_PAGE_LIMIT`` paginas y se OCR'a solo ese slice. Los PDFs nativos
(2023+) se saltan (texto seleccionable).

Estrategia por PDF:
  1. Samplear chars/pagina (paginas SAMPLE_START..SAMPLE_END).
  2. Si >= THRESHOLD: nativo -> saltar (no OCR).
  3. Si <  THRESHOLD: escaneo -> recortar primeras N paginas -> --force-ocr
     -> pdf_ocr/{anio}/{stem}_ocr.pdf

La segmentacion posterior prefiere automaticamente la version OCR'd cuando
existe (via ``_resolve_best_pdf`` en segment.py).

Config OCR (compatible Windows + Linux), igual que SLP/Guanajuato:
  - --force-ocr, --deskew, --rotate-pages
  - SIN --remove-background ni --clean (requieren unpaper, no en Windows)

Dependencias:
  Windows: Tesseract (paquete spa) + Ghostscript + ocrmypdf
  Linux:   apt install tesseract-ocr tesseract-ocr-spa ghostscript; pip install ocrmypdf
"""

from __future__ import annotations

import csv
import subprocess
import tempfile
from pathlib import Path

import fitz  # PyMuPDF

from src.estados.bajacalifornia import config


# Umbral en chars/pagina promedio. Por encima -> nativo; por debajo -> escaneo.
SCAN_THRESHOLD_CHARS_PER_PAGE = 300

# Paginas a samplear para decidir escaneo vs nativo (saltando portada/sumario).
SAMPLE_PAGE_START = 3
SAMPLE_PAGE_END = 10


def _check_ocrmypdf_available() -> bool:
    try:
        import ocrmypdf  # noqa: F401
        return True
    except ImportError:
        return False


def needs_ocr_pdf(pdf_path: Path) -> tuple[bool, float]:
    """Detecta si un PDF necesita OCR (texto nativo insuficiente).

    Muestrea SAMPLE_PAGE_START..SAMPLE_PAGE_END (1-indexed) y promedia chars.
    Retorna (needs_ocr, avg_chars_per_page).
    """
    try:
        with fitz.open(pdf_path) as doc:
            n_pages = doc.page_count
            if n_pages == 0:
                return True, 0.0
            start = min(SAMPLE_PAGE_START - 1, n_pages - 1)
            end = min(SAMPLE_PAGE_END, n_pages)
            total = sum(len(doc[i].get_text("text") or "") for i in range(start, end))
            n_sampled = max(end - start, 1)
            avg = total / n_sampled
    except Exception:
        return True, 0.0
    return avg < SCAN_THRESHOLD_CHARS_PER_PAGE, avg


def _slice_first_pages(input_pdf: Path, n_pages: int, out_pdf: Path) -> int:
    """Guarda las primeras ``n_pages`` paginas de input_pdf en out_pdf.

    Retorna el numero de paginas escritas.
    """
    src = fitz.open(str(input_pdf))
    dst = fitz.open()
    try:
        last = min(n_pages, len(src)) - 1
        dst.insert_pdf(src, from_page=0, to_page=last)
        dst.save(str(out_pdf))
        return last + 1
    finally:
        dst.close()
        src.close()


def _ocr_single(input_pdf: Path, output_pdf: Path) -> str:
    """Aplica force-OCR a un PDF (ya recortado). Retorna 'ok' o 'error:...'."""
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
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode in (0, 6, 15):
            return "ok"
        output_pdf.unlink(missing_ok=True)
        err = (result.stderr or result.stdout or "unknown")[:300]
        return f"error:rc{result.returncode}:{err}"
    except subprocess.TimeoutExpired:
        output_pdf.unlink(missing_ok=True)
        return "error:timeout"
    except Exception as e:
        output_pdf.unlink(missing_ok=True)
        return f"error:{type(e).__name__}"


def run_ocr(adapter, year: str | None = None, force_reocr: bool = False) -> Path:
    """OCR adaptativo + page-limited sobre los PDFs descargados.

    Solo procesa escaneos (chars/pagina < umbral). Para cada uno, recorta las
    primeras ``config.OCR_PAGE_LIMIT`` paginas y OCR'a el slice.
    """
    if not _check_ocrmypdf_available():
        raise RuntimeError(
            "ocrmypdf no esta instalado.\n"
            "  pip install ocrmypdf\n"
            "  Windows: Tesseract (paquete spa) + Ghostscript\n"
            "  Linux: apt install tesseract-ocr tesseract-ocr-spa ghostscript"
        )

    pdf_raw_dir = adapter.pdf_raw_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    meta_dir = adapter.meta_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    ocr_log_csv = meta_dir / "ocr_log.csv"

    print("=== Baja California: OCR adaptativo (page-limited) ===")
    print(f"    Threshold: {SCAN_THRESHOLD_CHARS_PER_PAGE} chars/pagina")
    print(f"    OCR limitado a primeras {config.OCR_PAGE_LIMIT} paginas")
    if year:
        print(f"    Filtro de anio: {year}")

    if not pdf_raw_dir.exists():
        print("    pdf_raw/ no existe. Ejecuta 'download' primero.")
        return ocr_log_csv

    pdf_files: list[Path] = []
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
    n_native = n_processed = n_skipped_existing = n_errors = 0

    for i, pdf_path in enumerate(pdf_files, 1):
        ejercicio = pdf_path.parent.name
        ocr_path = pdf_ocr_dir / ejercicio / (pdf_path.stem + "_ocr.pdf")

        needs, avg = needs_ocr_pdf(pdf_path)
        row = {
            "ejercicio": ejercicio,
            "input_pdf": pdf_path.name,
            "ocr_pdf": ocr_path.name,
            "avg_chars_per_page": round(avg, 1),
            "decision": "scan" if needs else "native",
            "pages_ocr": "",
            "status": "",
        }

        if not needs:
            row["status"] = "skipped:native"
            n_native += 1
            log_rows.append(row)
            continue

        if ocr_path.exists() and not force_reocr:
            row["status"] = "already_exists"
            n_skipped_existing += 1
            log_rows.append(row)
            continue

        ocr_path.unlink(missing_ok=True)
        print(f"    [{i}/{len(pdf_files)}] OCR ({avg:.0f} c/p): {pdf_path.name}")
        # Recortar primeras N paginas a un temporal, luego OCR.
        with tempfile.TemporaryDirectory() as tmp:
            sliced = Path(tmp) / (pdf_path.stem + "_slice.pdf")
            try:
                n_sliced = _slice_first_pages(pdf_path, config.OCR_PAGE_LIMIT, sliced)
                row["pages_ocr"] = n_sliced
            except Exception as e:
                row["status"] = f"error:slice:{type(e).__name__}"
                n_errors += 1
                log_rows.append(row)
                print(f"      -> {row['status']}")
                continue
            status = _ocr_single(sliced, ocr_path)
        row["status"] = status
        if status == "ok":
            n_processed += 1
        else:
            n_errors += 1
            print(f"      -> {status}")
        log_rows.append(row)

    fieldnames = [
        "ejercicio", "input_pdf", "ocr_pdf",
        "avg_chars_per_page", "decision", "pages_ocr", "status",
    ]
    with ocr_log_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log_rows)

    print("\n  -- Resumen OCR --")
    print(f"  Nativos (saltados):  {n_native}")
    print(f"  OCR procesados:      {n_processed}")
    print(f"  Ya OCR'd (saltados): {n_skipped_existing}")
    print(f"  Errores:             {n_errors}")
    print(f"  Log: {ocr_log_csv}")
    return ocr_log_csv
