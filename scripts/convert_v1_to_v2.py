#!/usr/bin/env python3
"""Convierte JSONs en formato v1 PredialSchema (data/{estado}/json_predial/) al
schema_v2 vía `reclasificar()`, persistiéndolos en predial-mx-v2/{estado}/.

Mantiene la convención de nombres v2 (`{PREFIJO}_PREDIAL_{año}_{slug}.json`).
Si ya existe una extracción LLM válida en destino (modelo != 'reclasified_v1'),
se preserva — sólo se sobrescriben re-conversiones previas.

Uso:
    python -m scripts.convert_v1_to_v2 --estado jalisco
    python -m scripts.convert_v1_to_v2 --estado oaxaca
    python -m scripts.convert_v1_to_v2 --all
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from src.core.constants import PREFIJOS_ESTADO
from src.core.text_utils import parse_predial_filename, slugify
from src.core.validation import reclasificar


# Estados con corpus v1 a convertir.
SUPPORTED_ESTADOS = {
    "jalisco":       ("JAL", "14"),
    "oaxaca":        ("OAX", "20"),
    "sanluispotosi": ("SLP", "24"),
    "sonora":        ("SON", "26"),
}


def _load_inegi_lookup(catalog_path: Path, cve_ent: str) -> dict[str, str]:
    """{slug_normalizado: cve_mun} para los munis del estado."""
    out: dict[str, str] = {}
    if not catalog_path.exists():
        return out
    with catalog_path.open(encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("CVE_ENT") or "").strip() != cve_ent:
                continue
            slug = slugify(r.get("NOM_MUN") or "")
            cve_mun = (r.get("CVE_MUN") or "").strip()
            if slug and cve_mun:
                out[slug] = cve_mun
    return out


def _wrap_v2(
    predial_dict: dict, cvegeo: str, estado_slug: str, anio: int,
    src_meta: dict | None,
) -> dict:
    """Envuelve el dict 'predial' con _meta y _meta_v2."""
    src_modelo = (src_meta or {}).get("modelo", "")
    src_fuente = (src_meta or {}).get("fuente", "txt")
    return {
        "predial": predial_dict,
        "_meta": {
            "fuente": src_fuente,
            "modelo": f"reclasified_v1[{src_modelo}]" if src_modelo else "reclasified_v1",
        },
        "_meta_v2": {
            "intentos": 0,
            "requiere_revision": False,
            "razon": None,
            "tokens": {"input": 0, "output": 0, "cached": 0},
            "cvegeo": cvegeo,
            "estado": estado_slug,
            "anio": anio,
        },
    }


def _convert_estado(
    estado: str, dest_root: Path, dry_run: bool, force: bool,
) -> tuple[int, int, int, list[str]]:
    """Returns (n_written, n_preserved, n_skipped, errors)."""
    prefijo, cve_ent = SUPPORTED_ESTADOS[estado]
    src_root = Path(f"data/{estado}/json_predial")
    if not src_root.exists():
        print(f"  [{estado}] directorio fuente no existe: {src_root}")
        return 0, 0, 0, []

    dest_dir = dest_root / estado
    if not dry_run:
        dest_dir.mkdir(parents=True, exist_ok=True)

    inegi = _load_inegi_lookup(Path("catalogs/municipios_inegi.csv"), cve_ent)
    if not inegi:
        return 0, 0, 0, [f"catálogo INEGI vacío para cve_ent={cve_ent}"]

    n_written = 0
    n_preserved = 0
    n_skipped = 0
    errors: list[str] = []

    for src_path in sorted(src_root.rglob("*.json")):
        # Parsear nombre para obtener (anio, slug, nombre_pretty)
        try:
            anio, slug, _ = parse_predial_filename(src_path, prefijo)
        except ValueError as e:
            errors.append(f"{src_path.name}: parse_filename ({e})")
            n_skipped += 1
            continue

        # Resolver cvegeo
        cve_mun = inegi.get(slug)
        if not cve_mun:
            errors.append(f"{src_path.name}: cvegeo no resuelto (slug={slug})")
            n_skipped += 1
            continue
        cvegeo = f"{cve_ent}{cve_mun}"

        # Cargar y validar v1
        try:
            src = json.loads(src_path.read_text(encoding="utf-8"))
        except Exception as e:
            errors.append(f"{src_path.name}: read failed ({e})")
            n_skipped += 1
            continue

        predial = src.get("predial")
        if not isinstance(predial, dict):
            errors.append(f"{src_path.name}: predial ausente o no es dict")
            n_skipped += 1
            continue

        # Reclasificar v1 → variante v2 tipada
        try:
            variant = reclasificar(predial)
        except Exception as e:
            errors.append(f"{src_path.name}: reclasificar threw ({e})")
            n_skipped += 1
            continue

        # Serializar la variante a dict puro
        v2_predial = variant.model_dump(mode="json")

        # Construir destino
        out_name = f"{prefijo}_PREDIAL_{anio}_{slug}.json"
        out_path = dest_dir / out_name

        # Preservar extracciones LLM previas válidas (a menos que --force)
        if out_path.exists() and not force:
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
                modelo = (existing.get("_meta") or {}).get("modelo", "")
                pred = existing.get("predial") if isinstance(existing, dict) else None
                if (
                    pred
                    and pred.get("tipo_esquema")
                    and not modelo.startswith("reclasified_v1")
                    and modelo not in {"synthesized_short_form", "hardcoded"}
                ):
                    n_preserved += 1
                    continue
            except Exception:
                pass

        v2_doc = _wrap_v2(v2_predial, cvegeo, estado, anio, src.get("_meta"))
        if not dry_run:
            out_path.write_text(
                json.dumps(v2_doc, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        n_written += 1

    return n_written, n_preserved, n_skipped, errors


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--estado", choices=list(SUPPORTED_ESTADOS), help="Convertir un estado.")
    ap.add_argument("--all", action="store_true", help="Convertir todos los estados soportados.")
    ap.add_argument("--dest", default="predial-mx-v2",
                    help="Raíz de salida (default: predial-mx-v2).")
    ap.add_argument("--dry-run", action="store_true", help="No escribir; solo reportar.")
    ap.add_argument("--force", action="store_true",
                    help="Sobrescribir incluso extracciones LLM previas válidas.")
    args = ap.parse_args()

    if not (args.all or args.estado):
        ap.error("Debes pasar --all o --estado <slug>.")

    estados = list(SUPPORTED_ESTADOS) if args.all else [args.estado]
    dest_root = Path(args.dest)

    total_written = 0
    total_preserved = 0
    total_skipped = 0
    all_errors: list[tuple[str, str]] = []

    for estado in estados:
        prefijo, cve_ent = SUPPORTED_ESTADOS[estado]
        print(f"\n[{estado}] (prefijo={prefijo}, cve_ent={cve_ent}) "
              f"-> {dest_root / estado}/")
        n_w, n_p, n_s, errors = _convert_estado(estado, dest_root, args.dry_run, args.force)
        print(f"  Escritos: {n_w}  Preservados: {n_p}  Saltados: {n_s}")
        for err in errors[:10]:
            print(f"    ! {err}")
        if len(errors) > 10:
            print(f"    ... ({len(errors) - 10} más)")
        total_written += n_w
        total_preserved += n_p
        total_skipped += n_s
        all_errors.extend((estado, e) for e in errors)

    print(f"\n=== Total: Escritos={total_written}  Preservados={total_preserved}  "
          f"Saltados={total_skipped}  Errores={len(all_errors)} ===")


if __name__ == "__main__":
    main()
