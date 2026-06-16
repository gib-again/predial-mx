"""Servidor Flask local para revisión HITL de cambios interanuales.

Lee `output/anexos/cambios_interanuales.csv` (producido por
`detectar_cambios_interanuales.py`) y sirve una UI side-by-side por caso
que muestra: JSON completo de ambos años (scrolleable), TXT focus_predial
de ambos años, PDF de origen canónico rastreado vía `_meta.fuente`, y un
dropdown de 5 decisiones HITL.

Decisiones disponibles:
  - aceptar_nuevo               cambio detectado es real (reforma documentada)
  - propagar_previo             el JSON nuevo es incorrecto; copia el previo
  - reextraer                   re-correr extracción LLM sobre el segmento existente
  - re_segmentar                el segmento está mal recortado; re-segmentar antes de re-extraer
  - cambio_real_documentado     como aceptar_nuevo + justificación documental

NOTA: la decisión `re_segmentar` NO la procesa todavía
`aplicar_decisiones_hitl.py` (ver P-100 en bitácora). La UI sí la registra
en el CSV; el aplicador queda como TODO.

Persistencia:
  - Cada save actualiza ÚNICAMENTE las columnas `decision` y `notas` del CSV.
  - Escritura atómica (temp + os.replace) — suficiente para un revisor único.
  - Resto del CSV intacto.

Uso:
  pip install flask
  python -m scripts.temps.hitl_revisor_server
  python -m scripts.temps.hitl_revisor_server --port 5500 --no-browser
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import tempfile
import threading
import webbrowser
from html import escape
from pathlib import Path
from urllib.parse import quote, unquote

from flask import Flask, abort, jsonify, redirect, request, url_for
from werkzeug.exceptions import HTTPException

from scripts.temps.build_anexo_esquemas import ESTADO_SLUG_PRETTY

DEFAULT_CSV = Path("output/anexos/cambios_interanuales.csv")
DATA_ROOT = Path("data")
V2_ROOT = Path("predial-mx-v2")
HITL_ROOT = Path("predial-mx-v2-hitl")

# Allowlist de raíces que pueden servirse via /file (defensa contra path traversal).
SERVE_ROOTS = [
    DATA_ROOT.resolve(),
    V2_ROOT.resolve(),
    HITL_ROOT.resolve() if HITL_ROOT.exists() else None,
]
SERVE_ROOTS = [r for r in SERVE_ROOTS if r is not None]

VALID_DECISIONS = [
    "aceptar_nuevo",
    "propagar_previo",
    "reextraer",
    "re_segmentar",
    "cambio_real_documentado",
]

# Pretty labels para el UI (incluye descripción corta).
DECISION_LABELS = {
    "":                          "(sin decisión)",
    "aceptar_nuevo":             "Aceptar el cambio (es real)",
    "propagar_previo":           "Propagar el año previo (nuevo es error)",
    "reextraer":                 "Re-extraer LLM (segmento OK, extracción falló)",
    "re_segmentar":              "Re-segmentar (segmento mal recortado) [pendiente aplicador]",
    "cambio_real_documentado":   "Cambio real DOCUMENTADO (notas obligatorias)",
}

_FNAME_RE = re.compile(r"_PREDIAL_(\d{4})_(.+)\.json$")


# ── Estado en memoria ──

class State:
    def __init__(self, csv_path: Path):
        self.csv_path = csv_path
        self.rows: list[dict] = []
        self.id_to_idx: dict[str, int] = {}
        self.fieldnames: list[str] = []
        self._lock = threading.Lock()
        self.load()

    @staticmethod
    def _row_id(row: dict) -> str:
        key = f"{row.get('estado_slug')}|{row.get('municipio_slug')}|{row.get('anio_prev')}|{row.get('anio')}"
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:10]

    def load(self) -> None:
        with self._lock:
            if not self.csv_path.exists():
                raise SystemExit(
                    f"No existe {self.csv_path}. Corre primero "
                    "`python -m scripts.temps.detectar_cambios_interanuales`."
                )
            with self.csv_path.open(encoding="utf-8") as f:
                reader = csv.DictReader(f)
                self.fieldnames = reader.fieldnames or []
                self.rows = list(reader)
            self.id_to_idx = {self._row_id(r): i for i, r in enumerate(self.rows)}

    def save_atomic(self) -> None:
        """Reescribe el CSV completo de forma atómica (temp + os.replace)."""
        with self._lock:
            tmp_fd, tmp_path = tempfile.mkstemp(
                suffix=".csv",
                prefix=self.csv_path.stem + ".",
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

    def update_decision(self, row_id: str, decision: str, notas: str) -> dict:
        """Actualiza decision/notas de una fila por ID. Atómico."""
        if decision not in VALID_DECISIONS and decision != "":
            raise ValueError(f"decisión inválida: {decision!r}")
        idx = self.id_to_idx.get(row_id)
        if idx is None:
            raise KeyError(f"row_id desconocido: {row_id}")
        with self._lock:
            self.rows[idx]["decision"] = decision
            self.rows[idx]["notas"] = notas
        self.save_atomic()
        return self.rows[idx]

    def next_pending_id(self, after_id: str | None) -> str | None:
        """ID del siguiente caso sin decisión, respetando el orden actual del CSV."""
        with self._lock:
            start = (self.id_to_idx.get(after_id) + 1) if after_id in self.id_to_idx else 0
            for i in range(start, len(self.rows)):
                if not (self.rows[i].get("decision") or "").strip():
                    return self._row_id(self.rows[i])
            # wrap-around
            for i in range(0, start):
                if not (self.rows[i].get("decision") or "").strip():
                    return self._row_id(self.rows[i])
            return None

    def get(self, row_id: str) -> dict | None:
        idx = self.id_to_idx.get(row_id)
        return self.rows[idx] if idx is not None else None


# ── Resolución de archivos auxiliares ──

def _glob_first(root: Path, pattern: str) -> Path | None:
    if not root.exists():
        return None
    matches = sorted(root.glob(pattern))
    return matches[0] if matches else None


def localizar_archivos(estado_slug: str, anio: int, muni_slug: str,
                       json_path: Path) -> dict:
    """Localiza los paths existentes y relevantes para un caso.

    Devuelve dict con keys: `json`, `txt`, `pdf`, `override_txt`, `override_pdf`,
    `pdf_raw_fallback`. Sólo incluye keys cuyo archivo existe.
    """
    out: dict[str, Path] = {"json": json_path}
    fp_dir = DATA_ROOT / estado_slug / "focus_predial" / str(anio)
    pat = f"*_PREDIAL_{anio}_{muni_slug}"

    txt = _glob_first(fp_dir, pat + ".txt")
    if txt:
        out["txt"] = txt
    pdf = _glob_first(fp_dir, pat + ".pdf")
    if pdf:
        out["pdf"] = pdf

    # Overrides — su existencia implica que se usaron (curados manuales).
    ov_dir = DATA_ROOT / estado_slug / "focus_predial_overrides" / str(anio)
    ov_txt = _glob_first(ov_dir, pat + ".txt")
    if ov_txt:
        out["override_txt"] = ov_txt
    ov_pdf = _glob_first(ov_dir, pat + ".pdf")
    if ov_pdf:
        out["override_pdf"] = ov_pdf

    # pdf_raw como fallback SOLO si no hay PDF en focus_predial.
    if "pdf" not in out:
        raw_dir = DATA_ROOT / estado_slug / "pdf_raw" / str(anio)
        raw_pdf = _glob_first(raw_dir, f"*{muni_slug}*.pdf")
        if raw_pdf:
            out["pdf_raw_fallback"] = raw_pdf

    return out


def cargar_predial_y_meta(json_path: Path) -> tuple[dict, dict]:
    """Devuelve (predial_dict, meta_dict). Si JSON v1 sin tabla, reclasifica."""
    try:
        doc = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return {}, {}
    meta = doc.get("_meta") or {}
    pred = doc.get("predial") or {}
    if isinstance(pred, dict) and "tabla" not in pred and pred.get("tipo_esquema"):
        try:
            from src.core.validation import reclasificar
            pred = reclasificar(pred).model_dump()
        except Exception:
            pass
    return pred, meta


def etiqueta_pdf(meta: dict) -> tuple[str, str]:
    """(etiqueta, css_class) según _meta.fuente / modelo."""
    fuente = (meta.get("fuente") or "").lower()
    modelo = (meta.get("modelo") or "").lower()
    if modelo == "hardcoded":
        return ("PDF — fuente: código estatal hardcoded (no rastreable)", "warn")
    if fuente.startswith("pdf_"):
        return ("PDF — fuente directa de extracción", "ok")
    if fuente.startswith("txt"):
        return ("PDF — documento de origen del TXT extraído", "ok")
    return ("PDF — fuente desconocida", "warn")


# ── Flask app ──

app = Flask(__name__)
state: State | None = None


def _file_url(p: Path) -> str:
    return url_for("serve_file") + "?path=" + quote(str(p.as_posix()))


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


@app.route("/caso/<row_id>/decision", methods=["POST"])
def post_decision(row_id):
    decision = (request.form.get("decision") or "").strip()
    notas = (request.form.get("notas") or "").strip()
    try:
        state.update_decision(row_id, decision, notas)
    except (ValueError, KeyError) as e:
        abort(400, str(e))
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
.pdf-label{font-size:.85rem;color:#374151;margin:.4rem 0;padding:.3rem .5rem;
           border-radius:3px;background:#eef2ff}
.pdf-label.warn{background:#fff7ed;color:#9a3412}
.pdf-label.ok{background:#ecfdf5;color:#065f46}
.tabs{display:flex;gap:.4rem;margin-bottom:.4rem;flex-wrap:wrap}
.tab{padding:.25rem .6rem;background:#e5e7eb;border-radius:3px;font-size:.8rem;
     cursor:pointer;border:none}
.tab.active{background:#3b82f6;color:#fff}
.badge{display:inline-block;padding:.15rem .5rem;border-radius:3px;
       font-size:.75rem;font-weight:600;margin-left:.4rem}
.sev1{background:#dc2626;color:#fff}
.sev2{background:#f59e0b;color:#fff}
.sev3{background:#10b981;color:#fff}
.diff{background:#fffbeb;border-left:3px solid #f59e0b;padding:.5rem .8rem;
      margin:.5rem 0;font-family:Menlo,Consolas,monospace;font-size:.85rem;
      white-space:pre-wrap}
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
table.list td{padding:.35rem .6rem;border-top:1px solid #f3f4f6;font-size:.85rem}
table.list tr:hover{background:#fafbff}
table.list a{color:#1d4ed8;text-decoration:none}
.filters{display:flex;gap:.8rem;flex-wrap:wrap;background:#fff;padding:.7rem;
         border-radius:6px;margin-bottom:.8rem;box-shadow:0 1px 2px rgba(0,0,0,.1)}
.filters label{font-size:.85rem;color:#374151}
.help{font-size:.8rem;color:#6b7280;margin-top:.3rem}
</style>
"""

_JS_SHORTCUTS = """
<script>
document.addEventListener('keydown',function(e){
  if(e.ctrlKey&&e.key==='Enter'){
    var f=document.querySelector('form'); if(f) f.submit();
  }
  if(['1','2','3','4','5'].indexOf(e.key)>-1 && !['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)){
    var s=document.querySelector('select[name=decision]');
    if(s) s.selectedIndex=parseInt(e.key);
  }
});
function showTab(idx){
  document.querySelectorAll('.tab-content').forEach(function(el,i){
    el.style.display = i===idx?'block':'none';
  });
  document.querySelectorAll('.tab').forEach(function(el,i){
    el.classList.toggle('active',i===idx);
  });
}
</script>
"""


def _render_index() -> str:
    sev_filter = request.args.get("sev", "")
    est_filter = request.args.get("estado", "")
    pendientes_only = request.args.get("pendientes") == "1"

    rows = state.rows
    if sev_filter:
        rows = [r for r in rows if r.get("severidad_max") == sev_filter]
    if est_filter:
        rows = [r for r in rows if r.get("estado_slug") == est_filter]
    if pendientes_only:
        rows = [r for r in rows if not (r.get("decision") or "").strip()]

    n_total = len(state.rows)
    n_decididos = sum(1 for r in state.rows if (r.get("decision") or "").strip())
    estados = sorted({r.get("estado_slug", "") for r in state.rows if r.get("estado_slug")})

    body = []
    body.append(_header(f"HITL — {n_decididos}/{n_total} decididos"))
    body.append('<main>')
    body.append('<div class="filters">')
    body.append('  <form method="get" style="display:flex;gap:.6rem;flex-wrap:wrap;align-items:end;padding:0;box-shadow:none;background:transparent">')
    body.append('  <div><label>Severidad</label>')
    body.append('  <select name="sev" onchange="this.form.submit()">')
    body.append('    <option value="">todas</option>')
    for s in ["1", "2", "3"]:
        sel = ' selected' if sev_filter == s else ''
        body.append(f'    <option value="{s}"{sel}>SEV{s}</option>')
    body.append('  </select></div>')
    body.append('  <div><label>Estado</label>')
    body.append('  <select name="estado" onchange="this.form.submit()">')
    body.append('    <option value="">todos</option>')
    for est in estados:
        sel = ' selected' if est_filter == est else ''
        body.append(f'    <option value="{est}"{sel}>{escape(ESTADO_SLUG_PRETTY.get(est, est))}</option>')
    body.append('  </select></div>')
    body.append(f'  <div><label><input type="checkbox" name="pendientes" value="1"'
                f' {"checked" if pendientes_only else ""} onchange="this.form.submit()">'
                f' Solo pendientes</label></div>')
    body.append('  </form>')
    body.append('</div>')

    body.append(f'<p style="color:#6b7280;font-size:.85rem">Mostrando {len(rows)} de {n_total} casos.</p>')
    body.append('<table class="list">')
    body.append('  <thead><tr><th>SEV</th><th>racha</th><th>Estado</th><th>Municipio</th>'
                '<th>Año</th><th>tipo prev → nuevo</th><th>cambios</th><th>decisión</th></tr></thead>')
    body.append('  <tbody>')
    for r in rows[:500]:  # cap a 500 para no saturar
        rid = State._row_id(r)
        sev = r.get("severidad_max", "")
        body.append('<tr>')
        body.append(f'  <td><span class="badge sev{sev}">SEV{sev}</span></td>')
        body.append(f'  <td>{escape(r.get("racha_estable_previa", ""))}</td>')
        body.append(f'  <td>{escape(r.get("estado", ""))}</td>')
        body.append(f'  <td><a href="{url_for("caso", row_id=rid)}">{escape(r.get("municipio", ""))}</a></td>')
        body.append(f'  <td>{escape(r.get("anio_prev", ""))}→{escape(r.get("anio", ""))}</td>')
        body.append(f'  <td>{escape(r.get("tipo_prev", ""))} → {escape(r.get("tipo_nuevo", ""))}</td>')
        body.append(f'  <td style="font-size:.75rem;color:#6b7280">{escape((r.get("diff_resumen", "") or "")[:120])}</td>')
        dec = (r.get("decision") or "").strip()
        body.append(f'  <td><b style="color:{"#10b981" if dec else "#9ca3af"}">{escape(dec or "—")}</b></td>')
        body.append('</tr>')
    body.append('  </tbody></table>')
    if len(rows) > 500:
        body.append(f'<p class="help">Mostrando primeros 500 de {len(rows)}; usa los filtros para reducir.</p>')
    body.append('</main>')

    return _html("HITL revisor — casos", "".join(body))


def _render_case(row_id: str) -> str:
    r = state.get(row_id)
    if not r:
        abort(404, "caso no encontrado")
    est_slug = r["estado_slug"]
    muni_slug = r["municipio_slug"]
    estado = r.get("estado", est_slug)
    municipio = r.get("municipio", muni_slug)
    anio_prev = int(r["anio_prev"])
    anio_curr = int(r["anio"])
    sev = r["severidad_max"]

    json_prev = Path(r["json_prev"])
    json_curr = Path(r["json_nuevo"])
    pred_prev, meta_prev = cargar_predial_y_meta(json_prev)
    pred_curr, meta_curr = cargar_predial_y_meta(json_curr)

    archivos_prev = localizar_archivos(est_slug, anio_prev, muni_slug, json_prev)
    archivos_curr = localizar_archivos(est_slug, anio_curr, muni_slug, json_curr)

    body = []
    body.append(_header(f"{municipio}, {estado} ({anio_prev}→{anio_curr})"))
    body.append('<main>')
    body.append(f'<h1 style="margin:.5rem 0">{escape(municipio)}, {escape(estado)} '
                f'<span class="badge sev{sev}">SEV{sev}</span> '
                f'<span style="font-size:.85rem;color:#6b7280">racha previa: {escape(r["racha_estable_previa"])}</span></h1>')
    body.append(f'<p style="color:#6b7280">{escape(r.get("tipo_prev", ""))} → '
                f'<b>{escape(r.get("tipo_nuevo", ""))}</b></p>')
    body.append(f'<div class="diff"><b>cambios detectados:</b><br>{escape(r.get("diff_resumen", ""))}</div>')

    body.append('<div class="grid">')
    body.append(_render_year_panel("Año previo: " + str(anio_prev), pred_prev, meta_prev, archivos_prev))
    body.append(_render_year_panel("Año nuevo: " + str(anio_curr), pred_curr, meta_curr, archivos_curr))
    body.append('</div>')

    # Footer: form de decisión.
    current_decision = (r.get("decision") or "").strip()
    current_notas = r.get("notas") or ""
    body.append(f'<form method="post" action="{url_for("post_decision", row_id=row_id)}">')
    body.append('  <label for="decision">Decisión (atajos: 1-5)</label>')
    body.append('  <select id="decision" name="decision">')
    for d in [""] + VALID_DECISIONS:
        sel = " selected" if current_decision == d else ""
        body.append(f'    <option value="{escape(d)}"{sel}>{escape(DECISION_LABELS[d])}</option>')
    body.append('  </select>')
    body.append('  <label for="notas">Notas</label>')
    body.append(f'  <textarea id="notas" name="notas">{escape(current_notas)}</textarea>')
    body.append('  <button type="submit">Guardar y siguiente (Ctrl+Enter)</button>')
    body.append(f'  <a href="{url_for("next_case", row_id=row_id)}" style="margin-left:1rem;color:#6b7280">Saltar →</a>')
    body.append('</form>')
    body.append('</main>')

    return _html(f"{municipio} {anio_prev}→{anio_curr}", "".join(body))


def _render_year_panel(titulo: str, pred: dict, meta: dict, archivos: dict) -> str:
    parts = ['<div class="col">']
    parts.append(f'<h2>{escape(titulo)}</h2>')

    # JSON predial completo (scrolleable).
    tipo = pred.get("tipo_esquema", "?")
    n_filas = len(pred.get("tabla") or pred.get("tabla_cruda") or [])
    parts.append(f'<div style="font-size:.85rem;color:#374151">'
                 f'tipo: <code>{escape(tipo)}</code> · n_filas: {n_filas}'
                 f' · modelo: <code>{escape(meta.get("modelo", "?"))}</code>'
                 f' · fuente: <code>{escape(meta.get("fuente", "?"))}</code></div>')
    json_str = json.dumps(pred, indent=2, ensure_ascii=False)
    parts.append('<details open><summary style="cursor:pointer;font-size:.85rem;'
                 'color:#374151;margin:.4rem 0">JSON predial completo</summary>')
    parts.append(f'<div class="scroll">{escape(json_str)}</div></details>')

    # TXT focus_predial.
    if "txt" in archivos:
        parts.append('<details><summary style="cursor:pointer;font-size:.85rem;'
                     'color:#374151;margin:.4rem 0">TXT focus_predial</summary>')
        try:
            txt_content = archivos["txt"].read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            txt_content = f"(error leyendo TXT: {e})"
        parts.append(f'<div class="scroll-txt">{escape(txt_content)}</div></details>')

    # PDF de origen canónico.
    pdf_label_text, pdf_class = etiqueta_pdf(meta)
    if "pdf" in archivos:
        parts.append(f'<div class="pdf-label {pdf_class}">{escape(pdf_label_text)}</div>')
        parts.append(f'<embed src="{_file_url(archivos["pdf"])}" type="application/pdf">')
    elif "pdf_raw_fallback" in archivos:
        parts.append('<div class="pdf-label warn">PDF no disponible en focus_predial — '
                     'mostrando pdf_raw como fallback</div>')
        parts.append(f'<embed src="{_file_url(archivos["pdf_raw_fallback"])}" type="application/pdf">')
    else:
        parts.append('<div class="pdf-label warn">PDF de origen no disponible localmente. '
                     'Considerar <code>reextraer</code> o <code>re_segmentar</code>.</div>')

    # Tabs adicionales solo si existen.
    tab_items = []
    if "override_pdf" in archivos:
        tab_items.append(("override PDF", "pdf", archivos["override_pdf"]))
    if "override_txt" in archivos:
        tab_items.append(("override TXT", "txt", archivos["override_txt"]))
    if tab_items:
        parts.append('<details style="margin-top:.5rem"><summary style="cursor:pointer;'
                     'font-size:.85rem;color:#9a3412">Overrides curados manualmente '
                     f'({len(tab_items)})</summary>')
        for label, kind, path in tab_items:
            parts.append(f'<div style="margin:.4rem 0"><b style="font-size:.8rem">{escape(label)}</b><br>')
            if kind == "pdf":
                parts.append(f'<embed src="{_file_url(path)}" type="application/pdf" style="height:300px">')
            else:
                try:
                    c = path.read_text(encoding="utf-8", errors="replace")
                except Exception as e:
                    c = f"(error: {e})"
                parts.append(f'<div class="scroll-txt" style="max-height:200px">{escape(c)}</div>')
            parts.append('</div>')
        parts.append('</details>')

    parts.append('</div>')
    return "".join(parts)


def _header(subtitle: str) -> str:
    return (f'<header><div><b>HITL Revisor</b> '
            f'<span style="font-weight:normal;opacity:.8;margin-left:.6rem">{escape(subtitle)}</span></div>'
            f'<div><a href="{url_for("index")}">Volver al índice</a></div></header>')


def _html(title: str, body: str) -> str:
    return (f'<!DOCTYPE html><html><head><meta charset="utf-8"><title>{escape(title)}</title>'
            f'{_CSS}</head><body>{body}{_JS_SHORTCUTS}</body></html>')


# ── Main ──

def main():
    global state
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--csv", default=str(DEFAULT_CSV),
                    help=f"CSV de cambios HITL (default {DEFAULT_CSV}).")
    ap.add_argument("--port", type=int, default=5500, help="Puerto local (default 5500).")
    ap.add_argument("--no-browser", action="store_true",
                    help="No abrir el navegador automáticamente.")
    args = ap.parse_args()

    state = State(Path(args.csv))
    print(f"Cargadas {len(state.rows)} filas desde {args.csv}")
    n_pend = sum(1 for r in state.rows if not (r.get("decision") or "").strip())
    print(f"Pendientes (sin decisión): {n_pend}")

    url = f"http://localhost:{args.port}/"
    print(f"Servidor: {url}")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    app.run(host="127.0.0.1", port=args.port, debug=False, use_reloader=False)


if __name__ == "__main__":
    main()
