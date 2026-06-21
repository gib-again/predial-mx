"""Orquestador: itera corpus v3 + segment CSVs, ejecuta detectores, escribe cola.

Uso:
    python -m src.hitl.run_detectors
    python -m src.hitl.run_detectors --estado coahuila
    python -m src.hitl.run_detectors --merge   # preserva decisiones existentes
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from src.core.catalog import cvegeo_to_nombre
from src.core.constants import PREFIJOS_ESTADO
from src.core.corpus import iter_corpus_files, parse_fname
from src.core.segment_schema import read_segment_csv
from src.hitl.cobertura import EXCLUIDOS as COBERTURA_EXCLUIDOS
from src.hitl.cobertura import estados_cobertura
from src.hitl.detectors import (
    JSON_DETECTORS,
    det_cambio_interanual,
    det_cobertura_incompleta,
    det_distancia_inicio_anomala,
    det_frontera_sin_verificar,
)
from src.hitl.decisiones import load_latest
from src.hitl.queue_schema import (
    QueueRow,
    consolidate_rows,
    write_queue,
)

DATA_ROOT = Path("data")

# Estados que NO entran a la cola HITL (Oaxaca por volumen; hardcoded no se
# segmentan).  Reusa la exclusión de la capa de cobertura.
OMIT_HITL = COBERTURA_EXCLUIDOS

ESTADO_PRETTY = {
    "coahuila": "Coahuila", "guanajuato": "Guanajuato", "jalisco": "Jalisco",
    "oaxaca": "Oaxaca", "queretaro": "Querétaro", "sanluispotosi": "San Luis Potosí",
    "sonora": "Sonora", "tamaulipas": "Tamaulipas", "yucatan": "Yucatán",
    "chihuahua": "Chihuahua", "colima": "Colima", "edomex": "Estado de México",
    "sinaloa": "Sinaloa", "tabasco": "Tabasco",
}

ESTADOS_HARDCODED = {"chihuahua", "colima", "edomex", "sinaloa", "tabasco"}


def _pretty_muni(slug: str) -> str:
    palabras = slug.split("_")
    skip = {"de", "del", "la", "las", "los", "el", "y", "e"}
    return " ".join(w if w in skip else w.capitalize() for w in palabras)


def _is_llm_direct(meta: dict) -> bool:
    modelo = (meta.get("modelo") or "").lower()
    if not modelo:
        return False
    if modelo.startswith(("imputed_", "synthesized_", "audit_", "discovered_", "hardcoded")):
        return False
    return "gpt-" in modelo


# ══════════════════════════════════════════════════════════════
# Corpus iterators
# ══════════════════════════════════════════════════════════════

def iter_v3_corpus(
    estado_filter: str | None = None,
    include_hardcoded: bool = False,
):
    """Yield (estado_slug, anio, muni_slug, doc_dict, json_path).

    Itera el corpus v3 desde data/{estado}/json_predial/{anio}/ vía
    src.core.corpus (overlay HITL incluido).
    """
    estados = (
        [estado_filter] if estado_filter
        else sorted(set(PREFIJOS_ESTADO) | (ESTADOS_HARDCODED if include_hardcoded else set()))
    )
    for slug in estados:
        if slug in OMIT_HITL and not (include_hardcoded and slug in ESTADOS_HARDCODED):
            continue  # Oaxaca y hardcoded fuera de HITL
        for p in iter_corpus_files(slug):
            parsed = parse_fname(p)
            if not parsed:
                continue
            anio, muni_slug = parsed
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            meta = doc.get("_meta") or {}
            if not include_hardcoded and not _is_llm_direct(meta):
                continue
            if not isinstance(doc.get("predial"), dict):
                continue
            yield slug, anio, muni_slug, doc, str(p)


def load_segment_csv(estado_slug: str) -> list[dict]:
    """Lee segment.csv canónico (alias legados normalizados por segment_schema)."""
    return read_segment_csv(DATA_ROOT / estado_slug / "meta" / "segment.csv")


# ══════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════

def run(
    estado_filter: str | None = None,
    merge: bool = False,  # deprecado: las decisiones viven en hitl_decisiones.csv
    include_hardcoded: bool = False,
) -> Path:
    all_rows: list[QueueRow] = []

    # ── Segment-based detectors (D1, D2) ──
    estados_to_scan = (
        [estado_filter] if estado_filter
        else sorted(PREFIJOS_ESTADO.keys())
    )
    for est_slug in estados_to_scan:
        if est_slug in OMIT_HITL and not (include_hardcoded and est_slug in ESTADOS_HARDCODED):
            continue  # Oaxaca y hardcoded fuera de HITL
        seg_rows = load_segment_csv(est_slug)
        if not seg_rows:
            continue
        pretty = ESTADO_PRETTY.get(est_slug, est_slug.capitalize())

        if est_slug == "jalisco":
            all_rows.extend(det_frontera_sin_verificar(seg_rows, est_slug, pretty))

        all_rows.extend(det_distancia_inicio_anomala(seg_rows, est_slug, pretty))
        # identidad_no_resuelta queda subsumido por la capa de cobertura
        # (det_cobertura_incompleta adjunta el focus huérfano como pista).

    # ── JSON-based detectors (D3-D11) + collect series for D12 ──
    n_json = 0
    by_estado: dict[str, int] = defaultdict(int)
    # For D12: group docs by (estado_slug, municipio_slug)
    series_by_muni: dict[tuple[str, str], dict[int, tuple[dict, str]]] = defaultdict(dict)
    muni_info: dict[tuple[str, str], dict] = {}

    for est_slug, anio, muni_slug, doc, json_path in iter_v3_corpus(
        estado_filter, include_hardcoded,
    ):
        n_json += 1
        by_estado[est_slug] += 1
        if n_json % 500 == 0:
            print(f"  [{n_json}] procesando JSONs v3...")

        meta_v3 = doc.get("_meta_v3") or {}
        pretty = ESTADO_PRETTY.get(est_slug, est_slug.capitalize())
        cvegeo = meta_v3.get("cvegeo", "")
        # Nombre de display SIEMPRE desde el catálogo INEGI (cvegeo), nunca
        # desde el slug del archivo ni de texto extraído.
        kw = dict(
            estado=pretty,
            municipio=cvegeo_to_nombre(cvegeo) or _pretty_muni(muni_slug),
            cvegeo=cvegeo,
        )
        for det_fn in JSON_DETECTORS:
            hits = det_fn(doc, est_slug, muni_slug, anio, json_path, **kw)
            all_rows.extend(hits)

        key = (est_slug, muni_slug)
        series_by_muni[key][anio] = (doc, json_path)
        if key not in muni_info:
            muni_info[key] = kw

    # ── D12: interannual detector ──
    n_interanual = 0
    for (est_slug, muni_slug), series in series_by_muni.items():
        kw = muni_info.get((est_slug, muni_slug), {})
        hits = det_cambio_interanual(series, est_slug, muni_slug, **kw)
        all_rows.extend(hits)
        n_interanual += len(hits)
    if n_interanual:
        print(f"  D12 cambio_interanual: {n_interanual} transiciones con cambio")

    # ── Cobertura: JSONs sin predial (placeholders + extracciones fallidas) ──
    # iter_v3_corpus excluye predial=null, así que se itera aparte.
    n_cob = 0
    for est_slug in estados_cobertura():
        if estado_filter and est_slug != estado_filter:
            continue
        pretty = ESTADO_PRETTY.get(est_slug, est_slug.capitalize())
        for p in iter_corpus_files(est_slug):
            parsed = parse_fname(p)
            if not parsed:
                continue
            anio, muni_slug = parsed
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            if doc.get("predial") is not None:
                continue  # solo placeholders / fallidos
            cvegeo = (doc.get("_meta_v3") or {}).get("cvegeo", "")
            kw = dict(estado=pretty,
                      municipio=cvegeo_to_nombre(cvegeo) or _pretty_muni(muni_slug),
                      cvegeo=cvegeo)
            hits = det_cobertura_incompleta(doc, est_slug, muni_slug, anio, str(p), **kw)
            all_rows.extend(hits)
            n_cob += len(hits)
    if n_cob:
        print(f"  cobertura: {n_cob} casos sin predial (placeholders + fallidos)")

    # ── Consolidate: one row per municipio-año ──
    print(f"\nCorpus v3: {n_json} JSONs ({dict(by_estado)})")
    print(f"Detecciones brutas: {len(all_rows)}")
    consolidated = consolidate_rows(all_rows)
    print(f"Consolidadas: {len(consolidated)} casos (municipio-año)")

    # ── Vista derivada: overlay de decisiones desde la capa append-only ──
    # La cola NO almacena decisiones (Causa B); se reconstruye desde el estado
    # actual y se anota con la última decisión registrada por caso.  Así los
    # orphans son imposibles: sólo hay filas respaldadas por JSON/segment actual.
    latest = load_latest()
    n_dec = 0
    for r in consolidated:
        d = latest.get(r.id)
        if d:
            r.decision = d.get("decision", "")
            r.notas = d.get("notas", "")
            n_dec += 1
    if n_dec:
        print(f"  Decisiones aplicadas desde log append-only: {n_dec}")

    result = sorted(consolidated, key=lambda r: (
        {"SEV1-H": 0, "SEV1": 1, "SEV2": 2, "SEV3": 3}.get(r.severidad, 9),
        r.estado_slug, r.municipio_slug, r.anio,
    ))

    out = write_queue(result)
    by_sev = defaultdict(int)
    by_det = defaultdict(int)
    for r in result:
        by_sev[r.severidad] += 1
        for d in r.detector.split(","):
            by_det[d.strip()] += 1

    print(f"\nCola escrita: {out} ({len(result)} filas)")
    print(f"  Por severidad: {dict(sorted(by_sev.items()))}")
    print(f"  Por detector:  {dict(sorted(by_det.items()))}")
    return out


def main():
    parser = argparse.ArgumentParser(description="Ejecutar detectores HITL sobre corpus v3")
    parser.add_argument("--estado", help="Filtrar a un solo estado")
    parser.add_argument("--merge", action="store_true",
                        help="(deprecado, no-op) las decisiones ahora viven en "
                             "hitl_decisiones.csv y se aplican siempre")
    parser.add_argument("--include-hardcoded", action="store_true",
                        help="Incluir estados hardcoded (Grupo B)")
    args = parser.parse_args()
    run(args.estado, args.merge, args.include_hardcoded)


if __name__ == "__main__":
    main()
