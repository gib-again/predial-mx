# Buenas Prácticas — predial-mx

Consolidación de lecciones aprendidas en Coahuila, Jalisco, Querétaro y Yucatán.
Referencia obligatoria antes de implementar un nuevo estado.

---

## 1. Arquitectura de un adaptador

Cada estado vive en `src/estados/{slug}/` con 4 módulos:

```
__init__.py   → Clase adapter, registra con @register
config.py     → Constantes: URLs, prefijo, años, flags
download.py   → Descarga PDFs del Periódico Oficial
segment.py    → Localiza leyes → extrae sección predial → genera TXT/PDF
```

Los pasos compartidos (OCR, LLM, validación, consolidación) están en `src/core/`.

### Convención de archivos
```
data/{estado}/
├── pdf_raw/{año}/{PREFIJO}_RAW_{año}_{slug}.pdf
├── pdf_ocr/{año}/...                              ← solo si needs_ocr=True
├── focus_predial/{año}/{PREFIJO}_PREDIAL_{año}_{slug}.txt
│                 {año}/{PREFIJO}_PREDIAL_{año}_{slug}.pdf
├── json_predial/{año}/{PREFIJO}_PREDIAL_{año}_{slug}.json
├── meta/          ← CSVs de bitácora, índice
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

### Patrón: API REST
Si el estado tiene API (Jalisco):
- Iterar IDs de municipio × año.
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

## 3. Segmentación

### Dos niveles de segmentación
Para estados con tomos (múltiples leyes en un solo PDF):
1. **Nivel 1**: Localizar inicio de cada ley municipal (por título/decreto).
2. **Nivel 2**: Dentro de cada ley, localizar sección de predial.

Para estados con PDFs individuales por municipio:
- Solo nivel 2.

### Detección de sección predial
Patrones probados:
```python
# Inicio
r"(?:IMPUESTO|DEL\s+IMPUESTO)\s+(?:SOBRE\s+)?(?:LA\s+)?PROPIEDAD\s+(?:RA[IÍ]Z|INMOBILIARIA)"
r"(?:IMPUESTO\s+)?PREDIAL"
r"ART[IÍ]CULO\s+\d+.*?PREDIAL"

# Fin (inicio de siguiente impuesto)
r"(?:IMPUESTO\s+SOBRE\s+)?(?:TRASLACI[OÓ]N|ADQUISICI[OÓ]N)\s+DE\s+(?:DOMINIO|INMUEBLES)"
r"IMPUESTO\s+SOBRE\s+ESPECT[AÁ]CULOS"
r"DEL\s+IMPUESTO\s+SOBRE\s+DIVERSIONES"
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

### Manejo de duplicados
- Si el archivo ya existe: **skip y loggear**, no crear `__dup`.
- Primera ocurrencia es casi siempre la correcta.

---

## 4. Municipios

### Catálogo y aliases
- Cada estado necesita un dict de aliases para nombres no estándar:
  ```python
  ALIASES = {
      "cadereyta": "cadereyta_de_montes",
      "tlaquepaque": "san_pedro_tlaquepaque",
  }
  ```
- Match contra catálogo INEGI para CVE_ENT/CVE_MUN.
- `changes_ageeml.csv` para municipios nuevos (CGO_ACT="M") y cambios de nombre ("W").

### Slugs limpios
- Eliminar sufijo del estado si aparece: `amealco_de_bonfil_queretaro` → `amealco_de_bonfil`.
- Usar `slugify()` de `text_utils.py` para consistencia.
- Normalizar acentos: `é` → `e`.

---

## 5. LLM Extraction

### El prompt importa más que el modelo
- Documentar **qué ignorar**: descuentos, condonaciones, recargos, tablas de valores catastrales,
  frutos civiles.
- Documentar **unidades implícitas**: progresivo siempre en pesos/factor decimal,
  tarifa_millar siempre al millar, etc.
- Solo pedir clasificación de unidad explícita para mixto (ColumnaValor.unidad).
- Dar ejemplos concretos del estado en el prompt si hay patrones únicos.

### Esquemas de predial por estado (hasta ahora)
| Estado    | Esquema dominante | Notas |
|-----------|-------------------|-------|
| Coahuila  | mixto             | Tablas multi-columna (habitacional, no hab, con barda, sin barda) |
| Jalisco   | tarifa_millar     | Tasas al millar bimestral por tipo de predio |
| Querétaro | tasa_unica        | Factor sobre valor catastral |
| Yucatán   | variado           | Mezcla de tasa plana, progresivo, factor decimal |

### Batch API
- Sub-batches de ~2.5M tokens (límite OpenAI: 3M TPD).
- Prompt caching + Batch = hasta 75% ahorro en input tokens.
- Guardar batch IDs para recovery.

---

## 6. Consolidación (Fase 6)

### predial_panel.csv
Columnas: `cve_ent, cve_mun, municipio, estado, ejercicio, tipo_esquema, tasa_urbano,
tasa_urbano_edificado, tasa_rustico, tasa_baldio, n_rangos, cuota_minima,
fuente_json, extraction_method`

`tasa_urbano` es el insumo principal para cuantificar predial de vivienda media:
- tarifa_millar → urbano_edificado > urbano > general
- tasa_unica → convertir a al millar si viene en %
- progresivo → tasa marginal del rango mediano
- mixto → best-effort desde tablas disponibles

### quality_report.csv
- `tasa_changed`: >0.1% relativo
- `schema_changed`: tipo_esquema diferente al año anterior
- `rangos_changed`: solo progresivo→progresivo
- Para tarifa_millar: NO flaggear agregar/quitar tipos de predio

---

## 7. Imputación (Fase 7)

| Regla | Condición | Gap máximo | Etiqueta |
|-------|-----------|------------|----------|
| Confirmed fill | T=X, hueco, T+k+1=X (igual) | ≤4 años | confirmed_fill |
| Aggressive fill | T=X, hueco, T+k+1=Y (diferente) | ≤2 años | aggressive_fill |
| Forward fill | T=X, sin dato posterior confirmable | ≤4 años | ffill |
| Backward fill | Primer dato en T, municipio ya existía | ≤4 años | bfill |

No backward-fill antes del año de creación de municipios nuevos (changes_ageeml.csv).

---

## 8. Checklist para nuevo estado

- [ ] Investigar estructura del Periódico Oficial (tomos vs individuales, API vs HTML)
- [ ] Descargar 2-3 PDFs de muestra (año reciente, año antiguo, municipio grande)
- [ ] Identificar patrón de URLs
- [ ] Identificar esquema de predial dominante
- [ ] Verificar si necesita OCR
- [ ] Implementar config.py con constantes
- [ ] Implementar download.py
- [ ] Implementar segment.py (validar con muestras)
- [ ] Agregar aliases de municipios
- [ ] Agregar a constants.py (PREFIJOS_ESTADO)
- [ ] Agregar a __init__.py (import + register)
- [ ] Test: download → segment → LLM → validate pipeline completo
