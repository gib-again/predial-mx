"""Validación de JSONs de predial vía schema_v2 (discriminated union).

Reemplaza las reglas heurísticas previas (chequeos manuales por tabla, conteos
cruzados) por validación Pydantic contra cada variante del discriminated union.
La función `reclasificar()` intenta cada variante y cae a `otro_no_clasificado`
si ninguna valida — capturando la tabla cruda y la razón.

Firmas públicas preservadas:
  - check_predial_structure(predial) -> dict
  - apply_interanual_rules(rows) -> None
  - validate_all(json_dir, prefijo, out_csv) -> None

Nueva:
  - reclasificar(predial_dict) -> variante de schema_v2
"""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Callable, Union

from pydantic import BaseModel, ValidationError

from src.core.text_utils import parse_predial_filename
from src.extraction.schema_v2 import (
    CuotaFijaEscalonadaSchema,
    CuotaFijaSimpleSchema,
    MixtoSchema,
    OtroNoClasificadoSchema,
    ProgresivoSchema,
    TarifaMillarSchema,
    TasaUnicaSchema,
)

PredialV2Variant = Union[
    TarifaMillarSchema,
    ProgresivoSchema,
    TasaUnicaSchema,
    CuotaFijaSimpleSchema,
    CuotaFijaEscalonadaSchema,
    MixtoSchema,
    OtroNoClasificadoSchema,
]


# Tipos válidos en v2 (incluye el escape hatch).
ALLOWED_TIPOS = {
    "tarifa_millar",
    "progresivo",
    "tasa_unica",
    "cuota_fija_simple",
    "cuota_fija_escalonada",
    "mixto",
    "otro_no_clasificado",
}

# Snap de huecos pequeños entre brackets (cent-gap convención mexicana).
_BRACKET_SNAP_TOLERANCE = 1.0


# ── Helpers de coerción ──

def _to_float(v):
    """Coerce string/int/float monetario a float. None → None.

    Robusta a `$`, `,`, espacios, comillas tipográficas (U+2019) y la palabra
    'adelante' (que se traduce a None).
    """
    if v is None or isinstance(v, (int, float)):
        return v
    s = (
        str(v)
        .strip()
        .replace("$", "")
        .replace(",", "")
        .replace("\u2019", "")
        .replace("'", "")
        .replace(" ", "")
    )
    if not s or "adelante" in s.lower():
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _superior_v2(s):
    """v1 'En Adelante'/'En adelante' → None; resto vía _to_float."""
    if isinstance(s, str) and "adelante" in s.lower():
        return None
    return _to_float(s)


def _n_rango_int(v) -> int:
    """v1 n_rango (str '1', 'I-1', 'a-1' o int) → int. Fallback 0 si no parseable."""
    if isinstance(v, int):
        return v
    if v is None:
        return 0
    try:
        return int(str(v))
    except ValueError:
        m = re.search(r"(\d+)$", str(v))
        return int(m.group(1)) if m else 0


def _snap_brackets(rows: list[dict]) -> None:
    """Cierra cent-gaps in-place: si |inf_next - sup| ≤ 1 peso, snapea inf_next = sup.

    Gaps grandes y solapes (gap negativo grande) se preservan para que el validador
    de schema_v2 los reporte.
    """
    for i in range(len(rows) - 1):
        sup = rows[i].get("superior")
        inf_next = rows[i + 1].get("inferior")
        if sup is None or inf_next is None:
            continue
        if abs(inf_next - sup) <= _BRACKET_SNAP_TOLERANCE:
            rows[i + 1]["inferior"] = sup


# ── Mappers v1 → v2 (uno por variante) ──

def _to_v2_tarifa_millar(p: dict) -> dict:
    return {
        "tipo_esquema": "tarifa_millar",
        "tabla": [
            {
                "grupo": r.get("grupo", "general"),
                "clave": r.get("clave", ""),
                "descripcion": r.get("descripcion", ""),
                "tasa_millar": _to_float(r.get("tasa_millar")),
                "periodicidad": r.get("periodicidad", "anual"),
                "cuota_fija_adicional": r.get("cuota_fija_adicional"),
            }
            for r in (p.get("tabla_tarifa_millar") or [])
            if isinstance(r, dict)
        ],
        "minimo_predial": p.get("minimo_predial"),
        "comentarios": p.get("comentarios", "") or "",
    }


def _to_v2_progresivo(p: dict) -> dict:
    rows: list[dict] = []
    for r in p.get("tabla_progresiva") or []:
        if not isinstance(r, dict):
            continue
        rows.append(
            {
                "n_rango": _n_rango_int(r.get("n_rango")),
                "inferior": _to_float(r.get("inferior")),
                "superior": _superior_v2(r.get("superior")),
                "cuota_fija": _to_float(r.get("cuota_fija")) or 0.0,
                "tasa_marginal": _to_float(r.get("tasa_marginal")) or 0.0,
            }
        )
    _snap_brackets(rows)
    return {
        "tipo_esquema": "progresivo",
        "tabla": rows,
        "minimo_predial": p.get("minimo_predial"),
        "comentarios": p.get("comentarios", "") or "",
    }


def _to_v2_tasa_unica(p: dict) -> dict:
    return {
        "tipo_esquema": "tasa_unica",
        "tabla": [
            {
                "descripcion": r.get("descripcion", ""),
                "tasa": _to_float(r.get("tasa")),
                "base_calculo": r.get("base_calculo", "valor_catastral"),
                "unidad": r.get("unidad", "al_millar"),
            }
            for r in (p.get("tabla_tasa_unica") or [])
            if isinstance(r, dict)
        ],
        "minimo_predial": p.get("minimo_predial"),
        "comentarios": p.get("comentarios", "") or "",
    }


def _to_v2_cuota_fija_simple(p: dict) -> dict:
    return {
        "tipo_esquema": "cuota_fija_simple",
        "tabla": [
            {
                "descripcion": r.get("descripcion", ""),
                "monto": _to_float(r.get("monto")),
                "periodicidad": r.get("periodicidad", "anual"),
                "unidad": r.get("unidad", "pesos"),
            }
            for r in (p.get("tabla_cuota_fija") or [])
            if isinstance(r, dict)
        ],
        "minimo_predial": p.get("minimo_predial"),
        "comentarios": p.get("comentarios", "") or "",
    }


def _to_v2_cuota_fija_escalonada(p: dict) -> dict:
    """Captura el bug `tipo_esquema='progresivo'` con `tasa_marginal=0` en todos
    los rows: usa `tabla_progresiva` mapeando `cuota_fija` → `monto`.

    Para v1 declared='cuota_fija' con múltiples entradas (rangos codificados en
    descripción), `tabla_progresiva` está vacía y este mapper devuelve tabla=[],
    haciendo fallar la variante. Ese caso cae a `otro_no_clasificado`.
    """
    rows: list[dict] = []
    for r in p.get("tabla_progresiva") or []:
        if not isinstance(r, dict):
            continue
        rows.append(
            {
                "n_rango": _n_rango_int(r.get("n_rango")),
                "inferior": _to_float(r.get("inferior")),
                "superior": _superior_v2(r.get("superior")),
                "monto": _to_float(r.get("cuota_fija")) or 0.0,
            }
        )
    _snap_brackets(rows)
    return {
        "tipo_esquema": "cuota_fija_escalonada",
        "tabla": rows,
        "minimo_predial": p.get("minimo_predial"),
        "comentarios": p.get("comentarios", "") or "",
    }


def _to_v2_mixto(p: dict) -> dict:
    rows: list[dict] = []
    for r in p.get("tabla_mixta_rango") or []:
        if not isinstance(r, dict):
            continue
        cols_v1 = r.get("columnas")
        if isinstance(cols_v1, dict):
            cols_v2 = [
                {
                    "nombre": k,
                    "valor": _to_float((v or {}).get("valor")) or 0.0,
                    "tipo": (v or {}).get("tipo", "tasa_millar"),
                    "unidad": (v or {}).get("unidad", "pesos"),
                }
                for k, v in cols_v1.items()
            ]
        elif isinstance(cols_v1, list):
            cols_v2 = [
                {
                    "nombre": c.get("nombre", ""),
                    "valor": _to_float(c.get("valor")) or 0.0,
                    "tipo": c.get("tipo", "tasa_millar"),
                    "unidad": c.get("unidad", "pesos"),
                }
                for c in cols_v1
                if isinstance(c, dict)
            ]
        else:
            cols_v2 = []
        rows.append(
            {
                "n_rango": _n_rango_int(r.get("n_rango")),
                "inferior": _to_float(r.get("inferior")),
                "superior": _superior_v2(r.get("superior")),
                "columnas": cols_v2,
            }
        )
    _snap_brackets(rows)
    return {
        "tipo_esquema": "mixto",
        "tabla": rows,
        "minimo_predial": p.get("minimo_predial"),
        "comentarios": p.get("comentarios", "") or "",
    }


# ── reclasificar ──

# Variantes "reales" (no escape hatch). Orden = prioridad de fallback cuando
# `declared` no coincide con ningún match. La preferencia primaria es la
# variante que coincide con el `tipo_esquema` declarado.
_VARIANT_ATTEMPTS: list[tuple[str, type[BaseModel], Callable[[dict], dict]]] = [
    ("tarifa_millar", TarifaMillarSchema, _to_v2_tarifa_millar),
    ("progresivo", ProgresivoSchema, _to_v2_progresivo),
    ("tasa_unica", TasaUnicaSchema, _to_v2_tasa_unica),
    ("cuota_fija_simple", CuotaFijaSimpleSchema, _to_v2_cuota_fija_simple),
    ("cuota_fija_escalonada", CuotaFijaEscalonadaSchema, _to_v2_cuota_fija_escalonada),
    ("mixto", MixtoSchema, _to_v2_mixto),
]


def _capture_tabla_cruda(p: dict) -> list[dict]:
    """Vuelca todas las tablas v1 no vacías como `tabla_cruda` para el escape hatch."""
    out = []
    for k in (
        "tabla_tarifa_millar",
        "tabla_progresiva",
        "tabla_tasa_unica",
        "tabla_cuota_fija",
        "tabla_mixta_rango",
    ):
        for row in p.get(k) or []:
            if isinstance(row, dict):
                out.append({"_tabla": k, **row})
            else:
                out.append({"_tabla": k, "_raw": str(row)})
    return out


def _infer_categoria(p: dict) -> str:
    """Heurística mínima para escoger la categoría del escape hatch."""
    has_any_table = any(
        len(p.get(k) or []) > 0
        for k in (
            "tabla_tarifa_millar",
            "tabla_progresiva",
            "tabla_tasa_unica",
            "tabla_cuota_fija",
            "tabla_mixta_rango",
        )
    )
    return "estructura_no_estandar" if has_any_table else "segmento_vacio"


def reclasificar(predial_dict: dict) -> PredialV2Variant:
    """Intenta validar `predial_dict` (formato v1) contra cada variante de schema_v2.

    Estrategia:
      1. Para cada variante, mapear v1→v2 y `model_validate`.
      2. Si una o más validan → preferir la que coincide con `tipo_esquema`
         declarado; si ninguna coincide, retornar la primera en orden de
         `_VARIANT_ATTEMPTS`.
      3. Si ninguna valida → retornar `OtroNoClasificadoSchema` con `categoria`,
         `descripcion_estructural` (razones) y `tabla_cruda` (volcado v1).
    """
    declared = predial_dict.get("tipo_esquema")
    matches: list[tuple[str, BaseModel]] = []
    errors: list[tuple[str, str]] = []

    for tipo, Variant, mapper in _VARIANT_ATTEMPTS:
        try:
            v2_dict = mapper(predial_dict)
        except Exception as e:
            errors.append((tipo, f"mapeo: {e}"))
            continue
        try:
            instance = Variant.model_validate(v2_dict)
            matches.append((tipo, instance))
        except ValidationError as e:
            errs = e.errors()
            msg = errs[0].get("msg", str(e))[:200] if errs else str(e)[:200]
            errors.append((tipo, msg))

    if matches:
        for tipo, inst in matches:
            if tipo == declared:
                return inst
        return matches[0][1]

    razon = "; ".join(f"{t}: {e}" for t, e in errors)
    return OtroNoClasificadoSchema(
        tipo_esquema="otro_no_clasificado",
        categoria=_infer_categoria(predial_dict),
        descripcion_estructural=(
            f"Ninguna variante validó (declared={declared!r}). Razones: {razon}"
        )[:2000],
        tabla_cruda=_capture_tabla_cruda(predial_dict),
        minimo_predial=predial_dict.get("minimo_predial"),
        comentarios=predial_dict.get("comentarios", "") or "",
    )


# ── check_predial_structure (firma v1, semántica v2) ──

def check_predial_structure(predial: dict) -> dict:
    """Valida un dict 'predial' usando schema_v2 vía `reclasificar`.

    Retorna el mismo shape que la versión v1 (preservando keys para downstream):
      tipo_esquema, esquema_valido, n_tarifa_rows, n_prog_rows, n_tasa_unica_rows,
      n_cuota_fija_rows (suma de simple + escalonada), n_mixta_rows, anomalias.

    Anomalías emitidas:
      - `reclasificado_de_X_a_Y`: el `tipo_esquema` declarado difiere del que
        realmente validó (típicamente captura el bug progresivo→cuota_fija_escalonada).
      - `otro_no_clasificado_<categoria>`: ninguna variante validó.
    """
    instance = reclasificar(predial)
    declared = predial.get("tipo_esquema")
    actual = instance.tipo_esquema

    anomalias: list[str] = []
    if isinstance(instance, OtroNoClasificadoSchema):
        anomalias.append(f"otro_no_clasificado_{instance.categoria}")
    elif declared and declared != actual:
        anomalias.append(f"reclasificado_de_{declared}_a_{actual}")

    n_tarifa = len(instance.tabla) if isinstance(instance, TarifaMillarSchema) else 0
    n_prog = len(instance.tabla) if isinstance(instance, ProgresivoSchema) else 0
    n_tasa_u = len(instance.tabla) if isinstance(instance, TasaUnicaSchema) else 0
    n_cuota_simple = len(instance.tabla) if isinstance(instance, CuotaFijaSimpleSchema) else 0
    n_cuota_esc = len(instance.tabla) if isinstance(instance, CuotaFijaEscalonadaSchema) else 0
    n_mixta = len(instance.tabla) if isinstance(instance, MixtoSchema) else 0

    return {
        "tipo_esquema": actual,
        "esquema_valido": not isinstance(instance, OtroNoClasificadoSchema),
        "n_tarifa_rows": n_tarifa,
        "n_prog_rows": n_prog,
        "n_tasa_unica_rows": n_tasa_u,
        "n_cuota_fija_rows": n_cuota_simple + n_cuota_esc,
        "n_mixta_rows": n_mixta,
        "anomalias": anomalias,
    }


# ── Reglas interanuales ──

def apply_interanual_rules(rows: list[dict]):
    """Aplica reglas interanuales a la lista de filas ya validadas.

    Modifica las anomalías in-place.

    Reglas:
      1. Continuidad de tipo_esquema entre años consecutivos del mismo municipio.
         Se omite cuando alguno de los lados es `otro_no_clasificado` (no hay
         clasificación confiable que comparar).
      2. Cambio brusco en número de filas (ratio > 2x o < 0.5x).
    """
    by_muni: dict[str, list[dict]] = {}
    for row in rows:
        slug = row["municipio_slug"]
        by_muni.setdefault(slug, []).append(row)

    for _slug, lst in by_muni.items():
        lst.sort(key=lambda r: r["anio"])

        for i in range(len(lst) - 1):
            cur = lst[i]
            nxt = lst[i + 1]

            if (
                cur["esquema_valido"] is True
                and nxt["esquema_valido"] is True
                and cur["tipo_esquema"] != nxt["tipo_esquema"]
                and cur["tipo_esquema"] != "otro_no_clasificado"
                and nxt["tipo_esquema"] != "otro_no_clasificado"
            ):
                anomalias = set(nxt.get("anomalias") or [])
                anomalias.add(
                    f"cambio_esquema_{cur['tipo_esquema']}_a_{nxt['tipo_esquema']}_desde_{cur['anio']}"
                )
                nxt["anomalias"] = sorted(anomalias)

            n_cur = (cur.get("n_prog_rows") or 0) + (cur.get("n_tarifa_rows") or 0)
            n_nxt = (nxt.get("n_prog_rows") or 0) + (nxt.get("n_tarifa_rows") or 0)
            if n_cur > 0 and n_nxt > 0:
                ratio = n_nxt / n_cur
                if ratio > 2.0 or ratio < 0.5:
                    anomalias = set(nxt.get("anomalias") or [])
                    anomalias.add(f"cambio_brusco_n_filas_{n_cur}_a_{n_nxt}")
                    nxt["anomalias"] = sorted(anomalias)


# ── Función principal ──

def validate_all(json_dir: Path, prefijo: str, out_csv: Path):
    """Valida todos los JSONs en `json_dir` y genera un CSV resumen.

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

    apply_interanual_rules(rows)

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

    total = len(rows)
    n_ok = sum(1 for r in rows if not r["anomalias"])
    n_anom = total - n_ok

    print("\n  ── Resumen validación ──")
    print(f"  Filas totales   : {total}")
    print(f"  Sin anomalías   : {n_ok}")
    print(f"  Con anomalías   : {n_anom}")
    print(f"  Errores lectura : {errores}")
    print(f"  CSV guardado en : {out_csv}")

    counts: dict[str, int] = {}
    for r in rows:
        t = r.get("tipo_esquema", "?")
        counts[t] = counts.get(t, 0) + 1
    print("\n  Distribución de esquemas:")
    for k in sorted(counts.keys()):
        print(f"    {k}: {counts[k]}")

    qa_dir = out_csv.parent
    _write_qa_reports(rows, qa_dir, prefijo)


def _write_qa_reports(rows: list[dict], qa_dir: Path, prefijo: str):
    """Genera reportes QA detallados.

    Outputs (en `qa_dir`):
      - anomalies.csv         : una fila por anomalía
      - schema_timeline.csv   : (municipio, año, esquema)
      - schema_switches.csv   : cambios de esquema interanuales
      - coverage_by_muni.csv  : cobertura temporal por municipio
      - stability_flags.csv   : cambios bruscos en rangos entre años consecutivos
    """
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

    by_muni: dict[str, list[dict]] = {}
    for r in rows:
        by_muni.setdefault(r["municipio_slug"], []).append(r)

    switches = []
    for slug, lst in by_muni.items():
        lst.sort(key=lambda r: r["anio"])
        prev = None
        for r in lst:
            cur = r["tipo_esquema"]
            if (
                prev is not None
                and cur != prev
                and cur != "otro_no_clasificado"
                and prev != "otro_no_clasificado"
            ):
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

    stability = []
    for slug, lst in by_muni.items():
        lst.sort(key=lambda r: r["anio"])
        for i in range(len(lst) - 1):
            cur, nxt = lst[i], lst[i + 1]
            if cur["tipo_esquema"] == "progresivo" == nxt["tipo_esquema"]:
                nc = cur.get("n_prog_rows", 0)
                nn = nxt.get("n_prog_rows", 0)
                if nc > 0 and nn > 0 and abs(nc - nn) > 2:
                    stability.append({
                        "municipio": slug,
                        "anio": nxt["anio"],
                        "flag": f"prog_rowcount_jump_{nc}_to_{nn}",
                    })
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
