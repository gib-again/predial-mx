"""Calibración: ¿es la calidad del segment o la capacidad del modelo?

Toma 50 muestras estratificadas por método de segmentación y las extrae
con gpt-5.4 (modelo grande). Compara con resultados típicos de gpt-5.4-mini.
"""
import os
import sys
import json
from collections import defaultdict
from pathlib import Path

# Override ANTES de importar llm_extract (lee env en import time)
os.environ["OPENAI_MODEL"] = "gpt-5.4"
os.environ["OPENAI_VISION_MODEL"] = "gpt-5.4"

import dotenv
dotenv.load_dotenv(Path(".env"), override=False)

sys.stdout.reconfigure(encoding="utf-8")

from src.estados import get_adapter
from src.core.llm_extract import extract_single, OPENAI_MODEL

print(f">> OPENAI_MODEL en runtime: {OPENAI_MODEL}")

adapter = get_adapter("oaxaca")
calib_dir = Path("data/oaxaca/_calibration/json_gpt54")
calib_dir.mkdir(parents=True, exist_ok=True)

sample = json.loads(
    Path("data/oaxaca/_calibration/sample_50.json").read_text(encoding="utf-8")
)

results = []
for i, entry in enumerate(sample, 1):
    method = entry["method"]
    txt_path = Path(entry["path"])
    print(f'\n[{i}/{len(sample)}] {method} | {txt_path.name} ({entry["chars"]} chars)')
    try:
        out = extract_single(
            txt_path=txt_path,
            json_dir=calib_dir,
            prefijo="OAX",
            estado_nombre="Oaxaca",
            pdf_fallback=True,
            adapter=adapter,
        )
    except Exception as e:
        print(f"  EXCEPCIÓN: {e}")
        out = None

    classified = "?"
    valid = False
    fuente = ""
    if out and out.exists():
        data = json.loads(out.read_text(encoding="utf-8"))
        pred = data.get("predial", {})
        classified = pred.get("tipo_esquema", "?")
        valid = pred.get("esquema_valido", False)
        fuente = data.get("_meta", {}).get("fuente", "")
    results.append({
        "method_segment": method,
        "year": entry["year"],
        "file": txt_path.name,
        "chars": entry["chars"],
        "tipo_esquema": classified,
        "esquema_valido": valid,
        "fuente": fuente,
    })

Path("data/oaxaca/_calibration/results_gpt54.json").write_text(
    json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8"
)

# Summary
summary = defaultdict(lambda: {"total": 0, "valido": 0, "desconocido": 0, "fail": 0})
for r in results:
    s = summary[r["method_segment"]]
    s["total"] += 1
    if r["esquema_valido"]:
        s["valido"] += 1
    if r["tipo_esquema"] == "desconocido":
        s["desconocido"] += 1
    if r["tipo_esquema"] == "?":
        s["fail"] += 1

print("\n\n══════ RESUMEN gpt-5.4 ══════")
print(f'{"método":<28} {"total":>5} {"válido":>7} {"descon":>7} {"fail":>5}')
for m, s in summary.items():
    print(
        f'{m:<28} {s["total"]:>5} {s["valido"]:>7} {s["desconocido"]:>7} {s["fail"]:>5}'
    )
