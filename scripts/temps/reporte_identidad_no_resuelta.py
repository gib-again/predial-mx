"""Reporte de casos identidad_no_resuelta (todos los estados).

Lista cada fila de segment.csv con status=identidad_no_resuelta (texto de
municipio que no matcheó el catálogo INEGI → sin cvegeo) y, para juzgar a
priori si es **ruido** o **recuperable**, agrega la mejor sugerencia de match
(sin umbral) y si el caso tiene focus_predial.

Salida: output/hitl/identidad_no_resuelta.csv + resumen por estado.

Uso:
  python -m scripts.temps.reporte_identidad_no_resuelta
  python -m scripts.temps.reporte_identidad_no_resuelta --estado guanajuato
"""

from __future__ import annotations

import argparse
import csv
import importlib
from pathlib import Path

from src.core.catalog import build_cvegeo, cvegeo_to_nombre
from src.core.constants import CVE_ENT_ESTADO, PREFIJOS_ESTADO
from src.core.muni_matcher import MuniMatcher
from src.core.segment_schema import STATUS_OK, STATUS_IDENTIDAD, read_segment_csv
from src.extraction.llm_utils import _find_focus_paths

DATA = Path("data")
OUT = Path("output/hitl/identidad_no_resuelta.csv")
COLS = [
    "estado", "anio", "municipio_raw", "slug_actual", "source_pdf", "tiene_focus",
    "cand_cvegeo", "cand_nombre", "cand_score", "cand_metodo", "veredicto", "gap_neto",
]


def _aliases(estado: str) -> dict[str, str]:
    try:
        return dict(getattr(importlib.import_module(f"src.estados.{estado}.config"), "ALIASES", {}) or {})
    except Exception:
        return {}


def _veredicto(score: float) -> str:
    if score >= 0.85:
        return "recuperable_alias"      # casi matchea: alias/umbral lo recupera
    if score >= 0.60:
        return "revisar"                # candidato plausible, validar manual
    return "ruido_o_OCR_severo"         # sin candidato cercano


def _estados() -> list[str]:
    return [e for e in PREFIJOS_ESTADO if (DATA / e / "meta" / "segment.csv").exists()]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--estado")
    args = ap.parse_args()
    estados = [args.estado] if args.estado else _estados()

    rows_out: list[dict] = []
    resumen: dict[str, dict] = {}
    for est in estados:
        cve_ent = CVE_ENT_ESTADO.get(est, "")
        prefijo = PREFIJOS_ESTADO.get(est, est.upper())
        matcher = MuniMatcher(cve_ent=cve_ent, aliases=_aliases(est), fuzzy_threshold=0.0)
        seg = read_segment_csv(DATA / est / "meta" / "segment.csv")
        # (cvegeo, anio) que YA tienen fila ok → un identidad que apunte ahí es
        # ruido eliminable (ya lo tenemos resuelto aparte).
        ok_keys = {(r.get("cvegeo"), str(r.get("anio")))
                   for r in seg if (r.get("status") or "") == STATUS_OK and r.get("cvegeo")}
        idn = [r for r in seg if (r.get("status") or "") == STATUS_IDENTIDAD]
        cont = {"total": len(idn), "recuperable_alias": 0, "revisar": 0,
                "ruido_o_OCR_severo": 0, "con_focus": 0, "gap_neto": 0}
        for r in idn:
            raw = (r.get("municipio_raw") or "").strip()
            slug = r.get("municipio_slug") or r.get("slug") or ""
            try:
                anio = int(r.get("anio") or 0)
            except ValueError:
                anio = 0
            txt, _ = _find_focus_paths(est, prefijo, anio, slug)
            tiene_focus = txt is not None
            m = matcher.match(raw or slug)
            cand_cvegeo = build_cvegeo(cve_ent, m.cve_mun) if m.cve_mun else ""
            ver = _veredicto(m.score)
            # gap_neto: el (cand_cvegeo, anio) NO tiene fila ok → pérdida real.
            # Si ya hay fila ok, este identidad es ruido eliminable (duplicado).
            gap_neto = bool(cand_cvegeo) and (cand_cvegeo, str(anio)) not in ok_keys
            cont[ver] += 1
            cont["con_focus"] += int(tiene_focus)
            cont["gap_neto"] += int(gap_neto)
            rows_out.append({
                "estado": est, "anio": anio,
                "municipio_raw": " ".join(raw.split())[:120],
                "slug_actual": slug, "source_pdf": Path(r.get("source_pdf", "")).name,
                "tiene_focus": tiene_focus,
                "cand_cvegeo": cand_cvegeo,
                "cand_nombre": cvegeo_to_nombre(cand_cvegeo) if cand_cvegeo else "",
                "cand_score": f"{m.score:.2f}", "cand_metodo": m.method,
                "veredicto": ver, "gap_neto": gap_neto,
            })
        resumen[est] = cont

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows_out)

    print(f"Reporte: {OUT}  ({len(rows_out)} casos)\n")
    print(f"{'estado':14s} {'total':>5} {'revisar':>7} {'ruido':>6} {'c/focus':>7} {'gap_neto':>8}")
    for est, c in sorted(resumen.items()):
        if c["total"]:
            print(f"{est:14s} {c['total']:5d} {c['revisar']:7d} {c['ruido_o_OCR_severo']:6d} "
                  f"{c['con_focus']:7d} {c['gap_neto']:8d}")


if __name__ == "__main__":
    main()
