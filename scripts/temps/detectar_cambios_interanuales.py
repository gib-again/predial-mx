"""Detecta cambios interanuales en clasificación + tarifas por municipio.

Asunción central: la legislación predial es "sticky" — el mismo municipio
mantiene el mismo esquema y tarifas año tras año salvo reforma documentada.
Cualquier cambio detectado por el sistema es candidato a:
  (a) error de extracción / segmentación (lo más probable estadísticamente), o
  (b) reforma real (a confirmar manualmente).

Estrategia:
  1. Agrupa todos los JSONs por (estado_slug, municipio_slug).
  2. Para cada grupo, ordena por año y compara año tras año en estricto.
  3. Emite una fila por transición con cambio, ordenada por sospecha
     (severidad descendente, luego racha estable previa descendente —
      cuanto más larga la racha previa, mayor confianza en que el "estable"
      es lo correcto y el cambio nuevo es el error).
  4. La salida es una plantilla HITL que el humano llena (columna `decision`).

Severidades:
  SEV1  cambio de tipo_esquema             (reforma de mecánica — rarísimo)
  SEV2  cambio en n_filas/n_rangos, grupos, tasas (rates no inflacionan)
  SEV3  cambio en montos en pesos (cuota_fija, límites, monto, mínimo)

La tolerancia es estricta: cualquier diferencia exacta dispara revisión.

Salidas en `output/anexos/`:
  - cambios_interanuales.csv   plantilla HITL ordenada por sospecha
  - cambios_resumen.csv         conteo por severidad/estado

Uso:
  python -m scripts.detectar_cambios_interanuales
  python -m scripts.detectar_cambios_interanuales --solo-estado guanajuato
  python -m scripts.detectar_cambios_interanuales --sev-min 2  # solo SEV1+SEV2
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path

from scripts.temps.build_anexo_esquemas import (
    DATA_ROOT,
    ESTADO_SLUG_PRETTY,
    V2_ROOT,
    pretty_muni,
)
from src.core.validation import reclasificar

OUT_DIR = Path("output/anexos")
_FNAME_RE = re.compile(r"_PREDIAL_(\d{4})_(.+)$")

# Tipos "reales" (excluye otro_no_clasificado y desconocido).
TIPOS_REALES = {
    "tarifa_millar", "progresivo", "tasa_unica",
    "cuota_fija_simple", "cuota_fija_escalonada", "cuota_fija", "mixto",
}

# Estados con tarifa estatal uniforme (hardcoded) — por construcción 100%
# sticky; sus "cambios" son artefactos del adapter, no decisiones humanas.
# Se omiten por default; --include-hardcoded los reincluye para auditoría.
ESTADOS_HARDCODED = {"chihuahua", "colima", "edomex", "sinaloa", "tabasco"}

# Tolerancia "cent-gap" para límites de rango (consistente con
# src/core/validation._BRACKET_SNAP_TOLERANCE = 1.0). La convención mexicana
# usa 0.01 como límite exclusivo (rango 1: 0–60000, rango 2: 60000.01–90000);
# el snap evita reportar 0.0↔0.01 como cambios sustantivos.
_SNAP_TOL = 1.0


def _close(a, b, tol: float = _SNAP_TOL) -> bool:
    """True si a y b se consideran iguales bajo tolerancia cent-gap.

    Maneja None: None==None es True; None vs número es False.
    """
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


# ── Corpus iterator ──

def _is_llm_direct(modelo: str) -> bool:
    """True solo si el JSON viene de una extracción directa de LLM.

    Excluye imputaciones (`imputed_*`), markers sintetizados
    (`synthesized_*`), overrides de auditoría (`audit_*`), leyes descubiertas
    (`discovered_law[...]`) y adapters hardcoded. Para HITL queremos
    comparar año-tras-año únicamente observaciones reales del LLM.
    """
    if not modelo:
        return False
    m = modelo.lower()
    # Excluir prefijos no-LLM.
    if m.startswith(("imputed_", "synthesized_", "audit_", "discovered_", "hardcoded")):
        return False
    # Incluir si contiene "gpt-" (cubre gpt-5.4-mini, reclasified_v1[gpt-5.2], etc.).
    return "gpt-" in m


def iter_corpus(include_hardcoded: bool = False,
                include_imputed: bool = False):
    """Yield (estado_slug, anio, slug, predial_dict, json_path).

    Por default omite:
      - estados hardcoded (chihuahua, colima, edomex, sinaloa, tabasco) —
        artefactos del adapter, no requieren HITL.
      - JSONs no-LLM (imputed_*, synthesized_*, audit_*, discovered_*) —
        no son observaciones directas y contaminarian la comparación
        interanual.

    `include_imputed=True` los re-incluye (útil para auditorías de cobertura).
    """
    if V2_ROOT.exists():
        for est_dir in sorted(p for p in V2_ROOT.iterdir() if p.is_dir()):
            est_slug = est_dir.name
            if est_slug in ESTADOS_HARDCODED and not include_hardcoded:
                continue
            for p in sorted(est_dir.glob("*_PREDIAL_*.json")):
                m = _FNAME_RE.search(p.stem)
                if not m:
                    continue
                try:
                    doc = json.loads(p.read_text(encoding="utf-8"))
                except Exception:
                    continue
                meta = doc.get("_meta") or {}
                if not include_imputed and not _is_llm_direct(meta.get("modelo", "")):
                    continue
                pred = doc.get("predial")
                if isinstance(pred, dict) and pred.get("tipo_esquema") and "tabla" in pred:
                    yield est_slug, int(m.group(1)), m.group(2), pred, p
    ox = DATA_ROOT / "oaxaca" / "json_predial"
    if ox.exists():
        for p in sorted(ox.rglob("*_PREDIAL_*.json")):
            m = _FNAME_RE.search(p.stem)
            if not m:
                continue
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            meta = doc.get("_meta") or {}
            if not include_imputed and not _is_llm_direct(meta.get("modelo", "")):
                continue
            pred = doc.get("predial")
            if not isinstance(pred, dict):
                continue
            try:
                inst = reclasificar(pred)
            except Exception:
                continue
            yield "oaxaca", int(m.group(1)), m.group(2), inst.model_dump(), p


# ── Diff por tipo ──

def _diff_tarifa_millar(prev, curr):
    cambios, sev = [], 0
    p_by = {(r.get("grupo"), r.get("clave")): r for r in prev}
    c_by = {(r.get("grupo"), r.get("clave")): r for r in curr}
    for k, c in c_by.items():
        if k not in p_by:
            cambios.append(f"nueva fila {k}: tasa={c.get('tasa_millar')}")
            sev = max(sev, 2)
            continue
        p = p_by[k]
        if p.get("tasa_millar") != c.get("tasa_millar"):
            cambios.append(f"{k}: tasa {p.get('tasa_millar')}→{c.get('tasa_millar')}")
            sev = max(sev, 2)
        pa, ca = p.get("cuota_fija_adicional"), c.get("cuota_fija_adicional")
        if pa != ca:
            cambios.append(f"{k}: cuota_adic {pa}→{ca}")
            sev = max(sev, 3)
    for k in p_by:
        if k not in c_by:
            cambios.append(f"fila eliminada {k}")
            sev = max(sev, 2)
    return cambios, sev


def _diff_progresivo(prev, curr):
    cambios, sev = [], 0
    p_by = {r.get("n_rango"): r for r in prev}
    c_by = {r.get("n_rango"): r for r in curr}
    for rng in sorted(set(p_by) | set(c_by), key=lambda x: (x is None, x)):
        if rng not in p_by:
            cambios.append(f"rango {rng} nuevo")
            sev = max(sev, 2)
            continue
        if rng not in c_by:
            cambios.append(f"rango {rng} eliminado")
            sev = max(sev, 2)
            continue
        p, c = p_by[rng], c_by[rng]
        # Límites (inferior/superior) usan tolerancia cent-gap; el resto es estricto.
        for field, label, s in [("inferior", "inf", 3), ("superior", "sup", 3)]:
            if not _close(p.get(field), c.get(field)):
                cambios.append(f"r{rng}.{label}: {p.get(field)}→{c.get(field)}")
                sev = max(sev, s)
        for field, label, s in [("cuota_fija", "cf", 3), ("tasa_marginal", "tm", 2)]:
            if p.get(field) != c.get(field):
                cambios.append(f"r{rng}.{label}: {p.get(field)}→{c.get(field)}")
                sev = max(sev, s)
    return cambios, sev


def _diff_tasa_unica(prev, curr):
    cambios, sev = [], 0
    if not (prev and curr):
        return cambios, sev
    p, c = prev[0], curr[0]
    for field, s in [("tasa", 2), ("base_calculo", 2), ("unidad", 2)]:
        if p.get(field) != c.get(field):
            cambios.append(f"{field}: {p.get(field)}→{c.get(field)}")
            sev = max(sev, s)
    return cambios, sev


def _diff_cuota_fija_simple(prev, curr):
    cambios, sev = [], 0
    if not (prev and curr):
        return cambios, sev
    p, c = prev[0], curr[0]
    for field, s in [("monto", 3), ("periodicidad", 2), ("unidad", 2)]:
        if p.get(field) != c.get(field):
            cambios.append(f"{field}: {p.get(field)}→{c.get(field)}")
            sev = max(sev, s)
    return cambios, sev


def _diff_cuota_fija_escalonada(prev, curr):
    cambios, sev = [], 0
    p_by = {r.get("n_rango"): r for r in prev}
    c_by = {r.get("n_rango"): r for r in curr}
    for rng in sorted(set(p_by) | set(c_by), key=lambda x: (x is None, x)):
        if rng not in p_by:
            cambios.append(f"rango {rng} nuevo")
            sev = max(sev, 2)
            continue
        if rng not in c_by:
            cambios.append(f"rango {rng} eliminado")
            sev = max(sev, 2)
            continue
        p, c = p_by[rng], c_by[rng]
        # Límites con tolerancia cent-gap; monto estricto.
        for field, label in [("inferior", "inf"), ("superior", "sup")]:
            if not _close(p.get(field), c.get(field)):
                cambios.append(f"r{rng}.{label}: {p.get(field)}→{c.get(field)}")
                sev = max(sev, 3)
        if p.get("monto") != c.get("monto"):
            cambios.append(f"r{rng}.monto: {p.get('monto')}→{c.get('monto')}")
            sev = max(sev, 3)
    return cambios, sev


def _diff_mixto(prev, curr):
    cambios, sev = [], 0
    p_by = {r.get("n_rango"): r for r in prev}
    c_by = {r.get("n_rango"): r for r in curr}
    for rng in sorted(set(p_by) | set(c_by), key=lambda x: (x is None, x)):
        if rng not in p_by:
            cambios.append(f"rango {rng} nuevo")
            sev = max(sev, 2)
            continue
        if rng not in c_by:
            cambios.append(f"rango {rng} eliminado")
            sev = max(sev, 2)
            continue
        p, c = p_by[rng], c_by[rng]
        # Límites con tolerancia cent-gap.
        if not (_close(p.get("inferior"), c.get("inferior"))
                and _close(p.get("superior"), c.get("superior"))):
            cambios.append(
                f"r{rng} límites: ({p.get('inferior')},{p.get('superior')})→"
                f"({c.get('inferior')},{c.get('superior')})"
            )
            sev = max(sev, 3)
        p_cols = sorted(
            (cc.get("nombre", ""), cc.get("valor"), cc.get("tipo", ""), cc.get("unidad", ""))
            for cc in (p.get("columnas") or [])
        )
        c_cols = sorted(
            (cc.get("nombre", ""), cc.get("valor"), cc.get("tipo", ""), cc.get("unidad", ""))
            for cc in (c.get("columnas") or [])
        )
        if p_cols != c_cols:
            cambios.append(f"r{rng} columnas cambiaron ({len(p_cols)}→{len(c_cols)} celdas)")
            sev = max(sev, 3)
    return cambios, sev


_DIFFERS = {
    "tarifa_millar": _diff_tarifa_millar,
    "progresivo": _diff_progresivo,
    "tasa_unica": _diff_tasa_unica,
    "cuota_fija_simple": _diff_cuota_fija_simple,
    "cuota_fija": _diff_cuota_fija_simple,
    "cuota_fija_escalonada": _diff_cuota_fija_escalonada,
    "mixto": _diff_mixto,
}


def diff_predial(prev: dict, curr: dict) -> tuple[list[str], int]:
    """Devuelve (lista_de_cambios, severidad_max). Lista vacía = sin cambios."""
    cambios: list[str] = []
    sev = 0
    if prev.get("tipo_esquema") != curr.get("tipo_esquema"):
        cambios.append(
            f"tipo_esquema: {prev.get('tipo_esquema')}→{curr.get('tipo_esquema')}"
        )
        return cambios, 1
    tipo = prev.get("tipo_esquema")
    pt, ct = prev.get("tabla") or [], curr.get("tabla") or []
    if len(pt) != len(ct):
        cambios.append(f"n_filas: {len(pt)}→{len(ct)}")
        sev = max(sev, 2)
    differ = _DIFFERS.get(tipo)
    if differ is not None:
        c2, s2 = differ(pt, ct)
        cambios.extend(c2)
        sev = max(sev, s2)
    pmin = prev.get("minimo_predial") or {}
    cmin = curr.get("minimo_predial") or {}
    for field, s in [("monto", 3), ("periodicidad", 2), ("unidad", 2)]:
        if pmin.get(field) != cmin.get(field):
            cambios.append(f"minimo.{field}: {pmin.get(field)}→{cmin.get(field)}")
            sev = max(sev, s)
    return cambios, sev


def _join_cambios(cambios: list[str], max_chars: int = 280) -> str:
    text = "; ".join(cambios)
    return text if len(text) <= max_chars else text[: max_chars - 3] + "..."


# ── Pipeline ──

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--solo-estado", help="Solo un estado_slug (e.g. guanajuato).")
    ap.add_argument("--sev-min", type=int, default=1, choices=[1, 2, 3],
                    help="Reporta cambios con severidad >= N (default 1).")
    ap.add_argument("--max-filas", type=int, help="Trunca el CSV HITL a N filas.")
    ap.add_argument("--include-hardcoded", action="store_true",
                    help=("Incluye estados hardcoded (chihuahua, colima, edomex, "
                          "sinaloa, tabasco) que por default se omiten — son 100% "
                          "sticky por construccion y sus 'cambios' son artefactos."))
    ap.add_argument("--include-imputed", action="store_true",
                    help=("Incluye JSONs no-LLM (imputed_*, synthesized_*, "
                          "audit_*, discovered_*) que por default se omiten — "
                          "no son observaciones directas y contaminarian la "
                          "comparacion interanual."))
    ap.add_argument("--out", default=str(OUT_DIR / "cambios_interanuales.csv"))
    args = ap.parse_args()
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print("Cargando corpus...")
    if not args.include_hardcoded:
        print(f"  Saltando estados hardcoded: {sorted(ESTADOS_HARDCODED)}")
        print("  (usa --include-hardcoded para incluirlos en auditoria completa)")
    if not args.include_imputed:
        print("  Saltando JSONs no-LLM (imputed_*, synthesized_*, audit_*, discovered_*)")
        print("  (usa --include-imputed para incluirlos)")
    grupos: dict[tuple[str, str], list[tuple[int, dict, Path]]] = defaultdict(list)
    n_jsons = 0
    for est, anio, slug, pred, path in iter_corpus(
        include_hardcoded=args.include_hardcoded,
        include_imputed=args.include_imputed,
    ):
        if args.solo_estado and est != args.solo_estado:
            continue
        grupos[(est, slug)].append((anio, pred, path))
        n_jsons += 1
        if n_jsons % 2000 == 0:
            print(f"  {n_jsons} JSONs cargados...")
    print(f"  {n_jsons} JSONs en {len(grupos)} (estado, municipio) unicos")

    rows: list[dict] = []
    n_transiciones = 0
    estables_completos = 0  # munis sin ningún cambio en su serie

    for (est, slug), entries in grupos.items():
        entries.sort(key=lambda x: x[0])
        if len(entries) < 2:
            continue
        prev_changes: list[bool] = []
        any_change = False
        for i in range(len(entries) - 1):
            y_prev, p_prev, path_prev = entries[i]
            y_curr, p_curr, path_curr = entries[i + 1]
            n_transiciones += 1
            cambios, sev = diff_predial(p_prev, p_curr)
            if not cambios:
                prev_changes.append(False)
                continue
            any_change = True
            # racha: # de transiciones previas SIN cambio (consecutivas).
            racha = 0
            for changed in reversed(prev_changes):
                if not changed:
                    racha += 1
                else:
                    break
            prev_changes.append(True)
            if sev < args.sev_min:
                continue
            rows.append({
                "severidad_max": sev,
                "racha_estable_previa": racha,
                "estado": ESTADO_SLUG_PRETTY.get(est, est),
                "estado_slug": est,
                "municipio": pretty_muni(slug),
                "municipio_slug": slug,
                "anio_prev": y_prev,
                "anio": y_curr,
                "tipo_prev": p_prev.get("tipo_esquema"),
                "tipo_nuevo": p_curr.get("tipo_esquema"),
                "n_cambios": len(cambios),
                "diff_resumen": _join_cambios(cambios),
                "json_prev": path_prev.as_posix(),
                "json_nuevo": path_curr.as_posix(),
                "decision": "",
                "notas": "",
            })
        if not any_change:
            estables_completos += 1

    # Orden: severidad ascendente (SEV1 = tipo_esquema = más serio primero),
    # luego racha_estable_previa descendente (más estabilidad = más sospecha).
    rows.sort(key=lambda r: (
        r["severidad_max"], -r["racha_estable_previa"],
        r["estado"], r["municipio"], r["anio"],
    ))
    if args.max_filas:
        rows = rows[: args.max_filas]

    cols = ["severidad_max", "racha_estable_previa", "estado", "estado_slug",
            "municipio", "municipio_slug", "anio_prev", "anio",
            "tipo_prev", "tipo_nuevo", "n_cambios", "diff_resumen",
            "json_prev", "json_nuevo", "decision", "notas"]
    with out_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)

    # Resumen
    by_sev: dict[int, int] = defaultdict(int)
    by_est: dict[str, int] = defaultdict(int)
    for r in rows:
        by_sev[r["severidad_max"]] += 1
        by_est[r["estado"]] += 1
    print(f"\nTransiciones evaluadas: {n_transiciones}")
    print(f"Transiciones con cambio (sev>={args.sev_min}): {len(rows)}"
          f"  ({100*len(rows)/max(n_transiciones,1):.1f}%)")
    print(f"Municipios con serie 100% estable: {estables_completos}/{len(grupos)}")
    print("\nPor severidad:")
    for s in sorted(by_sev):
        etiqueta = {1: "tipo_esquema", 2: "estructura/tasas", 3: "montos pesos"}[s]
        print(f"  SEV{s} ({etiqueta:18s}): {by_sev[s]}")
    print("\nPor estado:")
    for est, n in sorted(by_est.items(), key=lambda x: -x[1]):
        print(f"  {est:30s} {n}")
    print(f"\nCSV HITL: {out_path}")

    # CSV resumen aparte (para anexo)
    res_path = out_path.parent / "cambios_resumen.csv"
    with res_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["dimension", "categoria", "n"])
        for s in sorted(by_sev):
            w.writerow(["severidad", f"SEV{s}", by_sev[s]])
        for est, n in sorted(by_est.items(), key=lambda x: -x[1]):
            w.writerow(["estado", est, n])
        w.writerow(["resumen", "transiciones_totales", n_transiciones])
        w.writerow(["resumen", "munis_serie_estable", estables_completos])
        w.writerow(["resumen", "munis_totales", len(grupos)])
    print(f"Resumen: {res_path}")


if __name__ == "__main__":
    main()
