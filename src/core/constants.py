"""Constantes globales del proyecto predial-mx."""

from pathlib import Path

EJERCICIO_INI = 2010
EJERCICIO_FIN = 2025  # inclusive

# ── Rutas del corpus v3 ──
# El corpus v3 vive bajo data/{estado}/json_predial/{anio}/ (layout por año,
# espeja focus_predial/{anio}/).  Las correcciones HITL viven en un overlay
# paralelo json_predial_hitl/{anio}/ (se conservan los originales).  Centralizar
# aquí evita que cada módulo hardcodee la ruta.
DATA_ROOT = Path("data")


def json_predial_dir(estado: str, anio) -> Path:
    """Directorio del corpus v3 canónico para un estado-año."""
    return DATA_ROOT / estado / "json_predial" / str(anio)


def json_predial_hitl_dir(estado: str, anio) -> Path:
    """Directorio del overlay HITL-corregido para un estado-año."""
    return DATA_ROOT / estado / "json_predial_hitl" / str(anio)


def json_predial_root(estado: str) -> Path:
    """Raíz del corpus v3 de un estado (todas las carpetas por año)."""
    return DATA_ROOT / estado / "json_predial"


def json_predial_hitl_root(estado: str) -> Path:
    """Raíz del overlay HITL-corregido de un estado."""
    return DATA_ROOT / estado / "json_predial_hitl"

# Prefijos por estado para nombres de archivo
PREFIJOS_ESTADO = {
    "aguascalientes": "AGS",
    "coahuila":  "COAH",
    "jalisco":   "JAL",
    "queretaro": "QRO",
    "yucatan":   "YUC",
    "tamaulipas": "TAMPS",
    "chihuahua": "CHIH",
    "guanajuato": "GTO",
    "sanluispotosi": "SLP",
    "sonora":     "SON",
    "oaxaca":     "OAX",
}

# Clave de entidad INEGI (2 dígitos) por estado.  Junto con la CVE_MUN (3
# dígitos) forma el CVEGEO de 5 dígitos, la llave canónica de identidad
# municipal en todos los artefactos (segment.csv, JSON v3, cola HITL).
# Fuente: src/estados/{slug}/config.py (CVE_ENT).
CVE_ENT_ESTADO = {
    "aguascalientes": "01",
    "coahuila":  "05",
    "colima":    "06",
    "chihuahua": "08",
    "guanajuato": "11",
    "jalisco":   "14",
    "edomex":    "15",
    "oaxaca":    "20",
    "queretaro": "22",
    "sanluispotosi": "24",
    "sinaloa":   "25",
    "sonora":    "26",
    "tabasco":   "27",
    "tamaulipas": "28",
    "yucatan":   "31",
}
