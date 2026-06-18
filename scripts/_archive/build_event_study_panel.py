"""Construye el panel binario final para event-study (predial-mx, 2010-2024).

Fuentes (heterogéneas por decisión del usuario):
  - Sonora              ← output/panel_v2_balanced_sonora_pragmatic.csv
  - San Luis Potosi     ← output/predial_panel_pragmatic.csv (filtrar)
  - Oaxaca              ← construido desde cero contra catálogo INEGI:
                          OdJ (20067) tarifa_millar 2010-2021 + progresivo 2022-2024;
                          resto: tarifa_millar 2010-2024
  - 11 estados restantes ← output/panel_v2.csv

Reglas de tratamiento:
  TREATMENT = {progresivo, mixto}        → arm = T, treated = 1
  CONTROL   = {tarifa_millar, tasa_unica,
               cuota_fija, cuota_fija_simple, cuota_fija_escalonada} → arm = C, treated = 0
  WILDCARD  = {desconocido, otro_no_clasificado, blank} → arm = W

Resolución de wildcard (forward-fill absorbente):
  - W posterior al primer T del muni → T (propaga absorbente)
  - Muni nunca-T  → W → C
  - W previo al primer T → C (no contamina pre-tratamiento)

Reversiones (T→C): se aceptan como dato real en `treated`. Se expone columna
alternativa `treated_absorbing` (1 desde primer T en adelante) para DiD canónico.

Outputs en output/event_study/:
  - panel_event_study.csv         (14 estados con datos, columnas mínimas)
  - panel_event_study_long.csv    (14 estados, columnas de trazabilidad)
  - panel_event_study_full.csv    (14 + 17 estados never-treated, excl CDMX)
  - panel_event_study_full_long.csv (full + columnas de trazabilidad)
  - treatment_trajectories.csv    (1 fila por muni, solo 14 estados con datos)
  - coverage_report.md            (métricas finales)
  - README.md                     (documentación)

Panel completo (full): añade 17 estados como never-treated bajo la asunción del
usuario de que ningún municipio fuera de los 14 considerados ha adoptado tarifa
progresiva. Respeta la fecha de creación de municipios nuevos (changes_ageeml.csv):
solo emite filas desde el año de creación, no llena pre-creación.
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

ANIO_MIN, ANIO_MAX = 2010, 2024
YEARS = list(range(ANIO_MIN, ANIO_MAX + 1))

TREATMENT = {"progresivo", "mixto"}
CONTROL = {
    "tarifa_millar", "tasa_unica",
    "cuota_fija", "cuota_fija_simple", "cuota_fija_escalonada",
}
# WILDCARD implícito: cualquier valor que no esté en TREATMENT ∪ CONTROL
# (incluye "desconocido", "otro_no_clasificado", "no_aplica", blank)

ESTADOS_TARGET = {
    "05": "Coahuila de Zaragoza",
    "06": "Colima",
    "08": "Chihuahua",
    "11": "Guanajuato",
    "14": "Jalisco",
    "15": "Mexico",
    "20": "Oaxaca",
    "22": "Queretaro",
    "24": "San Luis Potosi",
    "25": "Sinaloa",
    "26": "Sonora",
    "27": "Tabasco",
    "28": "Tamaulipas",
    "31": "Yucatan",
}

# Estados nunca tratados (asunción del usuario): no han adoptado tarifa progresiva.
# Excluye CDMX (09) explícitamente — sus alcaldías no son municipios fiscales comparables.
ESTADOS_NEVER_TREATED = {
    "01": "Aguascalientes",
    "02": "Baja California",
    "03": "Baja California Sur",
    "04": "Campeche",
    "07": "Chiapas",
    "10": "Durango",
    "12": "Guerrero",
    "13": "Hidalgo",
    "16": "Michoacan",
    "17": "Morelos",
    "18": "Nayarit",
    "19": "Nuevo Leon",
    "21": "Puebla",
    "23": "Quintana Roo",
    "29": "Tlaxcala",
    "30": "Veracruz",
    "32": "Zacatecas",
}

OUT_DIR = Path("output/event_study")
INEGI_CSV = Path("catalogs/municipios_inegi.csv")
CHANGES_CSV = Path("catalogs/changes_ageeml.csv")


def arm(t: str) -> str:
    if t in TREATMENT:
        return "T"
    if t in CONTROL:
        return "C"
    return "W"


def load_inegi_universe() -> dict[str, list[tuple[str, str]]]:
    """Devuelve {cve_ent: [(cvegeo, nombre_muni), ...]} ordenado por cvegeo."""
    out: dict[str, list[tuple[str, str]]] = defaultdict(list)
    with INEGI_CSV.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ent = (r.get("CVE_ENT") or "").strip().zfill(2)
            if ent in ESTADOS_TARGET:
                cvegeo = (r.get("CVEGEO") or "").strip().zfill(5)
                nom = (r.get("NOM_MUN") or "").strip()
                out[ent].append((cvegeo, nom))
    return {k: sorted(v) for k, v in out.items()}


def load_sonora() -> list[dict]:
    rows = []
    src = Path("output/balance/panel_v2_balanced_sonora_pragmatic.csv")
    with src.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            try:
                anio = int(r["ejercicio"])
            except (ValueError, KeyError):
                continue
            if not (ANIO_MIN <= anio <= ANIO_MAX):
                continue
            rows.append({
                "cvegeo": (r.get("cvegeo") or "").strip().zfill(5),
                "estado": "Sonora",
                "municipio": (r.get("municipio") or "").strip(),
                "ejercicio": anio,
                "tipo_esquema": (r.get("tipo_esquema") or "").strip(),
                "source": "sonora_pragmatic",
                "raw_method": (r.get("pragmatic_method") or "").strip(),
            })
    return rows


def load_slp() -> list[dict]:
    rows = []
    src = Path("output/predial_panel_pragmatic.csv")
    with src.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if (r.get("estado") or "").strip().lower() != "sanluispotosi":
                continue
            try:
                anio = int(r["ejercicio"])
            except (ValueError, KeyError):
                continue
            if not (ANIO_MIN <= anio <= ANIO_MAX):
                continue
            cve_ent = (r.get("cve_ent") or "").strip().zfill(2)
            cve_mun = (r.get("cve_mun") or "").strip().zfill(3)
            rows.append({
                "cvegeo": cve_ent + cve_mun,
                "estado": "San Luis Potosi",
                "municipio": (r.get("municipio") or "").strip(),
                "ejercicio": anio,
                "tipo_esquema": (r.get("tipo_esquema") or "").strip(),
                "source": "slp_pragmatic",
                "raw_method": (r.get("imputed") or "").strip(),
            })
    return rows


def build_oaxaca(inegi: dict[str, list[tuple[str, str]]]) -> list[dict]:
    rows = []
    for cvegeo, nom in inegi.get("20", []):
        for y in YEARS:
            tipo = "progresivo" if (cvegeo == "20067" and y >= 2022) else "tarifa_millar"
            rows.append({
                "cvegeo": cvegeo,
                "estado": "Oaxaca",
                "municipio": nom,
                "ejercicio": y,
                "tipo_esquema": tipo,
                "source": "oaxaca_override",
                "raw_method": "user_specified",
            })
    return rows


def load_resto() -> list[dict]:
    """Resto de 11 estados desde panel_v2.csv (excluyendo Oaxaca, Sonora, SLP)."""
    excluded = {"Oaxaca", "Sonora", "San Luis Potosi"}
    rows = []
    src = Path("output/panel_v2.csv")
    with src.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            estado = (r.get("estado") or "").strip()
            if estado in excluded:
                continue
            try:
                anio = int(r["ejercicio"])
            except (ValueError, KeyError):
                continue
            if not (ANIO_MIN <= anio <= ANIO_MAX):
                continue
            rows.append({
                "cvegeo": (r.get("cvegeo") or "").strip().zfill(5),
                "estado": estado,
                "municipio": (r.get("municipio") or "").strip(),
                "ejercicio": anio,
                "tipo_esquema": (r.get("tipo_esquema") or "").strip(),
                "source": "panel_v2",
                "raw_method": (r.get("imputed_method") or "").strip(),
            })
    return rows


def fill_balance(
    rows: list[dict],
    inegi: dict[str, list[tuple[str, str]]],
) -> tuple[list[dict], Counter]:
    """Garantiza 1 fila por (cvegeo, año) para cada muni del universo INEGI.

    Si falta una celda, imputa en este orden:
      1. canonical_muni_fill: tipo modal del muni en años observados
      2. canonical_state_year_fill: tipo modal del estado en ese año
      3. default_fallback: 'tarifa_millar'
    """
    by_key: dict[tuple[str, int], dict] = {}
    for r in rows:
        key = (r["cvegeo"], r["ejercicio"])
        # si hay duplicado, prioriza el primero (sources van en orden Sonora, SLP, Oaxaca, resto)
        if key not in by_key:
            by_key[key] = r

    state_year_tipos: dict[tuple[str, int], Counter] = defaultdict(Counter)
    muni_tipos: dict[str, Counter] = defaultdict(Counter)
    muni_meta: dict[str, tuple[str, str]] = {}
    for r in rows:
        cvegeo = r["cvegeo"]
        ent = cvegeo[:2]
        tipo = r["tipo_esquema"]
        if tipo:
            state_year_tipos[(ent, r["ejercicio"])][tipo] += 1
            muni_tipos[cvegeo][tipo] += 1
        muni_meta[cvegeo] = (r["estado"], r["municipio"])

    out: list[dict] = []
    fill_stats: Counter = Counter()

    for ent, munis in inegi.items():
        estado_canon = ESTADOS_TARGET[ent]
        for cvegeo, nom in munis:
            for y in YEARS:
                key = (cvegeo, y)
                if key in by_key:
                    r = dict(by_key[key])
                    raw = r.get("raw_method") or ""
                    if raw and raw != "false":
                        method = raw
                    elif (r.get("tipo_esquema") or "") == "":
                        method = "blank"
                    else:
                        method = "observed"
                    r["imputed_method_final"] = method
                    out.append(r)
                    fill_stats[method] += 1
                else:
                    estado_real, nom_real = muni_meta.get(cvegeo, (estado_canon, nom))
                    if cvegeo in muni_tipos and muni_tipos[cvegeo]:
                        tipo = muni_tipos[cvegeo].most_common(1)[0][0]
                        method = "canonical_muni_fill"
                    elif (ent, y) in state_year_tipos and state_year_tipos[(ent, y)]:
                        tipo = state_year_tipos[(ent, y)].most_common(1)[0][0]
                        method = "canonical_state_year_fill"
                    else:
                        tipo = "tarifa_millar"
                        method = "default_fallback"
                    out.append({
                        "cvegeo": cvegeo,
                        "estado": estado_real,
                        "municipio": nom_real,
                        "ejercicio": y,
                        "tipo_esquema": tipo,
                        "source": "synthesized",
                        "raw_method": method,
                        "imputed_method_final": method,
                    })
                    fill_stats[method] += 1

    return out, fill_stats


def resolve_wildcard_and_event(rows: list[dict]) -> list[dict]:
    """Resuelve W con forward-fill absorbente y agrega variables event-study."""
    by_muni: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        by_muni[r["cvegeo"]].append(r)

    out: list[dict] = []
    for cvegeo, muni_rows in by_muni.items():
        muni_rows.sort(key=lambda x: x["ejercicio"])

        # primer año T en datos crudos (antes de resolver W)
        first_T_raw = None
        for r in muni_rows:
            if arm(r["tipo_esquema"]) == "T":
                first_T_raw = r["ejercicio"]
                break

        # Resolver W
        for r in muni_rows:
            arm_orig = arm(r["tipo_esquema"])
            r["arm_raw"] = arm_orig
            r["tipo_esquema_raw"] = r["tipo_esquema"]

            if arm_orig != "W":
                r["arm"] = arm_orig
                r["wildcard_resolved"] = ""
            else:
                if first_T_raw is not None and r["ejercicio"] >= first_T_raw:
                    r["arm"] = "T"
                    r["wildcard_resolved"] = "ffill_absorbing_T"
                else:
                    r["arm"] = "C"
                    r["wildcard_resolved"] = "default_C"
            r["treated"] = 1 if r["arm"] == "T" else 0

        arms = [r["arm"] for r in muni_rows]
        n_T = sum(1 for a in arms if a == "T")

        if n_T == len(muni_rows):
            cat = "always_treated"
        elif n_T == 0:
            had_obs = any(r["arm_raw"] != "W" for r in muni_rows)
            cat = "never_treated" if had_obs else "wildcard_only"
        else:
            seen_T = False
            seen_C_after_T = False
            for r in muni_rows:
                if r["arm"] == "T":
                    seen_T = True
                elif r["arm"] == "C" and seen_T:
                    seen_C_after_T = True
                    break
            cat = "reversion" if seen_C_after_T else "treated_cohort"

        treatment_year: int | str = ""
        for r in muni_rows:
            if r["arm"] == "T":
                treatment_year = r["ejercicio"]
                break

        trayectoria = "".join(r["arm"] for r in muni_rows)

        for r in muni_rows:
            r["treatment_year"] = treatment_year
            r["categoria_muni"] = cat
            r["trayectoria"] = trayectoria
            if isinstance(treatment_year, int):
                r["treated_absorbing"] = 1 if r["ejercicio"] >= treatment_year else 0
                r["event_time"] = r["ejercicio"] - treatment_year
                r["cohort"] = str(treatment_year)
            else:
                r["treated_absorbing"] = 0
                r["event_time"] = ""
                r["cohort"] = "never"

        out.extend(muni_rows)

    return sorted(out, key=lambda x: (x["cvegeo"], x["ejercicio"]))


def load_creation_years() -> dict[str, int]:
    """Devuelve {cvegeo: año_creación} para municipios marcados CGO_ACT='M' (Nuevo).

    Si un mismo cvegeo aparece varias veces, se queda con el año más temprano.
    """
    out: dict[str, int] = {}
    if not CHANGES_CSV.exists():
        return out
    with CHANGES_CSV.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            cgo = (r.get("CGO_ACT") or "").strip().strip('"')
            if cgo != "M":
                continue
            ent = (r.get("CVE_ENT") or "").strip().strip('"').zfill(2)
            mun = (r.get("CVE_MUN") or "").strip().strip('"').zfill(3)
            cvegeo = ent + mun
            fecha = (r.get("FECHA_ACT") or "").strip().strip('"')
            try:
                year = int(fecha[:4])
            except ValueError:
                continue
            if cvegeo not in out or year < out[cvegeo]:
                out[cvegeo] = year
    return out


def build_never_treated_states(creation_years: dict[str, int]) -> list[dict]:
    """Genera filas tarifa_millar para los 17 estados never-treated del usuario.

    Para municipios con creation_year > 2010, solo emite filas desde el año
    de creación. CDMX se omite por completo.
    """
    munis_by_ent: dict[str, list[tuple[str, str]]] = defaultdict(list)
    with INEGI_CSV.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            ent = (r.get("CVE_ENT") or "").strip().zfill(2)
            if ent in ESTADOS_NEVER_TREATED:
                cvegeo = (r.get("CVEGEO") or "").strip().zfill(5)
                nom = (r.get("NOM_MUN") or "").strip()
                munis_by_ent[ent].append((cvegeo, nom))

    rows: list[dict] = []
    for ent in sorted(munis_by_ent):
        estado_canon = ESTADOS_NEVER_TREATED[ent]
        for cvegeo, nom in sorted(munis_by_ent[ent]):
            year_start = max(creation_years.get(cvegeo, ANIO_MIN), ANIO_MIN)
            n_years = ANIO_MAX - year_start + 1
            trayectoria = "C" * n_years
            for y in range(year_start, ANIO_MAX + 1):
                rows.append({
                    "cvegeo": cvegeo,
                    "estado": estado_canon,
                    "municipio": nom,
                    "ejercicio": y,
                    "tipo_esquema": "tarifa_millar",
                    "arm": "C",
                    "treated": 0,
                    "treatment_year": "",
                    "treated_absorbing": 0,
                    "event_time": "",
                    "cohort": "never",
                    "categoria_muni": "never_treated",
                    "tipo_esquema_raw": "tarifa_millar",
                    "arm_raw": "C",
                    "wildcard_resolved": "",
                    "trayectoria": trayectoria,
                    "source": "never_treated_assumption",
                    "imputed_method_final": "user_assumption",
                    "raw_method": "user_assumption",
                })
    return rows


def write_full_panel(rows_14: list[dict], rows_never: list[dict]) -> None:
    """Escribe el panel expandido (14 estados con datos + 17 never-treated)."""
    full = rows_14 + rows_never
    full = sorted(full, key=lambda x: (x["cvegeo"], x["ejercicio"]))

    fields_clean = [
        "cvegeo", "estado", "municipio", "ejercicio", "tipo_esquema",
        "arm", "treated", "treatment_year", "treated_absorbing",
        "event_time", "cohort", "categoria_muni",
    ]
    with (OUT_DIR / "panel_event_study_full.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_clean, extrasaction="ignore")
        w.writeheader()
        w.writerows(full)

    fields_long = fields_clean + [
        "tipo_esquema_raw", "arm_raw", "wildcard_resolved",
        "trayectoria", "source", "imputed_method_final", "raw_method",
    ]
    with (OUT_DIR / "panel_event_study_full_long.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_long, extrasaction="ignore")
        w.writeheader()
        w.writerows(full)


def write_panels(rows: list[dict]) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    fields_clean = [
        "cvegeo", "estado", "municipio", "ejercicio", "tipo_esquema",
        "arm", "treated", "treatment_year", "treated_absorbing",
        "event_time", "cohort", "categoria_muni",
    ]
    with (OUT_DIR / "panel_event_study.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_clean, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    fields_long = fields_clean + [
        "tipo_esquema_raw", "arm_raw", "wildcard_resolved",
        "trayectoria", "source", "imputed_method_final", "raw_method",
    ]
    with (OUT_DIR / "panel_event_study_long.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields_long, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    seen: set[str] = set()
    traj_rows: list[dict] = []
    for r in rows:
        if r["cvegeo"] in seen:
            continue
        seen.add(r["cvegeo"])
        traj_rows.append({
            "cvegeo": r["cvegeo"],
            "estado": r["estado"],
            "municipio": r["municipio"],
            "trayectoria": r["trayectoria"],
            "categoria_muni": r["categoria_muni"],
            "treatment_year": r["treatment_year"],
            "cohort": r["cohort"],
        })
    with (OUT_DIR / "treatment_trajectories.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(traj_rows[0].keys()))
        w.writeheader()
        w.writerows(traj_rows)


def write_coverage_report(
    rows: list[dict],
    fill_stats: Counter,
    inegi: dict[str, list[tuple[str, str]]],
) -> None:
    by_estado = Counter(r["estado"] for r in rows)
    arm_dist = Counter(r["arm"] for r in rows)
    arm_raw_dist = Counter(r["arm_raw"] for r in rows)
    src_dist = Counter(r["source"] for r in rows)
    method_dist = Counter(r["imputed_method_final"] for r in rows)

    seen: set[str] = set()
    cat_dist: Counter = Counter()
    cohort_dist: Counter = Counter()
    munis_obs: dict[str, set] = defaultdict(set)
    for r in rows:
        munis_obs[r["estado"]].add(r["cvegeo"])
        if r["cvegeo"] not in seen:
            seen.add(r["cvegeo"])
            cat_dist[r["categoria_muni"]] += 1
            cohort_dist[r["cohort"]] += 1

    total = len(rows)
    n_munis = len(seen)

    L = [
        "# Cobertura del panel event-study (2010-2024)",
        "",
        f"- **Total filas:** {total:,}",
        f"- **Total municipios:** {n_munis:,}",
        f"- **Años:** {ANIO_MIN}-{ANIO_MAX} ({len(YEARS)} años)",
        f"- **Tratamiento absorbente:** wildcard W resuelto vía forward-fill T (decisión del usuario)",
        f"- **Reversiones (T→C):** preservadas en `treated`, marcadas `categoria_muni=reversion`",
        "",
        "## 1. Cobertura por estado",
        "",
        "| Estado | Filas | Munis observados | Munis INEGI | Cob. |",
        "|---|---:|---:|---:|---:|",
    ]
    for ent in sorted(ESTADOS_TARGET):
        estado_canon = ESTADOS_TARGET[ent]
        n_filas = by_estado.get(estado_canon, 0)
        n_esperados = len(inegi.get(ent, []))
        n_obs = len(munis_obs.get(estado_canon, set()))
        cov = (n_obs / n_esperados * 100) if n_esperados else 0
        L.append(f"| {estado_canon} | {n_filas:,} | {n_obs} | {n_esperados} | {cov:.1f}% |")

    L += [
        "",
        "## 2. Distribución de arm (resuelto)",
        "",
        "| arm | conteo | % |",
        "|---|---:|---:|",
    ]
    for a, n in sorted(arm_dist.items()):
        L.append(f"| {a} | {n:,} | {n/total*100:.1f}% |")

    L += [
        "",
        "## 3. Distribución de arm crudo (antes de resolver W)",
        "",
        "| arm_raw | conteo | % |",
        "|---|---:|---:|",
    ]
    for a, n in sorted(arm_raw_dist.items()):
        L.append(f"| {a} | {n:,} | {n/total*100:.1f}% |")

    L += [
        "",
        "## 4. Categorías de muni (1 fila por muni)",
        "",
        "| categoria_muni | # munis | % |",
        "|---|---:|---:|",
    ]
    for c, n in cat_dist.most_common():
        L.append(f"| {c} | {n} | {n/n_munis*100:.1f}% |")

    L += [
        "",
        "## 5. Cohortes de tratamiento",
        "",
        "| cohort | # munis |",
        "|---|---:|",
    ]
    for c, n in sorted(cohort_dist.items()):
        L.append(f"| {c} | {n} |")

    L += [
        "",
        "## 6. Fuentes",
        "",
        "| source | # filas |",
        "|---|---:|",
    ]
    for s, n in src_dist.most_common():
        L.append(f"| {s} | {n:,} |")

    L += [
        "",
        "## 7. Métodos de imputación finales",
        "",
        "| imputed_method_final | # filas |",
        "|---|---:|",
    ]
    for m, n in method_dist.most_common():
        L.append(f"| {m or '(blank)'} | {n:,} |")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "coverage_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> None:
    print("[1/6] Cargando catalogo INEGI...")
    inegi = load_inegi_universe()
    n_munis_target = sum(len(v) for v in inegi.values())
    print(f"      Estados objetivo: {len(inegi)}, total munis: {n_munis_target}")
    print(f"      Esperado: {n_munis_target} x {len(YEARS)} = {n_munis_target * len(YEARS):,} celdas")

    print("[2/6] Cargando fuentes...")
    son = load_sonora()
    slp = load_slp()
    oax = build_oaxaca(inegi)
    resto = load_resto()
    print(f"      Sonora: {len(son)} | SLP: {len(slp)} | Oaxaca (built): {len(oax)} | Resto: {len(resto)}")

    rows = son + slp + oax + resto
    print(f"      Total armonizado: {len(rows):,} filas")

    print("[3/6] Verificando balance + imputando huecos...")
    rows, fill_stats = fill_balance(rows, inegi)
    print(f"      Total despues de balance: {len(rows):,} filas")
    for k, v in fill_stats.most_common():
        print(f"        {k}: {v}")

    print("[4/6] Resolviendo wildcards + variables event-study...")
    rows = resolve_wildcard_and_event(rows)

    print("[5/6] Escribiendo panels...")
    write_panels(rows)

    print("[6/7] Escribiendo coverage_report.md...")
    write_coverage_report(rows, fill_stats, inegi)

    print("[7/7] Construyendo panel_full (14 + 17 never-treated, excl CDMX)...")
    creation_years = load_creation_years()
    rows_never = build_never_treated_states(creation_years)
    n_munis_never = len({r["cvegeo"] for r in rows_never})
    n_recent = sum(1 for cv in creation_years if creation_years[cv] > ANIO_MIN
                   and cv[:2] in ESTADOS_NEVER_TREATED)
    print(f"      Estados never-treated: {len(ESTADOS_NEVER_TREATED)} | munis: {n_munis_never}")
    print(f"      Filas never-treated: {len(rows_never):,} (con {n_recent} munis de reciente creación)")
    write_full_panel(rows, rows_never)
    print(f"      Total panel_full: {len(rows) + len(rows_never):,} filas")

    # Sanity checks
    print("\n=== Validaciones ===")
    odj = sorted([r for r in rows if r["cvegeo"] == "20067"], key=lambda x: x["ejercicio"])
    print(f"OdJ (20067): {len(odj)} filas | trayectoria={odj[0]['trayectoria'] if odj else 'N/A'} | "
          f"treatment_year={odj[0]['treatment_year'] if odj else 'N/A'}")

    expected = {"Sonora": 72, "San Luis Potosi": 59, "Oaxaca": 570}
    for est, n_exp in expected.items():
        n = sum(1 for r in rows if r["estado"] == est)
        flag = "OK" if n == n_exp * len(YEARS) else "WARN"
        print(f"{flag} {est}: {n} (esperado {n_exp}x{len(YEARS)}={n_exp * len(YEARS)})")

    print(f"\nOutputs en {OUT_DIR}/")


if __name__ == "__main__":
    main()
