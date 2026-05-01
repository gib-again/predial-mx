"""Panel taxonómico v2: cvegeo × ejercicio × estado × municipio × tipo_esquema
× numero_rangos × monto_max_rango.

Lee de tres fuentes (mutuamente excluyentes):

  1. predial-mx-v2/{estado}/                — ya en schema_v2
       coahuila, guanajuato, queretaro, tamaulipas, yucatan
       + colima, edomex, sinaloa, tabasco (tras convert_hardcoded_to_v2)

  2. data/{jalisco,oaxaca}/json_predial/   — formato v1 PredialSchema
       (jalisco: predial-mx-v2/jalisco/ es sparse y se descarta)

  3. data/chihuahua/json_predial/           — formato hardcoded (in-memory)

`tipo_esquema` se obtiene:
  - fuente 1: directo del JSON.
  - fuente 2: vía `reclasificar()` (capa de validación).
  - fuente 3: vía adapter inline (`adapt_chihuahua`) + validación schema_v2.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from pydantic import ValidationError

from src.core.adapters_hardcoded import adapt_chihuahua
from src.core.consolidate import _ESTADO_CVE, _load_inegi
from src.core.text_utils import parse_predial_filename
from src.core.validation import reclasificar
from src.extraction.schema_v2 import (
    CuotaFijaEscalonadaSchema,
    MixtoSchema,
    ProgresivoSchema,
)


V2_ESTADOS = {
    "coahuila", "guanajuato", "queretaro", "tamaulipas", "yucatan",
    "colima", "edomex", "sinaloa", "tabasco",
    "chihuahua", "jalisco",
}
V1_ESTADOS_INMEM = {"oaxaca"}
HARDCODED_INMEM: set[str] = set()

ESQUEMAS_CON_RANGOS = {"progresivo", "cuota_fija_escalonada", "mixto"}

# Prefijos de archivo para los estados in-memory.
_PREFIJOS_INMEM = {
    "jalisco": "JAL",
    "oaxaca": "OAX",
    "chihuahua": "CHIH",
}

# Códigos INEGI para estados que no están en consolidate._ESTADO_CVE.
_EXTRA_ESTADO_CVE = {
    "chihuahua": "08",
    "colima":    "06",
    "edomex":    "15",
    "oaxaca":    "20",
    "sinaloa":   "25",
    "tabasco":   "27",
}


# ── Helpers ──

def _rangos_y_max(tabla: list) -> tuple[int | None, float | None]:
    """numero_rangos y monto_max_rango. Solo para variantes con rangos."""
    if not tabla:
        return None, None
    n = len(tabla)
    superiores = []
    for r in tabla:
        sup = r.get("superior") if isinstance(r, dict) else getattr(r, "superior", None)
        if sup is not None:
            superiores.append(float(sup))
    monto_max = max(superiores) if superiores else None
    return n, monto_max


def _row_template(cvegeo: str, ejercicio: int, slug: str, estado_slug: str) -> dict:
    return {
        "cvegeo": cvegeo,
        "ejercicio": ejercicio,
        "estado": "",
        "municipio": "",
        "tipo_esquema": "",
        "numero_rangos": "",
        "monto_max_rango": "",
        "_slug": slug,
        "_estado_slug": estado_slug,
    }


def _fill_rangos(row: dict, tipo: str, tabla) -> None:
    if tipo in ESQUEMAS_CON_RANGOS:
        n, mmax = _rangos_y_max(tabla)
        row["numero_rangos"] = n if n is not None else ""
        row["monto_max_rango"] = mmax if mmax is not None else ""


# ── Fuente 1: predial-mx-v2/{estado}/*.json ──

def _row_from_v2_json(json_path: Path, estado_slug: str) -> dict | None:
    try:
        doc = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    predial = doc.get("predial")
    if not isinstance(predial, dict) or not predial.get("tipo_esquema"):
        # Extracción fallida (predial=null) o sin tipo — descartar.
        return None
    meta = doc.get("_meta_v2") or {}
    cvegeo = str(meta.get("cvegeo") or "").zfill(5)
    anio = meta.get("anio")
    if not cvegeo or anio is None:
        return None

    tipo = predial["tipo_esquema"]
    # Para otro_no_clasificado la tabla puede venir en `tabla_cruda`, sin `tabla`.
    tabla = predial.get("tabla") or []

    # Slug desde el nombre de archivo (cae al cve_mun + nom_mun para enriquecer).
    slug = json_path.stem.split("_PREDIAL_", 1)[-1]
    if "_" in slug:
        # COAH_PREDIAL_2014_saltillo → saltillo (split en _PREDIAL_ ya removió prefijo+año).
        # En caso edge, parts puede venir con año adelante. Reusar parse si falla.
        slug = "_".join(slug.split("_")[1:]) if slug.split("_")[0].isdigit() else slug

    row = _row_template(cvegeo, int(anio), slug, estado_slug)
    row["tipo_esquema"] = tipo
    _fill_rangos(row, tipo, tabla)
    return row


def _iter_v2_rows(v2_root: Path) -> list[dict]:
    rows: list[dict] = []
    for estado in sorted(V2_ESTADOS):
        est_dir = v2_root / estado
        if not est_dir.exists():
            continue
        for jp in sorted(est_dir.glob("*.json")):
            r = _row_from_v2_json(jp, estado)
            if r is not None:
                rows.append(r)
    return rows


# ── Fuente 2: data/{jalisco,oaxaca}/json_predial/ con reclasificar() ──

def _row_from_v1_inmem(json_path: Path, estado_slug: str, prefijo: str,
                       inegi: dict) -> dict | None:
    try:
        doc = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    predial = doc.get("predial")
    if not isinstance(predial, dict):
        return None

    try:
        anio, slug, _ = parse_predial_filename(json_path, prefijo)
    except ValueError:
        return None

    cve_ent = _ESTADO_CVE.get(estado_slug) or _EXTRA_ESTADO_CVE.get(estado_slug)
    if not cve_ent:
        return None
    info = inegi.get((cve_ent, slug))
    if not info:
        return None
    cvegeo = f"{cve_ent}{info['cve_mun']}"

    inst = reclasificar(predial)
    tipo = inst.tipo_esquema
    tabla = list(inst.tabla) if hasattr(inst, "tabla") else []

    row = _row_template(cvegeo, anio, slug, estado_slug)
    row["tipo_esquema"] = tipo
    _fill_rangos(row, tipo, tabla)
    return row


def _iter_v1_inmem_rows(data_root: Path, inegi: dict) -> list[dict]:
    rows: list[dict] = []
    for estado in sorted(V1_ESTADOS_INMEM):
        prefijo = _PREFIJOS_INMEM[estado]
        json_dir = data_root / estado / "json_predial"
        if not json_dir.exists():
            continue
        for jp in sorted(json_dir.rglob("*.json")):
            r = _row_from_v1_inmem(jp, estado, prefijo, inegi)
            if r is not None:
                rows.append(r)
    return rows


# ── Fuente 3: data/chihuahua/json_predial/ vía adapter inline ──

def _row_from_chihuahua_inmem(json_path: Path, inegi: dict) -> dict | None:
    try:
        src = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return None

    cve_ent = src.get("cve_ent") or _EXTRA_ESTADO_CVE["chihuahua"]
    cve_mun = src.get("cve_mun")
    if not (cve_ent and cve_mun):
        return None
    cvegeo = f"{cve_ent}{cve_mun}"
    slug = src.get("slug") or json_path.stem.split("_", 2)[-1]
    anio = int(src["ejercicio"])

    try:
        v2_doc = adapt_chihuahua(src)
    except Exception:
        return None
    predial_v2 = v2_doc["predial"]
    tipo = predial_v2["tipo_esquema"]

    # Validar; si falla, dejar vacíos los campos de rangos.
    Variant = {"progresivo": ProgresivoSchema,
               "cuota_fija_escalonada": CuotaFijaEscalonadaSchema}.get(tipo)
    tabla = predial_v2.get("tabla") or []
    if Variant is not None:
        try:
            Variant.model_validate(predial_v2)
        except ValidationError:
            tipo = "otro_no_clasificado"
            tabla = []

    row = _row_template(cvegeo, anio, slug, "chihuahua")
    row["tipo_esquema"] = tipo
    _fill_rangos(row, tipo, tabla)
    return row


def _iter_chihuahua_rows(data_root: Path, inegi: dict) -> list[dict]:
    rows: list[dict] = []
    for estado in sorted(HARDCODED_INMEM):
        json_dir = data_root / estado / "json_predial"
        if not json_dir.exists():
            continue
        for jp in sorted(json_dir.rglob("*.json")):
            r = _row_from_chihuahua_inmem(jp, inegi)
            if r is not None:
                rows.append(r)
    return rows


# ── Enriquecer y escribir ──

def _build_inegi_by_cvegeo(catalog_path: Path) -> dict[str, dict]:
    """Lee el catálogo INEGI directamente y construye índice por CVEGEO."""
    out: dict[str, dict] = {}
    if not catalog_path.exists():
        return out
    with catalog_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cvegeo = (row.get("CVEGEO") or "").strip()
            if not cvegeo:
                cve_ent = (row.get("CVE_ENT") or "").strip()
                cve_mun = (row.get("CVE_MUN") or "").strip()
                cvegeo = f"{cve_ent}{cve_mun}"
            if cvegeo and len(cvegeo) >= 4:
                out[cvegeo.zfill(5)] = {
                    "nom_ent": (row.get("NOM_ENT") or "").strip(),
                    "nom_mun": (row.get("NOM_MUN") or "").strip(),
                }
    return out


def _enrich(rows: list[dict], inegi_by_cvegeo: dict[str, dict]) -> None:
    for row in rows:
        info = inegi_by_cvegeo.get(row["cvegeo"])
        if info:
            row["estado"] = info["nom_ent"]
            row["municipio"] = info["nom_mun"]


def _write_csv(rows: list[dict], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["cvegeo", "ejercicio", "estado", "municipio",
            "tipo_esquema", "numero_rangos", "monto_max_rango"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow(row)


# ── Pipeline público ──

def build_panel_v2(
    v2_root: Path = Path("predial-mx-v2"),
    data_root: Path = Path("data"),
    catalog_path: Path = Path("catalogs/municipios_inegi.csv"),
    out_csv: Path = Path("output/panel_v2.csv"),
) -> Path:
    print("Cargando catálogo INEGI...")
    # _load_inegi rellena el cache para reclasificar v1 (key: (cve_ent, slug)).
    inegi_by_slug = _load_inegi(catalog_path)
    inegi_by_cvegeo = _build_inegi_by_cvegeo(catalog_path)
    print(f"  munis en catálogo: {len(inegi_by_cvegeo)}")

    print("\nLeyendo predial-mx-v2/...")
    rows_v2 = _iter_v2_rows(v2_root)
    print(f"  filas v2: {len(rows_v2)}")

    print("\nLeyendo data/{jalisco,oaxaca}/json_predial/...")
    rows_v1 = _iter_v1_inmem_rows(data_root, inegi_by_slug)
    print(f"  filas v1 in-memory: {len(rows_v1)}")

    print("\nLeyendo data/chihuahua/json_predial/...")
    rows_chih = _iter_chihuahua_rows(data_root, inegi_by_slug)
    print(f"  filas chihuahua: {len(rows_chih)}")

    rows = rows_v2 + rows_v1 + rows_chih

    # Filtrar años fuera de rango plausible (artefactos de filename/OCR).
    n_before = len(rows)
    rows = [r for r in rows if 2010 <= r["ejercicio"] <= 2026]
    if n_before != len(rows):
        print(f"  filas fuera de rango año descartadas: {n_before - len(rows)}")

    # Dedupe por (cvegeo, ejercicio); v2 gana sobre v1 (orden de concatenación).
    seen: set[tuple[str, int]] = set()
    deduped: list[dict] = []
    dups = 0
    for row in rows:
        key = (row["cvegeo"], row["ejercicio"])
        if key in seen:
            dups += 1
            continue
        seen.add(key)
        deduped.append(row)
    if dups:
        print(f"  duplicados descartados: {dups}")

    print("\nEnriqueciendo con catálogo INEGI...")
    _enrich(deduped, inegi_by_cvegeo)

    deduped.sort(key=lambda r: (r["cvegeo"], r["ejercicio"]))

    print(f"\nEscribiendo {out_csv} ({len(deduped)} filas)...")
    _write_csv(deduped, out_csv)

    # Reporte de cobertura.
    by_estado: dict[str, int] = {}
    by_tipo: dict[str, int] = {}
    for row in deduped:
        by_estado[row["estado"] or "(sin estado)"] = by_estado.get(row["estado"] or "(sin estado)", 0) + 1
        by_tipo[row["tipo_esquema"] or "(vacío)"] = by_tipo.get(row["tipo_esquema"] or "(vacío)", 0) + 1
    print("\nCobertura por estado:")
    for est, n in sorted(by_estado.items(), key=lambda x: -x[1]):
        print(f"  {est:35s} {n}")
    print("\nDistribución tipo_esquema:")
    for tipo, n in sorted(by_tipo.items(), key=lambda x: -x[1]):
        print(f"  {tipo:25s} {n}")

    return out_csv
