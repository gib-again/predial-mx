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
    Fallback: primeras 6 páginas si no se encuentra sección predial.

Particularidades de Oaxaca vs Guanajuato:
  - 570 municipios (vs 46): no se puede tener catálogo completo hardcodeado.
    Los slugs se generan dinámicamente desde el nombre en el PDF.
  - Estructura de PDF: año/mes/filename (vs solo año).
  - Los municipios tienen nombres largos con santo/san/santiago + distrito.
  - La sección predial usa "Sección Primera/Única. Predial" (no "SECCIÓN PRIMERA
    DEL IMPUESTO PREDIAL" como en Guanajuato).
  - El "CAPÍTULO II IMPUESTOS SOBRE EL PATRIMONIO" precede a la sección predial.

Genera:
  data/oaxaca/focus_predial/{ejercicio}/OAX_PREDIAL_{ejercicio}_{slug}.txt
  data/oaxaca/focus_predial/{ejercicio}/OAX_PREDIAL_{ejercicio}_{slug}.pdf
  data/oaxaca/meta/segment.csv
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path

import fitz  # PyMuPDF

from src.core.text_utils import slugify
from src.estados.oaxaca import config


FALLBACK_PAGES = 6
# Máximo de caracteres para el fallback de ley completa.
# ~30k chars ≈ 8-10k tokens, cabe holgado en contexto de gpt-5.2.
FALLBACK_MAX_CHARS = 30_000


# ═══════════════════════════════════════════════════
# Data classes
# ═══════════════════════════════════════════════════

@dataclass
class LeyMunicipal:
    """Resultado de localizar una ley municipal dentro de un PDF del PO."""
    municipio: str          # Nombre como aparece en el PDF
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


# ═══════════════════════════════════════════════════
# Normalización de nombres de municipio
# ═══════════════════════════════════════════════════

def _normalize_municipio_name(raw: str) -> str:
    """
    Normaliza nombre de municipio del PDF al slug canónico.

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
    # (Oaxaca tiene 570 municipios, el catálogo puede estar incompleto)
    return slug


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
    return municipio, distrito


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
                if muni:
                    hits.append((page_idx, muni, dist, last_decreto, last_ejercicio))

    # Deduplicar por slug + ejercicio (primera aparición gana)
    seen: set[str] = set()
    unique: list[tuple[int, str, str, str, int]] = []
    hits.sort(key=lambda x: x[0])

    for page, muni, dist, dec, ej in hits:
        slug = _normalize_municipio_name(muni)
        key = f"{slug}_{ej}"
        if key in seen:
            continue
        seen.add(key)
        unique.append((page, muni, dist, dec, ej))

    # Construir LeyMunicipal con page_end
    leyes: list[LeyMunicipal] = []
    for i, (page, muni, dist, dec, ej) in enumerate(unique):
        slug = _normalize_municipio_name(muni)
        page_end = unique[i + 1][0] if i + 1 < len(unique) else len(doc)

        leyes.append(LeyMunicipal(
            municipio=muni,
            distrito=dist,
            slug=slug,
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
    # → buscar "Predial" después
    m = _RE_PREDIAL_START_CAPITULO.search(text)
    if m:
        # Verificar que hay "predial" relativamente cerca después
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
        # FALLBACK: enviar la ley completa (truncada a FALLBACK_MAX_CHARS).
        # En Oaxaca muchos municipios (usos y costumbres) no cobran predial;
        # necesitamos que el LLM vea toda la ley para confirmar "no_aplica".
        fb_text = full_text[:FALLBACK_MAX_CHARS].strip()
        return SeccionPredial(
            found=True,
            text=fb_text,
            page_start=ley.page_start,
            page_end=ley.page_end,
            method="fallback_ley_completa",
        )

    # ── Buscar fin ──
    end_pos = _find_predial_end(full_text, start_pos)

    if end_pos is None:
        # Sin delimitador de fin: usar máximo 12000 chars desde inicio
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

    print(f"═══ Oaxaca: Segmentación ═══")

    stats = {
        "total": 0, "found_exact": 0, "found_fallback": 0,
        "skipped": 0, "errors": 0,
    }
    all_meta_rows: list[dict] = []

    for ejercicio in range(config.YEAR_MIN, config.YEAR_MAX + 1):
        year_raw_dir = pdf_raw_dir / str(ejercicio)
        if not year_raw_dir.exists():
            continue

        # Buscar PDFs en año y sus subdirectorios (mes)
        pdf_files = sorted(year_raw_dir.rglob("*.pdf")) + sorted(year_raw_dir.rglob("*.PDF"))
        # Deduplicar
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

        year_out = focus_dir / str(ejercicio)
        year_out.mkdir(parents=True, exist_ok=True)

        print(f"\n  [{ejercicio}] {len(pdf_files)} PDFs en pdf_raw/")

        for raw_pdf in pdf_files:
            best_pdf = _resolve_best_pdf(raw_pdf, pdf_ocr_dir, pdf_raw_dir)

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

                if seccion.method.startswith("fallback"):
                    print(f"      {ley.slug}: predial no detectada → {seccion.method}")
                    stats["found_fallback"] += 1
                else:
                    stats["found_exact"] += 1

                # Guardar TXT
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
