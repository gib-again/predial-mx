"""
Descarga de las Leyes de Hacienda municipales de BCS (Word digital, sin OCR).

Dos versiones por municipio:
  - actual:        Congreso del Estado (cbcs.gob.mx/LEYES-BCS/)
  - baseline_2009: Orden Juridico Nacional (ordenjuridico.gob.mx), consolidadas
                   a ~2008-2009 = baseline para el inicio del panel (2010).

Las URLs estan fijadas en data/{estado}/meta/fuentes_leyes_hacienda.csv (ya
curado durante la investigacion de fuentes). Esta descarga es idempotente.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

from src.estados.bajacaliforniasur import config
from src.estados.bajacaliforniasur.leyes import LEYES_DIR

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def _curl(url: str, out: Path) -> tuple[bool, int]:
    out.parent.mkdir(parents=True, exist_ok=True)
    res = subprocess.run(
        ["curl", "-s", "-L", "-k", "-A", UA, "--max-time", "90", url, "-o", str(out)],
        capture_output=True,
    )
    ok = res.returncode == 0 and out.exists() and out.stat().st_size > 2000
    return ok, (out.stat().st_size if out.exists() else 0)


def run_download(adapter, force: bool = False) -> Path:
    """Descarga las 10 Leyes de Hacienda (5 munis x 2 versiones) segun el
    manifiesto meta/fuentes_leyes_hacienda.csv. Devuelve la ruta del manifiesto.
    """
    if not shutil.which("curl"):
        raise RuntimeError("curl no esta en PATH (requerido para descargar de cbcs/ordenjuridico).")

    meta = Path("data") / config.ESTADO_SLUG / "meta" / "fuentes_leyes_hacienda.csv"
    if not meta.exists():
        raise FileNotFoundError(
            f"Falta el manifiesto de fuentes: {meta}. "
            "Debe contener columnas: slug, version, url, archivo."
        )

    print("=== Baja California Sur: descarga de Leyes de Hacienda ===")
    n_ok = n_skip = n_err = 0
    with meta.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            url = (row.get("url") or "").strip()
            rel = (row.get("archivo") or "").strip()
            if not url or not rel:
                continue
            out = Path("data") / config.ESTADO_SLUG / rel
            if out.exists() and out.stat().st_size > 2000 and not force:
                n_skip += 1
                continue
            ok, size = _curl(url, out)
            if ok:
                print(f"  descargado: {rel} ({size}B)")
                n_ok += 1
            else:
                print(f"  ERROR: {rel} <- {url}")
                n_err += 1

    print(f"\n  Leyes en {LEYES_DIR}: {n_ok} descargadas, {n_skip} ya existian, {n_err} errores")
    return meta
