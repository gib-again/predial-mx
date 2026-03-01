"""
Pipeline de Tabasco — Genera JSON por municipio-año.

Tarifa uniforme en los 17 municipios (Art. 94 Ley de Hacienda Municipal).
Tabla sin cambios 2010-2025. Cuota fija en pesos nominales.
Diferencia por año: solo el impuesto mínimo (SM→UMA en 2017).

Genera:
  data/tabasco/json/{ejercicio}/TAB_{ejercicio}_{slug}.json
  data/tabasco/meta/pipeline.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.estados.tabasco import config
from src.estados.tabasco.tarifa_base import TARIFA_ART94


def _rangos_to_list(tabla) -> list[dict]:
    return [
        {
            "rango": r.numero,
            "lim_inf": r.lim_inf,
            "lim_sup": r.lim_sup,
            "cuota_fija_pesos": r.cuota_fija,
            "tasa_pct": r.tasa_pct,
        }
        for r in tabla
    ]


def _build_record(
    ejercicio: int,
    cve_mun: str,
    nombre: str,
    slug: str,
) -> dict:
    min_urbano, unidad_u = config.minimo_anual(ejercicio, "urbano")
    min_rustico, unidad_r = config.minimo_anual(ejercicio, "rustico")

    return {
        "cve_ent": config.CVE_ENT,
        "cve_mun": cve_mun,
        "estado": config.ESTADO_NOMBRE,
        "municipio": nombre,
        "slug": slug,
        "ejercicio": ejercicio,
        "fuente": "Ley de Hacienda Municipal del Estado de Tabasco, Art. 94",
        "fuente_reforma": "P.O. 30-dic-1995 (tabla sin cambios 2010-2025)",
        "fuente_url": "https://congresotabasco.gob.mx/leyes/",
        "metodo_extraccion": "hardcoded_ley_hacienda_municipal",
        "predial": {
            "tipo": "progresiva_rangos",
            "n_rangos": len(TARIFA_ART94),
            "rangos": _rangos_to_list(TARIFA_ART94),
            "cuota_fija_unidad": "pesos",
            "formula": "cuota_fija + (valor_fiscal - lim_inf) × (tasa_pct / 100)",
            "base_gravable": {
                "tipo": "valor_fiscal",
                "calculo": "valor_catastral × porcentaje_fiscal_zona",
                "porcentaje_fiscal_minimo": 20,
                "nota": "Porcentaje fiscal por zona determinado por Cabildo, aprobado por Congreso (Art. 90)",
            },
            "minimo_anual": {
                "urbano_pesos": min_urbano,
                "urbano_formula": f"4 × {unidad_u}",
                "rustico_pesos": min_rustico,
                "rustico_formula": f"3 × {unidad_r}",
                "unidad": unidad_u,
            },
            "sobretasa_baldio": {
                "rango_pct": "0-30%",
                "determinacion": "propuesta por Cabildo, aprobada por Congreso (Art. 97)",
                "aplica_a": "predios urbanos no edificados o con construcción ruinosa",
            },
        },
        "notas": (
            "Tarifa Art. 94 idéntica en 17 municipios, sin cambios 2010-2025. "
            "Base gravable = valor fiscal (valor catastral × % fiscal de zona, mín 20%). "
            f"Mínimo anual: urbano ${min_urbano:.2f} (4×{unidad_u}), "
            f"rústico ${min_rustico:.2f} (3×{unidad_u}). "
            + ("Reforma P.O. 7808 (05-jul-2017): mínimo cambia de SM a UMA. " if ejercicio >= 2017 else "")
            + "El % fiscal de zona y la sobretasa de baldíos varían por municipio."
        ),
    }


def run(
    data_dir: Path = Path("data/tabasco"),
    year_min: int = config.YEAR_MIN,
    year_max: int = config.YEAR_MAX,
) -> Path:
    json_dir = data_dir / "json"
    meta_dir = data_dir / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)

    print("═══ Tabasco: Generación de JSONs ═══")

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
