"""
Tarifa base del impuesto predial del Estado de México.

Fuente: Código Financiero del Estado de México y Municipios, Art. 109.
  - Tabla 2009 (G.G. 26-dic-2007): aplica al ejercicio 2010.
  - Tabla 2010 (G.G. 21-dic-2010): rangos 1-3 reformados, aplica ejercicios 2011-2025.
  - Tabla 2025 (G.G. dic-2025): aplica desde ejercicio 2026 (fuera del periodo,
    incluida como referencia).

Estructura: 13 rangos progresivos.
  Impuesto = cuota_fija + (valor_catastral − lím_inferior) × factor
  Cuota fija expresada en pesos nominales (no requiere conversión UMA/SM).

Baldíos urbanos >200 m²: +15% sobre monto total (desde ejercicio 2017,
  reforma G.G. 28-nov-2016).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RangoPredial:
    """Un rango de la tarifa progresiva Art. 109."""
    numero: int
    lim_inf: float           # Límite inferior (pesos)
    lim_sup: Optional[float] # Límite superior (None = en adelante)
    cuota_fija: float        # Cuota fija en pesos nominales
    factor: float            # Factor sobre excedente del límite inferior


# ══════════════════════════════════════════════════════════════
# Tabla 2009 — G.G. 26-dic-2007 (aplica ejercicio 2010)
# ══════════════════════════════════════════════════════════════

TARIFA_2009: list[RangoPredial] = [
    RangoPredial( 1,         1,   180_970,   150.00, 0.000330),
    RangoPredial( 2,   180_971,   343_840,   210.00, 0.001287),
    RangoPredial( 3,   343_841,   554_420,   420.00, 0.001541),
    RangoPredial( 4,   554_421,   763_890,   745.00, 0.001788),
    RangoPredial( 5,   763_891,   973_930, 1_120.00, 0.002283),
    RangoPredial( 6,   973_931, 1_188_880, 1_600.00, 0.002673),
    RangoPredial( 7, 1_188_881, 1_403_840, 2_175.00, 0.003371),
    RangoPredial( 8, 1_403_841, 1_618_840, 2_900.00, 0.003905),
    RangoPredial( 9, 1_618_841, 1_854_060, 3_740.00, 0.004228),
    RangoPredial(10, 1_854_061, 2_100_310, 4_735.00, 0.004506),
    RangoPredial(11, 2_100_311, 2_433_150, 5_845.00, 0.004670),
    RangoPredial(12, 2_433_151, 2_780_990, 7_400.00, 0.004943),
    RangoPredial(13, 2_780_991,      None, 9_120.00, 0.003500),
]

# ══════════════════════════════════════════════════════════════
# Tabla 2010 — G.G. 21-dic-2010 (aplica ejercicios 2011-2025)
# Rangos 1-3 reformados en cuota fija y factor; rangos 4-13 sin cambio.
# ══════════════════════════════════════════════════════════════

TARIFA_2010: list[RangoPredial] = [
    RangoPredial( 1,         1,   180_970,   170.00, 0.000331),
    RangoPredial( 2,   180_971,   343_840,   230.00, 0.001350),
    RangoPredial( 3,   343_841,   554_420,   450.00, 0.001400),
    RangoPredial( 4,   554_421,   763_890,   745.00, 0.001788),
    RangoPredial( 5,   763_891,   973_930, 1_120.00, 0.002283),
    RangoPredial( 6,   973_931, 1_188_880, 1_600.00, 0.002673),
    RangoPredial( 7, 1_188_881, 1_403_840, 2_175.00, 0.003371),
    RangoPredial( 8, 1_403_841, 1_618_840, 2_900.00, 0.003905),
    RangoPredial( 9, 1_618_841, 1_854_060, 3_740.00, 0.004228),
    RangoPredial(10, 1_854_061, 2_100_310, 4_735.00, 0.004506),
    RangoPredial(11, 2_100_311, 2_433_150, 5_845.00, 0.004670),
    RangoPredial(12, 2_433_151, 2_780_990, 7_400.00, 0.004943),
    RangoPredial(13, 2_780_991,      None, 9_120.00, 0.003500),
]

# ══════════════════════════════════════════════════════════════
# Tabla 2025 — aplica desde ejercicio 2026 (nice-to-have)
# Todos los rangos actualizados en cuota fija y factor.
# ══════════════════════════════════════════════════════════════

TARIFA_2025: list[RangoPredial] = [
    RangoPredial( 1,         1,   180_970,   176.00, 0.000342),
    RangoPredial( 2,   180_971,   343_840,   238.00, 0.001399),
    RangoPredial( 3,   343_841,   554_420,   466.00, 0.001447),
    RangoPredial( 4,   554_421,   763_890,   771.00, 0.001850),
    RangoPredial( 5,   763_891,   973_930, 1_159.00, 0.002364),
    RangoPredial( 6,   973_931, 1_188_880, 1_656.00, 0.002766),
    RangoPredial( 7, 1_188_881, 1_403_840, 2_251.00, 0.003492),
    RangoPredial( 8, 1_403_841, 1_618_840, 3_002.00, 0.004045),
    RangoPredial( 9, 1_618_841, 1_854_060, 3_872.00, 0.004381),
    RangoPredial(10, 1_854_061, 2_100_310, 4_903.00, 0.004668),
    RangoPredial(11, 2_100_311, 2_433_150, 6_053.00, 0.004841),
    RangoPredial(12, 2_433_151, 2_780_990, 7_665.00, 0.005124),
    RangoPredial(13, 2_780_991,      None, 9_448.00, 0.003628),
]

# ══════════════════════════════════════════════════════════════
# Tasa adicional para baldíos urbanos >200 m²
# ══════════════════════════════════════════════════════════════
TASA_ADICIONAL_BALDIO = 0.15  # 15% sobre monto total


# ══════════════════════════════════════════════════════════════
# Selección de tabla por ejercicio
# ══════════════════════════════════════════════════════════════

def tabla_para_ejercicio(ejercicio: int) -> tuple[list[RangoPredial], str]:
    """Retorna (tabla, etiqueta_reforma) para el ejercicio dado."""
    if ejercicio <= 2010:
        return TARIFA_2009, "G.G. 26-dic-2007"
    elif ejercicio <= 2025:
        return TARIFA_2010, "G.G. 21-dic-2010 (rangos 1-3 reformados)"
    else:
        return TARIFA_2025, "G.G. dic-2025"


# ══════════════════════════════════════════════════════════════
# Cálculo
# ══════════════════════════════════════════════════════════════

def _ubicar_rango(valor_catastral: float, tabla: list[RangoPredial]) -> RangoPredial:
    """Ubica el rango correspondiente al valor catastral."""
    rango = tabla[0]
    for r in tabla:
        if valor_catastral >= r.lim_inf:
            rango = r
        else:
            break
    return rango


def calcular_predial(
    valor_catastral: float,
    tabla: list[RangoPredial],
) -> float:
    """
    Calcula impuesto predial Art. 109.
    Impuesto = cuota_fija + (valor_catastral − lím_inferior) × factor
    """
    rango = _ubicar_rango(valor_catastral, tabla)
    excedente = max(0, valor_catastral - rango.lim_inf)
    return rango.cuota_fija + excedente * rango.factor


def calcular_con_baldio(
    valor_catastral: float,
    tabla: list[RangoPredial],
    es_baldio_mayor_200m2: bool = False,
    ejercicio: int = 2025,
) -> float:
    """Calcula predial con posible recargo de baldíos >200m²."""
    from src.estados.edomex.config import YEAR_BALDIO_15PCT
    impuesto = calcular_predial(valor_catastral, tabla)
    if es_baldio_mayor_200m2 and ejercicio >= YEAR_BALDIO_15PCT:
        impuesto *= (1 + TASA_ADICIONAL_BALDIO)
    return impuesto
