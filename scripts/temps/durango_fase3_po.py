"""
Durango FASE 3 (FY2011-2015) — JOB NOCTURNO: descarga + OCR de las gacetas
escaneadas del Periodico Oficial.

Las Leyes de Ingresos municipales 2011-2015 NO estan en el Congreso (ni en
carpetas de leyes ni como decretos digitales identificables). Estan en las
gacetas del PO (periodicooficial.durango.gob.mx, Next.js + PDFs en S3
transp23), publicadas como DECRETO en numeros de fin de diciembre. Son
ESCANEADAS (300-600 pp) y multi-municipio.

Este script (para correr de noche):
  1. Por cada anio de publicacion 2010-2014, lee la pagina `?anio={anio}` del PO
     (SSR; muestra los ~20 periodicos mas recientes = ventana nov-dic).
  2. Filtra los de diciembre con "DECRETO" en `asuntos` (candidatos a contener
     las leyes de ingresos municipales).
  3. Descarga el PDF (S3) a data/durango/pdf_raw/{anio_pub}/.
  4. OCR (ocrmypdf --force-ocr) -> data/durango/pdf_ocr/{anio_pub}/.
     (mismos directorios que el resto del pipeline Grupo A; los nombres de
     archivo de gaceta {num}-{tipo}-{anio}.pdf no colisionan con el patron
     DGO_RAW_{anio}_{slug}.pdf de las leyes del Congreso, que viven en los
     mismos anios-carpeta cuando aplica.)

Reanudable: salta descargas y OCR ya hechos. La segmentacion 2-niveles
(localizar cada ley municipal dentro de la gaceta OCR'd y luego el predial) es
trabajo de seguimiento (no en este script).

Uso:  python -m scripts.temps.durango_fase3_po
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import fitz  # PyMuPDF (conteo de paginas)

# Solo se OCR'an las gacetas grandes: las que agrupan las ~39 leyes de ingresos
# municipales tienen cientos de paginas; las demas gacetas DECRETO son chicas.
MIN_PAGINAS_OCR = 150

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
PO_BASE = "https://periodicooficial.durango.gob.mx"
DATA = Path("data") / "durango"
RAW = DATA / "pdf_raw"
OCR = DATA / "pdf_ocr"

# Anios de publicacion -> FY (la ley de FY{n} se publica en dic de {n-1}).
PUB_YEARS = [2010, 2011, 2012, 2013, 2014]  # FY2011..FY2015


def _curl_text(url: str) -> str:
    return subprocess.run(["curl", "-s", "-L", "-k", "-A", UA, "--max-time", "60", url],
                          capture_output=True).stdout.decode("utf-8", errors="replace")


def _po_records(anio: int) -> list[dict]:
    html = _curl_text(f"{PO_BASE}/periodicos?anio={anio}").replace('\\"', '"')
    recs = []
    for m in re.finditer(
        r'"num":(\d+),"type":"(\w+)","year":(\d+),"status":"[^"]*","asuntos":"([^"]*)"'
        r'[^}]*?"fecha_emision":"([^"]*)"[^}]*?"periodico_url":"(https://[^"]+\.pdf)"',
        html,
    ):
        recs.append({"num": int(m.group(1)), "type": m.group(2), "asuntos": m.group(4),
                     "fecha": m.group(5), "url": m.group(6)})
    return recs


def _es_candidato(r: dict) -> bool:
    # diciembre + DECRETO en asuntos (las leyes de ingresos se publican como decreto)
    return r["fecha"][5:7] == "12" and "DECRETO" in r["asuntos"].upper()


def _download(url: str, out: Path) -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and out.stat().st_size > 10000:
        return True
    res = subprocess.run(["curl", "-s", "-L", "-k", "-A", UA, "--max-time", "600",
                          "--retry", "2", url, "-o", str(out)], capture_output=True)
    return res.returncode == 0 and out.exists() and out.stat().st_size > 10000


def _ocr(src: Path, dst: Path) -> str:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and dst.stat().st_size > 10000:
        return "already_exists"
    cmd = ["ocrmypdf", "--language", "spa", "--force-ocr", "--rotate-pages",
           "--deskew", "--optimize", "0", "--tesseract-timeout", "300",
           "--jobs", "4", "--output-type", "pdf", str(src), str(dst)]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=14400)
        if r.returncode in (0, 6, 15):
            return "ok"
        dst.unlink(missing_ok=True)
        return f"error:rc{r.returncode}"
    except Exception as e:
        dst.unlink(missing_ok=True)
        return f"error:{type(e).__name__}"


def run() -> None:
    print("=== Durango FASE 3: descarga + OCR de gacetas del PO (NOCTURNO) ===")
    n_dl = n_ocr = 0
    for anio in PUB_YEARS:
        recs = _po_records(anio)
        cands = [r for r in recs if _es_candidato(r)]
        print(f"  [{anio}] {len(recs)} periodicos, {len(cands)} candidatos DECRETO-dic")
        for r in cands:
            stem = f"{r['num']}-{r['type'].lower()}-{anio}"
            raw = RAW / str(anio) / f"{stem}.pdf"
            if _download(r["url"], raw):
                n_dl += 1
            else:
                print(f"    ERROR descarga {stem}")
                continue
            # Solo OCR si es una gaceta grande (bundle de leyes municipales).
            try:
                with fitz.open(str(raw)) as d:
                    npag = len(d)
            except Exception:
                npag = 0
            if npag < MIN_PAGINAS_OCR:
                continue
            ocr = OCR / str(anio) / f"{stem}_ocr.pdf"
            st = _ocr(raw, ocr)
            if st in ("ok", "already_exists"):
                n_ocr += 1
                print(f"    OCR {st}: {stem} ({npag}pp, {raw.stat().st_size // (1024*1024)}MB)")
            else:
                print(f"    OCR {st}: {stem} ({npag}pp)")
    print(f"\nFase 3 nocturno: {n_dl} gacetas descargadas, {n_ocr} OCR'd.")
    print("Siguiente (manana): segmentacion 2-niveles sobre pdf_ocr/ + extract.")


if __name__ == "__main__":
    run()
