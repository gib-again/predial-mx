"""
Descarga de PDFs del Periódico Oficial de Querétaro ("La Sombra de Arteaga").

Flujo:
  1) Descargar índices anuales (2010 y 2011+). 2009 no tiene índice (hardcoded).
  2) Parsear índices para obtener hits de "Ley de Ingresos del Municipio de X" (texto + ejercicio).
  3) Canonizar municipio contra catálogo INEGI (CVE_ENT=22) para benchmark/QA.
  4) Generar URLs candidatas (ejemplar × partes) usando URL_TEMPLATE.
  5) Agregar URLs hardcoded (2009/2010/2011).
  6) Descargar PDFs y guardarlos en pdf_raw/{YYYY}/...

Notas:
  - Los PDFs descargados se guardan como:
        data/queretaro/pdf_raw/{YYYY}/QRO_RAW_{...}-{PART}.pdf
  - El {YYYY} aquí es el año de publicación / ruta, NO necesariamente el ejercicio fiscal.
"""

from __future__ import annotations

import csv
import random
import re
import time
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse, parse_qs

import requests
import fitz  # PyMuPDF

from src.core.text_utils import slugify
from src.estados.queretaro.config import (
    URL_TEMPLATE,
    USER_AGENT,
    REFERER,
    YEAR_MIN,
    YEAR_MAX,
    MAX_PARTS_PER_ISSUE,
    RATE_LIMIT_MIN,
    RATE_LIMIT_MAX,
    SPANISH_MONTHS,
    INDEX_URL_TEMPLATE,
    INDEX_URL_2010,
    HARDCODED_URLS,
)

# ──────────────────────────────────────────────────────────────
# Catálogo de municipios INEGI (para benchmark y canonización)
# ──────────────────────────────────────────────────────────────

def _muni_key(s: str) -> str:
    s = (s or "").strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(municipio|mun)\s+de\s+", "", s).strip()
    s = re.sub(r"\bqro\b$", "", s).strip()
    return s


def _find_catalog_path() -> Path:
    here = Path(__file__).resolve()
    for p in [here] + list(here.parents):
        cand = p / "catalogs" / "municipios_inegi.csv"
        if cand.exists():
            return cand
    return Path("catalogs/municipios_inegi.csv")


_MUNI_CATALOG: Optional[dict[str, str]] = None


def _load_inegi_munis_qro() -> dict[str, str]:
    """
    Devuelve dict: key_normalizada -> NOM_MUN (solo Querétaro, CVE_ENT=22).
    """
    global _MUNI_CATALOG
    if _MUNI_CATALOG is not None:
        return _MUNI_CATALOG

    path = _find_catalog_path()
    d: dict[str, str] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if (r.get("CVE_ENT") or "").strip() != "22":
                continue
            nom = (r.get("NOM_MUN") or "").strip()
            if not nom:
                continue
            d[_muni_key(nom)] = nom

    # Aliases frecuentes
    d[_muni_key("Santiago de Queretaro")] = "Querétaro"
    d[_muni_key("Santiago de Querétaro")] = "Querétaro"
    d[_muni_key("Queretaro")] = "Querétaro"
    d[_muni_key("El Marques")] = "El Marqués"

    _MUNI_CATALOG = d
    return d


def _map_municipio_to_inegi(raw_name: str, min_score: float = 0.86) -> tuple[str, float, str]:
    """
    Devuelve (municipio_canon, score, method) donde method ∈ {exact, alias, fuzzy, fallback}.
    """
    cat = _load_inegi_munis_qro()
    k = _muni_key(raw_name)

    if k in cat:
        canon = cat[k]
        method = "alias" if _muni_key(canon) != k else "exact"
        return canon, 1.0, method

    best_name = raw_name.strip()
    best_score = 0.0
    for kk, canon in cat.items():
        score = SequenceMatcher(None, k, kk).ratio()
        if score > best_score:
            best_score = score
            best_name = canon

    if best_score >= min_score:
        return best_name, best_score, "fuzzy"

    return raw_name.strip(), best_score, "fallback"


# ──────────────────────────────────────────────────────────────
# HTTP helpers
# ──────────────────────────────────────────────────────────────

def _get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Referer": REFERER,
        "Accept": "text/html,application/pdf;q=0.9,*/*;q=0.8",
    })
    return session


def _http_get(session: requests.Session, url: str, timeout: int = 40) -> Optional[bytes]:
    try:
        r = session.get(url, timeout=timeout)
        r.raise_for_status()
        return r.content
    except Exception:
        return None


def _looks_like_pdf(b: bytes) -> bool:
    return len(b) > 4 and b[:4] == b"%PDF"


def _sleep_polite() -> None:
    time.sleep(random.uniform(RATE_LIMIT_MIN, RATE_LIMIT_MAX))


# ──────────────────────────────────────────────────────────────
# Index parsing
# ──────────────────────────────────────────────────────────────

_RE_LEY = re.compile(r"Ley\s+de\s+Ingresos\s+del\s+Municipio\s+de\s+([^\n,.]+)", re.I)
_RE_EJERCICIO = re.compile(r"ejercicio\s+(?:fiscal\s+)?(20\d{2})", re.I)
_RE_PO_HEADER = re.compile(
    r"P\.\s*O\.\s*(?:No\.|Núm\.?)\s*(\d+)\s*[,–-]?\s*"
    r"(\d{1,2}\s+de\s+[A-Za-zÁÉÍÓÚáéíóúñ]+?\s+de\s+\d{4})",
    re.I,
)


def _parse_date_str(fecha_str: str) -> tuple[Optional[int], Optional[int]]:
    """Extrae (mes, año) de '24 de diciembre de 2023'."""
    m = re.search(r"de\s+([a-záéíóúñ]+)\s+de\s+(\d{4})", fecha_str, re.I)
    if not m:
        return None, None
    mes_norm = (m.group(1).lower()
                .replace("á", "a").replace("é", "e").replace("í", "i")
                .replace("ó", "o").replace("ú", "u"))
    mm = SPANISH_MONTHS.get(mes_norm)
    return mm, int(m.group(2))


def _parse_index_pdf(pdf_path: Path) -> list[dict]:
    """Parsea un índice anual y extrae hits de leyes de ingresos."""
    hits: list[dict] = []
    with fitz.open(pdf_path) as doc:
        text = "\n".join(page.get_text("text") or "" for page in doc)

    headers = list(_RE_PO_HEADER.finditer(text))
    ends = [h.end() for h in headers] + [len(text)]

    for i, hm in enumerate(headers):
        ejemplar = hm.group(1)
        fecha_str = hm.group(2)
        block = text[hm.end():ends[i + 1]]

        for lm in _RE_LEY.finditer(block):
            muni_raw = lm.group(1).strip()
            tail = block[lm.end():lm.end() + 250]
            em = _RE_EJERCICIO.search(tail)
            ejercicio = em.group(1) if em else ""

            muni_canon, score, method = _map_municipio_to_inegi(muni_raw)

            hits.append({
                "ejemplar": ejemplar,
                "fecha_str": fecha_str,
                "municipio_texto": muni_raw,
                "municipio": muni_canon,
                "municipio_slug": slugify(muni_canon),
                "match_score": f"{score:.3f}",
                "match_method": method,
                "ejercicio": ejercicio,
            })

    return hits


# ──────────────────────────────────────────────────────────────
# URL building / naming
# ──────────────────────────────────────────────────────────────

def _filename_from_url(url: str) -> str:
    """
    Obtiene nombre del archivo del URL (incluye soporte para getfile.php?p1=...).
    """
    u = urlparse(url)
    qs = parse_qs(u.query or "")
    if "p1" in qs and qs["p1"]:
        return qs["p1"][0]
    name = Path(u.path).name
    return name or "unknown.pdf"


# ──────────────────────────────────────────────────────────────
# Entry point
# ──────────────────────────────────────────────────────────────

def run_download(adapter) -> Path:
    """
    Pipeline completo: parsea índices → genera URLs → descarga PDFs.
    """
    data_dir: Path = adapter.data_dir
    meta_dir: Path = adapter.meta_dir
    pdf_raw_dir: Path = adapter.pdf_raw_dir
    indices_dir = data_dir / "indices"

    for d in (meta_dir, pdf_raw_dir, indices_dir):
        d.mkdir(parents=True, exist_ok=True)

    session = _get_session()

    # ── Paso 0: Descargar índices anuales ──
    print("  [0/3] Descargando índices anuales...")
    for anio in range(max(YEAR_MIN, 2010), YEAR_MAX + 1):
        idx_path = indices_dir / f"indice-{anio}.pdf"
        if idx_path.exists() and idx_path.stat().st_size > 1000:
            continue

        if anio == 2010:
            url = INDEX_URL_2010
        else:
            url = INDEX_URL_TEMPLATE.format(YYYY=anio)

        payload = _http_get(session, url)
        if payload and _looks_like_pdf(payload):
            idx_path.write_bytes(payload)
            print(f"    [OK] Índice {anio}")
        else:
            print(f"    [WARN] No se pudo descargar índice {anio}")

        _sleep_polite()

    # ── Paso 1: Parsear índices ──
    print("  [1/3] Parseando índices...")
    all_hits: list[dict] = []
    for pdf_path in sorted(indices_dir.glob("indice-*.pdf")):
        m = re.search(r"(\d{4})", pdf_path.name)
        if not m:
            continue
        anio = int(m.group(1))
        try:
            hits = _parse_index_pdf(pdf_path)
            for h in hits:
                h["anio_indice"] = anio
            all_hits.extend(hits)
            print(f"    Índice {anio}: {len(hits)} hits")
        except Exception as e:
            print(f"    [ERROR] Índice {anio}: {e}")

    # Guardar index_hits
    hits_csv = meta_dir / "index_hits.csv"
    fieldnames_h = [
        "anio_indice", "ejemplar", "fecha_str",
        "municipio_texto", "municipio", "municipio_slug",
        "match_score", "match_method", "ejercicio",
    ]
    with hits_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_h)
        writer.writeheader()
        writer.writerows(all_hits)

    # Benchmark rápido
    expected = set(_load_inegi_munis_qro().values())
    found = set(h["municipio"] for h in all_hits if h.get("municipio"))
    missing = sorted(expected - found)
    print(f"    Benchmark INEGI (QRO): {len(expected)} municipios | detectados en índices: {len(found)}")
    if missing:
        print(f"    [WARN] Municipios ausentes en índices (posible): {missing}")

    # ── Paso 2: Generar URLs candidatas ──
    print("  [2/3] Generando URLs candidatas...")
    candidates: list[dict] = []

    for h in all_hits:
        mm, yyyy = _parse_date_str(h["fecha_str"])
        if not mm or not yyyy:
            continue
        for part in range(1, MAX_PARTS_PER_ISSUE + 1):
            url = URL_TEMPLATE.format(
                YYYY=yyyy,
                MM=f"{mm:02d}",
                ISSUE=h["ejemplar"],
                PART=f"{part:02d}",
            )
            candidates.append({
                "YYYY": str(yyyy),
                "MM": f"{mm:02d}",
                "ejemplar": h["ejemplar"],
                "parte": f"{part:02d}",
                "url": url,
                "hardcoded": "0",
            })

    # Hardcoded URLs (2009/2010/2011)
    hardcoded_count = 0
    for y, urls in (HARDCODED_URLS or {}).items():
        for u in urls:
            name = _filename_from_url(u)
            mpart = re.search(r"-(\d{2})\.pdf$", name)
            part = mpart.group(1) if mpart else ""
            candidates.append({
                "YYYY": str(y),
                "MM": "",  # no aplica
                "ejemplar": "",  # no aplica
                "parte": part,
                "url": u,
                "hardcoded": "1",
            })
            hardcoded_count += 1

    # Deduplicar por URL
    seen: set[str] = set()
    unique_cands: list[dict] = []
    for c in candidates:
        if c["url"] in seen:
            continue
        seen.add(c["url"])
        unique_cands.append(c)

    print(f"  URLs candidatas únicas: {len(unique_cands)}")
    if hardcoded_count:
        print(f"  + hardcoded: {hardcoded_count}")

    # ── Paso 3: Descargar PDFs ──
    print("  [3/3] Descargando PDFs...")
    dl_rows: list[dict] = []

    for c in unique_cands:
        url = c["url"]
        year_folder = c["YYYY"]

        year_dir = pdf_raw_dir / year_folder
        year_dir.mkdir(parents=True, exist_ok=True)

        if c["hardcoded"] == "1":
            base_name = _filename_from_url(url)
            fname = f"QRO_RAW_{base_name}"
        else:
            YYYY, MM = c["YYYY"], c["MM"]
            ISSUE, PART = c["ejemplar"], c["parte"]
            fname = f"QRO_RAW_{YYYY}{MM}{ISSUE}-{PART}.pdf"

        dst = year_dir / fname

        if dst.exists() and dst.stat().st_size > 1000:
            dl_rows.append({**c, "status": "cache_hit", "file": str(dst.relative_to(pdf_raw_dir))})
            continue

        payload = _http_get(session, url)
        _sleep_polite()

        if not payload:
            dl_rows.append({**c, "status": "http_error", "file": ""})
            continue

        if _looks_like_pdf(payload):
            dst.write_bytes(payload)
            dl_rows.append({**c, "status": "ok", "file": str(dst.relative_to(pdf_raw_dir))})
            print(f"    [OK] {dst.relative_to(pdf_raw_dir)}")
        else:
            dl_rows.append({**c, "status": "not_pdf", "file": ""})

    # Guardar registry
    registry_csv = meta_dir / "raw_registry.csv"
    fieldnames_r = ["YYYY", "MM", "ejemplar", "parte", "url", "hardcoded", "status", "file"]
    with registry_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames_r)
        writer.writeheader()
        writer.writerows(dl_rows)

    ok_count = sum(1 for r in dl_rows if r["status"] in ("ok", "cache_hit"))
    print(f"  Descargados: {ok_count}/{len(dl_rows)} → {registry_csv}")
    return registry_csv