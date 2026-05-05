"""
Calibración OCR para Sonora — Fase 2 del quality audit.

Toma una muestra estratificada de 60 PDFs (4 por año × 15 años) y aplica
3 variantes de OCR a cada uno:
  V1: OCR sin cleanup (baseline actual)
  V2: clean_pdf_watermark threshold=140 + OCR
  V3: clean_pdf_watermark threshold=160 + OCR

Compara métricas de calidad para decidir si activar watermark cleanup en el
pipeline final y qué threshold usar.

Sampling estratificado:
  - 4 PDFs por anio_pub para cada año en 2010-2024 (15 años)
  - Prioriza PDFs en audit_download.csv con status='mismatch' o 'no_text'
    (los problemáticos), completa con random si no hay suficientes
  - Random seed=42 para reproducibilidad

Output:
  data/sonora/_calibration_v2/calibration_results.csv (60×3 = 180 filas)
  data/sonora/_calibration_v2/{pdf_stem}_v{N}.txt (texto por variante)
"""

from __future__ import annotations

import csv
import random
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

import fitz  # PyMuPDF

# Permitir importar src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.estados import get_adapter  # noqa: E402
from src.estados.oaxaca.preprocess import clean_pdf_watermark  # noqa: E402


# ═══════════════════════════════════════════════════
# Métricas de calidad
# ═══════════════════════════════════════════════════

_RE_TITULO_CANONICO = re.compile(
    r"LEY[\s\w]{0,30}INGRESOS[\s\w]{0,80}MUNICIPIO[\s\w]{0,30}DE\s+\w+",
    re.IGNORECASE,
)
_RE_ARTICULO_PREDIAL = re.compile(
    r"ART[IÍ]CULO\s+\d+[°ºo]?\.?\s*[\s\S]{0,200}?(?:[Ee]l\s+)?[Ii]mpuesto\s+[Pp]redial",
    re.IGNORECASE,
)
_RE_VALOR_MONETARIO = re.compile(r"\$\s?\d{1,3}(?:[,.]?\d{3})*(?:\.\d{2})?")


def _score_quality(text: str) -> dict:
    if not text:
        return {
            "tiene_titulo_canonico": False,
            "tiene_articulo_predial": False,
            "tiene_tabla_rangos": False,
            "n_valores_monetarios": 0,
        }
    n_valores = len(_RE_VALOR_MONETARIO.findall(text))
    return {
        "tiene_titulo_canonico": bool(_RE_TITULO_CANONICO.search(text)),
        "tiene_articulo_predial": bool(_RE_ARTICULO_PREDIAL.search(text)),
        "tiene_tabla_rangos": n_valores >= 5,
        "n_valores_monetarios": n_valores,
    }


# ═══════════════════════════════════════════════════
# OCR
# ═══════════════════════════════════════════════════

def _run_ocrmypdf(input_pdf: Path, output_pdf: Path, *, timeout_sec: int = 600) -> tuple[str, float]:
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ocrmypdf",
        "--language", "spa",
        "--force-ocr",
        "--invalidate-digital-signatures",
        "--deskew", "--rotate-pages",
        "--optimize", "0",
        "--tesseract-timeout", "300",
        "--jobs", "4",
        "--output-type", "pdf",
        str(input_pdf), str(output_pdf),
    ]
    t0 = time.perf_counter()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_sec)
    except subprocess.TimeoutExpired:
        return "error:timeout", time.perf_counter() - t0
    except Exception as e:
        return f"error:{type(e).__name__}", time.perf_counter() - t0
    secs = time.perf_counter() - t0
    if result.returncode in (0, 6, 15) and output_pdf.exists():
        return "ok", secs
    return f"error:rc{result.returncode}", secs


def _extract_text(pdf_path: Path) -> str:
    try:
        with fitz.open(str(pdf_path)) as doc:
            return "\n".join((doc[i].get_text("text") or "") for i in range(len(doc)))
    except Exception:
        return ""


def _process_variant(
    pdf_path: Path,
    out_dir: Path,
    variant: str,
    *,
    threshold: int | None,
    use_cleanup: bool,
) -> dict:
    cleaning_secs = 0.0
    cleaning_threshold = ""
    cleaned_pdf: Path | None = None
    work_pdf = pdf_path

    if use_cleanup:
        cleaned_pdf = out_dir / f"{pdf_path.stem}_{variant}_cleaned.pdf"
        try:
            t0 = time.perf_counter()
            info = clean_pdf_watermark(
                pdf_path, cleaned_pdf, dpi=300,
                threshold=threshold, adaptive=False,
            )
            cleaning_secs = time.perf_counter() - t0
            ts = info.get("thresholds_used", [])
            if ts:
                cleaning_threshold = (
                    str(min(ts)) if min(ts) == max(ts) else f"{min(ts)}-{max(ts)}"
                )
            elif info.get("vector_stripped"):
                cleaning_threshold = "vector"
            work_pdf = cleaned_pdf if cleaned_pdf.exists() else pdf_path
        except Exception as e:
            return {
                "variant": variant, "status": f"error:clean:{type(e).__name__}",
                "cleaning_seconds": round(cleaning_secs, 2), "ocr_seconds": 0,
                "total_seconds": round(cleaning_secs, 2),
                "ocr_chars_total": 0, "ocr_chars_per_page_avg": 0,
                "cleaning_threshold": cleaning_threshold,
                "tiene_titulo_canonico": False, "tiene_articulo_predial": False,
                "tiene_tabla_rangos": False, "n_valores_monetarios": 0,
            }

    ocr_pdf = out_dir / f"{pdf_path.stem}_{variant}_ocr.pdf"
    status, ocr_secs = _run_ocrmypdf(work_pdf, ocr_pdf)

    if status == "ok":
        text = _extract_text(ocr_pdf)
        try:
            with fitz.open(str(ocr_pdf)) as doc:
                n_pages = max(len(doc), 1)
        except Exception:
            n_pages = 1
        chars_total = len(text)
        chars_avg = chars_total / n_pages
        scoring = _score_quality(text)
        # Guardar TXT para inspección
        (out_dir / f"{pdf_path.stem}_{variant}.txt").write_text(text, encoding="utf-8")
    else:
        chars_total = 0
        chars_avg = 0
        scoring = _score_quality("")

    # Limpiar archivos pesados
    if cleaned_pdf and cleaned_pdf.exists():
        cleaned_pdf.unlink(missing_ok=True)
    if ocr_pdf.exists():
        ocr_pdf.unlink(missing_ok=True)

    return {
        "variant": variant, "status": status,
        "cleaning_seconds": round(cleaning_secs, 2),
        "ocr_seconds": round(ocr_secs, 2),
        "total_seconds": round(cleaning_secs + ocr_secs, 2),
        "ocr_chars_total": chars_total,
        "ocr_chars_per_page_avg": round(chars_avg, 1),
        "cleaning_threshold": cleaning_threshold,
        **scoring,
    }


# ═══════════════════════════════════════════════════
# Sampling estratificado
# ═══════════════════════════════════════════════════

def _stratified_sample(
    audit_csv: Path,
    *,
    pdfs_per_year: int = 4,
    seed: int = 42,
) -> list[dict]:
    """
    4 PDFs por anio_pub × 15 años (2010-2024) = 60 PDFs.
    Prioriza PDFs con status='mismatch' o 'no_text' (problemáticos),
    completa con 'partial' u 'ok' si no hay suficientes.
    """
    if not audit_csv.exists():
        raise FileNotFoundError(f"Falta {audit_csv}. Corre sonora_audit_download.py primero.")

    with audit_csv.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    # Indexar por anio_pub
    by_year: dict[int, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        try:
            y = int(r["anio_pub"])
        except (ValueError, KeyError):
            continue
        by_year[y][r["status"]].append(r)

    rng = random.Random(seed)
    sample: list[dict] = []
    for y in range(2010, 2025):
        # Prioridad: mismatch > no_text > partial > ok
        priority = ["mismatch", "no_text", "partial", "ok"]
        chosen = []
        for status in priority:
            available = by_year[y].get(status, [])
            if not available:
                continue
            n_needed = pdfs_per_year - len(chosen)
            if n_needed <= 0:
                break
            chosen.extend(rng.sample(available, min(n_needed, len(available))))
        sample.extend(chosen)

    return sample


# ═══════════════════════════════════════════════════
# Pipeline principal
# ═══════════════════════════════════════════════════

_CALIB_FIELDS = [
    "pdf_path", "anio_pub", "audit_status", "variant", "status",
    "cleaning_seconds", "ocr_seconds", "total_seconds",
    "ocr_chars_total", "ocr_chars_per_page_avg", "cleaning_threshold",
    "tiene_titulo_canonico", "tiene_articulo_predial",
    "tiene_tabla_rangos", "n_valores_monetarios",
]


def calibrate_ocr(
    adapter,
    *,
    pdfs_per_year: int = 4,
    seed: int = 42,
) -> Path:
    meta_dir = adapter.meta_dir
    audit_csv = meta_dir / "audit_download.csv"
    pdf_raw_dir = adapter.pdf_raw_dir
    calib_dir = adapter.data_dir / "_calibration_v2"
    calib_dir.mkdir(parents=True, exist_ok=True)
    results_csv = calib_dir / "calibration_results.csv"

    print("═══ Sonora: Calibración OCR (Fase 2) ═══")
    sample = _stratified_sample(audit_csv, pdfs_per_year=pdfs_per_year, seed=seed)
    print(f"    Muestra: {len(sample)} PDFs ({pdfs_per_year} por año × 15 años max)")
    print(f"    Estimado: {len(sample) * 3 * 80 / 60:.0f} min total")

    rows: list[dict] = []
    t_start = time.perf_counter()

    for i, item in enumerate(sample, 1):
        fname = item["filename"]
        anio_pub = item["anio_pub"]
        audit_status = item["status"]
        pdf_path = pdf_raw_dir / str(anio_pub) / fname
        if not pdf_path.exists():
            print(f"    [{i}/{len(sample)}] SKIP: no existe {pdf_path}")
            continue

        elapsed = time.perf_counter() - t_start
        eta = (elapsed / i) * (len(sample) - i) if i > 0 else 0
        print(
            f"    [{i}/{len(sample)}] {fname} (anio_pub={anio_pub}, "
            f"status={audit_status}) | eta={eta/60:.0f}min"
        )

        for variant, threshold, use_cleanup in [
            ("v1_no_clean", None, False),
            ("v2_clean_t140", 140, True),
            ("v3_clean_t160", 160, True),
        ]:
            res = _process_variant(
                pdf_path, calib_dir, variant,
                threshold=threshold, use_cleanup=use_cleanup,
            )
            print(
                f"      {variant}: status={res['status']} chars/pg={res['ocr_chars_per_page_avg']:.0f} "
                f"titulo={res['tiene_titulo_canonico']} tabla={res['tiene_tabla_rangos']} "
                f"({res['total_seconds']:.0f}s)"
            )
            rows.append({
                "pdf_path": fname, "anio_pub": anio_pub, "audit_status": audit_status,
                **res,
            })

        # Flush incremental cada PDF
        with results_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=_CALIB_FIELDS)
            writer.writeheader()
            writer.writerows(rows)

    # ═══════════════════════════════════════════════════
    # Análisis comparativo
    # ═══════════════════════════════════════════════════
    print("\n  ── Análisis comparativo ──")
    by_variant: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_variant[r["variant"]].append(r)

    print(
        f"  {'Variante':<20} {'titulo%':<10} {'articulo%':<11} "
        f"{'tabla%':<10} {'avg_chars/pg':<14} {'avg_secs':<10}"
    )
    scores: dict[str, dict] = {}
    for variant in ["v1_no_clean", "v2_clean_t140", "v3_clean_t160"]:
        items = [r for r in by_variant.get(variant, []) if r["status"] == "ok"]
        if not items:
            print(f"  {variant:<20} (sin datos)")
            continue
        n = len(items)
        pct_titulo = sum(1 for r in items if r["tiene_titulo_canonico"]) / n * 100
        pct_articulo = sum(1 for r in items if r["tiene_articulo_predial"]) / n * 100
        pct_tabla = sum(1 for r in items if r["tiene_tabla_rangos"]) / n * 100
        avg_chars = sum(r["ocr_chars_per_page_avg"] for r in items) / n
        avg_secs = sum(r["total_seconds"] for r in items) / n
        scores[variant] = {
            "pct_titulo": pct_titulo, "pct_articulo": pct_articulo,
            "pct_tabla": pct_tabla, "avg_chars": avg_chars, "avg_secs": avg_secs,
            "score_combined": pct_titulo + pct_articulo + pct_tabla,
        }
        print(
            f"  {variant:<20} {pct_titulo:<9.0f}% {pct_articulo:<10.0f}% "
            f"{pct_tabla:<9.0f}% {avg_chars:<14.0f} {avg_secs:<10.1f}"
        )

    # Decisión automática
    print("\n  ── Decisión automatizada ──")
    if not scores:
        print("  No hay datos suficientes para decidir.")
    else:
        v1 = scores.get("v1_no_clean", {})
        best = max(scores.items(), key=lambda x: x[1]["score_combined"])
        v1_combined = v1.get("score_combined", 0) if v1 else 0
        delta = best[1]["score_combined"] - v1_combined
        print(f"  V1 (baseline) score: {v1_combined:.0f}")
        print(f"  Mejor variante: {best[0]} score: {best[1]['score_combined']:.0f} (Δ={delta:+.0f})")
        if v1 and v1.get("pct_tabla", 0) >= 85 and best[0] == "v1_no_clean":
            print("  → V1 ya logra >=85% en tabla. Recomendación: clean_watermark=False.")
        elif delta > 25:
            t = best[0].replace("v2_clean_t", "").replace("v3_clean_t", "").replace("v1_no_clean", "")
            print(f"  → Cleanup mejora claramente (Δ>25). Recomendación: clean_watermark=True, threshold={t}.")
        else:
            print("  → Mejora marginal (Δ<=25). Recomendación: clean_watermark=False (más rápido).")

    print(f"\n  Resultados: {results_csv}")
    print(f"  TXTs por variante: {calib_dir}/*.txt")
    return results_csv


if __name__ == "__main__":
    adapter = get_adapter("sonora")
    calibrate_ocr(adapter)
