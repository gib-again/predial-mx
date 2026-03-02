# Buenas Prácticas — predial-mx

Consolidación de lecciones aprendidas en los 11 estados implementados.
Referencia obligatoria antes de implementar un nuevo estado.

---

## 1. Arquitectura de un adaptador

Cada estado vive en `src/estados/{slug}/` con 4-5 módulos:
```
__init__.py   → Clase adapter, registra con @register
config.py     → Constantes: URLs, prefijo, años, flags, municipios/aliases
download.py   → Descarga PDFs del Periódico Oficial
segment.py    → Localiza leyes → extrae sección predial → genera TXT/PDF
ocr.py        → (Solo si needs_ocr=True) OCR con ocrmypdf
```

Los pasos compartidos (LLM extraction con structured output, validación,
consolidación) están en `src/core/`.

### Convención de archivos
```
data/{estado}/
├── pdf_raw/{año}/{PREFIJO}_RAW_{año}_{slug}.pdf
├── pdf_ocr/{año}/{stem}_ocr.pdf                   ← solo si needs_ocr=True
├── focus_predial/{año}/{PREFIJO}_PREDIAL_{año}_{slug}.txt
│                 {año}/{PREFIJO}_PREDIAL_{año}_{slug}.pdf
├── json_predial/{año}/{PREFIJO}_PREDIAL_{año}_{slug}.json
├── meta/          ← CSVs de bitácora, índice, ocr_log, segment
└── qa/            ← Reportes de validación
```

---

## 2. Download

### Patrón: URLs template
Si las URLs siguen un patrón predecible (año, número, sufijo):
- **HEAD antes de GET**: Verificar existencia con HEAD request (status 200 + Content-Type PDF).
  Reduce tiempo dramáticamente (Yucatán: 10h → 10min).
- **Limitar sufijos**: No escanear 01-99; la mayoría de estados usa 01-05 como máximo.
- **HARDCODED_URLS**: Para ejemplares que no siguen el patrón (El Marqués 2016 en Querétaro).

### Patrón: API REST con paginación
Si el estado tiene API (Jalisco, Guanajuato):
- Iterar IDs de municipio × año (Jalisco) o buscar por ejercicio con paginación (Guanajuato).
- Filtrar resultados: excluir reformas, empréstitos, ley estatal (Guanajuato).
- Extraer metadata del API que no siempre viene limpia (Guanajuato: municipio extraído
  del campo "asunto" con regex para parchar campo "NO APLICA").
- Guardar metadata (URL, fecha pub, status) en CSV de índice.

### Patrón: Archivo del Congreso
Si el Congreso publica un PDF consolidado por año:
- Un solo download por año (más simple).
- Verificar si hay PDFs individuales por municipio como alternativa.

### Reglas generales
- User-Agent realista (algunos sitios bloquean bots).
- Sleep entre requests (1-2s) para no saturar.
- Guardar CSV de índice: `{estado}_index.csv` con columnas [año, url, filename, status, size].
- Nunca reescribir PDFs existentes; skip si ya descargado.

---

## 3. OCR

### Cuándo se necesita OCR
- PDFs completamente escaneados (Jalisco).
- PDFs híbridos: texto legal digital + tablas de tarifas como imágenes (Guanajuato).
- Para híbridos, usar `--force-ocr` siempre — `--skip-text` preserva el texto digital
  pero NO procesa las tablas que son imágenes, que es precisamente lo que necesitamos.

### Flags cross-platform (Windows + Linux)
Flags seguros que funcionan en ambos sistemas:
```
ocrmypdf --force-ocr --deskew --rotate-pages --optimize 0
         --tesseract-timeout 300 --jobs 4 --output-type pdf
```

Flags que **NO usar** en Windows:
- `--remove-background`: requiere unpaper (no disponible en Windows)
- `--clean` / `--clean-final`: requiere unpaper
- `--image-dpi N`: solo aplica a inputs imagen (PNG/TIFF), NO a PDFs.
  ocrmypdf lo ignora y retorna error rc15.

### Exit codes de ocrmypdf
- **0**: éxito limpio
- **6**: "already has text" — no debería pasar con --force-ocr, pero es OK
- **15**: "completed with warnings" — **NORMAL** en PDFs tagged/híbridos.
  El archivo de salida ES válido. Tratar como éxito.
- Cualquier otro: error real, borrar archivo de salida corrupto.

### Deduplicación en Windows
Windows es case-insensitive: `*.pdf` y `*.PDF` capturan el mismo archivo.
Deduplicar por path lowercase antes de procesar.

---

## 4. Segmentación

### Dos niveles de segmentación
Para estados con tomos (múltiples leyes en un solo PDF):
1. **Nivel 1**: Localizar inicio de cada ley municipal (por título/decreto).
2. **Nivel 2**: Dentro de cada ley, localizar sección de predial.

Para estados con PDFs individuales por municipio:
- Solo nivel 2.

Guanajuato es el caso más complejo: múltiples PDFs por año, cada uno con 2-5 leyes.
Requiere nivel 1 (encontrar leyes) + nivel 2 (encontrar predial) + auto-detección
de páginas a saltar (portada/sumario).

### Detección de sección predial
Patrones probados:
```python
# Inicio
r"(?:IMPUESTO|DEL\s+IMPUESTO)\s+(?:SOBRE\s+)?(?:LA\s+)?PROPIEDAD\s+(?:RA[IÍ]Z|INMOBILIARIA)"
r"(?:IMPUESTO\s+)?PREDIAL"
r"ART[IÍ]CULO\s+\d+.*?PREDIAL"
r"SECCI[OÓ]N\s+PRIMERA.*?IMPUESTO\s+PREDIAL"  # Guanajuato
r"CAP[IÍ]TULO\s+TERCERO.*?IMPUESTO\s+PREDIAL"  # Guanajuato

# Fin (inicio de siguiente impuesto)
r"(?:IMPUESTO\s+SOBRE\s+)?(?:TRASLACI[OÓ]N|ADQUISICI[OÓ]N)\s+DE\s+(?:DOMINIO|INMUEBLES)"
r"IMPUESTO\s+SOBRE\s+ESPECT[AÁ]CULOS"
r"DEL\s+IMPUESTO\s+SOBRE\s+DIVERSIONES"
r"SECCI[OÓ]N\s+SEGUNDA"  # Guanajuato
r"DIVISI[OÓ]N"            # Guanajuato
```

### Trampas comunes
- **Promulgación ≠ contenido**: "SE EXPIDE LA LEY..." al inicio del tomo no es la ley misma.
- **Índice/TOC**: Las entradas del índice mencionan "predial" pero no son la sección.
- **Tablas de valores catastrales**: Aparecen en Yucatán, Tamaulipas — son catastro, no tarifa.
- **ANEXOS/CRITERIOS**: En Querétaro, tablas duplicadas en anexos. Filtrar por posición.
- **Mojibake**: OCR o encoding defectuoso produce caracteres basura. Normalizar antes de regex.

### Expansión de rangos de páginas
Si `forced_end=True` o rango ≤ 2 páginas:
- Expandir N páginas hacia atrás (Jalisco: 5 páginas).
- Mejor dar contexto extra al LLM que truncar la sección.
- En el fallback PDF visión, se agrega +1 página extra automáticamente.

### Manejo de duplicados
- Si el archivo ya existe: **skip y loggear**, no crear `__dup`.
- Primera ocurrencia es casi siempre la correcta.

---

## 5. Municipios

### Catálogo y aliases
- Cada estado necesita un dict de aliases para nombres no estándar:
```python
  ALIASES = {
      "cadereyta": "cadereyta_de_montes",
      "tlaquepaque": "san_pedro_tlaquepaque",
      # Guanajuato: aliases extensos para tolerancia a ruido OCR
      "dolores_hidalgo_cuna_de_la_independencia_nacional": "dolores_hidalgo",
      "s_miguel_de_allende": "san_miguel_de_allende",
  }
```
- Match contra catálogo INEGI para CVE_ENT/CVE_MUN.
- `changes_ageeml.csv` para municipios nuevos (CGO_ACT="M") y cambios de nombre ("W").

### Slugs limpios
- Eliminar sufijo del estado si aparece: `amealco_de_bonfil_queretaro` → `amealco_de_bonfil`.
- Usar `slugify()` de `text_utils.py` para consistencia.
- Normalizar acentos: `é` → `e`.

---

## 6. LLM Extraction

### Structured output (v2)
A partir de Guanajuato, `src/core/llm_extract.py` usa structured output de OpenAI:
- `response_format={"type": "json_schema", ...}` con `PREDIAL_JSON_SCHEMA`
- Garantiza que el JSON siempre tenga la estructura exacta esperada
- Elimina errores de parseo, campos faltantes, y respuestas con markdown
- Activado por default. Desactivar con `OPENAI_STRUCTURED_OUTPUT=0` (modo legacy)

### Fallback TXT→PDF visión
Para estados con `needs_ocr=True`, si el esquema extraído del TXT no es válido:
1. Se renderiza el PDF recortado a imágenes (200 DPI) con PyMuPDF
2. Se agrega +1 página extra del source PDF (lee de segment.csv)
3. Se envía al LLM como input multimodal (visión) con structured output
4. Si la versión PDF es válida, reemplaza la del TXT

Cada JSON incluye metadata `_meta.fuente` ("txt" o "pdf_vision") y `_meta.modelo`.

Re-ejecución inteligente: si un JSON existe pero fue por TXT y es inválido,
al re-ejecutar `--steps extract` intenta con PDF automáticamente.

### El prompt importa más que el modelo
- Documentar **qué ignorar**: descuentos, condonaciones, recargos, tablas de valores catastrales,
  frutos civiles, predios ejidales con base en producción, derechos catastrales.
- Documentar **unidades implícitas**: progresivo siempre en pesos/factor decimal,
  tarifa_millar siempre al millar, etc.
- Solo pedir clasificación de unidad explícita para mixto (ColumnaValor.unidad).
- Dar ejemplos concretos del estado en el prompt si hay patrones únicos.

### Campo cuota_fija_adicional
Algunos municipios cobran una cuota fija ADEMÁS de la tasa al millar
(ej: "$150 más 3.5 al millar"). Esto se captura en `tabla_tarifa_millar[].cuota_fija_adicional`
(nullable). NO convierte el esquema en "mixto".

### Esquemas de predial por estado (hasta ahora)
| Estado      | Esquema dominante | Notas |
|-------------|-------------------|-------|
| Coahuila    | mixto             | Tablas multi-columna (habitacional, no hab, con barda, sin barda) |
| Jalisco     | tarifa_millar     | Tasas al millar bimestral por tipo de predio |
| Querétaro   | tasa_unica        | Factor sobre valor catastral |
| Yucatán     | variado           | Mezcla de tasa plana, progresivo, factor decimal |
| Tamaulipas  | tarifa_millar     | Tasas al millar por tipo de predio |
| Guanajuato  | tarifa_millar     | Con cuota fija adicional en algunos municipios |
| Chihuahua   | progresivo        | 5 rangos + tasa fija rústicos/minería (Grupo B) |
| Colima      | progresivo        | 26 rangos urbano, 9 rústico, cuotas en UMA (Grupo B) |
| Edo. México | progresivo        | 13 rangos, cuotas en pesos nominales (Grupo B) |
| Sinaloa     | progresivo        | 11 rangos, actualización INPC anual (Grupo B) |
| Tabasco     | progresivo        | 5 rangos, tabla estática desde 1995 (Grupo B) |

### Batch API
- Sub-batches de ~1.1M tokens (margen del límite de 1.35M TPD).
- Structured output + Batch = JSON garantizado + 50% descuento.
- Prompt caching automático (system prompt ≥1024 tokens).
- Guardar batch IDs para recovery.
- Después de batch, re-ejecutar en modo síncrono para fallback PDF.

---

## 7. Consolidación (Fase 6)

### predial_panel.csv
Columnas: `cve_ent, cve_mun, municipio, estado, ejercicio, tipo_esquema, tasa_urbano,
tasa_urbano_edificado, tasa_rustico, tasa_baldio, n_rangos, cuota_minima,
fuente_json, extraction_method`

`tasa_urbano` es el insumo principal para cuantificar predial de vivienda media:
- tarifa_millar → urbano_edificado > urbano > general (+ cuota_fija_adicional si aplica)
- tasa_unica → convertir a al millar si viene en %
- progresivo → tasa marginal del rango mediano
- mixto → best-effort desde tablas disponibles

### quality_report.csv
- `tasa_changed`: >0.1% relativo
- `schema_changed`: tipo_esquema diferente al año anterior
- `rangos_changed`: solo progresivo→progresivo
- Para tarifa_millar: NO flaggear agregar/quitar tipos de predio

---

## 8. Imputación (Fase 7)

| Regla | Condición | Gap máximo | Etiqueta |
|-------|-----------|------------|----------|
| Confirmed fill | T=X, hueco, T+k+1=X (igual) | ≤4 años | confirmed_fill |
| Aggressive fill | T=X, hueco, T+k+1=Y (diferente) | ≤2 años | aggressive_fill |
| Forward fill | T=X, sin dato posterior confirmable | ≤4 años | ffill |
| Backward fill | Primer dato en T, municipio ya existía | ≤4 años | bfill |

No backward-fill antes del año de creación de municipios nuevos (changes_ageeml.csv).

---

## 9. Trabajo distribuido (multi-PC)

### Branching por estado
- Crear rama por estado: `feat/guanajuato`, `feat/oaxaca`.
- Cada PC trabaja en su rama. Merge a `main` cuando pipeline está completo.
- Regla de oro para `src/core/`: solo modificar en una PC a la vez, push inmediato.

### Sincronización de data/
- `data/` no va en Git (demasiado pesado). Sincronizar vía OneDrive, Google Drive, o S3.
- Lo que SÍ va en Git: `src/`, `scripts/`, `docs/`, `catalogs/`, `meta/*.csv`.

### Tracking de progreso
Mantener `meta/pipeline_status.csv`:
```
estado,download,ocr,segment,extract,validate,pc,notas
guanajuato,done,done,done,running,pending,PC-A,290 PDFs
oaxaca,done,running,pending,pending,pending,PC-B,570 mpios
```

### Cambios al schema JSON
- Cuando cambias el schema (ej: agregar `cuota_fija_adicional`), hacer merge a main primero.
- Pull en ambas PCs antes de continuar.
- Para JSONs existentes, crear script de migración que agregue campos nuevos con `null`
  en lugar de re-llamar a la API.

---

## 10. Checklist para nuevo estado

- [ ] Investigar estructura del Periódico Oficial (tomos vs individuales, API vs HTML)
- [ ] Descargar 2-3 PDFs de muestra (año reciente, año antiguo, municipio grande)
- [ ] Identificar patrón de URLs
- [ ] Identificar esquema de predial dominante
- [ ] Verificar si necesita OCR
- [ ] Si necesita OCR: probar flags en Windows (no usar --remove-background, --clean, --image-dpi)
- [ ] Implementar config.py con constantes
- [ ] Implementar download.py
- [ ] Si necesita OCR: implementar ocr.py (ocrmypdf --force-ocr + flags cross-platform)
- [ ] Implementar segment.py (validar con muestras)
- [ ] Agregar aliases de municipios (tolerancia a ruido OCR si aplica)
- [ ] Agregar a constants.py (PREFIJOS_ESTADO)
- [ ] Agregar a __init__.py (import + register)
- [ ] Agregar entrada en docs/notas_por_estado.md
- [ ] Test: download → [ocr] → segment → extract → validate pipeline completo
- [ ] Verificar _meta.fuente en JSONs para entender ratio TXT vs PDF visión