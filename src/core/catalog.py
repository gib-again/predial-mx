"""Catálogo INEGI — resolución canónica de identidad municipal.

Única fuente de verdad para nombre / slug / cvegeo de un municipio.  El
**display siempre** sale de aquí (``cvegeo_to_nombre``); el pipeline nunca
debe usar texto extraído (OCR, headers de ley) como identidad ni como nombre.

CVEGEO = CVE_ENT (2 dígitos) + CVE_MUN (3 dígitos) = 5 dígitos.

Uso:
    from src.core import catalog

    catalog.cvegeo_to_nombre("11025")          # -> "Moroleón"
    catalog.resolve_cvegeo("guanajuato", "MOROLEON")  # -> "11025"
    catalog.build_cvegeo("11", "025")          # -> "11025"
"""

from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

from src.core.constants import CVE_ENT_ESTADO
from src.core.muni_matcher import MatchResult, MuniMatcher
from src.core.text_utils import slugify

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "catalogs" / "municipios_inegi.csv"

# Score mínimo para aceptar un match como identidad confiable.  Por debajo de
# esto el caller debe marcar ``status=identidad_no_resuelta`` en vez de
# propagar un cvegeo dudoso.
DEFAULT_MIN_SCORE = 0.85


@lru_cache(maxsize=1)
def _by_cvegeo() -> dict[str, dict]:
    """cvegeo(5) -> {nom_mun, slug, cve_ent, cve_mun, nom_ent}."""
    out: dict[str, dict] = {}
    if not CATALOG.exists():
        return out
    with CATALOG.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            cvegeo = (row.get("CVEGEO") or "").zfill(5)
            if not cvegeo or cvegeo == "00000":
                continue
            nom = row.get("NOM_MUN", "")
            out[cvegeo] = {
                "nom_mun": nom,
                "slug": slugify(nom),
                "cve_ent": row.get("CVE_ENT", ""),
                "cve_mun": row.get("CVE_MUN", ""),
                "nom_ent": row.get("NOM_ENT", ""),
            }
    return out


def build_cvegeo(cve_ent: str, cve_mun: str) -> str:
    """Compone CVEGEO de 5 dígitos a partir de entidad + municipio."""
    return f"{str(cve_ent).zfill(2)}{str(cve_mun).zfill(3)}"


def cvegeo_to_nombre(cvegeo: str) -> str:
    """Nombre INEGI (``NOM_MUN``) para display.  '' si no se encuentra."""
    rec = _by_cvegeo().get(str(cvegeo).zfill(5))
    return rec["nom_mun"] if rec else ""


def cvegeo_to_slug(cvegeo: str) -> str:
    """Slug canónico INEGI.  '' si no se encuentra."""
    rec = _by_cvegeo().get(str(cvegeo).zfill(5))
    return rec["slug"] if rec else ""


def resolve_cvegeo_pair(cvegeo: str) -> tuple[str, str]:
    """(slug, NOM_MUN) a partir del CVEGEO.  Lanza KeyError si no existe.

    Compat con la antigua ``llm_utils._resolve_cvegeo``.
    """
    rec = _by_cvegeo().get(str(cvegeo).zfill(5))
    if rec is None:
        raise KeyError(f"CVEGEO {cvegeo} no encontrado en {CATALOG}")
    return rec["slug"], rec["nom_mun"]


_matcher_cache: dict[str, MuniMatcher] = {}


def _matcher_for(cve_ent: str, aliases: dict[str, str] | None) -> MuniMatcher:
    key = cve_ent + "|" + ",".join(f"{k}={v}" for k, v in sorted((aliases or {}).items()))
    m = _matcher_cache.get(key)
    if m is None:
        m = MuniMatcher(cve_ent=cve_ent, aliases=aliases)
        _matcher_cache[key] = m
    return m


def resolve_cvegeo(
    estado_slug: str,
    raw_or_slug: str,
    aliases: dict[str, str] | None = None,
    min_score: float = DEFAULT_MIN_SCORE,
) -> str:
    """Resuelve un nombre/slug crudo a CVEGEO de 5 dígitos vía ``MuniMatcher``.

    Devuelve '' si no hay match confiable (score < ``min_score`` o sin
    cve_mun); el caller debe entonces marcar ``identidad_no_resuelta`` en vez
    de adivinar.

    ``aliases`` = diccionario por-estado (``config.ALIASES``) para mapear
    NOM_CAB → slug de NOM_MUN donde difieren.
    """
    res = match_municipio(estado_slug, raw_or_slug, aliases)
    cve_ent = CVE_ENT_ESTADO.get(estado_slug, "")
    if cve_ent and res.matched and res.score >= min_score and res.cve_mun:
        return build_cvegeo(cve_ent, res.cve_mun)
    return ""


def match_municipio(
    estado_slug: str,
    raw_or_slug: str,
    aliases: dict[str, str] | None = None,
) -> MatchResult:
    """Devuelve el ``MatchResult`` crudo (slug, cve_mun, score, method).

    Útil cuando el caller necesita inspeccionar score/método para decidir el
    ``status``.  Para sólo obtener el cvegeo usar ``resolve_cvegeo``.
    """
    cve_ent = CVE_ENT_ESTADO.get(estado_slug, "")
    if not cve_ent:
        return MatchResult(slug=slugify(raw_or_slug))
    return _matcher_for(cve_ent, aliases).match(raw_or_slug)
