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
from dotenv import load_dotenv

# Cargar .env temprano para que OPENAI_API_KEY esté disponible.
load_dotenv()

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
    """Busca el PDF primero en data/{estado_slug}/pdf_raw/, luego en
    catalogs/discovered_laws/ (PDFs aportados por el auditor que no son
    parte de los tomos del POE).
    """
    candidates = [
        Path(f"data/{estado_slug}/pdf_raw"),
        Path("catalogs/discovered_laws"),
    ]
    base_lower = pdf_filename.lower()
    for root in candidates:
        if not root.exists():
            continue
        # Match exacto primero
        for p in root.rglob(pdf_filename):
            if p.is_file():
                return p
        # Match por basename (case-insensitive)
        for p in root.rglob("*.pdf"):
            if p.name.lower() == base_lower:
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


_RE_IMPUTAR_CON_DATOS = re.compile(
    r"imputar\s+con\s+datos\s+de\s+(\d{4})", re.IGNORECASE,
)


def _parse_directed_impute_year(notas: str) -> int | None:
    """Detecta 'imputar con datos de YYYY' en notas; retorna año fuente o None."""
    if not notas:
        return None
    m = _RE_IMPUTAR_CON_DATOS.search(notas)
    return int(m.group(1)) if m else None


def _find_json_by_cvegeo_year(
    estado_slug: str, prefijo: str, cvegeo: str, anio: int, default_slug: str,
) -> Path | None:
    """Localiza un JSON por (cvegeo, anio) sin asumir el slug. Primero prueba
    el slug INEGI esperado; si no existe, escanea predial-mx-v2/{estado}/ y
    devuelve el archivo cuyo `_meta_v2.cvegeo` y `_meta_v2.anio` coincidan
    (los segmenters por estado a veces usan slugs distintos al INEGI).
    """
    # 1. Intentar el slug INEGI directo
    direct = Path(f"predial-mx-v2/{estado_slug}/{prefijo}_PREDIAL_{anio}_{default_slug}.json")
    if direct.exists():
        return direct
    # 2. Escanear archivos del año coincidente
    pattern = f"{prefijo}_PREDIAL_{anio}_*.json"
    for p in Path(f"predial-mx-v2/{estado_slug}").glob(pattern):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            meta = d.get("_meta_v2") or {}
            if str(meta.get("cvegeo") or "").zfill(5) == cvegeo and meta.get("anio") == anio:
                return p
        except Exception:
            continue
    return None


def _write_directed_imputed(
    cvegeo: str, target_anio: int, source_anio: int, estado_slug: str,
    prefijo: str, slug: str, auditor: str, fecha: str, notas: str,
) -> tuple[Path | None, str]:
    """Imputación dirigida por auditor: clonar el JSON del año fuente al target.
    Retorna (path, msg). Si el JSON fuente no existe o es inválido → (None, error).
    """
    src_path = _find_json_by_cvegeo_year(
        estado_slug, prefijo, cvegeo, source_anio, slug,
    )
    if src_path is None:
        return None, f"JSON fuente no localizable para cvegeo={cvegeo} año={source_anio}"

    try:
        src_doc = json.loads(src_path.read_text(encoding="utf-8"))
    except Exception as e:
        return None, f"error leyendo JSON fuente: {e}"

    src_pred = src_doc.get("predial")
    if not isinstance(src_pred, dict) or not src_pred.get("tipo_esquema"):
        return None, f"JSON fuente sin predial.tipo_esquema válido"

    # Clonar predial entero del fuente.
    target_pred = json.loads(json.dumps(src_pred))
    old_com = (target_pred.get("comentarios") or "").strip()
    target_pred["comentarios"] = (
        f"[audit_directed_impute desde {source_anio}] "
        f"Auditor instruyó imputar con datos de {source_anio} (notas: {notas})."
        + (f" Comentario original: {old_com}" if old_com else "")
    )

    src_meta = src_doc.get("_meta") or {}
    target_doc = {
        "predial": target_pred,
        "_meta": {
            "fuente": src_meta.get("fuente", "txt"),
            "modelo": f"imputed_audit_directed[from_{source_anio}]",
        },
        "_meta_v2": {
            "intentos": 0,
            "requiere_revision": False,
            "razon": None,
            "tokens": {"input": 0, "output": 0, "cached": 0},
            "cvegeo": cvegeo,
            "estado": estado_slug,
            "anio": target_anio,
            "imputed_from_year": source_anio,
            "imputed_method": "audit_directed",
            "audit_auditor": auditor,
            "audit_fecha": fecha,
        },
    }
    out_path = Path(f"predial-mx-v2/{estado_slug}/{prefijo}_PREDIAL_{target_anio}_{slug}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(target_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path, f"clonado desde {source_anio}"


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
    ap.add_argument("--audit-csv", default="output/audits/audit_pendiente.csv")
    ap.add_argument("--log-csv", default="output/audits/reextract_log.csv")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--overwrite", action="store_true",
                    help="Sobrescribir JSONs existentes incluso si tienen modelo real "
                         "(útil cuando el LLM previo falló y el JSON tiene tipo_esquema=None).")
    ap.add_argument("--estado", default="",
                    help="Filtrar a un solo estado (NOM_ENT del catálogo, ej. 'Queretaro').")
    args = ap.parse_args()

    audit_path = Path(args.audit_csv)
    if not audit_path.exists():
        print(f"[ERROR] No existe {audit_path}")
        return

    rows = list(csv.DictReader(open(audit_path, encoding="utf-8-sig")))
    pending = [r for r in rows if (r.get("estatus") or "").strip()]
    if args.estado:
        pending = [r for r in pending if r.get("estado", "") == args.estado]
        print(f"Filtro --estado={args.estado!r}: {len(pending)} filas pendientes")
    print(f"Filas en audit: {len(rows)}; con estatus llenado: {len(pending)}; "
          f"--overwrite={args.overwrite}")

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
        # no sobrescribir — a menos que --overwrite o que el JSON tenga predial=null/tipo=None.
        v2_path = Path(f"predial-mx-v2/{estado_slug}/{prefijo}_PREDIAL_{anio}_{muni_slug}.json")
        if v2_path.exists() and not args.overwrite:
            try:
                existing = json.loads(v2_path.read_text(encoding="utf-8"))
                modelo = (existing.get("_meta") or {}).get("modelo", "")
                pred_existing = existing.get("predial")
                tipo_existing = (pred_existing or {}).get("tipo_esquema") if pred_existing else None
                # Si el JSON existente está vacío/inválido (tipo=None), permitir sobrescritura.
                if (
                    modelo
                    and not modelo.startswith(("imputed_", "audit_no_ley"))
                    and tipo_existing  # tiene tipo válido
                ):
                    log_rows.append(_row_resp(r, "skip", f"existe JSON real ({modelo}, tipo={tipo_existing}); no sobrescribir"))
                    n_skipped += 1
                    continue
            except Exception:
                pass

        if estatus == "no_existe_ley":
            # Detectar instrucción "imputar con datos de YYYY" en notas
            directed_year = _parse_directed_impute_year(notas)
            if directed_year and directed_year != anio:
                if args.dry_run:
                    print(f"  [DRY] directed_impute desde {directed_year} → {v2_path.name}")
                    log_rows.append(_row_resp(r, "would_directed_impute", f"desde {directed_year}"))
                    n_no_ley += 1
                    continue
                out, msg = _write_directed_imputed(
                    cvegeo, anio, directed_year, estado_slug,
                    prefijo, muni_slug, auditor, fecha, notas,
                )
                if out is None:
                    print(f"  [error directed_impute {anio}←{directed_year}] {msg}")
                    log_rows.append(_row_resp(r, "error_directed_impute", msg))
                    n_errors += 1
                else:
                    print(f"  [directed_impute {anio}←{directed_year}] → {out.name}")
                    log_rows.append(_row_resp(r, "wrote_directed_impute", str(out)))
                    n_no_ley += 1
                continue
            if directed_year == anio:
                # Auto-referencia: el auditor escribió el mismo año, probable typo.
                msg = f"notas dicen 'imputar con datos de {directed_year}' pero ese ES el año del hueco; ignorando"
                print(f"  [warn] {msg}")
                log_rows.append(_row_resp(r, "warn_self_ref", msg))
                n_skipped += 1
                continue

            # Sin instrucción de imputación → audit_no_ley sintético.
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
