#!/usr/bin/env python3
"""
Compara cobertura de segment_coverage.csv (segmentación) vs
coverage_by_muni.csv (JSONs válidos post-extracción).

Uso:
    python scripts/compare_coverage.py
    python scripts/compare_coverage.py guanajuato queretaro
"""

import csv
import sys
from pathlib import Path

DATA_DIR = Path("data")

# Estados Grupo A (con segmentación)
GROUP_A = [
    "coahuila", "guanajuato", "jalisco", "oaxaca",
    "queretaro", "tamaulipas", "yucatan",
]


def load_segment_coverage(meta_dir: Path) -> dict[str, dict]:
    """Carga segment_coverage.csv agrupado por slug."""
    csv_path = meta_dir / "segment_coverage.csv"
    if not csv_path.exists():
        return {}
    by_muni: dict[str, dict] = {}
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            slug = row["slug"]
            if slug not in by_muni:
                by_muni[slug] = {"total": 0, "ok": 0, "fallback": 0, "missing": 0}
            by_muni[slug]["total"] += 1
            st = row["status"]
            if st == "ok":
                by_muni[slug]["ok"] += 1
            elif st == "fallback":
                by_muni[slug]["fallback"] += 1
            else:
                by_muni[slug]["missing"] += 1
    return by_muni


def load_json_coverage(meta_dir: Path) -> dict[str, dict]:
    """Carga coverage_by_muni.csv."""
    csv_path = meta_dir / "coverage_by_muni.csv"
    if not csv_path.exists():
        return {}
    by_muni: dict[str, dict] = {}
    with csv_path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            slug = row["municipio"]
            n_years = int(row.get("n_years", 0))
            n_missing = int(row.get("n_missing", 0))
            # Sanity: skip corrupted rows (e.g. Oaxaca has n_missing=2026)
            if n_missing > n_years or n_years > 50:
                continue
            by_muni[slug] = {"n_years": n_years, "n_missing": n_missing}
    return by_muni


def compare_estado(estado: str):
    meta_dir = DATA_DIR / estado / "meta"
    seg = load_segment_coverage(meta_dir)
    jsn = load_json_coverage(meta_dir)

    if not seg and not jsn:
        print(f"  {estado}: sin datos")
        return

    all_slugs = sorted(set(seg.keys()) | set(jsn.keys()))

    # Totales
    seg_total = sum(m["total"] for m in seg.values())
    seg_covered = sum(m["ok"] + m["fallback"] for m in seg.values())
    jsn_total = sum(m["n_years"] for m in jsn.values())
    jsn_missing = sum(m["n_missing"] for m in jsn.values())
    jsn_covered = jsn_total - jsn_missing

    seg_pct = 100 * seg_covered / seg_total if seg_total else 0
    jsn_pct = 100 * jsn_covered / jsn_total if jsn_total else 0

    print(f"\n  {'=' * 60}")
    print(f"  {estado.upper()}")
    print(f"  {'=' * 60}")
    print(f"  {'':30s} {'Segment':>12s} {'JSON (valid)':>12s} {'Delta':>8s}")
    print(f"  {'Esperados':30s} {seg_total:12d} {jsn_total:12d}")
    print(f"  {'Cubiertos':30s} {seg_covered:12d} {jsn_covered:12d}"
          f" {jsn_covered - seg_covered:+8d}")
    print(f"  {'Cobertura %':30s} {seg_pct:11.1f}% {jsn_pct:11.1f}%"
          f" {jsn_pct - seg_pct:+7.1f}%")

    # Municipios donde difieren significativamente
    diffs = []
    for slug in all_slugs:
        s = seg.get(slug, {"total": 0, "ok": 0, "fallback": 0, "missing": 0})
        j = jsn.get(slug, {"n_years": 0, "n_missing": 0})
        seg_cov = s["ok"] + s["fallback"]
        jsn_cov = j["n_years"] - j["n_missing"]
        delta = jsn_cov - seg_cov
        if delta != 0:
            diffs.append((slug, seg_cov, s["total"], jsn_cov, j["n_years"], delta))

    if diffs:
        # Ordenar por delta descendente (JSON tiene más)
        diffs.sort(key=lambda x: -abs(x[5]))
        print(f"\n  Municipios con diferencia (top 20):")
        print(f"  {'Municipio':35s} {'Seg':>5s} {'JSON':>5s} {'Delta':>6s}  Nota")
        print(f"  {'-' * 35} {'-' * 5} {'-' * 5} {'-' * 6}  {'-' * 25}")
        for slug, sc, st, jc, jt, delta in diffs[:20]:
            nota = ""
            if delta > 0:
                nota = "JSON > Segment (fallback ok?)"
            elif delta < 0:
                nota = "Segment > JSON (extract fail?)"
            print(f"  {slug:35s} {sc:5d} {jc:5d} {delta:+6d}  {nota}")

        n_json_more = sum(1 for d in diffs if d[5] > 0)
        n_seg_more = sum(1 for d in diffs if d[5] < 0)
        print(f"\n  Resumen: {n_json_more} munis donde JSON > Segment,"
              f" {n_seg_more} donde Segment > JSON")
    else:
        print("\n  Sin diferencias por municipio.")


def main():
    estados = sys.argv[1:] if len(sys.argv) > 1 else GROUP_A
    for estado in estados:
        compare_estado(estado)
    print()


if __name__ == "__main__":
    main()
