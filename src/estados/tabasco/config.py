"""
Configuración específica de Tabasco.

17 municipios. Ley de Hacienda Municipal del Estado de Tabasco, Art. 87-105.
Tarifa estatal uniforme (Art. 94): 5 rangos progresivos, cuota fija en pesos,
tasa porcentual sobre excedente del límite inferior.

Base gravable: valor FISCAL = valor catastral × porcentaje fiscal por zona
  (porcentaje fiscal ≥ 20%, determinado por cada Cabildo, Art. 90).

La tabla del Art. 94 (reformada P.O. 30-dic-1995) NO ha cambiado en el periodo
2010-2025. Los rangos y cuotas permanecen fijos en pesos nominales.

Reforma relevante: P.O. 7808, 05-jul-2017 → cambio de SM a UMA para el
impuesto mínimo anual (Art. 98), no afecta la tabla del Art. 94.

Mínimos anuales (Art. 98):
  - Rústico: 3 v.d.u.m.a. (antes 2017: 3 SM diarios)
  - Urbano: 4 v.d.u.m.a. (antes 2017: 4 SM diarios)

Sobretasa baldíos urbanos (Art. 97): 0-30%, propuesta por Cabildo, aprobada
  por Congreso del Estado.
"""

from __future__ import annotations

ESTADO_SLUG = "tabasco"
PREFIJO = "TAB"
ESTADO_NOMBRE = "Tabasco"
CVE_ENT = "27"
NEEDS_OCR = False  # Tarifa hardcoded de la Ley de Hacienda Municipal

YEAR_MIN = 2010
YEAR_MAX = 2025

# Año a partir del cual el mínimo anual se expresa en UMA (reforma P.O. 7808).
YEAR_CAMBIO_UMA = 2017

# ── 17 municipios de Tabasco ───────────────────────────────
# Fuente: INEGI catálogo AGEEML (CVE_ENT=27).
MUNICIPIOS: list[tuple[str, str, str]] = [
    ("001", "Balancán", "balancan"),
    ("002", "Cárdenas", "cardenas"),
    ("003", "Centla", "centla"),
    ("004", "Centro", "centro"),
    ("005", "Comalcalco", "comalcalco"),
    ("006", "Cunduacán", "cunduacan"),
    ("007", "Emiliano Zapata", "emiliano_zapata"),
    ("008", "Huimanguillo", "huimanguillo"),
    ("009", "Jalapa", "jalapa"),
    ("010", "Jalpa de Méndez", "jalpa_de_mendez"),
    ("011", "Jonuta", "jonuta"),
    ("012", "Macuspana", "macuspana"),
    ("013", "Nacajuca", "nacajuca"),
    ("014", "Paraíso", "paraiso"),
    ("015", "Tacotalpa", "tacotalpa"),
    ("016", "Teapa", "teapa"),
    ("017", "Tenosique", "tenosique"),
]

# ── Series para impuesto mínimo ─────────────────────────────
# SM diario zona C/general aplicable a Tabasco (2010-2016).
SM_DIARIO: dict[int, float] = {
    2010: 54.47,
    2011: 56.70,
    2012: 59.08,
    2013: 61.38,
    2014: 63.77,
    2015: 68.28,
    2016: 73.04,
}

# UMA diaria (2017-2025).
UMA_DIARIA: dict[int, float] = {
    2017: 75.49,
    2018: 80.60,
    2019: 84.49,
    2020: 86.88,
    2021: 89.62,
    2022: 96.22,
    2023: 103.74,
    2024: 108.57,
    2025: 113.14,
}


def minimo_anual(ejercicio: int, tipo: str = "urbano") -> tuple[float, str]:
    """
    Retorna (monto_pesos, unidad) del impuesto mínimo anual.
    tipo: 'urbano' (4×) o 'rustico' (3×).
    """
    multiplicador = 4 if tipo == "urbano" else 3
    if ejercicio < YEAR_CAMBIO_UMA:
        valor = SM_DIARIO[ejercicio]
        return round(multiplicador * valor, 2), "SM_diario"
    else:
        valor = UMA_DIARIA[ejercicio]
        return round(multiplicador * valor, 2), "UMA_diaria"
