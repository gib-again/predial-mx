"""
Descarga de PDFs del Periódico Oficial de San Luis Potosí.

Flujo:
  1. Para cada ejercicio fiscal N (2010-2025):
     - Buscar en `/api/publicacion/busqueda/filtro/gt` con rango de fechas
       nov-1-(N-1) a feb-28-N y palabra "ley de ingresos" (filtro por título).
     - Unir resultados de todos los grupos `agrupadas.nivel_gob_*_ordinaria_*`.
  2. Filtrar:
     - Excluir "Reforma", "Adición", "Fe de erratas", "Empréstito".
     - Excluir "Ley de Ingresos del Estado" (no municipal).
     - Mantener sólo "Ley de Ingresos del Municipio de X".
  3. Para cada registro válido:
     - Determinar municipio (preferir campo `segundo` en nivel_gob_id=1, fallback a regex sobre título).
     - Determinar ejercicio fiscal del título (no de la fecha de publicación).
     - Resolver municipio canónico vía MuniMatcher contra catálogo INEGI.
  4. Descargar PDF: `/api/publicacion/imprimir/guest/{id}/documento`
     → `data/sanluispotosi/pdf_raw/{ejercicio}/SLP_RAW_{ejercicio}_{slug}.pdf`.
  5. Escribir bitácora `meta/ley_ingresos_index.csv`.
"""

from __future__ import annotations

import csv
import re
import time
from pathlib import Path

import requests

from src.core.muni_matcher import MuniMatcher
from src.estados.sanluispotosi import config


# ═══════════════════════════════════════════════════
# Filtros y parsing de títulos
# ═══════════════════════════════════════════════════

_RE_REJECT = re.compile(
    r"\b(?:"
    r"reforma\w*|adici[oó]n\w*|adiciona\w*|"
    r"deroga\w*|abroga\w*|modifica\w*|"
    r"fe\s+de\s+erratas?|"
    r"empr[eé]stito|"
    r"se\s+(?:adiciona|reforma|deroga|abroga|modifica)"
    r")\b",
    re.IGNORECASE,
)

_RE_LEY_ESTADO = re.compile(
    r"Ley\s+de\s+Ingresos\s+del\s+Estado",
    re.IGNORECASE,
)

# Acepta ambas formas:
#   "Ley de Ingresos del Municipio de X"      (formato histórico)
#   "Ley de Ingresos para el Municipio de X"  (formato 2024+)
_RE_LEY_MUNICIPAL = re.compile(
    r"Ley\s+de\s+[Ii]ngresos\s+(?:del|para\s+el)\s+[Mm]unicipio\s+de\s+",
    re.IGNORECASE,
)

# Captura municipio entre "del/para el Municipio de" y delimitador de fin.
# El delimitador puede ser: coma + SLP, coma + "para el ejercicio", " para el ejercicio".
_RE_MUNICIPIO_TITULO = re.compile(
    r"Ley\s+de\s+[Ii]ngresos\s+(?:del|para\s+el)\s+[Mm]unicipio\s+de\s+"
    r"(?P<muni>.+?)"
    r"(?:\s*,\s*S\.?\s*L\.?\s*P\.?|\s+S\.?\s*L\.?\s*P\.?\s+|\s*,\s*para\s+el\s+|\s+para\s+el\s+)",
    re.IGNORECASE | re.DOTALL,
)

# Captura ejercicio fiscal del título. Tolera typos comunes ("Físcal", "Físacal").
_RE_EJERCICIO_TITULO = re.compile(
    r"[Ee]jercicio\s+\w+\s+(\d{4})",
)

# Captura número de decreto (con tolerancia a "Decreto N" / "DECRETO N" / "Decreto No N").
_RE_DECRETO = re.compile(
    r"Decreto\s+(?:N[oºú\.]*\s*)?(\d{1,5})",
    re.IGNORECASE,
)


def _es_ley_municipal(item: dict) -> bool:
    """Filtra registros para quedarnos sólo con leyes de ingresos municipales completas."""
    titulo = (item.get("titulo") or "").strip()
    if not titulo:
        return False

    if _RE_REJECT.search(titulo):
        return False

    if _RE_LEY_ESTADO.search(titulo):
        return False

    return bool(_RE_LEY_MUNICIPAL.search(titulo))


def _municipio_desde_titulo(titulo: str) -> str | None:
    m = _RE_MUNICIPIO_TITULO.search(titulo or "")
    if not m:
        return None
    raw = m.group("muni")
    # Colapsar saltos de línea y espacios múltiples (la API parte títulos largos en líneas).
    raw = re.sub(r"\s+", " ", raw).strip(" ,.;-")
    return raw or None


def _ejercicio_desde_titulo(titulo: str) -> int | None:
    m = _RE_EJERCICIO_TITULO.search(titulo or "")
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _decreto_desde_titulo(titulo: str) -> str:
    m = _RE_DECRETO.search(titulo or "")
    return m.group(1) if m else ""


# ═══════════════════════════════════════════════════
# Sesión HTTP + búsqueda en API
# ═══════════════════════════════════════════════════

def _get_session() -> requests.Session:
    """Sesión con warm-up para capturar cookies XSRF dinámicamente."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": config.USER_AGENT,
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    })
    # Warm-up: visitar el portal para que el backend setee XSRF-TOKEN y poe_session.
    try:
        session.get(
            f"{config.BASE_URL}/menu/consulta/periodico",
            timeout=30, allow_redirects=True,
        )
    except Exception as e:
        print(f"    [WARN] warm-up falló: {e} (continuando sin cookies pre-cargadas)")

    # Si la cookie XSRF está presente, replicarla en el header (requerido por algunos
    # endpoints Laravel-style detrás de la API).
    xsrf = session.cookies.get("XSRF-TOKEN")
    if xsrf:
        # Las cookies XSRF de Laravel vienen URL-encoded; pasarlas al header tal cual
        # con un decode mínimo (los endpoints aceptan ambos).
        from urllib.parse import unquote
        session.headers["X-XSRF-TOKEN"] = unquote(xsrf)

    return session


def _agrupadas_to_records(data: dict) -> list[dict]:
    """Aplana `agrupadas.nivel_gob_X_ordinaria_Y` a lista única de records."""
    agrupadas = (data or {}).get("agrupadas") or {}
    records: list[dict] = []
    for key, items in agrupadas.items():
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    records.append(it)
    return records


def _buscar_rango(
    session: requests.Session,
    fecha_inicio: str,
    fecha_fin: str,
    palabra: str = config.PALABRA,
) -> list[dict]:
    """Emite GET al endpoint de búsqueda con rango de fechas + palabra clave."""
    params = {
        "fechaInicio": fecha_inicio,
        "fechaFin": fecha_fin,
        "tipo": "disposiciones",
        "tipoPalabra": "titulo",
        "palabra": palabra,
    }
    try:
        r = session.get(config.API_BUSQUEDA, params=params, **config.REQUESTS_KWARGS)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"    [WARN] búsqueda {fecha_inicio}..{fecha_fin}: {e}")
        return []

    return _agrupadas_to_records(data)


# ═══════════════════════════════════════════════════
# Descarga de PDFs
# ═══════════════════════════════════════════════════

def _looks_like_pdf(path: Path) -> bool:
    """Verifica magic bytes %PDF al inicio del archivo (evita guardar HTML 404)."""
    try:
        with path.open("rb") as f:
            head = f.read(4)
        return head == b"%PDF"
    except Exception:
        return False


def _descargar_pdf(
    session: requests.Session,
    id_publicacion: int,
    dest_path: Path,
    max_retries: int = 3,
    endpoints: list[str] | None = None,
) -> tuple[Path, str]:
    """
    Descarga un PDF por id de publicación con cascada de endpoints.

    Si el endpoint principal da 404 (o el archivo descargado no es un PDF
    válido), prueba el siguiente en `config.FALLBACK_PDF_ENDPOINTS`.
    Retorna (ruta, status). Status "ok" incluye el endpoint efectivo:
    "ok" para el principal, "ok:fallback{N}" para los demás.
    """
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return dest_path, "already_exists"

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    endpoints = endpoints or config.FALLBACK_PDF_ENDPOINTS

    last_error = "unknown"

    for ep_idx, ep_template in enumerate(endpoints):
        url = ep_template.format(id=id_publicacion)

        for attempt in range(1, max_retries + 1):
            try:
                resp = session.get(url, timeout=120, stream=True)
                # 404 es señal clara de "siguiente endpoint"; no consumimos retries.
                if resp.status_code == 404:
                    last_error = "404"
                    break
                resp.raise_for_status()
                with dest_path.open("wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)

                # Validar que efectivamente es un PDF (algunos endpoints devuelven
                # HTML de error con status 200).
                if not _looks_like_pdf(dest_path):
                    dest_path.unlink(missing_ok=True)
                    last_error = "invalid_pdf"
                    break

                time.sleep(0.5)  # throttling estándar del proyecto
                tag = "ok" if ep_idx == 0 else f"ok:fallback{ep_idx}"
                return dest_path, tag
            except Exception as e:
                if dest_path.exists():
                    dest_path.unlink(missing_ok=True)
                last_error = f"{type(e).__name__}"
                if attempt < max_retries:
                    time.sleep(1.5 * attempt)
                    continue
                # último retry: pasar al siguiente endpoint
                break

    return dest_path, f"error:{last_error}:all_endpoints"


# ═══════════════════════════════════════════════════
# Pipeline principal
# ═══════════════════════════════════════════════════

_INDEX_FIELDS = [
    "ejercicio", "id_publicacion", "fecha_publicacion", "nivel_gob_id",
    "decreto", "titulo_original", "municipio_raw", "slug", "cve_mun",
    "match_method", "match_score", "pdf_url", "file_local", "status",
    "source",  # po_api (per_year), po_api_wide, congreso, wayback
]


def _read_existing_index(index_csv: Path) -> list[dict]:
    """Carga el índice existente para mergear con corridas previas."""
    if not index_csv.exists():
        return []
    rows: list[dict] = []
    with index_csv.open(encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            # Back-compat: filas previas sin columna 'source' se taggean como 'po_api'.
            r.setdefault("source", "po_api")
            rows.append(r)
    return rows


def _key_id(row: dict) -> str:
    return f"{row.get('id_publicacion','')}"


def _key_year_slug(row: dict) -> str:
    return f"{row.get('ejercicio','')}|{row.get('slug','')}"


def _process_records(
    session: requests.Session,
    records_by_year: dict[int, list[dict]],
    pdf_raw_dir: Path,
    matcher: MuniMatcher,
    source_tag: str,
    descargados_ids: set[int],
    existentes_year_slug: set[str],
) -> tuple[list[dict], dict[int, int]]:
    """
    Procesa registros agrupados por ejercicio fiscal: descarga PDFs faltantes
    y construye filas para el índice. Retorna (rows_nuevos, contadores).

    `descargados_ids` y `existentes_year_slug` se mutan in-place para evitar
    re-descargar lo que ya está en disco o ya se procesó en esta corrida.
    """
    rows: list[dict] = []
    contadores: dict[int, int] = {}

    for ej in sorted(records_by_year.keys()):
        ley_anio = records_by_year[ej]
        contadores[ej] = len(ley_anio)
        if not ley_anio:
            continue

        print(f"  [{ej}] {len(ley_anio)} leyes municipales (source={source_tag})")

        for record in ley_anio:
            id_pub = record.get("id")
            if id_pub is None:
                continue

            titulo = (record.get("titulo") or "").strip()
            fecha = (record.get("fecha_publicacion") or "").strip()
            nivel_gob = record.get("nivel_gob_id")
            segundo = (record.get("segundo") or "").strip()

            # Determinar municipio: preferir `segundo` si nivel_gob_id=1 (Municipal),
            # caer a regex sobre título.
            muni_raw = ""
            if nivel_gob == 1 and segundo and "PODER" not in segundo.upper():
                muni_raw = segundo
            else:
                from_title = _municipio_desde_titulo(titulo)
                if from_title:
                    muni_raw = from_title

            if not muni_raw:
                rows.append({
                    "ejercicio": ej,
                    "id_publicacion": id_pub,
                    "fecha_publicacion": fecha,
                    "nivel_gob_id": nivel_gob or "",
                    "decreto": _decreto_desde_titulo(titulo),
                    "titulo_original": titulo,
                    "municipio_raw": "",
                    "slug": "",
                    "cve_mun": "",
                    "match_method": "no_municipio",
                    "match_score": 0,
                    "pdf_url": config.API_DOC.format(id=id_pub),
                    "file_local": "",
                    "status": "skipped:no_municipio",
                    "source": source_tag,
                })
                continue

            mr = matcher.match(muni_raw)
            slug = mr.slug
            year_slug = f"{ej}|{slug}"

            file_local = (
                pdf_raw_dir / str(ej) / f"{config.PREFIJO}_RAW_{ej}_{slug}.pdf"
            )

            # Idempotencia: si ya tenemos PDF (en disco o registrado en otra fuente),
            # sólo registrar en bitácora.
            if year_slug in existentes_year_slug or (
                file_local.exists() and file_local.stat().st_size > 1024
            ):
                existentes_year_slug.add(year_slug)
                status = "already_exists"
            elif id_pub in descargados_ids:
                status = "already_logged"
            else:
                _, status = _descargar_pdf(session, int(id_pub), file_local)
                if status.startswith("ok"):
                    print(f"    Descargado [{status}]: {file_local.name}")
                    existentes_year_slug.add(year_slug)
                elif status == "already_exists":
                    existentes_year_slug.add(year_slug)
                else:
                    print(f"    [ERROR] id={id_pub} {slug}: {status}")
                descargados_ids.add(int(id_pub))

            rows.append({
                "ejercicio": ej,
                "id_publicacion": id_pub,
                "fecha_publicacion": fecha,
                "nivel_gob_id": nivel_gob or "",
                "decreto": _decreto_desde_titulo(titulo),
                "titulo_original": titulo,
                "municipio_raw": muni_raw,
                "slug": slug,
                "cve_mun": mr.cve_mun,
                "match_method": mr.method,
                "match_score": round(mr.score, 3),
                "pdf_url": config.API_DOC.format(id=id_pub),
                "file_local": str(file_local),
                "status": status,
                "source": source_tag,
            })

    return rows, contadores


_RE_FECHA_YMD = re.compile(r"^(\d{4})-(\d{2})-(\d{2})")


def _ejercicio_desde_fecha(fecha_publicacion: str) -> int | None:
    """
    Deriva fiscal_year de la fecha de publicación cuando el título está truncado.

    Heurística:
      - Publicado nov-dic de año Y    → fiscal_year = Y + 1
      - Publicado ene-jun de año Y    → fiscal_year = Y
      - Publicado jul-oct (atípico)   → ambiguo, asumir Y + 1 (suponer "publicación
        anticipada"). Casos raros; sólo aplica como último recurso.
    """
    if not fecha_publicacion:
        return None
    m = _RE_FECHA_YMD.match(fecha_publicacion.strip())
    if not m:
        return None
    try:
        y = int(m.group(1))
        mo = int(m.group(2))
    except ValueError:
        return None
    if mo >= 11:
        return y + 1
    if mo <= 6:
        return y
    # jul-oct: ambiguo
    return y + 1


def _agrupar_por_ejercicio(records: list[dict]) -> dict[int, list[dict]]:
    """
    Agrupa registros municipales por ejercicio fiscal.

    Fuente primaria del año fiscal: regex sobre el título.
    Fallback: derivado de `fecha_publicacion` (la API trunca títulos largos
    y el año puede quedar recortado).
    """
    grouped: dict[int, list[dict]] = {}
    for r in records:
        if not _es_ley_municipal(r):
            continue
        anio = _ejercicio_desde_titulo(r.get("titulo") or "")
        if anio is None:
            anio = _ejercicio_desde_fecha(r.get("fecha_publicacion") or "")
        if anio is None:
            continue
        if anio < config.YEAR_MIN or anio > config.YEAR_MAX:
            continue
        grouped.setdefault(anio, []).append(r)
    return grouped


def run_download(adapter, mode: str = "per_year") -> Path:
    """
    Busca en la API del PO, descarga PDFs municipales y actualiza CSV índice.

    Args:
        adapter: Adaptador SLP.
        mode:
          - "per_year": query por año con ventana corta (legacy, default).
          - "wide": una sola query histórica con rango 1857-2026 + filtro por
            fiscal year del título. Recupera registros que la búsqueda
            estrecha pierde (especialmente 2012-2013-2016-2021).

    Idempotente: lee el índice previo y sólo descarga lo que falta. Mergea
    nuevas filas con las existentes (preservando back-compat sin columna source).
    """
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    pdf_raw_dir.mkdir(parents=True, exist_ok=True)

    index_csv = meta_dir / "ley_ingresos_index.csv"
    matcher = MuniMatcher(cve_ent=config.CVE_ENT, aliases=config.ALIASES)

    print(f"═══ San Luis Potosí: Descarga PO (mode={mode}) ═══")
    print(f"    Ejercicios: {config.YEAR_MIN}-{config.YEAR_MAX}")

    # Cargar índice previo para idempotencia y para detectar (año, slug) ya cubiertos
    # por otras fuentes (Congreso, Wayback) en corridas anteriores.
    existing_rows = _read_existing_index(index_csv)
    existentes_year_slug: set[str] = set()
    for r in existing_rows:
        if r.get("status") in ("ok", "already_exists", "already_logged") or \
           (r.get("status", "").startswith("ok:")):
            slug = r.get("slug", "")
            ej = r.get("ejercicio", "")
            if slug and ej:
                existentes_year_slug.add(f"{ej}|{slug}")

    session = _get_session()
    descargados_ids: set[int] = set()

    # ── Recolectar records según mode ──
    records_by_year: dict[int, list[dict]] = {}
    source_tag = "po_api" if mode == "per_year" else "po_api_wide"

    if mode == "wide":
        print(f"  Consulta única: {config.WIDE_FECHA_INICIO}..{config.WIDE_FECHA_FIN}, palabra='{config.PALABRA}'")
        all_records = _buscar_rango(
            session,
            config.WIDE_FECHA_INICIO,
            config.WIDE_FECHA_FIN,
            palabra=config.PALABRA,
        )
        print(f"  Records crudos en respuesta: {len(all_records)}")
        records_by_year = _agrupar_por_ejercicio(all_records)
        n_total = sum(len(v) for v in records_by_year.values())
        print(f"  Records municipales válidos (con fiscal year reconocido): {n_total}")

    else:  # per_year (legacy)
        for ejercicio in range(config.YEAR_MIN, config.YEAR_MAX + 1):
            fecha_inicio = f"{ejercicio - 1}-01-01"
            fecha_fin = f"{ejercicio}-06-30"
            records = _buscar_rango(session, fecha_inicio, fecha_fin)
            municipales = [r for r in records if _es_ley_municipal(r)]
            ley_anio: list[dict] = []
            for r in municipales:
                anio_titulo = _ejercicio_desde_titulo(r.get("titulo") or "")
                if anio_titulo == ejercicio or anio_titulo is None:
                    ley_anio.append(r)
            records_by_year[ejercicio] = ley_anio

    # ── Procesar y descargar ──
    new_rows, contadores = _process_records(
        session=session,
        records_by_year=records_by_year,
        pdf_raw_dir=pdf_raw_dir,
        matcher=matcher,
        source_tag=source_tag,
        descargados_ids=descargados_ids,
        existentes_year_slug=existentes_year_slug,
    )

    # ── Mergear con índice previo ──
    # Estrategia: preservamos filas previas; las nuevas con (id_publicacion, source)
    # idéntico sustituyen a versiones viejas. Esto permite re-correr y actualizar
    # statuses sin perder histórico de otras fuentes.
    seen: set[tuple[str, str]] = set()
    merged: list[dict] = []
    for r in new_rows:
        key = (str(r.get("id_publicacion", "")), r.get("source", ""))
        merged.append(r)
        seen.add(key)
    for r in existing_rows:
        key = (str(r.get("id_publicacion", "")), r.get("source", "po_api"))
        if key not in seen:
            # Asegurar columna source (back-compat)
            r.setdefault("source", "po_api")
            merged.append(r)

    # Escribir CSV (atómico)
    tmp = index_csv.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(merged)
    tmp.replace(index_csv)

    print("\n  ── Resumen descarga ──")
    for ej in sorted(contadores):
        print(f"  {ej}: {contadores[ej]} leyes ({source_tag})")
    n_ok = sum(1 for r in new_rows if r["status"] in ("ok", "already_exists") or r["status"].startswith("ok:"))
    n_skip = sum(1 for r in new_rows if r["status"].startswith("skipped"))
    n_err = sum(1 for r in new_rows if r["status"].startswith("error"))
    print(f"  Filas nuevas: {len(new_rows)} (ok/cached={n_ok}, skip={n_skip}, err={n_err})")
    print(f"  Filas totales en índice: {len(merged)}")
    print(f"  Índice: {index_csv}")
    return index_csv
