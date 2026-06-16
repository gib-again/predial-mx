"""Adapters: formato 'hardcoded' (data/{estado}/...) → schema_v3.

Full v3: deshace reescalado de v2, añade tarifas paralelas que v2 descartaba,
y produce el contenedor multi-tarifa TarifaPredial[].

Cambios vs adapters_hardcoded.py (v2):
  - Chihuahua: +rústico tasa_unica (antes descartado). Urbano con tasa fiel al_millar.
  - Colima:    +rústico progresivo + baldío tasa_unica (antes descartados).
  - Sinaloa:   +baldío progresivo (antes descartado). Tasas fieles al_millar.
  - Tabasco:   tasa_pct fiel con unidad=porcentaje (antes /100).
  - Edomex:    factor → al_millar ×1000 con unidad explícita.
"""

from __future__ import annotations

from typing import Callable


# ── Helpers ──


def _build_progresivo_esquema(rows: list[dict], unidad: str) -> dict:
    """Produce ProgresivoSchema dict con un solo bloque 'general'."""
    tabla = [
        {
            "n_rango": r["n_rango"],
            "inferior": r["inferior"],
            "superior": r["superior"],
            "cuota_fija": r["cuota_fija"],
            "tasa_marginal": r["tasa_marginal"],
            "unidad": unidad,
        }
        for r in rows
    ]
    any_positive = any(r["tasa_marginal"] > 0 for r in rows)
    if any_positive:
        return {"tipo_esquema": "progresivo", "bloques": [{"categoria": "general", "tabla": tabla}]}
    return {
        "tipo_esquema": "cuota_fija_escalonada",
        "tabla": [
            {"n_rango": r["n_rango"], "inferior": r["inferior"],
             "superior": r["superior"], "monto": r["cuota_fija"]}
            for r in rows
        ],
    }


def _tarifa(ambito: str, base_gravable: str, esquema: dict, **kw) -> dict:
    return {
        "ambito": ambito,
        "ambito_detalle": kw.get("ambito_detalle"),
        "base_gravable": base_gravable,
        "esquema": esquema,
        "minimo_predial": kw.get("minimo_predial"),
    }


def _tasa_unica(descripcion: str, tasa: float, unidad: str) -> dict:
    return {
        "tipo_esquema": "tasa_unica",
        "tabla": [{
            "descripcion": descripcion,
            "tasa": tasa,
            "unidad": unidad,
            "cuota_fija_adicional": None,
        }],
    }


def _wrap_v3(
    tarifas: list[dict],
    *,
    minimo_general: dict | None = None,
    comentarios: str = "",
    cvegeo: str,
    estado: str,
    anio: int,
    fuente_url: str = "",
) -> dict:
    return {
        "predial": {
            "tarifas": tarifas,
            "minimo_predial_general": minimo_general,
            "comentarios": comentarios,
        },
        "_meta": {"fuente": "txt", "modelo": "hardcoded"},
        "_meta_v3": {
            "intentos": 0,
            "requiere_revision": False,
            "escalado": False,
            "razon": None,
            "usado_reocr": False,
            "usado_vision": False,
            "tokens": {"input": 0, "output": 0, "cached": 0},
            "cvegeo": cvegeo,
            "estado": estado,
            "anio": anio,
            "procedencia": {
                "archivo_pdf": None,
                "archivo_txt": None,
                "paginas": None,
                "fuente_ganadora": "txt",
                "origen_override": False,
            },
        },
    }


# ── Chihuahua ──


def adapt_chihuahua_v3(src: dict) -> dict:
    """Tarifa 1: urbano progresivo (tasa fiel al millar).
    Tarifa 2: rústico tasa_unica (tasa fiel al millar).
    v2 descartaba rústico y dividía tasa_millar/1000."""
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
            "tasa_marginal": float(r.get("tasa_millar") or 0.0),
        })

    tarifas = [
        _tarifa("urbano", "valor_catastral",
                _build_progresivo_esquema(rows, "al_millar")),
    ]

    rustico = p.get("rustico") or {}
    if rustico.get("tasa_millar") is not None:
        tarifas.append(
            _tarifa("rustico", "valor_catastral",
                    _tasa_unica("Predios rústicos",
                                float(rustico["tasa_millar"]), "al_millar"))
        )

    cvegeo = f"{src['cve_ent']}{src['cve_mun']}"
    return _wrap_v3(
        tarifas,
        comentarios="Hardcoded → v3 desde Código Municipal de Chihuahua.",
        cvegeo=cvegeo, estado="chihuahua", anio=int(src["ejercicio"]),
        fuente_url=src.get("fuente_url", ""),
    )


# ── Colima ──


def adapt_colima_v3(src: dict) -> dict:
    """Tarifa 1: urbano_edificado progresivo.
    Tarifa 2: rústico progresivo.
    Tarifa 3: urbano baldío tasa_unica.
    v2 solo usaba urbano_edificado; descartaba rústico y baldío."""
    p = src["predial"]

    def _colima_rows(seccion: dict) -> list[dict]:
        rangos = seccion.get("rangos") or []
        factor_pesos = float(seccion.get("cuota_fija_valor_pesos") or 1.0)
        return [
            {
                "n_rango": int(r["rango"]),
                "inferior": float(r["lim_inf"]),
                "superior": float(r["lim_sup"]) if r.get("lim_sup") is not None else None,
                "cuota_fija": float(r.get("cuota_fija_unidad") or 0.0) * factor_pesos,
                "tasa_marginal": float(r.get("tasa_marginal") or 0.0) * 1000.0,
            }
            for r in rangos
        ]

    tarifas: list[dict] = []

    ue = p.get("urbano_edificado") or {}
    if ue.get("rangos"):
        tarifas.append(
            _tarifa("urbano", "valor_catastral",
                    _build_progresivo_esquema(_colima_rows(ue), "al_millar"),
                    ambito_detalle="edificado")
        )

    rust = p.get("rustico") or {}
    if rust.get("rangos"):
        tarifas.append(
            _tarifa("rustico", "valor_catastral",
                    _build_progresivo_esquema(_colima_rows(rust), "al_millar"))
        )

    baldio = p.get("urbano_baldio") or {}
    if baldio.get("tasa") is not None:
        tasa_raw = float(baldio["tasa"])
        nota = baldio.get("nota", "")
        if "millar" in nota.lower():
            tasa_val = tasa_raw * 1000.0 if tasa_raw < 1 else tasa_raw
            unidad = "al_millar"
        else:
            tasa_val = tasa_raw * 1000.0
            unidad = "al_millar"
        tarifas.append(
            _tarifa("urbano", "valor_catastral",
                    _tasa_unica("Predios urbanos baldíos", tasa_val, unidad),
                    ambito_detalle="baldío")
        )

    cvegeo = f"{src['cve_ent']}{src['cve_mun']}"
    return _wrap_v3(
        tarifas,
        comentarios="Hardcoded → v3 desde Ley de Hacienda Municipal de Colima.",
        cvegeo=cvegeo, estado="colima", anio=int(src["ejercicio"]),
        fuente_url=src.get("fuente_url", ""),
    )


# ── Sinaloa ──


def adapt_sinaloa_v3(src: dict) -> dict:
    """Tarifa 1: urbano construido progresivo (tasa fiel al millar).
    Tarifa 2: urbano baldío progresivo (tasa fiel al millar).
    v2 solo usaba construido y dividía tasa/1000."""
    p = src["predial"]
    urbano = p.get("urbano") or {}
    rangos = urbano.get("rangos") or []

    construido_rows = [
        {
            "n_rango": int(r["rango"]),
            "inferior": float(r["lim_inf"]),
            "superior": float(r["lim_sup"]) if r.get("lim_sup") is not None else None,
            "cuota_fija": float(r.get("cuota_construido") or 0.0),
            "tasa_marginal": float(r.get("tasa_construido_millar") or 0.0),
        }
        for r in rangos
    ]

    baldio_rows = [
        {
            "n_rango": int(r["rango"]),
            "inferior": float(r["lim_inf"]),
            "superior": float(r["lim_sup"]) if r.get("lim_sup") is not None else None,
            "cuota_fija": float(r.get("cuota_baldio") or 0.0),
            "tasa_marginal": float(r.get("tasa_baldio_millar") or 0.0),
        }
        for r in rangos
    ]

    tarifas = [
        _tarifa("urbano", "valor_catastral",
                _build_progresivo_esquema(construido_rows, "al_millar"),
                ambito_detalle="construido"),
    ]
    if any(r["tasa_marginal"] > 0 or r["cuota_fija"] > 0 for r in baldio_rows):
        tarifas.append(
            _tarifa("urbano", "valor_catastral",
                    _build_progresivo_esquema(baldio_rows, "al_millar"),
                    ambito_detalle="baldío")
        )

    cvegeo = f"{src['cve_ent']}{src['cve_mun']}"
    return _wrap_v3(
        tarifas,
        comentarios=(
            "Hardcoded → v3 desde Ley de Hacienda Municipal de Sinaloa (Art. 35-36)."
        ),
        cvegeo=cvegeo, estado="sinaloa", anio=int(src["ejercicio"]),
        fuente_url=src.get("fuente_url", ""),
    )


# ── Tabasco ──


def adapt_tabasco_v3(src: dict) -> dict:
    """Tarifa general progresiva con tasa fiel en porcentaje.
    v2 dividía tasa_pct/100."""
    p = src["predial"]
    rangos = p.get("rangos") or []

    rows = [
        {
            "n_rango": int(r["rango"]),
            "inferior": float(r["lim_inf"]),
            "superior": float(r["lim_sup"]) if r.get("lim_sup") is not None else None,
            "cuota_fija": float(r.get("cuota_fija_pesos") or 0.0),
            "tasa_marginal": float(r.get("tasa_pct") or 0.0),
        }
        for r in rangos
    ]

    tarifas = [
        _tarifa("general", "valor_catastral",
                _build_progresivo_esquema(rows, "porcentaje")),
    ]

    cvegeo = f"{src['cve_ent']}{src['cve_mun']}"
    return _wrap_v3(
        tarifas,
        comentarios="Hardcoded → v3 desde Ley de Hacienda Municipal de Tabasco (Art. 94).",
        cvegeo=cvegeo, estado="tabasco", anio=int(src["ejercicio"]),
        fuente_url=src.get("fuente_url", ""),
    )


# ── Edomex ──


def adapt_edomex_v3(src: dict) -> dict:
    """Tarifa general progresiva. factor (proporción decimal) → al_millar ×1000.
    v2 usaba el factor crudo como tasa_marginal."""
    p = src["predial"]
    rangos = p.get("rangos") or []

    rows = [
        {
            "n_rango": int(r["rango"]),
            "inferior": float(r["lim_inf"]),
            "superior": float(r["lim_sup"]) if r.get("lim_sup") is not None else None,
            "cuota_fija": float(r.get("cuota_fija_pesos") or 0.0),
            "tasa_marginal": float(r.get("factor") or 0.0) * 1000.0,
        }
        for r in rangos
    ]

    tarifas = [
        _tarifa("general", "valor_catastral",
                _build_progresivo_esquema(rows, "al_millar")),
    ]

    cvegeo = f"{src['cve_ent']}{src['cve_mun']}"
    return _wrap_v3(
        tarifas,
        comentarios=(
            "Hardcoded → v3 desde Código Financiero del Estado de México (Art. 109). "
            "Factor original convertido a al_millar (×1000)."
        ),
        cvegeo=cvegeo, estado="edomex", anio=int(src["ejercicio"]),
        fuente_url=src.get("fuente_url", ""),
    )


# ── Registry ──

ADAPTERS_V3: dict[str, Callable[[dict], dict]] = {
    "chihuahua": adapt_chihuahua_v3,
    "colima":    adapt_colima_v3,
    "sinaloa":   adapt_sinaloa_v3,
    "tabasco":   adapt_tabasco_v3,
    "edomex":    adapt_edomex_v3,
}
