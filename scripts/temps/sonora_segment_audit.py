"""
Audit de segment.py para Sonora — Fase 3 del quality audit.

Analiza el comportamiento de `find_leyes_in_pdf` y `extract_predial_section`:
  1. Fallback rate por año (de segment.csv).
  2. Para los 126 fallbacks (segment_method=fallback_*), inspecciona el TXT
     y categoriza:
       - 'no_predial_in_pdf': el PDF realmente no contiene sección predial
         (boletín equivocado, página corrupta).
       - 'pattern_miss': el PDF SÍ contiene "Impuesto Predial" en alguna
         variante pero los regex no lo capturan.
       - 'low_quality_ocr': texto OCR tan ruidoso que ni regex laxos lo
         detectan (necesita re-OCR o cleanup).
  3. Genera un dump de los pattern_miss para diseñar nuevos regex.

Output: data/sonora/meta/segment_audit.csv
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path


# Permitir importar src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.estados import get_adapter  # noqa: E402


# ═══════════════════════════════════════════════════
# Detectores de "Impuesto Predial" en texto
# ═══════════════════════════════════════════════════

# Más laxo que los regex de segment.py: solo busca menciones del término
_RE_IMPUESTO_PREDIAL_LAXO = re.compile(
    r"impuesto[\s\w]{0,5}predial",
    re.IGNORECASE,
)
_RE_TASA_PREDIAL = re.compile(
    r"(?:tasa|cuota|tarifa)[\s\w]{0,30}(?:al\s+millar|por\s+millar|millar|valor\s+catastral)",
    re.IGNORECASE,
)
_RE_VALOR_MONETARIO = re.compile(r"\$\s?\d{1,3}(?:[,.]?\d{3})*(?:\.\d{2})?")
_RE_CAPITULO_PRIMERO = re.compile(
    r"cap[ií]tulo\s+(?:primero|i\b|1)",
    re.IGNORECASE,
)


def _normalize(text: str) -> str:
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if unicodedata.category(c) != "Mn").lower()


# ═══════════════════════════════════════════════════
# Audit
# ═══════════════════════════════════════════════════

_AUDIT_FIELDS = [
    "ejercicio", "slug", "source_pdf", "focus_file", "segment_method",
    "txt_chars", "n_impuesto_predial", "n_tasa_predial",
    "n_valores_monetarios", "tiene_capitulo_primero",
    "categoria",  # no_predial_in_pdf | pattern_miss | low_quality_ocr | (otros)
    "muestra_texto",
]


def audit_segment(adapter) -> Path:
    meta_dir = adapter.meta_dir
    seg_csv = meta_dir / "segment.csv"
    audit_csv = meta_dir / "segment_audit.csv"
    focus_dir = adapter.focus_dir
    excluded_dir = adapter.data_dir / "_focus_excluded"

    if not seg_csv.exists():
        raise FileNotFoundError(f"Falta {seg_csv}.")

    with seg_csv.open(encoding="utf-8") as f:
        seg = list(csv.DictReader(f))

    print("═══ Sonora: Segment audit (Fase 3) ═══")
    print(f"    Filas en segment.csv: {len(seg)}")

    # 1. Fallback rate por año
    by_year: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in seg:
        ej = r["ejercicio"]
        by_year[ej]["total"] += 1
        if r["segment_method"].startswith("fallback"):
            by_year[ej]["fallback"] += 1
        elif r["segment_method"].endswith("_unvalidated"):
            by_year[ej]["unvalidated"] += 1
        elif r["segment_method"] == "no_text":
            by_year[ej]["no_text"] += 1
        else:
            by_year[ej]["ok"] += 1

    print("\n  ── Fallback rate por año ──")
    print(f"  {'año':<6} {'total':<6} {'ok':<5} {'fallback':<10} {'%fb':<6}")
    for y in sorted(by_year):
        s = by_year[y]
        total = s.get("total", 0)
        fb = s.get("fallback", 0) + s.get("unvalidated", 0) + s.get("no_text", 0)
        pct = 100 * fb / total if total else 0
        print(f"  {y:<6} {total:<6} {s.get('ok', 0):<5} {fb:<10} {pct:>5.1f}%")

    # 2. Categorizar fallbacks (incluye los movidos a _focus_excluded)
    fallback_rows = [
        r for r in seg
        if r["segment_method"].startswith("fallback")
        or r["segment_method"].endswith("_unvalidated")
        or r["segment_method"] == "no_text"
    ]
    print(f"\n    Fallbacks/unvalidated/no_text: {len(fallback_rows)}")

    audit_rows: list[dict] = []
    for r in fallback_rows:
        ej = r["ejercicio"]
        focus_file = r["focus_file"]
        if not focus_file:
            continue
        # Buscar TXT en focus_predial/ o en _focus_excluded/
        candidates = [
            focus_dir / ej / focus_file,
            excluded_dir / ej / focus_file,
        ]
        txt_path = next((p for p in candidates if p.exists()), None)
        if txt_path is None:
            continue
        text = txt_path.read_text(encoding="utf-8", errors="ignore")
        # Saltar el header (líneas que empiezan con #)
        body = "\n".join(line for line in text.split("\n") if not line.startswith("#"))
        body_norm = _normalize(body)

        n_imp_pred = len(_RE_IMPUESTO_PREDIAL_LAXO.findall(body_norm))
        n_tasa_pred = len(_RE_TASA_PREDIAL.findall(body_norm))
        n_valores = len(_RE_VALOR_MONETARIO.findall(body))
        tiene_cap1 = bool(_RE_CAPITULO_PRIMERO.search(body_norm))

        # Categorizar
        if n_imp_pred == 0 and n_tasa_pred == 0:
            categoria = "no_predial_in_pdf"
        elif n_imp_pred >= 2 and tiene_cap1 and n_valores >= 5:
            # Sí tiene predial pero el regex no lo capturó
            categoria = "pattern_miss"
        elif n_imp_pred >= 1 and len(body) < 5000:
            # Texto corto → posible OCR pobre
            categoria = "low_quality_ocr"
        else:
            categoria = "ambiguo"

        # Muestra: primeros 200 chars del cuerpo
        muestra = body[:200].replace("\n", " ").strip()

        audit_rows.append({
            "ejercicio": ej,
            "slug": r["slug"],
            "source_pdf": r["source_pdf"],
            "focus_file": focus_file,
            "segment_method": r["segment_method"],
            "txt_chars": len(body),
            "n_impuesto_predial": n_imp_pred,
            "n_tasa_predial": n_tasa_pred,
            "n_valores_monetarios": n_valores,
            "tiene_capitulo_primero": tiene_cap1,
            "categoria": categoria,
            "muestra_texto": muestra,
        })

    # Escribir CSV
    with audit_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(audit_rows)

    # Reporte
    print("\n  ── Categorización de fallbacks ──")
    cat_cnt = Counter(r["categoria"] for r in audit_rows)
    for cat, n in cat_cnt.most_common():
        pct = 100 * n / len(audit_rows) if audit_rows else 0
        print(f"  {cat:<25} {n:<5} ({pct:>5.1f}%)")

    # Pattern_miss: muestra concreta
    pattern_miss = [r for r in audit_rows if r["categoria"] == "pattern_miss"]
    print("\n  ── TOP 15 pattern_miss (regex no captura aunque hay predial) ──")
    print(f"  {'slug':<25} {'año':<6} {'n_pred':<7} {'n_tasa':<7} {'cap1':<5} {'sample'}")
    for r in pattern_miss[:15]:
        print(
            f"  {r['slug'][:24]:<25} {r['ejercicio']:<6} "
            f"{r['n_impuesto_predial']:<7} {r['n_tasa_predial']:<7} "
            f"{('Y' if r['tiene_capitulo_primero'] else 'N'):<5} "
            f"{r['muestra_texto'][:80]}"
        )

    print(f"\n  Bitácora: {audit_csv}")
    return audit_csv


if __name__ == "__main__":
    adapter = get_adapter("sonora")
    audit_segment(adapter)
