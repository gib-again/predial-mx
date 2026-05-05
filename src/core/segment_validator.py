"""
Validación y auditoría de cobertura de la etapa de segmentación.

Genera un CSV que cruza el catálogo INEGI de municipios con segment.csv
(o predial_sections.csv) para identificar municipio-años no segmentados,
segmentados vía fallback, o ausentes del master.

Soporta 4 formatos de segmentación:
  - Estándar (GTO, OAX, YUC, TAMPS): segment.csv con ejercicio, slug, predial_found
  - Jalisco: segment.csv con anio, municipio (sin slug)
  - Coahuila: predial_sections.csv con nom_mun, ejercicio, predial_status
  - Querétaro: predial_sections.csv con municipio_slug, ejercicio, status

Uso:
    python -m scripts.run_pipeline {estado} --steps segment-audit
"""

import csv
from difflib import SequenceMatcher
from pathlib import Path

from src.core.text_utils import slugify


# ── CVE_ENT por estado ──
_ESTADO_CVE = {
    "coahuila": "05",
    "chihuahua": "08",
    "colima": "06",
    "edomex": "15",
    "guanajuato": "11",
    "jalisco": "14",
    "oaxaca": "20",
    "queretaro": "22",
    "sanluispotosi": "24",
    "sinaloa": "25",
    "sonora": "26",
    "tabasco": "27",
    "tamaulipas": "28",
    "yucatan": "31",
}

# Estados Grupo B (tarifa_base.py, sin segmentación)
_GROUP_B = {"chihuahua", "colima", "edomex", "sinaloa", "tabasco"}

# Prioridad para deduplicación: true > fallback > false
_FOUND_PRIORITY = {"true": 3, "fallback": 2, "false": 1}


def _load_inegi_municipios(estado_slug: str, catalog_path: Path | None = None) -> list[dict]:
    """Carga municipios del catálogo INEGI para un estado."""
    if catalog_path is None:
        catalog_path = Path("catalogs/municipios_inegi.csv")
    if not catalog_path.exists():
        return []

    cve_ent = _ESTADO_CVE.get(estado_slug)
    if not cve_ent:
        return []

    munis = []
    with catalog_path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("CVE_ENT") == cve_ent:
                munis.append({
                    "cve_mun": row.get("CVE_MUN", ""),
                    "nom_mun": row.get("NOM_MUN", ""),
                    "slug": slugify(row.get("NOM_MUN", "")),
                })
    return munis


def _upsert_segment(
    segments: dict[tuple[int, str], dict],
    key: tuple[int, str],
    entry: dict,
) -> None:
    """Inserta o actualiza entrada en segments, manteniendo la de mayor prioridad.

    Cuando hay múltiples filas para el mismo (ejercicio, slug) — como en Querétaro
    donde un mismo municipio-año tiene filas "ok" y "no_predial_found" — se conserva
    la fila con predial_found de mayor prioridad (true > fallback > false).
    """
    existing = segments.get(key)
    if not existing:
        segments[key] = entry
        return
    new_prio = _FOUND_PRIORITY.get(entry["predial_found"], 0)
    old_prio = _FOUND_PRIORITY.get(existing["predial_found"], 0)
    if new_prio > old_prio:
        segments[key] = entry


def _load_segment_data(meta_dir: Path) -> dict[tuple[int, str], dict]:
    """
    Carga datos de segmentación desde el CSV disponible.

    Detecta automáticamente el formato:
      1. segment.csv estándar (ejercicio, slug, predial_found, predial_method)
      2. segment.csv Jalisco (anio, municipio, predial_page_start)
      3. predial_sections.csv Coahuila (ejercicio, nom_mun, predial_status)
      4. predial_sections.csv Querétaro (ejercicio, municipio_slug, status)

    Maneja duplicados conservando la fila con mejor predial_found.

    Returns:
        dict (ejercicio, slug) → {predial_found: str, method: str, txt_chars: str}
    """
    segments: dict[tuple[int, str], dict] = {}

    # Intentar segment.csv primero, luego predial_sections.csv
    seg_csv = meta_dir / "segment.csv"
    sections_csv = meta_dir / "predial_sections.csv"

    if seg_csv.exists():
        with seg_csv.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = set(reader.fieldnames or [])

            if "ejercicio" in headers and "slug" in headers:
                # Formato estándar (GTO, OAX, YUC, TAMPS)
                for row in reader:
                    try:
                        ej = int(row.get("ejercicio", 0))
                    except (ValueError, TypeError):
                        continue
                    slug = row.get("slug", "")
                    if not ej or not slug:
                        continue

                    found_raw = row.get("predial_found", "").lower()
                    method = row.get("predial_method", "")

                    # "skipped" (TAMPS) = archivo ya existía, contar como ok
                    if found_raw in ("true", "1", "yes", "skipped"):
                        predial_found = "true"
                    elif "fallback" in found_raw or "fallback" in method.lower():
                        predial_found = "fallback"
                    else:
                        predial_found = found_raw

                    _upsert_segment(segments, (ej, slug), {
                        "predial_found": predial_found,
                        "method": method,
                        "txt_chars": row.get("txt_chars", ""),
                    })

            elif "anio" in headers and "municipio" in headers:
                # Formato Jalisco (anio, municipio, predial_page_start)
                for row in reader:
                    try:
                        ej = int(row.get("anio", 0))
                    except (ValueError, TypeError):
                        continue
                    muni_name = row.get("municipio", "")
                    if not ej or not muni_name:
                        continue
                    slug = slugify(muni_name)

                    page_start = row.get("predial_page_start", "")
                    forced_end = row.get("forced_end", "").lower()

                    if page_start and page_start.strip():
                        predial_found = "true"
                    else:
                        predial_found = "false"

                    method = "page_based"
                    if forced_end == "true":
                        method = "forced_end"

                    _upsert_segment(segments, (ej, slug), {
                        "predial_found": predial_found,
                        "method": method,
                        "txt_chars": "",
                    })

    elif sections_csv.exists():
        with sections_csv.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = set(reader.fieldnames or [])

            if "nom_mun" in headers and "predial_status" in headers:
                # Formato Coahuila
                for row in reader:
                    try:
                        ej = int(row.get("ejercicio", 0))
                    except (ValueError, TypeError):
                        continue
                    slug = slugify(row.get("nom_mun", ""))
                    if not ej or not slug:
                        continue

                    status = row.get("predial_status", "")
                    if status.startswith("ok"):
                        predial_found = "true"
                    elif "fallback" in status:
                        predial_found = "fallback"
                    else:
                        predial_found = "false"

                    _upsert_segment(segments, (ej, slug), {
                        "predial_found": predial_found,
                        "method": status,
                        "txt_chars": "",
                    })

            elif "municipio_slug" in headers and "status" in headers:
                # Formato Querétaro
                for row in reader:
                    try:
                        ej = int(row.get("ejercicio", 0))
                    except (ValueError, TypeError):
                        continue
                    slug = row.get("municipio_slug", "")
                    if not ej or not slug:
                        continue

                    status = row.get("status", "")
                    chars = row.get("predial_chars", "")

                    if status == "ok":
                        predial_found = "true"
                    elif "fallback" in status:
                        predial_found = "fallback"
                    else:
                        predial_found = "false"

                    _upsert_segment(segments, (ej, slug), {
                        "predial_found": predial_found,
                        "method": status,
                        "txt_chars": chars,
                    })

    return segments


def _build_slug_aliases(
    segments: dict[tuple[int, str], dict],
    inegi_slugs: set[str],
) -> dict[str, str]:
    """
    Construye mapa de alias: slug_segment → slug_inegi.

    Usa 3 estrategias en orden:
      1. Token subset: tokens(A) <= tokens(B) o viceversa
         (captura san_jose_iturbide → san_jose_de_iturbide)
      2. SequenceMatcher ratio >= 0.85
         (captura typos OCR, diferencias menores de spelling)
      3. Sin match → queda como orphan
    """
    aliases: dict[str, str] = {}
    seg_slugs = {s for (_, s) in segments}
    orphan_slugs = seg_slugs - inegi_slugs

    for orphan in orphan_slugs:
        o_tokens = set(orphan.split("_"))
        best_match = None
        best_score = 0.0

        for inegi_s in inegi_slugs:
            i_tokens = set(inegi_s.split("_"))

            # Estrategia 1: token subset (uno es subconjunto del otro)
            if o_tokens <= i_tokens or i_tokens <= o_tokens:
                score = SequenceMatcher(None, orphan, inegi_s).ratio()
                if score > best_score:
                    best_score = score
                    best_match = inegi_s
                continue

            # Estrategia 2: SequenceMatcher para matches cercanos
            score = SequenceMatcher(None, orphan, inegi_s).ratio()
            if score >= 0.85 and score > best_score:
                best_score = score
                best_match = inegi_s

        if best_match:
            aliases[orphan] = best_match

    return aliases


def generate_segment_coverage(
    estado_slug: str,
    meta_dir: Path,
    ejercicio_range: range,
    catalog_path: Path | None = None,
) -> Path:
    """
    Genera segment_coverage.csv cruzando INEGI × años × segment data.

    La fuente de verdad es segment.csv / predial_sections.csv.
    No usa JSONs como fuente de verdad.

    Args:
        estado_slug: Slug del estado (ej: "guanajuato")
        meta_dir: Directorio meta/ del estado
        ejercicio_range: Rango de ejercicios fiscales esperados
        catalog_path: Ruta al catálogo INEGI (default: catalogs/municipios_inegi.csv)

    Returns:
        Ruta al CSV generado: meta_dir/segment_coverage.csv
    """
    # Grupo B: sin segmentación
    if estado_slug in _GROUP_B:
        print(f"\n  {estado_slug}: Grupo B (tarifa_base.py) — sin segmentacion de PDFs.")
        out_path = meta_dir / "segment_coverage.csv"
        return out_path

    munis = _load_inegi_municipios(estado_slug, catalog_path)
    segments = _load_segment_data(meta_dir)

    if not segments:
        print(f"\n  [WARN] No se encontro segment data en {meta_dir}")

    out_path = meta_dir / "segment_coverage.csv"
    meta_dir.mkdir(parents=True, exist_ok=True)

    # Contadores para resumen
    n_ok = 0
    n_fallback = 0
    n_not_found = 0
    n_not_segmented = 0
    n_extra = 0
    total_expected = 0

    # Slugs esperados según INEGI
    inegi_slugs = {m["slug"] for m in munis}

    # Construir alias de slugs para resolver mismatches
    slug_aliases = _build_slug_aliases(segments, inegi_slugs)

    rows = []

    # Para cada municipio × año esperado
    for muni in munis:
        for ejercicio in ejercicio_range:
            total_expected += 1
            key = (ejercicio, muni["slug"])

            # Buscar en segment data (directo o via alias inverso)
            seg_row = segments.get(key)
            if not seg_row:
                # Buscar con slugs alternativos que mapean a este INEGI slug
                for alt_slug, inegi_s in slug_aliases.items():
                    if inegi_s == muni["slug"]:
                        seg_row = segments.get((ejercicio, alt_slug))
                        if seg_row:
                            break

            if seg_row:
                method = seg_row.get("method", "")
                found = seg_row.get("predial_found", "")
                txt_chars = seg_row.get("txt_chars", "")

                if found == "fallback" or "fallback" in method.lower():
                    status = "fallback"
                    n_fallback += 1
                elif found == "true":
                    status = "ok"
                    n_ok += 1
                else:
                    status = "not_found"
                    n_not_found += 1
            else:
                method = ""
                txt_chars = ""
                status = "not_segmented"
                n_not_segmented += 1

            rows.append({
                "ejercicio": ejercicio,
                "municipio": muni["nom_mun"],
                "slug": muni["slug"],
                "cve_mun": muni["cve_mun"],
                "in_segment": "true" if seg_row else "false",
                "segment_method": method,
                "txt_chars": txt_chars,
                "status": status,
            })

    # Municipios extra (en segment pero no en INEGI, excluyendo aliased)
    aliased_slugs = set(slug_aliases.keys())
    for (ejercicio, slug), seg_row in sorted(segments.items()):
        if slug not in inegi_slugs and slug not in aliased_slugs:
            n_extra += 1
            rows.append({
                "ejercicio": ejercicio,
                "municipio": slug,
                "slug": slug,
                "cve_mun": "",
                "in_segment": "true",
                "segment_method": seg_row.get("method", ""),
                "txt_chars": seg_row.get("txt_chars", ""),
                "status": "not_in_inegi",
            })

    # Escribir CSV
    fieldnames = [
        "ejercicio", "municipio", "slug", "cve_mun",
        "in_segment", "segment_method", "txt_chars", "status",
    ]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sorted(rows, key=lambda r: (r["slug"], int(r["ejercicio"]))))

    # Imprimir resumen
    n_years = len(ejercicio_range)
    n_munis = len(munis)
    n_covered = n_ok + n_fallback
    print(f"\n  === Cobertura segmentacion {estado_slug} ===")
    print(f"  Municipios INEGI: {n_munis}")
    print(f"  Ejercicios: {ejercicio_range.start}-{ejercicio_range.stop - 1} ({n_years} anios)")
    print(f"  Esperados: {total_expected}")
    print(f"  Segmentados (ok):      {n_ok:4d} ({100 * n_ok / total_expected:.1f}%)")
    print(f"  Segmentados (fallback):{n_fallback:4d} ({100 * n_fallback / total_expected:.1f}%)")
    print(f"  En segment, no found:  {n_not_found:4d} ({100 * n_not_found / total_expected:.1f}%)")
    print(f"  No segmentados:        {n_not_segmented:4d}"
          f" ({100 * n_not_segmented / total_expected:.1f}%)")
    print(f"  --- Cobertura: {100 * n_covered / total_expected:.1f}% ---")
    if n_extra:
        print(f"  Extra (no en INEGI):   {n_extra:4d}")
    if slug_aliases:
        print(f"  Slug aliases:          {len(slug_aliases)}")
        for alt, canon in sorted(slug_aliases.items()):
            print(f"    {alt} -> {canon}")
    print(f"\n  CSV: {out_path}")

    # Municipios con peor cobertura
    muni_gaps: dict[str, int] = {}
    for r in rows:
        if r["status"] in ("not_segmented", "not_found"):
            muni_gaps[r["slug"]] = muni_gaps.get(r["slug"], 0) + 1

    if muni_gaps:
        print("\n  Top municipios con gaps:")
        for slug, gap_count in sorted(muni_gaps.items(), key=lambda x: -x[1])[:15]:
            nom = next((m["nom_mun"] for m in munis if m["slug"] == slug), slug)
            print(f"    {nom:35s} {gap_count:3d} anios faltantes")

    return out_path
