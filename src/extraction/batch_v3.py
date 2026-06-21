"""Batch API (−50%) para extracción v3.  Flujo asíncrono (hasta 24 h).

  1. crear_batch_v3(estado)   → JSONL en data/{estado}/meta/batch_v3/
  2. submit_estado(estado)    → sube + batches.create; guarda ids en submitted.json
  3. (esperar) descargar_estado(estado) → parsea, guarda JSONs válidos, y corre el
     **fallback síncrono** (cascada re-OCR/visión) sobre los que fallaron.

Batch es one-shot: solo el primer intento (txt, OPENAI_MODEL).  Los inválidos o
`otro_no_clasificado` caen al fallback síncrono con `extraer_municipio`.  Escribe
con `_save_result` (misma ruta data/{estado}/json_predial/{anio}/ + overlay-win).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from src.core.catalog import cvegeo_to_nombre
from src.core.constants import PREFIJOS_ESTADO
from src.core.corpus import resolve_json
from src.core.segment_schema import STATUS_OK, read_segment_csv
from src.extraction.llm_extract_v3 import (
    OPENAI_MODEL,
    ROOT,
    SYSTEM_PROMPT_V3,
    USER_TEMPLATE_V3,
    ExtractionResult,
    PredialOutputV3,
    _build_openai_schema,
    _save_result,
    _should_attempt_rescue,
)
from src.extraction.llm_utils import _find_focus_paths, _get_client

BATCH_MAX_REQUESTS = 50_000          # límite duro de OpenAI por batch
BATCH_TOKEN_LIMIT = 1_900_000        # margen bajo el tope de enqueued tokens


def _batch_dir(estado: str) -> Path:
    return Path("data") / estado / "meta" / "batch_v3"


def _has_real_json(estado: str, anio: int, slug: str) -> bool:
    p = resolve_json(estado, anio, slug)
    if not p:
        return False
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("predial") is not None
    except Exception:
        return False


def _pending(estado: str) -> list[tuple[str, int, str, Path]]:
    """(cvegeo, anio, slug, txt_path) de celdas ok con focus y sin extracción real."""
    prefijo = PREFIJOS_ESTADO[estado]
    seg = read_segment_csv(Path("data") / estado / "meta" / "segment.csv")
    seen: set[tuple[str, int]] = set()
    out: list[tuple[str, int, str, Path]] = []
    for r in seg:
        if (r.get("status") or "") != STATUS_OK:
            continue
        cvegeo = (r.get("cvegeo") or "").strip()
        slug = (r.get("municipio_slug") or "").strip()
        try:
            anio = int(r.get("anio") or 0)
        except ValueError:
            anio = 0
        if not cvegeo or not anio or not slug or (cvegeo, anio) in seen:
            continue
        seen.add((cvegeo, anio))
        if _has_real_json(estado, anio, slug):
            continue
        txt, _ = _find_focus_paths(estado, prefijo, anio, slug, cvegeo=cvegeo)
        if txt is None:
            continue  # sin focus → será placeholder de cobertura, no batch
        out.append((cvegeo, anio, slug, txt))
    return out


def crear_batch_v3(estado: str, *, token_limit: int = BATCH_TOKEN_LIMIT,
                   max_requests: int = BATCH_MAX_REQUESTS) -> list[Path]:
    """Genera los JSONL de requests para las celdas pendientes del estado."""
    cells = _pending(estado)
    if not cells:
        print(f"  [{estado}] nada pendiente para batch.")
        return []
    prefijo = PREFIJOS_ESTADO[estado]
    estado_pretty = estado.capitalize()
    schema = _build_openai_schema()
    bdir = _batch_dir(estado)
    bdir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    idx = ntok = nreq = 0
    f = None

    def _new():
        nonlocal idx, f, ntok, nreq
        if f:
            f.close()
        idx += 1
        p = bdir / f"batch_{prefijo}_{idx:03d}.jsonl"
        paths.append(p)
        ntok = nreq = 0
        return p.open("w", encoding="utf-8")

    for cvegeo, anio, slug, txt in cells:
        texto = txt.read_text(encoding="utf-8", errors="ignore").strip()
        if not texto:
            continue
        muni = cvegeo_to_nombre(cvegeo) or slug
        user = USER_TEMPLATE_V3.format(MUNICIPIO=muni, ESTADO=estado_pretty,
                                       ANIO=anio, TEXTO=texto)
        est_tok = len(SYSTEM_PROMPT_V3) // 4 + len(user) // 4 + 800
        if f is None or ntok + est_tok > token_limit or nreq >= max_requests:
            f = _new()
        req = {
            "custom_id": f"{estado}|{cvegeo}|{anio}|{slug}",
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": {
                "model": OPENAI_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT_V3},
                    {"role": "user", "content": user},
                ],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {"name": "PredialOutputV3", "strict": True,
                                    "schema": schema},
                },
            },
        }
        f.write(json.dumps(req, ensure_ascii=False) + "\n")
        ntok += est_tok
        nreq += 1
    if f:
        f.close()
    print(f"  [{estado}] {len(cells)} requests -> {len(paths)} sub-batches en {bdir}")
    return paths


def submit_batch_v3(jsonl_path: Path) -> str:
    client = _get_client()
    with jsonl_path.open("rb") as fh:
        fobj = client.files.create(file=fh, purpose="batch")
    b = client.batches.create(input_file_id=fobj.id,
                              endpoint="/v1/chat/completions",
                              completion_window="24h")
    print(f"  batch {b.id} ({b.status}) <- {jsonl_path.name}")
    return b.id


def submit_estado(estado: str) -> list[str]:
    """Crea y sube todos los sub-batches del estado; registra ids."""
    ids = [submit_batch_v3(p) for p in crear_batch_v3(estado)]
    if ids:
        reg = _batch_dir(estado) / "submitted.json"
        prev = json.loads(reg.read_text()) if reg.exists() else []
        reg.write_text(json.dumps(prev + ids, indent=2), encoding="utf-8")
        print(f"  [{estado}] {len(ids)} batches registrados en {reg}")
    return ids


def _result_from_line(estado: str, res: dict) -> ExtractionResult | None:
    """Construye ExtractionResult de una línea de salida del batch.

    Devuelve None si la respuesta es inválida o `otro_no_clasificado` (→ fallback).
    """
    cid = res.get("custom_id", "")
    try:
        _, cvegeo, anio_s, slug = cid.split("|")
        anio = int(anio_s)
    except ValueError:
        return None
    resp = res.get("response") or {}
    if res.get("error") or resp.get("status_code") != 200:
        return None
    body = resp.get("body") or {}
    try:
        content = body["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        return None
    try:
        output = PredialOutputV3.model_validate(json.loads(content))
    except Exception:
        return None
    if _should_attempt_rescue(output):
        return None  # otro_no_clasificado → fallback síncrono con cascada
    usage = body.get("usage") or {}
    prefijo = PREFIJOS_ESTADO[estado]
    txt, pdf = _find_focus_paths(estado, prefijo, anio, slug, cvegeo=cvegeo)
    return ExtractionResult(
        estado=estado, cvegeo=cvegeo, anio=anio, slug=slug,
        archivo=f"{prefijo}_PREDIAL_{anio}_{slug}.json",
        output=output, requiere_revision=False, razon="batch_ok",
        tokens_in=usage.get("prompt_tokens", 0),
        tokens_out=usage.get("completion_tokens", 0),
        tokens_cached=(usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
        intentos=1, fuente="txt",
        procedencia={
            "archivo_pdf": str(pdf.relative_to(ROOT)) if pdf else None,
            "archivo_txt": str(txt.relative_to(ROOT)) if txt else None,
            "paginas": None, "fuente_ganadora": "txt", "origen_override": False,
        },
    )


def descargar_estado(estado: str, *, run_fallback: bool = True) -> dict:
    """Descarga batches completados, guarda válidos y corre fallback de fallidos."""
    client = _get_client()
    reg = _batch_dir(estado) / "submitted.json"
    if not reg.exists():
        print(f"  [{estado}] sin batches registrados ({reg}).")
        return {}
    ids = json.loads(reg.read_text())
    saved = pendientes = 0
    fallidos: list[tuple[str, int, str]] = []
    for bid in ids:
        b = client.batches.retrieve(bid)
        if b.status != "completed":
            print(f"  {bid}: {b.status} (aún no listo)")
            pendientes += 1
            continue
        text = client.files.content(b.output_file_id).text
        for line in text.splitlines():
            if not line.strip():
                continue
            res = json.loads(line)
            r = _result_from_line(estado, res)
            if r is None:
                cid = res.get("custom_id", "")
                try:
                    _, cvegeo, anio_s, slug = cid.split("|")
                    fallidos.append((cvegeo, int(anio_s), slug))
                except ValueError:
                    pass
            else:
                _save_result(r)
                saved += 1
    print(f"  [{estado}] guardados={saved}  fallidos(->fallback)={len(fallidos)}  "
          f"batches_pendientes={pendientes}")
    if fallidos and run_fallback:
        fallback_sincrono(estado, fallidos)
    return {"saved": saved, "fallidos": len(fallidos), "pendientes": pendientes}


def fallback_sincrono(estado: str, fallidos: list[tuple[str, int, str]]) -> None:
    """Re-extrae los fallidos con la cascada síncrona completa."""
    from src.extraction.llm_extract_v3 import extraer_municipio

    by_cvegeo: dict[str, dict] = defaultdict(lambda: {"slug": "", "anios": []})
    for cvegeo, anio, slug in fallidos:
        by_cvegeo[cvegeo]["slug"] = slug
        by_cvegeo[cvegeo]["anios"].append(anio)
    print(f"  [{estado}] fallback síncrono (cascada) sobre {len(fallidos)} casos...")
    for cvegeo, info in sorted(by_cvegeo.items()):
        extraer_municipio(estado=estado, cvegeo=cvegeo,
                          anios=sorted(set(info["anios"])),
                          slug_override=info["slug"] or None)
