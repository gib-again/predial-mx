"""
Build del panel BCS: extrae las versiones unicas de Ley de Hacienda (LLM v3)
y las expande a todos los anios en que cada version estuvo vigente.

Costo minimo: ~8 llamadas LLM (una por (municipio, version) unica) en vez de
80 (5 munis x 16 anios). El texto fuente es Word digital limpio, asi que la
extraccion suele acertar al primer intento.

Salida: data/bajacaliforniasur/json_predial/{anio}/BCS_PREDIAL_{anio}_{slug}.json
Los munis con anio de transicion sin confirmar (Los Cabos, Mulege) se marcan
con requiere_revision=True y un comentario para que el HITL los flaggee.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.catalog import build_cvegeo
from src.estados.bajacaliforniasur import config

JSON_DIR = Path("data") / config.ESTADO_SLUG / "json_predial"


def _rep_anio(slug: str, version_id: str) -> int:
    for vid, desde, _hasta, _rev in config.VERSIONES[slug]:
        if vid == version_id:
            return desde
    raise KeyError(f"version {version_id} no existe para {slug}")


def _json_path(anio: int, slug: str) -> Path:
    return JSON_DIR / str(anio) / f"{config.PREFIJO}_PREDIAL_{anio}_{slug}.json"


def _replicate(doc: dict, anio: int, cvegeo: str, version_id: str, revisar: bool) -> dict:
    """Clona el doc de una version para un anio destino, ajustando metadatos."""
    out = json.loads(json.dumps(doc))  # deep copy
    meta = out.setdefault("_meta_v3", {})
    meta["anio"] = anio
    meta["cvegeo"] = cvegeo
    meta["estado"] = config.ESTADO_SLUG
    nota = (f"Tasas de la Ley de Hacienda Municipal, version '{version_id}'. "
            "BCS: el predial vive en la Ley de Hacienda (no en la ley de ingresos anual).")
    if revisar:
        nota += (" ATENCION: el anio exacto de transicion entre versiones esta "
                 "pendiente de confirmacion manual (HITL).")
        meta["requiere_revision"] = True
    pred = out.setdefault("predial", {})
    prev = (pred.get("comentarios") or "").strip()
    pred["comentarios"] = (prev + " " + nota).strip() if prev else nota
    return out


def run_build(adapter, force: bool = False) -> Path:
    """Extrae versiones unicas y expande al panel completo."""
    from src.extraction.llm_extract_v3 import extraer_municipio

    print("=== Baja California Sur: build del panel (extraccion + expansion) ===")
    JSON_DIR.mkdir(parents=True, exist_ok=True)

    n_extraidas = n_expandidas = n_fail = 0
    for cve_mun, _nombre, slug in config.MUNICIPIOS:
        cvegeo = build_cvegeo(config.CVE_ENT, cve_mun)
        for version_id, desde, hasta, revisar in config.VERSIONES[slug]:
            rep = _rep_anio(slug, version_id)
            rep_json = _json_path(rep, slug)

            # 1) Extraer la version representativa (si falta o force).
            if force or not (rep_json.exists() and _has_tarifas(rep_json)):
                extraer_municipio(config.ESTADO_SLUG, cvegeo, [rep], slug_override=slug)
                n_extraidas += 1
            if not (rep_json.exists() and _has_tarifas(rep_json)):
                print(f"  [FAIL] {slug}/{version_id}: extraccion sin tarifas en {rep}")
                n_fail += 1
                continue

            base_doc = json.loads(rep_json.read_text(encoding="utf-8"))

            # 2) Expandir a todos los anios de la version (incluido rep).
            for anio in range(desde, hasta + 1):
                out = _replicate(base_doc, anio, cvegeo, version_id, revisar)
                dst = _json_path(anio, slug)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
                n_expandidas += 1

    print(f"\n  Versiones extraidas: {n_extraidas} | JSONs panel: {n_expandidas} | fallos: {n_fail}")
    return JSON_DIR


def _has_tarifas(p: Path) -> bool:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return bool((d.get("predial") or {}).get("tarifas"))
    except Exception:
        return False
