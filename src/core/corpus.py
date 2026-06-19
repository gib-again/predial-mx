"""Acceso centralizado al corpus v3.

El corpus canónico vive en ``data/{estado}/json_predial/{anio}/`` y las
correcciones HITL en un overlay paralelo ``data/{estado}/json_predial_hitl/{anio}/``
(se conservan los originales; el overlay gana cuando existe).

Estas funciones son la **única** forma de localizar JSONs v3 para que la ruta
sea consistente entre el extractor, los detectores, la UI y los orquestadores.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from src.core.constants import (
    PREFIJOS_ESTADO,
    json_predial_dir,
    json_predial_hitl_dir,
    json_predial_hitl_root,
    json_predial_root,
)

_FNAME_RE = re.compile(r"_PREDIAL_(\d{4})_(.+)\.json$")


def _norm_slug(s: str) -> str:
    n = unicodedata.normalize("NFD", s or "")
    n = "".join(c for c in n if unicodedata.category(c) != "Mn").lower()
    return n.replace(" ", "_").replace("/", "_").replace(".", "")


def iter_corpus_files(estado: str, *, prefer_hitl: bool = True) -> list[Path]:
    """Lista de JSONs v3 del estado.  El overlay HITL reemplaza al canónico
    cuando ambos existen para el mismo nombre de archivo."""
    chosen: dict[str, Path] = {}
    canon_root = json_predial_root(estado)
    if canon_root.exists():
        for p in sorted(canon_root.glob("*/*.json")):
            chosen[p.name] = p
    if prefer_hitl:
        hitl_root = json_predial_hitl_root(estado)
        if hitl_root.exists():
            for p in sorted(hitl_root.glob("*/*.json")):
                chosen[p.name] = p
    return sorted(chosen.values())


def parse_fname(path: Path | str) -> tuple[int, str] | None:
    """(anio, slug) desde un nombre de archivo v3, o None si no matchea."""
    m = _FNAME_RE.search(Path(path).name)
    if not m:
        return None
    return int(m.group(1)), m.group(2)


def resolve_json(estado: str, anio: int, slug: str, *, prefer_hitl: bool = True) -> Path:
    """Localiza el JSON v3 de un (estado, anio, slug).  Path('') si no existe.

    Tolera slug bonito o normalizado (compara normalizado).  Prefiere el overlay
    HITL cuando ``prefer_hitl``.
    """
    prefijo = PREFIJOS_ESTADO.get(estado, estado.upper())
    target = _norm_slug(slug)
    dirs = []
    if prefer_hitl:
        dirs.append(json_predial_hitl_dir(estado, anio))
    dirs.append(json_predial_dir(estado, anio))
    for d in dirs:
        if not d.exists():
            continue
        exact = d / f"{prefijo}_PREDIAL_{anio}_{target}.json"
        if exact.exists():
            return exact
        for p in d.glob(f"*_PREDIAL_{anio}_*.json"):
            parsed = parse_fname(p)
            if parsed and _norm_slug(parsed[1]) == target:
                return p
    return Path("")


def prefer_hitl_path(canonical: Path) -> Path:
    """Dado un JSON canónico, devuelve su versión HITL-corregida si existe."""
    parsed = parse_fname(canonical)
    if not parsed:
        return canonical
    anio, _ = parsed
    estado = _estado_from_path(canonical)
    if not estado:
        return canonical
    cand = json_predial_hitl_dir(estado, anio) / canonical.name
    return cand if cand.exists() else canonical


def adjacent_json(path: Path | str, anio: int, offset: int,
                  *, prefer_hitl: bool = True) -> Path | None:
    """JSON del año ``anio+offset`` para el mismo municipio.  None si no existe."""
    p = Path(path)
    parsed = parse_fname(p)
    if not parsed:
        return None
    estado = _estado_from_path(p)
    if not estado:
        return None
    target_year = anio + offset
    target_name = p.name.replace(f"_{anio}_", f"_{target_year}_")
    dirs = []
    if prefer_hitl:
        dirs.append(json_predial_hitl_dir(estado, target_year))
    dirs.append(json_predial_dir(estado, target_year))
    for d in dirs:
        cand = d / target_name
        if cand.exists():
            return cand
    return None


def _estado_from_path(path: Path) -> str:
    """Extrae el estado_slug de una ruta data/{estado}/json_predial[_hitl]/{anio}/file."""
    parts = path.resolve().parts
    for i, part in enumerate(parts):
        if part in ("json_predial", "json_predial_hitl") and i >= 1:
            return parts[i - 1]
    return ""
