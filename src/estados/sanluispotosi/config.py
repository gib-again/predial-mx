"""
Configuración específica de San Luis Potosí.

Fuente: Periódico Oficial del Estado de San Luis Potosí.
API JSON pública: búsqueda por rango de fechas + palabra clave en título,
descarga por id de publicación. Cada PDF contiene UNA ley municipal completa
(modelo 1-PDF-por-municipio-año, similar a Jalisco).

CVE_ENT = 24 (INEGI). 58 municipios.
PDFs nativos con texto seleccionable → no requiere OCR; el fallback de
PDF visión en llm_extract cubre casos atípicos.
"""

from __future__ import annotations

ESTADO_SLUG = "sanluispotosi"
PREFIJO = "SLP"
ESTADO_NOMBRE = "San Luis Potosí"
CVE_ENT = "24"
# OCR adaptativo: solo se aplica a PDFs escaneados (2012-2016, 2019); los
# nativos (2017+) se saltan automáticamente. Ver src/estados/sanluispotosi/ocr.py
NEEDS_OCR = True

# ── Años ──
YEAR_MIN = 2010
YEAR_MAX = 2025

# ── API del Periódico Oficial ──
BASE_URL = "https://periodicooficial.slp.gob.mx"
API_BUSQUEDA = f"{BASE_URL}/api/publicacion/busqueda/filtro/gt"
API_DOC = f"{BASE_URL}/api/publicacion/imprimir/guest/{{id}}/documento"
PALABRA = "ley de ingresos"

# Cascada de endpoints PDF para reintentos (la app web del PO los rota
# silenciosamente cuando el primero da 404). Probado contra IDs históricos.
FALLBACK_PDF_ENDPOINTS = [
    f"{BASE_URL}/api/publicacion/imprimir/guest/{{id}}/documento",  # principal
    f"{BASE_URL}/api/publicacion/imprimir/{{id}}/documento",        # sin "guest"
    f"{BASE_URL}/api/publicacion/{{id}}/pdf",                       # legacy
    f"{BASE_URL}/publicacion/{{id}}/pdf",                           # sin /api
    f"{BASE_URL}/storage/publicaciones/{{id}}.pdf",                 # static Laravel
]

# Rango "ancho" para barrido histórico en una sola query — replica el
# comportamiento que la SPA del PO usa por defecto. Capturado en
# catalogs/curl_slp.txt. La hipótesis es que la API no expone los mismos
# resultados con ventanas estrechas que con esta consulta global.
WIDE_FECHA_INICIO = "1857-06-06"
WIDE_FECHA_FIN = "2026-12-31"

# ── Congreso del Estado de SLP (Ruta A — Playwright) ──
# Sitio del Congreso Local. Su listado de leyes municipales sirve como
# fuente alterna para 2010-2011 (cuyos PDFs ya no existen en el backend
# del PO). El sitio está protegido por Sucuri Cloud Proxy con challenge
# JavaScript: requiere navegador real (Playwright).
BASE_URL_CONGRESO = "https://www.congresosanluis.gob.mx"
URL_CONGRESO_LEYES = f"{BASE_URL_CONGRESO}/legislacion/leyes"

# ── Wayback Machine (Ruta C — best effort) ──
WAYBACK_AVAILABILITY_API = "https://archive.org/wayback/available"
WAYBACK_REPLAY_BASE = "https://web.archive.org/web"
# Backoff conservador: vimos 503s en pruebas; prefieren rate < 1 req/s.
WAYBACK_THROTTLE_SECONDS = 8.0

# ── Headers HTTP ──
USER_AGENT = "Mozilla/5.0 (compatible; PredialMX/1.0)"
REQUESTS_KWARGS = {"timeout": 60, "verify": True}

# ── Aliases: variantes en títulos / API → slug canónico INEGI ──
# Se actualizarán iterativamente conforme aparezcan municipios sin match.
ALIASES: dict[str, str] = {
    # San Luis Potosí (capital) — a veces aparece como "S.L.P." en el campo segundo
    "san_luis": "san_luis_potosi",
    "slp": "san_luis_potosi",
    # Soledad de Graciano Sánchez — a veces "Soledad" a secas
    "soledad": "soledad_de_graciano_sanchez",
    "soledad_graciano_sanchez": "soledad_de_graciano_sanchez",
    "soledad_de_graciano": "soledad_de_graciano_sanchez",
    # Armadillo de los Infante
    "armadillo": "armadillo_de_los_infante",
    "armadillo_de_los_infantes": "armadillo_de_los_infante",
    # Axtla de Terrazas
    "axtla": "axtla_de_terrazas",
    # Matehuala — typo "Matahuala" aparece en datos antiguos
    "matahuala": "matehuala",
    # Ciudad Valles
    "valles": "ciudad_valles",
    # Cerro de San Pedro
    "cerro_san_pedro": "cerro_de_san_pedro",
    # San Antonio
    "san_antonio_misiones": "san_antonio",
    # Tamuín
    "tamuin": "tamuin",
    # Tanlajás
    "tanlajas": "tanlajas",
    # San Martín Chalchicuautla
    "san_martin": "san_martin_chalchicuautla",
    # Santa María del Río
    "santa_maria_rio": "santa_maria_del_rio",
    # Villa de Arriaga / Villa de Arista / Villa de Guadalupe / Villa de la Paz / Villa de Ramos / Villa de Reyes
    # (estos son nombres canónicos, sólo agregar si aparecen variantes en datos reales)
    # Tierra Nueva
    "tierranueva": "tierra_nueva",
    # Tampamolón Corona
    "tampamolon": "tampamolon_corona",
    # Tancanhuitz (antes "Ciudad Santos")
    "ciudad_santos": "tancanhuitz",
    # Xilitla
    "xilitla": "xilitla",
    # Aquismón — typo común
    "aquismon": "aquismon",
}
