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

- `data/{estado}/pdf_raw/`, `pdf_ocr/`, `focus_predial/`, `json_predial/`, `meta/`, `qa/`
- `predial-mx-v2/` — JSONs de extracción v2 (una tarifa por archivo)
- `predial-mx-v3/` — JSONs de extracción v3 (multi-tarifa, tasas fieles)
- `predial-mx-v3-hitl/` — JSONs propagados/corregidos por HITL
- `output/` — `predial_panel.csv`, `predial_panel_balanced.csv`, `quality_report.csv`
- `output/hitl/` — `cola_unificada.csv`, `cola_reextraccion.csv`, `hitl_bitacora.csv`

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
- v2: `src/extraction/llm_extract_v2.py` → `predial-mx-v2/`
- v3: `src/extraction/llm_extract_v3.py` → `predial-mx-v3/`

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

Cola única `output/hitl/cola_unificada.csv` alimentada por 12 detectores sobre corpus v3.
Cada fila = un municipio-año consolidado; `detector` es comma-separated, `senal` es pipe-separated.
`id = sha1(estado|muni|anio)` (sin detector). La UI siempre intenta mostrar año previo (side-by-side).

### Detectores

| # | Nombre | SEV | Input |
|---|--------|-----|-------|
| D1 | `frontera_sin_verificar` | SEV1-H | segment.csv (solo Jalisco) |
| D2 | `distancia_inicio_anomala` | SEV1-H | segment.csv: z-score > 2σ en char_start |
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
# 1. Ejecutar detectores → cola_unificada.csv
python -m src.hitl.run_detectors
python -m src.hitl.run_detectors --estado coahuila --merge

# 2. Revisar en UI
python -m scripts.temps.hitl_revisor_server

# 3. Aplicar decisiones → bitácora + cola_reextraccion.csv
python -m scripts.temps.aplicar_decisiones_hitl
python -m scripts.temps.aplicar_decisiones_hitl --dry-run

# 4. Consumir cola de re-extracción (usa gpt-5.4 full)
python -m scripts.consume_reextraction_queue
python -m scripts.consume_reextraction_queue --dry-run
```

### Decisiones HITL

`confirmar_ok` | `propagar_previo` | `corregir_previo` | `reextraer` | `re_segmentar` | `ignorar`

Para `re_segmentar`: campo notas = `paginas=X-Y [; pdf=ruta/al/pdf]`

### Archivos

- `src/hitl/queue_schema.py` — QueueRow dataclass, helpers CSV, merge
- `src/hitl/detectors.py` — D1-D12
- `src/hitl/run_detectors.py` — orquestador CLI
- `scripts/temps/hitl_revisor_server.py` — Flask UI (single-year + side-by-side para D12)
- `scripts/temps/aplicar_decisiones_hitl.py` — aplica decisiones, escribe a `predial-mx-v3-hitl/`
- `scripts/consume_reextraction_queue.py` — consumidor de cola re-extracción

## Advertencia sobre tipo_esquema
Se identificó un error sistemático en el codigo: el LLM clasifica como tabla_progresiva con tasa_marginal=0 cuando la estructura real es cuota fija escalonada. Corrección via discriminated union con escape hatch (otro_no_clasificado). Tamaulipas y Querétaro funcionan como regression tests. Evitar leer tipo_esquema crudo del JSON; esperar a pasar por la capa de validación.

## API
La API key vive en .env (no commiteado). Nunca incluir la key en código, prompts, logs o commits. Si necesitas verificar que está configurada, usa os.environ.get("OPENAI_API_KEY") is not None, no imprimas el valor.
