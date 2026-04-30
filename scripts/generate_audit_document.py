#!/usr/bin/env python3
"""Genera un documento de auditoría rellenable (CSV + Markdown) para los munis
que el balanceador no pudo cerrar automáticamente.

Cubre tres clases de huecos:
  1. `schema_discontinuity` — pares de años observados con tipo_esquema/rangos/
     monto_max divergentes. El revisor decide si es reforma real o error de
     extracción.
  2. `edge` — huecos en el borde de la ventana donde no hay observación
     contigua del lado faltante.
  3. `sin_predial_residual` — focus_predial que el segmentador NO logró crear
     (ni siquiera con el fallback short_form). Requiere ajuste manual del
     segmentador o la ley fuente está realmente vacía.

Outputs:
  output/audit_pendiente.csv  — formato rellenable (1 fila por hueco)
  output/audit_pendiente.md   — vista navegable agrupada por muni
"""

from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from src.core.balance_panel_v2 import (
    EXCLUDED_NOM_ENT, INCLUDED_NOM_ENT,
    _build_state_donors, _detect_schema_discontinuities,
    _impute_municipality, _load_inegi_universe, _read_panel,
)
from src.core.constants import EJERCICIO_INI, EJERCICIO_FIN
from src.core.impute import _load_new_municipalities


# Columnas del CSV rellenable.
_AUDIT_FIELDS = [
    # Identificación
    "cvegeo", "estado", "municipio", "ejercicio",
    # Diagnóstico
    "motivo", "obs_validas_muni",
    # Contexto del hueco
    "tipo_esquema_observado_prev", "tipo_esquema_observado_next",
    "anio_prev", "anio_next",
    # Fuente sugerida
    "pdf_candidato", "ruta_pdf",
    # Campos a llenar por el auditor
    "tipo_esquema_decidido",
    "numero_rangos_decidido",
    "monto_max_rango_decidido",
    "es_reforma_real",          # sí/no/N/A
    "decision_final",           # imputar | excluir | reextraer | manual_fill
    "comentarios_auditor",
    "auditor", "fecha",
]


def _pdf_candidate(estado: str, anio: int) -> tuple[str, str]:
    """Localiza un PDF candidato para el muni-año. Retorna (basename, full_path)."""
    estado_slug = estado.lower().replace(" ", "_").replace("é", "e")
    estado_slug = {
        "coahuila de zaragoza": "coahuila", "mexico": "edomex",
    }.get(estado_slug, estado_slug)

    # Estructura típica: data/{estado}/pdf_raw/{anio}/...pdf
    pdf_dir = Path(f"data/{estado_slug}/pdf_raw") / str(anio)
    if pdf_dir.exists():
        pdfs = sorted(pdf_dir.glob("*.pdf"))
        if pdfs:
            return pdfs[0].name, str(pdfs[0])
    # Fallback: data/{estado}/pdf_raw/ (any subdir)
    pdf_dir = Path(f"data/{estado_slug}/pdf_raw")
    if pdf_dir.exists():
        pdfs = sorted(pdf_dir.rglob(f"*{anio}*.pdf"))
        if pdfs:
            return pdfs[0].name, str(pdfs[0])
    return "", ""


def _build_audit_rows(
    raw_by_muni: dict[str, list[dict]],
    universe: dict[str, dict],
    new_munis_by_cvegeo: dict[str, int],
    state_donors: dict,
    year_min: int, year_max: int,
) -> list[dict]:
    """Reconstruye los huecos remanentes después del balanceo y los expande
    a filas auditables individuales."""
    rows: list[dict] = []

    for cv, info in sorted(universe.items()):
        if info["nom_ent"] not in INCLUDED_NOM_ENT:
            continue
        creation_year = new_munis_by_cvegeo.get(cv)
        obs = raw_by_muni.get(cv, [])
        donors = state_donors.get(info["nom_ent"], {})
        _filled, gaps = _impute_municipality(
            cv, info["nom_ent"], info["nom_mun"], obs,
            year_min, year_max, creation_year, donors,
        )
        if not gaps:
            continue

        # Indexar obs por año para localizar prev/next.
        by_year = {int(r["ejercicio"]): r for r in obs}

        for y, motivo in gaps:
            prev_y = max((py for py in by_year if py < y), default=None)
            next_y = min((ny for ny in by_year if ny > y), default=None)

            tipo_prev = by_year[prev_y]["tipo_esquema"] if prev_y is not None else ""
            tipo_next = by_year[next_y]["tipo_esquema"] if next_y is not None else ""

            pdf_name, pdf_path = _pdf_candidate(info["nom_ent"], y)

            rows.append({
                "cvegeo": cv,
                "estado": info["nom_ent"],
                "municipio": info["nom_mun"],
                "ejercicio": y,
                "motivo": motivo,
                "obs_validas_muni": len(obs),
                "tipo_esquema_observado_prev": tipo_prev,
                "tipo_esquema_observado_next": tipo_next,
                "anio_prev": prev_y if prev_y is not None else "",
                "anio_next": next_y if next_y is not None else "",
                "pdf_candidato": pdf_name,
                "ruta_pdf": pdf_path,
                "tipo_esquema_decidido": "",
                "numero_rangos_decidido": "",
                "monto_max_rango_decidido": "",
                "es_reforma_real": "",
                "decision_final": "",
                "comentarios_auditor": "",
                "auditor": "",
                "fecha": "",
            })

    # Filtrar a las clases que queremos auditar (exclude no_data — esos no son
    # auditables ítem a ítem; ya cubiertos en short_form sintético o requieren
    # búsqueda manual de PDFs).
    rows = [r for r in rows if r["motivo"] in {"schema_discontinuity", "edge"}]
    return rows


def _add_residual_unsegmented_rows(
    rows: list[dict],
    universe: dict[str, dict],
) -> list[dict]:
    """Añade filas para focus_predial residuales que el segmentador NO logró
    crear (status=no_predial_found en predial_sections.csv después del fallback).
    """
    sections_csv = Path("data/yucatan/meta/predial_sections.csv")
    if not sections_csv.exists():
        return rows

    # Lookup de cvegeo por (estado, slug)
    nom_to_cvegeo: dict[tuple[str, str], str] = {}
    for cv, info in universe.items():
        if info["nom_ent"] != "Yucatan":
            continue
        from src.core.text_utils import slugify
        nom_to_cvegeo[("Yucatan", slugify(info["nom_mun"]))] = cv

    from src.core.text_utils import slugify
    with sections_csv.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r.get("status") != "no_predial_found":
                continue
            try:
                anio = int(r["ejercicio"])
            except (ValueError, TypeError):
                continue
            if not (EJERCICIO_INI <= anio <= EJERCICIO_FIN):
                continue
            muni_slug = slugify(r.get("municipio", ""))
            cv = nom_to_cvegeo.get(("Yucatan", muni_slug), "")
            pdf_name = (r.get("file") or "").replace("\\", "/").split("/")[-1]
            pdf_path = f"data/yucatan/pdf_raw/{r.get('file', '')}".replace("\\", "/")
            rows.append({
                "cvegeo": cv,
                "estado": "Yucatan",
                "municipio": r.get("municipio", ""),
                "ejercicio": anio,
                "motivo": "sin_predial_residual",
                "obs_validas_muni": "",
                "tipo_esquema_observado_prev": "",
                "tipo_esquema_observado_next": "",
                "anio_prev": "",
                "anio_next": "",
                "pdf_candidato": pdf_name,
                "ruta_pdf": pdf_path,
                "tipo_esquema_decidido": "",
                "numero_rangos_decidido": "",
                "monto_max_rango_decidido": "",
                "es_reforma_real": "",
                "decision_final": "",
                "comentarios_auditor": "",
                "auditor": "",
                "fecha": "",
            })
    return rows


def _write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_AUDIT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in sorted(rows, key=lambda r: (r["estado"], r["municipio"], r["ejercicio"])):
            w.writerow(row)


def _write_md(rows: list[dict], out_path: Path) -> None:
    """Vista markdown navegable agrupada por muni."""
    out_path.parent.mkdir(parents=True, exist_ok=True)

    by_muni: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in rows:
        by_muni[(r["estado"], r["municipio"], r["cvegeo"])].append(r)

    # Conteos
    motivos = defaultdict(int)
    for r in rows:
        motivos[r["motivo"]] += 1

    lines = []
    lines.append("# Documento de auditoría — huecos pendientes")
    lines.append("")
    lines.append("Acompaña a `output/audit_pendiente.csv` (formato rellenable).")
    lines.append("")
    lines.append(f"**Total de filas a auditar: {len(rows)}**")
    lines.append("")
    lines.append("Por motivo:")
    for m, n in sorted(motivos.items(), key=lambda x: -x[1]):
        lines.append(f"- `{m}`: {n}")
    lines.append("")

    lines.append("## Cómo llenar el CSV")
    lines.append("")
    lines.append("Por cada fila, después de revisar el PDF candidato:")
    lines.append("")
    lines.append("| Columna | Qué llenar |")
    lines.append("|---|---|")
    lines.append("| `tipo_esquema_decidido` | Uno de: `tarifa_millar`, `progresivo`, `tasa_unica`, `cuota_fija_simple`, `cuota_fija_escalonada`, `mixto`, `otro_no_clasificado`, o `imputable` si confirma que aplica imputación. |")
    lines.append("| `numero_rangos_decidido` | Entero si `tipo_esquema_decidido` ∈ {progresivo, cuota_fija_escalonada, mixto}; vacío si no aplica. |")
    lines.append("| `monto_max_rango_decidido` | Float (valor máximo del campo `superior` no-nulo); vacío si no aplica. |")
    lines.append("| `es_reforma_real` | `sí` si el cambio entre años observados es una reforma genuina (en cuyo caso el hueco queda como missing); `no` si fue error de extracción; `N/A` para `edge` o `sin_predial_residual`. |")
    lines.append("| `decision_final` | `imputar` (aplicar valor al hueco), `excluir` (marcar como missing definitivo), `reextraer` (re-correr LLM con prompt mejorado), `manual_fill` (insertar valores decididos). |")
    lines.append("| `comentarios_auditor` | Notas libres. Cita el artículo/página del PDF si es manual_fill. |")
    lines.append("| `auditor`, `fecha` | Identificación del revisor y fecha YYYY-MM-DD. |")
    lines.append("")

    lines.append("## Munis a auditar")
    lines.append("")
    for (estado, mun, cv), items in sorted(by_muni.items()):
        lines.append(f"### {estado} — {mun} ({cv})")
        lines.append("")
        lines.append("| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |")
        lines.append("|---|---|---|---|---:|---:|---|")
        for it in sorted(items, key=lambda x: x["ejercicio"]):
            lines.append(
                f"| {it['ejercicio']} | `{it['motivo']}` | "
                f"{it['tipo_esquema_observado_prev'] or '—'} | "
                f"{it['tipo_esquema_observado_next'] or '—'} | "
                f"{it['anio_prev'] or '—'} | {it['anio_next'] or '—'} | "
                f"{it['pdf_candidato'] or '—'} |"
            )
        lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


def main():
    print("Cargando catálogo INEGI y panel crudo...")
    universe = _load_inegi_universe(Path("catalogs/municipios_inegi.csv"))

    new_munis_by_cve = _load_new_municipalities(Path("catalogs/changes_ageeml.csv"))
    new_munis_by_cvegeo = {
        f"{ce}{cm}".zfill(5): yr
        for (ce, cm), yr in new_munis_by_cve.items()
    }

    raw = _read_panel(Path("output/panel_v2.csv"))
    raw = [r for r in raw if r["estado"] not in EXCLUDED_NOM_ENT]
    raw = [r for r in raw if EJERCICIO_INI <= r["ejercicio"] <= EJERCICIO_FIN]
    raw_by_muni: dict[str, list[dict]] = defaultdict(list)
    for r in raw:
        raw_by_muni[r["cvegeo"]].append(r)

    state_donors = _build_state_donors(raw_by_muni, universe)

    print("Calculando huecos remanentes (schema_discontinuity, edge)...")
    rows = _build_audit_rows(
        raw_by_muni, universe, new_munis_by_cvegeo, state_donors,
        EJERCICIO_INI, EJERCICIO_FIN,
    )
    print(f"  schema_discontinuity + edge: {len(rows)}")

    print("Sumando focus_predial residuales (sin_predial_residual)...")
    n_before = len(rows)
    rows = _add_residual_unsegmented_rows(rows, universe)
    print(f"  sin_predial_residual añadidos: {len(rows) - n_before}")

    csv_path = Path("output/audit_pendiente.csv")
    md_path = Path("output/audit_pendiente.md")
    _write_csv(rows, csv_path)
    _write_md(rows, md_path)
    print(f"\n  -> {csv_path} ({len(rows)} filas)")
    print(f"  -> {md_path}")


if __name__ == "__main__":
    main()
