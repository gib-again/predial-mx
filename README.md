# predial-mx

Extracción estructurada de tasas de impuesto predial municipal desde los Periódicos Oficiales estatales de México.

## Objetivo

Construir una base de datos panel (municipio × año) con la estructura del impuesto predial de cada municipio, extraída directamente de las Leyes de Ingresos publicadas en los Periódicos Oficiales de cada estado.

**Ejercicios fiscales**: 2010–2025  
**Estados objetivo**: 10–15 (actualmente: Coahuila, Jalisco, Querétaro, Yucatán)

## Pipeline

```
Descarga → OCR (si aplica) → Master → Segmentación → Extracción LLM → Validación
```

Cada estado implementa su propia lógica de descarga y segmentación (el diseño web de cada Periódico Oficial es distinto). La extracción LLM y la validación son compartidas.

## Estructura

```
src/core/          # Lógica compartida (PDF, texto, LLM, validación, schemas)
src/estados/       # Un adaptador por estado (descarga + segmentación)
catalogs/          # Catálogo de municipios INEGI
data/{estado}/     # Datos por estado (PDFs, metadatos, JSONs)
output/            # Panel consolidado y reportes de calidad
scripts/           # Puntos de entrada CLI
```

## Instalación

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Uso

```bash
# Pipeline completo para un estado
python -m scripts.run_pipeline jalisco

# Solo ciertos pasos
python -m scripts.run_pipeline jalisco --steps download
python -m scripts.run_pipeline jalisco --steps segment,extract

# Desde un paso en adelante
python -m scripts.run_pipeline jalisco --from-step extract

# Todos los estados
python -m scripts.run_pipeline --all --steps validate

#Ejecución de batch (ahorro en LLM)
python -m scripts.run_pipeline coahuila --steps extract --batch   

# Descarga de batch 
python -m scripts.batch_download yucatan   

# Generar panel consolidado
python -c "from src.core.consolidate import consolidate_all; consolidate_all()"

#Imputación de datos 
from src.core.impute import impute_panel; impute_panel()
```




## Tipos de esquema de predial

| Tipo | Descripción |
|------|-------------|
| `tarifa_millar` | Tasa(s) al millar por tipo de predio |
| `progresivo` | Tabla por rangos de valor con cuota fija + tasa marginal |
| `tasa_unica` | Una sola tasa para todos los predios |
| `cuota_fija` | Monto fijo por predio sin referencia al valor |
| `mixto` | Combinación de los anteriores |
| `desconocido` | Texto ambiguo o contradictorio |
