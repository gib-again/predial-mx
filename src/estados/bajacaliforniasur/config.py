"""
Configuracion de Baja California Sur.

Caso atipico: las tasas de predial NO estan en una ley anual (la "Ley de
Ingresos" / "Presupuesto de Ingresos" municipal solo trae montos estimados de
recaudacion, sin tasas). Viven en la **Ley de Hacienda Municipal**, una por
municipio, con tasas diferenciadas "al millar" por tipo de predio + minimo en
UMA (o salario minimo antes de 2016).

Estrategia (estilo Grupo B versionado, no LLM por-anio):
  - Fuente = Leyes de Hacienda municipales en formato Word digital (sin OCR):
      * Vigente (cbcs.gob.mx):        data/.../leyes_hacienda/actual/
      * ~2009 / baseline 2010 (ordenjuridico.gob.mx): .../baseline_2009/
  - Se extrae la seccion predial de cada VERSION (LLM v3 -> tasas_diferenciadas)
    y se expande a los anios en que esa version estuvo vigente.
  - Solo cambian las tasas cuando se reforma el articulo de predial de la Ley
    de Hacienda; entre reformas, la tasa es estable.

CVE_ENT = 03 (INEGI). 5 municipios.

Estado del fechado de transiciones (jun-2026; ver meta/transiciones_predial.csv):
  - Comondu, La Paz: predial ESTABLE 2010-2025 (una sola version).
  - Loreto: cambio en FY2022 (Decreto 2792 publicado 12-nov-2021). FIRME.
  - Los Cabos, Mulege: cambiaron pero el anio exacto esta PENDIENTE de
    segmentacion manual (HITL). Se usa un anio placeholder marcado `revisar`.
"""

from __future__ import annotations

ESTADO_SLUG = "bajacaliforniasur"
PREFIJO = "BCS"
ESTADO_NOMBRE = "Baja California Sur"
CVE_ENT = "03"
NEEDS_OCR = False  # Leyes de Hacienda son Word digital

# -- Anios --
YEAR_MIN = 2010
YEAR_MAX = 2025

# -- 5 municipios de BCS (INEGI AGEEML) --
# Tupla: (cve_mun, nombre_oficial, slug)
MUNICIPIOS: list[tuple[str, str, str]] = [
    ("001", "Comondu", "comondu"),
    ("002", "Mulege", "mulege"),
    ("003", "La Paz", "la_paz"),
    ("008", "Los Cabos", "los_cabos"),
    ("009", "Loreto", "loreto"),
]

# Anio placeholder para transiciones aun no fechadas (Los Cabos, Mulege).
# Interpolacion de numeros de decreto (1404=2002, 2584=2018, ~74 decretos/anio)
# ubica las reformas candidatas ~2013-2015; se usa 2014 como placeholder.
TRANSICION_PLACEHOLDER = 2014

# -- Versiones de la Ley de Hacienda por municipio --
# Cada entrada: lista de (version_id, anio_desde, anio_hasta, revisar)
#   version_id: nombre del subdir/archivo en leyes_hacienda/
#   revisar: True si el corte de anio esta pendiente de confirmacion (HITL)
# Comondu/La Paz: estables -> una sola version cubre todo el periodo.
# Loreto: corte firme 2022. Los Cabos/Mulege: corte placeholder (revisar).
VERSIONES: dict[str, list[tuple[str, int, int, bool]]] = {
    "comondu":   [("actual", 2010, 2025, False)],
    "la_paz":    [("actual", 2010, 2025, False)],
    "loreto":    [("baseline_2009", 2010, 2021, False),
                  ("actual",        2022, 2025, False)],
    "los_cabos": [("baseline_2009", 2010, TRANSICION_PLACEHOLDER - 1, True),
                  ("actual",        TRANSICION_PLACEHOLDER, 2025, True)],
    "mulege":    [("baseline_2009", 2010, TRANSICION_PLACEHOLDER - 1, True),
                  ("actual",        TRANSICION_PLACEHOLDER, 2025, True)],
}

# -- Dicts rapidos --
SLUG_TO_CVE = {slug: (cve, name) for cve, name, slug in MUNICIPIOS}
SLUGS = [slug for _cve, _name, slug in MUNICIPIOS]


def version_para_anio(slug: str, anio: int) -> tuple[str, bool] | None:
    """Devuelve (version_id, revisar) vigente para (municipio, anio)."""
    for version_id, desde, hasta, revisar in VERSIONES.get(slug, []):
        if desde <= anio <= hasta:
            return version_id, revisar
    return None
