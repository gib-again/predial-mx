"""Parser de `docs/HITL_BITACORA.md` — extrae anotaciones HITL en formato dict.

Cada caso revisado tiene un bloque markdown con campos parseables:

    ### `estado/slug/anio` (cvegeo XXXXX)
    ...
    **Revisión**:

    - [x] revisado
    - veredicto: incorrecto
    - tipo_correcto: tarifa_millar
    - causa_raiz: api_error
    - patron: P-02
    - notas: ...
    - accion: ...

Maneja typos comunes (`segmetacion`, `api_eror`, `[ x]`, `[x ]`) y devuelve
estructuras tipadas reutilizables por `scripts/reprocess_municipios.py`.

Funciones principales:
  - parse_bitacora(path) -> BitacoraData
  - BitacoraData.cases       — lista de BitacoraCase (todas las entradas)
  - BitacoraData.reviewed()  — solo las marcadas [x]
  - BitacoraData.pending()   — solo las marcadas [ ]
  - BitacoraData.patrones    — dict {P-XX: PatronEntry}
  - BitacoraData.munis_for_patron(p) -> set[(estado, slug)]
  - BitacoraData.munis_pending() -> set[(estado, slug)]
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# ── Tipos ──

VEREDICTOS_VALIDOS = {"correcto", "incorrecto", "parcial", "invalido"}
TIPOS_VALIDOS = {
    "tarifa_millar", "progresivo", "tasa_unica", "cuota_fija_simple",
    "cuota_fija_escalonada", "mixto", "otro_no_clasificado", "n/a",
}
CAUSAS_VALIDAS = {
    "segmentacion", "prompt", "schema", "ocr", "documento_ambiguo",
    "api_error", "clasificacion_correcta", "otro",
}

# Mapeo de typos comunes → valor canónico
_TYPO_CAUSAS = {
    "segment": "segmentacion",
    "segmetacion": "segmentacion",
    "segmentación": "segmentacion",
    "api_eror": "api_error",
    "api error": "api_error",
}
_TYPO_VEREDICTOS = {
    "invalid": "invalido",
    "inválido": "invalido",
    "incorrect": "incorrecto",
    "incorrecto.": "incorrecto",
    "correct": "correcto",
}


@dataclass
class BitacoraCase:
    """Una entrada de revisión — corresponde a un (estado, slug, anio) específico."""

    estado: str
    slug: str
    anio: int
    cvegeo: str
    json_rel: str               # ruta al JSON v2 relativo a la raíz del repo
    tipo_actual: str            # tipo_esquema reportado por LLM (puede ser "FALTA_PREDIAL")
    revisado: bool
    veredicto: str = ""         # canonicalizado
    tipo_correcto: str = ""     # canonicalizado
    causa_raiz: str = ""        # canonicalizado
    patron: str = ""            # "P-XX" o ""
    notas: str = ""
    accion: str = ""
    raw_block: str = ""         # bloque markdown original (para debug)


@dataclass
class PatronEntry:
    """Una sección `### P-XX` del documento de patrones."""

    id: str                     # ej. "P-01"
    diagnostico: str = ""
    fix_propuesto: str = ""
    prioridad: str = ""
    estado: str = ""            # pending / in_progress / done
    casos: str = ""             # texto libre con la lista de casos


@dataclass
class BitacoraData:
    cases: list[BitacoraCase] = field(default_factory=list)
    patrones: dict[str, PatronEntry] = field(default_factory=dict)

    def reviewed(self) -> list[BitacoraCase]:
        return [c for c in self.cases if c.revisado]

    def pending(self) -> list[BitacoraCase]:
        return [c for c in self.cases if not c.revisado]

    def by_patron(self, patron_id: str) -> list[BitacoraCase]:
        pid = patron_id.upper().strip()
        return [c for c in self.cases if c.patron.upper() == pid]

    def munis_for_patron(self, patron_id: str) -> set[tuple[str, str]]:
        return {(c.estado, c.slug) for c in self.by_patron(patron_id)}

    def munis_pending(self) -> set[tuple[str, str]]:
        return {(c.estado, c.slug) for c in self.pending()}

    def munis_reviewed(self) -> set[tuple[str, str]]:
        return {(c.estado, c.slug) for c in self.reviewed()}

    def all_affected_munis(self) -> set[tuple[str, str]]:
        """Munis donde algún caso requiere acción (revisado con veredicto != correcto, o pendiente)."""
        out: set[tuple[str, str]] = set()
        for c in self.cases:
            if not c.revisado:
                out.add((c.estado, c.slug))
            elif c.veredicto and c.veredicto != "correcto":
                out.add((c.estado, c.slug))
        return out


# ── Parsing ──

_HEADER_CASE_RE = re.compile(
    r"`(?P<estado>[a-z_]+)/(?P<slug>[a-z0-9_]+)/(?P<anio>\d{4})`\s*"
    r"\(cvegeo\s+(?P<cvegeo>\d+)\)"
)
_JSON_LINE_RE = re.compile(r"\*\*JSON\*\*:\s*\[`(?P<rel>[^`]+)`\]")
_TIPO_LINE_RE = re.compile(r"\*\*tipo actual\*\*[^:]*:\s*`(?P<tipo>[^`]+)`")
_CHECKBOX_RE = re.compile(r"-\s*\[\s*(?P<mark>[xX]|\s*)\s*\]\s*revisado")

_FIELD_RES = {
    "veredicto": re.compile(r"-\s*veredicto:\s*(?P<v>[^\n]*)"),
    "tipo_correcto": re.compile(r"-\s*tipo_correcto:\s*(?P<v>[^\n]*)"),
    "causa_raiz": re.compile(r"-\s*causa_raiz:\s*(?P<v>[^\n]*)"),
    "patron": re.compile(r"-\s*patron:\s*(?P<v>[^\n]*)"),
    "notas": re.compile(r"-\s*notas:\s*(?P<v>[^\n]*)"),
    "accion": re.compile(r"-\s*accion:\s*(?P<v>[^\n]*)"),
}

_PATRON_ID_RE = re.compile(r"^###\s*(P-\d{2})\b", re.MULTILINE)
_PATRON_FIELD_RES = {
    "diagnostico": re.compile(r"-\s*\*\*diagnostico\*\*:\s*(?P<v>[^\n]*)"),
    "fix_propuesto": re.compile(r"-\s*\*\*fix_propuesto\*\*:\s*(?P<v>[^\n]*)"),
    "prioridad": re.compile(r"-\s*\*\*prioridad\*\*:\s*(?P<v>[^\n]*)"),
    "estado": re.compile(r"-\s*\*\*estado\*\*:\s*(?P<v>[^\n]*)"),
    "casos": re.compile(r"-\s*\*\*casos\*\*:\s*(?P<v>[^\n]*)"),
}


def _norm_veredicto(s: str) -> str:
    s = s.strip().lower().rstrip(".")
    return _TYPO_VEREDICTOS.get(s, s) if s else ""


def _norm_causa(s: str) -> str:
    s = s.strip().lower()
    if not s:
        return ""
    # split por coma — quedarse con la primera (la más relevante)
    first = s.split(",")[0].strip()
    return _TYPO_CAUSAS.get(first, first)


def _norm_patron(s: str) -> str:
    m = re.search(r"P-\d{2}", s, re.IGNORECASE)
    return m.group(0).upper() if m else ""


def _extract_field(block: str, field_name: str) -> str:
    pat = _FIELD_RES[field_name]
    m = pat.search(block)
    if not m:
        return ""
    return m.group("v").strip()


def _parse_case_block(block: str) -> BitacoraCase | None:
    """Parsea un bloque markdown de un caso. Devuelve None si no es un caso válido."""
    h = _HEADER_CASE_RE.search(block)
    if not h:
        return None

    json_m = _JSON_LINE_RE.search(block)
    tipo_m = _TIPO_LINE_RE.search(block)
    chk_m = _CHECKBOX_RE.search(block)

    revisado = bool(chk_m and chk_m.group("mark").strip().lower() == "x")

    return BitacoraCase(
        estado=h.group("estado"),
        slug=h.group("slug"),
        anio=int(h.group("anio")),
        cvegeo=h.group("cvegeo"),
        json_rel=json_m.group("rel") if json_m else "",
        tipo_actual=tipo_m.group("tipo") if tipo_m else "",
        revisado=revisado,
        veredicto=_norm_veredicto(_extract_field(block, "veredicto")),
        tipo_correcto=_extract_field(block, "tipo_correcto").lower(),
        causa_raiz=_norm_causa(_extract_field(block, "causa_raiz")),
        patron=_norm_patron(_extract_field(block, "patron")),
        notas=_extract_field(block, "notas"),
        accion=_extract_field(block, "accion"),
        raw_block=block,
    )


def _parse_patrones(content: str) -> dict[str, PatronEntry]:
    """Extrae las entradas `### P-XX` del documento."""
    patrones: dict[str, PatronEntry] = {}

    # Localizar la sección "## Patrones detectados"
    # Tomar todo entre ese encabezado y el siguiente "## " a nivel raíz.
    sec_m = re.search(
        r"##\s+Patrones detectados\s*\n(.*?)(?=\n##\s+[^#])",
        content, re.DOTALL,
    )
    if not sec_m:
        return patrones
    section = sec_m.group(1)

    # Cada patrón empieza en `### P-XX` y termina antes del siguiente `### P-` o `---`.
    parts = re.split(r"\n###\s+", section)
    for p in parts[1:]:
        # p empieza con "P-XX..."
        idm = re.match(r"(P-\d{2})", p)
        if not idm:
            continue
        pid = idm.group(1)
        entry = PatronEntry(id=pid)
        for field_name, pat in _PATRON_FIELD_RES.items():
            m = pat.search(p)
            if m:
                setattr(entry, field_name, m.group("v").strip())
        patrones[pid] = entry
    return patrones


def parse_bitacora(path: str | Path) -> BitacoraData:
    """Parsea `docs/HITL_BITACORA.md` (o un path equivalente) en estructura tipada.

    Tolerante a:
      - Casillas `[ x]`, `[x ]`, `[X]`
      - Typos en causa_raiz / veredicto comunes
      - Bloques que sólo tienen header (no llenados)
      - Patrones referenciados sin entrada formal (los retorna sin campos)
    """
    path = Path(path)
    content = path.read_text(encoding="utf-8")

    data = BitacoraData()
    data.patrones = _parse_patrones(content)

    # Cada caso empieza con `\n### \`estado/slug/anio\``. Splitear en `\n### ` y
    # quedarse con los chunks que matchean el header de caso (no patrones, no TOC).
    chunks = re.split(r"\n###\s+", content)
    for chunk in chunks[1:]:
        # Reconstruir: lo que viene después de `### ` es el header line + cuerpo
        if not chunk.startswith("`"):
            # No es un caso (es patrón, TOC, etc.)
            continue
        case = _parse_case_block(chunk)
        if case is not None:
            data.cases.append(case)

    return data


# ── Entry point para inspección rápida ──

def _summary(data: BitacoraData) -> str:
    from collections import Counter
    n_total = len(data.cases)
    n_rev = sum(1 for c in data.cases if c.revisado)
    n_pend = n_total - n_rev
    veredicto_counts = Counter(c.veredicto for c in data.reviewed() if c.veredicto)
    causa_counts = Counter(c.causa_raiz for c in data.reviewed() if c.causa_raiz)
    patron_counts = Counter(c.patron for c in data.reviewed() if c.patron)
    munis_aff = data.all_affected_munis()

    lines = [
        f"casos:       {n_total}",
        f"revisados:   {n_rev}",
        f"pendientes:  {n_pend}",
        f"munis afectados (revisados ≠ correcto + pendientes): {len(munis_aff)}",
        f"patrones definidos: {len(data.patrones)}",
        "",
        "veredictos:",
    ]
    for k, v in veredicto_counts.most_common():
        lines.append(f"  {k:15s} {v}")
    lines.append("")
    lines.append("causas:")
    for k, v in causa_counts.most_common():
        lines.append(f"  {k:25s} {v}")
    lines.append("")
    lines.append("patrones (revisados):")
    for k, v in patron_counts.most_common():
        lines.append(f"  {k:8s} {v}")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys
    p = sys.argv[1] if len(sys.argv) > 1 else "docs/HITL_BITACORA.md"
    data = parse_bitacora(p)
    print(_summary(data))
