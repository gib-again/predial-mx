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

STEPS_ORDERED = ["download", "ocr", "master", "segment", "extract", "validate", "audit"]

STEP_METHODS = {
    "download": lambda a, **kw: a.download(),
    "ocr":      lambda a, **kw: a.run_ocr(),
    "master":   lambda a, **kw: a.build_master(),
    "segment":  lambda a, **kw: a.extract_predial_sections(),
    "extract":  lambda a, **kw: a.run_llm_extraction(batch_mode=kw.get("batch", False)),
    "validate": lambda a, **kw: a.run_validation(),
    "audit":    lambda a, **kw: a.run_audit(),
}


def run_estado(estado_slug: str, steps: list[str], batch: bool = False):
    adapter = get_adapter(estado_slug)

    print(f"\n{'#' * 60}")
    print(f"  ESTADO: {adapter.slug.upper()}")
    print(f"  Ejercicios: {adapter.ejercicio_range.start}–{adapter.ejercicio_range.stop - 1}")
    print(f"  OCR: {'sí' if adapter.needs_ocr else 'no'}")
    print(f"  Pasos: {', '.join(steps)}")
    if batch and "extract" in steps:
        print(f"  Modo LLM: BATCH (50% descuento)")
    print(f"{'#' * 60}")

    for step in steps:
        print(f"\n{'─' * 40}")
        print(f"  Paso: {step}")
        print(f"{'─' * 40}")

        t0 = time.time()
        try:
            STEP_METHODS[step](adapter, batch=batch)
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
        run_estado(estado, steps, batch=args.batch)

    elapsed_total = time.time() - t_total
    print(f"\n{'=' * 60}")
    print(f"  ✓ Pipeline completado para {len(estados)} estado(s) en {elapsed_total:.1f}s")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()