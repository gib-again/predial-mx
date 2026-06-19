"""Capa append-only de decisiones HITL.

La cola ``cola_unificada.csv`` es una **vista derivada idempotente** que se
reconstruye en cada corrida de detectores.  Las decisiones del revisor NO viven
en la cola (eso causaba orphans, Causa B); viven aquí, en un log append-only que
sobrevive a cualquier rebuild y se une a la cola por la llave del caso.

Llave de caso (``id``): el id consolidado de la cola = sha1(estado|muni_slug|anio).
Es estable porque ``municipio_slug`` ahora es canónico (derivado de cvegeo).

Cada decisión es una fila nueva (append-only); la más reciente por ``id`` gana.
Esto da trazabilidad completa (quién decidió qué y cuándo).
"""

from __future__ import annotations

import csv
import getpass
import os
from datetime import datetime, timezone
from pathlib import Path

HITL_DIR = Path("output/hitl")
DECISIONES_CSV = HITL_DIR / "hitl_decisiones.csv"
EDICIONES_CSV = HITL_DIR / "hitl_ediciones.csv"

# Whitelist de campos editables en "cambio menor" (§6a).  Cambios fuera de esto
# → la decisión correcta es re-extraer, no "cambio menor".
EDIT_WHITELIST = ("minimo_predial", "unidad", "periodicidad")

EDICION_FIELDS = [
    "timestamp", "id", "cvegeo", "estado_slug", "anio",
    "campo", "valor_viejo", "valor_nuevo", "revisor",
]

DECISION_FIELDS = [
    "timestamp",
    "id",
    "cvegeo",
    "estado_slug",
    "municipio_slug",
    "anio",
    "decision",
    "sub_opcion",   # "" | fiel | cambio_menor (Fase 6a)
    "revisor",
    "notas",
]


def default_revisor() -> str:
    return os.environ.get("HITL_REVISOR") or getpass.getuser() or "anon"


def append_decision(
    *,
    id: str,
    decision: str,
    cvegeo: str = "",
    estado_slug: str = "",
    municipio_slug: str = "",
    anio: int | str = "",
    sub_opcion: str = "",
    revisor: str | None = None,
    notas: str = "",
    path: Path = DECISIONES_CSV,
) -> None:
    """Agrega una decisión al log append-only."""
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "id": id,
        "cvegeo": cvegeo,
        "estado_slug": estado_slug,
        "municipio_slug": municipio_slug,
        "anio": anio,
        "decision": decision,
        "sub_opcion": sub_opcion,
        "revisor": revisor if revisor is not None else default_revisor(),
        "notas": notas,
    }
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=DECISION_FIELDS, extrasaction="ignore")
        if is_new:
            w.writeheader()
        w.writerow(row)


def append_edicion(
    *,
    id: str,
    cvegeo: str,
    estado_slug: str,
    anio: int | str,
    campo: str,
    valor_viejo,
    valor_nuevo,
    revisor: str | None = None,
    path: Path = EDICIONES_CSV,
) -> None:
    """Registra una edición de whitelist con before/after (§6a)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=EDICION_FIELDS, extrasaction="ignore")
        if is_new:
            w.writeheader()
        w.writerow({
            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "id": id,
            "cvegeo": cvegeo,
            "estado_slug": estado_slug,
            "anio": anio,
            "campo": campo,
            "valor_viejo": "" if valor_viejo is None else valor_viejo,
            "valor_nuevo": "" if valor_nuevo is None else valor_nuevo,
            "revisor": revisor if revisor is not None else default_revisor(),
        })


def procedencia_hitl(decision: str, sub_opcion: str = "") -> str:
    """Taxonomía de procedencia post-HITL para auditoría/citas (§6a)."""
    sub = (sub_opcion or "").strip().lower()
    mapping = {
        "confirmar_ok": "confirmado_cambio_menor" if sub == "cambio_menor" else "confirmado_fiel",
        "propagar_previo": "propagado_previo",
        "corregir_previo": "corregido_previo",
        "reextraer": "reextraido",
        "re_segmentar": "resegmentado",
        "ignorar": "ignorado",
    }
    return mapping.get(decision, decision)


def load_all(path: Path = DECISIONES_CSV) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def load_latest(path: Path = DECISIONES_CSV) -> dict[str, dict]:
    """``id`` -> última decisión (la fila más reciente gana)."""
    latest: dict[str, dict] = {}
    for row in load_all(path):
        rid = row.get("id", "")
        if not rid:
            continue
        prev = latest.get(rid)
        if prev is None or row.get("timestamp", "") >= prev.get("timestamp", ""):
            latest[rid] = row
    return latest
