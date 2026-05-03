"""Traceback Oaxaca de Juárez: extraer todos los años y reportar tipo_esquema."""
import sys
import json
from pathlib import Path

import dotenv
dotenv.load_dotenv(Path(".env"), override=False)

sys.stdout.reconfigure(encoding="utf-8")

from src.estados import get_adapter
from src.core.llm_extract import extract_single, OPENAI_MODEL

print(f"Modelo: {OPENAI_MODEL}\n")

adapter = get_adapter("oaxaca")
years = sorted({int(p.stem.split("_")[2]) for p in Path("data/oaxaca/focus_predial").glob(
    "*/OAX_PREDIAL_*_oaxaca_de_juarez.txt"
)})

results = []
for year in years:
    txt_path = Path(f"data/oaxaca/focus_predial/{year}/OAX_PREDIAL_{year}_oaxaca_de_juarez.txt")
    json_dir = Path("data/oaxaca/json_predial")
    print(f"\n[{year}] Extrayendo ({txt_path.stat().st_size} chars)...")
    out = extract_single(
        txt_path=txt_path,
        json_dir=json_dir,
        prefijo="OAX",
        estado_nombre="Oaxaca",
        pdf_fallback=True,
        adapter=adapter,
    )
    if out and out.exists():
        data = json.loads(out.read_text(encoding="utf-8"))
        pred = data.get("predial", {})
        tipo = pred.get("tipo_esquema", "?")
        valido = pred.get("esquema_valido", False)
        fuente = data.get("_meta", {}).get("fuente", "?")
        results.append((year, tipo, valido, fuente))
    else:
        results.append((year, "FAIL", False, "-"))

print("\n=== Cronología Oaxaca de Juárez ===")
print(f"{'año':<6} {'tipo_esquema':<22} {'válido':<7} {'fuente'}")
for year, tipo, valido, fuente in results:
    flag = "← PROGRESIVO" if "progresivo" in tipo else ""
    print(f"{year:<6} {tipo:<22} {valido!s:<7} {fuente:<14} {flag}")
