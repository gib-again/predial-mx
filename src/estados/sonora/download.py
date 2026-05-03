"""
Descarga incremental de PDFs del Boletín Oficial de Sonora.

Modelo v3 (post-discoverer):
  1. `discover_leyes()` (en discoverer.py) parsea el HTML estructurado del
     índice Joomla y produce `meta/source_documents.csv` con todos los PDFs
     que mencionan leyes municipales.
  2. `descargar_documentos_faltantes()` (este módulo) lee ese CSV y descarga
     únicamente los PDFs faltantes en `pdf_raw/`, actualizando sha256 y
     path_local en source_documents.csv.

Resiliencia:
  - User-Agent realista (el sitio bloquea 403 sin él).
  - Retries con backoff exponencial.
  - Verificación de Content-Type=application/pdf antes de escribir.
  - Hash SHA-256 para deduplicación y detección de re-descargas.
"""

from __future__ import annotations

import csv
import hashlib
import time
from pathlib import Path

import requests

from src.estados.sonora import config


# ═══════════════════════════════════════════════════
# Sesión HTTP
# ═══════════════════════════════════════════════════

def _make_session() -> requests.Session:
    """Sesión con User-Agent de navegador realista (el sitio bloquea 403 sin él)."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    return session


# ═══════════════════════════════════════════════════
# Descarga de PDFs
# ═══════════════════════════════════════════════════

def _download_pdf(
    session: requests.Session,
    url: str,
    dest_path: Path,
    *,
    max_retries: int = 3,
) -> tuple[str, str]:
    """Descarga un PDF a `dest_path`. Retorna (status, sha256_hex)."""
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return "already_exists", _sha256_file(dest_path)

    dest_path.parent.mkdir(parents=True, exist_ok=True)

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, timeout=120, stream=True)
            resp.raise_for_status()
            ctype = (resp.headers.get("Content-Type") or "").lower()
            if "pdf" not in ctype and "octet-stream" not in ctype:
                return f"error:bad_content_type:{ctype[:60]}", ""
            sha = hashlib.sha256()
            with dest_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        sha.update(chunk)
            time.sleep(config.THROTTLE_SECONDS)
            return "ok", sha.hexdigest()
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
                continue
            return f"error:{type(e).__name__}", ""

    return "error:max_retries", ""


def _sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            sha.update(chunk)
    return sha.hexdigest()


# ═══════════════════════════════════════════════════
# Pipeline principal: descarga incremental
# ═══════════════════════════════════════════════════

def descargar_documentos_faltantes(adapter) -> Path:
    """
    Descarga solo los PDFs listados en source_documents.csv que aún NO
    están en pdf_raw/. Actualiza source_documents.csv con sha256 + path_local.

    Filtro implícito: solo descarga documentos que tengan al menos una ley
    municipal asociada en discovered_laws.csv (ahorra descargar avisos).
    """
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    docs_csv = meta_dir / "source_documents.csv"
    laws_csv = meta_dir / "discovered_laws.csv"

    if not docs_csv.exists() or not laws_csv.exists():
        raise FileNotFoundError(
            f"Faltan {docs_csv} o {laws_csv}. Corre 'discover' primero."
        )

    print("═══ Sonora: Descarga incremental ═══")

    with docs_csv.open(encoding="utf-8") as f:
        docs = list(csv.DictReader(f))
    with laws_csv.open(encoding="utf-8") as f:
        urls_con_leyes = set(r["documento_url"] for r in csv.DictReader(f))
    docs_con_leyes = [d for d in docs if d["url_pdf"] in urls_con_leyes]
    print(f"    Documentos con leyes municipales: {len(docs_con_leyes)}")

    # Identificar faltantes (no en pdf_raw/)
    pdfs_existentes = set()
    for yd in pdf_raw_dir.iterdir():
        if yd.is_dir():
            for p in yd.glob("*.pdf"):
                pdfs_existentes.add(p.name)

    faltantes = []
    for d in docs_con_leyes:
        fname = d["url_pdf"].rsplit("/", 1)[-1]
        if fname not in pdfs_existentes:
            faltantes.append(d)

    print(f"    Faltantes a descargar: {len(faltantes)}")

    if not faltantes:
        print("    Nada que descargar.")
        return docs_csv

    session = _make_session()
    n_ok = 0
    n_err = 0
    sha_map: dict[str, str] = {}
    path_map: dict[str, str] = {}

    for i, d in enumerate(faltantes, 1):
        url = d["url_pdf"]
        anio_pub = d.get("anio_pub", "")
        fname = url.rsplit("/", 1)[-1]
        dest = pdf_raw_dir / str(anio_pub) / fname
        status, sha = _download_pdf(session, url, dest)
        if status in ("ok", "already_exists"):
            n_ok += 1
            sha_map[url] = sha
            path_map[url] = str(dest)
            print(f"    [{i}/{len(faltantes)}] {fname}: {status}")
        else:
            n_err += 1
            print(f"    [{i}/{len(faltantes)}] {fname}: {status}")

    # Actualizar source_documents.csv con sha256 + path_local
    for d in docs:
        url = d["url_pdf"]
        if url in sha_map:
            d["sha256"] = sha_map[url]
        if url in path_map:
            d["path_local"] = path_map[url]
        elif (pdf_raw_dir / d.get("anio_pub", "") / url.rsplit("/", 1)[-1]).exists():
            d["path_local"] = str(pdf_raw_dir / d.get("anio_pub", "") / url.rsplit("/", 1)[-1])

    fieldnames = list(docs[0].keys()) if docs else [
        "url_pdf", "anio_pub", "fecha_publicacion", "tomo", "numero_boletin",
        "seccion", "era", "sha256", "path_local",
    ]
    with docs_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(docs)

    print(f"\n  Resumen: {n_ok} descargados/cached, {n_err} errores")
    print(f"  source_documents.csv actualizado: {docs_csv}")
    return docs_csv
