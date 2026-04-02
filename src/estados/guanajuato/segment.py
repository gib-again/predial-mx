"""
Segmentación de los PDFs del PO de Guanajuato.

A diferencia de Tamaulipas (1 PDF consolidado por año), Guanajuato tiene
MÚLTIPLES PDFs por año (cada uno con 2-5 leyes de ingresos municipales).

La segmentación tiene dos niveles:

  Nivel 1: Localizar cada ley municipal dentro de cada PDF.
    Patrón: "LEY DE INGRESOS PARA EL MUNICIPIO DE {NOMBRE}, GTO"
    Extraer: municipio, decreto, ejercicio, rango de páginas.
    Las primeras páginas (portada/sumario) se ignoran.

  Nivel 2: Dentro de cada ley, extraer la sección de predial.
    Inicio (en orden de prioridad):
      1) "SECCIÓN PRIMERA" + "DEL IMPUESTO PREDIAL"
      2) "CAPÍTULO" + ordinal + "IMPUESTO PREDIAL"
      3) "DEL IMPUESTO PREDIAL" standalone (con filtro de contexto)
    Fin:
      1) "SECCIÓN SEGUNDA" / "IMPUESTO SOBRE TRASLACIÓN"
      2) "DIVISIÓN" (de impuesto)
    Fallback: primeras 8 páginas si no se encuentra sección predial.

Genera:
  data/guanajuato/focus_predial/{ejercicio}/GTO_PREDIAL_{ejercicio}_{slug}.txt
  data/guanajuato/focus_predial/{ejercicio}/GTO_PREDIAL_{ejercicio}_{slug}.pdf
  data/guanajuato/meta/segment.csv
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from src.core.text_utils import slugify
from src.estados.guanajuato import config


FALLBACK_PAGES = 18


# ═══════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════

@dataclass
class LeyMunicipal:
    """Resultado de localizar una ley municipal dentro de un PDF del PO."""
    municipio: str          # Nombre como aparece en el PDF
    slug: str               # Slug normalizado
    cve_mun: str            # Clave INEGI
    decreto: str            # Número de decreto
    ejercicio: int          # Año fiscal
    page_start: int         # Página 0-indexed donde inicia
    page_end: int           # Página 0-indexed donde termina (exclusivo)
    pdf_path: Path          # PDF fuente


@dataclass
class SeccionPredial:
    """Resultado de localizar la sección predial dentro de una ley."""
    found: bool
    text: str = ""
    page_start: int = -1
    page_end: int = -1
    method: str = ""        # "seccion_predial" | "capitulo_predial" | "impuesto_predial" | "fallback_18pp"


# ═══════════════════════════════════════════════════
# Normalización de nombres de municipio
# ═══════════════════════════════════════════════════

def _normalize_municipio_name(raw: str) -> str:
    """Normaliza nombre de municipio del PDF al slug canónico."""
    name = raw.strip().rstrip(",").strip()
    name = re.sub(r"\s+", " ", name, flags=re.UNICODE)

    slug = slugify(name)
    slug = re.sub(r"[^a-z0-9_]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")

    # Match directo
    if slug in config.SLUG_TO_CVE:
        return slug

    # Alias
    if slug in config.ALIASES:
        return config.ALIASES[slug]

    # Match por nombre oficial
    upper = name.upper().strip()
    if upper in config.NAME_TO_SLUG:
        return config.NAME_TO_SLUG[upper]

    # Fuzzy: quitar sufijos comunes
    for suffix in ["_de", "_del", "_la", "_el", "_las", "_los"]:
        if slug.endswith(suffix):
            candidate = slug[: -len(suffix)]
            if candidate in config.SLUG_TO_CVE:
                return candidate

    # Substring match
    for canonical_slug in config.SLUG_TO_CVE:
        if canonical_slug in slug or slug in canonical_slug:
            return canonical_slug

    # Alias substring
    for alias, canonical in config.ALIASES.items():
        if alias in slug or slug in alias:
            return canonical

    return slug


# ═══════════════════════════════════════════════════
# Nivel 1: Localizar leyes municipales
# ═══════════════════════════════════════════════════

# Patrón para detectar inicio de cada ley municipal.
# Tolera ruido OCR con \s+ flexible.
_RE_LEY_INICIO = re.compile(
    r"LEY\s+DE\s+INGRESOS\s+PARA\s+EL\s+MUNICIPIO\s+DE\s+"
    r"([\w\sÁÉÍÓÚÑÜáéíóúñü\.\,]+?)"
    r"(?:[,\s]+GTO\.?|[,\s]+GUANAJUATO|[,\s]+PARA\s+EL\s+EJERCICIO)",
    re.IGNORECASE,
)

# Patrón para decreto
_RE_DECRETO = re.compile(
    r"D\s*E\s*C\s*R\s*E\s*T\s*O\s+(?:No\.?|N[oúu]m\.?)\s*([0-9A-Z\-]+)",
    re.IGNORECASE,
)

# Patrón para ejercicio fiscal
_RE_EJERCICIO = re.compile(
    r"EJERCICIO\s+FISCAL\s+(?:DEL\s+A[ÑN]O\s+)?(\d{4})",
    re.IGNORECASE,
)


def _detect_skip_pages(doc: fitz.Document, max_check: int = 5) -> int:
    """Auto-detecta cuántas páginas de portada/sumario saltar."""
    for i in range(min(max_check, len(doc))):
        text = (doc[i].get_text("text") or "").upper()
        if "SUMARIO" in text or "ÍNDICE" in text or "INDICE" in text:
            return i + 1
    return 1  # Default: saltar solo la portada


def find_leyes_in_pdf(
    doc: fitz.Document,
    pdf_path: Path,
    skip_pages: int = 1,
    default_ejercicio: int | None = None,
) -> list[LeyMunicipal]:
    """
    Escanea un PDF del PO y localiza el inicio de cada ley municipal.
    Retorna lista ordenada por page_start.
    """
    hits: list[tuple[int, str, str, int]] = []  # (page, municipio_raw, decreto, ejercicio)
    last_decreto = ""
    last_ejercicio = default_ejercicio or 0

    for page_idx in range(skip_pages, len(doc)):
        text = doc[page_idx].get_text("text")
        if not text:
            continue

        # Buscar decretos
        for m in _RE_DECRETO.finditer(text):
            last_decreto = m.group(1).strip()

        # Buscar ejercicio fiscal
        for m in _RE_EJERCICIO.finditer(text):
            try:
                last_ejercicio = int(m.group(1))
            except ValueError:
                pass

        # Buscar inicio de ley
        for m in _RE_LEY_INICIO.finditer(text):
            muni_raw = m.group(1).strip()
            hits.append((page_idx, muni_raw, last_decreto, last_ejercicio))

    # Deduplicar por slug (primera aparición gana)
    seen: set[str] = set()
    unique: list[tuple[int, str, str, int]] = []
    hits.sort(key=lambda x: x[0])

    for page, muni, dec, ej in hits:
        slug = _normalize_municipio_name(muni)
        key = f"{slug}_{ej}"
        if key in seen:
            continue
        seen.add(key)
        unique.append((page, muni, dec, ej))

    # Construir LeyMunicipal con page_end
    leyes: list[LeyMunicipal] = []
    for i, (page, muni, dec, ej) in enumerate(unique):
        slug = _normalize_municipio_name(muni)
        cve_mun = config.SLUG_TO_CVE.get(slug, ("???",))[0] if slug in config.SLUG_TO_CVE else "???"

        page_end = unique[i + 1][0] if i + 1 < len(unique) else len(doc)

        leyes.append(LeyMunicipal(
            municipio=muni,
            slug=slug,
            cve_mun=cve_mun,
            decreto=dec,
            ejercicio=ej,
            page_start=page,
            page_end=page_end,
            pdf_path=pdf_path,
        ))

    return leyes


# ═══════════════════════════════════════════════════
# Nivel 2: Extraer sección predial
# ═══════════════════════════════════════════════════

# Inicio de sección predial — ESTRATEGIA:
#
# Buscar todas las ocurrencias de "IMPUESTO PREDIAL" en el texto,
# y para cada una verificar el contexto circundante para determinar
# si es el inicio real de la sección (no facilidades/estímulos/índice).
#
# Contexto positivo (dentro de ~300 chars antes):
#   - "SECCIÓN PRIMERA/ÚNICA" → método "seccion_predial"
#   - "CAPÍTULO" + ordinal → método "capitulo_predial"
#   - Ninguno de los anteriores pero tiene "Artículo" después → "impuesto_predial"
#
# Contexto negativo (dentro de ~500 chars antes):
#   - FACILIDADES ADMINISTRATIVAS / ESTÍMULOS FISCALES
#   - ESTIMACIÓN / CLASIFICADOR / CONCEPTO (tabla presupuestal)
#   - DISPOSICIONES GENERALES

_RE_IMPUESTO_PREDIAL = re.compile(
    r"(?:DEL\s+)?IMPUESTO\s+PREDIAL",
    re.IGNORECASE,
)

_RE_CONTEXT_SECCION = re.compile(
    r"SECCI[OÓ]N\s+(?:PRIMERA|ÚNICA|UNICA)",
    re.IGNORECASE,
)

_RE_CONTEXT_CAPITULO = re.compile(
    r"CAP[IÍ]TULO\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|"
    r"S[EÉ]PTIMO|OCTAVO|NOVENO|D[EÉ]CIMO|[IVX]+|\d+)",
    re.IGNORECASE,
)

_RE_CONTEXT_ARTICULO = re.compile(
    r"ART[IÍ]CULO\s+\d+",
    re.IGNORECASE,
)

# Contextos que NO son inicio de predial
_RE_FALSE_POSITIVE = re.compile(
    r"(?:1210\b|CLASIFICADOR|DISPOSICIONES\s+GENERALES|"
    r"FACILIDADES\s+ADMINISTRATIVAS|EST[IÍ]MULOS\s+FISCALES|"
    r"REDUCCI[OÓ]N\s+(?:DEL|EN\s+EL)\s+(?:PAGO|IMPUESTO))",
    re.IGNORECASE,
)

# Fin de sección predial
_RE_PREDIAL_END_SECCION = re.compile(
    r"SECCI[OÓ]N\s+SEGUNDA",
    re.IGNORECASE,
)
_RE_PREDIAL_END_TRASLACION = re.compile(
    r"(?:DEL\s+)?IMPUESTO\s+SOBRE\s+(?:TRASLACI[OÓ]N|TRANSMISI[OÓ]N)\s+DE\s+DOMINIO",
    re.IGNORECASE,
)
_RE_PREDIAL_END_DIVISION = re.compile(
    r"DIVISI[OÓ]N\s+(?:SEGUNDA|DEL\s+IMPUESTO)",
    re.IGNORECASE,
)
_RE_PREDIAL_END_ADQUISICION = re.compile(
    r"(?:DEL\s+)?IMPUESTO\s+SOBRE\s+(?:LA\s+)?ADQUISICI[OÓ]N\s+DE\s+(?:BIENES?\s+)?INMUEBLES",
    re.IGNORECASE,
)


def _find_predial_start(text: str) -> tuple[int | None, str]:
    """Busca inicio de sección predial. Retorna (posición, método) o (None, "").

    Filtros de falsos positivos:
      a) Descarta si en los 800 chars anteriores hay FACILIDADES/ESTÍMULOS.
      b) Descarta si está después de la mitad del texto de la ley.
      c) Descarta si "IMPUESTO PREDIAL" está en minúsculas/mixtas (mención
         dentro de párrafo, no encabezado). Solo acepta MAYÚSCULAS.
    """
    half = len(text) // 2

    for m in _RE_IMPUESTO_PREDIAL.finditer(text):
        pos = m.start()

        # Filtro (c): solo aceptar si el match está en MAYÚSCULAS (encabezado)
        if m.group(0) != m.group(0).upper():
            continue

        # Filtro (b): descartar si está en la segunda mitad de la ley
        if pos > half:
            continue

        # Filtro (a): descartar facilidades/estímulos/índice (800 chars atrás)
        context_far = text[max(0, pos - 800): pos]
        if _RE_FALSE_POSITIVE.search(context_far):
            continue

        # Contexto positivo: determinar método
        context_near = text[max(0, pos - 300): pos]

        if _RE_CONTEXT_SECCION.search(context_near):
            sec_m = _RE_CONTEXT_SECCION.search(context_near)
            offset = max(0, pos - 300) + sec_m.start()
            return offset, "seccion_predial"

        if _RE_CONTEXT_CAPITULO.search(context_near):
            cap_m = _RE_CONTEXT_CAPITULO.search(context_near)
            offset = max(0, pos - 300) + cap_m.start()
            return offset, "capitulo_predial"

        # Sin SECCIÓN ni CAPÍTULO, pero verificar que tenga "Artículo" después
        context_after = text[m.end(): min(len(text), m.end() + 300)]
        if _RE_CONTEXT_ARTICULO.search(context_after):
            return pos, "impuesto_predial"

    return None, ""


def _find_predial_end(text: str, start_pos: int) -> int | None:
    """Busca fin de sección predial DESPUÉS de start_pos."""
    remaining = text[start_pos:]

    # Buscar todos los posibles finales y tomar el más cercano
    candidates: list[int] = []

    for pattern in [
        _RE_PREDIAL_END_SECCION,
        _RE_PREDIAL_END_TRASLACION,
        _RE_PREDIAL_END_DIVISION,
        _RE_PREDIAL_END_ADQUISICION,
    ]:
        m = pattern.search(remaining)
        if m and m.start() > 200:  # Ignorar matches muy cerca del inicio
            candidates.append(start_pos + m.start())

    return min(candidates) if candidates else None


def extract_predial_section(
    doc: fitz.Document,
    ley: LeyMunicipal,
) -> SeccionPredial:
    """
    Extrae la sección de predial de una ley municipal.
    Si no se encuentra, devuelve las primeras FALLBACK_PAGES páginas.
    """
    pages_text: list[tuple[int, str]] = []
    for p in range(ley.page_start, ley.page_end):
        text = doc[p].get_text("text")
        if text:
            pages_text.append((p, text))

    if not pages_text:
        return SeccionPredial(found=False, method="no_text")

    full_text = "\n".join(t for _, t in pages_text)

    # ── Buscar inicio ──
    start_pos, method = _find_predial_start(full_text)

    if start_pos is None:
        # ── FALLBACK: primeras N páginas de la ley ──
        fb_end = min(ley.page_start + FALLBACK_PAGES, ley.page_end)
        fb_text_parts = []
        for p in range(ley.page_start, fb_end):
            t = doc[p].get_text("text")
            if t:
                fb_text_parts.append(t)
        fb_text = "\n".join(fb_text_parts).strip()
        return SeccionPredial(
            found=True,
            text=fb_text,
            page_start=ley.page_start,
            page_end=fb_end,
            method=f"fallback_{FALLBACK_PAGES}pp",
        )

    # ── Buscar fin ──
    end_pos = _find_predial_end(full_text, start_pos)

    if end_pos is None:
        # Sin delimitador de fin: usar máximo 15000 chars desde inicio
        end_pos = min(start_pos + 15000, len(full_text))

    section_text = full_text[start_pos:end_pos].strip()

    # Determinar páginas que cubre esta sección
    char_count = 0
    p_start = pages_text[0][0]
    p_end = pages_text[-1][0] + 1
    for page_idx, page_text in pages_text:
        page_end_char = char_count + len(page_text) + 1
        if char_count <= start_pos < page_end_char:
            p_start = page_idx
        if char_count <= end_pos < page_end_char:
            p_end = page_idx + 1
            break
        char_count = page_end_char

    return SeccionPredial(
        found=True,
        text=section_text,
        page_start=p_start,
        page_end=p_end,
        method=method,
    )


# ═══════════════════════════════════════════════════
# Resolución de PDF fuente (prioridad: forceocr > ocr > raw)
# ═══════════════════════════════════════════════════

def _resolve_best_pdf(raw_pdf: Path, ocr_dir: Path) -> Path:
    """
    Dado un PDF raw, retorna la mejor versión disponible:
      1. _ocr.pdf (OCR procesado con force-ocr)
      2. original (si no hay versión OCR)
    """
    relative = raw_pdf.parent.name  # el año
    ocr_subdir = ocr_dir / relative

    ocr_path = ocr_subdir / (raw_pdf.stem + "_ocr.pdf")
    if ocr_path.exists():
        return ocr_path

    return raw_pdf


# ═══════════════════════════════════════════════════
# Meta CSV
# ═══════════════════════════════════════════════════

_META_FIELDS = [
    "ejercicio", "municipio", "slug", "cve_mun", "decreto",
    "source_pdf",
    "ley_page_start", "ley_page_end",
    "predial_found", "predial_method",
    "predial_page_start", "predial_page_end",
    "txt_file", "txt_chars",
]


def _write_meta_csv(meta_dir: Path, all_rows: list[dict]) -> Path:
    meta_dir.mkdir(parents=True, exist_ok=True)
    csv_path = meta_dir / "segment.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_META_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    return csv_path


# ═══════════════════════════════════════════════════
# Pipeline principal
# ═══════════════════════════════════════════════════

def run_segment(adapter, force: bool = False) -> Path:
    """
    Segmenta todos los PDFs del PO en secciones de predial por municipio.

    A diferencia de Tamaulipas (1 PDF/año), Guanajuato tiene múltiples
    PDFs por año, cada uno con varias leyes. Iteramos sobre todos.

    Returns:
        Path al CSV de metadatos de segmentación.
    """
    pdf_raw_dir = adapter.pdf_raw_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    focus_dir = adapter.focus_dir
    meta_dir = adapter.meta_dir

    print(f"═══ Guanajuato: Segmentación ═══")

    stats = {
        "total": 0, "found_exact": 0, "found_fallback": 0,
        "skipped": 0, "errors": 0,
    }
    all_meta_rows: list[dict] = []

    for ejercicio in range(config.YEAR_MIN, config.YEAR_MAX + 1):
        year_raw_dir = pdf_raw_dir / str(ejercicio)
        if not year_raw_dir.exists():
            continue

        pdf_files = sorted({p for p in year_raw_dir.iterdir() if p.suffix.lower() == ".pdf"})
        if not pdf_files:
            continue

        year_out = focus_dir / str(ejercicio)
        year_out.mkdir(parents=True, exist_ok=True)

        print(f"\n  [{ejercicio}] {len(pdf_files)} PDFs en pdf_raw/")

        for raw_pdf in pdf_files:
            # Usar la mejor versión OCR disponible
            best_pdf = _resolve_best_pdf(raw_pdf, pdf_ocr_dir)

            try:
                doc = fitz.open(str(best_pdf))
            except Exception as e:
                print(f"    ERROR abriendo {best_pdf.name}: {e}")
                stats["errors"] += 1
                continue

            skip_n = _detect_skip_pages(doc)

            # Nivel 1: encontrar leyes
            leyes = find_leyes_in_pdf(
                doc, best_pdf, skip_pages=skip_n,
                default_ejercicio=ejercicio,
            )

            if not leyes:
                doc.close()
                continue

            print(f"    {best_pdf.name}: {len(leyes)} leyes (skip={skip_n}pp)")

            for ley in leyes:
                stats["total"] += 1
                ej = ley.ejercicio or ejercicio

                txt_path = year_out / f"{config.PREFIJO}_PREDIAL_{ej}_{ley.slug}.txt"
                pdf_out = year_out / f"{config.PREFIJO}_PREDIAL_{ej}_{ley.slug}.pdf"

                if txt_path.exists() and not force:
                    stats["skipped"] += 1
                    all_meta_rows.append({
                        "ejercicio": ej,
                        "municipio": ley.municipio,
                        "slug": ley.slug,
                        "cve_mun": ley.cve_mun,
                        "decreto": ley.decreto,
                        "source_pdf": best_pdf.name,
                        "ley_page_start": ley.page_start + 1,
                        "ley_page_end": ley.page_end,
                        "predial_found": "skipped",
                        "predial_method": "",
                        "predial_page_start": "",
                        "predial_page_end": "",
                        "txt_file": txt_path.name,
                        "txt_chars": txt_path.stat().st_size if txt_path.exists() else 0,
                    })
                    continue

                # Nivel 2: extraer predial
                seccion = extract_predial_section(doc, ley)

                if seccion.method.startswith("fallback"):
                    print(f"      {ley.slug}: predial no detectada → {seccion.method}")
                    stats["found_fallback"] += 1
                else:
                    stats["found_exact"] += 1

                # Guardar TXT
                header = (
                    f"# Municipio: {ley.municipio}\n"
                    f"# Estado: Guanajuato\n"
                    f"# Ejercicio: {ej}\n"
                    f"# Decreto: {ley.decreto}\n"
                    f"# Fuente: {best_pdf.name}\n"
                    f"# Páginas ley: {ley.page_start + 1}-{ley.page_end}\n"
                    f"# Páginas predial: {seccion.page_start + 1}-{seccion.page_end}\n"
                    f"# Método detección: {seccion.method}\n"
                    f"# CVE_MUN: {ley.cve_mun}\n\n"
                )
                txt_content = header + seccion.text
                txt_path.write_text(txt_content, encoding="utf-8")

                # Guardar PDF recortado
                try:
                    out_doc = fitz.open()
                    for p in range(seccion.page_start, seccion.page_end):
                        if 0 <= p < len(doc):
                            out_doc.insert_pdf(doc, from_page=p, to_page=p)
                    out_doc.save(str(pdf_out))
                    out_doc.close()
                except Exception as e:
                    print(f"      {ley.slug}: Error guardando PDF: {e}")

                all_meta_rows.append({
                    "ejercicio": ej,
                    "municipio": ley.municipio,
                    "slug": ley.slug,
                    "cve_mun": ley.cve_mun,
                    "decreto": ley.decreto,
                    "source_pdf": best_pdf.name,
                    "ley_page_start": ley.page_start + 1,
                    "ley_page_end": ley.page_end,
                    "predial_found": "true" if not seccion.method.startswith("fallback") else "fallback",
                    "predial_method": seccion.method,
                    "predial_page_start": seccion.page_start + 1,
                    "predial_page_end": seccion.page_end,
                    "txt_file": txt_path.name,
                    "txt_chars": len(txt_content),
                })

            doc.close()

    # Escribir meta CSV
    if all_meta_rows:
        csv_path = _write_meta_csv(meta_dir, all_meta_rows)
        print(f"\n  Meta: {csv_path.name} ({len(all_meta_rows)} filas)")

    print(f"\n  ── Resumen ──")
    print(f"  Total: {stats['total']}")
    print(f"  Predial exacta: {stats['found_exact']}")
    print(f"  Predial fallback: {stats['found_fallback']}")
    print(f"  Ya existían: {stats['skipped']}")
    print(f"  Errores: {stats['errors']}")

    return meta_dir / "segment.csv"
