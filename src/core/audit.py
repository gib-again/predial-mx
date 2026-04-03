"""
Auditoría pre-consolidación de extracciones predial.

Fase intermedia entre validate y consolidate. Genera un reporte CSV
con todos los municipio-año que requieren revisión manual:
  - esquema_valido = false
  - tipo_esquema = desconocido
  - tasas sospechosas (sanity check)
  - fallback de segmentación (posible recorte incorrecto)

El reporte incluye una columna "auditado" que el investigador llena
manualmente (ok | corregido | excluir | pendiente). La consolidación
solo procede cuando no hay filas "pendiente".

Uso:
  python -m scripts.run_pipeline {estado} --steps audit

Genera:
  data/{estado}/qa/audit_{PREFIJO}.csv

Flujo:
  1. Primera corrida: genera el CSV con todas las filas en "pendiente"
  2. El investigador revisa, corrige JSONs, y actualiza la columna "auditado"
  3. Re-correr audit: actualiza el CSV preservando las marcas manuales
  4. Consolidación: lee el CSV y excluye/incluye según la columna "auditado"
"""

from __future__ import annotations

import csv
import json
from pathlib import Path


def _load_existing_audit(audit_csv: Path) -> dict[str, dict]:
    """Carga auditoría existente indexada por (ejercicio, slug)."""
    if not audit_csv.exists():
        return {}
    existing = {}
    with audit_csv.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            key = f"{row.get('ejercicio', '')}_{row.get('slug', '')}"
            existing[key] = row
    return existing


def _sanity_check(data: dict) -> list[str]:
    """Retorna lista de problemas detectados."""
    issues = []
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


def classify_error(
    issues: list[str],
    segment_method: str,
    tipo_esquema: str,
    esquema_valido: bool,
) -> tuple[str, str, str, str]:
    """
    Clasifica el error y recomienda acción correctiva.

    Returns:
        (error_class, error_detail, action, action_detail)
    """
    # 1. Error de segmentación
    if "fallback" in segment_method.lower():
        return (
            "segment",
            f"Segmentacion fallback: {segment_method}",
            "re_segment",
            "Re-segmentar con regex mejorados o LLM localizador",
        )

    # 2. Schema inválido / desconocido
    if tipo_esquema == "desconocido" or not esquema_valido:
        return (
            "schema",
            f"Esquema {tipo_esquema}, valido={esquema_valido}",
            "re_extract",
            "Re-extraer: intentar TXT extendido o PDF vision",
        )

    # 3. Valores inconsistentes (tasas)
    value_flags = [i for i in issues if "tasa" in i or "monto" in i or "cero" in i]
    if value_flags:
        return (
            "value",
            f"Valores sospechosos: {'; '.join(value_flags)}",
            "review",
            "Verificar valores contra PDF original",
        )

    # 4. Tablas vacías
    empty_flags = [i for i in issues if "vacia" in i]
    if empty_flags:
        return (
            "schema",
            f"Tabla esperada vacia: {'; '.join(empty_flags)}",
            "re_extract",
            "Re-extraer: posible truncamiento de texto",
        )

    # 5. Inconsistencia interanual
    inter_flags = [i for i in issues if "cambio" in i or "brusco" in i]
    if inter_flags:
        return (
            "interanual",
            f"Cambio interanual: {'; '.join(inter_flags)}",
            "review",
            "Comparar con anio anterior/posterior en PDF",
        )

    # 6. Otros issues
    if issues:
        return (
            "other",
            "; ".join(issues),
            "review",
            "Revisar manualmente",
        )

    # 7. Sin errores
    return ("none", "", "ok", "")


def run_audit(
    json_dir: Path,
    prefijo: str,
    qa_dir: Path,
    meta_dir: Path | None = None,
) -> Path:
    """
    Genera o actualiza el reporte de auditoría.

    Preserva marcas manuales existentes en la columna "auditado".
    """
    qa_dir.mkdir(parents=True, exist_ok=True)
    audit_csv = qa_dir / f"audit_{prefijo}.csv"

    # Cargar marcas existentes
    existing = _load_existing_audit(audit_csv)
    if existing:
        print(f"  Auditoría existente: {len(existing)} registros cargados")

    # Cargar segment.csv para info de método de detección
    segment_info: dict[str, str] = {}
    if meta_dir:
        seg_csv = meta_dir / "segment.csv"
        if seg_csv.exists():
            with seg_csv.open(encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    txt = row.get("txt_file", "").replace(".txt", "")
                    method = row.get("predial_method", "")
                    segment_info[txt] = method

    # Cargar prompt_log para hash
    prompt_info: dict[str, str] = {}
    if meta_dir:
        prompt_csv = meta_dir / f"prompt_log_{prefijo}.csv"
        if prompt_csv.exists():
            with prompt_csv.open(encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    key = f"{row.get('ejercicio', '')}_{row.get('slug', '')}"
                    prompt_info[key] = row.get("prompt_hash", "")

    # Escanear todos los JSONs
    pattern = f"{prefijo}_PREDIAL_*.json"
    json_files = sorted(json_dir.rglob(pattern))

    if not json_files:
        print(f"  No se encontraron JSONs con patrón '{pattern}'")
        return audit_csv

    rows: list[dict] = []
    stats = {"total": 0, "ok": 0, "issues": 0, "pendiente": 0}

    for jf in json_files:
        stats["total"] += 1

        # Parsear nombre: PREFIJO_PREDIAL_ANIO_SLUG.json
        parts = jf.stem.split("_", 3)  # PREFIJO, PREDIAL, ANIO, SLUG
        if len(parts) < 4:
            continue
        anio = parts[2]
        slug = "_".join(parts[3:])
        key = f"{anio}_{slug}"

        # Leer JSON
        try:
            data = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            rows.append({
                "ejercicio": anio, "slug": slug,
                "tipo_esquema": "", "esquema_valido": "",
                "fuente": "", "prompt_hash": "",
                "segment_method": "", "issues": "json_parse_error",
                "auditado": existing.get(key, {}).get("auditado", "pendiente"),
                "notas": existing.get(key, {}).get("notas", ""),
            })
            stats["issues"] += 1
            continue

        predial = data.get("predial", {})
        meta = data.get("_meta", {})
        issues = _sanity_check(data)

        # Info de segmentación
        txt_stem = jf.stem  # same as TXT stem
        seg_method = segment_info.get(txt_stem, "")
        is_fallback = "fallback" in seg_method

        if is_fallback:
            issues.append(f"segment_fallback:{seg_method}")

        # Clasificar error y acción recomendada
        tipo = predial.get("tipo_esquema", "")
        valido = predial.get("esquema_valido", False)
        error_class, error_detail, action, action_detail = classify_error(
            issues, seg_method, tipo, valido,
        )

        # Determinar estado de auditoría
        prev = existing.get(key, {})
        if issues:
            auditado = prev.get("auditado", "pendiente")
            stats["issues"] += 1
            if auditado == "pendiente":
                stats["pendiente"] += 1
        else:
            auditado = prev.get("auditado", "ok")
            stats["ok"] += 1

        rows.append({
            "ejercicio": anio,
            "slug": slug,
            "tipo_esquema": tipo,
            "esquema_valido": valido,
            "fuente": meta.get("fuente", ""),
            "prompt_hash": meta.get("prompt_hash", prompt_info.get(key, "")),
            "segment_method": seg_method,
            "error_class": error_class,
            "error_detail": error_detail,
            "issues": "; ".join(issues) if issues else "",
            "action": action,
            "action_detail": action_detail,
            "auditado": auditado,
            "notas": prev.get("notas", ""),
        })

    # Ordenar por ejercicio, slug
    rows.sort(key=lambda r: (r["ejercicio"], r["slug"]))

    # Escribir CSV
    fieldnames = [
        "ejercicio", "slug", "tipo_esquema", "esquema_valido",
        "fuente", "prompt_hash", "segment_method",
        "error_class", "error_detail", "issues",
        "action", "action_detail",
        "auditado", "notas",
    ]
    with audit_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Resumen
    issues_only = [r for r in rows if r["issues"]]
    print(f"\n  ── Auditoría {prefijo} ──")
    print(f"  Total JSONs       : {stats['total']}")
    print(f"  Sin issues        : {stats['ok']}")
    print(f"  Con issues        : {len(issues_only)}")
    print(f"  Pendientes revisión: {stats['pendiente']}")
    print(f"  Reporte: {audit_csv}")

    if issues_only:
        # Desglose de issues
        from collections import Counter
        issue_counts = Counter()
        for r in issues_only:
            for iss in r["issues"].split("; "):
                if iss:
                    # Agrupar por tipo base (sin índice de fila)
                    base = iss.split("_fila_")[0] if "_fila_" in iss else iss
                    base = base.split(":")[0] if ":" in base else base
                    issue_counts[base] += 1
        print("\n  Desglose de issues:")
        for iss, count in issue_counts.most_common():
            print(f"    {iss}: {count}")

    # Gate check: ¿se puede proceder a consolidación?
    pending = sum(1 for r in rows if r["issues"] and r["auditado"] == "pendiente")
    if pending > 0:
        print(f"\n  ⚠ {pending} municipio-año pendientes de revisar.")
        print("  Consolidación bloqueada hasta que se auditen.")
    else:
        print("\n  ✓ Todos los issues han sido auditados. Consolidación habilitada.")

    return audit_csv
