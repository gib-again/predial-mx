"""
Descarga de PDFs del Periodico Oficial de Baja California.

Estrategia (1 ley por PDF, modelo SLP):
  1. Abrir sesion en /inicioConsulta.jsp para obtener la cookie JSESSIONID.
  2. Por cada municipio, buscar en el indice full-text del PO
     (palabra1="INGRESOS", palabra2=<clave del municipio>).
  3. Filtrar los resultados que son la Ley de Ingresos municipal real
     (no reformas, fe de erratas, acuerdos, presupuestos, decretos, etc.).
  4. Extraer el ejercicio fiscal del titulo y descargar el PDF (rutaDocumento
     -> CDN externo).

Notas de robustez:
  - El servidor (Tomcat viejo) RECHAZA el handshake TLS de Python/requests
    (ConnectionReset 10054); curl negocia bien. Por eso el transporte HTTP
    es curl via subprocess (cookie jar + decodificacion latin-1). curl viene
    incluido en Windows 10 1803+, macOS y Linux.
  - El titulo del indice intercala texto entre "LEY DE INGRESOS" y "DEL
    MUNICIPIO" (p.ej. Tecate "... Y TABLA DE VALORES CATASTRALES ... DEL
    MUNICIPIO DE TECATE"). El discriminador robusto: el texto ANTES de
    "LEY DE INGRESOS" no debe contener palabras de descarte (ACUERDO,
    DECRETO, FE DE ERRATA, REFORMA, PROYECTO, PRESUPUESTO, ...). Asi se
    permite el prefijo de legislatura/ayuntamiento y se descartan enmiendas.
  - El fraseo del ejercicio varia: "EJERCICIO FISCAL DE 2014",
    "... FISCAL DEL 2015", "... FISCAL 2023".

Archivos generados:
  data/bajacalifornia/pdf_raw/{ejercicio}/BC_RAW_{ejercicio}_{slug}.pdf
  data/bajacalifornia/meta/catalogo_leyes.csv
"""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.parse
from pathlib import Path

from src.estados.bajacalifornia import config


# ===================================================
# Filtros de titulo
# ===================================================

_RE_EJ = re.compile(
    r"EJERCICIO\s+FISCAL\s+(?:DEL?\s+)?(?:A[NÑ]O\s+)?(\d{4})",
    re.IGNORECASE,
)

# Palabras que, si aparecen ANTES de "LEY DE INGRESOS" en el titulo, indican
# que el documento NO es la ley sino una enmienda/derivado.
_DISQUALIFIERS = (
    "ACUERDO", "DECRETO", "PROYECTO", "PRESUPUESTO", "CUENTA",
    "FE DE ERRATA", "ERRATAS", "REFORMA", "CONDONA", "EXIME", "CONVENIO",
    "INFORME", "AVISO", "ADICIONA", "DEROGA", "DICTAMEN", "LINEAMIENTOS",
    "REGLAS", "REQUISITOS",
)


def _normalize(indice: str) -> str:
    """Colapsa espacios/saltos y pasa a mayusculas para el matching."""
    return " ".join((indice or "").upper().split())


def extraer_ejercicio_de_ley(indice: str) -> int | None:
    """Devuelve el ejercicio fiscal si el titulo es una Ley de Ingresos
    municipal real; None en caso contrario.

    Reglas:
      - Debe contener "LEY DE INGRESOS".
      - El texto antes de "LEY DE INGRESOS" no debe traer descalificadores.
      - Debe mencionar "MUNICIPIO".
      - Debe traer "EJERCICIO FISCAL <anio>".
    """
    U = _normalize(indice)
    pos = U.find("LEY DE INGRESOS")
    if pos < 0:
        return None
    before = U[:pos]
    if any(d in before for d in _DISQUALIFIERS):
        return None
    if "MUNICIPIO" not in U:
        return None
    m = _RE_EJ.search(U)
    if not m:
        return None
    return int(m.group(1))


# ===================================================
# Transporte HTTP (curl) — el servidor rechaza el TLS de requests
# ===================================================

class _CurlSession:
    """Sesion HTTP minima sobre curl con cookie jar (JSESSIONID)."""

    def __init__(self) -> None:
        if not shutil.which("curl"):
            raise RuntimeError(
                "curl no esta disponible en PATH. BC requiere curl porque el "
                "servidor del PO rechaza el handshake TLS de Python/requests. "
                "curl viene incluido en Windows 10 1803+, macOS y Linux."
            )
        self._tmp = tempfile.mkdtemp(prefix="bc_dl_")
        self.cookie_jar = str(Path(self._tmp) / "cookies.txt")
        # Abrir sesion (set JSESSIONID).
        self.get_bytes(config.SESSION_URL)

    def _base_cmd(self, max_time: int) -> list[str]:
        return [
            "curl", "-s", "-k",
            "-A", config.USER_AGENT,
            "-c", self.cookie_jar, "-b", self.cookie_jar,
            "--max-time", str(max_time),
        ]

    def get_bytes(self, url: str, extra_headers: dict | None = None) -> bytes:
        cmd = self._base_cmd(config.REQUESTS_KWARGS.get("timeout", 90))
        for k, v in (extra_headers or {}).items():
            cmd += ["-H", f"{k}: {v}"]
        cmd.append(url)
        return subprocess.run(cmd, capture_output=True).stdout

    def download_to(self, url: str, out_path: Path) -> bool:
        # Timeout amplio + reintentos: algunos tomos escaneados pesan ~50 MB y
        # el CDN es lento; --max-time 90 (busqueda) no alcanza.
        cmd = self._base_cmd(config.DOWNLOAD_TIMEOUT) + [
            "--retry", "2", "--retry-delay", "3",
            "-o", str(out_path), url,
        ]
        res = subprocess.run(cmd, capture_output=True)
        return res.returncode == 0 and out_path.exists()

    def close(self) -> None:
        shutil.rmtree(self._tmp, ignore_errors=True)


_SEARCH_HEADERS = {
    "X-Requested-With": "XMLHttpRequest",
    "Referer": config.SESSION_URL,
    "Accept": "application/json, text/javascript, */*; q=0.01",
}


def _search(session: _CurlSession, palabra1: str, palabra2: str) -> list[dict]:
    """Busca en el indice del PO. Devuelve la lista Data (decodificada latin-1)."""
    options = json.dumps({"take": 2000, "skip": 0, "page": 1, "pageSize": 2000, "sort": []})
    params = {
        "options": options,
        "indicePublico": "1",
        "fechaInicio": "",
        "fechaFin": "",
        "palabra1": palabra1,
        "palabra2": palabra2,
    }
    url = config.SEARCH_URL + "?" + urllib.parse.urlencode(params)
    try:
        raw = session.get_bytes(url, extra_headers=_SEARCH_HEADERS)
        if not raw:
            return []
        # El servidor envia latin-1 (acentos en nombres de seccion/archivo).
        data = json.loads(raw.decode("latin-1"))
        return data.get("Data", []) or []
    except Exception as e:
        print(f"    [WARN] error de busqueda '{palabra1}/{palabra2}': {e}")
        return []


def _normalize_ruta(ruta: str) -> str | None:
    """Re-codifica el query del CDN (nombreArchivo trae acentos/espacios)."""
    if not ruta:
        return None
    if "?" not in ruta:
        return ruta
    pre, q = ruta.split("?", 1)
    params = dict(urllib.parse.parse_qsl(q))
    return pre + "?" + urllib.parse.urlencode(params)


# ===================================================
# Descarga
# ===================================================

def _download_pdf(
    session: _CurlSession,
    ruta: str,
    ejercicio: int,
    slug: str,
    pdf_raw_dir: Path,
) -> tuple[Path, str]:
    carpeta = pdf_raw_dir / str(ejercicio)
    carpeta.mkdir(parents=True, exist_ok=True)
    nombre = f"{config.PREFIJO}_RAW_{ejercicio}_{slug}.pdf"
    ruta_out = carpeta / nombre
    if ruta_out.exists() and ruta_out.stat().st_size > 0:
        return ruta_out, "already_exists"

    url = _normalize_ruta(ruta)
    if not url:
        return ruta_out, "error:sin_url"
    try:
        ok = session.download_to(url, ruta_out)
        time.sleep(0.4)
        if not ok or not ruta_out.exists():
            ruta_out.unlink(missing_ok=True)
            return ruta_out, "error:descarga"
        # Validacion minima: PDF no vacio y con cabecera %PDF
        if ruta_out.stat().st_size < 1024:
            ruta_out.unlink(missing_ok=True)
            return ruta_out, "error:pdf_vacio"
        with ruta_out.open("rb") as f:
            if f.read(5) != b"%PDF-":
                ruta_out.unlink(missing_ok=True)
                return ruta_out, "error:no_es_pdf"
        return ruta_out, "ok"
    except Exception as e:
        ruta_out.unlink(missing_ok=True)
        return ruta_out, f"error:{type(e).__name__}"


# ===================================================
# Pipeline principal
# ===================================================

def run_download(adapter) -> Path:
    """Busca y descarga las Leyes de Ingresos municipales de BC.

    Returns:
        Path al CSV catalogo generado.
    """
    meta_dir = adapter.meta_dir
    pdf_raw_dir = adapter.pdf_raw_dir
    meta_dir.mkdir(parents=True, exist_ok=True)
    pdf_raw_dir.mkdir(parents=True, exist_ok=True)

    catalogo_csv = meta_dir / "catalogo_leyes.csv"
    session = _CurlSession()
    catalogo_rows: list[dict] = []

    print("=== Baja California: Descarga de PDFs del PO ===")
    print(f"    Ejercicios: {config.YEAR_MIN}-{config.YEAR_MAX}")

    for palabra2, slug in config.SEARCH_NAMES:
        data = _search(session, "INGRESOS", palabra2)
        if not data:
            print(f"  [{slug}] sin resultados")
            continue

        # Quedarnos con la ley real por ejercicio (la primera valida; las
        # republicaciones/correcciones se descartan por el filtro).
        por_ejercicio: dict[int, dict] = {}
        for r in data:
            ej = extraer_ejercicio_de_ley(r.get("indice"))
            if ej is None or ej < config.YEAR_MIN or ej > config.YEAR_MAX:
                continue
            if not r.get("rutaDocumento"):
                continue
            por_ejercicio.setdefault(ej, r)

        print(f"  [{slug}] {len(data)} resultados, {len(por_ejercicio)} leyes en rango")

        for ej in sorted(por_ejercicio):
            r = por_ejercicio[ej]
            ruta_out, status = _download_pdf(
                session, r["rutaDocumento"], ej, slug, pdf_raw_dir,
            )
            if status == "ok":
                print(f"    Descargado: {ruta_out.name}")
            elif status.startswith("error"):
                print(f"    ERROR {slug} {ej}: {status}")

            catalogo_rows.append({
                "ejercicio": ej,
                "slug": slug,
                "fecha_publicacion": r.get("fechaRegistro", ""),
                "seccion": r.get("seccion", ""),
                "pagina": r.get("pagina", ""),
                "folio": r.get("folio", ""),
                "nombre_documento": " ".join((r.get("indice") or "").split()),
                "status_descarga": status,
                "ruta_documento": r.get("rutaDocumento", ""),
            })

    # Guardar catalogo
    fieldnames = [
        "ejercicio", "slug", "fecha_publicacion", "seccion", "pagina",
        "folio", "nombre_documento", "status_descarga", "ruta_documento",
    ]
    with catalogo_csv.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(catalogo_rows)

    session.close()
    n_ok = sum(1 for r in catalogo_rows if r["status_descarga"] in ("ok", "already_exists"))
    print(f"\n  Catalogo: {catalogo_csv} ({len(catalogo_rows)} registros, {n_ok} PDFs)")
    return catalogo_csv
