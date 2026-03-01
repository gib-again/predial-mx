#!/usr/bin/env python3
"""
Consulta estado y descarga resultados de sub-batches.

Uso:
    python scripts/batch_download.py coahuila           # Check + download si está listo
    python scripts/batch_download.py jalisco --check     # Solo consultar estado
    python scripts/batch_download.py jalisco --download   # Forzar descarga

Lee los batch_ids desde data/{estado}/meta/batch_{PREFIJO}_ids.json,
que se genera automáticamente al correr --batch.
"""

import argparse
import json
import sys
from pathlib import Path

from src.estados import get_adapter
from src.core.llm_extract import check_batch, download_batch_results, _get_client


def main():
    parser = argparse.ArgumentParser(description="Gestión de batches de OpenAI")
    parser.add_argument("estado", help="Slug del estado (ej: coahuila)")
    parser.add_argument("--check", action="store_true", help="Solo consultar estado")
    parser.add_argument("--download", action="store_true", help="Forzar descarga de completados")
    args = parser.parse_args()

    adapter = get_adapter(args.estado)
    prefijo = adapter.prefijo
    json_dir = adapter.json_dir

    ids_file = adapter.meta_dir / f"batch_{prefijo}_ids.json"
    if not ids_file.exists():
        print(f"[ERROR] No se encontró {ids_file}")
        print(f"  Primero ejecuta: python scripts/run_pipeline.py {args.estado} --steps extract --batch")
        sys.exit(1)

    with ids_file.open() as f:
        info = json.load(f)

    batch_ids = info["batch_ids"]
    model = info.get("model", "?")
    print(f"Estado: {args.estado.upper()}")
    print(f"Modelo: {model}")
    print(f"Sub-batches: {len(batch_ids)}")

    client = _get_client()

    all_completed = True
    for i, bid in enumerate(batch_ids, 1):
        batch = client.batches.retrieve(bid)
        counts = batch.request_counts

        status_icon = {
            "completed": "✓",
            "failed": "✗",
            "in_progress": "⟳",
            "validating": "…",
            "finalizing": "…",
        }.get(batch.status, "?")

        print(f"\n  [{i}] {bid}")
        print(f"      Estado: {status_icon} {batch.status}")
        print(f"      Progreso: {counts.completed}/{counts.total} ({counts.failed} fallidos)")

        if batch.status != "completed":
            all_completed = False

        # Descargar si está completado y no es solo --check
        if batch.status == "completed" and batch.output_file_id and not args.check:
            print(f"      Descargando resultados...")
            download_batch_results(bid, batch.output_file_id, prefijo, json_dir)

    if args.check:
        if all_completed:
            print(f"\n  Todos los batches completados. Corre sin --check para descargar.")
        else:
            print(f"\n  Algunos batches aún en proceso. Vuelve a consultar más tarde.")
    elif all_completed:
        print(f"\n  ✓ Todos los resultados descargados.")
        print(f"  Siguiente paso: python scripts/run_pipeline.py {args.estado} --steps validate")


if __name__ == "__main__":
    main()
