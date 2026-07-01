"""
Descarga de la Ley de Hacienda de los Municipios del Estado de Campeche (PDF
digital, sin OCR). Tres versiones segun el manifiesto
meta/fuentes_leyes_hacienda.csv (curado en la investigacion de fuentes).
Idempotente.
"""

from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

from src.estados.campeche import config

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"


def run_download(adapter, force: bool = False) -> Path:
    if not shutil.which("curl"):
        raise RuntimeError("curl no esta en PATH (requerido para descargar la ley).")

    base = Path("data") / config.ESTADO_SLUG
    meta = base / "meta" / "fuentes_leyes_hacienda.csv"
    if not meta.exists():
        raise FileNotFoundError(f"Falta el manifiesto: {meta}")

    print("=== Campeche: descarga de la Ley de Hacienda de los Municipios ===")
    n_ok = n_skip = n_err = 0
    with meta.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            url = (row.get("url") or "").strip()
            rel = (row.get("archivo") or "").strip()
            if not url or not rel:
                continue
            out = base / rel
            if out.exists() and out.stat().st_size > 5000 and not force:
                n_skip += 1
                continue
            out.parent.mkdir(parents=True, exist_ok=True)
            res = subprocess.run(
                ["curl", "-s", "-L", "-k", "-A", UA, "--max-time", "120", url, "-o", str(out)],
                capture_output=True,
            )
            if res.returncode == 0 and out.exists() and out.stat().st_size > 5000:
                print(f"  descargado: {rel}")
                n_ok += 1
            else:
                print(f"  ERROR: {rel} <- {url}")
                n_err += 1

    print(f"\n  {n_ok} descargadas, {n_skip} ya existian, {n_err} errores")
    return meta
