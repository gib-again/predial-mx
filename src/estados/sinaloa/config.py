"""
Configuración específica de Sinaloa.

18 municipios. Ley de Hacienda Municipal del Estado de Sinaloa, Art. 35-36.
Tarifa estatal uniforme con actualización anual por INPC (Art. 36):
  factor = INPC_nov(Y-1) / INPC_nov(Y-2)
  Se aplica a límites inferior/superior y cuotas fijas (las tasas al millar NO cambian).

Estructura de tarifa:
  - Fracción I: Predios/fincas urbanas, 11 rangos con columnas para construidos y baldíos.
  - Fracción II: Predios rústicos productivos (agricultura, acuicultura, ganadería,
    porcicultura, avicultura) → tasa sobre valor de producción anual comercializada.
  - Fracción III: Demás predios rurales → misma tarifa de fracción I.
  - Fracción IV: Campos de golf → régimen especial.

Descuentos:
  - Pago total anual en primeros 2 meses: 10% (Art. 41).
  - Casa habitación permanente: 50% (Art. 43).
  - Jubilados/pensionados/discapacitados: cuota fija 3 UMA o -80% (Art. 42).
  - Empresas comerciales/industriales: hasta 40% aprobado por Ayuntamiento (Art. 44).
"""

from __future__ import annotations

ESTADO_SLUG = "sinaloa"
PREFIJO = "SIN"
ESTADO_NOMBRE = "Sinaloa"
CVE_ENT = "25"
NEEDS_OCR = False  # Tarifa base hardcoded + actualización INPC computada

YEAR_MIN = 2010
YEAR_MAX = 2025

# ── 18 municipios de Sinaloa ───────────────────────────────
# Fuente: INEGI catálogo AGEEML (CVE_ENT=25).
MUNICIPIOS: list[tuple[str, str, str]] = [
    ("001", "Ahome", "ahome"),
    ("002", "Angostura", "angostura"),
    ("003", "Badiraguato", "badiraguato"),
    ("004", "Concordia", "concordia"),
    ("005", "Cosalá", "cosala"),
    ("006", "Culiacán", "culiacan"),
    ("007", "Choix", "choix"),
    ("008", "Elota", "elota"),
    ("009", "Escuinapa", "escuinapa"),
    ("010", "El Fuerte", "el_fuerte"),
    ("011", "Guasave", "guasave"),
    ("012", "Mazatlán", "mazatlan"),
    ("013", "Mocorito", "mocorito"),
    ("014", "Rosario", "rosario"),
    ("015", "Salvador Alvarado", "salvador_alvarado"),
    ("016", "San Ignacio", "san_ignacio"),
    ("017", "Sinaloa", "sinaloa_mun"),
    ("018", "Navolato", "navolato"),
]

# ── Predios rústicos productivos (Art. 35, fracción II) ────
TASAS_RUSTICO_PRODUCCION = {
    "agricultura": 0.010,    # 1.0%
    "acuicultura": 0.010,    # 1.0%
    "ganaderia": 0.010,      # 1.0%
    "porcicultura": 0.005,   # 0.5%
    "avicultura": 0.005,     # 0.5%
}
