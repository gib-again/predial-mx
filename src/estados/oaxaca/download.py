"""
Descarga de PDFs del Periódico Oficial de Oaxaca.

Dos fases:
  1. Búsqueda HTML: POST a busqueda.php con payload por año.
     Parsea la tabla de resultados (tblNueva) y extrae metadata + hrefs.
  2. Descarga de PDFs: Para cada href único, descarga el PDF.

Los PDFs de Oaxaca tienen estructura:
  files/{YYYY}/{MM}/{nombre}.pdf

Convención de salida:
  data/oaxaca/pdf_raw/{año}/{mes}/{filename_original}.pdf
  data/oaxaca/meta/oaxaca_index.csv

Los PDFs del PO contienen múltiples leyes de ingresos (3-7 por "Sección").
La segmentación posterior se encarga de extraer cada municipio.

Nota: El PO de Oaxaca publica leyes durante TODO el año (no solo enero/febrero),
por lo que hay PDFs en muchos meses distintos. Esto es normal.
"""

from __future__ import annotations

import csv
import hashlib
import re
import time
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.estados.oaxaca import config


# ═══════════════════════════════════════════════════
# Utilidades
# ═══════════════════════════════════════════════════

_MONTHS_ES = {
    "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6,
    "jul": 7, "ago": 8, "sep": 9, "oct": 10, "nov": 11, "dic": 12,
}

# Distritos y aliases frecuentes en el PO / OCR del índice HTML
_DISTRICT_ALIASES: dict[str, str] = {
    "BENEMERITO DISTRITO DE IXTLAN DE JUAREZ": "Ixtlán",
    "BENEMERITO IXTLAN DE JUAREZ": "Ixtlán",
    "DISTRITO DE IXTLAN DE JUAREZ": "Ixtlán",
    "IXTLAN DE JUAREZ": "Ixtlán",
    "BENEMERITO IXTLAN": "Ixtlán",
    "ZACATEPEC MIXE": "Mixe",
    "HUAJUAPAM": "Huajuapan",
    "HUAJUAPAN": "Huajuapan",
    "CHOAPAM": "Choápam",
    "JUCHITAN": "Juchitán",
    "JUCHITN": "Juchitán",
    "MIAHUTLAN": "Miahuatlán",
    "MIAHUATLAN": "Miahuatlán",
    "MIAHUATLN": "Miahuatlán",
    "NOCHIXTLAN": "Nochixtlán",
    "TEOTITLAN": "Teotitlán",
    "CUICATLAN": "Cuicatlán",
    "CUICATLN": "Cuicatlán",
    "COIXTLAHUACA": "Coixtlahuaca",
    "SILACAYOAPAM": "Silacayoapam",
    "SOLA DE VEGA": "Sola de Vega",
    "VILLA ALTA": "Villa Alta",
    "CENTRO": "Centro",
    "ETLA": "Etla",
    "EJUTLA": "Ejutla",
    "IXTLAN": "Ixtlán",
    "JAMILTEPEC": "Jamiltepec",
    "JUQUILA": "Juquila",
    "JUXTLAHUACA": "Juxtlahuaca",
    "MIXE": "Mixe",
    "OCOTLAN": "Ocotlán",
    "POCHUTLA": "Pochutla",
    "PUTLA": "Putla",
    "TEHUANTEPEC": "Tehuantepec",
    "TEPOSCOLULA": "Teposcolula",
    "TLACOLULA": "Tlacolula",
    "TLAXIACO": "Tlaxiaco",
    "TUXTEPEC": "Tuxtepec",
    "YAUTEPEC": "Yautepec",
    "ZAACHILA": "Zaachila",
    "ZIMATLAN": "Zimatlán",
}

for _dist in getattr(config, "DISTRITOS", []):
    _norm = unicodedata.normalize("NFD", _dist)
    _norm = "".join(c for c in _norm if unicodedata.category(c) != "Mn").upper()
    _DISTRICT_ALIASES[_norm] = _dist
    _DISTRICT_ALIASES[_dist.upper()] = _dist

_MUNICIPALITY_NAMES_CACHE: list[tuple[str, str]] | None = None


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _looks_like_pdf(path: Path) -> bool:
    try:
        with path.open("rb") as f:
            return f.read(4) == b"%PDF"
    except Exception:
        return False


def _safe_text(el) -> str:
    return el.get_text(" ", strip=True) if el else ""


def _strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def _text_quality_score(s: str) -> int:
    if not s:
        return -10**9
    bad = sum(s.count(ch) for ch in ("Ã", "Â", "�", "¤"))
    good = sum(s.count(ch) for ch in "áéíóúÁÉÍÓÚñÑ")
    return good - 3 * bad


def _repair_mojibake(text: str) -> str:
    if not isinstance(text, str):
        return text
    s = text
    for _ in range(2):
        if all(ch not in s for ch in ("Ã", "Â", "�", "¤")):
            break
        candidates = [s]
        for src_enc in ("latin-1", "cp1252"):
            try:
                candidates.append(s.encode(src_enc).decode("utf-8"))
            except Exception:
                try:
                    candidates.append(
                        s.encode(src_enc, errors="ignore").decode("utf-8", errors="ignore")
                    )
                except Exception:
                    pass
        s = max(candidates, key=_text_quality_score)
    return s


def _clean_text(s: str) -> str:
    s = _repair_mojibake(s or "")
    s = s.replace("\xa0", " ")
    s = re.sub(r"\s+", " ", s).strip()

    # Pega/rompe palabras comunes del índice HTML
    s = re.sub(r"(?<=[a-záéíóúñ])(?=[A-ZÁÉÍÓÚÑ])", " ", s)   # LomaBonita -> Loma Bonita
    s = re.sub(r"\b(DE)(?=[A-ZÁÉÍÓÚÑ])", r"\1 ", s)           # DEASUNCIÓN -> DE ASUNCIÓN
    s = re.sub(r"\b(de)(?=[A-ZÁÉÍÓÚÑ])", r"\1 ", s)           # dePutla -> de Putla
    s = re.sub(r"\b(LA)(?=HEROICA\b)", r"\1 ", s, flags=re.IGNORECASE)

    # OCR/HTML a veces rompe DEL como "DE L"
    s = re.sub(r"(?i)\bDE\s+L(?=\s+[A-ZÁÉÍÓÚÑ])", "DEL", s)

    s = re.sub(r"\bDELMUNICIPIODE\b", "DEL MUNICIPIO DE", s, flags=re.IGNORECASE)
    s = re.sub(r"\bDELMUNICIPIO\b", "DEL MUNICIPIO", s, flags=re.IGNORECASE)
    s = re.sub(r"\bMUNICIPIODE\b", "MUNICIPIO DE", s, flags=re.IGNORECASE)

    # Typos frecuentes del índice HTML / OCR
    fixes = {
        r"\bEJERCIDO\b": "EJERCICIO",
        r"\bEJECICIO\b": "EJERCICIO",
        r"\bEJERICICIO\b": "EJERCICIO",
        r"\bEJERCICICIO\b": "EJERCICIO",
        r"\bEJERCICICO\b": "EJERCICIO",
        r"\bEJERCICO\b": "EJERCICIO",
        r"\bEJERCIO\b": "EJERCICIO",
        r"\bEJRCICIO\b": "EJERCICIO",
        r"\bFISCL\b": "FISCAL",
    }
    for pat, repl in fixes.items():
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)

    return s.strip()


def _norm_search(s: str) -> str:
    s = _clean_text(s)
    s = _strip_accents(s).upper()
    s = re.sub(r"[^A-Z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _decode_html_response(resp: requests.Response) -> str:
    raw = resp.content
    meta_match = re.search(
        rb"charset=['\"]?([A-Za-z0-9_\-]+)",
        raw[:4096],
        flags=re.IGNORECASE,
    )
    meta_encoding = meta_match.group(1).decode("ascii", errors="ignore") if meta_match else None

    candidates: list[str] = []
    for enc in (meta_encoding, resp.apparent_encoding, resp.encoding, "utf-8", "cp1252", "latin-1"):
        if enc and enc not in candidates:
            candidates.append(enc)

    decoded_candidates: list[str] = []
    for enc in candidates:
        try:
            decoded_candidates.append(raw.decode(enc, errors="replace"))
        except Exception:
            continue

    if not decoded_candidates:
        decoded_candidates = [raw.decode("utf-8", errors="replace")]

    best = max(decoded_candidates, key=_text_quality_score)
    return _repair_mojibake(best)


def _parse_fecha_publicacion(value: str) -> date | None:
    s = _clean_text(value).lower()
    m = re.match(r"(\d{1,2})-([a-záéíóúñ]{3})-(\d{2,4})$", s)
    if not m:
        return None
    day = int(m.group(1))
    mon = _MONTHS_ES.get(_strip_accents(m.group(2))[:3])
    year = int(m.group(3))
    if year < 100:
        year += 2000
    if not mon:
        return None
    try:
        return date(year, mon, day)
    except ValueError:
        return None


def _get_municipality_names() -> list[tuple[str, str]]:
    global _MUNICIPALITY_NAMES_CACHE
    if _MUNICIPALITY_NAMES_CACHE is not None:
        return _MUNICIPALITY_NAMES_CACHE

    names: list[tuple[str, str]] = []
    try:
        for _, nombre, _slug in config.load_municipios():
            names.append((_norm_search(nombre), nombre))
    except Exception:
        names = []

    names.sort(key=lambda x: len(x[0]), reverse=True)
    _MUNICIPALITY_NAMES_CACHE = names
    return names


def _find_municipio_from_catalog(sumario: str) -> str:
    text_norm = _norm_search(sumario)
    if not text_norm:
        return ""

    for norm_name, nombre in _get_municipality_names():
        if not norm_name:
            continue
        if re.search(rf"(^| )({re.escape(norm_name)})( |$)", text_norm):
            return nombre
    return ""


def _should_keep_sumario(sumario: str) -> bool:
    s = _norm_search(sumario)
    if not s or "LEY DE INGRESOS" not in s:
        return False

    # Se conserva como documento de consulta
    if "LEY GENERAL DE INGRESOS MUNICIPALES DEL ESTADO DE OAXACA" in s:
        return True

    # Se suprime la ley estatal
    if "LEY DE INGRESOS DEL ESTADO DE OAXACA" in s and "MUNICIPALES" not in s:
        return False

    # Tipos de documento a suprimir por texto del sumario, no por tipo_documento
    prefix = re.sub(r"^DECRETO\s+NUM(?:ERO|\.|)\s*\d+\s*", "", s).strip()
    if re.match(r"^(FE DE ERRATAS|CALENDARIO|ANEXO(?:S)?|CONVOCATORIA|ACUERDO)\b", prefix):
        return False
    if re.search(r"\b(FE DE ERRATAS|ERRATAS|CALENDARIO|ANEXO(?:S)?|CONVOCATORIA|ACUERDO)\b", prefix[:60]):
        return False

    # Reformas, adiciones, prórrogas, vigencias
    if re.search(
        r"\b(REFORMA(?:DA|DO|S)?|REFORMAN|ADICION(?:A|AN|ES)?|PRORROG(?:A|AN|AR)|VIGENCIA)\b",
        s,
    ):
        return False

    # No municipales
    if "CORPORACION OAXAQUENA DE RADIO Y TELEVISION" in s:
        return False

    # Municipales válidas: por municipio o por nombre municipal directo
    if "MUNICIPIO" in s:
        return True

    return bool(
        re.search(r"LEY DE INGRESOS DE (?:LA )?(?:HEROICA|CIUDAD|VILLA)\b", s)
    )


def _extract_ejercicio_fiscal(sumario: str) -> int | None:
    s = _norm_search(sumario)
    patterns = [
        r"(?:PARA|SU)?\s*EL?\s*(?:EJ[A-Z]{3,18}|LEGAL)\s*(?:FISCAL|LEGAL)?\s*(?:DEL\s+)?(20\d{2})\b",
        r"\b(20\d{2})\b$",
    ]
    for pat in patterns:
        m = re.search(pat, s)
        if m:
            try:
                return int(m.group(1))
            except Exception:
                return None
    return None


def _split_rest_municipio_distrito(rest: str) -> tuple[str, str]:
    rest = _clean_text(rest)
    rest = re.split(r"(?i)\b(?:PAA|PARA)\b", rest, maxsplit=1)[0]
    rest = re.sub(r"(?i)[,;]?\s*OAXACA\s*\.?$", "", rest).strip(" ,.;")
    rest = rest.replace(";", ",")

    if not rest:
        return "", ""

    parts = [
        _clean_text(p).strip(" ,.;")
        for p in re.split(r"\s*,\s*", rest)
        if _clean_text(p).strip(" ,.;")
    ]
    if len(parts) >= 2:
        municipio = parts[0]
        distrito = parts[1]
        distrito = re.sub(r"(?i)^DISTRITO DE\s+", "", distrito).strip(" ,.;")
        return municipio, distrito

    only = parts[0] if parts else rest
    n_only = _norm_search(only)

    # Split por alias de distrito al final
    for alias, _canonical in sorted(_DISTRICT_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
        if n_only.endswith(" " + alias):
            alias_len = len(alias.split())
            tokens = _clean_text(only).split()
            if len(tokens) > alias_len:
                municipio = " ".join(tokens[:-alias_len]).strip(" ,.;")
                distrito = " ".join(tokens[-alias_len:]).strip(" ,.;")
                distrito = re.sub(r"(?i)^DISTRITO DE\s+", "", distrito).strip(" ,.;")
                return municipio, distrito

    return only.strip(" ,.;"), ""


def _extract_municipio_ejercicio(sumario: str) -> tuple[str, str, int | None]:
    """
    Extrae municipio, distrito y ejercicio fiscal del sumario con tolerancia
    a OCR/HTML defectuoso y variaciones en el encabezado.
    """
    s = _clean_text(sumario)
    s_norm = _norm_search(s)

    if "LEY GENERAL DE INGRESOS MUNICIPALES DEL ESTADO DE OAXACA" in s_norm:
        fy = _extract_ejercicio_fiscal(s)
        return "LEY GENERAL DE INGRESOS MUNICIPALES DEL ESTADO DE OAXACA", "", fy

    fy = _extract_ejercicio_fiscal(s)

    patterns = [
        r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DEL\s+MUNICIPIO\s+DE\s+(?P<rest>.+)",
        r"LEY\s+DE\s+INGRESOS\s+DEL\s+HONORABLE\s+AYUNTAMIENTO\s+DE\s+(?P<rest>.+)",
        r"LEY\s+DE\s+INGRESOS\s+DEL\s+MUNICIPIO\s+DE\s+(?P<rest>.+)",
        r"LEY\s+DE\s+INGRESOS\s+DE\s+(?P<rest>.+)",
    ]

    rest = ""
    for pat in patterns:
        m = re.search(pat, s, flags=re.IGNORECASE)
        if m:
            rest = m.group("rest").strip()
            break

    municipio = distrito = ""
    if rest:
        municipio, distrito = _split_rest_municipio_distrito(rest)

    # Recuperación auxiliar por catálogo si el municipio sigue vacío
    if (not municipio or municipio.upper().startswith("L MUNICIPIO")) and "MUNICIPIO" in s_norm:
        municipio_catalogo = _find_municipio_from_catalog(s)
        if municipio_catalogo:
            municipio = municipio_catalogo

    if municipio.upper().startswith("L MUNICIPIO"):
        municipio = ""

    return municipio, distrito, fy


# ═══════════════════════════════════════════════════
# Fase 1: Búsqueda HTML
# ═══════════════════════════════════════════════════

def _parse_search_results(html_text: str) -> list[dict]:
    """
    Parsea la tabla tblNueva del resultado de búsqueda.
    Retorna lista de dicts con metadata de cada hit.
    """
    soup = BeautifulSoup(html_text, "html.parser")
    table = soup.find("table", {"id": "tblNueva"})
    if not table:
        return []

    rows = table.find_all("tr")
    if len(rows) <= 1:
        return []

    out: list[dict] = []
    for tr in rows[1:]:
        tds = tr.find_all("td")
        if len(tds) < 6:
            continue

        a = tds[0].find("a", href=True)
        href = a["href"].strip() if a else ""
        href = href.replace("\\", "/")

        out.append({
            "href_pdf": href,
            "tipo_publicacion": _clean_text(_safe_text(tds[0])),
            "fecha_publicacion": _clean_text(_safe_text(tds[1])),
            "sumario": _clean_text(_safe_text(tds[2])),
            "tipo_documento": _clean_text(_safe_text(tds[3])),
            "sujeto_publica": _clean_text(_safe_text(tds[4])),
            "clasificacion_sujeto": _clean_text(_safe_text(tds[5])),
        })

    return out


def _search_year(session: requests.Session, year: int) -> tuple[list[dict], str]:
    """Busca leyes de ingresos para un año específico."""
    payload = dict(config.SEARCH_PAYLOAD_BASE)
    payload["c8"] = str(year)

    r = session.post(
        config.SEARCH_URL,
        data=payload,
        timeout=240,
        headers={"User-Agent": config.USER_AGENT},
    )
    r.raise_for_status()

    html_text = _decode_html_response(r)
    return _parse_search_results(html_text), html_text


# ═══════════════════════════════════════════════════
# Fase 2: Descarga de PDFs
# ═══════════════════════════════════════════════════

def _parse_year_month_from_href(href: str) -> tuple[str, str]:
    """
    href típico: files/2024/04/SEC16-13RA-2024-04-20.pdf
    """
    parts = href.strip("/").split("/")
    if (
        len(parts) >= 4
        and parts[0] == "files"
        and parts[1].isdigit()
        and parts[2].isdigit()
    ):
        return parts[1], parts[2]
    return "unknown", "unknown"


def _download_one(session: requests.Session, href: str, out_path: Path):
    """Descarga un PDF individual."""
    url = urljoin(config.BASE_URL, href)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with session.get(
        url,
        stream=True,
        timeout=config.REQUESTS_KWARGS["timeout"],
        headers={"User-Agent": config.USER_AGENT},
    ) as r:
        r.raise_for_status()
        with out_path.open("wb") as f:
            for chunk in r.iter_content(chunk_size=128 * 1024):
                if chunk:
                    f.write(chunk)


# ═══════════════════════════════════════════════════
# Heurísticas de imputación
# ═══════════════════════════════════════════════════

def _is_special_reference_row(hit: dict) -> bool:
    return (hit.get("municipio") or "") == "LEY GENERAL DE INGRESOS MUNICIPALES DEL ESTADO DE OAXACA"


def _sorted_hits_for_imputation(hits: list[dict]) -> list[dict]:
    def _key(h: dict):
        d = _parse_fecha_publicacion(h.get("fecha_publicacion", ""))
        return (
            int(h.get("year_query") or 0),
            d or date(1900, 1, 1),
            h.get("href_pdf", ""),
            int(h.get("_row_order") or 0),
        )
    return sorted(hits, key=_key)


def _impute_missing_ejercicio(hits: list[dict]) -> None:
    """
    Reglas conservadoras para imputar ejercicio_fiscal cuando el sumario no lo
    trae claramente:
      1) Si dentro del mismo href_pdf hay un único ejercicio conocido, usarlo.
      2) Si en la serie ordenada (fecha/href/orden) el ejercicio anterior y el
         posterior conocidos coinciden, imputar ese valor.
    """
    # 1) Por href_pdf
    by_href: dict[str, set[int]] = {}
    for h in hits:
        href = h.get("href_pdf", "")
        fy = h.get("ejercicio_fiscal")
        if href and isinstance(fy, int):
            by_href.setdefault(href, set()).add(fy)

    for h in hits:
        if h.get("ejercicio_fiscal"):
            continue
        href = h.get("href_pdf", "")
        values = by_href.get(href, set())
        if len(values) == 1:
            h["ejercicio_fiscal"] = next(iter(values))

    # 2) Por vecinos inmediatos con mismo ejercicio
    ordered = _sorted_hits_for_imputation(hits)
    prev_known: list[int | None] = [None] * len(ordered)
    next_known: list[int | None] = [None] * len(ordered)

    last: int | None = None
    for i, h in enumerate(ordered):
        fy = h.get("ejercicio_fiscal")
        prev_known[i] = last
        if isinstance(fy, int):
            last = fy

    last = None
    for i in range(len(ordered) - 1, -1, -1):
        fy = ordered[i].get("ejercicio_fiscal")
        next_known[i] = last
        if isinstance(fy, int):
            last = fy

    for i, h in enumerate(ordered):
        if h.get("ejercicio_fiscal"):
            continue
        if _is_special_reference_row(h):
            continue
        prev_fy = prev_known[i]
        next_fy = next_known[i]
        if prev_fy and next_fy and prev_fy == next_fy:
            h["ejercicio_fiscal"] = prev_fy


# ═══════════════════════════════════════════════════
# Pipeline principal
# ═══════════════════════════════════════════════════

def run_download(adapter) -> Path:
    """
    Ejecuta búsqueda + descarga para todos los años configurados.

    Returns:
        Path al CSV índice de PDFs descargados.
    """
    pdf_raw_dir = adapter.pdf_raw_dir
    meta_dir = adapter.meta_dir
    meta_dir.mkdir(parents=True, exist_ok=True)

    index_csv = meta_dir / "oaxaca_index.csv"
    search_dir = meta_dir / "busqueda_raw"
    search_dir.mkdir(parents=True, exist_ok=True)

    print("═══ Oaxaca: Descarga ═══")

    # ── Fase 1: Búsqueda por año ──
    all_hits: list[dict] = []
    unique_hrefs: set[str] = set()
    row_counter = 0

    with requests.Session() as session:
        # Inicializar sesión (PHPSESSID)
        session.get(
            config.SEARCH_URL,
            timeout=60,
            headers={"User-Agent": config.USER_AGENT},
        )

        for year in range(config.YEAR_MIN, config.YEAR_MAX + 1):
            print(f"  [{year}] Buscando leyes de ingresos...")
            try:
                hits, html_text = _search_year(session, year)

                # Guardar HTML bruto ya decodificado/limpio para depuración
                raw_path = search_dir / f"search_{year}.html"
                raw_path.write_text(html_text, encoding="utf-8")

                kept_this_year = 0
                for h in hits:
                    if not _should_keep_sumario(h.get("sumario", "")):
                        continue

                    h["year_query"] = year
                    h["_row_order"] = row_counter
                    row_counter += 1

                    mun, dist, fy = _extract_municipio_ejercicio(h.get("sumario", ""))
                    h["municipio"] = mun
                    h["distrito"] = dist
                    h["ejercicio_fiscal"] = fy if fy else ""

                    if h["href_pdf"] and h["href_pdf"].lower().endswith(".pdf"):
                        unique_hrefs.add(h["href_pdf"])

                    all_hits.append(h)
                    kept_this_year += 1

                print(f"    → {len(hits)} resultados brutos | {kept_this_year} conservados")
            except Exception as e:
                print(f"    ERROR: {e}")

            time.sleep(config.SLEEP_BETWEEN_REQUESTS)

        _impute_missing_ejercicio(all_hits)

        # ── Fase 2: Descarga ──
        print(f"\n  {len(unique_hrefs)} PDFs únicos para descargar")

        download_log: list[dict] = []
        for href in sorted(unique_hrefs):
            year_str, month_str = _parse_year_month_from_href(href)
            filename = href.strip("/").split("/")[-1]
            out_path = pdf_raw_dir / year_str / month_str / filename

            if out_path.exists() and out_path.stat().st_size > 0 and _looks_like_pdf(out_path):
                download_log.append({
                    "href": href,
                    "status": "skip_ok",
                    "filename": filename,
                    "year": year_str,
                    "sha256": _sha256_file(out_path),
                })
                continue

            ok = False
            for attempt in range(1, config.MAX_RETRIES + 1):
                try:
                    if out_path.exists():
                        out_path.unlink(missing_ok=True)
                    _download_one(session, href, out_path)
                    if _looks_like_pdf(out_path):
                        ok = True
                        break
                    raise RuntimeError("Downloaded file is not a valid PDF")
                except Exception as e:
                    if attempt < config.MAX_RETRIES:
                        time.sleep(1.5 * attempt)
                    else:
                        print(f"    ERROR descargando {filename}: {e}")
                        download_log.append({
                            "href": href,
                            "status": f"error:{e}",
                            "filename": filename,
                            "year": year_str,
                        })

            if ok:
                download_log.append({
                    "href": href,
                    "status": "ok",
                    "filename": filename,
                    "year": year_str,
                    "sha256": _sha256_file(out_path),
                })

            time.sleep(config.SLEEP_BETWEEN_REQUESTS)

    # ── Guardar índice ──
    index_fields = [
        "year_query", "ejercicio_fiscal", "municipio", "distrito",
        "fecha_publicacion", "href_pdf", "sumario",
        "tipo_publicacion", "tipo_documento",
    ]
    with index_csv.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=index_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_hits)

    n_ok = sum(1 for d in download_log if d["status"] in ("ok", "skip_ok"))
    n_missing_fy = sum(1 for h in all_hits if not h.get("ejercicio_fiscal"))
    n_missing_mun = sum(1 for h in all_hits if not h.get("municipio"))

    print(f"\n  Índice: {index_csv} ({len(all_hits)} filas)")
    print(f"  PDFs descargados: {n_ok}")
    print(f"  Sin ejercicio_fiscal: {n_missing_fy}")
    print(f"  Sin municipio: {n_missing_mun}")

    return index_csv
