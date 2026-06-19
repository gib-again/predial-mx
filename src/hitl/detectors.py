"""Detectores D1-D12 para la cola HITL unificada.

Cada detector es una función que recibe datos del corpus y devuelve
una lista de ``QueueRow``.  Dos familias:

  Segment-based (D1, D2): operan sobre filas de ``segment.csv``.
  JSON-based (D3-D11): operan sobre un JSON v3 individual.

D12 (cambio interanual) se implementa aparte por su complejidad.
"""

from __future__ import annotations

import re
import statistics

from src.core.catalog import cvegeo_to_nombre
from src.core.corpus import resolve_json
from src.core.segment_schema import STATUS_IDENTIDAD
from src.hitl.queue_schema import QueueRow, make_id


def _seg_identity(row: dict) -> tuple[str, str, str]:
    """(municipio_slug, cvegeo, municipio_display) desde una fila de segment.

    El display siempre sale del catálogo (cvegeo); nunca del texto crudo.
    """
    muni_slug = row.get("municipio_slug") or row.get("slug") or ""
    cvegeo = row.get("cvegeo") or ""
    municipio = cvegeo_to_nombre(cvegeo) or row.get("municipio_raw") or muni_slug
    return muni_slug, cvegeo, municipio

_RE_TRANSITORIO = re.compile(
    r"\b(transitor|abrog|salario\s*m[ií]nim|d[ií]as?\s+de\s+salario|vsm\b|"
    r"vigencia|publicaci[oó]n\s+oficial)",
    re.IGNORECASE,
)


def _bool(val) -> bool:
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in ("true", "1", "yes")


def _resolve_json_path(estado_slug: str, muni_name_or_slug: str, anio: int) -> str:
    """Resolve the v3 JSON path from segment.csv fields (slug o nombre bonito)."""
    return str(resolve_json(estado_slug, anio, muni_name_or_slug) or "")


# ══════════════════════════════════════════════════════════════
# D1 — frontera_sin_verificar (segment.csv, SEV1-H)
# ══════════════════════════════════════════════════════════════

def det_frontera_sin_verificar(
    segment_rows: list[dict],
    estado_slug: str,
    estado: str,
) -> list[QueueRow]:
    """Jalisco-specific: flags rows where forced_end=True or expansion_applied=True."""
    out: list[QueueRow] = []
    for i, row in enumerate(segment_rows):
        if (row.get("status") or "") == STATUS_IDENTIDAD:
            continue  # lo cubre det_identidad_no_resuelta
        forced = _bool(row.get("forced_end", False))
        expanded = _bool(row.get("expansion_applied", False))
        if not (forced or expanded):
            continue
        parts = []
        if forced:
            parts.append("fin del segmento adivinado (no se encontró siguiente impuesto)")
        if expanded:
            parts.append("segmento expandido por ser muy corto")
        muni_slug, cvegeo, municipio = _seg_identity(row)
        anio = int(row.get("anio", 0))
        json_path = _resolve_json_path(estado_slug, muni_slug, anio)
        out.append(QueueRow(
            id=make_id(estado_slug, muni_slug, anio, "frontera_sin_verificar"),
            severidad="SEV1-H",
            detector="frontera_sin_verificar",
            estado=estado,
            estado_slug=estado_slug,
            municipio=municipio,
            municipio_slug=muni_slug,
            cvegeo=cvegeo,
            anio=anio,
            senal="; ".join(parts),
            json_path=json_path,
            segment_row=i,
        ))
    return out


# ══════════════════════════════════════════════════════════════
# D2 — distancia_inicio_anomala (segment.csv, SEV1-H)
# ══════════════════════════════════════════════════════════════

def det_distancia_inicio_anomala(
    segment_rows: list[dict],
    estado_slug: str,
    estado: str,
    *,
    z_threshold: float = 2.0,
) -> list[QueueRow]:
    """Flags rows where char_start is a statistical outlier within the estado-año cohort.

    Only meaningful for offset-based states (tomos compartidos).  Rows with
    char_start <= 0 are skipped.
    """
    by_anio: dict[int, list[tuple[int, dict]]] = {}
    for i, row in enumerate(segment_rows):
        if (row.get("status") or "") == STATUS_IDENTIDAD:
            continue  # identidad no resuelta → no cohorte estadística
        try:
            cs = int(float(row.get("char_start", -1)))
        except (ValueError, TypeError):
            continue
        if cs <= 0:
            continue
        anio = int(row.get("anio", 0))
        by_anio.setdefault(anio, []).append((i, row))

    out: list[QueueRow] = []
    for anio, entries in by_anio.items():
        if len(entries) < 4:
            continue
        values = [int(float(r.get("char_start", 0))) for _, r in entries]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values)
        if stdev < 100:
            continue
        for idx, (row_i, row) in enumerate(entries):
            cs = values[idx]
            z = abs(cs - mean) / stdev
            if z < z_threshold:
                continue
            muni_slug, cvegeo, municipio = _seg_identity(row)
            json_path = _resolve_json_path(estado_slug, muni_slug, anio)
            out.append(QueueRow(
                id=make_id(estado_slug, muni_slug, anio, "distancia_inicio_anomala"),
                severidad="SEV1-H",
                detector="distancia_inicio_anomala",
                estado=estado,
                estado_slug=estado_slug,
                municipio=municipio,
                municipio_slug=muni_slug,
                cvegeo=cvegeo,
                anio=anio,
                senal=(f"Inicio de segmento en posición {cs} — anormalmente "
                       f"{'lejos' if cs > mean else 'cerca'} del promedio "
                       f"(z={z:.1f}, media={mean:.0f}, desv={stdev:.0f})"),
                json_path=json_path,
                segment_row=row_i,
            ))
    return out


# ══════════════════════════════════════════════════════════════
# D2b — identidad_no_resuelta (segment.csv, SEV1)
# ══════════════════════════════════════════════════════════════

def det_identidad_no_resuelta(
    segment_rows: list[dict],
    estado_slug: str,
    estado: str,
) -> list[QueueRow]:
    """Filas cuyo texto de municipio no matchea el catálogo INEGI (cvegeo vacío).

    Es el bug Causa A: texto OCR/header de ley entró al campo de identidad.  En
    vez de propagar un nombre/slug basura, se marca como hallazgo explícito para
    que el revisor corrija OCR/segmentación.
    """
    out: list[QueueRow] = []
    for i, row in enumerate(segment_rows):
        if (row.get("status") or "") != STATUS_IDENTIDAD:
            continue
        raw = (row.get("municipio_raw") or row.get("municipio_slug") or "").strip()
        raw_short = " ".join(raw.split())[:120]
        anio = int(row.get("anio", 0) or 0)
        # slug único por fila (no hay identidad real que consolidar)
        muni_slug = row.get("municipio_slug") or f"sin_identidad_{i}"
        out.append(QueueRow(
            id=make_id(estado_slug, muni_slug, anio, "identidad_no_resuelta"),
            severidad="SEV1",
            detector="identidad_no_resuelta",
            estado=estado,
            estado_slug=estado_slug,
            municipio=f"(identidad no resuelta) {raw_short}" if raw_short
                      else "(identidad no resuelta)",
            municipio_slug=muni_slug,
            cvegeo="",
            anio=anio,
            senal=(f"El texto de municipio no coincide con el catálogo INEGI: "
                   f"«{raw_short}». Revisar OCR/segmentación (posible header de ley "
                   f"capturado como identidad)."),
            json_path="",
            segment_row=i,
        ))
    return out


# ══════════════════════════════════════════════════════════════
# Helpers for JSON-based detectors (D3-D11)
# ══════════════════════════════════════════════════════════════

def _iter_tarifas(doc: dict):
    """Yield (tarifa_idx, tarifa_dict) from a v3 document."""
    predial = doc.get("predial")
    if not isinstance(predial, dict):
        return
    for i, t in enumerate(predial.get("tarifas") or []):
        yield i, t


def _esquema(tarifa: dict) -> dict:
    return tarifa.get("esquema") or {}


def _make_row(
    detector: str,
    severidad: str,
    senal: str,
    estado_slug: str,
    municipio_slug: str,
    anio: int,
    json_path: str,
    *,
    estado: str = "",
    municipio: str = "",
    cvegeo: str = "",
    segment_row: int = -1,
) -> QueueRow:
    return QueueRow(
        id=make_id(estado_slug, municipio_slug, anio, detector),
        severidad=severidad,
        detector=detector,
        estado=estado,
        estado_slug=estado_slug,
        municipio=municipio or municipio_slug,
        municipio_slug=municipio_slug,
        cvegeo=cvegeo,
        anio=anio,
        senal=senal,
        json_path=json_path,
        segment_row=segment_row,
    )


# ══════════════════════════════════════════════════════════════
# D3 — mixto_monocolumna_cuotafija (SEV1)
# ══════════════════════════════════════════════════════════════

def det_mixto_monocolumna_cuotafija(
    doc: dict, estado_slug: str, municipio_slug: str, anio: int,
    json_path: str, **kw,
) -> list[QueueRow]:
    out: list[QueueRow] = []
    for ti, tarifa in _iter_tarifas(doc):
        esq = _esquema(tarifa)
        if esq.get("tipo_esquema") != "mixto":
            continue
        tabla = esq.get("tabla") or []
        if not tabla:
            continue
        nombres, tipos = set(), set()
        all_single = True
        for row in tabla:
            cols = row.get("columnas") or []
            if len(cols) != 1:
                all_single = False
                break
            nombres.add(cols[0].get("nombre"))
            tipos.add(cols[0].get("tipo"))
        if not all_single:
            continue
        if len(nombres) == 1 and tipos == {"cuota_fija"}:
            amb = tarifa.get("ambito", "")
            out.append(_make_row(
                "mixto_monocolumna_cuotafija", "SEV1",
                (f"Tarifa #{ti} ({amb}): esquema mixto con una sola columna "
                 f"'{next(iter(nombres))}', todas cuota fija — "
                 f"probable error de clasificación"),
                estado_slug, municipio_slug, anio, json_path, **kw,
            ))
    return out


# ══════════════════════════════════════════════════════════════
# D4 — tabla_vacia (SEV1)
# ══════════════════════════════════════════════════════════════

_TIPOS_CON_TABLA = {
    "tarifa_millar", "progresivo", "tasa_unica",
    "cuota_fija_simple", "cuota_fija_escalonada", "mixto",
}


def det_tabla_vacia(
    doc: dict, estado_slug: str, municipio_slug: str, anio: int,
    json_path: str, **kw,
) -> list[QueueRow]:
    out: list[QueueRow] = []
    for ti, tarifa in _iter_tarifas(doc):
        esq = _esquema(tarifa)
        tipo = esq.get("tipo_esquema")
        if tipo not in _TIPOS_CON_TABLA:
            continue
        if tipo == "progresivo":
            bloques = esq.get("bloques") or []
            empty = not bloques or all(not (b.get("tabla") or []) for b in bloques)
        else:
            empty = not (esq.get("tabla") or [])
        if empty:
            amb = tarifa.get("ambito", "")
            out.append(_make_row(
                "tabla_vacia", "SEV1",
                (f"Tarifa #{ti} ({amb}): esquema '{tipo}' sin datos en tabla — "
                 f"extracción fallida o sección vacía en PDF"),
                estado_slug, municipio_slug, anio, json_path, **kw,
            ))
    return out


# ══════════════════════════════════════════════════════════════
# D5 — otro_no_clasificado (SEV1)
# ══════════════════════════════════════════════════════════════

def det_otro_no_clasificado(
    doc: dict, estado_slug: str, municipio_slug: str, anio: int,
    json_path: str, **kw,
) -> list[QueueRow]:
    out: list[QueueRow] = []
    for ti, tarifa in _iter_tarifas(doc):
        esq = _esquema(tarifa)
        if esq.get("tipo_esquema") != "otro_no_clasificado":
            continue
        cat = esq.get("categoria", "?")
        desc = (esq.get("descripcion_estructural") or "")[:80]
        amb = tarifa.get("ambito", "")
        out.append(_make_row(
            "otro_no_clasificado", "SEV1",
            (f"Tarifa #{ti} ({amb}): el LLM no pudo clasificar el esquema "
             f"(categoría: {cat}). Descripción: \"{desc}\""),
            estado_slug, municipio_slug, anio, json_path, **kw,
        ))
    return out


# ══════════════════════════════════════════════════════════════
# D6 — progresivo_tasa_cero (SEV1)
# ══════════════════════════════════════════════════════════════

def det_progresivo_tasa_cero(
    doc: dict, estado_slug: str, municipio_slug: str, anio: int,
    json_path: str, **kw,
) -> list[QueueRow]:
    """ProgresivoSchema where ALL tasa_marginal == 0.

    Pydantic v3 validator rejects this, but raw JSON from v2-era files
    or from malformed LLM output may bypass validation.
    """
    out: list[QueueRow] = []
    for ti, tarifa in _iter_tarifas(doc):
        esq = _esquema(tarifa)
        if esq.get("tipo_esquema") != "progresivo":
            continue
        all_rows = [
            r for b in (esq.get("bloques") or [])
            for r in (b.get("tabla") or [])
        ]
        if not all_rows:
            continue
        if all(float(r.get("tasa_marginal", 1)) == 0 for r in all_rows):
            amb = tarifa.get("ambito", "")
            out.append(_make_row(
                "progresivo_tasa_cero", "SEV1",
                (f"Tarifa #{ti} ({amb}): esquema progresivo con {len(all_rows)} rangos "
                 f"pero TODAS las tasas marginales son 0 — "
                 f"probable cuota fija escalonada mal clasificada"),
                estado_slug, municipio_slug, anio, json_path, **kw,
            ))
    return out


# ══════════════════════════════════════════════════════════════
# D7 — bracket_superior_cerrado (SEV2)
# ══════════════════════════════════════════════════════════════

def det_bracket_superior_cerrado(
    doc: dict, estado_slug: str, municipio_slug: str, anio: int,
    json_path: str, **kw,
) -> list[QueueRow]:
    """Last bracket of progresivo/escalonada/mixto should have superior=None."""
    out: list[QueueRow] = []
    for ti, tarifa in _iter_tarifas(doc):
        esq = _esquema(tarifa)
        tipo = esq.get("tipo_esquema")
        tables: list[list[dict]] = []
        if tipo == "progresivo":
            tables = [b.get("tabla") or [] for b in (esq.get("bloques") or [])]
        elif tipo in ("cuota_fija_escalonada", "mixto"):
            tables = [esq.get("tabla") or []]
        for tabla in tables:
            if len(tabla) < 2:
                continue
            last = tabla[-1]
            if last.get("superior") is not None:
                amb = tarifa.get("ambito", "")
                out.append(_make_row(
                    "bracket_superior_cerrado", "SEV2",
                    (f"Tarifa #{ti} ({amb}): el último rango de '{tipo}' tiene "
                     f"límite superior cerrado ({last['superior']}) — "
                     f"debería ser abierto (None/\"en adelante\")"),
                    estado_slug, municipio_slug, anio, json_path, **kw,
                ))
                break
    return out


# ══════════════════════════════════════════════════════════════
# D8 — rangos_no_monotonos (SEV2)
# ══════════════════════════════════════════════════════════════

def det_rangos_no_monotonos(
    doc: dict, estado_slug: str, municipio_slug: str, anio: int,
    json_path: str, **kw,
) -> list[QueueRow]:
    out: list[QueueRow] = []
    for ti, tarifa in _iter_tarifas(doc):
        esq = _esquema(tarifa)
        tipo = esq.get("tipo_esquema")

        if tipo == "progresivo":
            for b in (esq.get("bloques") or []):
                tabla = b.get("tabla") or []
                sig = _check_monotonia_cuota(tabla, "cuota_fija")
                if sig:
                    cat = b.get("categoria", "?")
                    out.append(_make_row(
                        "rangos_no_monotonos", "SEV2",
                        f"tarifa[{ti}] progresivo/{cat}: {sig}",
                        estado_slug, municipio_slug, anio, json_path, **kw,
                    ))

        elif tipo == "mixto":
            tabla = esq.get("tabla") or []
            sig = _check_monotonia_mixto(tabla)
            if sig:
                out.append(_make_row(
                    "rangos_no_monotonos", "SEV2",
                    f"tarifa[{ti}] mixto: {sig}",
                    estado_slug, municipio_slug, anio, json_path, **kw,
                ))

        elif tipo == "cuota_fija_escalonada":
            tabla = esq.get("tabla") or []
            sig = _check_monotonia_cuota(tabla, "monto")
            if sig:
                out.append(_make_row(
                    "rangos_no_monotonos", "SEV2",
                    f"tarifa[{ti}] cuota_fija_escalonada: {sig}",
                    estado_slug, municipio_slug, anio, json_path, **kw,
                ))
    return out


def _check_monotonia_cuota(tabla: list[dict], field: str) -> str | None:
    if len(tabla) < 2:
        return None
    vals = [float(r.get(field) or 0) for r in tabla]
    for i in range(len(vals) - 1):
        if vals[i + 1] < vals[i] - 0.01:
            return f"{field} {vals[i]}→{vals[i+1]} (rango {i+1}→{i+2})"
    return None


def _check_monotonia_mixto(tabla: list[dict]) -> str | None:
    if len(tabla) < 2:
        return None
    from collections import defaultdict
    by_col: dict[str, list[float]] = defaultdict(list)
    for row in tabla:
        for c in (row.get("columnas") or []):
            if c.get("tipo") == "cuota_fija":
                by_col[c.get("nombre", "?")].append(float(c.get("valor") or 0))
    for nombre, vals in by_col.items():
        for i in range(len(vals) - 1):
            if vals[i + 1] < vals[i] - 0.01:
                return f"col '{nombre}': {vals[i]}→{vals[i+1]}"
    return None


# ══════════════════════════════════════════════════════════════
# D9 — tarifa_millar_factor (SEV2)
# ══════════════════════════════════════════════════════════════

def det_tarifa_millar_factor(
    doc: dict, estado_slug: str, municipio_slug: str, anio: int,
    json_path: str, **kw,
) -> list[QueueRow]:
    """tarifa_millar where max(tasa) < 0.5 — likely expressed as factor, not millar."""
    out: list[QueueRow] = []
    for ti, tarifa in _iter_tarifas(doc):
        esq = _esquema(tarifa)
        if esq.get("tipo_esquema") != "tarifa_millar":
            continue
        tasas = [
            float(r.get("tasa_millar") or 0)
            for r in (esq.get("tabla") or [])
            if r.get("tasa_millar")
        ]
        if tasas and max(tasas) < 0.5:
            amb = tarifa.get("ambito", "")
            out.append(_make_row(
                "tarifa_millar_factor", "SEV2",
                (f"Tarifa #{ti} ({amb}): tarifa al millar con tasa máxima "
                 f"{max(tasas):.4f} — sospechosamente baja, "
                 f"posible confusión de unidad (¿es factor decimal?)"),
                estado_slug, municipio_slug, anio, json_path, **kw,
            ))
    return out


# ══════════════════════════════════════════════════════════════
# D10 — tasa_unica_unidad_factor (SEV2)
# ══════════════════════════════════════════════════════════════

def det_tasa_unica_unidad_factor(
    doc: dict, estado_slug: str, municipio_slug: str, anio: int,
    json_path: str, **kw,
) -> list[QueueRow]:
    out: list[QueueRow] = []
    for ti, tarifa in _iter_tarifas(doc):
        esq = _esquema(tarifa)
        if esq.get("tipo_esquema") != "tasa_unica":
            continue
        tabla = esq.get("tabla") or []
        if not tabla:
            continue
        r = tabla[0]
        tasa = r.get("tasa")
        unidad = r.get("unidad", "")
        if tasa is None:
            continue
        tasa = float(tasa)
        sig = None
        if unidad == "porcentaje" and tasa < 0.05:
            sig = (f"Tarifa #{ti}: tasa única {tasa}% — "
                   f"sospechosamente baja para porcentaje, ¿debería ser al millar?")
        elif unidad == "al_millar" and tasa < 0.5:
            sig = (f"Tarifa #{ti}: tasa única {tasa} al millar — "
                   f"sospechosamente baja, ¿es factor decimal?")
        if sig:
            out.append(_make_row(
                "tasa_unica_unidad_factor", "SEV2",
                sig,
                estado_slug, municipio_slug, anio, json_path, **kw,
            ))
    return out


# ══════════════════════════════════════════════════════════════
# D11 — desc_transitorios (SEV1)
# ══════════════════════════════════════════════════════════════

def det_desc_transitorios(
    doc: dict, estado_slug: str, municipio_slug: str, anio: int,
    json_path: str, **kw,
) -> list[QueueRow]:
    out: list[QueueRow] = []
    for ti, tarifa in _iter_tarifas(doc):
        esq = _esquema(tarifa)
        tipo = esq.get("tipo_esquema", "")
        hits = _scan_desc_transitorios(esq, tipo)
        if hits:
            amb = tarifa.get("ambito", "")
            out.append(_make_row(
                "desc_transitorios", "SEV1",
                (f"Tarifa #{ti} ({amb}): descripción contiene referencia a "
                 f"transitorios/vigencia — posible segmento equivocado. {hits}"),
                estado_slug, municipio_slug, anio, json_path, **kw,
            ))
    return out


def _scan_desc_transitorios(esq: dict, tipo: str) -> str | None:
    rows_to_scan: list[dict] = []
    if tipo == "progresivo":
        for b in (esq.get("bloques") or []):
            rows_to_scan.extend(b.get("tabla") or [])
    elif tipo == "otro_no_clasificado":
        rows_to_scan = esq.get("tabla_cruda") or []
    else:
        rows_to_scan = esq.get("tabla") or []

    for r in rows_to_scan:
        desc = r.get("descripcion", "") or r.get("descripcion_estructural", "") or ""
        m = _RE_TRANSITORIO.search(desc)
        if m:
            return f"hit='{m.group(0)}' en '{desc[:80]}'"
    return None


# ══════════════════════════════════════════════════════════════
# D12 — cambio_interanual (SEV1/2/3)
# ══════════════════════════════════════════════════════════════

_SNAP_TOL = 1.0


def _close(a, b, tol: float = _SNAP_TOL) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    try:
        return abs(float(a) - float(b)) <= tol
    except (TypeError, ValueError):
        return a == b


def _tarifa_key(tarifa: dict) -> tuple[str, str]:
    return (tarifa.get("ambito", "general"), tarifa.get("base_gravable", "valor_catastral"))


def _diff_tarifa_millar_v3(prev_tabla: list, curr_tabla: list) -> tuple[list[str], int]:
    cambios, sev = [], 0
    p_by = {(r.get("grupo"), r.get("clave")): r for r in prev_tabla}
    c_by = {(r.get("grupo"), r.get("clave")): r for r in curr_tabla}
    for k, c in c_by.items():
        if k not in p_by:
            cambios.append(f"nueva fila {k}: tasa={c.get('tasa_millar')}")
            sev = max(sev, 2)
            continue
        p = p_by[k]
        if p.get("tasa_millar") != c.get("tasa_millar"):
            cambios.append(f"{k}: tasa {p.get('tasa_millar')}→{c.get('tasa_millar')}")
            sev = max(sev, 2)
        if p.get("cuota_fija_adicional") != c.get("cuota_fija_adicional"):
            cambios.append(f"{k}: cuota_adic cambió")
            sev = max(sev, 3)
    for k in p_by:
        if k not in c_by:
            cambios.append(f"fila eliminada {k}")
            sev = max(sev, 2)
    return cambios, sev


def _diff_progresivo_bloque(prev_tabla: list, curr_tabla: list) -> tuple[list[str], int]:
    cambios, sev = [], 0
    p_by = {r.get("n_rango"): r for r in prev_tabla}
    c_by = {r.get("n_rango"): r for r in curr_tabla}
    for rng in sorted(set(p_by) | set(c_by), key=lambda x: (x is None, x)):
        if rng not in p_by:
            cambios.append(f"rango {rng} nuevo")
            sev = max(sev, 2)
            continue
        if rng not in c_by:
            cambios.append(f"rango {rng} eliminado")
            sev = max(sev, 2)
            continue
        p, c = p_by[rng], c_by[rng]
        for field, label, s in [("inferior", "inf", 3), ("superior", "sup", 3)]:
            if not _close(p.get(field), c.get(field)):
                cambios.append(f"r{rng}.{label}: {p.get(field)}→{c.get(field)}")
                sev = max(sev, s)
        for field, label, s in [("cuota_fija", "cf", 3), ("tasa_marginal", "tm", 2)]:
            if p.get(field) != c.get(field):
                cambios.append(f"r{rng}.{label}: {p.get(field)}→{c.get(field)}")
                sev = max(sev, s)
    return cambios, sev


def _diff_progresivo_v3(prev_esq: dict, curr_esq: dict) -> tuple[list[str], int]:
    cambios, sev = [], 0
    p_bloques = {b.get("categoria", "general"): b for b in (prev_esq.get("bloques") or [])}
    c_bloques = {b.get("categoria", "general"): b for b in (curr_esq.get("bloques") or [])}
    for cat in sorted(set(p_bloques) | set(c_bloques)):
        if cat not in p_bloques:
            cambios.append(f"bloque '{cat}' nuevo")
            sev = max(sev, 2)
            continue
        if cat not in c_bloques:
            cambios.append(f"bloque '{cat}' eliminado")
            sev = max(sev, 2)
            continue
        c2, s2 = _diff_progresivo_bloque(
            p_bloques[cat].get("tabla") or [],
            c_bloques[cat].get("tabla") or [],
        )
        cambios.extend(f"[{cat}] {x}" for x in c2)
        sev = max(sev, s2)
    return cambios, sev


def _diff_tasa_unica_v3(prev_tabla: list, curr_tabla: list) -> tuple[list[str], int]:
    cambios, sev = [], 0
    if not (prev_tabla and curr_tabla):
        return cambios, sev
    p, c = prev_tabla[0], curr_tabla[0]
    for field, s in [("tasa", 2), ("unidad", 2)]:
        if p.get(field) != c.get(field):
            cambios.append(f"{field}: {p.get(field)}→{c.get(field)}")
            sev = max(sev, s)
    return cambios, sev


def _diff_cuota_fija_simple_v3(prev_tabla: list, curr_tabla: list) -> tuple[list[str], int]:
    cambios, sev = [], 0
    if not (prev_tabla and curr_tabla):
        return cambios, sev
    p, c = prev_tabla[0], curr_tabla[0]
    for field, s in [("monto", 3), ("periodicidad", 2), ("unidad", 2)]:
        if p.get(field) != c.get(field):
            cambios.append(f"{field}: {p.get(field)}→{c.get(field)}")
            sev = max(sev, s)
    return cambios, sev


def _diff_cuota_fija_escalonada_v3(prev_tabla: list, curr_tabla: list) -> tuple[list[str], int]:
    cambios, sev = [], 0
    p_by = {r.get("n_rango"): r for r in prev_tabla}
    c_by = {r.get("n_rango"): r for r in curr_tabla}
    for rng in sorted(set(p_by) | set(c_by), key=lambda x: (x is None, x)):
        if rng not in p_by:
            cambios.append(f"rango {rng} nuevo")
            sev = max(sev, 2)
            continue
        if rng not in c_by:
            cambios.append(f"rango {rng} eliminado")
            sev = max(sev, 2)
            continue
        p, c = p_by[rng], c_by[rng]
        for field, label in [("inferior", "inf"), ("superior", "sup")]:
            if not _close(p.get(field), c.get(field)):
                cambios.append(f"r{rng}.{label}: {p.get(field)}→{c.get(field)}")
                sev = max(sev, 3)
        if p.get("monto") != c.get("monto"):
            cambios.append(f"r{rng}.monto: {p.get('monto')}→{c.get('monto')}")
            sev = max(sev, 3)
    return cambios, sev


def _diff_mixto_v3(prev_tabla: list, curr_tabla: list) -> tuple[list[str], int]:
    cambios, sev = [], 0
    p_by = {r.get("n_rango"): r for r in prev_tabla}
    c_by = {r.get("n_rango"): r for r in curr_tabla}
    for rng in sorted(set(p_by) | set(c_by), key=lambda x: (x is None, x)):
        if rng not in p_by:
            cambios.append(f"rango {rng} nuevo")
            sev = max(sev, 2)
            continue
        if rng not in c_by:
            cambios.append(f"rango {rng} eliminado")
            sev = max(sev, 2)
            continue
        p, c = p_by[rng], c_by[rng]
        if not (_close(p.get("inferior"), c.get("inferior"))
                and _close(p.get("superior"), c.get("superior"))):
            cambios.append(
                f"r{rng} límites: ({p.get('inferior')},{p.get('superior')})→"
                f"({c.get('inferior')},{c.get('superior')})"
            )
            sev = max(sev, 3)
        p_cols = sorted(
            (cc.get("nombre", ""), cc.get("valor"), cc.get("tipo", ""), cc.get("unidad", ""))
            for cc in (p.get("columnas") or [])
        )
        c_cols = sorted(
            (cc.get("nombre", ""), cc.get("valor"), cc.get("tipo", ""), cc.get("unidad", ""))
            for cc in (c.get("columnas") or [])
        )
        if p_cols != c_cols:
            cambios.append(f"r{rng} columnas cambiaron ({len(p_cols)}→{len(c_cols)} celdas)")
            sev = max(sev, 3)
    return cambios, sev


_DIFFERS_V3 = {
    "tarifa_millar": _diff_tarifa_millar_v3,
    "tasa_unica": _diff_tasa_unica_v3,
    "cuota_fija_simple": _diff_cuota_fija_simple_v3,
    "cuota_fija_escalonada": _diff_cuota_fija_escalonada_v3,
    "mixto": _diff_mixto_v3,
}


def _diff_esquema_v3(prev_esq: dict, curr_esq: dict) -> tuple[list[str], int]:
    """Diff two esquema dicts. Returns (changes, max_severity)."""
    cambios: list[str] = []
    sev = 0
    prev_tipo = prev_esq.get("tipo_esquema")
    curr_tipo = curr_esq.get("tipo_esquema")
    if prev_tipo != curr_tipo:
        cambios.append(f"tipo_esquema: {prev_tipo}→{curr_tipo}")
        return cambios, 1

    if prev_tipo == "progresivo":
        return _diff_progresivo_v3(prev_esq, curr_esq)

    prev_tabla = prev_esq.get("tabla") or []
    curr_tabla = curr_esq.get("tabla") or []
    if len(prev_tabla) != len(curr_tabla):
        cambios.append(f"n_filas: {len(prev_tabla)}→{len(curr_tabla)}")
        sev = max(sev, 2)
    differ = _DIFFERS_V3.get(prev_tipo)
    if differ:
        c2, s2 = differ(prev_tabla, curr_tabla)
        cambios.extend(c2)
        sev = max(sev, s2)
    return cambios, sev


def _diff_minimo(prev_min: dict | None, curr_min: dict | None) -> tuple[list[str], int]:
    cambios, sev = [], 0
    p = prev_min or {}
    c = curr_min or {}
    for field, s in [("monto", 3), ("periodicidad", 2), ("unidad", 2)]:
        if p.get(field) != c.get(field):
            cambios.append(f"minimo.{field}: {p.get(field)}→{c.get(field)}")
            sev = max(sev, s)
    return cambios, sev


def _join_cambios(cambios: list[str], max_chars: int = 280) -> str:
    text = "; ".join(cambios)
    return text if len(text) <= max_chars else text[:max_chars - 3] + "..."


_SEV_MAP = {1: "SEV1", 2: "SEV2", 3: "SEV3"}


def det_cambio_interanual(
    series: dict[int, tuple[dict, str]],
    estado_slug: str,
    municipio_slug: str,
    *,
    estado: str = "",
    municipio: str = "",
    cvegeo: str = "",
) -> list[QueueRow]:
    """Compare year-over-year within a municipio's v3 time series.

    Args:
        series: ``{anio: (doc_dict, json_path)}`` for one municipio.
    """
    if len(series) < 2:
        return []

    years = sorted(series.keys())
    out: list[QueueRow] = []

    for i in range(len(years) - 1):
        y_prev, y_curr = years[i], years[i + 1]
        doc_prev, path_prev = series[y_prev]
        doc_curr, path_curr = series[y_curr]

        pred_prev = doc_prev.get("predial") or {}
        pred_curr = doc_curr.get("predial") or {}
        tarifas_prev = pred_prev.get("tarifas") or []
        tarifas_curr = pred_curr.get("tarifas") or []

        all_cambios: list[str] = []
        max_sev = 0

        # Match tarifas by (ambito, base_gravable)
        prev_by_key = {}
        for t in tarifas_prev:
            prev_by_key.setdefault(_tarifa_key(t), []).append(t)
        curr_by_key = {}
        for t in tarifas_curr:
            curr_by_key.setdefault(_tarifa_key(t), []).append(t)

        all_keys = sorted(set(prev_by_key) | set(curr_by_key))
        for key in all_keys:
            p_list = prev_by_key.get(key, [])
            c_list = curr_by_key.get(key, [])
            prefix = f"[{key[0]}/{key[1]}] " if len(all_keys) > 1 else ""

            if not p_list:
                all_cambios.append(f"{prefix}tarifa nueva {key}")
                max_sev = max(max_sev, 1)
                continue
            if not c_list:
                all_cambios.append(f"{prefix}tarifa eliminada {key}")
                max_sev = max(max_sev, 1)
                continue

            # Compare first match (most common: 1 tarifa per key)
            p_esq = _esquema(p_list[0])
            c_esq = _esquema(c_list[0])
            cambios, sev = _diff_esquema_v3(p_esq, c_esq)
            all_cambios.extend(f"{prefix}{x}" for x in cambios)
            max_sev = max(max_sev, sev)

        # Minimo predial general
        c_min, s_min = _diff_minimo(
            pred_prev.get("minimo_predial_general"),
            pred_curr.get("minimo_predial_general"),
        )
        all_cambios.extend(c_min)
        max_sev = max(max_sev, s_min)

        if not all_cambios:
            continue

        sev_label = _SEV_MAP.get(max_sev, f"SEV{max_sev}")
        out.append(QueueRow(
            id=make_id(estado_slug, municipio_slug, y_curr, "cambio_interanual"),
            severidad=sev_label,
            detector="cambio_interanual",
            estado=estado,
            estado_slug=estado_slug,
            municipio=municipio or municipio_slug,
            municipio_slug=municipio_slug,
            cvegeo=cvegeo,
            anio=y_curr,
            senal=_join_cambios(all_cambios),
            json_path=path_curr,
            segment_row=-1,
        ))

    return out


# ══════════════════════════════════════════════════════════════
# Registry
# ══════════════════════════════════════════════════════════════

SEGMENT_DETECTORS = [
    det_frontera_sin_verificar,
    det_distancia_inicio_anomala,
]

JSON_DETECTORS = [
    det_mixto_monocolumna_cuotafija,
    det_tabla_vacia,
    det_otro_no_clasificado,
    det_progresivo_tasa_cero,
    det_bracket_superior_cerrado,
    det_rangos_no_monotonos,
    det_tarifa_millar_factor,
    det_tasa_unica_unidad_factor,
    det_desc_transitorios,
]
