"""
Segmentación de secciones de predial de Jalisco.

Migrado de:
  - 50_predial_locate_sections.py  → locate_predial (heurísticas por página)
  - 60_pdf_trim_txt.py             → extract_sections (recorta PDF + TXT)
  - 65_re_delimited.py             → re_delimit (expande ventana para inválidos)

Diferencias clave con Coahuila:
  - Jalisco trabaja por PÁGINA (no por offsets de carácter)
  - Los PDFs de Jalisco son individuales por municipio-año (no tomos compartidos)
  - Se necesita heurística especial: SECCION + "predial" + "articulo" en misma página
  - Prioridad de PDFs: _forceocr > _ocr > original
"""

import csv
import re
from pathlib import Path

import fitz  # PyMuPDF — ~5-10x faster than pdfplumber for text extraction
from unidecode import unidecode

from src.core.muni_matcher import MuniMatcher
from src.estados.jalisco.config import (
    BLACKLIST_HEADER_PATTERNS,
    CVE_ENT,
    NEXT_TAX_PATTERNS,
)

# Matcher unificado de municipios INEGI
_matcher = MuniMatcher(cve_ent=CVE_ENT)


# ══════════════════════════════════════════════════════════════
# Utilidades de texto (específicas de Jalisco, normalizan por línea)
# ══════════════════════════════════════════════════════════════

def _normalize_text(s: str) -> str:
    s = s or ""
    s = unidecode(s.lower())
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _split_lines_normalized(s: str) -> list[str]:
    if not s:
        return []
    return [ln for ln in (_normalize_text(line) for line in s.splitlines()) if ln]


def _page_candidate_paths(raw_path: Path, ocr_dir: Path) -> list[Path]:
    """
    Devuelve PDFs candidatos en orden de prioridad: forceocr > ocr > original.
    OCR files live in pdf_ocr/, not alongside raw.
    """
    stem = raw_path.stem
    # Derive año from parent directory name (e.g., pdf_raw/2011/)
    anio = raw_path.parent.name
    candidates = [
        ocr_dir / anio / f"{stem}_forceocr.pdf",
        ocr_dir / anio / f"{stem}_ocr.pdf",
        raw_path,
    ]
    return [p for p in dict.fromkeys(candidates) if p.exists()]


# ══════════════════════════════════════════════════════════════
# Heurísticas de localización (específicas de Jalisco)
# ══════════════════════════════════════════════════════════════

def _detect_next_tax_header(lines: list[str]):
    """Detecta si la página contiene encabezado del siguiente impuesto."""
    for idx, ln in enumerate(lines):
        if len(ln) > 120:
            continue
        for pat, label in NEXT_TAX_PATTERNS:
            if re.search(pat, ln):
                starts_header = ln.startswith("del impuesto") or ln.startswith("de los impuestos")
                has_context = False
                if idx > 0:
                    prev = lines[idx - 1]
                    if any(w in prev for w in ("capitulo", "seccion")):
                        has_context = True
                if starts_header or has_context:
                    return True, label
    return False, None


def _detect_blacklisted_page(lines: list[str]) -> bool:
    """True si la página está en contexto que NO es inicio de predial."""
    for i, ln in enumerate(lines):
        if i >= 8:
            break
        for pat in BLACKLIST_HEADER_PATTERNS:
            if re.search(pat, ln):
                return True
    return False


def _is_seccion_line_for_predial(line: str) -> bool:
    if "seccion" not in line:
        return False
    if any(w in line for w in ("primera", "segunda", "unica", "unico")):
        return True
    if re.search(r"seccion\s+([ivxlcdm]+|\d+|\b[a-z]\b|\|)", line):
        return True
    return False


def _is_predial_header_candidate(line: str) -> str | None:
    if re.search(r"\bdel\s+impuesto\s+pred[ia]al\b", line):
        return "del_impuesto"
    if "predial" in line and "impuesto" not in line and len(line) <= 30:
        return "predial_solo"
    return None


def _find_predial_core_page(pages_lines: list[list[str]]) -> int | None:
    """
    Busca la primera página con encabezado de predial en contexto jurídico válido.

    Condiciones: SECCION + "del impuesto predial" + "articulo" en misma página o siguiente.
    """
    n_pages = len(pages_lines)

    for p in range(n_pages):
        lines = pages_lines[p]
        if not lines:
            continue

        if _detect_blacklisted_page(lines):
            continue

        has_patrimonio = any(
            "impuestos sobre el patrimonio" in ln or "impuesto sobre el patrimonio" in ln
            for ln in lines
        )
        has_capitulo = any("capitulo" in ln for ln in lines)
        has_impuestos = any("impuestos" in ln or "impuesto" in ln for ln in lines)
        articulo_here = any("articulo" in ln for ln in lines)
        articulo_next = (p + 1 < n_pages and any("articulo" in ln for ln in pages_lines[p + 1]))

        for i, ln in enumerate(lines):
            header_type = _is_predial_header_candidate(ln)
            if header_type is None:
                continue

            j0 = max(0, i - 5)
            context_prev = lines[j0:i]
            has_seccion_prev = any(_is_seccion_line_for_predial(cl) for cl in context_prev)
            has_capitulo_prev = any("capitulo" in cl for cl in context_prev)
            has_impuestos_prev = any("impuestos" in cl or "impuesto" in cl for cl in context_prev)

            ok = False
            if header_type == "predial_solo":
                if has_seccion_prev:
                    ok = True
            elif header_type == "del_impuesto":
                if has_seccion_prev:
                    ok = True
                elif has_patrimonio:
                    ok = True
                elif (has_capitulo_prev or has_capitulo) and (has_impuestos_prev or has_impuestos):
                    ok = True

            if not ok:
                continue
            if not (articulo_here or articulo_next):
                continue

            return p

    return None


def _analyze_pdf_for_predial(pdf_path: Path) -> dict:
    """Analiza un PDF y localiza la sección de predial (1-based pages)."""
    pages_lines = []

    with fitz.open(pdf_path) as doc:
        for page in doc:
            text = page.get_text("text") or ""
            pages_lines.append(_split_lines_normalized(text))

    n_pages = len(pages_lines)
    if n_pages == 0:
        return {"n_pages": 0, "predial_page_start": None, "predial_page_end": None,
                "page_start_next_tax": None, "next_tax_label": None, "forced_end": False}

    page_core = _find_predial_core_page(pages_lines)
    if page_core is None:
        return {"n_pages": n_pages, "predial_page_start": None, "predial_page_end": None,
                "page_start_next_tax": None, "next_tax_label": None, "forced_end": False}

    # Buscar fin: siguiente impuesto
    page_start_next_tax = None
    next_tax_label = None
    for j in range(page_core + 1, n_pages):
        found, label = _detect_next_tax_header(pages_lines[j])
        if found:
            page_start_next_tax = j
            next_tax_label = label
            break

    forced_end = False
    if page_start_next_tax is not None:
        page_end = max(page_core, page_start_next_tax - 1)
    else:
        forced_end = True
        page_end = min(n_pages - 1, page_core + 4)

    return {
        "n_pages": n_pages,
        "predial_page_start": page_core + 1,       # 1-based
        "predial_page_end": page_end + 1,           # 1-based
        "page_start_next_tax": (page_start_next_tax + 1) if page_start_next_tax is not None else None,
        "next_tax_label": next_tax_label,
        "forced_end": forced_end,
    }


# ══════════════════════════════════════════════════════════════
# PASO 1: locate_predial (script 50)
# ══════════════════════════════════════════════════════════════

def run_locate_sections(adapter) -> Path:
    """
    Localiza la sección de predial en cada PDF y genera un CSV bitácora.
    """
    meta_dir = adapter.meta_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    downloads_csv = meta_dir / "ingresos_downloads.csv"
    sections_csv = meta_dir / "segment.csv"

    if not downloads_csv.exists():
        raise FileNotFoundError(f"No existe {downloads_csv}")

    with downloads_csv.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        dl_rows = [r for r in reader if r.get("status") in ("ok", "already_exists")]

    print(f"  {len(dl_rows)} PDFs para analizar.")

    rows_out = []
    for i, row in enumerate(dl_rows, 1):
        municipio = row["municipio"]
        anio = int(row["anio"])
        raw_path = Path(row["file_local"])

        if i % 25 == 0 or i == len(dl_rows):
            print(f"    [{i}/{len(dl_rows)}] procesando...")

        candidates = _page_candidate_paths(raw_path, pdf_ocr_dir)
        if not candidates:
            rows_out.append({"municipio": municipio, "anio": anio, "pdf_used": "",
                             "n_pages": 0, "predial_page_start": None,
                             "predial_page_end": None, "page_start_next_tax": None,
                             "next_tax_label": None, "forced_end": False})
            continue

        pdf_used = candidates[0]
        try:
            info = _analyze_pdf_for_predial(pdf_used)
        except Exception as e:
            print(f"    [ERROR] {municipio} {anio}: {e}")
            info = {"n_pages": 0, "predial_page_start": None, "predial_page_end": None,
                    "page_start_next_tax": None, "next_tax_label": None, "forced_end": False}

        rows_out.append({"municipio": municipio, "anio": anio, "pdf_used": str(pdf_used), **info})

    fieldnames = ["municipio", "anio", "pdf_used", "n_pages",
                  "predial_page_start", "predial_page_end",
                  "page_start_next_tax", "next_tax_label", "forced_end"]
    with sections_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_out)

    found = sum(1 for r in rows_out if r["predial_page_start"] is not None)
    print(f"  Secciones localizadas: {found}/{len(rows_out)} → {sections_csv}")
    return sections_csv


# ══════════════════════════════════════════════════════════════
# PASO 2: extract_sections (script 60)
# ══════════════════════════════════════════════════════════════

def _extract_section_to_pdf_and_txt(
    pdf_path: Path, start_page: int, end_page: int,
    out_pdf: Path, out_txt: Path,
):
    """Recorta páginas y extrae texto usando PyMuPDF."""
    with fitz.open(pdf_path) as doc:
        n_pages = doc.page_count
        start_idx = max(0, start_page - 1)
        end_idx = min(end_page - 1, n_pages - 1)
        if start_idx > end_idx:
            start_idx = end_idx

        # PDF recortado
        out_pdf.parent.mkdir(parents=True, exist_ok=True)
        new_doc = fitz.open()
        new_doc.insert_pdf(doc, from_page=start_idx, to_page=end_idx)
        new_doc.save(str(out_pdf), deflate=True)
        new_doc.close()

        # TXT
        texts = [doc[i].get_text("text") or "" for i in range(start_idx, end_idx + 1)]

    full_text = "\n\n" + ("\n\n" + "-" * 40 + "\n\n").join(texts) + "\n\n"
    out_txt.parent.mkdir(parents=True, exist_ok=True)
    out_txt.write_text(full_text, encoding="utf-8")


def run_extract_sections(adapter) -> Path:
    """
    Recorta PDF + extrae TXT para cada sección de predial localizada.
    """
    meta_dir = adapter.meta_dir
    focus_dir = adapter.focus_dir
    prefijo = adapter.prefijo

    sections_csv = meta_dir / "segment.csv"
    if not sections_csv.exists():
        raise FileNotFoundError(f"No existe {sections_csv}. Ejecuta 'master' primero.")

    with sections_csv.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [r for r in reader if r.get("predial_page_start")]

    print(f"  {len(rows)} secciones para extraer.")

    ok_count = 0
    for row in rows:
        municipio = row["municipio"]
        anio = int(row["anio"])
        pdf_used = Path(row["pdf_used"])
        start = int(float(row["predial_page_start"]))
        end = int(float(row["predial_page_end"]))
        forced_end = str(row.get("forced_end", "")).strip().lower() in ("true", "1", "yes")

        # Heurística: si el rango es muy estrecho (≤2 páginas) o forced_end,
        # es probable que predial_page_start esté adelantado respecto al inicio
        # real de la sección. Incorporamos 5 páginas extra hacia atrás y dejamos
        # que el LLM interprete el contenido relevante.
        page_span = end - start + 1
        if forced_end or page_span <= 2:
            start = max(1, start - 5)

        mun_slug = _matcher.match(municipio).slug
        out_pdf = focus_dir / str(anio) / f"{prefijo}_PREDIAL_{anio}_{mun_slug}.pdf"
        out_txt = focus_dir / str(anio) / f"{prefijo}_PREDIAL_{anio}_{mun_slug}.txt"

        try:
            _extract_section_to_pdf_and_txt(pdf_used, start, end, out_pdf, out_txt)
            ok_count += 1
        except Exception as e:
            print(f"    [ERROR] {municipio} {anio}: {e}")

    print(f"  Extraídas: {ok_count}/{len(rows)}")
    return sections_csv
