"""scripts/sonora_classify_vision_multi.py — orquestador para PDFs problemáticos.

OBJETIVO
─────────
Para los PDFs de Sonora que NO produjeron JSONs válidos en la pipeline normal
(causa raíz: OCR degradado pre-2017, agrupados multi-municipio), corre una
extracción vision multi-municipio en una sola llamada por PDF y emite un JSON
individual por municipio en `predial-mx-v2/sonora/`.

PIPELINE
─────────
1. Lee inventario de "huecos" (qué CVEGEO×año no tienen JSON válido).
2. Cruza con inventario de PDFs disponibles para mapear (cve_mun, anio) → pdf_path.
3. Agrupa por PDF: {pdf_path: [(slug, cvegeo, anio), ...]}.
4. Para cada PDF: llama call_llm_vision_multi con la lista de municipios esperados.
5. Para cada item con encontrado=True y output válido: guarda
   `predial-mx-v2/sonora/SON_PREDIAL_{anio}_{slug}.json` con metadata.
6. Bitácora CSV en `data/sonora/meta/vision_multi_log.csv`.

IDEMPOTENCIA
────────────
Por defecto, no re-procesa PDFs ya en bitácora con `status=ok`. Override
con `--force-pdf <stem>` o `--force-all`.

NO sobrescribe JSONs existentes con `_meta.fuente in {txt, pdf_vision,
pdf_vision_multi}` válidos (i.e. `requiere_revision=False`). Sí sobrescribe
JSONs marcados como `requiere_revision=True`.

USO
────
  # Dry-run (lista qué PDFs se procesarían):
  python -m scripts.sonora_classify_vision_multi --dry-run

  # Procesar un PDF específico (debugging):
  python -m scripts.sonora_classify_vision_multi --pdf 2013CXCII50XIII

  # Procesar todo:
  python -m scripts.sonora_classify_vision_multi

  # Procesar todo, modelo full forzado (default ya es full):
  OPENAI_MODEL_FALLBACK=gpt-5.4 python -m scripts.sonora_classify_vision_multi

  # Cap absoluto de costo (aborta cuando se acumula):
  python -m scripts.sonora_classify_vision_multi --max-cost-usd 35

NOTAS PARA CODE
───────────────
Hay marcadores TODO[code] en lugares donde el nombre exacto de un archivo,
campo o función puede diferir en tu repo. Reemplázalos con los nombres reales.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from dotenv import load_dotenv
load_dotenv()

from src.core.llm_extract import (
    OPENAI_MODEL_FALLBACK,
    OUTPUT_ROOT,
    ROOT,
    call_llm_vision_multi,
)
from src.extraction.schema_v2 import OtroNoClasificadoSchema
from src.core.constants import PREFIJOS_ESTADO

# ─────────────────────────────────────────────────────────────────────────────
# Configuración
# ─────────────────────────────────────────────────────────────────────────────

ESTADO = "sonora"
ESTADO_PRETTY = "Sonora"
PREFIJO = PREFIJOS_ESTADO[ESTADO]  # típicamente "SON"

# TODO[code]: ajustar a las rutas reales de tu repo si difieren.
META_DIR = ROOT / "data" / ESTADO / "meta"
DISCOVERED_LAWS = META_DIR / "discovered_laws.csv"
SEGMENT_AUDIT = META_DIR / "segment_audit.csv"
VISION_LOG = META_DIR / "vision_multi_log.csv"

# Directorio donde están los PDFs canónicos (después de OCR y consolidate).
# TODO[code]: ajusta a tu estructura real. Probablemente:
PDF_OCR_DIR = ROOT / "data" / ESTADO / "pdf_ocr"
PDF_RAW_DIR = ROOT / "data" / ESTADO / "pdf_raw"

# Directorio de salida de JSONs (heredado de llm_extract_v2)
OUT_DIR = OUTPUT_ROOT / ESTADO

# Costos aproximados (USD por 1M tokens) — para tracking, no para enforcement
# del API. Ajusta cuando cambien.
PRICE_INPUT_PER_1M = float(os.environ.get("PRICE_INPUT_PER_1M", "2.50"))
PRICE_OUTPUT_PER_1M = float(os.environ.get("PRICE_OUTPUT_PER_1M", "10.00"))

# Throttle entre llamadas (segundos)
SLEEP_BETWEEN_CALLS = float(os.environ.get("VISION_MULTI_SLEEP", "1.0"))

# Cobertura objetivo
ANIOS_OBJETIVO = list(range(2010, 2026))  # 16 años

# ─────────────────────────────────────────────────────────────────────────────
# Estructuras
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Hueco:
    """Un (cve_mun, anio) que necesita procesarse."""
    cvegeo: str           # 5 dígitos, "26002" etc.
    anio: int
    slug: str
    nombre: str
    pdf_path: Path | None = None  # se llena en mapping
    pdf_stem: str | None = None


@dataclass
class PdfBatch:
    """Un PDF con la lista de municipios a buscarle."""
    pdf_path: Path
    pdf_stem: str
    items: list[Hueco] = field(default_factory=list)


@dataclass
class LogRow:
    """Una fila de la bitácora vision_multi_log.csv."""
    timestamp: str
    pdf_stem: str
    pdf_path: str
    n_munis_pedidos: int
    n_munis_encontrados: int
    n_munis_validos: int       # encontrados Y no otro_no_clasificado
    status: str                # ok | partial | api_error | validation_error | render_failed
    modelo: str
    tokens_in: int
    tokens_out: int
    tokens_cached: int
    cost_usd: float
    n_imagenes: int
    elapsed_sec: float
    error: str = ""
    slugs_encontrados: str = ""    # ";" join
    slugs_no_encontrados: str = "" # ";" join


# ─────────────────────────────────────────────────────────────────────────────
# Carga de inputs
# ─────────────────────────────────────────────────────────────────────────────

def _cargar_huecos() -> list[Hueco]:
    """Identifica los (cve_mun, anio) que faltan o requieren revisión.

    Estrategia:
      1. Cargar grid completo: 72 munis × 16 años = 1152 filas esperadas.
      2. Para cada (cvegeo, anio), mirar si existe el JSON correspondiente
         en `predial-mx-v2/sonora/{PREFIJO}_PREDIAL_{anio}_{slug}.json`.
      3. Si NO existe, o existe con `_meta_v2.requiere_revision=True`, es un
         hueco a procesar.

    NOTA[code]: este helper depende de tu inventario INEGI. Si tienes una
    función `cargar_municipios_estado(estado_cve='26')` reúsala. Si no,
    lee directamente `catalogs/municipios_inegi.csv` filtrando CVE_ENT=26.
    """
    # TODO[code]: reemplazar con tu loader real de los 72 municipios.
    # Estructura esperada: list[dict] con keys CVEGEO, NOM_MUN, slug.
    munis_son = _cargar_municipios_sonora()

    # Esquemas que consideramos válidos para event-study (NO huecos).
    # Excluimos `desconocido` y `otro_no_clasificado` (limpiados previamente).
    TIPOS_VALIDOS = {
        "tarifa_millar", "progresivo", "tasa_unica",
        "cuota_fija_simple", "cuota_fija_escalonada", "mixto",
    }

    huecos: list[Hueco] = []
    for muni in munis_son:
        cvegeo = str(muni["CVEGEO"]).zfill(5)
        slug = muni["slug"]
        nombre = muni["NOM_MUN"]
        for anio in ANIOS_OBJETIVO:
            archivo = OUT_DIR / f"{PREFIJO}_PREDIAL_{anio}_{slug}.json"
            if not archivo.exists():
                huecos.append(Hueco(cvegeo=cvegeo, anio=anio, slug=slug, nombre=nombre))
                continue
            try:
                payload = json.loads(archivo.read_text(encoding="utf-8"))
            except Exception:
                huecos.append(Hueco(cvegeo=cvegeo, anio=anio, slug=slug, nombre=nombre))
                continue
            # Criterio: si el JSON ya tiene un tipo_esquema válido (entre los 6
            # esperados), NO es hueco — sin importar `requiere_revision` (que
            # los `reclasified_v1[*]` no setean explícitamente, default True).
            pred = payload.get("predial") or {}
            tipo = pred.get("tipo_esquema")
            if tipo in TIPOS_VALIDOS:
                continue
            # Caso contrario (predial vacío, tipo_esquema='desconocido' u
            # 'otro_no_clasificado'): hueco a re-procesar.
            huecos.append(Hueco(cvegeo=cvegeo, anio=anio, slug=slug, nombre=nombre))
    return huecos


def _cargar_municipios_sonora() -> list[dict]:
    """Lee los 72 municipios de Sonora desde el catálogo INEGI."""
    # TODO[code]: si tienes un helper centralizado para esto, úsalo.
    catalog = ROOT / "catalogs" / "municipios_inegi.csv"
    munis = []
    # IMPORTACIÓN diferida para evitar circular si está en otro modulo
    from src.core.text_utils import slugify
    with catalog.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            if row.get("CVE_ENT") == "26":  # Sonora
                munis.append({
                    "CVEGEO": str(row["CVEGEO"]).zfill(5),
                    "NOM_MUN": row["NOM_MUN"],
                    "slug": slugify(row["NOM_MUN"]),
                })
    if len(munis) != 72:
        print(f"[WARN] Esperaba 72 munis Sonora, obtuve {len(munis)}", file=sys.stderr)
    return munis


def _mapear_pdfs(huecos: list[Hueco]) -> list[Hueco]:
    """Para cada hueco, encuentra el PDF correspondiente (si existe).

    Estrategia:
      1. Indexar `discovered_laws.csv` por (cvegeo, anio_fiscal). Columnas
         reales: anio_fiscal, municipio_slug, cve_mun, municipio_raw,
         numero_ley, documento_url, regimen, page_start, page_end.
         Construir cvegeo = "26" + cve_mun.zfill(3).
      2. Derivar pdf_stem del documento_url (último componente sin .pdf).
      3. Probar `pdf_ocr/{anio_pub}/{stem}_ocr.pdf` y `pdf_raw/{anio_pub}/{stem}.pdf`
         con anio_pub ∈ {anio-1, anio, anio-2, prefix(stem)}.
    """
    if not DISCOVERED_LAWS.exists():
        print(f"[ERROR] No existe {DISCOVERED_LAWS}", file=sys.stderr)
        return huecos

    # Index discovered_laws por (cvegeo, anio_fiscal)
    discovered: dict[tuple[str, int], dict] = {}
    with DISCOVERED_LAWS.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            try:
                cve_mun = str(row.get("cve_mun") or "").strip().zfill(3)
                if not cve_mun:
                    continue
                cvegeo = f"26{cve_mun}"
                anio_fiscal = int(row.get("anio_fiscal") or 0)
            except (ValueError, TypeError):
                continue
            if not anio_fiscal:
                continue
            # Si hay múltiples leyes para el mismo (cvegeo, anio), conservar la
            # primera (suele ser la principal). Override con --pdf si se necesita
            # otra.
            discovered.setdefault((cvegeo, anio_fiscal), row)

    # Resolver PDF para cada hueco
    for h in huecos:
        row = discovered.get((h.cvegeo, h.anio))
        if not row:
            continue

        url = (row.get("documento_url") or "").strip()
        if not url:
            continue
        # Derivar stem del URL: ".../2013CXCII50XIII.pdf" → "2013CXCII50XIII"
        # También maneja URLs sin .pdf y query strings.
        pdf_basename = Path(url.split("?")[0]).name
        if pdf_basename.endswith(".pdf"):
            pdf_stem = pdf_basename[:-4]
        else:
            pdf_stem = pdf_basename
        if not pdf_stem:
            continue

        # anio_pub: probar varios candidatos en orden de probabilidad.
        # Prefijo del stem (los primeros 4 dígitos del nombre canónico tipo
        # "2013CXCII50XIII") suele ser el año de publicación.
        anio_pub_candidates: list[str] = []
        try:
            anio_pub_candidates.append(str(int(pdf_stem[:4])))
        except (ValueError, IndexError):
            pass
        anio_pub_candidates.extend([
            str(h.anio - 1),
            str(h.anio),
            str(h.anio - 2),
        ])
        # Dedup conservando orden
        seen_ap: set[str] = set()
        anio_pub_candidates = [
            ap for ap in anio_pub_candidates
            if not (ap in seen_ap or seen_ap.add(ap))
        ]

        # Buscar PDF físico (OCR primero, luego raw)
        for ap in anio_pub_candidates:
            for candidate in [
                PDF_OCR_DIR / ap / f"{pdf_stem}_ocr.pdf",
                PDF_RAW_DIR / ap / f"{pdf_stem}.pdf",
            ]:
                if candidate.exists():
                    h.pdf_path = candidate
                    h.pdf_stem = pdf_stem
                    break
            if h.pdf_path is not None:
                break

    return huecos


def _agrupar_por_pdf(huecos: list[Hueco]) -> list[PdfBatch]:
    """Agrupa los huecos resueltos por su pdf_path."""
    by_stem: dict[str, PdfBatch] = {}
    for h in huecos:
        if h.pdf_path is None or h.pdf_stem is None:
            continue
        if h.pdf_stem not in by_stem:
            by_stem[h.pdf_stem] = PdfBatch(pdf_path=h.pdf_path, pdf_stem=h.pdf_stem)
        by_stem[h.pdf_stem].items.append(h)
    return list(by_stem.values())


# ─────────────────────────────────────────────────────────────────────────────
# Bitácora
# ─────────────────────────────────────────────────────────────────────────────

LOG_FIELDS = [
    "timestamp", "pdf_stem", "pdf_path",
    "n_munis_pedidos", "n_munis_encontrados", "n_munis_validos",
    "status", "modelo",
    "tokens_in", "tokens_out", "tokens_cached", "cost_usd",
    "n_imagenes", "elapsed_sec", "error",
    "slugs_encontrados", "slugs_no_encontrados",
]


def _cargar_log_existente() -> dict[str, dict]:
    """Lee la bitácora si existe. Devuelve {pdf_stem: ultima_fila}."""
    if not VISION_LOG.exists():
        return {}
    out: dict[str, dict] = {}
    with VISION_LOG.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            stem = row.get("pdf_stem", "")
            if stem:
                out[stem] = row  # última escritura gana
    return out


def _append_log(row: LogRow) -> None:
    VISION_LOG.parent.mkdir(parents=True, exist_ok=True)
    is_new = not VISION_LOG.exists()
    with VISION_LOG.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=LOG_FIELDS, extrasaction="ignore")
        if is_new:
            writer.writeheader()
        writer.writerow(asdict(row))


# ─────────────────────────────────────────────────────────────────────────────
# Guardado de JSONs individuales (formato compatible con extraer_municipio)
# ─────────────────────────────────────────────────────────────────────────────

def _guardar_json_municipio(
    *,
    item,                      # VisionMultiItem (no podemos type-hint sin import circular)
    cvegeo: str,
    anio: int,
    nombre: str,
    pdf_stem: str,
    modelo: str,
    tokens: dict,
    elapsed_sec: float,
) -> Path | None:
    """Guarda un JSON individual con la misma estructura que extraer_municipio.

    Solo guarda si el item está completo (encontrado=True, output presente,
    output.predial validable). Si está incompleto, devuelve None (el orquestador
    lo refleja en la bitácora).
    """
    if not item.encontrado or item.output is None:
        return None

    archivo = OUT_DIR / f"{PREFIJO}_PREDIAL_{anio}_{item.slug}.json"
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # En nuestra integración, item.output ya es un dict (validado y re-dumpeado
    # en call_llm_vision_multi). Trabajamos directo con el dict.
    payload = dict(item.output) if isinstance(item.output, dict) else \
        item.output.model_dump(by_alias=True, mode="json", exclude_none=False)

    pred = payload.get("predial") or {}
    tipo = pred.get("tipo_esquema") if isinstance(pred, dict) else None
    is_otro = (tipo == "otro_no_clasificado")
    requiere_revision = is_otro

    payload["_meta"] = {
        "fuente": "pdf_vision_multi",
        "modelo": modelo,
    }
    payload["_meta_v2"] = {
        "intentos": 1,
        "requiere_revision": requiere_revision,
        "escalado": True,                # vision multi siempre usa modelo full por default
        "razon": ("clasificado_como_otro_no_clasificado" if is_otro else
                  "rescate_via_vision_multi"),
        "usado_reocr": False,
        "usado_vision": True,
        "usado_vision_multi": True,
        "tokens": tokens,
        "cvegeo": cvegeo,
        "estado": ESTADO,
        "anio": anio,
        "pdf_stem": pdf_stem,
        "elapsed_sec_pdf": elapsed_sec,  # tiempo del batch del PDF, no por muni
        "razon_no_encontrado": item.razon_no_encontrado,
    }

    archivo.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    return archivo


# ─────────────────────────────────────────────────────────────────────────────
# Procesamiento de un PDF
# ─────────────────────────────────────────────────────────────────────────────

def _procesar_batch(batch: PdfBatch, *, dry_run: bool = False) -> LogRow:
    """Procesa un PdfBatch: 1 llamada vision multi → N JSONs guardados."""
    pedido_munis = [{"slug": h.slug, "nombre": h.nombre} for h in batch.items]
    pedido_anios = sorted({h.anio for h in batch.items})

    # Si todos los huecos del batch tienen el mismo año fiscal, lo usamos.
    # Si no, ATENCIÓN: la vision_multi expects un anio por llamada. En la
    # práctica, los huecos de un mismo PDF SÍ comparten anio fiscal porque
    # un boletín cubre 1 ejercicio fiscal. Si encuentras un PDF con huecos
    # de varios años, hay un bug en discovered_laws — investigar.
    if len(pedido_anios) != 1:
        msg = f"PDF {batch.pdf_stem} tiene huecos de años múltiples: {pedido_anios}"
        print(f"[WARN] {msg}", file=sys.stderr)
        # En este caso, procesa el año más frecuente y deja los demás para
        # otra corrida.
        from collections import Counter
        anio = Counter(h.anio for h in batch.items).most_common(1)[0][0]
        batch.items = [h for h in batch.items if h.anio == anio]
        pedido_munis = [{"slug": h.slug, "nombre": h.nombre} for h in batch.items]
    else:
        anio = pedido_anios[0]

    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")

    if dry_run:
        return LogRow(
            timestamp=timestamp,
            pdf_stem=batch.pdf_stem,
            pdf_path=str(batch.pdf_path),
            n_munis_pedidos=len(pedido_munis),
            n_munis_encontrados=0,
            n_munis_validos=0,
            status="dry_run",
            modelo="—",
            tokens_in=0, tokens_out=0, tokens_cached=0, cost_usd=0.0,
            n_imagenes=0, elapsed_sec=0.0,
            slugs_encontrados="", slugs_no_encontrados="",
        )

    # Llamada
    t0 = time.monotonic()
    call = call_llm_vision_multi(
        pdf_path=batch.pdf_path,
        estado_pretty=ESTADO_PRETTY,
        anio=anio,
        municipios=pedido_munis,
    )
    elapsed = time.monotonic() - t0

    cost_usd = (
        call.tokens_in * (PRICE_INPUT_PER_1M / 1_000_000)
        + call.tokens_out * (PRICE_OUTPUT_PER_1M / 1_000_000)
    )

    if call.output is None:
        return LogRow(
            timestamp=timestamp,
            pdf_stem=batch.pdf_stem, pdf_path=str(batch.pdf_path),
            n_munis_pedidos=len(pedido_munis),
            n_munis_encontrados=0, n_munis_validos=0,
            status="error", modelo=call.modelo,
            tokens_in=call.tokens_in, tokens_out=call.tokens_out,
            tokens_cached=call.tokens_cached, cost_usd=cost_usd,
            n_imagenes=call.n_imagenes, elapsed_sec=elapsed,
            error=call.error or "unknown",
        )

    # Index por slug — fallback robusto
    items_by_slug = {it.slug: it for it in call.output.resultados}

    # Validar cobertura
    slugs_pedidos = {h.slug for h in batch.items}
    slugs_recibidos = set(items_by_slug.keys())
    slugs_faltantes = slugs_pedidos - slugs_recibidos
    slugs_extra = slugs_recibidos - slugs_pedidos
    if slugs_extra:
        # El modelo devolvió slugs no pedidos — los ignoramos pero los logueamos.
        print(f"[WARN] {batch.pdf_stem}: slugs no solicitados ignorados: "
              f"{sorted(slugs_extra)}", file=sys.stderr)

    # Guardar JSONs
    n_encontrados = 0
    n_validos = 0
    encontrados_list: list[str] = []
    no_encontrados_list: list[str] = []

    cvegeo_by_slug = {h.slug: h.cvegeo for h in batch.items}
    nombre_by_slug = {h.slug: h.nombre for h in batch.items}

    tokens_dict = {
        "input": call.tokens_in,
        "output": call.tokens_out,
        "cached": call.tokens_cached,
    }

    for slug in slugs_pedidos:
        item = items_by_slug.get(slug)
        if item is None:
            no_encontrados_list.append(f"{slug}:no_response")
            continue
        if not item.encontrado or item.output is None:
            no_encontrados_list.append(
                f"{slug}:{item.razon_no_encontrado or 'no_output'}"
            )
            continue
        n_encontrados += 1
        guardado = _guardar_json_municipio(
            item=item,
            cvegeo=cvegeo_by_slug[slug],
            anio=anio,
            nombre=nombre_by_slug[slug],
            pdf_stem=batch.pdf_stem,
            modelo=call.modelo,
            tokens=tokens_dict,
            elapsed_sec=elapsed,
        )
        if guardado:
            # item.output es dict en nuestra integración (validado en call_llm_vision_multi)
            pred = (item.output or {}).get("predial") or {}
            is_otro = (pred.get("tipo_esquema") == "otro_no_clasificado")
            if not is_otro:
                n_validos += 1
            encontrados_list.append(slug)

    status = (
        "ok" if (n_validos == len(slugs_pedidos))
        else "partial" if (n_validos > 0)
        else "no_validos"
    )

    return LogRow(
        timestamp=timestamp,
        pdf_stem=batch.pdf_stem, pdf_path=str(batch.pdf_path),
        n_munis_pedidos=len(pedido_munis),
        n_munis_encontrados=n_encontrados,
        n_munis_validos=n_validos,
        status=status, modelo=call.modelo,
        tokens_in=call.tokens_in, tokens_out=call.tokens_out,
        tokens_cached=call.tokens_cached, cost_usd=cost_usd,
        n_imagenes=call.n_imagenes, elapsed_sec=elapsed,
        slugs_encontrados=";".join(sorted(encontrados_list)),
        slugs_no_encontrados=";".join(sorted(no_encontrados_list)),
    )


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--dry-run", action="store_true",
                        help="Lista los PDFs que se procesarían sin llamar al modelo.")
    parser.add_argument("--pdf", type=str, default=None,
                        help="Procesar SOLO este pdf_stem (debugging).")
    parser.add_argument("--force-pdf", type=str, default=None,
                        help="Re-procesar este pdf_stem aunque ya esté en bitácora.")
    parser.add_argument("--force-all", action="store_true",
                        help="Re-procesar TODO sin importar bitácora.")
    parser.add_argument("--max-cost-usd", type=float, default=50.0,
                        help="Cap absoluto. Aborta si se acumula. Default 50.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Procesar a lo más N PDFs (debugging).")
    parser.add_argument("--shard", type=str, default=None,
                        help="Procesar solo el shard N/T (ej. 0/4, 1/4, ...). "
                             "Reparte PDFs por hash(pdf_stem) % T == N. Cada "
                             "shard escribe su propia bitácora "
                             "vision_multi_log.s{N}of{T}.csv para evitar "
                             "race conditions; al final consolida con `cat`.")
    args = parser.parse_args(argv)

    # Sharding: separar bitácora por shard si aplica
    shard_n: int | None = None
    shard_t: int | None = None
    global VISION_LOG
    if args.shard:
        try:
            sn, st = args.shard.split("/", 1)
            shard_n = int(sn)
            shard_t = int(st)
            if shard_n < 0 or shard_n >= shard_t or shard_t < 1:
                raise ValueError
        except (ValueError, TypeError):
            parser.error(f"--shard debe ser N/T con 0<=N<T (recibido: {args.shard!r})")
        # Cada shard escribe a su propio log para evitar race conditions
        VISION_LOG = META_DIR / f"vision_multi_log.s{shard_n}of{shard_t}.csv"
        print(f"[info] shard {shard_n}/{shard_t} → bitácora {VISION_LOG.name}")

    print(f"[info] cargando huecos de Sonora...")
    huecos = _cargar_huecos()
    print(f"[info] {len(huecos)} huecos identificados")

    huecos = _mapear_pdfs(huecos)
    sin_pdf = sum(1 for h in huecos if h.pdf_path is None)
    print(f"[info] {sin_pdf} huecos sin PDF asociado (no procesables aquí)")

    batches = _agrupar_por_pdf(huecos)
    print(f"[info] {len(batches)} PDFs únicos a procesar "
          f"(cubren {sum(len(b.items) for b in batches)} huecos)")

    # Idempotencia: cargar log GLOBAL + log del shard (si aplica) y unionar.
    # Los PDFs procesados con status=ok en CUALQUIER log se saltan.
    log_existente = _cargar_log_existente()  # log del shard actual (o global)
    if shard_t is not None:
        # Cargar también el log "global" (vision_multi_log.csv) y los logs de
        # otros shards, para evitar re-procesar PDFs que ya completó otra
        # corrida o el batch original sin sharding.
        global_log_path = META_DIR / "vision_multi_log.csv"
        if global_log_path.exists():
            with global_log_path.open(encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    stem = row.get("pdf_stem", "")
                    if stem and (stem not in log_existente or row.get("status") == "ok"):
                        log_existente[stem] = row
        # Otros shards
        for other in range(shard_t):
            if other == shard_n:
                continue
            p = META_DIR / f"vision_multi_log.s{other}of{shard_t}.csv"
            if p.exists():
                with p.open(encoding="utf-8-sig", newline="") as f:
                    for row in csv.DictReader(f):
                        stem = row.get("pdf_stem", "")
                        if stem and (stem not in log_existente or row.get("status") == "ok"):
                            log_existente[stem] = row

    # Aplicar shard ANTES de filtros de idempotencia: solo este shard procesa
    # los PDFs cuyo hash_estable(pdf_stem) % shard_t == shard_n.
    # Importante: usar hashlib (estable entre procesos) NO el hash() builtin
    # de Python que tiene PYTHONHASHSEED random.
    if shard_t is not None:
        import hashlib
        before_n = len(batches)
        def _shard_of(stem: str) -> int:
            h = hashlib.sha1(stem.encode("utf-8")).hexdigest()
            return int(h[:8], 16) % shard_t
        batches = [b for b in batches if _shard_of(b.pdf_stem) == shard_n]
        print(f"[info] shard {shard_n}/{shard_t}: {len(batches)} de {before_n} PDFs en este shard")

    # Filtrar
    if args.pdf:
        batches = [b for b in batches if b.pdf_stem == args.pdf]
    elif not args.force_all:
        # Idempotencia: skip los ya en log con status=ok (a menos que --force-pdf)
        def keep(b: PdfBatch) -> bool:
            if args.force_pdf and b.pdf_stem == args.force_pdf:
                return True
            prev = log_existente.get(b.pdf_stem)
            if prev and prev.get("status") == "ok":
                return False
            return True
        batches = [b for b in batches if keep(b)]
        print(f"[info] {len(batches)} PDFs después de aplicar idempotencia")

    if args.limit:
        batches = batches[:args.limit]
        print(f"[info] limitado a {len(batches)} PDFs")

    if args.dry_run:
        print("[dry-run] PDFs que se procesarían:")
        for b in batches:
            slugs = ",".join(h.slug for h in b.items)
            print(f"  {b.pdf_stem}  ({len(b.items)} munis: {slugs})")
        return 0

    cost_acum = 0.0
    n_ok = 0
    n_partial = 0
    n_error = 0

    for i, batch in enumerate(batches, 1):
        if cost_acum > args.max_cost_usd:
            print(f"[abort] costo acumulado ${cost_acum:.2f} > cap "
                  f"${args.max_cost_usd:.2f}", file=sys.stderr)
            break

        print(f"\n[{i}/{len(batches)}] {batch.pdf_stem}  "
              f"({len(batch.items)} munis)")
        try:
            row = _procesar_batch(batch)
        except KeyboardInterrupt:
            print("\n[abort] interrumpido por usuario", file=sys.stderr)
            break
        except Exception as e:
            row = LogRow(
                timestamp=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                pdf_stem=batch.pdf_stem, pdf_path=str(batch.pdf_path),
                n_munis_pedidos=len(batch.items),
                n_munis_encontrados=0, n_munis_validos=0,
                status="exception", modelo="—",
                tokens_in=0, tokens_out=0, tokens_cached=0, cost_usd=0.0,
                n_imagenes=0, elapsed_sec=0.0,
                error=f"{type(e).__name__}: {e}",
            )

        _append_log(row)
        cost_acum += row.cost_usd
        if row.status == "ok":
            n_ok += 1
        elif row.status == "partial":
            n_partial += 1
        else:
            n_error += 1

        print(f"  status={row.status}  encontrados={row.n_munis_encontrados}/"
              f"{row.n_munis_pedidos}  validos={row.n_munis_validos}  "
              f"tokens(in={row.tokens_in}, out={row.tokens_out})  "
              f"cost=${row.cost_usd:.3f}  elapsed={row.elapsed_sec:.1f}s")
        if row.error:
            print(f"  error: {row.error}")

        time.sleep(SLEEP_BETWEEN_CALLS)

    print(f"\n=== Resumen ===")
    print(f"PDFs procesados:  {n_ok + n_partial + n_error}")
    print(f"  ok:             {n_ok}")
    print(f"  partial:        {n_partial}")
    print(f"  error:          {n_error}")
    print(f"Costo acumulado:  ${cost_acum:.2f} USD")
    print(f"Bitácora:         {VISION_LOG}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
