#!/usr/bin/env python3
"""Genera un documento de auditoría enfocado: el auditor sólo localiza la
sección de predial faltante (PDF + páginas) o confirma que no existe ley.

Cubre tres clases de huecos remanentes tras el balanceo:
  1. `schema_discontinuity` — años donde tipo_esquema/rangos/monto difieren
     entre vecinos cercanos; auditor verifica si hay reforma real o error de
     extracción.
  2. `edge` — huecos en bordes de ventana sin observación contigua.
  3. `sin_predial_residual` — focus_predial que el segmentador no logró
     crear (ni con el fallback short_form). Auditor localiza el rango.

Outputs:
  output/audit_pendiente.csv  — 1 fila por hueco, 4 campos rellenables
  output/audit_pendiente.md   — vista navegable agrupada por muni con punteros
                                 PDF+páginas de los años vecinos
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from src.core.balance_panel_v2 import (
    EXCLUDED_NOM_ENT,
    ESTADO_SLUG_BY_NOM_ENT,
    INCLUDED_NOM_ENT,
    PREFIJOS_BY_SLUG,
    _build_state_donors,
    _impute_municipality,
    _load_inegi_universe,
    _read_panel,
)
from src.core.constants import EJERCICIO_INI, EJERCICIO_FIN
from src.core.impute import _load_new_municipalities
from src.core.text_utils import slugify


# ── Columnas del CSV ──
# Auto-pobladas: contexto + punteros a PDFs vecinos (lectura segment.csv).
# Llenadas por el auditor: estatus + pdf_objetivo + paginas + notas + auditor + fecha.

_AUDIT_FIELDS = [
    # Identificación
    "cvegeo", "estado", "municipio", "ejercicio_gap", "motivo",
    # Contexto vecino — auto-poblado
    "prev_anio", "prev_tipo", "prev_pdf", "prev_paginas",
    "next_anio", "next_tipo", "next_pdf", "next_paginas",
    # Sugerencia automática del PDF candidato del año del hueco
    "pdf_candidato_gap",
    # Llenado por el auditor (4 campos clave)
    "estatus",          # encontrado | no_existe_ley
    "pdf_objetivo",     # nombre del PDF donde está la sección predial
    "paginas",          # rango "47-52" o "47"
    "notas",            # texto libre
    # Trazabilidad
    "auditor", "fecha",
]


# ── Cargar segment.csv para resolver pdf+páginas por (estado, muni, año) ──

def _load_segment_locations(estados: set[str]) -> dict[tuple[str, int, str], dict]:
    """{(estado_slug, anio, muni_slug): {pdf, pages_str}} desde segment.csv."""
    out: dict[tuple[str, int, str], dict] = {}
    for estado_slug in estados:
        seg_csv = Path(f"data/{estado_slug}/meta/segment.csv")
        if not seg_csv.exists():
            continue
        try:
            with seg_csv.open(encoding="utf-8-sig") as f:
                for r in csv.DictReader(f):
                    try:
                        anio = int(r.get("ejercicio") or 0)
                    except (TypeError, ValueError):
                        continue
                    slug = (r.get("slug") or "").strip()
                    if not slug or not anio:
                        continue
                    pdf = (r.get("source_pdf") or "").strip()
                    p_start = (r.get("predial_page_start") or "").strip()
                    p_end = (r.get("predial_page_end") or "").strip()
                    pages_str = ""
                    if p_start and p_end:
                        pages_str = f"p.{p_start}-{p_end}" if p_start != p_end else f"p.{p_start}"
                    out[(estado_slug, anio, slug)] = {
                        "pdf": pdf,
                        "pages": pages_str,
                        "predial_found": (r.get("predial_found") or "").strip(),
                        "predial_method": (r.get("predial_method") or "").strip(),
                    }
        except Exception:
            continue
    return out


def _pdf_candidato_gap(estado_slug: str, anio: int) -> str:
    """Primer PDF del año en data/{estado}/pdf_raw/{anio}/, o vacío."""
    pdf_dir = Path(f"data/{estado_slug}/pdf_raw") / str(anio)
    if not pdf_dir.exists():
        return ""
    pdfs = sorted(pdf_dir.glob("*.pdf"))
    return pdfs[0].name if pdfs else ""


# ── Construir filas del audit ──

def _empty_audit_fields() -> dict:
    return {f: "" for f in [
        "estatus", "pdf_objetivo", "paginas", "notas", "auditor", "fecha",
    ]}


def _build_rows_from_balance_gaps(
    raw_by_muni: dict[str, list[dict]],
    universe: dict[str, dict],
    new_munis_by_cvegeo: dict[str, int],
    state_donors: dict,
    seg_locations: dict[tuple[str, int, str], dict],
    year_min: int,
    year_max: int,
) -> list[dict]:
    """Filas para schema_discontinuity y edge (gaps que la imputación no cerró)."""
    rows: list[dict] = []

    for cv, info in sorted(universe.items()):
        if info["nom_ent"] not in INCLUDED_NOM_ENT:
            continue
        estado_slug = ESTADO_SLUG_BY_NOM_ENT.get(info["nom_ent"]) or ""
        creation_year = new_munis_by_cvegeo.get(cv)
        obs = raw_by_muni.get(cv, [])
        donors = state_donors.get(info["nom_ent"], {})
        _filled, gaps = _impute_municipality(
            cv, info["nom_ent"], info["nom_mun"], obs,
            year_min, year_max, creation_year, donors,
        )
        if not gaps:
            continue

        by_year = {int(r["ejercicio"]): r for r in obs}
        muni_slug = slugify(info["nom_mun"])

        for y, motivo in gaps:
            if motivo not in {"schema_discontinuity", "edge"}:
                continue
            prev_y = max((py for py in by_year if py < y), default=None)
            next_y = min((ny for ny in by_year if ny > y), default=None)

            prev_loc = seg_locations.get((estado_slug, prev_y, muni_slug), {}) if prev_y else {}
            next_loc = seg_locations.get((estado_slug, next_y, muni_slug), {}) if next_y else {}

            row = {
                "cvegeo": cv,
                "estado": info["nom_ent"],
                "municipio": info["nom_mun"],
                "ejercicio_gap": y,
                "motivo": motivo,
                "prev_anio": prev_y if prev_y is not None else "",
                "prev_tipo": by_year[prev_y]["tipo_esquema"] if prev_y is not None else "",
                "prev_pdf": prev_loc.get("pdf", ""),
                "prev_paginas": prev_loc.get("pages", ""),
                "next_anio": next_y if next_y is not None else "",
                "next_tipo": by_year[next_y]["tipo_esquema"] if next_y is not None else "",
                "next_pdf": next_loc.get("pdf", ""),
                "next_paginas": next_loc.get("pages", ""),
                "pdf_candidato_gap": _pdf_candidato_gap(estado_slug, y),
            }
            row.update(_empty_audit_fields())
            rows.append(row)
    return rows


def _build_rows_from_unsegmented(
    universe: dict[str, dict],
    seg_locations: dict[tuple[str, int, str], dict],
    panel_cells: set[tuple[str, int]],
    year_min: int, year_max: int,
) -> list[dict]:
    """Filas para sin_predial_residual: leer predial_sections.csv de cada estado
    y emitir una fila por cada (muni, año) donde status='no_predial_found'
    Y la celda NO existe ya en el panel (raw o imputada).

    `panel_cells` es el set de (cvegeo, ejercicio) presentes en panel_v2.csv —
    se usa para filtrar casos ya cubiertos vía short_form sintético u otra ruta.
    """
    rows: list[dict] = []
    cvegeo_by_estado_slug_muni: dict[tuple[str, str], str] = {}
    for cv, info in universe.items():
        estado_slug = ESTADO_SLUG_BY_NOM_ENT.get(info["nom_ent"]) or ""
        cvegeo_by_estado_slug_muni[(estado_slug, slugify(info["nom_mun"]))] = cv

    for estado_slug in sorted(set(ESTADO_SLUG_BY_NOM_ENT.values())):
        sections_csv = Path(f"data/{estado_slug}/meta/predial_sections.csv")
        if not sections_csv.exists():
            continue
        with sections_csv.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("status") != "no_predial_found":
                    continue
                try:
                    anio = int(r.get("ejercicio") or 0)
                except (TypeError, ValueError):
                    continue
                if not (year_min <= anio <= year_max):
                    continue
                muni_slug = slugify(r.get("municipio", ""))
                cv = cvegeo_by_estado_slug_muni.get((estado_slug, muni_slug), "")
                if not cv:
                    continue
                # Filtrar: si la celda ya está cubierta en el panel, NO es hueco real.
                if (cv, anio) in panel_cells:
                    continue
                pdf_basename = (r.get("file") or "").replace("\\", "/").split("/")[-1]
                row = {
                    "cvegeo": cv,
                    "estado": next(
                        (ne for ne, slg in ESTADO_SLUG_BY_NOM_ENT.items() if slg == estado_slug),
                        estado_slug,
                    ),
                    "municipio": r.get("municipio", ""),
                    "ejercicio_gap": anio,
                    "motivo": "sin_predial_residual",
                    "prev_anio": "", "prev_tipo": "", "prev_pdf": "", "prev_paginas": "",
                    "next_anio": "", "next_tipo": "", "next_pdf": "", "next_paginas": "",
                    "pdf_candidato_gap": pdf_basename,
                }
                row.update(_empty_audit_fields())
                rows.append(row)
    return rows


# ── Salidas ──

def _write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_AUDIT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in sorted(rows, key=lambda r: (r["estado"], r["municipio"], r["ejercicio_gap"])):
            w.writerow(row)


def _format_neighbor(anio, tipo: str, pdf: str, pages: str) -> str:
    """Formato compacto para markdown: '2018 · tarifa_millar · 2017-12-29.pdf p.34-39'"""
    parts = []
    parts.append(str(anio) if anio != "" else "—")
    parts.append(f"`{tipo}`" if tipo else "(sin tipo)")
    if pdf:
        loc = f"{pdf}"
        if pages:
            loc += f" {pages}"
        parts.append(loc)
    return " · ".join(parts)


def _write_md(rows: list[dict], out_path: Path) -> None:
    """Vista markdown agrupada por (estado, muni). Una sección por hueco con
    punteros precisos a vecinos."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    by_muni: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in rows:
        by_muni[(r["estado"], r["municipio"], r["cvegeo"])].append(r)

    motivos = defaultdict(int)
    for r in rows:
        motivos[r["motivo"]] += 1

    lines = []
    lines.append("# Auditoría — localizar sección predial faltante")
    lines.append("")
    lines.append("Acompaña a `output/audit_pendiente.csv`.")
    lines.append("")
    lines.append(f"**Total de huecos a auditar: {len(rows)}**")
    lines.append("")
    for m, n in sorted(motivos.items(), key=lambda x: -x[1]):
        lines.append(f"- `{m}`: {n}")
    lines.append("")

    lines.append("## Tu trabajo")
    lines.append("")
    lines.append("Por cada hueco listado, abre los PDFs de los **años vecinos** "
                 "indicados (con sus páginas precisas) y compara con el PDF candidato "
                 "del año del hueco. Tu salida son **4 campos** del CSV:")
    lines.append("")
    lines.append("| Campo | Valor | Significado |")
    lines.append("|---|---|---|")
    lines.append("| `estatus` | `encontrado` | Localizaste la sección predial. Llena `pdf_objetivo` y `paginas`. |")
    lines.append("| `estatus` | `no_existe_ley` | Confirmas que no se publicó Ley de Ingresos ese año. |")
    lines.append("| `pdf_objetivo` | filename | PDF dentro de `data/{estado}/pdf_raw/.../` (ej. `2019-01-15.pdf`). Vacío si `no_existe_ley`. |")
    lines.append("| `paginas` | `47-52` o `47` | Rango de páginas de la sección predial. Vacío si `no_existe_ley`. |")
    lines.append("| `notas` | texto libre | Opcional. Cita de art./reforma, fuente alternativa, etc. |")
    lines.append("")
    lines.append("Una vez llenados los campos, corre "
                 "`python -m scripts.reextract_from_audit` para que el pipeline "
                 "stage el focus_predial.txt y dispare la extracción LLM.")
    lines.append("")

    lines.append("## Huecos por municipio")
    lines.append("")
    for (estado, mun, cv), items in sorted(by_muni.items()):
        lines.append(f"### {cv} {estado} — {mun}")
        lines.append("")
        for it in sorted(items, key=lambda x: x["ejercicio_gap"]):
            y = it["ejercicio_gap"]
            motivo = it["motivo"]
            lines.append(f"#### {y} · `{motivo}`")
            lines.append("")
            if it["prev_anio"] != "":
                lines.append(f"- **Vecino previo**:  "
                             f"{_format_neighbor(it['prev_anio'], it['prev_tipo'], it['prev_pdf'], it['prev_paginas'])}")
            if it["next_anio"] != "":
                lines.append(f"- **Vecino siguiente**: "
                             f"{_format_neighbor(it['next_anio'], it['next_tipo'], it['next_pdf'], it['next_paginas'])}")
            if it["pdf_candidato_gap"]:
                lines.append(f"- **PDF candidato {y}**: `{it['pdf_candidato_gap']}` "
                             f"(en `data/{ESTADO_SLUG_BY_NOM_ENT.get(estado, '?')}/pdf_raw/{y}/`)")
            else:
                lines.append(f"- **PDF candidato {y}**: (no hay PDFs en `data/{ESTADO_SLUG_BY_NOM_ENT.get(estado, '?')}/pdf_raw/{y}/`)")
            lines.append("")
            lines.append("Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.")
            lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    print("Cargando catálogo INEGI y panel...")
    universe = _load_inegi_universe(Path("catalogs/municipios_inegi.csv"))

    new_munis_by_cve = _load_new_municipalities(Path("catalogs/changes_ageeml.csv"))
    new_munis_by_cvegeo = {
        f"{ce}{cm}".zfill(5): yr for (ce, cm), yr in new_munis_by_cve.items()
    }

    all_panel = _read_panel(Path("output/panel_v2.csv"))
    in_scope = [r for r in all_panel
                if r["estado"] not in EXCLUDED_NOM_ENT
                and EJERCICIO_INI <= r["ejercicio"] <= EJERCICIO_FIN]

    # Set de (cvegeo, ejercicio) que YA están en el panel (raw + imputed) —
    # usado para filtrar sin_predial_residual irrelevantes.
    panel_cells: set[tuple[str, int]] = {
        (r["cvegeo"], r["ejercicio"]) for r in in_scope
    }

    # Sólo observaciones para la lógica de gap-detection.
    raw = [r for r in in_scope if not (r.get("imputed_method") or "").strip()]
    raw_by_muni: dict[str, list[dict]] = defaultdict(list)
    for r in raw:
        raw_by_muni[r["cvegeo"]].append(r)
    state_donors = _build_state_donors(raw_by_muni, universe)

    print("Cargando ubicaciones (PDF + páginas) desde segment.csv de cada estado...")
    estados_slug = set(ESTADO_SLUG_BY_NOM_ENT.values())
    seg_locations = _load_segment_locations(estados_slug)
    print(f"  ubicaciones cargadas: {len(seg_locations)}")

    print("Calculando huecos remanentes (schema_discontinuity, edge)...")
    rows_balance = _build_rows_from_balance_gaps(
        raw_by_muni, universe, new_munis_by_cvegeo, state_donors,
        seg_locations, EJERCICIO_INI, EJERCICIO_FIN,
    )
    print(f"  schema_discontinuity + edge: {len(rows_balance)}")

    print("Sumando focus_predial residuales (sin_predial_residual, no cubiertos por panel)...")
    rows_unseg = _build_rows_from_unsegmented(
        universe, seg_locations, panel_cells, EJERCICIO_INI, EJERCICIO_FIN,
    )
    print(f"  sin_predial_residual: {len(rows_unseg)}")

    rows = rows_balance + rows_unseg

    csv_path = Path("output/audit_pendiente.csv")
    md_path = Path("output/audit_pendiente.md")
    _write_csv(rows, csv_path)
    _write_md(rows, md_path)
    print(f"\n  -> {csv_path} ({len(rows)} filas)")
    print(f"  -> {md_path}")


if __name__ == "__main__":
    main()
