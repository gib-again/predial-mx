"""Re-procesa municipios completos (TODOS los años) tras fixes de schema/prompt/segmenter.

Uso:
    # Re-procesar munis específicos (slug-based)
    python -m scripts.reprocess_municipios --munis coahuila/ocampo,guanajuato/abasolo

    # Leer munis automáticamente desde HITL_BITACORA.md (revisados ≠ correcto + pendientes)
    python -m scripts.reprocess_municipios --from-bitacora

    # Solo munis revisados (no incluir pendientes)
    python -m scripts.reprocess_municipios --from-bitacora --reviewed-only

    # Filtrar por patrón
    python -m scripts.reprocess_municipios --from-bitacora --patron P-09

    # Dry-run (mostrar qué se procesaría sin invocar LLM)
    python -m scripts.reprocess_municipios --from-bitacora --dry-run

Constraint clave (ver plan): cuando se re-procesa un municipio, se procesa para
TODOS los años disponibles en `data/{estado}/focus_predial/`, no solo el año
revisado. Los esquemas son estables intertemporalmente, así que un fix raramente
aplica a un solo año.

Output:
  - JSONs actualizados en `predial-mx-v2/{estado}/`
  - Reporte de cambios (tipo_anterior → tipo_nuevo) impreso a stdout
  - Reconstrucción de `output/extraction_log_v2.csv` al final
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

# Reconfigurar stdout a UTF-8 (Windows cp1252 crash en `→` de validation errors)
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from dotenv import load_dotenv

load_dotenv()

from src.core.constants import PREFIJOS_ESTADO  # noqa: E402
from src.core.text_utils import slugify  # noqa: E402
from src.extraction.bitacora_parser import parse_bitacora  # noqa: E402
from src.extraction.llm_extract_v2 import (  # noqa: E402
    OPENAI_MODEL,
    OPENAI_MODEL_FALLBACK,
    extraer_municipio,
)
from src.extraction.schema_v2 import OtroNoClasificadoSchema  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BITACORA_PATH = ROOT / "docs" / "HITL_BITACORA.md"
LOG_PATH = ROOT / "output" / "extraction_log_v2.csv"
CATALOG = ROOT / "catalogs" / "municipios_inegi.csv"
OUTPUT_ROOT = ROOT / "predial-mx-v2"

# Pricing USD por 1M tokens (estimado)
PRICING = {
    "gpt-5.4-mini": {"input": 0.25, "cached": 0.025, "output": 2.00},
    "gpt-5.4": {"input": 2.50, "cached": 0.25, "output": 20.00},
}

CVE_ENT = {
    "coahuila": "05", "jalisco": "14", "guanajuato": "11",
    "queretaro": "22", "yucatan": "31", "tamaulipas": "28",
}

# Munis donde gpt-5.4-mini interpreta sistemáticamente mal — invocar gpt-5.4
# desde el primer intento (P-04 del HITL pasada 2). Si entran por
# --from-bitacora --patron P-04 también se activa automáticamente.
P04_MUNIS = {
    ("yucatan", "tepakan"),
    ("yucatan", "kaua"),
    ("guanajuato", "purisima_del_rincon"),
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


def _discover_anios(estado: str, slug: str) -> list[int]:
    """Lista todos los años de focus_predial donde aparece este slug.

    Considera también `focus_predial_overrides/` (P-10) para no perder años
    con override manual.
    """
    prefijo = PREFIJOS_ESTADO[estado]
    pattern = f"{prefijo}_PREDIAL_*_{slug}.txt"
    anios: set[int] = set()
    for base_subdir in ("focus_predial", "focus_predial_overrides"):
        base = ROOT / "data" / estado / base_subdir
        if not base.exists():
            continue
        for p in base.rglob(pattern):
            parts = p.stem.split("_")
            try:
                anios.add(int(parts[2]))
            except (IndexError, ValueError):
                continue
    return sorted(anios)


def _resolve_muni_specs(specs: list[str]) -> list[tuple[str, str, str, list[int]]]:
    """Convierte ['estado/slug', ...] → [(estado, slug, cvegeo, anios), ...]."""
    out: list[tuple[str, str, str, list[int]]] = []
    cve_cache: dict[str, dict[str, str]] = {}
    for s in specs:
        if "/" not in s:
            print(f"  [skip] '{s}': formato esperado 'estado/slug'")
            continue
        estado, slug = s.split("/", 1)
        estado = estado.strip().lower()
        slug = slug.strip().lower()
        if estado not in CVE_ENT:
            print(f"  [skip] '{s}': estado '{estado}' no conocido")
            continue
        if estado not in cve_cache:
            cve_cache[estado] = _slug_to_cvegeo(estado)
        cvegeo = cve_cache[estado].get(slug)
        if not cvegeo:
            # Slug aliases (suma_de_hidalgo → 31072, san_jose_iturbide → 11032)
            from scripts.temps.reextract_v2 import SLUG_ALIASES
            cvegeo = SLUG_ALIASES.get((estado, slug))
        if not cvegeo:
            print(f"  [skip] '{s}': slug no resuelto en catálogo INEGI")
            continue
        anios = _discover_anios(estado, slug)
        if not anios:
            print(f"  [skip] '{s}': sin focus_predial encontrado para slug='{slug}'")
            continue
        out.append((estado, slug, cvegeo, anios))
    return out


def _munis_from_bitacora(
    reviewed_only: bool = False,
    pending_only: bool = False,
    patron: str | None = None,
) -> list[str]:
    """Extrae lista de 'estado/slug' del HITL_BITACORA según filtros."""
    data = parse_bitacora(BITACORA_PATH)
    munis: set[tuple[str, str]] = set()

    if patron:
        for c in data.by_patron(patron):
            munis.add((c.estado, c.slug))
        return [f"{e}/{s}" for e, s in sorted(munis)]

    if reviewed_only:
        for c in data.reviewed():
            if c.veredicto and c.veredicto != "correcto":
                munis.add((c.estado, c.slug))
    elif pending_only:
        for c in data.pending():
            munis.add((c.estado, c.slug))
    else:
        # Default: revisados ≠ correcto + pendientes (excluye los confirmados ok)
        for c in data.cases:
            if not c.revisado:
                munis.add((c.estado, c.slug))
            elif c.veredicto and c.veredicto != "correcto":
                munis.add((c.estado, c.slug))

    return [f"{e}/{s}" for e, s in sorted(munis)]


def _cost(tok_in: int, tok_cached: int, tok_out: int, modelo: str) -> float:
    p = PRICING.get(modelo, PRICING["gpt-5.4-mini"])
    nc = max(0, tok_in - tok_cached)
    return (nc * p["input"] + tok_cached * p["cached"] + tok_out * p["output"]) / 1e6


def _load_existing_tipo(estado: str, prefijo: str, anio: int, slug: str) -> str:
    """Lee el tipo_esquema actual del JSON v2 (para diff)."""
    p = OUTPUT_ROOT / estado / f"{prefijo}_PREDIAL_{anio}_{slug}.json"
    if not p.exists():
        return "—"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return (d.get("predial") or {}).get("tipo_esquema", "—")
    except Exception:
        return "—"


def main() -> int:
    ap = argparse.ArgumentParser()
    src_group = ap.add_mutually_exclusive_group(required=True)
    src_group.add_argument(
        "--munis",
        help="Lista CSV de 'estado/slug' (ej. 'coahuila/ocampo,guanajuato/abasolo')",
    )
    src_group.add_argument(
        "--from-bitacora",
        action="store_true",
        help="Leer munis de docs/HITL_BITACORA.md (default: revisados≠correcto + pendientes)",
    )

    ap.add_argument("--reviewed-only", action="store_true",
                    help="Con --from-bitacora: solo revisados con veredicto≠correcto")
    ap.add_argument("--pending-only", action="store_true",
                    help="Con --from-bitacora: solo pendientes (no revisados)")
    ap.add_argument("--patron", default=None,
                    help="Filtrar por patrón (ej. P-01, P-09)")
    ap.add_argument("--force-full-model", action="store_true",
                    help="Forzar gpt-5.4 desde el primer intento (skip mini). "
                         "Auto-activa para munis en P04_MUNIS o cuando --patron=P-04.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Mostrar qué se procesaría sin invocar LLM")
    ap.add_argument("--no-rebuild-csv", action="store_true",
                    help="No regenerar output/extraction_log_v2.csv al final")
    args = ap.parse_args()

    # Resolver lista de munis
    if args.from_bitacora:
        muni_specs = _munis_from_bitacora(
            reviewed_only=args.reviewed_only,
            pending_only=args.pending_only,
            patron=args.patron,
        )
        print(f"[reprocess] {len(muni_specs)} munis desde HITL_BITACORA.md")
    else:
        muni_specs = [s.strip() for s in args.munis.split(",") if s.strip()]
        print(f"[reprocess] {len(muni_specs)} munis de --munis")

    targets = _resolve_muni_specs(muni_specs)
    if not targets:
        print("[reprocess] sin targets resueltos. Saliendo.")
        return 1

    n_total_archivos = sum(len(anios) for _, _, _, anios in targets)
    print(f"[reprocess] {len(targets)} munis · {n_total_archivos} muni-años")
    print(f"[reprocess] modelo={OPENAI_MODEL} fallback={OPENAI_MODEL_FALLBACK}")

    if args.dry_run:
        print("\n[dry-run] munis a procesar:")
        for est, slug, cve, anios in targets:
            print(f"  {est}/{slug} (cvegeo {cve}): {len(anios)} años "
                  f"[{anios[0]}–{anios[-1]}]")
        return 0

    t0 = time.time()
    diffs: list[dict] = []  # {estado, slug, anio, tipo_antes, tipo_despues, fuente}
    grand_in = grand_out = grand_cached = 0
    grand_cost = 0.0

    # Determinar si --patron P-04 fue solicitado (para auto-force-full-model)
    patron_is_p04 = (args.patron or "").upper() == "P-04"

    for i, (estado, slug, cvegeo, anios) in enumerate(sorted(targets), 1):
        prefijo = PREFIJOS_ESTADO[estado]

        # Decidir si se fuerza gpt-5.4 para este muni
        force_full = (
            args.force_full_model
            or patron_is_p04
            or (estado, slug) in P04_MUNIS
        )
        ff_tag = "  [FORCE_FULL]" if force_full else ""
        print(f"\n[{i}/{len(targets)}] {estado}/{slug} (cvegeo {cvegeo}, "
              f"{len(anios)} años: {anios[0]}–{anios[-1]}){ff_tag}")

        # Snapshot tipos previos
        tipos_antes = {a: _load_existing_tipo(estado, prefijo, a, slug) for a in anios}

        try:
            results = extraer_municipio(
                estado, cvegeo, anios,
                slug_override=slug,
                force_full_model=force_full,
            )
        except Exception as e:
            print(f"  [ERROR] {type(e).__name__}: {e}")
            continue

        for r in results:
            tipo_despues = r.output.predial.tipo_esquema if r.output else "—"
            tipo_antes = tipos_antes.get(r.anio, "—")
            diffs.append({
                "estado": estado,
                "slug": slug,
                "anio": r.anio,
                "tipo_antes": tipo_antes,
                "tipo_despues": tipo_despues,
                "fuente": r.fuente,
                "intentos": r.intentos,
                "modelo": r.modelo_usado,
            })
            cost = _cost(r.tokens_in, r.tokens_cached, r.tokens_out, r.modelo_usado)
            grand_in += r.tokens_in
            grand_out += r.tokens_out
            grand_cached += r.tokens_cached
            grand_cost += cost

    elapsed = (time.time() - t0) / 60
    print(f"\n{'=' * 80}")
    print(f"[reprocess] terminado en {elapsed:.1f} min")
    print(f"  archivos procesados: {len(diffs)}")
    print(f"  tokens (in/out/cached): {grand_in:,} / {grand_out:,} / {grand_cached:,}")
    print(f"  costo estimado: ${grand_cost:.2f} USD")

    # ── Reporte de cambios ──
    changes = [d for d in diffs if d["tipo_antes"] != d["tipo_despues"]]
    print(f"\n[reprocess] cambios de tipo_esquema: {len(changes)}/{len(diffs)}")
    if changes:
        # Agrupa transiciones
        transitions: dict[tuple[str, str], int] = defaultdict(int)
        for d in changes:
            transitions[(d["tipo_antes"], d["tipo_despues"])] += 1
        print(f"\n  Transiciones (antes → después):")
        for (a, b), n in sorted(transitions.items(), key=lambda x: -x[1]):
            print(f"    {a:25s} → {b:25s}: {n}")

        # Resumen por fuente (txt / pdf_reocr / pdf_vision)
        by_fuente = defaultdict(int)
        for d in diffs:
            by_fuente[d["fuente"]] += 1
        print(f"\n  Distribución por fuente final:")
        for k, v in sorted(by_fuente.items()):
            print(f"    {k}: {v}")

    # ── Reconstruir CSV ──
    if not args.no_rebuild_csv:
        from scripts.temps.reextract_v2 import _rebuild_csv_from_jsons, ESTADOS as REEX_ESTADOS
        all_estados = sorted(set(REEX_ESTADOS) | {est for est, _, _, _ in targets})
        n_csv, by = _rebuild_csv_from_jsons(all_estados)
        print(f"\n[reprocess] CSV reconstruido: {n_csv} filas, por estado: {by}")

    print(f"{'=' * 80}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
