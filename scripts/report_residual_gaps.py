#!/usr/bin/env python3
"""Reporte final tras reextract_from_audit + apply_discovered_laws.

Reconstruye el panel desde predial-mx-v2/ (ahora con todas las capas: real,
hardcoded, reclasified_v1, synthesized_short_form, audit_no_ley,
discovered_law, imputed_*) y identifica los muni-años que SIGUEN causando
desbalance — los casos donde el panel NO tiene cobertura ni siquiera tras
la auditoría.

Para cada muni residual reporta:
  - cvegeo, estado, municipio
  - años faltantes
  - razón inferida (sin obs en pdf_raw, OCR fallido, etc.)
  - acción sugerida para tomar decisión

Output:
  output/residual_gaps_report.md
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from src.core.balance_panel_v2 import (
    EXCLUDED_NOM_ENT,
    ESTADO_SLUG_BY_NOM_ENT,
    INCLUDED_NOM_ENT,
    _build_state_donors,
    _impute_municipality,
    _load_inegi_universe,
    _read_panel,
)
from src.core.constants import EJERCICIO_INI, EJERCICIO_FIN
from src.core.impute import _load_new_municipalities


def _load_panel_index() -> dict[tuple[str, int], dict]:
    """{(cvegeo, ejercicio): row} desde panel_v2.csv post-rebuild."""
    panel = _read_panel(Path("output/panel_v2.csv"))
    return {(r["cvegeo"], r["ejercicio"]): r for r in panel}


def _load_audit_index() -> dict[tuple[str, int], dict]:
    """{(cvegeo, ejercicio): row} desde audit_pendiente.csv (decisiones del auditor)."""
    rows = list(csv.DictReader(open("output/audit_pendiente.csv", encoding="utf-8-sig")))
    return {(r["cvegeo"], int(r["ejercicio_gap"])): r for r in rows if r["cvegeo"]}


def _load_reextract_log() -> dict[tuple[str, int], dict]:
    """Lee el log de reextract para entender qué falló."""
    p = Path("output/reextract_log.csv")
    if not p.exists():
        return {}
    out = {}
    with p.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                key = (r["cvegeo"], int(r["ejercicio_gap"]))
            except (ValueError, KeyError):
                continue
            out[key] = r
    return out


def main():
    print("Cargando panel reconstruido y auditoría...")
    panel_idx = _load_panel_index()
    audit_idx = _load_audit_index()
    reextract_log = _load_reextract_log()

    universe = _load_inegi_universe(Path("catalogs/municipios_inegi.csv"))
    new_munis_by_cve = _load_new_municipalities(Path("catalogs/changes_ageeml.csv"))
    new_munis_by_cvegeo = {
        f"{ce}{cm}".zfill(5): yr for (ce, cm), yr in new_munis_by_cve.items()
    }

    # Identificar huecos REALES = años NO presentes en panel_v2 (incluye raw e imputados).
    # Esto es lo correcto: si un año está en panel (aunque sea imputed), no es hueco.
    in_scope_panel = [r for r in _read_panel(Path("output/panel_v2.csv"))
                      if r["estado"] not in EXCLUDED_NOM_ENT
                      and EJERCICIO_INI <= r["ejercicio"] <= EJERCICIO_FIN]
    panel_cells: set[tuple[str, int]] = {
        (r["cvegeo"], r["ejercicio"]) for r in in_scope_panel
    }

    # Para narrativa de motivos, computamos también los gaps "de vecinos
    # observados" (raw) por muni — útil para explicar el por qué.
    raw_panel = [r for r in in_scope_panel
                 if not (r.get("imputed_method") or "").strip()]
    raw_by_muni: dict[str, list[dict]] = defaultdict(list)
    for r in raw_panel:
        raw_by_muni[r["cvegeo"]].append(r)

    # Para cada muni del universo, ver qué años están realmente faltantes
    # (no en el panel_v2.csv).
    residuals_by_muni: dict[str, dict] = {}
    for cv, info in sorted(universe.items()):
        if info["nom_ent"] not in INCLUDED_NOM_ENT:
            continue
        creation_year = new_munis_by_cvegeo.get(cv)
        exists_since = max(EJERCICIO_INI, creation_year) if creation_year else EJERCICIO_INI

        missing_years: list[int] = []
        for y in range(exists_since, EJERCICIO_FIN + 1):
            if (cv, y) not in panel_cells:
                missing_years.append(y)
        if not missing_years:
            continue

        obs = raw_by_muni.get(cv, [])
        # Inferir motivo: si no hay obs, "no_data"; si hay vecinos cercanos
        # con tipo distinto, "schema_discontinuity"; si gap > 4, "long_gap"; sino "edge".
        obs_years = sorted({int(r["ejercicio"]) for r in obs})
        gaps_with_motivo: list[tuple[int, str]] = []
        for y in missing_years:
            prev_y = max((py for py in obs_years if py < y), default=None)
            next_y = min((ny for ny in obs_years if ny > y), default=None)
            if not obs_years:
                motivo = "no_data"
            elif prev_y is None and next_y is None:
                motivo = "no_data"
            elif prev_y is None:
                motivo = "edge" if (next_y - y) > 4 else "edge"
            elif next_y is None:
                gap_back = y - prev_y
                motivo = "long_gap" if gap_back > 4 else "edge"
            else:
                obs_p = next(r for r in obs if int(r["ejercicio"]) == prev_y)
                obs_n = next(r for r in obs if int(r["ejercicio"]) == next_y)
                if (obs_p.get("tipo_esquema", "") or "") != (obs_n.get("tipo_esquema", "") or ""):
                    motivo = "schema_discontinuity"
                else:
                    motivo = "long_gap" if (next_y - prev_y - 1) > 4 else "schema_discontinuity"
            gaps_with_motivo.append((y, motivo))

        residuals_by_muni[cv] = {
            "estado": info["nom_ent"],
            "municipio": info["nom_mun"],
            "creation_year": creation_year,
            "n_obs": len(obs),
            "gaps": gaps_with_motivo,
        }

    # Generar markdown
    lines: list[str] = []
    lines.append("# Reporte de huecos residuales — decisión pendiente")
    lines.append("")
    lines.append(f"Tras `apply_discovered_laws` + `reextract_from_audit` + `balance_panel_v2`, "
                 f"siguen sin cobertura **{sum(len(r['gaps']) for r in residuals_by_muni.values())}** "
                 f"muni-años distribuidos en **{len(residuals_by_muni)}** municipios.")
    lines.append("")

    # Resumen por estado y motivo
    by_estado_count: dict[str, int] = defaultdict(int)
    by_motivo: dict[str, int] = defaultdict(int)
    for d in residuals_by_muni.values():
        by_estado_count[d["estado"]] += len(d["gaps"])
        for _, motivo in d["gaps"]:
            by_motivo[motivo] += 1

    lines.append("## Resumen")
    lines.append("")
    lines.append("**Por estado:**")
    lines.append("")
    lines.append("| Estado | Huecos residuales |")
    lines.append("|---|---:|")
    for est, n in sorted(by_estado_count.items(), key=lambda x: -x[1]):
        lines.append(f"| {est} | {n} |")
    lines.append("")
    lines.append("**Por motivo:**")
    lines.append("")
    lines.append("| Motivo | Conteo |")
    lines.append("|---|---:|")
    for m, n in sorted(by_motivo.items(), key=lambda x: -x[1]):
        lines.append(f"| `{m}` | {n} |")
    lines.append("")

    # Detalle por muni
    lines.append("## Munis residuales — decisión sugerida")
    lines.append("")
    lines.append("Cada muni listado abajo causa desbalance. La columna **decisión sugerida** "
                 "te indica qué cabe hacer: aceptar la imputación parcial, marcar el muni "
                 "como missing intencional, o reabrir investigación.")
    lines.append("")

    for cv, d in sorted(residuals_by_muni.items(),
                        key=lambda x: (-len(x[1]["gaps"]), x[1]["estado"], x[1]["municipio"])):
        gap_years = sorted({y for y, _ in d["gaps"]})
        gap_motivos = {motivo for _, motivo in d["gaps"]}
        creation = d["creation_year"]
        n_obs = d["n_obs"]
        n_gaps = len(d["gaps"])

        # Inferir decisión
        # Buscar las decisiones del auditor para esos años
        audit_status_set = set()
        for y in gap_years:
            ar = audit_idx.get((cv, y))
            if ar:
                audit_status_set.add((ar.get("estatus", "") or "").strip() or "(no audited)")
            else:
                audit_status_set.add("(not in audit)")

        if "no_existe_ley" in audit_status_set and len(audit_status_set) == 1:
            decision = (
                "**Marcar missing**: auditor confirmó que no hay Ley de Ingresos. "
                "Considera ejecutar `reextract_from_audit` para emitir JSONs sintéticos "
                "`audit_no_ley` que cubran el panel."
            )
        elif "encontrado" in audit_status_set:
            # El auditor sí encontró, pero la extracción falló
            log_results = []
            for y in gap_years:
                lr = reextract_log.get((cv, y))
                if lr:
                    log_results.append(f"{y}: {lr.get('result')} — {lr.get('mensaje', '')[:80]}")
            decision = (
                "**Reabrir investigación**: auditor reportó `encontrado` pero la "
                "extracción LLM falló. Ver log:\n"
            )
            for lr in log_results:
                decision += f"\n  - `{lr}`"
        elif n_obs == 0:
            decision = (
                f"**Sin datos en universo INEGI**. Muni con 0 observaciones; "
                f"{'creación post-2010 (' + str(creation) + ')' if creation else 'no figura como nuevo'}. "
                "Considera revisar manualmente el portal del POE."
            )
        else:
            decision = (
                "**Revisar manualmente**: motivos mixtos "
                f"({', '.join(sorted(gap_motivos))}). Ver vecinos observados ({n_obs} obs)."
            )

        lines.append(f"### {cv} {d['estado']} — {d['municipio']}")
        lines.append("")
        lines.append(f"- Años faltantes ({n_gaps}): {', '.join(str(y) for y in gap_years)}")
        lines.append(f"- Observaciones válidas en universo: {n_obs}")
        if creation:
            lines.append(f"- Creación post-{EJERCICIO_INI}: año {creation}")
        lines.append(f"- Motivos: {', '.join(sorted(gap_motivos))}")
        lines.append(f"- Estatus auditor: {', '.join(sorted(audit_status_set))}")
        lines.append(f"- **Decisión sugerida**: {decision}")
        lines.append("")

    # Section: tokens / costo info si disponible
    out_path = Path("output/residual_gaps_report.md")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  -> {out_path}")
    print(f"  Munis residuales: {len(residuals_by_muni)}")
    print(f"  Huecos residuales: {sum(len(r['gaps']) for r in residuals_by_muni.values())}")


if __name__ == "__main__":
    main()
