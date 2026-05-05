"""
Fase 6: Consolidación de JSONs de todos los estados en un panel y reporte de calidad.

Lee los JSONs validados de data/{estado}/json_predial/{año}/{PREFIJO}_PREDIAL_{año}_{slug}.json
y genera:

  output/predial_panel.csv    → 1 fila por (estado, municipio, ejercicio)
  output/quality_report.csv   → Diagnóstico de calidad, cobertura y cambios interanuales

El catálogo INEGI (catalogs/municipios_inegi.csv) se usa para CVE_ENT/CVE_MUN.
Si no existe, las claves quedan vacías.

Diseño de tasa_urbano:
  La tasa más representativa para cuantificar el predial de una vivienda urbana media.
    · tarifa_millar → grupo urbano_edificado > urbano > general (al millar)
    · tasa_unica   → la tasa (convertida a al millar si viene en %)
    · progresivo   → tasa_marginal del rango mediano
    · mixto        → best-effort desde tablas disponibles
    · cuota_fija   → None (no hay tasa proporcional)
    · desconocido  → None

quality_report — reglas interanuales:
    · tasa_changed:   tasa_urbano difiere >0.1% relativo del año anterior
    · schema_changed: tipo_esquema cambió respecto al año anterior
    · rangos_changed: (solo progresivo→progresivo) n_rangos cambió
    · Para tarifa_millar: NO se flaggea agregar/quitar tipos de predio
      (solo si las tasas numéricas cambian)
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from src.core.text_utils import parse_predial_filename, parse_monto_to_float
from src.core.constants import PREFIJOS_ESTADO


# ══════════════════════════════════════════════════════════════
# Catálogo INEGI
# ══════════════════════════════════════════════════════════════

_INEGI_MAP: dict[tuple[str, str], dict] | None = None

_ESTADO_CVE = {
    "coahuila": "05",
    "guanajuato": "11",
    "jalisco": "14",
    "oaxaca": "20",
    "queretaro": "22",
    "sanluispotosi": "24",
    "sonora": "26",
    "tamaulipas": "28",
    "yucatan": "31",
}


def _load_inegi(catalog_path: Path) -> dict[tuple[str, str], dict]:
    """Carga catálogo INEGI: (cve_ent, slug_normalizado) → {cve_ent, cve_mun, nom_mun}."""
    global _INEGI_MAP
    if _INEGI_MAP is not None:
        return _INEGI_MAP

    _INEGI_MAP = {}
    if not catalog_path.exists():
        return _INEGI_MAP

    import unicodedata
    import re

    def _norm(s: str) -> str:
        s = s.strip().lower()
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
        return s

    with catalog_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            cve_ent = (row.get("CVE_ENT") or "").strip()
            cve_mun = (row.get("CVE_MUN") or "").strip()
            nom = (row.get("NOM_MUN") or "").strip()
            if cve_ent and nom:
                _INEGI_MAP[(cve_ent, _norm(nom))] = {
                    "cve_ent": cve_ent, "cve_mun": cve_mun, "nom_mun": nom,
                }

    return _INEGI_MAP


def _lookup_inegi(estado_slug: str, muni_slug: str, catalog: dict) -> tuple[str, str]:
    """Devuelve (cve_ent, cve_mun) o ('', '')."""
    cve_ent = _ESTADO_CVE.get(estado_slug, "")
    if not cve_ent:
        return "", ""
    info = catalog.get((cve_ent, muni_slug))
    return (info["cve_ent"], info["cve_mun"]) if info else (cve_ent, "")


# ══════════════════════════════════════════════════════════════
# Extracción de tasa_urbano desde JSON predial
# ══════════════════════════════════════════════════════════════

def _extract_tasa_urbano(predial: dict) -> Optional[float]:
    """
    Extrae la tasa más representativa para una vivienda urbana media.
    Devuelve float (al millar) o None.
    """
    tipo = predial.get("tipo_esquema", "desconocido")

    if tipo == "tarifa_millar":
        return _tasa_from_tarifa_millar(predial.get("tabla_tarifa_millar", []))
    if tipo == "tasa_unica":
        return _tasa_from_tasa_unica(predial.get("tabla_tasa_unica", []))
    if tipo == "progresivo":
        return _tasa_from_progresivo(predial.get("tabla_progresiva", []))
    if tipo == "mixto":
        for fn, key in [
            (_tasa_from_tarifa_millar, "tabla_tarifa_millar"),
            (_tasa_from_tasa_unica, "tabla_tasa_unica"),
            (_tasa_from_progresivo, "tabla_progresiva"),
        ]:
            t = fn(predial.get(key, []))
            if t is not None:
                return t
    return None


def _tasa_from_tarifa_millar(tabla: list) -> Optional[float]:
    """
    Busca la tasa más relevante para vivienda urbana:
      Prioridad: urbano_edificado > urbano > general > primera disponible.
    """
    if not isinstance(tabla, list) or not tabla:
        return None

    candidates = []
    for row in tabla:
        if not isinstance(row, dict):
            continue
        tasa = row.get("tasa_millar")
        if tasa is None:
            continue
        try:
            tasa_f = float(tasa)
        except (ValueError, TypeError):
            continue

        text = " ".join([
            (row.get("grupo") or ""),
            (row.get("clave") or ""),
            (row.get("descripcion") or ""),
        ]).lower()

        score = 1
        if "urbano" in text:
            score += 10
        if "edificado" in text:
            score += 5
        if "general" in text:
            score += 3

        candidates.append((score, tasa_f))

    if not candidates:
        return None
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1]


def _tasa_from_tasa_unica(tabla: list) -> Optional[float]:
    """Extrae tasa, convierte a al_millar si viene en porcentaje."""
    if not isinstance(tabla, list) or not tabla:
        return None
    for row in tabla:
        if not isinstance(row, dict):
            continue
        tasa = row.get("tasa")
        if tasa is None:
            continue
        try:
            tasa_f = float(tasa)
        except (ValueError, TypeError):
            continue
        unidad = (row.get("unidad") or "").lower()
        if "porcentaje" in unidad:
            tasa_f *= 10  # % → al millar
        elif "bimestral" in unidad:
            tasa_f *= 6  # bimestral al millar → anual al millar
        return tasa_f
    return None


def _tasa_from_progresivo(tabla: list) -> Optional[float]:
    """Tasa marginal del rango mediano como proxy de vivienda media."""
    if not isinstance(tabla, list) or not tabla:
        return None
    tasas = []
    for row in tabla:
        if not isinstance(row, dict):
            continue
        tm = row.get("tasa_marginal")
        if tm is None:
            continue
        val = parse_monto_to_float(tm)
        if val is not None and val > 0:
            tasas.append(val)
    if not tasas:
        return None
    tasas.sort()
    return tasas[len(tasas) // 2]


# ══════════════════════════════════════════════════════════════
# Lectura de JSONs de todos los estados
# ══════════════════════════════════════════════════════════════

def _load_audit_exclusions(data_root: Path) -> set[tuple[str, str, str]]:
    """
    Lee los audit CSVs y devuelve set de (estado, ejercicio, slug) a excluir.

    Solo excluye filas donde auditado = "excluir".
    """
    exclusions: set[tuple[str, str, str]] = set()
    for estado_slug, prefijo in PREFIJOS_ESTADO.items():
        audit_csv = data_root / estado_slug / "qa" / f"audit_{prefijo}.csv"
        if not audit_csv.exists():
            continue
        try:
            with audit_csv.open(encoding="utf-8-sig") as f:
                for row in csv.DictReader(f):
                    if row.get("auditado") == "excluir":
                        ej = row.get("ejercicio", "")
                        slug = row.get("slug", "")
                        if ej and slug:
                            exclusions.add((estado_slug, ej, slug))
        except Exception:
            continue
    return exclusions


def _load_all_jsons(data_root: Path) -> list[dict]:
    """Lee todos los JSONs de json_predial/ y extrae campos relevantes."""
    records = []

    # Cargar exclusiones de audit
    exclusions = _load_audit_exclusions(data_root)
    if exclusions:
        print(f"  Audit exclusions: {len(exclusions)} municipio-año marcados 'excluir'")

    for estado_slug, prefijo in sorted(PREFIJOS_ESTADO.items()):
        json_dir = data_root / estado_slug / "json_predial"
        if not json_dir.exists():
            continue

        for json_path in sorted(json_dir.rglob("*.json")):
            try:
                anio, slug, nombre = parse_predial_filename(json_path, prefijo)
            except ValueError:
                continue

            # Skip if excluded by audit
            if (estado_slug, str(anio), slug) in exclusions:
                continue

            try:
                with json_path.open(encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            predial = data.get("predial")
            if not isinstance(predial, dict):
                continue

            tipo = predial.get("tipo_esquema", "desconocido")
            tasa_urbano = _extract_tasa_urbano(predial)

            # Tablas auxiliares
            tabla_millar = predial.get("tabla_tarifa_millar", [])
            tabla_prog = predial.get("tabla_progresiva", [])

            # tasa_rustico y tasa_baldio (solo tarifa_millar)
            tasa_rustico = _find_tasa_by_keyword(tabla_millar, ["rustico", "rústico"])
            tasa_baldio = _find_tasa_by_keyword(tabla_millar, ["baldio", "baldío"])

            # n_rangos (solo progresivo)
            n_rangos = len(tabla_prog) if tipo == "progresivo" else None

            # Cuota mínima
            cuota_minima = None
            minimo = predial.get("minimo_predial")
            if isinstance(minimo, dict) and minimo.get("monto") is not None:
                try:
                    cuota_minima = float(minimo["monto"])
                except (ValueError, TypeError):
                    pass

            records.append({
                "estado": estado_slug,
                "prefijo": prefijo,
                "municipio": nombre,
                "municipio_slug": slug,
                "ejercicio": anio,
                "tipo_esquema": tipo,
                "esquema_valido": predial.get("esquema_valido", False),
                "tasa_urbano": tasa_urbano,
                "tasa_rustico": tasa_rustico,
                "tasa_baldio": tasa_baldio,
                "n_rangos": n_rangos,
                "cuota_minima": cuota_minima,
                "fuente_json": str(json_path.relative_to(data_root)),
                "extraction_method": "llm_direct",
            })

    return records


def _find_tasa_by_keyword(tabla_millar: list, keywords: list[str]) -> Optional[float]:
    """Busca tasa_millar en tabla_tarifa_millar cuyo grupo/clave/desc contenga algún keyword."""
    if not isinstance(tabla_millar, list):
        return None
    for row in tabla_millar:
        if not isinstance(row, dict):
            continue
        text = " ".join([
            (row.get("grupo") or ""),
            (row.get("clave") or ""),
            (row.get("descripcion") or ""),
        ]).lower()
        if any(kw in text for kw in keywords):
            try:
                return float(row["tasa_millar"])
            except (KeyError, ValueError, TypeError):
                pass
    return None


# ══════════════════════════════════════════════════════════════
# predial_panel.csv
# ══════════════════════════════════════════════════════════════

_PANEL_FIELDS = [
    "cve_ent", "cve_mun", "municipio", "estado", "ejercicio",
    "tipo_esquema", "tasa_urbano",
    "tasa_urbano_edificado", "tasa_rustico", "tasa_baldio",
    "n_rangos", "cuota_minima",
    "fuente_json", "extraction_method",
]


def _fmt(val: Optional[float]) -> str:
    if val is None:
        return ""
    return f"{val:.6f}" if abs(val) < 1 else f"{val:.2f}"


def _write_panel(records: list[dict], catalog: dict, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_PANEL_FIELDS)
        writer.writeheader()

        for r in sorted(records, key=lambda x: (x["estado"], x["municipio_slug"], x["ejercicio"])):
            cve_ent, cve_mun = _lookup_inegi(r["estado"], r["municipio_slug"], catalog)
            writer.writerow({
                "cve_ent": cve_ent,
                "cve_mun": cve_mun,
                "municipio": r["municipio"],
                "estado": r["estado"],
                "ejercicio": r["ejercicio"],
                "tipo_esquema": r["tipo_esquema"],
                "tasa_urbano": _fmt(r["tasa_urbano"]),
                "tasa_urbano_edificado": _fmt(r["tasa_urbano"]),
                "tasa_rustico": _fmt(r["tasa_rustico"]),
                "tasa_baldio": _fmt(r["tasa_baldio"]),
                "n_rangos": r["n_rangos"] if r["n_rangos"] is not None else "",
                "cuota_minima": _fmt(r["cuota_minima"]),
                "fuente_json": r["fuente_json"],
                "extraction_method": r["extraction_method"],
            })

    print(f"  → {output_path} ({len(records)} filas)")


# ══════════════════════════════════════════════════════════════
# quality_report.csv
# ══════════════════════════════════════════════════════════════

_QR_FIELDS = [
    "cve_ent", "cve_mun", "municipio", "estado", "ejercicio",
    "tipo_esquema", "tasa_urbano",
    "has_tasa", "tasa_changed", "schema_changed",
    "rangos_changed",
    "flag_anomaly", "notes",
]


def _write_quality_report(records: list[dict], catalog: dict, output_path: Path) -> None:
    # Agrupar por municipio
    by_muni: dict[tuple[str, str], list[dict]] = {}
    for r in records:
        by_muni.setdefault((r["estado"], r["municipio_slug"]), []).append(r)

    qr_rows: list[dict] = []

    for (estado, muni_slug), muni_recs in sorted(by_muni.items()):
        muni_recs.sort(key=lambda x: x["ejercicio"])
        cve_ent, cve_mun = _lookup_inegi(estado, muni_slug, catalog)

        prev: dict | None = None

        for r in muni_recs:
            flags: list[str] = []
            notes: list[str] = []
            tasa = r["tasa_urbano"]
            has_tasa = tasa is not None and tasa > 0

            # ── tasa_changed ──
            tasa_changed = ""
            if prev is not None and prev["tasa_urbano"] is not None and tasa is not None:
                pt = prev["tasa_urbano"]
                if pt > 0:
                    pct = abs(tasa - pt) / pt
                    tasa_changed = str(pct > 0.001)
                    if pct > 0.50:
                        flags.append("jump_gt_50pct")
                        notes.append(f"tasa {pt:.4f}→{tasa:.4f}")

            # ── schema_changed ──
            schema_changed = ""
            if prev is not None:
                pt = prev["tipo_esquema"]
                ct = r["tipo_esquema"]
                if pt != "desconocido" and ct != "desconocido":
                    schema_changed = str(pt != ct)
                    if pt != ct:
                        flags.append("schema_change")
                        notes.append(f"esquema {pt}→{ct}")

            # ── rangos_changed (solo progresivo→progresivo) ──
            rangos_changed = ""
            if prev is not None:
                if prev["tipo_esquema"] == "progresivo" and r["tipo_esquema"] == "progresivo":
                    pn = prev.get("n_rangos")
                    cn = r.get("n_rangos")
                    if pn is not None and cn is not None:
                        rangos_changed = str(pn != cn)
                        if pn != cn:
                            notes.append(f"rangos {pn}→{cn}")

            # ── Anomalías generales ──
            if not has_tasa:
                flags.append("tasa_zero_or_missing")

            qr_rows.append({
                "cve_ent": cve_ent,
                "cve_mun": cve_mun,
                "municipio": r["municipio"],
                "estado": estado,
                "ejercicio": r["ejercicio"],
                "tipo_esquema": r["tipo_esquema"],
                "tasa_urbano": _fmt(tasa),
                "has_tasa": str(has_tasa),
                "tasa_changed": tasa_changed,
                "schema_changed": schema_changed,
                "rangos_changed": rangos_changed,
                "flag_anomaly": "|".join(flags) if flags else "",
                "notes": "; ".join(notes) if notes else "",
            })

            prev = r

    # Escribir
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=_QR_FIELDS)
        writer.writeheader()
        writer.writerows(qr_rows)

    total = len(qr_rows)
    with_flags = sum(1 for r in qr_rows if r["flag_anomaly"])
    schema_chg = sum(1 for r in qr_rows if r["schema_changed"] == "True")
    tasa_chg = sum(1 for r in qr_rows if r["tasa_changed"] == "True")
    rango_chg = sum(1 for r in qr_rows if r["rangos_changed"] == "True")

    print(f"  → {output_path} ({total} filas)")
    print(f"    Con anomalías:       {with_flags}")
    print(f"    Cambios de esquema:  {schema_chg}")
    print(f"    Cambios de tasa:     {tasa_chg}")
    print(f"    Cambios de rangos:   {rango_chg}")


# ══════════════════════════════════════════════════════════════
# Entry point
# ══════════════════════════════════════════════════════════════

def consolidate_all(
    data_root: Path = Path("data"),
    output_dir: Path = Path("output"),
    catalog_path: Path = Path("catalogs/municipios_inegi.csv"),
):
    """
    Lee todos los JSONs validados de data/*/json_predial/
    y genera predial_panel.csv + quality_report.csv.
    """
    print("═" * 60)
    print("  FASE 6: Consolidación")
    print("═" * 60)

    catalog = _load_inegi(catalog_path)
    print(f"  Catálogo INEGI: {len(catalog)} entradas" if catalog
          else f"  [WARN] Catálogo INEGI no encontrado en {catalog_path}")

    print("\n  Leyendo JSONs...")
    records = _load_all_jsons(data_root)

    if not records:
        print("  [WARN] No se encontraron JSONs. ¿Ya corriste la extracción LLM (Fase 5)?")
        return

    # Resumen por estado
    by_estado: dict[str, int] = {}
    for r in records:
        by_estado[r["estado"]] = by_estado.get(r["estado"], 0) + 1
    for est, cnt in sorted(by_estado.items()):
        n_m = len(set(r["municipio_slug"] for r in records if r["estado"] == est))
        print(f"    {est}: {cnt} obs ({n_m} municipios)")

    print("\n  Generando predial_panel.csv...")
    _write_panel(records, catalog, output_dir / "predial_panel.csv")

    print("\n  Generando quality_report.csv...")
    _write_quality_report(records, catalog, output_dir / "quality_report.csv")

    # Resumen global
    n_munis = len(set((r["estado"], r["municipio_slug"]) for r in records))
    tipos: dict[str, int] = {}
    for r in records:
        tipos[r["tipo_esquema"]] = tipos.get(r["tipo_esquema"], 0) + 1

    print(f"\n  ── Resumen ──")
    print(f"  Observaciones: {len(records)}")
    print(f"  Municipios:    {n_munis}")
    years = [r["ejercicio"] for r in records]
    print(f"  Años:          {min(years)}-{max(years)}")
    print(f"  Esquemas:")
    for t, cnt in sorted(tipos.items(), key=lambda x: -x[1]):
        print(f"    {t:20s} {cnt:5d} ({100*cnt/len(records):.1f}%)")
