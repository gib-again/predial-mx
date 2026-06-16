"""Reporte de ambigüedad en identificadores de filas tarifarias.

El LLM genera identificadores (clave en tarifa_millar; nombre en
columnas de mixto) libremente — sin slugify de Python, sin instrucción
explícita de prompt. Esto produce:

  - Inconsistencias slugify (mayúsculas, signos, etc.).
  - Fragmentación intra-estado: el mismo concepto se nombra de N formas.
  - Solapamiento inter-estado: conceptos típicos (predio urbano, baldío,
    rústico) reciben slugs muy distintos en cada estado.

El reporte cubre:
  - tarifa_millar (campo `clave` + `grupo`)
  - mixto (campo `nombre` en cada `columna`; el `grupo` queda vacío
    porque mixto no lo tiene por fila)

Outputs en `output/anexos/`:
  - claves_tarifa_millar.csv          un renglón por (tipo_esquema, estado,
                                       grupo, clave) con frecuencia, ejemplo
                                       descripcion, flag slugify_match,
                                       n_municipios, n_años.
  - claves_tarifa_millar_resumen.md   markdown con secciones por estado,
                                       fragmentación severa, inconsistencias
                                       slugify, solapamientos inter-estado.

Nota: el nombre del archivo conserva "tarifa_millar" por compatibilidad
retro, pero el contenido cubre ambos esquemas.

Uso:
  python -m scripts.temps.reporte_claves_tarifa_millar
"""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from scripts.temps.build_anexo_esquemas import ESTADO_SLUG_PRETTY
from scripts.temps.detectar_cambios_interanuales import iter_corpus
from src.core.text_utils import slugify

OUT_DIR = Path("output/anexos")

# Conceptos canónicos a rastrear inter-estado (sub-strings normalizados).
CONCEPTOS = {
    "urbano_edificado": ("urbano", "edif"),
    "urbano_baldio": ("urbano", "bald"),
    "urbano_generico": ("urbano",),
    "rustico": ("rustic",),
    "ejidal": ("ejid",),
    "comercial": ("comerc",),
    "habitacional": ("habit",),
    "industrial": ("industr",),
}


def _norm(s: str) -> str:
    return slugify(s or "")


def _coincide_concepto(clave: str, sustrings: tuple) -> bool:
    n = _norm(clave)
    return all(sub in n for sub in sustrings)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out-csv", default=str(OUT_DIR / "claves_tarifa_millar.csv"))
    ap.add_argument("--out-md", default=str(OUT_DIR / "claves_tarifa_millar_resumen.md"))
    ap.add_argument("--out-mapa", default=str(OUT_DIR / "claves_mapa_exhaustivo.md"),
                    help=("Mapa markdown organizado por (tipo_esquema, estado, grupo) "
                          "con TODAS las claves listadas — para trabajo de consolidación."))
    ap.add_argument("--no-mapa", action="store_true",
                    help="No generar el mapa exhaustivo (acelera la corrida).")
    ap.add_argument("--include-hardcoded", action="store_true",
                    help="Incluir estados hardcoded (omitidos por default).")
    args = ap.parse_args()

    # Aggregador: (tipo_esquema, estado, grupo, clave) -> {n, descripciones, munis, anios, valores}
    agg: dict[tuple[str, str, str, str], dict] = defaultdict(
        lambda: {"n": 0, "descripciones": [], "munis": set(),
                 "anios": set(), "valores": []}
    )

    print("Iterando corpus...")
    n_jsons = 0
    n_filas = 0
    n_por_tipo: dict[str, int] = defaultdict(int)
    for est_slug, anio, muni_slug, predial, _path in iter_corpus(
        include_hardcoded=args.include_hardcoded
    ):
        n_jsons += 1
        if n_jsons % 2000 == 0:
            print(f"  {n_jsons} JSONs procesados...")
        tipo = predial.get("tipo_esquema")
        tabla = predial.get("tabla") or []

        if tipo == "tarifa_millar":
            for row in tabla:
                grupo = (row.get("grupo") or "").strip()
                clave = (row.get("clave") or "").strip()
                if not clave:
                    continue
                key = (tipo, est_slug, grupo, clave)
                rec = agg[key]
                rec["n"] += 1
                desc = (row.get("descripcion") or "").strip()
                if desc and len(rec["descripciones"]) < 3:
                    rec["descripciones"].append(desc)
                rec["munis"].add(muni_slug)
                rec["anios"].add(anio)
                t = row.get("tasa_millar")
                if t is not None and len(rec["valores"]) < 5:
                    rec["valores"].append(t)
                n_filas += 1
                n_por_tipo[tipo] += 1
        elif tipo == "mixto":
            # En mixto el identificador esta en columnas[*].nombre; no hay grupo
            # por fila. Tratamos cada columna como una "clave" con grupo vacio.
            for row in tabla:
                for col in row.get("columnas") or []:
                    clave = (col.get("nombre") or "").strip()
                    if not clave:
                        continue
                    key = (tipo, est_slug, "", clave)
                    rec = agg[key]
                    rec["n"] += 1
                    rec["munis"].add(muni_slug)
                    rec["anios"].add(anio)
                    v = col.get("valor")
                    if v is not None and len(rec["valores"]) < 5:
                        rec["valores"].append(v)
                    n_filas += 1
                    n_por_tipo[tipo] += 1

    print(f"  {n_jsons} JSONs leidos; {n_filas} filas con identificador")
    for t, n in sorted(n_por_tipo.items(), key=lambda x: -x[1]):
        print(f"    {t}: {n}")
    print(f"  {len(agg)} (tipo_esquema, estado, grupo, clave) unicos")

    # CSV detallado.
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = Path(args.out_csv)
    cols = ["tipo_esquema", "estado_slug", "estado", "grupo", "clave",
            "n_apariciones", "n_municipios", "n_anios", "slugify_match",
            "slugify_sugerido", "valores_observados", "descripcion_ejemplo"]
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for (tipo, est, grupo, clave), rec in sorted(
            agg.items(), key=lambda x: (-x[1]["n"], x[0])
        ):
            sug = slugify(clave)
            w.writerow({
                "tipo_esquema": tipo,
                "estado_slug": est,
                "estado": ESTADO_SLUG_PRETTY.get(est, est),
                "grupo": grupo,
                "clave": clave,
                "n_apariciones": rec["n"],
                "n_municipios": len(rec["munis"]),
                "n_anios": len(rec["anios"]),
                "slugify_match": "sí" if sug == clave else "no",
                "slugify_sugerido": sug if sug != clave else "",
                "valores_observados": "|".join(str(t) for t in rec["valores"][:5]),
                "descripcion_ejemplo": (rec["descripciones"][0] if rec["descripciones"] else "")[:200],
            })
    print(f"  CSV: {csv_path}")

    # Análisis para markdown. Indexa por (tipo, est, grupo) para mantener
    # separados los esquemas en las vistas de fragmentación.
    by_tipo_estado: dict[tuple[str, str], dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for (tipo, est, grupo, clave), _rec in agg.items():
        by_tipo_estado[(tipo, est)][grupo].add(clave)

    inconsistencias_slug = [
        (tipo, est, grupo, clave, slugify(clave))
        for (tipo, est, grupo, clave), _ in agg.items()
        if slugify(clave) != clave
    ]

    # Fragmentación intra-(tipo, estado, grupo).
    fragmentacion = [
        (tipo, est, grupo, len(claves), claves)
        for (tipo, est), grupos in by_tipo_estado.items()
        for grupo, claves in grupos.items()
    ]
    fragmentacion.sort(key=lambda x: -x[3])

    # Solapamiento inter-estado por concepto (sin distinguir tipo — el concepto
    # es semántico, no estructural).
    concepto_por_estado: dict[str, dict[str, set]] = defaultdict(lambda: defaultdict(set))
    for (_tipo, est, _grupo, clave), _rec in agg.items():
        for concepto, sustrings in CONCEPTOS.items():
            if _coincide_concepto(clave, sustrings):
                concepto_por_estado[concepto][est].add(clave)

    # Markdown.
    md_path = Path(args.out_md)
    tipos_str = ", ".join(f"{t}={n}" for t, n in
                          sorted(n_por_tipo.items(), key=lambda x: -x[1]))
    md = [
        "# Reporte de ambigüedad en identificadores tarifarios",
        "",
        f"Corpus: **{n_jsons} JSONs** procesados, **{n_filas} filas** con "
        f"identificador ({tipos_str}), **{len(agg)} identificadores únicos** "
        "por (tipo_esquema, estado, grupo, clave).",
        "",
        "Cubre dos esquemas:",
        "",
        "- `tarifa_millar`: campo `clave` agrupado por `grupo` (urbano, rústico, ...).",
        "- `mixto`: campo `nombre` en cada `columna`; el `grupo` queda vacío.",
        "",
        "## 1. Inconsistencias slugify",
        "",
        f"{len(inconsistencias_slug)} identificadores donde `slugify(clave) != clave` "
        f"({100*len(inconsistencias_slug)/max(len(agg),1):.1f}% del total).",
        "",
    ]
    if inconsistencias_slug:
        md.append("Ejemplos (primeros 20):")
        md.append("")
        md.append("| tipo_esquema | estado | grupo | clave actual | slugify_sugerido |")
        md.append("|---|---|---|---|---|")
        for tipo, est, grupo, clave, sug in inconsistencias_slug[:20]:
            md.append(f"| `{tipo}` | {est} | `{grupo}` | `{clave}` | `{sug}` |")
        if len(inconsistencias_slug) > 20:
            md.append(f"| … | | | … y {len(inconsistencias_slug) - 20} más | |")
    md.append("")

    md.append("## 2. Fragmentación intra-(tipo, estado, grupo)")
    md.append("")
    md.append("Top 20 combinaciones con mayor número de identificadores distintos — "
              "fragmentación alta indica el mismo concepto se nombra de muchas "
              "formas dentro de un mismo (esquema, estado, grupo):")
    md.append("")
    md.append("| tipo_esquema | estado | grupo | n_claves | ejemplos |")
    md.append("|---|---|---|---:|---|")
    for tipo, est, grupo, n, claves in fragmentacion[:20]:
        ejemplos = ", ".join(sorted(claves)[:3])
        if len(claves) > 3:
            ejemplos += f", … (+{len(claves) - 3})"
        md.append(f"| `{tipo}` | {ESTADO_SLUG_PRETTY.get(est, est)} | `{grupo}` | {n} | {ejemplos} |")
    md.append("")

    md.append("## 3. Solapamiento inter-estado por concepto")
    md.append("")
    md.append("Para conceptos típicos del predial, ¿qué claves los representan en cada estado? "
              "Las divergencias indican oportunidades de consolidación nomenclatural.")
    md.append("")
    for concepto in CONCEPTOS:
        estados = concepto_por_estado.get(concepto, {})
        if not estados:
            continue
        n_total = sum(len(c) for c in estados.values())
        md.append(f"### `{concepto}` — {n_total} claves en {len(estados)} estados")
        md.append("")
        for est in sorted(estados):
            claves = sorted(estados[est])
            md.append(f"- **{ESTADO_SLUG_PRETTY.get(est, est)}**: "
                      + ", ".join(f"`{c}`" for c in claves[:5])
                      + (f" … (+{len(claves) - 5})" if len(claves) > 5 else ""))
        md.append("")

    md.append("## 4. Frecuencia global (top 20)")
    md.append("")
    md.append("| tipo_esquema | estado | grupo | clave | n_apariciones | n_municipios |")
    md.append("|---|---|---|---|---:|---:|")
    top = sorted(agg.items(), key=lambda x: -x[1]["n"])[:20]
    for (tipo, est, grupo, clave), rec in top:
        md.append(f"| `{tipo}` | {ESTADO_SLUG_PRETTY.get(est, est)} | `{grupo}` | "
                  f"`{clave[:60]}` | {rec['n']} | {len(rec['munis'])} |")
    md.append("")

    md.append("## Propuestas de consolidación")
    md.append("")
    md.append("Recomendaciones derivadas del análisis (ver "
              "`output/anexos/bitacora_acciones_pendientes.md` P-102):")
    md.append("")
    md.append("1. Aplicar `text_utils.slugify` automático en validator de "
              "`FilaTarifaMillar.clave` para normalizar mayúsculas/signos "
              "(elimina inconsistencias de la sección 1).")
    md.append("2. Definir un set canónico de claves por grupo (urbano_edificado, "
              "urbano_baldio, rustico, ejidal, etc.) y reformular el prompt "
              "del extractor para preferirlas. Reduce la fragmentación de "
              "la sección 2.")
    md.append("3. Para los conceptos de la sección 3, considerar un mapeo "
              "canónico que renombre los slugs durante consolidación del "
              "panel.")

    md_path.write_text("\n".join(md), encoding="utf-8")
    print(f"  Markdown: {md_path}")

    # ── Mapa exhaustivo ──
    if not args.no_mapa:
        mapa_path = Path(args.out_mapa)
        _escribir_mapa_exhaustivo(agg, mapa_path)
        print(f"  Mapa exhaustivo: {mapa_path}")

    # Resumen consola.
    print("\nResumen:")
    print(f"  claves únicas (estado,grupo,clave): {len(agg)}")
    print(f"  inconsistencias slugify:            {len(inconsistencias_slug)} "
          f"({100*len(inconsistencias_slug)/max(len(agg),1):.1f}%)")
    print(f"  top fragmentación: {fragmentacion[0][:3] if fragmentacion else 'N/A'}")


def _escribir_mapa_exhaustivo(agg: dict, path: Path) -> None:
    """Emite un markdown exhaustivo organizado por (tipo_esquema, estado, grupo)
    con TODAS las claves listadas — para trabajo manual de consolidación.

    Estructura:
      # Mapa exhaustivo
      ## Índice          (TOC por tipo > estado > grupo con conteos)
      ## tarifa_millar
      ### Coahuila — 12 claves
      #### grupo: urbano (3 claves)
      - `predios_urbanos` — n_apariciones=200 munis=40 años=5 tasas=5.0|3.0
        - desc: "Sobre los predios urbanos"
      ...
    """
    # Re-indexar por (tipo, est, grupo) -> list[(clave, rec)].
    by_teg: dict[tuple[str, str, str], list[tuple[str, dict]]] = defaultdict(list)
    for (tipo, est, grupo, clave), rec in agg.items():
        by_teg[(tipo, est, grupo)].append((clave, rec))

    # Sort claves por n desc.
    for k in by_teg:
        by_teg[k].sort(key=lambda x: -x[1]["n"])

    # Tipos y estados ordenados estables.
    tipos_orden = sorted({t for t, _, _ in by_teg})
    estados_orden = sorted({e for _, e, _ in by_teg})

    out: list[str] = []
    out.append("# Mapa exhaustivo de identificadores tarifarios")
    out.append("")
    out.append("Listado completo organizado por **tipo_esquema → estado → grupo**, "
               "con todas las claves observadas y su frecuencia. Usar para planear "
               "consolidación nomenclatural; pares semánticamente equivalentes "
               "deberían unificarse al mismo slug canónico.")
    out.append("")
    out.append(f"Generado a partir de {sum(rec['n'] for rec in agg.values())} filas "
               f"y {len(agg)} identificadores únicos.")
    out.append("")

    # Índice (TOC).
    out.append("## Índice")
    out.append("")
    for tipo in tipos_orden:
        out.append(f"- **{tipo}**")
        for est in estados_orden:
            grupos_est = sorted({g for (t, e, g) in by_teg if t == tipo and e == est})
            if not grupos_est:
                continue
            n_est = sum(len(by_teg[(tipo, est, g)]) for g in grupos_est)
            anchor = f"{tipo}-{est}".replace("_", "-")
            out.append(f"  - [{ESTADO_SLUG_PRETTY.get(est, est)}](#{anchor}) "
                       f"— {n_est} claves en {len(grupos_est)} grupo(s)")
    out.append("")

    # Secciones.
    for tipo in tipos_orden:
        out.append(f"## {tipo}")
        out.append("")
        for est in estados_orden:
            grupos_est = sorted({g for (t, e, g) in by_teg if t == tipo and e == est})
            if not grupos_est:
                continue
            anchor = f"{tipo}-{est}".replace("_", "-")
            n_est = sum(len(by_teg[(tipo, est, g)]) for g in grupos_est)
            out.append(f"### {ESTADO_SLUG_PRETTY.get(est, est)} "
                       f"<a id='{anchor}'></a> — {n_est} claves")
            out.append("")
            for grupo in grupos_est:
                claves = by_teg[(tipo, est, grupo)]
                gname = grupo if grupo else "(sin grupo)"
                out.append(f"#### grupo: `{gname}` — {len(claves)} clave(s)")
                out.append("")
                for clave, rec in claves:
                    sug = slugify(clave)
                    flag = "" if sug == clave else f" ⚠ slugify_sug=`{sug}`"
                    vals = "|".join(str(v) for v in rec["valores"][:5])
                    out.append(
                        f"- `{clave}` — "
                        f"apar={rec['n']}, munis={len(rec['munis'])}, "
                        f"años={len(rec['anios'])}"
                        + (f", vals={vals}" if vals else "")
                        + flag
                    )
                    desc = (rec["descripciones"][0] if rec["descripciones"] else "")[:140]
                    if desc:
                        out.append(f"  - desc: {desc}")
                out.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
