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

from src.core.catalog import cvegeo_to_nombre
from src.core.constants import json_predial_hitl_dir
from src.core.corpus import adjacent_json, resolve_json
from src.hitl.decisiones import (
    EDIT_WHITELIST,
    append_edicion,
    load_latest,
    procedencia_hitl,
)

HITL_DIR = Path("output/hitl")
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


def _load_decisions(csv_path: Path | None = None) -> list[dict]:
    """Carga las decisiones desde el log append-only (fuente de verdad).

    Cada decisión se enriquece con ``json_path`` (resuelto vía catálogo/corpus)
    y el nombre de display.  ``csv_path`` se ignora (compat retro de la firma).
    """
    decisiones = []
    for d in load_latest().values():
        decision = (d.get("decision") or "").strip().lower()
        if not decision:
            continue
        est = d.get("estado_slug", "")
        slug = d.get("municipio_slug", "")
        try:
            anio = int(d.get("anio", 0) or 0)
        except ValueError:
            anio = 0
        jp = resolve_json(est, anio, slug) if (est and slug and anio) else Path("")
        decisiones.append({
            "id": d.get("id", ""),
            "decision": decision,
            "sub_opcion": d.get("sub_opcion", ""),
            "estado_slug": est,
            "estado": cvegeo_to_nombre(d.get("cvegeo", "")) and est or est,
            "municipio_slug": slug,
            "municipio": cvegeo_to_nombre(d.get("cvegeo", "")) or slug,
            "cvegeo": d.get("cvegeo", ""),
            "anio": anio,
            "json_path": str(jp or ""),
            "notas": d.get("notas", ""),
            "detector": "",
            "severidad": "",
            "senal": "",
        })
    return decisiones


def _append_bitacora(rows: list[dict]) -> None:
    if not rows:
        return
    is_new = not BITACORA_CSV.exists()
    BITACORA_CSV.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "timestamp", "id", "decision", "sub_opcion", "procedencia_hitl",
        "detector", "severidad",
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
        "json_path", "hint", "hint_tipo_esquema", "force_vision",
        "hint_paginas", "hint_notas", "notas", "procesado", "timestamp",
    ]
    is_new = not QUEUE_CSV.exists()
    with QUEUE_CSV.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if is_new:
            w.writeheader()
        w.writerows(rows)


_RE_KV = re.compile(r"(\w+)\s*=\s*([^;]+)")


def _parse_kv(notas: str) -> dict[str, str]:
    """Parsea pares ``clave=valor`` separados por ``;`` del campo notas."""
    return {m.group(1).strip().lower(): m.group(2).strip() for m in _RE_KV.finditer(notas or "")}


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
    anio = int(row.get("anio", 0))
    prev_year = anio - 1

    prev_path = adjacent_json(str(json_path), anio, -1)
    if not prev_path:
        print(f"  [ERROR] JSON año previo no existe para {est_slug} {anio}")
        return None

    dst = json_predial_hitl_dir(est_slug, anio) / json_path.name
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
    anio = int(row.get("anio", 0))
    prev_year = anio - 1
    prev_name = json_path.name.replace(f"_{anio}_", f"_{prev_year}_")

    dst = json_predial_hitl_dir(est_slug, prev_year) / prev_name
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


def _apply_cambio_menor(row: dict, dst: Path, timestamp: str) -> int:
    """Aplica ediciones de whitelist (§6a) sobre el JSON aceptado en ``dst``.

    Sólo campos en EDIT_WHITELIST.  Registra before/after en hitl_ediciones.csv y
    estampa ``_meta.cambios_menores`` (auditable) + aplica ``minimo_predial`` a
    ``predial.minimo_predial_general`` cuando el valor es numérico.  unidad y
    periodicidad quedan documentadas para aplicación downstream.  Devuelve nº de
    ediciones aplicadas.
    """
    edits = {k: v for k, v in _parse_kv(row.get("notas", "")).items() if k in EDIT_WHITELIST}
    if not edits or not dst.exists():
        return 0
    try:
        doc = json.loads(dst.read_text(encoding="utf-8"))
    except Exception:
        return 0
    predial = doc.get("predial") or {}
    cambios = []
    for campo, nuevo in edits.items():
        viejo = ""
        if campo == "minimo_predial":
            mpg = predial.get("minimo_predial_general") or {}
            viejo = mpg.get("monto", "")
            try:
                mpg["monto"] = float(str(nuevo).replace(",", ""))
                predial["minimo_predial_general"] = mpg
                doc["predial"] = predial
            except ValueError:
                pass
        cambios.append({"campo": campo, "valor_viejo": viejo, "valor_nuevo": nuevo})
        append_edicion(
            id=row.get("id", ""), cvegeo=row.get("cvegeo", ""),
            estado_slug=row.get("estado_slug", ""), anio=row.get("anio", ""),
            campo=campo, valor_viejo=viejo, valor_nuevo=nuevo,
        )
    meta = doc.get("_meta") or {}
    meta["cambios_menores"] = cambios
    meta["hitl_timestamp"] = timestamp
    doc["_meta"] = meta
    dst.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(cambios)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true",
                    help="No escribe archivos; solo reporta lo que haría.")
    args = ap.parse_args()

    from src.hitl.decisiones import DECISIONES_CSV
    decisiones = _load_decisions()
    print(f"Cargadas {len(decisiones)} decisiones desde {DECISIONES_CSV}")

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

        sub_opcion = (row.get("sub_opcion") or "").strip().lower()
        bit_row = {
            "timestamp": timestamp,
            "id": row.get("id", ""),
            "decision": decision,
            "sub_opcion": sub_opcion,
            "procedencia_hitl": procedencia_hitl(decision, sub_opcion),
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
                if sub_opcion == "cambio_menor":
                    _apply_cambio_menor(row, dst, timestamp)
                bit_row["json_propagado"] = str(dst)

        elif decision == "corregir_previo":
            if args.dry_run:
                bit_row["json_propagado"] = "(dry-run)"
            else:
                dst = _correct_prev_v3(row, timestamp)
                if dst is None:
                    contadores["error"] += 1
                    continue
                if sub_opcion == "cambio_menor":
                    _apply_cambio_menor(row, dst, timestamp)
                bit_row["json_propagado"] = str(dst)

        elif decision == "confirmar_ok":
            # Fiel = no-op (provenance en bitácora/log).  Cambio menor = aplica
            # whitelist sobre overlay HITL del JSON aceptado.
            if sub_opcion == "cambio_menor" and not args.dry_run:
                src = Path(row.get("json_path", ""))
                if src.exists():
                    dst = json_predial_hitl_dir(
                        row.get("estado_slug", ""), int(row.get("anio", 0) or 0)
                    ) / src.name
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if not dst.exists():
                        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
                    n = _apply_cambio_menor(row, dst, timestamp)
                    bit_row["json_propagado"] = str(dst) if n else ""

        elif decision == "reextraer":
            hints = _parse_kv(row.get("notas", ""))
            paginas = hints.get("paginas", "")
            pdf_correcto = hints.get("pdf", "")
            if paginas and not args.dry_run:
                _write_override(
                    row.get("estado_slug", ""), int(row.get("anio", 0) or 0),
                    row.get("cvegeo", ""), paginas, pdf_correcto,
                    f"HITL reextraer hint: {row.get('notas','')}",
                )
            cola.append({
                "estado_slug": row.get("estado_slug", ""),
                "municipio_slug": row.get("municipio_slug", ""),
                "cvegeo": row.get("cvegeo", ""),
                "anio": row.get("anio", ""),
                "json_path": row.get("json_path", ""),
                "hint": REEXTRACT_HINT,
                "hint_tipo_esquema": hints.get("hint_tipo", ""),
                "force_vision": "1" if hints.get("force_vision", "").lower() in ("1", "true", "yes") else "",
                "hint_paginas": paginas,
                "hint_notas": hints.get("hint_notas", "") or row.get("notas", ""),
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
