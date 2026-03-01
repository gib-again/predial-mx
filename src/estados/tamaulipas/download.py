"""
Descarga de PDFs del PO de Tamaulipas.

Esquema simple: un PDF consolidado por año fiscal, URLs hardcodeadas en config.py.
Cada PDF contiene las 43 leyes de ingresos municipales.

Archivos generados:
  data/tamaulipas/pdf_raw/{ejercicio}/TAMPS_RAW_{ejercicio}_consolidado.pdf
"""

from __future__ import annotations

import time
from pathlib import Path

import requests

from src.estados.tamaulipas import config

import certifi

session = requests.Session()
session.headers.update({"User-Agent": config.USER_AGENT})
session.verify = certifi.where()


def download_all(
    data_dir: Path = Path("data/tamaulipas"),
    year_min: int = config.YEAR_MIN,
    year_max: int = config.YEAR_MAX,
    force: bool = False,
):
    """
    Descarga los PDFs consolidados del PO para cada ejercicio fiscal.
    """
    raw_dir = data_dir / "pdf_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT})

    seen_urls: set[str] = set()
    downloaded = 0
    skipped = 0
    errors = 0

    print(f"═══ Tamaulipas: Descarga de PDFs del PO ═══")
    print(f"    Rango: {year_min}-{year_max}")

    for ejercicio in range(year_min, year_max + 1):
        url = config.URLS_PO.get(ejercicio)
        if not url:
            print(f"  [{ejercicio}] Sin URL configurada — SKIP")
            continue

        # Detectar URLs duplicadas (ej: 2017/2018 misma URL)
        url_normalized = url.replace("http://", "https://")
        if url_normalized in seen_urls:
            print(f"  [{ejercicio}] URL duplicada (ya descargada) — SKIP")
            skipped += 1
            continue
        seen_urls.add(url_normalized)

        year_dir = raw_dir / str(ejercicio)
        year_dir.mkdir(exist_ok=True)
        dest = year_dir / f"{config.PREFIJO}_RAW_{ejercicio}_consolidado.pdf"

        if dest.exists() and not force:
            size_mb = dest.stat().st_size / 1024 / 1024
            print(f"  [{ejercicio}] Ya existe ({size_mb:.1f} MB) — SKIP")
            skipped += 1
            continue

        print(f"  [{ejercicio}] Descargando...", end=" ", flush=True)
        try:
            resp = session.get(url, timeout=120, stream=True, verify=False)
            resp.raise_for_status()

            # Verificar que sea PDF
            ct = resp.headers.get("Content-Type", "")
            if "pdf" not in ct.lower() and not url.endswith(".pdf"):
                print(f"WARN: Content-Type={ct}")

            with dest.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)

            size_mb = dest.stat().st_size / 1024 / 1024
            print(f"OK ({size_mb:.1f} MB)")
            downloaded += 1

        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1
            if dest.exists():
                dest.unlink()

        time.sleep(1)  # cortesía

    print(f"\n  Descargados: {downloaded}  |  Ya existían: {skipped}  |  Errores: {errors}")
    return downloaded
