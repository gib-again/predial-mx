"""
Segmentacion de los PDFs del PO de Aguascalientes.

A diferencia de Guanajuato (multiples leyes por PDF), en Aguascalientes cada
PDF/seccion del PO es una ley de ingresos municipal individual.  Esto simplifica
la segmentacion a un solo nivel: localizar la seccion de predial dentro de la ley.

La ley de ingresos empieza en la pagina 2 (pagina 1 = portada/encabezado).  La
seccion predial se encuentra buscando "IMPUESTO PREDIAL" con contexto de
SECCION/CAPITULO, y termina al inicio del siguiente impuesto (traslacion de
dominio, espectaculos, etc.).

Genera:
  data/aguascalientes/focus_predial/{ejercicio}/AGS_PREDIAL_{ejercicio}_{slug}.txt
  data/aguascalientes/focus_predial/{ejercicio}/AGS_PREDIAL_{ejercicio}_{slug}.pdf
  data/aguascalientes/meta/segment.csv
"""

from __future__ import annotations

import csv
import re
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
from src.estados.aguascalientes import config


FALLBACK_PAGES = 12


# ===================================================
# Nombre del municipio a partir del PDF
# ===================================================

_matcher = MuniMatcher(cve_ent=config.CVE_ENT, aliases=config.ALIASES)

_RE_LEY_TITULO = re.compile(
    r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+"
    r"([\w\sÁÉÍÓÚÑÜáéíóúñü\.\,]+?)"
    r"(?:,\s*AGUASCALIENTES|,\s*AGS|,?\s*PARA\s+EL\s+EJERCICIO)",
    re.IGNORECASE,
)

_RE_EJERCICIO = re.compile(
    r"EJERCICIO\s+FISCAL\s+(?:DEL\s+A[ÑN]O\s+)?(\d{4})",
    re.IGNORECASE,
)

_RE_DECRETO = re.compile(
    r"DECRETO\s+(?:N[UÚ]MERO|NO\.?|N[UÚ]M\.?)\s*(\d+)",
    re.IGNORECASE,
)


def _identify_from_pdf(doc: fitz.Document) -> tuple[str, int, str]:
    """Extrae municipio, ejercicio y decreto de las primeras paginas."""
    municipio = ""
    ejercicio = 0
    decreto = ""
    for i in range(min(4, len(doc))):
        text = doc[i].get_text("text") or ""
        if not municipio:
            m = _RE_LEY_TITULO.search(text)
            if m:
                raw = m.group(1).strip().rstrip(",").strip()
                slug = config.NOMBRE_PO.get(raw.upper())
                if not slug:
                    result = _matcher.match(raw)
                    slug = result.slug if result.matched else ""
                municipio = slug
        if not ejercicio:
            m = _RE_EJERCICIO.search(text)
            if m:
                ejercicio = int(m.group(1))
        if not decreto:
            m = _RE_DECRETO.search(text)
            if m:
                decreto = m.group(1)
    return municipio, ejercicio, decreto


# ===================================================
# Seccion predial (nivel unico)
# ===================================================

_AGS_START_SPECS = [
    # "SECCIÓN ÚNICA / Impuesto a la Propiedad Raíz" (Aguascalientes, Jesús María, etc.)
    PatternSpec(re.compile(
        r"SECCI[OÓ]N\s+(?:PRIMERA|[UÚ]NICA)\s*[\s\S]{0,300}?"
        r"(?:DEL\s+)?(?:IMPUESTO\s+)?(?:A\s+LA\s+|SOBRE\s+LA\s+)?PROPI?EDAD\s+RA[IÍ]Z",
        re.IGNORECASE,
    ), "seccion_propiedad_raiz"),
    PatternSpec(re.compile(
        r"SECCI[OÓ]N\s+(?:PRIMERA|[UÚ]NICA)\s*[\s\S]{0,300}?"
        r"(?:DEL\s+)?IMPUESTO\s+PREDIAL",
        re.IGNORECASE,
    ), "seccion_predial"),
    # "CAPÍTULO I / A la Propiedad Raíz" o "CAPÍTULO II / ... Propiedad Raíz"
    PatternSpec(re.compile(
        r"CAP[IÍ]TULO\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|"
        r"S[EÉ]PTIMO|OCTAVO|NOVENO|D[EÉ]CIMO|[IVX]+|\d+)"
        r"\s*[\s\S]{0,300}?(?:A\s+LA\s+|SOBRE\s+LA\s+)?PROPI?EDAD\s+RA[IÍ]Z",
        re.IGNORECASE,
    ), "capitulo_propiedad_raiz"),
    PatternSpec(re.compile(
        r"CAP[IÍ]TULO\s+(?:PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|"
        r"S[EÉ]PTIMO|OCTAVO|NOVENO|D[EÉ]CIMO|[IVX]+|\d+)"
        r"\s*[\s\S]{0,300}?(?:DEL\s+)?IMPUESTO\s+PREDIAL",
        re.IGNORECASE,
    ), "capitulo_predial"),
    # Standalone "Impuesto a la Propiedad Raíz" / "A la Propiedad Raíz"
    PatternSpec(re.compile(
        r"(?:IMPUESTO\s+)?A\s+LA\s+PROPI?EDAD\s+RA[IÍ]Z",
        re.IGNORECASE,
    ), "propiedad_raiz"),
    PatternSpec(re.compile(
        r"(?:DEL\s+)?IMPUESTO\s+PREDIAL",
        re.IGNORECASE,
    ), "impuesto_predial"),
]

_AGS_END_SPECS = [
    PatternSpec(re.compile(r"SECCI[OÓ]N\s+SEGUNDA", re.IGNORECASE), "seccion_segunda"),
    # "CAPÍTULO III" (next chapter = next tax in many municipalities)
    PatternSpec(re.compile(
        r"CAP[IÍ]TULO\s+(?:III|TERCERO)\b",
        re.IGNORECASE,
    ), "capitulo_iii"),
    PatternSpec(re.compile(
        r"(?:DEL\s+)?IMPUESTO\s+SOBRE\s+(?:TRASLACI[OÓ]N|TRANSMISI[OÓ]N)\s+DE\s+DOMINIO",
        re.IGNORECASE,
    ), "traslacion"),
    PatternSpec(re.compile(
        r"(?:DEL\s+)?IMPUESTO\s+SOBRE\s+DIVISI[OÓ]N(?:ES)?\s+(?:Y\s+)?LOTIFICACI[OÓ]N",
        re.IGNORECASE,
    ), "division_lotificacion"),
    PatternSpec(re.compile(
        r"(?:DEL\s+)?IMPUESTO\s+SOBRE\s+ESPECT[AÁ]CULOS",
        re.IGNORECASE,
    ), "espectaculos"),
    PatternSpec(re.compile(
        r"(?:DEL\s+)?IMPUESTO\s+SOBRE\s+JUEGOS",
        re.IGNORECASE,
    ), "juegos"),
    PatternSpec(re.compile(
        r"(?:DEL\s+)?IMPUESTO\s+SOBRE\s+(?:LA\s+)?ADQUISICI[OÓ]N\s+DE\s+(?:BIENES?\s+)?INMUEBLES",
        re.IGNORECASE,
    ), "adquisicion"),
    # Derechos section (common next section after impuestos)
    PatternSpec(re.compile(
        r"T[IÍ]TULO\s+(?:TERCERO|III)\b[\s\S]{0,100}?DERECHOS",
        re.IGNORECASE,
    ), "titulo_derechos"),
]

_AGS_BLACKLIST = [
    re.compile(
        r"(?:CLASIFICADOR|DISPOSICIONES\s+GENERALES|"
        r"FACILIDADES\s+ADMINISTRATIVAS|EST[IÍ]MULOS\s+FISCALES)",
        re.IGNORECASE,
    ),
]

_RE_CONTEXT_ARTICULO = re.compile(r"ART[IÍ]CULO\s+\d+", re.IGNORECASE)


def _ags_context_validator(text: str, match: re.Match, method: str) -> bool:
    if method in ("impuesto_predial", "propiedad_raiz"):
        context_after = text[match.end():min(len(text), match.end() + 500)]
        if not _RE_CONTEXT_ARTICULO.search(context_after):
            return False
        # Reject if match is in the second half (likely a reference, not the section)
        if match.start() > len(text) * 0.6:
            return False
    return True


# ===================================================
# Meta CSV
# ===================================================

_META_FIELDS = [
    "ejercicio", "municipio", "slug", "cve_mun", "decreto",
    "source_pdf",
    "predial_found", "predial_method",
    "predial_page_start", "predial_page_end",
    "txt_file", "txt_chars",
    *HITL_EXTRA_FIELDS,
]


def _write_meta_csv(meta_dir: Path, all_rows: list[dict]) -> Path:
    meta_dir.mkdir(parents=True, exist_ok=True)
    csv_path = meta_dir / "segment.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_META_FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)
    return csv_path


# ===================================================
# Pipeline principal
# ===================================================

def run_segment(adapter, year: str | None = None, force: bool = False) -> Path:
    """
    Segmenta PDFs ya descargados en secciones de predial.

    Cada PDF = una ley de ingresos de un municipio.  Se extrae el municipio
    y ejercicio del contenido del PDF, luego se localiza la seccion predial.

    Returns:
        Path al CSV segment.csv.
    """
    pdf_raw_dir = adapter.pdf_raw_dir
    focus_dir = adapter.focus_dir
    meta_dir = adapter.meta_dir

    print("=== Aguascalientes: Segmentacion ===")

    stats = {
        "total": 0, "found_exact": 0, "found_fallback": 0,
        "skipped": 0, "errors": 0,
    }
    all_meta_rows: list[dict] = []

    years = [int(year)] if year else range(config.YEAR_MIN, config.YEAR_MAX + 1)

    for ejercicio in years:
        year_dir = pdf_raw_dir / str(ejercicio)
        if not year_dir.exists():
            continue

        pdf_files = sorted(year_dir.glob("*.pdf"))
        if not pdf_files:
            continue

        print(f"\n  [{ejercicio}] {len(pdf_files)} PDFs")

        for pdf_path in pdf_files:
            stats["total"] += 1

            try:
                doc = fitz.open(str(pdf_path))
            except Exception as e:
                print(f"    ERROR abriendo {pdf_path.name}: {e}")
                stats["errors"] += 1
                continue

            slug, ej_from_pdf, decreto = _identify_from_pdf(doc)

            if not slug:
                # Fallback: inferir del nombre de archivo
                stem = pdf_path.stem
                parts = stem.split("_")
                if len(parts) >= 4:
                    slug = "_".join(parts[3:])
                else:
                    print(f"    WARN: No se pudo identificar municipio en {pdf_path.name}")
                    doc.close()
                    stats["errors"] += 1
                    continue

            ej = ej_from_pdf or ejercicio
            cve_info = config.SLUG_TO_CVE.get(slug, ("???", ""))
            cve_mun = cve_info[0]

            ej_out = focus_dir / str(ej)
            ej_out.mkdir(parents=True, exist_ok=True)
            txt_path = ej_out / f"{config.PREFIJO}_PREDIAL_{ej}_{slug}.txt"
            pdf_out = ej_out / f"{config.PREFIJO}_PREDIAL_{ej}_{slug}.pdf"

            if txt_path.exists() and not force:
                stats["skipped"] += 1
                all_meta_rows.append({
                    "ejercicio": ej,
                    "municipio": cve_info[1] if len(cve_info) > 1 else slug,
                    "slug": slug,
                    "cve_mun": cve_mun,
                    "decreto": decreto,
                    "source_pdf": pdf_path.name,
                    "predial_found": "skipped",
                    "predial_method": "",
                    "predial_page_start": "",
                    "predial_page_end": "",
                    "txt_file": txt_path.name,
                    "txt_chars": txt_path.stat().st_size if txt_path.exists() else 0,
                    **hitl_extra_columns(),
                })
                doc.close()
                continue

            # Extraer texto completo (saltar portada)
            start_page = 1 if len(doc) > 1 else 0
            pages_text: list[tuple[int, str]] = []
            for p in range(start_page, len(doc)):
                t = doc[p].get_text("text")
                if t:
                    pages_text.append((p, t))

            if not pages_text:
                doc.close()
                stats["errors"] += 1
                all_meta_rows.append({
                    "ejercicio": ej,
                    "municipio": cve_info[1] if len(cve_info) > 1 else slug,
                    "slug": slug,
                    "cve_mun": cve_mun,
                    "decreto": decreto,
                    "source_pdf": pdf_path.name,
                    "predial_found": "no_text",
                    "predial_method": "no_text",
                    "predial_page_start": "",
                    "predial_page_end": "",
                    "txt_file": "",
                    "txt_chars": 0,
                    **hitl_extra_columns(),
                })
                continue

            full_text = "\n".join(t for _, t in pages_text)

            result = find_predial_section(
                text=full_text,
                start_specs=_AGS_START_SPECS,
                end_specs=_AGS_END_SPECS,
                blacklist_patterns=_AGS_BLACKLIST,
                context_validator=_ags_context_validator,
                max_chars=15_000,
                fallback_chars=0,
            )

            if not result.found:
                fb_end = min(start_page + FALLBACK_PAGES, len(doc))
                fb_parts = []
                for p in range(start_page, fb_end):
                    t = doc[p].get_text("text")
                    if t:
                        fb_parts.append(t)
                section_text = "\n".join(fb_parts).strip()
                p_start = start_page
                p_end = fb_end
                method = f"fallback_{FALLBACK_PAGES}pp"
                stats["found_fallback"] += 1
                seg_result = None
            else:
                section_text = full_text[result.start_char:result.end_char].strip()
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
                method = result.method
                seg_result = result
                if method.startswith("fallback"):
                    stats["found_fallback"] += 1
                else:
                    stats["found_exact"] += 1

            # Guardar TXT
            header = (
                f"# Municipio: {cve_info[1] if len(cve_info) > 1 else slug}\n"
                f"# Estado: Aguascalientes\n"
                f"# Ejercicio: {ej}\n"
                f"# Decreto: {decreto}\n"
                f"# Fuente: {pdf_path.name}\n"
                f"# Paginas predial: {p_start + 1}-{p_end}\n"
                f"# Metodo deteccion: {method}\n"
                f"# CVE_MUN: {cve_mun}\n\n"
            )
            txt_content = header + section_text
            txt_path.write_text(txt_content, encoding="utf-8")

            # Guardar PDF recortado
            try:
                out_doc = fitz.open()
                for p in range(p_start, p_end):
                    if 0 <= p < len(doc):
                        out_doc.insert_pdf(doc, from_page=p, to_page=p)
                out_doc.save(str(pdf_out))
                out_doc.close()
            except Exception as e:
                print(f"      {slug}: Error guardando PDF: {e}")

            if not method.startswith("fallback"):
                log_method = method
            else:
                log_method = method
                print(f"    {slug}: predial no detectada -> {method}")

            all_meta_rows.append({
                "ejercicio": ej,
                "municipio": cve_info[1] if len(cve_info) > 1 else slug,
                "slug": slug,
                "cve_mun": cve_mun,
                "decreto": decreto,
                "source_pdf": pdf_path.name,
                "predial_found": "true" if not method.startswith("fallback") else "fallback",
                "predial_method": method,
                "predial_page_start": p_start + 1,
                "predial_page_end": p_end,
                "txt_file": txt_path.name,
                "txt_chars": len(txt_content),
                **hitl_extra_columns(seg_result),
            })

            doc.close()

    if all_meta_rows:
        csv_path = _write_meta_csv(meta_dir, all_meta_rows)
        print(f"\n  Meta: {csv_path.name} ({len(all_meta_rows)} filas)")

    print("\n  -- Resumen --")
    print(f"  Total: {stats['total']}")
    print(f"  Predial exacta: {stats['found_exact']}")
    print(f"  Predial fallback: {stats['found_fallback']}")
    print(f"  Ya existian: {stats['skipped']}")
    print(f"  Errores: {stats['errors']}")

    return meta_dir / "segment.csv"
