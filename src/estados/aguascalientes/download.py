"""
Descarga de PDFs del Periodico Oficial de Aguascalientes.

API JSON (ASP.NET WebMethod):
  - Busqueda: Default.aspx/obtenerInformacion  (POST, JSON)
  - Detalle:  Default.aspx/obtenerDetalle       (POST, JSON)
  - PDF:      Archivos/{IdPeriodico}.pdf

Particularidad Aguascalientes:
  - Cada seccion del PO es un PDF separado = una ley de ingresos municipal.
  - Se publican como EXTRAORDINARIO cerca de dic 27-31 del anio anterior
    al ejercicio fiscal (ej. dic 2023 contiene FY 2024).
  - 11 municipios → ~11 PDFs por ejercicio fiscal.
  - La API de busqueda tiene un limite de 500 resultados sin paginacion
    funcional. Se busca por nombre de municipio para obtener todos los anios.

Archivos generados:
  data/aguascalientes/pdf_raw/{ejercicio}/{AGS_RAW_{ejercicio}_{slug}.pdf
  data/aguascalientes/meta/catalogo_leyes.csv
"""

from __future__ import annotations

import csv
import json
import re
import time
from pathlib import Path

import requests

from src.estados.aguascalientes import config


# ===================================================
# API helpers
# ===================================================

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": config.USER_AGENT,
        "Content-Type": "application/json; charset=utf-8",
    })
    return s


def _search(session: requests.Session, nombre_doc: str) -> list[dict]:
    """Busca documentos por NombreDocumento en la API del PO."""
    payload = {
        "fipub": "", "ffpub": "",
        "actualIndice": None,
        "IdOrdenGobierno": "", "IdDependencia": "", "numero": "",
        "IdEdicion": "", "IdTipoPublicacion": "",
        "NombreDocumento": nombre_doc,
        "IdTomo": "", "IdSeccion": "", "Contenido": "",
        "indiceActual": 1,
    }
    try:
        r = session.post(config.SEARCH_URL, json=payload, **config.REQUESTS_KWARGS)
        r.raise_for_status()
        data = r.json()
        raw = data.get("d", "")
        return json.loads(raw) if raw else []
    except Exception as e:
        print(f"    [WARN] API search error for '{nombre_doc}': {e}")
        return []


def _get_detail(session: requests.Session, id_periodico: int) -> list[dict]:
    """Obtiene los documentos dentro de un numero del PO."""
    payload = {
        "id": id_periodico,
        "fipub": "", "ffpub": "",
        "actualIndice": None,
        "IdOrdenGobierno": "", "IdDependencia": "", "numero": "",
        "IdEdicion": "", "IdTipoPublicacion": "",
        "NombreDocumento": "",
        "IdTomo": "", "IdSeccion": "", "Contenido": "",
    }
    try:
        r = session.post(config.DETAIL_URL, json=payload, **config.REQUESTS_KWARGS)
        r.raise_for_status()
        data = r.json()
        raw = data.get("d", "")
        return json.loads(raw) if raw else []
    except Exception as e:
        print(f"    [WARN] API detail error for id={id_periodico}: {e}")
        return []


# ===================================================
# Filtros
# ===================================================

_RE_EJERCICIO = re.compile(
    r"EJERCICIO\s+FISCAL\s+(?:DEL\s+A[ÑN]O\s+)?(\d{4})",
    re.IGNORECASE,
)

_RE_MUNICIPIO = re.compile(
    r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+"
    r"([\w\sÁÉÍÓÚÑÜáéíóúñü]+?)"
    r"(?:,\s*AGUASCALIENTES|,\s*AGS|,?\s*PARA\s+EL\s+EJERCICIO)",
    re.IGNORECASE,
)


def _extract_ejercicio(nombre_doc: str) -> int | None:
    m = _RE_EJERCICIO.search(nombre_doc)
    if m:
        return int(m.group(1))
    return None


def _extract_municipio(nombre_doc: str) -> str | None:
    m = _RE_MUNICIPIO.search(nombre_doc)
    if m:
        raw = m.group(1).strip().rstrip(",").strip()
        return config.NOMBRE_PO.get(raw.upper())
    return None


def _is_ley_ingresos_municipal(nombre_doc: str) -> bool:
    """True si el documento es una Ley de Ingresos municipal (no estatal ni reforma)."""
    upper = nombre_doc.upper()
    if "LEY DE INGRESOS DEL MUNICIPIO" not in upper:
        return False
    if "LEY DE INGRESOS DEL ESTADO" in upper:
        return False
    if "REFORMA" in upper or "FE DE ERRATA" in upper:
        return False
    if "EMPRÉSTITO" in upper or "EMPRESTITO" in upper:
        return False
    if "PRESUPUESTO DE EGRESOS" in upper:
        return False
    # Derivative documents that reference the Ley de Ingresos but aren't the law itself
    if re.match(r"REGLAS\s+DE\s+CAR", upper):
        return False
    if re.match(r"BASES\s+GENERALES", upper):
        return False
    if re.match(r"DISPOSICI", upper):
        return False
    if re.match(r"INFORME\b", upper):
        return False
    if re.match(r"AVISO\b", upper):
        return False
    return True


# ===================================================
# Descarga
# ===================================================

def _download_pdf(
    session: requests.Session,
    id_periodico: int,
    ejercicio: int,
    slug: str,
    pdf_raw_dir: Path,
) -> tuple[Path, str]:
    carpeta = pdf_raw_dir / str(ejercicio)
    carpeta.mkdir(parents=True, exist_ok=True)

    nombre = f"{config.PREFIJO}_RAW_{ejercicio}_{slug}.pdf"
    ruta = carpeta / nombre

    if ruta.exists():
        return ruta, "already_exists"

    url = f"{config.PDF_URL}/{id_periodico}.pdf"
    try:
        resp = session.get(url, timeout=120, stream=True)
        resp.raise_for_status()
        with ruta.open("wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                f.write(chunk)
        time.sleep(0.5)
        return ruta, "ok"
    except Exception as e:
        if ruta.exists():
            ruta.unlink()
        return ruta, f"error:{type(e).__name__}"


# ===================================================
# Pipeline principal
# ===================================================

def run_download(adapter) -> Path:
    """
    Busca leyes de ingresos municipales via API, descarga PDFs, genera catalogo.

    Estrategia: buscar por nombre de cada municipio (11 busquedas) para evitar
    el limite de 500 resultados de la API. Luego obtener detalle de cada
    resultado para confirmar municipio y ejercicio fiscal.

    Returns:
        Path al CSV catalogo generado.
    """
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    pdf_raw_dir.mkdir(parents=True, exist_ok=True)

    catalogo_csv = meta_dir / "catalogo_leyes.csv"
    session = _session()
    catalogo_rows: list[dict] = []
    descargados: set[int] = set()

    print(f"=== Aguascalientes: Descarga de PDFs del PO ===")
    print(f"    Ejercicios: {config.YEAR_MIN}-{config.YEAR_MAX}")

    for search_name, muni_slug in config.SEARCH_NAMES:
        query = f"Ley de Ingresos del Municipio de {search_name}"
        items = _search(session, query)
        if not items:
            print(f"  [{search_name}] sin resultados")
            continue

        # Filtrar rango de fechas relevante (dic year-1 a ene year, para FY year)
        relevant = []
        for item in items:
            fecha = item.get("FechaPublicacion", "")[:10]
            try:
                pub_year = int(fecha[:4])
            except (ValueError, IndexError):
                continue
            # La publicacion en dic YYYY es para FY YYYY+1
            # La publicacion en ene YYYY es para FY YYYY
            if pub_year < config.YEAR_MIN - 1 or pub_year > config.YEAR_MAX:
                continue
            relevant.append(item)

        print(f"  [{search_name}] {len(items)} total, {len(relevant)} en rango")

        for item in relevant:
            idp = item["IdPeriodico"]
            fecha = item.get("FechaPublicacion", "")[:10]

            # Obtener detalle para confirmar nombre del documento
            details = _get_detail(session, idp)
            time.sleep(0.3)

            for doc in details:
                nombre_doc = doc.get("NombreDocumento", "")
                if not _is_ley_ingresos_municipal(nombre_doc):
                    continue

                ejercicio = _extract_ejercicio(nombre_doc)
                muni_from_doc = _extract_municipio(nombre_doc)

                if not ejercicio:
                    continue
                if ejercicio < config.YEAR_MIN or ejercicio > config.YEAR_MAX:
                    continue

                slug = muni_from_doc or muni_slug
                pagina = doc.get("Pagina", "")

                catalogo_rows.append({
                    "ejercicio": ejercicio,
                    "IdPeriodico": idp,
                    "municipio": search_name,
                    "slug": slug,
                    "fecha_publicacion": fecha,
                    "nombre_documento": nombre_doc,
                    "pagina": pagina,
                    "seccion": item.get("Seccion", ""),
                    "edicion": item.get("Edicion", ""),
                })

                if idp not in descargados:
                    ruta, status = _download_pdf(
                        session, idp, ejercicio, slug, pdf_raw_dir,
                    )
                    if status == "ok":
                        print(f"    Descargado: {ruta.name}")
                    elif status.startswith("error"):
                        print(f"    ERROR id={idp}: {status}")
                    descargados.add(idp)

    # Guardar catalogo
    fieldnames = [
        "ejercicio", "IdPeriodico", "municipio", "slug",
        "fecha_publicacion", "nombre_documento", "pagina",
        "seccion", "edicion",
    ]
    with catalogo_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(catalogo_rows)

    n_pdfs = len(descargados)
    n_rows = len(catalogo_rows)
    print(f"\n  Catalogo: {catalogo_csv} ({n_rows} registros, {n_pdfs} PDFs unicos)")
    return catalogo_csv
