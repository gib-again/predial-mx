"""
Segmentación de los PDFs del PO de Oaxaca.

Oaxaca tiene ~570 municipios con leyes de ingresos publicadas en el
Periódico Oficial a lo largo de todo el año. Cada PDF ("Sección") contiene
3-7 leyes de ingresos municipales.

La segmentación tiene dos niveles (como Guanajuato):

  Nivel 1: Localizar cada ley municipal dentro de cada PDF.
    Patrón: "LEY DE INGRESOS DEL MUNICIPIO DE {NOMBRE}, {DISTRITO}, OAXACA"
    El inicio de cada ley se detecta por el encabezado DECRETO + LEY DE INGRESOS.
    Las primeras páginas (portada/sumario) se ignoran.

  Nivel 2: Dentro de cada ley, extraer la sección de predial.
    Inicio (en orden de prioridad):
      1) "Sección Primera. Predial" o "Sección Única. Predial"
      2) "CAPÍTULO I/II ... IMPUESTOS SOBRE EL PATRIMONIO" + "Predial"
      3) "DEL IMPUESTO PREDIAL" / "Artículo N ... predial"
    Fin:
      1) "Sección Segunda" (Fraccionamiento / Fusión / Traslación)
      2) "CAPÍTULO II/III ... IMPUESTOS SOBRE LA PRODUCCIÓN"
      3) "IMPUESTOS SOBRE EL CONSUMO Y LAS TRANSACCIONES"
    Fallback: primeras páginas siguientes al inicio si no se encuentra un final
    válido, o ley completa truncada si no se detecta la sección predial.

Particularidades de Oaxaca vs Guanajuato:
  - 570 municipios (vs 46): no se puede tener catálogo completo hardcodeado.
    Los slugs se generan dinámicamente desde el nombre en el PDF o desde el
    índice HTML ya curado (oaxaca_index.csv).
  - Estructura de PDF: año/mes/filename (vs solo año).
  - Los municipios tienen nombres largos con santo/san/santiago + distrito.
  - La sección predial usa "Sección Primera/Única. Predial".
  - El mapeo de municipio/ejercicio proviene prioritariamente de
    data/oaxaca/meta/oaxaca_index.csv; la localización de páginas se sigue
    haciendo sobre la versión OCR del PDF.

Genera:
  data/oaxaca/focus_predial/{ejercicio_fiscal}/OAX_PREDIAL_{ejercicio}_{slug}.txt
  data/oaxaca/focus_predial/{ejercicio_fiscal}/OAX_PREDIAL_{ejercicio}_{slug}.pdf
  data/oaxaca/meta/segment.csv
"""

from __future__ import annotations

import csv
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from src.core.text_utils import slugify
from src.estados.oaxaca import config


FALLBACK_PAGES = 6
# Cuando el rango inicio/fin detectado no es válido, recortar al menos 3 páginas
# a partir del inicio. Esto evita page_end <= page_start.
MIN_VALID_RANGE_PAGES = 3
# Máximo de caracteres para el fallback de ley completa.
# ~30k chars ≈ 8-10k tokens, cabe holgado en contexto de gpt-5.2.
FALLBACK_MAX_CHARS = 30_000


# ═══════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════

@dataclass
class LeyMunicipal:
    """Resultado de localizar una ley municipal dentro de un PDF del PO."""
    municipio: str          # Nombre como aparece en el PDF o índice
    distrito: str           # Distrito judicial
    slug: str               # Slug normalizado
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
    method: str = ""


@dataclass
class IndexLey:
    """Registro proveniente de oaxaca_index.csv."""
    municipio: str
    distrito: str
    ejercicio: int | None
    href_pdf: str
    slug: str


# ═══════════════════════════════════════════════════
# Normalización de nombres de municipio
# ═══════════════════════════════════════════════════


def _normalize_municipio_name(raw: str) -> str:
    """
    Normaliza nombre de municipio al slug canónico.

    Oaxaca tiene nombres largos como:
      "SANTO DOMINGO YANHUITLÁN"
      "SAN PEDRO MÁRTIR YUCUXACO"
      "SANTIAGO IHUITLÁN PLUMAS"
    """
    name = raw.strip().rstrip(",").strip()
    name = re.sub(r"\s+", " ", name, flags=re.UNICODE)

    slug = slugify(name)
    slug = re.sub(r"[^a-z0-9_]+", "_", slug)
    slug = re.sub(r"_+", "_", slug).strip("_")

    # Aliases
    if slug in config.ALIASES:
        return config.ALIASES[slug]

    # Match directo en catálogo cargado
    slug_to_cve = config.get_slug_to_cve()
    if slug in slug_to_cve:
        return slug

    # Match por nombre oficial
    name_to_slug = config.get_name_to_slug()
    upper = name.upper().strip()
    if upper in name_to_slug:
        return name_to_slug[upper]

    # Si no está en catálogo, retornar el slug tal cual
    return slug


# Reverse map solo para distritos faltantes cuando municipio ya quedó limpio.
_SLUG_TO_NAME_UPPER = {
    slug: nombre.upper().strip()
    for slug, (_, nombre) in config.get_slug_to_cve().items()
}


def _split_municipio_distrito(text: str) -> tuple[str, str]:
    """
    Separa nombre de municipio y distrito.
    Ejemplo: "SANTO DOMINGO YANHUITLÁN, NOCHIXTLÁN, OAXACA"
           → ("SANTO DOMINGO YANHUITLÁN", "NOCHIXTLÁN")
    """
    text = re.sub(r"\s+", " ", text or "").strip().rstrip(".")
    parts = [p.strip(" ,.") for p in text.split(",") if p.strip(" ,.")]

    # Quitar "OAXACA" al final
    if parts and parts[-1].upper() == "OAXACA":
        parts = parts[:-1]

    municipio = parts[0] if parts else ""
    distrito = parts[1] if len(parts) >= 2 else ""
    distrito = re.sub(r"^DISTRITO\s+DE\s+", "", distrito, flags=re.IGNORECASE).strip()
    return municipio, distrito


# ═══════════════════════════════════════════════════
# Índice HTML curado (oaxaca_index.csv)
# ═══════════════════════════════════════════════════


def _to_int(value: object) -> int | None:
    s = str(value or "").strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def _canonical_pdf_key_from_href(href_pdf: str) -> str:
    href = (href_pdf or "").strip().replace("\\", "/")
    href = href.lstrip("/")
    if href.lower().startswith("files/"):
        href = href[6:]
    return href


def _load_index_map(meta_dir: Path) -> tuple[dict[str, list[IndexLey]], dict[str, list[IndexLey]]]:
    """Carga oaxaca_index.csv y lo agrupa por ruta relativa y por basename."""
    index_csv = meta_dir / "oaxaca_index.csv"
    by_rel: dict[str, list[IndexLey]] = defaultdict(list)
    by_name: dict[str, list[IndexLey]] = defaultdict(list)

    if not index_csv.exists():
        return {}, {}

    with index_csv.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            href_pdf = (row.get("href_pdf") or "").strip()
            if not href_pdf:
                continue

            municipio = (row.get("municipio") or "").strip()
            distrito = (row.get("distrito") or "").strip()
            ejercicio = _to_int(row.get("ejercicio_fiscal"))
            slug = _normalize_municipio_name(municipio) if municipio else ""

            item = IndexLey(
                municipio=municipio,
                distrito=distrito,
                ejercicio=ejercicio,
                href_pdf=href_pdf,
                slug=slug,
            )

            rel_key = _canonical_pdf_key_from_href(href_pdf)
            by_rel[rel_key].append(item)
            by_name[Path(rel_key).name].append(item)

    return dict(by_rel), dict(by_name)


def _lookup_index_rows(
    raw_pdf: Path,
    pdf_raw_dir: Path,
    index_by_rel: dict[str, list[IndexLey]],
    index_by_name: dict[str, list[IndexLey]],
) -> list[IndexLey]:
    rel_key = raw_pdf.relative_to(pdf_raw_dir).as_posix()
    if rel_key in index_by_rel:
        return index_by_rel[rel_key]
    return index_by_name.get(raw_pdf.name, [])


def _fill_district_from_catalog(municipio: str, distrito: str) -> str:
    """Completa distrito solo en casos triviales; homónimos se dejan igual."""
    if distrito.strip():
        return distrito.strip()

    slug = _normalize_municipio_name(municipio)
    if not slug:
        return ""

    if slug in config.HOMONIMOS:
        return ""

    # No hay un catálogo distrito→municipio en config; dejar vacío es mejor que inventar.
    _ = _SLUG_TO_NAME_UPPER.get(slug)
    return ""


def _sanitize_page_range(
    start: int,
    end: int,
    doc_len: int,
    *,
    upper_bound: int | None = None,
    fallback_pages: int = MIN_VALID_RANGE_PAGES,
) -> tuple[int, int]:
    """
    Normaliza un rango [start, end) de páginas.

    Reglas:
      - start siempre dentro del documento.
      - end siempre > start.
      - si end <= start, usar fallback de `fallback_pages` páginas después del inicio.
      - si upper_bound está dado, end no puede rebasarlo.
    """
    if doc_len <= 0:
        return 0, 0

    start = max(0, min(int(start), doc_len - 1))

    limit = doc_len if upper_bound is None else min(max(upper_bound, 0), doc_len)
    if limit <= start:
        limit = doc_len

    try:
        end = int(end)
    except Exception:
        end = start

    end = max(0, min(end, limit))
    if end <= start:
        end = min(start + fallback_pages, limit)
    if end <= start:
        end = min(start + 1, doc_len)

    return start, end


def _merge_ocr_and_index(
    leyes_ocr: list[LeyMunicipal],
    index_rows: list[IndexLey],
    pdf_path: Path,
    doc_len: int,
    default_ejercicio: int,
) -> list[LeyMunicipal]:
    """
    Usa el índice curado como fuente de verdad para municipio/ejercicio,
    pero conserva page_start/page_end detectados en OCR.

    El matching es por orden dentro del mismo PDF, porque el índice HTML ya
    viene separado por decreto/municipio dentro de cada sección del PO.
    """
    if not leyes_ocr:
        return []

    # Si no existe índice para este PDF, usar OCR tal cual (saneando rangos).
    if not index_rows:
        out: list[LeyMunicipal] = []
        for ley in leyes_ocr:
            p_start, p_end = _sanitize_page_range(ley.page_start, ley.page_end, doc_len)
            out.append(LeyMunicipal(
                municipio=ley.municipio,
                distrito=_fill_district_from_catalog(ley.municipio, ley.distrito),
                slug=ley.slug,
                decreto=ley.decreto,
                ejercicio=ley.ejercicio or default_ejercicio,
                page_start=p_start,
                page_end=p_end,
                pdf_path=pdf_path,
            ))
        return out

    pair_count = min(len(leyes_ocr), len(index_rows))
    merged: list[LeyMunicipal] = []

    for i in range(pair_count):
        ocr = leyes_ocr[i]
        idx = index_rows[i]

        municipio = idx.municipio or ocr.municipio
        distrito = idx.distrito or ocr.distrito
        distrito = _fill_district_from_catalog(municipio, distrito)
        ejercicio = idx.ejercicio or ocr.ejercicio or default_ejercicio
        slug = idx.slug or _normalize_municipio_name(municipio or ocr.municipio)

        p_start, p_end = _sanitize_page_range(ocr.page_start, ocr.page_end, doc_len)

        merged.append(LeyMunicipal(
            municipio=municipio,
            distrito=distrito,
            slug=slug,
            decreto=ocr.decreto,
            ejercicio=ejercicio,
            page_start=p_start,
            page_end=p_end,
            pdf_path=pdf_path,
        ))

    return merged


# ═══════════════════════════════════════════════════
# Nivel 1: Localizar leyes municipales
# ═══════════════════════════════════════════════════

# Patrón principal: "LEY DE INGRESOS DEL MUNICIPIO DE X, DISTRITO, OAXACA"
# re.DOTALL para que \s+ capture newlines dentro del nombre del municipio
_RE_LEY_INICIO = re.compile(
    r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+"
    r"([\w\sÁÉÍÓÚÑÜáéíóúñü\.\,]+?)"
    r"(?:\s*,\s*OAXACA\s*,?\s*PARA\s+EL\s+EJERCICIO"
    r"|\s*,\s*PARA\s+EL\s+EJERCICIO"
    r"|\s*,\s*DISTRITO\s+DE)",
    re.IGNORECASE | re.DOTALL,
)

# Variante más laxa: "LEY DE INGRESOS DEL MUNICIPIO DE X, DISTRITO DE Y"
_RE_LEY_INICIO_LAXO = re.compile(
    r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+"
    r"([\w\sÁÉÍÓÚÑÜáéíóúñü\.\,]+?)"
    r"\s*,\s*([\w\sÁÉÍÓÚÑÜáéíóúñü]+?)\s*,\s*OAXACA",
    re.IGNORECASE,
)

# Patrón para decreto
_RE_DECRETO = re.compile(
    r"DECRETO\s+(?:No\.?|N[oúu]m\.?)\s*([0-9A-Z\-\.]+)",
    re.IGNORECASE,
)

# Patrón para ejercicio fiscal
_RE_EJERCICIO = re.compile(
    r"EJERCICIO\s+FISCAL\s+(?:DEL?\s+A[ÑN]O\s+)?(\d{4})",
    re.IGNORECASE,
)


def _detect_skip_pages(doc: fitz.Document, max_check: int = 3) -> int:
    """Auto-detecta cuántas páginas de portada/sumario saltar."""
    for i in range(min(max_check, len(doc))):
        text = (doc[i].get_text("text") or "").upper()
        if "SUMARIO" in text or "ÍNDICE" in text or "INDICE" in text:
            return i + 1
    return 1  # Default: saltar solo portada


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
    hits: list[tuple[int, str, str, str, int]] = []  # (page, muni, dist, decreto, ej)
    last_decreto = ""
    last_ejercicio = default_ejercicio or 0

    for page_idx in range(skip_pages, len(doc)):
        text = doc[page_idx].get_text("text")
        if not text:
            continue

        # Buscar decretos
        for m in _RE_DECRETO.finditer(text):
            last_decreto = m.group(1).strip().rstrip(".-").strip()

        # Buscar ejercicio fiscal
        for m in _RE_EJERCICIO.finditer(text):
            try:
                last_ejercicio = int(m.group(1))
            except ValueError:
                pass

        # Buscar inicio de ley — patrón principal
        for m in _RE_LEY_INICIO.finditer(text):
            rest = m.group(1).strip()
            muni, dist = _split_municipio_distrito(rest)
            if muni:
                hits.append((page_idx, muni, dist, last_decreto, last_ejercicio))

        # Buscar con patrón laxo si el principal no encontró nada en esta página
        if not any(h[0] == page_idx for h in hits):
            for m in _RE_LEY_INICIO_LAXO.finditer(text):
                muni = m.group(1).strip().rstrip(",").strip()
                dist = m.group(2).strip()
                dist = re.sub(r"^DISTRITO\s+DE\s+", "", dist, flags=re.IGNORECASE).strip()
                if muni:
                    hits.append((page_idx, muni, dist, last_decreto, last_ejercicio))

    # Deduplicar por slug + ejercicio + página (primera aparición gana)
    seen: set[str] = set()
    unique: list[tuple[int, str, str, str, int]] = []
    hits.sort(key=lambda x: x[0])

    for page, muni, dist, dec, ej in hits:
        slug = _normalize_municipio_name(muni)
        key = f"{page}|{slug}_{ej}"
        if key in seen:
            continue
        seen.add(key)
        unique.append((page, muni, dist, dec, ej))

    # Construir LeyMunicipal con page_end
    leyes: list[LeyMunicipal] = []
    for i, (page, muni, dist, dec, ej) in enumerate(unique):
        slug = _normalize_municipio_name(muni)
        page_end = unique[i + 1][0] if i + 1 < len(unique) else len(doc)
        page_start, page_end = _sanitize_page_range(page, page_end, len(doc))

        leyes.append(LeyMunicipal(
            municipio=muni,
            distrito=dist,
            slug=slug,
            decreto=dec,
            ejercicio=ej,
            page_start=page_start,
            page_end=page_end,
            pdf_path=pdf_path,
        ))

    return leyes


# ═══════════════════════════════════════════════════
# Nivel 2: Extraer sección predial
# ═══════════════════════════════════════════════════

# Inicio de sección predial — ORDEN DE PRIORIDAD:
#
# 1) "Sección Primera. Predial" o "Sección Única. Predial"
_RE_PREDIAL_START_SECCION = re.compile(
    r"SECCI[OÓ]N\s+(?:PRIMERA|[UÚ]NICA)[.\s\-:]*\s*(?:DEL\s+)?(?:IMPUESTO\s+)?PREDIAL",
    re.IGNORECASE,
)

# 2) "CAPÍTULO I/II ... IMPUESTOS SOBRE EL PATRIMONIO" seguido de predial
_RE_PREDIAL_START_CAPITULO = re.compile(
    r"CAP[IÍ]TULO\s+(?:I{1,3}|PRIMERO|SEGUNDO)\s*[.\s\-:]*\s*"
    r"IMPUESTOS\s+SOBRE\s+EL\s+PATRIMONIO",
    re.IGNORECASE,
)

# 3) "DEL IMPUESTO PREDIAL" o "Artículo N ... predial"
_RE_PREDIAL_START_STANDALONE = re.compile(
    r"(?:DEL\s+)?IMPUESTO\s+PREDIAL",
    re.IGNORECASE,
)

# 4) Artículo que menciona "impuesto predial"
_RE_PREDIAL_START_ARTICULO = re.compile(
    r"ART[IÍ]CULO\s+\d+[.\s]+.*?(?:impuesto\s+)?predial\s+(?:se\s+determinar[aá]|"
    r"la\s+contribuci[oó]n|percibe\s+el\s+Municipio)",
    re.IGNORECASE,
)

# Contextos que NO son inicio de predial (tabla de estimación, índice, sumario)
_RE_FALSE_POSITIVE = re.compile(
    r"(?:CONCEPTO|ESTIMACI[OÓ]N|CLASIFICADOR|DISPOSICIONES\s+GENERALES|"
    r"SUMARIO|INGRESOS\s+ESTIMADOS|IMPUESTOS\s+SOBRE\s+EL\s+PATRIMONIO\s+\d)",
    re.IGNORECASE,
)

# Fin de sección predial
_RE_PREDIAL_END_SECCION = re.compile(
    r"SECCI[OÓ]N\s+SEGUNDA[.\s\-:]*\s*(?:FRACCIONAMIENTO|FUSI[OÓ]N|TRASLACI[OÓ]N)",
    re.IGNORECASE,
)

_RE_PREDIAL_END_CAPITULO = re.compile(
    r"CAP[IÍ]TULO\s+(?:II|III|SEGUNDO|TERCERO)\s*[.\s\-:]*\s*"
    r"(?:IMPUESTOS\s+SOBRE\s+(?:LA\s+PRODUCCI[OÓ]N|EL\s+CONSUMO|TRASLACI[OÓ]N))",
    re.IGNORECASE,
)

_RE_PREDIAL_END_TRASLACION = re.compile(
    r"(?:DEL\s+)?IMPUESTO\s+(?:SOBRE\s+)?TRASLACI[OÓ]N\s+DE\s+DOMINIO",
    re.IGNORECASE,
)

_RE_PREDIAL_END_FRACCIONAMIENTO = re.compile(
    r"SECCI[OÓ]N\s+SEGUNDA[.\s\-:]*\s*FRACCIONAMIENTO",
    re.IGNORECASE,
)


def _find_predial_start(text: str) -> tuple[int | None, str]:
    """Busca inicio de sección predial. Retorna (posición, método) o (None, "")."""

    # 1) Sección Primera/Única. Predial
    m = _RE_PREDIAL_START_SECCION.search(text)
    if m:
        return m.start(), "seccion_predial"

    # 2) Capítulo N ... Impuestos Sobre el Patrimonio
    m = _RE_PREDIAL_START_CAPITULO.search(text)
    if m:
        after = text[m.start():m.start() + 3000]
        if re.search(r"PREDIAL", after, re.IGNORECASE):
            return m.start(), "capitulo_patrimonio"

    # 3) "DEL IMPUESTO PREDIAL" standalone (con filtro de falsos positivos)
    for m in _RE_PREDIAL_START_STANDALONE.finditer(text):
        context_before = text[max(0, m.start() - 200): m.start()]
        if not _RE_FALSE_POSITIVE.search(context_before):
            return m.start(), "impuesto_predial"

    # 4) Artículo que menciona predial
    m = _RE_PREDIAL_START_ARTICULO.search(text)
    if m:
        return m.start(), "articulo_predial"

    return None, ""


def _find_predial_end(text: str, start_pos: int) -> int | None:
    """Busca fin de sección predial DESPUÉS de start_pos."""
    remaining = text[start_pos:]
    candidates: list[int] = []

    for pattern in [
        _RE_PREDIAL_END_SECCION,
        _RE_PREDIAL_END_CAPITULO,
        _RE_PREDIAL_END_TRASLACION,
        _RE_PREDIAL_END_FRACCIONAMIENTO,
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
    Si no se encuentra, devuelve la ley completa truncada.
    """
    pages_text: list[tuple[int, str]] = []
    for p in range(ley.page_start, ley.page_end):
        text = doc[p].get_text("text")
        if text:
            pages_text.append((p, text))

    if not pages_text:
        p_start, p_end = _sanitize_page_range(
            ley.page_start,
            ley.page_end,
            len(doc),
            upper_bound=ley.page_end,
        )
        return SeccionPredial(found=False, method="no_text", page_start=p_start, page_end=p_end)

    full_text = "\n".join(t for _, t in pages_text)

    # ── Buscar inicio ──
    start_pos, method = _find_predial_start(full_text)

    if start_pos is None:
        fb_text = full_text[:FALLBACK_MAX_CHARS].strip()
        p_start, p_end = _sanitize_page_range(
            ley.page_start,
            ley.page_end,
            len(doc),
            upper_bound=ley.page_end,
        )
        return SeccionPredial(
            found=True,
            text=fb_text,
            page_start=p_start,
            page_end=p_end,
            method="fallback_ley_completa",
        )

    # ── Buscar fin ──
    end_pos = _find_predial_end(full_text, start_pos)

    if end_pos is None:
        end_pos = min(start_pos + 12000, len(full_text))

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

    p_start, p_end = _sanitize_page_range(
        p_start,
        p_end,
        len(doc),
        upper_bound=ley.page_end,
    )

    return SeccionPredial(
        found=True,
        text=section_text,
        page_start=p_start,
        page_end=p_end,
        method=method,
    )


# ═══════════════════════════════════════════════════
# Resolución de PDF fuente (prioridad: ocr > raw)
# ═══════════════════════════════════════════════════


def _resolve_best_pdf(raw_pdf: Path, ocr_dir: Path, raw_dir: Path) -> Path:
    """
    Dado un PDF raw, retorna la mejor versión disponible:
      1. _ocr.pdf (OCR procesado)
      2. original (si no hay versión OCR)

    Preserva la estructura año/mes de Oaxaca.
    """
    relative = raw_pdf.relative_to(raw_dir)
    ocr_path = ocr_dir / relative.parent / (raw_pdf.stem + "_ocr.pdf")
    if ocr_path.exists():
        return ocr_path
    return raw_pdf


# ═══════════════════════════════════════════════════
# Meta CSV
# ═══════════════════════════════════════════════════

_META_FIELDS = [
    "ejercicio", "municipio", "distrito", "slug", "decreto",
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

    Oaxaca tiene estructura: pdf_raw/{año}/{mes}/{filename}.pdf
    A diferencia de Guanajuato, hay subdirectorios por mes.

    Returns:
        Path al CSV de metadatos de segmentación.
    """
    pdf_raw_dir = adapter.pdf_raw_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    focus_dir = adapter.focus_dir
    meta_dir = adapter.meta_dir

    index_by_rel, index_by_name = _load_index_map(meta_dir)

    print("═══ Oaxaca: Segmentación ═══")

    stats = {
        "total": 0,
        "found_exact": 0,
        "found_fallback": 0,
        "skipped": 0,
        "errors": 0,
        "pdfs_with_index": 0,
        "pdfs_count_mismatch": 0,
    }
    all_meta_rows: list[dict] = []

    for pub_year in range(config.YEAR_MIN, config.YEAR_MAX + 1):
        year_raw_dir = pdf_raw_dir / str(pub_year)
        if not year_raw_dir.exists():
            continue

        pdf_files = sorted(year_raw_dir.rglob("*.pdf")) + sorted(year_raw_dir.rglob("*.PDF"))
        seen_paths: set[str] = set()
        unique_pdfs: list[Path] = []
        for p in pdf_files:
            key = str(p).lower()
            if key not in seen_paths:
                seen_paths.add(key)
                unique_pdfs.append(p)
        pdf_files = unique_pdfs

        if not pdf_files:
            continue

        print(f"\n  [{pub_year}] {len(pdf_files)} PDFs en pdf_raw/")

        for raw_pdf in pdf_files:
            best_pdf = _resolve_best_pdf(raw_pdf, pdf_ocr_dir, pdf_raw_dir)

            try:
                doc = fitz.open(str(best_pdf))
            except Exception as e:
                print(f"    ERROR abriendo {best_pdf.name}: {e}")
                stats["errors"] += 1
                continue

            skip_n = _detect_skip_pages(doc)
            index_rows = _lookup_index_rows(raw_pdf, pdf_raw_dir, index_by_rel, index_by_name)
            if index_rows:
                stats["pdfs_with_index"] += 1

            # Nivel 1: encontrar leyes (sobre OCR)
            leyes_ocr = find_leyes_in_pdf(
                doc,
                best_pdf,
                skip_pages=skip_n,
                default_ejercicio=pub_year,
            )
            leyes = _merge_ocr_and_index(
                leyes_ocr,
                index_rows,
                best_pdf,
                len(doc),
                default_ejercicio=pub_year,
            )

            if index_rows and len(leyes_ocr) != len(index_rows):
                stats["pdfs_count_mismatch"] += 1
                print(
                    f"    {best_pdf.name}: OCR={len(leyes_ocr)} vs index={len(index_rows)} "
                    f"(se emparejan {min(len(leyes_ocr), len(index_rows))})"
                )

            if not leyes:
                doc.close()
                continue

            print(f"    {best_pdf.name}: {len(leyes)} leyes (skip={skip_n}pp)")

            for ley in leyes:
                stats["total"] += 1
                ej = ley.ejercicio or pub_year
                year_out = focus_dir / str(ej)
                year_out.mkdir(parents=True, exist_ok=True)

                txt_path = year_out / f"{config.PREFIJO}_PREDIAL_{ej}_{ley.slug}.txt"
                pdf_out = year_out / f"{config.PREFIJO}_PREDIAL_{ej}_{ley.slug}.pdf"

                if txt_path.exists() and not force:
                    stats["skipped"] += 1
                    all_meta_rows.append({
                        "ejercicio": ej,
                        "municipio": ley.municipio,
                        "distrito": ley.distrito,
                        "slug": ley.slug,
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
                p_start, p_end = _sanitize_page_range(
                    seccion.page_start,
                    seccion.page_end,
                    len(doc),
                    upper_bound=ley.page_end,
                )
                seccion.page_start = p_start
                seccion.page_end = p_end

                if seccion.method.startswith("fallback"):
                    print(f"      {ley.slug}: predial no detectada → {seccion.method}")
                    stats["found_fallback"] += 1
                else:
                    stats["found_exact"] += 1

                header = (
                    f"# Municipio: {ley.municipio}\n"
                    f"# Distrito: {ley.distrito}\n"
                    f"# Estado: Oaxaca\n"
                    f"# Ejercicio: {ej}\n"
                    f"# Decreto: {ley.decreto}\n"
                    f"# Fuente: {best_pdf.name}\n"
                    f"# Páginas ley: {ley.page_start + 1}-{ley.page_end}\n"
                    f"# Páginas predial: {seccion.page_start + 1}-{seccion.page_end}\n"
                    f"# Método detección: {seccion.method}\n\n"
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
                    print(f"      {ley.slug}: Error guardando PDF: {e}")

                all_meta_rows.append({
                    "ejercicio": ej,
                    "municipio": ley.municipio,
                    "distrito": ley.distrito,
                    "slug": ley.slug,
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

    if all_meta_rows:
        csv_path = _write_meta_csv(meta_dir, all_meta_rows)
        print(f"\n  Meta: {csv_path.name} ({len(all_meta_rows)} filas)")

    print("\n  ── Resumen ──")
    print(f"  Total: {stats['total']}")
    print(f"  Predial exacta: {stats['found_exact']}")
    print(f"  Predial fallback: {stats['found_fallback']}")
    print(f"  Ya existían: {stats['skipped']}")
    print(f"  PDFs con índice: {stats['pdfs_with_index']}")
    print(f"  PDFs con desajuste OCR/index: {stats['pdfs_count_mismatch']}")
    print(f"  Errores: {stats['errors']}")

    return meta_dir / "segment.csv"
