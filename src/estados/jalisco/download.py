"""
Descarga de PDFs del Periódico Oficial de Jalisco.

Migrado de:
  - 30_jal_ingresos_make_index.py   → build_index (consulta API REST)
  - 31_dowload_pdf.py               → download_pdfs (descarga PDFs)

Jalisco es diferente a Coahuila: tiene una API REST pública con endpoints
por municipio_id que devuelven JSON con años disponibles y URLs de PDFs.
"""

import time
import csv
from pathlib import Path

import requests

from src.core.text_utils import slugify
from src.estados.jalisco.config import (
    API_BASE,
    API_INGRESOS,
    YEAR_MIN,
    YEAR_MAX,
    MIN_MPO_ID,
    MAX_MPO_ID,
    USER_AGENT,
)


def _get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    })
    return session


def fetch_ingresos_municipio(session: requests.Session, municipio_id: int):
    """
    Consulta la API para un municipio y devuelve (nombre, lista_de_registros).
    """
    params = {"municipio_id": municipio_id}
    resp = session.get(API_INGRESOS, params=params, timeout=30)
    try:
        resp.raise_for_status()
    except Exception:
        return f"municipio_{municipio_id}", []

    data = resp.json()
    if data.get("errors") is True:
        return f"municipio_{municipio_id}", []

    result = data.get("result", {})
    municipio = result.get("municipio", {}) or {}
    nombre_mun = municipio.get("nombre", f"municipio_{municipio_id}")

    years = result.get("years", []) or []
    rows = []
    for y in years:
        anio = y.get("year")
        publicado = y.get("publicado", False)
        doc_id = y.get("id")

        if not isinstance(anio, int) or not (YEAR_MIN <= anio <= YEAR_MAX):
            continue
        if not publicado or not doc_id:
            continue

        pdf_url = f"{API_BASE}/{doc_id}/pdf"
        rows.append({
            "id_mpo": municipio_id,
            "municipio": nombre_mun,
            "anio": anio,
            "doc_id": doc_id,
            "pdf_url": pdf_url,
        })

    return nombre_mun, rows


def build_index(meta_dir: Path) -> Path:
    """
    Consulta la API para todos los municipios (1-125) y genera un CSV índice.

    Returns:
        Path al CSV índice generado.
    """
    out_csv = meta_dir / "ingresos_index_api.csv"
    meta_dir.mkdir(parents=True, exist_ok=True)

    session = _get_session()
    registros = []

    for mid in range(MIN_MPO_ID, MAX_MPO_ID + 1):
        print(f"  Consultando municipio_id={mid} ...")
        try:
            nombre_mun, rows = fetch_ingresos_municipio(session, mid)
        except Exception as e:
            print(f"    ERROR: {e}")
            continue

        if rows:
            print(f"    {nombre_mun}: {len(rows)} años")
        registros.extend(rows)
        time.sleep(0.2)

    # Deduplicar y ordenar
    seen = set()
    unique = []
    for r in registros:
        key = (r["id_mpo"], r["anio"], r["doc_id"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    unique.sort(key=lambda r: (r["municipio"], r["anio"]))

    fieldnames = ["id_mpo", "municipio", "anio", "doc_id", "pdf_url"]
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unique)

    print(f"  Índice guardado en {out_csv} ({len(unique)} registros)")
    return out_csv


def download_pdfs(meta_dir: Path, pdf_raw_dir: Path) -> Path:
    """
    Descarga PDFs a partir del índice generado por build_index.

    Returns:
        Path al CSV log de descargas.
    """
    index_csv = meta_dir / "ingresos_index_api.csv"
    downloads_csv = meta_dir / "ingresos_downloads.csv"

    if not index_csv.exists():
        raise FileNotFoundError(f"No existe índice: {index_csv}. Ejecuta 'download' primero.")

    pdf_raw_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({
        "User-Agent": USER_AGENT,
        "Accept": "application/pdf, application/octet-stream, */*",
    })

    rows_status = []
    with index_csv.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        index_rows = list(reader)

    for row in index_rows:
        municipio = row["municipio"]
        anio = int(row["anio"])
        pdf_url = row["pdf_url"]
        doc_id = row["doc_id"]
        id_mpo = row["id_mpo"]

        m_slug = slugify(municipio)
        out_dir = pdf_raw_dir / str(anio)
        out_dir.mkdir(parents=True, exist_ok=True)

        filename = f"JAL_RAW_{anio}_{m_slug}.pdf"
        out_path = out_dir / filename

        status = "ok"
        if out_path.exists():
            status = "already_exists"
        else:
            print(f"  Descargando {municipio} {anio} ...")
            try:
                with session.get(pdf_url, timeout=120, stream=True) as resp:
                    resp.raise_for_status()
                    with open(out_path, "wb") as f:
                        for chunk in resp.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
            except Exception as e:
                status = f"error:{type(e).__name__}"
                print(f"    ERROR: {e}")

        rows_status.append({
            "id_mpo": id_mpo,
            "municipio": municipio,
            "anio": anio,
            "doc_id": doc_id,
            "pdf_url": pdf_url,
            "file_local": str(out_path),
            "status": status,
        })

        if status == "ok":
            time.sleep(0.3)

    fieldnames = ["id_mpo", "municipio", "anio", "doc_id", "pdf_url", "file_local", "status"]
    with downloads_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows_status)

    ok_count = sum(1 for r in rows_status if r["status"] in ("ok", "already_exists"))
    print(f"  Descargas: {ok_count}/{len(rows_status)} OK → {downloads_csv}")
    return downloads_csv


# ── Entry point ──

def run_download(adapter) -> Path:
    """Ejecuta build_index + download_pdfs."""
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir

    print("  [1/2] Construyendo índice desde API...")
    build_index(meta_dir)

    print("  [2/2] Descargando PDFs...")
    return download_pdfs(meta_dir, pdf_raw_dir)
