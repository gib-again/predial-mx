"""
Configuración específica de Coahuila.

URLs del Periódico Oficial, prefijo de archivos, flags.
"""

ESTADO_SLUG = "coahuila"
PREFIJO = "COAH"
ESTADO_NOMBRE = "Coahuila"
NEEDS_OCR = False

# URL del Periódico Oficial de Coahuila (ASP clásico con DataTables)
BASE_LISTA = "https://periodico.segobcoahuila.gob.mx/BusquedaPorA%C3%B1o.asp"
BASE_ROOT = "https://periodico.segobcoahuila.gob.mx"

# Headers para requests (el sitio bloquea user-agents genéricos)
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
}

# Rango de años de PUBLICACIÓN a scrapear.
# Ej: leyes publicadas en dic-2010 corresponden al ejercicio 2011.
ANIO_PUB_INI = 2009
ANIO_PUB_FIN = 2024

# Catálogo de municipios (path relativo a la raíz del proyecto)
DIR_MUN_CSV = "catalogs/municipios_inegi.csv"

# El PO de Coahuila usa el patrón:
#   NUMERO xxx.- LEY DE INGRESOS DEL MUNICIPIO DE {MUNICIPIO}, COAHUILA
PATRON_LEY_HEADER = (
    r"NUMERO\s+\d+\.-\s*LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+"
)

# Patrón para delimitar el fin de la sección predial
PATRON_FIN_PREDIAL = (
    r"CAPITULO\s+SEGUNDO\s+DEL\s+IMPUESTO\s+SOBRE\s+ADQUISICION\s+DE\s+INMUEBLES"
    r"|CAPITULO\s+SEGUNDO\s+DEL\s+IMPUESTO\s+AL\s+TRASLADO\s+DE\s+DOMINIO"
)

CVE_ENT = "05"
ALIASES: dict[str, str] = {
    # NOM_CAB → slug de NOM_MUN donde difieren
    "ciudad_acuna": "acuna",
    "nueva_rosita": "san_juan_de_sabinas",
    "piedras_negras": "piedras_negras",
}
