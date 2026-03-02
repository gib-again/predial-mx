"""
Descarga de PDFs del Periódico Oficial de Oaxaca.

Dos fases:
  1. Búsqueda HTML: POST a busqueda.php con payload por año.
     Parsea la tabla de resultados (tblNueva) y extrae metadata + hrefs.
  2. Descarga de PDFs: Para cada href único, descarga el PDF.

Los PDFs de Oaxaca tienen estructura:
  files/{YYYY}/{MM}/{nombre}.pdf

Convención de salida:
  data/oaxaca/pdf_raw/{año}/{mes}/{filename_original}.pdf
  data/oaxaca/meta/oaxaca_index.csv

Los PDFs del PO contienen múltiples leyes de ingresos (3-7 por "Sección").
La segmentación posterior se encarga de extraer cada municipio.

Nota: El PO de Oaxaca publica leyes durante TODO el año (no solo enero/febrero),
por lo que hay PDFs en muchos meses distintos. Esto es normal.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
import time
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.estados.oaxaca import config


# ═══════════════════════════════════════════════════
# Utilidades
# ═══════════════════════════════════════════════════

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _looks_like_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(4) == b"%PDF"
    except Exception:
        return False


def _safe_text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


# ═══════════════════════════════════════════════════
# Fase 1: Búsqueda HTML
# ═══════════════════════════════════════════════════

def _parse_search_results(html_bytes: bytes) -> list[dict]:
    """
    Parsea la tabla tblNueva del resultado de búsqueda.
    Retorna lista de dicts con metadata de cada hit.
    """
    soup = BeautifulSoup(html_bytes, "html.parser")
    table = soup.find("table", {"id": "tblNueva"})
    if not table:
        return []

    rows = table.find_all("tr")
    if len(rows) <= 1:
        return []

    out = []
    for tr in rows[1:]:
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue

        a = tds[0].find("a", href=True)
        href = a["href"].strip() if a else ""
        href = href.replace("\\", "/")

        out.append({
            "href_pdf": href,
            "tipo_publicacion": _safe_text(tds[0]),
            "fecha_publicacion": _safe_text(tds[1]),
            "sumario": _safe_text(tds[2]),
            "tipo_documento": _safe_text(tds[3]),
            "sujeto_publica": _safe_text(tds[4]),
            "clasificacion_sujeto": _safe_text(tds[5]),
        })

    return out


def _search_year(session: requests.Session, year: int) -> list[dict]:
    """Busca leyes de ingresos para un año específico."""
    payload = dict(config.SEARCH_PAYLOAD_BASE)
    payload["c8"] = str(year)

    r = session.post(
        config.SEARCH_URL,
        data=payload,
        timeout=240,
        headers={"User-Agent": config.USER_AGENT},
    )
    r.raise_for_status()
    return _parse_search_results(r.content)


def _extract_municipio_ejercicio(sumario: str) -> tuple[str, str, int | None]:
    """
    Extrae municipio, distrito y ejercicio fiscal del campo sumario.
    Ejemplo: "LEY DE INGRESOS DEL MUNICIPIO DE X, DISTRITO, OAXACA,
             PARA EL EJERCICIO FISCAL 2022"
    """
    s = re.sub(r"\s+", " ", sumario or "").strip().rstrip(".")

    municipio = distrito = ""
    fy = None

    # Regex principal
    m = re.search(
        r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+"
        r"(?P<rest>.+?)\s*,\s*PARA\s+EL\s+EJERCICIO\s+FISCAL\s+(?P<fy>\d{4})",
        s, flags=re.IGNORECASE,
    )
    if m:
        fy = int(m.group("fy"))
        rest = m.group("rest").strip()
        parts = [p.strip(" ,.") for p in rest.split(",") if p.strip(" ,.")]
        if parts and parts[-1].upper() == "OAXACA":
            parts = parts[:-1]
        municipio = parts[0] if parts else ""
        distrito = parts[1] if len(parts) >= 2 else ""
        return municipio, distrito, fy

    # Fallback: extraer ejercicio
    mfy = re.search(r"EJERCICIO\s+FISCAL\s+(\d{4})", s, flags=re.IGNORECASE)
    if mfy:
        fy = int(mfy.group(1))

    # Fallback: extraer municipio
    m2 = re.search(
        r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+(.+?)(?:,|\.|\s+PARA)",
        s, flags=re.IGNORECASE,
    )
    if m2:
        municipio = re.sub(r"\s+", " ", m2.group(1)).strip()

    return municipio, distrito, fy


# ═══════════════════════════════════════════════════
# Fase 2: Descarga de PDFs
# ═══════════════════════════════════════════════════

def _parse_year_month_from_href(href: str) -> tuple[str, str]:
    """
    href típico: files/2024/04/SEC16-13RA-2024-04-20.pdf
    """
    parts = href.strip("/").split("/")
    if (
        len(parts) >= 4
        and parts[0] == "files"
        and parts[1].isdigit()
        and parts[2].isdigit()
    ):
        return parts[1], parts[2]
    return "unknown", "unknown"


def _download_one(session: requests.Session, href: str, out_path: Path):
    """Descarga un PDF individual."""
    url = urljoin(config.BASE_URL, href)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with session.get(
        url,
        stream=True,
        timeout=config.REQUESTS_KWARGS["timeout"],
        headers={"User-Agent": config.USER_AGENT},
    ) as r:
        r.raise_for_status()
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=128 * 1024):
                if chunk:
                    f.write(chunk)


# ═══════════════════════════════════════════════════
# Pipeline principal
# ═══════════════════════════════════════════════════

def run_download(adapter) -> Path:
    """
    Ejecuta búsqueda + descarga para todos los años configurados.

    Returns:
        Path al CSV índice de PDFs descargados.
    """
    pdf_raw_dir = adapter.pdf_raw_dir
    meta_dir = adapter.meta_dir
    meta_dir.mkdir(parents=True, exist_ok=True)

    index_csv = meta_dir / "oaxaca_index.csv"
    search_dir = meta_dir / "busqueda_raw"
    search_dir.mkdir(parents=True, exist_ok=True)

    print(f"═══ Oaxaca: Descarga ═══")

    # ── Fase 1: Búsqueda por año ──
    all_hits: list[dict] = []
    unique_hrefs: set[str] = set()

    with requests.Session() as session:
        # Inicializar sesión (PHPSESSID)
        session.get(config.SEARCH_URL, timeout=60,
                    headers={"User-Agent": config.USER_AGENT})

        for year in range(config.YEAR_MIN, config.YEAR_MAX + 1):
            print(f"  [{year}] Buscando leyes de ingresos...")
            try:
                hits = _search_year(session, year)
                for h in hits:
                    h["year_query"] = year
                    mun, dist, fy = _extract_municipio_ejercicio(h.get("sumario", ""))
                    h["municipio"] = mun
                    h["distrito"] = dist
                    h["ejercicio_fiscal"] = fy if fy else ""
                    if h["href_pdf"] and h["href_pdf"].lower().endswith(".pdf"):
                        unique_hrefs.add(h["href_pdf"])
                all_hits.extend(hits)
                print(f"    → {len(hits)} resultados")
            except Exception as e:
                print(f"    ERROR: {e}")

            time.sleep(config.SLEEP_BETWEEN_REQUESTS)

        # ── Fase 2: Descarga ──
        print(f"\n  {len(unique_hrefs)} PDFs únicos para descargar")

        download_log: list[dict] = []
        for href in sorted(unique_hrefs):
            year_str, month_str = _parse_year_month_from_href(href)
            filename = href.strip("/").split("/")[-1]
            out_path = pdf_raw_dir / year_str / month_str / filename

            if out_path.exists() and out_path.stat().st_size > 0 and _looks_like_pdf(out_path):
                download_log.append({
                    "href": href, "status": "skip_ok",
                    "filename": filename, "year": year_str,
                })
                continue

            ok = False
            for attempt in range(1, config.MAX_RETRIES + 1):
                try:
                    if out_path.exists():
                        out_path.unlink(missing_ok=True)
                    _download_one(session, href, out_path)
                    if _looks_like_pdf(out_path):
                        ok = True
                        break
                    else:
                        raise RuntimeError("Downloaded file is not a valid PDF")
                except Exception as e:
                    if attempt < config.MAX_RETRIES:
                        time.sleep(1.5 * attempt)
                    else:
                        print(f"    ERROR descargando {filename}: {e}")
                        download_log.append({
                            "href": href, "status": f"error:{e}",
                            "filename": filename, "year": year_str,
                        })

            if ok:
                download_log.append({
                    "href": href, "status": "ok",
                    "filename": filename, "year": year_str,
                })

            time.sleep(config.SLEEP_BETWEEN_REQUESTS)

    # ── Guardar índice ──
    index_fields = [
        "year_query", "ejercicio_fiscal", "municipio", "distrito",
        "fecha_publicacion", "href_pdf", "sumario",
        "tipo_publicacion", "tipo_documento",
    ]
    with index_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=index_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_hits)

    print(f"\n  Índice: {index_csv} ({len(all_hits)} filas)")
    print(f"  PDFs descargados: {sum(1 for d in download_log if d['status'] in ('ok', 'skip_ok'))}")

    return index_csv
