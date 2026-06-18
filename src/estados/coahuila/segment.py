"""
Segmentación de leyes de ingresos de Coahuila.

Consolida:
  - 03_coah_predial_master.py    → build_master (cruza directorio INEGI × índice de leyes)
  - 04_patch_predial_master_2017 → patch_2017 (escaneo especial de PDFs 2017)
  - 05_coah_master_merger.py     → merge_2017 (merge del patch al master)
  - 10_coah_predial_sections.py  → extract_predial_sections (localiza sección predial)

Todas las funciones de PDF usan src.core.pdf_utils en lugar de copias locales.
"""

import csv
import re
from pathlib import Path

from src.core.muni_matcher import MuniMatcher
from src.core.pdf_utils import build_text_and_offsets, idx_to_page, save_pdf_slice
from src.core.segment_utils import (
    HITL_EXTRA_FIELDS,
    PatternSpec,
    SegmentResult,
    find_predial_section,
    hitl_extra_columns,
)
from src.core.text_utils import norm
from src.estados.coahuila import config
from src.estados.coahuila.config import (
    DIR_MUN_CSV,
    PATRON_LEY_HEADER,
    PATRON_FIN_PREDIAL,
)


# ══════════════════════════════════════════════════════════════
# Utilidades compartidas dentro de este módulo
# ══════════════════════════════════════════════════════════════

def _load_directorio(catalogs_path: Path, estado_cve: str = "05") -> list[dict]:
    """
    Carga municipios del catálogo INEGI filtrando por clave de entidad.
    Coahuila = "05".
    """
    csv_path = catalogs_path / Path(DIR_MUN_CSV).name
    if not csv_path.exists():
        # Fallback: buscar en la ruta original
        csv_path = Path(DIR_MUN_CSV)
    if not csv_path.exists():
        print(f"  [ERROR] No encuentro catálogo de municipios: {csv_path}")
        return []

    munis = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Filtrar por entidad si el catálogo es nacional
            cve_ent = (row.get("CVE_ENT") or "").strip()
            if cve_ent and cve_ent != estado_cve:
                continue

            nom_mun = (row.get("NOM_MUN") or "").strip()
            nom_cab = (row.get("NOM_CAB") or "").strip()
            if not nom_mun:
                continue
            munis.append({
                "cve_mun": (row.get("CVE_MUN") or "").strip(),
                "nom_mun": nom_mun,
                "nom_cab": nom_cab,
                "norm_mun": norm(nom_mun),
                "norm_cab": norm(nom_cab),
            })
    print(f"  Leí {len(munis)} municipios del directorio.")
    return munis


def _load_leyes_index(csv_path: Path) -> list[dict]:
    """Carga el CSV índice de leyes de ingresos."""
    if not csv_path.exists():
        print(f"  [ERROR] No encuentro {csv_path}")
        return []

    leyes = []
    with csv_path.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            muni = (row.get("municipio") or "").strip()
            if not muni:
                continue
            try:
                ejercicio = int(row.get("ejercicio") or 0)
            except ValueError:
                continue
            leyes.append({
                "ejercicio": ejercicio,
                "municipio": muni,
                "muni_norm": norm(muni),
                "num_po": row.get("num_po", ""),
                "tipo_po": row.get("tipo", ""),
                "tomo": row.get("tomo", ""),
                "fecha_po": row.get("fecha_po", ""),
                "pdf_file": row.get("file_local") or row.get("file") or "",
            })
    print(f"  Leí {len(leyes)} registros de leyes de ingresos.")
    return leyes


# ══════════════════════════════════════════════════════════════
# Funciones de localización (específicas de Coahuila)
# ══════════════════════════════════════════════════════════════

def find_ley_span(raw_text: str, municipio: str):
    """
    Localiza (start_idx, end_idx) de la LEY DE INGRESOS de un municipio en el PDF.

    Se ancla en 'NUMERO xxx.- LEY DE INGRESOS DEL MUNICIPIO DE {MUNICIPIO}'
    del cuerpo del PO. Cuando ese ancla falla (OCR rompió "NUMERO X.-"), cae
    a un patrón laxo `LEY DE INGRESOS DEL MUNICIPIO DE {MUNI}` PERO descartando
    matches que caen en el sumario al principio del PO (antes del primer
    "NUMERO X.- LEY..." de cualquier municipio). Sin esto, el sumario en pg 1
    capturaba a Ocampo/Piedras Negras/Ramos Arizpe en 2010 y producía un span
    pg 1-2 con solo el índice.
    """
    norm_text = norm(raw_text)
    muni_norm = norm(municipio)
    if not muni_norm:
        return None

    muni_pattern = r"\s+".join(muni_norm.split())
    patt_numero = rf"NUMERO\s+\d+\.-\s*LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+{muni_pattern}"

    m = re.search(patt_numero, norm_text, flags=re.DOTALL)
    if not m:
        patt_simple = rf"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+{muni_pattern}"

        # Identificar inicio del cuerpo (primer "NUMERO X.- LEY..." de
        # cualquier muni). Matches simples antes de eso son del sumario.
        first_numero = re.search(
            r"NUMERO\s+\d+\.-\s*LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+\w+",
            norm_text, flags=re.DOTALL,
        )
        cuerpo_min_idx = first_numero.start() if first_numero else 0

        m = None
        for m_simple in re.finditer(patt_simple, norm_text, flags=re.DOTALL):
            if m_simple.start() >= cuerpo_min_idx:
                m = m_simple
                break
        if not m:
            return None

    law_start = m.start()
    law_header_end = m.end()

    # Cierre del span: primero intentar el patrón estricto NUMERO X.-, luego
    # un patrón laxo (cualquier "LEY DE INGRESOS DEL MUNICIPIO DE ..." que
    # marque el inicio de OTRA ley con OCR dañado de NUMERO).
    patt_any_numero = PATRON_LEY_HEADER
    m_next = re.search(patt_any_numero, norm_text[law_header_end:], flags=re.DOTALL)
    if m_next:
        law_end = law_header_end + m_next.start()
    else:
        m_next_simple = re.search(
            r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+\w+",
            norm_text[law_header_end:], flags=re.DOTALL,
        )
        if m_next_simple:
            law_end = law_header_end + m_next_simple.start()
        else:
            law_end = len(norm_text)

    if law_end <= law_start:
        return None

    return law_start, law_end


# ── Patrones de inicio predial (prioridad descendente) ──
# El backtrack del código original (buscar TITULO SEGUNDO o CAPITULO PRIMERO
# antes de "DEL IMPUESTO PREDIAL") se captura con patrones combinados.
_COAH_START_SPECS = [
    PatternSpec(re.compile(
        r"TITULO\s+SEGUNDO[\s\S]{0,2000}?DEL\s+IMPUESTO\s+PREDIAL",
        re.IGNORECASE,
    ), "titulo_predial"),
    PatternSpec(re.compile(
        r"CAPITULO\s+PRIMERO[\s\S]{0,500}?DEL\s+IMPUESTO\s+PREDIAL",
        re.IGNORECASE,
    ), "capitulo_predial"),
    PatternSpec(re.compile(
        r"DEL\s+IMPUESTO\s+PREDIAL",
        re.IGNORECASE,
    ), "impuesto_predial"),
]

_COAH_END_SPECS = [
    PatternSpec(re.compile(PATRON_FIN_PREDIAL, re.IGNORECASE), "adquisicion_traslado"),
]

_matcher = MuniMatcher(cve_ent=config.CVE_ENT, aliases=config.ALIASES)


def find_predial_in_window(
    norm_text: str, law_start: int, law_end: int,
) -> tuple[int, int, SegmentResult] | None:
    """
    Busca la sección de impuesto predial dentro de [law_start, law_end].
    Devuelve (predial_start, predial_end, SegmentResult) o None.
    """
    law_start = max(0, law_start)
    law_end = min(len(norm_text), law_end)
    if law_end <= law_start:
        return None

    sub = norm_text[law_start:law_end]

    result = find_predial_section(
        text=sub,
        start_specs=_COAH_START_SPECS,
        end_specs=_COAH_END_SPECS,
        max_chars=len(sub),  # sin cap, la ley ya está delimitada
    )

    if not result.found:
        return None

    predial_start = law_start + result.start_char
    predial_end = law_start + result.end_char

    if predial_end <= predial_start:
        return None

    return predial_start, predial_end, result


# ══════════════════════════════════════════════════════════════
# PASO 1: build_master (scripts 03 + 04 + 05)
# ══════════════════════════════════════════════════════════════

def run_build_master(adapter) -> Path:
    """
    Construye el master CSV cruzando directorio INEGI × índice de leyes.
    Incluye el patch especial para 2017.

    Equivale a ejecutar scripts 03 → 04 → 05 en secuencia.

    Returns:
        Path al master CSV final.
    """
    meta_dir = adapter.meta_dir
    catalogs_dir = Path("catalogs")
    ejercicio_range = adapter.ejercicio_range

    # ── Cargar datos de entrada ──
    leyes_csv = meta_dir / "ley_ingresos_index.csv"
    munis = _load_directorio(catalogs_dir, estado_cve="05")
    leyes_list = _load_leyes_index(leyes_csv)

    # Mapa (ejercicio, muni_norm) → fila de ley
    leyes_map = {}
    for row in leyes_list:
        key = (row["ejercicio"], row["muni_norm"])
        if key not in leyes_map:
            leyes_map[key] = row

    print(f"  Mapa de leyes: {len(leyes_map)} combinaciones ejercicio-municipio.")

    # ── Construir master ──
    pdf_cache = {}
    out_rows = []

    for ejercicio in ejercicio_range:
        print(f"  --- Ejercicio {ejercicio} ---")
        for m in munis:
            base = {
                "cve_mun": m["cve_mun"],
                "nom_mun": m["nom_mun"],
                "nom_cab": m["nom_cab"],
                "ejercicio": ejercicio,
                "status": "no_ley_en_PO",
                "municipio_en_PO": "",
                "num_po": "",
                "tipo_po": "",
                "tomo": "",
                "fecha_po": "",
                "pdf_file": "",
                "page_start_ley": "",
                "page_end_ley": "",
            }

            # Intentar con NOM_MUN
            key1 = (ejercicio, m["norm_mun"])
            ley = leyes_map.get(key1)

            # Fallback: NOM_CAB (p.ej. Ciudad Acuña vs Acuña)
            if not ley and m["norm_cab"]:
                key2 = (ejercicio, m["norm_cab"])
                ley = leyes_map.get(key2)

            if not ley:
                out_rows.append(base)
                continue

            base["status"] = "ley_encontrada"
            base["municipio_en_PO"] = ley["municipio"]
            base["num_po"] = ley["num_po"]
            base["tipo_po"] = ley["tipo_po"]
            base["tomo"] = ley["tomo"]
            base["fecha_po"] = ley["fecha_po"]
            base["pdf_file"] = ley["pdf_file"]

            pdf_path = Path(ley["pdf_file"])
            if not pdf_path.exists():
                base["status"] = "ley_encontrada_pdf_no_encontrado"
                out_rows.append(base)
                continue

            # Cargar texto + offsets (con caché)
            if pdf_path not in pdf_cache:
                raw_text, page_starts = build_text_and_offsets(pdf_path)
                pdf_cache[pdf_path] = (raw_text, page_starts)
            else:
                raw_text, page_starts = pdf_cache[pdf_path]

            span = find_ley_span(raw_text, m["nom_mun"])
            if not span:
                base["status"] = "ley_encontrada_sin_span"
                out_rows.append(base)
                continue

            start_idx, end_idx = span
            base["page_start_ley"] = idx_to_page(start_idx, page_starts)
            base["page_end_ley"] = idx_to_page(end_idx - 1, page_starts)
            out_rows.append(base)

    # ── Patch 2017: escanear PDFs de diciembre directamente ──
    out_rows = _patch_2017(out_rows, adapter)

    # ── Guardar master ──
    master_csv = meta_dir / "predial_master.csv"
    master_csv.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "cve_mun", "nom_mun", "nom_cab", "ejercicio", "status",
        "municipio_en_PO", "num_po", "tipo_po", "tomo", "fecha_po",
        "pdf_file", "page_start_ley", "page_end_ley",
    ]
    with master_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    total = len(out_rows)
    encontrados = sum(1 for r in out_rows if r["status"].startswith("ley_encontrada"))
    print(f"  Master escrito en {master_csv} ({total} filas, {encontrados} leyes localizadas)")

    return master_csv


def _patch_2017(out_rows: list[dict], adapter) -> list[dict]:
    """
    Patch para ejercicio 2017: escanea PDFs de diciembre 2016 directamente
    para encontrar leyes que el índice no detectó bien.

    Equivale a scripts 04 + 05.
    """
    base_2017_dir = adapter.pdf_raw_dir / "2017"
    if not base_2017_dir.exists():
        print(f"  [2017 patch] No existe {base_2017_dir}, saltando.")
        return out_rows

    pdf_paths = sorted(
        p for p in base_2017_dir.glob("*.pdf")
        if "DIC-2016" in p.name.upper() or "DIC_2016" in p.name.upper()
    )
    # También buscar .PDF (mayúsculas)
    pdf_paths += sorted(
        p for p in base_2017_dir.glob("*.PDF")
        if "DIC-2016" in p.name.upper() or "DIC_2016" in p.name.upper()
    )

    if not pdf_paths:
        print(f"  [2017 patch] No encontré PDFs de diciembre 2016 en {base_2017_dir}")
        return out_rows

    print(f"  [2017 patch] Escaneando {len(pdf_paths)} PDFs de diciembre 2016...")

    # Construir mapa de municipios para matching
    catalogs_dir = Path("catalogs")
    munis = _load_directorio(catalogs_dir, estado_cve="05")
    muni_dir_map = {m["norm_mun"]: m for m in munis}

    # Escanear PDFs buscando leyes de ingresos
    map_2017 = {}  # cve_mun → info
    patt = re.compile(
        r"NUMERO\s+(\d+)\.-\s*LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+([A-Z\s\.]+?),\s+COAHUILA",
        flags=re.DOTALL,
    )

    for pdf_path in pdf_paths:
        raw_text, page_starts = build_text_and_offsets(pdf_path)
        norm_text = norm(raw_text)
        matches = list(patt.finditer(norm_text))

        for i, m in enumerate(matches):
            muni_raw = m.group(2).strip()
            muni_norm = norm(muni_raw)
            start_idx = m.start()
            end_idx = matches[i + 1].start() if i < len(matches) - 1 else len(norm_text)

            muni_info = muni_dir_map.get(muni_norm)
            if muni_info:
                cve = muni_info["cve_mun"]
                map_2017[cve] = {
                    "pdf_file": str(pdf_path),
                    "page_start": idx_to_page(start_idx, page_starts),
                    "page_end": idx_to_page(end_idx - 1, page_starts),
                }

    print(f"  [2017 patch] Encontradas {len(map_2017)} leyes con match en directorio.")

    # Merge al master
    updated = 0
    for row in out_rows:
        try:
            ej = int(row.get("ejercicio") or 0)
        except ValueError:
            continue
        if ej != 2017:
            continue

        cve = (row.get("cve_mun") or "").strip()
        if cve in map_2017:
            info = map_2017[cve]
            row["status"] = "ley_encontrada_2017_patch"
            row["pdf_file"] = info["pdf_file"]
            row["page_start_ley"] = info["page_start"]
            row["page_end_ley"] = info["page_end"]
            updated += 1

    print(f"  [2017 patch] {updated} filas actualizadas en el master.")
    return out_rows


# ══════════════════════════════════════════════════════════════
# PASO 2: extract_predial_sections (script 10)
# ══════════════════════════════════════════════════════════════

def run_extract_sections(adapter) -> Path:
    """
    Localiza la sección de predial dentro de cada ley y genera:
      - TXT con el texto de la sección predial
      - PDF recortado con solo las páginas de predial

    Returns:
        Path al CSV bitácora de secciones.
    """
    meta_dir = adapter.meta_dir
    focus_dir = adapter.focus_dir
    prefijo = adapter.prefijo

    master_csv = meta_dir / "predial_master.csv"
    if not master_csv.exists():
        print(f"  [ERROR] No encuentro master: {master_csv}")
        print("  Ejecuta primero el paso 'master'.")
        return master_csv

    with master_csv.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        master_rows = list(reader)
        base_fields = reader.fieldnames or []

    if not master_rows:
        print("  [ERROR] Master vacío.")
        return master_csv

    extra_fields = [
        "predial_status", "predial_txt_file", "predial_pdf_file",
        "predial_page_start", "predial_page_end",
        "predial_start_idx", "predial_end_idx",
    ]
    fieldnames = base_fields + [f for f in extra_fields if f not in base_fields]

    pdf_cache = {}
    out_rows = []
    seg_rows: list[dict] = []

    for row in master_rows:
        ejercicio = row.get("ejercicio", "")
        municipio = row.get("nom_mun", "")
        status_ley = row.get("status", "")

        out = dict(row)
        for f in extra_fields:
            out[f] = ""

        # Sin ley → nada que hacer
        if not status_ley.startswith("ley_encontrada"):
            out["predial_status"] = "no_ley"
            out_rows.append(out)
            continue

        # Verificar PDF
        pdf_file = (row.get("pdf_file") or "").strip()
        if not pdf_file:
            out["predial_status"] = "pdf_missing"
            out_rows.append(out)
            continue

        pdf_path = Path(pdf_file)
        if not pdf_path.exists():
            out["predial_status"] = "pdf_missing"
            out_rows.append(out)
            continue

        # Obtener texto y offsets (con caché)
        if pdf_path not in pdf_cache:
            raw_text, page_starts = build_text_and_offsets(pdf_path)
            norm_text = norm(raw_text)
            pdf_cache[pdf_path] = (raw_text, norm_text, page_starts)
        else:
            raw_text, norm_text, page_starts = pdf_cache[pdf_path]

        n_pages = len(page_starts)

        # Span de la ley desde master (páginas → índices)
        law_span = None
        try:
            p_start_ley = int(row.get("page_start_ley") or 0)
            p_end_ley = int(row.get("page_end_ley") or 0)
        except ValueError:
            p_start_ley = p_end_ley = 0

        if p_start_ley > 0 and p_end_ley >= p_start_ley and p_start_ley <= n_pages:
            law_start_idx = page_starts[p_start_ley - 1]
            if p_end_ley < n_pages:
                law_end_idx = page_starts[p_end_ley]
            else:
                law_end_idx = len(norm_text)
            law_span = (law_start_idx, law_end_idx)

        # Intento 1: buscar predial dentro de las páginas de la ley
        span = None
        if law_span:
            span = find_predial_in_window(norm_text, *law_span)

        # Intento 2: buscar en todo el documento
        if not span:
            span = find_predial_in_window(norm_text, 0, len(norm_text))
            attempt_label = "ok_global"
        else:
            attempt_label = "ok_window"

        if not span:
            out["predial_status"] = "predial_missing"
            out_rows.append(out)
            continue

        start_idx, end_idx, seg_result = span
        p_start_pred = idx_to_page(start_idx, page_starts)
        p_end_pred = idx_to_page(end_idx - 1, page_starts)

        # Guardar TXT y PDF recortado
        muni_slug = _matcher.match(municipio).slug
        year_str = str(ejercicio)
        txt_path = focus_dir / year_str / f"{prefijo}_PREDIAL_{year_str}_{muni_slug}.txt"
        pdf_out_path = focus_dir / year_str / f"{prefijo}_PREDIAL_{year_str}_{muni_slug}.pdf"

        txt_path.parent.mkdir(parents=True, exist_ok=True)
        txt_path.write_text(raw_text[start_idx:end_idx], encoding="utf-8")
        save_pdf_slice(pdf_path, p_start_pred, p_end_pred, pdf_out_path)

        out["predial_status"] = attempt_label
        out["predial_txt_file"] = str(txt_path)
        out["predial_pdf_file"] = str(pdf_out_path)
        out["predial_page_start"] = p_start_pred
        out["predial_page_end"] = p_end_pred
        out["predial_start_idx"] = start_idx
        out["predial_end_idx"] = end_idx

        out_rows.append(out)

        seg_rows.append({
            "ejercicio": ejercicio,
            "municipio": municipio,
            "slug": muni_slug,
            "source_pdf": pdf_file,
            "predial_found": "true",
            "predial_method": attempt_label,
            "predial_page_start": p_start_pred,
            "predial_page_end": p_end_pred,
            "txt_file": txt_path.name,
            "txt_chars": end_idx - start_idx,
            **hitl_extra_columns(seg_result),
        })

    # Guardar bitácora
    sections_csv = meta_dir / "predial_sections.csv"
    sections_csv.parent.mkdir(parents=True, exist_ok=True)

    with sections_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(out_rows)

    # segment.csv estándar (compatible con HITL detectors)
    _seg_fields = [
        "ejercicio", "municipio", "slug", "source_pdf",
        "predial_found", "predial_method",
        "predial_page_start", "predial_page_end",
        "txt_file", "txt_chars",
        *HITL_EXTRA_FIELDS,
    ]
    seg_csv = meta_dir / "segment.csv"
    with seg_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_seg_fields)
        writer.writeheader()
        writer.writerows(seg_rows)
    print(f"  segment.csv: {len(seg_rows)} filas → {seg_csv}")

    # Resumen
    counts = {}
    for r in out_rows:
        s = r["predial_status"]
        counts[s] = counts.get(s, 0) + 1

    print(f"  Bitácora escrita en {sections_csv} ({len(out_rows)} filas)")
    print("  Resumen de status:")
    for k, v in sorted(counts.items()):
        print(f"    {k}: {v}")

    return sections_csv
