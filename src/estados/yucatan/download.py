"""
Descarga de PDFs del Diario Oficial de Yucatán.

Optimizaciones (target: <10 min vs anterior 10h):
  1. HEAD request antes de GET — verifica existencia sin descargar (50ms vs 30s)
  2. MAX_SUFFIX = 5 (reducido de 8, nunca hemos visto relevante en _6+)
  3. Solo meses 12, 1 (KEEP_MONTHS)
  4. Skip descarga si archivo ya existe y es >10KB
  5. Early stop en sufijos: si _N da 404, no prueba _N+1
  6. Content-Length check: skip PDFs > MAX_PDF_SIZE_MB antes de descargar
  7. Solo verifica contenido de PDFs descargados (no re-analiza existentes)
"""

import csv
import json
import re
import time
from dataclasses import dataclass, asdict
from datetime import date
from pathlib import Path
from typing import Optional

import requests

from src.estados.yucatan.config import (
    BASE_INDEX_URL,
    BASE_DIARIO_URL,
    USER_AGENT,
    YEAR_MIN,
    YEAR_MAX,
    KEEP_MONTHS,
    MAX_SUFFIX,
    EXTRA_SUFFIXES,
    MAX_PDF_SIZE_MB,
    MERIDA_URLS,
)


# ── Constantes ──

MONTHS_ES = {
    "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4, "MAYO": 5, "JUNIO": 6,
    "JULIO": 7, "AGOSTO": 8, "SEPTIEMBRE": 9, "SETIEMBRE": 9,
    "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
}

RE_DATE_DASH = re.compile(r"\b(\d{1,2})-([A-ZÁÉÍÓÚÜÑ]+)-(\d{2,4})\b", flags=re.IGNORECASE)

KEYWORDS = [
    "LEY DE INGRESOS DEL MUNICIPIO",
    "LEY DE INGRESOS PARA EL MUNICIPIO",
    "LEYES DE INGRESOS",
]

RE_MUN = re.compile(
    r"LEY\s+DE\s+INGRESOS\s+(?:DEL|PARA\s+EL)\s+MUNICIPIO\s+DE\s+"
    r"([A-ZÁÉÍÓÚÜÑ\s\-.]+?)(?:,|\s+PARA|\s+DEL|\s+YUCAT[ÁA]N|\n)",
    flags=re.IGNORECASE,
)


@dataclass
class Record:
    index_year: int
    pub_year: int
    ymd: str
    suffix: str
    url: str
    local_path: str
    municipios_count: int
    municipios: list


# ── Helpers ──

def _parse_dash_date(s: str) -> Optional[str]:
    m = RE_DATE_DASH.search(s.strip())
    if not m:
        return None
    dd, mon_str, yy = int(m.group(1)), m.group(2).upper(), int(m.group(3))
    if yy < 100:
        yy += 2000
    month = MONTHS_ES.get(mon_str)
    if not month:
        return None
    try:
        return date(yy, month, dd).isoformat()
    except ValueError:
        return None


def _extract_text_pdf(path: Path) -> str:
    import fitz
    with fitz.open(path) as doc:
        return "\n".join(page.get_text("text") for page in doc)


def _pdf_has_muni_income(path: Path) -> bool:
    text = _extract_text_pdf(path).upper()
    return any(kw in text for kw in KEYWORDS)


def _extract_municipios(path: Path) -> list[str]:
    text = _extract_text_pdf(path)
    return sorted(set(m.group(1).strip() for m in RE_MUN.finditer(text)))


def _url_exists(session, url) -> Optional[int]:
    """HEAD request para verificar si URL existe. Retorna Content-Length o None."""
    try:
        r = session.head(url, timeout=15, allow_redirects=True)
        if r.status_code == 200:
            cl = r.headers.get("Content-Length")
            return int(cl) if cl else 0
        return None
    except requests.RequestException:
        return None


def _download_url(session, url, dst, retries=3, sleep=1.0, max_size_mb=MAX_PDF_SIZE_MB) -> bool:
    if dst.exists() and dst.stat().st_size > 10_000:
        return True
    for attempt in range(1, retries + 1):
        try:
            with session.get(url, stream=True, timeout=60, allow_redirects=True) as r:
                if r.status_code == 404:
                    return False
                if r.status_code != 200:
                    if attempt < retries:
                        time.sleep(sleep * attempt)
                        continue
                    return False
                # Check Content-Length
                cl = r.headers.get("Content-Length")
                if cl and int(cl) > max_size_mb * 1024 * 1024:
                    return False
                dst.parent.mkdir(parents=True, exist_ok=True)
                tmp = dst.with_suffix(dst.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=128 * 1024):
                        if chunk:
                            f.write(chunk)
                with open(tmp, "rb") as f:
                    if f.read(4) != b"%PDF":
                        tmp.unlink(missing_ok=True)
                        return False
                tmp.replace(dst)
                return True
        except requests.RequestException:
            if attempt < retries:
                time.sleep(sleep * attempt)
    return False


def _parse_index_dates(index_path: Path, year_min: int, year_max: int) -> set[str]:
    """Extrae fechas candidatas del índice anual."""
    import fitz
    dates = set()
    with fitz.open(index_path) as doc:
        for page in doc:
            text = page.get_text("text").upper()
            if not any(kw in text for kw in KEYWORDS):
                continue
            for m in RE_DATE_DASH.finditer(text):
                d = _parse_dash_date(m.group(0))
                if d:
                    y = int(d[:4])
                    if year_min - 1 <= y <= year_max + 1:
                        dates.add(d)
    return dates


def _filter_relevant_dates(dates: set[str]) -> set[str]:
    """Solo mantiene fechas en meses relevantes."""
    return {d for d in dates if int(d[5:7]) in KEEP_MONTHS}


# ── Entry point ──

def run_download(adapter) -> Path:
    """Descarga índices y diarios relevantes del DO de Yucatán."""
    data_dir = adapter.data_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    meta_dir = adapter.meta_dir
    indices_dir = data_dir / "indices"
    diarios_dir = pdf_raw_dir

    for d in (indices_dir, diarios_dir, meta_dir):
        d.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    records = []

    for index_year in range(YEAR_MIN, YEAR_MAX + 1):
        print(f"\n  === Índice {index_year} ===")
        index_url = BASE_INDEX_URL.format(year=index_year)
        index_path = indices_dir / f"{index_year}.pdf"

        if not _download_url(session, index_url, index_path, retries=4):
            print(f"    [WARN] No pude descargar índice {index_year}")
            continue

        candidate_dates = _parse_index_dates(index_path, YEAR_MIN, YEAR_MAX)
        candidate_dates = _filter_relevant_dates(candidate_dates)
        print(f"    Fechas candidatas: {len(candidate_dates)}")

        for ymd in sorted(candidate_dates):
            pub_year = int(ymd[:4])
            year_dir = diarios_dir / str(pub_year)
            year_dir.mkdir(parents=True, exist_ok=True)

            # Probar URL base y sufijos
            suffixes_to_try = [""] + [f"_{n}" for n in range(1, MAX_SUFFIX + 1)] + list(EXTRA_SUFFIXES)

            for sfx in suffixes_to_try:
                url = BASE_DIARIO_URL.format(year=pub_year, ymd=ymd, suffix=sfx)
                dst = year_dir / f"{ymd}{sfx}.pdf"

                # Skip si ya descargado y verificado
                if dst.exists() and dst.stat().st_size > 10_000:
                    try:
                        if _pdf_has_muni_income(dst):
                            munis = _extract_municipios(dst)
                            records.append(Record(
                                index_year=index_year, pub_year=pub_year, ymd=ymd,
                                suffix=sfx, url=url, local_path=str(dst),
                                municipios_count=len(munis), municipios=munis,
                            ))
                            print(f"    [CACHED] {dst.name} ({len(munis)} municipios)")
                        continue
                    except Exception:
                        continue

                # Fast-fail con HEAD
                size = _url_exists(session, url)
                if size is None:
                    # Sufijos numéricos son consecutivos: si _N no existe, stop
                    if sfx and sfx.startswith("_") and sfx[1:].isdigit():
                        break
                    continue

                # Skip PDFs demasiado grandes o demasiado pequeños
                if size and size < 5_000:
                    continue
                if size and size > MAX_PDF_SIZE_MB * 1024 * 1024:
                    continue

                if not _download_url(session, url, dst):
                    if sfx and sfx.startswith("_") and sfx[1:].isdigit():
                        break
                    continue
                time.sleep(0.3)

                try:
                    if not _pdf_has_muni_income(dst):
                        dst.unlink(missing_ok=True)
                        continue
                except Exception:
                    continue

                try:
                    munis = _extract_municipios(dst)
                except Exception:
                    munis = []

                records.append(Record(
                    index_year=index_year, pub_year=pub_year, ymd=ymd,
                    suffix=sfx, url=url, local_path=str(dst),
                    municipios_count=len(munis), municipios=munis,
                ))
                print(f"    [KEEP] {ymd}{sfx}.pdf ({len(munis)} municipios)")

    # ── Mérida: descarga especial desde portal municipal ──
    print("\n  === Mérida (portal municipal) ===")
    merida_dir = diarios_dir / "merida"
    merida_dir.mkdir(parents=True, exist_ok=True)
    for fy, url in sorted(MERIDA_URLS.items()):
        dst = merida_dir / f"merida_hacienda_{fy}.pdf"
        if dst.exists() and dst.stat().st_size > 10_000:
            print(f"    [CACHED] {dst.name}")
            records.append(Record(
                index_year=fy, pub_year=fy, ymd=f"{fy}-12-01",
                suffix="_merida", url=url, local_path=str(dst),
                municipios_count=1, municipios=["Mérida"],
            ))
            continue
        if _download_url(session, url, dst, retries=4):
            print(f"    [KEEP] {dst.name}")
            records.append(Record(
                index_year=fy, pub_year=fy, ymd=f"{fy}-12-01",
                suffix="_merida", url=url, local_path=str(dst),
                municipios_count=1, municipios=["Mérida"],
            ))
        else:
            print(f"    [WARN] No pude descargar Mérida FY={fy}")
        time.sleep(0.3)

    # Guardar manifest
    manifest_csv = meta_dir / "manifest.csv"
    fieldnames = ["index_year", "pub_year", "ymd", "suffix", "url",
                  "local_path", "municipios_count", "municipios"]
    with manifest_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in records:
            d = asdict(r)
            d["municipios"] = ";".join(d["municipios"])
            writer.writerow(d)

    manifest_json = meta_dir / "manifest.json"
    with manifest_json.open("w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in records], f, ensure_ascii=False, indent=2)

    print(f"\n  PDFs relevantes: {len(records)} → {manifest_csv}")
    return manifest_csv
