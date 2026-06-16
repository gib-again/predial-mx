"""scripts/compactar_tipo_esquema.py — reduce JSONs a la columna que importa.

OBJETIVO
─────────
El pipeline downstream (balance_panel_v2, imputación, event-study) sólo necesita
`tipo_esquema` por (cve_mun, anio). Los JSONs full de PredialOutputV2 contienen
mucho más (tabla, brackets, comentarios, metadata) que es valioso para auditoría
pero pesado para el panel.

Este script lee TODOS los JSONs en `predial-mx-v2/{estado}/` y emite un CSV
compacto con UNA fila por (estado, cvegeo, anio). Si tipo_esquema=mixto,
incluye `clasificacion_justificacion` para auditoría rápida.

USO
────
  # Compacta un estado:
  python -m scripts.compactar_tipo_esquema --estado sonora

  # Compacta varios estados:
  python -m scripts.compactar_tipo_esquema --estado sonora --estado yucatan

  # Compacta TODOS los estados con JSONs en predial-mx-v2/:
  python -m scripts.compactar_tipo_esquema --all

OUTPUT
───────
Default: `output/predial_compact_{estado}.csv` (uno por estado).
Override con `--out`.

Columnas:
  estado, cvegeo, anio, slug, tipo_esquema, requiere_revision,
  fuente, modelo, intentos, escalado, usado_vision, usado_vision_multi,
  clasificacion_justificacion, archivo
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

from src.core.llm_extract import OUTPUT_ROOT, ROOT


COMPACT_FIELDS = [
    "estado", "cvegeo", "anio", "slug",
    "tipo_esquema", "requiere_revision",
    "fuente", "modelo", "intentos", "escalado",
    "usado_reocr", "usado_vision", "usado_vision_multi",
    "clasificacion_justificacion",
    "archivo",
]


@dataclass
class CompactRow:
    estado: str
    cvegeo: str
    anio: int
    slug: str
    tipo_esquema: str
    requiere_revision: bool
    fuente: str
    modelo: str
    intentos: int
    escalado: bool
    usado_reocr: bool
    usado_vision: bool
    usado_vision_multi: bool
    clasificacion_justificacion: str
    archivo: str


def _compactar_json(path: Path, estado: str) -> CompactRow | None:
    """Lee un JSON y devuelve una CompactRow, o None si está irrecuperable."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[skip] no se pudo parsear {path.name}: {e}", file=sys.stderr)
        return None

    pred = payload.get("predial")
    meta = payload.get("_meta") or {}
    meta_v2 = payload.get("_meta_v2") or {}

    # tipo_esquema: si pred es None o sin campo, marcar 'sin_dato'
    if isinstance(pred, dict):
        tipo = pred.get("tipo_esquema") or "sin_dato"
        clasif = pred.get("clasificacion_justificacion") or ""
    else:
        tipo = "sin_dato"
        clasif = ""

    # Derivar cvegeo, anio, slug del nombre o de _meta_v2
    cvegeo = str(meta_v2.get("cvegeo") or "").zfill(5)
    anio = meta_v2.get("anio")

    # Fallback: parsear el nombre del archivo
    # Formato esperado: {PREFIJO}_PREDIAL_{anio}_{slug}.json
    # Ej. SON_PREDIAL_2014_agua_prieta.json
    stem = path.stem
    slug = ""
    parts = stem.split("_PREDIAL_")
    if len(parts) == 2:
        anio_slug = parts[1]
        try:
            anio_str, slug = anio_slug.split("_", 1)
            if not anio:
                anio = int(anio_str)
        except ValueError:
            pass

    if not isinstance(anio, int):
        try:
            anio = int(anio)
        except (TypeError, ValueError):
            print(f"[skip] no pude inferir anio de {path.name}", file=sys.stderr)
            return None

    return CompactRow(
        estado=estado,
        cvegeo=cvegeo,
        anio=anio,
        slug=slug,
        tipo_esquema=tipo,
        requiere_revision=bool(meta_v2.get("requiere_revision", False)),
        fuente=str(meta.get("fuente") or ""),
        modelo=str(meta.get("modelo") or ""),
        intentos=int(meta_v2.get("intentos") or 0),
        escalado=bool(meta_v2.get("escalado", False)),
        usado_reocr=bool(meta_v2.get("usado_reocr", False)),
        usado_vision=bool(meta_v2.get("usado_vision", False)),
        usado_vision_multi=bool(meta_v2.get("usado_vision_multi", False)),
        clasificacion_justificacion=clasif,
        archivo=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else path.name,
    )


def _compactar_estado(estado: str, out_path: Path) -> dict:
    """Compacta todos los JSONs de un estado. Devuelve resumen."""
    in_dir = OUTPUT_ROOT / estado
    if not in_dir.exists():
        print(f"[error] no existe {in_dir}", file=sys.stderr)
        return {"estado": estado, "n_total": 0, "n_compactados": 0}

    rows: list[CompactRow] = []
    for path in sorted(in_dir.glob("*.json")):
        row = _compactar_json(path, estado=estado)
        if row is not None:
            rows.append(row)

    # Detectar duplicados (mismo cvegeo+anio): conservar el de menor
    # `requiere_revision` (i.e. preferir el válido sobre el inválido).
    seen: dict[tuple[str, int], CompactRow] = {}
    for r in rows:
        key = (r.cvegeo, r.anio)
        if key not in seen:
            seen[key] = r
        else:
            # Tie-break: preferir no-revision
            if seen[key].requiere_revision and not r.requiere_revision:
                seen[key] = r

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COMPACT_FIELDS)
        writer.writeheader()
        for r in seen.values():
            writer.writerow(asdict(r))

    # Resumen por tipo_esquema
    from collections import Counter
    tipo_counter = Counter(r.tipo_esquema for r in seen.values())
    n_revision = sum(1 for r in seen.values() if r.requiere_revision)

    print(f"\n=== {estado.upper()} ===")
    print(f"  archivos JSON leídos:   {len(rows)}")
    print(f"  filas compactadas:      {len(seen)} (deduplicadas)")
    print(f"  requiere_revision:      {n_revision}")
    print(f"  distribución tipo_esquema:")
    for tipo, count in tipo_counter.most_common():
        print(f"    {tipo:30s} {count:4d}")
    print(f"  output:                 {out_path}")

    return {
        "estado": estado,
        "n_total": len(rows),
        "n_compactados": len(seen),
        "n_revision": n_revision,
        "out_path": str(out_path),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--estado", action="append", default=[],
                        help="Estado a compactar (puede usarse varias veces).")
    parser.add_argument("--all", action="store_true",
                        help="Compactar todos los estados con JSONs.")
    parser.add_argument("--out", type=str, default=None,
                        help="Path explícito de salida. Solo válido si "
                             "--estado se usa una sola vez.")
    parser.add_argument("--out-dir", type=str, default=None,
                        help="Directorio donde escribir los CSVs compactos. "
                             "Default: output/")
    args = parser.parse_args(argv)

    if not args.estado and not args.all:
        parser.error("Debe usar --estado o --all")

    if args.all:
        # Descubrir estados con JSONs
        if not OUTPUT_ROOT.exists():
            print(f"[error] no existe {OUTPUT_ROOT}", file=sys.stderr)
            return 1
        estados = sorted(
            d.name for d in OUTPUT_ROOT.iterdir()
            if d.is_dir() and any(d.glob("*.json"))
        )
    else:
        estados = list(dict.fromkeys(args.estado))  # dedup mantiene orden

    if not estados:
        print("[info] ningún estado a procesar", file=sys.stderr)
        return 0

    out_dir = Path(args.out_dir) if args.out_dir else (ROOT / "output")

    if args.out and len(estados) > 1:
        parser.error("--out solo se permite con un solo --estado")

    summaries = []
    for estado in estados:
        if args.out:
            out_path = Path(args.out)
        else:
            out_path = out_dir / f"predial_compact_{estado}.csv"
        summary = _compactar_estado(estado, out_path)
        summaries.append(summary)

    print(f"\n=== TOTAL ===")
    total_compact = sum(s["n_compactados"] for s in summaries)
    total_revision = sum(s.get("n_revision", 0) for s in summaries)
    print(f"  estados procesados: {len(summaries)}")
    print(f"  filas compactadas:  {total_compact}")
    print(f"  requiere_revision:  {total_revision}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
