"""Aplica decisiones HITL desde `cambios_interanuales.csv`.

Lee el CSV producido por `detectar_cambios_interanuales.py` con la columna
`decision` llena por un humano. Cada fila puede tener una de cuatro decisiones:

  - `aceptar_nuevo`              el cambio detectado es real (reforma legal o
                                 ajuste documentado). No-op, se registra.
  - `propagar_previo`            el JSON nuevo es incorrecto; copia el del año
                                 anterior con `_meta.modelo = imputed_human_propagation`
                                 a `predial-mx-v2-hitl/<estado>/`.
  - `reextraer`                  el JSON nuevo es incorrecto; agrega el archivo
                                 a `cola_reextraccion.csv` con un hint para
                                 reorientar la segmentación / extracción LLM.
  - `cambio_real_documentado`    como `aceptar_nuevo` pero con justificación
                                 documental en `notas` (reforma específica).

Salidas en `output/anexos/`:
  - hitl_bitacora.csv       append-only: cada decisión aplicada con timestamp
  - cola_reextraccion.csv   archivos pendientes de re-extracción

Y archivos JSON propagados en `predial-mx-v2-hitl/<estado>/`.

Diseño:
  - NUNCA mutamos `predial-mx-v2/` original. Los JSONs propagados van a una
    carpeta paralela `predial-mx-v2-hitl/` que tiene prioridad downstream.
  - La bitácora es append-only: cada corrida añade decisiones nuevas y mantiene
    historial completo para auditoría de la tesis.
  - Decisiones sin valor (filas con `decision` vacío) se ignoran. Esto permite
    revisar el CSV en bloques.

Uso:
  python -m scripts.aplicar_decisiones_hitl
  python -m scripts.aplicar_decisiones_hitl --dry-run     # solo reporta
  python -m scripts.aplicar_decisiones_hitl --csv otro.csv
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

OUT_DIR = Path("output/anexos")
HITL_JSON_DIR = Path("predial-mx-v2-hitl")
DEFAULT_CSV = OUT_DIR / "cambios_interanuales.csv"
QUEUE_CSV = OUT_DIR / "cola_reextraccion.csv"
BITACORA_CSV = OUT_DIR / "hitl_bitacora.csv"

VALID_DECISIONS = {
    "aceptar_nuevo",
    "propagar_previo",
    "reextraer",
    "cambio_real_documentado",
}

# Hints sugeridos por tipo de cambio (orientan al extractor LLM al re-extraer).
REEXTRACT_HINT = (
    "Extraer ARTÍCULO PRINCIPAL DE TARIFA del impuesto predial. "
    "Ignorar artículos de mínimo predial, transitorios, vigencia, beneficios "
    "y bonificaciones a menos que sean la única tarifa. Si el documento "
    "contiene la tarifa en varios artículos, integrar la mecánica completa."
)


def _load_decisions(csv_path: Path) -> list[dict]:
    if not csv_path.exists():
        raise SystemExit(f"No existe {csv_path}. Corre primero detectar_cambios_interanuales.")
    with csv_path.open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _append_bitacora(rows: list[dict]) -> None:
    if not rows:
        return
    is_new = not BITACORA_CSV.exists()
    BITACORA_CSV.parent.mkdir(parents=True, exist_ok=True)
    cols = [
        "timestamp", "decision", "estado", "municipio", "anio_prev", "anio",
        "tipo_prev", "tipo_nuevo", "severidad_max", "racha_estable_previa",
        "json_prev", "json_nuevo", "json_propagado", "notas",
    ]
    with BITACORA_CSV.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        if is_new:
            w.writeheader()
        w.writerows(rows)


def _write_queue(rows: list[dict]) -> None:
    if not rows:
        return
    QUEUE_CSV.parent.mkdir(parents=True, exist_ok=True)
    cols = ["estado", "estado_slug", "municipio", "anio", "json_path", "hint", "notas"]
    with QUEUE_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _propagate(row: dict, timestamp: str) -> Path | None:
    """Copia el JSON del año previo al año nuevo en predial-mx-v2-hitl/."""
    src = Path(row["json_prev"])
    new_path = Path(row["json_nuevo"])
    if not src.exists():
        print(f"  [ERROR] JSON previo no existe: {src}")
        return None
    estado_dir = new_path.parent.name  # último segmento (estado_slug)
    dst = HITL_JSON_DIR / estado_dir / new_path.name
    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc = json.loads(src.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  [ERROR] Leyendo {src}: {e}")
        return None
    meta = doc.get("_meta") or {}
    meta["modelo"] = "imputed_human_propagation"
    meta["imputed_from_year"] = int(row["anio_prev"])
    meta["target_year"] = int(row["anio"])
    meta["hitl_timestamp"] = timestamp
    meta["hitl_decision"] = "propagar_previo"
    doc["_meta"] = meta
    dst.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return dst


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(DEFAULT_CSV),
                    help=f"CSV de decisiones (default {DEFAULT_CSV}).")
    ap.add_argument("--dry-run", action="store_true",
                    help="No escribe archivos; solo reporta lo que haría.")
    args = ap.parse_args()
    csv_path = Path(args.csv)

    decisiones = _load_decisions(csv_path)
    print(f"Cargadas {len(decisiones)} filas desde {csv_path}")

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    bitacora: list[dict] = []
    cola: list[dict] = []
    contadores = {
        "aceptar_nuevo": 0, "propagar_previo": 0, "reextraer": 0,
        "cambio_real_documentado": 0, "sin_decision": 0, "invalida": 0,
        "propagar_error": 0,
    }

    for row in decisiones:
        decision = (row.get("decision") or "").strip().lower()
        if not decision:
            contadores["sin_decision"] += 1
            continue
        if decision not in VALID_DECISIONS:
            print(f"  [WARN] decisión inválida '{decision}' en "
                  f"{row['municipio']} {row['anio']}")
            contadores["invalida"] += 1
            continue

        bit_row = {
            "timestamp": timestamp,
            "decision": decision,
            "estado": row.get("estado"),
            "municipio": row.get("municipio"),
            "anio_prev": row.get("anio_prev"),
            "anio": row.get("anio"),
            "tipo_prev": row.get("tipo_prev"),
            "tipo_nuevo": row.get("tipo_nuevo"),
            "severidad_max": row.get("severidad_max"),
            "racha_estable_previa": row.get("racha_estable_previa"),
            "json_prev": row.get("json_prev"),
            "json_nuevo": row.get("json_nuevo"),
            "json_propagado": "",
            "notas": row.get("notas", ""),
        }

        if decision == "propagar_previo":
            if args.dry_run:
                dst = HITL_JSON_DIR / Path(row["json_nuevo"]).parent.name / Path(row["json_nuevo"]).name
                bit_row["json_propagado"] = str(dst) + " (dry-run)"
            else:
                dst = _propagate(row, timestamp)
                if dst is None:
                    contadores["propagar_error"] += 1
                    continue
                bit_row["json_propagado"] = dst.as_posix()
            contadores["propagar_previo"] += 1

        elif decision == "reextraer":
            cola.append({
                "estado": row.get("estado"),
                "estado_slug": row.get("estado_slug"),
                "municipio": row.get("municipio"),
                "anio": row.get("anio"),
                "json_path": row.get("json_nuevo"),
                "hint": REEXTRACT_HINT,
                "notas": row.get("notas", ""),
            })
            contadores["reextraer"] += 1

        elif decision == "aceptar_nuevo":
            contadores["aceptar_nuevo"] += 1

        elif decision == "cambio_real_documentado":
            contadores["cambio_real_documentado"] += 1

        bitacora.append(bit_row)

    # Escribir resultados.
    if not args.dry_run:
        _append_bitacora(bitacora)
        _write_queue(cola)

    print("\nResumen:")
    print(f"  propagar_previo:          {contadores['propagar_previo']}"
          f"    -> {HITL_JSON_DIR}/")
    print(f"  reextraer:                {contadores['reextraer']}"
          f"    -> {QUEUE_CSV}")
    print(f"  aceptar_nuevo:            {contadores['aceptar_nuevo']}")
    print(f"  cambio_real_documentado:  {contadores['cambio_real_documentado']}")
    print(f"  filas sin decision:       {contadores['sin_decision']}")
    print(f"  decisiones invalidas:     {contadores['invalida']}")
    if contadores["propagar_error"]:
        print(f"  errores al propagar:      {contadores['propagar_error']}")
    if not args.dry_run:
        print(f"\nBitacora: {BITACORA_CSV} (append-only)")
    else:
        print("\n(dry-run: no se escribió nada)")


if __name__ == "__main__":
    main()
