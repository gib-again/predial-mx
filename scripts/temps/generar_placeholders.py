"""Genera placeholders de cobertura (muni-años sin extracción) para HITL.

Correr **después** de la extracción real (los placeholders solo cubren las
celdas residuales).  Excluye Oaxaca y estados hardcoded.  Idempotente.

Uso:
  python -m scripts.temps.generar_placeholders --dry-run
  python -m scripts.temps.generar_placeholders                 # todos los Grupo A
  python -m scripts.temps.generar_placeholders --estado guanajuato
"""

from __future__ import annotations

import argparse
import importlib

from src.hitl.cobertura import estados_cobertura, generar_placeholders


def _aliases(estado: str) -> dict:
    try:
        return dict(getattr(importlib.import_module(f"src.estados.{estado}.config"),
                            "ALIASES", {}) or {})
    except Exception:
        return {}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--estado")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    estados = [args.estado] if args.estado else estados_cobertura()
    tot_creados = tot_hint = 0
    print(f"{'estado':14s} {'munis':>6} {'creados':>8} {'con_hint':>9} {'saltados':>9}")
    for est in estados:
        r = generar_placeholders(est, dry_run=args.dry_run, aliases=_aliases(est))
        if r.get("excluido"):
            print(f"{est:14s}  (excluido de cobertura)")
            continue
        tot_creados += r["creados"]
        tot_hint += r["con_hint"]
        print(f"{est:14s} {r['munis']:6d} {r['creados']:8d} {r['con_hint']:9d} {r['saltados']:9d}")
    print(f"\nTotal placeholders {'(dry-run) ' if args.dry_run else ''}"
          f"a crear: {tot_creados} (con pista de focus huérfano: {tot_hint})")


if __name__ == "__main__":
    main()
