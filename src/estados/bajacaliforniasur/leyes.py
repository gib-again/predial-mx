"""
Lectura de las Leyes de Hacienda municipales de BCS (Word digital) y
localizacion de la seccion del Impuesto Predial.

Las leyes vienen en .doc (legacy, via antiword) o .docx (via python-docx).
La seccion predial es el Capitulo del Impuesto Predial: objeto -> sujetos ->
base y tasa (tasas diferenciadas "al millar" por tipo de predio) -> hasta el
siguiente impuesto (Adquisicion de Inmuebles / Diversiones / siguiente capitulo).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from src.estados.bajacaliforniasur import config

LEYES_DIR = Path("data") / config.ESTADO_SLUG / "leyes_hacienda"


def doc_path(slug: str, version: str) -> Path | None:
    """Ruta al archivo de la Ley de Hacienda (acepta .doc o .docx)."""
    base = LEYES_DIR / version
    sufijo = "2009" if version == "baseline_2009" else "actual"
    for ext in (".doc", ".docx"):
        p = base / f"LHacienda_{slug}_{sufijo}{ext}"
        if p.exists():
            return p
    return None


def extract_text(path: Path) -> str:
    """Extrae texto plano de .doc (antiword) o .docx (python-docx)."""
    if path.suffix.lower() == ".docx":
        import docx  # python-docx
        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    out = subprocess.run(
        ["antiword", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return out.stdout


_MIN_END_DISTANCE = 3000
_MAX_SECTION = 18000

_END_PATTERNS = [
    r"IMPUESTO SOBRE (?:LA )?ADQUISICI[OÓ]N",
    r"IMPUESTO SOBRE DIVERSIONES",
    r"IMPUESTO SOBRE ESPECT",
    r"T[IÍ]TULO\s+(?:TERCERO|III)\b",
    r"CAP[IÍ]TULO\s+TERCERO\b",
]


def locate_predial(text: str) -> tuple[int, int]:
    """Devuelve (start, end) de la seccion predial en `text`.

    Ancla el inicio en el Capitulo del Impuesto Predial DESPUES del cuerpo legal
    (primer "Articulo 1", para saltar el indice/sumario) exigiendo que el header
    venga seguido de objeto/sujetos/base-y-tasa. El fin es el siguiente impuesto
    a >MIN_END_DISTANCE chars (para saltar la enumeracion de impuestos del objeto).
    Retorna (-1, -1) si no se localiza.
    """
    U = text.upper()
    mb = re.search(r"ART[IÍ]CULO\s+1[°ºo.\s-]", U)
    body = mb.start() if mb else 0

    start = -1
    for m in re.finditer(r"IMPUESTO PREDIAL", U):
        if m.start() < body:
            continue
        if re.search(r"OBJETO|SON SUJETOS|BASE Y TASA|SE CAUSAR", U[m.start():m.start() + 1600]):
            start = m.start()
            break
    if start < 0:
        return -1, -1

    cands: list[int] = []
    for pat in _END_PATTERNS:
        for m in re.finditer(pat, U[start:]):
            if m.start() > _MIN_END_DISTANCE:
                cands.append(m.start())
                break
    end = start + min(cands) if cands else min(start + _MAX_SECTION, len(text))
    return start, end


def predial_text(slug: str, version: str) -> str | None:
    """Texto de la seccion predial para (municipio, version), o None."""
    p = doc_path(slug, version)
    if p is None:
        return None
    full = extract_text(p)
    s, e = locate_predial(full)
    if s < 0:
        return None
    return full[s:e].strip()
