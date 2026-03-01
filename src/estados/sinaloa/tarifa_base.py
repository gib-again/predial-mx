"""
Tarifa base del impuesto predial de Sinaloa.

Fuente: Ley de Hacienda Municipal del Estado de Sinaloa, Art. 35 fracción I.
  Tabla publicada por el Instituto Catastral del Estado de Sinaloa.

Mecánica de actualización (Art. 36):
  Cada año, el Instituto Catastral publica la tarifa actualizada aplicando:
    factor = INPC_nov(Y-1) / INPC_nov(Y-2)
  a los límites inferior/superior y cuotas fijas.
  Las tasas al millar NO se actualizan.

Tabla ancla: ejercicio 2010 (publicada P.O. 28-dic-2009).
  Verificada contra PDFs publicados de 2012-2019; coincidencia <$0.30 por redondeo.

Estructura: 11 rangos, con columnas separadas para predios construidos y baldíos.
  Impuesto = cuota_fija + (valor_catastral − lím_inferior) × (tasa_al_millar / 1000)

Baldíos: se equiparan a predios sin construcción los que tengan construcción inhabitable
  o <25% del terreno construido con valor <50% del terreno (Art. 35-I).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class RangoSinaloa:
    """Un rango de la tarifa Art. 35-I."""
    numero: int
    lim_inf: float             # Límite inferior (pesos)
    lim_sup: Optional[float]   # Límite superior (None = en adelante)
    cuota_construido: float    # Cuota fija construidos (pesos)
    tasa_construido: float     # Tasa al millar construidos
    cuota_baldio: float        # Cuota fija baldíos (pesos)
    tasa_baldio: float         # Tasa al millar baldíos


# ══════════════════════════════════════════════════════════════
# Tabla ancla — Ejercicio 2010 (P.O. 28-dic-2009)
# Rangos 1-6 extraídos directamente del PDF.
# Rangos 7-11 verificados cruzando base legal × factor acumulado
# y confirmados contra PDFs de años posteriores (2015, 2019).
# ══════════════════════════════════════════════════════════════

TABLA_2010: list[RangoSinaloa] = [
    RangoSinaloa( 1,          0.01,    32_082.79,       0.00,  2.50,       0.00,  4.50),
    RangoSinaloa( 2,     32_082.80,    71_569.29,      80.22,  2.55,     144.38,  5.05),
    RangoSinaloa( 3,     71_569.30,   153_010.21,     180.92,  2.64,     343.80,  5.14),
    RangoSinaloa( 4,    153_010.22,   202_368.33,     395.93,  2.77,     762.42,  5.27),
    RangoSinaloa( 5,    202_368.34,   251_726.46,     532.66,  2.95,   1_022.55,  5.45),
    RangoSinaloa( 6,    251_726.47,   375_121.78,     678.28,  3.31,   1_281.56,  5.81),
    RangoSinaloa( 7,    375_121.79,   715_692.89,   1_086.73,  3.82,   2_008.50,  6.32),
    RangoSinaloa( 8,    715_692.90, 1_086_085.43,   2_388.36,  4.28,   4_161.22,  6.78),
    RangoSinaloa( 9,  1_086_085.44, 1_925_399.58,   3_973.63,  4.98,   6_673.22,  7.48),
    RangoSinaloa(10,  1_925_399.59, 3_949_694.81,   8_152.30,  5.37,  12_949.44,  7.87),
    RangoSinaloa(11,  3_949_694.82,         None,  19_020.94,  6.57,  28_893.73,  9.07),
]


# ══════════════════════════════════════════════════════════════
# Motor de actualización INPC
# ══════════════════════════════════════════════════════════════

def _build_inpc_index(csv_path: str | Path) -> dict[tuple[int, int], float]:
    """Construye índice INPC acumulativo desde serie de inflación mensual."""
    idx = 100.0
    inpc: dict[tuple[int, int], float] = {}
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parts = row["Fecha"].strip().split("/")
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
            inf_pct = float(row["inflacion_mensual"].strip())
            idx = idx * (1 + inf_pct / 100)
            inpc[(year, month)] = idx
    return inpc


def _factor_inpc(inpc: dict, year: int) -> float:
    """Factor de actualización Art. 36: INPC_nov(Y-1) / INPC_nov(Y-2)."""
    return inpc[(year - 1, 11)] / inpc[(year - 2, 11)]


def _update_tabla(tabla: list[RangoSinaloa], factor: float) -> list[RangoSinaloa]:
    """Aplica factor INPC a límites y cuotas fijas. Tasas no cambian."""
    result = []
    for r in tabla:
        result.append(RangoSinaloa(
            numero=r.numero,
            lim_inf=round(r.lim_inf * factor, 2),
            lim_sup=round(r.lim_sup * factor, 2) if r.lim_sup is not None else None,
            cuota_construido=round(r.cuota_construido * factor, 2),
            tasa_construido=r.tasa_construido,
            cuota_baldio=round(r.cuota_baldio * factor, 2),
            tasa_baldio=r.tasa_baldio,
        ))
    return result


def generar_tablas_por_ejercicio(
    inpc_csv: str | Path,
    year_min: int = 2010,
    year_max: int = 2025,
) -> dict[int, list[RangoSinaloa]]:
    """
    Genera tablas actualizadas para cada ejercicio fiscal.

    Encadena desde la tabla ancla 2010, aplicando el factor INPC año a año
    con redondeo en cada paso (como hace el Instituto Catastral).
    """
    inpc = _build_inpc_index(inpc_csv)
    tablas: dict[int, list[RangoSinaloa]] = {2010: TABLA_2010}

    current = TABLA_2010
    for year in range(2011, year_max + 1):
        factor = _factor_inpc(inpc, year)
        current = _update_tabla(current, factor)
        tablas[year] = current

    return tablas


# ══════════════════════════════════════════════════════════════
# Cálculo
# ══════════════════════════════════════════════════════════════

def _ubicar_rango(valor_catastral: float, tabla: list[RangoSinaloa]) -> RangoSinaloa:
    rango = tabla[0]
    for r in tabla:
        if valor_catastral >= r.lim_inf:
            rango = r
        else:
            break
    return rango


def calcular_predial(
    valor_catastral: float,
    tabla: list[RangoSinaloa],
    es_baldio: bool = False,
) -> float:
    """
    Impuesto = cuota_fija + (VC − lím_inf) × (tasa_al_millar / 1000)
    """
    rango = _ubicar_rango(valor_catastral, tabla)
    if es_baldio:
        cuota = rango.cuota_baldio
        tasa = rango.tasa_baldio
    else:
        cuota = rango.cuota_construido
        tasa = rango.tasa_construido
    excedente = max(0, valor_catastral - rango.lim_inf)
    return cuota + excedente * (tasa / 1000)
