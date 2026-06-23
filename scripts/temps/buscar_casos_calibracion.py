"""Busca casos candidatos para la gold-calibración (40 casos, 3 bloques).

Mina el corpus v3 + la cola HITL y propone, por cada slot del diseño
(`gold_calibracion_diseno.md`), una lista corta de candidatos concretos con sus
atributos clave, para que el usuario cure la muestra final.

  Bloque 1 (canónicos): query por tipo_esquema × n_tarifas × fuente, ranqueado
                        por limpieza (intentos=1, sin revisión, tabla corta).
  Bloque 2 (errores):   join con la cola HITL por detector + heurísticas.
  Bloque 3 (ambiguos):  heurísticas (suburbano, remisión, notas, base ambigua...).

Uso:
    python -m scripts.temps.buscar_casos_calibracion
    python -m scripts.temps.buscar_casos_calibracion --out reportes/casos_calibracion.md
    python -m scripts.temps.buscar_casos_calibracion --n 5      # candidatos por slot
"""

from __future__ import annotations

import argparse
import csv
import glob
import json
from collections import defaultdict
from pathlib import Path

# Universo de la calibración (diseño) — 8 estados.  Otros (p.ej. aguascalientes)
# se incluyen pero se marcan como fuera del universo.
UNIVERSO = {"coahuila", "guanajuato", "jalisco", "queretaro",
            "sanluispotosi", "sonora", "tamaulipas", "yucatan"}
COLA = Path("output/hitl/cola_unificada.csv")


# ── Carga e indexado ──────────────────────────────────────────────

def _fuente(m3: dict) -> str:
    if m3.get("usado_vision"):
        return "vision"
    if m3.get("usado_reocr"):
        return "ocr"
    return "txt"


def _tabla_len(esq: dict) -> int:
    if "tabla" in esq and isinstance(esq["tabla"], list):
        return len(esq["tabla"])
    if "bloques" in esq:
        return max((len(b.get("tabla") or []) for b in esq["bloques"]), default=0)
    return 0


def _prog_all_zero(esq: dict) -> bool:
    if esq.get("tipo_esquema") != "progresivo":
        return False
    tasas = [r.get("tasa_marginal") for b in esq.get("bloques", [])
             for r in (b.get("tabla") or [])]
    tasas = [t for t in tasas if t is not None]
    return bool(tasas) and all(t == 0 for t in tasas)


def _gist_from_predial(p: dict) -> str:
    """Resumen humano de una sola línea del contenido real (tasas/estructura)."""
    tarifas = p.get("tarifas") or []
    parts = []
    for t in tarifas[:3]:
        amb = t.get("ambito") or "?"
        e = t.get("esquema") or {}
        tipo = e.get("tipo_esquema")
        g = f"{amb}:{tipo}"
        tab = e.get("tabla") or []
        if tipo == "tasa_unica" and tab:
            g += f" {tab[0].get('tasa')} {tab[0].get('unidad', '')}"
        elif tipo == "tarifa_millar" and tab:
            g += f" {[r.get('tasa_millar') for r in tab[:4]]}"
        elif tipo == "cuota_fija_simple" and tab:
            g += f" {tab[0].get('monto')} {tab[0].get('unidad', '')}"
        elif tipo == "cuota_fija_escalonada" and tab:
            ms = [r.get("monto") for r in tab if r.get("monto") is not None]
            g += f" {len(tab)}r montos {min(ms)}-{max(ms)}" if ms else f" {len(tab)}r"
        elif tipo == "progresivo":
            bl = e.get("bloques") or []
            ts = [r.get("tasa_marginal") for b in bl for r in (b.get("tabla") or [])
                  if r.get("tasa_marginal") is not None]
            g += f" {len(bl)}bloq " + (f"tasa {min(ts)}-{max(ts)}" if ts else "")
        elif tipo == "mixto":
            g += f" {len(e.get('tabla') or e.get('bloques') or [])}filas"
        elif tipo == "otro_no_clasificado":
            g += f" ({e.get('categoria', '')})"
        parts.append(g)
    if len(tarifas) > 3:
        parts.append(f"+{len(tarifas) - 3} más")
    mg = p.get("minimo_predial_general")
    if mg:
        parts.append(f"mín {mg.get('monto')} {mg.get('unidad', '')}")
    return " | ".join(parts)


def cargar_corpus() -> list[dict]:
    recs = []
    for f in glob.glob("data/*/json_predial/**/*.json", recursive=True):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        p = d.get("predial")
        if not p or (d.get("_meta_cobertura") or {}).get("placeholder"):
            continue
        m3 = d.get("_meta_v3") or {}
        tarifas = p.get("tarifas") or []
        esquemas = [t.get("esquema") or {} for t in tarifas]
        minimos = []
        if p.get("minimo_predial_general"):
            minimos.append(("general", (p["minimo_predial_general"] or {}).get("unidad", "?")))
        for t in tarifas:
            if t.get("minimo_predial"):
                minimos.append(("tarifa", (t["minimo_predial"] or {}).get("unidad", "?")))
        recs.append({
            "path": f.replace("\\", "/"),
            "estado": m3.get("estado", Path(f).parts[1]),
            "cvegeo": m3.get("cvegeo", ""),
            "anio": int(m3.get("anio") or 0),
            "slug": Path(f).stem.split("_PREDIAL_")[-1].split("_", 1)[-1]
                    if "_PREDIAL_" in Path(f).stem else Path(f).stem,
            "tipos": [e.get("tipo_esquema") for e in esquemas],
            "n_tarifas": len(tarifas),
            "ambitos": [t.get("ambito") for t in tarifas],
            "ambito_det": " ".join(str(t.get("ambito_detalle") or "") for t in tarifas).lower(),
            "bases": [t.get("base_gravable") for t in tarifas],
            "fuente": _fuente(m3),
            "intentos": int(m3.get("intentos") or 1),
            "revision": bool(m3.get("requiere_revision")),
            "escalado": bool(m3.get("escalado")),
            "minimos": minimos,
            "max_filas": max((_tabla_len(e) for e in esquemas), default=0),
            "n_bloques": max((len(e.get("bloques", [])) for e in esquemas
                              if e.get("tipo_esquema") == "progresivo"), default=0),
            "prog_zero": any(_prog_all_zero(e) for e in esquemas),
            "coment": (p.get("comentarios") or "").lower(),
            "gist": _gist_from_predial(p),
        })
    return recs


def cargar_cola() -> dict[tuple[str, int], dict]:
    """(cvegeo, anio) -> {detectores:set, severidades:set, senales:[..]}."""
    idx: dict[tuple, dict] = defaultdict(
        lambda: {"detectores": set(), "severidades": set(), "senales": []})
    if not COLA.exists():
        return idx
    with COLA.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            key = (r.get("cvegeo", ""), int(r.get("anio") or 0))
            dets = [d.strip() for d in (r.get("detector") or "").split(",") if d.strip()]
            idx[key]["detectores"].update(dets)
            idx[key]["severidades"].add(r.get("severidad", ""))
            if r.get("senal"):
                idx[key]["senales"].append(r["senal"])
    return idx


# ── Ranking de limpieza (Bloque 1) ────────────────────────────────

def _clean_key(r: dict) -> tuple:
    """Menor = más limpio."""
    return (r["revision"], r["intentos"] != 1, r["escalado"], r["max_filas"], len(r["coment"]))


def _variar_estados(cands: list[dict], n: int) -> list[dict]:
    """Toma hasta n candidatos prefiriendo variedad de estados."""
    cands = sorted(cands, key=_clean_key)
    out, vistos = [], set()
    for r in cands:
        if r["estado"] not in vistos:
            out.append(r)
            vistos.add(r["estado"])
        if len(out) >= n:
            return out
    for r in cands:  # rellenar si faltan
        if r not in out:
            out.append(r)
        if len(out) >= n:
            break
    return out


# ── Render ─────────────────────────────────────────────────────────

SHOW_GIST = False


def _line(r: dict, cola: dict | None = None) -> str:
    uni = "" if r["estado"] in UNIVERSO else " ⚠fuera-universo"
    bases = sorted({str(b) for b in r["bases"] if b})
    mins = sorted({u for _, u in r["minimos"]})
    extra = ""
    if bases:
        extra += f" base={bases}"
    if mins:
        extra += f" min={mins}"
    base = (f"  - **{r['estado']} {r['anio']} {r['slug']}** (cve {r['cvegeo']}) — "
            f"tipos={r['tipos']} n_tar={r['n_tarifas']} fuente={r['fuente']} "
            f"int={r['intentos']}{' REV' if r['revision'] else ''} "
            f"filas={r['max_filas']}{extra}{uni}")
    if SHOW_GIST and r.get("gist"):
        base += f"\n    → {r['gist']}"
    base += f"\n    `{r['path']}`"
    if cola is not None:
        info = cola.get((r["cvegeo"], r["anio"]))
        if info:
            base += f"\n    cola: {sorted(info['detectores'])}"
    return base


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="reportes/casos_calibracion.md")
    ap.add_argument("--n", type=int, default=0, help="candidatos por slot (0=auto)")
    ap.add_argument("--shortlist", action="store_true",
                    help="solo bloques A y B, con resumen de contenido (gist)")
    args = ap.parse_args()

    global SHOW_GIST
    SHOW_GIST = args.shortlist
    n_default = 3 if args.shortlist else 4
    if args.shortlist and args.out == "reportes/casos_calibracion.md":
        args.out = "reportes/casos_calibracion_shortlist.md"

    recs = cargar_corpus()
    cola = cargar_cola()
    n = args.n or n_default
    L: list[str] = [f"# Candidatos gold-calibración ({len(recs)} JSON v3 en corpus)\n"]

    def seccion(titulo: str):
        L.append(f"\n## {titulo}\n")

    def slot(num, nombre, cands, with_cola=False):
        L.append(f"\n### {num}. {nombre}  ({len(cands)} candidatos)\n")
        if not cands:
            L.append("  _(sin candidatos automáticos — fabricar o buscar a mano)_\n")
            return
        for r in _variar_estados(cands, n):
            L.append(_line(r, cola if with_cola else None) + "\n")

    def has(r, tipo):
        return tipo in r["tipos"]

    def solo(r, tipo):
        return r["tipos"] and all(t == tipo for t in r["tipos"])

    # ── BLOQUE 1 ──
    seccion("BLOQUE 1 — Canónicos (extracción correcta de cada tipo)")
    slot(1, "tasa_unica simple (1 tarifa, valor catastral)",
         [r for r in recs if r["n_tarifas"] == 1 and solo(r, "tasa_unica")
          and any("catastral" in str(b) for b in r["bases"])])
    slot(2, "tasa_unica por hectárea (rústico/superficie)",
         [r for r in recs if has(r, "tasa_unica")
          and any("superficie" in str(b) or "hectar" in str(b) for b in r["bases"])])
    slot(3, "tarifa_millar con 3-5 categorías",
         [r for r in recs if solo(r, "tarifa_millar") and 3 <= r["max_filas"] <= 5])
    slot(4, "cuota_fija_simple", [r for r in recs if solo(r, "cuota_fija_simple")])
    slot(5, "cuota_fija_escalonada", [r for r in recs if solo(r, "cuota_fija_escalonada")])
    slot(6, "progresivo (1 bloque)",
         [r for r in recs if solo(r, "progresivo") and r["n_bloques"] == 1])
    slot(7, "progresivo por bloques (≥2 categorías)",
         [r for r in recs if has(r, "progresivo") and r["n_bloques"] >= 2])
    slot(8, "mixto (Piedras Negras 2022 si aparece)",
         [r for r in recs if has(r, "mixto")])
    slot(9, "otro_no_clasificado (legítimo)",
         [r for r in recs if has(r, "otro_no_clasificado")], with_cola=True)
    slot(10, "1 tarifa general", [r for r in recs if r["n_tarifas"] == 1
                                   and r["ambitos"] == ["general"]])
    slot(11, "2 tarifas paralelas (urbano+rústico)",
         [r for r in recs if r["n_tarifas"] == 2
          and any("urban" in str(a) for a in r["ambitos"])
          and any("rust" in str(a) or "rúst" in str(a) for a in r["ambitos"])])
    slot(12, "3+ tarifas paralelas (preferir Sonora)",
         [r for r in recs if r["n_tarifas"] >= 3])
    slot(13, "con mínimo predial (varía unidad)",
         [r for r in recs if r["minimos"]])
    slot(14, "fuente OCR (limpia)", [r for r in recs if r["fuente"] == "ocr"])
    slot(15, "fuente visión (limpia)", [r for r in recs if r["fuente"] == "vision"])

    # ── BLOQUE 2 (errores: join cola) ──
    seccion("BLOQUE 2 — Errores (decisión HITL esperada)")

    def con_det(det):
        return [r for r in recs
                if det in cola.get((r["cvegeo"], r["anio"]), {}).get("detectores", set())]

    slot(16, "Segmentación truncada → re_segmentar [proxy: bracket_superior_cerrado]",
         con_det("bracket_superior_cerrado"), with_cola=True)
    slot(17, "Sobre-incluida (otra tabla) → re_segmentar [proxy: distancia_inicio_anomala]",
         con_det("distancia_inicio_anomala"), with_cola=True)
    slot(18, "Otro municipio → re_segmentar [proxy: identidad/distancia]",
         con_det("identidad_no_resuelta") or con_det("distancia_inicio_anomala"),
         with_cola=True)
    slot(19, "progresivo con tasa_marginal=0 → reextraer(hint escalonada)",
         [r for r in recs if r["prog_zero"]]
         or con_det("progresivo_tasa_cero"), with_cola=True)
    slot(20, "escalonada→mixto monocolumna → reextraer",
         con_det("mixto_monocolumna_cuotafija"), with_cola=True)
    slot(21, "tarifa paralela perdida (rústico en comentarios) → reextraer",
         [r for r in recs if r["n_tarifas"] == 1
          and ("rústic" in r["coment"] or "rustic" in r["coment"] or "rural" in r["coment"])])
    slot(22, "tarifa paralela inventada (ámbitos duplicados) → reextraer",
         [r for r in recs if r["n_tarifas"] >= 2
          and len(set(map(str, r["ambitos"]))) < r["n_tarifas"]])
    slot(23, "unidad equivocada (factor) → cambio_menor/reextraer",
         con_det("tarifa_millar_factor") or con_det("tasa_unica_unidad_factor"),
         with_cola=True)
    slot(24, "mínimo equivocado → cambio_menor [revisar a mano cuota_fija_simple+min]",
         [r for r in recs if solo(r, "cuota_fija_simple") and r["minimos"]])
    slot(25, "valor numérico equivocado → cambio_menor  (FABRICAR: corromper 1 dígito)", [])
    slot(26, "año anterior idéntico → confirmar_fiel  (ver pares sin cambio abajo)", [])
    slot(27, "año anterior cambio menor → cambio_menor [cambio_interanual SEV3]",
         con_det("cambio_interanual"), with_cola=True)
    slot(28, "P-00 legítimo (remite a ley externa) → confirmar_fiel",
         con_det("remite_a_ley_externa"), with_cola=True)
    slot(29, "OCR ruidoso parcial → reextraer(force_vision)",
         [r for r in recs if r["fuente"] == "ocr" and r["revision"]], with_cola=True)
    slot(30, "otro_no_clasificado clasificable → reextraer(hint)",
         con_det("otro_no_clasificado"), with_cola=True)

    # pares año-idéntico (slot 26)
    L.append("\n#### Apoyo slot 26 — pares de años consecutivos con extracción idéntica\n")
    by_cve: dict[str, dict[int, dict]] = defaultdict(dict)
    for r in recs:
        by_cve[r["cvegeo"]][r["anio"]] = r
    pares = []
    for cve, ys in by_cve.items():
        for a in sorted(ys):
            if a - 1 in ys:
                p0 = json.load(open(ys[a - 1]["path"], encoding="utf-8")).get("predial")
                p1 = json.load(open(ys[a]["path"], encoding="utf-8")).get("predial")
                if json.dumps(p0, sort_keys=True) == json.dumps(p1, sort_keys=True):
                    pares.append((ys[a]["estado"], cve, a - 1, a, ys[a]["slug"]))
    for est, cve, a0, a1, slug in sorted(pares)[:n]:
        L.append(f"  - **{est} {slug}** (cve {cve}): {a0}=={a1} idénticos\n")
    if not pares:
        L.append("  _(ninguno idéntico exacto)_\n")

    # ── BLOQUE 3 (ambiguos: heurísticas) ── (se omite en --shortlist)
    if not args.shortlist:
        seccion("BLOQUE 3 — Ambiguos (heurísticas; el usuario cura/aporta)")
        slot(31, "¿2 tarifas o subcategorías? (n_tarifas≥2 con ámbito_detalle rico)",
             [r for r in recs if r["n_tarifas"] >= 2 and len(r["ambito_det"]) > 20])
        slot(32, "ámbito 'suburbano'",
             [r for r in recs if "suburban" in r["ambito_det"]
              or any("suburban" in str(a) for a in r["ambitos"])])
        slot(33, "remite a 'la tarifa del artículo X'",
             [r for r in recs if "artícul" in r["coment"] or "articul" in r["coment"]],
             with_cola=True)
        slot(34, "nota al pie que modifica una tasa",
             [r for r in recs if "nota" in r["coment"]])
        slot(35, "descuento por pronto pago en la tabla",
             [r for r in recs if "pronto pago" in r["coment"] or "descuento" in r["coment"]])
        slot(36, "mínimo ambiguo (raíz Y por tarifa)",
             [r for r in recs if any(s == "general" for s, _ in r["minimos"])
              and any(s == "tarifa" for s, _ in r["minimos"])])
        slot(37, "cambio de nombre de esquema entre años → ¿SEV1?",
             con_det("cambio_interanual"), with_cola=True)
        slot(38, "base ambigua (no valor_catastral)",
             [r for r in recs if any(b and "catastral" not in str(b) for b in r["bases"])])
        slot(39, "al millar vs al ciento (OCR + factor)",
             [r for r in recs if r["fuente"] == "ocr"
              and "tarifa_millar_factor" in cola.get((r["cvegeo"], r["anio"]), {}).get("detectores", set())],
             with_cola=True)
        slot(40, "tabla como imagen (fuente visión)",
             [r for r in recs if r["fuente"] == "vision"])

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(L), encoding="utf-8")
    print(f"Reporte escrito: {out}  ({len(recs)} JSON analizados, {len(cola)} casos en cola)")
    print("Revisa el markdown; cada slot trae candidatos con ruta al JSON.")


if __name__ == "__main__":
    main()
