"""
Configuración específica de Querétaro.

Fuente: Periódico Oficial "La Sombra de Arteaga".
"""

from __future__ import annotations

ESTADO_SLUG = "queretaro"
PREFIJO = "QRO"
ESTADO_NOMBRE = "Querétaro"
NEEDS_OCR = False  # PDFs digitales

# ── URLs ──────────────────────────────────────────────────────
# Template para diarios del PO
URL_TEMPLATE = (
    "https://lasombradearteaga.segobqueretaro.gob.mx/getfile.php"
    "?p1={YYYY}{MM}{ISSUE}-{PART}.pdf"
)

# Templates para índices anuales
# 2011-2025: https://lasombradearteaga.segobqueretaro.gob.mx/getfile.php?p1=indice-{YYYY}.pdf
# 2010:      https://lasombradearteaga.segobqueretaro.gob.mx/2010/indice2010.pdf
INDEX_URL_TEMPLATE = (
    "https://lasombradearteaga.segobqueretaro.gob.mx/getfile.php?p1=indice-{YYYY}.pdf"
)
INDEX_URL_2010 = "https://lasombradearteaga.segobqueretaro.gob.mx/2010/indice2010.pdf"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
REFERER = "https://lasombradearteaga.segobqueretaro.gob.mx/"

# ── Años ──────────────────────────────────────────────────────
# Ojo: aunque el ejercicio mínimo sea 2010, necesitas publicaciones 2009 para leyes 2010 (hardcoded).
YEAR_MIN = 2010
YEAR_MAX = 2025

# ── Parámetros de descarga ────────────────────────────────────
MAX_PARTS_PER_ISSUE = 6
RATE_LIMIT_MIN = 0.3
RATE_LIMIT_MAX = 1.0

# ── Hardcoded diarios (cuando el índice / template no cubre) ───
HARDCODED_URLS: dict[int, list[str]] = {
    2009: [
        "https://lasombradearteaga.segobqueretaro.gob.mx/2009/20091295-01.pdf",
        "https://lasombradearteaga.segobqueretaro.gob.mx/2009/20091295-02.pdf",
        "https://lasombradearteaga.segobqueretaro.gob.mx/2009/20091295-03.pdf",
        "https://lasombradearteaga.segobqueretaro.gob.mx/2009/20091295-04.pdf",
    ],
    2010: [
        "https://lasombradearteaga.segobqueretaro.gob.mx/2010/20101272-01.pdf",
        "https://lasombradearteaga.segobqueretaro.gob.mx/2010/20101272-02.pdf",
        "https://lasombradearteaga.segobqueretaro.gob.mx/2010/20101272-03.pdf",
        "https://lasombradearteaga.segobqueretaro.gob.mx/2010/20101272-04.pdf",
    ],
    2011: [
        "https://lasombradearteaga.segobqueretaro.gob.mx/getfile.php?p1=20111270-01.pdf",
        "https://lasombradearteaga.segobqueretaro.gob.mx/getfile.php?p1=20111270-02.pdf",
        "https://lasombradearteaga.segobqueretaro.gob.mx/getfile.php?p1=20111270-03.pdf",
    ],
}

# ── Meses españoles para parseo de índices ─────────────────────
SPANISH_MONTHS = {
    "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
    "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
    "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12,
}

# ── Patrones / heurísticas ─────────────────────────────────────
# Anti-índice: si una página tiene ≥3 municipios distintos, suele ser índice/sumario
MAX_INDEX_PAGES = 4
INDEX_HITS_THRESHOLD = 3

# Keywords para heurísticas/QA (no determinan el corte, solo útiles si agregas validaciones)
PREDIAL_KEYWORDS = [
    "predial", "tabla", "tarifa", "tarifas", "valores", "rango", "rangos",
    "cuota", "fija", "excedente", "limite", "límite", "porcentaje", "bimestral",
    "uma", "avaluo", "avalúo",
]

