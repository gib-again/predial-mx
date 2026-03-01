"""
Descarga de PDFs del Periódico Oficial de Coahuila.

Migrado de: 01_coah_get_ley_ingresos.py

Flujo:
  1. Para cada año de publicación, obtiene el HTML de la tabla de publicaciones
  2. Parsea las filas buscando "ley de ingresos" en el sumario
  3. Descarga los PDFs correspondientes
  4. Genera un CSV índice con metadatos de cada ley encontrada
"""

import csv
import re
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from src.core.text_utils import norm_light, slugify
from src.estados.coahuila.config import (
    BASE_LISTA,
    BASE_ROOT,
    HEADERS,
    ANIO_PUB_INI,
    ANIO_PUB_FIN,
)


def obtener_html_anio(year: int) -> str:
    """Descarga el HTML de publicaciones del PO para un año dado."""
    params = {"Ano": str(year)}
    resp = requests.get(BASE_LISTA, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.text


def parsear_filas_leyes(html: str, year_pub: int, debug_html_dir: Path | None = None):
    """
    Parsea el HTML de la tabla de publicaciones y extrae filas de leyes de ingresos.

    Args:
        html: HTML de la página de publicaciones.
        year_pub: Año de publicación.
        debug_html_dir: Si se proporciona, guarda HTML para debug cuando no hay tabla.

    Returns:
        Lista de dicts con metadatos de cada ley de ingresos encontrada.
    """
    soup = BeautifulSoup(html, "lxml")

    tabla = soup.find("table", id="publicationsTable")
    if not tabla:
        if debug_html_dir:
            debug_html_dir.mkdir(parents=True, exist_ok=True)
            debug_file = debug_html_dir / f"coah_{year_pub}_sin_tabla.html"
            debug_file.write_text(html, encoding="utf-8")
        print(f"  [!] No encontré tabla 'publicationsTable' en {year_pub}")
        return []

    tbody = tabla.find("tbody") or tabla

    filas = []
    for tr in tbody.find_all("tr"):
        clases = tr.get("class") or []
        if "child" in clases:
            continue
        filas.append(tr)

    print(f"  Encontré {len(filas)} filas útiles para {year_pub}")

    registros = []

    for tr in filas:
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        fecha = tds[1].get_text(strip=True)
        tomo = tds[2].get_text(strip=True)
        num_po = tds[3].get_text(strip=True)
        tipo = tds[4].get_text(strip=True)

        # Celda con botones INDICE / PERIODICO
        celda_ver = tds[0]
        enlaces = celda_ver.find_all("a", onclick=True)

        url_pdf = None
        file_name = None

        for a in enlaces:
            onclick = a.get("onclick", "")
            if "verPDFpc.asp" in onclick:
                m = re.search(r"verPDFpc\.asp\?file=([^']+)'", onclick)
                if m:
                    file_name = m.group(1)
                    break

        if file_name:
            url_pdf = f"{BASE_ROOT}/ArchivosPO/{file_name}"

        # Último <td> oculto contiene el sumario completo
        sumario_td = tds[-1]
        parrafos = sumario_td.find_all("p")

        for p in parrafos:
            texto = p.get_text(" ", strip=True)
            norm = norm_light(texto)

            if "ley de ingresos" not in norm:
                continue

            # Identificar municipio o estado
            if "ley de ingresos del municipio de" in norm:
                m_muni = re.search(r"ley de ingresos del municipio de ([^,]+)", norm)
                if m_muni:
                    muni = " ".join(w.capitalize() for w in m_muni.group(1).split())
                else:
                    muni = ""
            elif "ley de ingresos del estado de coahuila" in norm:
                muni = "Coahuila (Estado)"
            else:
                muni = ""

            ejercicio = year_pub + 1  # Leyes publicadas en dic-T aplican al ejercicio T+1

            registros.append({
                "ejercicio": ejercicio,
                "anio_publicacion": year_pub,
                "municipio": muni,
                "tomo": tomo,
                "tipo": tipo,
                "num_po": num_po,
                "fecha_po": fecha,
                "file_name": file_name or "",
                "url_pdf": url_pdf or "",
                "sumario_linea": texto,
            })

    print(f"  -> {len(registros)} leyes de ingresos encontradas para {year_pub}")
    return registros


def descargar_pdf(url_pdf: str, ejercicio: int, muni_slug: str,
                  file_name: str, pdf_raw_dir: Path) -> str:
    """Descarga un PDF si no existe ya localmente."""
    if not url_pdf or not file_name:
        return ""

    dest = pdf_raw_dir / str(ejercicio) / f"COAH_RAW_{ejercicio}_{muni_slug}_{file_name}"
    dest.parent.mkdir(parents=True, exist_ok=True)

    if dest.exists():
        return str(dest)

    print(f"    Descargando {file_name} -> {dest}")
    resp = requests.get(url_pdf, headers=HEADERS, timeout=120)
    resp.raise_for_status()

    with open(dest, "wb") as f:
        for chunk in resp.iter_content(8192):
            if chunk:
                f.write(chunk)

    return str(dest)


# ── Entry point llamado por el adaptador ──

def run_download(adapter) -> Path:
    """
    Ejecuta la descarga completa del PO de Coahuila.

    Args:
        adapter: Instancia del CoahuilaAdapter (para acceder a rutas).

    Returns:
        Path al CSV índice de leyes descargadas.
    """
    pdf_raw_dir = adapter.pdf_raw_dir
    meta_dir = adapter.meta_dir
    out_csv = meta_dir / "ley_ingresos_index.csv"

    pdf_raw_dir.mkdir(parents=True, exist_ok=True)
    meta_dir.mkdir(parents=True, exist_ok=True)

    debug_html_dir = adapter.data_dir / "debug_html"

    todos = []

    for year in range(ANIO_PUB_INI, ANIO_PUB_FIN + 1):
        print(f"  Procesando año de publicación {year}...")
        html = obtener_html_anio(year)
        regs = parsear_filas_leyes(html, year, debug_html_dir=debug_html_dir)

        for r in regs:
            muni_slug = slugify(r["municipio"])
            local_file = descargar_pdf(
                r["url_pdf"], r["ejercicio"], muni_slug,
                r["file_name"], pdf_raw_dir,
            )
            r["file_local"] = local_file
            todos.append(r)

    with out_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "ejercicio", "anio_publicacion", "municipio",
                "tomo", "tipo", "num_po", "fecha_po",
                "file_name", "url_pdf", "file_local", "sumario_linea",
            ],
        )
        writer.writeheader()
        writer.writerows(todos)

    print(f"  Listo. Se guardaron {len(todos)} registros en {out_csv}")
    return out_csv
