"""Cuantifica inconsistencias en la clasificación schema_v2 sobre el corpus completo.

Itera todos los JSONs de predial (predial-mx-v2/ canónicos + data/oaxaca/ vía
reclasificar()) y corre varios detectores ortogonales:

  estructurales (las herramientas verdaderas para "fixearlo bien"):
    1. mixto_monocolumna_cuotafija   mixto con 1 sola columna, todas cuota_fija
                                     → candidato a `cuota_fija_escalonada`
    2. tabla_vacia                   tipo válido pero `tabla == []`
    3. legacy_cuota_fija             tipo == 'cuota_fija' (sin _simple/_escalonada)
    4. legacy_desconocido            tipo == 'desconocido'
    5. rangos_no_monotonos           progresivo/mixto con cuota fija decreciente

  unidades (representación, no error de extracción):
    6. tarifa_millar_factor          tarifa_millar con max(tasa) < 0.5 (factor)
    7. tasa_unica_unidad_factor      tasa_unica con valor < unidad declarada

  segmentación (el caso Juventino Rosas — la fuente fue otra parte del doc):
    8. cuota_es_minimo               cuota_fija_simple cuya desc contiene
                                     'mínim*' o cuyo monto == minimo_predial.monto
    9. desc_transitorios             cualquier fila cuya descripción menciona
                                     transitorios / vigencia / abrogación

Salidas en `output/anexos/`:
  - inconsistencias_resumen.csv   tabla detector × n × denominador × %
  - inconsistencias_detalle.csv   un renglón por hallazgo con ruta del JSON
  - inconsistencias.md            reporte legible con muestras

Uso:
  python -m scripts.qa_inconsistencias
"""

from __future__ import annotations

import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

from scripts.temps.build_anexo_esquemas import (
    DATA_ROOT,
    ESTADO_SLUG_PRETTY,
    V2_ROOT,
    pretty_muni,
)
from src.core.validation import reclasificar

OUT_DIR = Path("output/anexos")
_FNAME_RE = re.compile(r"_PREDIAL_(\d{4})_(.+)$")
_RE_TRANSITORIO = re.compile(
    r"\b(transitor|abrog|salario\s*m[ií]nim|d[ií]as?\s+de\s+salario|vsm\b|"
    r"vigencia|publicaci[oó]n\s+oficial)",
    re.IGNORECASE,
)

# Tipos "reales" (excluye otro_no_clasificado, que es escape hatch).
TIPOS_REALES = {
    "tarifa_millar", "progresivo", "tasa_unica",
    "cuota_fija_simple", "cuota_fija_escalonada", "cuota_fija", "mixto",
}


def _norm(s: str) -> str:
    n = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in n if unicodedata.category(c) != "Mn").lower()


# ── Detectores: cada uno regresa una "señal" str o None ──

def det_mixto_monocol_cuotafija(pred: dict) -> str | None:
    if pred.get("tipo_esquema") != "mixto":
        return None
    tabla = pred.get("tabla") or []
    if not tabla:
        return None
    nombres, tipos = set(), set()
    for r in tabla:
        cols = r.get("columnas") or []
        if len(cols) != 1:
            return None
        nombres.add(cols[0].get("nombre"))
        tipos.add(cols[0].get("tipo"))
    if len(nombres) == 1 and tipos == {"cuota_fija"}:
        return f"col='{next(iter(nombres))}'"
    return None


def det_tabla_vacia(pred: dict) -> str | None:
    t = pred.get("tipo_esquema")
    if t not in TIPOS_REALES:
        return None
    if (pred.get("tabla") or []) == []:
        return t
    return None


def det_legacy_cuota_fija(pred: dict) -> str | None:
    return "literal" if pred.get("tipo_esquema") == "cuota_fija" else None


def det_legacy_desconocido(pred: dict) -> str | None:
    return "desconocido" if pred.get("tipo_esquema") == "desconocido" else None


def det_rangos_no_monotonos(pred: dict) -> str | None:
    t = pred.get("tipo_esquema")
    if t not in {"progresivo", "mixto"}:
        return None
    tabla = pred.get("tabla") or []
    if len(tabla) < 2:
        return None
    if t == "progresivo":
        cs = [float(r.get("cuota_fija") or 0) for r in tabla]
        for i in range(len(cs) - 1):
            if cs[i + 1] < cs[i] - 0.01:
                return f"cuota_fija {cs[i]}→{cs[i+1]} (rango {i+1}→{i+2})"
        return None
    # mixto: monotonía por columna cuota_fija
    by_col: dict[str, list[float]] = defaultdict(list)
    for r in tabla:
        for c in r.get("columnas") or []:
            if c.get("tipo") == "cuota_fija":
                by_col[c.get("nombre")].append(float(c.get("valor") or 0))
    for nombre, vals in by_col.items():
        for i in range(len(vals) - 1):
            if vals[i + 1] < vals[i] - 0.01:
                return f"col '{nombre}': {vals[i]}→{vals[i+1]}"
    return None


def det_tarifa_millar_factor(pred: dict) -> str | None:
    if pred.get("tipo_esquema") != "tarifa_millar":
        return None
    tasas = [r.get("tasa_millar") for r in (pred.get("tabla") or []) if r.get("tasa_millar")]
    if not tasas:
        return None
    if max(tasas) < 0.5:
        return f"max={max(tasas):.5f}"
    return None


def det_tasa_unica_unidad_factor(pred: dict) -> str | None:
    if pred.get("tipo_esquema") != "tasa_unica":
        return None
    tabla = pred.get("tabla") or []
    if not tabla:
        return None
    r = tabla[0]
    tasa, unidad = r.get("tasa"), r.get("unidad", "")
    if tasa is None:
        return None
    if unidad == "porcentaje" and tasa < 0.05:
        return f"porcentaje, tasa={tasa}"
    if unidad == "al_millar" and tasa < 0.5:
        return f"al_millar, tasa={tasa}"
    return None


def det_cuota_es_minimo(pred: dict) -> str | None:
    """Caso Juventino Rosas: la 'cuota fija' es realmente el mínimo predial,
    típicamente porque la sección extraída fue 'transitorios' o sólo el artículo
    del mínimo."""
    t = pred.get("tipo_esquema")
    if t not in {"cuota_fija_simple", "cuota_fija"}:
        return None
    tabla = pred.get("tabla") or []
    if not tabla:
        return None
    r = tabla[0]
    desc = _norm(r.get("descripcion", ""))
    monto = r.get("monto")
    senales = []
    if "minim" in desc:
        senales.append("desc=minim*")
    min_p = pred.get("minimo_predial") or {}
    m_min = min_p.get("monto")
    if monto is not None and m_min is not None:
        try:
            if abs(float(monto) - float(m_min)) < 0.01:
                senales.append("monto==minimo_predial")
        except (TypeError, ValueError):
            pass
    return f"{';'.join(senales)} (monto={monto})" if senales else None


def det_desc_transitorios(pred: dict) -> str | None:
    for r in pred.get("tabla") or []:
        desc = r.get("descripcion", "") or ""
        m = _RE_TRANSITORIO.search(desc)
        if m:
            return f"hit='{m.group(0)}' en desc='{desc[:80]}'"
    return None


DETECTORES = [
    ("mixto_monocolumna_cuotafija", det_mixto_monocol_cuotafija, "mixto"),
    ("tabla_vacia", det_tabla_vacia, "tipos reales"),
    ("legacy_cuota_fija", det_legacy_cuota_fija, "todo el corpus"),
    ("legacy_desconocido", det_legacy_desconocido, "todo el corpus"),
    ("rangos_no_monotonos", det_rangos_no_monotonos, "progresivo+mixto"),
    ("tarifa_millar_factor", det_tarifa_millar_factor, "tarifa_millar"),
    ("tasa_unica_unidad_factor", det_tasa_unica_unidad_factor, "tasa_unica"),
    ("cuota_es_minimo", det_cuota_es_minimo, "cuota_fija_simple+legacy"),
    ("desc_transitorios", det_desc_transitorios, "tipos con desc"),
]

# Denominador (pool) por detector — set de tipo_esquema que cuenta.
DENOMINADOR_TIPOS = {
    "mixto_monocolumna_cuotafija": {"mixto"},
    "tabla_vacia": TIPOS_REALES,
    "legacy_cuota_fija": None,  # corpus total
    "legacy_desconocido": None,
    "rangos_no_monotonos": {"progresivo", "mixto"},
    "tarifa_millar_factor": {"tarifa_millar"},
    "tasa_unica_unidad_factor": {"tasa_unica"},
    "cuota_es_minimo": {"cuota_fija_simple", "cuota_fija"},
    "desc_transitorios": TIPOS_REALES,
}


# ── Corpus iterator ──

def iter_corpus():
    """Yield (estado_slug, anio, slug, predial_dict, json_path)."""
    # v2 canónicos
    if V2_ROOT.exists():
        for est_dir in sorted(p for p in V2_ROOT.iterdir() if p.is_dir()):
            est_slug = est_dir.name
            for p in sorted(est_dir.glob("*_PREDIAL_*.json")):
                m = _FNAME_RE.search(p.stem)
                if not m:
                    continue
                try:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                pred = doc.get("predial")
                if isinstance(pred, dict) and pred.get("tipo_esquema") and "tabla" in pred:
                    yield est_slug, int(m.group(1)), m.group(2), pred, p
    # oaxaca (v1 → reclasificar)
    ox = DATA_ROOT / "oaxaca" / "json_predial"
    if ox.exists():
        for p in sorted(ox.rglob("*_PREDIAL_*.json")):
            m = _FNAME_RE.search(p.stem)
            if not m:
                continue
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            pred = doc.get("predial")
            if not isinstance(pred, dict):
                continue
            try:
                inst = reclasificar(pred)
            except Exception:
                continue
            yield "oaxaca", int(m.group(1)), m.group(2), inst.model_dump(), p


# ── Pipeline ──

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Iterando corpus (puede tardar ~1 min)...")
    total = 0
    por_tipo: dict[str, int] = defaultdict(int)
    hallazgos: dict[str, list[dict]] = defaultdict(list)

    for est_slug, anio, slug, pred, path in iter_corpus():
        total += 1
        tipo = pred.get("tipo_esquema", "?")
        por_tipo[tipo] += 1
        if total % 2000 == 0:
            print(f"  {total} JSONs procesados...")
        for nombre, fn, _pool_label in DETECTORES:
            try:
                senal = fn(pred)
            except Exception as e:
                senal = f"DETECTOR_ERROR: {e}"
            if senal:
                hallazgos[nombre].append({
                    "detector": nombre,
                    "estado": ESTADO_SLUG_PRETTY.get(est_slug, est_slug),
                    "municipio": pretty_muni(slug),
                    "anio": anio,
                    "tipo_esquema": tipo,
                    "senal": senal,
                    "json_path": path.as_posix(),
                })

    print(f"\nTotal JSONs procesados: {total}")

    # ── Resumen CSV + tabla por consola ──
    resumen_rows = []
    print(f"\n{'detector':32s} {'n':>6s}  {'pool':>6s}  {'%':>6s}  pool_label")
    print("-" * 80)
    for nombre, _fn, pool_label in DETECTORES:
        n = len(hallazgos.get(nombre, []))
        tipos_pool = DENOMINADOR_TIPOS[nombre]
        if tipos_pool is None:
            denom = total
        else:
            denom = sum(c for t, c in por_tipo.items() if t in tipos_pool)
        pct = (100 * n / denom) if denom else 0.0
        resumen_rows.append({
            "detector": nombre, "n_casos": n, "denominador": denom,
            "pct": f"{pct:.2f}", "pool_label": pool_label,
        })
        print(f"{nombre:32s} {n:6d}  {denom:6d}  {pct:5.2f}%  {pool_label}")

    res_csv = OUT_DIR / "inconsistencias_resumen.csv"
    with res_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["detector", "n_casos", "denominador", "pct", "pool_label"])
        w.writeheader()
        w.writerows(resumen_rows)
    print(f"\nResumen: {res_csv}")

    # ── Detalle CSV (todos los hallazgos) ──
    det_csv = OUT_DIR / "inconsistencias_detalle.csv"
    all_rows = [row for filas in hallazgos.values() for row in filas]
    if all_rows:
        with det_csv.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(all_rows[0].keys()))
            w.writeheader()
            w.writerows(all_rows)
    print(f"Detalle: {det_csv}  ({len(all_rows)} hallazgos)")

    # ── Reporte markdown con muestras ──
    md = [
        "# Inconsistencias de clasificación schema_v2 — cuantificación",
        "",
        f"Corpus: **{total} JSONs** (predial-mx-v2/ + data/oaxaca/ vía reclasificar).",
        "",
        "## Resumen",
        "",
        "| Detector | n | pool | % del pool | pool |",
        "|---|---:|---:|---:|---|",
    ]
    for row in resumen_rows:
        md.append(
            f"| `{row['detector']}` | {row['n_casos']} | {row['denominador']} | "
            f"{row['pct']}% | {row['pool_label']} |"
        )
    md.append("")
    md.append("## Distribución de tipos en el corpus")
    md.append("")
    md.append("| tipo_esquema | n |")
    md.append("|---|---:|")
    for t, c in sorted(por_tipo.items(), key=lambda x: -x[1]):
        md.append(f"| `{t}` | {c} |")
    md.append("")
    md.append("## Muestras por detector (primeros 5)")
    md.append("")
    for nombre, _fn, _pool in DETECTORES:
        filas = hallazgos.get(nombre, [])
        md.append(f"### `{nombre}` — {len(filas)} casos")
        md.append("")
        if not filas:
            md.append("_sin hallazgos_")
            md.append("")
            continue
        for row in filas[:5]:
            md.append(
                f"- **{row['municipio']}, {row['estado']} ({row['anio']})** "
                f"— tipo=`{row['tipo_esquema']}` — {row['senal']}"
            )
            md.append(f"  - `{row['json_path']}`")
        if len(filas) > 5:
            md.append(f"- … y {len(filas) - 5} más (ver `inconsistencias_detalle.csv`).")
        md.append("")

    md_path = OUT_DIR / "inconsistencias.md"
    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"Reporte: {md_path}")


if __name__ == "__main__":
    main()
