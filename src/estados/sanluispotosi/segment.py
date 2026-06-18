"""
Segmentación de PDFs del PO de San Luis Potosí.

Modelo: 1 PDF = 1 ley municipal completa (similar a Jalisco). No hay tomos
multi-municipio, así que la segmentación es de un solo nivel.

Estructura real de la ley en SLP (verificada con muestras 2024):

  [Página 1]   Sumario / portada / decreto                  ← evitar
  [Página 2+]  EXPOSICIÓN DE MOTIVOS                         ← evitar
               (incluye "del impuesto predial" varias veces)
  [Página ~3-5] TÍTULO SEGUNDO / DE LOS IMPUESTOS
               CAPÍTULO I / IMPUESTOS SOBRE LOS INGRESOS
                 SECCIÓN ÚNICA / ESPECTÁCULOS PÚBLICOS
               CAPÍTULO II / IMPUESTOS SOBRE EL PATRIMONIO   ← AQUÍ empieza
                 SECCIÓN PRIMERA / PREDIAL                     la sección
                   ARTÍCULO 6°. El impuesto predial se calculará...
                   [TABLA DE TASAS]
                   ARTÍCULO 7°. ...
                 SECCIÓN SEGUNDA / IMPUESTO SOBRE ADQUISICIÓN ← AQUÍ termina
               CAPÍTULO III / ACCESORIOS DE IMPUESTOS

Patrones priorizados:
  1. "SECCIÓN PRIMERA ... PREDIAL"
  2. "CAPÍTULO II ... PATRIMONIO ... PREDIAL"
  3. "ARTÍCULO N ... el impuesto predial se calculará"
  4. "PREDIAL" como cabecera de línea (tras CAPÍTULO/SECCIÓN)
Fin:
  1. "SECCIÓN SEGUNDA"
  2. "IMPUESTO SOBRE ADQUISICIÓN DE INMUEBLES"
  3. "CAPÍTULO III" / "ACCESORIOS DE IMPUESTOS"

Trampas conocidas:
  - "del impuesto predial" en exposición de motivos (chars 2 000-6 000)
  - Tablas anexas comparativas al final del PDF que repiten "impuesto predial
    nunca será inferior..." → si el matcher cae ahí, el segmento sale truncado
  → ambos se evitan con patrones específicos arriba (no usar regex genérica
    "(?:DEL\\s+)?IMPUESTO\\s+PREDIAL" como inicio)

Genera:
  data/sanluispotosi/focus_predial/{ejercicio}/SLP_PREDIAL_{ejercicio}_{slug}.txt
  data/sanluispotosi/focus_predial/{ejercicio}/SLP_PREDIAL_{ejercicio}_{slug}.pdf
  data/sanluispotosi/meta/predial_master.csv  (inventario simple)
  data/sanluispotosi/meta/segment.csv        (bitácora con confidence/method)
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
from src.estados.sanluispotosi import config


FALLBACK_PAGES = 12  # ley típica de SLP cabe en ~10-15 páginas


# ═══════════════════════════════════════════════════
# Patrones SLP
# ═══════════════════════════════════════════════════

_SLP_START_SPECS = [
    # 1) Más específico: SECCIÓN PRIMERA seguido de PREDIAL (estructura canónica 2010+)
    PatternSpec(re.compile(
        r"SECCI[OÓ]N\s+(?:PRIMERA|[UÚ]NICA)\b\s*[\s\S]{0,200}?\bPREDIAL\b",
        re.IGNORECASE,
    ), "seccion_predial"),

    # 2) CAPÍTULO II + (PATRIMONIO opcional) + PREDIAL
    PatternSpec(re.compile(
        r"CAP[IÍ]TULO\s+(?:II|SEGUNDO|2)\b[\s\S]{0,800}?"
        r"(?:IMPUESTOS?\s+SOBRE\s+EL\s+PATRIMONIO[\s\S]{0,500}?)?"
        r"\bPREDIAL\b",
        re.IGNORECASE,
    ), "capitulo_ii_predial"),

    # 3) ARTÍCULO N + "el impuesto predial se calculará" (formato moderno)
    PatternSpec(re.compile(
        r"ART[IÍ]CULO\s+\d+[°ºo]?\.?\s*[\s\S]{0,80}?"
        r"[Ee]l\s+impuesto\s+predial\s+se\s+calcular[áa]",
        re.IGNORECASE,
    ), "articulo_predial_calcula"),

    # 4) Variante: TÍTULO SEGUNDO + DE LOS IMPUESTOS + ... + PREDIAL
    #    (en algunas leyes históricas el predial sí está en CAPÍTULO I)
    PatternSpec(re.compile(
        r"T[IÍ]TULO\s+SEGUNDO\b[\s\S]{0,3000}?"
        r"DE\s+LOS\s+IMPUESTOS[\s\S]{0,2000}?"
        r"CAP[IÍ]TULO\s+(?:I|PRIMERO|1)\b[\s\S]{0,500}?\bPREDIAL\b",
        re.IGNORECASE,
    ), "titulo_capitulo_i_predial"),
]

_SLP_END_SPECS = [
    # SECCIÓN SEGUNDA (en SLP típicamente = ADQUISICIÓN DE INMUEBLES)
    PatternSpec(re.compile(r"SECCI[OÓ]N\s+SEGUNDA\b", re.IGNORECASE), "seccion_segunda"),
    PatternSpec(re.compile(
        r"(?:DEL\s+)?IMPUESTO\s+SOBRE\s+(?:LA\s+)?ADQUISICI[OÓ]N\s+DE\s+(?:BIENES\s+)?INMUEBLES",
        re.IGNORECASE,
    ), "adquisicion_inmuebles"),
    PatternSpec(re.compile(r"CAP[IÍ]TULO\s+(?:III|TERCERO|3)\b", re.IGNORECASE), "capitulo_iii"),
    PatternSpec(re.compile(r"ACCESORIOS\s+DE\s+IMPUESTOS", re.IGNORECASE), "accesorios"),
    PatternSpec(re.compile(r"T[IÍ]TULO\s+TERCERO\b", re.IGNORECASE), "titulo_tercero"),
]

_SLP_BLACKLIST = [
    # Bloquear matches cuyo contexto previo sea exposición de motivos
    re.compile(r"EXPOSICI[OÓ]N\s+DE\s+MOTIVOS", re.IGNORECASE),
]


def _slp_context_validator(text: str, match: re.Match, method: str) -> bool:
    """
    Validador SLP — los specs ya son lo suficientemente específicos para no
    necesitar filtros de posición agresivos. Solo se descartan matches dentro
    de las primeras 1 500 palabras (zona de sumario/portada).
    """
    pos = match.start()
    # Rechazar matches en zona de sumario (chars 0-1500): el sumario contiene
    # el título "Ley de Ingresos del Municipio de X" pero ningún ARTÍCULO N.
    if pos < 1500:
        return False
    return True


# ═══════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════

def _iter_pdfs(pdf_raw_dir: Path, year_filter: str | None = None):
    """Itera (ejercicio, pdf_path) en pdf_raw/{año}/*.pdf, opcionalmente filtrado."""
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
    """
    Devuelve la mejor versión disponible del PDF:
      1. {pdf_ocr_dir}/{año}/{stem}_ocr.pdf si existe (OCR aplicado).
      2. raw_pdf en caso contrario.
    """
    year_name = raw_pdf.parent.name
    ocr_path = pdf_ocr_dir / year_name / (raw_pdf.stem + "_ocr.pdf")
    if ocr_path.exists() and ocr_path.stat().st_size > 0:
        return ocr_path
    return raw_pdf


def _slug_from_filename(pdf_path: Path) -> str | None:
    """Extrae slug de SLP_RAW_{año}_{slug}.pdf."""
    stem = pdf_path.stem
    parts = stem.split("_")
    if len(parts) < 4:
        return None
    if parts[0] != config.PREFIJO or parts[1] != "RAW":
        return None
    try:
        int(parts[2])
    except ValueError:
        return None
    return "_".join(parts[3:]) or None


# ═══════════════════════════════════════════════════
# Paso "master": inventario de PDFs descargados
# ═══════════════════════════════════════════════════

_MASTER_FIELDS = ["ejercicio", "slug", "source_pdf", "num_pages"]


def run_build_master(adapter) -> Path:
    """Inventario de PDFs en pdf_raw/. En SLP cada PDF = 1 ley completa."""
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
            "ejercicio": ejercicio,
            "slug": slug,
            "source_pdf": pdf_path.name,
            "num_pages": num_pages,
        })

    with master_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_MASTER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  Master: {master_csv} ({len(rows)} PDFs inventariados)")
    return master_csv


# ═══════════════════════════════════════════════════
# Paso "segment": extraer sección predial
# ═══════════════════════════════════════════════════

_SEGMENT_FIELDS = [
    "ejercicio", "slug", "source_pdf", "focus_file",
    "segment_method", "page_start", "page_end",
    "char_start", "char_end", "txt_chars", "confidence",
    "error_class", "error_detail",
    *[f for f in HITL_EXTRA_FIELDS if f not in {"char_start", "char_end", "confidence"}],
]


def _build_pages_text(doc: fitz.Document) -> tuple[str, list[tuple[int, int]]]:
    """
    Concatena el texto de todas las páginas y devuelve también la tabla de
    (page_idx, char_offset_inicio) para mapear índices de char a páginas.
    """
    parts: list[str] = []
    offsets: list[tuple[int, int]] = []  # (page_idx, char_start)
    cursor = 0
    for p_idx in range(len(doc)):
        offsets.append((p_idx, cursor))
        text = doc[p_idx].get_text("text") or ""
        parts.append(text)
        cursor += len(text) + 1  # +1 por el "\n" del join
    return "\n".join(parts), offsets


def _char_to_page(char_idx: int, offsets: list[tuple[int, int]], n_pages: int) -> int:
    """Mapea índice de carácter (en el texto concatenado) a índice de página 0-based."""
    page = 0
    for p_idx, start in offsets:
        if start <= char_idx:
            page = p_idx
        else:
            break
    return min(page, n_pages - 1)


def _save_pdf_slice(doc: fitz.Document, page_start: int, page_end: int, out_path: Path) -> None:
    """Guarda un slice de PDF [page_start, page_end) en out_path."""
    out_doc = fitz.open()
    try:
        for p in range(page_start, min(page_end, len(doc))):
            out_doc.insert_pdf(doc, from_page=p, to_page=p)
        out_doc.save(str(out_path))
    finally:
        out_doc.close()


def run_extract_sections(adapter, year: str | None = None) -> Path:
    """Para cada PDF en pdf_raw/, extrae la sección predial → TXT + PDF recortado.

    Si existe una versión OCR'd en pdf_ocr/{año}/{stem}_ocr.pdf, se prefiere
    sobre el raw (los PDFs SLP 2012-2016 y 2019 son escaneos).
    """
    pdf_raw_dir = adapter.pdf_raw_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    focus_dir = adapter.focus_dir
    meta_dir = adapter.meta_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    segment_csv = meta_dir / "segment.csv"

    print("═══ San Luis Potosí: Segmentación predial ═══")
    if year:
        print(f"    Filtro de año: {year}")

    rows: list[dict] = []
    stats = {"total": 0, "found": 0, "fallback": 0, "errors": 0, "skipped": 0, "from_ocr": 0}

    for ejercicio, raw_pdf in _iter_pdfs(pdf_raw_dir, year_filter=year):
        slug = _slug_from_filename(raw_pdf)
        if not slug:
            print(f"    [WARN] nombre no parseable: {raw_pdf.name}")
            continue

        # Preferir versión OCR'd si existe
        pdf_path = _resolve_best_pdf(raw_pdf, pdf_ocr_dir)
        used_ocr = pdf_path != raw_pdf
        if used_ocr:
            stats["from_ocr"] += 1

        stats["total"] += 1
        year_focus = focus_dir / str(ejercicio)
        year_focus.mkdir(parents=True, exist_ok=True)

        txt_out = year_focus / f"{config.PREFIJO}_PREDIAL_{ejercicio}_{slug}.txt"
        pdf_out = year_focus / f"{config.PREFIJO}_PREDIAL_{ejercicio}_{slug}.pdf"

        # Abrir PDF (versión OCR si está disponible)
        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            print(f"    [ERROR] {pdf_path.name}: no se pudo abrir ({e})")
            stats["errors"] += 1
            rows.append({
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
                print(f"    [WARN] {pdf_path.name}: sin texto extraíble (¿escaneado?)")
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
                start_specs=_SLP_START_SPECS,
                end_specs=_SLP_END_SPECS,
                blacklist_patterns=_SLP_BLACKLIST,
                context_validator=_slp_context_validator,
                max_chars=20_000,
                min_chars=300,
                fallback_chars=0,  # fallback se maneja con páginas abajo
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
                # Fallback: páginas iniciales después del front-matter (saltar p1-2).
                skip = min(2, n_pages - 1)
                p_start = skip
                p_end = min(skip + FALLBACK_PAGES, n_pages)
                fb_chunks = []
                for p in range(p_start, p_end):
                    t = doc[p].get_text("text")
                    if t:
                        fb_chunks.append(t)
                segment_text = "\n".join(fb_chunks).strip()
                method = f"fallback_{p_end - p_start}pp"
                confidence = 0.3
                stats["fallback"] += 1

            # Header informativo
            header = (
                f"# Estado: {config.ESTADO_NOMBRE}\n"
                f"# Municipio (slug): {slug}\n"
                f"# Ejercicio: {ejercicio}\n"
                f"# Fuente: {pdf_path.name}\n"
                f"# Páginas predial: {p_start + 1}-{p_end}\n"
                f"# Método detección: {method}\n"
                f"# Confianza: {confidence:.2f}\n\n"
            )
            txt_content = header + segment_text
            txt_out.write_text(txt_content, encoding="utf-8")

            # PDF slice
            try:
                _save_pdf_slice(doc, p_start, p_end, pdf_out)
            except Exception as e:
                print(f"    [WARN] {pdf_path.name}: no se pudo guardar PDF slice ({e})")

            rows.append({
                **hitl_extra_columns(result if result.found else None),
                "ejercicio": ejercicio,
                "slug": slug,
                "source_pdf": pdf_path.name,
                "focus_file": txt_out.name,
                "segment_method": method,
                "page_start": p_start + 1,
                "page_end": p_end,
                "char_start": result.start_char if result.found else "",
                "char_end": result.end_char if result.found else "",
                "txt_chars": len(txt_content),
                "confidence": round(confidence, 3),
                "error_class": "" if result.found else "fallback",
                "error_detail": "",
            })

        finally:
            doc.close()

    # CSV bitácora
    with segment_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_SEGMENT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print("\n  ── Resumen segmentación ──")
    print(f"  Total:    {stats['total']}")
    print(f"  Exacta:   {stats['found']}")
    print(f"  Fallback: {stats['fallback']}")
    print(f"  Errores:  {stats['errors']}")
    print(f"  Desde OCR: {stats['from_ocr']}")
    print(f"  Bitácora: {segment_csv}")
    return segment_csv
