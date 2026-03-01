"""
Configuración específica de Chihuahua.

Fuente: Código Municipal para el Estado de Chihuahua, Arts. 148-149.
  Tarifa estatal uniforme para 67 municipios.
  No requiere descarga de PDFs ni OCR.
"""

from __future__ import annotations

ESTADO_SLUG = "chihuahua"
PREFIJO = "CHIH"
ESTADO_NOMBRE = "Chihuahua"
CVE_ENT = "08"
NEEDS_OCR = False  # Tarifa hardcoded del Código estatal

# ── Años ──
YEAR_MIN = 2010
YEAR_MAX = 2025

# ── 67 municipios de Chihuahua ──────────────────────────────
# Fuente: INEGI catálogo AGEEML (CVE_ENT=08).
# Tupla: (cve_mun, nombre_oficial, slug)
MUNICIPIOS: list[tuple[str, str, str]] = [
    ("001", "Ahumada", "ahumada"),
    ("002", "Aldama", "aldama"),
    ("003", "Allende", "allende"),
    ("004", "Aquiles Serdán", "aquiles_serdan"),
    ("005", "Ascensión", "ascension"),
    ("006", "Bachíniva", "bachiniva"),
    ("007", "Balleza", "balleza"),
    ("008", "Batopilas de Manuel Gómez Morín", "batopilas"),
    ("009", "Bocoyna", "bocoyna"),
    ("010", "Buenaventura", "buenaventura"),
    ("011", "Camargo", "camargo"),
    ("012", "Carichí", "carichi"),
    ("013", "Casas Grandes", "casas_grandes"),
    ("014", "Chihuahua", "chihuahua"),
    ("015", "Chínipas", "chinipas"),
    ("016", "Coronado", "coronado"),
    ("017", "Coyame del Sotol", "coyame_del_sotol"),
    ("018", "Cuauhtémoc", "cuauhtemoc"),
    ("019", "Cusihuiriachi", "cusihuiriachi"),
    ("020", "Delicias", "delicias"),
    ("021", "Dr. Belisario Domínguez", "dr_belisario_dominguez"),
    ("022", "El Tule", "el_tule"),
    ("023", "Galeana", "galeana"),
    ("024", "Gómez Farías", "gomez_farias"),
    ("025", "Gran Morelos", "gran_morelos"),
    ("026", "Guachochi", "guachochi"),
    ("027", "Guadalupe", "guadalupe"),
    ("028", "Guadalupe y Calvo", "guadalupe_y_calvo"),
    ("029", "Guazapares", "guazapares"),
    ("030", "Guerrero", "guerrero"),
    ("031", "Hidalgo del Parral", "hidalgo_del_parral"),
    ("032", "Huejotitán", "huejotitan"),
    ("033", "Ignacio Zaragoza", "ignacio_zaragoza"),
    ("034", "Janos", "janos"),
    ("035", "Jiménez", "jimenez"),
    ("036", "Juárez", "juarez"),
    ("037", "Julimes", "julimes"),
    ("038", "La Cruz", "la_cruz"),
    ("039", "López", "lopez"),
    ("040", "Madera", "madera"),
    ("041", "Maguarichi", "maguarichi"),
    ("042", "Manuel Benavides", "manuel_benavides"),
    ("043", "Matachí", "matachi"),
    ("044", "Matamoros", "matamoros"),
    ("045", "Meoqui", "meoqui"),
    ("046", "Morelos", "morelos"),
    ("047", "Moris", "moris"),
    ("048", "Namiquipa", "namiquipa"),
    ("049", "Nonoava", "nonoava"),
    ("050", "Nuevo Casas Grandes", "nuevo_casas_grandes"),
    ("051", "Ocampo", "ocampo"),
    ("052", "Ojinaga", "ojinaga"),
    ("053", "Praxedis G. Guerrero", "praxedis_g_guerrero"),
    ("054", "Riva Palacio", "riva_palacio"),
    ("055", "Rosales", "rosales"),
    ("056", "San Francisco de Borja", "san_francisco_de_borja"),
    ("057", "San Francisco de Conchos", "san_francisco_de_conchos"),
    ("058", "San Francisco del Oro", "san_francisco_del_oro"),
    ("059", "Santa Bárbara", "santa_barbara"),
    ("060", "Santa Isabel", "santa_isabel"),
    ("061", "Satevó", "satevo"),
    ("062", "Saucillo", "saucillo"),
    ("063", "Temósachic", "temosachic"),
    ("064", "Urique", "urique"),
    ("065", "Uruachi", "uruachi"),
    ("066", "Valle de Zaragoza", "valle_de_zaragoza"),
    ("067", "Valle del Rosario", "valle_del_rosario"),
]

SLUG_TO_CVE = {slug: (cve, name) for cve, name, slug in MUNICIPIOS}
NAME_TO_SLUG = {name.upper(): slug for _cve, name, slug in MUNICIPIOS}
