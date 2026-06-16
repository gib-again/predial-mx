"""Verifica los huecos remanentes del panel Sonora vía web_search (gpt-5.4).

Lee `output/balance/panel_v2_balanced.csv` y identifica filas Sonora donde:
  - `tipo_esquema` está vacío (gap remanente — no imputado)
  - O `tipo_esquema` == 'desconocido' (clasificación dudosa)
  - O fila ausente del balanced (cve_mun × anio del grid INEGI)

Para cada hueco llama `verify_gap()` y persiste en
`data/sonora/meta/web_verification.csv`.

Uso:
    # Test con primeros N gaps (sin gastar mucho)
    python -m scripts.sonora_web_verify_gaps --limit 5

    # Producción: todos los huecos
    python -m scripts.sonora_web_verify_gaps

    # Reanudar: salta filas ya verificadas
    python -m scripts.sonora_web_verify_gaps --resume

    # Estimación de costo (no llama al API)
    python -m scripts.sonora_web_verify_gaps --dry-run
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from pathlib import Path

# Permitir `python scripts/foo.py` además de `python -m scripts.foo`.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv()

from src.core.web_verifier import verify_gap  # noqa: E402

CVE_ENT_SONORA = "26"
ANIO_MIN = 2010
ANIO_MAX = 2025

OUTPUT_FIELDS = [
    "cve_mun", "cvegeo", "municipio_nom", "anio",
    "existe_ley", "url_pdf", "fuente",
    "razon_bloqueo", "confianza", "comentario",
    "tokens_input", "tokens_output",
    "model", "error",
]


def _load_inegi_munis_sonora(catalog_path: Path) -> dict[str, str]:
    """{cve_mun: nom_mun} para los 72 munis de Sonora."""
    out: dict[str, str] = {}
    if not catalog_path.exists():
        raise FileNotFoundError(f"Falta {catalog_path}")
    with catalog_path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("CVE_ENT") or "").strip() != CVE_ENT_SONORA:
                continue
            cve_mun = (r.get("CVE_MUN") or "").strip()
            nom_mun = (r.get("NOM_MUN") or "").strip()
            if cve_mun and nom_mun:
                out[cve_mun] = nom_mun
    return out


def _load_panel_coverage(panel_csv: Path) -> dict[tuple[str, int], dict]:
    """{(cve_mun, anio): row} para Sonora."""
    out: dict[tuple[str, int], dict] = {}
    if not panel_csv.exists():
        return out
    with panel_csv.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r.get("estado") or "").lower() != "sonora":
                continue
            cvegeo = r.get("cvegeo", "").zfill(5)
            cve_mun = cvegeo[2:]
            try:
                anio = int(r["ejercicio"])
            except (KeyError, ValueError):
                continue
            out[(cve_mun, anio)] = r
    return out


def _identify_gaps(
    munis: dict[str, str],
    coverage: dict[tuple[str, int], dict],
) -> list[tuple[str, str, int, str]]:
    """Lista huecos del panel: (cve_mun, nom_mun, anio, motivo)."""
    gaps: list[tuple[str, str, int, str]] = []
    for cve_mun, nom_mun in sorted(munis.items()):
        for anio in range(ANIO_MIN, ANIO_MAX + 1):
            row = coverage.get((cve_mun, anio))
            if row is None:
                gaps.append((cve_mun, nom_mun, anio, "missing_from_panel"))
            else:
                tipo = (row.get("tipo_esquema") or "").strip()
                if not tipo:
                    gaps.append((cve_mun, nom_mun, anio, "tipo_vacio"))
                elif tipo == "desconocido":
                    gaps.append((cve_mun, nom_mun, anio, "desconocido"))
    return gaps


def _load_existing_verifications(out_csv: Path) -> set[tuple[str, int]]:
    """Set de (cve_mun, anio) ya verificados, para --resume."""
    done: set[tuple[str, int]] = set()
    if not out_csv.exists():
        return done
    with out_csv.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                done.add((r["cve_mun"], int(r["anio"])))
            except (KeyError, ValueError):
                continue
    return done


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument(
        "--panel",
        default="output/balance/panel_v2_balanced.csv",
        help="CSV del panel balanceado v2.",
    )
    ap.add_argument(
        "--catalog",
        default="catalogs/municipios_inegi.csv",
        help="Catálogo INEGI municipios.",
    )
    ap.add_argument(
        "--out",
        default="data/sonora/meta/web_verification.csv",
        help="CSV de salida (incremental).",
    )
    ap.add_argument(
        "--limit", type=int, default=0,
        help="Máx. verificaciones (0 = todas).",
    )
    ap.add_argument(
        "--resume", action="store_true",
        help="Saltar (cve_mun, anio) ya presentes en --out.",
    )
    ap.add_argument(
        "--dry-run", action="store_true",
        help="Listar huecos y estimar costo, sin llamar API.",
    )
    ap.add_argument(
        "--throttle", type=float, default=1.0,
        help="Segundos a dormir entre llamadas (default 1.0).",
    )
    ap.add_argument(
        "--flush-every", type=int, default=10,
        help="Forzar flush del CSV cada N filas (default 10).",
    )
    ap.add_argument(
        "--model", default=None,
        help="Override modelo (default env OPENAI_WEB_VERIFIER_MODEL o gpt-5.4).",
    )
    args = ap.parse_args()

    panel_csv = Path(args.panel)
    catalog = Path(args.catalog)
    out_csv = Path(args.out)

    print(f"Cargando catálogo INEGI ({catalog})...")
    munis = _load_inegi_munis_sonora(catalog)
    print(f"  munis Sonora: {len(munis)}")

    print(f"Cargando panel balanceado ({panel_csv})...")
    coverage = _load_panel_coverage(panel_csv)
    print(f"  filas Sonora en panel: {len(coverage)}")

    gaps = _identify_gaps(munis, coverage)
    print(f"\nHuecos identificados: {len(gaps)}")
    motivos: dict[str, int] = {}
    for _, _, _, motivo in gaps:
        motivos[motivo] = motivos.get(motivo, 0) + 1
    for m, n in sorted(motivos.items(), key=lambda x: -x[1]):
        print(f"  {m:25s} {n}")

    if args.dry_run:
        # Estimación: ~$0.065 por verificación
        cost = len(gaps) * 0.065
        print(f"\n[DRY] Costo estimado: ~${cost:.2f} USD ({len(gaps)} verificaciones)")
        print("\n[DRY] Sample primeros 10 huecos:")
        for g in gaps[:10]:
            print(f"  cve_mun={g[0]} {g[1]:30s} anio={g[2]} motivo={g[3]}")
        return

    # --resume: cargar verificados previos
    done: set[tuple[str, int]] = set()
    if args.resume:
        done = _load_existing_verifications(out_csv)
        print(f"  ya verificados (resume): {len(done)}")
        gaps = [g for g in gaps if (g[0], g[2]) not in done]
        print(f"  huecos pendientes después de resume: {len(gaps)}")

    if args.limit > 0:
        gaps = gaps[: args.limit]
        print(f"  --limit aplicado: procesando {len(gaps)}")

    if not gaps:
        print("\nNo hay huecos pendientes. Nada que hacer.")
        return

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    write_header = not out_csv.exists()
    f_out = out_csv.open("a", encoding="utf-8", newline="")
    writer = csv.DictWriter(f_out, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
    if write_header:
        writer.writeheader()
        f_out.flush()

    n_done = 0
    n_errors = 0
    try:
        for cve_mun, nom_mun, anio, motivo in gaps:
            try:
                result = verify_gap(
                    municipio_nom=nom_mun,
                    anio=anio,
                    estado_nom="Sonora",
                    model=args.model,
                )
            except Exception as e:
                result = {
                    "error": f"{type(e).__name__}: {e}",
                    "existe_ley": False,
                    "url_pdf": None,
                    "fuente": None,
                    "razon_bloqueo": "otro",
                    "confianza": "low",
                    "comentario": f"Excepción no controlada: {e}",
                }

            row = {
                "cve_mun": cve_mun,
                "cvegeo": f"{CVE_ENT_SONORA}{cve_mun}",
                "municipio_nom": nom_mun,
                "anio": anio,
                "existe_ley": result.get("existe_ley", False),
                "url_pdf": result.get("url_pdf") or "",
                "fuente": result.get("fuente") or "",
                "razon_bloqueo": result.get("razon_bloqueo") or "otro",
                "confianza": result.get("confianza") or "low",
                "comentario": (result.get("comentario") or "")[:600],
                "tokens_input": result.get("tokens_input") or "",
                "tokens_output": result.get("tokens_output") or "",
                "model": (
                    args.model
                    or __import__("os").environ.get("OPENAI_WEB_VERIFIER_MODEL")
                    or "gpt-5.4"
                ),
                "error": result.get("error") or "",
            }
            writer.writerow(row)
            n_done += 1
            if result.get("error"):
                n_errors += 1

            # Log compacto
            ind = "✓" if result.get("existe_ley") else "·"
            print(
                f"  [{n_done}/{len(gaps)}] {ind} {nom_mun[:25]:25s} {anio} "
                f"motivo={motivo[:18]:18s} → "
                f"razon={row['razon_bloqueo'][:25]:25s} conf={row['confianza']}"
            )
            if row["error"]:
                print(f"      ! error: {row['error'][:100]}")

            # Flush incremental
            if n_done % args.flush_every == 0:
                f_out.flush()

            # Throttle
            if args.throttle > 0:
                time.sleep(args.throttle)
    except KeyboardInterrupt:
        print("\n[INTERRUPT] Se detuvo. Filas escritas se conservan.")
    finally:
        f_out.flush()
        f_out.close()

    print(
        f"\n=== Total: verificadas={n_done}  errores={n_errors}  "
        f"output={out_csv} ==="
    )


if __name__ == "__main__":
    main()
