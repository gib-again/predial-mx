"""
Preprocesado de PDFs de Oaxaca: eliminación de la marca de agua
"DOCUMENTO SOLO PARA CONSULTA" antes del OCR.

Estrategia en dos fases por PDF:

  Fase 0 — Vector strip (intento barato):
    Inspeccionar el PDF con pikepdf. Si la marca de agua está como overlay
    vectorial (Form XObject o stamp en el content stream con el texto literal
    "DOCUMENTO SOLO PARA CONSULTA"), removerla directamente. Esto preserva
    el texto vectorial original sin pérdida de calidad.

  Fase 1 — Raster threshold:
    Si Fase 0 no aplica, renderizar cada página a 300 DPI con PyMuPDF,
    convertir a grayscale numpy array, aplicar threshold por luminancia
    (pixeles más claros que T → blanco puro; el resto se preserva), y
    reensamblar el PDF limpio insertando cada página como imagen.

El watermark de Oaxaca es gris medio (luminancia ~180-210) sobre cuerpo
de texto casi negro (luminancia ~30-50): un threshold simple lo separa
limpiamente sin tocar el cuerpo del texto.

Ejemplo de uso:
    from src.estados.oaxaca.preprocess import clean_pdf_watermark
    info = clean_pdf_watermark(input_pdf, output_pdf, dpi=300)
"""

from __future__ import annotations

import io
import re
import time
from pathlib import Path

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

WATERMARK_PATTERN = re.compile(
    r"DOCUMENTO\s+SOLO\s+PARA\s+CONSULTA",
    re.IGNORECASE,
)

# Calibrado contra muestras 2010-2023: el cuerpo del texto de Oaxaca está
# en luminancia [0-90] (negro/oscuro), el watermark "DOCUMENTO SOLO PARA
# CONSULTA" varía: en la mayoría de PDFs cae en [150-180], pero en algunos
# (sobre todo 2019-2021) cae en [120-150] (más oscuro). La heurística
# adaptativa busca el peak de luminancia del watermark (rango medio
# [80,220), excluyendo texto y fondo) y pone el threshold debajo del peak
# para garantizar que TODOS los pixeles del watermark caigan a blanco.
DEFAULT_THRESHOLD = 140
ADAPTIVE_FLOOR = 120
ADAPTIVE_CEIL = 170
ADAPTIVE_MARGIN = 15  # peak_center - MARGIN = threshold


def clean_pdf_watermark(
    input_pdf: Path,
    output_pdf: Path,
    *,
    dpi: int = 300,
    threshold: int | None = None,
    adaptive: bool = True,
) -> dict:
    """
    Genera una versión del PDF sin la marca de agua de Oaxaca.

    Intenta primero strip vectorial (barato y sin pérdida); si falla,
    cae al pipeline raster con threshold por luminancia.

    Args:
        input_pdf: PDF original con watermark.
        output_pdf: Destino del PDF limpio. Se crean directorios padre.
        dpi: Resolución de rasterizado en la fase raster.
        threshold: Si se da, fija el threshold para todas las páginas.
            Si None y adaptive=True, se calcula por página.
        adaptive: Si True y threshold es None, usa heurística por página.

    Returns:
        dict con:
          - pages: int, páginas procesadas
          - thresholds_used: list[int], threshold por página (vacío si vector)
          - vector_stripped: bool, True si bastó la fase 0
          - elapsed_ms: int, tiempo total en ms
    """
    output_pdf.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    if _try_vector_watermark_strip(input_pdf, output_pdf):
        # Verificar que el output existe y tiene contenido
        if output_pdf.exists() and output_pdf.stat().st_size > 0:
            return {
                "pages": _safe_page_count(output_pdf),
                "thresholds_used": [],
                "vector_stripped": True,
                "elapsed_ms": int((time.perf_counter() - t0) * 1000),
            }

    pages, thresholds = _raster_clean(
        input_pdf,
        output_pdf,
        dpi=dpi,
        fixed_threshold=threshold,
        adaptive=adaptive,
    )

    return {
        "pages": pages,
        "thresholds_used": thresholds,
        "vector_stripped": False,
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
    }


def _safe_page_count(pdf_path: Path) -> int:
    try:
        with fitz.open(pdf_path) as doc:
            return doc.page_count
    except Exception:
        return 0


def _try_vector_watermark_strip(input_pdf: Path, output_pdf: Path) -> bool:
    """
    Intenta remover el watermark si está como overlay vectorial.

    Busca en cada página:
      1. Form XObjects que contengan el texto del watermark.
      2. Bloques de texto en el content stream que matcheen el patrón.

    Si encuentra y remueve al menos una ocurrencia, guarda el PDF
    limpio en output_pdf y retorna True. Si no encuentra nada
    aplicable o falla la operación, retorna False (y el caller
    debe usar el fallback raster).
    """
    try:
        import pikepdf
    except ImportError:
        return False

    try:
        with pikepdf.open(input_pdf) as pdf:
            stripped_any = False

            for page in pdf.pages:
                # 1. Form XObjects (stamps típicamente)
                resources = page.get("/Resources")
                if resources is not None:
                    xobjects = resources.get("/XObject")
                    if xobjects is not None:
                        for xname in list(xobjects.keys()):
                            xobj = xobjects[xname]
                            try:
                                stream_bytes = bytes(xobj.read_bytes())
                            except Exception:
                                continue
                            if _contains_watermark(stream_bytes):
                                del xobjects[xname]
                                stripped_any = True

                # 2. Texto literal en el content stream de la página
                try:
                    raw = page.Contents.read_bytes() if hasattr(page, "Contents") else None
                except Exception:
                    raw = None

                if raw and _contains_watermark(raw):
                    cleaned = _strip_watermark_text_blocks(raw)
                    if cleaned is not None and cleaned != raw:
                        page.Contents.write(cleaned)
                        stripped_any = True

            if not stripped_any:
                return False

            pdf.save(output_pdf)
            return True

    except Exception:
        return False


def _contains_watermark(stream_bytes: bytes) -> bool:
    """Busca el texto del watermark en bytes de un content stream."""
    try:
        decoded = stream_bytes.decode("latin-1", errors="ignore")
    except Exception:
        return False
    return bool(WATERMARK_PATTERN.search(decoded))


def _strip_watermark_text_blocks(raw: bytes) -> bytes | None:
    """
    Elimina BT...ET (text blocks) que contengan el watermark.

    Los bloques de texto en PDFs van entre operadores BT (Begin Text)
    y ET (End Text). Si un bloque contiene el patrón del watermark,
    lo borramos completo. Operación conservadora: si no podemos decodificar
    el stream, retornamos None y el caller usa el fallback raster.
    """
    try:
        raw.decode("latin-1", errors="ignore")
    except Exception:
        return None

    pattern = re.compile(rb"BT\b.*?ET\b", re.DOTALL)
    out = bytearray()
    last = 0
    for m in pattern.finditer(raw):
        block = m.group(0)
        try:
            block_text = block.decode("latin-1", errors="ignore")
        except Exception:
            continue
        if WATERMARK_PATTERN.search(block_text):
            out.extend(raw[last:m.start()])
            last = m.end()
    out.extend(raw[last:])
    return bytes(out) if last > 0 else raw


def _compute_threshold(arr: np.ndarray, fallback: int = DEFAULT_THRESHOLD) -> int:
    """
    Heurística adaptativa: localiza el peak del watermark y pone el
    threshold MARGIN luminancia debajo del peak para asegurar que toda
    la distribución del watermark caiga a blanco.

    Mira solo el rango [80,220) (excluye texto negro y fondo blanco),
    construye histograma con bins de 10 luminancia, y toma el bin con
    más pixeles como centro del watermark.

    Para PDFs típicos de Oaxaca el peak está en [150-180) → T≈155.
    Para PDFs con watermark más oscuro (~140) el peak cae en [140-150)
    → T≈130.
    """
    mid = arr[(arr >= 80) & (arr < 220)]
    if mid.size < 1000:
        return fallback
    try:
        hist, edges = np.histogram(mid, bins=range(80, 230, 10))
        peak_idx = int(np.argmax(hist))
        peak_center = int((edges[peak_idx] + edges[peak_idx + 1]) / 2)
    except Exception:
        return fallback
    candidate = peak_center - ADAPTIVE_MARGIN
    return max(ADAPTIVE_FLOOR, min(ADAPTIVE_CEIL, candidate))


def _clean_page_array(arr: np.ndarray, threshold: int) -> np.ndarray:
    """
    Binarización pura: pixeles > threshold → 255 (blanco), <= threshold → 0 (negro).

    Por qué binarizar (no preservar grises):
      - Versión grayscale dejaba mid-tones [120-150) (anti-alias del texto + bordes
        del watermark) que sobrevivían al threshold.
      - Esos mid-tones, al re-encodearse con JPEG en ocrmypdf (--optimize 1
        --jpeg-quality 80), generaban artefactos de bloque/halo que reintroducían
        un fantasma del watermark visible.
      - Binarización pura garantiza output con sólo 0 y 255 → ningún re-encoder
        puede inventar mid-tones, el watermark queda definitivamente borrado.
      - Tesseract trabaja igual de bien con B/W puro que con grayscale.
      - Reduce ~5× el tamaño del PDF intermedio (1-bit comprime mejor que JPEG).
    """
    return np.where(arr > threshold, np.uint8(255), np.uint8(0)).astype(np.uint8)


def _raster_clean(
    input_pdf: Path,
    output_pdf: Path,
    *,
    dpi: int,
    fixed_threshold: int | None,
    adaptive: bool,
) -> tuple[int, list[int]]:
    """
    Pipeline raster: render → grayscale → threshold → reensamblar PDF.

    Devuelve (pages_procesadas, thresholds_usados).
    """
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)

    src = fitz.open(input_pdf)
    try:
        out = fitz.open()
        try:
            thresholds: list[int] = []

            for page in src:
                pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csGRAY, alpha=False)
                arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)

                if fixed_threshold is not None:
                    t = int(fixed_threshold)
                elif adaptive:
                    t = _compute_threshold(arr)
                else:
                    t = DEFAULT_THRESHOLD
                thresholds.append(t)

                cleaned = _clean_page_array(arr, t)

                # Como _clean_page_array binariza, convertimos directo a 1-bit
                # PNG (lossless, comprime ~10× mejor que JPEG en B/W).
                img = Image.fromarray(cleaned, mode="L").convert("1")
                buf = io.BytesIO()
                img.save(buf, format="PNG", optimize=True)
                buf.seek(0)

                page_w_pt = pix.width * 72.0 / dpi
                page_h_pt = pix.height * 72.0 / dpi
                new_page = out.new_page(width=page_w_pt, height=page_h_pt)
                new_page.insert_image(new_page.rect, stream=buf.getvalue())

            out.save(output_pdf, deflate=True, garbage=3)
            return src.page_count, thresholds
        finally:
            out.close()
    finally:
        src.close()
