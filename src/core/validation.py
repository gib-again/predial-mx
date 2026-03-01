"""
Validación estructural e interanual de JSONs de predial.

Generaliza 25_json_consistency.py:
  - Acepta prefijo como parámetro (ya no hardcoded a "COAH")
  - Soporta los tipos de esquema nuevos (tasa_unica, cuota_fija, mixto)
  - Agrega reglas interanuales más robustas:
    * Continuidad de tipo_esquema (no solo progresivo)
    * Cambio brusco en número de rangos/filas
"""

import csv
import json
from pathlib import Path

from src.core.text_utils import parse_predial_filename, parse_monto_to_float

# ── Constantes para validación de rangos progresivos ──

STEP = 0.01   # tamaño esperado entre rangos (lo = prev_sup + STEP)
EPS  = 1e-4   # tolerancia numérica

# Tipos de esquema válidos (expandidos)
ALLOWED_TIPOS = {
    "tarifa_millar", "progresivo", "tasa_unica",
    "cuota_fija", "mixto", "desconocido",
}


# ── Verificación estructural de un JSON ──

def check_predial_structure(predial: dict) -> dict:
    """
    Revisa un dict 'predial' y devuelve un dict con:
      - tipo_esquema
      - esquema_valido
      - n_tarifa_rows, n_prog_rows, n_tasa_unica_rows, n_cuota_fija_rows
      - anomalias (lista de strings)

    No revisa reglas interanuales (eso se hace después).
    """
    anomalias = []

    tipo = predial.get("tipo_esquema")
    esquema_valido = predial.get("esquema_valido")

    if tipo not in ALLOWED_TIPOS:
        anomalias.append("tipo_esquema_invalido")

    if not isinstance(esquema_valido, bool):
        anomalias.append("esquema_valido_no_bool")

    # Extraer tablas con validación de tipo
    tabla_tarifa = predial.get("tabla_tarifa_millar", [])
    tabla_prog = predial.get("tabla_progresiva", [])
    tabla_tasa_u = predial.get("tabla_tasa_unica", [])
    tabla_cuota_f = predial.get("tabla_cuota_fija", [])
    tabla_mixta = predial.get("tabla_mixta_rango", [])

    for nombre, tabla in [
        ("tabla_tarifa_millar", tabla_tarifa),
        ("tabla_progresiva", tabla_prog),
        ("tabla_tasa_unica", tabla_tasa_u),
        ("tabla_cuota_fija", tabla_cuota_f),
        ("tabla_mixta_rango", tabla_mixta),
    ]:
        if not isinstance(tabla, list):
            anomalias.append(f"{nombre}_no_lista")

    # Forzar a lista para conteos seguros
    if not isinstance(tabla_tarifa, list):
        tabla_tarifa = []
    if not isinstance(tabla_prog, list):
        tabla_prog = []
    if not isinstance(tabla_tasa_u, list):
        tabla_tasa_u = []
    if not isinstance(tabla_cuota_f, list):
        tabla_cuota_f = []
    if not isinstance(tabla_mixta, list):
        tabla_mixta = []

    n_tarifa = len(tabla_tarifa)
    n_prog = len(tabla_prog)
    n_tasa_u = len(tabla_tasa_u)
    n_cuota_f = len(tabla_cuota_f)
    n_mixta = len(tabla_mixta)

    # ── Coherencia tipo_esquema vs tablas ──
    if tipo == "tarifa_millar":
        if n_tarifa == 0:
            anomalias.append("tipo_tarifa_millar_sin_filas")
        if n_prog > 0:
            anomalias.append("tipo_tarifa_millar_con_tabla_progresiva_no_vacia")
        if n_tasa_u > 0:
            anomalias.append("tipo_tarifa_millar_con_tabla_tasa_unica_no_vacia")
        if n_cuota_f > 0:
            anomalias.append("tipo_tarifa_millar_con_tabla_cuota_fija_no_vacia")
            # Dentro de check_predial_structure, en el bloque tipo == "tarifa_millar":
        for fila in tabla_tarifa:
            cfa = fila.get("cuota_fija_adicional")
            if cfa is not None:
                if not isinstance(cfa, dict):
                    anomalias.append("cuota_fija_adicional_no_dict")
                elif "monto" not in cfa:
                    anomalias.append("cuota_fija_adicional_sin_monto")

    elif tipo == "progresivo":
        if n_prog == 0:
            anomalias.append("tipo_progresivo_sin_filas")
        if n_tarifa > 0:
            anomalias.append("tipo_progresivo_con_tabla_tarifa_no_vacia")
        if n_tasa_u > 0:
            anomalias.append("tipo_progresivo_con_tabla_tasa_unica_no_vacia")
        if n_cuota_f > 0:
            anomalias.append("tipo_progresivo_con_tabla_cuota_fija_no_vacia")

    elif tipo == "tasa_unica":
        if n_tasa_u == 0:
            anomalias.append("tipo_tasa_unica_sin_filas")
        if n_tarifa > 0 or n_prog > 0 or n_cuota_f > 0:
            anomalias.append("tipo_tasa_unica_con_otras_tablas_no_vacias")

    elif tipo == "cuota_fija":
        if n_cuota_f == 0:
            anomalias.append("tipo_cuota_fija_sin_filas")
        if n_tarifa > 0 or n_prog > 0 or n_tasa_u > 0:
            anomalias.append("tipo_cuota_fija_con_otras_tablas_no_vacias")

    elif tipo == "mixto":
        total_filas = n_tarifa + n_prog + n_tasa_u + n_cuota_f + n_mixta
        if total_filas == 0:
            anomalias.append("tipo_mixto_sin_tablas")
        if not predial.get("comentarios", "").strip():
            anomalias.append("tipo_mixto_sin_comentarios")

    elif tipo == "desconocido":
        total_filas = n_tarifa + n_prog + n_tasa_u + n_cuota_f + n_mixta
        if total_filas > 0:
            anomalias.append("tipo_desconocido_con_tablas_no_vacias")

    # ── Validaciones detalladas por tabla ──
    anomalias.extend(_check_tarifa_table(tabla_tarifa))
    anomalias.extend(_check_prog_table(tabla_prog))
    anomalias.extend(_check_tasa_unica_table(tabla_tasa_u))
    anomalias.extend(_check_cuota_fija_table(tabla_cuota_f))
    anomalias.extend(_check_mixta_rango_table(tabla_mixta))

    # ── minimo_predial (nuevo campo, opcional) ──
    minimo = predial.get("minimo_predial")
    has_minimo = False
    if minimo is not None:
        if isinstance(minimo, dict):
            monto = minimo.get("monto")
            if monto is not None:
                try:
                    float(monto)
                    has_minimo = True
                except (ValueError, TypeError):
                    anomalias.append("minimo_predial_monto_no_numerico")
        else:
            anomalias.append("minimo_predial_no_dict")

    return {
        "tipo_esquema": tipo,
        "esquema_valido": esquema_valido,
        "n_tarifa_rows": n_tarifa,
        "n_prog_rows": n_prog,
        "n_tasa_unica_rows": n_tasa_u,
        "n_cuota_fija_rows": n_cuota_f,
        "n_mixta_rows": n_mixta,
        "anomalias": anomalias,
    }


def _check_tarifa_table(tabla: list) -> list:
    """Validaciones detalladas para tabla_tarifa_millar."""
    anomalias = []
    for idx, row in enumerate(tabla, start=1):
        prefix = f"tarifa_row{idx}_"
        if not isinstance(row, dict):
            anomalias.append(prefix + "no_dict")
            continue

        tasa = row.get("tasa_millar")
        cuota = row.get("cuota_fija")

        if tasa is not None:
            try:
                float(tasa)
            except (ValueError, TypeError):
                anomalias.append(prefix + "tasa_millar_no_numerica")

        if cuota is not None:
            try:
                float(cuota)
            except (ValueError, TypeError):
                anomalias.append(prefix + "cuota_fija_no_numerica")

    return anomalias


def _check_prog_table(tabla: list) -> list:
    """Validaciones detalladas para tabla_progresiva (rangos, solapes, huecos)."""
    anomalias = []
    prog_rows = []

    for idx, row in enumerate(tabla, start=1):
        prefix = f"prog_row{idx}_"
        if not isinstance(row, dict):
            anomalias.append(prefix + "no_dict")
            continue

        n_rango = row.get("n_rango")
        inferior = row.get("inferior")
        superior = row.get("superior")

        n_rango_int = None
        if n_rango is not None:
            try:
                n_rango_int = int(str(n_rango))
            except (ValueError, TypeError):
                anomalias.append(prefix + "n_rango_no_int")

        if not inferior:
            anomalias.append(prefix + "inferior_vacio")

        inf_val = parse_monto_to_float(inferior)
        sup_val = parse_monto_to_float(superior)

        prog_rows.append({
            "idx": idx,
            "n_rango_int": n_rango_int,
            "inferior_val": inf_val,
            "superior_val": sup_val,
        })

    # Revisar continuidad de rangos
    if prog_rows:
        all_have_n = all(r["n_rango_int"] is not None for r in prog_rows)
        if all_have_n:
            prog_rows_sorted = sorted(prog_rows, key=lambda r: r["n_rango_int"])

            prev_sup = None
            for r in prog_rows_sorted:
                lo = r["inferior_val"]
                hi = r["superior_val"]
                idx_label = r["idx"]

                # superior null solo aceptable en último rango
                if hi is None and r != prog_rows_sorted[-1]:
                    anomalias.append(f"prog_row{idx_label}_superior_null_no_ultimo")

                if prev_sup is not None and lo is not None and hi is not None:
                    delta = lo - prev_sup
                    if delta < -STEP - EPS:
                        anomalias.append(f"prog_row{idx_label}_solape_con_anterior")
                    elif delta > STEP + EPS:
                        anomalias.append(f"prog_row{idx_label}_hueco_con_anterior")

                if hi is not None:
                    prev_sup = hi

    return anomalias


def _check_tasa_unica_table(tabla: list) -> list:
    """Validaciones para tabla_tasa_unica."""
    anomalias = []
    for idx, row in enumerate(tabla, start=1):
        prefix = f"tasa_unica_row{idx}_"
        if not isinstance(row, dict):
            anomalias.append(prefix + "no_dict")
            continue

        tasa = row.get("tasa")
        if tasa is not None:
            try:
                float(tasa)
            except (ValueError, TypeError):
                anomalias.append(prefix + "tasa_no_numerica")

        unidad = row.get("unidad", "")
        if unidad not in ("porcentaje", "al_millar", "al_millar_bimestral", ""):
            anomalias.append(prefix + "unidad_no_reconocida")

    return anomalias


def _check_cuota_fija_table(tabla: list) -> list:
    """Validaciones para tabla_cuota_fija."""
    anomalias = []
    for idx, row in enumerate(tabla, start=1):
        prefix = f"cuota_fija_row{idx}_"
        if not isinstance(row, dict):
            anomalias.append(prefix + "no_dict")
            continue

        monto = row.get("monto")
        if monto is not None:
            try:
                float(monto)
            except (ValueError, TypeError):
                anomalias.append(prefix + "monto_no_numerico")

    return anomalias


def _check_mixta_rango_table(tabla: list) -> list:
    """Validaciones para tabla_mixta_rango (multi-columna por tipo de predio)."""
    anomalias = []
    for idx, row in enumerate(tabla, start=1):
        prefix = f"mixta_row{idx}_"
        if not isinstance(row, dict):
            anomalias.append(prefix + "no_dict")
            continue

        if not row.get("inferior"):
            anomalias.append(prefix + "inferior_vacio")
        if not row.get("superior") and not row.get("n_rango"):
            anomalias.append(prefix + "superior_vacio")

        columnas = row.get("columnas")
        if not isinstance(columnas, dict) or not columnas:
            anomalias.append(prefix + "columnas_vacias")
            continue

        for col_name, col_val in columnas.items():
            if not isinstance(col_val, dict):
                anomalias.append(prefix + f"col_{col_name}_no_dict")
                continue
            valor = col_val.get("valor")
            tipo = col_val.get("tipo")
            if valor is not None:
                try:
                    float(valor)
                except (ValueError, TypeError):
                    anomalias.append(prefix + f"col_{col_name}_valor_no_numerico")
            if tipo not in ("cuota_fija", "tasa_millar", None):
                anomalias.append(prefix + f"col_{col_name}_tipo_invalido")

    return anomalias


# ── Reglas interanuales ──

def apply_interanual_rules(rows: list[dict]):
    """
    Aplica reglas interanuales a la lista de filas ya validadas.
    Modifica las anomalías in-place.

    Reglas:
    1. Continuidad de tipo_esquema: si T tiene tipo X válido, T+1 debería tener X.
    2. Cambio brusco en número de filas (ratio > 2x o < 0.5x).
    """
    # Agrupar por municipio
    by_muni: dict[str, list[dict]] = {}
    for row in rows:
        slug = row["municipio_slug"]
        by_muni.setdefault(slug, []).append(row)

    for slug, lst in by_muni.items():
        lst.sort(key=lambda r: r["anio"])

        for i in range(len(lst) - 1):
            cur = lst[i]
            nxt = lst[i + 1]

            # Regla 1: continuidad de esquema
            if (
                cur["esquema_valido"] is True
                and nxt["esquema_valido"] is True
                and cur["tipo_esquema"] != nxt["tipo_esquema"]
                and cur["tipo_esquema"] != "desconocido"
                and nxt["tipo_esquema"] != "desconocido"
            ):
                anomalias = set(nxt.get("anomalias") or [])
                anomalias.add(
                    f"cambio_esquema_{cur['tipo_esquema']}_a_{nxt['tipo_esquema']}_desde_{cur['anio']}"
                )
                nxt["anomalias"] = sorted(anomalias)

            # Regla 2: cambio brusco en número de filas
            n_cur = (cur.get("n_prog_rows") or 0) + (cur.get("n_tarifa_rows") or 0)
            n_nxt = (nxt.get("n_prog_rows") or 0) + (nxt.get("n_tarifa_rows") or 0)
            if n_cur > 0 and n_nxt > 0:
                ratio = n_nxt / n_cur
                if ratio > 2.0 or ratio < 0.5:
                    anomalias = set(nxt.get("anomalias") or [])
                    anomalias.add(f"cambio_brusco_n_filas_{n_cur}_a_{n_nxt}")
                    nxt["anomalias"] = sorted(anomalias)


# ── Función principal ──

def validate_all(
    json_dir: Path,
    prefijo: str,
    out_csv: Path,
):
    """
    Valida todos los JSONs en json_dir y genera un CSV resumen.

    Args:
        json_dir: Directorio con JSONs de salida del LLM.
        prefijo: Prefijo del estado (ej: "COAH").
        out_csv: Ruta para el CSV de resumen.
    """
    if not json_dir.exists():
        print(f"  [ERROR] No existe {json_dir}")
        return

    pattern = f"{prefijo}_PREDIAL_*.json"
    json_files = sorted(json_dir.rglob(pattern))

    if not json_files:
        print(f"  No se encontraron JSON con patrón '{pattern}' en {json_dir}")
        return

    print(f"  Encontrados {len(json_files)} JSONs de predial.")

    rows = []
    errores = 0

    for json_path in json_files:
        try:
            anio, slug, nombre_mpio = parse_predial_filename(json_path, prefijo)
        except Exception as e:
            print(f"  [SKIP] {json_path.name}: {e}")
            errores += 1
            continue

        try:
            with json_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"  [ERROR] Leyendo {json_path.name}: {e}")
            errores += 1
            continue

        predial = data.get("predial")
        if not isinstance(predial, dict):
            print(f"  [ERROR] {json_path.name}: 'predial' no es dict.")
            errores += 1
            continue

        checks = check_predial_structure(predial)

        rows.append({
            "municipio_slug": slug,
            "municipio_nombre": nombre_mpio,
            "anio": anio,
            "tipo_esquema": checks["tipo_esquema"],
            "esquema_valido": checks["esquema_valido"],
            "n_tarifa_rows": checks["n_tarifa_rows"],
            "n_prog_rows": checks["n_prog_rows"],
            "n_tasa_unica_rows": checks.get("n_tasa_unica_rows", 0),
            "n_cuota_fija_rows": checks.get("n_cuota_fija_rows", 0),
            "n_mixta_rows": checks.get("n_mixta_rows", 0),
            "anomalias": checks["anomalias"],
            "json_path": str(json_path),
        })

    # Aplicar reglas interanuales
    apply_interanual_rules(rows)

    # Escribir CSV
    out_csv.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "municipio_slug", "municipio_nombre", "anio",
        "tipo_esquema", "esquema_valido",
        "n_tarifa_rows", "n_prog_rows", "n_tasa_unica_rows", "n_cuota_fija_rows",
        "n_mixta_rows", "anomalias", "json_path",
    ]

    with out_csv.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in sorted(rows, key=lambda x: (x["municipio_slug"], x["anio"])):
            row_out = r.copy()
            anoms = row_out.get("anomalias") or []
            if isinstance(anoms, list):
                row_out["anomalias"] = "|".join(anoms)
            writer.writerow(row_out)

    # Resumen por consola
    total = len(rows)
    n_ok = sum(1 for r in rows if not r["anomalias"])
    n_anom = total - n_ok

    print(f"\n  ── Resumen validación ──")
    print(f"  Filas totales   : {total}")
    print(f"  Sin anomalías   : {n_ok}")
    print(f"  Con anomalías   : {n_anom}")
    print(f"  Errores lectura : {errores}")
    print(f"  CSV guardado en : {out_csv}")

    # Resumen por tipo de esquema
    counts: dict[str, int] = {}
    for r in rows:
        t = r.get("tipo_esquema", "?")
        counts[t] = counts.get(t, 0) + 1
    print(f"\n  Distribución de esquemas:")
    for k in sorted(counts.keys()):
        print(f"    {k}: {counts[k]}")

    # ── QA adicional (inspirado en 77_consistency_check de Querétaro) ──

    qa_dir = out_csv.parent
    _write_qa_reports(rows, qa_dir, prefijo)


def _write_qa_reports(rows: list[dict], qa_dir: Path, prefijo: str):
    """
    Genera reportes QA detallados:
      - anomalies.csv         : una fila por anomalía
      - schema_timeline.csv   : (municipio, año, esquema) para análisis visual
      - schema_switches.csv   : cambios de esquema interanuales
      - coverage_by_muni.csv  : cobertura temporal por municipio
      - stability_flags.csv   : cambios bruscos en rangos entre años consecutivos
    """
    # ── Anomalías detalladas ──
    anom_rows = []
    for r in rows:
        anoms = r.get("anomalias") or []
        if isinstance(anoms, str):
            anoms = anoms.split("|") if anoms else []
        for a in anoms:
            anom_rows.append({
                "municipio": r["municipio_slug"],
                "anio": r["anio"],
                "anomalia": a,
                "json_path": r.get("json_path", ""),
            })

    if anom_rows:
        anom_csv = qa_dir / "anomalies.csv"
        with anom_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["municipio", "anio", "anomalia", "json_path"])
            w.writeheader()
            w.writerows(anom_rows)
        print(f"  Anomalías detalladas: {len(anom_rows)} → {anom_csv}")

    # ── Schema timeline ──
    tl_csv = qa_dir / "schema_timeline.csv"
    with tl_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["municipio", "anio", "tipo_esquema", "esquema_valido"])
        w.writeheader()
        for r in sorted(rows, key=lambda x: (x["municipio_slug"], x["anio"])):
            w.writerow({
                "municipio": r["municipio_slug"],
                "anio": r["anio"],
                "tipo_esquema": r["tipo_esquema"],
                "esquema_valido": r["esquema_valido"],
            })

    # ── Schema switches (cambios de esquema) ──
    by_muni: dict[str, list[dict]] = {}
    for r in rows:
        by_muni.setdefault(r["municipio_slug"], []).append(r)

    switches = []
    for slug, lst in by_muni.items():
        lst.sort(key=lambda r: r["anio"])
        prev = None
        for r in lst:
            cur = r["tipo_esquema"]
            if (prev is not None
                    and cur != prev
                    and cur != "desconocido"
                    and prev != "desconocido"):
                switches.append({
                    "municipio": slug,
                    "anio": r["anio"],
                    "de": prev,
                    "a": cur,
                })
            prev = cur

    if switches:
        sw_csv = qa_dir / "schema_switches.csv"
        with sw_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["municipio", "anio", "de", "a"])
            w.writeheader()
            w.writerows(switches)
        print(f"  Cambios de esquema: {len(switches)} → {sw_csv}")

    # ── Cobertura por municipio ──
    # Infiere rango de años del dataset
    all_years = sorted(set(r["anio"] for r in rows))
    if all_years:
        year_min, year_max = all_years[0], all_years[-1]
        expected = set(range(year_min, year_max + 1))

        coverage_rows = []
        for slug, lst in sorted(by_muni.items()):
            got = set(r["anio"] for r in lst)
            missing = sorted(expected - got)
            coverage_rows.append({
                "municipio": slug,
                "n_years": len(got),
                "years_present": ";".join(map(str, sorted(got))),
                "n_missing": len(missing),
                "years_missing": ";".join(map(str, missing)),
            })

        cov_csv = qa_dir / "coverage_by_muni.csv"
        with cov_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "municipio", "n_years", "years_present", "n_missing", "years_missing",
            ])
            w.writeheader()
            w.writerows(coverage_rows)

        total_munis = len(coverage_rows)
        full_cov = sum(1 for r in coverage_rows if r["n_missing"] == 0)
        print(f"  Cobertura: {full_cov}/{total_munis} municipios con todos los años")
        print(f"  → {cov_csv}")

    # ── Stability flags (Querétaro-style) ──
    stability = []
    for slug, lst in by_muni.items():
        lst.sort(key=lambda r: r["anio"])
        for i in range(len(lst) - 1):
            cur, nxt = lst[i], lst[i + 1]
            # Progresiva: comparar número de rangos
            if cur["tipo_esquema"] == "progresivo" == nxt["tipo_esquema"]:
                nc = cur.get("n_prog_rows", 0)
                nn = nxt.get("n_prog_rows", 0)
                if nc > 0 and nn > 0 and abs(nc - nn) > 2:
                    stability.append({
                        "municipio": slug,
                        "anio": nxt["anio"],
                        "flag": f"prog_rowcount_jump_{nc}_to_{nn}",
                    })
            # Millar: comparar número de filas
            if cur["tipo_esquema"] == "tarifa_millar" == nxt["tipo_esquema"]:
                nc = cur.get("n_tarifa_rows", 0)
                nn = nxt.get("n_tarifa_rows", 0)
                if nc > 0 and nn > 0 and abs(nc - nn) > 2:
                    stability.append({
                        "municipio": slug,
                        "anio": nxt["anio"],
                        "flag": f"millar_rowcount_jump_{nc}_to_{nn}",
                    })

    if stability:
        stab_csv = qa_dir / "stability_flags.csv"
        with stab_csv.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["municipio", "anio", "flag"])
            w.writeheader()
            w.writerows(stability)
        print(f"  Flags de estabilidad: {len(stability)} → {stab_csv}")
