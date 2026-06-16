# scripts/temps/ — Scripts no canónicos

Este directorio contiene **scripts auxiliares**: calibraciones por estado,
retries one-shot, QA/muestreo, anexos de tesis, workflow HITL y exploraciones
de panel. **No forman parte del pipeline canónico** (`scripts/` raíz).

Para distinguir:

- **`scripts/` (raíz)** — pipeline production (`run_pipeline.py`,
  `batch_download.py`, `consolidate_panel.py`, `build_panel_v2.py`,
  `balance_panel_v2.py`, `convert_hardcoded_to_v2.py`, `convert_v1_to_v2.py`,
  `generar_bitacora.py`). Documentado en `CLAUDE.md`.
- **`scripts/temps/`** — todo lo demás.

## Cómo usar

Estos scripts NO son production. Pueden requerir ajustes a paths, datos
faltantes (carpetas `data/_calibration/`, etc.) o variables de entorno antes
de re-ejecutarse. Inspecciona el docstring de cada script antes de correrlo.

Se invocan como módulos:

```bash
python -m scripts.temps.<nombre_script> [args]
```

## Inventario

### QA / muestreo / auditoría

| Script | Propósito | Estado |
|---|---|---|
| `qa_muestra_clasificacion.py` | Muestra aleatoria estratificada por esquema para revisión manual | vigente |
| `qa_inconsistencias.py` | Detecta 9 patrones de inconsistencia (mixto mono-col, tabla vacía, unit factor, etc.) | vigente |
| `sample_v2.py` | Sampling general del panel v2 | vigente |
| `compare_coverage.py` | Compara cobertura entre versiones del panel | vigente |
| `validate_corrections.py` | Valida correcciones aplicadas | vigente |
| `regression_v1_v2.py` | Regresión v1 vs v2 (citado en `src/core/balance_panel_v2.py`) | vigente |
| `audit_treatment_anomalies.py` | Audita anomalías de treatment (event study) | vigente |
| `report_residual_gaps.py` | Reporta huecos residuales del panel | vigente |
| `reporte_taxonomico.py` | Reporte de la taxonomía de esquemas | vigente |
| `generate_audit_document.py` | Genera documento de auditoría markdown | vigente |
| `traceback_odj.py` | Debug/trace de Oaxaca ODJ casos específicos | one-shot |
| `invalid_scheme.py` | Identifica JSONs con esquemas inválidos | vigente |

### Re-extracción / re-procesamiento

| Script | Propósito | Estado |
|---|---|---|
| `reextract_v2.py` | Re-extrae JSONs en formato v2 sobre selección | vigente |
| `reextract_from_audit.py` | Re-extrae casos marcados en audit | vigente |
| `reocr_and_resegment.py` | Re-OCR + re-segmenta selección de PDFs | vigente |
| `reprocess_municipios.py` | Reprocesa municipios específicos end-to-end | vigente |
| `fix_errors.py` | Correcciones puntuales de errores conocidos | one-shot |

### Calibración estado-específica

| Script | Propósito | Estado |
|---|---|---|
| `calibrate_oaxaca_2018.py` | Calibración del extractor para Oaxaca 2018 | one-shot histórico |
| `calibrate_oaxaca_gpt54.py` | Calibración con gpt-5.4 para Oaxaca | one-shot histórico |
| `oaxaca_fill_canonical.py` | Rellena JSONs canónicos en Oaxaca | one-shot |
| `odj_vision_retry.py` | Retry con vision multimodal para Oaxaca ODJ | one-shot |
| `odj_2014_retry.py` | Retry específico de Oaxaca ODJ 2014 | one-shot |
| `sonora_audit_download.py` | Auditoría de downloads en Sonora | one-shot |
| `sonora_ocr_calibration.py` | Calibración OCR para Sonora | one-shot |
| `sonora_segment_audit.py` | Auditoría de segmentación en Sonora | one-shot |
| `sonora_web_verify_gaps.py` | Verificación web de huecos en Sonora | one-shot |
| `sonora_classify_vision_multi.py` | Clasificación vision multi para Sonora | one-shot |
| `sonora_apply_audit_pragmatic.py` | Aplica audit pragmático en Sonora | one-shot |

### Migraciones one-shot

| Script | Propósito | Estado |
|---|---|---|
| `reorganize_jal.py` | Reorganización one-shot de archivos Jalisco | one-shot histórico |
| `synthesize_short_form_jsons.py` | Genera JSONs sintéticos para leyes de ingreso en formato corto (Yucatán). Citado en `docs/HITL_BITACORA.md` | vigente |
| `mark_p00_imputables.py` | Marca casos imputables P-00 en bitácora | vigente |
| `apply_discovered_laws.py` | Aplica leyes descubiertas en `catalogs/discovered_laws/` | vigente |
| `apply_treatment_audit.py` | Aplica audit de treatment (event study) | vigente |

### Anexos de tesis

| Script | Propósito | Estado |
|---|---|---|
| `build_anexo_esquemas.py` | Genera LaTeX de los 5 esquemas para anexo + estadísticos descriptivos | vigente |

### Workflow HITL (meta-pipeline)

| Script | Propósito | Estado |
|---|---|---|
| `detectar_cambios_interanuales.py` | Detecta cambios año-tras-año por municipio; emite plantilla HITL ordenada por sospecha | vigente |
| `aplicar_decisiones_hitl.py` | Aplica decisiones HITL: propaga JSON previo, encola re-extracciones, registra bitácora. NO procesa aún la decisión `re_segmentar` (TODO en bitácora pendientes) | vigente |
| `hitl_revisor_server.py` | App Flask local para revisor humano: side-by-side de TXT+PDF+JSON de ambos años, dropdown de 5 decisiones, escritura atómica al CSV | vigente |
| `reporte_claves_tarifa_millar.py` | Reporta ambigüedad/fragmentación de slugs `clave` en filas tarifa_millar | vigente |

### Paneles exploratorios

| Script | Propósito | Estado |
|---|---|---|
| `build_panel_pragmatic.py` | Panel pragmático alterno (no canónico) | vigente |
| `build_event_study_panel.py` | Panel para event study | vigente |
| `compactar_tipo_esquema.py` | Compacta valores de tipo_esquema | vigente |

## Dependencias adicionales

- `hitl_revisor_server.py` requiere `pip install flask`.

## Convenciones

- Cada script tiene un docstring inicial describiendo su propósito y uso.
- Los outputs van a `output/anexos/` (anexos de tesis y reportes HITL) o
  `output/qa/` (auditorías).
- Los scripts en `one-shot histórico` se preservan para reproducibilidad de
  decisiones pasadas; no se garantiza que sigan funcionando contra el corpus
  actual sin ajustes.
