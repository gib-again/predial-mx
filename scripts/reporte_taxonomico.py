"""Reporte taxonómico de extracciones v2.

Corre validación schema_v2 sobre predial-mx-v2/ y genera reporte markdown:
  (1) Conteo por tipo_corregido global y por estado
  (2) Casos otro_no_clasificado agrupados por similitud, ordenados por frecuencia
  (3) Por grupo: muni-años, estados, rango años
  (4) Casos requiere_revision

Output: output/reporte_taxonomico.md
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.extraction.schema_v2 import OtroNoClasificadoSchema, PredialOutputV2  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
V2_ROOT = ROOT / "predial-mx-v2"
OUT_PATH = ROOT / "output" / "reporte_taxonomico.md"
ESTADOS = ["coahuila", "guanajuato", "tamaulipas", "yucatan"]

# Tags semánticos para sub-agrupar `descripcion_estructural`. Se aplican en
# orden — el primer match gana. Una descripción puede combinar varios temas;
# nos quedamos con el más específico (early match wins).
SEMANTIC_TAGS: list[tuple[str, str]] = [
    ("dos_tarifas_paralelas", r"\b(dos|tres) (mec[aá]nicas|tarifas?|tablas?) (paralel|distint|alternat)"),
    ("dos_tarifas_paralelas", r"\b(paralel[ao]s?|alternativ[ao]s?)\b.*\b(tarif|tabla|mec[aá]nic)"),
    ("solo_valores_unitarios", r"valores?\s+unitari[oa]s"),
    ("solo_valores_catastro", r"\b(tabla|tablas)\s+(de\s+)?(valores?\s+)?catastr"),
    ("solo_encabezado", r"\b(s[oó]lo|únicamente|solo)\b.*\bencabezad"),
    ("solo_encabezado", r"\bencabezad[oa]s?\b.*\b(s[oó]lo|únicamente|solo|sin)\b"),
    ("texto_truncado", r"\b(truncad|corrige a media|incomplet[oa]|recorte|recortad)"),
    ("texto_truncado", r"a\s+media\s+frase"),
    ("ocr_ilegible", r"\b(ilegible|ocr|corrupt|garbled|caracteres? extra[ñn])"),
    ("factor_sin_tabla", r"\bfactor\b.*\b(multiplicaci[oó]n|catastr|c[aá]lculo)"),
    ("muni_sin_predial", r"no\s+(causa|cobra|aplica)\s+(el\s+)?impuesto"),
    ("muni_sin_predial", r"municipio\s+sin\s+impuesto"),
    ("ejidal_comunal", r"\b(ejid|comun[ae]l|agropecuari)"),
    ("articulado_ausente", r"no\s+contiene\s+(el\s+)?(articulado|art[ií]culo)"),
    ("seccion_ausente", r"no\s+contiene\s+(la\s+)?secci[oó]n"),
    ("seccion_ausente", r"no\s+(aparece|incluye|presenta)\s+(la\s+)?secci[oó]n"),
    ("apartado_ausente", r"no\s+contiene\s+(el\s+)?apartado"),
    ("contenido_ausente", r"no\s+(incluye|contiene)\s+el\s+contenido"),
    ("mecanica_ausente", r"no\s+(incluye|contiene)\s+(la\s+)?mec[aá]nica"),
    ("texto_vacio", r"texto\s+(proporcionado|fuente)\s+(est[aá]\s+)?vac[ií]"),
]
SEMANTIC_TAGS_COMPILED = [(tag, re.compile(pat, re.IGNORECASE)) for tag, pat in SEMANTIC_TAGS]


def _parse_filename(name: str) -> tuple[int, str]:
    stem = name[:-5] if name.endswith(".json") else name
    parts = stem.split("_")
    try:
        anio = int(parts[2])
    except (IndexError, ValueError):
        anio = 0
    slug = "_".join(parts[3:]) if len(parts) > 3 else ""
    return anio, slug


def _semantic_tag(text: str | None) -> str:
    if not text:
        return "sin_descripcion"
    for tag, pat in SEMANTIC_TAGS_COMPILED:
        if pat.search(text):
            return tag
    return "otro_patron"


def main() -> int:
    rows: list[dict] = []
    invalid: list[dict] = []

    for estado in ESTADOS:
        d = V2_ROOT / estado
        if not d.exists():
            continue
        for jp in sorted(d.glob("*.json")):
            try:
                data = json.loads(jp.read_text(encoding="utf-8"))
            except Exception as e:
                invalid.append({"path": str(jp), "error": f"json_load: {e}"})
                continue

            anio, slug = _parse_filename(jp.name)
            meta_v2 = data.get("_meta_v2") or {}
            cvegeo = meta_v2.get("cvegeo", "")
            requiere_revision = bool(meta_v2.get("requiere_revision", False))
            razon = meta_v2.get("razon", "") or ""
            escalado = bool(meta_v2.get("escalado", False))
            modelo = (data.get("_meta") or {}).get("modelo", "")

            predial = data.get("predial")
            if not isinstance(predial, dict):
                rows.append({
                    "estado": estado, "anio": anio, "slug": slug, "cvegeo": cvegeo,
                    "tipo_corregido": "FALTA_PREDIAL",
                    "es_otro": False, "categoria": None, "descripcion": None,
                    "comentarios": "", "requiere_revision": requiere_revision,
                    "razon": razon, "escalado": escalado, "modelo": modelo,
                    "valido": False, "json_path": str(jp.relative_to(ROOT)),
                })
                continue

            try:
                output = PredialOutputV2.model_validate({
                    "predial": predial,
                    "_meta": data.get("_meta"),
                })
                p = output.predial
                tipo = p.tipo_esquema
                es_otro = isinstance(p, OtroNoClasificadoSchema)
                categoria = getattr(p, "categoria", None) if es_otro else None
                descripcion = getattr(p, "descripcion_estructural", None) if es_otro else None
                comentarios = getattr(p, "comentarios", "") or ""
                rows.append({
                    "estado": estado, "anio": anio, "slug": slug, "cvegeo": cvegeo,
                    "tipo_corregido": tipo, "es_otro": es_otro,
                    "categoria": categoria, "descripcion": descripcion,
                    "comentarios": comentarios,
                    "requiere_revision": requiere_revision,
                    "razon": razon, "escalado": escalado, "modelo": modelo,
                    "valido": True, "json_path": str(jp.relative_to(ROOT)),
                })
            except Exception as e:
                invalid.append({"path": str(jp), "error": f"validation: {e!s}"[:300]})
                rows.append({
                    "estado": estado, "anio": anio, "slug": slug, "cvegeo": cvegeo,
                    "tipo_corregido": "INVALIDO",
                    "es_otro": False, "categoria": None, "descripcion": None,
                    "comentarios": "",
                    "requiere_revision": True,
                    "razon": f"validation_error: {e}"[:200],
                    "escalado": escalado, "modelo": modelo,
                    "valido": False, "json_path": str(jp.relative_to(ROOT)),
                })

    # (1) Conteos
    tipo_global = Counter(r["tipo_corregido"] for r in rows)
    tipo_by_estado: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        tipo_by_estado[r["estado"]][r["tipo_corregido"]] += 1

    # (2)+(3) Grupos otro_no_clasificado
    otros = [r for r in rows if r["es_otro"]]
    for r in otros:
        r["_tag"] = _semantic_tag(r["descripcion"])
    grupos: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in otros:
        cat = r["categoria"] or "sin_categoria"
        grupos[(cat, r["_tag"])].append(r)
    grupos_ordenados = sorted(grupos.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    # (4) requiere_revision excluyendo otro
    revision_no_otro = [r for r in rows if r["requiere_revision"] and not r["es_otro"]]

    # ── Escribir markdown ──
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as f:
        f.write("# Reporte taxonómico — extracciones predial v2\n\n")
        f.write(
            f"Fuente: `predial-mx-v2/`  ·  Estados: {', '.join(ESTADOS)}  ·  "
            f"Total JSONs: **{len(rows)}**\n\n"
        )
        if invalid:
            f.write(f"⚠️ **{len(invalid)} archivo(s) fallaron lectura/validación.**\n\n")
            for inv in invalid[:10]:
                f.write(f"- `{Path(inv['path']).name}`: {inv['error']}\n")
            if len(invalid) > 10:
                f.write(f"- … ({len(invalid) - 10} más)\n")
            f.write("\n")

        # (1) Distribución
        f.write("## 1. Distribución por `tipo_corregido`\n\n")
        f.write("### Global\n\n")
        f.write("| Tipo | Casos | % |\n|---|---:|---:|\n")
        total = sum(tipo_global.values())
        for tipo, n in tipo_global.most_common():
            pct = 100 * n / total if total else 0
            f.write(f"| `{tipo}` | {n} | {pct:.1f}% |\n")
        f.write(f"| **Total** | **{total}** | 100.0% |\n\n")

        f.write("### Por estado\n\n")
        all_tipos = [t for t, _ in tipo_global.most_common()]
        f.write("| Estado | " + " | ".join(f"`{t}`" for t in all_tipos) + " | Total |\n")
        f.write("|---|" + "---:|" * (len(all_tipos) + 1) + "\n")
        for est in ESTADOS:
            counts = tipo_by_estado[est]
            total_est = sum(counts.values())
            cells = " | ".join(str(counts.get(t, 0)) for t in all_tipos)
            f.write(f"| {est} | {cells} | **{total_est}** |\n")
        f.write("\n")

        # (2)+(3) otro_no_clasificado agrupado
        f.write("## 2. Casos `otro_no_clasificado` agrupados por similitud\n\n")
        f.write(
            f"Total casos: **{len(otros)}**  ·  "
            f"Grupos distintos: **{len(grupos_ordenados)}**  ·  "
            f"Criterio: `(categoria, tag_semántico)` — "
            f"el tag se asigna por keywords-regex sobre `descripcion_estructural`. "
            f"Una descripción que matchea el primer patrón gana ese tag (early-match-wins).\n\n"
        )

        for i, ((cat, tag), members) in enumerate(grupos_ordenados, 1):
            estados_grupo = sorted(Counter(m["estado"] for m in members).items())
            anios = sorted(set(m["anio"] for m in members if m["anio"]))
            if not anios:
                anio_range = "—"
            elif len(anios) == 1:
                anio_range = str(anios[0])
            else:
                anio_range = f"{anios[0]}–{anios[-1]} ({len(anios)} años distintos)"

            # Ejemplar = descripción más larga
            sample = max(members, key=lambda m: len(m["descripcion"] or ""))
            desc = sample["descripcion"] or "(sin descripción)"

            est_str = ", ".join(f"{e}({n})" for e, n in estados_grupo)

            f.write(f"### Grupo #{i} — {len(members)} caso(s)  ·  `{tag}`\n\n")
            f.write(f"- **categoria**: `{cat}`\n")
            f.write(f"- **tag**: `{tag}`\n")
            f.write(f"- **estados**: {est_str}\n")
            f.write(f"- **rango años**: {anio_range}\n")
            f.write(f"- **muni-años afectados**: {len(members)}\n\n")
            f.write("**descripcion_estructural (ejemplar)**:\n\n")
            f.write("> " + desc.replace("\n", "\n> ") + "\n\n")

            f.write(f"<details><summary>Lista completa ({len(members)} casos)</summary>\n\n")
            for m in sorted(members, key=lambda x: (x["estado"], x["slug"], x["anio"])):
                f.write(
                    f"- `{m['estado']}` · {m['slug']} ({m['anio']}) — cvegeo {m['cvegeo']}"
                )
                if m["escalado"]:
                    f.write(" — escalado")
                f.write("\n")
            f.write("\n</details>\n\n")

        # (4) requiere_revision (no-otro)
        f.write("## 3. Casos `requiere_revision` excluyendo `otro_no_clasificado`\n\n")
        f.write(f"Total: **{len(revision_no_otro)}**\n\n")
        if revision_no_otro:
            f.write("| Estado | Año | Slug | tipo_corregido | Escalado | Razón |\n")
            f.write("|---|---:|---|---|:-:|---|\n")
            for r in sorted(revision_no_otro, key=lambda x: (x["estado"], x["slug"], x["anio"])):
                razon = (r["razon"] or "").replace("|", "\\|").replace("\n", " ")[:140]
                esc = "✓" if r["escalado"] else ""
                f.write(
                    f"| {r['estado']} | {r['anio']} | {r['slug']} | "
                    f"`{r['tipo_corregido']}` | {esc} | {razon} |\n"
                )
        f.write("\n")

        # Métricas finales
        f.write("## 4. Métricas resumen\n\n")
        n_valid = sum(1 for r in rows if r["valido"])
        n_otro = len(otros)
        n_rev_total = sum(1 for r in rows if r["requiere_revision"])
        n_esc = sum(1 for r in rows if r["escalado"])
        f.write(f"- Total JSONs: **{len(rows)}**\n")
        f.write(f"- Schema-validados (load + Pydantic v2): **{n_valid}** ({100*n_valid/len(rows):.1f}%)\n")
        f.write(f"- `otro_no_clasificado`: **{n_otro}** ({100*n_otro/len(rows):.1f}%) en {len(grupos_ordenados)} grupos\n")
        f.write(f"- `requiere_revision` total: **{n_rev_total}** ({100*n_rev_total/len(rows):.1f}%)\n")
        f.write(f"- Escalados a fallback (`gpt-5.4`): **{n_esc}** ({100*n_esc/len(rows):.1f}%)\n")

    print(f"OK reporte: {OUT_PATH.relative_to(ROOT)}")
    print(f"  total JSONs:           {len(rows)}")
    print(f"  schema-validados:      {sum(1 for r in rows if r['valido'])}")
    print(f"  otro_no_clasificado:   {len(otros)} ({len(grupos_ordenados)} grupos)")
    print(f"  requiere_revision (no-otro): {len(revision_no_otro)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
