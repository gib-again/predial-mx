"""Utilidades schema-agnostic compartidas entre llm_extract_v2 y llm_extract_v3.

Contiene: cliente OpenAI, resolución CVEGEO, localización de source files,
overrides manuales, constantes de rescate, formateo de errores.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

from openai import OpenAI
from pydantic import ValidationError

# Cargar .env al importar (antes de leer OPENAI_MODEL/KEY) para que tanto el
# modelo como la API key sean configurables desde .env sin exportar a mano.
# No sobrescribe variables ya presentes en el entorno.
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# ── Rutas y configuración ──

ROOT = Path(__file__).resolve().parents[2]

# Default mini-first (cascada mini → full).  Definir en .env para sobreescribir.
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.4-mini")
OPENAI_MODEL_FALLBACK = os.environ.get("OPENAI_MODEL_FALLBACK", "gpt-5.4")

_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            # Cargar .env si la key no está exportada en el entorno (no sobrescribe
            # variables ya presentes).  Hace que run_pipeline extract / consume
            # funcionen sin exportar la key a mano.
            try:
                from dotenv import load_dotenv
                load_dotenv()
            except Exception:
                pass
            api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError("OPENAI_API_KEY no definida en el entorno ni en .env")
        _client = OpenAI(api_key=api_key)
    return _client


# ── Mapeo CVEGEO → slug, nombre ──
# La lógica canónica vive ahora en src.core.catalog; se reexporta aquí para
# no romper imports existentes (`from src.extraction.llm_utils import _resolve_cvegeo`).


def _resolve_cvegeo(cvegeo: str) -> tuple[str, str]:
    """Devuelve (slug, NOM_MUN) a partir del CVEGEO INEGI (5 dígitos)."""
    from src.core.catalog import resolve_cvegeo_pair

    return resolve_cvegeo_pair(cvegeo)


# ── Localizar source (con manual overrides) ──

_OVERRIDE_CACHE: dict[str, dict[tuple[int, str], dict]] = {}


def _load_overrides(estado: str) -> dict[tuple[int, str], dict]:
    """Carga `data/{estado}/manual_pdf_overrides.csv` si existe."""
    if estado in _OVERRIDE_CACHE:
        return _OVERRIDE_CACHE[estado]
    p = ROOT / "data" / estado / "manual_pdf_overrides.csv"
    out: dict[tuple[int, str], dict] = {}
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                try:
                    anio = int(r["anio"])
                except (KeyError, ValueError):
                    continue
                cvegeo = (r.get("cvegeo") or "").strip().zfill(5)
                if not cvegeo:
                    continue
                out[(anio, cvegeo)] = {
                    "pdf_correcto": (r.get("pdf_correcto") or "").strip(),
                    "paginas": (r.get("paginas") or "").strip(),
                    "nota": (r.get("nota_auditor") or "").strip(),
                }
    _OVERRIDE_CACHE[estado] = out
    return out


def _parse_paginas(spec: str) -> list[int] | None:
    """Convierte '30', '15-16', '1,3,5' o '' → list[int] | None."""
    if not spec:
        return None
    pages: list[int] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            pages.extend(range(int(a), int(b) + 1))
        elif part:
            pages.append(int(part))
    return pages or None


def _apply_pdf_override(
    estado: str, prefijo: str, anio: int, slug: str, override: dict,
) -> tuple[Path | None, Path | None]:
    """Genera TXT/PDF temporales recortados a las páginas del override."""
    src_pdf = Path(override["pdf_correcto"])
    if not src_pdf.is_absolute():
        src_pdf = ROOT / src_pdf
    if not src_pdf.exists():
        print(f"  [override] PDF no existe: {src_pdf}")
        return (None, None)

    pages = _parse_paginas(override["paginas"])

    out_dir = ROOT / "data" / estado / "focus_predial_overrides" / str(anio)
    out_dir.mkdir(parents=True, exist_ok=True)
    name = f"{prefijo}_PREDIAL_{anio}_{slug}"
    out_txt = out_dir / f"{name}.txt"
    out_pdf = out_dir / f"{name}.pdf"

    if out_txt.exists() and out_pdf.exists():
        if out_txt.stat().st_mtime >= src_pdf.stat().st_mtime:
            return (out_txt, out_pdf)

    try:
        import fitz
    except ImportError:
        if pages is None:
            import shutil
            shutil.copy2(src_pdf, out_pdf)
            return (None, out_pdf)
        return (None, None)

    with fitz.open(src_pdf) as doc:
        n = doc.page_count
        if pages is None:
            page_idxs = list(range(n))
        else:
            page_idxs = [p - 1 for p in pages if 1 <= p <= n]

        if not page_idxs:
            return (None, None)

        texto = "\n\n".join(
            doc[i].get_text("text") or "" for i in page_idxs
        ).strip()

        new_doc = fitz.open()
        for i in page_idxs:
            new_doc.insert_pdf(doc, from_page=i, to_page=i)
        new_doc.save(str(out_pdf), deflate=True)
        new_doc.close()

    out_txt.write_text(texto, encoding="utf-8")
    return (out_txt, out_pdf)


def _find_focus_paths(
    estado: str,
    prefijo: str,
    anio: int,
    slug: str,
    cvegeo: str | None = None,
) -> tuple[Path | None, Path | None]:
    """Localiza el TXT/PDF de la sección predial."""
    if cvegeo:
        cvegeo_padded = str(cvegeo).zfill(5)
        overrides = _load_overrides(estado)
        ov = overrides.get((anio, cvegeo_padded))
        if ov:
            txt, pdf = _apply_pdf_override(estado, prefijo, anio, slug, ov)
            if txt is not None:
                return (txt, pdf)

    base = ROOT / "data" / estado / "focus_predial"
    name = f"{prefijo}_PREDIAL_{anio}_{slug}"
    primary = base / str(anio)
    txt = primary / f"{name}.txt"
    pdf = primary / f"{name}.pdf"
    if not txt.exists():
        for hit in base.rglob(f"{name}.txt"):
            txt = hit
            break
    if not pdf.exists():
        for hit in base.rglob(f"{name}.pdf"):
            pdf = hit
            break
    return (txt if txt.exists() else None, pdf if pdf.exists() else None)


# ── Formateo de errores ──

def _format_validation_error(e: ValidationError) -> str:
    parts = []
    for err in e.errors()[:6]:
        loc = ".".join(str(p) for p in err["loc"])
        parts.append(f"  • {loc}: {err['msg']}")
    return "\n".join(parts)


# ── Constantes de rescate ──

_REOCR_MIN_CHARS = 1500
_REOCR_IMPROVEMENT_FACTOR = 3.0

_P00_DESCRIPCION_SIGNALS = (
    "sólo menciona una cuota",
    "solo menciona una cuota",
    "no establece tarifa",
    "rige por la ley general",
    "remite a la ley general",
    "no causa el impuesto",
    "ley estatal de hacienda",
    "ley general de hacienda municipal",
    "se rige por la ley",
    "tres salarios mínimos",
    "tres salarios minimos",
    "única tasa visible corresponde al impuesto sobre adquisición",
    "unica tasa visible corresponde al impuesto sobre adquisicion",
)


def _patch_schema_for_openai(node):
    """Normaliza recursivamente para strict mode de OpenAI."""
    if isinstance(node, dict):
        if "oneOf" in node:
            node["anyOf"] = node.pop("oneOf")
        for k in ("discriminator", "default", "title", "minItems", "maxItems"):
            node.pop(k, None)
        for v in node.values():
            _patch_schema_for_openai(v)
    elif isinstance(node, list):
        for item in node:
            _patch_schema_for_openai(item)
    return node
