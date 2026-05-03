#!/usr/bin/env python3
"""
Orquestador principal del pipeline de extracción de predial.

Uso:
    python scripts/run_pipeline.py coahuila                          # Todo el pipeline
    python scripts/run_pipeline.py coahuila --steps download         # Solo descarga
    python scripts/run_pipeline.py coahuila --steps segment,extract  # Parcial
    python scripts/run_pipeline.py jalisco --from-step extract       # Desde extracción
    python scripts/run_pipeline.py --all --steps validate            # Validar todos

Pasos disponibles (en orden):
    download  → Descarga de PDFs del Periódico Oficial
    ocr       → OCR con Tesseract (solo si el estado lo requiere)
    master    → Construcción del master (municipio, año) → PDF
    segment   → Extracción de sección predial (TXT + PDF recortado)
    extract   → Extracción LLM (GPT-5.2)
    validate  → Validación estructural + interanual
    audit     → Auditoría pre-consolidación (revisión manual de inválidos)
"""

import argparse
import sys
import time

from src.estados import get_adapter, list_estados

STEPS_ORDERED = [
    "discover", "download", "ocr",
    "master", "segment", "segment-audit",
    "extract", "validate", "audit",
]

STEP_METHODS = {
    "discover":       lambda a, **kw: a.discover_leyes(),
    "download":       lambda a, **kw: a.download(),
    "ocr":            lambda a, **kw: a.run_ocr(
                          year=kw.get("year"),
                          force_reocr=kw.get("force_reocr", False),
                          clean_watermark=kw.get("clean_watermark", True),
                          threshold=kw.get("threshold"),
                          limit=kw.get("limit"),
                          source_csv=kw.get("source_csv"),
                      ),
    "master":         lambda a, **kw: a.build_master(),
    "segment":        lambda a, **kw: (
                          a.extract_predial_sections(year=kw["year"])
                          if kw.get("year") else a.extract_predial_sections()
                      ),
    "segment-audit":  lambda a, **kw: a.run_segment_audit(),
    "extract":        lambda a, **kw: a.run_llm_extraction(batch_mode=kw.get("batch", False)),
    "validate":       lambda a, **kw: a.run_validation(),
    "audit":          lambda a, **kw: a.run_audit(),
}


def run_estado(
    estado_slug: str,
    steps: list[str],
    batch: bool = False,
    *,
    year: str | None = None,
    force_reocr: bool = False,
    clean_watermark: bool = True,
    threshold: int | None = None,
    limit: int | None = None,
    source_csv=None,
):
    adapter = get_adapter(estado_slug)

    print(f"\n{'#' * 60}")
    print(f"  ESTADO: {adapter.slug.upper()}")
    print(f"  Ejercicios: {adapter.ejercicio_range.start}–{adapter.ejercicio_range.stop - 1}")
    print(f"  OCR: {'sí' if adapter.needs_ocr else 'no'}")
    print(f"  Pasos: {', '.join(steps)}")
    if batch and "extract" in steps:
        print("  Modo LLM: BATCH (50% descuento)")
    if year and "ocr" in steps:
        print(f"  OCR: filtro año {year}")
    if force_reocr and "ocr" in steps:
        print("  OCR: --force-reocr")
    if not clean_watermark and "ocr" in steps:
        print("  OCR: --no-clean-watermark (legacy)")
    print(f"{'#' * 60}")

    for step in steps:
        print(f"\n{'─' * 40}")
        print(f"  Paso: {step}")
        print(f"{'─' * 40}")

        t0 = time.time()
        try:
            STEP_METHODS[step](
                adapter,
                batch=batch,
                year=year,
                force_reocr=force_reocr,
                clean_watermark=clean_watermark,
                threshold=threshold,
                limit=limit,
                source_csv=source_csv,
            )
        except Exception as e:
            print(f"\n  [ERROR] {step}: {e}")
            raise
        elapsed = time.time() - t0
        print(f"  ✓ {step} completado en {elapsed:.1f}s")


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline predial-mx",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"Pasos disponibles: {', '.join(STEPS_ORDERED)}",
    )
    parser.add_argument("estado", nargs="?", help="Slug del estado (ej: coahuila)")
    parser.add_argument("--all", action="store_true", help="Procesar todos los estados registrados")
    parser.add_argument("--steps", default="all", help="Pasos separados por coma, o 'all' (default: all)")
    parser.add_argument("--from-step", default=None, help="Ejecutar desde este paso en adelante")
    parser.add_argument("--batch", action="store_true",
                        help="Usar Batch API para extracción LLM (50%% descuento, hasta 24h)")
    parser.add_argument("--year", default=None,
                        help="Filtra los pasos ocr/segment a un solo año (ej: 2018)")
    parser.add_argument("--force-reocr", action="store_true",
                        help="Borra el OCR previo y lo regenera (sólo afecta paso ocr)")
    parser.add_argument("--no-clean-watermark", action="store_true",
                        help="Desactiva la limpieza de marca de agua antes del OCR (modo legacy)")
    parser.add_argument("--threshold", type=int, default=None,
                        help="Threshold fijo de luminancia (0-255) para limpieza de watermark. "
                             "Default calibrado: 140. Útil para iterar en calibración.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Procesa sólo los primeros N PDFs del paso ocr (calibración).")
    parser.add_argument("--source-csv", default=None,
                        help="source_documents.csv (Sonora v3). Si se pasa al "
                             "paso ocr, procesa solo los PDFs ahí listados.")
    args = parser.parse_args()

    # ── Determinar pasos ──
    if args.from_step:
        if args.from_step not in STEPS_ORDERED:
            print(f"[ERROR] Paso desconocido: '{args.from_step}'")
            print(f"  Disponibles: {', '.join(STEPS_ORDERED)}")
            sys.exit(1)
        idx = STEPS_ORDERED.index(args.from_step)
        steps = STEPS_ORDERED[idx:]
    elif args.steps == "all":
        steps = STEPS_ORDERED
    else:
        steps = [s.strip() for s in args.steps.split(",")]

    for s in steps:
        if s not in STEPS_ORDERED:
            print(f"[ERROR] Paso desconocido: '{s}'")
            print(f"  Disponibles: {', '.join(STEPS_ORDERED)}")
            sys.exit(1)

    # ── Determinar estados ──
    if args.all:
        estados = list_estados()
        if not estados:
            print("[ERROR] No hay estados registrados aún.")
            sys.exit(1)
    elif args.estado:
        estados = [args.estado]
    else:
        parser.print_help()
        sys.exit(1)

    # ── Ejecutar ──
    t_total = time.time()
    for estado in estados:
        from pathlib import Path as _Path
        source_csv_arg = _Path(args.source_csv) if args.source_csv else None
        run_estado(
            estado,
            steps,
            batch=args.batch,
            year=args.year,
            force_reocr=args.force_reocr,
            clean_watermark=not args.no_clean_watermark,
            threshold=args.threshold,
            limit=args.limit,
            source_csv=source_csv_arg,
        )

    elapsed_total = time.time() - t_total
    print(f"\n{'=' * 60}")
    print(f"  ✓ Pipeline completado para {len(estados)} estado(s) en {elapsed_total:.1f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()