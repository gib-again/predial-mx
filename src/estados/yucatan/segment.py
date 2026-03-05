"""
Segmentación de leyes de ingresos y secciones de predial de Yucatán.

ESTRUCTURA DE LOS TOMOS DEL PO DE YUCATÁN:

  Cada decreto contiene N leyes municipales:

    SUMARIO (lista de municipios con páginas)
    EXPOSICIÓN DE MOTIVOS (preámbulo genérico, contiene criterios generales)
    DECRETO:
    Artículo Primero.- Se aprueban las Leyes de Ingresos...
    Artículo Segundo.- Las Leyes de Ingresos ... se describen en cada fracción:

    I.- LEY DE INGRESOS DEL MUNICIPIO DE BACA, YUCATÁN, PARA EL EJERCICIO FISCAL 2011:
       TÍTULO PRIMERO - DE LOS CONCEPTOS DE INGRESO
       TÍTULO SEGUNDO - IMPUESTOS
         CAPÍTULO I Impuesto Predial
           - Tabla de valores catastrales (IGNORAR)
           - Tarifa/tasa/factor del impuesto
           - Predio rústico
           - Predial por frutos civiles (rentas)
         CAPÍTULO II Impuesto Sobre Adquisición...
         CAPÍTULO III Diversiones y Espectáculos
       TÍTULO TERCERO - DERECHOS
       ...
       TÍTULO SEXTO - DE LAS TASAS, CUOTAS Y TARIFAS (cuando existe)
         CAPÍTULO II Impuestos
           Sección Primera Impuesto Predial
             - Tarifa progresiva (la que necesitamos)
             - Tabla de valores (IGNORAR)
             - Predial por frutos civiles
           Sección Segunda Impuesto Sobre Adquisición...
       ...

    II.- LEY DE INGRESOS DEL MUNICIPIO DE BOKOBÁ...

DOS PATRONES DE PREDIAL:

  TIPO A (simple): Solo tiene CAPÍTULO I Impuesto Predial en TÍTULO SEGUNDO
    → Tarifa + valores están juntos
    → Buscar: "CAPÍTULO I Impuesto Predial" → hasta "CAPÍTULO II"

  TIPO B (TASAS separadas): Tiene "Sección Primera Impuesto Predial" en TÍTULO SEXTO
    → La tarifa real está en la Sección Primera
    → PREFERIR Sección Primera sobre CAPÍTULO I (más limpia)

EXTRACCIÓN DE PREDIAL:

  La sección extraída incluirá inevitablemente las tablas de valores catastrales.
  El prompt del LLM se encarga de distinguir:
    - TARIFA/TASA/FACTOR (lo que calcula el impuesto) → EXTRAER
    - VALORES UNITARIOS DE TERRENO/CONSTRUCCIÓN (catastro) → IGNORAR
"""

import csv
import json
import re
import unicodedata
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from src.core.text_utils import slugify
from src.estados.yucatan.config import PREFIJO, KEEP_MONTHS, MERIDA_URLS, MERIDA_REPLICA_YEARS


# ══════════════════════════════════════════════════════════════
# Utilidades
# ══════════════════════════════════════════════════════════════

def _norm(s: str) -> str:
    """Normaliza: sin acentos, mayúsculas, espacios simples."""
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s.upper()).strip()


def _fix_mojibake(s: str) -> str:
    """Repara mojibake: UTF-8 bytes leídos como Latin-1 → 'ManÃ\xad' → 'Maní'."""
    try:
        return s.encode("latin-1").decode("utf-8")
    except (UnicodeDecodeError, UnicodeEncodeError):
        return s


def _clean_muni_name(raw: str) -> str:
    """Limpia nombre de municipio extraído del header."""
    s = _fix_mojibake(raw.strip())
    # Quitar ", YUCATÁN" y variantes
    s = re.sub(r"\s*,?\s*YUCAT[AÁ]N\s*$", "", s, flags=re.I).strip()
    s = s.rstrip(",. ")
    # Title case
    s = s.title()
    s = re.sub(r"\bDe\b", "de", s)
    s = re.sub(r"\bDel\b", "del", s)
    s = re.sub(r"\bY\b", "y", s)
    if s:
        s = s[0].upper() + s[1:]
    return s


def _get_pub_month(name: str) -> Optional[int]:
    m = re.search(r"(20\d{2})-(\d{2})-(\d{2})", name)
    return int(m.group(2)) if m else None


# ══════════════════════════════════════════════════════════════
# MASTER: Detectar inicio de cada ley municipal en el tomo
# ══════════════════════════════════════════════════════════════

# Header: "I.- LEY DE INGRESOS DEL MUNICIPIO DE BACA, YUCATÁN, PARA EL EJERCICIO FISCAL 2011:"
# Variantes:
#   - "I.-LEY" (sin espacio), "I.- LEY", "VI.-LEY"
#   - "EJERCICIO FISCAL 2023:" vs "EJERCICIO FISCAL  2023:"
#   - "EJERICICIO" (typo en Cuzamá 2022)
_RE_LEY_HEADER = re.compile(
    r"^([IVXLCDM]+)\s*[.\-]+\s*"
    r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+(?:DE\s+)?"
    r"(.+?)"
    r",?\s*PARA\s+EL\s+"
    r"EJER[IE]?CICIO\s+FISCAL\s+(\d{4})",
    re.IGNORECASE | re.MULTILINE,
)

# Pattern to detect start of DECRETO section (to skip SUMARIO/EXPOSICIÓN)
_RE_DECRETO = re.compile(
    r"(?:D\s*E\s*C\s*R\s*E\s*T\s*O|Art[ií]culo\s+(?:Primero|Segundo)\s*[.\-])",
    re.IGNORECASE,
)


def _detect_laws_in_text(full_text: str) -> list[dict]:
    """
    Detecta inicio de cada ley municipal en el texto concatenado del tomo.

    Estrategia:
      1. Encontrar la sección DECRETO (saltear SUMARIO y EXPOSICIÓN)
      2. Buscar headers con numeral romano + "LEY DE INGRESOS DEL MUNICIPIO DE {X}"
      3. Extraer municipio y ejercicio fiscal
    """
    # Encontrar inicio del DECRETO para filtrar SUMARIO/EXPOSICIÓN
    decreto_start = 0
    m_dec = _RE_DECRETO.search(full_text)
    if m_dec:
        decreto_start = m_dec.start()

    results = []
    for m in _RE_LEY_HEADER.finditer(full_text, decreto_start):
        roman = m.group(1).strip()
        muni_raw = m.group(2).strip()
        fy = int(m.group(3))

        muni = _clean_muni_name(muni_raw)
        if len(muni) < 3:
            continue

        results.append({
            "municipio": muni,
            "fiscal_year": fy,
            "roman": roman,
            "char_start": m.start(),
        })

    return results


def run_build_master(adapter) -> Path:
    """
    Escanea todos los tomos y detecta inicio de cada ley municipal.
    """
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    meta_dir.mkdir(parents=True, exist_ok=True)

    pdf_files = sorted(pdf_raw_dir.rglob("*.pdf"))
    # Filtrar por mes
    pdf_files = [p for p in pdf_files
                 if _get_pub_month(p.name) is None or _get_pub_month(p.name) in KEEP_MONTHS]

    print(f"  PDFs a analizar: {len(pdf_files)}")

    all_segments = []

    for i, pdf_path in enumerate(pdf_files, 1):
        if i % 5 == 0 or i == len(pdf_files):
            print(f"    [{i}/{len(pdf_files)}] {pdf_path.name}...")

        try:
            with fitz.open(pdf_path) as doc:
                # Build text + char→page mapping
                import bisect
                parts = []
                page_char_starts = []  # char offset where each page starts
                cursor = 0
                for page_idx in range(doc.page_count):
                    page_char_starts.append(cursor)
                    t = doc[page_idx].get_text("text") or ""
                    parts.append(t)
                    parts.append("\n")
                    cursor += len(t) + 1

                full_text = "".join(parts)
                laws = _detect_laws_in_text(full_text)

                rel_path = str(pdf_path.relative_to(pdf_raw_dir))

                for law_idx, law in enumerate(laws):
                    # Calculate start/end chars
                    char_start = law["char_start"]
                    char_end = laws[law_idx + 1]["char_start"] if law_idx + 1 < len(laws) else len(full_text)

                    # Map to pages
                    start_page = bisect.bisect_right(page_char_starts, char_start)
                    end_page = bisect.bisect_right(page_char_starts, max(char_start, char_end - 1))

                    all_segments.append({
                        "file": rel_path,
                        "municipio": law["municipio"],
                        "fiscal_year": law["fiscal_year"],
                        "roman": law["roman"],
                        "start_page": start_page,
                        "end_page": end_page,
                        "char_start": char_start,
                        "char_end": char_end,
                    })

                if laws:
                    print(f"    {pdf_path.name}: {len(laws)} leyes")

        except Exception as e:
            print(f"    [ERROR] {pdf_path.name}: {e}")

    # Guardar segmentos
    segments_json = meta_dir / "segmentos.json"
    with segments_json.open("w", encoding="utf-8") as f:
        json.dump(all_segments, f, ensure_ascii=False, indent=2)

    n_munis = len(set(s["municipio"] for s in all_segments))
    n_years = len(set(s["fiscal_year"] for s in all_segments))
    print(f"  Leyes detectadas: {len(all_segments)} ({n_munis} municipios, {n_years} ejercicios) → {segments_json}")
    return segments_json


# ══════════════════════════════════════════════════════════════
# SEGMENT: Extraer sección de predial de cada ley
# ══════════════════════════════════════════════════════════════

# ── Predial Start ──

# TIPO B (preferido): "Sección Primera Impuesto Predial" en TÍTULO SEXTO
# Note: PDF text extraction often produces "Secci" (truncated) instead of "Sección"
_RE_SECCION_PRIMERA_PREDIAL = re.compile(
    r"Secci[oó]?n?\s+[Pp]rimera\s+(?:(?:del?\s+)?Imp[uú]esto\s+[Pp]redial)",
    re.IGNORECASE,
)

# TIPO A (fallback): "CAPÍTULO I Impuesto Predial" en TÍTULO SEGUNDO
_RE_CAPITULO_I_PREDIAL = re.compile(
    r"CAP[IÍ]TULO\s+(?:I|1|PRIMERO)\s+(?:(?:del?\s+)?Imp[uú]esto\s+[Pp]redial)",
    re.IGNORECASE,
)

# ── Predial End ──

# TIPO B end: "Sección Segunda" (Del Impuesto Sobre Adquisición / cualquier siguiente sección)
_RE_SECCION_SEGUNDA = re.compile(
    r"Secci[oó]?n?\s+Segunda\s+",
    re.IGNORECASE,
)

# TIPO A end: "CAPÍTULO II" (Impuesto Sobre Adquisición)
_RE_CAPITULO_II = re.compile(
    r"CAP[IÍ]TULO\s+(?:II|ll|2|SEGUNDO)\s+",
    re.IGNORECASE,
)

# Fallback end: "CAPÍTULO III Derechos" or "TÍTULO TERCERO"
_RE_TITULO_III = re.compile(
    r"(?:CAP[IÍ]TULO\s+(?:III|3|TERCERO)\s+Derechos|T[IÍ]TULO\s+TERCERO)",
    re.IGNORECASE,
)


def _extract_predial_text(law_text: str) -> Optional[str]:
    """
    Extrae la sección de predial del texto de una ley individual.

    DOS PATRONES:

    TIPO B (PREFERIDO): Busca "Sección Primera Impuesto Predial" (en TÍTULO SEXTO)
      → Contiene la tarifa progresiva/tasa real + valores catastrales + frutos civiles
      → Fin: "Sección Segunda"
      → PREFERIDO porque tiene la tarifa limpia y separada

    TIPO A (FALLBACK): Busca "CAPÍTULO I Impuesto Predial" (en TÍTULO SEGUNDO)
      → Contiene valores catastrales + tarifa/factor + rústicos + frutos civiles
      → Fin: "CAPÍTULO II"

    FILTRADO DE VALORES CATASTRALES:
      No filtramos aquí — el prompt del LLM se encarga de distinguir
      tarifa (lo que calcula el impuesto) de valores catastrales (catastro).
      Esto es más robusto que intentar separar con regex.

    Returns:
        Texto de la sección predial, o None si no se encuentra.
    """
    # Estrategia: TIPO B primero, TIPO A como fallback
    predial_text = _try_tipo_b(law_text)
    if predial_text:
        return predial_text

    predial_text = _try_tipo_a(law_text)
    if predial_text:
        return predial_text

    return None


def _try_tipo_b(law_text: str) -> Optional[str]:
    """Intenta extraer predial con patrón Sección Primera."""
    m_start = _RE_SECCION_PRIMERA_PREDIAL.search(law_text)
    if not m_start:
        return None

    predial_start = m_start.start()

    # Buscar fin: Sección Segunda
    m_end = _RE_SECCION_SEGUNDA.search(law_text, predial_start + 20)
    if m_end:
        predial_end = m_end.start()
    else:
        # Fallback: CAPÍTULO III o TÍTULO III
        m_end2 = _RE_TITULO_III.search(law_text, predial_start + 20)
        if m_end2:
            predial_end = m_end2.start()
        else:
            predial_end = min(predial_start + 10000, len(law_text))

    result = law_text[predial_start:predial_end].strip()
    return result if len(result) > 50 else None


def _try_tipo_a(law_text: str) -> Optional[str]:
    """Intenta extraer predial con patrón CAPÍTULO I."""
    m_start = _RE_CAPITULO_I_PREDIAL.search(law_text)
    if not m_start:
        return None

    predial_start = m_start.start()

    # Buscar fin: CAPÍTULO II
    m_end = _RE_CAPITULO_II.search(law_text, predial_start + 20)
    if m_end:
        predial_end = m_end.start()
    else:
        m_end2 = _RE_TITULO_III.search(law_text, predial_start + 20)
        if m_end2:
            predial_end = m_end2.start()
        else:
            predial_end = min(predial_start + 10000, len(law_text))

    result = law_text[predial_start:predial_end].strip()
    return result if len(result) > 50 else None


def run_extract_sections(adapter) -> Path:
    """
    Para cada ley delimitada, extrae sección de predial.
    Incluye manejo especial de Mérida (Ley de Hacienda separada).
    """
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    focus_dir = adapter.focus_dir
    prefijo = adapter.prefijo

    segments_json = meta_dir / "segmentos.json"
    if not segments_json.exists():
        raise FileNotFoundError(f"No existe {segments_json}. Ejecuta 'master' primero.")

    with segments_json.open(encoding="utf-8") as f:
        segments = json.load(f)

    print(f"  Segmentos a procesar: {len(segments)}")

    # Agrupar por PDF para cachear texto
    by_file = {}
    for s in segments:
        by_file.setdefault(s["file"], []).append(s)

    log_rows = []
    segment_rows = []

    for fname, group in by_file.items():
        pdf_path = pdf_raw_dir / fname
        if not pdf_path.exists():
            for s in group:
                log_rows.append({
                    "municipio": s["municipio"], "ejercicio": s["fiscal_year"],
                    "file": fname, "predial_chars": 0,
                    "predial_tipo": "", "status": "pdf_missing",
                })
            continue

        try:
            with fitz.open(pdf_path) as doc:
                # Concatenar texto completo
                parts = []
                for page_idx in range(doc.page_count):
                    t = doc[page_idx].get_text("text") or ""
                    parts.append(t)
                    parts.append("\n")
                full_text = "".join(parts)

                # Construir mapa de página → offset para este doc
                import bisect
                page_char_starts = []
                _cursor = 0
                for _pi in range(doc.page_count):
                    page_char_starts.append(_cursor)
                    _t = doc[_pi].get_text("text") or ""
                    _cursor += len(_t) + 1  # +1 por el "\n" del join

                for s in group:
                    muni = s["municipio"]
                    fy = str(s["fiscal_year"])
                    char_start = s["char_start"]
                    char_end = s["char_end"]
                    ley_start_page = s.get("start_page", 0)
                    ley_end_page = s.get("end_page", 0)

                    law_text = full_text[char_start:char_end]

                    # Detect which tipo was used
                    has_seccion = bool(_RE_SECCION_PRIMERA_PREDIAL.search(law_text))

                    predial_text = _extract_predial_text(law_text)

                    muni_slug = slugify(muni)
                    txt_name = f"{prefijo}_PREDIAL_{fy}_{muni_slug}.txt"

                    if not predial_text:
                        log_rows.append({
                            "municipio": muni, "ejercicio": fy,
                            "file": fname, "predial_chars": 0,
                            "predial_tipo": "none",
                            "status": "no_predial_found",
                        })
                        # Escribir row para segment.csv (sin predial)
                        segment_rows.append({
                            "ejercicio": fy, "municipio": muni, "slug": muni_slug,
                            "source_pdf": fname,
                            "ley_page_start": ley_start_page,
                            "ley_page_end": ley_end_page,
                            "predial_found": "false", "predial_method": "none",
                            "predial_page_start": "", "predial_page_end": "",
                            "txt_file": txt_name, "txt_chars": 0,
                        })
                        continue

                    # Detect tipo
                    if has_seccion and predial_text.lower().startswith("secci"):
                        predial_tipo = "seccion_primera"
                    else:
                        predial_tipo = "capitulo_i"

                    # Calcular páginas de predial a partir de offsets
                    predial_offset_in_full = full_text.find(predial_text, char_start)
                    if predial_offset_in_full < 0:
                        predial_offset_in_full = char_start
                    pred_page_start = bisect.bisect_right(page_char_starts, predial_offset_in_full)
                    pred_page_end = bisect.bisect_right(
                        page_char_starts,
                        max(predial_offset_in_full, predial_offset_in_full + len(predial_text) - 1)
                    )

                    # Guardar TXT
                    txt_path = focus_dir / fy / txt_name
                    txt_path.parent.mkdir(parents=True, exist_ok=True)
                    txt_path.write_text(predial_text, encoding="utf-8")

                    log_rows.append({
                        "municipio": muni, "ejercicio": fy,
                        "file": fname, "predial_chars": len(predial_text),
                        "predial_tipo": predial_tipo,
                        "status": "ok",
                    })
                    segment_rows.append({
                        "ejercicio": fy, "municipio": muni, "slug": muni_slug,
                        "source_pdf": fname,
                        "ley_page_start": ley_start_page,
                        "ley_page_end": ley_end_page,
                        "predial_found": "true", "predial_method": predial_tipo,
                        "predial_page_start": pred_page_start,
                        "predial_page_end": pred_page_end,
                        "txt_file": txt_name, "txt_chars": len(predial_text),
                    })

        except Exception as e:
            print(f"    [ERROR] {fname}: {e}")

    # ── Mérida: extraer predial de Ley de Hacienda ──
    merida_rows = _process_merida(pdf_raw_dir, focus_dir, prefijo)
    log_rows.extend(merida_rows)

    # Bitácora (formato legacy)
    sections_csv = meta_dir / "predial_sections.csv"
    fieldnames = ["municipio", "ejercicio", "file", "predial_chars", "predial_tipo", "status"]
    with sections_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log_rows)

    # segment.csv (formato estándar compatible con llm_extract fallbacks)
    _seg_fields = [
        "ejercicio", "municipio", "slug", "source_pdf",
        "ley_page_start", "ley_page_end",
        "predial_found", "predial_method",
        "predial_page_start", "predial_page_end",
        "txt_file", "txt_chars",
    ]
    seg_csv = meta_dir / "segment.csv"
    with seg_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_seg_fields)
        writer.writeheader()
        writer.writerows(segment_rows)
    print(f"  segment.csv: {len(segment_rows)} filas → {seg_csv}")

    ok_count = sum(1 for r in log_rows if r["status"] == "ok")
    no_pred = sum(1 for r in log_rows if r["status"] == "no_predial_found")
    tipo_b = sum(1 for r in log_rows if r.get("predial_tipo") == "seccion_primera")
    tipo_a = sum(1 for r in log_rows if r.get("predial_tipo") == "capitulo_i")
    merida_ok = sum(1 for r in log_rows if r.get("predial_tipo") == "merida_hacienda")
    print(f"  Secciones extraídas: {ok_count}/{len(log_rows)} "
          f"(tipo_B={tipo_b}, tipo_A={tipo_a}, mérida={merida_ok}, sin_predial={no_pred})")
    print(f"  → {sections_csv}")
    return sections_csv


# ══════════════════════════════════════════════════════════════
# MÉRIDA: Extracción especial desde Ley de Hacienda
# ══════════════════════════════════════════════════════════════

# Inicio: "De la tarifa ARTÍCULO 47.-" o "ARTICULO 45.-"
# Maneja: acentos, espacios pegados por OCR ("Delatarifa ARTICULO45.")
_RE_MERIDA_TARIFA_START = re.compile(
    r"De\s*la\s*tarifa\s*"
    r"ART[IÍ]CULO\s*(?:45|47)\s*[.\-]",
    re.IGNORECASE,
)

# Fin: "Del pago ARTÍCULO 46.-" o "ARTÍCULO 48.-"
# Maneja: "Delpago ARTICULO46."
_RE_MERIDA_TARIFA_END = re.compile(
    r"Del\s*pago\s*"
    r"ART[IÍ]CULO\s*(?:46|48)\s*[.\-]",
    re.IGNORECASE,
)


def _extract_merida_predial(pdf_path: Path) -> Optional[str]:
    """
    Extrae la sección de tarifa predial de la Ley de Hacienda de Mérida.

    Estrategia:
      1. Extraer texto nativo de todas las páginas
      2. Buscar "De la tarifa ARTÍCULO 47/45" → "Del pago ARTÍCULO 48/46"
      3. Si la tabla es imagen (texto nativo sin números de tarifa),
         hacer OCR con pdf2image+tesseract SOLO en las páginas relevantes

    Returns:
        Texto de la sección predial, o None si no se encuentra.
    """
    import fitz as _fitz

    try:
        doc = _fitz.open(pdf_path)
    except Exception:
        return None

    try:
        # ── Paso 1: Texto nativo ──
        page_texts = []
        for i in range(doc.page_count):
            page_texts.append(doc[i].get_text("text") or "")

        full_text = "\n".join(page_texts)
        result = _find_tarifa_section(full_text)

        # Si el resultado tiene números de tarifa (la tabla no es imagen), listo
        if result and _has_tarifa_numbers(result):
            return result

        # ── Paso 2: Encontrar páginas candidatas para OCR ──
        # Buscar páginas con "tarifa" o "ARTÍCULO 47/45" en texto nativo
        candidate_pages = set()
        for i, pt in enumerate(page_texts):
            if re.search(r"tarifa|ART[IÍ]CULO\s*(?:45|47)|Del\s*pago", pt, re.I):
                # OCR esta página y vecinas (la tabla imagen puede estar en la siguiente)
                for offset in range(-1, 3):
                    p = i + offset
                    if 0 <= p < doc.page_count:
                        candidate_pages.add(p)

        doc.close()
        doc = None

        if not candidate_pages:
            return result  # Devolver lo que teníamos (puede ser None)

        # ── Paso 3: OCR focalizado con pdf2image + tesseract ──
        ocr_text = _ocr_pages(pdf_path, sorted(candidate_pages))
        if not ocr_text:
            return result

        ocr_result = _find_tarifa_section(ocr_text)
        if ocr_result and len(ocr_result) > (len(result) if result else 0):
            return ocr_result

        return result

    finally:
        if doc:
            doc.close()


def _find_tarifa_section(text: str) -> Optional[str]:
    """Busca la sección de tarifa en un texto dado."""
    m_start = _RE_MERIDA_TARIFA_START.search(text)
    if not m_start:
        return None

    start = m_start.start()
    m_end = _RE_MERIDA_TARIFA_END.search(text, start + 20)
    end = m_end.start() if m_end else min(start + 8000, len(text))

    result = text[start:end].strip()
    return result if len(result) >= 50 else None


def _has_tarifa_numbers(text: str) -> bool:
    """Verifica si el texto contiene números de la tabla de tarifa progresiva."""
    # Debe tener al menos: límites numéricos Y factores/tasas
    has_limits = bool(re.search(r"\d{1,3}(?:,\d{3})+\.\d{2}", text))  # ej: 50,000.00
    has_factors = bool(re.search(r"0\.00\d{2,}", text))  # ej: 0.00075
    return has_limits and has_factors


def _ocr_pages(pdf_path: Path, page_numbers: list[int]) -> str:
    """
    OCR de páginas específicas usando pdf2image + tesseract.

    Usa pdf2image (poppler) para renderizar a 300 DPI y tesseract para OCR.
    Solo procesa las páginas indicadas — rápido para 2-4 páginas.

    Args:
        pdf_path: Ruta al PDF.
        page_numbers: Lista de números de página (0-indexed).

    Returns:
        Texto concatenado de las páginas OCR'eadas.
    """
    import subprocess
    import tempfile

    try:
        from pdf2image import convert_from_path
    except ImportError:
        print("    [WARN] pdf2image no disponible, OCR no posible")
        return ""

    # Detectar idiomas disponibles en tesseract
    try:
        lang_result = subprocess.run(
            ["tesseract", "--list-langs"],
            capture_output=True,
            timeout=10,
        )
        available_langs = (
            lang_result.stderr.decode("utf-8", errors="replace")
            + lang_result.stdout.decode("utf-8", errors="replace")
        )
        available_langs = lang_result.stderr + lang_result.stdout
        lang = "spa" if "spa" in available_langs else "eng"
    except Exception:
        lang = "eng"

    texts = []
    for page_num in page_numbers:
        try:
            # pdf2image usa 1-indexed
            images = convert_from_path(
                str(pdf_path),
                first_page=page_num + 1,
                last_page=page_num + 1,
                dpi=300,
            )
            if not images:
                continue

            img = images[0]

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                img.save(tmp.name, "PNG")
                tmp_path = tmp.name

            try:
                result = subprocess.run(
                    ["tesseract", tmp_path, "stdout", "-l", lang, "--psm", "6"],
                    capture_output=True,
                    timeout=60,
                )
                ocr_text = result.stdout.decode("utf-8", errors="replace")
                texts.append(ocr_text.replace("\x0c", ""))
                texts.append((result.stdout or "").replace("\x0c", ""))
            finally:
                import os
                os.unlink(tmp_path)

        except Exception as e:
            print(f"    [WARN] OCR page {page_num}: {e}")

    return "\n".join(texts)


def _process_merida(pdf_raw_dir: Path, focus_dir: Path, prefijo: str) -> list[dict]:
    """Procesa PDFs de Mérida y genera TXT de predial."""
    merida_dir = pdf_raw_dir / "merida"
    log_rows = []

    if not merida_dir.exists():
        return log_rows

    # Process each year's PDF
    processed_years = set()
    for fy, url in sorted(MERIDA_URLS.items()):
        pdf_path = merida_dir / f"merida_hacienda_{fy}.pdf"
        if not pdf_path.exists():
            log_rows.append({
                "municipio": "Mérida", "ejercicio": str(fy),
                "file": f"merida/merida_hacienda_{fy}.pdf",
                "predial_chars": 0, "predial_tipo": "merida_hacienda",
                "status": "pdf_missing",
            })
            continue

        predial_text = _extract_merida_predial(pdf_path)
        if not predial_text:
            log_rows.append({
                "municipio": "Mérida", "ejercicio": str(fy),
                "file": f"merida/merida_hacienda_{fy}.pdf",
                "predial_chars": 0, "predial_tipo": "merida_hacienda",
                "status": "no_predial_found",
            })
            continue

        # Guardar TXT
        txt_path = focus_dir / str(fy) / f"{prefijo}_PREDIAL_{fy}_merida.txt"
        txt_path.parent.mkdir(parents=True, exist_ok=True)
        txt_path.write_text(predial_text, encoding="utf-8")
        processed_years.add(fy)

        log_rows.append({
            "municipio": "Mérida", "ejercicio": str(fy),
            "file": f"merida/merida_hacienda_{fy}.pdf",
            "predial_chars": len(predial_text), "predial_tipo": "merida_hacienda",
            "status": "ok",
        })
        print(f"    Mérida FY={fy}: {len(predial_text)} chars")

    # Replica years (2023-2025 = same as 2022)
    source_fy = 2022
    source_txt = focus_dir / str(source_fy) / f"{prefijo}_PREDIAL_{source_fy}_merida.txt"
    if source_txt.exists():
        source_text = source_txt.read_text(encoding="utf-8")
        for fy in MERIDA_REPLICA_YEARS:
            txt_path = focus_dir / str(fy) / f"{prefijo}_PREDIAL_{fy}_merida.txt"
            txt_path.parent.mkdir(parents=True, exist_ok=True)
            txt_path.write_text(source_text, encoding="utf-8")
            log_rows.append({
                "municipio": "Mérida", "ejercicio": str(fy),
                "file": f"merida/merida_hacienda_{source_fy}.pdf",
                "predial_chars": len(source_text), "predial_tipo": "merida_replica",
                "status": "ok",
            })
            print(f"    Mérida FY={fy}: replica de {source_fy} ({len(source_text)} chars)")

    return log_rows
