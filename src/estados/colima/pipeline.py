"""
Pipeline de Colima — Genera JSON por municipio-año.

Tarifa uniforme en los 10 municipios (Art. 13 Ley de Hacienda Municipal).
Cuota fija en SM diario (2010-2016) o UMA diaria (2017-2025).

Genera:
  data/colima/json/{ejercicio}/COL_{ejercicio}_{slug}.json
  data/colima/meta/pipeline.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.estados.colima import config
from src.estados.colima.tarifa_base import (
    TARIFA_URBANO_EDIFICADO,
    TARIFA_RUSTICO,
    TASA_BALDIO,
    CUOTA_EJIDAL_UMA,
)


def _rangos_to_list(tabla) -> list[dict]:
    return [
        {
            "rango": r.numero,
            "lim_inf": r.lim_inf,
            "lim_sup": r.lim_sup,
            "cuota_fija_unidad": r.cuota_fija_uma,
            "tasa_marginal": r.tasa_marginal,
        }
        for r in tabla
    ]


def _build_record(
    ejercicio: int,
    cve_mun: str,
    nombre: str,
    slug: str,
) -> dict:
    factor, unidad = config.factor_conversion(ejercicio)

    return {
        "cve_ent": config.CVE_ENT,
        "cve_mun": cve_mun,
        "estado": config.ESTADO_NOMBRE,
        "municipio": nombre,
        "slug": slug,
        "ejercicio": ejercicio,
        "fuente": f"Ley de Hacienda para el Municipio de {nombre}, Art. 13",
        "fuente_url": "https://congresocol.gob.mx/web/www/leyes/index.php",
        "metodo_extraccion": "hardcoded_ley_hacienda_municipal",
        "predial": {
            "urbano_edificado": {
                "tipo": "progresiva_rangos",
                "n_rangos": len(TARIFA_URBANO_EDIFICADO),
                "rangos": _rangos_to_list(TARIFA_URBANO_EDIFICADO),
                "cuota_fija_unidad": unidad,
                "cuota_fija_valor_pesos": factor,
                "formula": "cuota_fija × factor + (valor_catastral - lim_inf) × tasa_marginal",
            },
            "urbano_baldio": {
                "tipo": "tasa_fija",
                "tasa": TASA_BALDIO,
                "nota": "6 al millar sobre valor catastral",
            },
            "rustico": {
                "tipo": "progresiva_rangos",
                "n_rangos": len(TARIFA_RUSTICO),
                "rangos": _rangos_to_list(TARIFA_RUSTICO),
                "cuota_fija_unidad": unidad,
                "cuota_fija_valor_pesos": factor,
            },
            "ejidal": {
                "tipo": "cuota_fija",
                "cuota_uma": CUOTA_EJIDAL_UMA,
                "cuota_pesos": round(CUOTA_EJIDAL_UMA * factor, 2),
                "unidad": unidad,
            },
            "bonificacion_pronto_pago": {
                "enero_pct": 15,
                "febrero_pct": 13,
                "marzo_pct": 11,
            },
            "bonificacion_vulnerable": {
                "pct": 50,
                "aplica_a": "jubilados, pensionados, discapacitados, 60+ años",
                "condicion": "un solo predio propio, residencia en el mismo",
            },
        },
        "notas": (
            "Tarifa idéntica en los 10 municipios de Colima (2010-2025). "
            f"Cuota fija expresada en {unidad} ({factor} pesos). "
            "Reforma Decreto 133 (22-nov-2016): cambió SM → UMA. "
            "Los valores catastrales varían por municipio y año."
        ),
    }


def run(
    data_dir: Path = Path("data/colima"),
    year_min: int = config.YEAR_MIN,
    year_max: int = config.YEAR_MAX,
) -> Path:
    json_dir = data_dir / "json"
    meta_dir = data_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    print("═══ Colima: Generación de JSONs ═══")

    meta_rows: list[dict] = []
    count = 0

    for ejercicio in range(year_min, year_max + 1):
        year_dir = json_dir / str(ejercicio)
        year_dir.mkdir(parents=True, exist_ok=True)

        for cve_mun, nombre, slug in config.MUNICIPIOS:
            record = _build_record(ejercicio, cve_mun, nombre, slug)
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
                "metodo": "hardcoded_ley_hacienda_municipal",
            })

    csv_path = meta_dir / "pipeline.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "ejercicio", "cve_mun", "municipio", "slug", "json_file", "metodo",
        ])
        writer.writeheader()
        writer.writerows(meta_rows)

    n_years = year_max - year_min + 1
    print(f"  JSONs: {count} ({len(config.MUNICIPIOS)} municipios × {n_years} años)")
    print(f"  Meta: {csv_path}")
    return csv_path
