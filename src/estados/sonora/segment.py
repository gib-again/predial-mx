"""
Segmentación de PDFs del Boletín Oficial de Sonora.

Modelo de 2 niveles (igual que Guanajuato):

  Nivel 1: Localizar cada ley municipal dentro de cada PDF físico.
    Cada PDF descargado corresponde a una sección romana del boletín y
    agrupa 1-6 leyes municipales en serie. Patrón canónico:
        "LEY DE INGRESOS Y PRESUPUESTO DE INGRESOS DEL AYUNTAMIENTO
         DEL MUNICIPIO DE {M}, SONORA, PARA EL EJERCICIO FISCAL DE {YYYY}"

  Nivel 2: Dentro de cada ley, extraer la sección de predial.
    Inicio (en orden de prioridad):
      1) "TÍTULO SEGUNDO" + "CAPÍTULO PRIMERO" + "Impuesto Predial"
      2) "CAPÍTULO PRIMERO" + "Impuesto Predial"
      3) "ARTÍCULO N" + "el impuesto predial se causará/calculará"
      4) "IMPUESTO PREDIAL" como fallback
    Fin:
      1) "CAPÍTULO SEGUNDO" + "Traslación de Dominio"
      2) "Impuesto sobre Traslación de Dominio"
      3) "CAPÍTULO TERCERO" / "TÍTULO TERCERO"
    Fallback: primeras FALLBACK_PAGES páginas de la ley.

Genera:
  data/sonora/meta/predial_master.csv  (nivel 1: ley × páginas)
  data/sonora/meta/segment.csv         (nivel 2: bitácora con confidence/method)
  data/sonora/focus_predial/{ejercicio}/SON_PREDIAL_{ejercicio}_{slug}.txt
  data/sonora/focus_predial/{ejercicio}/SON_PREDIAL_{ejercicio}_{slug}.pdf
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from src.core.muni_matcher import MuniMatcher
from src.core.segment_utils import (
    HITL_EXTRA_FIELDS,
    PatternSpec,
    SegmentResult,
    find_predial_section,
    hitl_extra_columns,
)
from src.estados.sonora import config


FALLBACK_PAGES = 14  # ley típica de Sonora cabe en ~10-15 páginas


# ═══════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════

@dataclass
class LeyMunicipal:
    """Resultado de localizar una ley municipal dentro de un PDF del Boletín."""
    municipio: str
    slug: str
    cve_mun: str
    num_ley: str
    ejercicio: int
    page_start: int   # 0-indexed donde inicia
    page_end: int     # 0-indexed donde termina (exclusivo)
    pdf_path: Path


@dataclass
class SeccionPredial:
    """Resultado de localizar la sección predial dentro de una ley."""
    found: bool
    text: str = ""
    page_start: int = -1
    page_end: int = -1
    method: str = ""
    _seg_result: SegmentResult | None = None


# ═══════════════════════════════════════════════════
# Matcher de municipios (singleton)
# ═══════════════════════════════════════════════════

_matcher = MuniMatcher(cve_ent=config.CVE_ENT, aliases=config.ALIASES)


def _normalize_municipio_name(raw: str) -> str:
    """Normaliza nombre del PDF al slug canónico INEGI."""
    name = re.sub(r"\s+", " ", (raw or "").strip().rstrip(",").strip())
    if not name:
        return ""
    return _matcher.match(name).slug


def _slug_to_cve(slug: str) -> str:
    """Mapea slug → cve_mun usando el matcher (que ya cargó el catálogo)."""
    if not slug:
        return ""
    mr = _matcher.match(slug)
    return mr.cve_mun


# ═══════════════════════════════════════════════════
# Nivel 1: Localizar leyes municipales dentro del PDF
# ═══════════════════════════════════════════════════

# Patrón tolerante a ruido OCR para detectar inicio de cada ley municipal.
# Empíricamente, el OCR introduce typos en palabras críticas del título:
#   - "AYUNTAMIENTO" → "AYUNTAMIF:NTO" / "A YLJNT AMIENTO" / a veces ausente
#   - "MUNICIPIO"     → "MUNTCH'JO" / "MUN ICIPIO" / "MUNICll'JO"
#   - "PRESUPUESTO"   → "Presupuestos" (con S) / "Presupuesto llE"
#   - "FISCAL"        → "FlSCAL"
# Estrategia: dos anclas estables ("LEY DE INGRESOS" + "MUNI*PIO DE X, SONORA")
# unidas por un comodín lazy, y "EJERCICIO FISCAL YYYY" como cierre. El nombre
# del municipio se valida después contra MuniMatcher INEGI.
_RE_LEY_INICIO = re.compile(
    r"LEY\s+DE\s+INGRESOS[\s\S]{0,300}?"
    # "MUNICIPIO DE" tolerante: M-U-N + cualquier ruido OCR (apóstrofes, puntos,
    # espacios, letras sueltas) hasta el siguiente "DE" + espacio.
    # Window 1-15 (era 1-8) para tolerar OCR mojibake severo en boletines
    # colectivos donde el right-margin del PDF se corta.
    r"MUN[\w\s\.\-:;'‘’]{1,15}?DE\s+"
    r"(?P<muni>[\w\sÁÉÍÓÚÑÜáéíóúñü\.\-]+?)\s*,?\s*"  # coma opcional (OCR a veces la pierde)
    r"SONORA[\s\S]{0,500}?"
    # El marcador "EJERCICIO FISCAL" se vuelve OPCIONAL: el OCR de boletines
    # colectivos trunca regularmente "EJERCICIO FISCAL DE 2010" → "EJERCICI\n2010".
    # Aceptamos cualquier prefijo razonable o ninguno antes del año, siempre que
    # el año (4 dígitos) aparezca en los siguientes 0-500 chars después de SONORA.
    r"(?:EJERC[A-Z]*\s+(?:F[A-Z]*\s+)?(?:DEL?\s+)?(?:A[ÑN]O\s+)?)?"
    r"(?P<anio>20\d{2}|19\d{2})",
    re.IGNORECASE,
)

_RE_NUM_LEY = re.compile(r"LEY\s+N[UÚ]MERO\s+(\d+)", re.IGNORECASE)


def find_leyes_in_pdf(
    doc: fitz.Document,
    pdf_path: Path,
    skip_pages: int = 0,
) -> list[LeyMunicipal]:
    """
    Escanea un PDF y localiza el inicio de cada ley municipal.
    Retorna lista ordenada por page_start, con page_end = inicio_siguiente_ley
    (o len(doc) para la última).
    """
    hits: list[tuple[int, str, int, str]] = []  # (page_idx, muni_raw, anio, num_ley)
    last_num_ley = ""

    for page_idx in range(skip_pages, len(doc)):
        text = doc[page_idx].get_text("text") or ""
        if not text:
            continue

        for m_num in _RE_NUM_LEY.finditer(text):
            last_num_ley = m_num.group(1).strip()

        for m in _RE_LEY_INICIO.finditer(text):
            muni_raw = m.group("muni").strip()
            try:
                anio = int(m.group("anio"))
            except ValueError:
                continue
            hits.append((page_idx, muni_raw, anio, last_num_ley))

    # Deduplicar por (slug, ejercicio) — primera aparición gana
    hits.sort(key=lambda x: x[0])
    seen: set[tuple[str, int]] = set()
    unique: list[tuple[int, str, int, str]] = []
    for page, muni, anio, num_ley in hits:
        slug = _normalize_municipio_name(muni)
        key = (slug, anio)
        if key in seen:
            continue
        seen.add(key)
        unique.append((page, muni, anio, num_ley))

    leyes: list[LeyMunicipal] = []
    for i, (page, muni, anio, num_ley) in enumerate(unique):
        slug = _normalize_municipio_name(muni)
        cve_mun = _slug_to_cve(slug)
        page_end = unique[i + 1][0] if i + 1 < len(unique) else len(doc)
        leyes.append(LeyMunicipal(
            municipio=muni,
            slug=slug,
            cve_mun=cve_mun,
            num_ley=num_ley,
            ejercicio=anio,
            page_start=page,
            page_end=page_end,
            pdf_path=pdf_path,
        ))
    return leyes


# ═══════════════════════════════════════════════════
# Nivel 2: Patrones de sección predial
# ═══════════════════════════════════════════════════

_SON_START_SPECS = [
    # 1) TÍTULO SEGUNDO + CAPÍTULO PRIMERO + Impuesto Predial (canónico)
    PatternSpec(re.compile(
        r"T[IÍ]TULO\s+SEGUNDO\b[\s\S]{0,2000}?"
        r"CAP[IÍ]TULO\s+(?:PRIMERO|I|1)\b[\s\S]{0,500}?"
        r"Impuesto\s+Predial",
        re.IGNORECASE,
    ), "titulo_segundo_capitulo_primero_predial"),

    # 2) CAPÍTULO PRIMERO + Impuesto Predial sin contexto previo
    PatternSpec(re.compile(
        r"CAP[IÍ]TULO\s+(?:PRIMERO|I|1)\b[\s\S]{0,300}?Impuesto\s+Predial",
        re.IGNORECASE,
    ), "capitulo_primero_predial"),

    # 3) ARTÍCULO N + "el impuesto predial se causará/calculará"
    PatternSpec(re.compile(
        r"ART[IÍ]CULO\s+\d+[°ºo]?\.?\s*[\s\S]{0,200}?"
        r"[Ee]l\s+impuesto\s+predial\s+se\s+(?:causar|calcular)[áa]",
        re.IGNORECASE,
    ), "articulo_predial_causa"),

    # 4) Fallback genérico
    PatternSpec(re.compile(
        r"\bIMPUESTO\s+PREDIAL\b",
        re.IGNORECASE,
    ), "impuesto_predial_generico"),
]

_SON_END_SPECS = [
    PatternSpec(re.compile(
        r"CAP[IÍ]TULO\s+(?:SEGUNDO|II|2)\b[\s\S]{0,200}?"
        r"(?:Impuesto\s+sobre\s+)?Traslaci[oó]n\s+de\s+Dominio",
        re.IGNORECASE,
    ), "capitulo_segundo_traslacion"),
    PatternSpec(re.compile(
        r"Impuesto\s+sobre\s+(?:la\s+)?Traslaci[oó]n\s+de\s+Dominio",
        re.IGNORECASE,
    ), "traslacion_dominio"),
    PatternSpec(re.compile(
        r"CAP[IÍ]TULO\s+(?:TERCERO|III|3)\b",
        re.IGNORECASE,
    ), "capitulo_tercero"),
    PatternSpec(re.compile(
        r"T[IÍ]TULO\s+TERCERO\b",
        re.IGNORECASE,
    ), "titulo_tercero"),
]

_SON_BLACKLIST: list[re.Pattern] = []


def _son_context_validator(text: str, match: re.Match, method: str) -> bool:
    """Rechaza matches en zona de portada/sumario (chars 0-1000)."""
    return match.start() >= 1000


def extract_predial_section(doc: fitz.Document, ley: LeyMunicipal) -> SeccionPredial:
    """
    Extrae la sección predial de una ley municipal individual.
    Si no encuentra patrones de inicio/fin, devuelve fallback de primeras N páginas.
    """
    pages_text: list[tuple[int, str]] = []
    for p in range(ley.page_start, ley.page_end):
        text = doc[p].get_text("text")
        if text:
            pages_text.append((p, text))

    if not pages_text:
        return SeccionPredial(found=False, method="no_text")

    full_text = "\n".join(t for _, t in pages_text)

    result = find_predial_section(
        text=full_text,
        start_specs=_SON_START_SPECS,
        end_specs=_SON_END_SPECS,
        blacklist_patterns=_SON_BLACKLIST,
        context_validator=_son_context_validator,
        max_chars=20_000,
        min_chars=300,
        fallback_chars=0,
    )

    if not result.found:
        fb_end = min(ley.page_start + FALLBACK_PAGES, ley.page_end)
        fb_text_parts: list[str] = []
        for p in range(ley.page_start, fb_end):
            t = doc[p].get_text("text")
            if t:
                fb_text_parts.append(t)
        return SeccionPredial(
            found=True,
            text="\n".join(fb_text_parts).strip(),
            page_start=ley.page_start,
            page_end=fb_end,
            method=f"fallback_{FALLBACK_PAGES}pp",
        )

    section_text = full_text[result.start_char:result.end_char].strip()

    # Mapear char_start/char_end a páginas absolutas del PDF
    char_count = 0
    p_start = pages_text[0][0]
    p_end = pages_text[-1][0] + 1
    for page_idx, page_text in pages_text:
        page_end_char = char_count + len(page_text) + 1
        if char_count <= result.start_char < page_end_char:
            p_start = page_idx
        if char_count <= result.end_char < page_end_char:
            p_end = page_idx + 1
            break
        char_count = page_end_char

    return SeccionPredial(
        found=True,
        text=section_text,
        page_start=p_start,
        page_end=p_end,
        method=result.method,
        _seg_result=result,
    )


# ═══════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════

def _iter_pdfs(pdf_raw_dir: Path):
    """Itera (anio_pub, pdf_path) en pdf_raw/{año}/*.pdf."""
    if not pdf_raw_dir.exists():
        return
    for year_dir in sorted(pdf_raw_dir.iterdir()):
        if not year_dir.is_dir():
            continue
        try:
            anio_pub = int(year_dir.name)
        except ValueError:
            continue
        for pdf in sorted(year_dir.glob("*.pdf")):
            yield anio_pub, pdf


def _resolve_best_pdf(raw_pdf: Path, pdf_ocr_dir: Path) -> Path:
    """Devuelve la versión OCR si existe, si no el raw."""
    year_name = raw_pdf.parent.name
    ocr_path = pdf_ocr_dir / year_name / (raw_pdf.stem + "_ocr.pdf")
    if ocr_path.exists() and ocr_path.stat().st_size > 0:
        return ocr_path
    return raw_pdf


def _save_pdf_slice(doc: fitz.Document, page_start: int, page_end: int, out_path: Path) -> None:
    out_doc = fitz.open()
    try:
        for p in range(page_start, min(page_end, len(doc))):
            out_doc.insert_pdf(doc, from_page=p, to_page=p)
        out_doc.save(str(out_path))
    finally:
        out_doc.close()


# ═══════════════════════════════════════════════════
# Paso "master": inventario de leyes por PDF
# ═══════════════════════════════════════════════════

_MASTER_FIELDS = [
    "ejercicio", "slug", "cve_mun", "municipio_raw", "num_ley",
    "source_pdf", "page_start", "page_end", "num_pages_ley",
]


def run_build_master(adapter) -> Path:
    """
    Para cada PDF físico descargado, localiza todas las leyes municipales
    que contiene y registra (ejercicio, slug, page_start, page_end) en master.
    """
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    master_csv = meta_dir / "predial_master.csv"

    print("═══ Sonora: Inventario de leyes por PDF ═══")
    rows: list[dict] = []
    n_pdfs = 0
    n_leyes = 0

    for anio_pub, raw_pdf in _iter_pdfs(pdf_raw_dir):
        n_pdfs += 1
        pdf_path = _resolve_best_pdf(raw_pdf, pdf_ocr_dir)
        try:
            with fitz.open(str(pdf_path)) as doc:
                leyes = find_leyes_in_pdf(doc, pdf_path)
        except Exception as e:
            print(f"  [WARN] {pdf_path.name}: {e}")
            continue

        for ley in leyes:
            n_leyes += 1
            rows.append({
                "ejercicio": ley.ejercicio,
                "slug": ley.slug,
                "cve_mun": ley.cve_mun,
                "municipio_raw": ley.municipio,
                "num_ley": ley.num_ley,
                "source_pdf": str(raw_pdf.relative_to(pdf_raw_dir.parent)),
                "page_start": ley.page_start,
                "page_end": ley.page_end,
                "num_pages_ley": ley.page_end - ley.page_start,
            })

    with master_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_MASTER_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print(f"  PDFs procesados: {n_pdfs} | Leyes localizadas: {n_leyes}")
    print(f"  Master: {master_csv}")
    return master_csv


# ═══════════════════════════════════════════════════
# Paso "segment": extraer sección predial por ley
# ═══════════════════════════════════════════════════

_SEGMENT_FIELDS = [
    "ejercicio", "slug", "source_pdf", "focus_file",
    "ley_page_start", "ley_page_end",
    "segment_method", "page_start", "page_end",
    "txt_chars", "confidence", "error_class", "error_detail",
    *[f for f in HITL_EXTRA_FIELDS if f != "confidence"],
]


def run_extract_sections(adapter, year: str | None = None) -> Path:
    """
    Para cada PDF físico, localiza cada ley municipal y extrae su sección
    predial. Genera TXT + PDF recortados por (ejercicio, slug).
    """
    pdf_raw_dir = adapter.pdf_raw_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    focus_dir = adapter.focus_dir
    meta_dir = adapter.meta_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    segment_csv = meta_dir / "segment.csv"

    print("═══ Sonora: Segmentación predial ═══")
    if year:
        print(f"    Filtro de ejercicio fiscal: {year}")

    rows: list[dict] = []
    stats = {"total": 0, "found": 0, "fallback": 0, "errors": 0, "from_ocr": 0}

    for anio_pub, raw_pdf in _iter_pdfs(pdf_raw_dir):
        pdf_path = _resolve_best_pdf(raw_pdf, pdf_ocr_dir)
        used_ocr = pdf_path != raw_pdf

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            print(f"    [ERROR] no se pudo abrir {pdf_path.name}: {e}")
            stats["errors"] += 1
            continue

        try:
            leyes = find_leyes_in_pdf(doc, pdf_path)

            if not leyes:
                continue

            for ley in leyes:
                if year and str(ley.ejercicio) != str(year):
                    continue
                if not ley.slug:
                    continue
                stats["total"] += 1
                if used_ocr:
                    stats["from_ocr"] += 1

                year_focus = focus_dir / str(ley.ejercicio)
                year_focus.mkdir(parents=True, exist_ok=True)
                txt_out = year_focus / f"{config.PREFIJO}_PREDIAL_{ley.ejercicio}_{ley.slug}.txt"
                pdf_out = year_focus / f"{config.PREFIJO}_PREDIAL_{ley.ejercicio}_{ley.slug}.pdf"

                seccion = extract_predial_section(doc, ley)
                method = seccion.method
                if method.startswith("fallback"):
                    stats["fallback"] += 1
                    confidence = 0.3
                else:
                    stats["found"] += 1
                    confidence = 0.9

                header = (
                    f"# Estado: {config.ESTADO_NOMBRE}\n"
                    f"# Municipio (slug): {ley.slug}\n"
                    f"# Municipio (raw): {ley.municipio}\n"
                    f"# Ejercicio: {ley.ejercicio}\n"
                    f"# Ley número: {ley.num_ley}\n"
                    f"# Fuente: {pdf_path.name}\n"
                    f"# Páginas ley: {ley.page_start + 1}-{ley.page_end}\n"
                    f"# Páginas predial: {seccion.page_start + 1}-{seccion.page_end}\n"
                    f"# Método detección: {method}\n"
                    f"# Confianza: {confidence:.2f}\n\n"
                )
                txt_content = header + seccion.text
                txt_out.write_text(txt_content, encoding="utf-8")

                try:
                    _save_pdf_slice(doc, seccion.page_start, seccion.page_end, pdf_out)
                except Exception as e:
                    print(f"    [WARN] {pdf_path.name}/{ley.slug}: PDF slice failed ({e})")

                rows.append({
                    **hitl_extra_columns(seccion._seg_result),
                    "ejercicio": ley.ejercicio,
                    "slug": ley.slug,
                    "source_pdf": raw_pdf.name,
                    "focus_file": txt_out.name,
                    "ley_page_start": ley.page_start + 1,
                    "ley_page_end": ley.page_end,
                    "segment_method": method,
                    "page_start": seccion.page_start + 1,
                    "page_end": seccion.page_end,
                    "txt_chars": len(txt_content),
                    "confidence": round(confidence, 3),
                    "error_class": "" if not method.startswith("fallback") else "fallback",
                    "error_detail": "",
                })
        finally:
            doc.close()

    with segment_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_SEGMENT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print("\n  ── Resumen segmentación ──")
    print(f"  Total leyes:   {stats['total']}")
    print(f"  Exacta:        {stats['found']}")
    print(f"  Fallback:      {stats['fallback']}")
    print(f"  Errores:       {stats['errors']}")
    print(f"  Desde OCR:     {stats['from_ocr']}")
    print(f"  Bitácora: {segment_csv}")
    return segment_csv
