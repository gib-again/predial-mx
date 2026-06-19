"""
Segmentación de leyes de ingresos y extracción de la sección de Impuesto Predial (Querétaro).

Objetivo:
  - Por cada municipio y ejercicio fiscal, recortar del PDF la sección de "Impuesto Predial".
  - Guardar:
      data/queretaro/focus_predial/{EJERCICIO}/QRO_PREDIAL_{EJERCICIO}_{municipio_slug}.txt
      data/queretaro/focus_predial/{EJERCICIO}/QRO_PREDIAL_{EJERCICIO}_{municipio_slug}.pdf

Punto clave:
  - Cada "tomo/ejemplar" suele venir en PARTES (-01, -02, -03, ...).
    NO debemos tratar cada parte como documento separado.
  - Aquí agrupamos PDFs por "base" (todo antes de "-NN.pdf") y concatenamos texto/páginas
    en orden para:
      - MASTER: detectar inicios de cada "Ley de Ingresos del Municipio ..."
      - SEGMENT: recortar predial usando el mapeo línea→(parte,página)

Heurísticas principales:
  - Detectar una ley por el TÍTULO:
        "LEY DE INGRESOS DEL MUNICIPIO DE {MUNICIPIO} ... PARA EL EJERCICIO FISCAL {YYYY}"
    validando que aparezca "Artículo 1" poco después (evita TOC/índices y menciones sueltas).
  - Predial:
      - Inicio = "Artículo N (10..20). El Impuesto Predial ..."
      - Fin    = inicio de "Artículo N+1. El Impuesto ..." (siguiente impuesto)
"""

from __future__ import annotations

import csv
import re
import unicodedata
from pathlib import Path
from typing import Optional

import fitz  # PyMuPDF

from src.core.muni_matcher import MuniMatcher
from src.core.segment_utils import HITL_EXTRA_FIELDS, hitl_extra_columns
from src.estados.queretaro import config

# ──────────────────────────────────────────────────────────────
# Matcher unificado de municipios INEGI
# ──────────────────────────────────────────────────────────────

_matcher = MuniMatcher(cve_ent=config.CVE_ENT, aliases=config.ALIASES)


def _clean_muni_name(raw: str) -> str:
    """
    Limpieza ligera del municipio extraído del título.

    Importante:
      - NO borrar "Querétaro" si es el municipio.
      - Sí borrar ", Querétaro" cuando viene separado por coma (estado).
      - Sí borrar "QRO" como abreviatura de estado.
    """
    s = (raw or "").strip()
    s = re.sub(r"\s*,?\s*QRO\.?\s*$", "", s, flags=re.I).strip()
    s = re.sub(r"\s*,\s*QUER[EÉ]TARO\s*$", "", s, flags=re.I).strip()
    s = s.rstrip(",. ")
    return s

# ----------------------------------------------
# Fixed hardcoded mapping for known OCR issues in municipio names:

def _norm_ascii(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", s).strip().lower()

def _strip_slug_queretaro_suffix(slug: str) -> str:
    # Solo quita el sufijo final exacto "_queretaro"
    return re.sub(r"_queretaro$", "", slug or "")

def _hardcoded_postfix_muni_fix(
    municipio: str,
    municipio_slug: str,
    *,
    law_text: str = "",
    predial_text: str = "",
) -> tuple[str, str, str]:
    """
    Devuelve (municipio, municipio_slug, action)
      action ∈ {"ok", "drop"}
    """
    muni = (municipio or "").strip()
    slug = (municipio_slug or "").strip()

    # 1) quitar sufijo _queretaro
    slug = _strip_slug_queretaro_suffix(slug)

    # 4) cadereyta -> cadereyta_de_montes
    if slug == "cadereyta":
        slug = "cadereyta_de_montes"
        if _norm_ascii(muni) == "cadereyta":
            muni = "Cadereyta de Montes"

    # 3) basura explícita
    if slug == "cadereyta_de_montes__dup1":
        return muni, slug, "drop"

    # 2) falso positivo que realmente es Colón
    if slug == "cadereyta_de_montes__dup24":
        muni = "Colón"
        slug = "colon"
    
    return muni, slug, "ok"


# ──────────────────────────────────────────────────────────────
# Agrupar PDFs por "documento" (base sin -NN)
# ──────────────────────────────────────────────────────────────

_RE_PART = re.compile(r"^(?P<base>.+)-(?P<part>\d{2})\.pdf$", re.IGNORECASE)


def _group_pdf_parts(pdf_raw_dir: Path) -> dict[str, list[Path]]:
    """
    Devuelve dict doc_id -> [paths...], donde:
      doc_id = "{year_folder}/{base}"
      base = nombre de archivo sin sufijo "-NN.pdf"
    """
    groups: dict[str, list[Path]] = {}

    for pdf_path in sorted(pdf_raw_dir.rglob("QRO_RAW_*.pdf")):
        year_folder = pdf_path.parent.name
        if not re.match(r"^\d{4}$", year_folder):
            year_folder = "unknown"

        name = pdf_path.name
        m = _RE_PART.match(name)
        if m:
            base = m.group("base")
        else:
            base = name[:-4]

        doc_id = f"{year_folder}/{base}"
        groups.setdefault(doc_id, []).append(pdf_path)

    def part_key(p: Path) -> int:
        m = _RE_PART.match(p.name)
        if not m:
            return 0
        return int(m.group("part"))

    for k in list(groups.keys()):
        groups[k] = sorted(groups[k], key=part_key)

    return groups


# ──────────────────────────────────────────────────────────────
# MASTER: detectar inicio de cada ley en un documento agrupado
# ──────────────────────────────────────────────────────────────

_RE_LEY_TITLE = re.compile(
    r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+"
    r"(?P<muni>.+?)\s*"
    r"(?:,?\s*QRO\.?)?\s*"
    r"(?:,?\s*PARA\s+EL\s+EJERCICIO\s+FISCAL\s+(?P<ej>\d{4}))",
    re.IGNORECASE,
)

_RE_EJERCICIO = re.compile(r"EJERCICIO\s+FISCAL\s+(?P<ej>\d{4})", re.IGNORECASE)
_RE_ART1 = re.compile(r"\bArt[ií]culo\s+(?:1|Primero)\b", re.IGNORECASE)
_RE_EXPIDO_PROMULGO = re.compile(r"\bexpido\s+y\s+promulgo\b", re.IGNORECASE)


def _detect_laws_in_lines(all_lines: list[str]) -> list[dict]:
    """
    Devuelve lista de dicts: municipio_raw, municipio, ejercicio, start_line.
    """
    results: list[dict] = []
    n_lines = len(all_lines)

    last_seen = set()

    for i in range(n_lines):
        combined = " ".join(
            all_lines[j].strip() for j in range(i, min(i + 3, n_lines))
            if all_lines[j].strip()
        )
        if not combined:
            continue

        m = _RE_LEY_TITLE.search(combined)
        if not m:
            continue

        muni_raw = _clean_muni_name(m.group("muni"))
        ejercicio = (m.group("ej") or "").strip()

        if not ejercicio:
            look = "\n".join(all_lines[i:min(i + 120, n_lines)])
            mm = _RE_EJERCICIO.search(look)
            if mm:
                ejercicio = mm.group("ej")

        after = "\n".join(all_lines[i:min(i + 160, n_lines)])
        if not _RE_ART1.search(after):
            continue

        prev = "\n".join(all_lines[max(0, i - 60): i + 1])
        if _RE_EXPIDO_PROMULGO.search(prev):
            continue

        mr = _matcher.match(muni_raw)
        muni_canon = muni_raw  # keep cleaned name for display
        muni_slug = mr.slug

        key = (muni_slug, ejercicio)
        if key in last_seen and results and (i - results[-1]["start_line"] < 25):
            continue
        last_seen.add(key)

        results.append({
            "municipio_raw": muni_raw,
            "municipio": muni_canon,
            "slug": muni_slug,
            "match_score": f"{mr.score:.3f}",
            "match_method": mr.method,
            "ejercicio": ejercicio,
            "start_line": i,
        })

    results.sort(key=lambda r: r["start_line"])
    return results


def run_build_master(adapter) -> Path:
    """
    Escanea documentos (agrupados por base), concatena texto, detecta leyes.

    Output: data/queretaro/meta/muni_starts.csv
    """
    meta_dir: Path = adapter.meta_dir
    pdf_raw_dir: Path = adapter.pdf_raw_dir
    meta_dir.mkdir(parents=True, exist_ok=True)

    groups = _group_pdf_parts(pdf_raw_dir)
    doc_ids = sorted(groups.keys())
    print(f"  PDFs a analizar: {sum(len(v) for v in groups.values())}")
    print(f"  Documentos agrupados: {len(doc_ids)}")

    rows: list[dict] = []

    for di, doc_id in enumerate(doc_ids, 1):
        parts = groups[doc_id]
        if di % 10 == 0 or di == len(doc_ids):
            print(f"    [{di}/{len(doc_ids)}] {doc_id} ({len(parts)} parts)...")

        all_lines: list[str] = []
        line_to_pos: dict[int, tuple[int, int]] = {}  # line -> (part_idx, page_1based)

        try:
            for part_idx, pdf_path in enumerate(parts):
                with fitz.open(pdf_path) as doc:
                    for page_idx in range(doc.page_count):
                        text = doc[page_idx].get_text("text") or ""
                        for line in text.splitlines():
                            line_to_pos[len(all_lines)] = (part_idx, page_idx + 1)
                            all_lines.append(line)

            laws = _detect_laws_in_lines(all_lines)
            for law in laws:
                part_idx, page = line_to_pos.get(law["start_line"], (0, 1))
                rows.append({
                    "doc_id": doc_id,
                    "parts": ";".join(str(p.relative_to(pdf_raw_dir)).replace("\\", "/") for p in parts),
                    "municipio_raw": law["municipio_raw"],
                    "municipio": law["municipio"],
                    "slug": law["slug"],
                    "match_score": law["match_score"],
                    "match_method": law["match_method"],
                    "ejercicio": law["ejercicio"] or "",
                    "start_part": part_idx + 1,
                    "start_page": page,
                    "start_line": law["start_line"],
                })

        except Exception as e:
            print(f"    [ERROR] {doc_id}: {e}")

    muni_starts_csv = meta_dir / "muni_starts.csv"
    fieldnames = [
        "doc_id", "parts",
        "municipio_raw", "municipio", "slug", "match_score", "match_method",
        "ejercicio",
        "start_part", "start_page", "start_line",
    ]
    with muni_starts_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["doc_id"], int(r["start_line"]))))

    n_munis = len(set(r["municipio"] for r in rows))
    print(f"  Leyes detectadas: {len(rows)} ({n_munis} municipios únicos) → {muni_starts_csv}")
    return muni_starts_csv


# ──────────────────────────────────────────────────────────────
# SEGMENT: extraer sección predial dentro de cada ley
# ──────────────────────────────────────────────────────────────

_RE_CRITERIOS = re.compile(r"CRITERIOS\s+PARA\s+LA\s+FORMULACI[OÓ]N", re.IGNORECASE)
_RE_ANEXOS = re.compile(r"^\s*ANEXOS\s*$", re.IGNORECASE | re.MULTILINE)
_RE_TRANSITORIOS = re.compile(r"TRANSITORIOS", re.IGNORECASE)

_RE_ART_PREDIAL = re.compile(
    r"^\s*Art[ií]culo\s+(?P<n>1[0-9]|20)\s*[\.\-–:]\s*(?:El\s+)?Imp[uú]esto\s+Predial\b",
    re.IGNORECASE,
)

def _re_next_impuesto(n_plus_1: int) -> re.Pattern:
    return re.compile(
        rf"^\s*Art[ií]culo\s+{n_plus_1}\s*[\.\-–:]\s*(?:El\s+)?Imp[uú]esto\b",
        re.IGNORECASE,
    )


def _match_in_two_lines(pat: re.Pattern, lines: list[str], i: int) -> Optional[re.Match]:
    if i < 0 or i >= len(lines):
        return None
    m = pat.search(lines[i])
    if m:
        return m
    if i + 1 < len(lines):
        m2 = pat.search((lines[i] + " " + lines[i + 1]).strip())
        if m2:
            return m2
    return None


def _find_predial_range_in_lines(all_lines: list[str], start: int, end: int) -> tuple[Optional[int], Optional[int], Optional[int]]:
    window_text = "\n".join(all_lines[start:end + 1])
    cutoff = end
    m1 = _RE_CRITERIOS.search(window_text)
    m2 = _RE_ANEXOS.search(window_text)
    if m1:
        cutoff = start + window_text[:m1.start()].count("\n")
    if m2:
        cutoff2 = start + window_text[:m2.start()].count("\n")
        cutoff = min(cutoff, cutoff2)

    s_line = None
    n_art = None
    for i in range(start, min(cutoff + 1, len(all_lines))):
        m = _match_in_two_lines(_RE_ART_PREDIAL, all_lines, i)
        if m:
            s_line = i
            n_art = int(m.group("n"))
            break

    if s_line is None or n_art is None:
        return None, None, None

    end_pat = _re_next_impuesto(n_art + 1)
    e_line = cutoff
    for j in range(s_line + 1, min(cutoff + 1, len(all_lines))):
        if _match_in_two_lines(end_pat, all_lines, j):
            e_line = j - 1
            break

    if e_line == cutoff:
        tail_text = "\n".join(all_lines[s_line:cutoff + 1])
        mt = _RE_TRANSITORIOS.search(tail_text)
        mc = _RE_CRITERIOS.search(tail_text)
        ma = _RE_ANEXOS.search(tail_text)
        cut_pos = None
        for mm in [mt, mc, ma]:
            if mm:
                cut_pos = mm.start() if cut_pos is None else min(cut_pos, mm.start())
        if cut_pos is not None:
            e_line = s_line + tail_text[:cut_pos].count("\n")

    return s_line, e_line, n_art


def _build_lines_and_maps(parts: list[Path]) -> tuple[list[str], list[tuple[int, int]], list[int]]:
    all_lines: list[str] = []
    line_to_pos: list[tuple[int, int]] = []
    part_page_counts: list[int] = []

    for part_idx, pdf_path in enumerate(parts):
        with fitz.open(pdf_path) as doc:
            part_page_counts.append(doc.page_count)
            for page_idx in range(doc.page_count):
                text = doc[page_idx].get_text("text") or ""
                for line in text.splitlines():
                    all_lines.append(line)
                    line_to_pos.append((part_idx, page_idx))

    return all_lines, line_to_pos, part_page_counts


def _insert_pages_across_parts(
    new_doc: fitz.Document,
    part_docs: list[fitz.Document],
    start_pos: tuple[int, int],
    end_pos: tuple[int, int],
) -> None:
    sp, spg = start_pos
    ep, epg = end_pos

    if sp > ep or (sp == ep and spg > epg):
        return

    for pi in range(sp, ep + 1):
        doc = part_docs[pi]
        if pi == sp and pi == ep:
            new_doc.insert_pdf(doc, from_page=spg, to_page=epg)
        elif pi == sp:
            new_doc.insert_pdf(doc, from_page=spg, to_page=doc.page_count - 1)
        elif pi == ep:
            new_doc.insert_pdf(doc, from_page=0, to_page=epg)
        else:
            new_doc.insert_pdf(doc, from_page=0, to_page=doc.page_count - 1)


def run_extract_sections(adapter) -> Path:
    meta_dir: Path = adapter.meta_dir
    pdf_raw_dir: Path = adapter.pdf_raw_dir
    focus_dir: Path = adapter.focus_dir
    prefijo: str = adapter.prefijo

    muni_starts_csv = meta_dir / "muni_starts.csv"
    if not muni_starts_csv.exists():
        raise FileNotFoundError(f"No existe {muni_starts_csv}. Ejecuta 'master' primero.")

    with muni_starts_csv.open(encoding="utf-8") as f:
        starts = list(csv.DictReader(f))

    by_doc: dict[str, list[dict]] = {}
    for r in starts:
        by_doc.setdefault(r["doc_id"], []).append(r)

    log_rows: list[dict] = []

    for doc_id, group in sorted(by_doc.items(), key=lambda x: x[0]):
        parts_rel = (group[0].get("parts") or "").split(";")
        parts = [pdf_raw_dir / Path(p) for p in parts_rel if p]
        parts = [p for p in parts if p.exists()]

        if not parts:
            print(f"  [WARN] Sin partes para {doc_id}")
            continue

        try:
            all_lines, line_to_pos, _ = _build_lines_and_maps(parts)
            group.sort(key=lambda r: int(r["start_line"]))

            part_docs = [fitz.open(p) for p in parts]
            try:
                for idx, row in enumerate(group):
                    muni = row["municipio"]
                    ejercicio = (row.get("ejercicio") or "").strip()
                    if not ejercicio:
                        ejercicio = doc_id.split("/", 1)[0] if "/" in doc_id else "unknown"

                    start_line = int(row["start_line"])
                    if idx + 1 < len(group):
                        end_line = int(group[idx + 1]["start_line"]) - 1
                    else:
                        end_line = len(all_lines) - 1

                    s_line, e_line, n_art = _find_predial_range_in_lines(all_lines, start_line, end_line)

                    muni_slug = row.get("slug") or _matcher.match(muni).slug

                    if s_line is None or e_line is None:
                        log_rows.append({
                            "municipio": muni,
                            "municipio_slug": muni_slug,
                            "ejercicio": ejercicio,
                            "doc_id": doc_id,
                            "ley_lines": f"{start_line}-{end_line}",
                            "predial_lines": "",
                            "predial_chars": 0,
                            "status": "no_predial_found",
                        })
                        continue

                    predial_text = "\n".join(all_lines[s_line:e_line + 1]).strip()
                    if not predial_text:
                        log_rows.append({
                            "municipio": muni,
                            "municipio_slug": muni_slug,
                            "ejercicio": ejercicio,
                            "doc_id": doc_id,
                            "ley_lines": f"{start_line}-{end_line}",
                            "predial_lines": f"{s_line}-{e_line}",
                            "predial_chars": 0,
                            "status": "predial_empty",
                        })
                        continue

                    # Hardcoded fixes puntuales (slug/nombre basados en texto real)
                    muni, muni_slug, action = _hardcoded_postfix_muni_fix(
                        muni,
                        muni_slug,
                        predial_text=predial_text,  # si lo tienes disponible
                    )

                    if action == "drop":
                        log_rows.append({
                            "municipio": muni,
                            "municipio_slug": muni_slug,
                            "ejercicio": ejercicio,   # o yyyy, según tu script
                            "doc_id": doc_id if "doc_id" in locals() else "",
                            "status": "dropped_hardcoded_bad_dup",
                        })
                        continue

                    txt_path = focus_dir / ejercicio / f"{prefijo}_PREDIAL_{ejercicio}_{muni_slug}.txt"
                    txt_path.parent.mkdir(parents=True, exist_ok=True)
                    if txt_path.exists():
                        txt_path = focus_dir / ejercicio / f"{prefijo}_PREDIAL_{ejercicio}_{muni_slug}__dup{idx+1}.txt"
                    txt_path.write_text(predial_text, encoding="utf-8")

                    start_pos = line_to_pos[s_line]
                    end_pos = line_to_pos[e_line]
                    new_doc = fitz.open()
                    _insert_pages_across_parts(new_doc, part_docs, start_pos, end_pos)

                    pdf_out = focus_dir / ejercicio / f"{prefijo}_PREDIAL_{ejercicio}_{muni_slug}.pdf"
                    pdf_out.parent.mkdir(parents=True, exist_ok=True)
                    if pdf_out.exists():
                        pdf_out = focus_dir / ejercicio / f"{prefijo}_PREDIAL_{ejercicio}_{muni_slug}__dup{idx+1}.pdf"

                    if new_doc.page_count == 0:
                        new_doc.close()
                        log_rows.append({
                            "municipio": muni,
                            "municipio_slug": muni_slug,
                            "ejercicio": ejercicio,
                            "doc_id": doc_id,
                            "ley_lines": f"{start_line}-{end_line}",
                            "predial_lines": f"{s_line}-{e_line}",
                            "predial_chars": len(predial_text),
                            "status": "zero_pages",
                        })
                        continue

                    new_doc.save(str(pdf_out), deflate=True)
                    new_doc.close()

                    # Inicio de la ley (Nivel 1): página dentro de la parte que
                    # la abre — para el botón "inicio de la ley" en HITL (§5).
                    try:
                        _sp_idx = int(row.get("start_part", 1)) - 1
                    except (TypeError, ValueError):
                        _sp_idx = 0
                    ley_part_pdf = (
                        str(parts[_sp_idx].as_posix())
                        if 0 <= _sp_idx < len(parts) else ""
                    )
                    log_rows.append({
                        "municipio": muni,
                        "municipio_slug": muni_slug,
                        "ejercicio": ejercicio,
                        "doc_id": doc_id,
                        "ley_lines": f"{start_line}-{end_line}",
                        "predial_lines": f"{s_line}-{e_line}",
                        "predial_chars": len(predial_text),
                        "status": "ok",
                        "predial_articulo": f"{n_art}",
                        "parts": ";".join(p.name for p in parts),
                        "ley_page_start": row.get("start_page", ""),
                        "ley_source_pdf": ley_part_pdf,
                    })

            finally:
                for d in part_docs:
                    d.close()

        except Exception as e:
            print(f"    [ERROR] {doc_id}: {e}")

    sections_csv = meta_dir / "predial_sections.csv"
    fieldnames = [
        "municipio", "municipio_slug", "ejercicio",
        "doc_id", "ley_lines", "predial_lines",
        "predial_chars", "status",
        "predial_articulo", "parts",
    ]
    with sections_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for r in log_rows:
            for fn in fieldnames:
                r.setdefault(fn, "")
        writer.writerows(log_rows)

    # segment.csv estándar (compatible con HITL detectors)
    _seg_fields = [
        "ejercicio", "municipio", "slug", "source_pdf",
        "ley_page_start",
        "predial_found", "predial_method",
        "predial_page_start", "predial_page_end",
        "txt_file", "txt_chars",
        *HITL_EXTRA_FIELDS,
    ]
    seg_rows: list[dict] = []
    for r in log_rows:
        if r.get("status") != "ok":
            continue
        slug = r.get("municipio_slug", "")
        ej = r.get("ejercicio", "")
        # source_pdf = la parte real que abre la ley (servible por el UI), no el
        # doc_id base; ley_page_start = página de inicio de la ley en esa parte.
        seg_rows.append({
            "ejercicio": ej,
            "municipio": r.get("municipio", ""),
            "slug": slug,
            "source_pdf": r.get("ley_source_pdf") or r.get("doc_id", ""),
            "ley_page_start": r.get("ley_page_start", ""),
            "predial_found": "true",
            "predial_method": "articulo_predial",
            "predial_page_start": "",
            "predial_page_end": "",
            "txt_file": f"{prefijo}_PREDIAL_{ej}_{slug}.txt",
            "txt_chars": r.get("predial_chars", 0),
            **hitl_extra_columns(),
        })
    seg_csv = meta_dir / "segment.csv"
    with seg_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_seg_fields)
        writer.writeheader()
        writer.writerows(seg_rows)
    print(f"  segment.csv: {len(seg_rows)} filas → {seg_csv}")

    ok_count = sum(1 for r in log_rows if r["status"] == "ok")
    print(f"  Secciones extraídas: {ok_count}/{len(log_rows)} → {sections_csv}")
    return sections_csv