"""
Ruta A — Best-effort search en el Congreso del Estado SLP.

Estado de la fuente (verificado en investigación):
  - El Congreso publica leyes ESTATALES vigentes en `/legislacion/leyes` (~30 PDFs).
  - **No hay sección dedicada a Leyes de Ingresos municipales históricas.**
  - Los subdominios de legislaturas pasadas (lviii.*, lix.*, lx.*, lxi.*) tienen
    DNS muerto (NAME_NOT_RESOLVED).
  - "Decretos Expedidos" sólo lista decretos de la legislatura actual.

A pesar de eso, este módulo intenta **rescate best-effort** vía:
  1. Formulario de búsqueda del sitio: `/search/node/{query}`.
     Para cada (muni, año), buscar "ley de ingresos {muni} {año}" y
     descargar cualquier PDF que aparezca en los resultados.
  2. Brute force de patrones URL conocidos (path ya descubierto):
     `/sites/default/files/unpload/legislacion/leyes/{YYYY}/{MM}/...`.
     Probar variantes con nombre del municipio.

Requiere Playwright para bypass del Sucuri Cloud Proxy challenge.

Si el yield termina siendo 0 (esperado dada la investigación previa), el
módulo deja en el log de qa la confirmación documentada de que esos PDFs
NO ESTÁN online en el Congreso. Sirve también como hook si en el futuro
el Congreso publica el archivo histórico.
"""

from __future__ import annotations

import asyncio
import csv
import re
from pathlib import Path

from src.core.muni_matcher import MuniMatcher
from src.estados.sanluispotosi import config
from src.estados.sanluispotosi.download import (
    _INDEX_FIELDS,
    _looks_like_pdf,
    _read_existing_index,
)


def _check_playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


# Slugs canónicos → nombre legible (para query a la búsqueda).
def _slug_a_nombre(slug: str) -> str:
    return slug.replace("_", " ").title()


async def _fetch_pdf_via_browser(
    page,
    pdf_url: str,
    dest_path: Path,
) -> str:
    """Descarga un PDF usando la sesión del browser (cookies Sucuri ya activas)."""
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        # Usamos request del context: hereda cookies del browser.
        resp = await page.context.request.get(pdf_url, timeout=120000)
        if not resp.ok:
            return f"error:congreso_get:{resp.status}"
        body = await resp.body()
        dest_path.write_bytes(body)
        if not _looks_like_pdf(dest_path):
            dest_path.unlink(missing_ok=True)
            return "error:congreso_not_pdf"
        return "ok"
    except Exception as e:
        if dest_path.exists():
            dest_path.unlink(missing_ok=True)
        return f"error:congreso_{type(e).__name__}"


_RE_LEY_MUNI_LINK = re.compile(
    r"ley.*ingresos.*(?:municipio|muni)", re.IGNORECASE | re.DOTALL,
)
_RE_AÑO = re.compile(r"\b(20\d{2})\b")


async def _buscar_muni_anio(
    page,
    muni_nombre: str,
    anio: int,
) -> list[str]:
    """
    Usa el formulario de búsqueda del Congreso para encontrar PDFs candidatos.
    Retorna lista de URLs a PDFs que contienen el patrón "ley...ingresos...municipio".
    """
    query = f"ley de ingresos {muni_nombre} {anio}"
    url = f"{config.BASE_URL_CONGRESO}/search/node/{query.replace(' ', '%20')}"
    try:
        await page.goto(url, wait_until="networkidle", timeout=45000)
    except Exception:
        return []

    # Recoger links a PDFs que parezcan ley de ingresos del muni
    try:
        links = await page.eval_on_selector_all(
            "a",
            "els => els.map(e => ({h: e.href || '', t: (e.textContent||'').trim()}))",
        )
    except Exception:
        return []

    candidates: list[str] = []
    muni_lc = muni_nombre.lower()
    for lk in links:
        href = (lk.get("h") or "").lower()
        text = (lk.get("t") or "").lower()
        if ".pdf" not in href:
            continue
        # Heurística: contiene "ingres", "muni" Y el nombre del muni Y el año
        blob = href + " " + text
        if not _RE_LEY_MUNI_LINK.search(blob):
            continue
        if muni_lc not in blob:
            continue
        if str(anio) not in blob:
            continue
        candidates.append(lk["h"])
    return candidates


async def _run_async(
    adapter,
    target_years: list[int] | None,
    max_munis_per_year: int | None,
    headless: bool,
):
    from playwright.async_api import async_playwright

    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    index_csv = meta_dir / "ley_ingresos_index.csv"
    matcher = MuniMatcher(cve_ent=config.CVE_ENT, aliases=config.ALIASES)

    print("═══ Ruta A: Congreso del Estado SLP (Playwright best-effort) ═══")
    if not target_years:
        # Default: sólo 2010-2011 (los únicos sin alternativa via PO).
        target_years = [2010, 2011]
    print(f"  Target years: {target_years}")

    # Cargar índice previo y determinar qué (año, slug) faltan en disco
    existing_rows = _read_existing_index(index_csv) if index_csv.exists() else []
    pdfs_existentes: set[str] = set()
    for r in existing_rows:
        if r.get("status", "").startswith(("ok", "already_exists")) or \
           r.get("status") == "already_logged":
            slug = r.get("slug", "")
            ej = r.get("ejercicio", "")
            if slug and ej:
                pdfs_existentes.add(f"{ej}|{slug}")

    # Lista de slugs canónicos SLP del catálogo INEGI.
    # Iteramos contra el matcher: build a list of all (anio, slug) faltantes.
    todos_los_slugs = sorted(matcher.slugs)
    if max_munis_per_year:
        todos_los_slugs = todos_los_slugs[:max_munis_per_year]

    new_rows: list[dict] = []
    n_ok = 0
    n_no_match = 0
    n_err = 0

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=headless)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            ),
            ignore_https_errors=True,
        )
        page = await context.new_page()

        # Warm-up: visitar la home para resolver Sucuri challenge una sola vez.
        print("  Warm-up Sucuri en /legislacion/leyes ...")
        try:
            await page.goto(
                f"{config.BASE_URL_CONGRESO}/legislacion/leyes",
                wait_until="networkidle", timeout=60000,
            )
        except Exception as e:
            print(f"  [WARN] warm-up falló: {e}; continuando")

        for anio in target_years:
            print(f"\n  ── Año {anio} ──")
            for slug in todos_los_slugs:
                year_slug = f"{anio}|{slug}"
                if year_slug in pdfs_existentes:
                    continue

                file_local = (
                    pdf_raw_dir / str(anio)
                    / f"{config.PREFIJO}_RAW_{anio}_{slug}.pdf"
                )
                if file_local.exists() and file_local.stat().st_size > 1024:
                    pdfs_existentes.add(year_slug)
                    continue

                muni_nombre = _slug_a_nombre(slug)
                candidates = await _buscar_muni_anio(page, muni_nombre, anio)

                if not candidates:
                    n_no_match += 1
                    new_rows.append({
                        "ejercicio": anio,
                        "id_publicacion": "",
                        "fecha_publicacion": "",
                        "nivel_gob_id": "",
                        "decreto": "",
                        "titulo_original": "",
                        "municipio_raw": muni_nombre,
                        "slug": slug,
                        "cve_mun": "",
                        "match_method": "search_no_match",
                        "match_score": 0,
                        "pdf_url": "",
                        "file_local": str(file_local),
                        "status": "congreso:no_match",
                        "source": "congreso",
                    })
                    continue

                # Tomar el primero y descargar
                pdf_url = candidates[0]
                status = await _fetch_pdf_via_browser(page, pdf_url, file_local)

                if status == "ok":
                    n_ok += 1
                    print(f"    [OK] {file_local.name} ← {pdf_url}")
                    pdfs_existentes.add(year_slug)
                else:
                    n_err += 1

                new_rows.append({
                    "ejercicio": anio,
                    "id_publicacion": "",
                    "fecha_publicacion": "",
                    "nivel_gob_id": "",
                    "decreto": "",
                    "titulo_original": "",
                    "municipio_raw": muni_nombre,
                    "slug": slug,
                    "cve_mun": "",
                    "match_method": "search_match",
                    "match_score": 1.0,
                    "pdf_url": pdf_url,
                    "file_local": str(file_local),
                    "status": status,
                    "source": "congreso",
                })

        await browser.close()

    # Mergear con índice
    seen = {(r.get("ejercicio", ""), r.get("slug", ""), r.get("source", ""))
            for r in new_rows}
    merged = list(new_rows)
    for r in existing_rows:
        key = (r.get("ejercicio", ""), r.get("slug", ""), r.get("source", "po_api"))
        if key not in seen:
            r.setdefault("source", "po_api")
            merged.append(r)

    tmp = index_csv.with_suffix(".tmp")
    with tmp.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_INDEX_FIELDS)
        writer.writeheader()
        writer.writerows(merged)
    tmp.replace(index_csv)

    print("\n  ── Resumen Ruta A (Congreso) ──")
    print(f"  Munis intentados:  {len(new_rows)}")
    print(f"  PDFs rescatados:   {n_ok}")
    print(f"  Sin match en search: {n_no_match}")
    print(f"  Errores descarga:    {n_err}")
    print(f"  Índice: {index_csv}")

    return index_csv


def run_download_congreso(
    adapter,
    target_years: list[int] | None = None,
    max_munis_per_year: int | None = None,
    headless: bool = True,
) -> Path:
    """
    Best-effort scrape del Congreso para Leyes de Ingresos municipales.

    Args:
        adapter: Adaptador SLP.
        target_years: Lista de años (default: [2010, 2011]).
        max_munis_per_year: Límite de munis por año (None = todos los 58).
        headless: True para ejecutar sin GUI.

    Returns:
        Path al índice CSV actualizado.
    """
    if not _check_playwright_available():
        raise RuntimeError(
            "Playwright no está instalado.\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    return asyncio.run(_run_async(
        adapter,
        target_years=target_years,
        max_munis_per_year=max_munis_per_year,
        headless=headless,
    ))
