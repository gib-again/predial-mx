"""Esquema único de ``segment.csv`` compartido por todos los estados.

Antes cada estado emitía columnas distintas (``ejercicio`` vs ``anio``,
``slug`` vs ``municipio_slug``, ``pdf_used`` vs ``source_pdf``, etc.), lo que
rompía los joins aguas abajo (Causa A).  Este módulo define un esquema
canónico, llaveado por ``cvegeo``, que todos los ``segment.py`` deben emitir
vía ``write_segment_csv`` y que la cola/UI leen vía ``read_segment_csv``.

Reglas de identidad:
- ``cvegeo`` es la llave canónica (5 dígitos).  '' = identidad no resuelta.
- ``municipio_raw`` guarda el texto crudo (OCR/header) **sólo** para auditoría;
  nunca se usa como identidad ni como nombre de display.
- El nombre para mostrar siempre se resuelve con ``catalog.cvegeo_to_nombre``.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import asdict, dataclass, fields, is_dataclass
from pathlib import Path

# ── Estados del caso de segmentación ──
STATUS_OK = "ok"
STATUS_NO_LOCALIZADA = "segmentacion_no_localizada"   # no se halló la sección
STATUS_IDENTIDAD = "identidad_no_resuelta"            # texto no matchea catálogo

# Orden fijo de columnas del segment.csv canónico.
SEGMENT_FIELDS = [
    "cvegeo",
    "estado_slug",
    "municipio_slug",      # slug canónico INEGI (de catalog), no del texto
    "municipio_raw",       # texto crudo (auditoría) — nunca identidad
    "anio",
    "status",
    "source_pdf",
    "ley_page_start",      # Nivel 1: inicio de la ley de ingresos del muni
    "ley_page_end",
    "predial_found",
    "predial_method",
    "predial_page_start",
    "predial_page_end",
    "char_start",
    "char_end",
    "confidence",
    "forced_end",
    "expansion_applied",
    "anchor_text_start",
    "anchor_text_end",
    "next_tax_label",
    "txt_file",
    "txt_chars",
]


@dataclass
class SegmentRow:
    cvegeo: str = ""
    estado_slug: str = ""
    municipio_slug: str = ""
    municipio_raw: str = ""
    anio: int | str = ""
    status: str = STATUS_OK
    source_pdf: str = ""
    ley_page_start: int | str = ""
    ley_page_end: int | str = ""
    predial_found: bool | str = ""
    predial_method: str = ""
    predial_page_start: int | str = ""
    predial_page_end: int | str = ""
    char_start: int | str = ""
    char_end: int | str = ""
    confidence: float | str = ""
    forced_end: bool | str = ""
    expansion_applied: bool | str = ""
    anchor_text_start: str = ""
    anchor_text_end: str = ""
    next_tax_label: str = ""
    txt_file: str = ""
    txt_chars: int | str = ""


# Alias legados → canónico.  Red de seguridad para CSVs aún no migrados; sólo
# se aplica cuando la columna canónica falta o está vacía.
_ALIASES = {
    "ejercicio": "anio",
    "slug": "municipio_slug",
    "pdf_used": "source_pdf",
    "page_start_ley": "ley_page_start",
    "page_end_ley": "ley_page_end",
}


def write_segment_csv(rows: Iterable[SegmentRow | dict], path: Path) -> Path:
    """Escribe ``segment.csv`` con el esquema canónico (columnas extra se ignoran)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=SEGMENT_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            d = asdict(r) if is_dataclass(r) else dict(r)
            w.writerow({k: d.get(k, "") for k in SEGMENT_FIELDS})
    return path


def read_segment_csv(path: Path) -> list[dict]:
    """Lee ``segment.csv`` normalizando alias legados a las llaves canónicas."""
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for old, new in _ALIASES.items():
            if old in row and not (row.get(new) or "").strip():
                row[new] = row[old]
    return rows


_SEGMENT_FIELD_NAMES = {f.name for f in fields(SegmentRow)}


def is_canonical(path: Path) -> bool:
    """True si el CSV ya trae la columna ``cvegeo`` (esquema canónico)."""
    if not path.exists():
        return False
    with path.open(encoding="utf-8-sig") as f:
        header = next(csv.reader(f), [])
    return "cvegeo" in header


# ── Canonicalización de filas nativas por-estado ──
# Mapeo único (nativo → canónico) usado tanto por la migración de CSVs
# existentes como por los segment.py al escribir.  Centralizar aquí evita que
# 9 estados divergan de nuevo.

def _first(row: dict, *keys: str) -> str:
    for k in keys:
        v = row.get(k)
        if v is not None and str(v).strip() != "":
            return v
    return ""


def load_ley_pages_from_master(estado_slug: str) -> dict[tuple[str, str], tuple[str, str]]:
    """(cvegeo, anio) -> (ley_page_start, ley_page_end) desde ``predial_master.csv``.

    Sólo Coahuila persiste el inicio de la ley (``page_start_ley``) en el master
    en vez de en el segment; el resto devuelve {} y el caller usa lo que tenga.
    """
    from src.core.catalog import build_cvegeo
    from src.core.constants import CVE_ENT_ESTADO

    path = Path("data") / estado_slug / "meta" / "predial_master.csv"
    out: dict[tuple[str, str], tuple[str, str]] = {}
    if not path.exists():
        return out
    cve_ent = CVE_ENT_ESTADO.get(estado_slug, "")
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            ps = _first(row, "page_start_ley", "ley_page_start")
            if not ps:
                continue
            pe = _first(row, "page_end_ley", "ley_page_end")
            anio = _first(row, "ejercicio", "anio")
            cve_mun = _first(row, "cve_mun")
            if not (cve_mun and cve_ent):
                continue
            out[(build_cvegeo(cve_ent, cve_mun), str(anio))] = (ps, pe)
    return out


def canonicalize_segment_row(
    estado_slug: str,
    row: dict,
    *,
    aliases: dict[str, str] | None = None,
    ley_pages: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> SegmentRow:
    """Mapea una fila nativa de cualquier estado a ``SegmentRow`` canónico.

    Resuelve ``cvegeo`` (desde ``cve_mun`` si existe, si no vía catálogo),
    normaliza nombres de columna divergentes y deriva ``status``.
    """
    from src.core.catalog import (
        build_cvegeo,
        cvegeo_to_nombre,
        cvegeo_to_slug,
        resolve_cvegeo,
    )
    from src.core.constants import CVE_ENT_ESTADO

    anio = _first(row, "anio", "ejercicio")
    municipio_raw = _first(row, "municipio_raw", "municipio")
    slug_in = _first(row, "municipio_slug", "slug")
    cve_ent = CVE_ENT_ESTADO.get(estado_slug, "")
    cve_mun = _first(row, "cve_mun")

    # Prioridad: (1) cvegeo ya presente y válido en catálogo → confiar (hace la
    # función idempotente y preserva el cvegeo derivado de cve_mun, que no está
    # en el esquema canónico); (2) cve_mun válido en catálogo; (3) resolución
    # por nombre/slug.  Todo candidato se valida contra el catálogo: un cve_mun
    # placeholder ("???") o inválido NO debe propagar un cvegeo basura.
    existing = str(_first(row, "cvegeo")).zfill(5) if _first(row, "cvegeo") else ""
    if existing and cvegeo_to_nombre(existing):
        cvegeo = existing
    else:
        cvegeo = ""
        if cve_mun and cve_ent:
            cand = build_cvegeo(cve_ent, cve_mun)
            if cvegeo_to_nombre(cand):
                cvegeo = cand
        if not cvegeo:
            cvegeo = resolve_cvegeo(estado_slug, slug_in or municipio_raw, aliases)

    municipio_slug = cvegeo_to_slug(cvegeo) if cvegeo else slug_in

    ley_start = _first(row, "ley_page_start")
    ley_end = _first(row, "ley_page_end")
    if not ley_start and ley_pages:
        lp = ley_pages.get((cvegeo, str(anio)))
        if lp:
            ley_start, ley_end = lp
    if estado_slug == "jalisco" and not ley_start:
        ley_start = 1  # un PDF por ley → la ley arranca en la página 1

    predial_start = _first(row, "predial_page_start", "page_start")
    predial_end = _first(row, "predial_page_end", "page_end")
    txt_file = _first(row, "txt_file", "focus_file")

    # "Localizado" = hay contenido extraíble: o se ubicó la página de predial, o
    # existe un focus txt (algunos estados, p.ej. GTO, extraen de la ley completa
    # sin fijar la página de predial).  ``predial_found`` trae vocabularios
    # distintos por estado (skipped/fallback/true); sólo refuerza.
    has_page = bool(str(predial_start).strip())
    has_focus = bool(str(txt_file).strip())
    predial_found = (
        has_page
        or has_focus
        or str(_first(row, "predial_found")).strip().lower() in ("true", "1", "yes")
    )

    if not cvegeo:
        status = STATUS_IDENTIDAD
    elif not predial_found:
        status = STATUS_NO_LOCALIZADA
    else:
        status = STATUS_OK

    return SegmentRow(
        cvegeo=cvegeo,
        estado_slug=estado_slug,
        municipio_slug=municipio_slug,
        municipio_raw=municipio_raw,
        anio=anio,
        status=status,
        source_pdf=_first(row, "source_pdf", "pdf_used"),
        ley_page_start=ley_start,
        ley_page_end=ley_end,
        predial_found=predial_found,
        predial_method=_first(row, "predial_method", "segment_method"),
        predial_page_start=predial_start,
        predial_page_end=predial_end,
        char_start=_first(row, "char_start"),
        char_end=_first(row, "char_end"),
        confidence=_first(row, "confidence"),
        forced_end=_first(row, "forced_end"),
        expansion_applied=_first(row, "expansion_applied"),
        anchor_text_start=_first(row, "anchor_text_start"),
        anchor_text_end=_first(row, "anchor_text_end"),
        next_tax_label=_first(row, "next_tax_label"),
        txt_file=txt_file,
        txt_chars=_first(row, "txt_chars"),
    )


def canonicalize_segment_rows(
    estado_slug: str,
    rows: list[dict],
    aliases: dict[str, str] | None = None,
    ley_pages: dict[tuple[str, str], tuple[str, str]] | None = None,
) -> list[SegmentRow]:
    """Canonicaliza una lista de filas nativas (resuelve master una sola vez)."""
    if ley_pages is None:
        ley_pages = load_ley_pages_from_master(estado_slug)
    return [
        canonicalize_segment_row(estado_slug, r, aliases=aliases, ley_pages=ley_pages)
        for r in rows
    ]


def canonicalize_segment_file(
    estado_slug: str,
    aliases: dict[str, str] | None = None,
    path: Path | None = None,
) -> list[SegmentRow]:
    """Lee, canonicaliza y reescribe ``segment.csv`` in-place.  Idempotente.

    Devuelve las filas canónicas (para que el caller compute estadísticas).
    """
    path = path or Path("data") / estado_slug / "meta" / "segment.csv"
    rows = read_segment_csv(path)
    canon = canonicalize_segment_rows(estado_slug, rows, aliases=aliases)
    if canon:
        write_segment_csv(canon, path)
    return canon
