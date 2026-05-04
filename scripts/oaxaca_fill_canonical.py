"""Fill agresivo Oaxaca: TODOS los munis con al menos un tipo válido + OdJ desde 2022.

Reglas:
- Lee panel_v2_raw.csv como fuente (datos crudos extraídos por el LLM).
- Para cada muni de Oaxaca con AL MENOS un año cuyo tipo_esquema esté en
  VALID_TIPOS (cualquier tipo que no sea otro_no_clasificado o blank),
  determina el tipo canónico por prioridad:
    tarifa_millar > cuota_fija_simple > progresivo >
    cuota_fija_escalonada > mixto > tasa_unica
  y propaga ese tipo a los 16 años (2010-2025).
- Si en la detección del canónico hay años con `otro_no_clasificado`, se
  ignoran (no impiden el fill).
- El año observado del tipo canónico queda como raw; los demás años se
  marcan como `canonical_fill` con `imputed_from_year` apuntando al año
  fuente.
- OdJ (cvegeo 20067): de 2022 en adelante se reclasifica como `progresivo`
  (bandas escalonadas cuentan como progresivo). Pre-2022 mantiene
  tarifa_millar como tipo dominante.
- Munis con SOLO otro_no_clasificado (sin ningún tipo válido) se mantienen
  como están en raw — no se pueden imputar.

El panel resultante se escribe a output/panel_v2.csv. Las filas de otros
estados (Coahuila, Jalisco, etc.) se preservan tal como están en el panel
imputado actual.
"""
import csv
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

PANEL_RAW = Path("output/panel_v2_raw.csv")
PANEL_OUT = Path("output/panel_v2.csv")
YEARS = list(range(2010, 2026))

# Prioridad para tipo canónico
PRIORITY = [
    "tarifa_millar",
    "cuota_fija_simple",
    "progresivo",
    "cuota_fija_escalonada",
    "mixto",
    "tasa_unica",
]
VALID_TIPOS = set(PRIORITY)
ODJ = "20067"


def find_canonical(rows: list[dict]) -> tuple[str, int, dict] | None:
    """Devuelve (tipo, año, fila_donor) o None.

    Filtra rows ignorando otro_no_clasificado y blank. Aplica prioridad y,
    dentro del mismo tipo, prefiere el año más reciente.
    """
    valid = [r for r in rows if r.get("tipo_esquema", "") in VALID_TIPOS]
    if not valid:
        return None
    for tipo in PRIORITY:
        same_type = [r for r in valid if r["tipo_esquema"] == tipo]
        if same_type:
            same_type.sort(key=lambda r: int(r["ejercicio"]), reverse=True)
            chosen = same_type[0]
            return tipo, int(chosen["ejercicio"]), chosen


def main() -> None:
    # Cargar raw
    with PANEL_RAW.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        raw_rows = list(reader)
    print(f"Panel raw: {len(raw_rows)} filas")

    # Cargar panel imputado actual (para preservar otros estados)
    with PANEL_OUT.open(encoding="utf-8-sig", newline="") as f:
        current_rows = list(csv.DictReader(f))
    print(f"Panel imputado actual: {len(current_rows)} filas")

    # Separar
    oax_raw = [r for r in raw_rows if r["estado"] == "Oaxaca"]
    other_imputed = [r for r in current_rows if r["estado"] != "Oaxaca"]
    print(f"  Oaxaca raw: {len(oax_raw)} | Otros estados imputados: {len(other_imputed)}")

    by_muni: dict[str, list[dict]] = defaultdict(list)
    for r in oax_raw:
        by_muni[r["cvegeo"]].append(r)

    new_oax: list[dict] = []
    stats = {
        "munis_filled": 0,
        "munis_only_unclass": 0,
        "rows_raw": 0,
        "rows_canonical_fill": 0,
        "rows_unclass_kept": 0,
        "odj_progresivo_imputed": 0,
        "odj_tarifa_imputed": 0,
        "by_canonical_type": defaultdict(int),
    }

    for cvegeo, obs in by_muni.items():
        municipio = obs[0]["municipio"]

        # ─── OdJ: caso especial ─────────────────────────────────────────
        if cvegeo == ODJ:
            existing = {r["ejercicio"]: r for r in obs if r.get("tipo_esquema") in VALID_TIPOS}
            for yr in YEARS:
                yr_str = str(yr)
                if yr_str in existing:
                    r = dict(existing[yr_str])
                    if yr >= 2022 and r["tipo_esquema"] != "progresivo":
                        r["tipo_esquema"] = "progresivo"
                        r["imputed_method"] = "user_reclass_progresivo"
                        r["imputed_from_year"] = ""
                        stats["odj_progresivo_imputed"] += 1
                    else:
                        # Limpiar campos imputed para raw
                        r["imputed_method"] = ""
                        r["imputed_from_year"] = ""
                        stats["rows_raw"] += 1
                    new_oax.append(r)
                else:
                    # Falta. Para 2022+ → progresivo; para <2022 → tarifa_millar
                    if yr >= 2022:
                        tipo = "progresivo"
                        method = "user_reclass_progresivo"
                        src = 2022
                        stats["odj_progresivo_imputed"] += 1
                    else:
                        tipo = "tarifa_millar"
                        # Buscar año más cercano con tarifa_millar
                        candidates = [int(y) for y, rr in existing.items()
                                      if rr["tipo_esquema"] == "tarifa_millar"
                                      and int(y) < 2022]
                        if candidates:
                            src = min(candidates, key=lambda y: abs(y - yr))
                            method = ("confirmed_fill" if (yr - 1) in candidates
                                      and (yr + 1) in candidates
                                      else ("bfill" if yr < min(candidates) else "ffill"))
                        else:
                            src = 2011
                            method = "bfill"
                        stats["odj_tarifa_imputed"] += 1
                    new_oax.append({
                        "cvegeo": cvegeo,
                        "ejercicio": yr_str,
                        "estado": "Oaxaca",
                        "municipio": municipio,
                        "tipo_esquema": tipo,
                        "numero_rangos": "",
                        "monto_max_rango": "",
                        "imputed_method": method,
                        "imputed_from_year": str(src),
                    })
            continue

        # ─── Resto de munis: detectar canónico y rellenar ─────────────
        canonical = find_canonical(obs)
        if canonical is None:
            # Solo otro_no_clasificado o blank → mantener tal cual
            new_oax.extend(obs)
            stats["munis_only_unclass"] += 1
            stats["rows_unclass_kept"] += len(obs)
            continue

        canonical_tipo, canonical_year, donor = canonical
        stats["munis_filled"] += 1
        stats["by_canonical_type"][canonical_tipo] += 1

        for yr in YEARS:
            yr_str = str(yr)
            if yr == canonical_year:
                # Preservar fila raw del año donor
                out = dict(donor)
                out["imputed_method"] = ""
                out["imputed_from_year"] = ""
                new_oax.append(out)
                stats["rows_raw"] += 1
            else:
                new_oax.append({
                    "cvegeo": cvegeo,
                    "ejercicio": yr_str,
                    "estado": "Oaxaca",
                    "municipio": municipio,
                    "tipo_esquema": canonical_tipo,
                    "numero_rangos": donor.get("numero_rangos", ""),
                    "monto_max_rango": donor.get("monto_max_rango", ""),
                    "imputed_method": "canonical_fill",
                    "imputed_from_year": str(canonical_year),
                })
                stats["rows_canonical_fill"] += 1

    final = other_imputed + new_oax
    final.sort(key=lambda r: (r["estado"], r["cvegeo"], int(r["ejercicio"])))

    # Escribir vía tmp + rename
    tmp = PANEL_OUT.with_suffix(".csv.tmp")
    with tmp.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(final)
    try:
        PANEL_OUT.unlink(missing_ok=True)
    except PermissionError:
        print(f"  [ERROR] {PANEL_OUT} bloqueado. Cierra Excel/visor.")
        return
    tmp.rename(PANEL_OUT)

    print(f"\nPanel actualizado: {len(final)} filas")
    print(f"\n── Resumen Oaxaca ──")
    print(f"  Munis con fill canónico:  {stats['munis_filled']}")
    print(f"  Munis solo no_clasificado: {stats['munis_only_unclass']}")
    print(f"  Filas raw preservadas:    {stats['rows_raw']}")
    print(f"  Filas canonical_fill:     {stats['rows_canonical_fill']}")
    print(f"  Filas no_clasificado:     {stats['rows_unclass_kept']}")
    print(f"  OdJ tarifa_millar imp:    {stats['odj_tarifa_imputed']}")
    print(f"  OdJ progresivo imp:       {stats['odj_progresivo_imputed']}")
    print(f"\n  Distribución tipo canónico (munis):")
    for t, n in sorted(stats["by_canonical_type"].items(), key=lambda x: -x[1]):
        print(f"    {t}: {n}")


if __name__ == "__main__":
    main()
