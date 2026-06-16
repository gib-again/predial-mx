#!/usr/bin/env python3
"""Aplica leyes descubiertas (catalogs/discovered_laws/*.pdf) a múltiples años.

Algunos PDFs descubiertos por el auditor son **Leyes de Hacienda Municipal**
que cubren un rango de ejercicios (ej. una ley vigente 2019-2024). El audit
marca esos años como `no_existe_ley` (porque la Ley de Ingresos puntual no
existe), pero el usuario aporta la Ley de Hacienda como "mejor reconstrucción
posible". Este script:

  1. Extrae predial vía LLM de cada Ley de Hacienda descubierta.
  2. Replica el JSON resultante a cada año target con
     `_meta.modelo = "discovered_law_hacienda_<source_year>"`
     y comentario explicativo.
  3. Escribe a predial-mx-v2/{estado}/.

Mappings hardcoded — añadir aquí cuando aparezcan nuevos PDFs:

  guan_celaya_2019.pdf                 → Celaya (Guanajuato), 2019  [single-year]
  yuc_hocaba_Ley_hacienda_2022.pdf     → Hocabá (Yucatán), 2019–2025
  yuc_valladolid_Ley_Hacienda_2019-2024.pdf
                                       → Valladolid (Yucatán), 2018–2024
  yuc_valladolid_Ley_Hacienda_2025.pdf → Valladolid (Yucatán), 2025

Idempotente: si el JSON destino ya existe con un modelo no-imputado/no-audit,
se preserva.

Uso:
    python -m scripts.apply_discovered_laws --dry-run
    python -m scripts.apply_discovered_laws            # gasta tokens
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import fitz
from dotenv import load_dotenv

# Cargar .env temprano para que OPENAI_API_KEY esté disponible.
load_dotenv()

from src.core.balance_panel_v2 import (
    ESTADO_SLUG_BY_NOM_ENT,
    PREFIJOS_BY_SLUG,
)
from src.core.llm_extract import extract_single
from src.core.text_utils import slugify


# ── Mappings de leyes descubiertas → (estado, muni_nom, anios, paginas) ──
# `paginas`: tupla (start, end) 1-indexed en el PDF, o None para todo el doc.

DISCOVERED_LAWS = [
    {
        "pdf": "guan_celaya_2019.pdf",
        "estado_nom": "Guanajuato",
        "municipio_nom": "Celaya",
        "anios": [2019],
        "paginas": (12, 14),  # rango razonable del audit "dic-13" → ~13
        "comentario_extra": "Ley de Ingresos discovered por el auditor.",
    },
    {
        "pdf": "yuc_hocaba_Ley_hacienda_2022.pdf",
        "estado_nom": "Yucatan",
        "municipio_nom": "Hocabá",
        "anios": [2019, 2020, 2021, 2022, 2023, 2024, 2025],
        "paginas": None,  # documento corto; usar todo el texto
        "comentario_extra": (
            "Ley de Hacienda Municipal de Hocabá vigente; "
            "aplicada como mejor reconstrucción a años sin Ley de Ingresos puntual."
        ),
    },
    {
        "pdf": "yuc_valladolid_Ley_Hacienda_2019-2024.pdf",
        "estado_nom": "Yucatan",
        "municipio_nom": "Valladolid",
        "anios": [2018, 2019, 2020, 2021, 2022, 2023, 2024],
        "paginas": None,
        "comentario_extra": (
            "Ley de Hacienda Municipal de Valladolid 2019-2024; "
            "aplicada también a 2018 como mejor reconstrucción."
        ),
    },
    {
        "pdf": "yuc_valladolid_Ley_Hacienda_2025.pdf",
        "estado_nom": "Yucatan",
        "municipio_nom": "Valladolid",
        "anios": [2025],
        "paginas": None,
        "comentario_extra": "Ley de Hacienda Municipal de Valladolid 2025.",
    },
]


def _extract_pdf_text(pdf_path: Path, paginas: tuple[int, int] | None) -> str:
    parts: list[str] = []
    with fitz.open(str(pdf_path)) as doc:
        n = doc.page_count
        if paginas is None:
            page_range = range(n)
        else:
            page_range = range(max(0, paginas[0] - 1), min(paginas[1], n))
        for i in page_range:
            t = doc[i].get_text("text") or ""
            parts.append(t)
            parts.append("\n")
    return "".join(parts).strip()


# Patrones para localizar la sección que define el impuesto predial dentro
# de una Ley de Hacienda completa (no Ley de Ingresos).
_RE_PREDIAL_SECTION_START = re.compile(
    r"(?:CAP[IÍ]TULO\s+\w+\s+DEL\s+IMPUESTO\s+PREDIAL"
    r"|T[IÍ]TULO\s+\w+\s+DEL\s+IMPUESTO\s+PREDIAL"
    r"|DEL\s+IMPUESTO\s+PREDIAL\b"
    r"|Secci[oó]n\s+\w+\s+(?:Del\s+)?Impuesto\s+Predial"
    r"|Impuesto\s+Predial\s*\n?\s*ART[IÍ]CULO)",
    re.IGNORECASE,
)
_RE_NEXT_CAPITULO = re.compile(
    r"(?:CAP[IÍ]TULO\s+\w+\s+(?:DEL?\s+)?(?:IMPUESTO|TR(?:A|Á)NSITO|TRASLACI|"
    r"ADQUISICI|HOSPEDAJE|ESPECT|DIVERSI|DERECHOS)"
    r"|T[IÍ]TULO\s+\w+\s+(?:DE\s+LOS?\s+)?(?:DERECHOS|PRODUCTOS|APROVECH)"
    r")",
    re.IGNORECASE,
)


def _focus_predial_section(full_text: str, max_chars: int = 60_000) -> str:
    """Recorta `full_text` a la sección del impuesto predial.

    Estrategia:
      1. Encuentra el primer match de `_RE_PREDIAL_SECTION_START`.
      2. Recorta desde ahí hasta el siguiente capítulo/título distinto, o
         hasta `max_chars` chars, lo que sea menor.
      3. Si no encuentra el anchor, retorna ventana alrededor de la primera
         mención literal de 'predial'.
    """
    m_start = _RE_PREDIAL_SECTION_START.search(full_text)
    if m_start:
        start = m_start.start()
        # Buscar fin (siguiente capítulo no-predial)
        end_search_zone = full_text[start + 200 : start + max_chars]
        m_end = _RE_NEXT_CAPITULO.search(end_search_zone)
        end = (start + 200 + m_end.start()) if m_end else min(start + max_chars, len(full_text))
        return full_text[start:end]

    # Fallback: primera mención de "predial" + ventana
    m_pred = re.search(r"(?i)\bpredial\b", full_text)
    if m_pred:
        start = max(0, m_pred.start() - 1000)
        end = min(start + max_chars, len(full_text))
        return full_text[start:end]
    return full_text[:max_chars]


def _propagate_json_to_years(
    source_json: dict,
    estado_slug: str,
    prefijo: str,
    muni_slug: str,
    cvegeo: str,
    source_pdf: str,
    target_anios: list[int],
    extra_comentario: str,
    dry_run: bool,
) -> tuple[int, int]:
    """Replica `source_json` (extraído del PDF descubierto) a cada año target.
    Retorna (n_escritos, n_preservados)."""
    n_written = 0
    n_preserved = 0
    out_dir = Path(f"predial-mx-v2/{estado_slug}")
    if not dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    for anio in target_anios:
        out_path = out_dir / f"{prefijo}_PREDIAL_{anio}_{muni_slug}.json"

        # Idempotencia: preservar JSONs reales (no imputados, no audit_no_ley).
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
                modelo = (existing.get("_meta") or {}).get("modelo", "")
                if (
                    modelo
                    and not modelo.startswith(("imputed_", "audit_no_ley"))
                ):
                    print(f"    [preserve] {out_path.name} (modelo={modelo})")
                    n_preserved += 1
                    continue
            except Exception:
                pass

        # Construir el doc destino: copia del predial extraído + meta propio.
        predial_copy = json.loads(json.dumps(source_json.get("predial") or {}))
        # Anotar comentarios para trazabilidad.
        old_com = (predial_copy.get("comentarios") or "").strip()
        marker = (
            f"[discovered_law:{source_pdf}] {extra_comentario}"
            + (f" Comentario original: {old_com}" if old_com else "")
        )
        predial_copy["comentarios"] = marker

        target_doc = {
            "predial": predial_copy,
            "_meta": {
                "fuente": "pdf_discovered",
                "modelo": f"discovered_law[{source_pdf}]",
            },
            "_meta_v2": {
                "intentos": 0,
                "requiere_revision": False,
                "razon": None,
                "tokens": {"input": 0, "output": 0, "cached": 0},
                "cvegeo": cvegeo,
                "estado": estado_slug,
                "anio": anio,
                "discovered_law_pdf": source_pdf,
            },
        }
        if not dry_run:
            out_path.write_text(
                json.dumps(target_doc, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        print(f"    [write] {out_path.name}")
        n_written += 1
    return n_written, n_preserved


def _resolve_cvegeo(estado_slug: str, muni_slug: str) -> str:
    """Lookup cvegeo desde catalogo INEGI."""
    import csv
    cve_ent_by_slug = {
        "coahuila": "05", "chihuahua": "08", "colima": "06", "guanajuato": "11",
        "jalisco": "14", "edomex": "15", "queretaro": "22", "sinaloa": "25",
        "tabasco": "27", "tamaulipas": "28", "yucatan": "31", "oaxaca": "20",
    }
    cve_ent = cve_ent_by_slug.get(estado_slug, "")
    if not cve_ent:
        return ""
    with open("catalogs/municipios_inegi.csv", encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            if (r.get("CVE_ENT") or "").strip() != cve_ent:
                continue
            if slugify(r.get("NOM_MUN") or "") == muni_slug:
                return f"{cve_ent}{(r.get('CVE_MUN') or '').strip()}"
    return ""


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    discovered_root = Path("catalogs/discovered_laws")
    if not discovered_root.exists():
        print(f"[ERROR] No existe {discovered_root}")
        return

    total_written = 0
    total_preserved = 0
    total_skipped = 0

    for entry in DISCOVERED_LAWS:
        pdf_name = entry["pdf"]
        pdf_path = discovered_root / pdf_name
        if not pdf_path.exists():
            print(f"\n[SKIP] No existe: {pdf_path}")
            total_skipped += 1
            continue

        estado_slug = ESTADO_SLUG_BY_NOM_ENT[entry["estado_nom"]]
        prefijo = PREFIJOS_BY_SLUG[estado_slug]
        muni_slug = slugify(entry["municipio_nom"])
        cvegeo = _resolve_cvegeo(estado_slug, muni_slug)
        if not cvegeo:
            print(f"\n[ERROR] No se pudo resolver cvegeo para "
                  f"{entry['estado_nom']} / {entry['municipio_nom']}")
            total_skipped += 1
            continue

        print(f"\n=== {pdf_name} ===")
        print(f"  estado={entry['estado_nom']}, muni={entry['municipio_nom']} "
              f"({cvegeo}), anios={entry['anios']}")

        # 1. Extraer texto del PDF
        try:
            full_txt = _extract_pdf_text(pdf_path, entry.get("paginas"))
        except Exception as e:
            print(f"  [ERROR] fitz extract: {e}")
            total_skipped += 1
            continue
        if len(full_txt) < 100:
            print(f"  [ERROR] texto extraído muy corto ({len(full_txt)} chars)")
            total_skipped += 1
            continue

        # 2. Focar la sección del impuesto predial (recorta a ~60K chars max).
        txt = _focus_predial_section(full_txt)
        print(f"  texto: {len(full_txt):,} chars total → {len(txt):,} chars predial focus")

        # 2. Stage focus_predial.txt (en el primer año del rango)
        target_anios = entry["anios"]
        seed_anio = target_anios[0]
        focus_dir = Path(f"data/{estado_slug}/focus_predial/{seed_anio}")
        if not args.dry_run:
            focus_dir.mkdir(parents=True, exist_ok=True)
        focus_txt = focus_dir / f"{prefijo}_PREDIAL_{seed_anio}_{muni_slug}.txt"
        if not args.dry_run:
            focus_txt.write_text(txt, encoding="utf-8")
        print(f"  staged: {focus_txt}")

        # 3. Llamar LLM (extract_single) — produce JSON v2 en predial-mx-v2/
        if args.dry_run:
            print(f"  [DRY] llamaría a extract_single → seed año {seed_anio}")
            print(f"  [DRY] luego replicaría a {len(target_anios)} año(s): {target_anios}")
            total_written += len(target_anios)
            continue

        json_dir = Path(f"predial-mx-v2/{estado_slug}")
        seed_json_path = extract_single(
            txt_path=focus_txt,
            json_dir=json_dir,
            prefijo=prefijo,
            estado_nombre=entry["estado_nom"],
            pdf_fallback=False,
        )
        if seed_json_path is None or not seed_json_path.exists():
            print(f"  [ERROR] extract_single no produjo JSON; abortando este PDF")
            total_skipped += 1
            continue

        seed_doc = json.loads(seed_json_path.read_text(encoding="utf-8"))
        print(f"  seed JSON: {seed_json_path.name}")

        # 4. Replicar el predial extraído a cada año target
        n_w, n_p = _propagate_json_to_years(
            source_json=seed_doc,
            estado_slug=estado_slug,
            prefijo=prefijo,
            muni_slug=muni_slug,
            cvegeo=cvegeo,
            source_pdf=pdf_name,
            target_anios=target_anios,
            extra_comentario=entry.get("comentario_extra", ""),
            dry_run=False,
        )
        total_written += n_w
        total_preserved += n_p

    print()
    print(f"=== Total escritos: {total_written}, "
          f"preservados: {total_preserved}, saltados: {total_skipped} ===")


if __name__ == "__main__":
    main()
