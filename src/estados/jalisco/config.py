"""
Configuración específica de Jalisco.

A diferencia de Coahuila (scraping HTML), Jalisco tiene una API REST pública.
"""

ESTADO_SLUG = "jalisco"
PREFIJO = "JAL"
ESTADO_NOMBRE = "Jalisco"
NEEDS_OCR = True  # PDFs del PO de Jalisco son frecuentemente escaneados
CVE_ENT = "14"

# ── API del Periódico Oficial ──
BASE_PORTAL = "https://periodicooficial.jalisco.gob.mx"
API_BASE = "https://apiperiodico.jalisco.gob.mx/api/otrosperiodicos/public"
API_INGRESOS = f"{API_BASE}/ingresos"

# IDs de municipio en la API (1-125)
MIN_MPO_ID = 1
MAX_MPO_ID = 125

# ── Años de interés ──
YEAR_MIN = 2010
YEAR_MAX = 2025

# ── Headers HTTP ──
USER_AGENT = "tesis-predial-jalisco/1.0"

# ── OCR ──
OCR_LANG = "spa+eng"

# ── Patrones para localización de predial ──
# Jalisco usa patrones diferentes a Coahuila:
# - Inicio: SECCION PRIMERA/SEGUNDA + "Del impuesto predial" + "Articulo NN"
# - Fin: siguiente impuesto (adquisición, traslado, transmisiones)
NEXT_TAX_PATTERNS = [
    (r"impuesto\s+sobre\s+la\s+adquisicion\s+de\s+bienes?\s+inmuebles", "adquisicion_inmuebles"),
    (r"impuesto\s+sobre\s+adquisicion\s+de\s+inmuebles", "adquisicion_inmuebles"),
    (r"impuesto\s+sobre\s+la\s+adquisicion\s+de\s+inmuebles", "adquisicion_inmuebles"),
    (r"impuesto\s+sobre\s+traslado\s+de\s+dominio", "traslado_dominio"),
    (r"impuesto\s+al\s+traslado\s+de\s+dominio", "traslado_dominio"),
    (r"impuesto\s+sobre\s+transmisiones\s+patrimoniales", "transmisiones_patrimoniales"),
]

# Contextos que NO son inicio de predial
BLACKLIST_HEADER_PATTERNS = [
    r"disposiciones\s+generales",
    r"incentivos\s+fiscales",
    r"generalidades\s+de\s+los\s+incentivos\s+fiscales",
]

# Márgenes para re-delimitación (script 65)
MARGIN_BEFORE_PAGES = 5
MARGIN_AFTER_PAGES = 18
