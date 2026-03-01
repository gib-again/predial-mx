"""
Configuración específica de Guanajuato.

Fuente: Periódico Oficial del Gobierno del Estado de Guanajuato.
API REST pública con búsqueda paginada y descarga por idPeriodico.
Cada PDF del PO contiene múltiples leyes de ingresos municipales (2-5 por PDF).
Los PDFs son frecuentemente escaneos de imagen → requiere OCR.

CVE_ENT = 11 (INEGI).
46 municipios.
"""

from __future__ import annotations
from urllib.parse import quote

ESTADO_SLUG = "guanajuato"
PREFIJO = "GTO"
ESTADO_NOMBRE = "Guanajuato"
CVE_ENT = "11"
NEEDS_OCR = True  # PDFs del PO de Guanajuato son escaneos de imagen

# ── Años ──
YEAR_MIN = 2010
YEAR_MAX = 2025

# ── API del Periódico Oficial ──
BASE_SEARCH = "https://backperiodico.guanajuato.gob.mx/api/Edictos/BuscarEdictoPaginado"
BASE_DOWNLOAD = "https://backperiodico.guanajuato.gob.mx/api/Periodico/DescargarPeriodicoId"
PALABRA = quote("ley de ingreso")

# ── Headers HTTP ──
USER_AGENT = "Mozilla/5.0 (compatible; PredialMX/1.0)"
REQUESTS_KWARGS = {"timeout": 30, "verify": True}

# ── OCR ──
OCR_LANG = "spa"
OCR_DPI = 300
OCR_JOBS = 4

# ── 46 municipios de Guanajuato ──
# Fuente: INEGI catálogo AGEEML.
# Tupla: (cve_mun, nombre_oficial, slug)
MUNICIPIOS: list[tuple[str, str, str]] = [
    ("001", "Abasolo", "abasolo"),
    ("002", "Acámbaro", "acambaro"),
    ("003", "San Miguel de Allende", "san_miguel_de_allende"),
    ("004", "Apaseo el Alto", "apaseo_el_alto"),
    ("005", "Apaseo el Grande", "apaseo_el_grande"),
    ("006", "Atarjea", "atarjea"),
    ("007", "Celaya", "celaya"),
    ("008", "Manuel Doblado", "manuel_doblado"),
    ("009", "Comonfort", "comonfort"),
    ("010", "Coroneo", "coroneo"),
    ("011", "Cortazar", "cortazar"),
    ("012", "Cuerámaro", "cueramaro"),
    ("013", "Doctor Mora", "doctor_mora"),
    ("014", "Dolores Hidalgo Cuna de la Independencia Nacional", "dolores_hidalgo_cuna_de_la_independencia_nacional"),
    ("015", "Guanajuato", "guanajuato"),
    ("016", "Huanímaro", "huanimaro"),
    ("017", "Irapuato", "irapuato"),
    ("018", "Jaral del Progreso", "jaral_del_progreso"),
    ("019", "Jerécuaro", "jerecuaro"),
    ("020", "León", "leon"),
    ("021", "Moroleón", "moroleon"),
    ("022", "Ocampo", "ocampo"),
    ("023", "Pénjamo", "penjamo"),
    ("024", "Pueblo Nuevo", "pueblo_nuevo"),
    ("025", "Purísima del Rincón", "purisima_del_rincon"),
    ("026", "Romita", "romita"),
    ("027", "Salamanca", "salamanca"),
    ("028", "Salvatierra", "salvatierra"),
    ("029", "San Diego de la Unión", "san_diego_de_la_union"),
    ("030", "San Felipe", "san_felipe"),
    ("031", "San Francisco del Rincón", "san_francisco_del_rincon"),
    ("032", "San José Iturbide", "san_jose_iturbide"),
    ("033", "San Luis de la Paz", "san_luis_de_la_paz"),
    ("034", "Santa Catarina", "santa_catarina"),
    ("035", "Santa Cruz de Juventino Rosas", "santa_cruz_de_juventino_rosas"),
    ("036", "Santiago Maravatío", "santiago_maravatio"),
    ("037", "Silao de la Victoria", "silao_de_la_victoria"),
    ("038", "Tarandacuao", "tarandacuao"),
    ("039", "Tarimoro", "tarimoro"),
    ("040", "Tierra Blanca", "tierra_blanca"),
    ("041", "Uriangato", "uriangato"),
    ("042", "Valle de Santiago", "valle_de_santiago"),
    ("043", "Victoria", "victoria"),
    ("044", "Villagrán", "villagran"),
    ("045", "Xichú", "xichu"),
    ("046", "Yuriria", "yuriria"),
]

# ── Aliases: variantes encontradas en PDFs / API → slug canónico ──
# Incluye nombres cortos, errores frecuentes de OCR, y variantes históricas.
ALIASES: dict[str, str] = {
    # Dolores Hidalgo (nombre muy largo, muchas variantes)
    "dolores_hidalgo": "dolores_hidalgo_cuna_de_la_independencia_nacional",
    "dolores_hidalgo_c_i_n": "dolores_hidalgo_cuna_de_la_independencia_nacional",
    "dolores_hidalgo_cin": "dolores_hidalgo_cuna_de_la_independencia_nacional",
    "dolores_hidalgo_cuna_de_la_independencia": "dolores_hidalgo_cuna_de_la_independencia_nacional",
    # San Miguel de Allende
    "san_miguel_allende": "san_miguel_de_allende",
    "allende": "san_miguel_de_allende",
    # Silao
    "silao": "silao_de_la_victoria",
    "silao_de_la_vlctoria": "silao_de_la_victoria",  # OCR noise
    # Purísima del Rincón
    "purisima": "purisima_del_rincon",
    "purisima_de_bustos": "purisima_del_rincon",
    # San Francisco del Rincón
    "san_francisco": "san_francisco_del_rincon",
    "san_francisco_rincon": "san_francisco_del_rincon",
    # Santa Cruz de Juventino Rosas
    "juventino_rosas": "santa_cruz_de_juventino_rosas",
    "santa_cruz_juventino_rosas": "santa_cruz_de_juventino_rosas",
    # San Diego de la Unión
    "san_diego": "san_diego_de_la_union",
    "san_diego_union": "san_diego_de_la_union",
    # San José Iturbide
    "san_jose": "san_jose_iturbide",
    # San Luis de la Paz
    "san_luis": "san_luis_de_la_paz",
    "san_luis_paz": "san_luis_de_la_paz",
    # Valle de Santiago
    "valle_santiago": "valle_de_santiago",
    # Jaral del Progreso
    "jaral": "jaral_del_progreso",
    # Santiago Maravatío
    "santiago": "santiago_maravatio",
    "santiago_maravatlo": "santiago_maravatio",  # OCR noise
    # Pueblo Nuevo
    "pueblo": "pueblo_nuevo",
    # Manuel Doblado (a veces "Ciudad Manuel Doblado")
    "ciudad_manuel_doblado": "manuel_doblado",
    "cd_manuel_doblado": "manuel_doblado",
    # Doctor Mora
    "dr_mora": "doctor_mora",
    # León
    "leon_de_los_aldama": "leon",
    # Apaseo
    "apaseo_alto": "apaseo_el_alto",
    "apaseo_grande": "apaseo_el_grande",
}

# ── Dicts rápidos ──
SLUG_TO_CVE = {slug: (cve, name) for cve, name, slug in MUNICIPIOS}
NAME_TO_SLUG: dict[str, str] = {}
for _cve, _name, _slug in MUNICIPIOS:
    NAME_TO_SLUG[_name.upper()] = _slug
