"""
Pipeline de Chihuahua — Genera JSON por municipio-año.

Chihuahua usa tarifa estatal uniforme (Código Municipal, Arts. 148-149)
para los 67 municipios. No requiere descarga/OCR de PDFs.

Genera:
  data/chihuahua/json/{ejercicio}/CHIH_{ejercicio}_{slug}.json
  data/chihuahua/meta/pipeline.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.estados.chihuahua import config
from src.estados.chihuahua.tarifa_base import (
    TARIFA_URBANA,
    TASA_RUSTICO_MILLAR,
    TASA_MINERO_MILLAR,
    TASA_SUBURBANO_MILLAR,
    TASA_ADICIONAL_UACH,
    MINIMO_FACTOR,
    MINIMO_CAMBIO_UMA_YEAR,
)


def _build_record(
    ejercicio: int,
    cve_mun: str,
    nombre: str,
    slug: str,
) -> dict:
    """Construye el JSON normalizado para un municipio-año."""

    # Determinar unidad del mínimo
    if ejercicio >= MINIMO_CAMBIO_UMA_YEAR:
        minimo_unidad = "UMA_diaria"
    else:
        minimo_unidad = "salario_minimo_diario"

    # Tabla de rangos urbanos
    rangos = []
    for r in TARIFA_URBANA:
        rangos.append({
            "rango": r.numero,
            "lim_inf": r.lim_inf,
            "tasa_millar": r.tasa_millar,
            "cuota_fija": r.cuota_fija,
        })

    return {
        "cve_ent": config.CVE_ENT,
        "cve_mun": cve_mun,
        "estado": config.ESTADO_NOMBRE,
        "municipio": nombre,
        "slug": slug,
        "ejercicio": ejercicio,
        "fuente": "Código Municipal para el Estado de Chihuahua, Arts. 148-149",
        "fuente_url": "https://www.congresochihuahua2.gob.mx/biblioteca/codigos/archivosCodigos/70.pdf",
        "metodo_extraccion": "hardcoded_codigo_estatal",
        "predial": {
            "urbano": {
                "tipo": "progresiva_rangos",
                "n_rangos": len(rangos),
                "rangos": rangos,
                "formula": "(valor_catastral - lim_inf) * tasa + cuota_fija",
            },
            "rustico": {
                "tipo": "tasa_fija",
                "tasa_millar": TASA_RUSTICO_MILLAR,
            },
            "minero": {
                "tipo": "tasa_fija",
                "tasa_millar": TASA_MINERO_MILLAR,
            },
            "suburbano": {
                "tipo": "tasa_fija",
                "tasa_millar": TASA_SUBURBANO_MILLAR,
                "nota": "Declarado en leyes de ingresos municipales, no en Código",
            },
            "minimo": {
                "factor": MINIMO_FACTOR,
                "unidad": minimo_unidad,
            },
            "adicional_uach": {
                "tasa": TASA_ADICIONAL_UACH,
                "nota": "4% sobre predial, según ley de ingresos municipal",
            },
        },
        "notas": (
            "Tarifa estatal uniforme del Código Municipal. "
            "Tabla fracc. I vigente desde Decreto 107-07 (2008). "
            "Los valores catastrales (tablas de valores unitarios de suelo "
            "y construcción) sí varían por municipio y año."
        ),
    }


def run(
    data_dir: Path = Path("data/chihuahua"),
    year_min: int = config.YEAR_MIN,
    year_max: int = config.YEAR_MAX,
) -> Path:
    """
    Genera JSONs por municipio-año y meta CSV.
    """
    json_dir = data_dir / "json"
    meta_dir = data_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    print("═══ Chihuahua: Generación de JSONs ═══")

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
                "metodo": "hardcoded_codigo_estatal",
            })

    # Meta CSV
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
