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
  - Pre-paso: limpiar la marca de agua con `preprocess.clean_pdf_watermark`
    (vector strip vía pikepdf si aplica; si no, threshold raster con numpy).
    El PDF limpio se cachea en data/oaxaca/pdf_cleaned/{año}/{mes}/.
  - --force-ocr: Obligatorio. El input al OCR es la versión limpia,
    que es totalmente raster después del preprocesado.
  - --deskew: Corregir inclinación del escaneo.
  - --rotate-pages: Auto-rotar páginas landscape.
  - SIN --remove-background: No disponible en Windows (requiere unpaper)
    y además ya no es necesario después de la limpieza por threshold.
  - SIN --clean: No disponible en Windows (requiere unpaper).
  - --optimize 0: Sin optimización para preservar calidad.
  - --tesseract-timeout 300: Timeout generoso por páginas de dos columnas.

Atomicidad:
  ocrmypdf escribe a {ocr_path}.tmp y se renombra al final con os.replace().
  Si el proceso se interrumpe, no quedan archivos corruptos en pdf_ocr/.

Archivos generados:
  data/oaxaca/pdf_cleaned/{año}/{mes}/{stem}_clean.pdf  (intermedio)
  data/oaxaca/pdf_ocr/{año}/{mes}/{stem}_ocr.pdf
  data/oaxaca/meta/ocr_log.csv
"""

from __future__ import annotations

import csv
import os
import subprocess
import time
from pathlib import Path

from src.estados.oaxaca import config
from src.estados.oaxaca.preprocess import clean_pdf_watermark


def _check_ocrmypdf_available() -> bool:
    try:
        import ocrmypdf  # noqa: F401
        return True
    except ImportError:
        return False


def _ocr_single(
    input_pdf: Path,
    output_pdf: Path,
    *,
    cleaned_pdf: Path | None = None,
    clean_watermark: bool = True,
    threshold: int | None = None,
    delete_cleaned_on_success: bool = True,
) -> dict:
    """
    Limpia el watermark y aplica OCR a un PDF.

    Si clean_watermark=True (default), genera un PDF intermedio sin
    watermark en cleaned_pdf y lo usa como input para ocrmypdf.
    Si clean_watermark=False, el input crudo va directo a ocrmypdf
    (modo legacy).

    El output se escribe atómicamente: ocrmypdf produce {output}.tmp
    y se renombra a {output} sólo si todo salió bien.

    Returns:
        dict con: status, threshold_used (str), vector_stripped (bool),
        cleaning_ms (int), ocr_ms (int), cleaned_pdf (str).
    """
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    tmp_output = output_pdf.with_suffix(output_pdf.suffix + ".tmp")
    if tmp_output.exists():
        tmp_output.unlink()

    info = {
        "status": "",
        "threshold_used": "",
        "vector_stripped": "",
        "cleaning_ms": 0,
        "ocr_ms": 0,
        "cleaned_pdf": "",
    }

    # ── Fase A: limpiar watermark ──
    if clean_watermark and cleaned_pdf is not None:
        try:
            clean_info = clean_pdf_watermark(
                input_pdf,
                cleaned_pdf,
                threshold=threshold,
                adaptive=(threshold is None),
            )
            thresholds = clean_info.get("thresholds_used") or []
            if thresholds:
                lo, hi = min(thresholds), max(thresholds)
                info["threshold_used"] = f"{lo}-{hi}" if lo != hi else str(lo)
            else:
                info["threshold_used"] = "vector"
            info["vector_stripped"] = "1" if clean_info.get("vector_stripped") else "0"
            info["cleaning_ms"] = int(clean_info.get("elapsed_ms", 0))
            info["cleaned_pdf"] = str(cleaned_pdf)
            ocr_input = cleaned_pdf
        except Exception as e:
            info["status"] = f"error:clean:{type(e).__name__}:{str(e)[:160]}"
            return info
    else:
        ocr_input = input_pdf

    # ── Fase B: OCR ──
    cmd = [
        "ocrmypdf",
        "--language", config.OCR_LANG,
        "--force-ocr",
        "--deskew",
        "--rotate-pages",
        # --optimize 1 recomprime las imágenes embebidas (lossless) sin
        # requerir pngquant/jbig2enc (--optimize 2/3). Reduce ~10-30%
        # el tamaño del PDF final vs --optimize 0.
        "--optimize", "1",
        "--jpeg-quality", "80",
        "--tesseract-timeout", "300",
        "--jobs", str(config.OCR_JOBS),
        "--output-type", "pdf",
        str(ocr_input),
        str(tmp_output),
    ]

    t0 = time.perf_counter()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,  # 1 hora máximo por PDF
        )
        info["ocr_ms"] = int((time.perf_counter() - t0) * 1000)

        if result.returncode in (0, 6, 15):
            # 0  = éxito limpio
            # 6  = "already has text" (no debería pasar con --force-ocr)
            # 15 = "completed with warnings" (normal en PDFs tagged/híbridos)
            if tmp_output.exists() and tmp_output.stat().st_size > 0:
                os.replace(tmp_output, output_pdf)
                info["status"] = "ok"
                # Borrar PDF intermedio limpiado para liberar espacio.
                # El cleaned PDF es regenerable a partir del raw + preprocess.
                if (
                    delete_cleaned_on_success
                    and cleaned_pdf is not None
                    and cleaned_pdf.exists()
                ):
                    try:
                        cleaned_pdf.unlink()
                    except Exception:
                        pass
            else:
                info["status"] = f"error:rc{result.returncode}:no-output"
        else:
            err_msg = (result.stderr or result.stdout or "unknown")[:300]
            info["status"] = f"error:rc{result.returncode}:{err_msg}"

    except subprocess.TimeoutExpired:
        info["ocr_ms"] = int((time.perf_counter() - t0) * 1000)
        info["status"] = "error:timeout"
    except Exception as e:
        info["ocr_ms"] = int((time.perf_counter() - t0) * 1000)
        info["status"] = f"error:{type(e).__name__}"
    finally:
        if tmp_output.exists():
            try:
                tmp_output.unlink()
            except Exception:
                pass

    return info


def run_ocr(
    adapter,
    *,
    year: str | None = None,
    force_reocr: bool = False,
    clean_watermark: bool = True,
    threshold: int | None = None,
    limit: int | None = None,
) -> Path:
    """
    Ejecuta OCR sobre todos los PDFs descargados.

    Args:
        adapter: OaxacaAdapter.
        year: Si se da (ej. "2018"), procesa sólo PDFs de ese año.
            Útil para calibrar antes del batch completo.
        force_reocr: Si True, borra el OCR previo y lo regenera.
        clean_watermark: Si True (default), pre-procesa el PDF para
            remover el watermark "DOCUMENTO SOLO PARA CONSULTA" antes
            del OCR. Si False, comportamiento legacy (OCR sobre raw).
        threshold: Threshold fijo (0-255) para el preprocesado raster.
            Si None, usa el default calibrado de preprocess.py (140).
        limit: Si se da, procesa sólo los primeros N PDFs (calibración).

    Estructura de directorios:
      pdf_raw/{año}/{mes}/{filename}.pdf
      pdf_cleaned/{año}/{mes}/{filename}_clean.pdf  (intermedio)
      pdf_ocr/{año}/{mes}/{filename}_ocr.pdf

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
    pdf_cleaned_dir = adapter.data_dir / "pdf_cleaned"
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

    # Filtrar por año si se solicita
    if year is not None:
        year_str = str(year)
        filtered: list[Path] = []
        for p in pdf_files:
            try:
                rel = p.relative_to(pdf_raw_dir)
            except ValueError:
                continue
            if rel.parts and rel.parts[0] == year_str:
                filtered.append(p)
        pdf_files = filtered

    if not pdf_files:
        scope = f" (año {year})" if year else ""
        print(f"  No se encontraron PDFs en pdf_raw/{scope}.")
        return ocr_log_csv

    if limit is not None and limit > 0:
        pdf_files = pdf_files[:limit]

    print("═══ Oaxaca: OCR ═══")
    print(f"  {len(pdf_files)} PDFs para procesar con OCR.")
    if year:
        print(f"  Filtro: año {year}")
    if limit:
        print(f"  Límite: primeros {limit} PDFs")
    if threshold is not None:
        print(f"  Threshold fijo: {threshold}")
    if force_reocr:
        print("  Modo: --force-reocr (regenera OCRs existentes)")
    if not clean_watermark:
        print("  Modo: --no-clean-watermark (OCR directo sobre raw, legacy)")

    fieldnames = [
        "ejercicio", "input_pdf", "cleaned_pdf", "ocr_pdf", "status",
        "threshold_used", "vector_stripped", "cleaning_ms", "ocr_ms",
    ]

    log_rows: list[dict] = []
    processed = 0
    skipped = 0
    errors = 0

    def _flush_log():
        with ocr_log_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(log_rows)

    for i, pdf_path in enumerate(pdf_files, 1):
        # Preservar estructura relativa: año/mes/filename
        relative = pdf_path.relative_to(pdf_raw_dir)
        ocr_path = pdf_ocr_dir / relative.parent / (pdf_path.stem + "_ocr.pdf")
        cleaned_path = pdf_cleaned_dir / relative.parent / (pdf_path.stem + "_clean.pdf")
        ocr_path.parent.mkdir(parents=True, exist_ok=True)

        ejercicio = relative.parts[0] if relative.parts else ""

        row = {
            "ejercicio": ejercicio,
            "input_pdf": str(pdf_path),
            "cleaned_pdf": "",
            "ocr_pdf": str(ocr_path),
            "status": "",
            "threshold_used": "",
            "vector_stripped": "",
            "cleaning_ms": "",
            "ocr_ms": "",
        }

        if ocr_path.exists() and ocr_path.stat().st_size > 0 and not force_reocr:
            row["status"] = "already_exists"
            skipped += 1
        else:
            if force_reocr and ocr_path.exists():
                try:
                    ocr_path.unlink()
                except Exception:
                    pass
            print(f"    [{i}/{len(pdf_files)}] OCR: {pdf_path.name}")
            info = _ocr_single(
                pdf_path,
                ocr_path,
                cleaned_pdf=cleaned_path,
                clean_watermark=clean_watermark,
                threshold=threshold,
            )
            row["status"] = info["status"]
            row["threshold_used"] = info["threshold_used"]
            row["vector_stripped"] = info["vector_stripped"]
            row["cleaning_ms"] = info["cleaning_ms"]
            row["ocr_ms"] = info["ocr_ms"]
            row["cleaned_pdf"] = info["cleaned_pdf"]
            if info["status"] == "ok":
                processed += 1
            else:
                errors += 1
                print(f"      {info['status']}")

        log_rows.append(row)
        _flush_log()  # write incremental para sobrevivir a interrupciones

    print(f"\n  OCR completado: {processed} procesados, {skipped} ya existían, {errors} errores")
    print(f"  Log: {ocr_log_csv}")
    return ocr_log_csv
