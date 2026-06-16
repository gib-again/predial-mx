#!/usr/bin/env python3
"""Runner interno para el piloto v3 LLM. Extrae todos los municipios de los
estados piloto (coahuila, jalisco, sonora) usando llm_extract_v3.

Uso:
    python -m scripts._run_pilot_v3_llm coahuila
    python -m scripts._run_pilot_v3_llm jalisco sonora
    python -m scripts._run_pilot_v3_llm --all
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.extraction.llm_extract_v3 import extraer_municipio

ROOT = Path(__file__).resolve().parents[1]
V2_ROOT = ROOT / "predial-mx-v2"
V3_ROOT = ROOT / "predial-mx-v3"
PILOT_STATES = ["coahuila", "jalisco", "sonora", "guanajuato"]


def _build_plan(estado: str) -> dict[str, list[int]]:
    """Lee v2 output para obtener el mapa cvegeo -> [anios]."""
    v2_dir = V2_ROOT / estado
    plan: dict[str, list[int]] = defaultdict(list)
    for p in sorted(v2_dir.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            meta = d.get("_meta_v2") or {}
            cvegeo = meta.get("cvegeo")
            anio = meta.get("anio")
            if cvegeo and anio:
                plan[cvegeo].append(int(anio))
        except Exception:
            continue
    return {k: sorted(set(v)) for k, v in plan.items()}


def _clean_quota_fail(estado: str) -> int:
    """Borra JSONs con razon de quota fail para que se re-extraigan."""
    v3_dir = V3_ROOT / estado
    removed = 0
    if not v3_dir.exists():
        return 0
    for p in v3_dir.glob("*.json"):
        try:
            meta = json.loads(p.read_text(encoding="utf-8")).get("_meta_v3") or {}
            razon = meta.get("razon") or ""
            if "insufficient" in razon or "quota" in razon.lower():
                p.unlink()
                removed += 1
        except Exception:
            continue
    return removed


def run_estado(estado: str, *, force_full: bool = False, clean_quota: bool = False):
    from src.core.constants import PREFIJOS_ESTADO
    plan = _build_plan(estado)
    prefijo = PREFIJOS_ESTADO[estado]
    n_munis = len(plan)
    n_files = sum(len(v) for v in plan.values())
    mode = " [FORCE FULL MODEL]" if force_full else ""
    print(f"\n{'='*60}")
    print(f"  PILOTO V3: {estado.upper()} - {n_munis} municipios, {n_files} archivos{mode}")
    print(f"{'='*60}\n")

    if clean_quota:
        n_cleaned = _clean_quota_fail(estado)
        if n_cleaned:
            print(f"  [clean] {n_cleaned} archivos quota-fail eliminados\n")

    # Build skip index (read all v3 JSONs once)
    skip_index: dict[str, set[int]] = defaultdict(set)
    v3_dir = V3_ROOT / estado
    if v3_dir.exists():
        for p in v3_dir.glob("*.json"):
            try:
                meta = json.loads(p.read_text(encoding="utf-8")).get("_meta_v3") or {}
                cv = meta.get("cvegeo")
                anio = meta.get("anio")
                if cv and anio is not None:
                    skip_index[cv].add(int(anio))
            except Exception:
                continue
    n_skip = sum(len(v) for v in skip_index.values())
    if n_skip:
        print(f"  [skip] {n_skip} archivos v3 ya existen, saltando\n")

    t0 = time.time()
    total_results = []

    for i, (cvegeo, anios) in enumerate(sorted(plan.items()), 1):
        existing = skip_index.get(cvegeo, set())
        pending = [a for a in anios if a not in existing]
        if not pending:
            continue
        skipped = len(anios) - len(pending)
        skip_msg = f" (skip {skipped})" if skipped else ""
        print(f"\n[{i}/{n_munis}] cvegeo={cvegeo}, {len(pending)} anios{skip_msg}")
        try:
            results = extraer_municipio(
                estado, cvegeo, pending, force_full_model=force_full,
            )
            total_results.extend(results)
        except Exception as e:
            print(f"  ERROR: {type(e).__name__}: {e}")

    elapsed = time.time() - t0
    n_revision = sum(1 for r in total_results if r.requiere_revision)
    total_in = sum(r.tokens_in for r in total_results)
    total_out = sum(r.tokens_out for r in total_results)
    total_cached = sum(r.tokens_cached for r in total_results)

    print(f"\n{'='*60}")
    print(f"  {estado.upper()} COMPLETADO en {elapsed/60:.1f} min")
    print(f"  Archivos: {len(total_results)}")
    print(f"  Requiere revision: {n_revision}")
    print(f"  Tokens: in={total_in:,}  out={total_out:,}  cached={total_cached:,}")
    print(f"{'='*60}\n")


def main():
    args = sys.argv[1:]
    force_full = "--force-full" in args
    clean_quota = "--clean-quota-fail" in args
    flags = {"--all", "--force-full", "--clean-quota-fail"}

    if "--all" in args:
        estados = PILOT_STATES
    else:
        estados = [a for a in args if a in PILOT_STATES and a not in flags]
    if not estados:
        print(
            f"Uso: python -m scripts._run_pilot_v3_llm "
            f"[--all | {' | '.join(PILOT_STATES)}] "
            f"[--force-full] [--clean-quota-fail]"
        )
        sys.exit(1)

    for estado in estados:
        run_estado(estado, force_full=force_full, clean_quota=clean_quota)


if __name__ == "__main__":
    main()
