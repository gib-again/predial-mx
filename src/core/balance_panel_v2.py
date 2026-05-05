"""Panel taxonómico v2 balanceado: aplica imputación a output/panel_v2.csv.

Reglas aplicadas (en orden, una vez que las anteriores no llenan el hueco):

  1. confirmed_fill         — gap ≤ 4 con extremos idénticos (tipo+rangos+monto).
  2. ffill                  — gap ≤ 4 hacia adelante, sin contradicción posterior.
  3. bfill                  — gap ≤ 4 hacia atrás, respeta creation_year.
  4. closure_fill           — primer y último observado del muni coinciden
                              (mismo tipo+rangos+monto), llenar todo en medio.
  5. tipo_only_fill         — gap ≤ 4 con extremos del mismo tipo_esquema
                              pero distintos rangos/monto. Imputa solo
                              tipo_esquema (rangos/monto quedan vacíos).
  6. uniform_state_fill     — solo para estados con tarifa estatal uniforme
                              (Chihuahua, Colima, Edomex, Sinaloa, Tabasco):
                              dona valores de cualquier muni del estado-año.

Outputs:
  predial-mx-v2/{estado}/*.json         — JSONs imputados con `_meta.modelo`
                                            "imputed_<método>" (vía impute_jsons).
  output/panel_v2_balanced.csv          — vista CSV rectangular del balance.
  output/panel_v2_balance_report.md     — cobertura, fuentes de desbalance y
                                            sugerencias human-in-the-loop por muni.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from src.core.constants import EJERCICIO_INI, EJERCICIO_FIN
from src.core.impute import _load_new_municipalities
from src.core.text_utils import slugify


INCLUDED_NOM_ENT = {
    "Coahuila de Zaragoza", "Chihuahua", "Colima", "Guanajuato", "Jalisco",
    "Mexico", "Queretaro", "San Luis Potosi", "Sinaloa", "Sonora",
    "Tabasco", "Tamaulipas", "Yucatan",
}
EXCLUDED_NOM_ENT = {"Oaxaca"}

UNIFORM_STATES_NOM_ENT = {"Chihuahua", "Colima", "Mexico", "Sinaloa", "Tabasco"}

# Mapeos para resolver paths del corpus v2 a partir del NOM_ENT del catálogo.
ESTADO_SLUG_BY_NOM_ENT = {
    "Coahuila de Zaragoza": "coahuila",
    "Chihuahua": "chihuahua",
    "Colima": "colima",
    "Guanajuato": "guanajuato",
    "Jalisco": "jalisco",
    "Mexico": "edomex",
    "Queretaro": "queretaro",
    "San Luis Potosi": "sanluispotosi",
    "Sinaloa": "sinaloa",
    "Sonora": "sonora",
    "Tabasco": "tabasco",
    "Tamaulipas": "tamaulipas",
    "Yucatan": "yucatan",
}
PREFIJOS_BY_SLUG = {
    "coahuila":   "COAH", "chihuahua": "CHIH", "colima":  "COL",
    "guanajuato": "GTO",  "jalisco":   "JAL",  "edomex":  "MEX",
    "queretaro":  "QRO",  "sanluispotosi": "SLP",
    "sinaloa":   "SIN",  "sonora": "SON",
    "tabasco": "TAB",
    "tamaulipas": "TAMPS","yucatan":   "YUC",
}

# Confianza por método: define si clonamos `tabla` del donor o emitimos esqueleto.
HIGH_CONFIDENCE_METHODS = {"confirmed_fill", "closure_fill", "uniform_state_fill"}
LOW_CONFIDENCE_METHODS = {"ffill", "bfill", "tipo_only_fill"}

MAX_GAP_CONFIRMED = 4
MAX_GAP_FFILL = 4
MAX_GAP_BFILL = 4
MAX_GAP_TIPO_ONLY = 4

_VALUE_FIELDS = ["tipo_esquema", "numero_rangos", "monto_max_rango"]
_ID_FIELDS = ["cvegeo", "estado", "municipio"]
_OUT_FIELDS = (
    _ID_FIELDS + ["ejercicio"] + _VALUE_FIELDS + ["imputed", "imputed_from_year"]
)


# ── Helpers ──

def _same_schema(a: dict, b: dict) -> bool:
    """Igualdad estricta sobre los 3 campos taxonómicos."""
    if not a.get("tipo_esquema") or not b.get("tipo_esquema"):
        return False
    for f in _VALUE_FIELDS:
        if (a.get(f, "") or "") != (b.get(f, "") or ""):
            return False
    return True


def _same_tipo_only(a: dict, b: dict) -> bool:
    """Igualdad solo en tipo_esquema."""
    ta = a.get("tipo_esquema", "")
    tb = b.get("tipo_esquema", "")
    return bool(ta) and ta == tb


def _make_imputed(
    source: dict, year: int, method: str, source_year: int,
    cvegeo: str, estado: str, municipio: str,
    *, drop_rangos_monto: bool = False,
) -> dict:
    row = {
        "cvegeo": cvegeo,
        "estado": estado,
        "municipio": municipio,
        "ejercicio": year,
        "imputed": method,
        "imputed_from_year": source_year,
    }
    for f in _VALUE_FIELDS:
        row[f] = source.get(f, "")
    if drop_rangos_monto:
        row["numero_rangos"] = ""
        row["monto_max_rango"] = ""
    return row


def _make_raw(obs: dict, year: int) -> dict:
    return {
        "cvegeo": obs["cvegeo"],
        "estado": obs.get("estado", ""),
        "municipio": obs.get("municipio", ""),
        "ejercicio": year,
        "tipo_esquema": obs.get("tipo_esquema", ""),
        "numero_rangos": obs.get("numero_rangos", ""),
        "monto_max_rango": obs.get("monto_max_rango", ""),
        "imputed": "false",
        "imputed_from_year": "",
    }


# ── Imputación por muni (multi-pass) ──

def _impute_municipality(
    cvegeo: str,
    estado_nom_ent: str,
    municipio: str,
    obs: list[dict],
    year_min: int,
    year_max: int,
    creation_year: Optional[int],
    state_donor_by_year: dict[int, dict],
) -> tuple[dict[int, dict], list[tuple[int, str]]]:
    """Devuelve ({year: filled_row}, [(year, motivo) por hueco no llenado])."""
    by_year: dict[int, dict] = {int(r["ejercicio"]): r for r in obs}

    exists_since = year_min
    if creation_year is not None and creation_year > year_min:
        exists_since = creation_year

    filled: dict[int, dict] = {}

    # Cargar observaciones crudas.
    for y, r in by_year.items():
        if exists_since <= y <= year_max:
            filled[y] = _make_raw(r, y)

    is_uniform = estado_nom_ent in UNIFORM_STATES_NOM_ENT

    def _try_fill(y: int) -> bool:
        if y in filled:
            return True
        prev_year = next((py for py in range(y - 1, exists_since - 1, -1) if py in by_year), None)
        next_year = next((ny for ny in range(y + 1, year_max + 1) if ny in by_year), None)

        # 1. confirmed_fill (estricto)
        if prev_year is not None and next_year is not None:
            total_gap = next_year - prev_year - 1
            if total_gap <= MAX_GAP_CONFIRMED and _same_schema(by_year[prev_year], by_year[next_year]):
                filled[y] = _make_imputed(by_year[prev_year], y, "confirmed_fill", prev_year,
                                          cvegeo, estado_nom_ent, municipio)
                return True

        # 2. ffill (estricto)
        if prev_year is not None and (y - prev_year) <= MAX_GAP_FFILL:
            if next_year is None or (next_year - prev_year - 1) > MAX_GAP_CONFIRMED:
                filled[y] = _make_imputed(by_year[prev_year], y, "ffill", prev_year,
                                          cvegeo, estado_nom_ent, municipio)
                return True

        # 3. bfill (estricto)
        if next_year is not None and prev_year is None:
            if (next_year - y) <= MAX_GAP_BFILL:
                filled[y] = _make_imputed(by_year[next_year], y, "bfill", next_year,
                                          cvegeo, estado_nom_ent, municipio)
                return True
        return False

    # Paso 1-3: reglas estrictas año por año.
    for y in range(exists_since, year_max + 1):
        _try_fill(y)

    # Paso 4: closure_fill — extremos del muni coinciden.
    if by_year:
        ext_a = min(by_year.keys())
        ext_b = max(by_year.keys())
        if ext_a != ext_b and _same_schema(by_year[ext_a], by_year[ext_b]):
            for y in range(max(ext_a, exists_since), min(ext_b, year_max) + 1):
                if y not in filled:
                    filled[y] = _make_imputed(by_year[ext_a], y, "closure_fill", ext_a,
                                              cvegeo, estado_nom_ent, municipio)

    # Paso 5: tipo_only_fill — extremos del mismo tipo_esquema, gap ≤ 4.
    for y in range(exists_since, year_max + 1):
        if y in filled:
            continue
        prev_year = next((py for py in range(y - 1, exists_since - 1, -1) if py in by_year), None)
        next_year = next((ny for ny in range(y + 1, year_max + 1) if ny in by_year), None)
        if prev_year is not None and next_year is not None:
            total_gap = next_year - prev_year - 1
            if total_gap <= MAX_GAP_TIPO_ONLY and _same_tipo_only(by_year[prev_year], by_year[next_year]):
                filled[y] = _make_imputed(by_year[prev_year], y, "tipo_only_fill", prev_year,
                                          cvegeo, estado_nom_ent, municipio,
                                          drop_rangos_monto=True)

    # Paso 6: uniform_state_fill — solo para estados uniformes.
    if is_uniform:
        for y in range(exists_since, year_max + 1):
            if y in filled:
                continue
            donor = state_donor_by_year.get(y)
            if donor is not None and donor["cvegeo"] != cvegeo:
                src_year = int(donor["ejercicio"])
                filled[y] = _make_imputed(donor, y, "uniform_state_fill", src_year,
                                          cvegeo, estado_nom_ent, municipio)

    # Recopilar huecos restantes con motivo diagnóstico.
    gaps: list[tuple[int, str]] = []
    for y in range(exists_since, year_max + 1):
        if y in filled:
            continue
        prev_year = next((py for py in range(y - 1, exists_since - 1, -1) if py in by_year), None)
        next_year = next((ny for ny in range(y + 1, year_max + 1) if ny in by_year), None)
        if not by_year:
            motivo = "no_data"
        elif prev_year is None and next_year is None:
            motivo = "no_data"
        elif prev_year is not None and next_year is not None and (next_year - prev_year - 1) <= MAX_GAP_CONFIRMED:
            motivo = "schema_discontinuity"
        else:
            nearest = min(
                v for v in [
                    (y - prev_year) if prev_year is not None else None,
                    (next_year - y) if next_year is not None else None,
                ] if v is not None
            )
            motivo = "long_gap" if nearest > MAX_GAP_FFILL else "edge"
        gaps.append((y, motivo))

    return filled, gaps


# ── Pipeline ──

def _load_inegi_universe(catalog_path: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not catalog_path.exists():
        return out
    with catalog_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cvegeo = (row.get("CVEGEO") or "").strip().zfill(5)
            if cvegeo:
                out[cvegeo] = {
                    "nom_ent": (row.get("NOM_ENT") or "").strip(),
                    "nom_mun": (row.get("NOM_MUN") or "").strip(),
                    "cve_ent": (row.get("CVE_ENT") or "").strip(),
                    "cve_mun": (row.get("CVE_MUN") or "").strip(),
                }
    return out


def _read_panel(input_csv: Path) -> list[dict]:
    rows: list[dict] = []
    with input_csv.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            r["ejercicio"] = int(r["ejercicio"])
            rows.append(r)
    return rows


def _write_balanced(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_OUT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


def _build_state_donors(
    raw_by_muni: dict[str, list[dict]],
    universe: dict[str, dict],
) -> dict[str, dict[int, dict]]:
    """{nom_ent: {year: representative_obs}} para estados uniformes.
    Toma la primera obs encontrada en ese state-year (todos deberían coincidir)."""
    by_state_year: dict[str, dict[int, dict]] = defaultdict(dict)
    for cv, obs_list in raw_by_muni.items():
        info = universe.get(cv)
        if not info:
            continue
        nom_ent = info["nom_ent"]
        if nom_ent not in UNIFORM_STATES_NOM_ENT:
            continue
        for r in obs_list:
            y = int(r["ejercicio"])
            if y not in by_state_year[nom_ent]:
                by_state_year[nom_ent][y] = r
    return dict(by_state_year)


def _ideal_for_muni(year_min: int, year_max: int, creation_year: Optional[int]) -> int:
    if creation_year is None or creation_year <= year_min:
        return year_max - year_min + 1
    if creation_year > year_max:
        return 0
    return year_max - creation_year + 1


def _compute_state_coverage(
    raw_rows: list[dict],
    balanced_rows: list[dict],
    universe: dict[str, dict],
    new_munis_by_cvegeo: dict[str, int],
    year_min: int, year_max: int,
) -> list[dict]:
    munis_by_estado: dict[str, list[str]] = defaultdict(list)
    for cv, info in universe.items():
        if info["nom_ent"] in INCLUDED_NOM_ENT:
            munis_by_estado[info["nom_ent"]].append(cv)

    raw_by_estado = Counter(r["estado"] for r in raw_rows)
    bal_by_estado = Counter(r["estado"] for r in balanced_rows)

    out = []
    for est in sorted(INCLUDED_NOM_ENT):
        cvs = munis_by_estado[est]
        n_munis = len(cvs)
        ideal = sum(
            _ideal_for_muni(year_min, year_max, new_munis_by_cvegeo.get(cv))
            for cv in cvs
        )
        raw = raw_by_estado.get(est, 0)
        bal = bal_by_estado.get(est, 0)
        out.append({
            "estado": est,
            "munis_universo": n_munis,
            "obs_raw": raw,
            "obs_balanced": bal,
            "ideal": ideal,
            "cov_raw_pct": round(raw / ideal * 100, 1) if ideal else 0,
            "cov_balanced_pct": round(bal / ideal * 100, 1) if ideal else 0,
            "huecos": ideal - bal,
        })
    return out


def _detect_schema_discontinuities(raw_by_muni: dict[str, list[dict]]) -> list[dict]:
    out = []
    for cv, obs in raw_by_muni.items():
        obs_sorted = sorted(obs, key=lambda r: r["ejercicio"])
        for i in range(len(obs_sorted) - 1):
            a, b = obs_sorted[i], obs_sorted[i + 1]
            gap = b["ejercicio"] - a["ejercicio"] - 1
            if gap == 0 or not a.get("tipo_esquema") or not b.get("tipo_esquema"):
                continue
            if gap <= MAX_GAP_CONFIRMED and not _same_schema(a, b):
                # Tras tipo_only_fill el gap se cierra si tipo coincide.
                tipo_match = _same_tipo_only(a, b)
                diff = []
                if (a.get("tipo_esquema") or "") != (b.get("tipo_esquema") or ""):
                    diff.append(f"tipo:{a.get('tipo_esquema')}→{b.get('tipo_esquema')}")
                if (a.get("numero_rangos") or "") != (b.get("numero_rangos") or ""):
                    diff.append(f"rangos:{a.get('numero_rangos')}→{b.get('numero_rangos')}")
                if (a.get("monto_max_rango") or "") != (b.get("monto_max_rango") or ""):
                    diff.append(f"monto_max:{a.get('monto_max_rango')}→{b.get('monto_max_rango')}")
                out.append({
                    "cvegeo": cv,
                    "estado": a.get("estado", ""),
                    "municipio": a.get("municipio", ""),
                    "year_a": a["ejercicio"],
                    "year_b": b["ejercicio"],
                    "gap": gap,
                    "tipo_match": tipo_match,
                    "diff": " | ".join(diff),
                })
    return out


# ── Sugerencias human-in-the-loop ──

def _hitl_suggestion(
    cvegeo: str,
    info: dict,
    raw_obs: list[dict],
    gaps: list[tuple[int, str]],
    creation_year: Optional[int],
    year_min: int,
    year_max: int,
) -> dict | None:
    """Devuelve una sugerencia priorizada para cerrar los huecos de un muni."""
    if not gaps:
        return None

    nom_ent = info["nom_ent"]
    nom_mun = info["nom_mun"]

    motivos = Counter(m for _, m in gaps)
    main_motivo = motivos.most_common(1)[0][0]
    gap_years = sorted({y for y, _ in gaps})

    if main_motivo == "no_data":
        if nom_ent in UNIFORM_STATES_NOM_ENT:
            accion = (
                f"Verificar que el muni {nom_mun} ({cvegeo}) está activo y debería "
                f"recibir uniform_state_fill. Si el catálogo de creación no lo registra "
                f"como muni nuevo, agregar entrada en `catalogs/changes_ageeml.csv`."
            )
        else:
            ej = creation_year or year_min
            accion = (
                f"No hay PDFs/JSONs en `data/{nom_ent.lower()}/`. Buscar leyes de "
                f"ingresos {ej}–{year_max} en periódico oficial del estado y/o portal "
                f"municipal. Si hubo fusión/cambio de cabecera, registrarlo en "
                f"`catalogs/changes_ageeml.csv`."
            )
    elif main_motivo == "schema_discontinuity":
        examples = [(y, m) for y, m in gaps if m == "schema_discontinuity"][:3]
        years_str = ", ".join(str(y) for y, _ in examples)
        # Encontrar pares que rodean el hueco más antiguo.
        accion = (
            f"Auditar manualmente PDFs de los años {years_str} — el esquema cambió "
            f"entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es "
            f"real (reforma) o si hubo un error de extracción en uno de los extremos. "
            f"Si es real, los huecos deben quedar como missing (no imputables)."
        )
    elif main_motivo == "long_gap":
        accion = (
            f"Hueco temporal largo (>4 años): {gap_years[0]}–{gap_years[-1]}. "
            f"Re-ejecutar la extracción para esos años con `python -m scripts.run_pipeline "
            f"{nom_ent.lower()} --steps download,segment,extract` y validar los PDFs "
            f"en `data/{nom_ent.lower()}/pdf_raw/`."
        )
    elif main_motivo == "edge":
        accion = (
            f"Hueco al borde de la ventana ({gap_years[0]}–{gap_years[-1]}). "
            f"Probable que falte el PDF más reciente o el más antiguo. "
            f"Revisar `data/{nom_ent.lower()}/pdf_raw/` y completar."
        )
    else:
        accion = "Motivo no clasificado — inspeccionar manualmente."

    return {
        "cvegeo": cvegeo,
        "estado": nom_ent,
        "municipio": nom_mun,
        "huecos": len(gap_years),
        "anos": ",".join(str(y) for y in gap_years),
        "motivo_principal": main_motivo,
        "obs_validas": len(raw_obs),
        "accion_sugerida": accion,
    }


# ── Reporte ──

def _write_report(
    state_coverage: list[dict],
    universe: dict[str, dict],
    raw_by_muni: dict[str, list[dict]],
    balanced_rows: list[dict],
    all_gaps: list[tuple[str, int, str]],
    schema_discontinuities: list[dict],
    method_counts: Counter,
    new_munis_by_cvegeo: dict[str, int],
    hitl_suggestions: list[dict],
    out_path: Path,
    year_min: int,
    year_max: int,
) -> None:
    n_years = year_max - year_min + 1

    universo_no_oax = {
        cv: info for cv, info in universe.items() if info["nom_ent"] in INCLUDED_NOM_ENT
    }
    munis_con_dato = set(raw_by_muni.keys())
    munis_sin_dato = sorted(set(universo_no_oax) - munis_con_dato)

    by_motivo = Counter(g[2] for g in all_gaps)
    by_estado_gaps = Counter()
    for cv, _y, _motivo in all_gaps:
        info = universe.get(cv)
        if info:
            by_estado_gaps[info["nom_ent"]] += 1

    huecos_por_muni = Counter(g[0] for g in all_gaps)
    top_huecos = huecos_por_muni.most_common(20)

    n_munis_universe = len(universo_no_oax)
    ideal_total = sum(s["ideal"] for s in state_coverage)
    obs_balanced = len(balanced_rows)
    cov_total = obs_balanced / ideal_total * 100 if ideal_total else 0

    raw_count = sum(1 for r in balanced_rows if r["imputed"] == "false")
    imputed_count = obs_balanced - raw_count

    lines = []
    lines.append("# Reporte de balance — panel v2 (con reglas extendidas)")
    lines.append("")
    lines.append(f"Rango temporal: **{year_min}–{year_max}** ({n_years} años).")
    lines.append(f"Estados incluidos: {len(INCLUDED_NOM_ENT)} (excluido: Oaxaca).")
    lines.append("")
    lines.append("Reglas aplicadas (en orden):")
    lines.append("`confirmed_fill` → `ffill` → `bfill` → `closure_fill` → `tipo_only_fill` → `uniform_state_fill`.")
    lines.append("Estados con `uniform_state_fill`: Chihuahua, Colima, Estado de México, Sinaloa, Tabasco.")
    lines.append("")
    lines.append("## 1. Métricas globales")
    lines.append("")
    lines.append(f"- Municipios en universo (excl. Oaxaca): **{n_munis_universe}**")
    lines.append(f"- Cobertura ideal (ajustada por creation_year): {ideal_total:,} celdas")
    lines.append(f"- Panel balanceado: **{obs_balanced:,}** celdas (**{cov_total:.1f}%** cobertura)")
    lines.append(f"  - Observaciones crudas: {raw_count:,}")
    lines.append(f"  - Imputadas: {imputed_count:,}")
    for method, n in method_counts.most_common():
        if method != "false":
            lines.append(f"    - `{method}`: {n:,}")
    huecos_total = ideal_total - obs_balanced
    lines.append(f"- Huecos remanentes: **{huecos_total:,}** "
                 f"({huecos_total / ideal_total * 100:.1f}%)" if ideal_total else "")
    lines.append("")

    lines.append("## 2. Cobertura por estado")
    lines.append("")
    lines.append("| Estado | Munis | Ideal | Crudo | Balanceado | Cov. cruda | Cov. balanceada | Huecos |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|")
    for s in sorted(state_coverage, key=lambda x: -x["cov_balanced_pct"]):
        lines.append(
            f"| {s['estado']} | {s['munis_universo']} | {s['ideal']} | {s['obs_raw']} | "
            f"{s['obs_balanced']} | {s['cov_raw_pct']}% | {s['cov_balanced_pct']}% | {s['huecos']} |"
        )
    lines.append("")

    lines.append("## 3. Fuentes de desbalance")
    lines.append("")
    lines.append(f"### 3.1 Municipios sin ningún dato observado ({len(munis_sin_dato)})")
    lines.append("")
    if munis_sin_dato:
        lines.append("Para los munis en estados uniformes (Chihuahua, Colima, EdoMex, Sinaloa, "
                     "Tabasco) la regla `uniform_state_fill` ya completó la cobertura. Los demás "
                     "siguen sin dato y requieren búsqueda manual.")
        lines.append("")
        lines.append("| cvegeo | Estado | Municipio | Cubierto via uniform_state_fill |")
        lines.append("|---|---|---|:---:|")
        for cv in munis_sin_dato:
            info = universe[cv]
            cubierto = "sí" if info["nom_ent"] in UNIFORM_STATES_NOM_ENT else "no"
            lines.append(f"| {cv} | {info['nom_ent']} | {info['nom_mun']} | {cubierto} |")
    else:
        lines.append("(ninguno)")
    lines.append("")

    lines.append(f"### 3.2 Huecos remanentes por motivo ({sum(by_motivo.values()):,})")
    lines.append("")
    lines.append("| Motivo | Conteo | Significado |")
    lines.append("|---|---:|---|")
    motivos_descr = {
        "long_gap": "Hueco > 4 años desde la observación más cercana → ffill/bfill no aplican; closure_fill tampoco (extremos no coinciden).",
        "schema_discontinuity": "tipo_esquema/rangos/monto_max difieren entre las observaciones que rodean el hueco; tipo_only_fill solo aplica si tipo_esquema coincide.",
        "edge": "Hueco al inicio/fin de la ventana sin observación cercana del lado faltante.",
        "no_data": "Muni con 0 observaciones en la ventana — solo se cubre vía uniform_state_fill.",
    }
    for motivo, n in by_motivo.most_common():
        lines.append(f"| `{motivo}` | {n:,} | {motivos_descr.get(motivo, '?')} |")
    lines.append("")

    lines.append("### 3.3 Huecos remanentes por estado")
    lines.append("")
    lines.append("| Estado | Huecos remanentes |")
    lines.append("|---|---:|")
    for est, n in by_estado_gaps.most_common():
        lines.append(f"| {est} | {n:,} |")
    lines.append("")

    pct_disc = sum(1 for d in schema_discontinuities if not d["tipo_match"])
    lines.append(f"### 3.4 Discontinuidades de esquema en gaps ≤ 4 años ({len(schema_discontinuities)})")
    lines.append("")
    lines.append(f"De estas, **{pct_disc}** son cambios de `tipo_esquema` (siguen bloqueando "
                 "imputación) y **{}** son solo cambios de rangos/monto (cubiertas por "
                 "`tipo_only_fill`).".format(len(schema_discontinuities) - pct_disc))
    lines.append("")
    if schema_discontinuities:
        lines.append("| cvegeo | Estado | Municipio | Año A | Año B | Gap | tipo coincide | Cambio |")
        lines.append("|---|---|---|---:|---:|---:|:---:|---|")
        for d in sorted(schema_discontinuities, key=lambda x: (x["tipo_match"], -x["gap"]))[:30]:
            tm = "sí" if d["tipo_match"] else "**no**"
            lines.append(
                f"| {d['cvegeo']} | {d['estado']} | {d['municipio']} | "
                f"{d['year_a']} | {d['year_b']} | {d['gap']} | {tm} | {d['diff']} |"
            )
        if len(schema_discontinuities) > 30:
            lines.append(f"| ... | | | | | | | (+{len(schema_discontinuities) - 30} más) |")
    lines.append("")

    lines.append("### 3.5 Top municipios con más huecos remanentes")
    lines.append("")
    lines.append("| cvegeo | Estado | Municipio | Huecos |")
    lines.append("|---|---|---|---:|")
    for cv, n in top_huecos:
        info = universe.get(cv, {})
        lines.append(f"| {cv} | {info.get('nom_ent', '?')} | {info.get('nom_mun', '?')} | {n} |")
    lines.append("")

    # ── Sección 4: Sugerencias HITL ──
    lines.append("## 4. Sugerencias human-in-the-loop")
    lines.append("")
    if not hitl_suggestions:
        lines.append("(no hay huecos remanentes — panel completamente balanceado)")
    else:
        lines.append("Una fila por muni con huecos. Ordenadas por número de huecos (descendente).")
        lines.append("")
        # Agrupar por motivo principal para resumen al inicio.
        by_motivo_hitl = Counter(s["motivo_principal"] for s in hitl_suggestions)
        lines.append("**Resumen por motivo principal:**")
        for motivo, n in by_motivo_hitl.most_common():
            lines.append(f"- `{motivo}`: {n} muni{'s' if n != 1 else ''}")
        lines.append("")
        lines.append("| cvegeo | Estado | Municipio | Huecos | Años | Motivo | Obs válidas | Acción sugerida |")
        lines.append("|---|---|---|---:|---|---|---:|---|")
        for s in sorted(hitl_suggestions, key=lambda x: -x["huecos"]):
            anos = s["anos"]
            if len(anos) > 60:
                anos = anos[:57] + "..."
            lines.append(
                f"| {s['cvegeo']} | {s['estado']} | {s['municipio']} | {s['huecos']} | "
                f"{anos} | `{s['motivo_principal']}` | {s['obs_validas']} | {s['accion_sugerida']} |"
            )
    lines.append("")

    # Sección 5: comandos útiles.
    lines.append("## 5. Comandos útiles para reextracción")
    lines.append("")
    lines.append("```bash")
    lines.append("# Reextracción de un muni-año específico (revisar primero el PDF crudo)")
    lines.append("python -m scripts.run_pipeline {estado} --steps extract --slug {slug} --year {YYYY}")
    lines.append("")
    lines.append("# Auditar discontinuidad: comparar JSON antes y después")
    lines.append("python -m scripts.regression_v1_v2 --cvegeo {cvegeo} --years {YYYY,YYYY}")
    lines.append("")
    lines.append("# Marcar una observación como 'excluir' en el audit CSV correspondiente")
    lines.append("# (data/{estado}/qa/audit_{PREFIJO}.csv) para que el panel la ignore.")
    lines.append("```")
    lines.append("")

    out_path.write_text("\n".join(lines), encoding="utf-8")


# ════════════════════════════════════════════════════════════════════
# impute_jsons — escribe JSONs imputados a predial-mx-v2/{estado}/
# ════════════════════════════════════════════════════════════════════

def _slug_by_cvegeo_from_catalog(catalog_path: Path) -> dict[str, str]:
    """{cvegeo: slug} desde catálogo INEGI (NOM_MUN slugified)."""
    out: dict[str, str] = {}
    if not catalog_path.exists():
        return out
    with catalog_path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            cvegeo = (r.get("CVEGEO") or "").strip().zfill(5)
            slug = slugify(r.get("NOM_MUN") or "")
            if cvegeo and slug:
                out[cvegeo] = slug
    return out


def _read_donor_json(
    cvegeo: str, donor_year: int, estado_slug: str, slug: str,
    v2_root: Path,
) -> tuple[Path, dict] | None:
    """Localiza y lee el JSON donor.

    Busca primero en `predial-mx-v2/{estado_slug}/` (corpus v2 estándar) y
    si no encuentra, hace fallback a `data/{estado_slug}/json_predial/{año}/`
    (estados v1 in-memory: oaxaca, sanluispotosi, sonora).
    """
    prefijo = PREFIJOS_BY_SLUG.get(estado_slug)
    if not prefijo:
        return None
    fname = f"{prefijo}_PREDIAL_{donor_year}_{slug}.json"

    # 1. Buscar en corpus v2
    path_v2 = v2_root / estado_slug / fname
    if path_v2.exists():
        try:
            return path_v2, json.loads(path_v2.read_text(encoding="utf-8"))
        except Exception:
            pass

    # 2. Fallback: data/{estado}/json_predial/{año}/
    path_v1 = Path("data") / estado_slug / "json_predial" / str(donor_year) / fname
    if path_v1.exists():
        try:
            return path_v1, json.loads(path_v1.read_text(encoding="utf-8"))
        except Exception:
            pass

    return None


def _build_imputed_predial(donor_predial: dict, method: str) -> dict:
    """Construye el dict 'predial' del JSON imputado según confianza del método.

    - HIGH_CONFIDENCE_METHODS: clonar el predial completo del donor.
    - LOW_CONFIDENCE_METHODS:  esqueleto mínimo con `tabla=[]` o equivalente.
    """
    if method in HIGH_CONFIDENCE_METHODS:
        # Clonación profunda vía json roundtrip (predial es siempre serializable).
        return json.loads(json.dumps(donor_predial))

    # Baja confianza — esqueleto sin clonar `tabla`.
    tipo = donor_predial.get("tipo_esquema") or ""
    skel: dict = {
        "tipo_esquema": tipo,
        "comentarios": (
            f"Imputado por {method}: tipo_esquema preservado del año donor; "
            f"tabla/rangos no clonados por baja confianza en estabilidad temporal."
        ),
        "minimo_predial": None,
    }
    # `tabla` se incluye vacía para que la variante quede sintácticamente válida
    # como referencia (la validación schema_v2 estricta no se aplica a imputados).
    if tipo in {
        "progresivo", "cuota_fija_escalonada", "mixto",
        "tarifa_millar", "tasa_unica", "cuota_fija_simple",
    }:
        skel["tabla"] = []
    if tipo == "otro_no_clasificado":
        # Preservar campos requeridos por OtroNoClasificadoSchema.
        skel["categoria"] = donor_predial.get("categoria", "estructura_no_estandar")
        skel["descripcion_estructural"] = (
            f"Imputado por {method}; descripción heredada del año donor."
        )
        skel["tabla_cruda"] = []
    return skel


def _build_imputed_doc(
    cvegeo: str, anio: int, estado_slug: str,
    method: str, donor_year: int, donor_doc: dict,
) -> dict:
    donor_predial = donor_doc.get("predial") or {}
    src_meta = donor_doc.get("_meta") or {}
    return {
        "predial": _build_imputed_predial(donor_predial, method),
        "_meta": {
            "fuente": src_meta.get("fuente", "txt"),
            "modelo": f"imputed_{method}",
        },
        "_meta_v2": {
            "intentos": 0,
            "requiere_revision": False,
            "razon": None,
            "tokens": {"input": 0, "output": 0, "cached": 0},
            "cvegeo": cvegeo,
            "estado": estado_slug,
            "anio": anio,
            "imputed_from_year": donor_year,
            "imputed_method": method,
        },
    }


def impute_jsons(
    panel_csv: Path = Path("output/panel_v2.csv"),
    v2_root: Path = Path("predial-mx-v2"),
    catalog_inegi: Path = Path("catalogs/municipios_inegi.csv"),
    changes_catalog: Path = Path("catalogs/changes_ageeml.csv"),
    year_min: int = EJERCICIO_INI,
    year_max: int = EJERCICIO_FIN,
    dry_run: bool = False,
) -> tuple[int, int, Counter]:
    """Aplica las 6 reglas y escribe JSONs imputados a predial-mx-v2/{estado}/.

    Devuelve (n_escritos, n_skipped_donor_missing, counter_por_metodo).
    """
    print("=" * 60)
    print("  impute_jsons — imputando JSONs a predial-mx-v2/")
    print("=" * 60)

    universe = _load_inegi_universe(catalog_inegi)
    slug_by_cvegeo = _slug_by_cvegeo_from_catalog(catalog_inegi)
    new_munis_by_cve = _load_new_municipalities(changes_catalog)
    new_munis_by_cvegeo: dict[str, int] = {
        f"{ce}{cm}".zfill(5): yr for (ce, cm), yr in new_munis_by_cve.items()
    }

    # Leer panel; filtrar Oaxaca, rango de años, y FUERA filas previamente
    # imputadas (idempotencia — solo trabajamos sobre observaciones crudas).
    raw = _read_panel(panel_csv)
    raw = [r for r in raw if r["estado"] not in EXCLUDED_NOM_ENT]
    raw = [r for r in raw if year_min <= r["ejercicio"] <= year_max]
    raw = [r for r in raw if not (r.get("imputed_method") or "").strip()]
    print(f"  filas crudas (excluye imputadas previas): {len(raw)}")

    raw_by_muni: dict[str, list[dict]] = defaultdict(list)
    for r in raw:
        raw_by_muni[r["cvegeo"]].append(r)

    state_donors = _build_state_donors(raw_by_muni, universe)

    n_written = 0
    n_donor_missing = 0
    n_existing_real = 0
    method_counts: Counter = Counter()

    for cv, info in sorted(universe.items()):
        if info["nom_ent"] not in INCLUDED_NOM_ENT:
            continue
        estado_slug = ESTADO_SLUG_BY_NOM_ENT.get(info["nom_ent"])
        prefijo = PREFIJOS_BY_SLUG.get(estado_slug or "")
        slug = slug_by_cvegeo.get(cv)
        if not (estado_slug and prefijo and slug):
            continue

        creation_year = new_munis_by_cvegeo.get(cv)
        obs = raw_by_muni.get(cv, [])
        donors_for_state = state_donors.get(info["nom_ent"], {})
        filled, _gaps = _impute_municipality(
            cv, info["nom_ent"], info["nom_mun"], obs,
            year_min, year_max, creation_year, donors_for_state,
        )

        for year, row in filled.items():
            method = row.get("imputed", "false")
            if method == "false":
                continue
            source_year = row.get("imputed_from_year")
            if not source_year:
                continue
            source_year = int(source_year)

            # Resolver donor JSON. uniform_state_fill puede venir de OTRO cvegeo.
            if method == "uniform_state_fill":
                donor_obs = donors_for_state.get(source_year)
                if not donor_obs:
                    n_donor_missing += 1
                    continue
                donor_cvegeo = donor_obs["cvegeo"]
                donor_slug = slug_by_cvegeo.get(donor_cvegeo)
                if not donor_slug:
                    n_donor_missing += 1
                    continue
                hit = _read_donor_json(
                    donor_cvegeo, source_year, estado_slug, donor_slug, v2_root,
                )
            else:
                hit = _read_donor_json(cv, source_year, estado_slug, slug, v2_root)

            if hit is None:
                n_donor_missing += 1
                continue
            _donor_path, donor_doc = hit

            # Path destino
            out_name = f"{prefijo}_PREDIAL_{year}_{slug}.json"
            out_path = v2_root / estado_slug / out_name

            # Idempotencia: no sobrescribir extracciones reales (LLM, hardcoded,
            # reclasified_v1, synthesized_short_form). Solo sobrescribir
            # imputaciones previas (`imputed_*`) o si no existe.
            if out_path.exists():
                try:
                    existing = json.loads(out_path.read_text(encoding="utf-8"))
                    existing_modelo = (existing.get("_meta") or {}).get("modelo", "")
                    if existing_modelo and not existing_modelo.startswith("imputed_"):
                        n_existing_real += 1
                        continue
                except Exception:
                    pass

            doc = _build_imputed_doc(
                cv, year, estado_slug, method, source_year, donor_doc,
            )
            if not dry_run:
                out_path.parent.mkdir(parents=True, exist_ok=True)
                out_path.write_text(
                    json.dumps(doc, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            n_written += 1
            method_counts[method] += 1

    print(f"  escritos: {n_written}")
    for m, n in method_counts.most_common():
        print(f"    {m}: {n}")
    if n_donor_missing:
        print(f"  donors faltantes (saltados): {n_donor_missing}")
    if n_existing_real:
        print(f"  destinos con extracción real preservados: {n_existing_real}")

    return n_written, n_donor_missing, method_counts


def balance_panel_v2(
    input_csv: Path = Path("output/panel_v2.csv"),
    output_csv: Path = Path("output/balance/panel_v2_balanced.csv"),
    report_md: Path = Path("output/balance/panel_v2_balance_report.md"),
    catalog_inegi: Path = Path("catalogs/municipios_inegi.csv"),
    changes_catalog: Path = Path("catalogs/changes_ageeml.csv"),
    v2_root: Path = Path("predial-mx-v2"),
    year_min: int = EJERCICIO_INI,
    year_max: int = EJERCICIO_FIN,
) -> tuple[Path, Path]:
    """Workflow completo:
       1. impute_jsons() — escribe JSONs imputados a predial-mx-v2/{estado}/
       2. build_panel_v2() — regenera panel_v2.csv con celdas imputadas
       3. Lee panel y emite panel_v2_balanced.csv (vista filtrada) + reporte
    """
    # ── Paso 1: imputar JSONs ──
    impute_jsons(
        panel_csv=input_csv, v2_root=v2_root,
        catalog_inegi=catalog_inegi, changes_catalog=changes_catalog,
        year_min=year_min, year_max=year_max,
    )

    # ── Paso 2: regenerar panel_v2.csv para que refleje los imputados ──
    print()
    from src.core.panel_v2 import build_panel_v2 as _build_panel
    _build_panel(v2_root=v2_root, catalog_path=catalog_inegi, out_csv=input_csv)

    # ── Paso 3: análisis de gaps + reporte ──
    print()
    print("=" * 60)
    print("  Análisis de huecos remanentes")
    print("=" * 60)

    universe = _load_inegi_universe(catalog_inegi)
    new_munis_by_cve = _load_new_municipalities(changes_catalog)
    new_munis_by_cvegeo: dict[str, int] = {
        f"{cve_ent}{cve_mun}".zfill(5): yr
        for (cve_ent, cve_mun), yr in new_munis_by_cve.items()
    }

    all_panel = _read_panel(input_csv)
    in_scope = [
        r for r in all_panel
        if r["estado"] not in EXCLUDED_NOM_ENT
        and year_min <= r["ejercicio"] <= year_max
    ]
    # Para detección de gaps usar sólo OBSERVACIONES (filas no imputadas).
    raw = [r for r in in_scope if not (r.get("imputed_method") or "").strip()]
    print(f"  filas en scope: {len(in_scope)}  (raw={len(raw)}, imputadas={len(in_scope)-len(raw)})")

    raw_by_muni: dict[str, list[dict]] = defaultdict(list)
    for r in raw:
        raw_by_muni[r["cvegeo"]].append(r)

    state_donors = _build_state_donors(raw_by_muni, universe)

    method_counts: Counter = Counter()
    all_gaps: list[tuple[str, int, str]] = []
    hitl_suggestions: list[dict] = []

    for cv, info in sorted(universe.items()):
        if info["nom_ent"] not in INCLUDED_NOM_ENT:
            continue
        creation_year = new_munis_by_cvegeo.get(cv)
        obs = raw_by_muni.get(cv, [])
        donors = state_donors.get(info["nom_ent"], {})
        filled, gaps = _impute_municipality(
            cv, info["nom_ent"], info["nom_mun"], obs,
            year_min, year_max, creation_year, donors,
        )
        for r in filled.values():
            method_counts[r["imputed"]] += 1
        for y, motivo in gaps:
            all_gaps.append((cv, y, motivo))
        if gaps:
            sug = _hitl_suggestion(cv, info, obs, gaps, creation_year, year_min, year_max)
            if sug:
                hitl_suggestions.append(sug)

    # Agregar `imputed` al row siguiendo el formato esperado por _write_balanced.
    balanced: list[dict] = []
    for r in in_scope:
        method = r.get("imputed_method") or "false"
        balanced.append({
            "cvegeo": r["cvegeo"],
            "estado": r.get("estado", ""),
            "municipio": r.get("municipio", ""),
            "ejercicio": r["ejercicio"],
            "tipo_esquema": r.get("tipo_esquema", ""),
            "numero_rangos": r.get("numero_rangos", ""),
            "monto_max_rango": r.get("monto_max_rango", ""),
            "imputed": method,
            "imputed_from_year": r.get("imputed_from_year", ""),
        })
    balanced.sort(key=lambda r: (r["cvegeo"], r["ejercicio"]))

    _write_balanced(balanced, output_csv)
    print(f"  -> {output_csv}")

    state_coverage = _compute_state_coverage(
        raw, balanced, universe, new_munis_by_cvegeo, year_min, year_max
    )
    schema_disc = _detect_schema_discontinuities(raw_by_muni)

    _write_report(
        state_coverage=state_coverage,
        universe=universe,
        raw_by_muni=raw_by_muni,
        balanced_rows=balanced,
        all_gaps=all_gaps,
        schema_discontinuities=schema_disc,
        method_counts=method_counts,
        new_munis_by_cvegeo=new_munis_by_cvegeo,
        hitl_suggestions=hitl_suggestions,
        out_path=report_md,
        year_min=year_min,
        year_max=year_max,
    )
    print(f"  -> {report_md}")
    print(f"  huecos remanentes: {len(all_gaps)}")
    return output_csv, report_md

    return output_csv, report_md
