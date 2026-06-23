"""Servidor Flask local para revisión HITL — cola unificada.

Lee ``output/hitl/cola_unificada.csv`` y sirve una UI de revisión que muestra:
  - Para detectores D3-D11: vista single-year con JSON v3, TXT, PDF
  - Para D12 (cambio_interanual): vista side-by-side de ambos años
  - Para D1/D2 (segmentación): vista de segment.csv + PDF con fronteras

Decisiones disponibles:
  - confirmar_ok               hallazgo revisado, sin problema
  - propagar_previo            (D12) copiar JSON del año anterior
  - reextraer                  re-correr extracción LLM
  - re_segmentar               re-segmentar + re-extraer (notas: paginas=X-Y)
  - ignorar                    descartar hallazgo

Uso:
  python -m scripts.temps.hitl_revisor_server
  python -m scripts.temps.hitl_revisor_server --port 5500 --no-browser
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
import threading
import webbrowser
from html import escape
from pathlib import Path
from urllib.parse import quote, unquote

from flask import Flask, abort, jsonify, redirect, request, url_for
from werkzeug.exceptions import HTTPException

from src.core.catalog import cvegeo_to_nombre
from src.core.constants import (
    EJERCICIO_FIN,
    EJERCICIO_INI,
    json_predial_hitl_dir,
)
from src.core.corpus import adjacent_json, prefer_hitl_path, resolve_json
from src.core.segment_schema import STATUS_IDENTIDAD, STATUS_NO_LOCALIZADA
from src.hitl.decisiones import DECISIONES_CSV, append_decision, load_latest

DEFAULT_CSV = Path("output/hitl/cola_unificada.csv")
DATA_ROOT = Path("data")

# El corpus v3 (canónico + overlay HITL) vive bajo data/.  Todo se sirve desde ahí.
SERVE_ROOTS = [r.resolve() for r in [DATA_ROOT] if r.exists()]

VALID_DECISIONS = [
    "confirmar_ok",
    "propagar_previo",
    "corregir_previo",
    "reextraer",
    "re_segmentar",
    "sin_ley",
    "ignorar",
]

DECISION_LABELS = {
    "":                          "(sin decisión)",
    "confirmar_ok":              "Confirmar OK (hallazgo revisado, sin problema)",
    "propagar_previo":           "Propagar año previo → actual (D12: actual es error)",
    "corregir_previo":           "Corregir año previo ← actual (D12: previo es error)",
    "reextraer":                 "Re-extraer LLM (segmento OK, extracción falló)",
    "re_segmentar":              "Re-segmentar (notas: paginas=X-Y [; pdf=ruta])",
    "sin_ley":                   "Sin ley (cobertura: no hubo ley de ingresos ese año)",
    "ignorar":                   "Ignorar / descartar",
}

TEMPORAL_DECISIONS = {"propagar_previo", "corregir_previo"}

SEV_CLASSES = {
    "SEV1-H": "sev1h", "SEV1": "sev1", "SEV2": "sev2", "SEV3": "sev3",
}

ESTADO_PRETTY = {
    "coahuila": "Coahuila", "guanajuato": "Guanajuato", "jalisco": "Jalisco",
    "oaxaca": "Oaxaca", "queretaro": "Querétaro", "sanluispotosi": "San Luis Potosí",
    "sonora": "Sonora", "tamaulipas": "Tamaulipas", "yucatan": "Yucatán",
    "chihuahua": "Chihuahua", "colima": "Colima", "edomex": "Estado de México",
    "sinaloa": "Sinaloa", "tabasco": "Tabasco",
}

def _has_flag(detector_field: str, flag: str) -> bool:
    """Check if flag is in a comma-separated detector field."""
    return flag in {d.strip() for d in detector_field.split(",")}


def _display_muni(row: dict) -> str:
    """Nombre de municipio para mostrar: SIEMPRE desde el catálogo (cvegeo).

    Nunca usa texto extraído como identidad.  Si no hay cvegeo (identidad no
    resuelta) cae al campo ``municipio`` de la fila, que ya trae el marcador
    "(identidad no resuelta) …" para diagnóstico.
    """
    return (
        cvegeo_to_nombre(row.get("cvegeo", ""))
        or row.get("municipio", "")
        or row.get("municipio_slug", "")
    )


def _norm(s: str) -> str:
    import unicodedata
    n = unicodedata.normalize("NFD", s or "")
    return "".join(c for c in n if unicodedata.category(c) != "Mn").lower()


def _try_resolve_json(estado_slug: str, muni_slug: str, anio: int) -> Path:
    """Resolve v3 JSON path dynamically. Returns Path("") if not found."""
    return resolve_json(estado_slug, anio, muni_slug) or Path("")


# ── State ──

class State:
    def __init__(self, csv_path: Path, decisiones_path: Path | None = None):
        self.csv_path = csv_path
        # Dónde se leen/escriben las decisiones.  En el kit por estado apunta al
        # archivo propio del asistente (que OneDrive sincroniza de vuelta).
        self.decisiones_path = decisiones_path or DECISIONES_CSV
        self.rows: list[dict] = []
        self.id_to_idx: dict[str, int] = {}
        self.fieldnames: list[str] = []
        self._lock = threading.Lock()
        self.load()

    def load(self) -> None:
        with self._lock:
            if not self.csv_path.exists():
                raise SystemExit(f"No existe {self.csv_path}. Corre run_detectors primero.")
            with self.csv_path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.fieldnames = reader.fieldnames or []
                self.rows = list(reader)
            # La cola es una vista derivada; las decisiones viven en el log
            # append-only.  Overlay la última decisión por caso al cargar para
            # que reinicios/rebuilds preserven el trabajo del revisor.
            latest = load_latest(self.decisiones_path)
            for r in self.rows:
                d = latest.get(r.get("id", ""))
                if d:
                    r["decision"] = d.get("decision", "")
                    r["notas"] = d.get("notas", "")
            self.id_to_idx = {r.get("id", ""): i for i, r in enumerate(self.rows)}

    def save_atomic(self) -> None:
        with self._lock:
            tmp_fd, tmp_path = tempfile.mkstemp(
                suffix=".csv", prefix=self.csv_path.stem + ".",
                dir=str(self.csv_path.parent),
            )
            try:
                with os.fdopen(tmp_fd, "w", encoding="utf-8", newline="") as f:
                    w = csv.DictWriter(f, fieldnames=self.fieldnames)
                    w.writeheader()
                    w.writerows(self.rows)
                os.replace(tmp_path, self.csv_path)
            except Exception:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                raise

    def update_decision(self, row_id: str, decision: str, notas: str,
                        sub_opcion: str = "") -> dict:
        if decision not in VALID_DECISIONS and decision != "":
            raise ValueError(f"decisión inválida: {decision!r}")
        idx = self.id_to_idx.get(row_id)
        if idx is None:
            raise KeyError(f"row_id desconocido: {row_id}")
        row = self.rows[idx]
        # Fuente de verdad: log append-only (sobrevive a rebuilds de la cola).
        append_decision(
            id=row_id,
            decision=decision,
            cvegeo=row.get("cvegeo", ""),
            estado_slug=row.get("estado_slug", ""),
            municipio_slug=row.get("municipio_slug", ""),
            anio=row.get("anio", ""),
            sub_opcion=sub_opcion,
            notas=notas,
            path=self.decisiones_path,
        )
        with self._lock:
            row["decision"] = decision
            row["notas"] = notas
        self.save_atomic()  # cache local; el log es la fuente de verdad
        return row

    def next_pending_id(self, after_id: str | None) -> str | None:
        with self._lock:
            start = (self.id_to_idx.get(after_id, -1) + 1) if after_id else 0
            for i in range(start, len(self.rows)):
                if not (self.rows[i].get("decision") or "").strip():
                    return self.rows[i].get("id", "")
            for i in range(0, start):
                if not (self.rows[i].get("decision") or "").strip():
                    return self.rows[i].get("id", "")
            return None

    def get(self, row_id: str) -> dict | None:
        idx = self.id_to_idx.get(row_id)
        return self.rows[idx] if idx is not None else None

    def get_related(self, row: dict) -> list[dict]:
        """All rows for the same (estado_slug, municipio_slug, anio)."""
        key = (row.get("estado_slug"), row.get("municipio_slug"), row.get("anio"))
        return [r for r in self.rows
                if (r.get("estado_slug"), r.get("municipio_slug"), r.get("anio")) == key]

    def add_row(self, row_dict: dict) -> str:
        """Append a new row to the queue. Returns its id."""
        with self._lock:
            self.rows.append(row_dict)
            idx = len(self.rows) - 1
            rid = row_dict.get("id", "")
            self.id_to_idx[rid] = idx
        self.save_atomic()
        return rid

    def find_existing_d12(self, estado_slug: str, municipio_slug: str, anio: int) -> str | None:
        """Find existing row with cambio_interanual or verificacion_temporal flag."""
        for r in self.rows:
            if (r.get("estado_slug") == estado_slug
                    and r.get("municipio_slug") == municipio_slug
                    and str(r.get("anio")) == str(anio)
                    and (_has_flag(r.get("detector", ""), "cambio_interanual")
                         or _has_flag(r.get("detector", ""), "verificacion_temporal"))):
                return r.get("id")
        return None


# ── File resolution ──

def _glob_first(root: Path, pattern: str) -> Path | None:
    if not root.exists():
        return None
    matches = sorted(root.glob(pattern))
    return matches[0] if matches else None


def localizar_archivos(estado_slug: str, anio: int, muni_slug: str,
                       json_path: Path | None = None) -> dict:
    out: dict[str, Path] = {}
    if json_path and json_path.exists():
        out["json"] = json_path

    fp_dir = DATA_ROOT / estado_slug / "focus_predial" / str(anio)
    pat = f"*_PREDIAL_{anio}_{muni_slug}"

    txt = _glob_first(fp_dir, pat + ".txt")
    if txt:
        out["txt"] = txt
    pdf = _glob_first(fp_dir, pat + ".pdf")
    if pdf:
        out["pdf"] = pdf

    ov_dir = DATA_ROOT / estado_slug / "focus_predial_overrides" / str(anio)
    ov_txt = _glob_first(ov_dir, pat + ".txt")
    if ov_txt:
        out["override_txt"] = ov_txt
    ov_pdf = _glob_first(ov_dir, pat + ".pdf")
    if ov_pdf:
        out["override_pdf"] = ov_pdf

    if "pdf" not in out:
        raw_dir = DATA_ROOT / estado_slug / "pdf_raw" / str(anio)
        raw_pdf = _glob_first(raw_dir, f"*{muni_slug}*.pdf")
        if raw_pdf:
            out["pdf_raw_fallback"] = raw_pdf

    return out


def cargar_v3(json_path: Path) -> tuple[dict, dict, dict]:
    """Returns (predial_dict, meta_dict, meta_v3_dict)."""
    try:
        doc = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return {}, {}, {}
    return (
        doc.get("predial") or {},
        doc.get("_meta") or {},
        doc.get("_meta_v3") or {},
    )


def _prefer_hitl_path(json_path: Path) -> Path:
    """If an HITL-corrected version of this JSON exists, prefer it."""
    if not json_path.name:
        return json_path
    return prefer_hitl_path(json_path)


def _apply_temporal_inline(row: dict, decision: str) -> Path | None:
    """Apply propagation/correction immediately so the next comparison is fresh."""
    json_path = _prefer_hitl_path(Path(row.get("json_path", "")))
    if not json_path.exists():
        return None

    est_slug = row.get("estado_slug", "")
    anio = int(row.get("anio", 0))
    prev_year = anio - 1

    if decision == "propagar_previo":
        src = _find_adjacent_json(str(json_path), anio, -1)
        if not src:
            return None
        dst = json_predial_hitl_dir(est_slug, anio) / json_path.name
        modelo, imputed_from, target = "imputed_human_propagation", prev_year, anio
    elif decision == "corregir_previo":
        src = json_path
        dst = json_predial_hitl_dir(est_slug, prev_year) / json_path.name.replace(
            f"_{anio}_", f"_{prev_year}_"
        )
        modelo, imputed_from, target = "imputed_human_correction", anio, prev_year
    else:
        return None

    dst.parent.mkdir(parents=True, exist_ok=True)
    try:
        doc = json.loads(src.read_text(encoding="utf-8"))
    except Exception:
        return None

    from datetime import datetime, timezone
    meta = doc.get("_meta") or {}
    meta["modelo"] = modelo
    meta["imputed_from_year"] = imputed_from
    meta["target_year"] = target
    meta["hitl_timestamp"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    meta["hitl_decision"] = decision
    doc["_meta"] = meta

    dst.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return dst


def _find_adjacent_json(json_path: str, anio: int, offset: int) -> Path | None:
    """Find adjacent year's JSON (overlay HITL preferido). None si no existe."""
    return adjacent_json(json_path, anio, offset)


def _find_prev_json(json_path: str, anio: int) -> Path | None:
    return _find_adjacent_json(json_path, anio, -1)


def _enqueue_temporal_verification(row: dict, decision: str) -> str | None:
    """After propagar_previo or corregir_previo, enqueue adjacent year for review.

    propagar_previo (prev→curr): verify consistency with curr+1
    corregir_previo (curr→prev): verify consistency with prev-1
    """
    est_slug = row.get("estado_slug", "")
    muni_slug = row.get("municipio_slug", "")
    anio = int(row.get("anio", 0))
    json_path = row.get("json_path", "")

    if decision == "propagar_previo":
        check_anio = anio + 1
        direction = "adelante"
    else:
        check_anio = anio - 1
        direction = "atrás"

    # Don't verify outside the panel period (comparison needs check_anio-1 and check_anio)
    if check_anio <= EJERCICIO_INI or check_anio >= EJERCICIO_FIN:
        return None

    adj_json = _find_adjacent_json(json_path, anio, check_anio - anio)
    if not adj_json:
        return None

    existing = state.find_existing_d12(est_slug, muni_slug, check_anio)
    if existing:
        return existing

    import hashlib
    raw = f"{est_slug}|{muni_slug}|{check_anio}|verificacion_temporal"
    rid = hashlib.sha1(raw.encode()).hexdigest()[:12]

    new_row = {
        "id": rid,
        "severidad": "SEV1",
        "detector": "verificacion_temporal",
        "estado": row.get("estado", ""),
        "estado_slug": est_slug,
        "municipio": row.get("municipio", ""),
        "municipio_slug": muni_slug,
        "cvegeo": row.get("cvegeo", ""),
        "anio": str(check_anio),
        "senal": (f"Verificación temporal ({direction}): tras '{decision}' en {anio}, "
                  f"revisar consistencia {check_anio-1}→{check_anio}"),
        "json_path": str(adj_json),
        "segment_row": "-1",
        "decision": "",
        "notas": "",
        "timestamp": "",
    }
    return state.add_row(new_row)


# ── JSON diff engine ──

def _json_diff(old, new, path: str = "") -> list[dict]:
    """Recursive structural diff. Returns list of {path, type, old, new}."""
    diffs = []
    if isinstance(old, dict) and isinstance(new, dict):
        all_keys = sorted(set(old) | set(new))
        for k in all_keys:
            child_path = f"{path}.{k}" if path else k
            if k not in old:
                diffs.append({"path": child_path, "type": "added", "old": None, "new": new[k]})
            elif k not in new:
                diffs.append({"path": child_path, "type": "removed", "old": old[k], "new": None})
            else:
                diffs.extend(_json_diff(old[k], new[k], child_path))
    elif isinstance(old, list) and isinstance(new, list):
        for i in range(max(len(old), len(new))):
            child_path = f"{path}[{i}]"
            if i >= len(old):
                diffs.append({"path": child_path, "type": "added", "old": None, "new": new[i]})
            elif i >= len(new):
                diffs.append({"path": child_path, "type": "removed", "old": old[i], "new": None})
            else:
                diffs.extend(_json_diff(old[i], new[i], child_path))
    elif old != new:
        diffs.append({"path": path, "type": "changed", "old": old, "new": new})
    return diffs


def _render_diff_html(diffs: list[dict]) -> str:
    """Render diff list as HTML table with color coding."""
    if not diffs:
        return '<p style="color:#10b981;font-size:.85rem">Sin diferencias.</p>'
    parts = ['<table class="diff-table">',
             '<thead><tr><th>Campo</th><th>Anterior</th><th>Nuevo</th></tr></thead>',
             '<tbody>']
    for d in diffs[:60]:
        path = escape(d["path"])
        dtype = d["type"]
        if dtype == "added":
            cls = "diff-add"
            old_cell = '<td class="diff-empty">—</td>'
            new_cell = f'<td class="diff-new">{escape(str(d["new"]))}</td>'
        elif dtype == "removed":
            cls = "diff-del"
            old_cell = f'<td class="diff-old">{escape(str(d["old"]))}</td>'
            new_cell = '<td class="diff-empty">—</td>'
        else:
            cls = "diff-chg"
            old_cell = f'<td class="diff-old">{escape(str(d["old"]))}</td>'
            new_cell = f'<td class="diff-new">{escape(str(d["new"]))}</td>'
        parts.append(f'<tr class="{cls}"><td class="diff-path">{path}</td>{old_cell}{new_cell}</tr>')
    parts.append('</tbody></table>')
    if len(diffs) > 60:
        parts.append(f'<p class="help">... y {len(diffs) - 60} más</p>')
    return "".join(parts)


def _render_json_highlighted(data: dict, changed_paths: set[str], prefix: str = "") -> str:
    """Render JSON with changed fields highlighted."""
    raw = json.dumps(data, indent=2, ensure_ascii=False)
    if not changed_paths:
        return f'<div class="scroll">{escape(raw)}</div>'

    lines = raw.split("\n")
    parts = []
    for line in lines:
        highlighted = False
        for cp in changed_paths:
            key_part = cp.rsplit(".", 1)[-1].split("[")[0]
            if key_part and f'"{key_part}"' in line:
                highlighted = True
                break
        if highlighted:
            parts.append(f'<span class="hl-changed">{escape(line)}</span>')
        else:
            parts.append(escape(line))
    return f'<div class="scroll">{"<br>".join(parts)}</div>'


# ── Flask app ──

app = Flask(__name__)
state: State | None = None


def _file_url(p: Path, anchor: str = "") -> str:
    url = url_for("serve_file") + "?path=" + quote(str(p.as_posix()))
    if anchor:
        url += "#search=" + quote(anchor[:60])
    return url


def _is_under_allowed_root(p: Path) -> bool:
    try:
        resolved = p.resolve()
    except Exception:
        return False
    for root in SERVE_ROOTS:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


_pdf_resolve_cache: dict[tuple[str, str], str] = {}


def _resolve_source_pdf(estado_slug: str, source_pdf: str) -> Path | None:
    """Resuelve el ``source_pdf`` de segment.csv a un archivo real en disco.

    segment.csv guarda ``source_pdf`` con formatos heterogéneos entre estados:
    ruta completa repo-relativa (Querétaro), solo el nombre (Sonora, GTO) o una
    ruta parcial año/archivo (Yucatán).  Se intenta el valor tal cual; si no
    existe, se busca por basename bajo ``data/{estado}/`` (pdf_raw + pdf_ocr).
    Cacheado por (estado, basename) para no re-globear miles de filas.
    """
    if not source_pdf:
        return None
    p = Path(source_pdf)
    if p.exists():
        return p
    base = Path(source_pdf.replace("\\", "/")).name
    key = (estado_slug, base)
    if key in _pdf_resolve_cache:
        cached = _pdf_resolve_cache[key]
        return Path(cached) if cached else None
    found = ""
    root = DATA_ROOT / estado_slug
    if base and root.exists():
        for cand in root.rglob(base):
            if cand.is_file():
                found = str(cand)
                break
    _pdf_resolve_cache[key] = found
    return Path(found) if found else None


@app.route("/file")
def serve_file():
    raw = request.args.get("path", "")
    if not raw:
        abort(400, "missing path")
    p = Path(unquote(raw))
    if not _is_under_allowed_root(p) or not p.exists() or not p.is_file():
        abort(403, "forbidden or missing")
    ext = p.suffix.lower()
    if ext == ".pdf":
        mime = "application/pdf"
    elif ext == ".json":
        mime = "application/json; charset=utf-8"
    else:
        mime = "text/plain; charset=utf-8"
    return p.read_bytes(), 200, {"Content-Type": mime}


@app.route("/")
def index():
    return _render_index()


@app.route("/caso/<row_id>")
def caso(row_id):
    return _render_case(row_id)


def _serialize_form_notas(form, decision: str) -> tuple[str, str]:
    """Combina los campos estructurados del form en (notas, sub_opcion).

    Los campos de whitelist/hints se serializan como ``clave=valor;`` para que
    aplicar_decisiones los parsee; el texto libre se preserva al final.
    """
    libre = (form.get("notas") or "").strip()
    sub_opcion = (form.get("sub_opcion") or "").strip()
    parts: list[str] = []
    if decision in ("confirmar_ok", "propagar_previo", "corregir_previo"):
        if sub_opcion == "cambio_menor":
            for campo in ("minimo_predial", "unidad", "periodicidad"):
                v = (form.get(f"edit_{campo}") or "").strip()
                if v:
                    parts.append(f"{campo}={v}")
    elif decision == "reextraer":
        if (form.get("hint_tipo") or "").strip():
            parts.append(f"hint_tipo={form.get('hint_tipo').strip()}")
        if form.get("force_vision"):
            parts.append("force_vision=1")
        if (form.get("hint_paginas") or "").strip():
            parts.append(f"paginas={form.get('hint_paginas').strip()}")
        if (form.get("hint_pdf") or "").strip():
            parts.append(f"pdf={form.get('hint_pdf').strip()}")
        if libre:
            parts.append(f"hint_notas={libre}")
            libre = ""
    elif decision == "re_segmentar":
        if (form.get("hint_paginas") or "").strip():
            parts.append(f"paginas={form.get('hint_paginas').strip()}")
        if (form.get("hint_pdf") or "").strip():
            parts.append(f"pdf={form.get('hint_pdf').strip()}")
    notas = "; ".join(parts)
    if libre:
        notas = (notas + "; " + libre) if notas else libre
    return notas, sub_opcion


@app.route("/caso/<row_id>/decision", methods=["POST"])
def post_decision(row_id):
    decision = (request.form.get("decision") or "").strip()
    notas, sub_opcion = _serialize_form_notas(request.form, decision)
    try:
        updated = state.update_decision(row_id, decision, notas, sub_opcion)
    except (ValueError, KeyError) as e:
        abort(400, str(e))

    if decision in TEMPORAL_DECISIONS:
        _apply_temporal_inline(updated, decision)
        verify_id = _enqueue_temporal_verification(updated, decision)
        if verify_id:
            return redirect(url_for("caso", row_id=verify_id), code=303)

    next_id = state.next_pending_id(after_id=row_id)
    if next_id:
        return redirect(url_for("caso", row_id=next_id), code=303)
    return redirect(url_for("index"), code=303)


@app.route("/next/<row_id>")
def next_case(row_id):
    nxt = state.next_pending_id(after_id=row_id)
    return redirect(url_for("caso", row_id=nxt) if nxt else url_for("index"))


@app.errorhandler(HTTPException)
def handle_http(e):
    return jsonify({"error": str(e)}), e.code


# ── Render ──

_CSS = """
<style>
body{font-family:-apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:0;
     background:#f4f4f7;color:#222}
header{background:#1f2937;color:#fff;padding:.6rem 1rem;display:flex;
       justify-content:space-between;align-items:center}
header a{color:#fff;text-decoration:none;margin-right:1rem}
main{padding:1rem 1.5rem;max-width:1600px;margin:0 auto}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-top:1rem}
.col{background:#fff;border-radius:6px;padding:.8rem;box-shadow:0 1px 2px rgba(0,0,0,.1)}
.col h2{margin:0 0 .5rem;font-size:1rem;color:#374151;border-bottom:1px solid #eee;padding-bottom:.4rem}
.scroll{max-height:400px;overflow:auto;background:#f9fafb;padding:.5rem;
        border:1px solid #e5e7eb;border-radius:4px;font-family:Menlo,Consolas,monospace;
        font-size:.78rem;white-space:pre-wrap;word-break:break-word}
.scroll-txt{max-height:300px;overflow:auto;background:#f9fafb;padding:.5rem;
            border:1px solid #e5e7eb;border-radius:4px;font-family:Menlo,Consolas,monospace;
            font-size:.78rem;white-space:pre-wrap}
embed{width:100%;height:540px;border:1px solid #e5e7eb;border-radius:4px;background:#fff}
.badge{display:inline-block;padding:.15rem .5rem;border-radius:3px;
       font-size:.75rem;font-weight:600;margin-left:.4rem}
.sev1h{background:#7f1d1d;color:#fff}
.sev1{background:#dc2626;color:#fff}
.sev2{background:#f59e0b;color:#fff}
.sev3{background:#10b981;color:#fff}
.det-badge{background:#e0e7ff;color:#3730a3;padding:.15rem .5rem;border-radius:3px;
           font-size:.75rem;margin-left:.3rem}
.diff{background:#fffbeb;border-left:3px solid #f59e0b;padding:.5rem .8rem;
      margin:.5rem 0;font-family:Menlo,Consolas,monospace;font-size:.85rem;
      white-space:pre-wrap}
.flags{background:#fef3c7;border:1px solid #fbbf24;border-radius:6px;padding:.6rem;
       margin:.5rem 0;font-size:.85rem}
.flags .flag{margin:.3rem 0;padding:.2rem .4rem;background:#fff;border-radius:3px;
             border:1px solid #e5e7eb}
form{background:#fff;padding:1rem;border-radius:6px;margin-top:1rem;
     box-shadow:0 1px 2px rgba(0,0,0,.1)}
form label{display:block;font-weight:600;margin:.5rem 0 .25rem}
select,textarea{width:100%;padding:.4rem;border:1px solid #d1d5db;
                border-radius:4px;font:inherit}
textarea{min-height:60px;resize:vertical}
button{background:#3b82f6;color:#fff;border:0;padding:.6rem 1.2rem;
       border-radius:4px;cursor:pointer;font-size:.95rem;margin-top:.6rem}
button:hover{background:#2563eb}
table.list{width:100%;border-collapse:collapse;background:#fff;
           box-shadow:0 1px 2px rgba(0,0,0,.1);border-radius:6px;overflow:hidden}
table.list th{background:#f3f4f6;text-align:left;padding:.4rem .6rem;font-size:.85rem}
table.list th.sortable:hover{background:#e5e7eb}
table.list td{padding:.35rem .6rem;border-top:1px solid #f3f4f6;font-size:.85rem}
table.list tr:hover{background:#fafbff}
table.list a{color:#1d4ed8;text-decoration:none}
.filters{display:flex;gap:.8rem;flex-wrap:wrap;background:#fff;padding:.7rem;
         border-radius:6px;margin-bottom:.8rem;box-shadow:0 1px 2px rgba(0,0,0,.1)}
.filters label{font-size:.85rem;color:#374151}
.help{font-size:.8rem;color:#6b7280;margin-top:.3rem}
.anchor-box{background:#ecfdf5;border:1px solid #86efac;border-radius:4px;
            padding:.3rem .5rem;font-size:.78rem;font-family:monospace;margin:.3rem 0}
.seg-info{background:#f0f9ff;border:1px solid #93c5fd;border-radius:6px;padding:.6rem;
          margin:.5rem 0;font-size:.85rem}
.seg-info .label{color:#1e40af;font-weight:600;margin-right:.4rem}
table.diff-table{width:100%;border-collapse:collapse;background:#fff;font-size:.78rem;
                 font-family:Menlo,Consolas,monospace;margin:.5rem 0;border-radius:4px;
                 overflow:hidden;border:1px solid #e5e7eb}
table.diff-table th{background:#f3f4f6;text-align:left;padding:.3rem .5rem;font-size:.75rem}
table.diff-table td{padding:.25rem .5rem;border-top:1px solid #f3f4f6;max-width:300px;
                    overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.diff-path{color:#6b7280;font-weight:600;white-space:nowrap}
.diff-old{background:#fef2f2;color:#991b1b}
.diff-new{background:#f0fdf4;color:#166534}
.diff-empty{color:#d1d5db}
tr.diff-add{background:#f0fdf4}
tr.diff-del{background:#fef2f2}
tr.diff-chg{background:#fffbeb}
.hl-changed{background:#fef08a;display:inline;padding:0 2px;border-radius:2px}
.verif-banner{background:#dbeafe;border:1px solid #3b82f6;border-radius:6px;
              padding:.6rem;margin:.5rem 0;font-size:.85rem;color:#1e40af}
</style>
"""

_JS = """
<script>
document.addEventListener('keydown',function(e){
  if(e.ctrlKey&&e.key==='Enter'){
    var f=document.querySelector('form'); if(f) f.submit();
  }
  if(['1','2','3','4','5','6','7'].indexOf(e.key)>-1
     && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){
    var s=document.querySelector('select[name=decision]');
    if(s) s.selectedIndex=parseInt(e.key);
  }
});
document.querySelectorAll('th.sortable').forEach(function(th){
  th.addEventListener('click',function(){
    var f=document.getElementById('fform');
    if(!f) return;
    f.querySelector('[name=sort]').value=th.dataset.col;
    f.querySelector('[name=desc]').value=th.dataset.desc;
    f.submit();
  });
});
function hitlToggle(){
  var sel=document.querySelector('select[name=decision]'); if(!sel) return;
  var d=sel.value;
  var subOK=['confirmar_ok','propagar_previo','corregir_previo'].indexOf(d)>-1;
  var subopt=document.getElementById('subopt');
  var reext=document.getElementById('reext');
  var wl=document.getElementById('whitelist');
  if(subopt) subopt.style.display=subOK?'block':'none';
  if(reext) reext.style.display=(d==='reextraer')?'block':'none';
  if(wl){
    var cm=document.querySelector('input[name=sub_opcion][value=cambio_menor]');
    wl.style.display=(subOK && cm && cm.checked)?'block':'none';
  }
}
document.addEventListener('DOMContentLoaded',hitlToggle);
</script>
"""


_SORT_KEYS = {
    "estado": lambda r: (r.get("estado", ""), r.get("municipio", ""), int(r.get("anio", 0))),
    "municipio": lambda r: (r.get("municipio", ""), int(r.get("anio", 0))),
    "anio": lambda r: int(r.get("anio", 0)),
    "sev": lambda r: r.get("severidad", ""),
    "detector": lambda r: r.get("detector", ""),
    "decision": lambda r: (r.get("decision") or "").strip() or "zzz",
}


def _render_index() -> str:
    sev_filter = request.args.get("sev", "")
    est_filter = request.args.get("estado", "")
    det_filter = request.args.get("detector", "")
    pendientes_only = request.args.get("pendientes") == "1"
    sort_col = request.args.get("sort", "estado")
    sort_desc = request.args.get("desc", "") == "1"

    rows = list(state.rows)
    if sev_filter:
        rows = [r for r in rows if r.get("severidad") == sev_filter]
    if est_filter:
        rows = [r for r in rows if r.get("estado_slug") == est_filter]
    if det_filter:
        rows = [r for r in rows if _has_flag(r.get("detector", ""), det_filter)]
    if pendientes_only:
        rows = [r for r in rows if not (r.get("decision") or "").strip()]

    key_fn = _SORT_KEYS.get(sort_col, _SORT_KEYS["estado"])
    rows.sort(key=key_fn, reverse=sort_desc)

    # Paginación
    try:
        page_size = max(10, min(1000, int(request.args.get("page_size", 200))))
    except ValueError:
        page_size = 200
    n_filtered = len(rows)
    n_pages = max(1, (n_filtered + page_size - 1) // page_size)
    try:
        page = int(request.args.get("page", 1))
    except ValueError:
        page = 1
    page = max(1, min(n_pages, page))
    page_rows = rows[(page - 1) * page_size: page * page_size]

    n_total = len(state.rows)
    n_decididos = sum(1 for r in state.rows if (r.get("decision") or "").strip())
    estados = sorted({r.get("estado_slug", "") for r in state.rows if r.get("estado_slug")})
    detectors = sorted({
        d.strip()
        for r in state.rows
        for d in (r.get("detector") or "").split(",")
        if d.strip()
    })
    sevs = sorted({r.get("severidad", "") for r in state.rows if r.get("severidad")})

    body = []
    body.append(_header(f"HITL — {n_decididos}/{n_total} decididos"))
    body.append('<main>')

    # Filters
    body.append('<div class="filters">')
    body.append('  <form id="fform" method="get" style="display:flex;gap:.6rem;flex-wrap:wrap;'
                'align-items:end;padding:0;box-shadow:none;background:transparent">')
    body.append(f'  <input type="hidden" name="sort" value="{escape(sort_col)}">')
    body.append(f'  <input type="hidden" name="desc" value="{"1" if sort_desc else ""}">')
    body.append('  <div><label>Severidad</label>')
    body.append('  <select name="sev" onchange="this.form.submit()">')
    body.append('    <option value="">todas</option>')
    for s in sevs:
        sel = ' selected' if sev_filter == s else ''
        body.append(f'    <option value="{s}"{sel}>{s}</option>')
    body.append('  </select></div>')
    body.append('  <div><label>Detector</label>')
    body.append('  <select name="detector" onchange="this.form.submit()">')
    body.append('    <option value="">todos</option>')
    for d in detectors:
        sel = ' selected' if det_filter == d else ''
        body.append(f'    <option value="{d}"{sel}>{d}</option>')
    body.append('  </select></div>')
    body.append('  <div><label>Estado</label>')
    body.append('  <select name="estado" onchange="this.form.submit()">')
    body.append('    <option value="">todos</option>')
    for est in estados:
        sel = ' selected' if est_filter == est else ''
        body.append(f'    <option value="{est}"{sel}>{escape(ESTADO_PRETTY.get(est, est))}</option>')
    body.append('  </select></div>')
    body.append(f'  <div><label><input type="checkbox" name="pendientes" value="1"'
                f' {"checked" if pendientes_only else ""} onchange="this.form.submit()">'
                f' Solo pendientes</label></div>')
    body.append('  </form></div>')

    def _sort_hdr(label: str, col: str) -> str:
        is_active = sort_col == col
        next_desc = "1" if (is_active and not sort_desc) else ""
        arrow = " ▲" if (is_active and not sort_desc) else " ▼" if (is_active and sort_desc) else ""
        return (f'<th class="sortable" data-col="{col}" data-desc="{next_desc}"'
                f' style="cursor:pointer;user-select:none">{label}{arrow}</th>')

    def _page_url(p: int) -> str:
        params = {
            "sev": sev_filter, "estado": est_filter, "detector": det_filter,
            "sort": sort_col, "desc": "1" if sort_desc else "",
            "page_size": page_size, "page": p,
        }
        if pendientes_only:
            params["pendientes"] = "1"
        qs = "&".join(f"{k}={quote(str(v))}" for k, v in params.items() if v != "")
        return url_for("index") + "?" + qs

    def _pager() -> str:
        lo = (page - 1) * page_size + 1 if n_filtered else 0
        hi = min(page * page_size, n_filtered)
        parts = ['<div style="display:flex;gap:.6rem;align-items:center;margin:.6rem 0">']
        if page > 1:
            parts.append(f'<a href="{_page_url(page - 1)}">‹ Anterior</a>')
        parts.append(f'<span style="font-size:.85rem;color:#6b7280">'
                     f'{lo}–{hi} de {n_filtered} (pág. {page}/{n_pages})</span>')
        if page < n_pages:
            parts.append(f'<a href="{_page_url(page + 1)}">Siguiente ›</a>')
        parts.append('</div>')
        return "".join(parts)

    body.append(f'<p style="color:#6b7280;font-size:.85rem">'
                f'{n_filtered} filtradas de {n_total} totales.</p>')
    body.append(_pager())
    body.append('<table class="list" id="htable">')
    body.append(f'  <thead><tr>{_sort_hdr("SEV", "sev")}{_sort_hdr("Detector", "detector")}'
                f'{_sort_hdr("Estado", "estado")}{_sort_hdr("Municipio", "municipio")}'
                f'{_sort_hdr("Año", "anio")}<th>Señal</th>'
                f'{_sort_hdr("Decisión", "decision")}</tr></thead>')
    body.append('  <tbody>')
    for r in page_rows:
        rid = r.get("id", "")
        sev = r.get("severidad", "")
        sev_cls = SEV_CLASSES.get(sev, "sev3")
        body.append('<tr>')
        body.append(f'  <td><span class="badge {sev_cls}">{escape(sev)}</span></td>')
        det_badges = " ".join(
            f'<span class="det-badge">{escape(d.strip())}</span>'
            for d in (r.get("detector") or "").split(",") if d.strip()
        )
        body.append(f'  <td>{det_badges}</td>')
        body.append(f'  <td>{escape(r.get("estado", ""))}</td>')
        body.append(f'  <td><a href="{url_for("caso", row_id=rid)}">'
                    f'{escape(_display_muni(r))}</a></td>')
        body.append(f'  <td>{escape(r.get("anio", ""))}</td>')
        body.append(f'  <td style="font-size:.75rem;color:#6b7280;max-width:300px;'
                    f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">'
                    f'{escape((r.get("senal", "") or "")[:150])}</td>')
        dec = (r.get("decision") or "").strip()
        body.append(f'  <td><b style="color:{"#10b981" if dec else "#9ca3af"}">'
                    f'{escape(dec or "—")}</b></td>')
        body.append('</tr>')
    body.append('  </tbody></table>')
    body.append(_pager())
    body.append('</main>')

    return _html("HITL revisor — cola unificada", "".join(body))


def _render_case(row_id: str) -> str:
    r = state.get(row_id)
    if not r:
        abort(404, "caso no encontrado")
    est_slug = r.get("estado_slug", "")
    muni_slug = r.get("municipio_slug", "")
    estado = r.get("estado", est_slug)
    municipio = _display_muni(r)
    anio = int(r.get("anio", 0))
    sev = r.get("severidad", "")
    sev_cls = SEV_CLASSES.get(sev, "sev3")
    detector = r.get("detector", "")
    json_path = Path(r.get("json_path", ""))
    if not json_path.name.endswith(".json") or not json_path.exists():
        json_path = _try_resolve_json(est_slug, muni_slug, anio)
    else:
        json_path = _prefer_hitl_path(json_path)

    det_flags = [d.strip() for d in detector.split(",")]

    body = []
    body.append(_header(f"{municipio}, {estado} ({anio})"))
    body.append('<main>')

    # Header with all detector badges
    badge_html = " ".join(f'<span class="det-badge">{escape(d)}</span>' for d in det_flags)
    body.append(f'<h1 style="margin:.5rem 0">{escape(municipio)}, {escape(estado)} — {anio} '
                f'<span class="badge {sev_cls}">{escape(sev)}</span> {badge_html}</h1>')

    # Show signals grouped by detector
    senal = r.get("senal", "")
    body.append(f'<div class="diff"><b>señales:</b> {escape(senal)}</div>')

    # Related rows (verificacion_temporal rows are still separate)
    related = state.get_related(r)
    if len(related) > 1:
        body.append('<div class="flags"><b>Filas relacionadas:</b>')
        for rel in related:
            if rel.get("id") == row_id:
                continue
            dec = (rel.get("decision") or "").strip()
            dec_tag = f' <span style="color:#10b981">[{dec}]</span>' if dec else ''
            body.append(
                f'<div class="flag">'
                f'<span class="badge {SEV_CLASSES.get(rel.get("severidad", ""), "sev3")}">'
                f'{escape(rel.get("severidad", ""))}</span> '
                f'<span class="det-badge">{escape(rel.get("detector", ""))}</span> '
                f'{escape((rel.get("senal", "") or "")[:120])}{dec_tag}'
                f'</div>'
            )
        body.append('</div>')

    # Verification banner
    if _has_flag(detector, "verificacion_temporal"):
        body.append('<div class="verif-banner"><b>Verificación temporal automática:</b> '
                    f'{escape(senal)}</div>')

    # Resolve segment data for current year
    seg_idx = int(r.get("segment_row", -1))
    seg_row_data = None
    if seg_idx >= 0:
        seg_rows = _load_segment_csv(est_slug)
        if 0 <= seg_idx < len(seg_rows):
            seg_row_data = seg_rows[seg_idx]
    if not seg_row_data:
        seg_row_data = _find_seg_row(est_slug, muni_slug, anio)
    anchor_start = (seg_row_data or {}).get("anchor_text_start", "")

    # Always try side-by-side with previous year; fall back to single-year
    prev = _find_prev_json(str(json_path), anio)
    if prev and prev.exists():
        body.append(_render_sidebyside(est_slug, muni_slug, anio, json_path, anchor_start))
    else:
        body.append(_render_seg_info(seg_row_data))
        body.append(_render_single_year(est_slug, muni_slug, anio, json_path, anchor_start))

    # Decision form
    current_decision = (r.get("decision") or "").strip()
    current_notas = r.get("notas") or ""
    body.append(f'<form method="post" action="{url_for("post_decision", row_id=row_id)}">')
    body.append('  <label for="decision">Decisión (atajos: 1-7)</label>')
    body.append('  <select id="decision" name="decision" onchange="hitlToggle()">')
    for d in [""] + VALID_DECISIONS:
        sel = " selected" if current_decision == d else ""
        body.append(f'    <option value="{escape(d)}"{sel}>{escape(DECISION_LABELS[d])}</option>')
    body.append('  </select>')

    # Sub-opción Fiel / Con cambio menor (§6a) — confirmar/propagar/corregir
    body.append('  <div id="subopt" style="display:none;margin-top:.5rem">')
    body.append('    <label>Procedencia</label>')
    body.append('    <label style="font-weight:normal;display:inline">'
                '<input type="radio" name="sub_opcion" value="fiel" checked onchange="hitlToggle()"> Fiel</label>'
                '&nbsp;&nbsp;'
                '<label style="font-weight:normal;display:inline">'
                '<input type="radio" name="sub_opcion" value="cambio_menor" onchange="hitlToggle()"> Con cambio menor</label>')
    body.append('    <div id="whitelist" style="display:none;margin-top:.4rem">')
    body.append('      <p class="help">Whitelist (no estructural). Vacío = sin cambio.</p>')
    for campo, ph in (("minimo_predial", "p. ej. 120.50"),
                      ("unidad", "p. ej. uma"), ("periodicidad", "p. ej. anual")):
        body.append(f'      <input name="edit_{campo}" placeholder="{campo} — {ph}" '
                    f'style="margin:.2rem 0">')
    body.append('    </div>')
    body.append('  </div>')

    # Hints de re-extracción (§6b) — reextraer
    body.append('  <div id="reext" style="display:none;margin-top:.5rem">')
    body.append('    <label>Pistas de re-extracción (sesgan, no fuerzan)</label>')
    body.append('    <select name="hint_tipo">')
    body.append('      <option value="">(sin hint de tipo_esquema)</option>')
    for t in ("tarifa_millar", "progresivo", "tasa_unica", "cuota_fija_simple",
              "cuota_fija_escalonada", "mixto", "otro_no_clasificado"):
        body.append(f'      <option value="{t}">{t}</option>')
    body.append('    </select>')
    body.append('    <label style="font-weight:normal;display:block;margin-top:.3rem">'
                '<input type="checkbox" name="force_vision" value="1"> force_vision '
                '(saltar cascada txt→re-OCR, ir directo a visión)</label>')
    body.append('    <input name="hint_paginas" placeholder="paginas= p. ej. 20-22" style="margin:.2rem 0">')
    body.append('    <input name="hint_pdf" placeholder="pdf= ruta/al/pdf (opcional)" style="margin:.2rem 0">')
    body.append('  </div>')

    body.append('  <label for="notas" style="margin-top:.5rem">Notas (texto libre)</label>')
    body.append(f'  <textarea id="notas" name="notas">{escape(current_notas)}</textarea>')
    body.append('  <p class="help">re_segmentar: usa los campos paginas/pdf de arriba o notas = paginas=20-22 [; pdf=ruta].</p>')
    body.append('  <button type="submit">Guardar y siguiente (Ctrl+Enter)</button>')
    body.append(f'  <a href="{url_for("next_case", row_id=row_id)}" '
                f'style="margin-left:1rem;color:#6b7280">Saltar →</a>')
    body.append('</form>')
    body.append('</main>')

    return _html(f"{municipio} {anio}", "".join(body))


def _render_single_year(est_slug: str, muni_slug: str, anio: int,
                        json_path: Path, anchor: str) -> str:
    parts = ['<div style="margin-top:1rem">']
    archivos = localizar_archivos(est_slug, anio, muni_slug, json_path)

    # JSON
    if json_path.exists():
        pred, meta, meta_v3 = cargar_v3(json_path)
        modelo = meta.get("modelo", "?")
        fuente = meta_v3.get("procedencia", {}).get("fuente_ganadora", meta.get("fuente", "?"))
        n_tarifas = len(pred.get("tarifas") or [])
        tipos = ", ".join(
            (t.get("esquema") or {}).get("tipo_esquema", "?")
            for t in (pred.get("tarifas") or [])
        )
        parts.append(f'<div style="font-size:.85rem;color:#374151">'
                     f'tarifas: {n_tarifas} · tipos: [{tipos}] · '
                     f'modelo: <code>{escape(modelo)}</code> · fuente: <code>{escape(fuente)}</code></div>')
        json_str = json.dumps(pred, indent=2, ensure_ascii=False)
        parts.append('<details open><summary style="cursor:pointer;font-size:.85rem;'
                     'color:#374151;margin:.4rem 0">JSON predial v3</summary>')
        parts.append(f'<div class="scroll">{escape(json_str)}</div></details>')

    # TXT
    if "txt" in archivos:
        parts.append('<details><summary style="cursor:pointer;font-size:.85rem;'
                     'color:#374151;margin:.4rem 0">TXT focus_predial</summary>')
        try:
            txt = archivos["txt"].read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            txt = f"(error: {e})"
        parts.append(f'<div class="scroll-txt">{escape(txt)}</div></details>')

    # PDF with anchor search
    pdf_key = "pdf" if "pdf" in archivos else "pdf_raw_fallback" if "pdf_raw_fallback" in archivos else None
    if pdf_key:
        url = _file_url(archivos[pdf_key], anchor)
        label = "PDF focus_predial" if pdf_key == "pdf" else "PDF raw (fallback)"
        parts.append(f'<div style="margin:.5rem 0;font-size:.85rem;color:#374151">{label}</div>')
        parts.append(f'<embed src="{url}" type="application/pdf">')
    else:
        parts.append('<div style="color:#9a3412;font-size:.85rem;margin:.4rem 0">'
                     'PDF no disponible.</div>')

    # Source PDF at trigger page is now rendered by _render_seg_info in _render_case

    parts.append('</div>')
    return "".join(parts)


def _render_seg_info(seg_row: dict | None, label: str = "Segmentación") -> str:
    """Render full segment info panel with trigger text and source PDF embeds.

    Distingue (§4a) los estados de segmentación: sin fila (no unió / no existe),
    sección no localizada (error real, SEV1), identidad no resuelta, u OK.
    """
    if not seg_row:
        return ('<div class="seg-info" style="font-size:.8rem;margin:.3rem 0;color:#9a3412">'
                '<b>Sin fila en segment.csv para este caso.</b> No se localizó/segmentó '
                'la ley, o la llave (cvegeo, año) no une.</div>')

    status = (seg_row.get("status") or "ok").strip()
    if status == STATUS_NO_LOCALIZADA:
        return ('<div class="seg-info" style="font-size:.8rem;margin:.3rem 0">'
                '<span class="badge sev1">SEV1</span> '
                '<b>Sección predial NO localizada</b> — no hay página de inicio en '
                'segment.csv. Revisar segmentación o re-segmentar.</div>')
    if status == STATUS_IDENTIDAD:
        raw = " ".join((seg_row.get("municipio_raw") or "").split())[:160]
        return ('<div class="seg-info" style="font-size:.8rem;margin:.3rem 0">'
                '<span class="badge sev1">SEV1</span> '
                f'<b>Identidad no resuelta</b> — el texto «{escape(raw)}» no coincide con '
                'el catálogo INEGI. Revisar OCR/segmentación.</div>')

    parts = ['<div class="seg-info" style="font-size:.8rem;margin:.3rem 0">']
    pg_start = seg_row.get("predial_page_start", "")
    pg_end = seg_row.get("predial_page_end", "")
    ley_start = seg_row.get("ley_page_start", "")
    forced = seg_row.get("forced_end", "")
    expanded = seg_row.get("expansion_applied", "")
    anchor = seg_row.get("anchor_text_start", "")
    anchor_end = seg_row.get("anchor_text_end", "")
    next_tax = seg_row.get("next_tax_label", "")
    # Esquema canónico usa source_pdf; pdf_used es alias legado.
    pdf_used = seg_row.get("source_pdf", "") or seg_row.get("pdf_used", "")
    estado_slug = seg_row.get("estado_slug", "")

    parts.append(f'<span class="label">{escape(label)}:</span> ')
    if pg_start:
        parts.append(f'pp. {pg_start}–{pg_end} ')
    if forced and str(forced).lower() == "true":
        parts.append('<span class="badge sev1h">forced_end</span> ')
    if expanded and str(expanded).lower() == "true":
        parts.append('<span class="badge sev2">expansion</span> ')
    if pdf_used:
        parts.append(f'<br><span class="label">PDF fuente:</span> '
                     f'<code>{escape(str(Path(pdf_used).name))}</code>')

    if anchor:
        parts.append(f'<div class="anchor-box" style="margin-top:.2rem">'
                     f'<b>Trigger inicio:</b> {escape(anchor[:250])}</div>')
    if anchor_end:
        parts.append(f'<div class="anchor-box" style="margin-top:.1rem">'
                     f'<b>Trigger fin:</b> {escape(anchor_end[:250])}</div>')
    if not anchor and next_tax:
        parts.append(f'<div style="color:#6b7280;font-size:.75rem;margin-top:.1rem">'
                     f'fin de sección: {escape(next_tax[:120])}</div>')
    if not anchor and not anchor_end:
        parts.append('<div style="color:#9a3412;font-size:.75rem;margin-top:.1rem">'
                     '(trigger text no disponible — re-ejecutar segmentación)</div>')

    # Botones de navegación del PDF fuente (§5):
    #   (a) inicio de la sección predial
    #   (b) inicio de la ley de ingresos del municipio (verifica identidad y
    #       descarta colisión entre leyes en tomos compartidos).  Se oculta en
    #       Jalisco (un PDF por ley → la ley arranca en la página 1) y cuando no
    #       se conoce ley_page_start.
    if pdf_used:
        src_pdf = _resolve_source_pdf(estado_slug, pdf_used)
        if src_pdf and _is_under_allowed_root(src_pdf):
            # Página para el embed/botón predial: usa inicio de sección si se
            # conoce; si no (p.ej. Querétaro no persiste predial_page_start),
            # cae al inicio de la ley para que el preview más útil esté siempre.
            embed_pg = pg_start or ley_start
            parts.append('<div style="margin-top:.3rem;display:flex;gap:.6rem;flex-wrap:wrap">')
            if pg_start:
                parts.append(f'<a href="{_file_url(src_pdf)}#page={pg_start}" target="_blank" '
                             f'style="font-size:.78rem">▸ PDF: sección predial (pág. {pg_start})</a>')
            show_ley = (estado_slug != "jalisco") and str(ley_start).strip()
            if show_ley:
                parts.append(f'<a href="{_file_url(src_pdf)}#page={ley_start}" target="_blank" '
                             f'style="font-size:.78rem">▸ PDF: inicio de la ley (pág. {ley_start})</a>')
            parts.append('</div>')
            # Embed colapsable en la página más informativa (sección o ley)
            if embed_pg:
                page_url = _file_url(src_pdf) + f"#page={embed_pg}"
                _lbl = "sección predial" if pg_start else "inicio de la ley"
                parts.append(f'<details style="margin-top:.3rem"><summary style="cursor:pointer;'
                             f'font-size:.75rem;color:#374151">'
                             f'&#9654; PDF fuente: página {embed_pg} ({_lbl})</summary>')
                parts.append(f'<embed src="{page_url}" type="application/pdf" '
                             'style="height:400px">')
                parts.append('</details>')
        else:
            # El PDF no se encontró en disco: aviso explícito en vez de ocultar
            # silenciosamente los botones (caso GTO/Sonora/Yucatán con ruta parcial).
            parts.append('<div style="color:#9a3412;font-size:.75rem;margin-top:.3rem">'
                         f'PDF fuente no encontrado en disco: <code>{escape(Path(pdf_used).name)}</code> '
                         '(revisar ruta en segment.csv).</div>')

    parts.append('</div>')
    return "".join(parts)


def _find_seg_row(est_slug: str, muni_slug: str, anio: int) -> dict | None:
    """Find segment row by (municipio, anio) from segment.csv."""
    seg_rows = _load_segment_csv(est_slug)
    for sr in seg_rows:
        sr_muni = sr.get("municipio_slug", sr.get("municipio", ""))
        if _norm(sr_muni) == _norm(muni_slug) and str(sr.get("anio")) == str(anio):
            return sr
    return None


def _render_sidebyside(est_slug: str, muni_slug: str, anio: int,
                       json_path: Path, anchor: str) -> str:
    # Always prefer HITL-corrected versions
    json_path = _prefer_hitl_path(json_path)
    prev_path = _find_prev_json(str(json_path), anio)
    pred_prev, pred_curr = {}, {}

    # Load both JSONs for diff
    if prev_path and prev_path.exists():
        pred_prev, _, _ = cargar_v3(prev_path)
    if json_path.exists():
        pred_curr, _, _ = cargar_v3(json_path)

    # Compute diff and changed paths
    diffs = _json_diff(pred_prev, pred_curr)
    changed_paths = {d["path"] for d in diffs}

    parts = []

    # Diff summary at top (collapsible, starts collapsed)
    if diffs:
        parts.append('<details><summary style="cursor:pointer;font-size:.9rem;'
                     'font-weight:600;color:#374151;margin:.5rem 0">'
                     f'&#9654; Tabla de diferencias ({len(diffs)} campos)</summary>')
        parts.append(_render_diff_html(diffs))
        parts.append('</details>')

    # Segment info for both years
    seg_prev = _find_seg_row(est_slug, muni_slug, anio - 1)
    seg_curr = _find_seg_row(est_slug, muni_slug, anio)

    parts.append('<div class="grid">')

    # Previous year
    parts.append('<div class="col">')
    parts.append(f'<h2>Año previo: {anio - 1}</h2>')
    parts.append(_render_seg_info(seg_prev, f"Segmentación {anio - 1}"))
    if pred_prev:
        parts.append(_render_json_highlighted(pred_prev, changed_paths))
        archivos_prev = localizar_archivos(est_slug, anio - 1, muni_slug, prev_path)
        if "pdf" in archivos_prev:
            prev_anchor = (seg_prev or {}).get("anchor_text_start", "")
            parts.append(f'<embed src="{_file_url(archivos_prev["pdf"], prev_anchor)}"'
                         ' type="application/pdf">')
    else:
        parts.append('<p style="color:#9a3412">JSON del año previo no disponible.</p>')
    parts.append('</div>')

    # Current year
    parts.append('<div class="col">')
    parts.append(f'<h2>Año nuevo: {anio}</h2>')
    parts.append(_render_seg_info(seg_curr, f"Segmentación {anio}"))
    if pred_curr:
        parts.append(_render_json_highlighted(pred_curr, changed_paths))
    archivos_curr = localizar_archivos(est_slug, anio, muni_slug, json_path)
    pdf_key = ("pdf" if "pdf" in archivos_curr
               else "pdf_raw_fallback" if "pdf_raw_fallback" in archivos_curr
               else None)
    if pdf_key:
        parts.append(f'<embed src="{_file_url(archivos_curr[pdf_key], anchor)}"'
                     ' type="application/pdf">')
    parts.append('</div>')

    parts.append('</div>')
    return "".join(parts)


_segment_cache: dict[str, list[dict]] = {}


def _load_segment_csv(estado_slug: str) -> list[dict]:
    if estado_slug in _segment_cache:
        return _segment_cache[estado_slug]
    seg_path = DATA_ROOT / estado_slug / "meta" / "segment.csv"
    if not seg_path.exists():
        return []
    with seg_path.open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    _segment_cache[estado_slug] = rows
    return rows


def _header(subtitle: str) -> str:
    return (f'<header><div><b>HITL Revisor</b> '
            f'<span style="font-weight:normal;opacity:.8;margin-left:.6rem">'
            f'{escape(subtitle)}</span></div>'
            f'<div><a href="{url_for("index")}">Volver al índice</a></div></header>')


def _html(title: str, body: str) -> str:
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{escape(title)}</title>'
            f'{_CSS}</head><body>{body}{_JS}</body></html>')


# ── Main ──

def main():
    global state
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(DEFAULT_CSV),
                    help=f"CSV de cola HITL (default {DEFAULT_CSV}).")
    ap.add_argument("--decisiones", default=None,
                    help="Archivo donde se guardan las decisiones "
                         f"(default {DECISIONES_CSV}).  En el kit por estado "
                         "apunta al archivo propio del asistente.")
    ap.add_argument("--revisor", default=None,
                    help="Nombre del revisor para atribuir las decisiones.")
    ap.add_argument("--port", type=int, default=5500, help="Puerto local (default 5500).")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    if args.revisor:
        os.environ["HITL_REVISOR"] = args.revisor
    dec_path = Path(args.decisiones) if args.decisiones else None
    state = State(Path(args.csv), decisiones_path=dec_path)
    print(f"Cargadas {len(state.rows)} filas desde {args.csv}")
    print(f"Decisiones -> {state.decisiones_path}")
    n_pend = sum(1 for r in state.rows if not (r.get("decision") or "").strip())
    print(f"Pendientes: {n_pend}")

    url = f"http://localhost:{args.port}/"
    print(f"Servidor: {url}")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
