"""
Fase 7: Imputación para panel balanceado.

Lee output/predial_panel.csv (crudo) y genera output/predial_panel_balanced.csv
con observaciones imputadas para cerrar huecos temporales.

Reglas de imputación (en orden de aplicación):

  1. CONFIRMED FILL (gap ≤ 4 años):
     Si en año T existe tasa X, en T+1..T+k no hay dato, y en T+k+1
     la tasa es IGUAL a X (misma tasa y mismo esquema) → imputar X
     en T+1..T+k.  Máximo gap: 4 años.
     Etiqueta: "confirmed_fill"

  2. AGGRESSIVE FILL (gap ≤ 2 años):
     Si en año T existe tasa X, en T+1..T+k no hay dato, y en T+k+1
     la tasa es DIFERENTE Y → mantener tasa X del año T en los huecos.
     Máximo gap: 2 años.
     Etiqueta: "aggressive_fill"

  3. FORWARD FILL (gap ≤ 4 años):
     Si en año T existe tasa X y no hay dato posterior que confirme
     ni contradiga → forward-fill X.  Máximo gap: 4 años.
     Etiqueta: "ffill"

  4. BACKWARD FILL (gap ≤ 4 años):
     Si el primer dato es en año T y no hay dato anterior, llenar
     hacia atrás SOLO si el municipio ya existía (no es nuevo).
     Los municipios nuevos se identifican con catalogs/changes_ageeml.csv
     (CGO_ACT = "M", FECHA_ACT indica año de creación).
     Etiqueta: "bfill"

Columnas agregadas en el panel balanceado:
  - imputed: false | confirmed_fill | aggressive_fill | ffill | bfill
  - imputed_from_year: año del dato fuente (vacío si no imputado)

Notas:
  - Los datos crudos nunca se modifican (imputed = "false").
  - Un municipio sin NINGÚN dato observado no se imputa.
  - El rango de años del panel es EJERCICIO_INI..EJERCICIO_FIN de constants.py.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Optional

from src.core.constants import EJERCICIO_INI, EJERCICIO_FIN


# ══════════════════════════════════════════════════════════════
# Catálogo de municipios nuevos
# ══════════════════════════════════════════════════════════════

def _load_new_municipalities(catalog_path: Path) -> dict[tuple[str, str], int]:
    """
    Lee changes_ageeml.csv y devuelve dict (cve_ent, cve_mun) → año de creación.
    Solo entradas con CGO_ACT = "M" (nuevo municipio).
    """
    new_munis: dict[tuple[str, str], int] = {}
    if not catalog_path.exists():
        return new_munis

    with catalog_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cgo = (row.get("CGO_ACT") or "").strip().strip('"')
            if cgo != "M":
                continue
            cve_ent = (row.get("CVE_ENT") or "").strip().strip('"')
            cve_mun = (row.get("CVE_MUN") or "").strip().strip('"')
            fecha = (row.get("FECHA_ACT") or "").strip().strip('"')
            if not cve_ent or not cve_mun or not fecha:
                continue
            try:
                year = int(fecha[:4])
            except (ValueError, IndexError):
                continue
            key = (cve_ent, cve_mun)
            # Si hay múltiples entradas, usar la más temprana
            if key not in new_munis or year < new_munis[key]:
                new_munis[key] = year

    return new_munis


# ══════════════════════════════════════════════════════════════
# Imputación
# ══════════════════════════════════════════════════════════════

# Campos que se copian en la imputación
_IMPUTE_FIELDS = [
    "tipo_esquema", "tasa_urbano", "tasa_urbano_edificado",
    "tasa_rustico", "tasa_baldio", "n_rangos", "cuota_minima",
]

# Campos de identidad (se copian siempre)
_ID_FIELDS = ["cve_ent", "cve_mun", "municipio", "estado"]

MAX_GAP_CONFIRMED = 4
MAX_GAP_AGGRESSIVE = 2
MAX_GAP_FFILL = 4
MAX_GAP_BFILL = 4


def _same_tasa(a: dict, b: dict) -> bool:
    """Verifica si dos registros tienen la misma tasa_urbano y tipo_esquema."""
    ta = a.get("tasa_urbano", "")
    tb = b.get("tasa_urbano", "")
    if not ta or not tb:
        return False
    ea = a.get("tipo_esquema", "")
    eb = b.get("tipo_esquema", "")
    return ta == tb and ea == eb


def _make_imputed_row(source: dict, year: int, method: str, source_year: int) -> dict:
    """Crea una fila imputada copiando datos de source para un año dado."""
    row = {}
    for f in _ID_FIELDS:
        row[f] = source.get(f, "")
    row["ejercicio"] = str(year)
    for f in _IMPUTE_FIELDS:
        row[f] = source.get(f, "")
    row["fuente_json"] = ""
    row["extraction_method"] = ""
    row["imputed"] = method
    row["imputed_from_year"] = str(source_year)
    return row


def _impute_municipality(
    obs: list[dict],
    year_min: int,
    year_max: int,
    creation_year: Optional[int],
) -> list[dict]:
    """
    Imputa huecos para un municipio.

    Args:
        obs: lista de observaciones crudas, ordenadas por ejercicio.
        year_min: primer año del panel.
        year_max: último año del panel.
        creation_year: año de creación del municipio (None si ya existía antes de year_min).

    Returns:
        Lista completa (crudos + imputados) ordenada por ejercicio.
    """
    if not obs:
        return []

    # Indexar por año
    by_year: dict[int, dict] = {}
    for r in obs:
        y = int(r["ejercicio"])
        by_year[y] = r

    obs_years = sorted(by_year.keys())
    first_obs = obs_years[0]
    last_obs = obs_years[-1]

    # El municipio "existe desde" creation_year si hay dato, sino desde year_min
    exists_since = year_min
    if creation_year is not None and creation_year > year_min:
        exists_since = creation_year

    result: list[dict] = []

    for y in range(year_min, year_max + 1):
        if y in by_year:
            # Dato crudo
            row = by_year[y].copy()
            row.setdefault("imputed", "false")
            row.setdefault("imputed_from_year", "")
            result.append(row)
            continue

        # No hay dato para este año — intentar imputar

        # Encontrar dato anterior más cercano
        prev_year = None
        for py in range(y - 1, year_min - 1, -1):
            if py in by_year:
                prev_year = py
                break

        # Encontrar dato posterior más cercano
        next_year = None
        for ny in range(y + 1, year_max + 1):
            if ny in by_year:
                next_year = ny
                break

        # ── Regla 1: CONFIRMED FILL ──
        if prev_year is not None and next_year is not None:
            gap_back = y - prev_year
            gap_fwd = next_year - y
            total_gap = next_year - prev_year - 1  # años faltantes entre ambos

            if total_gap <= MAX_GAP_CONFIRMED and _same_tasa(by_year[prev_year], by_year[next_year]):
                result.append(_make_imputed_row(by_year[prev_year], y, "confirmed_fill", prev_year))
                continue

        # ── Regla 2: AGGRESSIVE FILL ──
        if prev_year is not None and next_year is not None:
            total_gap = next_year - prev_year - 1
            if total_gap <= MAX_GAP_AGGRESSIVE:
                # Tasa diferente en next, but gap small → keep prev tasa
                result.append(_make_imputed_row(by_year[prev_year], y, "aggressive_fill", prev_year))
                continue

        # ── Regla 3: FORWARD FILL ──
        if prev_year is not None and (y - prev_year) <= MAX_GAP_FFILL:
            # No hay dato posterior para confirmar (o está muy lejos)
            if next_year is None or (next_year - prev_year - 1) > MAX_GAP_CONFIRMED:
                result.append(_make_imputed_row(by_year[prev_year], y, "ffill", prev_year))
                continue

        # ── Regla 4: BACKWARD FILL ──
        if next_year is not None and prev_year is None:
            gap = next_year - y
            if gap <= MAX_GAP_BFILL and y >= exists_since:
                result.append(_make_imputed_row(by_year[next_year], y, "bfill", next_year))
                continue

        # No se puede imputar — dejar hueco (no agregar fila)

    result.sort(key=lambda r: int(r["ejercicio"]))
    return result


# ══════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════

_PANEL_FIELDS = [
    "cve_ent", "cve_mun", "municipio", "estado", "ejercicio",
    "tipo_esquema", "tasa_urbano",
    "tasa_urbano_edificado", "tasa_rustico", "tasa_baldio",
    "n_rangos", "cuota_minima",
    "fuente_json", "extraction_method",
    "imputed", "imputed_from_year",
]


def impute_panel(
    input_csv: Path = Path("output/predial_panel.csv"),
    output_csv: Path = Path("output/predial_panel_balanced.csv"),
    changes_catalog: Path = Path("catalogs/changes_ageeml.csv"),
    year_min: int = EJERCICIO_INI,
    year_max: int = EJERCICIO_FIN,
):
    """
    Lee panel crudo, aplica imputación, genera panel balanceado.
    """
    print("═" * 60)
    print("  FASE 7: Imputación — Panel Balanceado")
    print("═" * 60)

    if not input_csv.exists():
        print(f"  [ERROR] No existe {input_csv}. Ejecuta consolidate_all() primero.")
        return

    # Cargar municipios nuevos
    new_munis = _load_new_municipalities(changes_catalog)
    if new_munis:
        print(f"  Catálogo de municipios nuevos: {len(new_munis)} entradas")
    else:
        print(f"  [WARN] Sin catálogo de municipios nuevos ({changes_catalog})")

    # Leer panel crudo
    with input_csv.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        raw_rows = list(reader)

    print(f"  Panel crudo: {len(raw_rows)} observaciones")

    # Agrupar por municipio
    by_muni: dict[tuple[str, str, str], list[dict]] = {}
    for r in raw_rows:
        key = (r["estado"], r["cve_ent"], r["cve_mun"])
        by_muni.setdefault(key, []).append(r)

    # Imputar
    all_rows: list[dict] = []
    stats = {"confirmed_fill": 0, "aggressive_fill": 0, "ffill": 0, "bfill": 0, "raw": 0}

    for (estado, cve_ent, cve_mun), obs in sorted(by_muni.items()):
        obs.sort(key=lambda r: int(r["ejercicio"]))

        # Determinar si es municipio nuevo
        creation_year = new_munis.get((cve_ent, cve_mun))

        imputed = _impute_municipality(obs, year_min, year_max, creation_year)
        for r in imputed:
            method = r.get("imputed", "false")
            if method == "false":
                stats["raw"] += 1
            else:
                stats[method] = stats.get(method, 0) + 1
        all_rows.extend(imputed)

    # Escribir
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_PANEL_FIELDS)
        writer.writeheader()
        for r in sorted(all_rows, key=lambda x: (x["estado"], x["cve_mun"], int(x["ejercicio"]))):
            row_out = {}
            for fn in _PANEL_FIELDS:
                row_out[fn] = r.get(fn, "")
            writer.writerow(row_out)

    # Resumen
    total = len(all_rows)
    total_imputed = total - stats["raw"]
    n_munis = len(by_muni)
    n_years = year_max - year_min + 1
    ideal = n_munis * n_years
    coverage = total / ideal * 100 if ideal > 0 else 0

    print(f"\n  → {output_csv}")
    print(f"  ── Resumen ──")
    print(f"  Municipios:        {n_munis}")
    print(f"  Rango:             {year_min}-{year_max} ({n_years} años)")
    print(f"  Panel ideal:       {ideal} obs")
    print(f"  Panel balanceado:  {total} obs ({coverage:.1f}% cobertura)")
    print(f"  Datos crudos:      {stats['raw']}")
    print(f"  Imputados:         {total_imputed}")
    print(f"    confirmed_fill:  {stats['confirmed_fill']}")
    print(f"    aggressive_fill: {stats['aggressive_fill']}")
    print(f"    ffill:           {stats['ffill']}")
    print(f"    bfill:           {stats['bfill']}")
    gaps = ideal - total
    if gaps > 0:
        print(f"  Huecos restantes:  {gaps} ({gaps/ideal*100:.1f}%)")
