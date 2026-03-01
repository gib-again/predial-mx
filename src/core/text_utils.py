"""
Normalización de texto, slugify, y parseo de montos.

Consolida funciones duplicadas:
  - norm()                → 03, 04, 10 (variantes con unidecode)
  - normalize_text()      → 01 (variante con unicodedata)
  - slugify()             → 01, 10
  - parse_monto_to_float() → 25
  - parse_filename()      → 20, 25 (generalizada para cualquier prefijo)
"""

import re
import unicodedata
from pathlib import Path

from unidecode import unidecode


# ── Normalización de texto ──

def norm(s: str) -> str:
    """
    Normaliza texto para matching: sin acentos, mayúsculas, stripped.

    Usa unidecode que es más robusto que unicodedata para español
    (maneja ñ → N, ü → U, etc.)
    """
    return unidecode((s or "").strip()).upper()


def norm_light(s: str) -> str:
    """
    Normalización ligera: sin acentos, minúsculas.
    Útil para búsquedas donde se quiere preservar la legibilidad.

    Equivalente a normalize_text() del script 01.
    """
    if s is None:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


# ── Slugify ──

def slugify(s: str) -> str:
    """
    Convierte nombre de municipio a slug filesystem-safe.

    Ej: "San Pedro de las Colonias" → "san_pedro_de_las_colonias"
    """
    n = norm(s)
    slug = (
        n.replace(" ", "_")
         .replace("/", "_")
         .replace(".", "")
         .replace(",", "")
         .lower()
    )
    return slug or "sin_municipio"


# ── Parseo de nombres de archivo ──

def parse_predial_filename(path: Path, prefijo: str) -> tuple[int, str, str]:
    """
    Parsea nombre de archivo de predial y extrae año, slug y nombre bonito.

    Formato esperado: {PREFIJO}_PREDIAL_{ANIO}_{slug}.{ext}
    Ejemplo: COAH_PREDIAL_2016_saltillo.txt → (2016, "saltillo", "Saltillo")

    Generaliza parse_filename() de scripts 20 y 25, que estaban
    hardcodeados a "COAH".

    Args:
        path: Ruta al archivo.
        prefijo: Prefijo del estado (ej: "COAH", "JAL").

    Returns:
        Tupla (anio, slug_municipio, nombre_municipio_pretty).

    Raises:
        ValueError: Si el nombre no sigue el formato esperado.
    """
    stem = path.stem
    parts = stem.split("_")

    # Mínimo: PREFIJO_PREDIAL_ANIO_slug (4 partes)
    if len(parts) < 4:
        raise ValueError(f"Nombre de archivo con menos de 4 partes: {stem}")

    if parts[0] != prefijo:
        raise ValueError(f"Prefijo esperado '{prefijo}', encontrado '{parts[0]}' en: {stem}")

    if parts[1] != "PREDIAL":
        raise ValueError(f"Se esperaba 'PREDIAL' como segunda parte, encontrado '{parts[1]}' en: {stem}")

    try:
        anio = int(parts[2])
    except ValueError:
        raise ValueError(f"Año no numérico '{parts[2]}' en: {stem}")

    slug = "_".join(parts[3:])
    nombre_mpio = " ".join(w.capitalize() for w in slug.split("_"))

    return anio, slug, nombre_mpio


# ── Parseo de montos monetarios ──

def parse_monto_to_float(monto_str) -> float | None:
    """
    Convierte strings de montos a float, manejando ambos formatos:

    Formato US:      '$620,100.00'  → 620100.00
    Formato europeo: '$183.818,00'  → 183818.00
    Miles sin dec.:  '60,000'       → 60000.0
    Decimal europeo: '$0,01'        → 0.01

    Originalmente en 25_json_consistency.py líneas 65-133.

    Returns:
        float si se pudo parsear, None si no.
    """
    if monto_str is None:
        return None

    # Si ya es número, devolver directo
    if isinstance(monto_str, (int, float)):
        return float(monto_str)

    s = str(monto_str).strip()

    # Quedarnos solo con dígitos, coma, punto y signo menos
    s = re.sub(r"[^0-9,.\-]", "", s)

    # Si no queda ningún dígito, no se puede parsear
    if not re.search(r"\d", s):
        return None

    has_dot = "." in s
    has_comma = "," in s

    if has_dot and has_comma:
        # Caso mixto: determinar cuál es separador decimal
        last_dot = s.rfind(".")
        if last_dot < s.rfind(","):
            # Formato europeo: 1.234,56 → quitar puntos, coma → punto
            s = s.replace(".", "").replace(",", ".")
        else:
            # Formato US: 1,234.56 → quitar comas
            s = s.replace(",", "")

    elif has_comma and not has_dot:
        if s.count(",") > 1:
            # Múltiples comas → separador de miles europeo
            s = s.replace(".", "").replace(",", ".")
        else:
            left, right = s.split(",")
            if len(right) in (1, 2):
                # Decimal europeo: 0,01 → 0.01
                s = s.replace(".", "").replace(",", ".")
            else:
                # Miles US sin decimales: 60,000 → 60000
                s = s.replace(",", "")
    else:
        # Solo punto o nada
        s = s.replace(",", "")

    try:
        return float(s)
    except (ValueError, OverflowError):
        return None
