"""Utilidades de re-OCR y rasterización para fallback de extracción.

Cuando el TXT pre-extraído de un focus_predial está incompleto o vacío de
señales tarifarias, este módulo permite:

  - aggressive_reocr(pdf_path, pages, dpi, lang)
        Re-OCR con tesseract a 600 dpi (config="--psm 6") sobre páginas
        específicas. Devuelve texto concatenado.

  - pdf_pages_to_base64(pdf_path, pages, dpi)
        Convierte páginas a PNG base64 (data URLs) para enviar a un modelo
        multimodal (gpt-5.4 con visión).

Ambas funciones son tolerantes a falta de dependencias: si pytesseract o
pdf2image no están disponibles, devuelven cadena vacía / lista vacía con
un warning, en lugar de fallar.

PyMuPDF (fitz) sirve como rasterizador alterno si pdf2image+poppler no
están disponibles — generalmente más confiable en Windows.
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ── Re-OCR agresivo ──

def aggressive_reocr(
    pdf_path: Path,
    pages: list[int] | None = None,
    dpi: int = 600,
    lang: str = "spa+lat",
    psm: int = 6,
) -> str:
    """Re-OCR de páginas específicas con tesseract.

    Args:
        pdf_path: ruta al PDF.
        pages: lista de páginas 1-based. None = todas.
        dpi: resolución de rasterización (600 es agresivo, 300 más rápido).
        lang: idiomas tesseract (`spa+lat` para español + latín extendido).
        psm: page-segmentation mode tesseract (6 = bloque uniforme).

    Returns:
        Texto OCR concatenado, separando páginas con doble newline.
        Cadena vacía si las dependencias no están disponibles o el PDF no
        existe.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.warning(f"aggressive_reocr: PDF no existe: {pdf_path}")
        return ""

    try:
        import pytesseract
        from PIL import Image
    except ImportError as e:
        logger.warning(f"aggressive_reocr: pytesseract/PIL no disponible ({e})")
        return ""

    try:
        import fitz  # PyMuPDF — rasterizador preferido en Windows
    except ImportError:
        fitz = None

    images: list[Image.Image] = []

    # Preferencia: PyMuPDF (no requiere poppler externo, funciona en Windows)
    if fitz is not None:
        try:
            with fitz.open(pdf_path) as doc:
                n_pages = doc.page_count
                page_idxs = (
                    [p - 1 for p in pages if 1 <= p <= n_pages]
                    if pages else list(range(n_pages))
                )
                # zoom = dpi/72 (PDF default ~72 dpi)
                mat = fitz.Matrix(dpi / 72, dpi / 72)
                for i in page_idxs:
                    pix = doc[i].get_pixmap(matrix=mat, alpha=False)
                    img = Image.open(io.BytesIO(pix.tobytes("png")))
                    images.append(img)
        except Exception as e:
            logger.warning(f"aggressive_reocr: fitz rasterización falló ({e}), intentando pdf2image")
            images = []

    # Fallback: pdf2image (requiere poppler)
    if not images:
        try:
            from pdf2image import convert_from_path
            kwargs = {"dpi": dpi}
            if pages:
                kwargs["first_page"] = min(pages)
                kwargs["last_page"] = max(pages)
            images = convert_from_path(str(pdf_path), **kwargs)
        except Exception as e:
            logger.warning(f"aggressive_reocr: pdf2image falló ({e})")
            return ""

    if not images:
        return ""

    config = f"--psm {psm}"
    parts: list[str] = []
    for img in images:
        try:
            txt = pytesseract.image_to_string(img, lang=lang, config=config)
            parts.append(txt or "")
        except Exception as e:
            logger.warning(f"aggressive_reocr: tesseract falló en una página ({e})")
            parts.append("")

    return "\n\n".join(parts).strip()


# ── Rasterización para visión ──

def pdf_pages_to_base64(
    pdf_path: Path,
    pages: list[int] | None = None,
    dpi: int = 150,
    max_pages: int = 6,
) -> list[str]:
    """Convierte páginas del PDF a PNG base64 (data URLs) para mensajes multimodales.

    Args:
        pdf_path: ruta al PDF.
        pages: lista 1-based. None = primeras `max_pages`.
        dpi: resolución (150 da legibilidad sin inflar tokens; 200 si la
             tabla es muy densa).
        max_pages: tope de páginas a rasterizar (~7 imágenes ya saturan
            tokens en gpt-5.4).

    Returns:
        Lista de strings tipo `"data:image/png;base64,iVBORw0KG..."`.
        Lista vacía si las dependencias no están o el PDF no existe.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        logger.warning(f"pdf_pages_to_base64: PDF no existe: {pdf_path}")
        return []

    try:
        import fitz
    except ImportError:
        logger.warning("pdf_pages_to_base64: PyMuPDF no disponible")
        return []

    out: list[str] = []
    try:
        with fitz.open(pdf_path) as doc:
            n_pages = doc.page_count
            if pages:
                page_idxs = [p - 1 for p in pages if 1 <= p <= n_pages]
            else:
                page_idxs = list(range(min(n_pages, max_pages)))
            page_idxs = page_idxs[:max_pages]

            mat = fitz.Matrix(dpi / 72, dpi / 72)
            for i in page_idxs:
                pix = doc[i].get_pixmap(matrix=mat, alpha=False)
                png_bytes = pix.tobytes("png")
                b64 = base64.b64encode(png_bytes).decode("ascii")
                out.append(f"data:image/png;base64,{b64}")
    except Exception as e:
        logger.warning(f"pdf_pages_to_base64: fitz falló ({e})")
        return []

    return out


__all__ = ["aggressive_reocr", "pdf_pages_to_base64"]
