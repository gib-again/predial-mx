#!/usr/bin/env python3
"""Auditoría de anomalías para event-study con tratamiento absorbente.

Tratamiento (T) := tipo_esquema ∈ {progresivo, mixto}.
Control    (C) := tipo_esquema ∈ {tarifa_millar, tasa_unica, cuota_fija_simple,
                                    cuota_fija_escalonada, otro_no_clasificado,
                                    desconocido}.

Para que un muni califique a un DiD con tratamiento ABSORBENTE su trayectoria
debe ser una de:
  - `siempre_C` (control puro) — válido como control.
  - `siempre_T` (tratado desde antes de la ventana) — útil pero no aporta
    variación temporal.
  - `clean_onset` (CCCC...TTTT con UNA sola transición C→T) — el caso ideal.

Cualquier otra trayectoria rompe el supuesto absorbente y necesita revisión:
  - `reversion`        : T sostenido → C sostenido (T...TCCC...).
  - `outlier_year_C_in_T`: T...TCT...T (un solo año C en medio de Ts).
  - `outlier_year_T_in_C`: C...CTC...C (un solo año T en medio de Cs).
  - `multi_flip`       : 2+ transiciones; trayectoria ruidosa.

Este script identifica cada AÑO problemático dentro de un muni anómalo, anota
su origen (LLM real, imputed_*, audit_no_ley, discovered_law, ...), localiza
el PDF/páginas (cuando hay segment metadata) y emite un CSV/MD audit-style.

El auditor decide por cada año:
  - `real_reform`        : la ley realmente cambió ese año (aceptar y excluir
                            el muni del DiD si rompe absorbing).
  - `extraction_error`   : el LLM clasificó mal; el tipo correcto es otro.
                            Llenar `tipo_correcto` y opcionalmente
                            `pdf_objetivo`/`paginas` para forzar
                            re-extracción.
  - `accept_as_is`       : el año es correcto pero el muni se trata como
                            "no absorbente" en el análisis.
  - `exclude_muni`       : descartar el muni completo del análisis.

Outputs:
  output/audit_treatment_anomalies.csv  — formato rellenable
  output/audit_treatment_anomalies.md   — vista navegable por muni
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

from src.core.balance_panel_v2 import (
    EXCLUDED_NOM_ENT,
    ESTADO_SLUG_BY_NOM_ENT,
    INCLUDED_NOM_ENT,
    PREFIJOS_BY_SLUG,
)
from src.core.constants import EJERCICIO_INI, EJERCICIO_FIN
from src.core.text_utils import slugify


TREATMENT_TIPOS = {"progresivo", "mixto"}
# Resto se considera control (incluye otro_no_clasificado, desconocido, etc.).


def _classify(tipo: str) -> str:
    """T si tratamiento, C si control."""
    return "T" if (tipo or "").strip() in TREATMENT_TIPOS else "C"


def _trajectory_pattern(seq: str) -> str:
    """Compacta la secuencia y la clasifica."""
    if not seq:
        return "vacio"
    if len(set(seq)) == 1:
        return "siempre_T" if seq[0] == "T" else "siempre_C"
    compact = "".join(c for i, c in enumerate(seq) if i == 0 or c != seq[i - 1])
    if compact == "CT":
        return "clean_onset"
    if compact == "TC":
        return "reversion_simple"
    if compact == "TCT":
        return "outlier_year_C_in_T"
    if compact == "CTC":
        return "outlier_year_T_in_C"
    if compact in ("CTCT", "TCTC"):
        return f"flip_x2[{compact}]"
    return f"multi_flip[{compact}]"


def _detect_anomalous_years(
    rows_sorted: list[dict],
) -> list[tuple[dict, str, str]]:
    """Para cada año dentro de un muni con trayectoria no-canónica,
    decide qué años son anómalos y por qué.

    Retorna lista de (row, motivo, tipo_esperado_ideal_T_or_C).

    Estrategia en dos pasos:
      1. Detectar outliers de 1 año (status[i] difiere de AMBOS vecinos).
      2. Sobre la secuencia SIN outliers, clasificar el patrón base y
         reportar segun corresponda.
    """
    if not rows_sorted:
        return []

    statuses = [_classify(r["tipo_esquema"]) for r in rows_sorted]
    n = len(statuses)
    if n < 2:
        return []

    # Paso 1: outliers de 1 año.
    outlier_indices: set[int] = set()
    for i in range(1, n - 1):
        if statuses[i - 1] == statuses[i + 1] and statuses[i - 1] != statuses[i]:
            outlier_indices.add(i)

    anomalies: list[tuple[dict, str, str]] = []
    for i in sorted(outlier_indices):
        s = statuses[i]
        expected = statuses[i - 1]  # vecinos coinciden
        anomalies.append((rows_sorted[i], f"outlier_{s}_in_{expected}", expected))

    # Paso 2: patrón sin outliers.
    clean = [s for i, s in enumerate(statuses) if i not in outlier_indices]
    if not clean:
        return anomalies
    clean_pattern = _trajectory_pattern("".join(clean))

    # Casos limpios — solo los outliers ya reportados son anomalía.
    if clean_pattern in ("siempre_T", "siempre_C", "clean_onset"):
        return anomalies

    # Reversión real: el bloque C final post-último-T (no-outlier).
    if clean_pattern == "reversion_simple":
        last_T_idx = None
        for i in range(n - 1, -1, -1):
            if i in outlier_indices:
                continue
            if statuses[i] == "T":
                last_T_idx = i
                break
        if last_T_idx is not None:
            for i in range(last_T_idx + 1, n):
                if i in outlier_indices:
                    continue
                if statuses[i] == "C":
                    anomalies.append((rows_sorted[i], "reversion_T_to_C", "T"))
        return anomalies

    # multi_flip / flip_x2 — reportar bloques minoritarios.
    n_T_clean = clean.count("T")
    n_C_clean = clean.count("C")
    minority_status = "T" if n_T_clean <= n_C_clean else "C"
    expected_majority = "C" if minority_status == "T" else "T"
    yrs_already = {a[0]["ejercicio"] for a in anomalies}
    for i, s in enumerate(statuses):
        if i in outlier_indices:
            continue
        if s == minority_status:
            yr = rows_sorted[i]["ejercicio"]
            if yr in yrs_already:
                continue
            motivo = (f"flip_minority_block_{s}_in_majority_{expected_majority}")
            anomalies.append((rows_sorted[i], motivo, expected_majority))
            yrs_already.add(yr)

    return anomalies


# ── Cargar metadata de segmentación (origen del año) ──

def _load_segment_locations(estados: set[str]) -> dict[tuple[str, int, str], dict]:
    """{(estado_slug, anio, muni_slug): {pdf, pages}} — formato segment.csv y QRO."""
    out: dict[tuple[str, int, str], dict] = {}
    for estado_slug in estados:
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
                        ps = (r.get("predial_page_start") or "").strip()
                        pe = (r.get("predial_page_end") or "").strip()
                        pages = ""
                        if ps and pe:
                            pages = f"p.{ps}-{pe}" if ps != pe else f"p.{ps}"
                        out[(estado_slug, anio, slug)] = {"pdf": pdf, "pages": pages}
            except Exception:
                pass
        sections_csv = Path(f"data/{estado_slug}/meta/predial_sections.csv")
        if sections_csv.exists():
            try:
                with sections_csv.open(encoding="utf-8") as f:
                    for r in csv.DictReader(f):
                        if "municipio_slug" not in r:
                            continue
                        try:
                            anio = int(r.get("ejercicio") or 0)
                        except (TypeError, ValueError):
                            continue
                        slug = (r.get("municipio_slug") or "").strip()
                        if not slug or not anio:
                            continue
                        if (estado_slug, anio, slug) in out:
                            continue
                        parts = (r.get("parts") or "").strip()
                        first_pdf = parts.split(";")[0].strip() if parts else (r.get("doc_id") or "")
                        articulo = (r.get("predial_articulo") or "").strip()
                        out[(estado_slug, anio, slug)] = {
                            "pdf": first_pdf,
                            "pages": f"art.{articulo}" if articulo else "",
                        }
            except Exception:
                pass
    return out


def _read_v2_modelo(estado_slug: str, prefijo: str, anio: int, slug: str) -> str:
    """Lee `_meta.modelo` del JSON v2 correspondiente. Si no se localiza por
    slug INEGI, escanea la carpeta y matchea por (cvegeo, anio).
    """
    direct = Path(f"predial-mx-v2/{estado_slug}/{prefijo}_PREDIAL_{anio}_{slug}.json")
    if direct.exists():
        try:
            d = json.loads(direct.read_text(encoding="utf-8"))
            return (d.get("_meta") or {}).get("modelo", "")
        except Exception:
            return ""
    return ""


# ── Output ──

_AUDIT_FIELDS = [
    "cvegeo", "estado", "municipio", "ejercicio_problema",
    "pattern_muni", "motivo", "trayectoria",
    "tipo_esquema_actual", "treatment_actual",
    "tipo_esperado_vecinos", "treatment_esperado",
    "modelo_actual", "source_pdf", "paginas",
    "numero_rangos_actual", "monto_max_rango_actual",
    # Llenar
    "decision",                # real_reform | extraction_error | accept_as_is | exclude_muni
    "tipo_correcto",           # si decision=extraction_error, qué tipo es realmente
    "pdf_objetivo", "paginas_objetivo",
    "notas",
    "auditor", "fecha",
]


def _build_trajectory_str(rows_sorted: list[dict], year_min: int, year_max: int) -> str:
    """Devuelve string compacto: 'C2010-2014, T2015-2019, C2020' o
    para gaps largos solo letras: 'CCCCCTTTTT'."""
    by_year = {int(r["ejercicio"]): _classify(r["tipo_esquema"]) for r in rows_sorted}
    parts = []
    for y in range(year_min, year_max + 1):
        s = by_year.get(y, "·")
        parts.append(s)
    return "".join(parts)


def main():
    print("Cargando panel y metadata...")
    panel = []
    with open("output/panel_v2.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                r["ejercicio"] = int(r["ejercicio"])
            except Exception:
                continue
            panel.append(r)

    in_scope = [r for r in panel
                if r["estado"] not in EXCLUDED_NOM_ENT
                and EJERCICIO_INI <= r["ejercicio"] <= EJERCICIO_FIN]

    by_muni: dict[str, list[dict]] = defaultdict(list)
    for r in in_scope:
        by_muni[r["cvegeo"]].append(r)

    estados_slug = set(ESTADO_SLUG_BY_NOM_ENT.values())
    seg_loc = _load_segment_locations(estados_slug)

    audit_rows: list[dict] = []
    pattern_counts: dict[str, int] = defaultdict(int)
    munis_anomalos = 0

    for cv, rows in sorted(by_muni.items()):
        rows.sort(key=lambda r: r["ejercicio"])
        if not rows:
            continue
        seq = "".join(_classify(r["tipo_esquema"]) for r in rows)
        pattern = _trajectory_pattern(seq)
        pattern_counts[pattern] += 1

        anomalies = _detect_anomalous_years(rows)
        if not anomalies:
            continue
        munis_anomalos += 1

        traj = _build_trajectory_str(rows, EJERCICIO_INI, EJERCICIO_FIN)
        estado_nom = rows[0]["estado"]
        estado_slug = ESTADO_SLUG_BY_NOM_ENT.get(estado_nom) or ""
        prefijo = PREFIJOS_BY_SLUG.get(estado_slug) or ""
        muni_slug = slugify(rows[0]["municipio"])

        for anom_row, motivo, tipo_esperado_status in anomalies:
            anio = int(anom_row["ejercicio"])
            modelo = _read_v2_modelo(estado_slug, prefijo, anio, muni_slug)
            loc = seg_loc.get((estado_slug, anio, muni_slug), {})

            audit_row = {
                "cvegeo": cv,
                "estado": estado_nom,
                "municipio": rows[0]["municipio"],
                "ejercicio_problema": anio,
                "pattern_muni": pattern,
                "motivo": motivo,
                "trayectoria": traj,
                "tipo_esquema_actual": anom_row.get("tipo_esquema", ""),
                "treatment_actual": _classify(anom_row.get("tipo_esquema", "")),
                "tipo_esperado_vecinos": "treatment" if tipo_esperado_status == "T" else "control",
                "treatment_esperado": tipo_esperado_status,
                "modelo_actual": modelo,
                "source_pdf": loc.get("pdf", ""),
                "paginas": loc.get("pages", ""),
                "numero_rangos_actual": anom_row.get("numero_rangos", ""),
                "monto_max_rango_actual": anom_row.get("monto_max_rango", ""),
                # Vacíos para auditor
                "decision": "",
                "tipo_correcto": "",
                "pdf_objetivo": "",
                "paginas_objetivo": "",
                "notas": "",
                "auditor": "",
                "fecha": "",
            }
            audit_rows.append(audit_row)

    print(f"\nDistribución de trayectorias:")
    for p, n in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        print(f"  {p:<35} {n}")
    print(f"\nMunis con anomalías: {munis_anomalos}")
    print(f"Años problemáticos a auditar: {len(audit_rows)}")

    # Escribir CSV
    csv_path = Path("output/audits/audit_treatment_anomalies.csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_AUDIT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in sorted(audit_rows, key=lambda r: (r["estado"], r["municipio"], r["ejercicio_problema"])):
            w.writerow(row)
    print(f"\n  -> {csv_path}")

    # MD
    md_path = Path("output/audits/audit_treatment_anomalies.md")
    by_muni_audit: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in audit_rows:
        by_muni_audit[(r["estado"], r["municipio"], r["cvegeo"])].append(r)

    motivo_counts: dict[str, int] = defaultdict(int)
    for r in audit_rows:
        motivo_counts[r["motivo"]] += 1

    lines: list[str] = []
    lines.append("# Auditoría de anomalías de tratamiento — event-study DiD")
    lines.append("")
    lines.append("**Objetivo**: identificar años que rompen el supuesto de tratamiento "
                 "absorbente (treatment una vez activado se queda activado) para decidir "
                 "si son errores de extracción/escaneo (recuperables) o reformas reales "
                 "(aceptar y descartar el muni del DiD).")
    lines.append("")
    lines.append("## Definiciones")
    lines.append("")
    lines.append("- **Treatment (T)**: `tipo_esquema ∈ {progresivo, mixto}`")
    lines.append("- **Control (C)**: el resto (`tarifa_millar`, `tasa_unica`, `cuota_fija_*`, "
                 "`otro_no_clasificado`, `desconocido`)")
    lines.append("")
    lines.append("## Distribución de trayectorias")
    lines.append("")
    lines.append("| Patrón | Munis | Significado |")
    lines.append("|---|---:|---|")
    descr = {
        "siempre_T": "tratado los 16 años — válido pero sin variación temporal",
        "siempre_C": "control puro — válido como control",
        "clean_onset": "C...CT...T — **caso ideal** para DiD absorbente",
        "reversion_simple": "T...TC...C — REVERSIÓN, rompe absorbing",
        "outlier_year_C_in_T": "TCT — un año C aislado en medio de tratamiento",
        "outlier_year_T_in_C": "CTC — un año T aislado en medio de control",
    }
    for p, n in sorted(pattern_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| `{p}` | {n} | {descr.get(p, 'patrón complejo, requiere revisión')} |")
    lines.append("")
    lines.append(f"**Munis a auditar**: {munis_anomalos} (con {len(audit_rows)} años problemáticos)")
    lines.append("")
    lines.append("## Por motivo")
    lines.append("")
    lines.append("| Motivo | Conteo |")
    lines.append("|---|---:|")
    for m, n in sorted(motivo_counts.items(), key=lambda x: -x[1]):
        lines.append(f"| `{m}` | {n} |")
    lines.append("")

    lines.append("## Cómo llenar el CSV")
    lines.append("")
    lines.append("Por cada año problemático, decidir:")
    lines.append("")
    lines.append("| `decision` | Cuándo usar |")
    lines.append("|---|---|")
    lines.append("| `real_reform` | El muni efectivamente cambió de régimen ese año (verificable en el PDF). El muni se descarta del DiD si rompe absorbing. |")
    lines.append("| `extraction_error` | El LLM clasificó mal — el tipo correcto es otro. Llena `tipo_correcto`; opcionalmente `pdf_objetivo`/`paginas_objetivo` para forzar re-extracción dirigida. |")
    lines.append("| `accept_as_is` | El año es correcto pero aceptas que el muni sea \"no absorbente\". Útil para munis multi-flip que vas a excluir. |")
    lines.append("| `exclude_muni` | Descartar el muni completo del análisis. Usa este valor en CUALQUIER fila del muni — la decisión se aplicará a todas. |")
    lines.append("")
    lines.append("Tras llenar el CSV, corre `python -m scripts.apply_treatment_audit` "
                 "(por crear) para aplicar las decisiones, o haz los cambios manualmente "
                 "según prefieras.")
    lines.append("")

    lines.append("## Munis a auditar")
    lines.append("")
    lines.append("Trayectoria por año (2010-2025): `T`=tratamiento, `C`=control, `·`=sin dato.")
    lines.append("")
    for (estado, mun, cv), items in sorted(by_muni_audit.items(),
                                            key=lambda x: (x[0][0], x[0][1])):
        first = items[0]
        lines.append(f"### {cv} {estado} — {mun}")
        lines.append("")
        lines.append(f"**Trayectoria** (2010-2025): `{first['trayectoria']}`")
        lines.append(f"**Patrón**: `{first['pattern_muni']}`")
        lines.append("")
        lines.append("| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |")
        lines.append("|---:|---|:---:|:---:|---|---|---|")
        for it in sorted(items, key=lambda x: x["ejercicio_problema"]):
            pdf_str = it["source_pdf"]
            if pdf_str and len(pdf_str) > 35:
                pdf_str = pdf_str[:32] + "..."
            page_str = it["paginas"]
            loc = f"{pdf_str} {page_str}".strip() if pdf_str or page_str else "—"
            lines.append(
                f"| {it['ejercicio_problema']} | {it['tipo_esquema_actual']} | "
                f"**{it['treatment_actual']}** | {it['treatment_esperado']} | "
                f"`{it['motivo']}` | {it['modelo_actual'] or '—'} | {loc} |"
            )
        lines.append("")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  -> {md_path}")


if __name__ == "__main__":
    main()
