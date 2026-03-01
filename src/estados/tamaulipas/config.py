"""
Configuración específica de Tamaulipas.

Fuente: Periódico Oficial del Estado de Tamaulipas (PO).
Un PDF consolidado por año con las leyes de ingresos de los 43 municipios.
Las URLs no siguen patrón lógico → hardcodeadas desde tamaulipas_url.txt.

Nota: el año de la URL es el año de PUBLICACIÓN, que corresponde al
ejercicio fiscal del año SIGUIENTE (ej: URL "2009" → ejercicio 2010).
"""

from __future__ import annotations

ESTADO_SLUG = "tamaulipas"
PREFIJO = "TAMPS"
ESTADO_NOMBRE = "Tamaulipas"
CVE_ENT = "28"
NEEDS_OCR = False  # PDFs del PO de Tamaulipas son digitales

# ── Años ──
YEAR_MIN = 2010
YEAR_MAX = 2025

# ── URLs hardcodeadas ──────────────────────────────────────
# Formato: ejercicio_fiscal → URL del PO
# El PO se publica en dic del año anterior (ej: dic-2009 → EF 2010)
URLS_PO: dict[int, str] = {
    2010: "https://po.tamaulipas.gob.mx/wp-content/uploads/2018/10/cxxxiv-153-231209F-ANEXO.pdf",
    2011: "https://po.tamaulipas.gob.mx/wp-content/uploads/2018/10/cxxxv-153-231210F-ANEXO.pdf",
    2012: "https://po.tamaulipas.gob.mx/wp-content/uploads/2018/10/cxxxvi-152-211211F-ANEXO.pdf",
    2013: "https://po.tamaulipas.gob.mx/wp-content/uploads/2013/01/cxxxvii-153-201212F-ANEXO7.pdf",
    2014: "https://po.tamaulipas.gob.mx/wp-content/uploads/2014/01/cxxxviii-153-191213F-ANEXO4.pdf",
    2015: "https://po.tamaulipas.gob.mx/wp-content/uploads/2015/01/cxxxix-154-241214F-ANEXO.pdf",
    2016: "https://po.tamaulipas.gob.mx/wp-content/uploads/2016/01/cxl-154-241215F-ANEXO.pdf",
    2017: "https://po.tamaulipas.gob.mx/wp-content/uploads/2019/03/cxli-151-201216F-ANEXO.pdf",
    2018: "https://po.tamaulipas.gob.mx/wp-content/uploads/2018/01/cxlii-152-201217F-ANEXO-1.pdf",
    2019: "https://po.tamaulipas.gob.mx/wp-content/uploads/2019/01/cxliii-Ext.No_.17-241218F-ANEXO.pdf",
    2020: "https://po.tamaulipas.gob.mx/wp-content/uploads/2020/03/cxliv-155-251219F-ANEXO.pdf",
    2021: "https://po.tamaulipas.gob.mx/wp-content/uploads/2021/01/cxlv-153-221220F-EV.pdf",
    2022: "https://po.tamaulipas.gob.mx/wp-content/uploads/2022/01/cxlvi-154-281221F-EV.pdf",
    2023: "https://po.tamaulipas.gob.mx/wp-content/uploads/2022/12/cxlvii-154-271222-EV.pdf",
    2024: "https://po.tamaulipas.gob.mx/wp-content/uploads/2023/12/cxlviii-155-271223-EV.pdf",
    2025: "https://po.tamaulipas.gob.mx/wp-content/uploads/2024/12/cxlix-Ext.No_.45-281224.pdf",
    2026: "https://po.tamaulipas.gob.mx/wp-content/uploads/2025/12/cl-Ext-No.64-261225.pdf",
}

# ── Headers HTTP ──
USER_AGENT = "Mozilla/5.0 (compatible; PredialMX/1.0)"

# ── 43 municipios de Tamaulipas ──────────────────────────────
# Fuente: INEGI catálogo AGEEML.
# Tupla: (cve_mun, nombre_oficial, slug)
MUNICIPIOS: list[tuple[str, str, str]] = [
    ("001", "Abasolo", "abasolo"),
    ("002", "Aldama", "aldama"),
    ("003", "Altamira", "altamira"),
    ("004", "Antiguo Morelos", "antiguo_morelos"),
    ("005", "Burgos", "burgos"),
    ("006", "Bustamante", "bustamante"),
    ("007", "Camargo", "camargo"),
    ("008", "Casas", "casas"),
    ("009", "Ciudad Madero", "ciudad_madero"),
    ("010", "Cruillas", "cruillas"),
    ("011", "Gómez Farías", "gomez_farias"),
    ("012", "González", "gonzalez"),
    ("013", "Güémez", "guemez"),
    ("014", "Guerrero", "guerrero"),
    ("015", "Gustavo Díaz Ordaz", "gustavo_diaz_ordaz"),
    ("016", "Hidalgo", "hidalgo"),
    ("017", "Jaumave", "jaumave"),
    ("018", "Jiménez", "jimenez"),
    ("019", "Llera", "llera"),
    ("020", "Mainero", "mainero"),
    ("021", "El Mante", "el_mante"),
    ("022", "Matamoros", "matamoros"),
    ("023", "Méndez", "mendez"),
    ("024", "Mier", "mier"),
    ("025", "Miguel Alemán", "miguel_aleman"),
    ("026", "Miquihuana", "miquihuana"),
    ("027", "Nuevo Laredo", "nuevo_laredo"),
    ("028", "Nuevo Morelos", "nuevo_morelos"),
    ("029", "Ocampo", "ocampo"),
    ("030", "Padilla", "padilla"),
    ("031", "Palmillas", "palmillas"),
    ("032", "Reynosa", "reynosa"),
    ("033", "Río Bravo", "rio_bravo"),
    ("034", "San Carlos", "san_carlos"),
    ("035", "San Fernando", "san_fernando"),
    ("036", "San Nicolás", "san_nicolas"),
    ("037", "Soto la Marina", "soto_la_marina"),
    ("038", "Tampico", "tampico"),
    ("039", "Tula", "tula"),
    ("040", "Valle Hermoso", "valle_hermoso"),
    ("041", "Victoria", "victoria"),
    ("042", "Villagrán", "villagran"),
    ("043", "Xicoténcatl", "xicotencatl"),
]

# ── Aliases de nombres ──────────────────────────────────────
# Mapea variantes encontradas en PDFs → slug canónico
ALIASES: dict[str, str] = {
    "cd. madero": "ciudad_madero",
    "cd madero": "ciudad_madero",
    "ciudad_madero": "ciudad_madero",
    "el_mante": "el_mante",
    "mante": "el_mante",
    "cd. mante": "el_mante",
    "cd_mante": "el_mante",
    "diaz_ordaz": "gustavo_diaz_ordaz",
    "gustavo_diaz_ordaz": "gustavo_diaz_ordaz",
    "gomez_farias": "gomez_farias",
    "rio_bravo": "rio_bravo",
    "soto_la_marina": "soto_la_marina",
    "soto_marina": "soto_la_marina",
    "valle_hermoso": "valle_hermoso",
    "xicotencatl": "xicotencatl",
    "nuevo_laredo": "nuevo_laredo",
    "nuevo_morelos": "nuevo_morelos",
    "antiguo_morelos": "antiguo_morelos",
    "san_carlos": "san_carlos",
    "san_fernando": "san_fernando",
    "san_nicolas": "san_nicolas",
    "miguel_aleman": "miguel_aleman",
}

# Dict rápido: slug → (cve_mun, nombre_oficial)
SLUG_TO_CVE = {slug: (cve, name) for cve, name, slug in MUNICIPIOS}
NAME_TO_SLUG = {}
for _cve, _name, _slug in MUNICIPIOS:
    NAME_TO_SLUG[_name.upper()] = _slug
