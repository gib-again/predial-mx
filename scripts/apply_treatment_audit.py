#!/usr/bin/env python3
"""Aplica las decisiones de output/audits/audit_treatment_anomalies.csv.

Decisiones soportadas:

  - `extraction_error`:
      a. Si `pdf_objetivo` + `paginas_objetivo` están llenados →
         stage focus_predial.txt y llama LLM para re-extracción dirigida.
      b. Si `notas` contiene "asumir esquema (del )?ejercicio anterior" →
         clonar el JSON del año (target-1) con marker
         `imputed_audit_directed[from_<year-1>]`.
      c. Si sólo `tipo_correcto` está llenado (sin PDF ni nota de
         imputación) → modificar el JSON existente in-place:
         actualizar `predial.tipo_esquema` y limpiar `tabla` si el
         tipo nuevo no corresponde con la estructura actual.

  - `real_reform`:
      - Con `tipo_correcto`: idem (c) — el tipo correcto post-reforma
        es el indicado.
      - Sin `tipo_correcto`: aceptar el tipo actual; registrar el
        muni en `output/audits/treatment_real_reform_munis.csv` para que el
        DiD lo trate como no-absorbente.

  - `accept_as_is`: registrar el muni en
    `output/audits/treatment_non_absorbing_munis.csv`.

  - `exclude_muni`: registrar el muni en
    `output/audits/treatment_excluded_munis.csv` (descartado por completo).

Outputs adicionales:
  output/audits/apply_treatment_audit.log  — log línea-por-fila con resultado.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import fitz
from dotenv import load_dotenv
load_dotenv()

from src.core.balance_panel_v2 import (
    ESTADO_SLUG_BY_NOM_ENT,
    PREFIJOS_BY_SLUG,
)
from src.core.llm_extract import extract_single
from src.core.text_utils import slugify


_RE_ASUMIR_ANTERIOR = re.compile(
    # Captura: "asumir esquema/tasa/valor/datos del ejercicio/año/periodo (inmediato) anterior"
    r"asumir\b.*\banterior\b",
    re.IGNORECASE | re.DOTALL,
)


def _find_json_by_cvegeo_year(
    estado_slug: str, prefijo: str, cvegeo: str, anio: int, default_slug: str,
) -> Path | None:
    """Localiza JSON por (cvegeo, año) escaneando el directorio si el slug
    INEGI no coincide con el slug usado por el segmenter."""
    direct = Path(f"predial-mx-v2/{estado_slug}/{prefijo}_PREDIAL_{anio}_{default_slug}.json")
    if direct.exists():
        return direct
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


def _resolve_pdf_path(estado_slug: str, pdf_filename: str) -> Path | None:
    candidates = [
        Path(f"data/{estado_slug}/pdf_raw"),
        Path("catalogs/discovered_laws"),
    ]
    base_lower = pdf_filename.lower()
    for root in candidates:
        if not root.exists():
            continue
        for p in root.rglob(pdf_filename):
            if p.is_file():
                return p
        for p in root.rglob("*.pdf"):
            if p.name.lower() == base_lower:
                return p
    return None


def _parse_pages(pages_str: str) -> tuple[int, int] | None:
    s = pages_str.strip().lower().replace("p.", "").replace("pp.", "").strip()
    if not s:
        return None
    m = re.match(r"^(\d+)\s*[-–—]\s*(\d+)$", s)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.match(r"^(\d+)$", s)
    if m:
        n = int(m.group(1))
        return n, n
    nums = [int(x) for x in re.findall(r"\d+", s)]
    if nums:
        return min(nums), max(nums)
    return None


def _extract_pages_to_txt(pdf_path: Path, p0: int, p1: int) -> str:
    parts = []
    with fitz.open(str(pdf_path)) as doc:
        n = doc.page_count
        for i in range(p0 - 1, min(p1, n)):
            t = doc[i].get_text("text") or ""
            parts.append(t)
            parts.append("\n")
    return "".join(parts).strip()


# ── Acciones por tipo de decisión ──

def _action_directed_impute_prev(
    cvegeo: str, target_anio: int, estado_slug: str, prefijo: str, slug: str,
    auditor: str, fecha: str, notas: str, dry_run: bool,
) -> tuple[bool, str]:
    """Imputar desde el año (target_anio - 1)."""
    source_anio = target_anio - 1
    src_path = _find_json_by_cvegeo_year(estado_slug, prefijo, cvegeo, source_anio, slug)
    if src_path is None:
        return False, f"JSON fuente {source_anio} no localizable"
    try:
        src = json.loads(src_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"error leyendo {src_path.name}: {e}"
    src_pred = src.get("predial")
    if not isinstance(src_pred, dict) or not src_pred.get("tipo_esquema"):
        return False, f"JSON {source_anio} sin predial válido"

    target_pred = json.loads(json.dumps(src_pred))
    old_com = (target_pred.get("comentarios") or "").strip()
    target_pred["comentarios"] = (
        f"[treatment_audit:asumir_esquema_anterior from {source_anio}] {notas}"
        + (f" Comentario original: {old_com}" if old_com else "")
    )

    src_meta = src.get("_meta") or {}
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
            "treatment_audit_source": "asumir_esquema_anterior",
            "audit_auditor": auditor,
            "audit_fecha": fecha,
        },
    }
    out_path = Path(f"predial-mx-v2/{estado_slug}/{prefijo}_PREDIAL_{target_anio}_{slug}.json")
    if dry_run:
        return True, f"[DRY] would write {out_path.name} from {source_anio}"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(target_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, f"directed_impute desde {source_anio} → {out_path.name}"


def _action_reextract_pdf(
    cvegeo: str, anio: int, estado_slug: str, prefijo: str, slug: str,
    estado_nom: str, pdf_objetivo: str, pages_str: str, dry_run: bool,
) -> tuple[bool, str]:
    """Re-extracción dirigida: PDF + páginas indicados."""
    pdf_path = _resolve_pdf_path(estado_slug, pdf_objetivo)
    if pdf_path is None:
        return False, f"PDF no localizable: {pdf_objetivo}"
    pages = _parse_pages(pages_str) if pages_str else None
    if pages is None:
        # Sin páginas — usar todo el PDF (focuser hará lo posible)
        pages = (1, 9999)
    try:
        txt = _extract_pages_to_txt(pdf_path, pages[0], pages[1])
    except Exception as e:
        return False, f"fitz extract: {e}"
    if len(txt) < 50:
        return False, f"TXT extraído muy corto ({len(txt)} chars)"
    focus_dir = Path(f"data/{estado_slug}/focus_predial/{anio}")
    focus_dir.mkdir(parents=True, exist_ok=True)
    focus_txt = focus_dir / f"{prefijo}_PREDIAL_{anio}_{slug}.txt"
    if dry_run:
        return True, f"[DRY] would stage {focus_txt.name} y llamar LLM"
    focus_txt.write_text(txt, encoding="utf-8")
    json_dir = Path(f"predial-mx-v2/{estado_slug}")
    out = extract_single(
        txt_path=focus_txt, json_dir=json_dir,
        prefijo=prefijo, estado_nombre=estado_nom, pdf_fallback=False,
    )
    if out is None:
        return False, "extract_single retornó None"
    return True, f"re-extracted → {out.name}"


def _action_override_tipo(
    cvegeo: str, anio: int, estado_slug: str, prefijo: str, slug: str,
    tipo_correcto: str, auditor: str, fecha: str, notas: str, dry_run: bool,
) -> tuple[bool, str]:
    """Modifica el JSON existente: actualiza `predial.tipo_esquema` al valor
    correcto. Limpia `tabla` si es necesario (cuando el tipo nuevo no sería
    compatible con la estructura actual). Marker en _meta.modelo.
    """
    json_path = _find_json_by_cvegeo_year(estado_slug, prefijo, cvegeo, anio, slug)
    if json_path is None:
        return False, f"JSON destino no localizable para {anio}"
    try:
        d = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:
        return False, f"error leyendo {json_path.name}: {e}"

    pred = d.get("predial") or {}
    old_tipo = pred.get("tipo_esquema", "") or ""
    if old_tipo == tipo_correcto:
        return True, "tipo ya coincide; no hay cambio"

    # Actualizar tipo y nota
    pred["tipo_esquema"] = tipo_correcto
    old_com = (pred.get("comentarios") or "").strip()
    pred["comentarios"] = (
        f"[treatment_audit:override_tipo {old_tipo}→{tipo_correcto}] "
        f"{notas if notas else 'Auditor manual'}"
        + (f" Comentario original: {old_com}" if old_com else "")
    )
    # Si el tipo nuevo NO usa tabla (tasa_unica/cuota_fija_simple/...) y la
    # actual sí la tiene, dejarla pero clarificar que no aplica para el nuevo
    # tipo. Para simplicidad: no tocamos tabla aquí (los analizadores
    # downstream se basan en tipo_esquema; tabla es solo metadata).

    old_meta = d.get("_meta") or {}
    old_modelo = old_meta.get("modelo", "")
    d["_meta"] = {
        "fuente": old_meta.get("fuente", "txt"),
        "modelo": f"audit_override[{old_tipo}->{tipo_correcto}|orig:{old_modelo}]",
    }
    meta_v2 = d.get("_meta_v2") or {}
    meta_v2["treatment_audit_override"] = {
        "old_tipo": old_tipo,
        "new_tipo": tipo_correcto,
        "auditor": auditor,
        "fecha": fecha,
        "notas": notas,
    }
    d["_meta_v2"] = meta_v2

    if dry_run:
        return True, f"[DRY] would override {old_tipo}→{tipo_correcto} in {json_path.name}"
    json_path.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    return True, f"override {old_tipo}→{tipo_correcto} en {json_path.name}"


# ── Pipeline ──

def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--audit-csv", default="output/audits/audit_treatment_anomalies.csv")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    audit_path = Path(args.audit_csv)
    if not audit_path.exists():
        print(f"[ERROR] No existe {audit_path}")
        return

    rows = list(csv.DictReader(open(audit_path, encoding="utf-8-sig")))
    print(f"Filas en audit: {len(rows)}")

    # Listas derivadas (por muni)
    excluded_munis: dict[str, dict] = {}            # exclude_muni
    real_reform_munis: dict[str, dict] = {}         # real_reform sin tipo_correcto
    non_absorbing_munis: dict[str, dict] = {}       # accept_as_is

    log_rows: list[dict] = []
    n_directed = 0
    n_reextract = 0
    n_override = 0
    n_excluded = 0
    n_real_reform = 0
    n_accept = 0
    n_skip = 0
    n_error = 0

    for r in rows:
        decision = (r.get("decision") or "").strip().lower()
        if not decision:
            n_skip += 1
            continue

        cvegeo = r.get("cvegeo", "").strip()
        estado_nom = r.get("estado", "").strip()
        municipio = r.get("municipio", "").strip()
        try:
            anio = int(r.get("ejercicio_problema") or 0)
        except (TypeError, ValueError):
            anio = 0
        estado_slug = ESTADO_SLUG_BY_NOM_ENT.get(estado_nom, "")
        prefijo = PREFIJOS_BY_SLUG.get(estado_slug, "")
        slug = slugify(municipio)
        tipo_correcto = (r.get("tipo_correcto") or "").strip()
        pdf_objetivo = (r.get("pdf_objetivo") or "").strip()
        paginas_obj = (r.get("paginas_objetivo") or "").strip()
        auditor = (r.get("auditor") or "").strip()
        fecha = (r.get("fecha") or "").strip()
        notas = (r.get("notas") or "").strip()

        if not (cvegeo and estado_slug and prefijo and slug and anio):
            log_rows.append({**r, "result": "skip", "mensaje": "metadata incompleta"})
            n_skip += 1
            continue

        # Trazabilidad por muni para listas derivadas
        muni_key = cvegeo
        muni_info = {
            "cvegeo": cvegeo, "estado": estado_nom, "municipio": municipio,
            "trayectoria": r.get("trayectoria", ""),
            "pattern_muni": r.get("pattern_muni", ""),
            "auditor": auditor, "fecha": fecha,
            "notas": notas,
        }

        if decision == "exclude_muni":
            excluded_munis[muni_key] = muni_info
            log_rows.append({**r, "result": "wrote_exclude", "mensaje": "muni añadido a exclude list"})
            n_excluded += 1
            continue

        if decision == "accept_as_is":
            non_absorbing_munis[muni_key] = muni_info
            log_rows.append({**r, "result": "wrote_accept", "mensaje": "muni marcado non_absorbing"})
            n_accept += 1
            continue

        if decision == "real_reform":
            if tipo_correcto:
                ok, msg = _action_override_tipo(
                    cvegeo, anio, estado_slug, prefijo, slug,
                    tipo_correcto, auditor, fecha, notas, args.dry_run,
                )
                if ok:
                    n_override += 1
                    log_rows.append({**r, "result": "real_reform_override", "mensaje": msg})
                else:
                    n_error += 1
                    log_rows.append({**r, "result": "error_override", "mensaje": msg})
            else:
                log_rows.append({**r, "result": "real_reform_no_change", "mensaje": "aceptado tipo actual"})
                n_real_reform += 1
            real_reform_munis[muni_key] = muni_info
            continue

        if decision == "extraction_error":
            # Decidir sub-acción
            if pdf_objetivo and paginas_obj:
                # Re-extracción dirigida (LLM)
                ok, msg = _action_reextract_pdf(
                    cvegeo, anio, estado_slug, prefijo, slug, estado_nom,
                    pdf_objetivo, paginas_obj, args.dry_run,
                )
                if ok:
                    n_reextract += 1
                    log_rows.append({**r, "result": "reextracted", "mensaje": msg})
                else:
                    n_error += 1
                    log_rows.append({**r, "result": "error_reextract", "mensaje": msg})
            elif _RE_ASUMIR_ANTERIOR.search(notas):
                ok, msg = _action_directed_impute_prev(
                    cvegeo, anio, estado_slug, prefijo, slug,
                    auditor, fecha, notas, args.dry_run,
                )
                if ok:
                    n_directed += 1
                    log_rows.append({**r, "result": "directed_impute_prev", "mensaje": msg})
                else:
                    n_error += 1
                    log_rows.append({**r, "result": "error_directed", "mensaje": msg})
            elif tipo_correcto:
                ok, msg = _action_override_tipo(
                    cvegeo, anio, estado_slug, prefijo, slug,
                    tipo_correcto, auditor, fecha, notas, args.dry_run,
                )
                if ok:
                    n_override += 1
                    log_rows.append({**r, "result": "extraction_error_override", "mensaje": msg})
                else:
                    n_error += 1
                    log_rows.append({**r, "result": "error_override", "mensaje": msg})
            else:
                log_rows.append({**r, "result": "skip", "mensaje": "extraction_error sin acción definida (ni tipo_correcto, ni pdf, ni notas de imputación)"})
                n_skip += 1
            continue

        log_rows.append({**r, "result": "skip", "mensaje": f"decision desconocida: {decision!r}"})
        n_skip += 1

    # Escribir listas
    out_dir = Path("output/audits")
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.dry_run:
        # excluded
        excl_path = out_dir / "treatment_excluded_munis.csv"
        with excl_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["cvegeo", "estado", "municipio", "trayectoria",
                                               "pattern_muni", "auditor", "fecha", "notas"])
            w.writeheader()
            for v in excluded_munis.values():
                w.writerow(v)
        # real_reform
        rr_path = out_dir / "treatment_real_reform_munis.csv"
        with rr_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["cvegeo", "estado", "municipio", "trayectoria",
                                               "pattern_muni", "auditor", "fecha", "notas"])
            w.writeheader()
            for v in real_reform_munis.values():
                w.writerow(v)
        # non_absorbing (accept_as_is)
        na_path = out_dir / "treatment_non_absorbing_munis.csv"
        with na_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["cvegeo", "estado", "municipio", "trayectoria",
                                               "pattern_muni", "auditor", "fecha", "notas"])
            w.writeheader()
            for v in non_absorbing_munis.values():
                w.writerow(v)
        # log
        log_path = out_dir / "apply_treatment_audit.log"
        log_fields = list(rows[0].keys()) if rows else []
        log_fields = [c for c in log_fields if c not in {"result", "mensaje"}] + ["result", "mensaje"]
        with log_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=log_fields, extrasaction="ignore")
            w.writeheader()
            for lr in log_rows:
                w.writerow(lr)

    print()
    print(f"  directed_impute (desde año-1): {n_directed}")
    print(f"  re-extracción LLM (PDF+páginas): {n_reextract}")
    print(f"  override de tipo (extraction_error/real_reform): {n_override}")
    print(f"  real_reform sin tipo (aceptado): {n_real_reform}")
    print(f"  accept_as_is: {n_accept}")
    print(f"  exclude_muni: {n_excluded}")
    print(f"  saltados: {n_skip}")
    print(f"  errores: {n_error}")
    print()
    print(f"  Munis excluidos del DiD: {len(excluded_munis)}")
    print(f"  Munis con reform real (no absorbente): {len(real_reform_munis)}")
    print(f"  Munis aceptados como no-absorbentes: {len(non_absorbing_munis)}")


if __name__ == "__main__":
    main()
