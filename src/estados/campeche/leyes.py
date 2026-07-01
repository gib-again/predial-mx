"""
Lectura de la Ley de Hacienda de los Municipios del Estado de Campeche (PDF
digital) y extraccion del bloque de tarifa de predial de un municipio.

El Articulo 26 trae UNA tabla con todos los municipios; cada bloque es:

    {MUNICIPIO}
    URBANOS: Habitacional   X%
    Comercial y de Servicios Y%
    Industrial              Y%
    Baldios                 Z%
    Preservacion Ecologica  W%
    RUSTICOS: Terrenos Explotados   A%
    Terrenos Inexplotados           B%

Se localiza la tabla (encabezado "TARIFAS") y se recorta el bloque desde el
encabezado del municipio hasta el siguiente municipio (o fin de tabla).
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

import pdfplumber

from src.estados.campeche import config

LEYES_DIR = Path("data") / config.ESTADO_SLUG


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s)
                   if unicodedata.category(c) != "Mn")


def doc_text(version_id: str) -> str | None:
    rel = config.VERSIONES_DOC.get(version_id)
    if not rel:
        return None
    p = LEYES_DIR / rel
    if not p.exists():
        return None
    with pdfplumber.open(str(p)) as pdf:
        return "".join((pg.extract_text() or "") + "\n" for pg in pdf.pages)


# Encabezados de municipio en la tabla (todos, para delimitar bloques).
_ALL_MUNI_HEADERS = [tabla for _c, _n, _s, tabla in config.MUNICIPIOS]


def _tarifa_region(full: str) -> str:
    """Aisla la tabla de tarifas del Impuesto Predial (Art. 26).

    Ancla en el encabezado de la tabla ("MUNICIPIO ... USOS ... SUELO ... TASA"),
    que es unico de la tabla predial (evita la tabla de tarifas de agua), y
    termina en la siguiente seccion ("DEL PAGO").
    """
    U = _strip_accents(full).upper()
    m = re.search(r"MUNICIPIO\s+USOS?\s+DE[L]?\s+SUELO\s+TASA", U)
    if not m:
        # Respaldo: el chapeau del impuesto predial.
        m = re.search(r"EL\s+IMPUESTO\s+PREDIAL\s+SE\s+PAGARA\s+APLICANDO", U)
    if not m:
        return full
    start = m.start()
    end = U.find("DEL PAGO", start + 50)
    return full[start: end if end > start else start + 8000]


# Lineas de encabezado/pie de pagina repetidas que parten los bloques.
_BOILERPLATE = re.compile(
    r"(?im)^\s*(?:\d{1,3}|LEGISLACI[OÓ]N ESTATAL|LEY DE HACIENDA DE LOS MUNICIPIOS"
    r"[^\n]*|Documento de consulta[^\n]*|P\.?O\.?E\.?[^\n]*)\s*$"
)


def _clean_region(region: str) -> str:
    """Quita encabezados/pies de pagina que parten los bloques de municipio."""
    return _BOILERPLATE.sub("", region)


def municipio_block(version_id: str, tabla_nombre: str) -> str | None:
    """Bloque de tarifa del municipio `tabla_nombre` en la version dada."""
    full = doc_text(version_id)
    if not full:
        return None
    region = _clean_region(_tarifa_region(full))
    region_norm = _strip_accents(region).upper()
    target = _strip_accents(tabla_nombre).upper().strip()

    # Posiciones de todos los encabezados de municipio en la region.
    positions: list[tuple[int, str]] = []
    for tabla in _ALL_MUNI_HEADERS:
        t = _strip_accents(tabla).upper().strip()
        # Encabezado = nombre del muni en su propia linea, seguido de "URBANOS".
        for mm in re.finditer(rf"(?m)^\s*{re.escape(t)}\s*$", region_norm):
            # Confirmar que es un encabezado de bloque (URBANOS cerca debajo).
            if "URBANOS" in region_norm[mm.start(): mm.start() + 120]:
                positions.append((mm.start(), t))
    if not positions:
        return None
    positions.sort()

    # Localizar el bloque del target y su fin (siguiente encabezado).
    for i, (pos, name) in enumerate(positions):
        if name == target:
            end = positions[i + 1][0] if i + 1 < len(positions) else len(region)
            return region[pos:end].strip()
    return None


def predial_focus(slug: str, version_id: str) -> str | None:
    """Texto focus para (municipio, version): bloque de tarifa + contexto."""
    tabla = config.TABLA_NOMBRE[slug]
    blk = municipio_block(version_id, tabla)
    if not blk:
        return None
    header = (
        "Impuesto Predial — Ley de Hacienda de los Municipios del Estado de "
        "Campeche, Artículo 26. Tarifa del municipio, en PORCENTAJE sobre el "
        "valor catastral, diferenciada por uso de suelo.\n\n"
    )
    return header + blk
