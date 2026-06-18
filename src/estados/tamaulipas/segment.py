"""
Segmentación del PO consolidado de Tamaulipas.

Cada PDF consolidado contiene las leyes de ingresos de los 43 municipios.
La segmentación tiene dos niveles:

  Nivel 1: Localizar inicio de cada ley municipal.
    Patrón: "LEY DE INGRESOS DEL MUNICIPIO DE {NOMBRE}"
    o: "LEY DE INGRESOS PARA EL MUNICIPIO DE {NOMBRE}"
    Precedido por "D E C R E T O No. {NUM}"
    Las primeras páginas (índice/sumario) se IGNORAN.
    La cantidad depende del año (1 página en 2019-2022 y 2024-2025; 2 en el resto).

  Nivel 2: Dentro de cada ley, extraer la sección de predial.
    Inicio (en orden de prioridad):
      1) "(DEL )IMPUESTO SOBRE LA PROPIEDAD URBANA" + ", SUBURBANA"
      2) "SECCIÓN ... DEL IMPUESTO SOBRE LA PROPIEDAD"
      3) "IMPUESTOS? SOBRE EL PATRIMONIO"
    Fin:
      1) "ADQUISICIÓN DE INMUEBLES" (como header de sección)
      2) "SECCIÓN TERCERA"
    Si NO se encuentra sección predial → primeras 5 páginas de la ley (LLM fallback).

IMPORTANTE: En Tamaulipas el predial casi NUNCA se llama "impuesto predial".
El nombre oficial es "IMPUESTO SOBRE LA PROPIEDAD URBANA, SUBURBANA Y RÚSTICA".
En municipios pequeños (Burgos, Mainero, etc.) el header NO lleva "DEL" al inicio:
  "IMPUESTO SOBRE LA PROPIEDAD URBANA, SUBURBANA Y RÚSTICA"
En municipios grandes (Reynosa, Victoria, etc.) suele llevar:
  "DEL IMPUESTO SOBRE LA PROPIEDAD URBANA, SUBURBANA Y RÚSTICA"

Genera:
  data/tamaulipas/focus_predial/{ejercicio}/TAMPS_PREDIAL_{ejercicio}_{slug}.txt
  data/tamaulipas/focus_predial/{ejercicio}/TAMPS_PREDIAL_{ejercicio}_{slug}.pdf
  data/tamaulipas/meta/segment.csv
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
from src.estados.tamaulipas import config


# ── Páginas a ignorar (índice/sumario) ──
# Años con solo 1 página de sumario:
_SKIP_1_PAGE_YEARS = set(range(2019, 2023)) | {2024, 2025}
# El resto (2010-2018, 2023) tiene 2 páginas de sumario.

FALLBACK_PAGES = 5


def _skip_pages_for_year(year: int) -> int:
    """Devuelve cuántas páginas de sumario ignorar para un ejercicio dado."""
    return 1 if year in _SKIP_1_PAGE_YEARS else 2


# ══════════════════════════════════════════════════════════════
# Data classes
# ══════════════════════════════════════════════════════════════

@dataclass
class LeyMunicipal:
    """Resultado de localizar una ley municipal dentro del tomo."""
    municipio: str          # Nombre como aparece en el PDF
    slug: str               # Slug normalizado
    cve_mun: str            # Clave INEGI
    decreto: str            # Número de decreto
    page_start: int         # Página 0-indexed donde inicia la ley
    page_end: int           # Página 0-indexed donde termina (exclusivo)


@dataclass
class SeccionPredial:
    """Resultado de localizar la sección predial dentro de una ley."""
    found: bool
    text: str = ""
    page_start: int = -1
    page_end: int = -1
    method: str = ""        # "propiedad_urbana" | "patrimonio_fallback" | "fallback_Npp"
    _seg_result: SegmentResult | None = None


# ══════════════════════════════════════════════════════════════
# Normalización de nombres de municipio
# ══════════════════════════════════════════════════════════════

_matcher = MuniMatcher(cve_ent=config.CVE_ENT, aliases=config.ALIASES)


def _normalize_municipio_name(raw: str) -> str:
    """Normaliza nombre de municipio del PDF al slug canónico."""
    name = raw.strip().rstrip(",").strip()
    name = re.sub(r"\s+", " ", name, flags=re.UNICODE)
    result = _matcher.match(name)
    return result.slug


# ══════════════════════════════════════════════════════════════
# Nivel 1: Localizar leyes municipales
# ══════════════════════════════════════════════════════════════

# Patrón para detectar inicio de cada ley municipal.
_RE_LEY_INICIO = re.compile(
    r"LEY\s+DE\s+INGRESOS\s+(?:DEL|PARA\s+EL)\s+MUNICIPIO\s+DE\s+"
    r"([A-ZÁÉÍÓÚÑÜ][A-ZÁÉÍÓÚÑÜ\s\.]+?)"
    r"[,\s]+TAMAULIPAS",
    re.IGNORECASE,
)

# Patrón para decreto (precede cada ley)
_RE_DECRETO = re.compile(
    r"D\s*E\s*C\s*R\s*E\s*T\s*O\s+(?:No\.|N[oúu]m\.?)\s*([0-9A-Z\-]+)",
    re.IGNORECASE,
)


def find_leyes_municipales(
    doc: fitz.Document,
    skip_pages: int = 2,
) -> list[LeyMunicipal]:
    """
    Escanea el PDF consolidado y localiza el inicio de cada ley municipal.
    Ignora las primeras `skip_pages` páginas (índice/sumario).
    Retorna lista ordenada por page_start.
    """
    hits: list[tuple[int, str, str]] = []  # (page, municipio_raw, decreto)
    last_decreto = ""

    for page_idx in range(skip_pages, len(doc)):
        text = doc[page_idx].get_text("text")
        if not text:
            continue

        # Buscar decretos en esta página
        for m in _RE_DECRETO.finditer(text):
            last_decreto = m.group(1).strip()

        # Buscar inicio de ley
        for m in _RE_LEY_INICIO.finditer(text):
            muni_raw = m.group(1).strip()
            hits.append((page_idx, muni_raw, last_decreto))

    # Deduplicar por slug: primera aparición gana
    seen: dict[str, bool] = {}
    unique_hits: list[tuple[int, str, str]] = []
    hits.sort(key=lambda x: x[0])

    for page, muni, dec in hits:
        slug = _normalize_municipio_name(muni)
        if slug in seen:
            continue
        seen[slug] = True
        unique_hits.append((page, muni, dec))

    # Construir LeyMunicipal con page_end = inicio de siguiente ley
    leyes: list[LeyMunicipal] = []
    for i, (page, muni, dec) in enumerate(unique_hits):
        slug = _normalize_municipio_name(muni)
        cve_mun = config.SLUG_TO_CVE.get(slug, ("???",))[0] if slug in config.SLUG_TO_CVE else "???"

        if i + 1 < len(unique_hits):
            page_end = unique_hits[i + 1][0]
        else:
            page_end = len(doc)

        leyes.append(LeyMunicipal(
            municipio=muni,
            slug=slug,
            cve_mun=cve_mun,
            decreto=dec,
            page_start=page,
            page_end=page_end,
        ))

    return leyes


# ══════════════════════════════════════════════════════════════
# Nivel 2: Extraer sección predial (usa segment_utils compartido)
# ══════════════════════════════════════════════════════════════

# Patrones de inicio — TAMAULIPAS usa "PROPIEDAD URBANA, SUBURBANA" no "PREDIAL"
_TAMPS_START_SPECS = [
    # 1) "(DEL) IMPUESTO SOBRE LA PROPIEDAD URBANA, SUBURBANA"
    #    El ", SUBURBANA" evita falsos positivos de la tabla de estimación
    PatternSpec(re.compile(
        r"(?:DEL\s+)?IMPUESTO\s+SOBRE\s+LA\s+PROPIEDAD\s+URBANA"
        r"[,\s]+SUBURBANA",
        re.IGNORECASE,
    ), "propiedad_urbana"),
    # 2) "SECCIÓN X DEL IMPUESTO SOBRE LA PROPIEDAD..."
    PatternSpec(re.compile(
        r"SECCI[OÓ]N\s+\w+\s+(?:DEL\s+)?IMPUESTO\s+SOBRE\s+LA\s+PROPIEDAD\s+"
        r"(?:URBANA|INMOBILIARIA|RA[IÍ]Z)",
        re.IGNORECASE,
    ), "seccion_propiedad"),
    # 3) Fallback: "IMPUESTOS SOBRE EL PATRIMONIO"
    PatternSpec(re.compile(
        r"IMPUESTOS?\s+SOBRE\s+EL\s+PATRIMONIO",
        re.IGNORECASE,
    ), "patrimonio_fallback"),
]

_TAMPS_END_SPECS = [
    PatternSpec(re.compile(
        r"(?:DEL\s+)?IMPUESTO\s+SOBRE\s+ADQUISICI[OÓ]N\s+DE\s+INMUEBLES",
        re.IGNORECASE,
    ), "adquisicion"),
    PatternSpec(re.compile(
        r"SECCI[OÓ]N\s+TERCERA",
        re.IGNORECASE,
    ), "seccion_tercera"),
]

# Blacklist: tabla de estimación "1210 IMPUESTO SOBRE LA PROPIEDAD URBANA" (sin SUBURBANA)
_TAMPS_BLACKLIST = [
    re.compile(r"(?:1210\b|ESTIMACI[OÓ]N|CLASIFICADOR)", re.IGNORECASE),
]


def extract_predial_section(
    doc: fitz.Document,
    ley: LeyMunicipal,
) -> SeccionPredial:
    """
    Extrae la sección de predial de una ley municipal.
    Si no se encuentra, devuelve las primeras FALLBACK_PAGES páginas de la ley.
    """
    pages_text: list[tuple[int, str]] = []
    for p in range(ley.page_start, ley.page_end):
        text = doc[p].get_text("text")
        if text:
            pages_text.append((p, text))

    if not pages_text:
        return SeccionPredial(found=False, method="no_text")

    full_text = "\n".join(t for _, t in pages_text)

    # ── Usar localizador compartido ──
    result = find_predial_section(
        text=full_text,
        start_specs=_TAMPS_START_SPECS,
        end_specs=_TAMPS_END_SPECS,
        blacklist_patterns=_TAMPS_BLACKLIST,
        max_chars=15_000,
        fallback_chars=0,  # manejamos fallback con páginas abajo
    )

    if not result.found:
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

    section_text = full_text[result.start_char:result.end_char].strip()

    # Determinar páginas que cubre esta sección
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


# ══════════════════════════════════════════════════════════════
# Meta CSV
# ══════════════════════════════════════════════════════════════

_META_FIELDS = [
    "ejercicio", "municipio", "slug", "cve_mun", "decreto", "source_pdf",
    "ley_page_start", "ley_page_end",
    "predial_found", "predial_method",
    "predial_page_start", "predial_page_end",
    "txt_file", "txt_chars",
    *HITL_EXTRA_FIELDS,
]


def _write_meta_csv(
    meta_dir: Path,
    all_rows: list[dict],
):
    """Escribe un único CSV de metadatos de segmentación (todos los años)."""
    meta_dir.mkdir(parents=True, exist_ok=True)
    csv_path = meta_dir / "segment.csv"

    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_META_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    return csv_path


# ══════════════════════════════════════════════════════════════
# Pipeline principal
# ══════════════════════════════════════════════════════════════

def segment_all(
    data_dir: Path = Path("data/tamaulipas"),
    year_min: int = config.YEAR_MIN,
    year_max: int = config.YEAR_MAX,
    force: bool = False,
):
    """
    Segmenta todos los PDFs consolidados en secciones de predial por municipio.
    Genera TXTs, PDFs recortados, y CSVs de metadatos en /meta.
    """
    raw_dir = data_dir / "pdf_raw"
    focus_dir = data_dir / "focus_predial"
    meta_dir = data_dir / "meta"

    print("═══ Tamaulipas: Segmentación ═══")

    stats = {
        "total": 0, "found_exact": 0, "found_fallback": 0,
        "skipped": 0, "errors": 0,
    }

    all_meta_rows: list[dict] = []

    for ejercicio in range(year_min, year_max + 1):
        pdf_path = raw_dir / str(ejercicio) / f"{config.PREFIJO}_RAW_{ejercicio}_consolidado.pdf"
        if not pdf_path.exists():
            print(f"  [{ejercicio}] PDF no encontrado — SKIP")
            continue

        year_out = focus_dir / str(ejercicio)
        year_out.mkdir(parents=True, exist_ok=True)

        skip_n = _skip_pages_for_year(ejercicio)
        print(f"\n  [{ejercicio}] Procesando {pdf_path.name} (skip={skip_n}pp)...")

        try:
            doc = fitz.open(str(pdf_path))
        except Exception as e:
            print(f"    ERROR abriendo PDF: {e}")
            stats["errors"] += 1
            continue

        # Nivel 1: encontrar leyes (ignorando sumario)
        leyes = find_leyes_municipales(doc, skip_pages=skip_n)
        print(f"    Leyes encontradas: {len(leyes)}")

        if len(leyes) < 30:
            print(f"    WARN: Se esperaban ~43 leyes, solo {len(leyes)} encontradas")

        for ley in leyes:
            stats["total"] += 1

            txt_path = year_out / f"{config.PREFIJO}_PREDIAL_{ejercicio}_{ley.slug}.txt"
            pdf_out = year_out / f"{config.PREFIJO}_PREDIAL_{ejercicio}_{ley.slug}.pdf"

            if txt_path.exists() and not force:
                stats["skipped"] += 1
                # Intentar recuperar páginas de predial del header del TXT existente
                _skip_pred_start = ""
                _skip_pred_end = ""
                _skip_method = ""
                try:
                    _hdr = txt_path.read_text(encoding="utf-8", errors="ignore")[:500]
                    import re as _re
                    _m_pages = _re.search(r"P.ginas predial: (\d+)-(\d+)", _hdr)
                    _m_method = _re.search(r"M.todo detecci.n: (\S+)", _hdr)
                    if _m_pages:
                        _skip_pred_start = _m_pages.group(1)
                        _skip_pred_end = _m_pages.group(2)
                    if _m_method:
                        _skip_method = _m_method.group(1)
                except Exception:
                    pass
                all_meta_rows.append({
                    "ejercicio": ejercicio,
                    "municipio": ley.municipio,
                    "slug": ley.slug,
                    "cve_mun": ley.cve_mun,
                    "decreto": ley.decreto,
                    "source_pdf": pdf_path.name,
                    "ley_page_start": ley.page_start + 1,
                    "ley_page_end": ley.page_end,
                    "predial_found": "skipped",
                    "predial_method": _skip_method,
                    "predial_page_start": _skip_pred_start,
                    "predial_page_end": _skip_pred_end,
                    "txt_file": txt_path.name,
                    "txt_chars": txt_path.stat().st_size if txt_path.exists() else 0,
                    **hitl_extra_columns(),
                })
                continue

            # Nivel 2: extraer predial (con fallback a primeras 5 páginas)
            seccion = extract_predial_section(doc, ley)

            if seccion.method.startswith("fallback"):
                print(f"    {ley.slug}: predial no detectada → {seccion.method}")
                stats["found_fallback"] += 1
            else:
                stats["found_exact"] += 1

            # Guardar TXT
            header = (
                f"# Municipio: {ley.municipio}\n"
                f"# Estado: Tamaulipas\n"
                f"# Ejercicio: {ejercicio}\n"
                f"# Decreto: {ley.decreto}\n"
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
                print(f"    {ley.slug}: Error guardando PDF: {e}")

            # Meta row
            all_meta_rows.append({
                "ejercicio": ejercicio,
                "municipio": ley.municipio,
                "slug": ley.slug,
                "cve_mun": ley.cve_mun,
                "decreto": ley.decreto,
                "source_pdf": pdf_path.name,
                "ley_page_start": ley.page_start + 1,
                "ley_page_end": ley.page_end,
                "predial_found": "true" if not seccion.method.startswith("fallback") else "fallback",
                "predial_method": seccion.method,
                "predial_page_start": seccion.page_start + 1,
                "predial_page_end": seccion.page_end,
                "txt_file": txt_path.name,
                "txt_chars": len(txt_content),
                **hitl_extra_columns(seccion._seg_result),
            })

        doc.close()

    # Escribir meta CSV único (todos los años)
    if all_meta_rows:
        csv_path = _write_meta_csv(meta_dir, all_meta_rows)
        print(f"\n  Meta: {csv_path.name} ({len(all_meta_rows)} filas)")

    print("\n  ── Resumen ──")
    print(f"  Total: {stats['total']}")
    print(f"  Predial exacta: {stats['found_exact']}")
    print(f"  Predial fallback: {stats['found_fallback']}")
    print(f"  Ya existían: {stats['skipped']}")
    print(f"  Errores: {stats['errors']}")
