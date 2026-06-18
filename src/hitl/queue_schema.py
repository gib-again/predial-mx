"""Esquema de la cola HITL unificada y helpers CSV.

La cola vive en ``output/hitl/cola_unificada.csv``.  Cada fila es un
caso por municipio-año consolidado; los detectores que disparan se
acumulan en ``detector`` (separados por coma) y las señales en ``senal``
(separadas por " | ").

El ``id`` es un hash determinista ``sha1(estado|muni|anio)`` que permite
re-runs idempotentes.
"""

from __future__ import annotations

import csv
import hashlib
from collections import defaultdict
from dataclasses import asdict, dataclass, fields
from pathlib import Path

QUEUE_DIR = Path("output/hitl")
QUEUE_CSV = QUEUE_DIR / "cola_unificada.csv"

SEVERIDADES = ("SEV1-H", "SEV1", "SEV2", "SEV3")


@dataclass
class QueueRow:
    id: str
    severidad: str
    detector: str
    estado: str
    estado_slug: str
    municipio: str
    municipio_slug: str
    cvegeo: str
    anio: int
    senal: str
    json_path: str
    segment_row: int
    decision: str = ""
    notas: str = ""
    timestamp: str = ""


QUEUE_FIELDS = [f.name for f in fields(QueueRow)]


def make_id(estado_slug: str, municipio_slug: str, anio: int, detector: str) -> str:
    raw = f"{estado_slug}|{municipio_slug}|{anio}|{detector}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def make_consolidated_id(estado_slug: str, municipio_slug: str, anio: int) -> str:
    raw = f"{estado_slug}|{municipio_slug}|{anio}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def consolidate_rows(rows: list[QueueRow]) -> list[QueueRow]:
    """Group rows by (estado_slug, municipio_slug, anio) into one row each.

    - ``detector`` becomes comma-separated list of unique detectors
    - ``senal`` becomes pipe-separated list of detector-prefixed signals
    - ``severidad`` = max across all grouped rows
    - ``json_path`` and ``segment_row`` taken from first row
    """
    groups: dict[tuple, list[QueueRow]] = defaultdict(list)
    for r in rows:
        groups[(r.estado_slug, r.municipio_slug, r.anio)].append(r)

    sev_rank = {s: i for i, s in enumerate(SEVERIDADES)}

    out: list[QueueRow] = []
    for (est, muni, anio), group in groups.items():
        group.sort(key=lambda r: sev_rank.get(r.severidad, 99))
        detectors = []
        signals = []
        seen_det: set[str] = set()
        for r in group:
            if r.detector not in seen_det:
                detectors.append(r.detector)
                seen_det.add(r.detector)
            signals.append(f"{r.detector}: {r.senal}")
        first = group[0]
        out.append(QueueRow(
            id=make_consolidated_id(est, muni, anio),
            severidad=first.severidad,
            detector=",".join(detectors),
            estado=first.estado,
            estado_slug=est,
            municipio=first.municipio,
            municipio_slug=muni,
            cvegeo=first.cvegeo,
            anio=anio,
            senal=" | ".join(signals),
            json_path=first.json_path,
            segment_row=first.segment_row,
        ))
    return out


def write_queue(rows: list[QueueRow], path: Path = QUEUE_CSV) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=QUEUE_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))
    return path


def read_queue(path: Path = QUEUE_CSV) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def merge_queues(
    new_rows: list[QueueRow],
    existing_path: Path = QUEUE_CSV,
) -> list[QueueRow]:
    """Merge new detections with existing queue, preserving human decisions.

    If an existing row has a non-empty ``decision``, it is kept as-is.
    New rows with the same ``id`` as a decided row are dropped.
    New rows whose ``id`` doesn't exist yet are appended.
    Existing rows without decisions are replaced by the new detection
    (signal text may have changed).
    """
    existing = read_queue(existing_path)
    decided: dict[str, dict] = {}
    for row in existing:
        if row.get("decision", "").strip():
            decided[row["id"]] = row

    merged: dict[str, QueueRow | dict] = {}
    for row in new_rows:
        if row.id in decided:
            merged[row.id] = decided[row.id]
        else:
            merged[row.id] = row

    for row_id, row in decided.items():
        if row_id not in merged:
            merged[row_id] = row

    result: list[QueueRow] = []
    for item in merged.values():
        if isinstance(item, QueueRow):
            result.append(item)
        else:
            result.append(QueueRow(**{
                k: item.get(k, "")
                for k in QUEUE_FIELDS
            }))
    result.sort(key=lambda r: (
        SEVERIDADES.index(r.severidad) if r.severidad in SEVERIDADES else 99,
        r.estado_slug,
        r.municipio_slug,
        r.anio,
    ))
    return result
