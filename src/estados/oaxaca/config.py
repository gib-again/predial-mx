"""
Configuración específica de Oaxaca.

Fuente: Periódico Oficial del Gobierno del Estado de Oaxaca.
Búsqueda HTML en periodicooficial.oaxaca.gob.mx (POST con payload).
Cada PDF ("Sección") contiene 3-7 leyes de ingresos municipales.
Los PDFs tienen marca de agua "DOCUMENTO SOLO PARA CONSULTA",
formato dos columnas y orientación landscape en algunas páginas.
Requiere OCR obligatorio.

CVE_ENT = 20 (INEGI).
570 municipios — la entidad con más municipios de México.

Esquema predial dominante: tasa_unica (0.5% anual sobre valor catastral)
con mínimos en UMA por tipo de suelo (urbano/rústico) y cuota por m²
para fraccionamiento por tipo habitacional.

Es común que algunos municipios pequeños no cobren el impuesto predial,
pero sí publiquen su ley de ingresos municipal en el Periódico Oficial.

"""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path

ESTADO_SLUG = "oaxaca"
PREFIJO = "OAX"
ESTADO_NOMBRE = "Oaxaca"
CVE_ENT = "20"
NEEDS_OCR = True  # PDFs con marca de agua + scanned elements

# ── Años ──
YEAR_MIN = 2010
YEAR_MAX = 2025

# ── Periódico Oficial ──
BASE_URL = "https://periodicooficial.oaxaca.gob.mx/"
SEARCH_URL = "https://periodicooficial.oaxaca.gob.mx/busqueda.php"

# Payload base para búsqueda de leyes de ingresos municipales
SEARCH_PAYLOAD_BASE = {
    "tipoPublicacion": "0",
    "mes": "0",
    "sumario": "ley de ingresos",
    "tipoDocumento": "0",
    "sujetoPublica": "",
    "clasificacionSujeto": "0",
    "buscarr": "Buscar",
}

# ── Headers HTTP ──
USER_AGENT = "Mozilla/5.0 (compatible; PredialMX/1.0)"
REQUESTS_KWARGS = {"timeout": 180, "verify": True}
SLEEP_BETWEEN_REQUESTS = 0.8
MAX_RETRIES = 4

# ── OCR ──
OCR_LANG = "spa"
OCR_DPI = 300
OCR_JOBS = 4

# ── Catálogo INEGI (compartido por todo el proyecto) ──
CATALOG_PATH = Path("catalogs/municipios_inegi.csv")


# ── Aliases: variantes comunes encontradas en PDFs del PO ──
ALIASES: dict[str, str] = {
    "oaxaca": "oaxaca_de_juarez",
    "oaxaca_de_juarez_centro": "oaxaca_de_juarez",
    # Municipios homónimos (mismo nombre, diferente distrito/cve_mun):
    #   San Juan Mixtepec:  cve 208 (Dto. Juxtlahuaca) vs 209 (Dto. Miahuatlán)
    #   San Pedro Mixtepec: cve 318 (Dto. Juquila)     vs 319 (Dto. Miahuatlán)
    # En el catálogo generan el mismo slug; se resuelven por distrito en
    # la segmentación. Aquí se registran variantes conocidas del PO.
    "san_juan_mixtepec_dto_26": "san_juan_mixtepec__209",
    "san_juan_mixtepec_dto_08": "san_juan_mixtepec__208",
    "san_pedro_mixtepec_dto_22": "san_pedro_mixtepec__318",
    "san_pedro_mixtepec_dto_26": "san_pedro_mixtepec__319",
}

# Municipios homónimos: slug → lista de (cve_mun, distrito_típico)
# Para resolución por distrito en la segmentación.
HOMONIMOS: dict[str, list[tuple[str, str]]] = {
    "san_juan_mixtepec": [("208", "Juxtlahuaca"), ("209", "Miahuatlán")],
    "san_pedro_mixtepec": [("318", "Juquila"), ("319", "Miahuatlán")],
}


# ── Distritos de Oaxaca (30 distritos judiciales) ──
DISTRITOS = [
    "Centro", "Coixtlahuaca", "Cuicatlán", "Ejutla", "Etla",
    "Huajuapam", "Ixtlán", "Jamiltepec", "Juchitán", "Juquila",
    "Juxtlahuaca", "Miahuatlán", "Mixe", "Nochixtlán", "Ocotlán",
    "Pochutla", "Putla", "Silacayoapam", "Sola de Vega", "Tehuantepec",
    "Teotitlán", "Teposcolula", "Tlacolula", "Tlaxiaco", "Tuxtepec",
    "Villa Alta", "Yautepec", "Zaachila", "Zimatlán",
]


# ═══════════════════════════════════════════════════
# Carga de municipios desde catálogo INEGI compartido
# ═══════════════════════════════════════════════════

def _norm(s: str) -> str:
    """Normaliza nombre a slug: quita acentos, lowercase, guiones bajos."""
    s = s.strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


# Cache (se puebla en load_municipios)
_MUNICIPIOS: list[tuple[str, str, str]] | None = None
_SLUG_TO_CVE: dict[str, tuple[str, str]] = {}
_NAME_TO_SLUG: dict[str, str] = {}


def load_municipios(
    catalog_path: Path | None = None,
) -> list[tuple[str, str, str]]:
    """
    Carga los 570 municipios de Oaxaca desde catalogs/municipios_inegi.csv.

    Filtra por CVE_ENT == "20" y construye:
      - MUNICIPIOS: [(cve_mun, nombre_oficial, slug), ...]
      - SLUG_TO_CVE: {slug: (cve_mun, nombre_oficial)}
      - NAME_TO_SLUG: {NOMBRE_UPPER: slug}

    Returns:
        Lista de tuplas (cve_mun, nombre_oficial, slug).
    """
    global _MUNICIPIOS, _SLUG_TO_CVE, _NAME_TO_SLUG
    if _MUNICIPIOS is not None:
        return _MUNICIPIOS

    path = catalog_path or CATALOG_PATH
    if not path.exists():
        raise FileNotFoundError(
            f"Catálogo INEGI no encontrado: {path}\n"
            f"Debe existir catalogs/municipios_inegi.csv en la raíz del proyecto."
        )

    munis: list[tuple[str, str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cve_ent = (row.get("CVE_ENT") or "").strip().strip('"')
            if cve_ent != CVE_ENT:
                continue
            cve_mun = (row.get("CVE_MUN") or "").strip().strip('"')
            nom = (row.get("NOM_MUN") or "").strip().strip('"')
            slug = _norm(nom)
            munis.append((cve_mun, nom, slug))

    munis.sort(key=lambda x: x[0])
    _MUNICIPIOS = munis

    _SLUG_TO_CVE.clear()
    _NAME_TO_SLUG.clear()
    for cve, nom, slug in munis:
        if slug in _SLUG_TO_CVE:
            # Colisión de slug (ej: San Juan Mixtepec ×2).
            # Guardar con sufijo __cve para disambiguar.
            existing_cve, existing_nom = _SLUG_TO_CVE[slug]
            _SLUG_TO_CVE[f"{slug}__{existing_cve}"] = (existing_cve, existing_nom)
            _SLUG_TO_CVE[f"{slug}__{cve}"] = (cve, nom)
            # El slug sin sufijo apunta al primero (por cve); en la
            # segmentación se resuelve por distrito vía HOMONIMOS.
        else:
            _SLUG_TO_CVE[slug] = (cve, nom)
        _NAME_TO_SLUG[nom.upper()] = slug

    return _MUNICIPIOS


def get_slug_to_cve() -> dict[str, tuple[str, str]]:
    if not _SLUG_TO_CVE:
        load_municipios()
    return _SLUG_TO_CVE


def get_name_to_slug() -> dict[str, str]:
    if not _NAME_TO_SLUG:
        load_municipios()
    return _NAME_TO_SLUG