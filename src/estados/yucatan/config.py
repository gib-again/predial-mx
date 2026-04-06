"""
Configuración específica de Yucatán.

Diferencias clave:
  - Los PDFs del Diario Oficial son tomos con TODAS las leyes municipales (~60-100 por tomo)
  - Típicamente 1-3 tomos por año (suplementos de diciembre)
  - Se segmenta primero en leyes individuales, luego se busca predial
  - Nombres mayas (Dzitbalché, Halachó, Hoctún)
  - Predial incluye tablas de valores catastrales (ignorar) + tarifa real
  - Diseños de predial variados: tasa plana, progresivo, factor sobre catastral, cuota fija
"""

ESTADO_SLUG = "yucatan"
PREFIJO = "YUC"
ESTADO_NOMBRE = "Yucatán"
NEEDS_OCR = False  # PDFs del DO de Yucatán son digitales
CVE_ENT = "31"

# ── URLs del Diario Oficial ──
BASE_INDEX_URL = "https://www.yucatan.gob.mx/docs/diario_oficial/indices/{year}.pdf"
BASE_DIARIO_URL = (
    "https://www.yucatan.gob.mx/docs/diario_oficial/diarios/{year}/{ymd}{suffix}.pdf"
)

USER_AGENT = "Mozilla/5.0 (compatible; DOYucatanDownloader/2.0)"

# ── Años ──
YEAR_MIN = 2010
YEAR_MAX = 2024

# Solo diciembre y enero (publicación de leyes de ingresos)
KEEP_MONTHS = {12, 1}

# ── Sufijos de URL a probar ──
# Leyes de ingresos salen en suplementos: _1, _2, _3, _4, _suplemento
# Reducido a 5: nunca hemos visto tomo relevante en _6+
MAX_SUFFIX = 5
EXTRA_SUFFIXES = ["_suplemento"]

# Tamaño máximo de PDF a descargar (MB)
MAX_PDF_SIZE_MB = 50

# ── Mérida: caso especial ──
# Mérida NO aparece en los tomos del DO porque tiene su propia Ley de Hacienda.
# La tarifa del predial está en la Ley de Hacienda (no en la Ley de Ingresos).
# Los PDFs se descargan del portal del Ayuntamiento de Mérida.
# Nota: las tarifas 2023-2025 son idénticas a 2022.
# Nota: algunas tablas son imagen y pueden necesitar OCR.
MERIDA_URLS = {
    2010: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/Archivos2010/leyes10.pdf",
    2011: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/Archivos2011/leyes11.pdf",
    2012: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/Archivos2012/LeyIngresosHacienda12.pdf",
    2013: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/archivos2012_2015/leyes13.pdf",
    2014: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/archivos2012_2015/leyes14.pdf",
    2015: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/archivos2012_2015/leyes15.pdf",
    2016: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/archivos2015-2018/LeyIngresosHacienda16.pdf",
    2017: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/archivos2015-2018/LeyIngresosHacienda17.pdf",
    2018: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/archivos2015-2018/LeyIngresosHacienda18.pdf",
    2019: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/archivos2018-2021/LeyIngresosHacienda19.pdf",
    2020: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/archivos2018-2021/LeyIngresosHacienda20.pdf",
    2021: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/archivos2018-2021/LeyIngresosHacienda21.pdf",
    2022: "http://www.merida.gob.mx/municipio/portal/norma/contenido/pdfs/archivos2021-2024/LeyIngresosHacienda22.pdf",
    # 2023-2025: mismas tarifas que 2022
}
# Años donde se replica la tarifa de 2022
MERIDA_REPLICA_YEARS = [2023, 2024, 2025]

# ── Municipios de Yucatán (106) ──
MUNICIPIOS = [
    "Abalá", "Acanceh", "Akil", "Baca", "Bokobá", "Buctzotz",
    "Cacalchén", "Calotmul", "Cansahcab", "Cantamayec", "Celestún",
    "Cenotillo", "Chacsinkin", "Chankom", "Chapab", "Chemax",
    "Chicxulub Pueblo", "Chichimilá", "Chikindzonot", "Chocholá",
    "Chumayel", "Conkal", "Cuncunul", "Cuzamá", "Dzan", "Dzemul",
    "Dzidzantún", "Dzilam de Bravo", "Dzilam González", "Dzitás",
    "Dzoncauich", "Espita", "Halachó", "Hocabá", "Hoctún", "Homún",
    "Huhí", "Hunucmá", "Ixil", "Izamal", "Kanasín", "Kantunil",
    "Kaua", "Kinchil", "Kopomá", "Mama", "Maní", "Maxcanú",
    "Mayapán", "Mérida", "Mocochá", "Motul", "Muna", "Muxupip",
    "Opichén", "Oxkutzcab", "Panabá", "Peto", "Progreso",
    "Quintana Roo", "Río Lagartos", "Sacalum", "Samahil", "Sanahcat",
    "San Felipe", "Santa Elena", "Seyé", "Sinanché", "Sotuta",
    "Sucilá", "Sudzal", "Suma de Hidalgo", "Tahdziú", "Tahmek",
    "Teabo", "Tecoh", "Tekal de Venegas", "Tekantó", "Tekax",
    "Tekit", "Tekom", "Telchac Pueblo", "Telchac Puerto", "Temax",
    "Temozón", "Tepakán", "Tetiz", "Teya", "Ticul", "Timucuy",
    "Tinum", "Tixcacalcupul", "Tixkokob", "Tixmehuac", "Tixpéual",
    "Tizimín", "Tunkás", "Tzucacab", "Uayma", "Ucú", "Umán",
    "Valladolid", "Xocchel", "Yaxcabá", "Yaxkukul", "Yobaín",
]
