"""
Ruta C — Wayback Machine fallback para PDFs irrecuperables del PO SLP.

Para IDs registrados como `error:*:all_endpoints` en el índice de descargas,
consulta la API de Internet Archive Wayback Machine. Si hay un snapshot
preservado del PDF, lo descarga.

Uso típico:
    from src.estados import get_adapter
    from src.estados.sanluispotosi.download_wayback import run_download_wayback
    run_download_wayback(get_adapter("sanluispotosi"), target_years=[2010, 2011])

Limitaciones conocidas:
  - Wayback rate-limita agresivamente (vimos 503 Service Unavailable en
    pruebas recientes). Backoff conservador entre requests.
  - La cobertura para PO SLP histórico es probablemente baja: la availability
    API devolvió `archived_snapshots: {}` para timestamps cercanos a Dic-2020.
  - Best effort: cualquier PDF rescatado es ganancia.
"""

from __future__ import annotations

import csv
import time
from pathlib import Path

import requests

from src.estados.sanluispotosi import config
from src.estados.sanluispotosi.download import (
    _INDEX_FIELDS,
    _looks_like_pdf,
    _read_existing_index,
)


def _query_availability(
    session: requests.Session,
    target_url: str,
    timestamp: str,
) -> str | None:
    """
    Consulta Wayback availability API y retorna URL del snapshot más cercano,
    o None si no hay archivos.
    """
    try:
        r = session.get(
            config.WAYBACK_AVAILABILITY_API,
            params={"url": target_url, "timestamp": timestamp},
            timeout=60,
        )
        if not r.ok:
            return None
        data = r.json() or {}
        snapshots = (data.get("archived_snapshots") or {}).get("closest") or {}
        if not snapshots.get("available"):
            return None
        return snapshots.get("url")
    except Exception:
        return None


def _download_from_wayback(
    session: requests.Session,
    snapshot_url: str,
    dest_path: Path,
) -> str:
    """Descarga el PDF del snapshot. Retorna 'ok' o 'error:...'."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Usar `if_=` (id_=identity) para evitar el wrapper HTML del Wayback player
        # y obtener el PDF crudo. Patrón estándar de Wayback.
        if "id_/" not in snapshot_url and "/web/" in snapshot_url:
            snapshot_url = snapshot_url.replace("/web/", "/web/", 1)
            # Insertar id_ después del timestamp
            parts = snapshot_url.split("/web/", 1)
            if len(parts) == 2:
                rest = parts[1]
                # rest = "{timestamp}/{original_url}" — insertar "id_" tras timestamp
                slash = rest.find("/")
                if slash > 0:
                    snapshot_url = f"{parts[0]}/web/{rest[:slash]}id_{rest[slash:]}"

        r = session.get(snapshot_url, timeout=120, stream=True)
        if not r.ok:
            return f"error:wayback_get:{r.status_code}"
        with dest_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)
        if not _looks_like_pdf(dest_path):
            dest_path.unlink(missing_ok=True)
            return "error:wayback_not_pdf"
        return "ok"
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        return f"error:wayback_{type(e).__name__}"


def run_download_wayback(
    adapter,
    target_years: list[int] | None = None,
    max_attempts_per_id: int = 1,
) -> Path:
    """
    Para cada ID con error en el índice, intenta rescatarlo via Wayback.

    Args:
        adapter: Adaptador SLP.
        target_years: Lista de años a procesar (None = todos los con error).
        max_attempts_per_id: Reintentos por ID (Wayback rate-limita; mantener 1).
    """
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    index_csv = meta_dir / "ley_ingresos_index.csv"

    print("═══ Ruta C: Wayback Machine (best effort) ═══")
    if not index_csv.exists():
        print("  No existe índice previo. Ejecuta `download` primero.")
        return index_csv

    rows = _read_existing_index(index_csv)
    candidatos = [
        r for r in rows
        if r.get("status", "").startswith("error")
        and r.get("id_publicacion", "")
        and r.get("slug", "")
    ]
    if target_years:
        targets = {str(y) for y in target_years}
        candidatos = [r for r in candidatos if r.get("ejercicio", "") in targets]

    if not candidatos:
        print("  No hay candidatos con error en el índice.")
        return index_csv

    print(f"  Candidatos para rescate via Wayback: {len(candidatos)}")
    if target_years:
        print(f"  Filtro de años: {sorted(target_years)}")
    print(f"  Throttle: {config.WAYBACK_THROTTLE_SECONDS}s entre requests")

    session = requests.Session()
    session.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept": "*/*",
    })

    new_rows: list[dict] = []
    n_ok = 0
    n_no_snapshot = 0
    n_err = 0

    for i, row in enumerate(candidatos, 1):
        id_pub = row.get("id_publicacion", "")
        ej = row.get("ejercicio", "")
        slug = row.get("slug", "")
        target_url = config.API_DOC.format(id=id_pub)
        # Timestamp para "más cercano a la publicación":
        # ejercicio fiscal N → publicado dic-(N-1)
        try:
            ts_year = int(ej) - 1
        except (ValueError, TypeError):
            ts_year = 2010
        timestamp = f"{ts_year}1230"

        dest_path = pdf_raw_dir / str(ej) / f"{config.PREFIJO}_RAW_{ej}_{slug}.pdf"

        if dest_path.exists() and dest_path.stat().st_size > 1024:
            # Ya descargado por otra ruta; skip.
            continue

        if (i - 1) % 10 == 0:
            print(f"  [{i}/{len(candidatos)}] {ej}/{slug} (id={id_pub}) ...")

        snapshot_url = _query_availability(session, target_url, timestamp)
        time.sleep(config.WAYBACK_THROTTLE_SECONDS)

        if not snapshot_url:
            n_no_snapshot += 1
            new_rows.append({
                **row,
                "source": "wayback",
                "status": "wayback:no_snapshot",
                "pdf_url": "",
                "file_local": str(dest_path),
            })
            continue

        status = _download_from_wayback(session, snapshot_url, dest_path)
        time.sleep(config.WAYBACK_THROTTLE_SECONDS)

        if status == "ok":
            n_ok += 1
            print(f"    [OK] Rescatado de Wayback: {dest_path.name}")
        else:
            n_err += 1

        new_rows.append({
            **row,
            "source": "wayback",
            "status": status,
            "pdf_url": snapshot_url,
            "file_local": str(dest_path),
        })

    # Mergear con índice existente (preservar filas previas que no procesamos).
    seen = {(r.get("id_publicacion", ""), r.get("source", "")) for r in new_rows}
    merged = list(new_rows)
    for r in rows:
        key = (r.get("id_publicacion", ""), r.get("source", "po_api"))
        if key not in seen:
            r.setdefault("source", "po_api")
            merged.append(r)

    tmp = index_csv.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(merged)
    tmp.replace(index_csv)

    print("\n  ── Resumen Ruta C (Wayback) ──")
    print(f"  Candidatos:       {len(candidatos)}")
    print(f"  Rescatados (OK):  {n_ok}")
    print(f"  Sin snapshot:     {n_no_snapshot}")
    print(f"  Errores:          {n_err}")
    print(f"  Índice: {index_csv}")
    return index_csv
