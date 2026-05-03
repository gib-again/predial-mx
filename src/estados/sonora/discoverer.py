"""
Discovery HTML del Boletín Oficial de Sonora — Fase A del pipeline v3.

Para cada índice anual de Joomla (mapeado en config.ID_JOOMLA_POR_ANIO_PUB),
parsea el HTML estructurado y extrae todas las leyes municipales mencionadas
en cada `<li>`, sin filtrar por mes.

Estructura típica de un `<li>` en el HTML:
  <li>
    <a href="/boletin/images/boletinesPdf/2012/enero/2012CLXXXIX2XXI.pdf">
      <strong>Jueves 5 de Enero de 2012. CLXXXIX Número 2. Secc. XXI</strong>
    </a>
    <strong>ESTATAL</strong>
    <strong>PODER EJECUTIVO-PODER LEGISLATIVO</strong>
    • Ley Número 179 de Ingresos y Presupuesto de Ingresos del H. Ayuntamiento
      del Municipio de Átil, para el Ejercicio Fiscal 2012.
    • Ley Número 180 de Ingresos y Presupuesto de Ingresos del H. Ayuntamiento
      del Municipio de Bacadéhuachi, para el Ejercicio Fiscal 2012.
  </li>

Régimen A (pre-~2017): N leyes municipales por PDF (boletines agrupados).
Régimen B (post-~2017): 1 ley = 1 PDF.

Outputs:
  data/sonora/meta/discovered_laws.csv     (1 fila por LeyIngreso)
  data/sonora/meta/source_documents.csv    (1 fila por DocumentoFuente, dedup)
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from src.core.muni_matcher import MuniMatcher
from src.core.text_utils import slugify
from src.estados.sonora import config


# ═══════════════════════════════════════════════════
# Dataclasses
# ═══════════════════════════════════════════════════

@dataclass
class DocumentoFuente:
    """PDF físico del Boletín Oficial."""
    url_pdf: str
    fecha_publicacion: str = ""   # ISO 8601 si parseable, sino vacío
    tomo: str = ""                # "CLXXXIX"
    numero_boletin: str = ""      # "2"
    seccion: str = ""             # "XXI"
    era: str = ""                 # "antigua" | "nueva" | "EE" | "otra"
    sha256: str = ""              # se llena tras descarga
    path_local: str = ""          # se llena tras descarga
    anio_pub: int = 0             # año del path interno (para organizar pdf_raw/)


@dataclass
class LeyIngreso:
    """Una ley de ingresos municipal individual."""
    municipio_raw: str
    municipio_slug: str
    cve_mun: str
    anio_fiscal: int
    numero_ley: str               # número de decreto/ley (puede no ser entero)
    documento_url: str            # FK a DocumentoFuente.url_pdf
    regimen: str = ""             # "A" (multi-ley en 1 PDF) | "B" (1 ley = 1 PDF)
    page_start: int = -1          # solo régimen A; -1 indica passthrough/desconocido
    page_end: int = -1


# ═══════════════════════════════════════════════════
# Regex para extracción de leyes del HTML
# ═══════════════════════════════════════════════════

# Captura UNA ley municipal en el texto del <li>. Tolera variantes:
#   - "Ley Número N de Ingresos..."
#   - "Ley número N, de Ingresos..."
#   - "Ley No. N, de Ingresos..."
#   - "Ley número 32, de Ingresos y Presupuesto..."  (con Y Presupuesto)
#   - "del H. Ayuntamiento" / "del Ayuntamiento"
#   - "Municipio de X" / "Municipio-de X"
#   - ", Sonora" opcional
#   - "Ejercicio Fiscal 2012" / "Ejercicio Fiscal de 2012" / "Ejercicio Fiscal del año 2012"
PATRON_LEY = re.compile(
    r"Ley\s+(?:n[uú]mero|N[uú]mero|No\.?)\s+(?P<num>\d+)"
    # Lista de números adicionales: ", N", " y N", ", N y M", ", N, M, ..."
    r"(?:[,\s]+(?:y\s+)?\d+)*"
    r"\s*[,\.]?\s*"
    r"(?:de\s+)?Ingresos(?:\s+y\s+Presupuestos?\s+de\s+Ingresos)?\s+"
    # Introductor del municipio (acepta opcionalmente "del" / "de los"):
    #   "del Ayuntamiento del Municipio de X"
    #   "del Ayuntamiento de X"
    #   "del Municipio de X"
    #   "del H. Ayuntamiento del Municipio de X"
    #   "de los H. Ayuntamientos de los Municipios de X" (multi)
    #   "Ayuntamiento de X" (sin "del")
    r"(?:del?\s+(?:los\s+)?)?"  # "del" / "de los" / vacío
    r"(?:"
    r"(?:H\.\s+)?Ayuntamientos?(?:\s+(?:del?\s+)?(?:los\s+)?Municipios?)?"
    r"|"
    r"Municipios?"
    r")\s+de\s+"
    r"(?P<muni>[\w\sÁÉÍÓÚÑÜáéíóúñü\.\-,]+?)"
    # Terminadores:
    #   ", Sonora" / "para el Ejercicio Fiscal" / EOL
    #   "." seguido de mayúscula, "•" (U+2022), "◊" (U+25CA) o "<"
    r"(?=\s*,\s*Sonora|\s+para\s+el\s+[Ee]jercicio|\s*\.\s*$"
    r"|\s*\.\s+(?=[A-Z•◊<])|\s+<|$)",
    re.IGNORECASE,
)

# Patrón secundario para extraer año fiscal opcional al final
PATRON_ANIO_FISCAL = re.compile(
    r"para\s+el\s+[Ee]jercicio\s+[Ff]iscal\s+(?:de(?:l)?\s+)?(?:a[ñn]o\s+)?"
    r"(?P<anio>20\d{2}|20\d\s\d|2\s0\d{2})",
    re.IGNORECASE,
)

# Filtros de exclusión: NO son leyes municipales originales.
# Aplican SOLO al contexto justo antes del match de "Ley Número N de Ingresos"
# (no a todo el documento). Patrones:
#   - "Decreto N que reforma la ley No N de Ingresos..."
#   - "Fe de erratas a la(s) ley(es) de Ingresos..."
#   - "Modificaciones al Presupuesto de Ingresos..."
PATRON_EXCLUSION = re.compile(
    r"("
    r"Decreto\s+\d{1,4}[,\s]+que\s+reforma|"
    r"reforma\s+(?:y\s+adiciona)?[^.]{0,40}\bley\b|"
    r"Fe\s+de\s+[Ee]rratas|"
    r"Modificaci[oó]n(?:es)?\s+al\s+Presupuesto"
    r")",
    re.IGNORECASE,
)
# Patrón para detectar "del Estado" justo después del título (NO municipal)
PATRON_LEY_ESTATAL = re.compile(
    r"Ingresos\s+y\s+Presupuestos?\s+de\s+Ingresos\s+del\s+Estado",
    re.IGNORECASE,
)

# Patrón alternativo (formato antiguo): captura LISTA de municipios
# "Ley de Ingresos y Presupuestos de Ingresos para el Ejercicio Fiscal YYYY,
#  de(l) los Municipios de X, Y, Z..."
# Tolerancia a typo "201 1" (con espacio entre dígitos del año).
# Captura TODA la lista para separarla por coma/y después.
PATRON_LEY_ALT = re.compile(
    r"Ley\s+de\s+Ingresos\s+y\s+Presupuestos?\s+de\s+Ingresos\s+"
    r"(?:del\s+Ayuntamiento\s+)?"
    r"para\s+el\s+Ejercicio\s+Fiscal\s+(?:del?\s+(?:a[ñn]o\s+)?)?"
    r"(?P<anio>20\d{2}|20\d\s\d|2\s0\d{2})\s*,?\s*"
    r"de(?:\s+los?)?\s+Municipios?\s+de\s+"
    r"(?P<lista>[\w\sÁÉÍÓÚÑÜáéíóúñü\.\,\-]+?)"
    r"(?:\s*\.|\s*<|\s+Periódico|\s+Tomo|\s+Boletín|$)",
    re.IGNORECASE,
)

# Patrón lista plural (formato 2010): "leyes de Ingresos y Presupuesto de
# Ingresos de los municipios de X, Y, Z, W, ..."
PATRON_LEY_LISTA = re.compile(
    r"leyes\s+de\s+Ingresos\s+y\s+Presupuestos?\s+de\s+Ingresos\s+"
    r"(?:para\s+el\s+Ejercicio\s+Fiscal\s+(?:del?\s+(?:a[ñn]o\s+)?)?(?P<anio>20\d{2}|20\d\s\d)[\s,]+)?"
    r"de\s+los\s+[Mm]unicipios?\s+de\s+"
    r"(?P<lista>[\w\sÁÉÍÓÚÑÜáéíóúñü\.\,\-]+?)"
    r"(?:\s*\.|\s*<|\s+Periódico|\s+Tomo|\s+Boletín|$)",
    re.IGNORECASE,
)

# Patrón plural numerado (formato 2014): "Leyes Números 101, 103, 105 y 111
# de Ingresos y Presupuesto de Ingresos de los (H.) Ayuntamientos de Aconchi,
# Álamos, Arivechi, Bacoachi, para el Ejercicio Fiscal 2014".
# Captura lista de municipios + año fiscal explícito al final.
PATRON_LEYES_PLURAL = re.compile(
    r"Leyes?\s+(?:n[uú]meros?|N[uú]meros?)\s+(?P<nums>[\d\s,yY]+?)\s+"
    r"(?:de\s+)?Ingresos(?:\s+y\s+Presupuestos?\s+de\s+Ingresos)?\s+"
    r"de\s+los?\s+(?:(?:H\.\s+)?Ayuntamientos?(?:\s+del?\s+los?\s+Municipios?)?|Municipios?)\s+de\s+"
    r"(?P<lista>[\w\sÁÉÍÓÚÑÜáéíóúñü\.\,\-]+?)"
    r"\s*,?\s*para\s+el\s+Ejercicio\s+Fiscal\s+(?:de(?:l)?\s+)?(?:a[ñn]o\s+)?(?P<anio>\d{4})",
    re.IGNORECASE,
)


def _split_lista_municipios(lista_raw: str) -> list[str]:
    """Separa una lista de municipios por comas o ' y '."""
    # Reemplazar variantes de ' y ' por coma para uniformidad
    lista_raw = re.sub(r"\s+y\s+", ",", lista_raw, flags=re.IGNORECASE)
    parts = re.split(r"\s*,\s*", lista_raw)
    out: list[str] = []
    for p in parts:
        p = p.strip(" .,;-")
        if not p:
            continue
        # "Gral" suele ser truncado de "General Plutarco Elías Calles"
        # — lo aceptamos como Gral y dejamos que MuniMatcher lo resuelva.
        # Limitar tamaño por sanidad.
        if len(p) < 3 or len(p) > 60:
            continue
        if p.upper() in {"ESTADO", "GOBIERNO", "PUEBLO", "SONORA", "OTROS", "ETC"}:
            continue
        out.append(p)
    return out

# Detección de fecha en encabezado del <li>: "Jueves 5 de Enero de 2012"
_MES_NOMBRE_A_NUM = {
    "enero": "01", "febrero": "02", "marzo": "03", "abril": "04",
    "mayo": "05", "junio": "06", "julio": "07", "agosto": "08",
    "septiembre": "09", "octubre": "10", "noviembre": "11", "diciembre": "12",
}
PATRON_FECHA = re.compile(
    r"\b(?P<dia>\d{1,2})\s+de\s+(?P<mes>"
    + "|".join(_MES_NOMBRE_A_NUM.keys())
    + r")\s+de\s+(?P<anio>\d{4})",
    re.IGNORECASE,
)
PATRON_TOMO_NUM = re.compile(
    r"(?P<tomo>[CDLXVI]{1,8})\s+N[uú]mero\s+(?P<num>\d+)\s*[\.\s]+(?:Secc?\.?\s*(?P<secc>[CDLXVI]+))?",
    re.IGNORECASE,
)

# Clasificación de URL por era
_RE_PDF_NEW = re.compile(r"/images/boletines/(?P<year>\d{4})/", re.IGNORECASE)
_RE_PDF_OLD = re.compile(r"/boletin/images/boletinesPdf/(?P<year>\d{4})/", re.IGNORECASE)
_RE_PDF_EE = re.compile(r"/EE\d{8}", re.IGNORECASE)
_RE_PDF_ANY = re.compile(r"\.pdf$", re.IGNORECASE)


# ═══════════════════════════════════════════════════
# Parsing helpers
# ═══════════════════════════════════════════════════

def _parse_fecha(text: str) -> str:
    """Extrae fecha ISO 8601 del texto del <li> ('Jueves 5 de Enero de 2012')."""
    m = PATRON_FECHA.search(text or "")
    if not m:
        return ""
    dia = m.group("dia").zfill(2)
    mes = _MES_NOMBRE_A_NUM[m.group("mes").lower()]
    anio = m.group("anio")
    return f"{anio}-{mes}-{dia}"


def _parse_tomo_num_secc(text: str) -> tuple[str, str, str]:
    """Extrae (tomo, numero_boletin, seccion) del texto del <li>."""
    m = PATRON_TOMO_NUM.search(text or "")
    if not m:
        return "", "", ""
    return m.group("tomo") or "", m.group("num") or "", m.group("secc") or ""


def _classify_era(url: str) -> tuple[str, int]:
    """Devuelve (era, anio_pub) basado en el path de la URL."""
    if _RE_PDF_EE.search(url):
        # Edición Especial: extraer año del nombre EEDDMMYYYY.pdf
        m = re.search(r"EE\d{4}(\d{4})", url)
        anio = int(m.group(1)) if m else 0
        return "EE", anio
    m = _RE_PDF_NEW.search(url)
    if m:
        return "nueva", int(m.group("year"))
    m = _RE_PDF_OLD.search(url)
    if m:
        return "antigua", int(m.group("year"))
    return "otra", 0


def _extract_leyes_from_text(text: str, url_pdf: str) -> list[dict]:
    """Aplica los patrones (PATRON_LEY + ALT + LISTA) y deduplica por (slug, anio).

    PATRON_LEY ahora captura el año desde una búsqueda secundaria (PATRON_ANIO_FISCAL)
    en el contexto siguiente, porque el año puede o no aparecer al final.
    Aplica filtros de exclusión: NO leyes del Estado, decretos, fes de erratas, etc.
    """
    if not text:
        return []
    out: list[dict] = []
    seen: set[tuple[str, int]] = set()

    for m in PATRON_LEY.finditer(text):
        muni_raw_full = re.sub(r"\s+", " ", m.group("muni") or "").strip(" ,.;-")
        if not muni_raw_full:
            continue
        # Filtros de exclusión: revisar contexto previo (decretos, fes erratas)
        # y verificar que NO sea una ley estatal (Ingresos del Estado).
        ctx_before = text[max(0, m.start() - 80):m.start()]
        if PATRON_EXCLUSION.search(ctx_before):
            continue
        # Verificar que no sea Ley del Estado (revisa match completo)
        if PATRON_LEY_ESTATAL.search(m.group(0)):
            continue
        # Buscar año fiscal en el contexto cercano (hasta 200 chars después)
        ctx_after = text[m.end():m.end() + 200]
        anio = 0
        am = PATRON_ANIO_FISCAL.search(ctx_after)
        if am:
            try:
                anio = int((am.group("anio") or "").replace(" ", ""))
            except ValueError:
                anio = 0
        # Separar municipios si hay multi (X y Y)
        for muni in _split_lista_municipios(muni_raw_full):
            key = (muni.lower(), anio)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "municipio_raw": muni,
                "anio_fiscal": anio,
                "numero_ley": m.group("num") or "",
                "url_pdf": url_pdf,
            })

    # PATRON_LEYES_PLURAL: "Leyes Números 101, 103, 105 y 111 de Ingresos
    # ... de los Ayuntamientos de Aconchi, Álamos, Arivechi, Bacoachi, para
    # el Ejercicio Fiscal 2014" (formato 2014)
    for m in PATRON_LEYES_PLURAL.finditer(text):
        # Filtros de exclusión
        ctx_before = text[max(0, m.start() - 80):m.start()]
        if PATRON_EXCLUSION.search(ctx_before):
            continue
        if PATRON_LEY_ESTATAL.search(m.group(0)):
            continue
        anio_raw = (m.group("anio") or "").replace(" ", "")
        try:
            anio = int(anio_raw)
        except ValueError:
            continue
        lista_raw = m.group("lista") or ""
        for muni in _split_lista_municipios(lista_raw):
            key = (muni.lower(), anio)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "municipio_raw": muni,
                "anio_fiscal": anio,
                "numero_ley": "",
                "url_pdf": url_pdf,
            })

    # PATRON_LEY_ALT: "Ley de Ingresos ... para el Ejercicio Fiscal Y, de los Municipios de X, Y, Z"
    for m in PATRON_LEY_ALT.finditer(text):
        anio_raw = (m.group("anio") or "").replace(" ", "")
        try:
            anio = int(anio_raw)
        except ValueError:
            continue
        lista_raw = m.group("lista") or ""
        for muni in _split_lista_municipios(lista_raw):
            key = (muni.lower(), anio)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "municipio_raw": muni,
                "anio_fiscal": anio,
                "numero_ley": "",
                "url_pdf": url_pdf,
            })

    # PATRON_LEY_LISTA: "leyes ... de los municipios de X, Y, Z" (formato 2010)
    for m in PATRON_LEY_LISTA.finditer(text):
        anio_raw = (m.group("anio") or "").replace(" ", "")
        try:
            anio = int(anio_raw) if anio_raw else 0
        except ValueError:
            anio = 0
        lista_raw = m.group("lista") or ""
        for muni in _split_lista_municipios(lista_raw):
            key = (muni.lower(), anio)
            if key in seen:
                continue
            seen.add(key)
            out.append({
                "municipio_raw": muni,
                "anio_fiscal": anio,  # 0 si no se detectó; se infiere en caller
                "numero_ley": "",
                "url_pdf": url_pdf,
            })

    return out


# ═══════════════════════════════════════════════════
# Parser principal de un índice anual
# ═══════════════════════════════════════════════════

def parsear_indice_anual(
    id_joomla: int,
    anio_pub: int,
    session,
) -> tuple[list[DocumentoFuente], list[LeyIngreso], MuniMatcher]:
    """
    Descarga el HTML del índice id_joomla y extrae:
      - DocumentoFuentes (1 por PDF único)
      - LeyIngresos (1 por (municipio, anio_fiscal) detectado)

    Estrategia: parsear cada `<li>` que contenga UN solo `<a href=*.pdf>` y
    leer las leyes mencionadas SOLO en el texto de ese `<li>` (no del padre,
    para evitar duplicados causados por contenedores anidados).

    Si un `<li>` contiene varios PDFs (típico en menús de navegación), se
    descarta — los menús de navegación tienen muchos PDFs de Constitución,
    Reglamentos, etc., y no son listas de leyes municipales.
    """
    matcher = MuniMatcher(cve_ent=config.CVE_ENT, aliases=config.ALIASES)
    url_index = config.INDEX_URL_TPL.format(id_joomla=id_joomla)

    try:
        r = session.get(url_index, **config.REQUESTS_KWARGS)
        r.raise_for_status()
    except Exception as e:
        print(f"    [WARN] index id={id_joomla}: {e}")
        return [], [], matcher

    soup = BeautifulSoup(r.text, "html.parser")
    docs: dict[str, DocumentoFuente] = {}  # url → DocumentoFuente
    # Vincular leyes únicas a cada (URL, slug, anio_fiscal) para deduplicar
    leyes_keys: set[tuple[str, str, int]] = set()
    leyes: list[LeyIngreso] = []

    # Estrategia: para cada `<a href=*.pdf>` del año esperado, encontrar
    # el texto de leyes asociado mirando los `<li>` hermanos anteriores
    # en el mismo `<ul>`. La estructura observada en el sitio es:
    #   <ul>
    #     <li>Encabezado fecha / autoridad</li>
    #     <li>• Ley número N de Ingresos del Municipio X...</li>  ← texto leyes
    #     <li><a href=PDF>...</a></li>                              ← PDF
    #     <li>Próximo encabezado...</li>
    #     ...
    #   </ul>
    # Para cada PDF, miramos hasta 3 hermanos anteriores en el `<ul>`
    # buscando texto de leyes; también miramos el `<li>` que contiene al PDF.

    for a in soup.find_all("a", href=_RE_PDF_ANY):
        href = (a.get("href") or "").strip()
        if not href:
            continue
        full_url = urljoin(url_index, href)

        era, year_path = _classify_era(full_url)
        if era == "otra":
            continue
        if year_path and year_path != anio_pub:
            continue

        # Subir hasta el `<li>` contenedor del `<a>`
        li_pdf = a.find_parent("li")
        if li_pdf is None:
            continue

        # Recolectar texto: el `<li>` propio + hasta 6 hermanos anteriores
        # (los formatos antiguos pueden tener varios <li> de descripción
        # antes del <li> con el PDF).
        text_partes: list[str] = [li_pdf.get_text(" ", strip=True)]
        sib = li_pdf.find_previous_sibling("li")
        depth = 0
        while sib is not None and depth < 6:
            sib_text = sib.get_text(" ", strip=True)
            # Parar si el hermano contiene OTRO PDF (frontera entre items)
            if sib.find("a", href=_RE_PDF_ANY):
                break
            if sib_text:
                text_partes.insert(0, sib_text)
            sib = sib.find_previous_sibling("li")
            depth += 1
        text_combined = " | ".join(text_partes)

        # Filtrar contenedores demasiado grandes (probablemente menús)
        if len(text_combined) > 5000:
            continue

        # Extraer metadata común
        tomo, num_bol, secc = _parse_tomo_num_secc(text_combined)
        fecha = _parse_fecha(text_combined)

        if full_url not in docs:
            docs[full_url] = DocumentoFuente(
                url_pdf=full_url,
                fecha_publicacion=fecha,
                tomo=tomo,
                numero_boletin=num_bol,
                seccion=secc,
                era=era,
                anio_pub=year_path,
            )

        # Detectar leyes del texto combinado
        for ley_data in _extract_leyes_from_text(text_combined, full_url):
            anio_fiscal = ley_data["anio_fiscal"]
            # Si no se detectó año, inferir desde anio_pub+1 (publicación
            # típica: leyes EF N publicadas en dic N-1 o ene N).
            if anio_fiscal == 0 and anio_pub:
                anio_fiscal = anio_pub + 1
            if anio_fiscal < config.YEAR_MIN or anio_fiscal > config.YEAR_MAX:
                continue
            mr = matcher.match(ley_data["municipio_raw"])
            slug = mr.slug or slugify(ley_data["municipio_raw"])
            if not mr.cve_mun:
                continue
            key = (full_url, slug, anio_fiscal)
            if key in leyes_keys:
                continue
            leyes_keys.add(key)
            leyes.append(LeyIngreso(
                municipio_raw=ley_data["municipio_raw"],
                municipio_slug=slug,
                cve_mun=mr.cve_mun,
                anio_fiscal=anio_fiscal,
                numero_ley=ley_data["numero_ley"],
                documento_url=full_url,
            ))

    return list(docs.values()), leyes, matcher


# ═══════════════════════════════════════════════════
# Pipeline principal
# ═══════════════════════════════════════════════════

_LEYES_FIELDS = [
    "anio_fiscal", "municipio_slug", "cve_mun", "municipio_raw",
    "numero_ley", "documento_url", "regimen", "page_start", "page_end",
]
_DOCS_FIELDS = [
    "url_pdf", "anio_pub", "fecha_publicacion", "tomo", "numero_boletin",
    "seccion", "era", "sha256", "path_local",
]


def _classify_regimen(leyes: list[LeyIngreso]) -> dict[str, str]:
    """Para cada documento, determina régimen A (>1 ley) o B (==1 ley)."""
    counts: dict[str, int] = {}
    for ley in leyes:
        counts[ley.documento_url] = counts.get(ley.documento_url, 0) + 1
    return {url: ("A" if n > 1 else "B") for url, n in counts.items()}


def descubrir_leyes(adapter) -> Path:
    """
    Itera todos los id_joomla de config.ID_JOOMLA_POR_ANIO_PUB,
    parsea cada índice anual y consolida en CSVs.
    """
    from src.estados.sonora.download import _make_session

    meta_dir = adapter.meta_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    laws_csv = meta_dir / "discovered_laws.csv"
    docs_csv = meta_dir / "source_documents.csv"

    print("═══ Sonora: Discovery HTML (Fase A) ═══")
    print(f"    Años a procesar: {sorted(config.ID_JOOMLA_POR_ANIO_PUB.keys())}")

    session = _make_session()
    todos_docs: dict[str, DocumentoFuente] = {}
    todas_leyes: list[LeyIngreso] = []

    for anio_pub in sorted(config.ID_JOOMLA_POR_ANIO_PUB.keys()):
        id_joomla = config.ID_JOOMLA_POR_ANIO_PUB[anio_pub]
        docs, leyes, _ = parsear_indice_anual(id_joomla, anio_pub, session)

        # Deduplicar docs por URL
        for d in docs:
            if d.url_pdf not in todos_docs:
                todos_docs[d.url_pdf] = d

        todas_leyes.extend(leyes)
        print(
            f"    anio_pub={anio_pub} (id={id_joomla}): "
            f"{len(docs)} docs únicos, {len(leyes)} leyes detectadas"
        )

    # Clasificar régimen por documento
    regimen_map = _classify_regimen(todas_leyes)
    for ley in todas_leyes:
        ley.regimen = regimen_map.get(ley.documento_url, "?")

    # Escribir leyes
    with laws_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_LEYES_FIELDS)
        writer.writeheader()
        for ley in todas_leyes:
            writer.writerow({
                "anio_fiscal": ley.anio_fiscal,
                "municipio_slug": ley.municipio_slug,
                "cve_mun": ley.cve_mun,
                "municipio_raw": ley.municipio_raw,
                "numero_ley": ley.numero_ley,
                "documento_url": ley.documento_url,
                "regimen": ley.regimen,
                "page_start": ley.page_start,
                "page_end": ley.page_end,
            })

    # Escribir docs
    with docs_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_DOCS_FIELDS)
        writer.writeheader()
        for url in sorted(todos_docs):
            d = todos_docs[url]
            writer.writerow({
                "url_pdf": d.url_pdf,
                "anio_pub": d.anio_pub,
                "fecha_publicacion": d.fecha_publicacion,
                "tomo": d.tomo,
                "numero_boletin": d.numero_boletin,
                "seccion": d.seccion,
                "era": d.era,
                "sha256": d.sha256,
                "path_local": d.path_local,
            })

    print()
    print("  ── Resumen discovery ──")
    print(f"  Documentos únicos:        {len(todos_docs)}")
    print(f"  Leyes municipales:        {len(todas_leyes)}")
    n_a = sum(1 for v in regimen_map.values() if v == "A")
    n_b = sum(1 for v in regimen_map.values() if v == "B")
    print(f"  Docs régimen A (multi):   {n_a}")
    print(f"  Docs régimen B (1 ley):   {n_b}")
    # Cobertura por año fiscal
    from collections import Counter
    cob = Counter(ley.anio_fiscal for ley in todas_leyes)
    print("  Cobertura por anio_fiscal:")
    for a in sorted(cob):
        print(f"    {a}: {cob[a]}")
    print(f"  Bitácoras: {laws_csv}, {docs_csv}")
    return laws_csv
