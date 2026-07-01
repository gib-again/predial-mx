"""
Configuracion de Durango.

Grupo A: la tasa al millar del predial se fija en la **Ley de Ingresos
Municipal anual** de cada municipio (la Ley de Hacienda para los Municipios solo
da el marco: objeto, sujetos, base). 39 municipios.

Fuente (FASE 1, 2018-2025): el **Congreso del Estado** (congresodurango.gob.mx)
aloja cada Ley de Ingresos Municipal como **PDF digital individual** (sin OCR):
  https://congresodurango.gob.mx/Archivos/{LEG}/LEYES[-]INGRESOS/{anio}/{NOMBRE}{anio}.pdf
Las paginas de dictamenes (/dictamenes-de-leyes-de-ingresos-{anio}/) listan los
~39 PDFs municipales por anio. Existen para 2018-2026.

FASE 2 (pendiente): 2010-2017 no esta en el Congreso -> requeriria las gacetas
escaneadas del PO (periodicooficial.durango.gob.mx, S3) con OCR + segmentacion
de 2 niveles, o fuentes alternas.

CVE_ENT = 10 (INEGI).
"""

from __future__ import annotations

ESTADO_SLUG = "durango"
PREFIJO = "DGO"
ESTADO_NOMBRE = "Durango"
CVE_ENT = "10"
NEEDS_OCR = False  # Leyes de Ingresos del Congreso son PDF digital

# -- Anios (Congreso) --
# FASE 1: 2022-2025 via paginas de dictamenes.
# FASE 2: 2016-2021 via indice Apache de las carpetas de leyes de ingreso
#   (el naming de carpeta varia por legislatura, ver FOLDER_POR_ANIO).
# FASE 3 (pendiente): 2010-2015 solo estan en lxv/lxvi/decretos/ (DEC###.pdf
#   sin etiqueta) -> requiere identificar las leyes de ingresos entre los decretos.
YEAR_MIN = 2016
YEAR_MAX = 2025

# FASE 3 (2011-2015): barrido de decretos digitales de lxv/lxvi. 2010 (FY2010,
# publicada dic-2009 = legislatura LXIV) no esta en el sitio -> queda como hueco.
YEAR_MIN_FASE3 = 2011

# Carpeta (Apache index) por anio para 2016-2021. Para 2022-2025 se usa la
# pagina de dictamenes (ver download.py). Las rutas con espacios se url-encodean.
FOLDER_POR_ANIO: dict[int, str] = {
    2016: "lxvii/Leyes de Ingreso 2016",
    2017: "lxvii/Leyes de Ingresos 2017",
    2018: "lxvii/Leyes de Ingreso 2018",
    2019: "LXVIII/LeyesdeIngreso/2019",
    2020: "LXVIII/LeyesdeIngreso/2020",
    2021: "LXVIII/LeyesdeIngreso/2021",
}

# -- Congreso: pagina de listado por anio --
BASE_CONGRESO = "https://congresodurango.gob.mx"
DICTAMENES_URL = BASE_CONGRESO + "/dictamenes-de-leyes-de-ingresos-{anio}/"

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"

# -- 39 municipios (INEGI AGEEML) --
# Tupla: (cve_mun, nombre_oficial, slug)
MUNICIPIOS: list[tuple[str, str, str]] = [
    ("001", "Canatlan", "canatlan"),
    ("002", "Canelas", "canelas"),
    ("003", "Coneto de Comonfort", "coneto_de_comonfort"),
    ("004", "Cuencame", "cuencame"),
    ("005", "Durango", "durango"),
    ("006", "General Simon Bolivar", "general_simon_bolivar"),
    ("007", "Gomez Palacio", "gomez_palacio"),
    ("008", "Guadalupe Victoria", "guadalupe_victoria"),
    ("009", "Guanacevi", "guanacevi"),
    ("010", "Hidalgo", "hidalgo"),
    ("011", "Inde", "inde"),
    ("012", "Lerdo", "lerdo"),
    ("013", "Mapimi", "mapimi"),
    ("014", "Mezquital", "mezquital"),
    ("015", "Nazas", "nazas"),
    ("016", "Nombre de Dios", "nombre_de_dios"),
    ("017", "Ocampo", "ocampo"),
    ("018", "El Oro", "el_oro"),
    ("019", "Otaez", "otaez"),
    ("020", "Panuco de Coronado", "panuco_de_coronado"),
    ("021", "Penon Blanco", "penon_blanco"),
    ("022", "Poanas", "poanas"),
    ("023", "Pueblo Nuevo", "pueblo_nuevo"),
    ("024", "Rodeo", "rodeo"),
    ("025", "San Bernardo", "san_bernardo"),
    ("026", "San Dimas", "san_dimas"),
    ("027", "San Juan de Guadalupe", "san_juan_de_guadalupe"),
    ("028", "San Juan del Rio", "san_juan_del_rio"),
    ("029", "San Luis del Cordero", "san_luis_del_cordero"),
    ("030", "San Pedro del Gallo", "san_pedro_del_gallo"),
    ("031", "Santa Clara", "santa_clara"),
    ("032", "Santiago Papasquiaro", "santiago_papasquiaro"),
    ("033", "Suchil", "suchil"),
    ("034", "Tamazula", "tamazula"),
    ("035", "Tepehuanes", "tepehuanes"),
    ("036", "Tlahualilo", "tlahualilo"),
    ("037", "Topia", "topia"),
    ("038", "Vicente Guerrero", "vicente_guerrero"),
    ("039", "Nuevo Ideal", "nuevo_ideal"),
]

# Aliases: nombre de archivo del Congreso (normalizado sin acentos/espacios/anio)
# -> slug canonico. Solo para los casos que el normalizador no resuelve directo.
CONGRESO_ALIASES: dict[str, str] = {
    "municipiodurango": "durango",
    "simonbolivar": "general_simon_bolivar",
    "gralsimonbolivar": "general_simon_bolivar",
    "gomez": "gomez_palacio",
    "gomezpalacio": "gomez_palacio",
    "gpevictoria": "guadalupe_victoria",
    "pblanco": "penon_blanco",
    "penonblanco": "penon_blanco",
    "sandima": "san_dimas",
    "sanjuangpe": "san_juan_de_guadalupe",
    "sanjuandegpe": "san_juan_de_guadalupe",
    "sjuandegpe": "san_juan_de_guadalupe",
    "sanjuandeguadalupe": "san_juan_de_guadalupe",
    "eloro": "el_oro",
    "santiago": "santiago_papasquiaro",
    "santiagopap": "santiago_papasquiaro",
    "vguerrero": "vicente_guerrero",
    "spedrodelgallo": "san_pedro_del_gallo",
    "sluisdelcordero": "san_luis_del_cordero",
    "sanluisdecordero": "san_luis_del_cordero",
    "sanluiscordero": "san_luis_del_cordero",
    "penblanco": "penon_blanco",
}

SLUG_TO_CVE = {slug: (cve, name) for cve, name, slug in MUNICIPIOS}
