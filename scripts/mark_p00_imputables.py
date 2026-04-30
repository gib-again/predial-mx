"""Marca casos P-00 del HITL como `imputar` en `output/audit_pendiente.csv`.

P-00 (segunda pasada del HITL) = casos donde el LLM clasificó correctamente
como `otro_no_clasificado` porque el documento legítimamente no contiene
mecánica de cálculo del predial (remite a otra ley, sólo establece cuota
mínima, etc.). No requieren re-extracción; sí requieren que el imputador
del panel los marque como `decision_final=imputar` en lugar de tratarlos
como huecos a llenar manualmente.

Uso:
    python -m scripts.mark_p00_imputables

Idempotente: si la combinación (cvegeo, ejercicio) ya existe en el CSV con
el motivo `sin_predial_residual_confirmado_hitl`, se actualiza la nota; no
duplica filas.
"""
from __future__ import annotations

import csv
import sys
from datetime import date
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.extraction.bitacora_parser import parse_bitacora  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BITACORA = ROOT / "docs" / "HITL_BITACORA.md"
AUDIT_CSV = ROOT / "output" / "audit_pendiente.csv"

AUDIT_FIELDS = [
    "cvegeo", "estado", "municipio", "ejercicio", "motivo", "obs_validas_muni",
    "tipo_esquema_observado_prev", "tipo_esquema_observado_next",
    "anio_prev", "anio_next", "pdf_candidato", "ruta_pdf",
    "tipo_esquema_decidido", "numero_rangos_decidido", "monto_max_rango_decidido",
    "es_reforma_real", "decision_final", "comentarios_auditor", "auditor", "fecha",
]

ESTADO_NOM = {
    "coahuila": "Coahuila", "guanajuato": "Guanajuato",
    "tamaulipas": "Tamaulipas", "yucatan": "Yucatán",
    "queretaro": "Querétaro", "jalisco": "Jalisco",
}


def main() -> int:
    if not AUDIT_CSV.exists():
        print(f"[error] no existe {AUDIT_CSV}, abortando")
        return 1

    data = parse_bitacora(BITACORA)
    p00 = [c for c in data.cases if c.patron == "P-00" and c.veredicto == "correcto"]
    print(f"[mark_p00] casos P-00 correctos: {len(p00)}")

    # Cargar audit existente
    existing_rows: list[dict] = []
    with AUDIT_CSV.open(encoding="utf-8-sig", newline="") as f:
        existing_rows = list(csv.DictReader(f))
    print(f"[mark_p00] filas existentes en audit: {len(existing_rows)}")

    # Map (cvegeo, ejercicio) → row idx
    by_key = {(r["cvegeo"], r["ejercicio"]): i for i, r in enumerate(existing_rows)}

    today = date.today().isoformat()
    n_added = 0
    n_updated = 0
    for c in p00:
        cvegeo = str(c.cvegeo).zfill(5)
        anio = str(c.anio)
        key = (cvegeo, anio)
        nota_truncada = (c.notas or "")[:300]
        new_row = {
            "cvegeo": cvegeo,
            "estado": ESTADO_NOM.get(c.estado, c.estado.capitalize()),
            "municipio": c.slug.replace("_", " ").title(),
            "ejercicio": anio,
            "motivo": "sin_predial_residual_confirmado_hitl",
            "obs_validas_muni": "",
            "tipo_esquema_observado_prev": "",
            "tipo_esquema_observado_next": "",
            "anio_prev": "",
            "anio_next": "",
            "pdf_candidato": "",
            "ruta_pdf": "",
            "tipo_esquema_decidido": "otro_no_clasificado",
            "numero_rangos_decidido": "",
            "monto_max_rango_decidido": "",
            "es_reforma_real": "no",
            "decision_final": "imputar",
            "comentarios_auditor": f"P-00 HITL: {nota_truncada}",
            "auditor": "hitl_pass2",
            "fecha": today,
        }

        if key in by_key:
            idx = by_key[key]
            existing = existing_rows[idx]
            # Solo actualizar si la fila existente no tiene una decisión final
            if not (existing.get("decision_final") or "").strip():
                # Mantener motivo original como contexto si existía
                prev_motivo = existing.get("motivo", "")
                if prev_motivo and prev_motivo != new_row["motivo"]:
                    new_row["comentarios_auditor"] = (
                        f"{new_row['comentarios_auditor']} (override de motivo previo: {prev_motivo})"
                    )
                existing_rows[idx] = new_row
                n_updated += 1
            else:
                print(f"  [skip] {cvegeo}/{anio}: ya tiene decision_final='{existing['decision_final']}'")
        else:
            existing_rows.append(new_row)
            n_added += 1

    # Escribir CSV
    with AUDIT_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=AUDIT_FIELDS)
        w.writeheader()
        w.writerows(existing_rows)

    print(f"[mark_p00] añadidos: {n_added}  actualizados: {n_updated}")
    print(f"[mark_p00] CSV escrito en {AUDIT_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
