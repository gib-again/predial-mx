"""Re-OCR full + re-segmentación para casos P-02 del HITL.

Problema P-02: el OCR del `pdf_raw` de Guanajuato está dañado tras las primeras
páginas (PyMuPDF lee del OCR layer roto y devuelve texto vacío/mojibake). El
segment original capturó páginas usando ese texto roto, así que el
`focus_predial.pdf` recortado no contiene la tabla de tarifas. La cascada
re-OCR/vision actual (Fase 1) opera sobre ese focus_predial y arrastra el
mismo contenido equivocado.

Solución: correr `ocrmypdf --force-ocr` sobre el `pdf_raw` original para
generar una versión con OCR limpio (`pdf_ocr_full/<nombre>.pdf`), luego
re-segmentar usando ese nuevo PDF y reescribir el `focus_predial`.

Pipeline:
  1. Mapear muni-años P-02 → pdf_raw via `segment.csv`
  2. Para cada pdf_raw único, correr ocrmypdf si no existe ya el output
  3. Para cada muni-año P-02, re-segmentar con el OCR limpio aplicando
     `find_predial_in_window` con las páginas del segment.csv
  4. Sobreescribir `focus_predial/<año>/<archivo>.{txt,pdf}`

Después de este script, correr scripts/reprocess_municipios.py --from-bitacora
--patron P-02 para re-extraer (la cascada ampliada de Fase 1 ya activará
re-OCR/vision si hace falta).

Uso:
    python -m scripts.reocr_and_resegment           # solo guanajuato
    python -m scripts.reocr_and_resegment --dry-run # mostrar plan sin ejecutar
"""
from __future__ import annotations

import argparse
import csv
import shutil
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from src.core.pdf_utils import build_text_and_offsets, idx_to_page, save_pdf_slice
from src.core.text_utils import norm
from src.extraction.bitacora_parser import parse_bitacora

ROOT = Path(__file__).resolve().parents[1]
BITACORA_PATH = ROOT / "docs" / "HITL_BITACORA.md"


def _segment_csv_lookup(estado: str) -> dict[tuple[int, str], dict]:
    """Returns {(anio, slug): row} from data/{estado}/meta/segment.csv."""
    p = ROOT / "data" / estado / "meta" / "segment.csv"
    if not p.exists():
        return {}
    out: dict[tuple[int, str], dict] = {}
    with p.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                anio = int(r["ejercicio"])
            except (KeyError, ValueError):
                continue
            slug = (r.get("slug") or "").strip()
            if slug:
                out[(anio, slug)] = r
    return out


def _resolve_pdf_path(estado: str, source_pdf: str) -> Path | None:
    """Localiza el pdf_raw real. Si segment apunta a `<base>_ocr.pdf` que no
    existe, prueba `<base>.pdf` en pdf_raw. Si tampoco, busca por glob."""
    raw_dir = ROOT / "data" / estado / "pdf_raw"
    ocr_dir = ROOT / "data" / estado / "pdf_ocr"

    # 1. Direct hit en pdf_ocr
    for d in (ocr_dir, raw_dir):
        for hit in d.rglob(source_pdf):
            return hit

    # 2. Si tiene sufijo _ocr, probar sin él
    if source_pdf.endswith("_ocr.pdf"):
        base = source_pdf[:-8] + ".pdf"
        for d in (raw_dir, ocr_dir):
            for hit in d.rglob(base):
                return hit

    return None


def _run_ocrmypdf(input_pdf: Path, output_pdf: Path, language: str = "spa+eng") -> bool:
    """Corre ocrmypdf --force-ocr. Retorna True si éxito.

    Si falla por DigitalSignatureError, reintenta con
    --invalidate-digital-signatures.
    """
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    base_cmd = [
        "ocrmypdf",
        "--force-ocr",                # re-OCR aunque ya tenga texto
        "--output-type", "pdf",       # más rápido que pdfa
        "--language", language,
        "--jobs", "4",                # paralelizar
        "--quiet",
    ]
    print(f"    ocrmypdf {input_pdf.name} → {output_pdf.relative_to(ROOT)}", flush=True)

    for attempt, extra_flags in enumerate(([], ["--invalidate-digital-signatures"]), 1):
        cmd = base_cmd + extra_flags + [str(input_pdf), str(output_pdf)]
        t0 = time.time()
        try:
            subprocess.run(cmd, check=True, timeout=900,
                           capture_output=True, text=True, encoding="utf-8")
            tag = " (sig invalidated)" if extra_flags else ""
            print(f"      OK ({time.time()-t0:.1f}s){tag}")
            return True
        except subprocess.TimeoutExpired:
            print(f"      TIMEOUT después de 900s")
            return False
        except subprocess.CalledProcessError as e:
            stderr = (e.stderr or "")
            if attempt == 1 and "DigitalSignature" in stderr:
                print(f"      retry con --invalidate-digital-signatures...")
                continue
            print(f"      FAIL: {e.returncode}")
            if stderr:
                print(f"      stderr: {stderr[:300]}")
            return False
    return False


def _resegment_guanajuato(
    anio: int, slug: str, new_pdf_path: Path, seg_row: dict,
) -> tuple[bool, str]:
    """Re-segment usando guanajuato.segment.extract_predial_section.

    extract_predial_section(doc, ley) opera sobre páginas y devuelve
    SeccionPredial con texto + page_start/page_end.
    """
    import fitz
    from src.estados.guanajuato.segment import LeyMunicipal, extract_predial_section

    try:
        p_start_ley = int(seg_row.get("ley_page_start") or 0) - 1  # 1-based → 0-based
        p_end_ley = int(seg_row.get("ley_page_end") or 0)         # 1-based, exclusive
    except ValueError:
        return (False, "ley_page_start/end inválidos")

    if p_start_ley < 0 or p_end_ley <= p_start_ley:
        return (False, f"rango ley inválido: {p_start_ley}-{p_end_ley}")

    try:
        doc = fitz.open(new_pdf_path)
    except Exception as e:
        return (False, f"fitz.open falló: {e}")

    if p_end_ley > doc.page_count:
        p_end_ley = doc.page_count

    ley = LeyMunicipal(
        municipio=seg_row.get("municipio", "") or slug.replace("_", " ").title(),
        slug=slug,
        cve_mun=seg_row.get("cve_mun", "") or "",
        decreto=seg_row.get("decreto", "") or "",
        ejercicio=anio,
        page_start=p_start_ley,
        page_end=p_end_ley,
        pdf_path=new_pdf_path,
    )

    try:
        seccion = extract_predial_section(doc, ley)
    except Exception as e:
        doc.close()
        return (False, f"extract_predial_section falló: {e}")

    if not seccion.found or not seccion.text:
        doc.close()
        return (False, "sección no encontrada")

    # Output paths
    name = f"GTO_PREDIAL_{anio}_{slug}"
    focus_dir = ROOT / "data" / "guanajuato" / "focus_predial" / str(anio)
    focus_dir.mkdir(parents=True, exist_ok=True)
    txt_path = focus_dir / f"{name}.txt"
    pdf_path_out = focus_dir / f"{name}.pdf"

    # Backup del actual (si existe) en focus_predial_backup_pre_reocr/
    backup_dir = ROOT / "data" / "guanajuato" / "focus_predial_backup_pre_reocr" / str(anio)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if txt_path.exists() and not (backup_dir / txt_path.name).exists():
        shutil.copy2(txt_path, backup_dir / txt_path.name)
    if pdf_path_out.exists() and not (backup_dir / pdf_path_out.name).exists():
        shutil.copy2(pdf_path_out, backup_dir / pdf_path_out.name)

    # Escribir TXT y PDF nuevos
    txt_path.write_text(seccion.text, encoding="utf-8")
    # save_pdf_slice usa páginas 1-based (inclusive). seccion.page_start/end
    # son 0-based; page_end exclusive.
    p_start_1b = seccion.page_start + 1
    p_end_1b = seccion.page_end  # convertir 0-based exclusive a 1-based inclusive
    if p_end_1b < p_start_1b:
        p_end_1b = p_start_1b
    doc.close()
    save_pdf_slice(new_pdf_path, p_start_1b, p_end_1b, pdf_path_out)

    return (True, f"resegmentado pg {p_start_1b}-{p_end_1b} ({len(seccion.text)} chars, method={seccion.method})")


def _resegment_coahuila(
    anio: int, slug: str, new_pdf_path: Path, seg_row: dict,
) -> tuple[bool, str]:
    """Re-segment para coahuila usando find_predial_in_window."""
    from src.estados.coahuila.segment import find_predial_in_window

    try:
        raw_text, page_starts = build_text_and_offsets(new_pdf_path)
    except Exception as e:
        return (False, f"build_text falló: {e}")
    norm_text = norm(raw_text)
    n_pages = len(page_starts)

    try:
        p_start_ley = int(seg_row.get("ley_page_start") or 0)
        p_end_ley = int(seg_row.get("ley_page_end") or 0)
    except ValueError:
        return (False, "ley_page_start/end inválidos")

    if p_start_ley <= 0 or p_end_ley < p_start_ley:
        law_start, law_end = 0, len(norm_text)
    else:
        if p_start_ley > n_pages:
            return (False, f"ley_page_start={p_start_ley} > n_pages={n_pages}")
        law_start = page_starts[p_start_ley - 1]
        law_end = page_starts[p_end_ley] if p_end_ley < n_pages else len(norm_text)

    span = find_predial_in_window(norm_text, law_start, law_end)
    if not span:
        span = find_predial_in_window(norm_text, 0, len(norm_text))
    if not span:
        return (False, "find_predial_in_window no encontró sección")

    start_idx, end_idx = span
    p_start_pred = idx_to_page(start_idx, page_starts)
    p_end_pred = idx_to_page(end_idx - 1, page_starts)

    name = f"COAH_PREDIAL_{anio}_{slug}"
    focus_dir = ROOT / "data" / "coahuila" / "focus_predial" / str(anio)
    focus_dir.mkdir(parents=True, exist_ok=True)
    txt_path = focus_dir / f"{name}.txt"
    pdf_path_out = focus_dir / f"{name}.pdf"

    backup_dir = ROOT / "data" / "coahuila" / "focus_predial_backup_pre_reocr" / str(anio)
    backup_dir.mkdir(parents=True, exist_ok=True)
    if txt_path.exists() and not (backup_dir / txt_path.name).exists():
        shutil.copy2(txt_path, backup_dir / txt_path.name)
    if pdf_path_out.exists() and not (backup_dir / pdf_path_out.name).exists():
        shutil.copy2(pdf_path_out, backup_dir / pdf_path_out.name)

    txt_path.write_text(raw_text[start_idx:end_idx], encoding="utf-8")
    save_pdf_slice(new_pdf_path, p_start_pred, p_end_pred, pdf_path_out)

    return (True, f"resegmentado pg {p_start_pred}-{p_end_pred} ({end_idx-start_idx} chars)")


def _resegment_one(
    estado: str, anio: int, slug: str, new_pdf_path: Path, seg_row: dict,
) -> tuple[bool, str]:
    if estado == "guanajuato":
        return _resegment_guanajuato(anio, slug, new_pdf_path, seg_row)
    elif estado == "coahuila":
        return _resegment_coahuila(anio, slug, new_pdf_path, seg_row)
    return (False, f"estado {estado} no soportado")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true",
                    help="Muestra el plan sin ejecutar ocrmypdf ni reescribir")
    ap.add_argument("--skip-ocr", action="store_true",
                    help="Saltar ocrmypdf (asume pdf_ocr_full ya generado), solo re-segmentar")
    ap.add_argument("--patron", default="P-02",
                    help="Patrón HITL a procesar (default: P-02)")
    args = ap.parse_args()

    data = parse_bitacora(BITACORA_PATH)
    casos = data.by_patron(args.patron)
    print(f"[reocr] casos {args.patron}: {len(casos)}")

    # Agrupar por estado
    casos_por_estado: dict[str, list] = defaultdict(list)
    for c in casos:
        casos_por_estado[c.estado].append(c)

    total_resegmented = 0
    total_failed = 0
    total_pdfs_ocrd = 0

    for estado, lista in casos_por_estado.items():
        print(f"\n[{estado}] {len(lista)} casos")

        seg_lookup = _segment_csv_lookup(estado)
        if not seg_lookup:
            print(f"  [skip] sin segment.csv para {estado}")
            continue

        # Mapear casos → segment row + pdf_raw
        muni_to_pdf: dict[tuple[int, str], tuple[dict, Path]] = {}
        pdfs_unicos: dict[Path, Path] = {}  # input → output (en pdf_ocr_full)

        for c in lista:
            key = (c.anio, c.slug)
            seg_row = seg_lookup.get(key)
            if not seg_row:
                print(f"  [skip] {c.slug}/{c.anio}: no en segment.csv")
                continue
            source_pdf = (seg_row.get("source_pdf") or "").strip()
            if not source_pdf:
                continue
            pdf_path = _resolve_pdf_path(estado, source_pdf)
            if not pdf_path or not pdf_path.exists():
                print(f"  [skip] {c.slug}/{c.anio}: pdf_raw no existe ({source_pdf})")
                continue

            # Determinar output del re-OCR
            ocr_full_dir = ROOT / "data" / estado / "pdf_ocr_full"
            # Mantener nombre del source_pdf (con _ocr si lo tenía) en pdf_ocr_full
            out_name = source_pdf
            ocr_full_path = ocr_full_dir / out_name
            pdfs_unicos[pdf_path] = ocr_full_path
            muni_to_pdf[key] = (seg_row, ocr_full_path)

        print(f"  pdf_raw únicos a re-OCR: {len(pdfs_unicos)}")
        print(f"  muni-años a re-segmentar: {len(muni_to_pdf)}")

        if args.dry_run:
            for src, dst in sorted(pdfs_unicos.items()):
                print(f"  [dry] ocr {src.name} → {dst.relative_to(ROOT)}")
            continue

        # Paso 1: re-OCR los PDFs únicos
        if not args.skip_ocr:
            print(f"\n  ── re-OCR {len(pdfs_unicos)} PDFs únicos ──")
            for i, (src, dst) in enumerate(sorted(pdfs_unicos.items()), 1):
                if dst.exists():
                    print(f"  [{i}/{len(pdfs_unicos)}] {src.name} → ya existe, skip")
                    continue
                print(f"  [{i}/{len(pdfs_unicos)}] {src.name}")
                if _run_ocrmypdf(src, dst):
                    total_pdfs_ocrd += 1
                else:
                    print(f"      FALLÓ — quedará sin re-segment")

        # Paso 2: re-segmentar muni-años
        print(f"\n  ── re-segmentar {len(muni_to_pdf)} muni-años ──")
        for (anio, slug), (seg_row, ocr_path) in sorted(muni_to_pdf.items()):
            if not ocr_path.exists():
                print(f"  [skip] {slug}/{anio}: ocr_full no existe")
                total_failed += 1
                continue
            ok, msg = _resegment_one(estado, anio, slug, ocr_path, seg_row)
            status = "OK" if ok else "FAIL"
            print(f"  [{status}] {slug}/{anio}: {msg}")
            if ok:
                total_resegmented += 1
            else:
                total_failed += 1

    print(f"\n{'='*60}")
    print(f"[reocr] PDFs re-OCRd: {total_pdfs_ocrd}")
    print(f"[reocr] muni-años re-segmentados: {total_resegmented}")
    print(f"[reocr] muni-años fallidos: {total_failed}")
    print(f"{'='*60}")
    print("\nSiguiente paso: scripts/reprocess_municipios.py --from-bitacora --patron "
          f"{args.patron}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
