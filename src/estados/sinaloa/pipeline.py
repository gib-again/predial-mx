"""
Pipeline de Sinaloa — Genera JSON por municipio-año.

Tarifa uniforme en los 18 municipios (Art. 35 Ley de Hacienda Municipal).
Tablas actualizadas anualmente por factor INPC (Art. 36).
Tabla ancla: 2010 (P.O. 28-dic-2009).

Genera:
  data/sinaloa/json/{ejercicio}/SIN_{ejercicio}_{slug}.json
  data/sinaloa/meta/pipeline.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.estados.sinaloa import config
from src.estados.sinaloa.tarifa_base import (
    generar_tablas_por_ejercicio,
    RangoSinaloa,
)


# Default INPC CSV location
INPC_CSV = Path("catalogs/INPC_2008-2025.csv")


def _rangos_to_list(tabla: list[RangoSinaloa]) -> list[dict]:
    return [
        {
            "rango": r.numero,
            "lim_inf": r.lim_inf,
            "lim_sup": r.lim_sup,
            "cuota_construido": r.cuota_construido,
            "tasa_construido_millar": r.tasa_construido,
            "cuota_baldio": r.cuota_baldio,
            "tasa_baldio_millar": r.tasa_baldio,
        }
        for r in tabla
    ]


def _build_record(
    ejercicio: int,
    cve_mun: str,
    nombre: str,
    slug: str,
    tabla: list[RangoSinaloa],
    factor_inpc: float | None,
) -> dict:
    return {
        "cve_ent": config.CVE_ENT,
        "cve_mun": cve_mun,
        "estado": config.ESTADO_NOMBRE,
        "municipio": nombre,
        "slug": slug,
        "ejercicio": ejercicio,
        "fuente": "Ley de Hacienda Municipal del Estado de Sinaloa, Art. 35-36",
        "fuente_url": "https://www.congresosinaloa.gob.mx/leyes/",
        "metodo_extraccion": "hardcoded_tarifa_base_2010_actualizada_inpc",
        "predial": {
            "urbano": {
                "tipo": "progresiva_rangos_doble",
                "descripcion": "Columnas separadas para construidos y baldíos",
                "n_rangos": len(tabla),
                "rangos": _rangos_to_list(tabla),
                "cuota_fija_unidad": "pesos",
                "tasa_unidad": "al_millar",
                "formula": "cuota_fija + (valor_catastral - lim_inf) × (tasa_millar / 1000)",
                "factor_inpc_aplicado": round(factor_inpc, 6) if factor_inpc else None,
            },
            "rustico_productivo": {
                "tipo": "tasa_sobre_produccion",
                "tasas": config.TASAS_RUSTICO_PRODUCCION,
                "nota": "Base: valor de producción anual comercializada (Art. 35-II)",
            },
            "rustico_otros": {
                "tipo": "misma_tarifa_urbana",
                "nota": "Predios rurales no productivos: se aplica tarifa fracción I (Art. 35-III)",
            },
            "descuentos": {
                "pronto_pago_pct": 10,
                "pronto_pago_plazo": "primeros 2 meses del ejercicio",
                "casa_habitacion_pct": 50,
                "casa_habitacion_condicion": "habitada permanentemente, predio propio",
                "jubilados_pensionados": {
                    "cuota_fija": "3 UMA diarias (si VC ≤ 10,000 UMA)",
                    "descuento_pct": 80,
                    "descuento_condicion": "si VC > 10,000 UMA",
                },
                "empresas_hasta_pct": 40,
                "empresas_condicion": "aprobado por Ayuntamiento (Art. 44)",
            },
        },
        "notas": (
            f"Tabla actualizada por factor INPC Art. 36"
            + (f" (factor={factor_inpc:.6f})" if factor_inpc else " (tabla ancla)")
            + ". Tarifa idéntica en los 18 municipios de Sinaloa. "
            "Baldíos = sin construcción en zona urbana con agua/drenaje >5,000 hab. "
            "Equiparables a baldío: inhabitable por abandono/ruina, o <25% construido con "
            "valor edificación <50% del terreno."
        ),
    }


def run(
    data_dir: Path = Path("data/sinaloa"),
    inpc_csv: Path = INPC_CSV,
    year_min: int = config.YEAR_MIN,
    year_max: int = config.YEAR_MAX,
) -> Path:
    json_dir = data_dir / "json"
    meta_dir = data_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    print("═══ Sinaloa: Generación de JSONs ═══")

    # Build INPC index for factor computation
    import csv as csv_mod
    inpc_index: dict[tuple[int, int], float] = {}
    idx = 100.0
    with open(inpc_csv, "r") as f:
        reader = csv_mod.DictReader(f)
        for row in reader:
            parts = row["Fecha"].strip().split("/")
            d, m, y = int(parts[0]), int(parts[1]), int(parts[2])
            inf_pct = float(row["inflacion_mensual"].strip())
            idx = idx * (1 + inf_pct / 100)
            inpc_index[(y, m)] = idx

    def factor_for(year):
        if year <= 2010:
            return None
        return inpc_index[(year - 1, 11)] / inpc_index[(year - 2, 11)]

    # Generate tables
    tablas = generar_tablas_por_ejercicio(inpc_csv, year_min, year_max)

    meta_rows: list[dict] = []
    count = 0

    for ejercicio in range(year_min, year_max + 1):
        year_dir = json_dir / str(ejercicio)
        year_dir.mkdir(parents=True, exist_ok=True)

        tabla = tablas[ejercicio]
        factor = factor_for(ejercicio)

        for cve_mun, nombre, slug in config.MUNICIPIOS:
            record = _build_record(ejercicio, cve_mun, nombre, slug, tabla, factor)
            filename = f"{config.PREFIJO}_{ejercicio}_{slug}.json"
            filepath = year_dir / filename

            with filepath.open("w", encoding="utf-8") as f:
                json.dump(record, f, ensure_ascii=False, indent=2)

            count += 1
            meta_rows.append({
                "ejercicio": ejercicio,
                "cve_mun": cve_mun,
                "municipio": nombre,
                "slug": slug,
                "json_file": f"{ejercicio}/{filename}",
                "metodo": "hardcoded_inpc",
                "factor_inpc": round(factor, 6) if factor else "",
            })

    csv_path = meta_dir / "pipeline.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "ejercicio", "cve_mun", "municipio", "slug",
            "json_file", "metodo", "factor_inpc",
        ])
        writer.writeheader()
        writer.writerows(meta_rows)

    n_years = year_max - year_min + 1
    print(f"  JSONs: {count} ({len(config.MUNICIPIOS)} municipios × {n_years} años)")
    print(f"  Meta: {csv_path}")
    return csv_path
