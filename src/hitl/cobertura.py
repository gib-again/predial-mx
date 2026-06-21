"""Capa de cobertura: placeholders para muni-años sin extracción (HITL exhaustivo).

Modelo *completeness-first*: para cada celda `(cvegeo, año)` de la rejilla
`municipios INEGI × años del panel` que NO tenga extracción real, se genera un
JSON placeholder (`predial=null`) que aparece en HITL como hueco a resolver.  El
auditor:
  - localiza PDF + span de páginas → `re_segmentar` (re-extrae), o
  - marca `sin_ley` (ausencia legítima de ley de ingresos ese año).

Subsume `identidad_no_resuelta`: si existe un focus huérfano (segmento hallado
pero sin cvegeo) cuyo mejor match difuso apunta a la celda, se adjunta como
**pista** en el placeholder (ruta + texto crudo).

Excluidos: Oaxaca (volumen, 570 munis) y estados hardcoded (predial uniforme
estatal, no se segmenta → no aplica "localiza el span").
"""

from __future__ import annotations

import json
from pathlib import Path

from src.core.catalog import (
    build_cvegeo,
    cvegeo_to_nombre,
    cvegeo_to_slug,
    cvegeos_de_estado,
)
from src.core.constants import (
    CVE_ENT_ESTADO,
    EJERCICIO_FIN,
    EJERCICIO_INI,
    PREFIJOS_ESTADO,
)
from src.core.corpus import resolve_json
from src.core.muni_matcher import MuniMatcher
from src.core.segment_schema import STATUS_IDENTIDAD, read_segment_csv

# Estados fuera de la cobertura HITL.
EXCLUIDOS = {"oaxaca", "chihuahua", "colima", "edomex", "sinaloa", "tabasco"}

PLACEHOLDER_MODELO = "placeholder_cobertura"
PLACEHOLDER_RAZON = "sin_extraccion"
# Score mínimo para adjuntar un focus huérfano como pista de una celda.
HINT_MIN_SCORE = 0.55


def estados_cobertura() -> list[str]:
    """Estados Grupo A elegibles para la rejilla de cobertura."""
    return [e for e in PREFIJOS_ESTADO if e not in EXCLUIDOS]


def anios_panel() -> range:
    return range(EJERCICIO_INI, EJERCICIO_FIN + 1)


def _orphan_hints(estado: str, aliases: dict | None) -> dict[tuple[str, str], dict]:
    """{(cvegeo, anio): hint} desde filas identidad_no_resuelta del segment.

    El cvegeo se infiere por match difuso del texto crudo (umbral bajo); la pista
    no afirma identidad, solo sugiere "aquí hay un focus que podría ser de esta
    celda" para que el auditor lo confirme.
    """
    cve_ent = CVE_ENT_ESTADO.get(estado, "")
    seg = read_segment_csv(Path("data") / estado / "meta" / "segment.csv")
    # Matcher de umbral bajo: el texto OCR-mutilado (XICRÚ, DCAMPO…) cae bajo el
    # 0.85 por defecto; aquí solo es una PISTA a confirmar por el auditor.
    matcher = MuniMatcher(cve_ent=cve_ent, aliases=aliases, fuzzy_threshold=HINT_MIN_SCORE)
    out: dict[tuple[str, str], dict] = {}
    for r in seg:
        if (r.get("status") or "") != STATUS_IDENTIDAD:
            continue
        raw = (r.get("municipio_raw") or r.get("municipio_slug") or "").strip()
        m = matcher.match(raw)
        if not m.cve_mun or m.score < HINT_MIN_SCORE:
            continue
        cvegeo = build_cvegeo(cve_ent, m.cve_mun)
        anio = str(r.get("anio") or "").strip()
        key = (cvegeo, anio)
        # Conservar la pista de mayor score si hay varias para la misma celda.
        prev = out.get(key)
        if prev is None or m.score > prev["score"]:
            out[key] = {
                "focus_txt": r.get("txt_file", ""),
                "source_pdf": r.get("source_pdf", ""),
                "texto_crudo": " ".join(raw.split())[:160],
                "score": round(m.score, 2),
            }
    return out


def _placeholder_payload(estado: str, cvegeo: str, anio: int, hint: dict | None) -> dict:
    payload = {
        "predial": None,
        "_meta": {"modelo": PLACEHOLDER_MODELO, "razon": PLACEHOLDER_RAZON},
        "_meta_v3": {
            "requiere_revision": True,
            "cvegeo": cvegeo,
            "estado": estado,
            "anio": anio,
            "razon": PLACEHOLDER_RAZON,
        },
        "_meta_cobertura": {
            "placeholder": True,
            "hint_focus_huerfano": hint,  # None si no hay evidencia
        },
    }
    return payload


def generar_placeholders(estado: str, *, dry_run: bool = False,
                         aliases: dict | None = None) -> dict:
    """Escribe placeholders para las celdas sin extracción real del estado.

    Idempotente: omite celdas que ya tienen JSON (real o placeholder).  Devuelve
    contadores.
    """
    if estado in EXCLUIDOS:
        return {"estado": estado, "excluido": True}
    prefijo = PREFIJOS_ESTADO.get(estado, estado.upper())
    hints = _orphan_hints(estado, aliases)
    anios = list(anios_panel())
    creados = saltados = con_hint = 0
    for cvegeo in cvegeos_de_estado(estado):
        slug = cvegeo_to_slug(cvegeo)
        for anio in anios:
            if resolve_json(estado, anio, slug) is not None:
                saltados += 1
                continue
            hint = hints.get((cvegeo, str(anio)))
            creados += 1
            con_hint += int(hint is not None)
            if not dry_run:
                out_dir = Path("data") / estado / "json_predial" / str(anio)
                out_dir.mkdir(parents=True, exist_ok=True)
                fname = f"{prefijo}_PREDIAL_{anio}_{slug}.json"
                payload = _placeholder_payload(estado, cvegeo, anio, hint)
                (out_dir / fname).write_text(
                    json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"estado": estado, "creados": creados, "saltados": saltados,
            "con_hint": con_hint, "munis": len(cvegeos_de_estado(estado)),
            "nombre_ejemplo": cvegeo_to_nombre(cvegeos_de_estado(estado)[0])
            if cvegeos_de_estado(estado) else ""}
