"""Aplica overrides del audit + correcciones manuales finales y construye
panel pragmático (Sonora) cerrando los 64 huecos restantes con imputación
agresiva por categoría de muni.

Correcciones manuales finales (post primera revisión):
  - Tepache 2010-2015: mixto (always_treated, no cohorte 2014)
  - Huatabampo 2010-2015: mixto (always_treated, no cohorte 2015)
  - Suaqui Grande 2010-2020: progresivo (always_treated, no cohorte 2021)

Reglas de imputación agresiva:
  - always_treated: hueco → tipo modal del brazo T del muni (típicamente progresivo)
  - reversion: hueco → tipo del vecino contiguo más cercano
  - treated_cohort: pre-cohorte → modal C; post-cohorte → modal T (respeta el switch)
  - never_treated: hueco → modal C
  - no_data: tarifa_millar (default fallback, marcado para auditoría)

Outputs:
  data/sonora/qa/treatment_overrides.csv     (re-escrito con manuales)
  output/balance/panel_v2_balanced_audited.csv      (re-aplicado)
  output/balance/panel_v2_balanced_sonora_pragmatic.csv  (1152 filas, 0 huecos)
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

TREATMENT = {"progresivo", "mixto"}
CONTROL = {
    "tarifa_millar", "tasa_unica",
    "cuota_fija_simple", "cuota_fija_escalonada", "cuota_fija",
}
ANIO_MIN, ANIO_MAX = 2010, 2025


def arm(t: str) -> str:
    if t in TREATMENT:
        return "T"
    if t in CONTROL:
        return "C"
    return "W"


def main() -> None:
    # 1. Cargar overrides existentes y añadir las correcciones manuales finales
    overrides: dict[tuple[str, int], tuple[str, str]] = {}
    audit_path = Path("data/sonora/qa/treatment_overrides.csv")
    muni_nom_by_cve: dict[str, str] = {}
    if audit_path.exists():
        with audit_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                key = (r["cve_mun"], int(r["anio"]))
                overrides[key] = (r["tipo_override"], r["source"])
                if r.get("municipio"):
                    muni_nom_by_cve[r["cve_mun"]] = r["municipio"]

    manual = [
        ("063", "Tepache",       "mixto",      2010, 2015),
        ("033", "Huatabampo",    "mixto",      2010, 2015),
        ("062", "Suaqui Grande", "progresivo", 2010, 2020),
    ]
    n_added = 0
    for cve, nom, tipo, y0, y1 in manual:
        muni_nom_by_cve[cve] = nom
        for y in range(y0, y1 + 1):
            overrides[(cve, y)] = (tipo, "user_manual")
            n_added += 1
    print(f"[1] Manual additions: {n_added} celdas (Tepache, Huatabampo, Suaqui Grande)")

    with audit_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["cve_mun", "municipio", "anio", "tipo_override", "source"])
        for (cve, anio), (tipo, src) in sorted(overrides.items()):
            w.writerow([cve, muni_nom_by_cve.get(cve, ""), anio, tipo, src])

    # 2. Re-aplicar overrides al panel
    src_panel = Path("output/balance/panel_v2_balanced.csv")
    dst_panel = Path("output/balance/panel_v2_balanced_audited.csv")
    with src_panel.open(encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        if "audit_source" not in fields:
            fields.append("audit_source")
        rows = list(reader)

    n_overridden = 0
    for r in rows:
        if (r.get("estado") or "").lower() != "sonora":
            r["audit_source"] = ""
            continue
        cve = r["cvegeo"].zfill(5)[2:]
        try:
            anio = int(r["ejercicio"])
        except ValueError:
            r["audit_source"] = ""
            continue
        key = (cve, anio)
        if key in overrides:
            new_tipo, src = overrides[key]
            r["tipo_esquema"] = new_tipo
            r["audit_source"] = src
            n_overridden += 1
        else:
            r["audit_source"] = ""

    try:
        with dst_panel.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        print(f"[2] {n_overridden} celdas Sonora overrided in {dst_panel}")
    except PermissionError:
        print(f"[2] [WARN] {dst_panel} abierto en otro programa, salto rewrite. "
              f"({n_overridden} overrides ya en memoria, se aplicarán al pragmático)")

    # 3. Construir panel pragmático
    sonora = [r for r in rows if (r.get("estado") or "").lower() == "sonora"]
    munis: dict[str, str] = {}
    with open("catalogs/municipios_inegi.csv", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("CVE_ENT") or "").strip() == "26":
                munis[r["CVE_MUN"].strip().zfill(3)] = r["NOM_MUN"].strip()
    print(f"[3] munis INEGI Sonora: {len(munis)}")

    panel_by_key: dict[tuple[str, int], dict] = {}
    for r in sonora:
        cve = r["cvegeo"].zfill(5)[2:]
        try:
            anio = int(r["ejercicio"])
        except ValueError:
            continue
        panel_by_key[(cve, anio)] = r

    def categorize(cve: str) -> tuple[str, str, str, int | None]:
        obs = []
        for y in range(ANIO_MIN, ANIO_MAX + 1):
            r = panel_by_key.get((cve, y))
            if r:
                tipo = (r.get("tipo_esquema") or "").strip()
                obs.append((y, tipo, arm(tipo)))
        n_obs = sum(1 for _, _, a in obs if a != "W")
        if n_obs == 0:
            return ("no_data", "progresivo", "tarifa_millar", None)
        tipos_T = [t for _, t, a in obs if a == "T"]
        tipos_C = [t for _, t, a in obs if a == "C"]
        modal_T = Counter(tipos_T).most_common(1)[0][0] if tipos_T else "progresivo"
        modal_C = Counter(tipos_C).most_common(1)[0][0] if tipos_C else "tarifa_millar"
        n_T = len(tipos_T)
        n_C = len(tipos_C)
        if n_T == n_obs:
            return ("always_treated", modal_T, modal_C, None)
        if n_C == n_obs:
            return ("never_treated", modal_T, modal_C, None)
        seen_T = False
        seen_C_after_T = False
        first_T = None
        for y, t, a in obs:
            if a == "T":
                if not seen_T:
                    first_T = y
                seen_T = True
            elif a == "C" and seen_T:
                seen_C_after_T = True
        if seen_C_after_T:
            return ("reversion", modal_T, modal_C, None)
        return ("treated_cohort", modal_T, modal_C, first_T)

    fields_prag = list(fields)
    if "pragmatic_method" not in fields_prag:
        fields_prag.append("pragmatic_method")

    pragmatic = []
    n_filled = 0
    method_cnt: Counter = Counter()
    cat_cnt: Counter = Counter()

    for cve in sorted(munis):
        nom = munis[cve]
        cvegeo = f"26{cve}"
        cat, modal_T, modal_C, cohort = categorize(cve)
        cat_cnt[cat] += 1

        for y in range(ANIO_MIN, ANIO_MAX + 1):
            r = panel_by_key.get((cve, y))
            if r:
                row = dict(r)
                row["pragmatic_method"] = "existing"
                pragmatic.append(row)
                continue
            n_filled += 1
            if cat == "always_treated":
                tipo = modal_T
                method = "always_T_modal_fill"
            elif cat == "reversion":
                tipo = None
                for delta in range(1, 17):
                    for sign in (-1, +1):
                        yy = y + sign * delta
                        if (cve, yy) in panel_by_key:
                            rr = panel_by_key[(cve, yy)]
                            tipo = (rr.get("tipo_esquema") or "").strip()
                            break
                    if tipo:
                        break
                tipo = tipo or modal_T
                method = "reversion_neighbor_fill"
            elif cat == "treated_cohort" and cohort is not None:
                if y < cohort:
                    tipo = modal_C
                    method = "cohort_pre_fill"
                else:
                    tipo = modal_T
                    method = "cohort_post_fill"
            elif cat == "never_treated":
                tipo = modal_C
                method = "never_T_modal_fill"
            else:
                tipo = "tarifa_millar"
                method = "no_data_default"
            method_cnt[method] += 1
            pragmatic.append({
                "cvegeo": cvegeo,
                "estado": "Sonora",
                "municipio": nom,
                "ejercicio": y,
                "tipo_esquema": tipo,
                "numero_rangos": "",
                "monto_max_rango": "",
                "imputed": "pragmatic",
                "imputed_from_year": "",
                "audit_source": "",
                "pragmatic_method": method,
            })

    out_prag = Path("output/balance/panel_v2_balanced_sonora_pragmatic.csv")
    with out_prag.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_prag, extrasaction="ignore")
        w.writeheader()
        w.writerows(pragmatic)

    print(f"[4] Pragmatic panel: {len(pragmatic)} filas (esperado 1152)")
    print(f"    Celdas existentes: {len(pragmatic) - n_filled}")
    print(f"    Celdas rellenadas: {n_filled}")
    print(f"    Por método de fill:")
    for k, v in method_cnt.most_common():
        print(f"      {k:30s} {v}")
    print(f"    Categorías de muni:")
    for k, v in cat_cnt.most_common():
        print(f"      {k:18s} {v}")
    print(f"    Output: {out_prag}")


if __name__ == "__main__":
    main()
