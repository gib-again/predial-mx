"""
Segmentacion de PDFs del PO de Baja California.

Modelo: 1 PDF = 1 ley municipal (una seccion del tomo de fin de anio). Es un
solo nivel de segmentacion, pero el PDF es grande (incluye la Tabla de Valores
Catastrales). La seccion de tasas del impuesto predial vive tipicamente en las
paginas ~15-20, despues de un indice/portada largo.

Estructura real de la ley en BC (verificada con muestras 2025):

  [Pag 1-14]  Portada + INDICE (menciona "Impuesto Predial ... pag 15")  <- evitar
  [Pag 15]    TITULO SEGUNDO / IMPUESTOS / CAPITULO I / IMPUESTO PREDIAL
                ARTICULO 4.- El impuesto predial, se causara ...
                (sobretasas diferenciadas "al millar": industrial, baldios,
                 rusticos; minimo en UMA)                               <- AQUI empieza
  [Pag ~20]   CAPITULO II / IMPUESTO SOBRE ADQUISICION DE INMUEBLES      <- AQUI termina
  [Pag 40+]   Tabla de Valores Catastrales Unitarios (cientos de pp)     <- evitar

La tasa base del predial remite a la Ley de Hacienda Municipal del Estado.

Si existe version OCR'd (escaneos 2010-2022) se prefiere sobre el raw. El OCR
es page-limited (primeras ~55 pp), asi que la seccion predial siempre cae
dentro del PDF OCR'd.

Genera:
  data/bajacalifornia/focus_predial/{ejercicio}/BC_PREDIAL_{ejercicio}_{slug}.txt
  data/bajacalifornia/focus_predial/{ejercicio}/BC_PREDIAL_{ejercicio}_{slug}.pdf
  data/bajacalifornia/meta/predial_master.csv
  data/bajacalifornia/meta/segment.csv
"""

from __future__ import annotations

import csv
import re
from pathlib import Path

import fitz  # PyMuPDF

from src.core.segment_utils import (
    HITL_EXTRA_FIELDS,
    PatternSpec,
    find_predial_section,
    hitl_extra_columns,
)
from src.estados.bajacalifornia import config


# Predial cae tras el indice; el fallback toma una ventana amplia para cubrirlo.
FALLBACK_PAGES = 12


# ═══════════════════════════════════════════════════
# Patrones BC
# ═══════════════════════════════════════════════════

_BC_START_SPECS = [
    # 1) Mas especifico: CAPITULO I + IMPUESTO PREDIAL + ARTICULO N + "se causara/determinara"
    PatternSpec(re.compile(
        r"CAP[IÍ]TULO\s+(?:I|PRIMERO|[UÚ]NICO)\b[\s\S]{0,400}?"
        r"IMPUESTO\s+PREDIAL[\s\S]{0,200}?"
        r"ART[IÍ]CULO\s+\d+",
        re.IGNORECASE,
    ), "capitulo_i_predial_articulo"),

    # 2) ARTICULO N ... "el impuesto predial[,] se causara/determinara"
    PatternSpec(re.compile(
        r"ART[IÍ]CULO\s+\d+[°ºo]?\.?\s*[-–]?\s*[\s\S]{0,60}?"
        r"impuesto\s+predial\s*,?\s*se\s+(?:causar[áa]|determinar[áa]|calcular[áa])",
        re.IGNORECASE,
    ), "articulo_predial_causa"),

    # 3) TITULO SEGUNDO / IMPUESTOS ... IMPUESTO PREDIAL
    PatternSpec(re.compile(
        r"T[IÍ]TULO\s+SEGUNDO\b[\s\S]{0,400}?"
        r"IMPUESTOS?\b[\s\S]{0,400}?"
        r"IMPUESTO\s+PREDIAL\b",
        re.IGNORECASE,
    ), "titulo_segundo_predial"),

    # 4) Generico: encabezado "IMPUESTO PREDIAL" (ultimo recurso, validado por contexto)
    PatternSpec(re.compile(
        r"\bIMPUESTO\s+PREDIAL\b",
        re.IGNORECASE,
    ), "impuesto_predial_generico"),
]

_BC_END_SPECS = [
    # CAPITULO II suele ser ADQUISICION DE INMUEBLES en BC
    PatternSpec(re.compile(
        r"CAP[IÍ]TULO\s+(?:II|SEGUNDO|2)\b[\s\S]{0,200}?"
        r"ADQUISICI[OÓ]N\s+DE\s+(?:BIENES\s+)?INMUEBLES",
        re.IGNORECASE,
    ), "capitulo_ii_adquisicion"),
    PatternSpec(re.compile(
        r"(?:DEL\s+|SOBRE\s+(?:LA\s+)?)?IMPUESTO\s+SOBRE\s+(?:LA\s+)?ADQUISICI[OÓ]N\s+"
        r"DE\s+(?:BIENES\s+)?INMUEBLES",
        re.IGNORECASE,
    ), "adquisicion_inmuebles"),
    PatternSpec(re.compile(
        r"IMPUESTO\s+SOBRE\s+(?:LA\s+)?TRASLACI[OÓ]N\s+DE\s+(?:DOMINIO|INMUEBLES)",
        re.IGNORECASE,
    ), "traslacion_dominio"),
    PatternSpec(re.compile(r"CAP[IÍ]TULO\s+(?:III|TERCERO|3)\b", re.IGNORECASE), "capitulo_iii"),
]

# Bloquear matches cuyo contexto previo sea claramente el indice (TOC).
_BC_BLACKLIST = [
    re.compile(r"[ÍI]NDICE\b", re.IGNORECASE),
    re.compile(r"\.\s*\.\s*\.\s*\.", re.IGNORECASE),  # lineas de puntos del TOC
]


def _bc_context_validator(text: str, match: re.Match, method: str) -> bool:
    """Rechaza matches en zona de portada/indice.

    El indice (pag 1-14) menciona "Impuesto Predial ..... 15" con lineas de
    puntos y numeros de pagina, pero NO el texto del articulo. Exigimos que
    cerca del match aparezca "ARTICULO" (senal de cuerpo normativo) salvo que
    el propio patron ya lo incluya.
    """
    pos = match.start()
    # Rechazar la zona de portada inmediata (sumario/decreto inicial).
    if pos < 800:
        return False
    if method in ("capitulo_i_predial_articulo", "articulo_predial_causa"):
        return True
    # Para patrones genericos, exigir ARTICULO en la ventana cercana.
    window = text[pos:pos + 400]
    return bool(re.search(r"ART[IÍ]CULO\s+\d+", window, re.IGNORECASE))


# ═══════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════

def _iter_pdfs(pdf_raw_dir: Path, year_filter: str | None = None):
    """Itera (ejercicio, pdf_path) en pdf_raw/{anio}/*.pdf."""
    if not pdf_raw_dir.exists():
        return
    for year_dir in sorted(pdf_raw_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        if year_filter and year_dir.name != str(year_filter):
            continue
        try:
            ejercicio = int(year_dir.name)
        except ValueError:
            continue
        for pdf in sorted(year_dir.glob("*.pdf")):
            yield ejercicio, pdf


def _resolve_best_pdf(raw_pdf: Path, pdf_ocr_dir: Path) -> Path:
    """Prefiere la version OCR'd (escaneos) si existe; si no, el raw."""
    year_name = raw_pdf.parent.name
    ocr_path = pdf_ocr_dir / year_name / (raw_pdf.stem + "_ocr.pdf")
    if ocr_path.exists() and ocr_path.stat().st_size > 0:
        return ocr_path
    return raw_pdf


def _slug_from_filename(pdf_path: Path) -> str | None:
    """Extrae slug de BC_RAW_{anio}_{slug}.pdf."""
    stem = pdf_path.stem
    parts = stem.split("_")
    if len(parts) < 4 or parts[0] != config.PREFIJO or parts[1] != "RAW":
        return None
    try:
        int(parts[2])
    except ValueError:
        return None
    return "_".join(parts[3:]) or None


def _build_pages_text(doc: fitz.Document) -> tuple[str, list[tuple[int, int]]]:
    """Concatena texto de todas las paginas + tabla (page_idx, char_offset)."""
    parts: list[str] = []
    offsets: list[tuple[int, int]] = []
    cursor = 0
    for p_idx in range(len(doc)):
        offsets.append((p_idx, cursor))
        text = doc[p_idx].get_text("text") or ""
        parts.append(text)
        cursor += len(text) + 1
    return "\n".join(parts), offsets


def _char_to_page(char_idx: int, offsets: list[tuple[int, int]], n_pages: int) -> int:
    """Mapea indice de char (texto concatenado) a indice de pagina 0-based."""
    page = 0
    for p_idx, start in offsets:
        if start <= char_idx:
            page = p_idx
        else:
            break
    return min(page, n_pages - 1)


def _save_pdf_slice(doc: fitz.Document, page_start: int, page_end: int, out_path: Path) -> None:
    """Guarda slice [page_start, page_end) en out_path."""
    out_doc = fitz.open()
    try:
        for p in range(page_start, min(page_end, len(doc))):
            out_doc.insert_pdf(doc, from_page=p, to_page=p)
        out_doc.save(str(out_path))
    finally:
        out_doc.close()


def _fallback_predial_page(doc: fitz.Document) -> int:
    """Localiza la primera pagina cuyo cuerpo contiene el impuesto predial.

    Busca "IMPUESTO PREDIAL" cerca de "ARTICULO" (cuerpo normativo, no TOC).
    Devuelve indice 0-based; si no encuentra, 0.
    """
    n = len(doc)
    for p in range(min(n, config.OCR_PAGE_LIMIT)):
        t = (doc[p].get_text("text") or "").upper()
        if "IMPUESTO PREDIAL" in t and re.search(r"ART[IÍ]CULO\s+\d+", t):
            return p
    return 0


# ═══════════════════════════════════════════════════
# Paso "master"
# ═══════════════════════════════════════════════════

_MASTER_FIELDS = ["ejercicio", "slug", "source_pdf", "num_pages"]


def run_build_master(adapter) -> Path:
    """Inventario de PDFs en pdf_raw/. En BC cada PDF = 1 ley municipal."""
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    master_csv = meta_dir / "predial_master.csv"

    rows: list[dict] = []
    for ejercicio, pdf_path in _iter_pdfs(pdf_raw_dir):
        slug = _slug_from_filename(pdf_path)
        if not slug:
            continue
        try:
            with fitz.open(str(pdf_path)) as doc:
                num_pages = len(doc)
        except Exception as e:
            print(f"  [WARN] no se pudo abrir {pdf_path.name}: {e}")
            num_pages = 0
        rows.append({
            "ejercicio": ejercicio, "slug": slug,
            "source_pdf": pdf_path.name, "num_pages": num_pages,
        })

    with master_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_MASTER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Master: {master_csv} ({len(rows)} PDFs inventariados)")
    return master_csv


# ═══════════════════════════════════════════════════
# Paso "segment"
# ═══════════════════════════════════════════════════

_SEGMENT_FIELDS = [
    "ejercicio", "slug", "source_pdf", "focus_file",
    "segment_method", "page_start", "page_end",
    "char_start", "char_end", "txt_chars", "confidence",
    "error_class", "error_detail",
    *[f for f in HITL_EXTRA_FIELDS if f not in {"char_start", "char_end", "confidence"}],
]


def run_extract_sections(adapter, year: str | None = None) -> Path:
    """Para cada PDF, extrae la seccion predial -> TXT + PDF recortado.

    Prefiere la version OCR'd (escaneos 2010-2022) cuando existe.
    """
    pdf_raw_dir = adapter.pdf_raw_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    focus_dir = adapter.focus_dir
    meta_dir = adapter.meta_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    segment_csv = meta_dir / "segment.csv"

    print("=== Baja California: Segmentacion predial ===")
    if year:
        print(f"    Filtro de anio: {year}")

    rows: list[dict] = []
    stats = {"total": 0, "found": 0, "fallback": 0, "errors": 0, "from_ocr": 0}

    for ejercicio, raw_pdf in _iter_pdfs(pdf_raw_dir, year_filter=year):
        slug = _slug_from_filename(raw_pdf)
        if not slug:
            print(f"    [WARN] nombre no parseable: {raw_pdf.name}")
            continue

        pdf_path = _resolve_best_pdf(raw_pdf, pdf_ocr_dir)
        used_ocr = pdf_path != raw_pdf
        if used_ocr:
            stats["from_ocr"] += 1

        stats["total"] += 1
        year_focus = focus_dir / str(ejercicio)
        year_focus.mkdir(parents=True, exist_ok=True)
        txt_out = year_focus / f"{config.PREFIJO}_PREDIAL_{ejercicio}_{slug}.txt"
        pdf_out = year_focus / f"{config.PREFIJO}_PREDIAL_{ejercicio}_{slug}.pdf"

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            print(f"    [ERROR] {pdf_path.name}: no se pudo abrir ({e})")
            stats["errors"] += 1
            rows.append({
                **hitl_extra_columns(),
                "ejercicio": ejercicio, "slug": slug,
                "source_pdf": pdf_path.name, "focus_file": "",
                "segment_method": "", "page_start": "", "page_end": "",
                "char_start": "", "char_end": "", "txt_chars": 0, "confidence": 0,
                "error_class": "open_error", "error_detail": str(e)[:200],
            })
            continue

        try:
            full_text, offsets = _build_pages_text(doc)
            n_pages = len(doc)

            if not full_text.strip():
                print(f"    [WARN] {pdf_path.name}: sin texto extraible (¿escaneado sin OCR?)")
                stats["errors"] += 1
                rows.append({
                    **hitl_extra_columns(),
                    "ejercicio": ejercicio, "slug": slug,
                    "source_pdf": pdf_path.name, "focus_file": "",
                    "segment_method": "", "page_start": "", "page_end": "",
                    "char_start": "", "char_end": "", "txt_chars": 0, "confidence": 0,
                    "error_class": "empty_text", "error_detail": "PDF sin capa de texto",
                })
                continue

            result = find_predial_section(
                text=full_text,
                start_specs=_BC_START_SPECS,
                end_specs=_BC_END_SPECS,
                blacklist_patterns=_BC_BLACKLIST,
                context_validator=_bc_context_validator,
                max_chars=20_000,
                min_chars=300,
                fallback_chars=0,
            )

            if result.found:
                segment_text = full_text[result.start_char:result.end_char].strip()
                p_start = _char_to_page(result.start_char, offsets, n_pages)
                p_end_inclusive = _char_to_page(max(result.end_char - 1, 0), offsets, n_pages)
                p_end = min(p_end_inclusive + 1, n_pages)
                method = result.method
                confidence = result.confidence
                if method.endswith("_unvalidated"):
                    stats["fallback"] += 1
                else:
                    stats["found"] += 1
            else:
                # Fallback por pagina: localizar primera pagina con cuerpo predial.
                p_start = _fallback_predial_page(doc)
                p_end = min(p_start + FALLBACK_PAGES, n_pages)
                fb_chunks = [doc[p].get_text("text") for p in range(p_start, p_end)]
                segment_text = "\n".join(c for c in fb_chunks if c).strip()
                method = f"fallback_{p_end - p_start}pp"
                confidence = 0.3
                stats["fallback"] += 1

            header = (
                f"# Estado: {config.ESTADO_NOMBRE}\n"
                f"# Municipio (slug): {slug}\n"
                f"# Ejercicio: {ejercicio}\n"
                f"# Fuente: {pdf_path.name}\n"
                f"# Paginas predial: {p_start + 1}-{p_end}\n"
                f"# Metodo deteccion: {method}\n"
                f"# Confianza: {confidence:.2f}\n\n"
            )
            txt_out.write_text(header + segment_text, encoding="utf-8")

            try:
                _save_pdf_slice(doc, p_start, p_end, pdf_out)
            except Exception as e:
                print(f"    [WARN] {pdf_path.name}: no se pudo guardar PDF slice ({e})")

            rows.append({
                **hitl_extra_columns(result if result.found else None),
                "ejercicio": ejercicio, "slug": slug,
                "source_pdf": pdf_path.name, "focus_file": txt_out.name,
                "segment_method": method,
                "page_start": p_start + 1, "page_end": p_end,
                "char_start": result.start_char if result.found else "",
                "char_end": result.end_char if result.found else "",
                "txt_chars": len(header) + len(segment_text),
                "confidence": round(confidence, 3),
                "error_class": "" if result.found else "fallback",
                "error_detail": "",
            })

        finally:
            doc.close()

    with segment_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_SEGMENT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print("\n  -- Resumen segmentacion --")
    print(f"  Total:    {stats['total']}")
    print(f"  Exacta:   {stats['found']}")
    print(f"  Fallback: {stats['fallback']}")
    print(f"  Errores:  {stats['errors']}")
    print(f"  Desde OCR: {stats['from_ocr']}")
    print(f"  Bitacora: {segment_csv}")
    return segment_csv
