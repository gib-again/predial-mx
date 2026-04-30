#!/usr/bin/env python3
"""Genera JSONs sintéticos `otro_no_clasificado / municipio_sin_impuesto` para
los focus_predial de Yucatán que el segmentador marcó como `short_form` (leyes
de ingreso en formato corto, sin sección de tarifa).

El resultado es determinista — el LLM no aporta valor en estos casos porque
las leyes literalmente no contienen rates. Se evitan tokens.

Uso:
    python -m scripts.synthesize_short_form_jsons
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.core.muni_matcher import MuniMatcher
from src.core.text_utils import slugify


SHORT_FORM_HEADER_TAG = "[NOTA DEL SEGMENTADOR — LEY DE INGRESOS DE FORMA CORTA]"

CVE_ENT_YUCATAN = "31"
ESTADO_SLUG = "yucatan"
PREFIJO = "YUC"


def _build_synthetic_json(
    cvegeo: str, anio: int, slug: str, txt_text: str,
) -> dict:
    """Construye un dict v2 listo para serializar."""
    return {
        "predial": {
            "tipo_esquema": "otro_no_clasificado",
            "categoria": "municipio_sin_impuesto",
            "descripcion_estructural": (
                "Ley de ingresos en formato corto: contiene únicamente "
                "pronóstico presupuestal por concepto (línea 'Impuesto Predial $X' "
                "o 'I.- Predial $X') sin secciones que detallen tarifas, tasas, "
                "montos al millar ni rangos. Las contribuciones se rigen por la "
                "Ley General de Hacienda Municipal del Estado de Yucatán "
                "(referenciada típicamente en Art. 13-15 del articulado)."
            ),
            "tabla_cruda": [],
            "minimo_predial": None,
            "comentarios": (
                "Síntesis determinista a partir del fallback `short_form` del "
                "segmentador de Yucatán. No se invocó LLM porque el documento "
                "fuente no contiene información de tarifa."
            ),
        },
        "_meta": {"fuente": "txt", "modelo": "synthesized_short_form"},
        "_meta_v2": {
            "intentos": 0,
            "requiere_revision": False,
            "razon": None,
            "tokens": {"input": 0, "output": 0, "cached": 0},
            "cvegeo": cvegeo,
            "estado": ESTADO_SLUG,
            "anio": anio,
        },
    }


def main():
    # Cargar segment.csv para identificar los focus_predial con predial_method=short_form
    segment_csv = Path(f"data/{ESTADO_SLUG}/meta/segment.csv")
    if not segment_csv.exists():
        print(f"[ERROR] No existe {segment_csv}. Ejecuta primero `run_pipeline yucatan --steps segment`.")
        return

    matcher = MuniMatcher(cve_ent=CVE_ENT_YUCATAN)
    inegi_lookup_by_slug: dict[str, str] = {}
    with open("catalogs/municipios_inegi.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("CVE_ENT") or "").strip() != CVE_ENT_YUCATAN:
                continue
            slug = slugify(r.get("NOM_MUN") or "")
            if slug:
                inegi_lookup_by_slug[slug] = (r.get("CVE_MUN") or "").strip()

    rows = list(csv.DictReader(open(segment_csv, encoding="utf-8-sig")))
    short_form_rows = [r for r in rows if r.get("predial_method") == "short_form"]
    print(f"Filas short_form en segment.csv: {len(short_form_rows)}")

    out_dir = Path("predial-mx-v2") / ESTADO_SLUG
    out_dir.mkdir(parents=True, exist_ok=True)

    n_written = 0
    n_skipped = 0
    n_no_cvegeo = 0

    for r in short_form_rows:
        anio = int(r["ejercicio"])
        slug = (r.get("slug") or "").strip()
        txt_file = (r.get("txt_file") or "").strip()
        if not slug or not txt_file:
            continue

        # Verificar el TXT contiene el header del fallback (sanity check).
        txt_path = Path(f"data/{ESTADO_SLUG}/focus_predial/{anio}/{txt_file}")
        if not txt_path.exists():
            print(f"  [SKIP] TXT no existe: {txt_path}")
            continue
        txt_text = txt_path.read_text(encoding="utf-8", errors="replace")
        if SHORT_FORM_HEADER_TAG not in txt_text:
            # No es realmente short_form (puede ser de un run anterior); skip.
            continue

        # cve_mun via catálogo INEGI normalizado
        cve_mun = inegi_lookup_by_slug.get(slug)
        if not cve_mun:
            # Fallback via MuniMatcher (más tolerante a typos/aliases)
            mm = matcher.match(slug)
            cve_mun = (mm.cve_mun or "").strip() or None
        if not cve_mun:
            n_no_cvegeo += 1
            continue

        cvegeo = f"{CVE_ENT_YUCATAN}{cve_mun}"
        out_name = f"{PREFIJO}_PREDIAL_{anio}_{slug}.json"
        out_path = out_dir / out_name

        if out_path.exists():
            # Solo sobrescribir si el archivo existente es de extracción LLM previa
            # con tipo_esquema vacío o también synthesized — para no destruir extracciones reales.
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
                pred = existing.get("predial") if isinstance(existing, dict) else None
                modelo = (existing.get("_meta") or {}).get("modelo", "")
                if pred is not None and pred.get("tipo_esquema") and modelo != "synthesized_short_form":
                    n_skipped += 1
                    continue
            except Exception:
                pass

        doc = _build_synthetic_json(cvegeo, anio, slug, txt_text)
        out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        n_written += 1

    print(f"\n=== Sintetizados {n_written} JSONs en {out_dir}/")
    print(f"    Saltados (extracción LLM previa válida): {n_skipped}")
    print(f"    Sin cvegeo (slug no resuelto): {n_no_cvegeo}")


if __name__ == "__main__":
    main()
