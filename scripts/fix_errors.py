#!/usr/bin/env python3
"""
Herramienta de corrección asistida para errores detectados en auditoría.

Lee audit_{PREFIJO}.csv, filtra por tipo de error o acción, y ejecuta
la corrección correspondiente (re-segmentar, re-extraer, o mostrar
info para captura manual).

Uso:
    python -m scripts.fix_errors {estado} --show-summary
    python -m scripts.fix_errors {estado} --class segment
    python -m scripts.fix_errors {estado} --class schema
    python -m scripts.fix_errors {estado} --action re_extract
    python -m scripts.fix_errors {estado} --action re_extract --execute
    python -m scripts.fix_errors {estado} --slug leon --year 2020
"""

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

from src.estados import get_adapter


def _load_audit(audit_csv: Path) -> list[dict]:
    """Carga audit CSV como lista de dicts."""
    if not audit_csv.exists():
        print(f"  [ERROR] No existe: {audit_csv}")
        sys.exit(1)
    with audit_csv.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _filter_rows(
    rows: list[dict],
    error_class: str | None = None,
    action: str | None = None,
    slug: str | None = None,
    year: int | None = None,
    only_pending: bool = True,
) -> list[dict]:
    """Filtra filas del audit según criterios."""
    filtered = []
    for r in rows:
        if only_pending and r.get("auditado") not in ("pendiente", ""):
            continue
        if error_class and r.get("error_class") != error_class:
            continue
        if action and r.get("action") != action:
            continue
        if slug and r.get("slug") != slug:
            continue
        if year and r.get("ejercicio") != str(year):
            continue
        filtered.append(r)
    return filtered


def show_summary(rows: list[dict], prefijo: str):
    """Muestra resumen de errores pendientes."""
    pending = [r for r in rows if r.get("auditado") in ("pendiente", "")]

    if not pending:
        print(f"\n  {prefijo}: No hay errores pendientes de revision.")
        return

    print(f"\n  === Resumen de errores pendientes: {prefijo} ===")
    print(f"  Total pendientes: {len(pending)}")

    # Por error_class
    by_class = Counter(r.get("error_class", "unknown") for r in pending)
    print("\n  Por tipo de error:")
    for cls, count in by_class.most_common():
        print(f"    {cls:15s} {count:4d}")

    # Por acción recomendada
    by_action = Counter(r.get("action", "unknown") for r in pending)
    print("\n  Por accion recomendada:")
    for act, count in by_action.most_common():
        print(f"    {act:15s} {count:4d}")

    # Top municipios afectados
    by_muni = Counter(r.get("slug", "") for r in pending)
    print("\n  Top municipios con errores:")
    for muni, count in by_muni.most_common(10):
        print(f"    {muni:35s} {count:3d}")


def show_errors(rows: list[dict]):
    """Muestra detalle de errores filtrados."""
    if not rows:
        print("  No hay filas que coincidan con los filtros.")
        return

    print(f"\n  {'Ejercicio':>10} {'Slug':30s} {'Error':12s} {'Accion':15s} {'Detalle'}")
    print(f"  {'-'*10} {'-'*30} {'-'*12} {'-'*15} {'-'*40}")
    for r in rows:
        print(
            f"  {r['ejercicio']:>10} {r['slug']:30s} "
            f"{r.get('error_class', ''):12s} {r.get('action', ''):15s} "
            f"{r.get('error_detail', '')[:50]}"
        )
    print(f"\n  Total: {len(rows)} filas")


def execute_re_extract(rows: list[dict], adapter, dry_run: bool = True):
    """Borra JSONs y re-ejecuta extracción para las filas indicadas."""
    prefijo = adapter.prefijo
    json_dir = adapter.json_dir

    targets = []
    for r in rows:
        anio = r["ejercicio"]
        slug = r["slug"]
        json_name = f"{prefijo}_PREDIAL_{anio}_{slug}.json"
        json_path = json_dir / anio / json_name
        if not json_path.exists():
            json_path = json_dir / json_name  # flat layout
        targets.append((anio, slug, json_path))

    print(f"\n  Archivos a re-extraer: {len(targets)}")
    for anio, slug, jp in targets:
        exists = "existe" if jp.exists() else "NO existe"
        print(f"    {anio} {slug:30s} ({exists})")

    if dry_run:
        print("\n  [DRY RUN] Usa --execute para borrar y re-extraer.")
        return

    # Borrar JSONs existentes
    deleted = 0
    for anio, slug, jp in targets:
        if jp.exists():
            jp.unlink()
            deleted += 1
    print(f"\n  Borrados: {deleted} JSONs")

    # Re-ejecutar extracción (solo procesa los faltantes)
    print("  Re-ejecutando extraccion LLM...")
    adapter.run_llm_extraction(batch_mode=False)
    print("  Listo. Corre audit de nuevo para actualizar el reporte.")


def execute_re_segment(rows: list[dict], adapter, dry_run: bool = True):
    """Borra TXT/PDF de focus y re-ejecuta segmentación para las filas indicadas."""
    prefijo = adapter.prefijo
    focus_dir = adapter.focus_dir
    json_dir = adapter.json_dir

    targets = []
    for r in rows:
        anio = r["ejercicio"]
        slug = r["slug"]
        base = f"{prefijo}_PREDIAL_{anio}_{slug}"
        txt_path = focus_dir / anio / f"{base}.txt"
        pdf_path = focus_dir / anio / f"{base}.pdf"
        json_path = json_dir / anio / f"{base}.json"
        targets.append((anio, slug, txt_path, pdf_path, json_path))

    print(f"\n  Archivos a re-segmentar: {len(targets)}")
    for anio, slug, txt, pdf, js in targets:
        parts = []
        if txt.exists():
            parts.append("TXT")
        if pdf.exists():
            parts.append("PDF")
        if js.exists():
            parts.append("JSON")
        files = ", ".join(parts) if parts else "ninguno"
        print(f"    {anio} {slug:30s} ({files})")

    if dry_run:
        print("\n  [DRY RUN] Usa --execute para borrar y re-segmentar.")
        print("  Esto borrara TXT + PDF de focus_predial Y el JSON correspondiente.")
        return

    deleted = 0
    for anio, slug, txt, pdf, js in targets:
        for p in (txt, pdf, js):
            if p.exists():
                p.unlink()
                deleted += 1
    print(f"\n  Borrados: {deleted} archivos")

    print("  Re-ejecutando segmentacion...")
    adapter.extract_predial_sections()
    print("  Re-ejecutando extraccion LLM...")
    adapter.run_llm_extraction(batch_mode=False)
    print("  Listo. Corre audit de nuevo para actualizar el reporte.")


def show_for_manual_capture(rows: list[dict], adapter):
    """Muestra info para captura manual: ruta al PDF, plantilla JSON."""
    prefijo = adapter.prefijo

    print("\n  === Captura manual requerida ===")
    print("  Para cada caso, abre el PDF y llena el JSON manualmente.\n")

    for r in rows:
        anio = r["ejercicio"]
        slug = r["slug"]
        base = f"{prefijo}_PREDIAL_{anio}_{slug}"

        # Buscar PDF fuente
        focus_pdf = adapter.focus_dir / anio / f"{base}.pdf"
        json_path = adapter.json_dir / anio / f"{base}.json"

        print(f"  {anio} | {slug}")
        print(f"    Error: {r.get('error_detail', 'N/A')}")
        if focus_pdf.exists():
            print(f"    PDF:  {focus_pdf}")
        else:
            print(f"    PDF:  No disponible (buscar en pdf_raw/{anio}/)")
        print(f"    JSON: {json_path}")

        # Si existe JSON, mostrar esquema actual
        if json_path.exists():
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                pred = data.get("predial", {})
                print(f"    Esquema actual: {pred.get('tipo_esquema', '?')}")
            except Exception:
                print("    JSON corrupto")
        print()


def main():
    parser = argparse.ArgumentParser(
        description="Correccion asistida de errores de auditoria predial-mx",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("estado", help="Slug del estado (ej: guanajuato)")
    parser.add_argument("--show-summary", action="store_true",
                        help="Mostrar resumen de errores pendientes")
    parser.add_argument("--class", dest="error_class",
                        choices=["segment", "schema", "value", "interanual", "other"],
                        help="Filtrar por tipo de error")
    parser.add_argument("--action",
                        choices=["re_segment", "re_extract", "manual_capture", "review", "ok"],
                        help="Filtrar por accion recomendada")
    parser.add_argument("--slug", help="Filtrar por slug de municipio")
    parser.add_argument("--year", type=int, help="Filtrar por ejercicio fiscal")
    parser.add_argument("--all-status", action="store_true",
                        help="Incluir filas ya auditadas (no solo pendientes)")
    parser.add_argument("--execute", action="store_true",
                        help="Ejecutar la correccion (borrar + re-procesar)")

    args = parser.parse_args()
    adapter = get_adapter(args.estado)
    audit_csv = adapter.qa_dir / f"audit_{adapter.prefijo}.csv"
    rows = _load_audit(audit_csv)

    if args.show_summary:
        show_summary(rows, adapter.prefijo)
        return

    # Filtrar
    filtered = _filter_rows(
        rows,
        error_class=args.error_class,
        action=args.action,
        slug=args.slug,
        year=args.year,
        only_pending=not args.all_status,
    )

    if not args.error_class and not args.action and not args.slug and not args.year:
        show_summary(rows, adapter.prefijo)
        return

    # Mostrar errores filtrados
    show_errors(filtered)

    if not args.execute:
        return

    # Ejecutar corrección según acción
    action = args.action
    if not action:
        # Inferir de las filas filtradas
        actions = {r.get("action") for r in filtered}
        if len(actions) == 1:
            action = actions.pop()
        else:
            print(f"\n  Multiples acciones en la seleccion: {actions}")
            print("  Usa --action para especificar cual ejecutar.")
            return

    if action == "re_extract":
        execute_re_extract(filtered, adapter, dry_run=False)
    elif action == "re_segment":
        execute_re_segment(filtered, adapter, dry_run=False)
    elif action == "manual_capture":
        show_for_manual_capture(filtered, adapter)
    elif action == "review":
        print("\n  'review' no tiene ejecucion automatica.")
        print("  Revisa los JSONs manualmente y actualiza la columna 'auditado' en el CSV.")
    else:
        print(f"\n  Accion '{action}' no soportada para ejecucion automatica.")


if __name__ == "__main__":
    main()
