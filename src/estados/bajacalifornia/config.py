"""
Configuracion de Baja California.

Fuente: Periodico Oficial del Estado de Baja California.
API JSON publica (Tomcat/JSP) con busqueda full-text del indice del PO:
  - Sesion:   GET  /oficial/inicioConsulta.jsp           (set JSESSIONID)
  - Busqueda: GET  /oficial/IndiceConsulta/getIndicesBusquedaConsulta
              params: options, indicePublico, fechaInicio, fechaFin,
                      palabra1, palabra2  -> {Total, Data:[{indice, seccion,
                      pagina, fechaRegistro, rutaDocumento, ...}]}
  - PDF:      rutaDocumento apunta al CDN externo (ObtenerImagenDeSistema).

Particularidades de Baja California:
  - Cada SECCION del numero del PO de fin de anio (publicado ~dic 27) es la
    Ley de Ingresos de UN municipio: SECC III=Mexicali, IV=Tijuana, V=Ensenada,
    VI=Tecate, VII=Rosarito, VIII=San Felipe, IX=San Quintin. Es decir, una ley
    por PDF (modelo similar a SLP/Jalisco), pero el PDF es GRANDE (230-440 pp)
    porque incluye la Tabla de Valores Catastrales Unitarios completa. La
    seccion de tasas del impuesto predial vive en las primeras ~20 paginas.
  - La respuesta JSON viene en latin-1 (acentos), no UTF-8.
  - PDFs ESCANEADOS 2010-2022; DIGITALES (texto extraible) 2023+. Por eso
    NEEDS_OCR=True con OCR adaptativo limitado a las primeras paginas
    (ver src/estados/bajacalifornia/ocr.py) -- no tiene sentido OCR'ar 400 pp
    de tablas catastrales para una seccion predial de ~6 pp.
  - Tasa base del predial remite a la Ley de Hacienda Municipal del Estado;
    la Ley de Ingresos fija sobretasas diferenciadas "al millar" (industrial,
    baldios, rusticos) y un minimo en UMA.

CVE_ENT = 02 (INEGI). 7 municipios (San Quintin y San Felipe creados ~2020).
"""

from __future__ import annotations

ESTADO_SLUG = "bajacalifornia"
PREFIJO = "BC"
ESTADO_NOMBRE = "Baja California"
CVE_ENT = "02"
# OCR adaptativo + page-limited: 2010-2022 son escaneos, 2023+ nativos.
NEEDS_OCR = True

# -- Anios --
YEAR_MIN = 2010
YEAR_MAX = 2025

# Paginas iniciales a conservar para OCR (la seccion predial vive al frente;
# el resto del PDF son tablas de valores catastrales que no se necesitan).
OCR_PAGE_LIMIT = 55

# -- API del Periodico Oficial --
BASE_URL = "https://periodicooficial.ebajacalifornia.gob.mx/oficial"
SESSION_URL = f"{BASE_URL}/inicioConsulta.jsp"
SEARCH_URL = f"{BASE_URL}/IndiceConsulta/getIndicesBusquedaConsulta"

# -- Headers HTTP --
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
# El servidor corta el handshake TLS de Python/requests; curl negocia bien.
# verify=False porque la cadena del CDN externo a veces no valida en Windows.
REQUESTS_KWARGS: dict = {"timeout": 90, "verify": False}

# Timeout (s) para descarga de PDFs: los tomos escaneados pesan hasta ~50 MB
# y el CDN es lento, asi que necesita mucho mas que el timeout de busqueda.
DOWNLOAD_TIMEOUT = 600

# -- 7 municipios de Baja California --
# Fuente: INEGI catalogo AGEEML. San Quintin (006) y San Felipe (007) fueron
# creados en 2020-2021 (escindidos de Ensenada y Mexicali); sus leyes propias
# arrancan en FY2021 y FY2022 respectivamente.
# Tupla: (cve_mun, nombre_oficial, slug)
MUNICIPIOS: list[tuple[str, str, str]] = [
    ("001", "Ensenada", "ensenada"),
    ("002", "Mexicali", "mexicali"),
    ("003", "Tecate", "tecate"),
    ("004", "Tijuana", "tijuana"),
    ("005", "Playas de Rosarito", "playas_de_rosarito"),
    ("006", "San Quintin", "san_quintin"),
    ("007", "San Felipe", "san_felipe"),
]

# Busqueda en la API: palabra clave distintiva del municipio (palabra2) junto
# con palabra1="INGRESOS". Se evita acentos en el termino de busqueda.
# Tupla: (palabra_clave_busqueda, slug)
SEARCH_NAMES: list[tuple[str, str]] = [
    ("ENSENADA", "ensenada"),
    ("MEXICALI", "mexicali"),
    ("TECATE", "tecate"),
    ("TIJUANA", "tijuana"),
    ("ROSARITO", "playas_de_rosarito"),
    ("QUINT", "san_quintin"),    # San Quintin (sin acento en la busqueda)
    ("FELIPE", "san_felipe"),
]

# Aliases para resolucion de identidad (MuniMatcher / catalog)
ALIASES: dict[str, str] = {
    "rosarito": "playas_de_rosarito",
    "playas_rosarito": "playas_de_rosarito",
    "san_quintin": "san_quintin",
    "quintin": "san_quintin",
    "san_felipe": "san_felipe",
}

# -- Dicts rapidos --
SLUG_TO_CVE = {slug: (cve, name) for cve, name, slug in MUNICIPIOS}
