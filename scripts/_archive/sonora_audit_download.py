"""
Audit exhaustivo del download de Sonora — Fase 1 del quality audit.

Para cada uno de los PDFs en source_documents.csv que tienen leyes asociadas
en discovered_laws.csv, verifica que el archivo físico contenga texto canónico
de ley de ingresos municipal.

Detecta mismatches HTML↔PDF: el HTML lista una ley pero el PDF no la contiene
(porque el discoverer asoció mal el PDF, porque el PDF es un boletín truncado,
o porque la ley está en otro PDF).

Categorías:
  ok          : todas las leyes esperadas se encuentran en el texto del PDF
  partial     : algunas leyes en el PDF, otras no
  mismatch    : ninguna ley esperada se encuentra (PDF probablemente no es ley)
  no_text     : PDF sin texto extraíble (necesita OCR)
  missing_file: PDF no descargado físicamente

Output: data/sonora/meta/audit_download.csv
"""

from __future__ import annotations

import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import fitz  # PyMuPDF

# Permitir importar src/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.estados import get_adapter  # noqa: E402


# ═══════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════

def _normalize_text(text: str) -> str:
    """Quita acentos, baja a minúsculas, colapsa whitespace."""
    if not text:
        return ""
    nfkd = unicodedata.normalize("NFKD", text)
    no_accents = "".join(c for c in nfkd if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", no_accents.lower())


def _slug_to_search_terms(slug: str, municipio_raw: str) -> list[str]:
    """
    Convierte un slug INEGI a términos de búsqueda alternativos.
    Ej: 'agua_prieta' → ['agua prieta'], 'general_plutarco_elias_calles' →
       ['general plutarco elias calles', 'plutarco elias calles', 'gral plutarco']
    """
    base = slug.replace("_", " ")
    terms = [base]
    # Variantes comunes
    if "general" in base:
        terms.append(base.replace("general ", ""))
        terms.append(base.replace("general ", "gral "))
        terms.append(base.replace("general ", "gral. "))
    if "heroica" in base:
        terms.append(base.replace("heroica ", ""))
    # Nombre raw como fallback
    if municipio_raw:
        terms.append(_normalize_text(municipio_raw))
    return list(set(t for t in terms if len(t) >= 4))


def _resolve_best_pdf(pdf_raw: Path, pdf_ocr_dir: Path) -> tuple[Path, bool]:
    """Devuelve (path, ocr_disponible)."""
    if not pdf_raw.exists():
        return pdf_raw, False
    year_name = pdf_raw.parent.name
    ocr_path = pdf_ocr_dir / year_name / (pdf_raw.stem + "_ocr.pdf")
    if ocr_path.exists() and ocr_path.stat().st_size > 0:
        return ocr_path, True
    return pdf_raw, False


def _extract_text(pdf_path: Path) -> str:
    """Extrae todo el texto del PDF."""
    try:
        with fitz.open(str(pdf_path)) as doc:
            return "\n".join((doc[i].get_text("text") or "") for i in range(len(doc)))
    except Exception:
        return ""


# ═══════════════════════════════════════════════════
# Audit
# ═══════════════════════════════════════════════════

# Patrón canónico tolerante para detectar "Ley...Ingresos" en PDF
_RE_LEY_INGRESOS = re.compile(
    r"ley[\s\w]{0,60}ingresos",
    re.IGNORECASE,
)

_AUDIT_FIELDS = [
    "url_pdf", "anio_pub", "era", "filename",
    "leyes_esperadas_total", "leyes_encontradas_total",
    "leyes_esperadas", "leyes_encontradas", "leyes_faltantes",
    "status", "ocr_disponible", "chars_extraidos",
    "tiene_titulo_ley_ingresos",
]


def audit_download(adapter) -> Path:
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    pdf_ocr_dir = adapter.pdf_ocr_dir
    audit_csv = meta_dir / "audit_download.csv"

    docs_csv = meta_dir / "source_documents.csv"
    laws_csv = meta_dir / "discovered_laws.csv"
    if not docs_csv.exists() or not laws_csv.exists():
        raise FileNotFoundError(
            f"Faltan {docs_csv} o {laws_csv}. Corre 'discover' primero."
        )

    # Cargar docs y leyes
    with docs_csv.open(encoding="utf-8") as f:
        docs = list(csv.DictReader(f))
    with laws_csv.open(encoding="utf-8") as f:
        laws = list(csv.DictReader(f))

    # Index leyes por url_pdf
    laws_por_url: dict[str, list[dict]] = defaultdict(list)
    for ley in laws:
        laws_por_url[ley["documento_url"]].append(ley)

    # Filtrar docs CON leyes
    docs_con_leyes = [d for d in docs if d["url_pdf"] in laws_por_url]
    print("═══ Sonora: Audit del download ═══")
    print(f"    Docs en source_documents.csv: {len(docs)}")
    print(f"    Docs CON leyes asociadas: {len(docs_con_leyes)}")
    print("    Procesando...")

    rows: list[dict] = []

    for i, doc in enumerate(docs_con_leyes, 1):
        url = doc["url_pdf"]
        anio_pub = doc.get("anio_pub", "")
        era = doc.get("era", "")
        fname = url.rsplit("/", 1)[-1]

        leyes_esperadas = laws_por_url[url]
        slugs_esperados = sorted(set(le["municipio_slug"] for le in leyes_esperadas))
        municipios_raw = {le["municipio_slug"]: le["municipio_raw"] for le in leyes_esperadas}

        # Resolver PDF
        pdf_raw_path = pdf_raw_dir / str(anio_pub) / fname
        if not pdf_raw_path.exists():
            rows.append({
                "url_pdf": url, "anio_pub": anio_pub, "era": era, "filename": fname,
                "leyes_esperadas_total": len(slugs_esperados),
                "leyes_encontradas_total": 0,
                "leyes_esperadas": ";".join(slugs_esperados),
                "leyes_encontradas": "",
                "leyes_faltantes": ";".join(slugs_esperados),
                "status": "missing_file", "ocr_disponible": False,
                "chars_extraidos": 0, "tiene_titulo_ley_ingresos": False,
            })
            continue

        pdf_path, ocr_ok = _resolve_best_pdf(pdf_raw_path, pdf_ocr_dir)
        text = _extract_text(pdf_path)
        chars = len(text)

        if chars < 200:
            rows.append({
                "url_pdf": url, "anio_pub": anio_pub, "era": era, "filename": fname,
                "leyes_esperadas_total": len(slugs_esperados),
                "leyes_encontradas_total": 0,
                "leyes_esperadas": ";".join(slugs_esperados),
                "leyes_encontradas": "",
                "leyes_faltantes": ";".join(slugs_esperados),
                "status": "no_text", "ocr_disponible": ocr_ok,
                "chars_extraidos": chars, "tiene_titulo_ley_ingresos": False,
            })
            continue

        text_norm = _normalize_text(text)
        tiene_titulo = bool(_RE_LEY_INGRESOS.search(text_norm))

        # Para cada slug esperado, ver si aparece en el texto
        encontrados: list[str] = []
        faltantes: list[str] = []
        for slug in slugs_esperados:
            search_terms = _slug_to_search_terms(slug, municipios_raw.get(slug, ""))
            if any(t in text_norm for t in search_terms):
                encontrados.append(slug)
            else:
                faltantes.append(slug)

        n_esp = len(slugs_esperados)
        n_enc = len(encontrados)
        if n_enc == n_esp:
            status = "ok"
        elif n_enc > 0:
            status = "partial"
        else:
            status = "mismatch"

        rows.append({
            "url_pdf": url, "anio_pub": anio_pub, "era": era, "filename": fname,
            "leyes_esperadas_total": n_esp,
            "leyes_encontradas_total": n_enc,
            "leyes_esperadas": ";".join(slugs_esperados),
            "leyes_encontradas": ";".join(encontrados),
            "leyes_faltantes": ";".join(faltantes),
            "status": status, "ocr_disponible": ocr_ok,
            "chars_extraidos": chars, "tiene_titulo_ley_ingresos": tiene_titulo,
        })

        if i % 50 == 0:
            print(f"    [{i}/{len(docs_con_leyes)}] procesados...")

    # Escribir CSV
    with audit_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_AUDIT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    # Reporte
    print("\n" + "═" * 60)
    print("  REPORTE DEL AUDIT DEL DOWNLOAD")
    print("═" * 60)
    status_cnt = Counter(r["status"] for r in rows)
    total = len(rows)
    print(f"\n  Total auditados: {total}\n")
    for s in ["ok", "partial", "mismatch", "no_text", "missing_file"]:
        n = status_cnt.get(s, 0)
        pct = 100 * n / total if total else 0
        bar = "█" * int(pct / 2.5)
        print(f"  {s:<14} {n:<5} ({pct:>5.1f}%)  {bar}")

    # Por año
    print("\n  ── Por anio_pub ──")
    print(f"  {'anio_pub':<10} {'total':<6} {'ok':<5} {'partial':<8} {'mismatch':<10} {'no_text':<8} {'missing':<8}")
    by_year: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        by_year[r["anio_pub"]][r["status"]] += 1
        by_year[r["anio_pub"]]["total"] += 1
    for y in sorted(by_year):
        s = by_year[y]
        print(
            f"  {y:<10} {s['total']:<6} {s.get('ok', 0):<5} "
            f"{s.get('partial', 0):<8} {s.get('mismatch', 0):<10} "
            f"{s.get('no_text', 0):<8} {s.get('missing_file', 0):<8}"
        )

    # OCR disponible vs no
    print("\n  ── OCR disponible ──")
    ocr_cnt = Counter(("OCR" if r["ocr_disponible"] else "RAW") + "/" + r["status"] for r in rows)
    for k in sorted(ocr_cnt):
        print(f"  {k:<25} {ocr_cnt[k]}")

    # Top 20 mismatches
    print("\n  ── TOP 20 mismatches (PDF no contiene leyes esperadas) ──")
    mismatches = [r for r in rows if r["status"] == "mismatch"][:20]
    for r in mismatches:
        muni_short = r["leyes_esperadas"][:60]
        print(f"  {r['filename']:<35} ← {muni_short}")

    print(f"\n  Bitácora: {audit_csv}")
    return audit_csv


if __name__ == "__main__":
    adapter = get_adapter("sonora")
    audit_download(adapter)
