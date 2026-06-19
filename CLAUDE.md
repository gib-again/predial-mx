# predial-mx

Extracción estructurada de tasas de impuesto predial municipal desde Periódicos Oficiales de estados mexicanos (2010-2025). Output: panel CSV (estado × municipio × año).

## Comandos frecuentes

```bash
# Pipeline completo para un estado
python -m scripts.run_pipeline {estado}

# Pasos específicos
python -m scripts.run_pipeline {estado} --steps download
python -m scripts.run_pipeline {estado} --steps segment,extract
python -m scripts.run_pipeline {estado} --from-step extract

# Batch mode (LLM con 50% descuento)
python -m scripts.run_pipeline {estado} --steps extract --batch
python -m scripts.batch_download {estado}

# Todos los estados
python -m scripts.run_pipeline --all --steps validate

# Consolidación e imputación
python -c "from src.core.consolidate import consolidate_all; consolidate_all()"
python -c "from src.core.impute import impute_panel; impute_panel()"

# Grupo B (hardcoded) → v3
python -m scripts.convert_hardcoded_to_v3 --all
python -m scripts.convert_hardcoded_to_v3 --estado chihuahua

# Diff v2 vs v3
python -m scripts.diff_v2_v3 --estado coahuila

# Tests y lint
python -m pytest
ruff check src/ scripts/
```

## Arquitectura

- `src/core/` — Lógica compartida: LLM extraction, schemas Pydantic, validación, consolidación, imputación, PDF utils, OCR, text utils, adapters hardcoded (v2 y v3)
- `src/extraction/` — Schemas y extractores versionados: `schema_v2.py`, `schema_v3.py`, `llm_extract_v2.py`, `llm_extract_v3.py`, `prompts_v3.py`
- `src/estados/` — Un adaptador por estado con patrón registry + factory (`@register`). Cada estado tiene: `config.py`, `download.py`, `segment.py`, opcionalmente `ocr.py`, `pipeline.py`, `tarifa_base.py`
- `src/estados/base.py` — Clase abstracta `EstadoAdapter` (métodos requeridos: `download`, `build_master`, `extract_predial_sections`)
- `src/hitl/` — Cola HITL unificada: detectores (D1-D12), esquema de cola, orquestador
- `scripts/` — Entry points CLI: `run_pipeline.py`, `batch_download.py`, `consolidate_panel.py`, `convert_hardcoded_to_v3.py`, `diff_v2_v3.py`, `pilot_v3.py`, `consume_reextraction_queue.py`
- `scripts/temps/` — Scripts de QA, HITL UI, calibraciones por estado, anexos de tesis
- `scripts/_archive/` — Scripts obsoletos/completados: DiD (audit_treatment, apply_treatment, build_event_study), ver README.md
- `catalogs/` — Catálogos INEGI de municipios
- `docs/` — BEST_PRACTICES.md (referencia obligatoria para nuevos estados), notas por estado, esquemas

## Convenciones de código

- Python 3.12+, line-length 100 (ruff)
- Naming de archivos: `{PREFIJO}_PREDIAL_{AÑO}_{slug}.{txt|pdf|json}`
- Prefijos por estado en `src/core/constants.py` (`PREFIJOS_ESTADO`)
- Slugs: `text_utils.slugify()` — sin acentos, lowercase, underscores
- Schemas: Pydantic v2 en `src/extraction/schema_v2.py` y `schema_v3.py`

## Datos (no van en git)

- `data/{estado}/pdf_raw/`, `pdf_ocr/`, `focus_predial/{anio}/`, `meta/`, `qa/`
- `data/{estado}/json_predial/{anio}/` — **corpus v3 canónico** (multi-tarifa, tasas fieles).
  Centralizado en `src/core/constants.py` (`json_predial_dir`) y accedido vía `src/core/corpus.py`.
- `data/{estado}/json_predial_hitl/{anio}/` — overlay HITL-corregido (originales se conservan)
- `output/` — `predial_panel.csv`, `predial_panel_balanced.csv`, `quality_report.csv`
- `output/hitl/` — `cola_unificada.csv` (vista **derivada**), `hitl_decisiones.csv` (decisiones
  append-only, fuente de verdad), `hitl_ediciones.csv` (cambios menores before/after),
  `cola_reextraccion.csv`, `hitl_bitacora.csv`
- Histórico: `predial-mx-v3/` y `predial-mx-v3-hitl/` (reubicados a `data/`; ver
  `docs/SCHEMA_EVOLUTION.md`). `predial-mx-v2/` eliminado.

## Schema v2 (`src/extraction/schema_v2.py`)

Una tarifa por municipio-año. Tarifas paralelas van en prosa en `comentarios`. Tasas reescaladas a decimales.

## Schema v3 (`src/extraction/schema_v3.py`)

Contenedor multi-tarifa `PredialV3.tarifas: list[TarifaPredial]`. Cambios clave:
- **Multi-tarifa**: cada tarifa paralela (urbano, rústico, agropecuario, etc.) es una entrada separada con `ambito` y `base_gravable`
- **Transcripción fiel (D3)**: tasas sin reescalar; campo `unidad` lleva la escala (`al_millar`, `porcentaje`, etc.)
- **BloqueProgresivo**: escalas progresivas diferenciadas por categoría
- **Procedencia**: `_meta_v3.procedencia` registra archivo PDF, páginas y fuente ganadora para HITL

## LLM extraction

- OpenAI API con structured output (JSON schema)
- Modelo default: gpt-5.4-mini. Fallback/visión: gpt-5.4
- Cascada: mini → retry → escalación a full → re-OCR → visión
- **v3 es el único flujo**: `src/extraction/llm_extract_v3.py` (`extraer_municipio`)
  → `data/{estado}/json_predial/{anio}/`
- El paso `extract` del pipeline (`EstadoAdapter.run_llm_extraction`) usa v3,
  manejado por `segment.csv` canónico (status=ok, agrupado por cvegeo).  Salta
  los casos ya extraídos (JSON v3 no vacío) salvo `--force-extract`.
- **Re-extracción gana sobre overlay HITL**: una extracción exitosa retira el
  overlay `json_predial_hitl/` del caso (`_save_result`).  Una fallida lo conserva.
- `--batch` (Batch API) **no** está soportado en v3; el flag se ignora.
- v2 (`llm_extract_v2.py`, `core/llm_extract.py`): legado dormido, ver `docs/SCHEMA_EVOLUTION.md`.

## Grupo B (estados hardcoded)

Chihuahua, Colima, Edomex, Sinaloa, Tabasco — tarifa uniforme estatal. No pasan por LLM.
- v2: `src/core/adapters_hardcoded.py` (una tarifa, tasas reescaladas)
- v3: `src/core/adapters_hardcoded_v3.py` (multi-tarifa, tasas fieles con `unidad`)

## Tipos de esquema (`tipo_esquema`)

`tarifa_millar` | `progresivo` | `tasa_unica` | `cuota_fija_simple` | `cuota_fija_escalonada` | `mixto` | `otro_no_clasificado`

## Variables de entorno

- `OPENAI_API_KEY` (requerida para extraction)
- `OPENAI_MODEL` (default: gpt-5.4-mini)
- `OPENAI_MODEL_FALLBACK` (default: gpt-5.4)

## Estados implementados (11)

Coahuila (COAH), Jalisco (JAL), Querétaro (QRO), Yucatán (YUC), Tamaulipas (TAMPS), Chihuahua (CHIH), Colima (COLIMA), Edomex (EDOMEX), Sinaloa (SINALOA), Tabasco (TABASCO), Guanajuato (GTO), Oaxaca (OAX)

## Pipeline (6 pasos)

download → ocr (si aplica) → master → segment → extract (LLM) → validate → [consolidate] → [impute]

## Pipeline HITL unificado (v3)

Cola `output/hitl/cola_unificada.csv` = **vista derivada idempotente**: se reconstruye en cada
corrida de `run_detectors` desde `{JSON v3} ⋈ {segment.csv} ⋈ {decisiones}`.  Las decisiones del
revisor NO viven en la cola (eso causaba orphans, Causa B); viven en `hitl_decisiones.csv`
(append-only, fuente de verdad) y se hacen overlay por `id`.  Así los orphans son imposibles.
Cada fila = un municipio-año consolidado; `detector` comma-separated, `senal` pipe-separated.
`id = sha1(estado|muni_slug|anio)`.  Identidad canónica = `cvegeo` (llave de unión en todos los
artefactos; ver Causa A).  La UI siempre intenta mostrar año previo (side-by-side).

### Detectores

| # | Nombre | SEV | Input |
|---|--------|-----|-------|
| D1 | `frontera_sin_verificar` | SEV1-H | segment.csv (solo Jalisco) |
| D2 | `distancia_inicio_anomala` | SEV1-H | segment.csv: z-score > 2σ en char_start |
| D2b | `identidad_no_resuelta` | SEV1 | segment.csv: texto no matchea catálogo INEGI (cvegeo vacío) |
| D3 | `mixto_monocolumna_cuotafija` | SEV1 | v3 JSON |
| D4 | `tabla_vacia` | SEV1 | v3 JSON |
| D5 | `otro_no_clasificado` | SEV1 | v3 JSON |
| D6 | `progresivo_tasa_cero` | SEV1 | v3 JSON |
| D7 | `bracket_superior_cerrado` | SEV2 | v3 JSON |
| D8 | `rangos_no_monotonos` | SEV2 | v3 JSON |
| D9 | `tarifa_millar_factor` | SEV2 | v3 JSON |
| D10 | `tasa_unica_unidad_factor` | SEV2 | v3 JSON |
| D11 | `desc_transitorios` | SEV1 | v3 JSON |
| D12 | `cambio_interanual` | SEV1/2/3 | pares v3 JSON año-a-año |

### Ciclo de revisión

```bash
# 1. Ejecutar detectores → reconstruye cola_unificada.csv (overlay decisiones)
python -m src.hitl.run_detectors            # (--merge está deprecado: las decisiones siempre se aplican)

# 2. Revisar en UI (escribe decisiones a hitl_decisiones.csv)
python -m scripts.temps.hitl_revisor_server

# 3. Aplicar decisiones (lee del log) → bitácora + ediciones + cola_reextraccion.csv
python -m scripts.temps.aplicar_decisiones_hitl
python -m scripts.temps.aplicar_decisiones_hitl --dry-run

# 4. Consumir cola de re-extracción (usa gpt-5.4 full; reenvía hints) — GATED por API
python -m scripts.consume_reextraction_queue
python -m scripts.consume_reextraction_queue --dry-run
```

### Decisiones HITL

`confirmar_ok` | `propagar_previo` | `corregir_previo` | `reextraer` | `re_segmentar` | `ignorar`

- **Sub-opción** (confirmar/propagar/corregir): `Fiel` | `Con cambio menor`.  "Cambio menor" edita
  un whitelist chico (`minimo_predial`, `unidad`, `periodicidad`), logueado con before/after en
  `hitl_ediciones.csv`.  Taxonomía de procedencia: `confirmado_fiel`, `confirmado_cambio_menor`,
  `propagado_previo`, `corregido_previo`, `reextraido`, `resegmentado`.
- **Hints de re-extracción** (reextraer): `hint_tipo_esquema` (sesga el prompt, no fuerza),
  `force_vision` (salta cascada→visión), `paginas`/`pdf` (vía overrides).
- `re_segmentar`: campo notas = `paginas=X-Y [; pdf=ruta/al/pdf]`.

### Archivos

- `src/core/catalog.py` — resolución canónica de identidad (cvegeo↔nombre↔slug)
- `src/core/segment_schema.py` — esquema único de segment.csv + canonicalización
- `src/core/corpus.py` — acceso centralizado al corpus v3 (canónico + overlay HITL)
- `src/hitl/decisiones.py` — capa append-only de decisiones + ediciones + procedencia
- `src/hitl/queue_schema.py` — QueueRow dataclass, helpers CSV
- `src/hitl/detectors.py` — D1-D12 + identidad_no_resuelta
- `src/hitl/run_detectors.py` — orquestador CLI (rebuild idempotente + overlay decisiones)
- `scripts/temps/hitl_revisor_server.py` — Flask UI (nombres desde catálogo, paginación,
  2 botones PDF, sub-opción Fiel/cambio menor, hints)
- `scripts/temps/aplicar_decisiones_hitl.py` — aplica decisiones del log, escribe a `json_predial_hitl/`
- `scripts/consume_reextraction_queue.py` — consumidor de cola re-extracción (reenvía hints)
- `scripts/temps/migrar_segment_csv.py`, `migrar_corpus_v3.py` — migraciones (sin API)

## Advertencia sobre tipo_esquema
Se identificó un error sistemático en el codigo: el LLM clasifica como tabla_progresiva con tasa_marginal=0 cuando la estructura real es cuota fija escalonada. Corrección via discriminated union con escape hatch (otro_no_clasificado). Tamaulipas y Querétaro funcionan como regression tests. Evitar leer tipo_esquema crudo del JSON; esperar a pasar por la capa de validación.

## API
La API key vive en .env (no commiteado). Nunca incluir la key en código, prompts, logs o commits. Si necesitas verificar que está configurada, usa os.environ.get("OPENAI_API_KEY") is not None, no imprimas el valor.
