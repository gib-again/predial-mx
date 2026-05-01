#!/usr/bin/env python3
"""
Calibración: corre segment+extract sólo sobre los 5 PDFs de Oaxaca 2018
re-OCR'd con la nueva limpieza de watermark, para comparar la calidad
de extracción contra la baseline (que usaba OCR sin limpieza + fallback
a pdf_vision).

Aislamiento para no contaminar el pipeline real:

  1. Re-segmenta los 5 PDFs reusando la lógica de segment.py.
     Sobrescribe focus_predial/2018/OAX_PREDIAL_2018_{slug}.{txt,pdf}
     SOLAMENTE para los slugs presentes en estos 5 PDFs (8 leyes en
     la corrida actual).

  2. Copia los focus producidos a un directorio aislado:
       data/oaxaca/_calibration/focus_predial/2018/
     Esto evita que extract_all() barra todo focus_predial y dispare
     llamadas LLM para munis no relacionados.

  3. Llama extract_all() apuntando a ese focus aislado y a un
     json_dir aislado:
       data/oaxaca/_calibration/json_predial/
     Los json reales (json_predial/2018/) NO se tocan.

  4. Reporta cada slug con (baseline JSON path, nuevo JSON path) y
     un resumen de diferencias clave (tipo_esquema, # tarifas).

Uso:
    python -m scripts.calibrate_oaxaca_2018
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import fitz  # PyMuPDF

from src.core.llm_extract import extract_all
from src.estados import get_adapter
from src.estados.oaxaca import config
from src.estados.oaxaca.segment import (
    _detect_skip_pages,
    _load_index_map,
    _lookup_index_rows,
    _merge_ocr_and_index,
    _resolve_best_pdf,
    _sanitize_page_range,
    extract_predial_section,
    find_leyes_in_pdf,
)

PDF_STEMS = [
    "EXT-DEC804-2018-01-03",
    "SEC04-08VA-2018-01-27",
    "SEC04-09NA-2018-01-27",
    "SEC04-10MA-2018-01-27",
    "SEC04-11RA-2018-01-27",
]

CALIB_ROOT = Path("data/oaxaca/_calibration")
CALIB_FOCUS = CALIB_ROOT / "focus_predial"
CALIB_JSON = CALIB_ROOT / "json_predial"


def _segment_one(
    raw_pdf: Path,
    pdf_raw_dir: Path,
    pdf_ocr_dir: Path,
    focus_dir: Path,
    index_by_rel: dict,
    index_by_name: dict,
) -> list[tuple[int, str, Path]]:
    """Reusa los helpers de segment.py para un solo PDF."""
    best_pdf = _resolve_best_pdf(raw_pdf, pdf_ocr_dir, pdf_raw_dir)
    relative = raw_pdf.relative_to(pdf_raw_dir)
    pub_year = int(relative.parts[0])

    print(f"\n  ── {raw_pdf.name} (best={best_pdf.name})")

    doc = fitz.open(str(best_pdf))
    try:
        skip_n = _detect_skip_pages(doc)
        index_rows = _lookup_index_rows(raw_pdf, pdf_raw_dir, index_by_rel, index_by_name)
        leyes_ocr = find_leyes_in_pdf(doc, best_pdf, skip_pages=skip_n, default_ejercicio=pub_year)
        leyes = _merge_ocr_and_index(
            leyes_ocr, index_rows, best_pdf, len(doc), default_ejercicio=pub_year
        )

        if not leyes:
            print(f"    {best_pdf.name}: 0 leyes detectadas")
            return []

        print(
            f"    skip={skip_n}pp, leyes_ocr={len(leyes_ocr)}, "
            f"index_rows={len(index_rows)}, merged={len(leyes)}"
        )

        produced: list[tuple[int, str, Path]] = []
        for ley in leyes:
            ej = ley.ejercicio or pub_year
            year_out = focus_dir / str(ej)
            year_out.mkdir(parents=True, exist_ok=True)

            txt_path = year_out / f"{config.PREFIJO}_PREDIAL_{ej}_{ley.slug}.txt"
            pdf_out = year_out / f"{config.PREFIJO}_PREDIAL_{ej}_{ley.slug}.pdf"

            seccion = extract_predial_section(doc, ley)
            p_start, p_end = _sanitize_page_range(
                seccion.page_start, seccion.page_end, len(doc), upper_bound=ley.page_end
            )
            seccion.page_start = p_start
            seccion.page_end = p_end

            method = seccion.method
            tag = "fallback" if method.startswith("fallback") else "exact"

            header = (
                f"# Municipio: {ley.municipio}\n"
                f"# Distrito: {ley.distrito}\n"
                f"# Estado: Oaxaca\n"
                f"# Ejercicio: {ej}\n"
                f"# Decreto: {ley.decreto}\n"
                f"# Fuente: {best_pdf.name}\n"
                f"# Páginas ley: {ley.page_start + 1}-{ley.page_end}\n"
                f"# Páginas predial: {seccion.page_start + 1}-{seccion.page_end}\n"
                f"# Método detección: {method}\n\n"
            )
            txt_content = header + seccion.text
            txt_path.write_text(txt_content, encoding="utf-8")

            try:
                out_doc = fitz.open()
                for p in range(seccion.page_start, seccion.page_end):
                    if 0 <= p < len(doc):
                        out_doc.insert_pdf(doc, from_page=p, to_page=p)
                out_doc.save(str(pdf_out))
                out_doc.close()
            except Exception as e:
                print(f"      {ley.slug}: error guardando PDF: {e}")

            print(
                f"      {ley.slug:48s} {tag:8s} pp{seccion.page_start + 1}-{seccion.page_end} "
                f"{len(txt_content)} chars"
            )
            produced.append((ej, ley.slug, txt_path))
        return produced
    finally:
        doc.close()


def _stage_calibration(
    produced: list[tuple[int, str, Path]],
    focus_dir: Path,
):
    """
    Copia los focus_predial producidos a CALIB_FOCUS, dejando todo lo
    demás fuera para que extract_all sólo vea estos.
    """
    if CALIB_FOCUS.exists():
        shutil.rmtree(CALIB_FOCUS)
    CALIB_FOCUS.mkdir(parents=True, exist_ok=True)

    staged = 0
    for ej, slug, txt_path in produced:
        target_year = CALIB_FOCUS / str(ej)
        target_year.mkdir(parents=True, exist_ok=True)
        for ext in (".txt", ".pdf"):
            src = focus_dir / str(ej) / f"{config.PREFIJO}_PREDIAL_{ej}_{slug}{ext}"
            if src.exists():
                shutil.copy2(src, target_year / src.name)
                staged += 1
    print(f"  Stage: {staged} archivos copiados a {CALIB_FOCUS}")


def _summarize_json(p: Path) -> dict:
    """Resumen mínimo para comparar."""
    if not p.exists():
        return {"exists": False}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return {"exists": True, "valid_json": False, "error": str(e)}
    meta = d.get("_meta", {}) or {}
    tarifas = d.get("tarifas") or d.get("tabla_tarifas") or d.get("rangos") or []
    if not isinstance(tarifas, list):
        tarifas = []
    return {
        "exists": True,
        "valid_json": True,
        "tipo_esquema": d.get("tipo_esquema"),
        "fuente": meta.get("fuente"),
        "modelo": meta.get("modelo"),
        "n_tarifas": len(tarifas),
        "ejercicio": d.get("ejercicio"),
        "municipio": d.get("municipio"),
    }


def main():
    adapter = get_adapter("oaxaca")
    pdf_raw_dir = adapter.pdf_raw_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    focus_dir = adapter.focus_dir
    real_json_dir = adapter.json_dir
    meta_dir = adapter.meta_dir

    raw_pdfs: list[Path] = []
    for stem in PDF_STEMS:
        candidates = list(pdf_raw_dir.rglob(f"{stem}.pdf")) + list(
            pdf_raw_dir.rglob(f"{stem}.PDF")
        )
        if not candidates:
            print(f"  [WARN] no se encontró raw para {stem}")
            continue
        raw_pdfs.append(candidates[0])

    if not raw_pdfs:
        print("[ERROR] no hay PDFs para procesar.")
        return

    index_by_rel, index_by_name = _load_index_map(meta_dir)

    print("═══ Calibración Oaxaca 2018 — segment ═══")
    print(f"  PDFs: {len(raw_pdfs)}")

    all_produced: list[tuple[int, str, Path]] = []
    for raw_pdf in raw_pdfs:
        all_produced.extend(
            _segment_one(
                raw_pdf, pdf_raw_dir, pdf_ocr_dir, focus_dir, index_by_rel, index_by_name
            )
        )

    if not all_produced:
        print("\n[ERROR] segment no produjo ningún focus_predial.")
        return
    print(f"\n  Total leyes segmentadas: {len(all_produced)}")

    print("\n═══ Stage focus aislado (calibración) ═══")
    _stage_calibration(all_produced, focus_dir)

    print("\n═══ Calibración Oaxaca 2018 — extract (aislado) ═══")
    print(f"  txt_dir: {CALIB_FOCUS}")
    print(f"  json_dir: {CALIB_JSON}")
    extract_all(
        txt_dir=CALIB_FOCUS,
        json_dir=CALIB_JSON,
        prefijo=config.PREFIJO,
        estado_nombre=config.ESTADO_NOMBRE,
        batch_mode=False,
        adapter=adapter,
        pdf_fallback=True,
    )

    print("\n═══ Comparativa baseline vs nuevo ═══")
    print(f"  {'slug':50s} {'src':10s} {'esq_old':14s} {'esq_new':14s} "
          f"{'old_n':>6s} {'new_n':>6s}")
    print(f"  {'-'*50} {'-'*10} {'-'*14} {'-'*14} {'-'*6} {'-'*6}")
    for ej, slug, _ in all_produced:
        baseline = real_json_dir / str(ej) / f"{config.PREFIJO}_PREDIAL_{ej}_{slug}.baseline.json"
        new_json = CALIB_JSON / str(ej) / f"{config.PREFIJO}_PREDIAL_{ej}_{slug}.json"
        old = _summarize_json(baseline)
        new = _summarize_json(new_json)
        src = (new.get("fuente") or "—")[:10]
        esq_old = (old.get("tipo_esquema") or "—")[:14]
        esq_new = (new.get("tipo_esquema") or "—")[:14]
        old_n = old.get("n_tarifas", "—")
        new_n = new.get("n_tarifas", "—")
        print(f"  {slug:50s} {src:10s} {esq_old:14s} {esq_new:14s} {old_n:>6} {new_n:>6}")


if __name__ == "__main__":
    main()
