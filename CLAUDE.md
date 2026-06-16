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

# Tests y lint
python -m pytest
ruff check src/ scripts/
```

## Arquitectura

- `src/core/` — Lógica compartida: LLM extraction, schemas Pydantic, validación, consolidación, imputación, PDF utils, OCR, text utils
- `src/estados/` — Un adaptador por estado con patrón registry + factory (`@register`). Cada estado tiene: `config.py`, `download.py`, `segment.py`, opcionalmente `ocr.py`, `pipeline.py`, `tarifa_base.py`
- `src/estados/base.py` — Clase abstracta `EstadoAdapter` (métodos requeridos: `download`, `build_master`, `extract_predial_sections`)
- `scripts/` — Entry points CLI canónicos del pipeline (`run_pipeline.py`, `batch_download.py`, `consolidate_panel.py`, builders del panel canónico y conversiones v1/hardcoded → v2)
- `scripts/temps/` — Scripts no canónicos: calibraciones por estado, retries, QA/muestreo, anexos de tesis, workflow HITL. Ver `scripts/temps/README.md`
- `catalogs/` — Catálogos INEGI de municipios
- `docs/` — BEST_PRACTICES.md (referencia obligatoria para nuevos estados), notas por estado, esquemas

## Convenciones de código

- Python 3.12+, line-length 100 (ruff)
- Naming de archivos: `{PREFIJO}_PREDIAL_{AÑO}_{slug}.{txt|pdf|json}`
- Prefijos por estado en `src/core/constants.py` (`PREFIJOS_ESTADO`)
- Slugs: `text_utils.slugify()` — sin acentos, lowercase, underscores
- Schemas: Pydantic v2 en `src/core/schemas.py`

## Datos (no van en git)

- `data/{estado}/pdf_raw/`, `pdf_ocr/`, `focus_predial/`, `json_predial/`, `meta/`, `qa/`
- `output/` — `predial_panel.csv`, `predial_panel_balanced.csv`, `quality_report.csv`

## LLM extraction

- OpenAI API con structured output (JSON schema) — modelo default: gpt-5.2
- Modo sync (default) y batch (50% descuento, ~24h)
- Fallback: TXT → PDF visión (+1 página) si esquema inválido
- Cada JSON incluye `_meta.fuente` ("txt" | "pdf_vision") y `_meta.modelo`

## Tipos de esquema (`tipo_esquema`)

`tarifa_millar` | `progresivo` | `tasa_unica` | `cuota_fija` | `mixto` | `desconocido`

## Variables de entorno

- `OPENAI_API_KEY` (requerida para extraction)
- `OPENAI_MODEL` (default: gpt-5.2)
- `OPENAI_VISION_MODEL` (default: mismo que OPENAI_MODEL)
- `OPENAI_STRUCTURED_OUTPUT` ("1" default, "0" para legacy)

## Estados implementados (11)

Coahuila (COAH), Jalisco (JAL), Querétaro (QRO), Yucatán (YUC), Tamaulipas (TAMPS), Chihuahua (CHIH), Colima (COLIMA), Edomex (EDOMEX), Sinaloa (SINALOA), Tabasco (TABASCO), Guanajuato (GTO), Oaxaca (OAX)

## Pipeline (6 pasos)

download → ocr (si aplica) → master → segment → extract (LLM) → validate → [consolidate] → [impute]

## Advertencia sobre tipo_esquema
Se identificó un error sistemático en el codigo: el LLM clasifica como tabla_progresiva con tasa_marginal=0 cuando la estructura real es cuota fija escalonada. A continuación de hará una corrección vía discriminated union con escape hatch (otro_no_clasificado). Tamaulipas y Querétaro funcionan como regression tests. Evitar leer tipo_esquema crudo del JSON; esperar a pasar por la capa de validación.

## API 
La API key vive en .env (no commiteado). Nunca incluir la key en código, prompts, logs o commits. Si necesitas verificar que está configurada, usa os.environ.get("OPENAI_API_KEY") is not None, no imprimas el valor.