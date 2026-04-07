"""
Auditoría exhaustiva pre-consolidación de extracciones predial.

Genera un CSV con UNA FILA por cada (municipio × año) del catálogo INEGI,
cruzando tres fuentes:
  1. Catálogo INEGI de municipios
  2. segment.csv / predial_sections.csv (info de segmentación)
  3. json_predial/ (JSONs extraídos + sanity checks)

Las filas sin JSON ni segmento aparecen con error_class="missing",
permitiendo que el asistente anote las páginas del PDF original
para re-segmentar y re-extraer.

Columnas editables por el asistente:
  - auditado: ok | corregido | re_run | excluir | pendiente
  - notas: texto libre
  - paginas_pdf: páginas del PDF original (ej: "5-8")
  - pdf_override: ruta a PDF alternativo

Uso:
  python -m scripts.run_pipeline {estado} --steps audit

Genera:
  data/{estado}/qa/audit_{PREFIJO}.csv
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from src.core.segment_validator import (
    _load_inegi_municipios,
    _load_segment_data,
    _build_slug_aliases,
    _GROUP_B,
)
from src.core.text_utils import slugify


# ── Columnas ──

FIELDNAMES = [
    "ejercicio", "slug", "cve_mun",
    "source_pdf", "focus_file",
    "tipo_esquema", "esquema_valido", "fuente",
    "segment_method",
    "error_class", "error_detail", "issues",
    "auditado", "notas", "paginas_pdf", "pdf_override",
]

# Columnas preservadas entre corridas (editadas manualmente)
_MANUAL_COLS = {"auditado", "notas", "paginas_pdf", "pdf_override"}


# ── Sanity checks ──

def _sanity_check(data: dict) -> list[str]:
    """Retorna lista de problemas detectados en un JSON extraído."""
    issues: list[str] = []
    predial = data.get("predial", {})
    tipo = predial.get("tipo_esquema", "")

    if not predial.get("esquema_valido", False):
        issues.append("esquema_invalido")

    if tipo == "desconocido":
        issues.append("tipo_desconocido")

    if tipo == "tarifa_millar":
        for i, fila in enumerate(predial.get("tabla_tarifa_millar", [])):
            tasa = fila.get("tasa_millar")
            if tasa is not None:
                if tasa == 0:
                    issues.append(f"tasa_cero_fila_{i}")
                elif tasa > 50:
                    issues.append(f"tasa_alta_{tasa}_fila_{i}")

    if tipo == "progresivo" and not predial.get("tabla_progresiva"):
        issues.append("tabla_progresiva_vacia")

    if tipo == "mixto" and not predial.get("tabla_mixta_rango"):
        issues.append("tabla_mixta_vacia")

    return issues


# ── Clasificación de errores ──

def classify_error(
    issues: list[str],
    segment_method: str,
    tipo_esquema: str,
    esquema_valido: bool,
    has_json: bool = True,
    has_focus: bool = True,
) -> tuple[str, str]:
    """
    Clasifica el error y genera detalle legible.

    Returns:
        (error_class, error_detail)
    """
    # 0. Missing — ni JSON ni focus
    if not has_json and not has_focus:
        return ("missing", "No hay TXT/JSON — no se segmentó o extrajo")

    # 1. Error de segmentación
    if "fallback" in segment_method.lower():
        return (
            "segment",
            f"Segmentacion fallback: {segment_method}",
        )

    # 2. Schema inválido / desconocido
    if tipo_esquema == "desconocido" or not esquema_valido:
        return (
            "schema",
            f"Esquema {tipo_esquema}, valido={esquema_valido}",
        )

    # 3. Valores inconsistentes (tasas)
    value_flags = [i for i in issues if "tasa" in i or "monto" in i or "cero" in i]
    if value_flags:
        return (
            "value",
            f"Valores sospechosos: {'; '.join(value_flags)}",
        )

    # 4. Tablas vacías
    empty_flags = [i for i in issues if "vacia" in i]
    if empty_flags:
        return (
            "schema",
            f"Tabla esperada vacia: {'; '.join(empty_flags)}",
        )

    # 5. Otros issues
    if issues:
        return ("other", "; ".join(issues))

    # 6. Sin errores
    return ("none", "")


# ── Carga enriquecida de segment data ──

def _load_segment_data_rich(
    meta_dir: Path,
) -> dict[tuple[int, str], dict]:
    """
    Carga segment data con campos adicionales: source_pdf, txt_file, page_start/end.

    Returns:
        dict (ejercicio, slug) → {predial_found, method, txt_chars,
                                   source_pdf, txt_file, page_start, page_end}
    """
    segments: dict[tuple[int, str], dict] = {}

    seg_csv = meta_dir / "segment.csv"
    sections_csv = meta_dir / "predial_sections.csv"

    def _upsert(key, entry):
        existing = segments.get(key)
        prio = {"true": 3, "fallback": 2, "false": 1}
        if not existing:
            segments[key] = entry
        elif prio.get(entry["predial_found"], 0) > prio.get(
            existing["predial_found"], 0
        ):
            segments[key] = entry

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

                    if found_raw in ("true", "1", "yes", "skipped"):
                        predial_found = "true"
                    elif "fallback" in found_raw or "fallback" in method.lower():
                        predial_found = "fallback"
                    else:
                        predial_found = found_raw

                    _upsert((ej, slug), {
                        "predial_found": predial_found,
                        "method": method,
                        "txt_chars": row.get("txt_chars", ""),
                        "source_pdf": row.get("source_pdf", ""),
                        "txt_file": row.get("txt_file", ""),
                        "page_start": row.get("predial_page_start", ""),
                        "page_end": row.get("predial_page_end", ""),
                    })

            elif "anio" in headers and "municipio" in headers:
                # Formato Jalisco
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

                    if page_start and page_start.strip():
                        predial_found = "true"
                    else:
                        predial_found = "false"

                    method = "page_based"
                    if row.get("forced_end", "").lower() == "true":
                        method = "forced_end"

                    _upsert((ej, slug), {
                        "predial_found": predial_found,
                        "method": method,
                        "txt_chars": "",
                        "source_pdf": row.get("pdf_used", ""),
                        "txt_file": "",
                        "page_start": page_start,
                        "page_end": row.get("predial_page_end", ""),
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

                    _upsert((ej, slug), {
                        "predial_found": predial_found,
                        "method": status,
                        "txt_chars": "",
                        "source_pdf": row.get("source_pdf", ""),
                        "txt_file": row.get("predial_txt_file", ""),
                        "page_start": row.get("predial_page_start", ""),
                        "page_end": row.get("predial_page_end", ""),
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
                    if status == "ok":
                        predial_found = "true"
                    elif "fallback" in status:
                        predial_found = "fallback"
                    else:
                        predial_found = "false"

                    _upsert((ej, slug), {
                        "predial_found": predial_found,
                        "method": status,
                        "txt_chars": row.get("predial_chars", ""),
                        "source_pdf": row.get("source_pdf", ""),
                        "txt_file": row.get("predial_txt_file", ""),
                        "page_start": "",
                        "page_end": "",
                    })

    return segments


# ── Carga de audit existente ──

def _load_existing_audit(audit_csv: Path) -> dict[str, dict]:
    """Carga auditoría existente indexada por '{ejercicio}_{slug}'."""
    if not audit_csv.exists():
        return {}
    existing = {}
    with audit_csv.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = f"{row.get('ejercicio', '')}_{row.get('slug', '')}"
            existing[key] = row
    return existing


# ── Función principal ──

def run_audit(adapter) -> Path:
    """
    Genera o actualiza el reporte de auditoría exhaustivo.

    Cruza catálogo INEGI × ejercicio_range × segment data × JSONs
    para producir una fila por cada (municipio, año) esperado.

    Preserva columnas editables de corridas anteriores.
    """
    estado_slug = adapter.slug
    prefijo = adapter.prefijo
    qa_dir = adapter.qa_dir
    meta_dir = adapter.meta_dir
    json_dir = adapter.json_dir
    focus_dir = adapter.focus_dir
    ejercicio_range = adapter.ejercicio_range

    qa_dir.mkdir(parents=True, exist_ok=True)
    audit_csv = qa_dir / f"audit_{prefijo}.csv"

    # Grupo B: sin segmentación de PDFs
    if estado_slug in _GROUP_B:
        print(f"\n  {estado_slug}: Grupo B (tarifa_base.py)")
        # Solo auditar JSONs existentes (no hay grid INEGI completo)
        return _audit_group_b(adapter, audit_csv)

    # ── 1. Cargar INEGI ──
    munis = _load_inegi_municipios(estado_slug)
    if not munis:
        print(f"  [WARN] No se encontraron municipios INEGI para {estado_slug}")
        return audit_csv

    # ── 2. Cargar segment data ──
    segments = _load_segment_data_rich(meta_dir)

    # ── 3. Escanear JSONs ──
    json_pattern = f"{prefijo}_PREDIAL_*.json"
    json_index: dict[str, tuple[Path, dict]] = {}  # key → (path, parsed_data)
    for jf in json_dir.rglob(json_pattern):
        parts = jf.stem.split("_", 3)
        if len(parts) < 4:
            continue
        anio = parts[2]
        slug = "_".join(parts[3:])
        key = f"{anio}_{slug}"
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            data = None
        json_index[key] = (jf, data)

    # ── 4. Escanear focus files ──
    focus_index: dict[str, Path] = {}
    focus_pattern = f"{prefijo}_PREDIAL_*.txt"
    for tf in focus_dir.rglob(focus_pattern):
        parts = tf.stem.split("_", 3)
        if len(parts) < 4:
            continue
        anio = parts[2]
        slug = "_".join(parts[3:])
        focus_index[f"{anio}_{slug}"] = tf

    # ── 5. Slug aliases ──
    inegi_slugs = {m["slug"] for m in munis}
    # Reutilizar _load_segment_data para aliases (usa el formato simple)
    seg_simple = _load_segment_data(meta_dir)
    slug_aliases = _build_slug_aliases(seg_simple, inegi_slugs)

    # ── 6. Cargar marcas existentes ──
    existing = _load_existing_audit(audit_csv)
    if existing:
        print(f"  Auditoria existente: {len(existing)} registros cargados")

    # ── 7. Generar grid exhaustivo ──
    rows: list[dict] = []
    stats = {"total": 0, "ok": 0, "issues": 0, "missing": 0, "pendiente": 0}

    for muni in munis:
        for ejercicio in ejercicio_range:
            stats["total"] += 1
            ej = ejercicio
            m_slug = muni["slug"]
            key = f"{ej}_{m_slug}"

            # Buscar segment data (directo o via alias)
            seg_key = (ej, m_slug)
            seg_row = segments.get(seg_key)
            if not seg_row:
                for alt_slug, inegi_s in slug_aliases.items():
                    if inegi_s == m_slug:
                        seg_row = segments.get((ej, alt_slug))
                        if seg_row:
                            break

            # Buscar JSON (directo o via alias)
            json_entry = json_index.get(key)
            if not json_entry:
                for alt_slug, inegi_s in slug_aliases.items():
                    if inegi_s == m_slug:
                        alt_key = f"{ej}_{alt_slug}"
                        json_entry = json_index.get(alt_key)
                        if json_entry:
                            break

            # Buscar focus file
            focus_path = focus_index.get(key)
            if not focus_path:
                for alt_slug, inegi_s in slug_aliases.items():
                    if inegi_s == m_slug:
                        alt_key = f"{ej}_{alt_slug}"
                        focus_path = focus_index.get(alt_key)
                        if focus_path:
                            break

            # Extraer info
            source_pdf = seg_row.get("source_pdf", "") if seg_row else ""
            seg_method = seg_row.get("method", "") if seg_row else ""
            has_json = json_entry is not None
            has_focus = focus_path is not None

            # JSON data
            tipo = ""
            valido = ""
            fuente = ""
            issues: list[str] = []

            if has_json:
                jf_path, data = json_entry
                if data is None:
                    issues.append("json_parse_error")
                    tipo = ""
                    valido = ""
                else:
                    predial = data.get("predial", {})
                    meta = data.get("_meta", {})
                    tipo = predial.get("tipo_esquema", "")
                    valido = predial.get("esquema_valido", False)
                    fuente = meta.get("fuente", "")
                    issues = _sanity_check(data)

                    # Flag fallback de segmentación
                    if seg_row and "fallback" in seg_method.lower():
                        issues.append(f"segment_fallback:{seg_method}")

            # Clasificar
            error_class, error_detail = classify_error(
                issues, seg_method, tipo,
                valido if isinstance(valido, bool) else str(valido).lower() == "true",
                has_json=has_json,
                has_focus=has_focus,
            )

            # Determinar auditado
            prev = existing.get(key, {})
            if error_class == "none":
                auditado = prev.get("auditado", "ok")
                stats["ok"] += 1
            elif error_class == "missing":
                auditado = prev.get("auditado", "pendiente")
                stats["missing"] += 1
                if auditado == "pendiente":
                    stats["pendiente"] += 1
            else:
                auditado = prev.get("auditado", "pendiente")
                stats["issues"] += 1
                if auditado == "pendiente":
                    stats["pendiente"] += 1

            rows.append({
                "ejercicio": ej,
                "slug": m_slug,
                "cve_mun": muni["cve_mun"],
                "source_pdf": source_pdf,
                "focus_file": str(focus_path) if focus_path else "",
                "tipo_esquema": tipo,
                "esquema_valido": valido,
                "fuente": fuente,
                "segment_method": seg_method,
                "error_class": error_class,
                "error_detail": error_detail,
                "issues": "; ".join(issues) if issues else "",
                "auditado": auditado,
                "notas": prev.get("notas", ""),
                "paginas_pdf": prev.get("paginas_pdf", ""),
                "pdf_override": prev.get("pdf_override", ""),
            })

    # Ordenar por slug, ejercicio
    rows.sort(key=lambda r: (r["slug"], int(r["ejercicio"])))

    # Escribir CSV
    with audit_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    # Resumen
    _print_summary(prefijo, stats, rows, audit_csv)
    return audit_csv


def _audit_group_b(adapter, audit_csv: Path) -> Path:
    """Auditoría simplificada para estados Grupo B (tarifa_base, sin segmentación)."""
    prefijo = adapter.prefijo
    json_dir = adapter.json_dir

    existing = _load_existing_audit(audit_csv)

    json_pattern = f"{prefijo}_PREDIAL_*.json"
    json_files = sorted(json_dir.rglob(json_pattern))

    if not json_files:
        print(f"  No se encontraron JSONs con patrón '{json_pattern}'")
        return audit_csv

    rows: list[dict] = []
    stats = {"total": 0, "ok": 0, "issues": 0, "missing": 0, "pendiente": 0}

    for jf in json_files:
        stats["total"] += 1
        parts = jf.stem.split("_", 3)
        if len(parts) < 4:
            continue
        anio = parts[2]
        slug = "_".join(parts[3:])
        key = f"{anio}_{slug}"

        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            data = None

        issues: list[str] = []
        tipo = ""
        valido = ""
        fuente = ""

        if data is None:
            issues.append("json_parse_error")
        else:
            predial = data.get("predial", {})
            meta = data.get("_meta", {})
            tipo = predial.get("tipo_esquema", "")
            valido = predial.get("esquema_valido", False)
            fuente = meta.get("fuente", "")
            issues = _sanity_check(data)

        error_class, error_detail = classify_error(
            issues, "", tipo,
            valido if isinstance(valido, bool) else str(valido).lower() == "true",
        )

        prev = existing.get(key, {})
        if error_class == "none":
            auditado = prev.get("auditado", "ok")
            stats["ok"] += 1
        else:
            auditado = prev.get("auditado", "pendiente")
            stats["issues"] += 1
            if auditado == "pendiente":
                stats["pendiente"] += 1

        rows.append({
            "ejercicio": anio,
            "slug": slug,
            "cve_mun": "",
            "source_pdf": "",
            "focus_file": "",
            "tipo_esquema": tipo,
            "esquema_valido": valido,
            "fuente": fuente,
            "segment_method": "",
            "error_class": error_class,
            "error_detail": error_detail,
            "issues": "; ".join(issues) if issues else "",
            "auditado": auditado,
            "notas": prev.get("notas", ""),
            "paginas_pdf": prev.get("paginas_pdf", ""),
            "pdf_override": prev.get("pdf_override", ""),
        })

    rows.sort(key=lambda r: (r["slug"], r["ejercicio"]))

    with audit_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)

    _print_summary(prefijo, stats, rows, audit_csv)
    return audit_csv


def _print_summary(
    prefijo: str, stats: dict, rows: list[dict], audit_csv: Path,
):
    """Imprime resumen de la auditoría."""
    issues_only = [r for r in rows if r["issues"] or r["error_class"] == "missing"]
    print(f"\n  -- Auditoria {prefijo} --")
    print(f"  Total filas       : {stats['total']}")
    print(f"  Sin issues        : {stats['ok']}")
    print(f"  Con issues        : {stats['issues']}")
    print(f"  Missing (sin JSON): {stats['missing']}")
    print(f"  Pendientes revision: {stats['pendiente']}")
    print(f"  Reporte: {audit_csv}")

    if issues_only:
        from collections import Counter
        issue_counts: Counter[str] = Counter()
        for r in issues_only:
            if r["error_class"] == "missing" and not r["issues"]:
                issue_counts["missing"] += 1
            for iss in r["issues"].split("; "):
                if iss:
                    base = iss.split("_fila_")[0] if "_fila_" in iss else iss
                    base = base.split(":")[0] if ":" in base else base
                    issue_counts[base] += 1
        print("\n  Desglose de issues:")
        for iss, count in issue_counts.most_common():
            print(f"    {iss}: {count}")

    # Error class breakdown
    from collections import Counter
    class_counts: Counter[str] = Counter(r["error_class"] for r in rows)
    print("\n  Por error_class:")
    for cls, count in class_counts.most_common():
        print(f"    {cls:12s} {count:5d}")

    # Gate check
    pending = sum(
        1 for r in rows
        if r["error_class"] != "none" and r["auditado"] == "pendiente"
    )
    if pending > 0:
        print(f"\n  [!] {pending} municipio-anio pendientes de revisar.")
        print("  Consolidacion bloqueada hasta que se auditen.")
    else:
        print("\n  [OK] Todos los issues han sido auditados. Consolidacion habilitada.")
