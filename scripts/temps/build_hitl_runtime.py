"""Arma el runtime portable para los HITL Kits (SAC-safe, sin instalar nada).

Por qué: las máquinas institucionales con *Smart App Control* (Windows 11)
bloquean ejecutables sin firma — un .exe de PyInstaller no corre.  En cambio, el
``python.exe`` oficial de python.org SÍ está firmado y SAC lo permite.  Este
script arma una carpeta portable con ese Python firmado + Flask + nuestro código,
que el lanzador .bat del kit usa para correr el revisor.

Produce ``dist_hitl/_runtime/`` con:
    runtime/   Python embebido oficial (python.exe firmado por PSF)
    lib/       dependencias (flask, unidecode, ...) instaladas con pip --target
    code/      src/ + scripts/temps/hitl_revisor_server.py

``export_hitl_kit.py`` copia estas tres carpetas dentro de cada kit.

Uso:
    python -m scripts.temps.build_hitl_runtime
    python -m scripts.temps.build_hitl_runtime --python 3.12.10
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "dist_hitl" / "_runtime"

# Dependencias de terceros que necesita el server (cierre de imports).
# Todas son Python puro → portables sin compilar.
DEPS = ["flask", "unidecode"]


def _say(m: str) -> None:
    print(m, flush=True)


def _download_embed(version: str, dest_zip: Path) -> None:
    url = (f"https://www.python.org/ftp/python/{version}/"
           f"python-{version}-embed-amd64.zip")
    _say(f"  descargando Python embebido {version}...")
    urllib.request.urlretrieve(url, dest_zip)


def _configure_pth(runtime_dir: Path) -> None:
    """Habilita las rutas a ../lib y ../code en el ._pth del embebido."""
    pth = next(runtime_dir.glob("python*._pth"), None)
    if pth is None:
        sys.exit("ERROR: no encontré el archivo ._pth del Python embebido.")
    base = pth.read_text(encoding="utf-8").splitlines()
    zipline = next((ln for ln in base if ln.strip().endswith(".zip")), "python312.zip")
    pth.write_text("\n".join([zipline, ".", r"..\lib", r"..\code", "import site"]) + "\n",
                   encoding="utf-8")


def _copy_code(code_dir: Path) -> None:
    if code_dir.exists():
        shutil.rmtree(code_dir)
    (code_dir / "scripts" / "temps").mkdir(parents=True)
    shutil.copytree(REPO / "src", code_dir / "src",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    for f in ["scripts/__init__.py", "scripts/temps/__init__.py"]:
        src = REPO / f
        (code_dir / f).write_text(
            src.read_text(encoding="utf-8") if src.exists() else "", encoding="utf-8")
    shutil.copy2(REPO / "scripts/temps/hitl_revisor_server.py",
                 code_dir / "scripts/temps/hitl_revisor_server.py")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--python", default="3.12.10", help="versión de Python embebido")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    runtime_dir = OUT / "runtime"
    lib_dir = OUT / "lib"
    code_dir = OUT / "code"

    # 1. Python embebido firmado.
    zip_path = OUT / "py-embed.zip"
    _download_embed(args.python, zip_path)
    if runtime_dir.exists():
        shutil.rmtree(runtime_dir)
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(runtime_dir)
    zip_path.unlink()
    _configure_pth(runtime_dir)
    _say("  runtime/ listo (python.exe firmado por PSF)")

    # 2. Dependencias (Python puro) a lib/.
    if lib_dir.exists():
        shutil.rmtree(lib_dir)
    _say(f"  instalando dependencias en lib/: {', '.join(DEPS)}")
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "--quiet", "--target", str(lib_dir), *DEPS])

    # 3. Nuestro código a code/.
    _copy_code(code_dir)
    _say("  code/ listo (src + server)")

    # 4. Verificación de imports con el Python embebido.
    py = runtime_dir / "python.exe"
    check = ("import flask, src.core.catalog, src.core.corpus, "
             "src.core.segment_schema, src.hitl.decisiones, "
             "scripts.temps.hitl_revisor_server; print('IMPORTS OK')")
    try:
        subprocess.check_call([str(py), "-X", "utf8", "-c", check])
    except subprocess.CalledProcessError:
        sys.exit("ERROR: el runtime no pudo importar el código.  Revisa DEPS.")

    _say(f"\nRuntime portable listo en: {OUT}")
    _say("  Ya puedes armar kits: python -m scripts.temps.export_hitl_kit --estado <slug>")


if __name__ == "__main__":
    main()
