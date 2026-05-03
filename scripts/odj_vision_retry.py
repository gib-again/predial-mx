"""Reintenta extracción de OdJ años desconocidos con visión sobre PDFs amplios."""
import sys
import json
from pathlib import Path

import dotenv
dotenv.load_dotenv(Path(".env"), override=False)

sys.stdout.reconfigure(encoding="utf-8")

import fitz
from src.core.llm_extract import call_llm_vision

WORK = Path("data/oaxaca/_calibration/odj_vision")
WORK.mkdir(parents=True, exist_ok=True)

# (year, source_pdf, page_start_0idx, page_end_excl)
specs = [
    ("2023", "data/oaxaca/pdf_ocr/2023/03/SEC10-05TA-2023-03-11_ocr.pdf", 3, 25),
    ("2024", "data/oaxaca/pdf_ocr/2024/04/SEC14-03RA-2024-04-06_ocr.pdf", 1, 25),
    ("2019", "data/oaxaca/pdf_ocr/2018/12/EXT-DEC66-2018-12-31_ocr.pdf", 1, 24),
    ("2014", "data/oaxaca/pdf_ocr/2013/12/EXT-DEC26-2013-12-31_ocr.pdf", 1, 28),
]

results = []
for year, src, p0, p1 in specs:
    if not Path(src).exists():
        print(f"[{year}] no existe {src}")
        continue
    doc = fitz.open(src)
    p1 = min(p1, len(doc))
    out_pdf = WORK / f"OdJ_{year}_pp{p0+1}-{p1}.pdf"
    new = fitz.open()
    for p in range(p0, p1):
        new.insert_pdf(doc, from_page=p, to_page=p)
    new.save(str(out_pdf))
    new.close()
    doc.close()
    print(f"\n[{year}] {out_pdf.name} ({p1-p0} páginas) -> visión...")

    try:
        data = call_llm_vision(out_pdf, anio=int(year), municipio_nombre="Oaxaca de Juárez", estado_nombre="Oaxaca")
    except Exception as e:
        print(f"  ERROR vision: {e}")
        results.append((year, "ERROR", str(e)[:100]))
        continue

    pred = data.get("predial", {}) if data else {}
    tipo = pred.get("tipo_esquema", "?")
    valido = pred.get("esquema_valido", False)
    com = pred.get("comentarios", "")[:200]
    print(f"  -> tipo={tipo} valido={valido}")
    print(f"  comentarios: {com}")

    out_json = WORK / f"OdJ_{year}_vision.json"
    out_json.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    results.append((year, tipo, valido))

print("\n=== Resumen visión ===")
for r in results:
    print(r)
