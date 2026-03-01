"""
Configuración específica de Colima.

10 municipios, cada uno con Ley de Hacienda municipal propia (Decretos 268-277, 2002).
Tablas de predial idénticas en los 10 municipios para el periodo 2010-2025.
Reforma clave: Decreto 133 (22-nov-2016) → cambia SM a UMA como unidad de cuota fija.

Excepción: Manzanillo actualizó su tabla en dic-2025 (aplica desde ejercicio 2026,
fuera del periodo de análisis).
"""

from __future__ import annotations

ESTADO_SLUG = "colima"
PREFIJO = "COL"
ESTADO_NOMBRE = "Colima"
CVE_ENT = "06"
NEEDS_OCR = False  # Tarifa hardcoded, tablas idénticas en los 10 municipios

YEAR_MIN = 2010
YEAR_MAX = 2025

# Año a partir del cual la cuota fija se expresa en UMA (reforma Decreto 133).
# Ejercicios 2010-2016: cuota fija × SM diario vigente en la zona.
# Ejercicios 2017-2025: cuota fija × UMA diaria vigente.
YEAR_CAMBIO_UMA = 2017

# ── 10 municipios de Colima ─────────────────────────────────
# Fuente: INEGI catálogo AGEEML (CVE_ENT=06).
# Tupla: (cve_mun, nombre_oficial, slug)
MUNICIPIOS: list[tuple[str, str, str]] = [
    ("001", "Armería", "armeria"),
    ("002", "Colima", "colima"),
    ("003", "Comala", "comala"),
    ("004", "Coquimatlán", "coquimatlan"),
    ("005", "Cuauhtémoc", "cuauhtemoc"),
    ("006", "Ixtlahuacán", "ixtlahuacan"),
    ("007", "Manzanillo", "manzanillo"),
    ("008", "Minatitlán", "minatitlan"),
    ("009", "Tecomán", "tecoman"),
    ("010", "Villa de Álvarez", "villa_de_alvarez"),
]

# ── Series de conversión ────────────────────────────────────
# SM diario zona C / zona general aplicable a Colima (2010-2016).
SM_DIARIO: dict[int, float] = {
    2010: 54.47,
    2011: 56.70,
    2012: 59.08,
    2013: 61.38,
    2014: 63.77,
    2015: 68.28,
    2016: 73.04,
}

# UMA diaria (2016-2026). Para el cálculo de cuotas 2017-2025.
UMA_DIARIA: dict[int, float] = {
    2016: 73.04,
    2017: 75.49,
    2018: 80.60,
    2019: 84.49,
    2020: 86.88,
    2021: 89.62,
    2022: 96.22,
    2023: 103.74,
    2024: 108.57,
    2025: 113.14,
    2026: 117.31,
}


def factor_conversion(ejercicio: int) -> tuple[float, str]:
    """Retorna (valor_pesos, unidad) para convertir cuota fija a pesos."""
    if ejercicio < YEAR_CAMBIO_UMA:
        return SM_DIARIO[ejercicio], "SM_diario"
    else:
        return UMA_DIARIA[ejercicio], "UMA_diaria"
