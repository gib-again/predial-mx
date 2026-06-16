"""Reintento OdJ 2014 con rango pp 26-35."""
import sys
import json
from pathlib import Path

import dotenv
dotenv.load_dotenv(Path(".env"), override=False)

sys.stdout.reconfigure(encoding="utf-8")

import fitz
from src.core.llm_extract import call_llm_vision

src = "data/oaxaca/pdf_ocr/2013/12/EXT-DEC26-2013-12-31_ocr.pdf"
WORK = Path("data/oaxaca/_calibration/odj_vision")

doc = fitz.open(src)
out_pdf = WORK / "OdJ_2014_pp26-35.pdf"
new = fitz.open()
for p in range(25, 35):
    new.insert_pdf(doc, from_page=p, to_page=p)
new.save(str(out_pdf))
new.close()
doc.close()

print("Probando OdJ 2014 con pp 26-35...")
data = call_llm_vision(
    out_pdf,
    anio=2014,
    municipio_nombre="Oaxaca de Juárez",
    estado_nombre="Oaxaca",
)
pred = data.get("predial", {})
print(f"tipo: {pred.get('tipo_esquema')}")
n_m = len(pred.get("tabla_tarifa_millar", []) or [])
n_p = len(pred.get("tabla_progresiva", []) or [])
print(f"Filas millar: {n_m}, prog: {n_p}")
print(f"comentarios: {pred.get('comentarios','')[:300]}")

if n_m or n_p:
    if "_meta" not in data:
        data["_meta"] = {"fuente": "pdf_vision", "modelo": "gpt-5.4-mini"}
    out_json = Path("data/oaxaca/json_predial/2014/OAX_PREDIAL_2014_oaxaca_de_juarez.json")
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    (WORK / "OdJ_2014_vision_v2.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nGuardado en {out_json}")
    for r in (pred.get("tabla_tarifa_millar", []) or [])[:6]:
        print(f"  {r.get('tasa_millar','?')}/mil — {r.get('descripcion','')[:80]}")
