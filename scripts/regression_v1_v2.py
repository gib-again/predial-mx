"""Re-extrae un estado completo con schema_v2 y compara contra el audit v1.

Para cada archivo focus_predial existente:
  1. Re-extrae con `extraer_municipio()` (schema_v2 LLM call) → predial-mx-v2/...
  2. Lee el `tipo_esquema` que produjo v1 (del audit CSV de QA).
  3. Marca discrepancia si v1 y v2 difieren.

Output:
  - `predial-mx-v2/{estado}/*.json` (todos los archivos)
  - `output/regression_v1_v2.csv` (sólo filas con discrepancia)
  - `output/regression_v1_v2_full.csv` (todas las filas, opcional con --full)

Uso:
    python -m scripts.regression_v1_v2 queretaro
    python -m scripts.regression_v1_v2 queretaro --limit 10  # debug
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from src.core.constants import PREFIJOS_ESTADO  # noqa: E402
from src.extraction.llm_extract_v2 import (  # noqa: E402
    ROOT,
    extraer_municipio,
)

# CVE_ENT por estado (primeros 2 dígitos del CVEGEO).
CVE_ENT_BY_ESTADO = {
    "aguascalientes": "01",
    "baja_california": "02",
    "baja_california_sur": "03",
    "campeche": "04",
    "coahuila": "05",
    "colima": "06",
    "chiapas": "07",
    "chihuahua": "08",
    "cdmx": "09",
    "durango": "10",
    "guanajuato": "11",
    "guerrero": "12",
    "hidalgo": "13",
    "jalisco": "14",
    "edomex": "15",
    "michoacan": "16",
    "morelos": "17",
    "nayarit": "18",
    "nuevo_leon": "19",
    "oaxaca": "20",
    "puebla": "21",
    "queretaro": "22",
    "quintana_roo": "23",
    "san_luis_potosi": "24",
    "sinaloa": "25",
    "sonora": "26",
    "tabasco": "27",
    "tamaulipas": "28",
    "tlaxcala": "29",
    "veracruz": "30",
    "yucatan": "31",
    "zacatecas": "32",
}


def _slug_to_cvegeo(estado: str) -> dict[str, str]:
    """slug → CVEGEO (5 dígitos), construido del audit CSV usando `cve_mun`."""
    prefijo = PREFIJOS_ESTADO[estado]
    audit_path = ROOT / "data" / estado / "qa" / f"audit_{prefijo}.csv"
    cve_ent = CVE_ENT_BY_ESTADO[estado]
    out: dict[str, str] = {}
    with audit_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            slug = (row.get("slug") or "").strip()
            cve_mun = (row.get("cve_mun") or "").strip()
            if not slug or not cve_mun:
                continue
            out[slug] = f"{cve_ent}{str(cve_mun).zfill(3)}"
    return out


def _v1_audit_per_file(estado: str) -> dict[tuple[int, str], dict[str, str]]:
    """(anio, slug) → {tipo_v1, valido_v1} desde el audit CSV."""
    prefijo = PREFIJOS_ESTADO[estado]
    audit_path = ROOT / "data" / estado / "qa" / f"audit_{prefijo}.csv"
    out: dict[tuple[int, str], dict[str, str]] = {}
    with audit_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                anio = int(row["ejercicio"])
            except (KeyError, ValueError):
                continue
            slug = (row.get("slug") or "").strip()
            if not slug:
                continue
            out[(anio, slug)] = {
                "tipo_v1": (row.get("tipo_esquema") or "").strip(),
                "valido_v1": (row.get("esquema_valido") or "").strip(),
            }
    return out


def _list_focus_files(estado: str) -> dict[str, list[int]]:
    """slug → lista ordenada de años con focus_predial TXT disponible."""
    prefijo = PREFIJOS_ESTADO[estado]
    base = ROOT / "data" / estado / "focus_predial"
    out: dict[str, list[int]] = defaultdict(list)
    for txt in base.rglob(f"{prefijo}_PREDIAL_*.txt"):
        parts = txt.stem.split("_")
        try:
            anio = int(parts[2])
            slug = "_".join(parts[3:])
        except (ValueError, IndexError):
            continue
        out[slug].append(anio)
    for s in out:
        out[s].sort()
    return dict(out)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("estado", help="slug del estado (ej. queretaro)")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="limitar a N municipios (para debug)",
    )
    parser.add_argument(
        "--out", default="output/regression_v1_v2.csv",
        help="ruta del CSV de discrepancias",
    )
    parser.add_argument(
        "--full", action="store_true",
        help="además genera output/regression_v1_v2_full.csv con todas las filas",
    )
    args = parser.parse_args(argv)

    estado = args.estado.lower()
    if estado not in PREFIJOS_ESTADO:
        print(f"[regress] estado desconocido: {estado}")
        return 1

    slug_to_cvegeo = _slug_to_cvegeo(estado)
    v1_audit = _v1_audit_per_file(estado)
    files_by_slug = _list_focus_files(estado)

    n_munis = len(files_by_slug)
    n_archivos = sum(len(v) for v in files_by_slug.values())
    print(f"[regress] {estado}: {n_munis} municipios, {n_archivos} archivos focus_predial")
    print(f"[regress] audit: {len(v1_audit)} filas | slug_to_cvegeo: {len(slug_to_cvegeo)} mapeos")

    items = sorted(files_by_slug.items())
    if args.limit:
        items = items[: args.limit]
        print(f"[regress] LIMIT: {len(items)} municipios")

    rows: list[dict] = []
    for i, (slug, anios) in enumerate(items, 1):
        cvegeo = slug_to_cvegeo.get(slug)
        if not cvegeo:
            print(f"  [SKIP {i}/{len(items)}] {slug}: cvegeo no encontrado en audit")
            continue
        print(f"\n  [{i}/{len(items)}] {slug} (cvegeo={cvegeo}, {len(anios)} anios)")
        try:
            results = extraer_municipio(estado, cvegeo, anios)
        except Exception as e:
            print(f"    ERROR extraer_municipio: {type(e).__name__}: {e}")
            continue
        for r in results:
            v1_info = v1_audit.get((r.anio, r.slug), {})
            tipo_v1 = v1_info.get("tipo_v1", "")
            tipo_v2 = r.output.predial.tipo_esquema if r.output else ""
            rows.append({
                "estado": estado,
                "anio": r.anio,
                "slug": r.slug,
                "cvegeo": cvegeo,
                "archivo": r.archivo,
                "tipo_v1": tipo_v1,
                "valido_v1": v1_info.get("valido_v1", ""),
                "tipo_v2": tipo_v2,
                "intentos_v2": r.intentos,
                "requiere_revision_v2": r.requiere_revision,
                "razon_v2": (r.razon or ""),
                "tokens_in": r.tokens_in,
                "tokens_out": r.tokens_out,
                "tokens_cached": r.tokens_cached,
                "discrepancia": "SI" if (tipo_v1 and tipo_v2 and tipo_v1 != tipo_v2) else "NO",
            })

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)

    discrepancias = [r for r in rows if r["discrepancia"] == "SI"]

    fieldnames = [
        "estado", "anio", "slug", "cvegeo", "archivo",
        "tipo_v1", "tipo_v2", "valido_v1",
        "intentos_v2", "requiere_revision_v2", "razon_v2",
        "tokens_in", "tokens_out", "tokens_cached",
        "discrepancia",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(discrepancias)

    if args.full:
        full_path = out_path.with_name("regression_v1_v2_full.csv")
        with full_path.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(rows)
        print(f"[regress] full: {full_path}  ({len(rows)} filas)")

    total_in = sum(r["tokens_in"] for r in rows)
    total_out = sum(r["tokens_out"] for r in rows)
    n_revision = sum(1 for r in rows if r["requiere_revision_v2"])
    print(
        f"\n[regress] RESUMEN — {estado}\n"
        f"  archivos procesados: {len(rows)}\n"
        f"  discrepancias v1↔v2: {len(discrepancias)}\n"
        f"  requiere_revision_v2: {n_revision}\n"
        f"  tokens totales: in={total_in}  out={total_out}\n"
        f"  CSV discrepancias: {out_path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
