# scripts/_archive/

Scripts one-off, de debugging o legacy que ya cumplieron su propósito.
Conservados por referencia; no forman parte del pipeline activo.

## Categorías

### v1 legacy
- `convert_v1_to_v2.py` — Migración v1→v2 (completada)
- `generar_bitacora.py` — Generador de bitácora v1

### Oaxaca debugging
- `calibrate_oaxaca_2018.py`, `calibrate_oaxaca_gpt54.py` — Calibración OCR/LLM
- `oaxaca_fill_canonical.py` — Fill gaps Oaxaca
- `odj_2014_retry.py`, `odj_vision_retry.py`, `traceback_odj.py` — Retries ODJ

### Sonora one-off
- `sonora_apply_audit_pragmatic.py`, `sonora_audit_download.py` — Audit pragmático
- `sonora_classify_vision_multi.py` — Clasificación multi-visión
- `sonora_ocr_calibration.py`, `sonora_segment_audit.py` — OCR/segmentación
- `sonora_web_verify_gaps.py` — Verificación web

### State fixes
- `reorganize_jal.py` — Reorganización Jalisco
- `fix_errors.py` — Fix errores puntuales

### Diagnóstico/reportes superados
- `compactar_tipo_esquema.py`, `invalid_scheme.py` — Análisis tipo_esquema
- `compare_coverage.py`, `report_residual_gaps.py` — Cobertura
- `reporte_taxonomico.py`, `reporte_claves_tarifa_millar.py` — Reportes
- `sample_v2.py`, `synthesize_short_form_jsons.py` — Muestreo
- `build_panel_pragmatic.py` — Panel pragmático (superado por consolidate)
- `regression_v1_v2.py` — Regresión v1/v2 (completada)
- `reextract_from_audit.py` — Re-extracción post-audit
