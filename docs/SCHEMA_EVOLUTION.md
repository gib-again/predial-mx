# Evolución de esquemas: v1 → v2 → v3

Este documento registra la evolución de los esquemas de extracción del predial
municipal.  **v3 es el único esquema vigente para nuevas extracciones.**  v1 y v2
se documentan aquí (no en código) por trazabilidad histórica.

## v1 — extracción cruda por municipio (legado)

- **Forma:** un JSON por municipio-año, campos planos (`cve_ent`, `cve_mun`,
  `estado`, `municipio`, `slug`, `ejercicio`, `predial`, `notas`).
- **Sin** discriminated union ni metadatos de extracción estructurados.
- **Ruta histórica:** `data/{estado}/json_predial/{anio}/` (algunos estados
  hardcoded como Chihuahua aún conservan estos JSONs locales con naming
  `{PREFIJO}_{anio}_{slug}.json`, sin el segmento `_PREDIAL_`).
- Estado: **retirado del flujo**.  No se generan nuevos.

## v2 — discriminated union sobre `tipo_esquema` (legado)

- **Forma:** una tarifa por municipio-año.  Wrapper `PredialOutputV2` con
  `predial` = union discriminada por `tipo_esquema`
  (`tarifa_millar | progresivo | tasa_unica | cuota_fija_simple |
  cuota_fija_escalonada | mixto | otro_no_clasificado`).
- **Aporte clave:** el *escape hatch* tipado `otro_no_clasificado` corrigió el
  error sistemático de clasificar cuota fija escalonada como progresivo con
  `tasa_marginal=0`.
- Tasas **reescaladas** a decimales; tarifas paralelas en prosa (`comentarios`).
- **Ruta histórica:** `predial-mx-v2/` — **corpus eliminado** (commit 1659f31,
  11,884 JSONs retirados).  El directorio ya no existe en disco.
- Código aún presente pero **dormido** (sin corpus que consumir):
  `src/extraction/schema_v2.py` (re-exporta submodelos canónicos de v3),
  `src/core/validation.py` (`reclasificar`), `src/core/panel_v2.py`,
  `src/core/balance_panel_v2.py`, `src/core/llm_extract.py` (extractor v2).
  Pendiente de retiro en un esfuerzo dedicado (ver «Pendientes» abajo).

## v3 — multi-tarifa + transcripción fiel (vigente)

- **Forma:** contenedor multi-tarifa `PredialOutputV3.predial.tarifas:
  list[TarifaPredial]`.  Cada tarifa paralela (urbano, rústico, agropecuario…)
  es una entrada con `ambito` y `base_gravable`.
- **Transcripción fiel (D3):** tasas **sin reescalar**; el campo `unidad` lleva
  la escala (`al_millar`, `porcentaje`, …).
- **Procedencia:** `_meta_v3.procedencia` registra PDF, páginas y fuente
  ganadora (txt / re-OCR / visión) para auditoría y HITL.
- **Identidad canónica:** `_meta_v3.cvegeo` (5 dígitos INEGI).  Es la llave de
  unión con `segment.csv` y la cola HITL (ver Causa A en el plan de mejoras).
- **Ruta canónica (vigente):** `data/{estado}/json_predial/{anio}/{PREFIJO}_PREDIAL_{anio}_{slug}.json`.
  Correcciones HITL en overlay paralelo
  `data/{estado}/json_predial_hitl/{anio}/` (se conservan los originales).
  Centralizado en `src/core/constants.py` (`json_predial_dir`, etc.) y accedido
  vía `src/core/corpus.py`.
  - *Histórico:* antes vivía en `predial-mx-v3/{estado}/` (plano).  Migrado por
    `scripts/temps/migrar_corpus_v3.py`.

## Tipos de esquema (`tipo_esquema`)

`tarifa_millar | progresivo | tasa_unica | cuota_fija_simple |
cuota_fija_escalonada | mixto | otro_no_clasificado`

> **Advertencia:** no leer `tipo_esquema` crudo del JSON; esperar a la capa de
> validación.  El LLM tiende a clasificar cuota fija escalonada como progresivo
> con `tasa_marginal=0`.  Tamaulipas y Querétaro funcionan como regression tests.

## Pendientes (retiro del stack v2 dormido)

> **Secuencia (acordado):** este retiro se hace **después** de la corrida de
> extracción v3, porque entre `extract` y `panel/consolidación` está el paso
> **HITL**.  El stack v2 (`panel_v2`/`balance_panel_v2`/`validation.reclasificar`)
> sólo se consume en panel/consolidación, aguas abajo de HITL; tocarlo antes de
> terminar extracción+HITL no aporta y arriesga ese flujo.  Orden:
> `extract (v3)` → `HITL` → retiro v2 → `panel/consolidación` (ya v3-only).

El corpus v2 ya no existe, y `core/llm_extract` ya NO está cableado al pipeline
(el paso `extract` es v3); pero queda código v2 dormido que conviene retirar en
un esfuerzo dedicado (alto riesgo: toca el flujo de panel/consolidación):

- Repuntar imports de `schema_v2` → `schema_v3` en `validation.py` y
  `src/extraction/__init__.py`; retirar el shim `schema_v2.py`.
- Migrar `panel_v2.py` / `balance_panel_v2.py` a v3-only y renombrar a `panel.py`.
- Archivar el extractor v2 (`src/core/llm_extract.py`, `llm_extract_v2.py`) y
  scripts que apuntan a `predial-mx-v2/` inexistente (`diff_v2_v3.py`, etc.).
