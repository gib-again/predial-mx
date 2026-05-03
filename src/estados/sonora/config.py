"""
Configuración específica de Sonora.

Fuente: Boletín Oficial del Estado de Sonora (boletinoficial.sonora.gob.mx).
Sitio Joomla (sppagebuilder) que lista los boletines del año en una página
índice por id_joomla. Cada boletín especial de finales de diciembre incluye
72 secciones romanas, una por municipio.

CVE_ENT = 26 (INEGI). 72 municipios.

Patrones de URL de PDFs (dos eras observadas):
  Era nueva (2019+):
    https://boletinoficial.sonora.gob.mx/images/boletines/{YEAR}/12/{YEAR}{TOMO}{NUM}{SECC}.pdf
  Era antigua (≤ 2018):
    https://boletinoficial.sonora.gob.mx/boletin/images/boletinesPdf/{YEAR}/12/{YEAR}{TOMO}{NUM}{SECC}.pdf
  Edición especial:
    https://boletinoficial.sonora.gob.mx/images/boletines/{YEAR}/12/EE{ddmmaaaa}{seq}.pdf

Estructura predial típica: cuota fija + tasa al millar por rangos de valor
catastral; rústicos con cuota fija por hectárea; mínimo en UMA (post-2017).
needs_ocr=True (adaptativo): los boletines antiguos pueden ser escaneados.
"""

from __future__ import annotations

ESTADO_SLUG = "sonora"
PREFIJO = "SON"
ESTADO_NOMBRE = "Sonora"
CVE_ENT = "26"
# OCR adaptativo: solo se aplica a PDFs con < 300 chars/página promedio.
# Los boletines nativos (era nueva, 2019+) se saltan automáticamente.
NEEDS_OCR = True

# ── Años ──
YEAR_MIN = 2010
YEAR_MAX = 2025

# ── Boletín Oficial de Sonora ──
BASE_URL = "https://boletinoficial.sonora.gob.mx"
INDEX_URL_TPL = f"{BASE_URL}/index.php?option=com_sppagebuilder&view=page&id={{id_joomla}}"

# Patrones de URL de PDFs (dos eras observadas)
PDF_URL_NEW_TPL = f"{BASE_URL}/images/boletines/{{year}}/12/{{year}}{{tomo}}{{num}}{{secc}}.pdf"
PDF_URL_OLD_TPL = (
    f"{BASE_URL}/boletin/images/boletinesPdf/{{year}}/12/{{year}}{{tomo}}{{num}}{{secc}}.pdf"
)
PDF_URL_EE_TPL = f"{BASE_URL}/images/boletines/{{year}}/12/EE{{ddmmaaaa}}{{seq}}.pdf"

# Mapeo año_pub → id_joomla. Descubierto empíricamente vía barrido (2026-05-01):
# para id_joomla N, los PDFs internos son del año (2070 - N) hasta id=63;
# id=91 contiene tanto 2024 como 2025.
# Para ejercicio fiscal F → buscar publicación en año_pub = F-1.
ID_JOOMLA_POR_ANIO_PUB: dict[int, int] = {
    2024: 82,  # Boletines de dic 2024 (leyes EF 2025) → id=82, NO id=91
    2023: 45,
    2022: 46,
    2021: 47,
    2020: 48,
    2019: 49,
    2018: 50,
    2017: 51,
    2016: 52,
    2015: 53,
    2014: 54,
    2013: 55,
    2012: 56,
    2011: 57,
    2010: 58,
    2009: 59,
}

# Tomos romanos del Boletín Oficial por año de publicación.
# El año_pub es N-1 para una ley con ejercicio fiscal N.
# Confirmados desde URLs de muestra (.md de contexto):
#   2018→CCII (2018CCII51XX), 2023→CCXII (2023CCXII52X), 2024→CCXIV (2024CCXIV53XV).
# Otros años se inferirán empíricamente o se descubrirán al scrapear el índice.
TOMOS_POR_ANIO_PUB: dict[int, str] = {
    2018: "CCII",
    2023: "CCXII",
    2024: "CCXIV",
    2025: "CCXV",
    2026: "CCXVII",
}

# ── Headers HTTP ──
# El sitio bloquea con 403 a User-Agents no-navegador, así que enviamos uno
# realista de Chrome estable.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
REQUESTS_KWARGS = {"timeout": 60, "verify": True}

# Pausa entre descargas para no saturar al servidor (segundos).
THROTTLE_SECONDS = 0.5

# ── Aliases: variantes en títulos / OCR → slug canónico INEGI ──
# Vacío inicialmente; poblar tras la primera corrida cuando se detecten
# nombres no matcheados por MuniMatcher.
ALIASES: dict[str, str] = {
    # Variantes históricas/OCR comunes anticipadas:
    "alamos": "alamos",
    "san_luis": "san_luis_rio_colorado",
    "slrc": "san_luis_rio_colorado",
    "puerto_penasco": "puerto_penasco",
    "magdalena_de_kino": "magdalena",
    "kino": "magdalena",
    "plutarco_elias_calles": "general_plutarco_elias_calles",
    "sonoyta": "general_plutarco_elias_calles",
    "gral": "general_plutarco_elias_calles",
    "gral_plutarco_elias_calles": "general_plutarco_elias_calles",
    "h_caborca": "caborca",
    "h_agua_prieta": "agua_prieta",
    "h_guaymas": "guaymas",
    "h_nogales": "nogales",
    "h_ures": "ures",
    "villa_juarez": "benito_juarez",
    "san_ignacio": "san_ignacio_rio_muerto",
    "nacozari": "nacozari_de_garcia",
    "villa_pesqueira_matape": "villa_pesqueira",
    "matape": "villa_pesqueira",
    "ures": "ures",
    "guaymas": "guaymas",
    "caborca": "caborca",
    "nogales": "nogales",
    "obregon": "cajeme",
    "ciudad_obregon": "cajeme",
    "cananea": "cananea",
}
