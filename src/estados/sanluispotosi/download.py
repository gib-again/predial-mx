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
    r"\b(?:reforma|reformas|adici[oó]n|adiciones|fe\s+de\s+erratas?|"
    r"empr[eé]stito|deroga(?:ci[oó]n)?)\b",
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

def _descargar_pdf(
    session: requests.Session,
    id_publicacion: int,
    dest_path: Path,
    max_retries: int = 3,
) -> tuple[Path, str]:
    """Descarga un PDF por id de publicación. Retorna (ruta, status)."""
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return dest_path, "already_exists"

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    url = config.API_DOC.format(id=id_publicacion)

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(url, timeout=120, stream=True)
            resp.raise_for_status()
            with dest_path.open("wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
            time.sleep(0.5)  # throttling estándar del proyecto
            return dest_path, "ok"
        except Exception as e:
            if dest_path.exists():
                dest_path.unlink(missing_ok=True)
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
                continue
            return dest_path, f"error:{type(e).__name__}"

    return dest_path, "error:max_retries"


# ═══════════════════════════════════════════════════
# Pipeline principal
# ═══════════════════════════════════════════════════

_INDEX_FIELDS = [
    "ejercicio", "id_publicacion", "fecha_publicacion", "nivel_gob_id",
    "decreto", "titulo_original", "municipio_raw", "slug", "cve_mun",
    "match_method", "match_score", "pdf_url", "file_local", "status",
]


def run_download(adapter) -> Path:
    """Busca en la API, descarga PDFs municipales y genera CSV índice."""
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    pdf_raw_dir.mkdir(parents=True, exist_ok=True)

    index_csv = meta_dir / "ley_ingresos_index.csv"
    matcher = MuniMatcher(cve_ent=config.CVE_ENT, aliases=config.ALIASES)

    print("═══ San Luis Potosí: Descarga de PDFs del PO ═══")
    print(f"    Ejercicios: {config.YEAR_MIN}-{config.YEAR_MAX}")

    session = _get_session()
    rows: list[dict] = []
    descargados: set[int] = set()
    contadores: dict[int, int] = {}  # ejercicio → leyes encontradas

    for ejercicio in range(config.YEAR_MIN, config.YEAR_MAX + 1):
        # Ventana amplia: año completo N-1 + primer semestre de N. Esto captura
        # publicaciones tempranas (jul-N-1) y tardías (mar-jun N). El filtro por
        # fiscal year extraído del título asegura que no contaminamos cross-año.
        fecha_inicio = f"{ejercicio - 1}-01-01"
        fecha_fin = f"{ejercicio}-06-30"

        records = _buscar_rango(session, fecha_inicio, fecha_fin)
        municipales = [r for r in records if _es_ley_municipal(r)]

        # Adicional: la búsqueda por rango puede traer leyes con fiscal year != ejercicio
        # (p.ej. fe de erratas filtradas, o publicaciones tardías). Filtramos por título.
        ley_anio: list[tuple[dict, int]] = []
        for r in municipales:
            anio_titulo = _ejercicio_desde_titulo(r.get("titulo") or "")
            if anio_titulo == ejercicio:
                ley_anio.append((r, anio_titulo))
            elif anio_titulo is None:
                # Sin año en título: caso raro; lo aceptamos asumiendo el del rango.
                ley_anio.append((r, ejercicio))

        contadores[ejercicio] = len(ley_anio)
        if not ley_anio:
            print(f"  [{ejercicio}] búsqueda {fecha_inicio}..{fecha_fin}: sin resultados municipales")
            continue

        print(f"  [{ejercicio}] búsqueda {fecha_inicio}..{fecha_fin}: {len(ley_anio)} leyes municipales")

        for record, ej in ley_anio:
            id_pub = record.get("id")
            if id_pub is None:
                continue

            titulo = (record.get("titulo") or "").strip()
            fecha = (record.get("fecha_publicacion") or "").strip()
            nivel_gob = record.get("nivel_gob_id")
            segundo = (record.get("segundo") or "").strip()

            # Determinar municipio: preferir `segundo` si nivel_gob_id=1 (Municipal)
            # ya que viene normalizado en mayúsculas. Si está vacío o es genérico,
            # caer a regex sobre el título.
            muni_raw = ""
            if nivel_gob == 1 and segundo and "PODER" not in segundo.upper():
                muni_raw = segundo
            else:
                from_title = _municipio_desde_titulo(titulo)
                if from_title:
                    muni_raw = from_title

            if not muni_raw:
                # Skip: no se puede asociar a un municipio.
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
                })
                continue

            mr = matcher.match(muni_raw)
            slug = mr.slug

            file_local = (
                pdf_raw_dir / str(ej) / f"{config.PREFIJO}_RAW_{ej}_{slug}.pdf"
            )

            if id_pub in descargados:
                # Mismo PDF ya descargado en otra iteración; sólo registrar en bitácora.
                status = "already_logged"
            else:
                _, status = _descargar_pdf(session, int(id_pub), file_local)
                if status == "ok":
                    print(f"    Descargado: {file_local.name}")
                elif status == "already_exists":
                    pass
                else:
                    print(f"    [ERROR] id={id_pub} {slug}: {status}")
                descargados.add(int(id_pub))

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
            })

    # Escribir CSV índice
    with index_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    print("\n  ── Resumen descarga ──")
    for ej in sorted(contadores):
        print(f"  {ej}: {contadores[ej]} leyes")
    n_ok = sum(1 for r in rows if r["status"] in ("ok", "already_exists"))
    n_skip = sum(1 for r in rows if r["status"].startswith("skipped"))
    n_err = sum(1 for r in rows if r["status"].startswith("error"))
    print(f"  Filas en índice: {len(rows)} (ok/cached={n_ok}, skip={n_skip}, err={n_err})")
    print(f"  Índice: {index_csv}")
    return index_csv
