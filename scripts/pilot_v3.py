#!/usr/bin/env python3
"""Piloto v3: ejecuta extraccion LLM + conversion hardcoded y produce reporte.

Piloto sobre coahuila, jalisco, sonora (todos los anios) + Grupo B (hardcoded).
Produce reportes/piloto_v3.md con metricas clave.

Uso:
    python -m scripts.pilot_v3 --llm          # Solo estados LLM
    python -m scripts.pilot_v3 --hardcoded     # Solo Grupo B
    python -m scripts.pilot_v3 --all           # Ambos
    python -m scripts.pilot_v3 --diff-only     # Solo diff (requiere datos previos)
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
V3_ROOT = ROOT / "predial-mx-v3"
REPORT_DIR = ROOT / "reportes"

PILOT_LLM_STATES = ["coahuila", "jalisco", "sonora"]
PILOT_HARDCODED_STATES = ["chihuahua", "colima", "edomex", "sinaloa", "tabasco"]


def _analyze_estado(estado: str) -> dict:
    """Analiza todos los JSONs v3 de un estado (data/{estado}/json_predial/)."""
    from src.core.corpus import iter_corpus_files

    files = iter_corpus_files(estado)
    if not files:
        return {"estado": estado, "n_files": 0}

    tipo_counter: Counter = Counter()
    ambito_counter: Counter = Counter()
    n_tarifas_counter: Counter = Counter()
    n_revision = 0
    n_rescue = 0
    n_with_proc = 0
    total_tokens_in = 0
    total_tokens_out = 0
    n_files = 0

    for p in files:
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue

        n_files += 1
        pred = doc.get("predial")
        if pred is None:
            tipo_counter["null"] += 1
            n_tarifas_counter[0] += 1
            continue

        tarifas = pred.get("tarifas") or []
        n_tarifas_counter[len(tarifas)] += 1

        for t in tarifas:
            esq = t.get("esquema", {})
            tipo_counter[esq.get("tipo_esquema", "?")] += 1
            ambito_counter[t.get("ambito", "?")] += 1

        meta = doc.get("_meta_v3") or {}
        if meta.get("requiere_revision"):
            n_revision += 1
        if meta.get("usado_reocr") or meta.get("usado_vision"):
            n_rescue += 1
        tokens = meta.get("tokens") or {}
        total_tokens_in += tokens.get("input", 0)
        total_tokens_out += tokens.get("output", 0)

        proc = meta.get("procedencia") or {}
        if proc.get("archivo_pdf") or proc.get("archivo_txt"):
            n_with_proc += 1

    return {
        "estado": estado,
        "n_files": n_files,
        "tipo_counter": tipo_counter,
        "ambito_counter": ambito_counter,
        "n_tarifas_counter": n_tarifas_counter,
        "n_revision": n_revision,
        "n_rescue": n_rescue,
        "n_with_proc": n_with_proc,
        "total_tokens_in": total_tokens_in,
        "total_tokens_out": total_tokens_out,
    }


def _generate_report(states: list[str]) -> str:
    lines: list[str] = []
    lines.append("# Piloto V3 - Reporte\n")

    for estado in states:
        stats = _analyze_estado(estado)
        lines.append(f"## {estado.upper()}\n")

        if stats["n_files"] == 0:
            lines.append("Sin datos v3.\n")
            continue

        lines.append(f"- **Archivos**: {stats['n_files']}")
        lines.append(f"- **Requiere revision**: {stats['n_revision']}")
        lines.append(f"- **Rescates (reocr/vision)**: {stats['n_rescue']}")
        lines.append(f"- **Con procedencia**: {stats['n_with_proc']}/{stats['n_files']}")
        lines.append(f"- **Tokens**: in={stats['total_tokens_in']:,}  out={stats['total_tokens_out']:,}\n")

        lines.append("### tipo_esquema (por tarifa)\n")
        lines.append("| Tipo | Count |")
        lines.append("|------|-------|")
        for t, c in stats["tipo_counter"].most_common():
            lines.append(f"| {t} | {c} |")
        lines.append("")

        lines.append("### Num tarifas por archivo\n")
        lines.append("| N | Count |")
        lines.append("|---|-------|")
        for n, c in sorted(stats["n_tarifas_counter"].items()):
            lines.append(f"| {n} | {c} |")
        lines.append("")

        lines.append("### ambito (por tarifa)\n")
        lines.append("| Ambito | Count |")
        lines.append("|--------|-------|")
        for a, c in stats["ambito_counter"].most_common():
            lines.append(f"| {a} | {c} |")
        lines.append("")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--llm", action="store_true", help="Ejecutar LLM extraction para piloto.")
    ap.add_argument("--hardcoded", action="store_true", help="Ejecutar conversion hardcoded.")
    ap.add_argument("--all", action="store_true", help="LLM + hardcoded.")
    ap.add_argument("--diff-only", action="store_true", help="Solo reporte (sin ejecutar).")
    args = ap.parse_args()

    if not (args.llm or args.hardcoded or args.all or args.diff_only):
        ap.error("Pasa --llm, --hardcoded, --all, o --diff-only.")

    # Hardcoded conversion
    if args.hardcoded or args.all:
        print("=== Convirtiendo Grupo B (hardcoded) ===")
        subprocess.run(
            [sys.executable, "-m", "scripts.convert_hardcoded_to_v3", "--all"],
            check=True,
        )

    # LLM extraction (placeholder - would require API key and costs $$)
    if args.llm or args.all:
        print("\n=== LLM extraction para piloto ===")
        print("NOTA: La extraccion LLM requiere OPENAI_API_KEY y consume tokens.")
        print("Ejecutar manualmente para cada estado:")
        for est in PILOT_LLM_STATES:
            print("  python -c \"from src.extraction.llm_extract_v3 import extraer_municipio; ...\"")
        print("(El piloto LLM se ejecuta manualmente por costo. Use --diff-only tras ejecutar.)")

    # Generate report
    all_states = []
    if args.hardcoded or args.all or args.diff_only:
        all_states.extend(PILOT_HARDCODED_STATES)
    if args.llm or args.all or args.diff_only:
        all_states.extend(PILOT_LLM_STATES)

    report = _generate_report(all_states)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORT_DIR / "piloto_v3.md"
    report_path.write_text(report, encoding="utf-8")
    print(f"\nReporte: {report_path.relative_to(ROOT)}")

    # Also run diff for paired states
    print("\n=== Diff v2 vs v3 ===")
    for estado in all_states:
        v2_dir = ROOT / "predial-mx-v2" / estado
        v3_dir = ROOT / "predial-mx-v3" / estado
        if v2_dir.exists() and v3_dir.exists():
            subprocess.run(
                [sys.executable, "-m", "scripts.diff_v2_v3", "--estado", estado],
                check=False,
            )


if __name__ == "__main__":
    main()
