"""CLI del flujo Batch v3 (extracción asíncrona, −50%).

Ciclo:
  python -m scripts.batch_v3 guanajuato --submit     # crea + sube (devuelve batch ids)
  python -m scripts.batch_v3 guanajuato --status      # estado de los batches
  python -m scripts.batch_v3 guanajuato --download    # descarga + guarda + fallback
  python -m scripts.batch_v3 guanajuato --build-only  # solo genera JSONL (sin API)

Tras --submit, esperar (hasta 24 h) y luego --download.  GATED por API.
"""

from __future__ import annotations

import argparse
import json

from src.extraction.batch_v3 import (
    crear_batch_v3,
    descargar_estado,
    submit_estado,
    _batch_dir,
)


def _status(estado: str) -> None:
    from src.extraction.llm_utils import _get_client

    reg = _batch_dir(estado) / "submitted.json"
    if not reg.exists():
        print(f"  [{estado}] sin batches registrados.")
        return
    client = _get_client()
    for bid in json.loads(reg.read_text()):
        b = client.batches.retrieve(bid)
        rc = getattr(b, "request_counts", None)
        print(f"  {bid}: {b.status}"
              + (f"  ({rc.completed}/{rc.total} ok, {rc.failed} fail)" if rc else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("estado")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--submit", action="store_true")
    g.add_argument("--status", action="store_true")
    g.add_argument("--download", action="store_true")
    g.add_argument("--build-only", action="store_true")
    ap.add_argument("--no-fallback", action="store_true",
                    help="con --download: no correr el fallback síncrono")
    args = ap.parse_args()

    if args.build_only:
        crear_batch_v3(args.estado)
    elif args.submit:
        submit_estado(args.estado)
    elif args.status:
        _status(args.estado)
    elif args.download:
        descargar_estado(args.estado, run_fallback=not args.no_fallback)


if __name__ == "__main__":
    main()
