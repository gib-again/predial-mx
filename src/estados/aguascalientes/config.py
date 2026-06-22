"""
Configuracion de Aguascalientes.

Fuente: Periodico Oficial del Estado de Aguascalientes.
API JSON publica (ASP.NET WebMethod) con busqueda por nombre de documento.
Cada PDF del PO es una seccion individual = una ley de ingresos municipal.
Los PDFs son digitales con texto extraible (no requieren OCR).

CVE_ENT = 01 (INEGI).
11 municipios.
"""

from __future__ import annotations

ESTADO_SLUG = "aguascalientes"
PREFIJO = "AGS"
ESTADO_NOMBRE = "Aguascalientes"
CVE_ENT = "01"
NEEDS_OCR = False

# -- Anios --
YEAR_MIN = 2010
YEAR_MAX = 2025

# -- API del Periodico Oficial --
BASE_URL = "https://eservicios2.aguascalientes.gob.mx/periodicooficial"
SEARCH_URL = f"{BASE_URL}/Default.aspx/obtenerInformacion"
DETAIL_URL = f"{BASE_URL}/Default.aspx/obtenerDetalle"
PDF_URL = f"{BASE_URL}/Archivos"  # {PDF_URL}/{IdPeriodico}.pdf

# -- Headers HTTP --
USER_AGENT = "Mozilla/5.0 (compatible; PredialMX/1.0)"
REQUESTS_KWARGS: dict = {"timeout": 60, "verify": True}

# -- 11 municipios de Aguascalientes --
# Fuente: INEGI catalogo AGEEML.
# Tupla: (cve_mun, nombre_oficial, slug)
MUNICIPIOS: list[tuple[str, str, str]] = [
    ("001", "Aguascalientes", "aguascalientes"),
    ("002", "Asientos", "asientos"),
    ("003", "Calvillo", "calvillo"),
    ("004", "Cosio", "cosio"),
    ("005", "Jesus Maria", "jesus_maria"),
    ("006", "Pabellon de Arteaga", "pabellon_de_arteaga"),
    ("007", "Rincon de Romos", "rincon_de_romos"),
    ("008", "San Jose de Gracia", "san_jose_de_gracia"),
    ("009", "Tepezala", "tepezala"),
    ("010", "El Llano", "el_llano"),
    ("011", "San Francisco de los Romo", "san_francisco_de_los_romo"),
]

# Nombre usado en el Periodico Oficial (con acentos) -> slug canonico.
# La API del PO usa nombres con acentos; el catalogo INEGI los omite.
NOMBRE_PO: dict[str, str] = {
    "AGUASCALIENTES": "aguascalientes",
    "ASIENTOS": "asientos",
    "CALVILLO": "calvillo",
    "COSÍO": "cosio",
    "COSIO": "cosio",
    "EL LLANO": "el_llano",
    "JESÚS MARÍA": "jesus_maria",
    "JESUS MARIA": "jesus_maria",
    "JESÚS  MARÍA": "jesus_maria",
    "PABELLÓN DE ARTEAGA": "pabellon_de_arteaga",
    "PABELLON DE ARTEAGA": "pabellon_de_arteaga",
    "RINCÓN DE ROMOS": "rincon_de_romos",
    "RINCON DE ROMOS": "rincon_de_romos",
    "SAN FRANCISCO DE LOS ROMO": "san_francisco_de_los_romo",
    "SAN FRANCISCO DE LOS ROMOS": "san_francisco_de_los_romo",
    "SAN JOSÉ DE GRACIA": "san_jose_de_gracia",
    "SAN JOSE DE GRACIA": "san_jose_de_gracia",
    "TEPEZALÁ": "tepezala",
    "TEPEZALA": "tepezala",
}

# Aliases adicionales para MuniMatcher (OCR noise, variantes historicas)
ALIASES: dict[str, str] = {
    "cosio": "cosio",
    "jesus_maria": "jesus_maria",
    "pabellon_arteaga": "pabellon_de_arteaga",
    "pabellon": "pabellon_de_arteaga",
    "rincon_romos": "rincon_de_romos",
    "rincon": "rincon_de_romos",
    "san_francisco_los_romo": "san_francisco_de_los_romo",
    "san_francisco_romo": "san_francisco_de_los_romo",
    "san_francisco_de_los_romos": "san_francisco_de_los_romo",
    "san_jose_gracia": "san_jose_de_gracia",
    "san_jose": "san_jose_de_gracia",
    "llano": "el_llano",
}

# -- Dicts rapidos --
SLUG_TO_CVE = {slug: (cve, name) for cve, name, slug in MUNICIPIOS}
NAME_TO_SLUG: dict[str, str] = {}
for _cve, _name, _slug in MUNICIPIOS:
    NAME_TO_SLUG[_name.upper()] = _slug

# Busqueda en la API: nombre del municipio tal como aparece en el PO
# (con articulo "de", acentos para la busqueda).
SEARCH_NAMES: list[tuple[str, str]] = [
    ("Aguascalientes", "aguascalientes"),
    ("Asientos", "asientos"),
    ("Calvillo", "calvillo"),
    ("Cosío", "cosio"),
    ("El Llano", "el_llano"),
    ("Jesús María", "jesus_maria"),
    ("Pabellón de Arteaga", "pabellon_de_arteaga"),
    ("Rincón de Romos", "rincon_de_romos"),
    ("San Francisco de los Romo", "san_francisco_de_los_romo"),
    ("San José de Gracia", "san_jose_de_gracia"),
    ("Tepezalá", "tepezala"),
]
