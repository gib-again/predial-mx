"""Adapters: formato 'hardcoded' (data/{estado}/...) → schema_v2.

Cuatro estados con tarifa uniforme estatal codificada manualmente, cada uno con
sub-formato distinto. Convertimos al esquema canónico v2 (`ProgresivoSchema` o
`CuotaFijaEscalonadaSchema`) usando como tipo de predio canónico:

  - colima:  predial.urbano_edificado.rangos
  - edomex:  predial.rangos        (root, único tipo)
  - sinaloa: predial.urbano.rangos (columna construido)
  - tabasco: predial.rangos        (root, único tipo)

Cada adapter es puro: dict → dict. La validación final corre vía
`reclasificar()` desde panel_v2 / convert_hardcoded_to_v2.
"""

from __future__ import annotations

from typing import Callable


def _build_v2_predial(rows: list[dict], comentarios: str) -> dict:
    """Decide progresivo vs cuota_fija_escalonada según las tasas marginales."""
    any_positive = any((r.get("tasa_marginal") or 0) > 0 for r in rows)
    if any_positive:
        return {
            "tipo_esquema": "progresivo",
            "tabla": rows,
            "minimo_predial": None,
            "comentarios": comentarios,
        }
    # Todos los marginales son 0 → cuota_fija_escalonada (mismo tabla pero con campo `monto`).
    return {
        "tipo_esquema": "cuota_fija_escalonada",
        "tabla": [
            {
                "n_rango": r["n_rango"],
                "inferior": r["inferior"],
                "superior": r["superior"],
                "monto": r["cuota_fija"],
            }
            for r in rows
        ],
        "minimo_predial": None,
        "comentarios": comentarios,
    }


def _wrap(predial: dict, *, cvegeo: str, estado: str, anio: int, fuente_url: str) -> dict:
    """Envolver el dict 'predial' con _meta y _meta_v2 para serialización."""
    return {
        "predial": predial,
        "_meta": {"fuente": "txt", "modelo": "hardcoded"},
        "_meta_v2": {
            "intentos": 0,
            "requiere_revision": False,
            "razon": None,
            "tokens": {"input": 0, "output": 0, "cached": 0},
            "cvegeo": cvegeo,
            "estado": estado,
            "anio": anio,
            "fuente_url": fuente_url,
        },
    }


# ── Colima ──

def adapt_colima(src: dict) -> dict:
    """colima: predial.urbano_edificado.rangos[*] {rango, lim_inf, lim_sup,
    cuota_fija_unidad, tasa_marginal}. cuota_fija_pesos = cuota_fija_unidad ×
    cuota_fija_valor_pesos."""
    p = src["predial"]
    ue = p.get("urbano_edificado") or {}
    rangos = ue.get("rangos") or []
    factor_pesos = float(ue.get("cuota_fija_valor_pesos") or 1.0)

    rows = [
        {
            "n_rango": int(r["rango"]),
            "inferior": float(r["lim_inf"]),
            "superior": float(r["lim_sup"]) if r.get("lim_sup") is not None else None,
            "cuota_fija": float(r.get("cuota_fija_unidad") or 0.0) * factor_pesos,
            "tasa_marginal": float(r.get("tasa_marginal") or 0.0),
        }
        for r in rangos
    ]
    cvegeo = f"{src['cve_ent']}{src['cve_mun']}"
    predial = _build_v2_predial(
        rows,
        comentarios=(
            f"Hardcoded → v2 desde Ley de Hacienda Municipal de Colima "
            f"(urbano_edificado). Cuota fija convertida de SM_diario a pesos "
            f"con factor {factor_pesos}."
        ),
    )
    return _wrap(predial, cvegeo=cvegeo, estado="colima", anio=int(src["ejercicio"]),
                 fuente_url=src.get("fuente_url", ""))


# ── Edomex ──

def adapt_edomex(src: dict) -> dict:
    """edomex: predial.rangos[*] {rango, lim_inf, lim_sup, cuota_fija_pesos, factor}.
    factor → tasa_marginal."""
    p = src["predial"]
    rangos = p.get("rangos") or []

    rows = [
        {
            "n_rango": int(r["rango"]),
            "inferior": float(r["lim_inf"]),
            "superior": float(r["lim_sup"]) if r.get("lim_sup") is not None else None,
            "cuota_fija": float(r.get("cuota_fija_pesos") or 0.0),
            "tasa_marginal": float(r.get("factor") or 0.0),
        }
        for r in rangos
    ]
    cvegeo = f"{src['cve_ent']}{src['cve_mun']}"
    predial = _build_v2_predial(
        rows,
        comentarios="Hardcoded → v2 desde Código Financiero del Estado de México (Art. 109).",
    )
    return _wrap(predial, cvegeo=cvegeo, estado="edomex", anio=int(src["ejercicio"]),
                 fuente_url=src.get("fuente_url", ""))


# ── Sinaloa ──

def adapt_sinaloa(src: dict) -> dict:
    """sinaloa: predial.urbano.rangos[*] {rango, lim_inf, lim_sup, cuota_construido,
    tasa_construido_millar, ...}. Usa la columna construido como canónica.
    tasa_construido_millar / 1000 → tasa_marginal."""
    p = src["predial"]
    urbano = p.get("urbano") or {}
    rangos = urbano.get("rangos") or []

    rows = [
        {
            "n_rango": int(r["rango"]),
            "inferior": float(r["lim_inf"]),
            "superior": float(r["lim_sup"]) if r.get("lim_sup") is not None else None,
            "cuota_fija": float(r.get("cuota_construido") or 0.0),
            "tasa_marginal": float(r.get("tasa_construido_millar") or 0.0) / 1000.0,
        }
        for r in rangos
    ]
    cvegeo = f"{src['cve_ent']}{src['cve_mun']}"
    predial = _build_v2_predial(
        rows,
        comentarios=(
            "Hardcoded → v2 desde Ley de Hacienda Municipal de Sinaloa (Art. 35-36, "
            "columna construido). Se descarta columna baldio para mantener un esquema "
            "por archivo."
        ),
    )
    return _wrap(predial, cvegeo=cvegeo, estado="sinaloa", anio=int(src["ejercicio"]),
                 fuente_url=src.get("fuente_url", ""))


# ── Tabasco ──

def adapt_tabasco(src: dict) -> dict:
    """tabasco: predial.rangos[*] {rango, lim_inf, lim_sup, cuota_fija_pesos, tasa_pct}.
    tasa_pct / 100 → tasa_marginal (decimal)."""
    p = src["predial"]
    rangos = p.get("rangos") or []

    rows = [
        {
            "n_rango": int(r["rango"]),
            "inferior": float(r["lim_inf"]),
            "superior": float(r["lim_sup"]) if r.get("lim_sup") is not None else None,
            "cuota_fija": float(r.get("cuota_fija_pesos") or 0.0),
            "tasa_marginal": float(r.get("tasa_pct") or 0.0) / 100.0,
        }
        for r in rangos
    ]
    cvegeo = f"{src['cve_ent']}{src['cve_mun']}"
    predial = _build_v2_predial(
        rows,
        comentarios="Hardcoded → v2 desde Ley de Hacienda Municipal de Tabasco (Art. 94).",
    )
    return _wrap(predial, cvegeo=cvegeo, estado="tabasco", anio=int(src["ejercicio"]),
                 fuente_url=src.get("fuente_url", ""))


# ── Chihuahua (in-memory only — no se escribe a predial-mx-v2/) ──

def adapt_chihuahua(src: dict) -> dict:
    """chihuahua: predial.urbano.rangos[*] {rango, lim_inf, tasa_millar, cuota_fija}.
    NO hay lim_sup explícito: superior=siguiente_rango.lim_inf, último=None.
    tasa_millar / 1000 → tasa_marginal."""
    p = src["predial"]
    urbano = p.get("urbano") or {}
    rangos = urbano.get("rangos") or []

    rows: list[dict] = []
    for i, r in enumerate(rangos):
        is_last = i == len(rangos) - 1
        superior = None if is_last else float(rangos[i + 1]["lim_inf"])
        rows.append({
            "n_rango": int(r["rango"]),
            "inferior": float(r["lim_inf"]),
            "superior": superior,
            "cuota_fija": float(r.get("cuota_fija") or 0.0),
            "tasa_marginal": float(r.get("tasa_millar") or 0.0) / 1000.0,
        })

    cvegeo = f"{src['cve_ent']}{src['cve_mun']}"
    predial = _build_v2_predial(
        rows,
        comentarios=(
            "Hardcoded → v2 desde Código Municipal de Chihuahua (urbano). lim_sup "
            "derivado del lim_inf del siguiente rango."
        ),
    )
    return _wrap(predial, cvegeo=cvegeo, estado="chihuahua", anio=int(src["ejercicio"]),
                 fuente_url=src.get("fuente_url", ""))


# ── Registry ──

ADAPTERS: dict[str, Callable[[dict], dict]] = {
    "colima":    adapt_colima,
    "edomex":    adapt_edomex,
    "sinaloa":   adapt_sinaloa,
    "tabasco":   adapt_tabasco,
    "chihuahua": adapt_chihuahua,
}
