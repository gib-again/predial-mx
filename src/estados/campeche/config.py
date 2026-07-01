"""
Configuracion de Campeche.

Caso Grupo B diferenciado (como BCS, pero mas limpio): las tasas de predial
NO estan en una ley anual sino en la **Ley de Hacienda de los Municipios del
Estado de Campeche** (un solo documento estatal). El Articulo 26 trae UNA tabla
de TARIFAS con tasas diferenciadas por municipio y uso de suelo, en porcentaje:
  URBANOS: Habitacional, Comercial/Servicios, Industrial, Baldios, Preservacion Ecologica
  RUSTICOS: Terrenos Explotados, Terrenos Inexplotados
El minimo (5 salarios minimos), descuentos y exenciones viven en la Ley de
Ingresos anual por municipio (secundario).

Estrategia (hardcoded versionado): se extrae el bloque de cada municipio de la
tabla Art. 26 de la VERSION vigente (LLM v3 -> tasas_diferenciadas, unidad
porcentaje) y se expande a los anios de vigencia.

Versiones digitales (sin OCR), en data/campeche/leyes_hacienda/:
  - baseline_2010: ordenjuridico/Justia (consolidada ~2005), vigente 2010-2013.
  - actual_2022:   consejeria LEXIUS (reforma 28-abr-2022), post-reformas.
  (interm_2019 de transparencia.calkini.gob.mx se conserva como referencia.)

Tasas mayormente ESTABLES 2010-2025. Cambio confirmado (diff baseline vs actual
por bloque de municipio; las notas inline del Art.26 nombran el municipio):
  - Carmen: tarifa reformada Decreto 30 (29-dic-2015) -> transicion FY2016
    (hab 0.20->0.17, com/ind 0.30->0.29).
  - Los 10 munis historicos restantes (incluido Campeche): ESTABLES.
  - Seybaplaya (04012) y Dzitbalche (04013): municipios nuevos (~2019-2021,
    anadidos a la ley por Decreto 165/2021) -> entran ~2021, marcado revisar.

CVE_ENT = 04 (INEGI). 13 municipios.
"""

from __future__ import annotations

ESTADO_SLUG = "campeche"
PREFIJO = "CAMP"
ESTADO_NOMBRE = "Campeche"
CVE_ENT = "04"
NEEDS_OCR = False  # Ley de Hacienda es PDF digital

# -- Anios --
YEAR_MIN = 2010
YEAR_MAX = 2025

# Anio placeholder de entrada de los municipios nuevos (por confirmar en HITL).
NUEVO_MUNI_PLACEHOLDER = 2021

# -- 13 municipios (INEGI AGEEML) --
# Tupla: (cve_mun, nombre_oficial, slug, nombre_en_tabla_Art26)
MUNICIPIOS: list[tuple[str, str, str, str]] = [
    ("001", "Calkini", "calkini", "CALKINI"),
    ("002", "Campeche", "campeche", "CAMPECHE"),
    ("003", "Carmen", "carmen", "CARMEN"),
    ("004", "Champoton", "champoton", "CHAMPOTON"),
    ("005", "Hecelchakan", "hecelchakan", "HECELCHAKAN"),
    ("006", "Hopelchen", "hopelchen", "HOPELCHEN"),
    ("007", "Palizada", "palizada", "PALIZADA"),
    ("008", "Tenabo", "tenabo", "TENABO"),
    ("009", "Escarcega", "escarcega", "ESCARCEGA"),
    ("010", "Calakmul", "calakmul", "CALAKMUL"),
    ("011", "Candelaria", "candelaria", "CANDELARIA"),
    ("012", "Seybaplaya", "seybaplaya", "SEYBAPLAYA"),
    ("013", "Dzitbalche", "dzitbalche", "DZITBALCHE"),
]

# -- Versiones disponibles -> archivo PDF --
VERSIONES_DOC: dict[str, str] = {
    "baseline_2010": "leyes_hacienda/LHaciendaMunicipios_baseline_2010.pdf",
    "actual_2022":   "leyes_hacienda/LHaciendaMunicipios_actual_2022.pdf",
}

# -- Mapeo version->anios por municipio --
# (version_id, anio_desde, anio_hasta, revisar)
_ESTABLE = [("actual_2022", 2010, 2025, False)]  # rates idénticos en baseline/actual
VERSIONES: dict[str, list[tuple[str, int, int, bool]]] = {
    "calkini":     _ESTABLE,
    "campeche":    _ESTABLE,   # estable (diff confirma sin cambio)
    "champoton":   _ESTABLE,
    "hecelchakan": _ESTABLE,
    "hopelchen":   _ESTABLE,
    "palizada":    _ESTABLE,
    "tenabo":      _ESTABLE,
    "escarcega":   _ESTABLE,
    "calakmul":    _ESTABLE,
    "candelaria":  _ESTABLE,
    # Carmen: tarifa reformada Decreto 30 (dic-2015) -> FY2016
    "carmen":      [("baseline_2010", 2010, 2015, False),
                    ("actual_2022",   2016, 2025, False)],
    # Municipios nuevos: entran ~2021 (placeholder), por confirmar en HITL.
    "seybaplaya":  [("actual_2022", NUEVO_MUNI_PLACEHOLDER, 2025, True)],
    "dzitbalche":  [("actual_2022", NUEVO_MUNI_PLACEHOLDER, 2025, True)],
}

# -- Dicts rapidos --
SLUG_TO_CVE = {slug: (cve, name) for cve, name, slug, _t in MUNICIPIOS}
TABLA_NOMBRE = {slug: tabla for _cve, _name, slug, tabla in MUNICIPIOS}


def version_para_anio(slug: str, anio: int) -> tuple[str, bool] | None:
    """Devuelve (version_id, revisar) vigente para (municipio, anio)."""
    for version_id, desde, hasta, revisar in VERSIONES.get(slug, []):
        if desde <= anio <= hasta:
            return version_id, revisar
    return None
