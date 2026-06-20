"""Consume la cola de re-extracción generada por aplicar_decisiones_hitl.

Lee ``output/hitl/cola_reextraccion.csv`` y re-ejecuta la extracción v3
para cada fila no procesada.  Las filas con ``procesado`` no vacío se saltan.

Usa gpt-5.4 (full model) por default (force_full_model=True), igual que el
extractor base; estos casos son los más difíciles.

Uso:
  python -m scripts.consume_reextraction_queue
  python -m scripts.consume_reextraction_queue --dry-run
  python -m scripts.consume_reextraction_queue --limit 10
"""

from __future__ import annotations

import argparse
import csv
import os
from datetime import datetime, timezone
from pathlib import Path

QUEUE_CSV = Path("output/hitl/cola_reextraccion.csv")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(QUEUE_CSV))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, help="Max rows to process")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    if not csv_path.exists():
        print(f"No existe {csv_path}. Nada que procesar.")
        return

    if not args.dry_run and os.environ.get("OPENAI_API_KEY") is None:
        raise SystemExit("OPENAI_API_KEY no configurada. Setear en .env o entorno.")

    with csv_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    pending = [r for r in rows if not (r.get("procesado") or "").strip()]
    print(f"Cola: {len(rows)} total, {len(pending)} pendientes")

    if args.limit:
        pending = pending[:args.limit]

    if not pending:
        print("Nada que procesar.")
        return

    if args.dry_run:
        for r in pending:
            print(f"  [dry-run] {r.get('estado_slug')}/{r.get('municipio_slug')} "
                  f"{r.get('anio')}: {r.get('hint', '')[:80]}")
        return

    from src.extraction.llm_extract_v3 import extraer_municipio

    processed = 0
    for r in pending:
        estado = r.get("estado_slug", "")
        cvegeo = r.get("cvegeo", "")
        anio = int(r.get("anio", 0))
        muni_slug = r.get("municipio_slug", "")

        hint_tipo = (r.get("hint_tipo_esquema") or "").strip()
        force_vision = (r.get("force_vision") or "").strip().lower() in ("true", "1", "yes")
        hint_notas = (r.get("hint_notas") or "").strip() or (r.get("hint") or "").strip()

        print(f"\n{'='*60}")
        print(f"Re-extracción: {estado}/{muni_slug} {anio}")
        if hint_tipo:
            print(f"  hint_tipo_esquema={hint_tipo}")
        if force_vision:
            print("  force_vision=ON (salta cascada txt→reocr)")
        if hint_notas:
            print(f"  notas: {hint_notas[:120]}")

        try:
            results = extraer_municipio(
                estado=estado,
                cvegeo=cvegeo,
                anios=[anio],
                slug_override=muni_slug,
                force_full_model=True,
                hint_tipo_esquema=hint_tipo,
                hint_notas=hint_notas,
                force_vision=force_vision,
            )
            ok = any(res.output is not None for res in results)
            r["procesado"] = "ok" if ok else "error_sin_output"
        except Exception as e:
            print(f"  [ERROR] {e}")
            r["procesado"] = f"error: {str(e)[:100]}"

        r["timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        processed += 1

    # Rewrite CSV with updated procesado/timestamp columns
    fieldnames = list(rows[0].keys()) if rows else []
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)

    print(f"\nProcesadas: {processed}/{len(pending)}")
    print(f"Cola actualizada: {csv_path}")


if __name__ == "__main__":
    main()
