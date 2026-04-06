"""
Matcher unificado de nombres de municipio contra catálogo INEGI.

Reemplaza la lógica ad-hoc de matching en cada estado (substring, aliases
hardcoded, etc.) con un pipeline consistente:
    exact → alias → suffix-strip → token-subset → fuzzy (SequenceMatcher)

Uso:
    from src.core.muni_matcher import MuniMatcher

    matcher = MuniMatcher(cve_ent="11", aliases={"dolores_hidalgo": "dolores_..."})
    result = matcher.match("San José Iturbide")
    # MatchResult(slug="san_jose_de_iturbide", cve_mun="032", score=0.92, method="token_subset")
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

from src.core.text_utils import slugify


@dataclass
class MatchResult:
    """Resultado de matching de un nombre de municipio."""
    slug: str
    cve_mun: str = ""
    score: float = 0.0
    method: str = "none"

    @property
    def matched(self) -> bool:
        return self.method != "none"


# Sufijos comunes que pueden faltar o sobrar entre fuentes
_STRIP_SUFFIXES = ("_de", "_del", "_la", "_el", "_las", "_los")

# Ruta default al catálogo INEGI
_DEFAULT_CATALOG = Path("catalogs/municipios_inegi.csv")


class MuniMatcher:
    """
    Matcher de municipios contra catálogo INEGI.

    Pipeline de matching (en orden de prioridad):
      1. Exact: slug coincide exactamente
      2. Alias: slug está en el diccionario de aliases del estado
      3. Suffix-strip: quitar sufijos comunes (_de, _del, _la) y reintentar
      4. Token-subset: tokens(slug) ⊆ tokens(inegi) o viceversa
      5. Fuzzy: SequenceMatcher ratio ≥ threshold
    """

    def __init__(
        self,
        cve_ent: str,
        aliases: dict[str, str] | None = None,
        catalog_path: Path | None = None,
        fuzzy_threshold: float = 0.85,
    ):
        # Slugify alias keys to handle mixed-format configs
        self._aliases = {slugify(k): v for k, v in (aliases or {}).items()}
        self._threshold = fuzzy_threshold

        # Cargar catálogo INEGI
        self._catalog: dict[str, str] = {}  # slug → cve_mun
        self._names: dict[str, str] = {}    # slug → nom_mun (para reporting)

        cat_path = catalog_path or _DEFAULT_CATALOG
        if cat_path.exists():
            with cat_path.open(encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    if row.get("CVE_ENT") == cve_ent:
                        slug = slugify(row.get("NOM_MUN", ""))
                        cve = row.get("CVE_MUN", "")
                        if slug:
                            self._catalog[slug] = cve
                            self._names[slug] = row.get("NOM_MUN", "")

    @property
    def slugs(self) -> set[str]:
        """Conjunto de slugs canónicos INEGI."""
        return set(self._catalog.keys())

    def match(self, raw_name: str) -> MatchResult:
        """
        Intenta matchear un nombre de municipio crudo contra el catálogo INEGI.

        Args:
            raw_name: Nombre tal como aparece en el PDF/texto.

        Returns:
            MatchResult con slug canónico, cve_mun, score y método.
        """
        slug = slugify(raw_name)
        return self.match_slug(slug)

    def match_slug(self, slug: str) -> MatchResult:
        """
        Intenta matchear un slug ya normalizado contra el catálogo INEGI.

        Args:
            slug: Slug normalizado (output de slugify()).

        Returns:
            MatchResult con slug canónico, cve_mun, score y método.
        """
        if not slug:
            return MatchResult(slug=slug)

        # 1. Exact
        if slug in self._catalog:
            return MatchResult(slug=slug, cve_mun=self._catalog[slug],
                               score=1.0, method="exact")

        # 2. Alias
        if slug in self._aliases:
            canon = self._aliases[slug]
            if canon in self._catalog:
                return MatchResult(slug=canon, cve_mun=self._catalog[canon],
                                   score=1.0, method="alias")

        # 3. Suffix-strip: quitar sufijos comunes y reintentar
        for suffix in _STRIP_SUFFIXES:
            if slug.endswith(suffix):
                candidate = slug[: -len(suffix)]
                if candidate in self._catalog:
                    return MatchResult(slug=candidate, cve_mun=self._catalog[candidate],
                                       score=0.95, method="suffix_strip")

        # 4. Token-subset: uno es subconjunto del otro
        slug_tokens = set(slug.split("_"))
        best_subset = None
        best_subset_score = 0.0
        for inegi_slug in self._catalog:
            inegi_tokens = set(inegi_slug.split("_"))
            if slug_tokens <= inegi_tokens or inegi_tokens <= slug_tokens:
                score = SequenceMatcher(None, slug, inegi_slug).ratio()
                if score > best_subset_score:
                    best_subset_score = score
                    best_subset = inegi_slug

        if best_subset and best_subset_score >= 0.5:
            return MatchResult(slug=best_subset, cve_mun=self._catalog[best_subset],
                               score=best_subset_score, method="token_subset")

        # 5. Fuzzy: SequenceMatcher
        best_fuzzy = None
        best_fuzzy_score = 0.0
        for inegi_slug in self._catalog:
            score = SequenceMatcher(None, slug, inegi_slug).ratio()
            if score > best_fuzzy_score:
                best_fuzzy_score = score
                best_fuzzy = inegi_slug

        if best_fuzzy and best_fuzzy_score >= self._threshold:
            return MatchResult(slug=best_fuzzy, cve_mun=self._catalog[best_fuzzy],
                               score=best_fuzzy_score, method="fuzzy")

        # Sin match
        return MatchResult(slug=slug, score=best_fuzzy_score if best_fuzzy else 0.0)
