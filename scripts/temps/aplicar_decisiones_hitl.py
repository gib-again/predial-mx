"""Aplica decisiones HITL desde la cola unificada.

Lee ``output/hitl/cola_unificada.csv`` (o un CSV compatible) con la columna
``decision`` llena por un humano.  Decisiones posibles:

  - ``confirmar_ok``              hallazgo revisado, sin problema.  No-op.
  - ``propagar_previo``           (D12) copia JSON del año anterior
                                  con ``_meta.modelo = imputed_human_propagation``.
  - ``reextraer``                 agrega a ``cola_reextraccion.csv`` para
                                  re-extracción LLM con hint.
  - ``re_segmentar``              escribe override en
                                  ``data/{estado}/manual_pdf_overrides.csv``,
                                  luego encola para re-extracción.
                                  Requiere ``paginas=X-Y`` en campo ``notas``;
                                  opcionalmente ``pdf=ruta/al/pdf``.
  - ``ignorar``                   descarta hallazgo.  No-op.

Salidas:
  - ``output/hitl/hitl_bitacora.csv``      append-only con timestamp
  - ``output/hitl/cola_reextraccion.csv``  archivos para re-extracción

Uso:
  python -m scripts.aplicar_decisiones_hitl
  python -m scripts.aplicar_decisiones_hitl --dry-run
  python -m scripts.aplicar_decisiones_hitl --csv output/hitl/cola_unificada.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HITL_DIR = Path("output/hitl")
HITL_JSON_DIR = Path("predial-mx-v3-hitl")
DEFAULT_CSV = HITL_DIR / "cola_unificada.csv"
QUEUE_CSV = HITL_DIR / "cola_reextraccion.csv"
BITACORA_CSV = HITL_DIR / "hitl_bitacora.csv"
DATA_ROOT = Path("data")

VALID_DECISIONS = {
    "confirmar_ok",
    "propagar_previo",
    "corregir_previo",
    "reextraer",
    "re_segmentar",
    "ignorar",
}

REEXTRACT_HINT = (
    "Extraer ARTÍCULO PRINCIPAL DE TARIFA del impuesto predial. "
    "Ignorar artículos de mínimo predial, transitorios, vigencia, beneficios "
    "y bonificaciones a menos que sean la única tarifa."
)

_RE_PAGINAS = re.compile(r"paginas\s*=\s*([\d,\s-]+)")
_RE_PDF = re.compile(r"pdf\s*=\s*(\S+)")


def _load_decisions(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        raise SystemExit(f"No existe {csv_path}. Corre primero run_detectors.")
    with csv_path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _append_bitacora(rows: list[dict]) -> None:
    if not rows:
        return
    is_new = not BITACORA_CSV.exists()
    BITACORA_CSV.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "timestamp", "id", "decision", "detector", "severidad",
        "estado", "estado_slug", "municipio", "municipio_slug",
        "cvegeo", "anio", "senal", "json_path", "notas",
        "json_propagado",
    ]
    with BITACORA_CSV.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if is_new:
            w.writeheader()
        w.writerows(rows)


def _write_reextraction_queue(rows: list[dict]) -> None:
    if not rows:
        return
    QUEUE_CSV.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "estado_slug", "municipio_slug", "cvegeo", "anio",
        "json_path", "hint", "notas", "procesado", "timestamp",
    ]
    is_new = not QUEUE_CSV.exists()
    with QUEUE_CSV.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if is_new:
            w.writeheader()
        w.writerows(rows)


def _parse_resegment_notas(notas: str) -> tuple[str, str]:
    """Extract paginas and pdf from notas field.

    Expected format: ``paginas=20-22`` or ``paginas=20-22; pdf=path/to/file.pdf``
    """
    paginas = ""
    pdf = ""
    m = _RE_PAGINAS.search(notas)
    if m:
        paginas = m.group(1).strip()
    m = _RE_PDF.search(notas)
    if m:
        pdf = m.group(1).strip()
    return paginas, pdf


def _write_override(
    estado_slug: str, anio: int, cvegeo: str,
    paginas: str, pdf_correcto: str, nota: str,
) -> Path:
    """Append a row to data/{estado}/manual_pdf_overrides.csv."""
    override_csv = DATA_ROOT / estado_slug / "manual_pdf_overrides.csv"
    override_csv.parent.mkdir(parents=True, exist_ok=True)
    cols = ["anio", "cvegeo", "pdf_correcto", "paginas", "nota_auditor"]
    is_new = not override_csv.exists()
    with override_csv.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        if is_new:
            w.writeheader()
        w.writerow({
            "anio": anio,
            "cvegeo": cvegeo,
            "pdf_correcto": pdf_correcto,
            "paginas": paginas,
            "nota_auditor": nota,
        })
    return override_csv


def _propagate_v3(row: dict, timestamp: str) -> Path | None:
    """For D12 propagar_previo: find previous year's JSON and copy it."""
    json_path = Path(row.get("json_path", ""))
    if not json_path.exists():
        print(f"  [ERROR] JSON no existe: {json_path}")
        return None

    est_slug = row.get("estado_slug", "")
    muni_slug = row.get("municipio_slug", "")
    anio = int(row.get("anio", 0))

    # Find previous year's JSON in same directory
    prev_year = anio - 1
    parent = json_path.parent
    prefix = json_path.name.split(f"_{anio}_")[0]
    prev_path = parent / f"{prefix}_{prev_year}_{muni_slug}.json"
    if not prev_path.exists():
        print(f"  [ERROR] JSON año previo no existe: {prev_path}")
        return None

    dst = HITL_JSON_DIR / est_slug / json_path.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc = json.loads(prev_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [ERROR] Leyendo {prev_path}: {e}")
        return None

    meta = doc.get("_meta") or {}
    meta["modelo"] = "imputed_human_propagation"
    meta["imputed_from_year"] = prev_year
    meta["target_year"] = anio
    meta["hitl_timestamp"] = timestamp
    meta["hitl_decision"] = "propagar_previo"
    doc["_meta"] = meta

    dst.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return dst


def _correct_prev_v3(row: dict, timestamp: str) -> Path | None:
    """For D12 corregir_previo: copy current year's JSON to overwrite previous year."""
    json_path = Path(row.get("json_path", ""))
    if not json_path.exists():
        print(f"  [ERROR] JSON no existe: {json_path}")
        return None

    est_slug = row.get("estado_slug", "")
    muni_slug = row.get("municipio_slug", "")
    anio = int(row.get("anio", 0))

    prev_year = anio - 1
    prefix = json_path.name.split(f"_{anio}_")[0]
    prev_name = f"{prefix}_{prev_year}_{muni_slug}.json"

    dst = HITL_JSON_DIR / est_slug / prev_name
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [ERROR] Leyendo {json_path}: {e}")
        return None

    meta = doc.get("_meta") or {}
    meta["modelo"] = "imputed_human_correction"
    meta["imputed_from_year"] = anio
    meta["target_year"] = prev_year
    meta["hitl_timestamp"] = timestamp
    meta["hitl_decision"] = "corregir_previo"
    doc["_meta"] = meta

    dst.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(DEFAULT_CSV),
                    help=f"CSV de decisiones (default {DEFAULT_CSV}).")
    ap.add_argument("--dry-run", action="store_true",
                    help="No escribe archivos; solo reporta lo que haría.")
    args = ap.parse_args()
    csv_path = Path(args.csv)

    decisiones = _load_decisions(csv_path)
    print(f"Cargadas {len(decisiones)} filas desde {csv_path}")

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    bitacora: list[dict] = []
    cola: list[dict] = []
    contadores: dict[str, int] = {d: 0 for d in VALID_DECISIONS}
    contadores.update({"sin_decision": 0, "invalida": 0, "error": 0})

    for row in decisiones:
        decision = (row.get("decision") or "").strip().lower()
        if not decision:
            contadores["sin_decision"] += 1
            continue
        if decision not in VALID_DECISIONS:
            print(f"  [WARN] decisión inválida '{decision}' en "
                  f"{row.get('municipio', '?')} {row.get('anio', '?')}")
            contadores["invalida"] += 1
            continue

        bit_row = {
            "timestamp": timestamp,
            "id": row.get("id", ""),
            "decision": decision,
            "detector": row.get("detector", ""),
            "severidad": row.get("severidad", ""),
            "estado": row.get("estado", ""),
            "estado_slug": row.get("estado_slug", ""),
            "municipio": row.get("municipio", ""),
            "municipio_slug": row.get("municipio_slug", ""),
            "cvegeo": row.get("cvegeo", ""),
            "anio": row.get("anio", ""),
            "senal": row.get("senal", ""),
            "json_path": row.get("json_path", ""),
            "notas": row.get("notas", ""),
            "json_propagado": "",
        }

        if decision == "propagar_previo":
            if args.dry_run:
                bit_row["json_propagado"] = "(dry-run)"
            else:
                dst = _propagate_v3(row, timestamp)
                if dst is None:
                    contadores["error"] += 1
                    continue
                bit_row["json_propagado"] = str(dst)

        elif decision == "corregir_previo":
            if args.dry_run:
                bit_row["json_propagado"] = "(dry-run)"
            else:
                dst = _correct_prev_v3(row, timestamp)
                if dst is None:
                    contadores["error"] += 1
                    continue
                bit_row["json_propagado"] = str(dst)

        elif decision == "reextraer":
            cola.append({
                "estado_slug": row.get("estado_slug", ""),
                "municipio_slug": row.get("municipio_slug", ""),
                "cvegeo": row.get("cvegeo", ""),
                "anio": row.get("anio", ""),
                "json_path": row.get("json_path", ""),
                "hint": REEXTRACT_HINT,
                "notas": row.get("notas", ""),
                "procesado": "",
                "timestamp": "",
            })

        elif decision == "re_segmentar":
            notas = row.get("notas", "")
            paginas, pdf_correcto = _parse_resegment_notas(notas)
            if not paginas:
                print(f"  [WARN] re_segmentar sin paginas= en notas: "
                      f"{row.get('municipio', '?')} {row.get('anio', '?')}")
                contadores["error"] += 1
                continue
            if not args.dry_run:
                _write_override(
                    row.get("estado_slug", ""),
                    int(row.get("anio", 0)),
                    row.get("cvegeo", ""),
                    paginas,
                    pdf_correcto,
                    f"HITL re_segmentar: {notas}",
                )
            cola.append({
                "estado_slug": row.get("estado_slug", ""),
                "municipio_slug": row.get("municipio_slug", ""),
                "cvegeo": row.get("cvegeo", ""),
                "anio": row.get("anio", ""),
                "json_path": row.get("json_path", ""),
                "hint": f"OVERRIDE paginas={paginas}. " + REEXTRACT_HINT,
                "notas": notas,
                "procesado": "",
                "timestamp": "",
            })

        contadores[decision] += 1
        bitacora.append(bit_row)

    if not args.dry_run:
        _append_bitacora(bitacora)
        _write_reextraction_queue(cola)

    print("\nResumen:")
    for d in VALID_DECISIONS:
        if contadores[d]:
            print(f"  {d:30s} {contadores[d]}")
    print(f"  {'sin_decision':30s} {contadores['sin_decision']}")
    if contadores["invalida"]:
        print(f"  {'invalida':30s} {contadores['invalida']}")
    if contadores["error"]:
        print(f"  {'error':30s} {contadores['error']}")
    if cola:
        print(f"\nCola re-extracción: {QUEUE_CSV} ({len(cola)} nuevas)")
    if bitacora and not args.dry_run:
        print(f"Bitácora: {BITACORA_CSV} (append-only)")
    elif args.dry_run:
        print("\n(dry-run: no se escribió nada)")


if __name__ == "__main__":
    main()
