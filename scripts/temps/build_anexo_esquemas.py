"""Genera el anexo de esquemas de cobro del predial para la tesis (salida LaTeX).

Dos productos, ambos en `output/anexos/`:

  (a) Ilustración de los 5 esquemas
      Para cada esquema (tarifa al millar, progresivo, tasa única, cuota fija /
      tarifa única, mixto) selecciona automáticamente un municipio-año real
      representativo desde `predial-mx-v2/` (JSONs ya en schema_v2) y renderiza
      su tabla en LaTeX (`ej_<tipo>.tex`). El maestro `anexo_esquemas.tex` los
      reúne con prosa descriptiva.

  (b) Estadísticos descriptivos
      Desde `output/panel_v2_raw.csv` (observaciones, sin imputación, ya
      clasificadas vía la capa de validación schema_v2) calcula la distribución
      de esquemas global, por estado y la cobertura. Emite CSVs y tablas LaTeX
      (`tab_*.tex`) reunidas en `anexo_estadisticos.tex`.

La clasificación NO lee `tipo_esquema` crudo de los JSON v1: usa la salida
canónica de schema_v2 (predial-mx-v2/ y panel_v2_raw.csv ya pasaron por
`reclasificar()` / los adapters hardcoded).

Uso:
    python -m scripts.build_anexo_esquemas            # (a) + (b)
    python -m scripts.build_anexo_esquemas --solo a
    python -m scripts.build_anexo_esquemas --solo b
"""

from __future__ import annotations

import argparse
import json
import re
from collections import OrderedDict
from pathlib import Path

import pandas as pd

from src.core.validation import reclasificar

# ── Rutas ──
V2_ROOT = Path("predial-mx-v2")
DATA_ROOT = Path("data")
PANEL_RAW = Path("output/panel_v2_raw.csv")
OUT_DIR = Path("output/anexos")

# Ejemplos curados por esquema de la tesis: (estado_slug, año, municipio_slug).
# Para cambiar un ejemplo, edita esta tabla. La forma canónica schema_v2 se
# resuelve desde predial-mx-v2/ o, si no está, desde data/ vía reclasificar().
EJEMPLOS_FIJOS = {
    "tarifa_millar": ("queretaro", 2015, "san_juan_del_rio"),
    "progresivo": ("jalisco", 2023, "zapopan"),
    "tasa_unica": ("oaxaca", 2014, "santa_maria_huatulco"),
    "cuota_fija": ("yucatan", 2011, "teya"),
    "mixto": ("tamaulipas", 2018, "tampico"),
}

# ── Vocabulario de esquemas ──

# schema_v2 -> categoría de la tesis (5 esquemas + "otro")
SCHEMA_V2_A_TESIS = {
    "tarifa_millar": "tarifa_millar",
    "progresivo": "progresivo",
    "tasa_unica": "tasa_unica",
    "cuota_fija_simple": "cuota_fija",
    "cuota_fija_escalonada": "cuota_fija",
    "cuota_fija": "cuota_fija",
    "mixto": "mixto",
    "otro_no_clasificado": "otro",
    "desconocido": "otro",
}

# Orden y etiqueta legible de las categorías de la tesis.
TESIS_ORDEN = ["tarifa_millar", "progresivo", "tasa_unica", "cuota_fija", "mixto", "otro"]
TESIS_LABEL = {
    "tarifa_millar": "Tarifa al millar",
    "progresivo": "Progresivo (tasa marginal)",
    "tasa_unica": "Tasa única",
    "cuota_fija": "Cuota fija (tarifa única)",
    "mixto": "Mixto",
    "otro": "Otro / no clasificado",
}

# Estados extraídos vía LLM vs. código estatal uniforme (hardcoded).
ESTADOS_CODIGO_ESTATAL = {"Chihuahua", "Colima", "Mexico", "Sinaloa", "Tabasco"}

ESTADO_SLUG_PRETTY = {
    "coahuila": "Coahuila", "guanajuato": "Guanajuato", "jalisco": "Jalisco",
    "oaxaca": "Oaxaca", "queretaro": "Querétaro", "sanluispotosi": "San Luis Potosí",
    "sonora": "Sonora", "tamaulipas": "Tamaulipas", "yucatan": "Yucatán",
    "chihuahua": "Chihuahua", "colima": "Colima", "edomex": "Estado de México",
    "sinaloa": "Sinaloa", "tabasco": "Tabasco",
}

_CONECTORES = {"de", "del", "la", "las", "los", "y", "el", "en"}
_FNAME_RE = re.compile(r"_PREDIAL_(\d{4})_(.+)$")


# ── Utilidades de formato ──

def latex_escape(s: str) -> str:
    """Escapa caracteres especiales de LaTeX en texto plano."""
    if s is None:
        return ""
    repl = {
        "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
        "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    out = []
    for ch in str(s):
        out.append(repl.get(ch, ch))
    return "".join(out)


def pretty_muni(slug: str) -> str:
    """piedras_negras -> Piedras Negras; hidalgo_del_parral -> Hidalgo del Parral."""
    palabras = slug.split("_")
    res = []
    for i, w in enumerate(palabras):
        if i > 0 and w in _CONECTORES:
            res.append(w)
        else:
            res.append(w.capitalize())
    return " ".join(res)


def fmt_num(x) -> str:
    """Número genérico sin ceros sobrantes (5.0 -> 5; 0.00443 -> 0.00443)."""
    if x is None:
        return "—"
    f = float(x)
    if f == int(f):
        return f"{int(f):,}".replace(",", "{,}")
    return f"{f:g}"


def fmt_money(x) -> str:
    r"""Pesos: \$1{,}234.56 (o entero si es redondo)."""
    if x is None:
        return "—"
    f = float(x)
    if f == int(f):
        cuerpo = f"{int(f):,}".replace(",", "{,}")
    else:
        cuerpo = f"{f:,.2f}".replace(",", "{,}")
    return rf"\${cuerpo}"


def fmt_limite(x) -> str:
    """Límite de rango: entero con miles, o 'En adelante' si None."""
    if x is None:
        return "En adelante"
    return fmt_money(x)


# ── (a) Selección + render de ejemplos ──

def _parse_v2_path(p: Path):
    """(estado_slug, anio, muni_slug) desde predial-mx-v2/<estado>/<PREFIJO>_PREDIAL_<anio>_<slug>.json"""
    estado_slug = p.parent.name
    m = _FNAME_RE.search(p.stem)
    if not m:
        return None
    return estado_slug, int(m.group(1)), m.group(2)


def _iter_v2_docs():
    """Itera (estado_slug, anio, slug, predial_dict) sobre predial-mx-v2/."""
    for p in sorted(V2_ROOT.glob("*/*.json")):
        meta = _parse_v2_path(p)
        if not meta:
            continue
        try:
            doc = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        predial = doc.get("predial")
        if not isinstance(predial, dict) or not predial.get("tipo_esquema"):
            continue
        yield (*meta, predial)


def _score_candidato(tipo_v2: str, predial: dict) -> float | None:
    """Puntaje de 'idoneidad ilustrativa' (mayor = mejor). None = descartar."""
    tabla = predial.get("tabla") or []
    n = len(tabla)
    if tipo_v2 == "tarifa_millar":
        if not (2 <= n <= 5):
            return None
        tasas = [r.get("tasa_millar") for r in tabla]
        if any(t is None for t in tasas):
            return None
        score = -abs(n - 3)
        # Penaliza filas con tasa 0 y premia tasas distintas (ejemplo más nítido).
        score -= 3 * sum(1 for t in tasas if not t)
        if len(set(tasas)) == len(tasas):
            score += 1
        # Premia tener grupos diferenciados (urbano/rústico/...).
        if len({r.get("grupo") for r in tabla}) >= 2:
            score += 1
        # Premia tasas expresadas como "al millar" genuino (3, 5, 12.5) y
        # penaliza la representación en factor decimal (0.003, 0.005).
        if all(t and t >= 0.5 for t in tasas):
            score += 2
        # Penaliza descripciones largas (desbordan la tabla en el PDF).
        score -= 2 * sum(1 for r in tabla if len(r.get("descripcion", "") or "") > 45)
        return score
    if tipo_v2 == "progresivo":
        if not (4 <= n <= 7):
            return None
        return -abs(n - 5)
    if tipo_v2 == "tasa_unica":
        if n != 1:
            return None
        r0 = tabla[0]
        tasa = r0.get("tasa")
        if not tasa:
            return None
        score = 0.0
        # Premia la representación "al millar" legible (2, 3.5, 12) sobre el
        # factor decimal (0.00443) y descripciones cortas.
        if r0.get("unidad") == "al_millar" and tasa >= 0.5:
            score += 3
        if len(r0.get("descripcion", "") or "") <= 45:
            score += 1
        return score
    if tipo_v2 == "cuota_fija_simple":
        if n != 1:
            return None
        if not tabla[0].get("monto"):
            return None
        return 0.0
    if tipo_v2 == "mixto":
        if not (3 <= n <= 6):
            return None
        nombres = OrderedDict()
        for r in tabla:
            for c in r.get("columnas") or []:
                nombres[c.get("nombre")] = True
        ncols = len(nombres)
        if not (2 <= ncols <= 3):
            return None
        return -(abs(ncols - 2) * 2 + abs(n - 4))
    return None


# Categoría tesis -> tipo schema_v2 usado como ejemplo.
EJEMPLO_TIPO_V2 = {
    "tarifa_millar": "tarifa_millar",
    "progresivo": "progresivo",
    "tasa_unica": "tasa_unica",
    "cuota_fija": "cuota_fija_simple",
    "mixto": "mixto",
}


def cargar_predial_v2(estado_slug: str, anio: int, slug: str):
    """Devuelve (predial_v2_dict, ruta) para un municipio-año.

    Prioriza predial-mx-v2/ (ya en schema_v2); si no está, lee el JSON v1 de
    data/ y lo pasa por reclasificar() para obtener la forma canónica.
    """
    patron = f"*_PREDIAL_{anio}_{slug}.json"
    est_dir = V2_ROOT / estado_slug
    if est_dir.exists():
        for p in sorted(est_dir.glob(patron)):
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            pred = doc.get("predial")
            if isinstance(pred, dict) and pred.get("tipo_esquema") and "tabla" in pred:
                return pred, p
    jdir = DATA_ROOT / estado_slug / "json_predial"
    if jdir.exists():
        for p in sorted(jdir.rglob(patron)):
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            pred = doc.get("predial")
            if isinstance(pred, dict):
                return reclasificar(pred).model_dump(), p
    return None, None


def seleccionar_ejemplos() -> dict:
    """Elige el municipio-año representativo de cada esquema de la tesis."""
    quiero = {v: k for k, v in EJEMPLO_TIPO_V2.items()}
    mejores: dict[str, tuple] = {}  # tesis_cat -> (score, estado, anio, slug, predial)
    for estado_slug, anio, slug, predial in _iter_v2_docs():
        tipo_v2 = predial["tipo_esquema"]
        if tipo_v2 not in quiero:
            continue
        score = _score_candidato(tipo_v2, predial)
        if score is None:
            continue
        cat = quiero[tipo_v2]
        cur = mejores.get(cat)
        # Mejor score; desempate determinista por menor (estado, anio, slug).
        if (
            cur is None
            or score > cur[0]
            or (score == cur[0] and (estado_slug, anio, slug) < (cur[1], cur[2], cur[3]))
        ):
            mejores[cat] = (score, estado_slug, anio, slug, predial)
    return mejores


def _caption(cat: str, estado_slug: str, anio: int, slug: str) -> str:
    est = ESTADO_SLUG_PRETTY.get(estado_slug, estado_slug.capitalize())
    return f"{TESIS_LABEL[cat]}: {pretty_muni(slug)}, {est} ({anio})."


def _factor_millar(tabla: list) -> int:
    """1000 si las tasas están en factor decimal (máx < 0.5), 1 si ya en al millar.

    Algunos estados (p. ej. Querétaro) guardan la tasa como factor (0.0016) en
    vez de al millar (1.6); las tasas al millar típicas del predial son ≥ ~0.5.
    """
    tasas = [r.get("tasa_millar") for r in tabla if r.get("tasa_millar")]
    if tasas and max(tasas) < 0.5:
        return 1000
    return 1


def _tabla_tarifa_millar(tabla: list) -> str:
    factor = _factor_millar(tabla)
    filas = []
    for r in tabla:
        cfa = r.get("cuota_fija_adicional")
        extra = fmt_money(cfa["monto"]) if isinstance(cfa, dict) else "—"
        t = r.get("tasa_millar")
        tasa_disp = fmt_num(t * factor) if t is not None else "—"
        filas.append(
            f"{latex_escape(r.get('grupo',''))} & {latex_escape(r.get('descripcion',''))} "
            f"& {tasa_disp} & {extra} \\\\"
        )
    cuerpo = "\n".join(filas)
    return (
        "\\begin{tabular}{llrr}\n\\toprule\n"
        "Grupo & Descripción & Tasa (al millar) & Cuota fija ad. \\\\\n\\midrule\n"
        f"{cuerpo}\n\\bottomrule\n\\end{{tabular}}"
    )


def _tabla_progresivo(tabla: list) -> str:
    filas = []
    for r in tabla:
        filas.append(
            f"{r.get('n_rango')} & {fmt_limite(r.get('inferior'))} & {fmt_limite(r.get('superior'))} "
            f"& {fmt_money(r.get('cuota_fija'))} & {fmt_num(r.get('tasa_marginal'))} \\\\"
        )
    cuerpo = "\n".join(filas)
    return (
        "\\begin{tabular}{rrrrr}\n\\toprule\n"
        "Rango & Límite inferior & Límite superior & Cuota fija & Tasa marginal \\\\\n\\midrule\n"
        f"{cuerpo}\n\\bottomrule\n\\end{{tabular}}"
    )


def _tabla_tasa_unica(tabla: list) -> str:
    r = tabla[0]
    fila = (
        f"{latex_escape(r.get('descripcion',''))} & {fmt_num(r.get('tasa'))} "
        f"& {latex_escape(r.get('base_calculo',''))} & {latex_escape(r.get('unidad',''))} \\\\"
    )
    return (
        "\\begin{tabular}{lrll}\n\\toprule\n"
        "Descripción & Tasa & Base de cálculo & Unidad \\\\\n\\midrule\n"
        f"{fila}\n\\bottomrule\n\\end{{tabular}}"
    )


def _tabla_cuota_fija(tabla: list) -> str:
    r = tabla[0]
    fila = (
        f"{latex_escape(r.get('descripcion',''))} & {fmt_money(r.get('monto'))} "
        f"& {latex_escape(r.get('periodicidad',''))} & {latex_escape(r.get('unidad',''))} \\\\"
    )
    return (
        "\\begin{tabular}{lrll}\n\\toprule\n"
        "Descripción & Monto & Periodicidad & Unidad \\\\\n\\midrule\n"
        f"{fila}\n\\bottomrule\n\\end{{tabular}}"
    )


def _fmt_celda_mixta(c: dict) -> str:
    if c is None:
        return "—"
    if c.get("tipo") == "cuota_fija":
        return fmt_money(c.get("valor"))
    return fmt_num(c.get("valor"))  # tasa al millar / marginal


def _tabla_mixto(tabla: list) -> str:
    nombres = OrderedDict()
    for r in tabla:
        for c in r.get("columnas") or []:
            nombres[c.get("nombre")] = True
    cols = list(nombres.keys())
    pretty = [pretty_muni(n) for n in cols]
    # Nombres largos desbordan: usa "Col. k" en el encabezado + leyenda al pie.
    usar_legend = any(len(pn) > 16 for pn in pretty) or len(cols) > 3
    headers = [f"Col. {i + 1}" for i in range(len(cols))] if usar_legend else pretty
    colspec = "rrr" + "r" * len(cols)
    enc_cols = " & ".join(latex_escape(h) for h in headers)
    filas = []
    for r in tabla:
        by_name = {c.get("nombre"): c for c in (r.get("columnas") or [])}
        celdas = " & ".join(_fmt_celda_mixta(by_name.get(n)) for n in cols)
        filas.append(
            f"{r.get('n_rango')} & {fmt_limite(r.get('inferior'))} & {fmt_limite(r.get('superior'))} "
            f"& {celdas} \\\\"
        )
    cuerpo = "\n".join(filas)
    tab = (
        f"\\begin{{tabular}}{{{colspec}}}\n\\toprule\n"
        f"Rango & Lím. inf. & Lím. sup. & {enc_cols} \\\\\n\\midrule\n"
        f"{cuerpo}\n\\bottomrule\n\\end{{tabular}}"
    )
    if usar_legend:
        leg = "; ".join(f"Col. {i + 1} = {pretty[i]}" for i in range(len(cols)))
        tab += f"\n\\par\\smallskip\\footnotesize Columnas: {latex_escape(leg)}."
    return tab


_RENDER = {
    "tarifa_millar": _tabla_tarifa_millar,
    "progresivo": _tabla_progresivo,
    "tasa_unica": _tabla_tasa_unica,
    "cuota_fija": _tabla_cuota_fija,
    "mixto": _tabla_mixto,
}

DESCRIPCION_ESQUEMA = {
    "tarifa_millar": (
        "Aplica una tasa fija por cada millar (\\textperthousand) del valor catastral, "
        "diferenciada por tipo de predio (urbano, rústico, etc.). El impuesto es "
        "lineal en el valor: $T = \\tau \\cdot V / 1000$."
    ),
    "progresivo": (
        "Tabla por rangos de valor catastral en la que cada tramo agrega una cuota "
        "fija más una tasa marginal sobre el excedente del límite inferior: "
        "$T = c_i + \\tau_i\\,(V - L_i)$. La carga efectiva crece con el valor."
    ),
    "tasa_unica": (
        "Una sola tasa (porcentaje o al millar) aplicada uniformemente al valor "
        "catastral de todos los predios, sin categorías ni rangos."
    ),
    "cuota_fija": (
        "Monto fijo en pesos por predio, independiente del valor catastral. En la "
        "tesis se denomina \\emph{tarifa única}. Algunos municipios la escalonan por "
        "rangos de valor (variante \\emph{cuota fija escalonada}), que aquí se agrupa "
        "dentro de esta categoría."
    ),
    "mixto": (
        "Estructura híbrida por rangos que combina columnas heterogéneas (cuotas "
        "fijas y/o tasas) según el tipo de predio, sin reducirse a las variantes "
        "anteriores."
    ),
}


def _resolver_ejemplos(auto: bool) -> dict:
    """cat_tesis -> (estado_slug, anio, slug, predial_v2_dict)."""
    if auto:
        mejores = seleccionar_ejemplos()
        return {cat: (e, a, s, pred) for cat, (_sc, e, a, s, pred) in mejores.items()}
    resuelto = {}
    for cat, (estado_slug, anio, slug) in EJEMPLOS_FIJOS.items():
        predial, ruta = cargar_predial_v2(estado_slug, anio, slug)
        if predial is None:
            print(f"  [!] no se encontró JSON para {cat}: {estado_slug}/{anio}/{slug}")
            continue
        tipo_cat = SCHEMA_V2_A_TESIS.get(predial.get("tipo_esquema"), "otro")
        if tipo_cat != cat:
            print(
                f"  [!] {estado_slug}/{anio}/{slug} clasifica como '{tipo_cat}', "
                f"no '{cat}' — se renderiza igual pero revisa el mapeo ({ruta})."
            )
        resuelto[cat] = (estado_slug, anio, slug, predial)
    return resuelto


def build_examples(out_dir: Path, auto: bool = False) -> None:
    print("== (a) Ejemplos de esquemas ==")
    ejemplos = _resolver_ejemplos(auto)
    out_dir.mkdir(parents=True, exist_ok=True)

    maestro = [
        "% Anexo A — Esquemas de cobro del impuesto predial",
        "% Generado por scripts/build_anexo_esquemas.py",
        "% Requiere: \\usepackage{booktabs}",
        "",
    ]
    for cat in EJEMPLO_TIPO_V2:
        if cat not in ejemplos:
            print(f"  [!] sin ejemplo para {cat}")
            continue
        estado_slug, anio, slug, predial = ejemplos[cat]
        tabla = predial.get("tabla") or []
        cuerpo_tabla = _RENDER[cat](tabla)
        caption = _caption(cat, estado_slug, anio, slug)
        minimo = predial.get("minimo_predial")
        nota_min = ""
        if isinstance(minimo, dict):
            nota_min = (
                f"\n\\par\\smallskip\\footnotesize Mínimo predial: "
                f"{fmt_money(minimo.get('monto'))} {latex_escape(minimo.get('unidad',''))} "
                f"({latex_escape(minimo.get('periodicidad',''))})."
            )
        tex = (
            f"% {cat} — {caption}\n"
            f"\\begin{{table}}[htbp]\n\\centering\n\\small\n"
            f"{cuerpo_tabla}\n"
            f"\\caption{{{latex_escape(caption)}}}\n"
            f"\\label{{tab:esquema-{cat}}}\n"
            f"{nota_min}\n"
            f"\\end{{table}}\n"
        )
        fpath = out_dir / f"ej_{cat}.tex"
        fpath.write_text(tex, encoding="utf-8")
        print(f"  {cat:14s} -> {ESTADO_SLUG_PRETTY.get(estado_slug,estado_slug)} / {pretty_muni(slug)} {anio}  ({fpath})")

        maestro.append(f"\\subsection*{{{TESIS_LABEL[cat]}}}")
        maestro.append(DESCRIPCION_ESQUEMA[cat])
        maestro.append(f"\\input{{ej_{cat}.tex}}")
        maestro.append("")

    (out_dir / "anexo_esquemas.tex").write_text("\n".join(maestro) + "\n", encoding="utf-8")
    print(f"  maestro -> {out_dir / 'anexo_esquemas.tex'}")


# ── (b) Estadísticos descriptivos ──

def _latex_tabular(df: pd.DataFrame, colspec: str, header: list[str]) -> str:
    enc = " & ".join(header) + " \\\\"
    filas = []
    for _, row in df.iterrows():
        filas.append(" & ".join(str(v) for v in row.tolist()) + " \\\\")
    cuerpo = "\n".join(filas)
    return (
        f"\\begin{{tabular}}{{{colspec}}}\n\\toprule\n{enc}\n\\midrule\n"
        f"{cuerpo}\n\\bottomrule\n\\end{{tabular}}"
    )


def build_stats(out_dir: Path) -> None:
    print("== (b) Estadísticos descriptivos ==")
    out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(PANEL_RAW, dtype=str)
    df["ejercicio"] = df["ejercicio"].astype(int)
    df = df[(df["estado"].notna()) & (df["estado"].str.strip() != "")].copy()
    df["esquema"] = df["tipo_esquema"].map(SCHEMA_V2_A_TESIS).fillna("otro")
    df["metodo"] = df["estado"].apply(
        lambda e: "código estatal" if e in ESTADOS_CODIGO_ESTATAL else "LLM"
    )

    total = len(df)
    print(f"  observaciones (estado×municipio×año): {total}")

    # --- Tabla 1: distribución global ---
    dist = df["esquema"].value_counts().reindex(TESIS_ORDEN).fillna(0).astype(int)
    dist_df = pd.DataFrame({
        "Esquema": [TESIS_LABEL[k] for k in TESIS_ORDEN],
        "Observaciones": [dist[k] for k in TESIS_ORDEN],
        "Porcentaje": [f"{100*dist[k]/total:.1f}\\%" for k in TESIS_ORDEN],
    })
    dist_df.to_csv(out_dir / "dist_global.csv", index=False)
    tab1 = _latex_tabular(dist_df, "lrr", ["Esquema", "Obs.", "\\%"])

    # --- Tabla 2: esquemas por estado (conteos + N) ---
    ct = pd.crosstab(df["estado"], df["esquema"])
    for k in TESIS_ORDEN:
        if k not in ct.columns:
            ct[k] = 0
    ct = ct[TESIS_ORDEN]
    ct["N"] = ct.sum(axis=1)
    ct = ct.sort_index()
    ct.to_csv(out_dir / "esquemas_por_estado.csv")
    ct_tex = ct.reset_index()
    ct_tex.columns = ["Estado"] + [TESIS_LABEL[k] for k in TESIS_ORDEN] + ["N"]
    ct_tex["Estado"] = ct_tex["Estado"].apply(latex_escape)
    tab2 = _latex_tabular(
        ct_tex, "l" + "r" * (len(TESIS_ORDEN) + 1),
        ["Estado", "T. millar", "Progr.", "Tasa única", "Cuota fija", "Mixto", "Otro", "N"],
    )

    # --- Tabla 2b: por estado en porcentaje del estado ---
    pct = ct[TESIS_ORDEN].div(ct["N"], axis=0) * 100
    pct_df = pct.round(1).reset_index()
    pct_df.to_csv(out_dir / "esquemas_por_estado_pct.csv", index=False)

    # --- Tabla 3: cobertura por estado ---
    cob = df.groupby("estado").agg(
        n_obs=("cvegeo", "size"),
        n_municipios=("cvegeo", "nunique"),
        anio_min=("ejercicio", "min"),
        anio_max=("ejercicio", "max"),
        n_anios=("ejercicio", "nunique"),
    ).reset_index()
    cob["metodo"] = cob["estado"].apply(
        lambda e: "código estatal" if e in ESTADOS_CODIGO_ESTATAL else "LLM"
    )
    cob = cob.sort_values("estado")
    cob.to_csv(out_dir / "cobertura_por_estado.csv", index=False)
    cob_tex = cob.copy()
    cob_tex["periodo"] = cob_tex["anio_min"].astype(str) + "–" + cob_tex["anio_max"].astype(str)
    cob_tex["estado"] = cob_tex["estado"].apply(latex_escape)
    cob_tex = cob_tex[["estado", "n_municipios", "periodo", "n_anios", "n_obs", "metodo"]]
    tab3 = _latex_tabular(
        cob_tex, "lrcrrl",
        ["Estado", "Municipios", "Periodo", "Años", "Obs.", "Fuente"],
    )

    # --- Tabla 4: evolución temporal (esquema × año, % del año) ---
    ct_yr = pd.crosstab(df["ejercicio"], df["esquema"])
    for k in TESIS_ORDEN:
        if k not in ct_yr.columns:
            ct_yr[k] = 0
    ct_yr = ct_yr[TESIS_ORDEN]
    ct_yr.to_csv(out_dir / "esquemas_por_anio.csv")

    # --- Maestro LaTeX ---
    maestro = [
        "% Anexo B — Estadísticos descriptivos de esquemas de cobro",
        "% Generado por scripts/build_anexo_esquemas.py",
        "% Requiere: \\usepackage{booktabs}",
        "% Fuente: output/panel_v2_raw.csv (observaciones, sin imputación;",
        "% clasificación canónica schema_v2).",
        "",
        f"\\paragraph{{Universo.}} {total} observaciones (estado $\\times$ municipio "
        f"$\\times$ año) en {df['estado'].nunique()} estados, "
        f"{df['ejercicio'].min()}--{df['ejercicio'].max()}.",
        "",
        "\\begin{table}[htbp]\\centering\\small",
        tab1,
        "\\caption{Distribución de esquemas de cobro del predial (todas las observaciones).}",
        "\\label{tab:dist-global-esquemas}",
        "\\end{table}",
        "",
        "\\begin{table}[htbp]\\centering\\small",
        tab2,
        "\\caption{Esquemas de cobro por estado (número de observaciones).}",
        "\\label{tab:esquemas-por-estado}",
        "\\end{table}",
        "",
        "\\begin{table}[htbp]\\centering\\small",
        tab3,
        "\\caption{Cobertura del panel por estado. Fuente indica si la tarifa se "
        "extrajo de leyes de ingresos municipales (LLM) o de un código/tarifa "
        "estatal uniforme.}",
        "\\label{tab:cobertura-estados}",
        "\\end{table}",
        "",
    ]
    (out_dir / "anexo_estadisticos.tex").write_text("\n".join(maestro) + "\n", encoding="utf-8")

    # Reporte por consola.
    print("\n  Distribución global:")
    for k in TESIS_ORDEN:
        print(f"    {TESIS_LABEL[k]:30s} {dist[k]:6d}  {100*dist[k]/total:5.1f}%")
    print(f"\n  CSVs y .tex escritos en {out_dir}")


def main():
    ap = argparse.ArgumentParser(description="Genera el anexo de esquemas (LaTeX).")
    ap.add_argument("--solo", choices=["a", "b"], help="Solo (a) ejemplos o (b) estadísticos.")
    ap.add_argument("--auto", action="store_true",
                    help="Selecciona ejemplos automáticamente en vez de usar EJEMPLOS_FIJOS.")
    ap.add_argument("--out", default=str(OUT_DIR), help="Directorio de salida.")
    args = ap.parse_args()
    out_dir = Path(args.out)
    if args.solo != "b":
        build_examples(out_dir, auto=args.auto)
    if args.solo != "a":
        build_stats(out_dir)
    print("\nListo.")


if __name__ == "__main__":
    main()
