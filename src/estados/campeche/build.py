"""
Build del panel Campeche: extrae los bloques de tarifa unicos (LLM v3) y los
expande a los anios de vigencia.

Costo minimo: ~14 llamadas LLM (10 munis estables + Carmen x2 + 2 nuevos) en vez
de ~200. El texto fuente es la tabla del Art. 26 (porcentaje por uso de suelo),
asi que la extraccion suele acertar al primer intento (tasas_diferenciadas).

Salida: data/campeche/json_predial/{anio}/CAMP_PREDIAL_{anio}_{slug}.json
Los munis nuevos (Seybaplaya, Dzitbalche) se marcan requiere_revision para que
el HITL confirme su anio de entrada.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.catalog import build_cvegeo
from src.estados.campeche import config

JSON_DIR = Path("data") / config.ESTADO_SLUG / "json_predial"


def _rep_anio(slug: str, version_id: str) -> int:
    for vid, desde, _hasta, _rev in config.VERSIONES[slug]:
        if vid == version_id:
            return desde
    raise KeyError(f"version {version_id} no existe para {slug}")


def _json_path(anio: int, slug: str) -> Path:
    return JSON_DIR / str(anio) / f"{config.PREFIJO}_PREDIAL_{anio}_{slug}.json"


def _has_tarifas(p: Path) -> bool:
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return bool((d.get("predial") or {}).get("tarifas"))
    except Exception:
        return False


def _replicate(doc: dict, anio: int, cvegeo: str, version_id: str, revisar: bool) -> dict:
    out = json.loads(json.dumps(doc))
    meta = out.setdefault("_meta_v3", {})
    meta["anio"] = anio
    meta["cvegeo"] = cvegeo
    meta["estado"] = config.ESTADO_SLUG
    nota = ("Tasas de la Ley de Hacienda de los Municipios del Estado de Campeche "
            f"(Art. 26, version '{version_id}'). El minimo, descuentos y exenciones "
            "viven en la Ley de Ingresos anual del municipio.")
    if revisar:
        nota += (" ATENCION: municipio de creacion reciente; su anio de entrada "
                 "al panel esta por confirmar (HITL).")
        meta["requiere_revision"] = True
    pred = out.setdefault("predial", {})
    prev = (pred.get("comentarios") or "").strip()
    pred["comentarios"] = (prev + " " + nota).strip() if prev else nota
    return out


def run_build(adapter, force: bool = False) -> Path:
    from src.extraction.llm_extract_v3 import extraer_municipio

    print("=== Campeche: build del panel (extraccion + expansion) ===")
    JSON_DIR.mkdir(parents=True, exist_ok=True)

    n_extraidas = n_expandidas = n_fail = 0
    for cve_mun, _nombre, slug, _tabla in config.MUNICIPIOS:
        cvegeo = build_cvegeo(config.CVE_ENT, cve_mun)
        for version_id, desde, hasta, revisar in config.VERSIONES[slug]:
            rep = _rep_anio(slug, version_id)
            rep_json = _json_path(rep, slug)

            if force or not (rep_json.exists() and _has_tarifas(rep_json)):
                extraer_municipio(config.ESTADO_SLUG, cvegeo, [rep], slug_override=slug)
                n_extraidas += 1
            if not (rep_json.exists() and _has_tarifas(rep_json)):
                print(f"  [FAIL] {slug}/{version_id}: extraccion sin tarifas en {rep}")
                n_fail += 1
                continue

            base_doc = json.loads(rep_json.read_text(encoding="utf-8"))
            for anio in range(desde, hasta + 1):
                out = _replicate(base_doc, anio, cvegeo, version_id, revisar)
                dst = _json_path(anio, slug)
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
                n_expandidas += 1

    print(f"\n  Bloques extraidos: {n_extraidas} | JSONs panel: {n_expandidas} | fallos: {n_fail}")
    return JSON_DIR
