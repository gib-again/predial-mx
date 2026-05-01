#!/usr/bin/env python3
"""Cierra los huecos de auditoría llenados por el revisor humano.

Lee output/audit_pendiente.csv. Para cada fila con `estatus`:

  - `encontrado`     : extrae el rango de páginas indicado del PDF objetivo
                        a focus_predial.txt y lanza extract_single() (LLM).
                        Persiste el JSON resultante en predial-mx-v2/{estado}/.
  - `no_existe_ley`  : escribe un JSON sintético determinista
                        (otro_no_clasificado / municipio_sin_impuesto, modelo
                        'audit_no_ley') en predial-mx-v2/{estado}/.
  - vacío            : skip (auditor no llegó a esa fila).

Idempotente: respeta JSONs reales preexistentes (modelo no-imputado/sintético).

Uso:
    python -m scripts.reextract_from_audit            # gasta tokens
    python -m scripts.reextract_from_audit --dry-run  # vista previa
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import fitz  # PyMuPDF

from src.core.balance_panel_v2 import (
    ESTADO_SLUG_BY_NOM_ENT,
    PREFIJOS_BY_SLUG,
)
from src.core.llm_extract import extract_single
from src.core.text_utils import slugify


def _parse_pages(pages_str: str) -> tuple[int, int] | None:
    """Parsea '47-52', '47', 'p.47-52', '47, 48, 49' → (start, end). 1-indexed."""
    s = pages_str.strip().lower().replace("p.", "").replace("pp.", "").strip()
    if not s:
        return None
    # Rango simple "47-52"
    m = re.match(r"^(\d+)\s*[-–—]\s*(\d+)$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Página única "47"
    m = re.match(r"^(\d+)$", s)
    if m:
        n = int(m.group(1))
        return n, n
    # Lista "47, 48, 49" — usar min y max
    nums = [int(x) for x in re.findall(r"\d+", s)]
    if nums:
        return min(nums), max(nums)
    return None


def _resolve_pdf_path(estado_slug: str, pdf_filename: str) -> Path | None:
    """Busca el PDF en data/{estado_slug}/pdf_raw/ recursivamente."""
    pdf_root = Path(f"data/{estado_slug}/pdf_raw")
    if not pdf_root.exists():
        return None
    # Match exacto primero
    for p in pdf_root.rglob(pdf_filename):
        if p.is_file():
            return p
    # Sin extensión exacta — buscar por basename
    base = pdf_filename.lower()
    for p in pdf_root.rglob("*.pdf"):
        if p.name.lower() == base:
            return p
    return None


def _extract_pages_to_txt(pdf_path: Path, page_start_1: int, page_end_1: int) -> str:
    """Extrae texto de páginas (1-indexed inclusive). Concatena por página."""
    parts = []
    with fitz.open(str(pdf_path)) as doc:
        n = doc.page_count
        for i in range(page_start_1 - 1, min(page_end_1, n)):
            t = doc[i].get_text("text") or ""
            parts.append(t)
            parts.append("\n")
    return "".join(parts).strip()


def _write_synthetic_no_ley(
    cvegeo: str, anio: int, estado_slug: str,
    prefijo: str, slug: str, auditor: str, fecha: str, notas: str,
) -> Path:
    """Emite JSON otro_no_clasificado/municipio_sin_impuesto cuando el auditor
    confirma que no se publicó Ley de Ingresos."""
    doc = {
        "predial": {
            "tipo_esquema": "otro_no_clasificado",
            "categoria": "municipio_sin_impuesto",
            "descripcion_estructural": (
                "Auditor confirmó que no existe Ley de Ingresos publicada para "
                f"este municipio en el ejercicio {anio}."
            ),
            "tabla_cruda": [],
            "minimo_predial": None,
            "comentarios": (
                f"Confirmado por {auditor or '(sin auditor)'} "
                f"el {fecha or '(sin fecha)'}."
                + (f" Notas: {notas}" if notas else "")
            ),
        },
        "_meta": {"fuente": "manual", "modelo": "audit_no_ley"},
        "_meta_v2": {
            "intentos": 0,
            "requiere_revision": False,
            "razon": None,
            "tokens": {"input": 0, "output": 0, "cached": 0},
            "cvegeo": cvegeo,
            "estado": estado_slug,
            "anio": anio,
            "audit_estatus": "no_existe_ley",
            "audit_auditor": auditor,
            "audit_fecha": fecha,
        },
    }
    out_path = Path(f"predial-mx-v2/{estado_slug}/{prefijo}_PREDIAL_{anio}_{slug}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path


def _row_resp(row: dict, status: str, msg: str) -> dict:
    return {
        "cvegeo": row.get("cvegeo", ""),
        "estado": row.get("estado", ""),
        "municipio": row.get("municipio", ""),
        "ejercicio_gap": row.get("ejercicio_gap", ""),
        "estatus_audit": row.get("estatus", ""),
        "result": status,
        "mensaje": msg,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--audit-csv", default="output/audit_pendiente.csv")
    ap.add_argument("--log-csv", default="output/reextract_log.csv")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    audit_path = Path(args.audit_csv)
    if not audit_path.exists():
        print(f"[ERROR] No existe {audit_path}")
        return

    rows = list(csv.DictReader(open(audit_path, encoding="utf-8-sig")))
    pending = [r for r in rows if (r.get("estatus") or "").strip()]
    print(f"Filas en audit: {len(rows)}; con estatus llenado: {len(pending)}")

    if not pending:
        print("Nada por procesar.")
        return

    log_rows: list[dict] = []
    n_extracted = 0
    n_no_ley = 0
    n_skipped = 0
    n_errors = 0

    for r in pending:
        estado_nom = (r.get("estado") or "").strip()
        estado_slug = ESTADO_SLUG_BY_NOM_ENT.get(estado_nom)
        cvegeo = (r.get("cvegeo") or "").strip()
        try:
            anio = int(r.get("ejercicio_gap") or 0)
        except (TypeError, ValueError):
            anio = 0
        muni_slug = slugify(r.get("municipio", ""))
        prefijo = PREFIJOS_BY_SLUG.get(estado_slug or "", "")
        estatus = (r.get("estatus") or "").strip().lower()
        auditor = (r.get("auditor") or "").strip()
        fecha = (r.get("fecha") or "").strip()
        notas = (r.get("notas") or "").strip()

        if not (estado_slug and prefijo and muni_slug and anio and cvegeo):
            log_rows.append(_row_resp(r, "skip", "metadata incompleta (estado/cvegeo/anio/slug)"))
            n_skipped += 1
            continue

        # Idempotencia: si ya existe JSON real (no imputado, no sintético previo de audit),
        # no sobrescribir.
        v2_path = Path(f"predial-mx-v2/{estado_slug}/{prefijo}_PREDIAL_{anio}_{muni_slug}.json")
        if v2_path.exists():
            try:
                existing = json.loads(v2_path.read_text(encoding="utf-8"))
                modelo = (existing.get("_meta") or {}).get("modelo", "")
                if modelo and not modelo.startswith(("imputed_", "audit_no_ley")):
                    log_rows.append(_row_resp(r, "skip", f"existe JSON real ({modelo}); no sobrescribir"))
                    n_skipped += 1
                    continue
            except Exception:
                pass

        if estatus == "no_existe_ley":
            if args.dry_run:
                print(f"  [DRY] no_existe_ley → {v2_path}")
                log_rows.append(_row_resp(r, "would_write_no_ley", str(v2_path)))
                n_no_ley += 1
                continue
            out = _write_synthetic_no_ley(
                cvegeo, anio, estado_slug, prefijo, muni_slug, auditor, fecha, notas,
            )
            print(f"  [no_ley] → {out}")
            log_rows.append(_row_resp(r, "wrote_no_ley", str(out)))
            n_no_ley += 1
            continue

        if estatus != "encontrado":
            log_rows.append(_row_resp(r, "skip", f"estatus inesperado: {estatus!r}"))
            n_skipped += 1
            continue

        # Caso 'encontrado': resolver pdf + páginas y extraer
        pdf_objetivo = (r.get("pdf_objetivo") or "").strip()
        pages_str = (r.get("paginas") or "").strip()
        if not pdf_objetivo or not pages_str:
            log_rows.append(_row_resp(r, "error", "encontrado pero pdf_objetivo o paginas vacíos"))
            n_errors += 1
            continue

        pdf_path = _resolve_pdf_path(estado_slug, pdf_objetivo)
        if pdf_path is None:
            log_rows.append(_row_resp(r, "error", f"PDF no encontrado: {pdf_objetivo}"))
            n_errors += 1
            continue

        pages = _parse_pages(pages_str)
        if pages is None:
            log_rows.append(_row_resp(r, "error", f"paginas no parseables: {pages_str!r}"))
            n_errors += 1
            continue

        # Extraer TXT y guardar a focus_predial
        try:
            txt = _extract_pages_to_txt(pdf_path, pages[0], pages[1])
        except Exception as e:
            log_rows.append(_row_resp(r, "error", f"fitz extract: {e}"))
            n_errors += 1
            continue
        if len(txt) < 50:
            log_rows.append(_row_resp(r, "error", f"TXT extraído muy corto ({len(txt)} chars)"))
            n_errors += 1
            continue

        focus_dir = Path(f"data/{estado_slug}/focus_predial/{anio}")
        focus_dir.mkdir(parents=True, exist_ok=True)
        focus_txt = focus_dir / f"{prefijo}_PREDIAL_{anio}_{muni_slug}.txt"

        if args.dry_run:
            print(f"  [DRY] would write {focus_txt} ({len(txt)} chars) y llamar extract_single")
            log_rows.append(_row_resp(r, "would_extract", f"{pdf_path.name} pp.{pages[0]}-{pages[1]}, {len(txt)} chars"))
            n_extracted += 1
            continue

        focus_txt.write_text(txt, encoding="utf-8")
        print(f"  [stage] {focus_txt}  ←  {pdf_path.name} pp.{pages[0]}-{pages[1]} ({len(txt)} chars)")

        try:
            json_dir = Path(f"predial-mx-v2/{estado_slug}")
            out = extract_single(
                txt_path=focus_txt,
                json_dir=json_dir,
                prefijo=prefijo,
                estado_nombre=estado_nom,
                pdf_fallback=False,  # ya es un TXT focalizado por el auditor
            )
            if out is None:
                log_rows.append(_row_resp(r, "error", "extract_single retornó None"))
                n_errors += 1
            else:
                log_rows.append(_row_resp(r, "extracted_ok", str(out)))
                n_extracted += 1
        except Exception as e:
            log_rows.append(_row_resp(r, "error", f"extract_single: {e}"))
            n_errors += 1

    # Escribir log
    log_path = Path(args.log_csv)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=[
            "cvegeo", "estado", "municipio", "ejercicio_gap",
            "estatus_audit", "result", "mensaje",
        ])
        w.writeheader()
        for lr in log_rows:
            w.writerow(lr)

    print()
    print(f"  Extraídos vía LLM: {n_extracted}")
    print(f"  No-ley sintéticos: {n_no_ley}")
    print(f"  Saltados:          {n_skipped}")
    print(f"  Errores:           {n_errors}")
    print(f"  -> log: {log_path}")


if __name__ == "__main__":
    main()
