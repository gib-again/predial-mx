"""
Pipeline del Estado de México — Genera JSON por municipio-año.

Tarifa uniforme en los 125 municipios (Código Financiero Art. 109).
Cuota fija en pesos nominales (no requiere conversión UMA/SM).

Genera:
  data/edomex/json/{ejercicio}/MEX_{ejercicio}_{slug}.json
  data/edomex/meta/pipeline.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.estados.edomex import config
from src.estados.edomex.tarifa_base import (
    tabla_para_ejercicio,
    TASA_ADICIONAL_BALDIO,
)


def _rangos_to_list(tabla) -> list[dict]:
    return [
        {
            "rango": r.numero,
            "lim_inf": r.lim_inf,
            "lim_sup": r.lim_sup,
            "cuota_fija_pesos": r.cuota_fija,
            "factor": r.factor,
        }
        for r in tabla
    ]


def _build_record(
    ejercicio: int,
    cve_mun: str,
    nombre: str,
    slug: str,
) -> dict:
    tabla, etiqueta = tabla_para_ejercicio(ejercicio)
    aplica_baldio_15 = ejercicio >= config.YEAR_BALDIO_15PCT

    record = {
        "cve_ent": config.CVE_ENT,
        "cve_mun": cve_mun,
        "estado": config.ESTADO_NOMBRE,
        "municipio": nombre,
        "slug": slug,
        "ejercicio": ejercicio,
        "fuente": "Código Financiero del Estado de México y Municipios, Art. 109",
        "fuente_reforma": etiqueta,
        "fuente_url": "https://legislacion.edomex.gob.mx/",
        "metodo_extraccion": "hardcoded_codigo_financiero",
        "predial": {
            "tipo": "progresiva_rangos",
            "n_rangos": len(tabla),
            "rangos": _rangos_to_list(tabla),
            "cuota_fija_unidad": "pesos",
            "formula": "cuota_fija + (valor_catastral - lim_inf) × factor",
            "baldio_urbano_mayor_200m2": {
                "aplica": aplica_baldio_15,
                "tasa_adicional": TASA_ADICIONAL_BALDIO if aplica_baldio_15 else None,
                "nota": (
                    "15% adicional sobre monto total (G.G. 28-nov-2016)"
                    if aplica_baldio_15
                    else "No aplica para este ejercicio"
                ),
            },
        },
        "notas": (
            f"Tarifa Art. 109 ({etiqueta}), idéntica en los 125 municipios. "
            "Cuota fija en pesos nominales. "
            + ("Baldíos urbanos >200 m²: +15% sobre monto total. " if aplica_baldio_15 else "")
            + "Tabla 2025 (ejercicio 2026) actualiza todos los rangos (fuera del periodo). "
            "Los valores catastrales se determinan con tablas de valores unitarios "
            "de suelo y construcciones publicadas por cada municipio."
        ),
    }
    return record


def run(
    data_dir: Path = Path("data/edomex"),
    year_min: int = config.YEAR_MIN,
    year_max: int = config.YEAR_MAX,
) -> Path:
    json_dir = data_dir / "json"
    meta_dir = data_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    print("═══ Estado de México: Generación de JSONs ═══")

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
                "metodo": "hardcoded_codigo_financiero",
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
