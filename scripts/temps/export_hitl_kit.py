"""Arma un "HITL Kit" autocontenido por estado para repartir a un asistente.

El kit es una carpeta que se sube a OneDrive (carpeta compartida por asistente).
Contiene SOLO los datos de ese estado + la rebanada de la cola + su archivo de
decisiones + un lanzador.  El asistente sincroniza, doble-click al lanzador,
revisa en su navegador; su archivo de decisiones se sincroniza de vuelta.

Uso:
    python -m scripts.temps.export_hitl_kit --estado coahuila
    python -m scripts.temps.export_hitl_kit --estado coahuila --pdfs link   # test rápido
    python -m scripts.temps.export_hitl_kit --estado coahuila --out "D:/ruta/HITL_COAHUILA"

Modos de PDF (--pdfs):
    copy  (default) — copia los PDFs al kit.  Úsalo para el handoff real (los
                      archivos quedan independientes en la carpeta de OneDrive).
    link            — hardlink a los PDFs del repo (instantáneo, 0 espacio extra).
                      Solo para probar el flujo localmente, NO para OneDrive.
    skip            — no incluye PDFs (prueba mínima del mecanismo).

La aplicación de decisiones (escribir a json_predial_hitl/) la haces TÚ con
``aplicar_decisiones_hitl`` tras recoger los archivos con ``import_hitl_decisiones``.
"""

from __future__ import annotations

import argparse
import csv
import os
import shutil
import sys
from pathlib import Path

from src.hitl.decisiones import DECISION_FIELDS

REPO = Path(__file__).resolve().parents[2]
COLA = REPO / "output" / "hitl" / "cola_unificada.csv"
CATALOG = REPO / "catalogs" / "municipios_inegi.csv"


def _say(msg: str) -> None:
    print(msg, flush=True)


def _slice_cola(estado: str, out_cola: Path) -> int:
    """Escribe solo las filas del estado a out_cola.  Devuelve cuántas filas."""
    if not COLA.exists():
        sys.exit(f"ERROR: no existe {COLA}.  Corre run_detectors primero.")
    with COLA.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        rows = [r for r in reader if (r.get("estado_slug") or "").strip() == estado]
    with out_cola.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    return len(rows)


def _copy_tree(src: Path, dst: Path) -> int:
    """Copia un árbol de archivos (json/csv).  Devuelve # archivos."""
    if not src.exists():
        return 0
    n = 0
    for f in src.rglob("*"):
        if f.is_file():
            rel = f.relative_to(src)
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, target)
            n += 1
    return n


def _place_pdfs(src: Path, dst: Path, mode: str) -> tuple[int, int]:
    """Coloca PDFs según el modo.  Devuelve (#archivos, bytes)."""
    if mode == "skip" or not src.exists():
        return 0, 0
    n = sz = 0
    for f in src.rglob("*.pdf"):
        if not f.is_file():
            continue
        rel = f.relative_to(src)
        target = dst / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if mode == "link":
                if target.exists():
                    target.unlink()
                os.link(f, target)        # hardlink (mismo volumen)
            else:
                shutil.copy2(f, target)
        except OSError:
            shutil.copy2(f, target)       # fallback a copia si el link falla
        n += 1
        try:
            sz += f.stat().st_size
        except OSError:
            pass
    return n, sz


_BAT = """@echo off
cd /d "%~dp0"
title HITL Revisor - {ESTADO_UP}
echo Iniciando el revisor de {ESTADO_UP}...
echo Se abrira tu navegador en unos segundos.  NO cierres esta ventana negra
echo mientras trabajas.  Para terminar, cierra esta ventana.
echo.
REVISAR.exe --csv cola_{estado}.csv --decisiones "decisiones\\hitl_decisiones_{estado}.csv" --revisor "%USERNAME%" --port {port}
pause
"""

_LEEME = """KIT DE REVISION HITL — {ESTADO_UP}
==================================================

Que es esto
-----------
Una herramienta para revisar los datos de impuesto predial de {ESTADO_UP}.
Todo lo que necesitas ya esta dentro de esta carpeta.

ANTES DE EMPEZAR (importante, una sola vez)
-------------------------------------------
1. En el Explorador de archivos, da click derecho sobre ESTA carpeta en OneDrive.
2. Elige "Conservar siempre en este dispositivo".
   (Esto descarga los PDF a tu computadora; si no, las vistas previas se cuelgan.)
   Espera a que termine de descargar antes de continuar.

COMO USARLO
-----------
1. Doble-click en  REVISAR_{ESTADO_UP}.bat
2. Se abre una ventana negra (dejala abierta) y luego tu navegador.
3. Revisa caso por caso.  Tus decisiones se guardan solas.
4. Para terminar: cierra la ventana negra.

Tu trabajo se guarda en  decisiones\\hitl_decisiones_{estado}.csv
OneDrive lo sincroniza de vuelta automaticamente.  No edites ese archivo a mano.

Si algo falla
-------------
- "Falta REVISAR.exe": avisa, el archivo del programa no llego completo.
- El navegador no abre: entra manualmente a  http://localhost:{port}
- Una vista previa de PDF no carga: revisa el paso "Conservar siempre en este
  dispositivo" de arriba.

Gracias!
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--estado", required=True, help="slug del estado, p.ej. coahuila")
    ap.add_argument("--out", default=None, help="carpeta destino del kit")
    ap.add_argument("--pdfs", choices=["copy", "link", "skip"], default="copy")
    ap.add_argument("--port", type=int, default=5500)
    args = ap.parse_args()

    estado = args.estado.strip().lower()
    src_data = REPO / "data" / estado
    if not src_data.exists():
        sys.exit(f"ERROR: no existe data/{estado}/.")

    out = Path(args.out) if args.out else (REPO / "dist_hitl" / f"HITL_{estado.upper()}")
    out.mkdir(parents=True, exist_ok=True)
    _say(f"Armando kit de {estado.upper()} en: {out}")

    # 1. Rebanada de la cola (solo este estado).
    n_cola = _slice_cola(estado, out / f"cola_{estado}.csv")
    _say(f"  cola_{estado}.csv: {n_cola} filas")

    # 2. Corpus v3 + overlay HITL + segment.csv.
    kit_data = out / "data" / estado
    n_json = _copy_tree(src_data / "json_predial", kit_data / "json_predial")
    n_hitl = _copy_tree(src_data / "json_predial_hitl", kit_data / "json_predial_hitl")
    seg = src_data / "meta" / "segment.csv"
    if seg.exists():
        (kit_data / "meta").mkdir(parents=True, exist_ok=True)
        shutil.copy2(seg, kit_data / "meta" / "segment.csv")
    _say(f"  json_predial: {n_json} archivos  (overlay HITL: {n_hitl})")

    # 3. PDFs fuente.
    n_raw, sz_raw = _place_pdfs(src_data / "pdf_raw", kit_data / "pdf_raw", args.pdfs)
    n_ocr, sz_ocr = _place_pdfs(src_data / "pdf_ocr", kit_data / "pdf_ocr", args.pdfs)
    _say(f"  PDFs ({args.pdfs}): pdf_raw={n_raw} pdf_ocr={n_ocr}  "
         f"({(sz_raw + sz_ocr) / 1e9:.2f} GB)")

    # 4. Catálogo INEGI (nombres canónicos).
    (out / "catalogs").mkdir(parents=True, exist_ok=True)
    shutil.copy2(CATALOG, out / "catalogs" / "municipios_inegi.csv")

    # 5. Archivo de decisiones del asistente (solo encabezado si no existe).
    dec_dir = out / "decisiones"
    dec_dir.mkdir(parents=True, exist_ok=True)
    dec_file = dec_dir / f"hitl_decisiones_{estado}.csv"
    if not dec_file.exists():
        with dec_file.open("w", encoding="utf-8", newline="") as f:
            csv.DictWriter(f, fieldnames=DECISION_FIELDS).writeheader()

    # 6. Lanzador + instrucciones.
    fmt = {"estado": estado, "ESTADO_UP": estado.upper(), "port": args.port}
    (out / f"REVISAR_{estado.upper()}.bat").write_text(_BAT.format(**fmt), encoding="utf-8")
    (out / "LEEME.txt").write_text(_LEEME.format(**fmt), encoding="utf-8")

    exe = out / "REVISAR.exe"
    _say("\nKit armado.")
    if not exe.exists():
        _say("  FALTA: copia REVISAR.exe a esta carpeta (build con PyInstaller).")
    _say(f"  Listo para subir a OneDrive: {out}")


if __name__ == "__main__":
    main()
