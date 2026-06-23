"""Migración: renombra tipo_esquema tarifa_millar→tasas_diferenciadas y el campo
tasa_millar→tasa en el corpus v3.  Sin API; solo reescribe JSONs.

Dirigido: solo toca filas dentro de un esquema cuyo tipo_esquema era
``tarifa_millar`` (no toca el vocabulario interno de ``mixto`` que usa
``tasa_millar`` como etiqueta de columna).

Uso:
    python -m scripts.temps.migrar_tasas_diferenciadas --dry-run
    python -m scripts.temps.migrar_tasas_diferenciadas
"""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

VIEJO, NUEVO = "tarifa_millar", "tasas_diferenciadas"


def _migrar_doc(d: dict) -> int:
    """Migra un doc in-place.  Devuelve nº de esquemas cambiados."""
    p = d.get("predial")
    if not isinstance(p, dict):
        return 0
    n = 0
    for t in p.get("tarifas") or []:
        esq = t.get("esquema")
        if not isinstance(esq, dict) or esq.get("tipo_esquema") != VIEJO:
            continue
        esq["tipo_esquema"] = NUEVO
        for row in esq.get("tabla") or []:
            if isinstance(row, dict) and "tasa_millar" in row:
                row["tasa"] = row.pop("tasa_millar")
        n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    patrones = ["data/*/json_predial/**/*.json", "data/*/json_predial_hitl/**/*.json"]
    archivos = sorted({f for pat in patrones for f in glob.glob(pat, recursive=True)})
    n_files = n_esq = 0
    for f in archivos:
        try:
            d = json.loads(Path(f).read_text(encoding="utf-8"))
        except Exception:
            continue
        c = _migrar_doc(d)
        if c:
            n_files += 1
            n_esq += c
            if not args.dry_run:
                Path(f).write_text(
                    json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    verbo = "(dry-run) se migrarían" if args.dry_run else "migrados"
    print(f"{verbo}: {n_files} archivos, {n_esq} esquemas tarifa_millar→tasas_diferenciadas")
    if args.dry_run:
        print("Quita --dry-run para aplicar.")


if __name__ == "__main__":
    main()
