"""
Descarga de PDFs del Periódico Oficial de Guanajuato.

Migrado de:
  - src/descarga.py        → búsqueda API + descarga PDF
  - src/filtros.py         → es_ley_municipal, extraer_municipio_desde_asunto
  - scripts/01_descargar_leyes.py → orquestación
  - scripts/02_patch_parsing_municipios.py → patch "NO APLICA"

API REST: backperiodico.guanajuato.gob.mx
  - Búsqueda paginada: BuscarEdictoPaginado/{anio}/.../palabra/{pagina}/0
  - Descarga: DescargarPeriodicoId/{idPeriodico}

Particularidad Guanajuato:
  - Las leyes se publican en dic del año anterior O en ene del ejercicio.
    Buscamos en año-1 (publicación dic) Y año (publicación ene).
  - Cada PDF del PO contiene múltiples leyes de ingresos (2-5 mpios).
  - El campo "municipio" de la API a menudo dice "NO APLICA".
    Usamos el texto del "asunto" (decreto) para extraer el nombre real.

Archivos generados:
  data/guanajuato/pdf_raw/{ejercicio}/{anio}_{idPeriodico}_{periodico_slug}.pdf
  data/guanajuato/meta/catalogo_leyes.csv
"""

from __future__ import annotations

import csv
import re
import time
from pathlib import Path

import requests

from src.core.text_utils import slugify
from src.estados.guanajuato import config


# ═══════════════════════════════════════════════════
# Filtros (migrados de src/filtros.py)
# ═══════════════════════════════════════════════════

def _normalizar_texto(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip().upper()


def _es_ley_municipal(item: dict) -> bool:
    """Filtra registros de la API para quedarnos solo con leyes de ingresos municipales."""
    asunto = _normalizar_texto(item.get("asunto", ""))

    # Excluir Ley de Ingresos del Estado
    if "LEY DE INGRESOS PARA EL ESTADO DE GUANAJUATO" in asunto:
        return False

    # Excluir reformas / empréstitos
    if "REFORMA LA" in asunto or "REFORMA LA FRACCI" in asunto:
        return False
    if "SE AUTORIZA AL EJECUTIVO DEL ESTADO" in asunto:
        return False
    if "EMPRESTITO" in asunto or "EMPRÉSTITO" in asunto:
        return False
    
    #Excluir Fe de erratas
    if "FE DE ERRATAS" in asunto:
        return False

    # Incluir leyes municipales
    if "LEY DE INGRESOS PARA EL MUNICIPIO" in asunto:
        return True

    # Fallback (redacciones raras)
    return "LEY DE INGRESOS" in asunto


_RE_MUNICIPIO_ASUNTO = re.compile(
    r"LEY\s+DE\s+INGRESOS\s+PARA\s+EL\s+MUNICIPIO\s+DE\s+(.*?)"
    r"(?:,?\s+GTO\.?|,?\s+GUANAJUATO|,?\s+GTO,|\s+PARA\s+EL\s+EJERCICIO|\.)",
    flags=re.IGNORECASE,
)


def _extraer_municipio_desde_asunto(asunto: str) -> str | None:
    """Extrae nombre del municipio del texto del decreto/asunto."""
    if not asunto:
        return None
    m = _RE_MUNICIPIO_ASUNTO.search(asunto)
    if not m:
        return None
    return m.group(1).strip(" ,") or None


# ═══════════════════════════════════════════════════
# Búsqueda en API
# ═══════════════════════════════════════════════════

def _get_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT})
    return session


def _buscar_leyes_anio(session: requests.Session, anio: int) -> list[dict]:
    """
    Busca leyes de ingreso para un año en la API (con paginación).
    Retorna lista de registros filtrados (solo leyes municipales).
    """
    pagina = 0
    todos: list[dict] = []

    while True:
        url = (
            f"{config.BASE_SEARCH}/{anio}/null/null/null/null/null/null"
            f"/{config.PALABRA}/{pagina}/0"
        )
        try:
            r = session.get(url, **config.REQUESTS_KWARGS)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            print(f"    [WARN] API error año {anio} pág {pagina}: {e}")
            break

        objetos = data.get("objeto", [])
        if not objetos:
            break

        todos.extend(objetos)
        total_paginas = data.get("totalPaginas", 1)

        pagina += 1
        if pagina >= total_paginas:
            break

    # Filtrar solo leyes municipales
    return [item for item in todos if _es_ley_municipal(item)]


# ═══════════════════════════════════════════════════
# Descarga de PDFs
# ═══════════════════════════════════════════════════

def _slug_periodico(nombre: str) -> str:
    """Slug seguro para nombre de periódico (para nombre de archivo)."""
    s = (nombre or "").strip()
    s = re.sub(r"[^\w\s\-.]", "", s)
    s = re.sub(r"\s+", "_", s)
    return s[:80]


def _descargar_pdf(
    session: requests.Session,
    id_periodico: int,
    anio: int,
    nombre_periodico: str,
    pdf_raw_dir: Path,
) -> tuple[Path, str]:
    """Descarga un PDF y retorna (ruta, status)."""
    carpeta_anio = pdf_raw_dir / str(anio)
    carpeta_anio.mkdir(parents=True, exist_ok=True)

    nombre_archivo = f"{anio}_{id_periodico}_{_slug_periodico(nombre_periodico)}.pdf"
    ruta_pdf = carpeta_anio / nombre_archivo

    if ruta_pdf.exists():
        return ruta_pdf, "already_exists"

    url_pdf = f"{config.BASE_DOWNLOAD}/{id_periodico}"
    try:
        resp = session.get(url_pdf, timeout=120, stream=True)
        resp.raise_for_status()
        with ruta_pdf.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        time.sleep(0.3)
        return ruta_pdf, "ok"
    except Exception as e:
        if ruta_pdf.exists():
            ruta_pdf.unlink()
        return ruta_pdf, f"error:{type(e).__name__}"


# ═══════════════════════════════════════════════════
# Pipeline principal
# ═══════════════════════════════════════════════════

def run_download(adapter) -> Path:
    """
    Busca leyes en la API, descarga PDFs, genera catálogo CSV.

    Para cada ejercicio fiscal, busca en año-1 (publicación dic)
    y año (publicación ene), y fusiona resultados.

    Returns:
        Path al CSV catálogo generado.
    """
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    pdf_raw_dir.mkdir(parents=True, exist_ok=True)

    catalogo_csv = meta_dir / "catalogo_leyes.csv"

    session = _get_session()
    catalogo_rows: list[dict] = []
    descargados: set[int] = set()

    print(f"═══ Guanajuato: Descarga de PDFs del PO ═══")
    print(f"    Ejercicios: {config.YEAR_MIN}-{config.YEAR_MAX}")

    for ejercicio in range(config.YEAR_MIN, config.YEAR_MAX + 1):
        # Buscar en año de publicación (dic año-1) y año del ejercicio (ene)
        anios_busqueda = [ejercicio - 1, ejercicio]
        registros_ej: list[dict] = []

        for anio_busq in anios_busqueda:
            items = _buscar_leyes_anio(session, anio_busq)
            if items:
                print(f"  [{ejercicio}] Búsqueda año {anio_busq}: {len(items)} leyes municipales")
            registros_ej.extend(items)

        if not registros_ej:
            print(f"  [{ejercicio}] Sin resultados")
            continue

        for item in registros_ej:
            idp = item["idPeriodico"]
            municipio_api = (item.get("municipio") or "").strip()
            periodico = (item.get("periodico") or "").strip()
            fecha = (item.get("fecha") or "").strip()
            asunto = (item.get("asunto") or "").strip()

            # Extraer municipio del asunto (más confiable que el campo API)
            municipio_from_asunto = _extraer_municipio_desde_asunto(asunto)
            municipio = municipio_from_asunto or municipio_api

            # Patch: si sigue siendo "NO APLICA", dejarlo para revisión manual
            if municipio.upper().strip() == "NO APLICA" and municipio_from_asunto:
                municipio = municipio_from_asunto

            catalogo_rows.append({
                "ejercicio": ejercicio,
                "anio_publicacion": fecha[:4] if fecha else "",
                "idPeriodico": idp,
                "municipio": municipio,
                "municipio_api": municipio_api,
                "periodico": periodico,
                "fecha": fecha,
                "asunto": asunto,
            })

            # Descargar PDF (una sola vez por idPeriodico)
            if idp not in descargados:
                ruta, status = _descargar_pdf(
                    session, idp, ejercicio, periodico, pdf_raw_dir
                )
                if status == "ok":
                    print(f"    Descargado: {ruta.name}")
                elif status.startswith("error"):
                    print(f"    ERROR descargando idP={idp}: {status}")
                descargados.add(idp)

    # Guardar catálogo
    fieldnames = [
        "ejercicio", "anio_publicacion", "idPeriodico", "municipio",
        "municipio_api", "periodico", "fecha", "asunto",
    ]
    with catalogo_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(catalogo_rows)

    n_pdfs = len(descargados)
    n_rows = len(catalogo_rows)
    print(f"\n  Catálogo: {catalogo_csv} ({n_rows} registros, {n_pdfs} PDFs únicos)")
    return catalogo_csv
