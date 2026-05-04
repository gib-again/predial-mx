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
    """{(estado_slug, anio, muni_slug): {pdf, pages_str}} desde segment.csv o
    predial_sections.csv (formato QRO con columnas distintas).
    """
    out: dict[tuple[str, int, str], dict] = {}
    for estado_slug in estados:
        # Formato estándar (yucatan, guanajuato, jalisco, etc.): segment.csv
        seg_csv = Path(f"data/{estado_slug}/meta/segment.csv")
        if seg_csv.exists():
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
                            "pdf": pdf, "pages": pages_str,
                            "predial_found": (r.get("predial_found") or "").strip(),
                            "predial_method": (r.get("predial_method") or "").strip(),
                        }
            except Exception:
                pass

        # Formato QRO: predial_sections.csv con columnas distintas
        # (municipio_slug, doc_id, predial_articulo, status, parts).
        sections_csv = Path(f"data/{estado_slug}/meta/predial_sections.csv")
        if sections_csv.exists():
            try:
                with sections_csv.open(encoding="utf-8") as f:
                    for r in csv.DictReader(f):
                        # Saltear formato yucatán (que no tiene municipio_slug y sí tiene status='no_predial_found')
                        if "municipio_slug" not in r:
                            continue
                        try:
                            anio = int(r.get("ejercicio") or 0)
                        except (TypeError, ValueError):
                            continue
                        slug = (r.get("municipio_slug") or "").strip()
                        if not slug or not anio:
                            continue
                        # Solo añadir si no existe ya (segment.csv tiene prioridad)
                        if (estado_slug, anio, slug) in out:
                            continue
                        # Para QRO, el doc_id apunta a un set de PDFs (parts)
                        doc_id = (r.get("doc_id") or "").strip()
                        parts = (r.get("parts") or "").strip()
                        # Tomar el primer PDF de parts como representativo
                        first_pdf = parts.split(";")[0].strip() if parts else ""
                        articulo = (r.get("predial_articulo") or "").strip()
                        out[(estado_slug, anio, slug)] = {
                            "pdf": first_pdf or doc_id,
                            "pages": f"art.{articulo}" if articulo else "",
                            "predial_found": "true" if (r.get("status") or "") == "ok" else "false",
                            "predial_method": (r.get("status") or "").strip(),
                        }
            except Exception:
                pass
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


def _build_rows_from_panel_gaps(
    panel_cells: set[tuple[str, int]],
    raw_by_muni: dict[str, list[dict]],
    universe: dict[str, dict],
    new_munis_by_cvegeo: dict[str, int],
    seg_locations: dict[tuple[str, int, str], dict],
    year_min: int,
    year_max: int,
) -> list[dict]:
    """Filas para huecos REALES del panel: años faltantes en panel_v2.csv.

    Esto reemplaza la versión anterior que se basaba en `_impute_municipality()`
    (subcontaba imputaciones como huecos). La versión actual usa el set de
    celdas presentes en el panel, que es lo que realmente importa para
    cobertura.
    """
    rows: list[dict] = []

    for cv, info in sorted(universe.items()):
        if info["nom_ent"] not in INCLUDED_NOM_ENT:
            continue
        estado_slug = ESTADO_SLUG_BY_NOM_ENT.get(info["nom_ent"]) or ""
        creation_year = new_munis_by_cvegeo.get(cv)
        exists_since = year_min if not creation_year or creation_year < year_min else creation_year

        obs = raw_by_muni.get(cv, [])
        by_year_obs = {int(r["ejercicio"]): r for r in obs}
        muni_slug = slugify(info["nom_mun"])

        for y in range(exists_since, year_max + 1):
            if (cv, y) in panel_cells:
                continue  # ya cubierto

            # Inferir motivo
            prev_y = max((py for py in by_year_obs if py < y), default=None)
            next_y = min((ny for ny in by_year_obs if ny > y), default=None)
            if prev_y is None and next_y is None:
                motivo = "no_data"
            elif prev_y is None:
                motivo = "edge"
            elif next_y is None:
                motivo = "long_gap" if (y - prev_y) > 4 else "edge"
            else:
                # Vecinos en ambos lados — comparar tipos
                tipo_p = (by_year_obs[prev_y].get("tipo_esquema") or "").strip()
                tipo_n = (by_year_obs[next_y].get("tipo_esquema") or "").strip()
                if tipo_p != tipo_n:
                    motivo = "schema_discontinuity"
                elif (next_y - prev_y - 1) > 4:
                    motivo = "long_gap"
                else:
                    motivo = "schema_discontinuity"

            prev_loc = seg_locations.get((estado_slug, prev_y, muni_slug), {}) if prev_y else {}
            next_loc = seg_locations.get((estado_slug, next_y, muni_slug), {}) if next_y else {}

            row = {
                "cvegeo": cv,
                "estado": info["nom_ent"],
                "municipio": info["nom_mun"],
                "ejercicio_gap": y,
                "motivo": motivo,
                "prev_anio": prev_y if prev_y is not None else "",
                "prev_tipo": by_year_obs[prev_y].get("tipo_esquema", "") if prev_y is not None else "",
                "prev_pdf": prev_loc.get("pdf", ""),
                "prev_paginas": prev_loc.get("pages", ""),
                "next_anio": next_y if next_y is not None else "",
                "next_tipo": by_year_obs[next_y].get("tipo_esquema", "") if next_y is not None else "",
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


def _load_existing_audit(audit_csv: Path) -> dict[tuple[str, int], dict]:
    """{(cvegeo, ejercicio_gap): row} desde audit existente.

    Usa la primera fila vista para cada llave (puede haber duplicados con
    nombres con/sin acento — preferimos la que tenga estatus llenado).
    """
    if not audit_csv.exists():
        return {}
    out: dict[tuple[str, int], dict] = {}
    with audit_csv.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cv = (r.get("cvegeo") or "").strip()
            try:
                anio = int(r.get("ejercicio_gap") or 0)
            except (TypeError, ValueError):
                continue
            if not cv or not anio:
                continue
            key = (cv, anio)
            est = (r.get("estatus") or "").strip()
            existing = out.get(key)
            # Preferir la fila con estatus llenado.
            if existing is None or (not (existing.get("estatus") or "").strip() and est):
                out[key] = r
    return out


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

    panel_cells: set[tuple[str, int]] = {
        (r["cvegeo"], r["ejercicio"]) for r in in_scope
    }

    raw = [r for r in in_scope if not (r.get("imputed_method") or "").strip()]
    raw_by_muni: dict[str, list[dict]] = defaultdict(list)
    for r in raw:
        raw_by_muni[r["cvegeo"]].append(r)

    print("Cargando ubicaciones (PDF + páginas) de segment.csv y predial_sections.csv...")
    estados_slug = set(ESTADO_SLUG_BY_NOM_ENT.values())
    seg_locations = _load_segment_locations(estados_slug)
    print(f"  ubicaciones cargadas: {len(seg_locations)}")

    print("Cargando audit existente (para preservar filas llenadas por el auditor)...")
    audit_csv = Path("output/audits/audit_pendiente.csv")
    existing_audit = _load_existing_audit(audit_csv)
    n_existing_filled = sum(
        1 for r in existing_audit.values() if (r.get("estatus") or "").strip()
    )
    print(f"  filas previas: {len(existing_audit)} (con estatus: {n_existing_filled})")

    print("Detectando huecos REALES en panel_v2.csv (celdas faltantes)...")
    rows_panel = _build_rows_from_panel_gaps(
        panel_cells, raw_by_muni, universe, new_munis_by_cvegeo,
        seg_locations, EJERCICIO_INI, EJERCICIO_FIN,
    )
    print(f"  huecos del panel: {len(rows_panel)}")

    # Preservar filas llenadas por el auditor para huecos que aún persisten.
    # Para huecos que YA NO existen (cerrados por la última extracción),
    # descartamos la fila vieja.
    final_rows: list[dict] = []
    new_keys = {(r["cvegeo"], int(r["ejercicio_gap"])) for r in rows_panel}
    n_preserved = 0
    n_new = 0
    n_obsolete = len(existing_audit) - len(new_keys & set(existing_audit.keys()))

    for r in rows_panel:
        key = (r["cvegeo"], int(r["ejercicio_gap"]))
        if key in existing_audit and (existing_audit[key].get("estatus") or "").strip():
            # El usuario ya llenó esta fila; preservar pero refrescar contexto auto-poblado.
            preserved = dict(existing_audit[key])
            # Re-aplicar columnas auto-pobladas (los vecinos pueden haber cambiado)
            for col in ("motivo", "prev_anio", "prev_tipo", "prev_pdf", "prev_paginas",
                        "next_anio", "next_tipo", "next_pdf", "next_paginas",
                        "pdf_candidato_gap"):
                preserved[col] = r.get(col, "")
            final_rows.append(preserved)
            n_preserved += 1
        else:
            final_rows.append(r)
            n_new += 1

    print(f"  preservados (llenado por auditor): {n_preserved}")
    print(f"  nuevos (a auditar): {n_new}")
    print(f"  obsoletos descartados (gap cerrado): {n_obsolete}")

    md_path = Path("output/audits/audit_pendiente.md")
    _write_csv(final_rows, audit_csv)
    _write_md(final_rows, md_path)
    print(f"\n  -> {audit_csv} ({len(final_rows)} filas)")
    print(f"  -> {md_path}")


if __name__ == "__main__":
    main()
