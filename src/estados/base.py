"""
Clase abstracta que define la interfaz de un adaptador de estado.

Cada estado implementa:
  - download()               → Descarga PDFs del Periódico Oficial
  - build_master()           → Construye el master (municipio, año) → PDF, páginas
  - extract_predial_sections() → Localiza sección predial, genera TXT + PDF recortados

Los pasos compartidos (OCR, LLM, validación) están implementados aquí
y usan la lógica de src/core/.

Convención de directorios:
  data/{estado}/
  ├── pdf_raw/{año}/{PREFIJO}_RAW_{año}_{slug}[_extra].pdf
  ├── pdf_ocr/{año}/{PREFIJO}_RAW_{año}_{slug}_ocr.pdf        ← OCR skip
  │            {año}/{PREFIJO}_RAW_{año}_{slug}_forceocr.pdf   ← OCR force
  ├── focus_predial/{año}/{PREFIJO}_PREDIAL_{año}_{slug}.txt
  │                 {año}/{PREFIJO}_PREDIAL_{año}_{slug}.pdf
  ├── json_predial/{año}/{PREFIJO}_PREDIAL_{año}_{slug}.json
  ├── meta/          ← CSVs de bitácora, índice, batch IDs
  └── qa/            ← Reportes de validación

Reglas:
  - pdf_raw/ solo contiene originales descargados (nunca OCR)
  - pdf_ocr/ es SOLO para estados con needs_ocr=True
  - Los nombres SIEMPRE siguen {PREFIJO}_{tipo}_{año}_{slug}[_sufijo].ext
  - El slug se genera con src.core.text_utils.slugify()
  - La estructura por año es plana (no anidada por municipio)
"""

from abc import ABC, abstractmethod
from pathlib import Path

from src.core.constants import EJERCICIO_INI, EJERCICIO_FIN


class EstadoAdapter(ABC):

    # ── Propiedades abstractas (cada estado las define) ──

    @property
    @abstractmethod
    def slug(self) -> str:
        """Identificador del estado. Ej: 'coahuila'"""

    @property
    @abstractmethod
    def prefijo(self) -> str:
        """Prefijo para nombres de archivo. Ej: 'COAH'"""

    @property
    def estado_nombre(self) -> str:
        """Nombre legible del estado. Default: slug capitalizado."""
        return self.slug.capitalize()

    # ── Propiedades con defaults (override si es necesario) ──

    @property
    def ejercicio_range(self) -> range:
        """Rango de ejercicios fiscales. Override si un estado tiene rango distinto."""
        return range(EJERCICIO_INI, EJERCICIO_FIN + 1)

    @property
    def needs_ocr(self) -> bool:
        """True si el estado tiene PDFs escaneados que requieren OCR."""
        return False

    # ── Rutas derivadas (consistentes para todos los estados) ──

    @property
    def data_dir(self) -> Path:
        return Path(f"data/{self.slug}")

    @property
    def pdf_raw_dir(self) -> Path:
        return self.data_dir / "pdf_raw"

    @property
    def pdf_ocr_dir(self) -> Path:
        return self.data_dir / "pdf_ocr"

    @property
    def meta_dir(self) -> Path:
        return self.data_dir / "meta"

    @property
    def focus_dir(self) -> Path:
        return self.data_dir / "focus_predial"

    @property
    def json_dir(self) -> Path:
        return self.data_dir / "json_predial"

    @property
    def qa_dir(self) -> Path:
        return self.data_dir / "qa"

    # ── Métodos abstractos (específicos por estado) ──

    @abstractmethod
    def download(self) -> Path:
        """
        Descarga PDFs del Periódico Oficial.
        Retorna: ruta al CSV índice de leyes descargadas.
        """

    @abstractmethod
    def build_master(self) -> Path:
        """
        Construye master CSV: (municipio, año) → PDF, páginas de la ley.
        Retorna: ruta al master CSV.
        """

    @abstractmethod
    def extract_predial_sections(self, **kwargs) -> Path:
        """
        Localiza sección de predial en cada ley, genera TXT y PDF recortados.

        Acepta kwargs específicos por estado (ej. year) para que el dispatcher
        del CLI sea uniforme; las implementaciones que no los usen pueden
        ignorarlos.

        Retorna: ruta al CSV bitácora de secciones.
        """

    # ── Métodos concretos (compartidos, usan core/) ──

    def run_ocr(self, **kwargs):
        """
        Aplica OCR a PDFs escaneados. Solo si needs_ocr=True.

        Acepta y descarta kwargs específicos por estado (ej. year, force_reocr,
        clean_watermark) para que el dispatcher del CLI sea uniforme.
        """
        if not self.needs_ocr:
            print(f"  [{self.slug}] OCR no requerido, saltando.")
            return
        from src.core.ocr import process_directory
        process_directory(self.pdf_raw_dir, self.pdf_ocr_dir)

    def run_llm_extraction(self, batch_mode: bool = False, force: bool = False, **kwargs):
        """Extracción v3 (schema_v3) para cada caso del segment.csv canónico.

        Itera ``meta/segment.csv`` (status=ok, con cvegeo) y llama
        ``extraer_municipio`` por (cvegeo, años).  Salta los casos que ya tienen
        JSON v3 no vacío (canónico u overlay HITL) salvo ``force=True``, para no
        re-gastar API.  Escribe en ``data/{estado}/json_predial/{anio}/``.
        """
        import json as _json
        from collections import defaultdict

        from src.core.corpus import resolve_json
        from src.core.segment_schema import STATUS_OK, read_segment_csv
        from src.extraction.llm_extract_v3 import extraer_municipio

        if batch_mode:
            # Batch API (−50%, asíncrono): crea + sube.  La descarga es aparte
            # (hasta 24 h después): python -m scripts.batch_v3 {estado} --download
            from src.extraction.batch_v3 import submit_estado
            ids = submit_estado(self.slug)
            print(f"  [{self.slug}] batch enviado ({len(ids)} sub-batches). "
                  f"Descargar luego: python -m scripts.batch_v3 {self.slug} --download")
            return

        seg_path = self.meta_dir / "segment.csv"
        seg_rows = read_segment_csv(seg_path)
        if not seg_rows:
            print(f"  [{self.slug}] sin segment.csv (¿estado hardcoded?). Nada que extraer LLM.")
            return

        def _existe_no_vacio(anio: int, slug: str) -> bool:
            p = resolve_json(self.slug, anio, slug)
            if not p:
                return False
            try:
                return (_json.loads(p.read_text(encoding="utf-8")).get("predial")) is not None
            except Exception:
                return False

        # Agrupar años por cvegeo (un solo extraer_municipio por municipio).
        por_cvegeo: dict[str, dict] = defaultdict(lambda: {"slug": "", "anios": []})
        n_total = n_skip = 0
        for r in seg_rows:
            if (r.get("status") or "") != STATUS_OK:
                continue
            cvegeo = (r.get("cvegeo") or "").strip()
            try:
                anio = int(r.get("anio") or 0)
            except ValueError:
                anio = 0
            if not cvegeo or not anio:
                continue
            n_total += 1
            slug = (r.get("municipio_slug") or "").strip()
            if not force and _existe_no_vacio(anio, slug):
                n_skip += 1
                continue
            por_cvegeo[cvegeo]["slug"] = slug
            por_cvegeo[cvegeo]["anios"].append(anio)

        n_pend = sum(len(v["anios"]) for v in por_cvegeo.values())
        print(f"  [{self.slug}] casos: {n_total} | ya extraídos (saltados): {n_skip} | "
              f"pendientes: {n_pend}")
        for cvegeo, info in sorted(por_cvegeo.items()):
            extraer_municipio(
                estado=self.slug,
                cvegeo=cvegeo,
                anios=sorted(set(info["anios"])),
                slug_override=info["slug"] or None,
            )

    def run_validation(self):
        """Valida JSONs y genera reporte de calidad."""
        from src.core.validation import validate_all
        validate_all(
            json_dir=self.json_dir,
            prefijo=self.prefijo,
            out_csv=self.meta_dir / f"{self.slug}_predial_summary.csv",
        )

    def run_audit(self):
        """Auditoría pre-consolidación: grid exhaustivo INEGI × años."""
        from src.core.audit import run_audit
        run_audit(adapter=self)

    def run_segment_audit(self):
        """Genera CSV de cobertura cruzando INEGI × segment.csv."""
        from src.core.segment_validator import generate_segment_coverage
        generate_segment_coverage(
            estado_slug=self.slug,
            meta_dir=self.meta_dir,
            ejercicio_range=self.ejercicio_range,
        )

    def canonicalize_segment(self) -> None:
        """Reescribe meta/segment.csv al esquema único canónico (con cvegeo).

        Se ejecuta tras el paso `segment` para que todos los estados emitan el
        mismo esquema, llaveado por cvegeo (esquema único / Causa A).  Es
        idempotente: correrla sobre un CSV ya canónico no lo altera.
        """
        import importlib

        from src.core.segment_schema import (
            STATUS_IDENTIDAD,
            STATUS_NO_LOCALIZADA,
            canonicalize_segment_file,
        )
        try:
            cfg = importlib.import_module(f"src.estados.{self.slug}.config")
            aliases = dict(getattr(cfg, "ALIASES", {}) or {})
        except Exception:
            aliases = {}
        canon = canonicalize_segment_file(self.slug, aliases=aliases)
        if canon:
            n_id = sum(1 for r in canon if r.status == STATUS_IDENTIDAD)
            n_nl = sum(1 for r in canon if r.status == STATUS_NO_LOCALIZADA)
            print(f"  [{self.slug}] segment canónico: {len(canon)} filas "
                  f"(identidad_no_resuelta={n_id}, no_localizada={n_nl})")