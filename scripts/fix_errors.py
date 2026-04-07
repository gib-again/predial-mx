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
            # Para re_run: también incluir filas con auditado=re_run
            if action == "re_run" and r.get("auditado") == "re_run":
                pass  # incluir
            else:
                continue
        if error_class and r.get("error_class") != error_class:
            continue
        # action filter: check both 'action' column (legacy) and 'auditado' column
        if action:
            row_action = r.get("action", "")
            row_auditado = r.get("auditado", "")
            if action == "re_run":
                # re_run is in auditado column, not action
                if row_auditado != "re_run":
                    continue
            elif row_action != action:
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


def execute_re_segment(
    rows: list[dict], adapter, dry_run: bool = True, use_llm: bool = False,
):
    """Borra TXT/PDF de focus y re-ejecuta segmentación para las filas indicadas.

    Si use_llm=True, intenta localizar la sección predial con el LLM locator
    (gpt-4.1-mini) en vez de re-correr el pipeline de regex completo.
    """
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

    label = "re-segmentar (LLM locator)" if use_llm else "re-segmentar"
    print(f"\n  Archivos a {label}: {len(targets)}")
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
        print(f"\n  [DRY RUN] Usa --execute para borrar y {label}.")
        print("  Esto borrara TXT + PDF de focus_predial Y el JSON correspondiente.")
        return

    if use_llm:
        _re_segment_with_llm(targets, adapter)
    else:
        deleted = 0
        for _anio, _slug, txt, pdf, js in targets:
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


def _re_segment_with_llm(targets: list, adapter):
    """Usa el LLM locator para re-localizar la sección predial."""
    from src.core.llm_locator import locate_predial_llm

    estado_slug = adapter.slug
    log_dir = adapter.meta_dir
    ok = 0
    fail = 0

    for anio, slug, txt_path, pdf_path, json_path in targets:
        # Leer texto completo actual
        if not txt_path.exists():
            print(f"    {anio}/{slug}: TXT no existe, skip")
            fail += 1
            continue

        texto = txt_path.read_text(encoding="utf-8", errors="ignore")
        if not texto.strip():
            print(f"    {anio}/{slug}: TXT vacio, skip")
            fail += 1
            continue

        loc = locate_predial_llm(
            text=texto,
            municipio=slug,
            ejercicio=int(anio),
            estado=estado_slug,
            log_dir=log_dir,
        )

        if loc.found and loc.confidence >= 0.6:
            # Reescribir TXT con sección localizada
            section = texto[loc.start_char:loc.end_char]
            txt_path.write_text(section, encoding="utf-8")
            # Borrar JSON para forzar re-extracción
            if json_path.exists():
                json_path.unlink()
            ok += 1
            print(
                f"    {anio}/{slug}: LLM locator OK "
                f"({loc.confidence:.0%}, {len(section)} chars)"
            )
        else:
            fail += 1
            print(
                f"    {anio}/{slug}: LLM locator no encontro seccion "
                f"(conf={loc.confidence:.0%})"
            )

    print(f"\n  LLM locator: {ok} OK, {fail} fallidos")


def execute_re_run(rows: list[dict], adapter, dry_run: bool = True):
    """
    Para filas con auditado=re_run: extrae las páginas indicadas del PDF original
    a focus_predial/, borra JSON existente, y re-ejecuta extracción LLM.

    El asistente debe haber anotado:
      - paginas_pdf: rango de páginas (ej: "5-8", "12-15")
      - pdf_override (opcional): ruta a un PDF alternativo
    """
    import fitz

    prefijo = adapter.prefijo
    focus_dir = adapter.focus_dir
    json_dir = adapter.json_dir

    targets = []
    skipped = 0
    for r in rows:
        anio = r["ejercicio"]
        slug = r["slug"]
        paginas = r.get("paginas_pdf", "").strip()
        pdf_over = r.get("pdf_override", "").strip()
        source = r.get("source_pdf", "").strip()

        if not paginas:
            print(f"    {anio}/{slug}: sin paginas_pdf, omitido")
            skipped += 1
            continue

        # Resolver PDF fuente
        pdf_path_str = pdf_over or source
        if not pdf_path_str:
            print(f"    {anio}/{slug}: sin source_pdf ni pdf_override, omitido")
            skipped += 1
            continue

        pdf_path = Path(pdf_path_str)
        # Si es nombre de archivo relativo, buscar en pdf_raw/ o pdf_ocr/
        if not pdf_path.is_absolute() or not pdf_path.exists():
            for search_dir in [adapter.pdf_ocr_dir, adapter.pdf_raw_dir]:
                candidate = search_dir / str(anio) / pdf_path.name
                if candidate.exists():
                    pdf_path = candidate
                    break
                # Buscar recursivamente
                found = list(search_dir.rglob(pdf_path.name))
                if found:
                    pdf_path = found[0]
                    break

        if not pdf_path.exists():
            print(f"    {anio}/{slug}: PDF no encontrado: {pdf_path_str}")
            skipped += 1
            continue

        # Parsear páginas (1-based)
        page_start, page_end = _parse_page_range(paginas)
        if page_start is None:
            print(f"    {anio}/{slug}: formato de paginas_pdf inválido: '{paginas}'")
            skipped += 1
            continue

        base = f"{prefijo}_PREDIAL_{anio}_{slug}"
        out_txt = focus_dir / str(anio) / f"{base}.txt"
        out_pdf = focus_dir / str(anio) / f"{base}.pdf"
        json_path = json_dir / str(anio) / f"{base}.json"

        targets.append({
            "anio": anio, "slug": slug,
            "pdf_path": pdf_path,
            "page_start": page_start, "page_end": page_end,
            "out_txt": out_txt, "out_pdf": out_pdf, "json_path": json_path,
        })

    print(f"\n  Archivos para re_run: {len(targets)} ({skipped} omitidos)")
    for t in targets:
        exists_parts = []
        if t["out_txt"].exists():
            exists_parts.append("TXT")
        if t["out_pdf"].exists():
            exists_parts.append("PDF")
        if t["json_path"].exists():
            exists_parts.append("JSON")
        files = ", ".join(exists_parts) if exists_parts else "ninguno"
        print(
            f"    {t['anio']}/{t['slug']}: pp.{t['page_start']}-{t['page_end']} "
            f"de {t['pdf_path'].name} ({files})"
        )

    if dry_run:
        print("\n  [DRY RUN] Usa --execute para re-segmentar y re-extraer.")
        return

    # Ejecutar
    ok = 0
    for t in targets:
        try:
            t["out_txt"].parent.mkdir(parents=True, exist_ok=True)
            t["out_pdf"].parent.mkdir(parents=True, exist_ok=True)

            with fitz.open(str(t["pdf_path"])) as doc:
                n_pages = doc.page_count
                start_idx = max(0, t["page_start"] - 1)
                end_idx = min(t["page_end"] - 1, n_pages - 1)
                if start_idx > end_idx:
                    start_idx = end_idx

                # Generar PDF recortado
                new_doc = fitz.open()
                new_doc.insert_pdf(doc, from_page=start_idx, to_page=end_idx)
                new_doc.save(str(t["out_pdf"]), deflate=True)
                new_doc.close()

                # Generar TXT
                texts = [
                    doc[i].get_text("text") or ""
                    for i in range(start_idx, end_idx + 1)
                ]

            full_text = "\n\n" + ("\n\n" + "-" * 40 + "\n\n").join(texts) + "\n\n"
            t["out_txt"].write_text(full_text, encoding="utf-8")

            # Borrar JSON para forzar re-extracción
            if t["json_path"].exists():
                t["json_path"].unlink()

            ok += 1
            print(f"    {t['anio']}/{t['slug']}: OK")

        except Exception as e:
            print(f"    {t['anio']}/{t['slug']}: ERROR: {e}")

    print(f"\n  Re-segmentados: {ok}/{len(targets)}")

    if ok > 0:
        print("  Re-ejecutando extraccion LLM...")
        adapter.run_llm_extraction(batch_mode=False)
        print("  Listo. Corre audit de nuevo para actualizar el reporte.")


def _parse_page_range(s: str) -> tuple[int | None, int | None]:
    """
    Parsea un rango de páginas: "5-8" → (5, 8), "12" → (12, 12).
    Soporta "5,7,12" → (5, 12) como rango mínimo-máximo.
    """
    s = s.strip()
    if not s:
        return None, None

    import re
    # Rango: "5-8"
    m = re.match(r"^(\d+)\s*[-–]\s*(\d+)$", s)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Página única: "12"
    m = re.match(r"^(\d+)$", s)
    if m:
        n = int(m.group(1))
        return n, n

    # Lista: "5,7,12"
    parts = re.findall(r"\d+", s)
    if parts:
        nums = [int(p) for p in parts]
        return min(nums), max(nums)

    return None, None


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
                        choices=["re_segment", "re_extract", "re_run",
                                 "manual_capture", "review", "ok"],
                        help="Filtrar por accion recomendada")
    parser.add_argument("--slug", help="Filtrar por slug de municipio")
    parser.add_argument("--year", type=int, help="Filtrar por ejercicio fiscal")
    parser.add_argument("--all-status", action="store_true",
                        help="Incluir filas ya auditadas (no solo pendientes)")
    parser.add_argument("--execute", action="store_true",
                        help="Ejecutar la correccion (borrar + re-procesar)")
    parser.add_argument("--llm-locator", action="store_true",
                        help="Usar LLM locator (gpt-4.1-mini) para re-segmentar")

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
        execute_re_segment(
            filtered, adapter, dry_run=False, use_llm=args.llm_locator,
        )
    elif action == "re_run":
        execute_re_run(filtered, adapter, dry_run=False)
    elif action == "manual_capture":
        show_for_manual_capture(filtered, adapter)
    elif action == "review":
        print("\n  'review' no tiene ejecucion automatica.")
        print("  Revisa los JSONs manualmente y actualiza la columna 'auditado' en el CSV.")
    else:
        print(f"\n  Accion '{action}' no soportada para ejecucion automatica.")


if __name__ == "__main__":
    main()
