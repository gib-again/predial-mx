"""
Tarifa base del impuesto predial de Colima.

Fuente: Ley de Hacienda para el Municipio de Colima (y los demás 9 municipios).
  Art. 13, reformado por Decreto 133 (P.O. 73, Sup. 3, 22-nov-2016).
  Tablas idénticas en los 10 municipios para el periodo 2010-2025.

Estructura:
  I. Predios urbanos edificados: tarifa progresiva (26 rangos).
     Cuota fija en UMA (o SM pre-2017) + tasa marginal sobre excedente.
  II. Predios urbanos NO edificados (baldíos): tasa fija 0.006 (6 al millar).
  III. Predios rústicos: tarifa progresiva (9 rangos).
  IV. Parcelas ejidales: cuota fija de 3 UMA (o SM) anuales.

Nota: Manzanillo actualizó su tabla en dic-2025, aplicable desde ejercicio 2026
(fuera del periodo de análisis 2010-2025).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RangoPredial:
    """Un rango de la tarifa progresiva Art. 13."""
    numero: int
    lim_inf: float          # Límite inferior (pesos de base gravable)
    lim_sup: Optional[float]  # Límite superior (None = en adelante)
    cuota_fija_uma: float   # Cuota fija en UMA (o SM pre-2017)
    tasa_marginal: float    # Tasa sobre excedente del límite inferior


# ══════════════════════════════════════════════════════════════
# Art. 13, fracción I — Predios urbanos edificados (26 rangos)
# ══════════════════════════════════════════════════════════════

TARIFA_URBANO_EDIFICADO: list[RangoPredial] = [
    RangoPredial( 1,         0,    40_400,  2.00, 0.0000000),
    RangoPredial( 2,    40_401,    48_400,  2.00, 0.0005525),
    RangoPredial( 3,    48_401,    58_400,  2.55, 0.0005850),
    RangoPredial( 4,    58_401,    68_400,  3.25, 0.0006175),
    RangoPredial( 5,    68_401,    72_000,  4.00, 0.0006500),
    RangoPredial( 6,    72_001,   122_000,  4.43, 0.0006825),
    RangoPredial( 7,   122_001,   172_000,  7.85, 0.0007150),
    RangoPredial( 8,   172_001,   222_000, 11.57, 0.0007475),
    RangoPredial( 9,   222_001,   288_000, 15.38, 0.0007800),
    RangoPredial(10,   288_001,   338_000, 21.06, 0.0008125),
    RangoPredial(11,   338_001,   388_000, 25.70, 0.0008450),
    RangoPredial(12,   388_001,   438_000, 30.64, 0.0008775),
    RangoPredial(13,   438_001,   480_000, 35.86, 0.0009100),
    RangoPredial(14,   480_001,   560_000, 40.41, 0.0009425),
    RangoPredial(15,   560_001,   640_000, 49.13, 0.0009750),
    RangoPredial(16,   640_001,   720_000, 58.02, 0.0010075),
    RangoPredial(17,   720_001,   800_000, 67.37, 0.0010400),
    RangoPredial(18,   800_001,   880_000, 77.23, 0.0010725),
    RangoPredial(19,   880_001,   960_000, 87.53, 0.0011050),
    RangoPredial(20,   960_001, 1_040_000, 98.29, 0.0011375),
    RangoPredial(21, 1_040_001, 1_120_000, 109.52, 0.0011700),
    RangoPredial(22, 1_120_001, 1_200_000, 121.21, 0.0012025),
    RangoPredial(23, 1_200_001, 1_280_000, 133.38, 0.0012350),
    RangoPredial(24, 1_280_001, 1_360_000, 146.01, 0.0012675),
    RangoPredial(25, 1_360_001, 1_440_000, 159.11, 0.0013000),
    RangoPredial(26, 1_440_001,      None, 173.00, 0.0020010),
]

# ══════════════════════════════════════════════════════════════
# Art. 13, fracción II — Predios urbanos NO edificados (baldíos)
# ══════════════════════════════════════════════════════════════
TASA_BALDIO = 0.006  # 6 al millar

# ══════════════════════════════════════════════════════════════
# Art. 13, fracción III — Predios rústicos (9 rangos)
# ══════════════════════════════════════════════════════════════

TARIFA_RUSTICO: list[RangoPredial] = [
    RangoPredial(1,      0,  9_600, 3.00, 0.000000),
    RangoPredial(2,  9_601, 12_400, 3.00, 0.003510),
    RangoPredial(3, 12_401, 14_400, 4.00, 0.003575),
    RangoPredial(4, 14_401, 16_400, 4.72, 0.003640),
    RangoPredial(5, 16_401, 18_400, 5.47, 0.003705),
    RangoPredial(6, 18_401, 20_400, 6.25, 0.003770),
    RangoPredial(7, 20_401, 22_000, 7.04, 0.003835),
    RangoPredial(8, 22_001, 24_000, 7.86, 0.003900),
    RangoPredial(9, 24_001,   None, 8.43, 0.004000),
]

# ══════════════════════════════════════════════════════════════
# Art. 13, fracción IV — Parcelas ejidales
# ══════════════════════════════════════════════════════════════
CUOTA_EJIDAL_UMA = 3.0  # 3 UMA (o SM) anuales


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
    factor_uma: float,
) -> float:
    """
    Calcula impuesto predial con tarifa progresiva.
    factor_uma: valor en pesos de 1 UMA (o SM) para convertir cuota fija.
    """
    rango = _ubicar_rango(valor_catastral, tabla)
    cuota_pesos = rango.cuota_fija_uma * factor_uma
    excedente = max(0, valor_catastral - rango.lim_inf)
    return cuota_pesos + excedente * rango.tasa_marginal


def calcular_urbano_edificado(valor_catastral: float, factor_uma: float) -> float:
    return calcular_predial(valor_catastral, TARIFA_URBANO_EDIFICADO, factor_uma)


def calcular_baldio(valor_catastral: float) -> float:
    return valor_catastral * TASA_BALDIO


def calcular_rustico(valor_catastral: float, factor_uma: float) -> float:
    return calcular_predial(valor_catastral, TARIFA_RUSTICO, factor_uma)


def calcular_ejidal(factor_uma: float) -> float:
    return CUOTA_EJIDAL_UMA * factor_uma
