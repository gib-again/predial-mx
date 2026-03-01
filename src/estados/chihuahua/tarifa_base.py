"""
Tarifa base del impuesto predial de Chihuahua.

Fuente: Código Municipal para el Estado de Chihuahua, Artículos 148-149.
  Publicado POE No. 92 del 18 de noviembre de 1995.
  Última Reforma POE 2026.01.24/No. 07
  URL: https://www.congresochihuahua2.gob.mx/biblioteca/codigos/archivosCodigos/70.pdf

Art. 148: Base = valor catastral (determinado por Ley de Catastro).

Art. 149: Tarifa progresiva por rangos.
  I. Predios urbanos: 5 rangos, tasas de 2 a 6 al millar.
  II. Predios rústicos: 2 al millar.
  III. Fundos mineros: 5 al millar.
  Mínimo: 2 UMA (desde 2018); antes: 2 salarios mínimos diarios.

Reformas relevantes:
  - Fracc. I reformada Decreto 107-07 (POE 103, 26-dic-2007): tabla actual.
  - Fracc. III reformada Decreto 515-05 (POE 105, 31-dic-2005): 5 al millar.
  - Párrafo mínimo reformado Decreto LXV/FRCLC/0266/2017 (POE 15, 22-feb-2017):
    cambia "salarios mínimos" → "Unidades de Medida y Actualización".

Aplica uniformemente a los 67 municipios en todo el periodo 2010-2025.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RangoPredial:
    """Un rango de la tarifa progresiva Art. 149 fracc. I."""
    numero: int
    lim_inf: float        # Límite inferior (pesos)
    tasa_millar: int       # Tasa al millar (2, 3, 4, 5, 6)
    cuota_fija: float      # Cuota fija (pesos)

    @property
    def tasa(self) -> float:
        return self.tasa_millar / 1000.0


# ══════════════════════════════════════════════════════════════
# Art. 149, fracción I — Predios urbanos (5 rangos)
# ══════════════════════════════════════════════════════════════
#
# ┌───────────┬──────────────┬──────────────┐
# │ Límite    │ Tasa rango   │ Cuota fija   │
# ├───────────┼──────────────┼──────────────┤
# │         0 │ 2 al millar  │         0.00 │
# │   183,240 │ 3 al millar  │       366.48 │
# │   366,480 │ 4 al millar  │       916.20 │
# │   641,340 │ 5 al millar  │     2,015.64 │
# │ 1,282,680 │ 6 al millar  │     5,222.34 │
# └───────────┴──────────────┴──────────────┘
#
# Fórmula: (Valor catastral − límite inferior) × tasa + cuota fija

TARIFA_URBANA: list[RangoPredial] = [
    RangoPredial(1,         0,  2,     0.00),
    RangoPredial(2,   183_240,  3,   366.48),
    RangoPredial(3,   366_480,  4,   916.20),
    RangoPredial(4,   641_340,  5, 2_015.64),
    RangoPredial(5, 1_282_680,  6, 5_222.34),
]

# ── Art. 149-II — Predios rústicos ───────────────────────────
TASA_RUSTICO_MILLAR = 2
TASA_RUSTICO = 0.002

# ── Art. 149-III — Fundos mineros ────────────────────────────
TASA_MINERO_MILLAR = 5
TASA_MINERO = 0.005

# ── Art. 149, último párrafo — Mínimo ────────────────────────
# Desde 2018: "2 Unidades de Medida y Actualización" (diarias).
# Antes de 2018: "2 salarios mínimos" (diarios).
MINIMO_FACTOR = 2
MINIMO_CAMBIO_UMA_YEAR = 2018

# ── Suburbano (leyes de ingresos municipales, no Código) ─────
TASA_SUBURBANO_MILLAR = 3
TASA_SUBURBANO = 0.003

# ── Adicional UACH (leyes de ingresos, no Código) ───────────
TASA_ADICIONAL_UACH = 0.04


# ══════════════════════════════════════════════════════════════
# Cálculo
# ══════════════════════════════════════════════════════════════

def calcular_predial_urbano(valor_catastral: float) -> float:
    """
    Calcula impuesto predial urbano Art. 149-I.
    NO aplica mínimo ni adicional.
    """
    rango = TARIFA_URBANA[0]
    for r in TARIFA_URBANA:
        if valor_catastral >= r.lim_inf:
            rango = r
        else:
            break
    excedente = valor_catastral - rango.lim_inf
    return rango.cuota_fija + excedente * rango.tasa


def calcular_predial_rustico(valor_catastral: float) -> float:
    return valor_catastral * TASA_RUSTICO


def calcular_predial_minero(valor_catastral: float) -> float:
    return valor_catastral * TASA_MINERO
