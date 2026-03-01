"""
Utilidades para lectura, indexación y recorte de PDFs.

Usa PyMuPDF (fitz) para toda la extracción de texto (~5-10x más rápido que pdfplumber).

Funciones:
  - build_text_and_offsets()  → texto concatenado + offsets por página
  - idx_to_page()             → carácter → página (bisect O(log n))
  - save_pdf_slice()          → recorte de PDFs
  - is_scanned_pdf()          → detecta si necesita OCR

Caché persistente en disco para no re-extraer PDFs ya procesados.
"""

import hashlib
import json
import bisect
from pathlib import Path

import fitz  # PyMuPDF

# ── Directorio de caché (relativo al CWD del proyecto) ──
_CACHE_DIR = Path(".text_cache")


def _cache_key(pdf_path: Path) -> str:
    stat = pdf_path.stat()
    raw = f"{pdf_path.resolve()}|{stat.st_size}|{stat.st_mtime_ns}"
    return hashlib.md5(raw.encode()).hexdigest()


def _load_from_cache(pdf_path: Path) -> tuple[str, list[int]] | None:
    key = _cache_key(pdf_path)
    cache_file = _CACHE_DIR / f"{key}.json"
    if not cache_file.exists():
        return None
    try:
        data = json.loads(cache_file.read_text(encoding="utf-8"))
        return data["raw_text"], data["page_starts"]
    except Exception:
        cache_file.unlink(missing_ok=True)
        return None


def _save_to_cache(pdf_path: Path, raw_text: str, page_starts: list[int]):
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        key = _cache_key(pdf_path)
        cache_file = _CACHE_DIR / f"{key}.json"
        cache_file.write_text(
            json.dumps({"raw_text": raw_text, "page_starts": page_starts},
                       ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def build_text_and_offsets(pdf_path: Path) -> tuple[str, list[int]]:
    """
    Lee un PDF con PyMuPDF y devuelve:
      - raw_text: texto concatenado (separado por '\\n' entre páginas)
      - page_starts: índice de carácter donde inicia cada página (0-based)
    """
    cached = _load_from_cache(pdf_path)
    if cached is not None:
        return cached

    parts: list[str] = []
    page_starts: list[int] = []
    cursor = 0

    with fitz.open(pdf_path) as doc:
        for page in doc:
            page_starts.append(cursor)
            t = page.get_text("text") or ""
            parts.append(t)
            parts.append("\n")
            cursor += len(t) + 1

    raw_text = "".join(parts)
    _save_to_cache(pdf_path, raw_text, page_starts)
    return raw_text, page_starts


def idx_to_page(idx: int, page_starts: list[int]) -> int:
    """Convierte un índice de carácter en número de página (1-based)."""
    pos = bisect.bisect_right(page_starts, idx)
    return max(1, pos)


def save_pdf_slice(
    pdf_path: Path,
    page_start: int,
    page_end: int,
    out_path: Path,
) -> None:
    """Recorta un PDF entre page_start y page_end (1-based, inclusive)."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with fitz.open(pdf_path) as doc:
        new_doc = fitz.open()
        s = max(1, page_start) - 1
        e = min(doc.page_count, page_end)
        new_doc.insert_pdf(doc, from_page=s, to_page=e - 1)
        new_doc.save(str(out_path), deflate=True)
        new_doc.close()


def is_scanned_pdf(pdf_path: Path, sample_pages: int = 3, threshold: int = 50) -> bool:
    """Heurística: promedio chars/página < threshold → escaneado."""
    with fitz.open(pdf_path) as doc:
        n = min(sample_pages, doc.page_count)
        if n == 0:
            return True
        total = sum(len(doc[i].get_text("text") or "") for i in range(n))
    return (total / n) < threshold


def get_page_count(pdf_path: Path) -> int:
    with fitz.open(pdf_path) as doc:
        return doc.page_count
