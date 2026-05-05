"""
Genera output/predial_panel_pragmatic.csv: variante "pragmática" del panel
balanceado con reglas específicas para SLP.

Reglas SLP (cve_ent=24):
  1. Sólo dos municipios pueden tener tipo_esquema='progresivo':
     - 028 San Luis Potosí (capital): progresivo desde 2022 en adelante.
       Año 2021 explícitamente marcado como tarifa_millar (no progresivo).
     - 059 Villa de Pozos: progresivo (creado en 2024, sólo 2024+).
  2. Los demás 57 municipios siempre tipo_esquema='tarifa_millar'.
  3. Forzar balance: 58 munis × 16 años (2010-2025) + Villa de Pozos × 2 (2024-2025) = 930 filas.
     Para huecos sin datos, ffill desde año previo con datos; bfill si no hay
     previo. Marcar como imputed='pragmatic_fill'.

Otros estados se copian sin cambios desde el panel balanceado.

Uso:
    python -m scripts.build_panel_pragmatic
"""

from __future__ import annotations

import csv
from pathlib import Path

# Constantes SLP
SLP_ESTADO = "sanluispotosi"
SLP_CVE_ENT = "24"
SLP_CAPITAL_CVE_MUN = "028"
VILLA_DE_POZOS_CVE_MUN = "059"
SLP_CAPITAL_PROGRESIVO_DESDE = 2022  # incluido
VILLA_DE_POZOS_CREADO_EN = 2024     # primer año con ley

YEAR_MIN = 2010
YEAR_MAX = 2025

PANEL_FIELDS = [
    "cve_ent", "cve_mun", "municipio", "estado", "ejercicio",
    "tipo_esquema", "tasa_urbano", "tasa_urbano_edificado",
    "tasa_rustico", "tasa_baldio", "n_rangos", "cuota_minima",
    "fuente_json", "extraction_method", "imputed", "imputed_from_year",
]


def _esquema_pragmatico(cve_mun: str, ejercicio: int) -> str:
    """Determina el tipo_esquema canónico bajo las reglas pragmáticas SLP."""
    if cve_mun == VILLA_DE_POZOS_CVE_MUN:
        return "progresivo"
    if cve_mun == SLP_CAPITAL_CVE_MUN and ejercicio >= SLP_CAPITAL_PROGRESIVO_DESDE:
        return "progresivo"
    return "tarifa_millar"


def _muni_existe_en_anio(cve_mun: str, ejercicio: int) -> bool:
    """Filtro de existencia: Villa de Pozos sólo desde 2024."""
    if cve_mun == VILLA_DE_POZOS_CVE_MUN:
        return ejercicio >= VILLA_DE_POZOS_CREADO_EN
    return True


def _build_slp_pragmatic(
    slp_rows: list[dict],
) -> list[dict]:
    """
    Construye el grid completo SLP forzando esquema y rellenando huecos.

    Estrategia:
      - Indexar (cve_mun, ejercicio) → row del panel balanceado.
      - Para cada (muni, año) en el grid ideal:
        - Si hay row → forzar tipo_esquema según reglas, marcar
          'pragmatic_force' si el original difería.
        - Si no hay row → ffill (preferido) / bfill, marcar 'pragmatic_fill'.
    """
    # 1. Index existing
    by_key: dict[tuple[str, int], dict] = {}
    munis_meta: dict[str, dict] = {}  # cve_mun → {cve_ent, municipio, estado}
    for r in slp_rows:
        cve_mun = r["cve_mun"]
        try:
            ej = int(r["ejercicio"])
        except (ValueError, TypeError):
            continue
        by_key[(cve_mun, ej)] = r
        munis_meta.setdefault(cve_mun, {
            "cve_ent": r["cve_ent"],
            "municipio": r["municipio"],
            "estado": r["estado"],
        })

    if not munis_meta:
        return []

    # 2. Grid ideal
    out: list[dict] = []
    for cve_mun in sorted(munis_meta.keys()):
        meta = munis_meta[cve_mun]
        for ejercicio in range(YEAR_MIN, YEAR_MAX + 1):
            if not _muni_existe_en_anio(cve_mun, ejercicio):
                continue

            esquema_target = _esquema_pragmatico(cve_mun, ejercicio)
            row_existing = by_key.get((cve_mun, ejercicio))

            if row_existing is not None:
                # Caso A: hay datos. Copiamos y forzamos esquema si difiere.
                row = dict(row_existing)
                original_esquema = row.get("tipo_esquema", "")
                if original_esquema != esquema_target:
                    # Forzamos. Si pasamos de progresivo→tarifa_millar y no
                    # hay tasa_urbano, sería inconsistente; pero confiamos
                    # en que consolidate ya extrajo tasa_urbano representativa.
                    row["tipo_esquema"] = esquema_target
                    row["imputed"] = "pragmatic_force"
                    # Si forzamos a tarifa_millar y había n_rangos, blanquear
                    if esquema_target == "tarifa_millar":
                        row["n_rangos"] = ""
                # else: imputed se mantiene como venía (false / ffill / etc.)
                out.append(row)
            else:
                # Caso B: hueco. ffill primero, bfill como respaldo.
                source_year = None
                source_row = None

                # ffill: año más reciente previo con datos
                for y in range(ejercicio - 1, YEAR_MIN - 1, -1):
                    if not _muni_existe_en_anio(cve_mun, y):
                        continue
                    if (cve_mun, y) in by_key:
                        source_year = y
                        source_row = by_key[(cve_mun, y)]
                        break

                # bfill si no hay previo
                if source_row is None:
                    for y in range(ejercicio + 1, YEAR_MAX + 1):
                        if not _muni_existe_en_anio(cve_mun, y):
                            continue
                        if (cve_mun, y) in by_key:
                            source_year = y
                            source_row = by_key[(cve_mun, y)]
                            break

                if source_row is None:
                    # Sin datos en absoluto — no podemos rellenar. Saltar.
                    continue

                row = dict(source_row)
                row["ejercicio"] = str(ejercicio)
                row["tipo_esquema"] = esquema_target
                if esquema_target == "tarifa_millar":
                    row["n_rangos"] = ""
                row["imputed"] = "pragmatic_fill"
                row["imputed_from_year"] = str(source_year)
                row["fuente_json"] = ""  # ya no es la fuente directa
                row["extraction_method"] = "pragmatic_fill"
                out.append(row)

    return out


def build_pragmatic_panel(
    input_csv: Path = Path("output/predial_panel_balanced.csv"),
    output_csv: Path = Path("output/predial_panel_pragmatic.csv"),
) -> Path:
    """Construye el panel pragmático y lo escribe a disco."""
    if not input_csv.exists():
        raise FileNotFoundError(f"No existe {input_csv}. Ejecuta consolidate + impute primero.")

    # 1. Leer panel completo
    all_rows: list[dict] = []
    with input_csv.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            all_rows.append(r)

    print(f"Panel balanceado: {len(all_rows)} filas")

    # 2. Separar SLP vs resto
    slp_rows = [r for r in all_rows if r.get("estado") == SLP_ESTADO]
    other_rows = [r for r in all_rows if r.get("estado") != SLP_ESTADO]
    print(f"  SLP: {len(slp_rows)} filas")
    print(f"  Resto: {len(other_rows)} filas")

    # 3. Construir SLP pragmático
    slp_pragmatic = _build_slp_pragmatic(slp_rows)
    print(f"\nSLP pragmático: {len(slp_pragmatic)} filas")

    # 4. Estadísticas SLP
    from collections import Counter
    by_imputed = Counter(r.get("imputed", "?") for r in slp_pragmatic)
    by_esquema = Counter(r.get("tipo_esquema", "?") for r in slp_pragmatic)
    print("  Por origen:")
    for k, v in sorted(by_imputed.items()):
        print(f"    {k}: {v}")
    print("  Por esquema:")
    for k, v in sorted(by_esquema.items()):
        print(f"    {k}: {v}")

    # 5. Concatenar y escribir
    panel_out = other_rows + slp_pragmatic
    panel_out.sort(key=lambda r: (r.get("estado", ""), r.get("cve_mun", ""),
                                  int(r.get("ejercicio", 0) or 0)))

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=PANEL_FIELDS)
        writer.writeheader()
        for r in panel_out:
            writer.writerow({k: r.get(k, "") for k in PANEL_FIELDS})

    print(f"\n→ {output_csv}")
    print(f"  Total filas: {len(panel_out)}")
    return output_csv


if __name__ == "__main__":
    build_pragmatic_panel()
