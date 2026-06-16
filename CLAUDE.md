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
- `scripts/` — Entry points CLI: `run_pipeline.py`, `batch_download.py`, `consolidate_panel.py`, `convert_hardcoded_to_v3.py`, `diff_v2_v3.py`, `pilot_v3.py`
- `scripts/temps/` — Scripts de QA, HITL, calibraciones por estado, anexos de tesis
- `scripts/_archive/` — Scripts obsoletos/completados (ver README.md dentro)
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
- `output/` — `predial_panel.csv`, `predial_panel_balanced.csv`, `quality_report.csv`

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

## Pipeline HITL (auditoría interanual)

4 scripts en `scripts/temps/` que forman el ciclo de revisión:
1. `detectar_cambios_interanuales.py` — detecta cambios año-a-año
2. `hitl_revisor_server.py` — Flask UI para revisión side-by-side
3. `aplicar_decisiones_hitl.py` — aplica decisiones, escribe a `predial-mx-v2-hitl/`
4. `build_anexo_esquemas.py` — anexo LaTeX para tesis

Actualmente leen schema v2. Post-piloto v3 se adaptan.

## Advertencia sobre tipo_esquema
Se identificó un error sistemático en el codigo: el LLM clasifica como tabla_progresiva con tasa_marginal=0 cuando la estructura real es cuota fija escalonada. Corrección via discriminated union con escape hatch (otro_no_clasificado). Tamaulipas y Querétaro funcionan como regression tests. Evitar leer tipo_esquema crudo del JSON; esperar a pasar por la capa de validación.

## API
La API key vive en .env (no commiteado). Nunca incluir la key en código, prompts, logs o commits. Si necesitas verificar que está configurada, usa os.environ.get("OPENAI_API_KEY") is not None, no imprimas el valor.
