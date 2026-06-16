#!/usr/bin/env python3
"""Compara estructuralmente los JSONs v2 vs v3 de un estado.

Comparacion ESTRUCTURAL (no de valores crudos por D3/unidad):
  - Regresion: v2 clasificado -> v3 todo otro_no_clasificado
  - Exito: v2 mencionaba paralelas en comentarios -> v3 las estructura
  - Distribucion de num tarifas por municipio-anio
  - Cobertura de procedencia y base_gravable

Uso:
    python -m scripts.diff_v2_v3 --estado coahuila
    python -m scripts.diff_v2_v3 --estado coahuila --csv diff_coah.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V2_ROOT = ROOT / "predial-mx-v2"
V3_ROOT = ROOT / "predial-mx-v3"


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _tipo_v2(doc: dict) -> str:
    pred = doc.get("predial")
    if pred is None:
        return "null"
    return pred.get("tipo_esquema", "???")


def _tipos_v3(doc: dict) -> list[str]:
    pred = doc.get("predial")
    if pred is None:
        return ["null"]
    tarifas = pred.get("tarifas") or []
    if not tarifas:
        return ["null"]
    return [t.get("esquema", {}).get("tipo_esquema", "???") for t in tarifas]


def _ambitos_v3(doc: dict) -> list[str]:
    pred = doc.get("predial")
    if pred is None:
        return []
    return [t.get("ambito", "?") for t in (pred.get("tarifas") or [])]


def diff_estado(estado: str, csv_path: str | None = None):
    v2_dir = V2_ROOT / estado
    v3_dir = V3_ROOT / estado

    if not v2_dir.exists() and not v3_dir.exists():
        print(f"No hay datos para {estado} en v2 ni v3.")
        return

    all_names: set[str] = set()
    if v2_dir.exists():
        all_names.update(p.name for p in v2_dir.glob("*.json"))
    if v3_dir.exists():
        all_names.update(p.name for p in v3_dir.glob("*.json"))

    rows: list[dict] = []
    tipo_counter_v2: Counter = Counter()
    tipo_counter_v3: Counter = Counter()
    n_tarifas_counter: Counter = Counter()
    regressions = 0
    gains = 0
    v2_only = 0
    v3_only = 0

    for name in sorted(all_names):
        v2_doc = _load_json(v2_dir / name) if v2_dir.exists() else None
        v3_doc = _load_json(v3_dir / name) if v3_dir.exists() else None

        if v2_doc and not v3_doc:
            v2_only += 1
            continue
        if v3_doc and not v2_doc:
            v3_only += 1
            continue

        tipo_v2 = _tipo_v2(v2_doc)
        tipos_v3 = _tipos_v3(v3_doc)
        ambitos = _ambitos_v3(v3_doc)
        n_tar = len(tipos_v3)

        tipo_counter_v2[tipo_v2] += 1
        for t in tipos_v3:
            tipo_counter_v3[t] += 1
        n_tarifas_counter[n_tar] += 1

        is_regression = (
            tipo_v2 != "otro_no_clasificado"
            and tipo_v2 != "null"
            and all(t == "otro_no_clasificado" for t in tipos_v3)
        )
        is_gain = (
            tipo_v2 == "otro_no_clasificado"
            and any(t != "otro_no_clasificado" for t in tipos_v3)
        )
        has_multi = n_tar > 1

        if is_regression:
            regressions += 1
        if is_gain:
            gains += 1

        # Procedencia
        meta_v3 = v3_doc.get("_meta_v3") or {}
        proc = meta_v3.get("procedencia") or {}
        has_proc = bool(proc.get("archivo_pdf") or proc.get("archivo_txt"))

        rows.append({
            "archivo": name,
            "tipo_v2": tipo_v2,
            "tipos_v3": "|".join(tipos_v3),
            "ambitos_v3": "|".join(ambitos),
            "n_tarifas": n_tar,
            "regression": is_regression,
            "gain": is_gain,
            "multi_tarifa": has_multi,
            "has_procedencia": has_proc,
        })

    # Print summary
    total = len(rows)
    print(f"\n{'='*60}")
    print(f"  DIFF v2 vs v3: {estado.upper()}")
    print(f"{'='*60}")
    print(f"  Archivos pareados: {total}")
    print(f"  Solo v2: {v2_only}  |  Solo v3: {v3_only}")
    print(f"\n  --- tipo_esquema v2 ---")
    for t, c in tipo_counter_v2.most_common():
        print(f"    {t:30s} {c:5d}")
    print(f"\n  --- tipo_esquema v3 (por tarifa) ---")
    for t, c in tipo_counter_v3.most_common():
        print(f"    {t:30s} {c:5d}")
    print(f"\n  --- Num tarifas v3 ---")
    for n, c in sorted(n_tarifas_counter.items()):
        print(f"    {n} tarifa(s): {c}")
    print(f"\n  Regresiones (v2 ok -> v3 otro): {regressions}")
    print(f"  Ganancias (v2 otro -> v3 ok):   {gains}")
    n_multi = sum(1 for r in rows if r["multi_tarifa"])
    print(f"  Multi-tarifa (>1): {n_multi}")
    n_proc = sum(1 for r in rows if r["has_procedencia"])
    print(f"  Con procedencia: {n_proc}/{total}")

    if regressions > 0:
        print(f"\n  !!! REGRESIONES !!!")
        for r in rows:
            if r["regression"]:
                print(f"    {r['archivo']}: {r['tipo_v2']} -> {r['tipos_v3']}")

    if csv_path:
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
            writer.writeheader()
            writer.writerows(rows)
        print(f"\n  CSV: {csv_path}")

    print()


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--estado", required=True, help="Estado a comparar.")
    ap.add_argument("--csv", help="Ruta del CSV de salida (opcional).")
    args = ap.parse_args()
    diff_estado(args.estado, args.csv)


if __name__ == "__main__":
    main()
