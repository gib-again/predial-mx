# `output/` — guía de archivos y carpetas

Estructura del directorio tras la consolidación. Solo dos archivos quedan en la
raíz; todo lo demás se organiza en subcarpetas temáticas.

```
output/
├── README.md                       ← este archivo
├── panel_v2.csv                    ← PANEL FINAL (imputado y auditado)
├── panel_v2_raw.csv                ← PANEL ORIGINAL (solo observaciones)
├── audits/                         ← documentos de auditoría humana
├── balance/                        ← reporte detallado de balance
├── legacy/                         ← outputs del proyecto antes del v2
└── logs/                           ← logs de ejecución (oaxaca, sonora, slp, etc.)
```

---

## Raíz (`output/`)

| Archivo | Descripción | Filas | Generado por |
|---|---|---:|---|
| **`panel_v2.csv`** | **Panel taxonómico FINAL** — incluye observaciones LLM/manuales + imputaciones automáticas (ffill, confirmed_fill, closure_fill, tipo_only_fill, uniform_state_fill) + decisiones de auditor (audit_directed, audit_no_ley, audit_override, discovered_law). Este es el archivo a usar en análisis. Columnas: `cvegeo, ejercicio, estado, municipio, tipo_esquema, numero_rangos, monto_max_rango, imputed_method, imputed_from_year`. | ~13,923 | `scripts/build_panel_v2.py` |
| **`panel_v2_raw.csv`** | **Panel ORIGINAL** — mismo schema, pero solo filas donde `imputed_method == ""` (sin imputaciones automáticas). Útil para análisis robustos que solo quieran observaciones de fuente directa. Incluye `audit_no_ley`, `discovered_law`, `synthesized_short_form`, `audit_override` (decisiones del auditor que no son rellenos automáticos). Excluye `imputed_*` (closure_fill, tipo_only_fill, ffill, bfill, confirmed_fill, uniform_state_fill, audit_directed). | ~13,545 | `scripts/build_panel_v2.py` (mismo run) |

Para regenerar:

```bash
python -m scripts.build_panel_v2  # produce ambos panels
```

---

## `output/audits/`

Decisiones humanas y trazabilidad del ciclo HITL.

### Audit de cobertura (huecos en el panel)

| Archivo | Descripción |
|---|---|
| `audit_pendiente.csv` | Filas rellenables (1 por hueco): `cvegeo, ejercicio_gap, motivo, prev_*/next_* (pdf+páginas auto-pobladas), pdf_candidato_gap`, y campos a llenar (`estatus`, `pdf_objetivo`, `paginas`, `notas`). Generado por `scripts/generate_audit_document.py`. Procesado por `scripts/reextract_from_audit.py`. |
| `audit_pendiente.md` | Vista navegable agrupada por muni con punteros precisos a PDFs vecinos. |
| `reextract_log.csv` | Log fila-por-fila de `reextract_from_audit.py`: qué se extrajo via LLM, qué se imputó, qué se marcó audit_no_ley. |
| `residual_gaps_report.md` | Resumen post-procesamiento: huecos que siguen sin cubrirse y decisión sugerida. Generado por `scripts/report_residual_gaps.py`. |

### Audit de elegibilidad para event-study DiD absorbente

| Archivo | Descripción |
|---|---|
| `audit_treatment_anomalies.csv` | Una fila por año problemático en muni con trayectoria no-canónica (reversion, outlier, multi_flip). Auditor llena `decision` + (opcionalmente) `tipo_correcto`/`pdf_objetivo`/`paginas_objetivo`/`notas`. Generado por `scripts/audit_treatment_anomalies.py`. Procesado por `scripts/apply_treatment_audit.py`. |
| `audit_treatment_anomalies.md` | Vista navegable por muni con la trayectoria 2010-2025 (`CCCC...TTTT`). |
| `apply_treatment_audit.log` | Log de `apply_treatment_audit.py`: qué decisiones se aplicaron, qué fallaron, qué se saltó. |
| `treatment_excluded_munis.csv` | Munis con `decision=exclude_muni` — descartar del DiD. |
| `treatment_real_reform_munis.csv` | Munis con `decision=real_reform` (la trayectoria refleja una reforma real) — no elegibles para DiD absorbente. |
| `treatment_non_absorbing_munis.csv` | Munis con `decision=accept_as_is` (aceptados como no-absorbentes) — no elegibles para DiD absorbente. |

### Cómo cargar las listas en código

```python
import csv

excluded = {r['cvegeo'] for r in csv.DictReader(open('output/audits/treatment_excluded_munis.csv', encoding='utf-8-sig'))}
real_reform = {r['cvegeo'] for r in csv.DictReader(open('output/audits/treatment_real_reform_munis.csv', encoding='utf-8-sig'))}
non_absorbing = {r['cvegeo'] for r in csv.DictReader(open('output/audits/treatment_non_absorbing_munis.csv', encoding='utf-8-sig'))}

# 583 munis elegibles para DiD absorbente
panel_did = [r for r in csv.DictReader(open('output/panel_v2.csv', encoding='utf-8-sig'))
             if r['estado'] != 'Oaxaca'
             and 2010 <= int(r['ejercicio']) <= 2025
             and r['cvegeo'] not in (excluded | real_reform | non_absorbing)]
```

---

## `output/balance/`

Reporte detallado del balance de imputación (solo informativo; las imputaciones
se aplicaron a los JSONs en `predial-mx-v2/{estado}/` y se reflejan en
`panel_v2.csv`).

| Archivo | Descripción |
|---|---|
| `panel_v2_balanced.csv` | Vista del panel post-balance, formato wide (1 fila por muni-año en rango incluyendo huecos cerrados). Equivalente a `panel_v2.csv` filtrado a estados balanceados. |
| `panel_v2_balance_report.md` | Reporte de cobertura por estado, distribución de métodos de imputación, sugerencias HITL. |

Generado por `scripts/balance_panel_v2.py` (que internamente llama a `impute_jsons` + `build_panel_v2`).

---

## `output/legacy/`

Outputs del proyecto **antes** de la migración a schema_v2 / panel taxonómico.
Mantenidos como referencia histórica; no usar en análisis nuevos.

| Archivo | Descripción |
|---|---|
| `predial_panel.csv` | Panel v1 — columnas `tasa_urbano`, `tasa_rustico`, `tasa_baldio`, `cuota_minima`. Generado por `src/core/consolidate.py`. |
| `predial_panel_balanced.csv` | Panel v1 con imputación heurística (heredado del flujo previo). |
| `quality_report.csv` | Reporte de calidad del panel v1: `tasa_changed`, `schema_changed`, `rangos_changed` por muni-año. |
| `reporte_taxonomico.md` | Reporte v1 — distribución de tipos de esquema y categorías de error. |
| `extraction_log_v2.csv` | Log de extracción del bulk re-run inicial (3,551 JSONs en 6 estados). |
| `regression_v1_v2.csv`, `regression_v1_v2_full.csv` | Comparación de extracciones v1 vs v2 (validación que la migración no cambió clasificaciones inesperadamente). |

---

## `output/logs/`

Logs de ejecuciones específicas (extracción, OCR, segmentación) por estado y
fase. Útiles para debugging cuando algún muni-año falla. **No tocar**.

Distribución típica:
- `oaxaca_*.log`, `oaxaca_calibration_*.log` — pipeline de Oaxaca.
- `sonora_*.log` — pipeline de Sonora (en desarrollo).
- `slp_*.log` — pipeline de San Luis Potosí (en desarrollo).
- `reocr_resegment*.log`, `reextract_v2*.log`, `reprocess_v2*.log` — re-runs masivos.
- `regression_qro.log`, `traceback_odj.log`, `odj_vision.log`, `sample_v2_postchanges.log` — debug puntual.

---

## Quién escribe en cada carpeta

| Script | Escribe a |
|---|---|
| `scripts/build_panel_v2.py` | `output/panel_v2.csv`, `output/panel_v2_raw.csv` |
| `scripts/balance_panel_v2.py` | `output/balance/panel_v2_balanced.csv`, `output/balance/panel_v2_balance_report.md` (+ JSONs imputados a `predial-mx-v2/`) |
| `scripts/generate_audit_document.py` | `output/audits/audit_pendiente.{csv,md}` |
| `scripts/reextract_from_audit.py` | `output/audits/reextract_log.csv` (+ JSONs a `predial-mx-v2/`) |
| `scripts/audit_treatment_anomalies.py` | `output/audits/audit_treatment_anomalies.{csv,md}` |
| `scripts/apply_treatment_audit.py` | `output/audits/apply_treatment_audit.log`, `output/audits/treatment_*.csv` (+ JSONs a `predial-mx-v2/`) |
| `scripts/report_residual_gaps.py` | `output/audits/residual_gaps_report.md` |
| `scripts/apply_discovered_laws.py` | (solo escribe a `predial-mx-v2/`) |
| `scripts/synthesize_short_form_jsons.py` | (solo escribe a `predial-mx-v2/`) |
| `scripts/convert_hardcoded_to_v2.py`, `convert_v1_to_v2.py` | (solo escriben a `predial-mx-v2/`) |
| `src/core/consolidate.py::consolidate_all` | `output/legacy/predial_panel.csv`, `output/legacy/quality_report.csv` |
| `src/core/impute.py::impute_panel` | `output/legacy/predial_panel_balanced.csv` |

---

## Pipeline corto (de raw a panel listo para análisis)

```bash
# 1. Construir el panel desde el corpus v2 — produce panel_v2.csv y panel_v2_raw.csv
python -m scripts.build_panel_v2

# 2. Aplicar reglas de imputación automática (escribe JSONs imputados a disco
#    + regenera panel_v2.csv con todas las celdas) y produce reporte de balance
python -m scripts.balance_panel_v2

# 3. (Solo si hay huecos) Generar audit de cobertura para el revisor humano
python -m scripts.generate_audit_document

# 4. Tras llenar el audit, aplicar decisiones del auditor
python -m scripts.reextract_from_audit

# 5. Para event-study: identificar anomalías de tratamiento
python -m scripts.audit_treatment_anomalies

# 6. Tras llenar el audit de tratamiento, aplicar decisiones
python -m scripts.apply_treatment_audit

# 7. Reporte final de huecos residuales
python -m scripts.report_residual_gaps
```
