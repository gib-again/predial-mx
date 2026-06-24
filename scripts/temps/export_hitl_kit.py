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
# Runtime portable (Python firmado + Flask + código).  Lo arma build_hitl_runtime.py.
RUNTIME_SRC = REPO / "dist_hitl" / "_runtime"


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
        # Borra el destino primero: si era un hardlink (kit previo en modo link),
        # copiar encima escribiría sobre el archivo ORIGINAL del repo (corrupción).
        if target.exists() or target.is_symlink():
            target.unlink()
        try:
            if mode == "link":
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
runtime\\python.exe -X utf8 -m scripts.temps.hitl_revisor_server --revisor "%USERNAME%" --port {port}
echo.
echo El revisor se cerro.  Puedes cerrar esta ventana.
pause
"""

_LEEME = """KIT DE REVISION HITL — {ESTADO_UP}
==================================================

Que es esto
-----------
Herramienta para revisar los datos de impuesto predial de {ESTADO_UP}.
Todo lo necesario ya viene en esta carpeta. No instalas nada.

PASO 0 — Al descargar (una sola vez)
------------------------------------
1. Si te llego como archivo .zip: ANTES de extraerlo, click derecho en el .zip
   > Propiedades > si aparece "Desbloquear" (Unblock), marcalo y Aceptar.
2. Extrae la carpeta COMPLETA a tu disco (Escritorio o Documentos).
   No la uses desde dentro del .zip ni desde el navegador.
{seccion_pdf}
COMO USARLO
-----------
1. Doble-click en  REVISAR_{ESTADO_UP}.bat
   Si Windows muestra un aviso azul "Windows protegio tu PC":
   clic en "Mas informacion" > "Ejecutar de todas formas".
2. Se abre una ventana negra (dejala abierta) y luego tu navegador.
3. Revisa caso por caso. Tus decisiones se guardan solas.
4. Para terminar: cierra la ventana negra.

COMO ENTREGAR TU TRABAJO (importante)
-------------------------------------
Al terminar (o al final de cada dia) enviame SOLO este archivo:
    decisiones\\hitl_decisiones_{estado}.csv
por el medio que acordamos (correo / carpeta de subida). Es un archivo
de texto chico. NO mandes toda la carpeta, solo ese archivo.
No lo edites a mano.

Si algo falla
-------------
- La ventana negra muestra un error y se queda abierta: copiame ese texto.
- El navegador no abre solo: entra a  http://localhost:{port}

Gracias!
"""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--estado", required=True, help="slug del estado, p.ej. coahuila")
    ap.add_argument("--out", default=None, help="carpeta destino del kit")
    ap.add_argument("--pdfs", choices=["copy", "link", "skip"], default="copy")
    ap.add_argument("--no-runtime", action="store_true",
                    help="no copiar el runtime portable (kit más chico, requiere "
                         "que el runtime se agregue aparte)")
    ap.add_argument("--port", type=int, default=5500)
    ap.add_argument("--zip", action="store_true",
                    help="además, empaca el kit en un .zip para distribuir por enlace")
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

    # 3. Sección predial recortada (focus_predial) — lo que el revisor ve
    #    embebido por año.  Pequeño y esencial: SIEMPRE se incluye (aun con
    #    --pdfs skip, que solo omite los pdf_raw/pdf_ocr pesados).
    n_fp = _copy_tree(src_data / "focus_predial", kit_data / "focus_predial")
    n_ov = _copy_tree(src_data / "focus_predial_overrides",
                      kit_data / "focus_predial_overrides")
    _say(f"  focus_predial: {n_fp} archivos  (overrides: {n_ov})")

    # 4. PDFs fuente pesados (para el botón 'inicio de la ley' y fallback).
    #    --pdfs skip: kit ligero; el revisor copia los PDF aparte a su ritmo.
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

    # 6. Runtime portable (Python firmado + Flask + código).
    runtime_ok = True
    if not args.no_runtime:
        if not (RUNTIME_SRC / "runtime" / "python.exe").exists():
            runtime_ok = False
        else:
            for sub in ("runtime", "lib", "code"):
                dst = out / sub
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(RUNTIME_SRC / sub, dst,
                                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            _say("  runtime portable: copiado (Python firmado + Flask + código)")

    # 7. Lanzador + instrucciones.
    if args.pdfs == "skip":
        seccion_pdf = (
            "\nPASO 0.5 — Copiar los PDF (una sola vez, a tu ritmo)\n"
            "----------------------------------------------------\n"
            "Este kit NO trae los PDF originales (pesan mucho). Descargalos de la\n"
            f"carpeta de OneDrive que te comparti (PDFs_{estado.upper()}) y copialos\n"
            f"dentro del kit, en la carpeta  data\\{estado}\\  de modo que queden:\n"
            f"    data\\{estado}\\pdf_raw\\...\n"
            f"    data\\{estado}\\pdf_ocr\\...   (si esa carpeta existe)\n"
            "Puedes hacerlo poco a poco; el revisor funciona aunque falten algunos.\n"
            "La seccion de predial recortada SI se ve siempre (ya viene incluida);\n"
            "los botones 'inicio de la ley' / 'PDF fuente' apareceran para los PDF\n"
            "que ya hayas copiado.\n")
    else:
        seccion_pdf = ""
    fmt = {"estado": estado, "ESTADO_UP": estado.upper(), "port": args.port,
           "seccion_pdf": seccion_pdf}
    (out / f"REVISAR_{estado.upper()}.bat").write_text(_BAT.format(**fmt), encoding="utf-8")
    (out / "LEEME.txt").write_text(_LEEME.format(**fmt), encoding="utf-8")

    _say("\nKit armado.")
    if not runtime_ok:
        _say("  FALTA el runtime portable.  Corre primero: "
             "python -m scripts.temps.build_hitl_runtime")

    # 8. (Opcional) empacar en .zip para distribuir por enlace de descarga.
    if args.zip:
        _say("  empacando .zip (puede tardar con muchos PDFs)...")
        zip_base = str(out)  # crea {out}.zip
        shutil.make_archive(zip_base, "zip", root_dir=out.parent, base_dir=out.name)
        zpath = Path(zip_base + ".zip")
        gb = zpath.stat().st_size / 1e9 if zpath.exists() else 0
        _say(f"  ZIP listo ({gb:.2f} GB): {zpath}")
        _say("  Sube ESE .zip a OneDrive y comparte el enlace de descarga.")
    else:
        _say(f"  Carpeta lista: {out}  (usa --zip para un archivo único distribuible)")


if __name__ == "__main__":
    main()
