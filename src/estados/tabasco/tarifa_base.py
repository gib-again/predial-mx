"""
Tarifa base del impuesto predial de Tabasco.

Fuente: Ley de Hacienda Municipal del Estado de Tabasco, Art. 94.
  Reformada P.O. 30-dic-1995. Sin cambios en el periodo 2010-2025.

Estructura: 5 rangos progresivos sobre el VALOR FISCAL del predio.
  Impuesto = cuota_fija + (valor_fiscal − lím_inferior) × (porcentaje / 100)

Valor fiscal = valor catastral × porcentaje fiscal de zona (≥20%, Art. 90).

Cuota fija en pesos nominales (no UMA ni SM).

Particularidades:
  - Aplica tanto a predios urbanos como rústicos.
  - Baldíos urbanos/ruinosos: sobretasa 0-30% adicional (Art. 97).
  - Mínimo anual: rústico 3 UMA, urbano 4 UMA (Art. 98, post-2017).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RangoPredial:
    """Un rango de la tarifa progresiva Art. 94."""
    numero: int
    lim_inf: float              # Límite inferior (pesos)
    lim_sup: Optional[float]    # Límite superior (None = en adelante)
    cuota_fija: float           # Cuota fija (pesos nominales)
    tasa_pct: float             # Porcentaje sobre excedente del límite inferior


# ══════════════════════════════════════════════════════════════
# Art. 94 — Tarifa del Impuesto Predial (P.O. 30-dic-1995)
# Sin modificaciones 2010-2025.
# ══════════════════════════════════════════════════════════════

TARIFA_ART94: list[RangoPredial] = [
    RangoPredial(1,      0.00,  10_000.00,   0.00, 0.7),
    RangoPredial(2, 10_001.00,  30_000.00,  70.00, 0.8),
    RangoPredial(3, 30_001.00,  50_000.00, 230.00, 0.9),
    RangoPredial(4, 50_001.00,  70_000.00, 410.00, 1.0),
    RangoPredial(5, 70_001.00,       None, 610.00, 1.1),
]


# ══════════════════════════════════════════════════════════════
# Cálculo
# ══════════════════════════════════════════════════════════════

def _ubicar_rango(valor_fiscal: float, tabla: list[RangoPredial]) -> RangoPredial:
    rango = tabla[0]
    for r in tabla:
        if valor_fiscal >= r.lim_inf:
            rango = r
        else:
            break
    return rango


def calcular_predial(
    valor_fiscal: float,
    minimo: float = 0.0,
    sobretasa_baldio_pct: float = 0.0,
) -> float:
    """
    Calcula impuesto predial Art. 94.
    valor_fiscal: valor catastral × porcentaje fiscal de zona.
    minimo: impuesto mínimo anual (3 o 4 UMA/SM según tipo).
    sobretasa_baldio_pct: 0-30% adicional para baldíos urbanos (Art. 97).
    """
    rango = _ubicar_rango(valor_fiscal, TARIFA_ART94)
    excedente = max(0, valor_fiscal - rango.lim_inf)
    impuesto = rango.cuota_fija + excedente * (rango.tasa_pct / 100)

    # Aplicar sobretasa baldíos
    if sobretasa_baldio_pct > 0:
        impuesto *= (1 + sobretasa_baldio_pct / 100)

    # Aplicar mínimo
    return max(impuesto, minimo)
