"""Re-extrae 4 estados con extract_v2.py en modo sync.

Procesa en orden alfabético: coahuila → guanajuato → tamaulipas → yucatan.
Después de cada estado imprime: archivos procesados, tokens, costo estimado,
requiere_revision, otro_no_clasificado.

Output:
  - predial-mx-v2/{estado}/*.json (uno por archivo)
  - output/extraction_log_v2.csv (uno por archivo)
"""
from __future__ import annotations

import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

# Reconfigurar stdout/stderr a UTF-8 — Windows usa cp1252 por default y el `→`
# en mensajes de validación (`brackets 1→2: hueco detectado`) revienta print().
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from src.core.constants import PREFIJOS_ESTADO  # noqa: E402
from src.core.text_utils import slugify  # noqa: E402
from src.extraction.llm_extract_v2 import (  # noqa: E402
    OPENAI_MODEL,
    OPENAI_MODEL_FALLBACK,
    extraer_municipio,
)
from src.extraction.schema_v2 import OtroNoClasificadoSchema  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ESTADOS = ["coahuila", "guanajuato", "tamaulipas", "yucatan"]
LOG_PATH = ROOT / "output" / "extraction_log_v2.csv"
CATALOG = ROOT / "catalogs" / "municipios_inegi.csv"
OUTPUT_ROOT = ROOT / "predial-mx-v2"

# USD por 1M tokens (gpt-5.4-mini default + gpt-5.4 fallback estimate).
PRICING = {
    "gpt-5.4-mini": {"input": 0.25, "cached": 0.025, "output": 2.00},
    "gpt-5.4": {"input": 2.50, "cached": 0.25, "output": 20.00},
}

# CVE_ENT (2 dígitos) por estado
CVE_ENT = {
    "coahuila": "05",
    "jalisco": "14",
    "guanajuato": "11",
    "queretaro": "22",
    "yucatan": "31",
    "tamaulipas": "28",
}

# Slugs en filename que NO matchean exacto contra catálogo INEGI:
#   - alias real: mappear al cvegeo correcto
#   - corrupto: skip
SLUG_ALIASES: dict[tuple[str, str], str] = {
    ("guanajuato", "san_jose_iturbide"): "11032",   # catálogo: "San Jose de Iturbide"
    ("yucatan", "suma_de_hidalgo"): "31072",        # catálogo: "Suma"
}
SLUG_SKIPS: set[tuple[str, str]] = {
    ("guanajuato", "penjiamo_guanaj_jato"),  # OCR artifact (Pénjamo)
    ("tamaulipas", "abasolo_la_sexagesima_segunda_legislatura_del_congreso_constitucional_del_estado_libre_y_soberano_de"),  # corrupted
}


def _slug_to_cvegeo(estado: str) -> dict[str, str]:
    cve_ent = CVE_ENT[estado]
    out: dict[str, str] = {}
    with CATALOG.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cvegeo = row["CVEGEO"]
            if cvegeo[:2] == cve_ent:
                out[slugify(row["NOM_MUN"])] = cvegeo
    return out


def _discover_files(estado: str) -> dict[str, list[int]]:
    prefijo = PREFIJOS_ESTADO[estado]
    base = ROOT / "data" / estado / "focus_predial"
    pattern = f"{prefijo}_PREDIAL_*.txt"
    by_slug: dict[str, set[int]] = defaultdict(set)
    for p in base.rglob(pattern):
        parts = p.stem.split("_")
        if len(parts) < 4:
            continue
        try:
            anio = int(parts[2])
        except ValueError:
            continue
        slug = "_".join(parts[3:])
        by_slug[slug].add(anio)
    return {s: sorted(a) for s, a in by_slug.items()}


def _cost(tok_in: int, tok_cached: int, tok_out: int, modelo: str) -> float:
    p = PRICING.get(modelo, PRICING["gpt-5.4-mini"])
    nc = max(0, tok_in - tok_cached)
    return (nc * p["input"] + tok_cached * p["cached"] + tok_out * p["output"]) / 1e6


def _expected_json(estado: str, prefijo: str, anio: int, slug: str) -> Path:
    return OUTPUT_ROOT / estado / f"{prefijo}_PREDIAL_{anio}_{slug}.json"


def _is_completed_json(path: Path) -> bool:
    """Considera completado solo si el JSON tiene `predial != null`.

    Los archivos `texto_fuente_no_encontrado` quedaron persistidos del run
    previo; deben re-procesarse cuando ahora pasamos slug_override correcto.
    """
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return data.get("predial") is not None


def _rebuild_csv_from_jsons(estados: list[str]) -> tuple[int, dict[str, int]]:
    """Reconstruye output/extraction_log_v2.csv desde TODOS los JSONs.

    Returns (total_rows, per_estado_count).
    """
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = defaultdict(int)
    n_total = 0
    with LOG_PATH.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "estado", "cvegeo", "anio", "slug", "archivo",
            "tipo_esquema", "intentos", "modelo", "escalado",
            "requiere_revision", "razon",
            "tokens_in", "tokens_out", "tokens_cached", "costo_usd",
        ])
        for estado in estados:
            estado_dir = OUTPUT_ROOT / estado
            if not estado_dir.exists():
                continue
            for jp in sorted(estado_dir.glob("*.json")):
                try:
                    d = json.loads(jp.read_text(encoding="utf-8"))
                except Exception:
                    continue
                meta = d.get("_meta_v2") or {}
                pred = d.get("predial") or {}
                tokens = meta.get("tokens") or {}
                tipo = pred.get("tipo_esquema", "") if isinstance(pred, dict) else ""
                tin = tokens.get("input", 0) or 0
                tout = tokens.get("output", 0) or 0
                tcache = tokens.get("cached", 0) or 0
                modelo = (d.get("_meta") or {}).get("modelo", OPENAI_MODEL)
                cost = _cost(tin, tcache, tout, modelo)
                # Recuperar slug y anio del filename del JSON
                stem = jp.stem  # PREFIJO_PREDIAL_ANIO_slug
                parts = stem.split("_")
                try:
                    anio = int(parts[2])
                    slug = "_".join(parts[3:])
                except (IndexError, ValueError):
                    anio, slug = 0, ""
                w.writerow([
                    estado, meta.get("cvegeo", ""), anio, slug, jp.name,
                    tipo, meta.get("intentos", 0), modelo, meta.get("escalado", False),
                    meta.get("requiere_revision", False), meta.get("razon", "") or "",
                    tin, tout, tcache, f"{cost:.4f}",
                ])
                counts[estado] += 1
                n_total += 1
    return n_total, dict(counts)


def main() -> int:
    print(f"[reextract_v2] modelo={OPENAI_MODEL} fallback={OPENAI_MODEL_FALLBACK}")
    print(f"[reextract_v2] estados={ESTADOS}")
    print(f"[reextract_v2] resume mode: skip si JSON ya completado")
    print(f"[reextract_v2] log={LOG_PATH.relative_to(ROOT)}")

    grand_n = 0
    grand_in = grand_out = grand_cached = 0
    grand_cost = 0.0
    grand_rev = grand_otro = 0
    t0_global = time.time()

    for estado in ESTADOS:
        print(f"\n{'=' * 72}")
        print(f"[{estado.upper()}] iniciando")
        print(f"{'=' * 72}")

        prefijo = PREFIJOS_ESTADO[estado]
        files_by_slug = _discover_files(estado)
        slug_to_cve = _slug_to_cvegeo(estado)

        # Lista de (cvegeo, filename_slug, anios)
        targets: list[tuple[str, str, list[int]]] = []
        skipped_corrupt: list[tuple[str, int]] = []
        unmatched: list[str] = []
        for slug, anios in files_by_slug.items():
            if (estado, slug) in SLUG_SKIPS:
                skipped_corrupt.extend((slug, a) for a in anios)
                continue
            cve = SLUG_ALIASES.get((estado, slug)) or slug_to_cve.get(slug)
            if cve:
                targets.append((cve, slug, anios))
            else:
                unmatched.append(slug)

        if skipped_corrupt:
            print(f"  ~ {len(skipped_corrupt)} archivo(s) saltado(s) por filename corrupto")
        if unmatched:
            print(f"  ! {len(unmatched)} slug(s) sin match: {unmatched[:5]}")

        # Filtrar a anios faltantes (resume)
        pending: list[tuple[str, str, list[int]]] = []
        n_total = n_done = 0
        for cve, slug, anios in targets:
            n_total += len(anios)
            missing = [a for a in anios
                       if not _is_completed_json(_expected_json(estado, prefijo, a, slug))]
            n_done += len(anios) - len(missing)
            if missing:
                pending.append((cve, slug, missing))

        n_pending = sum(len(a) for _, _, a in pending)
        print(f"  archivos: total={n_total}  ya_completos={n_done}  pendientes={n_pending}")

        t0 = time.time()
        estado_results = []
        for cve, slug, anios in sorted(pending, key=lambda x: x[0]):
            try:
                results = extraer_municipio(estado, cve, anios, slug_override=slug)
            except Exception as e:
                print(f"  [ERROR] {estado} {cve} ({slug}): {type(e).__name__}: {e}")
                continue
            estado_results.extend(results)

        # Resumen por estado: lee todos los JSONs (incluyendo los del run previo)
        estado_dir = OUTPUT_ROOT / estado
        n = tin = tout = tcache = 0
        n_rev = n_otro = 0
        cost_estado = 0.0
        for jp in estado_dir.glob("*.json"):
            try:
                d = json.loads(jp.read_text(encoding="utf-8"))
            except Exception:
                continue
            meta = d.get("_meta_v2") or {}
            pred = d.get("predial") or {}
            if not isinstance(pred, dict):
                continue
            n += 1
            tokens = meta.get("tokens") or {}
            ti = tokens.get("input", 0) or 0
            to = tokens.get("output", 0) or 0
            tc = tokens.get("cached", 0) or 0
            tin += ti; tout += to; tcache += tc
            modelo = (d.get("_meta") or {}).get("modelo", OPENAI_MODEL)
            cost_estado += _cost(ti, tc, to, modelo)
            if meta.get("requiere_revision"):
                n_rev += 1
            if pred.get("tipo_esquema") == "otro_no_clasificado":
                n_otro += 1

        elapsed = (time.time() - t0) / 60
        print(f"\n  {'-' * 60}")
        print(f"  RESUMEN [{estado.upper()}]   ({elapsed:.1f} min en este run)")
        print(f"    archivos procesados:    {n}")
        print(f"    tokens (in/out/cached): {tin:,} / {tout:,} / {tcache:,}")
        print(f"    costo estimado:         ${cost_estado:.2f} USD")
        print(f"    requiere_revision:      {n_rev}")
        print(f"    otro_no_clasificado:    {n_otro}")
        print(f"  {'-' * 60}")

        grand_n += n
        grand_in += tin
        grand_out += tout
        grand_cached += tcache
        grand_cost += cost_estado
        grand_rev += n_rev
        grand_otro += n_otro

    # Reconstruir CSV desde JSONs
    print(f"\n[reextract_v2] reconstruyendo {LOG_PATH.name} desde JSONs...")
    n_csv, per_state = _rebuild_csv_from_jsons(ESTADOS)
    print(f"  filas escritas: {n_csv}  por estado: {per_state}")

    elapsed_g = (time.time() - t0_global) / 60
    print(f"\n{'=' * 72}")
    print(f"[TOTAL]  ({elapsed_g:.1f} min)")
    print(f"  archivos procesados:    {grand_n}")
    print(f"  tokens (in/out/cached): {grand_in:,} / {grand_out:,} / {grand_cached:,}")
    print(f"  costo estimado:         ${grand_cost:.2f} USD")
    print(f"  requiere_revision:      {grand_rev}")
    print(f"  otro_no_clasificado:    {grand_otro}")
    print(f"  log: {LOG_PATH.relative_to(ROOT)}")
    print(f"{'=' * 72}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
