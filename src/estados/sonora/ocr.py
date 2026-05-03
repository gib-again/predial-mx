"""
OCR adaptativo para PDFs del Boletín Oficial de Sonora.

Esperamos que la era nueva (2019+) sean nativos con texto seleccionable y NO
requieran OCR. Los boletines antiguos (≤ 2018) podrían ser escaneos.

Estrategia:
  1. Para cada PDF en pdf_raw/, samplear chars/página (ignorando portada).
  2. Si chars/página >= THRESHOLD: saltar (texto nativo, OCR innecesario).
  3. Si chars/página <  THRESHOLD: --force-ocr → pdf_ocr/{año}/{stem}_ocr.pdf

La segmentación posterior prefiere automáticamente la versión OCR'd cuando
existe (vía `_resolve_best_pdf` en segment.py).

Configuración OCR (compatible Windows + Linux), idéntica a SLP/Guanajuato:
  - --force-ocr para reemplazar la capa de texto pobre
  - --deskew + --rotate-pages
  - SIN --remove-background ni --clean (requieren unpaper, no en Windows)
"""

from __future__ import annotations

import csv
import subprocess
from pathlib import Path

import time

import fitz  # PyMuPDF


# Umbral en chars/página promedio. Por encima → texto nativo; por debajo → escaneo.
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

    Muestrea las páginas SAMPLE_PAGE_START..SAMPLE_PAGE_END y calcula el
    promedio de chars. Retorna (needs_ocr, avg_chars_per_page).
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


def _ocr_single(
    input_pdf: Path,
    output_pdf: Path,
    *,
    clean_watermark: bool = False,
    threshold: int | None = None,
) -> tuple[str, dict]:
    """
    Aplica force-OCR a un PDF, opcionalmente con cleanup de watermark.

    Si clean_watermark=True, primero corre clean_pdf_watermark (reusa
    src/estados/oaxaca/preprocess.py) y luego ocrmypdf sobre el limpio.

    Returns:
        (status, info_dict) donde info_dict tiene: cleaning_ms, ocr_ms,
        threshold_used, vector_stripped.
    """
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    info: dict = {
        "cleaning_ms": 0,
        "ocr_ms": 0,
        "threshold_used": "",
        "vector_stripped": False,
    }

    work_pdf = input_pdf
    cleaned_pdf: Path | None = None

    if clean_watermark:
        try:
            from src.estados.oaxaca.preprocess import clean_pdf_watermark
        except ImportError:
            return "error:no_preprocess_module", info
        cleaned_pdf = output_pdf.with_suffix(".clean.pdf")
        try:
            clean_info = clean_pdf_watermark(
                input_pdf, cleaned_pdf, dpi=300,
                threshold=threshold, adaptive=(threshold is None),
            )
            info["cleaning_ms"] = clean_info.get("elapsed_ms", 0)
            info["vector_stripped"] = clean_info.get("vector_stripped", False)
            ts = clean_info.get("thresholds_used", [])
            if ts:
                if min(ts) == max(ts):
                    info["threshold_used"] = str(min(ts))
                else:
                    info["threshold_used"] = f"{min(ts)}-{max(ts)}"
            elif info["vector_stripped"]:
                info["threshold_used"] = "vector"
            work_pdf = cleaned_pdf if cleaned_pdf.exists() else input_pdf
        except Exception as e:
            if cleaned_pdf and cleaned_pdf.exists():
                cleaned_pdf.unlink(missing_ok=True)
            return f"error:clean:{type(e).__name__}", info

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
        str(work_pdf),
        str(output_pdf),
    ]

    import time
    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600,
        )
        info["ocr_ms"] = int((time.perf_counter() - t0) * 1000)
        # 0 = éxito, 6 = "already has text" (no debería con --force-ocr),
        # 15 = "completed with warnings" (normal con PDFs tagged/híbridos).
        if result.returncode in (0, 6, 15):
            if cleaned_pdf and cleaned_pdf.exists():
                cleaned_pdf.unlink(missing_ok=True)
            return "ok", info
        if output_pdf.exists():
            output_pdf.unlink()
        if cleaned_pdf and cleaned_pdf.exists():
            cleaned_pdf.unlink(missing_ok=True)
        err_msg = (result.stderr or result.stdout or "unknown")[:300]
        return f"error:rc{result.returncode}:{err_msg}", info
    except subprocess.TimeoutExpired:
        info["ocr_ms"] = int((time.perf_counter() - t0) * 1000)
        if output_pdf.exists():
            output_pdf.unlink()
        if cleaned_pdf and cleaned_pdf.exists():
            cleaned_pdf.unlink(missing_ok=True)
        return "error:timeout", info
    except Exception as e:
        if output_pdf.exists():
            output_pdf.unlink()
        if cleaned_pdf and cleaned_pdf.exists():
            cleaned_pdf.unlink(missing_ok=True)
        return f"error:{type(e).__name__}", info


def run_ocr(
    adapter,
    year: str | None = None,
    force_reocr: bool = False,
    *,
    source_csv: Path | None = None,
    clean_watermark: bool = False,
    threshold: int | None = None,
    limit: int | None = None,
) -> Path:
    """
    Ejecuta OCR sobre los PDFs descargados.

    Modos:
      - Default (source_csv=None): OCR adaptativo. Procesa solo PDFs con
        chars/pág < SCAN_THRESHOLD_CHARS_PER_PAGE.
      - Dirigido (source_csv=Path): procesa solo los PDFs en source_documents.csv
        que tengan al menos una ley en discovered_laws.csv. Recomendado tras
        el paso `discover` + `download`.

    Args:
        adapter: Adaptador Sonora.
        year: Si se pasa, sólo procesa ese año (filtro pdf_raw/{year}/).
        force_reocr: Si True, regenera el OCR aunque el output ya exista.
        source_csv: Si se pasa, restringe a PDFs en source_documents.csv
            con leyes asociadas.
        clean_watermark: Si True, aplica clean_pdf_watermark() (Oaxaca) antes.
        threshold: Threshold fijo de luminancia (None = adaptativo).
        limit: Procesa sólo los primeros N PDFs (modo dev/calibración).
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

    print("═══ Sonora: OCR ═══")
    if source_csv:
        print(f"    Modo: dirigido (source_csv={source_csv})")
    else:
        print(f"    Modo: adaptativo (threshold {SCAN_THRESHOLD_CHARS_PER_PAGE} chars/pág)")
    if clean_watermark:
        thr_label = f"threshold={threshold}" if threshold else "threshold=adaptive"
        print(f"    Cleanup watermark: ON ({thr_label})")
    if year:
        print(f"    Filtro de año: {year}")

    pdf_files: list[Path] = []
    if not pdf_raw_dir.exists():
        print("    pdf_raw/ no existe. Ejecuta 'download' primero.")
        return ocr_log_csv

    if source_csv and source_csv.exists():
        # Cargar PDFs desde source_documents.csv, filtrados a los que tengan
        # al menos 1 ley en discovered_laws.csv (mismo dir).
        laws_path = source_csv.parent / "discovered_laws.csv"
        urls_con_leyes: set[str] = set()
        if laws_path.exists():
            with laws_path.open(encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    urls_con_leyes.add(r["documento_url"])
        with source_csv.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if urls_con_leyes and r["url_pdf"] not in urls_con_leyes:
                    continue
                pl = r.get("path_local", "").strip()
                if not pl:
                    continue
                full = Path(pl)
                if not full.is_absolute():
                    full = adapter.data_dir.parent.parent / pl
                if full.exists():
                    if year and full.parent.name != str(year):
                        continue
                    pdf_files.append(full)
    else:
        for year_dir in sorted(pdf_raw_dir.iterdir()):
            if not year_dir.is_dir():
                continue
            if year and year_dir.name != str(year):
                continue
            pdf_files.extend(sorted(year_dir.glob("*.pdf")))

    if limit:
        pdf_files = pdf_files[:limit]

    if not pdf_files:
        print("    No se encontraron PDFs.")
        return ocr_log_csv

    print(f"    Total PDFs candidatos: {len(pdf_files)}")

    log_rows: list[dict] = []
    n_native = 0
    n_processed = 0
    n_skipped_existing = 0
    n_errors = 0
    t_start = time.perf_counter()

    for i, pdf_path in enumerate(pdf_files, 1):
        ejercicio = pdf_path.parent.name
        ocr_subdir = pdf_ocr_dir / ejercicio
        ocr_path = ocr_subdir / (pdf_path.stem + "_ocr.pdf")

        # En modo dirigido (source_csv), no chequeamos chars/pag para forzar
        # OCR de PDFs OCR-pobres aunque tengan poco texto nativo.
        if source_csv:
            needs, avg = needs_ocr_pdf(pdf_path)
            if not needs:
                # En modo dirigido, igual saltamos nativos (chars/pag suficientes).
                pass
        else:
            needs, avg = needs_ocr_pdf(pdf_path)
        decision = "scan" if needs else "native"

        row = {
            "ejercicio": ejercicio,
            "input_pdf": pdf_path.name,
            "ocr_pdf": ocr_path.name,
            "avg_chars_per_page": round(avg, 1),
            "decision": decision,
            "status": "",
            "threshold_used": "",
            "cleaning_ms": 0,
            "ocr_ms": 0,
            "vector_stripped": False,
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
                if i % 10 == 0 or i == 1:
                    elapsed = time.perf_counter() - t_start
                    rate = i / max(elapsed, 0.001)
                    eta = (len(pdf_files) - i) / max(rate, 0.001)
                    print(
                        f"    [{i}/{len(pdf_files)}] {pdf_path.name} "
                        f"| ok={n_processed} err={n_errors} | "
                        f"eta={eta/60:.1f}min"
                    )
                status, info = _ocr_single(
                    pdf_path, ocr_path,
                    clean_watermark=clean_watermark,
                    threshold=threshold,
                )
                row["status"] = status
                row["threshold_used"] = info["threshold_used"]
                row["cleaning_ms"] = info["cleaning_ms"]
                row["ocr_ms"] = info["ocr_ms"]
                row["vector_stripped"] = info["vector_stripped"]
                if status == "ok":
                    n_processed += 1
                else:
                    n_errors += 1
                    print(f"      → {status}")

        log_rows.append(row)

        # Flush incremental cada 10 PDFs
        if i % 10 == 0:
            _write_log(ocr_log_csv, log_rows)

    # Flush final
    _write_log(ocr_log_csv, log_rows)

    print("\n  ── Resumen OCR ──")
    print(f"  Nativos (saltados):  {n_native}")
    print(f"  OCR procesados:      {n_processed}")
    print(f"  Ya OCR'd (saltados): {n_skipped_existing}")
    print(f"  Errores:             {n_errors}")
    print(f"  Log: {ocr_log_csv}")
    return ocr_log_csv


def _write_log(ocr_log_csv: Path, log_rows: list[dict]) -> None:
    fieldnames = [
        "ejercicio", "input_pdf", "ocr_pdf",
        "avg_chars_per_page", "decision", "status",
        "threshold_used", "cleaning_ms", "ocr_ms", "vector_stripped",
    ]
    with ocr_log_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log_rows)
