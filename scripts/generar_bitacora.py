"""Genera plantilla inicial de bitácora HITL desde extracciones v2.

Output: docs/HITL_BITACORA.md (no sobrescribe si existe — usa --force).

Pre-carga:
  - Una entrada-stub por cada `otro_no_clasificado`, agrupado por (categoria, tag)
  - Una entrada-stub por cada `requiere_revision` excluyendo otro
  - Sección "Patrones detectados" para hallazgos transversales

Cada stub tiene un bloque `Revisión` con campos parseables que después se
extraen automáticamente para alimentar mejoras del prompt/schema.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scripts.reporte_taxonomico import _parse_filename, _semantic_tag  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
V2_ROOT = ROOT / "predial-mx-v2"
OUT_PATH = ROOT / "docs" / "HITL_BITACORA.md"
ESTADOS = ["coahuila", "guanajuato", "tamaulipas", "yucatan"]


HEADER = """\
# Bitácora de revisión HITL — extracciones predial v2

> Working document. Tus anotaciones aquí alimentan mejoras del prompt/schema.
> Regenera con `python -m scripts.generar_bitacora` (no sobreescribe). Pasa
> `--force` para regenerar desde cero (BORRA anotaciones).

## Alcance y documentos relacionados

- **Esta bitácora** cubre extracciones LLM con `tipo_esquema=otro_no_clasificado`
  o `requiere_revision=True` en los 4 estados re-extraídos: Coahuila, Guanajuato,
  Tamaulipas, Yucatán. Foco: calidad de extracción / clasificación.
- **`output/audit_pendiente.md` + `output/audit_pendiente.csv`** cubren huecos
  del panel balanceado (motivos `sin_predial_residual`, `schema_discontinuity`,
  `edge`) — foco: cobertura temporal y reformas. Si un caso aparece en ambos,
  resuelve el del panel primero (decisión de imputación) y referencia su veredicto.
- **Sintéticos `short_form`** (122 JSONs en Yucatán generados por
  `scripts/synthesize_short_form_jsons.py` cuando el segmentador detectó leyes
  de ingreso en formato corto) **se excluyen automáticamente** de esta bitácora —
  son markers deterministas, no errores LLM. Identificables por
  `_meta.modelo == "synthesized_short_form"`.
- **Estados fuera de scope (no incluidos)**: Colima, Edomex, Sinaloa, Tabasco.
  Si quieres extenderlos, edita `ESTADOS` en `scripts/generar_bitacora.py`.

## Cómo usar

Para cada caso listado:

1. Abre el JSON en `predial-mx-v2/...` y compáralo contra el TXT fuente en
   `data/{estado}/focus_predial/{anio}/...`.
2. Marca `[x] revisado` cuando termines.
3. Llena los campos con los valores válidos del esquema de abajo.
4. Si el caso pertenece a un patrón transversal, agrégalo a la sección
   **Patrones detectados** y referencia su `P-XX` en `patron:` del caso.

Después de varias revisiones, comparte el archivo conmigo: extraigo los
campos automáticamente y propongo fixes basados en los patrones acumulados.

## Esquema de campos (no editar la tabla)

| Campo | Valores válidos |
|---|---|
| `revisado` | `[ ]` pendiente · `[x]` hecho |
| `veredicto` | `correcto` · `incorrecto` · `parcial` · `invalido` |
| `tipo_correcto` | `tarifa_millar` · `progresivo` · `tasa_unica` · `cuota_fija_simple` · `cuota_fija_escalonada` · `mixto` · `otro_no_clasificado` · `n/a` |
| `causa_raiz` | `segmentacion` · `prompt` · `schema` · `ocr` · `documento_ambiguo` · `api_error` · `clasificacion_correcta` · `otro` |
| `patron` | `P-XX` (id de la sección de patrones) · vacío si caso aislado |
| `notas` | prosa libre |
| `accion` | prosa libre — fix sugerido o `n/a` |

### Convenciones de veredicto

- **`correcto`** — el LLM clasificó bien (incluye casos `otro_no_clasificado`
  legítimos, p.ej. errata documental real).
- **`incorrecto`** — el LLM clasificó mal y hay clasificación correcta posible.
- **`parcial`** — clasificación mejor que nada pero pierde información (ej.
  capturó una de dos tarifas paralelas).
- **`invalido`** — el JSON está vacío / FALTA_PREDIAL / api_error sin recovery.

---

## Patrones detectados

> Acumula aquí los hallazgos transversales que afectan a múltiples casos.
> Cada `P-XX` representa un cambio de código pendiente.

### P-00: ejemplo (borra al agregar el primero)

- **casos**: estado/slug/anio, …
- **diagnostico**: descripción del patrón
- **fix_propuesto**: qué cambiar (prompt, schema, segment, etc.)
- **prioridad**: alta · media · baja
- **estado**: pending · in_progress · done

---

"""


SYNTHETIC_MODELOS = {"synthesized_short_form"}


def _load_cases() -> tuple[list[dict], list[dict], int]:
    """Carga los casos a revisar.

    Returns:
        (otros, revision_no_otro, n_synthetic_skipped)
    """
    otros: list[dict] = []
    revision_no_otro: list[dict] = []
    n_synthetic = 0
    for estado in ESTADOS:
        d = V2_ROOT / estado
        if not d.exists():
            continue
        for jp in sorted(d.glob("*.json")):
            try:
                data = json.loads(jp.read_text(encoding="utf-8"))
            except Exception:
                continue
            anio, slug = _parse_filename(jp.name)
            meta_v2 = data.get("_meta_v2") or {}
            cvegeo = meta_v2.get("cvegeo", "")
            req_rev = bool(meta_v2.get("requiere_revision"))
            razon = meta_v2.get("razon", "") or ""
            escalado = bool(meta_v2.get("escalado", False))
            modelo = (data.get("_meta") or {}).get("modelo", "")
            predial = data.get("predial")

            # Skip JSONs sintéticos (deterministas, no requieren HITL).
            if modelo in SYNTHETIC_MODELOS:
                n_synthetic += 1
                continue

            base = {
                "estado": estado, "anio": anio, "slug": slug, "cvegeo": cvegeo,
                "razon": razon, "escalado": escalado, "modelo": modelo,
                "json_rel": str(jp.relative_to(ROOT)).replace("\\", "/"),
            }

            if isinstance(predial, dict) and predial.get("tipo_esquema") == "otro_no_clasificado":
                base.update({
                    "tipo": "otro_no_clasificado",
                    "categoria": predial.get("categoria", ""),
                    "descripcion": predial.get("descripcion_estructural", "") or "",
                    "tag": _semantic_tag(predial.get("descripcion_estructural", "")),
                })
                otros.append(base)
            elif req_rev:
                tipo_actual = (
                    predial.get("tipo_esquema") if isinstance(predial, dict)
                    else "FALTA_PREDIAL"
                )
                base.update({"tipo": tipo_actual})
                revision_no_otro.append(base)

    return otros, revision_no_otro, n_synthetic


def _entry(case: dict, kind: str) -> str:
    """Construye el stub markdown de un caso."""
    lines: list[str] = []
    lines.append(
        f"### `{case['estado']}/{case['slug']}/{case['anio']}` "
        f"(cvegeo {case['cvegeo']})"
    )
    lines.append("")
    lines.append(f"- **JSON**: [`{case['json_rel']}`]({case['json_rel']})")
    lines.append(f"- **tipo actual** (LLM): `{case['tipo']}`")
    if kind == "otro":
        lines.append(
            f"- **categoria**: `{case['categoria']}`  ·  "
            f"**tag**: `{case['tag']}`"
        )
        desc = (case.get("descripcion") or "").strip()
        if desc:
            lines.append("- **descripcion_estructural**:")
            for ln in desc.splitlines():
                lines.append(f"  > {ln}")
    if case.get("razon"):
        razon_short = case["razon"][:240].replace("\n", " ").replace("`", "'")
        lines.append(f"- **razon**: `{razon_short}`")
    if case.get("escalado"):
        lines.append(f"- **escalado**: sí ({case.get('modelo', '')})")
    lines.append("")
    lines.append("**Revisión**:")
    lines.append("")
    lines.append("- [ ] revisado")
    lines.append("- veredicto: ")
    lines.append("- tipo_correcto: ")
    lines.append("- causa_raiz: ")
    lines.append("- patron: ")
    lines.append("- notas: ")
    lines.append("- accion: ")
    lines.append("")
    return "\n".join(lines)


def _toc(grupos_ord: list, n_revision: int) -> str:
    lines = ["## Tabla de contenidos\n"]
    for i, ((cat, tag), members) in enumerate(grupos_ord, 1):
        anchor = f"grupo-g-{i:02d}-{cat}-{tag}".lower().replace("_", "-")
        lines.append(
            f"- [Grupo G-{i:02d}: `{cat}` / `{tag}` ({len(members)} casos)]"
            f"(#{anchor})"
        )
    lines.append(
        f"- [Casos `requiere_revision` ({n_revision} casos)]"
        f"(#casos-requiere_revision-excluyendo-otro_no_clasificado)"
    )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force", action="store_true",
        help="Sobreescribir aunque exista el archivo (BORRA anotaciones).",
    )
    args = parser.parse_args()

    if OUT_PATH.exists() and not args.force:
        print(f"[abort] {OUT_PATH.relative_to(ROOT)} ya existe. Usa --force para regenerar.")
        return 1

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    otros, revision, n_synthetic = _load_cases()

    grupos: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in otros:
        grupos[(r["categoria"] or "sin_categoria", r["tag"])].append(r)
    grupos_ord = sorted(grupos.items(), key=lambda kv: (-len(kv[1]), kv[0]))

    parts: list[str] = [HEADER, _toc(grupos_ord, len(revision))]
    if n_synthetic:
        parts.append(
            f"> ℹ️ Se excluyeron **{n_synthetic} JSONs sintéticos** "
            f"(`_meta.modelo == 'synthesized_short_form'`) que no requieren HITL.\n"
        )
    parts.append(
        f"## Casos `otro_no_clasificado` ({len(otros)} casos en "
        f"{len(grupos_ord)} grupos)\n"
    )

    for i, ((cat, tag), members) in enumerate(grupos_ord, 1):
        parts.append(
            f"## Grupo G-{i:02d}: `{cat}` / `{tag}` ({len(members)} casos)\n"
        )
        for case in sorted(members, key=lambda c: (c["estado"], c["slug"], c["anio"])):
            parts.append(_entry(case, "otro"))
            parts.append("---\n")

    parts.append(
        f"\n## Casos `requiere_revision` excluyendo `otro_no_clasificado` "
        f"({len(revision)} casos)\n"
    )
    for case in sorted(revision, key=lambda c: (c["estado"], c["slug"], c["anio"])):
        parts.append(_entry(case, "rev"))
        parts.append("---\n")

    OUT_PATH.write_text("\n".join(parts), encoding="utf-8")
    print(f"OK bitácora: {OUT_PATH.relative_to(ROOT)}")
    print(f"  otros agrupados: {len(otros)} en {len(grupos_ord)} grupos")
    print(f"  requiere_revision (no-otro): {len(revision)}")
    print(f"  sintéticos excluidos: {n_synthetic}")
    print(f"  total stubs: {len(otros) + len(revision)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
