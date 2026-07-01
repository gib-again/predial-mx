"""
Descarga de las Leyes de Ingresos Municipales de Durango (Congreso del Estado).

Por cada anio (2018-2025) se raspa la pagina de dictamenes
(/dictamenes-de-leyes-de-ingresos-{anio}/), se extraen los PDFs municipales del
folder LEYES[-]INGRESOS de ese anio, se mapea cada archivo a su municipio
canonico y se descarga. PDFs digitales (sin OCR).

Archivos: data/durango/pdf_raw/{anio}/DGO_RAW_{anio}_{slug}.pdf
          data/durango/meta/catalogo_leyes.csv
"""

from __future__ import annotations

import csv
import re
import subprocess
import unicodedata
from pathlib import Path

from src.estados.durango import config

UA = config.USER_AGENT


def _decode_escapes(s: str) -> str:
    """Decodifica los escapes raros del indice Apache: '%23U00d1'/'#U00d1' -> 'Ñ'."""
    return re.sub(r"(?:%23|#)U00([0-9a-fA-F]{2})",
                  lambda m: chr(int(m.group(1), 16)), s)


def _norm(s: str) -> str:
    """Normaliza: sin acentos, solo letras minusculas (quita ext, anio, espacios)."""
    s = _decode_escapes(s)
    s = re.sub(r"\.[A-Za-z]+$", "", s)   # quita extension (.pdf/.PDF)
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if unicodedata.category(c) != "Mn")
    s = re.sub(r"\d+", "", s)            # quita digitos (anio)
    s = re.sub(r"[^A-Za-z]", "", s)      # solo letras
    return s.lower()


# Slug normalizado (sin underscores) -> slug, para match directo.
_NORM_SLUG = {slug.replace("_", ""): slug for _c, _n, slug in config.MUNICIPIOS}
_NORM_NAME = {_norm(name): slug for _c, name, slug in config.MUNICIPIOS}


# Slugs ordenados por longitud desc para el match por substring (el mas largo
# gana: evita que "gomez" matchee antes que "gomezpalacio", etc.).
_NORM_SLUG_BYLEN = sorted(_NORM_SLUG.items(), key=lambda kv: -len(kv[0]))

# Prefijos de ruido (anclados al inicio) en los nombres del Congreso, p.ej.
# "DICTAMENLEYDEINGRESOS{MUNI}OK" / "LEY DE INGRESOS {MUNI}". Ordenados por
# longitud desc para quitar el mas largo. NO se quita "de"/"del" global (mutila
# nombres cortos como "inde").
_PREFIJOS_RUIDO = (
    "dictamenleydeingresosdel", "dictamenleydeingresosde", "dictamenleydeingresos",
    "dictamenleyingresosdel", "dictamenleyingresosde", "dictamenleyingresos",
    "leydeingresosdel", "leydeingresosde", "leydeingresos", "leyingresos",
    "dictamen", "municipiode", "municipio",
)


def _match_slug(filename: str) -> str | None:
    """Mapea el nombre de archivo del Congreso a un slug canonico."""
    n = _norm(filename)
    if not n:
        return None
    if n in config.CONGRESO_ALIASES:
        return config.CONGRESO_ALIASES[n]
    if n in _NORM_SLUG:
        return _NORM_SLUG[n]
    if n in _NORM_NAME:
        return _NORM_NAME[n]
    # Quitar prefijo de ruido (anclado) + sufijo (ok/esme/final) y reintentar.
    stripped = n
    for pre in _PREFIJOS_RUIDO:
        if stripped.startswith(pre):
            stripped = stripped[len(pre):]
            break
    stripped = re.sub(r"(?:ok|esme|final|municipio)$", "", stripped)
    if stripped in config.CONGRESO_ALIASES:
        return config.CONGRESO_ALIASES[stripped]
    if stripped in _NORM_SLUG:
        return _NORM_SLUG[stripped]
    if stripped in _NORM_NAME:
        return _NORM_NAME[stripped]
    # Substring: el slug canonico mas largo contenido en el nombre.
    for ns, slug in _NORM_SLUG_BYLEN:
        if len(ns) >= 5 and ns in n:
            return slug
    # Prefijo (respaldo).
    n2 = n[len("municipio"):] if n.startswith("municipio") else n
    for ns, slug in _NORM_SLUG.items():
        if n2 == ns or n2.startswith(ns) or ns.startswith(n2):
            return slug
    return None


# Excluir archivos que no son leyes de ingresos municipales.
_EXCLUIR = re.compile(
    r"EGRESO|ANEXO|ESTADO|ENTIDADES|PARAESTATAL|PAQUETE|CUENTA|INFORME|"
    r"PRESUPUESTO|DICTAMEN\s+LEY\s+DE\s+INGRESOS\s+DEL\s+ESTADO",
    re.I,
)


def _curl_text(url: str) -> str:
    out = subprocess.run(
        ["curl", "-s", "-L", "-k", "-A", UA, "--max-time", "60", url],
        capture_output=True,
    )
    return out.stdout.decode("utf-8", errors="replace")


def _curl_download(url: str, out: Path) -> bool:
    out.parent.mkdir(parents=True, exist_ok=True)
    # El servidor usa espacios en algunas URLs; curl los codifica con --url-query? No.
    url_enc = url.replace(" ", "%20")
    res = subprocess.run(
        ["curl", "-s", "-L", "-k", "-A", UA, "--max-time", "120", url_enc, "-o", str(out)],
        capture_output=True,
    )
    if res.returncode != 0 or not out.exists() or out.stat().st_size < 2000:
        out.unlink(missing_ok=True)
        return False
    with out.open("rb") as f:
        if f.read(5) != b"%PDF-":
            out.unlink(missing_ok=True)
            return False
    return True


def _ley_links(html: str, anio: int) -> list[tuple[str, str]]:
    """(slug, url) de las leyes de ingresos municipales en la pagina del anio."""
    links = re.findall(r'href=["\']([^"\']*LEYES?-?INGRESOS[^"\']*\.pdf)["\']', html, re.I)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href in links:
        fn = re.sub(r"%20", " ", href.split("/")[-1])
        if _EXCLUIR.search(fn):
            continue
        slug = _match_slug(fn)
        if not slug or slug in seen:
            continue
        url = href if href.startswith("http") else config.BASE_CONGRESO + href
        out.append((slug, url))
        seen.add(slug)
    return out


def _index_links(folder: str, anio: int) -> list[tuple[str, str]]:
    """(slug, url) desde el indice Apache de una carpeta de leyes de ingreso."""
    base = f"{config.BASE_CONGRESO}/Archivos/{folder}/".replace(" ", "%20")
    html = _curl_text(base)
    hrefs = re.findall(r'href=["\']([^"\']+\.pdf)["\']', html, re.I)
    out: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href in hrefs:
        fn = re.sub(r"%20", " ", href.split("/")[-1])
        # En el indice Apache los hrefs son relativos (solo el nombre de archivo);
        # los absolutos/globales (nav del sitio) se descartan por ruta.
        if href.startswith("/") or href.startswith("http"):
            continue
        if _EXCLUIR.search(fn):
            continue
        slug = _match_slug(fn)
        if not slug or slug in seen:
            continue
        out.append((slug, base + href))
        seen.add(slug)
    return out


def run_download(adapter, year: str | None = None) -> Path:
    meta_dir = Path("data") / config.ESTADO_SLUG / "meta"
    pdf_raw = Path("data") / config.ESTADO_SLUG / "pdf_raw"
    meta_dir.mkdir(parents=True, exist_ok=True)
    catalogo = meta_dir / "catalogo_leyes.csv"

    print("=== Durango: descarga de Leyes de Ingresos (Congreso) ===")
    rows: list[dict] = []
    years = [int(year)] if year else range(config.YEAR_MIN, config.YEAR_MAX + 1)
    for anio in years:
        if anio in config.FOLDER_POR_ANIO:
            links = _index_links(config.FOLDER_POR_ANIO[anio], anio)
            fuente = "index"
        else:
            links = _ley_links(_curl_text(config.DICTAMENES_URL.format(anio=anio)), anio)
            fuente = "dictamenes"
        print(f"  [{anio}] {len(links)} leyes municipales encontradas ({fuente})")
        for slug, url in links:
            out = pdf_raw / str(anio) / f"{config.PREFIJO}_RAW_{anio}_{slug}.pdf"
            if out.exists() and out.stat().st_size > 2000:
                status = "already_exists"
            else:
                status = "ok" if _curl_download(url, out) else "error"
            if status == "error":
                print(f"    ERROR {slug} {anio}: {url[:80]}")
            rows.append({"anio": anio, "slug": slug, "status": status, "url": url})

    with catalogo.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["anio", "slug", "status", "url"])
        w.writeheader()
        w.writerows(rows)
    n_ok = sum(1 for r in rows if r["status"] in ("ok", "already_exists"))
    print(f"\n  Catalogo: {catalogo} ({len(rows)} registros, {n_ok} PDFs)")
    return catalogo
