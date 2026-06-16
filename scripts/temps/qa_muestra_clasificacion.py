"""Muestra estratificada aleatoria para QA de clasificaciones de esquemas.

Para cada uno de los 5 esquemas de la tesis escoge k municipios-año al azar
desde `output/panel_v2_raw.csv` y emite un reporte markdown con: clasificación
canónica schema_v2, ruta del JSON fuente, ruta del TXT del segmento (cuando
aplica, sólo para estados con extracción LLM), comentarios del extractor y un
preview JSON de las primeras filas de la tabla, para que se pueda verificar
contra el Periódico Oficial fuente.

Uso:
  python -m scripts.qa_muestra_clasificacion                # seed=42, k=3
  python -m scripts.qa_muestra_clasificacion --seed 7 --k 5
  python -m scripts.qa_muestra_clasificacion --solo mixto   # un esquema
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path

import pandas as pd

from scripts.temps.build_anexo_esquemas import (
    DATA_ROOT,
    PANEL_RAW,
    SCHEMA_V2_A_TESIS,
    TESIS_LABEL,
    TESIS_ORDEN,
    V2_ROOT,
)
from src.core.validation import reclasificar

# panel pretty name (INEGI) -> directorio slug
ESTADO_PRETTY_A_SLUG = {
    "Chihuahua": "chihuahua",
    "Coahuila de Zaragoza": "coahuila",
    "Colima": "colima",
    "Guanajuato": "guanajuato",
    "Jalisco": "jalisco",
    "Mexico": "edomex",
    "Oaxaca": "oaxaca",
    "Queretaro": "queretaro",
    "San Luis Potosi": "sanluispotosi",
    "Sinaloa": "sinaloa",
    "Sonora": "sonora",
    "Tabasco": "tabasco",
    "Tamaulipas": "tamaulipas",
    "Yucatan": "yucatan",
}

# Estados con extracción LLM (tienen focus_predial); los demás son código estatal.
ESTADOS_LLM = {
    "coahuila", "guanajuato", "jalisco", "oaxaca", "queretaro",
    "sanluispotosi", "sonora", "tamaulipas", "yucatan",
}

_FNAME_RE = re.compile(r"_PREDIAL_(\d{4})_(.+)$")


def slugify(name: str) -> str:
    """nombre INEGI -> slug snake_case sin acentos."""
    n = unicodedata.normalize("NFD", name)
    n = "".join(c for c in n if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_")


def _index_estado(estado_slug: str) -> dict[tuple[int, str], Path]:
    """Construye {(anio, slug): ruta_json} para un estado, priorizando
    predial-mx-v2/ sobre data/<estado>/json_predial/."""
    idx: dict[tuple[int, str], Path] = {}
    for root in (V2_ROOT / estado_slug, DATA_ROOT / estado_slug / "json_predial"):
        if not root.exists():
            continue
        for p in root.rglob("*_PREDIAL_*.json"):
            m = _FNAME_RE.search(p.stem)
            if m:
                idx.setdefault((int(m.group(1)), m.group(2)), p)
    return idx


def _localizar(idx: dict, anio: int, muni: str) -> tuple[Path | None, str | None]:
    """Devuelve (ruta, slug_archivo) para el muni-año, con fallback fuzzy."""
    s = slugify(muni)
    if (anio, s) in idx:
        return idx[(anio, s)], s
    # Fallback: cualquier slug que contenga / esté contenido en el slugify.
    for (a, k), p in idx.items():
        if a == anio and (s in k or k in s):
            return p, k
    return None, None


def _cargar_predial(path: Path) -> dict:
    """Predial v2 dict: directo si predial-mx-v2, vía reclasificar si data/v1."""
    doc = json.loads(path.read_text(encoding="utf-8"))
    pred = doc.get("predial")
    if not isinstance(pred, dict):
        return {}
    if "tabla" in pred and pred.get("tipo_esquema"):
        return pred
    return reclasificar(pred).model_dump()


def _segment_txt(estado_slug: str, anio: int, slug: str) -> Path | None:
    if estado_slug not in ESTADOS_LLM:
        return None
    base = DATA_ROOT / estado_slug / "focus_predial" / str(anio)
    if not base.exists():
        return None
    for p in base.glob(f"*_PREDIAL_{anio}_{slug}.txt"):
        return p
    return None


def _preview(pred: dict, n: int = 3) -> str:
    tabla = pred.get("tabla") or []
    if not tabla:
        return "(sin tabla)"
    return json.dumps(tabla[:n], ensure_ascii=False, indent=2)


def build_report(seed: int, k: int, solo: str | None, out_path: Path) -> None:
    df = pd.read_csv(PANEL_RAW, dtype=str)
    df["ejercicio"] = df["ejercicio"].astype(int)
    df = df[df["estado"].isin(ESTADO_PRETTY_A_SLUG)].copy()
    df["esquema"] = df["tipo_esquema"].map(SCHEMA_V2_A_TESIS).fillna("otro")

    cats = [c for c in TESIS_ORDEN if c != "otro"]
    if solo:
        cats = [c for c in cats if c == solo]
        if not cats:
            raise SystemExit(f"--solo desconocido: {solo}; opciones: {TESIS_ORDEN}")

    lines = [
        f"# QA muestra aleatoria de clasificaciones (seed={seed}, k={k})",
        "",
        "Fuente: `output/panel_v2_raw.csv` (observaciones, sin imputación; "
        "clasificación canónica schema_v2 vía la capa de validación).",
        "",
    ]

    indices: dict[str, dict] = {}
    for cat in cats:
        pool = df[df["esquema"] == cat]
        if pool.empty:
            continue
        # random_state determinista por categoría a partir del seed.
        rs = (seed * 1009 + abs(hash(cat))) % (2**31 - 1)
        sample = pool.sample(n=min(k, len(pool)), random_state=rs)
        lines.append(f"## {TESIS_LABEL[cat]}  — `{cat}`  ({len(pool)} casos en pool)")
        lines.append("")
        for _, row in sample.iterrows():
            est_pretty = row["estado"]
            est_slug = ESTADO_PRETTY_A_SLUG[est_pretty]
            muni = row["municipio"] or "(sin nombre)"
            anio = int(row["ejercicio"])
            tipo_v2 = row["tipo_esquema"]

            idx = indices.setdefault(est_slug, _index_estado(est_slug))
            path, slug_arch = _localizar(idx, anio, muni)

            lines.append(f"### {muni}, {est_pretty} ({anio})")
            lines.append(f"- **clasificado como**: `{tipo_v2}`")
            if path is None:
                lines.append(
                    f"- **JSON**: no encontrado para slug=`{slugify(muni)}` en {est_slug}/{anio}"
                )
                lines.append("")
                continue
            try:
                pred = _cargar_predial(path)
            except Exception as e:
                pred = {"error": str(e)}
            tabla = pred.get("tabla") or []
            comentarios = (pred.get("comentarios") or "").strip()
            justif = (pred.get("clasificacion_justificacion") or "").strip()
            seg = _segment_txt(est_slug, anio, slug_arch)
            min_p = pred.get("minimo_predial")

            lines.append(f"- **n_filas**: {len(tabla)}")
            lines.append(f"- **JSON**: `{path.as_posix()}`")
            if seg:
                lines.append(f"- **TXT segmento**: `{seg.as_posix()}`")
            else:
                src = "código estatal hardcoded" if est_slug not in ESTADOS_LLM else "TXT no encontrado"
                lines.append(f"- **TXT segmento**: ({src})")
            if min_p:
                lines.append(
                    f"- **mínimo predial**: {min_p.get('monto')} {min_p.get('unidad','')} "
                    f"({min_p.get('periodicidad','')})"
                )
            if justif:
                lines.append(f"- **justificación clasificación**: {justif[:240]}")
            if comentarios:
                lines.append(f"- **comentarios extractor**: {comentarios[:300]}")
            lines.append("- **preview tabla** (primeras 3 filas):")
            lines.append("```json")
            lines.append(_preview(pred, 3))
            lines.append("```")
            lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Reporte: {out_path}")
    print(f"Casos: {sum(1 for line in lines if line.startswith('### '))}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", type=int, default=42, help="Semilla aleatoria (default 42).")
    ap.add_argument("--k", type=int, default=3, help="Casos por esquema (default 3).")
    ap.add_argument("--solo", choices=TESIS_ORDEN, help="Solo un esquema.")
    ap.add_argument(
        "--out", default="output/anexos/qa_muestra_clasificacion.md",
        help="Ruta del reporte markdown.",
    )
    args = ap.parse_args()
    build_report(args.seed, args.k, args.solo, Path(args.out))


if __name__ == "__main__":
    main()
