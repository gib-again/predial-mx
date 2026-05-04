# Auditoría de anomalías de tratamiento — event-study DiD

**Objetivo**: identificar años que rompen el supuesto de tratamiento absorbente (treatment una vez activado se queda activado) para decidir si son errores de extracción/escaneo (recuperables) o reformas reales (aceptar y descartar el muni del DiD).

## Definiciones

- **Treatment (T)**: `tipo_esquema ∈ {progresivo, mixto}`
- **Control (C)**: el resto (`tarifa_millar`, `tasa_unica`, `cuota_fija_*`, `otro_no_clasificado`, `desconocido`)

## Distribución de trayectorias

| Patrón | Munis | Significado |
|---|---:|---|
| `siempre_T` | 284 | tratado los 16 años — válido pero sin variación temporal |
| `siempre_C` | 227 | control puro — válido como control |
| `clean_onset` | 68 | C...CT...T — **caso ideal** para DiD absorbente |
| `reversion_simple` | 16 | T...TC...C — REVERSIÓN, rompe absorbing |
| `outlier_year_C_in_T` | 7 | TCT — un año C aislado en medio de tratamiento |
| `outlier_year_T_in_C` | 6 | CTC — un año T aislado en medio de control |
| `flip_x2[CTCT]` | 4 | patrón complejo, requiere revisión |
| `flip_x2[TCTC]` | 2 | patrón complejo, requiere revisión |
| `multi_flip[CTCTCT]` | 1 | patrón complejo, requiere revisión |

**Munis a auditar**: 36 (con 132 años problemáticos)

## Por motivo

| Motivo | Conteo |
|---|---:|
| `reversion_T_to_C` | 82 |
| `flip_minority_block_C_in_majority_T` | 22 |
| `flip_minority_block_T_in_majority_C` | 13 |
| `outlier_C_in_T` | 10 |
| `outlier_T_in_C` | 5 |

## Cómo llenar el CSV

Por cada año problemático, decidir:

| `decision` | Cuándo usar |
|---|---|
| `real_reform` | El muni efectivamente cambió de régimen ese año (verificable en el PDF). El muni se descarta del DiD si rompe absorbing. |
| `extraction_error` | El LLM clasificó mal — el tipo correcto es otro. Llena `tipo_correcto`; opcionalmente `pdf_objetivo`/`paginas_objetivo` para forzar re-extracción dirigida. |
| `accept_as_is` | El año es correcto pero aceptas que el muni sea "no absorbente". Útil para munis multi-flip que vas a excluir. |
| `exclude_muni` | Descartar el muni completo del análisis. Usa este valor en CUALQUIER fila del muni — la decisión se aplicará a todas. |

Tras llenar el CSV, corre `python -m scripts.apply_treatment_audit` (por crear) para aplicar las decisiones, o haz los cambios manualmente según prefieras.

## Munis a auditar

Trayectoria por año (2010-2025): `T`=tratamiento, `C`=control, `·`=sin dato.

### 05025 Coahuila de Zaragoza — Piedras Negras

**Trayectoria** (2010-2025): `CCTTTTTTTTTTTTTC`
**Patrón**: `outlier_year_T_in_C`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2010 | otro_no_clasificado | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4-mini | — |
| 2011 | tarifa_millar | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4-mini | — |
| 2025 | tarifa_millar | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4-mini | — |

### 11017 Guanajuato — Irapuato

**Trayectoria** (2010-2025): `CCCCCCCCCCTTTTTC`
**Patrón**: `outlier_year_T_in_C`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2020 | mixto | **T** | C | `flip_minority_block_T_in_majority_C` | gpt-5.4-mini | 2019_13223_Periodico_Numero_260_... p.10-32 |
| 2021 | mixto | **T** | C | `flip_minority_block_T_in_majority_C` | imputed_audit_directed[from_2020] | — |
| 2022 | progresivo | **T** | C | `flip_minority_block_T_in_majority_C` | gpt-5.4-mini | 2021_14625_Periodico_Numero_260_... p.28-225 |
| 2023 | mixto | **T** | C | `flip_minority_block_T_in_majority_C` | gpt-5.4-mini | 2022_15517_Periodico_Numero_260_... p.122-134 |
| 2024 | progresivo | **T** | C | `flip_minority_block_T_in_majority_C` | gpt-5.4-mini | 2023_16371_Periodico_Numero_261_... p.58-70 |

### 11031 Guanajuato — San Francisco del Rincon

**Trayectoria** (2010-2025): `CCCCCCCCCCTCCCCC`
**Patrón**: `outlier_year_T_in_C`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2020 | progresivo | **T** | C | `outlier_T_in_C` | gpt-5.4-mini | 2019_13218_Periodico_Numero_260_... p.199-208 |

### 11042 Guanajuato — Valle de Santiago

**Trayectoria** (2010-2025): `CCCCCCCCCCTTTTTC`
**Patrón**: `outlier_year_T_in_C`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2020 | progresivo | **T** | C | `flip_minority_block_T_in_majority_C` | gpt-5.4-mini | 2019_13202_Periodico_Numero_260_... p.9-18 |
| 2021 | progresivo | **T** | C | `flip_minority_block_T_in_majority_C` | gpt-5.4 | 2020_13872_Periodico_Numero_261_... p.158-174 |
| 2022 | progresivo | **T** | C | `flip_minority_block_T_in_majority_C` | gpt-5.4-mini | 2021_14637_Periodico_Numero_260_... p.31-46 |
| 2023 | progresivo | **T** | C | `flip_minority_block_T_in_majority_C` | gpt-5.4-mini | 2022_15528_Periodico_Numero_260_... p.188-203 |
| 2024 | progresivo | **T** | C | `flip_minority_block_T_in_majority_C` | gpt-5.4-mini | 2023_16391_Periodico_Numero_261_... p.38-53 |

### 14071 Jalisco — San Cristobal de la Barranca

**Trayectoria** (2010-2025): `CCCCCCCCCCCCTCTT`
**Patrón**: `flip_x2[CTCT]`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2022 | progresivo | **T** | C | `outlier_T_in_C` | reclasified_v1[gpt-5.2] | — |
| 2023 | otro_no_clasificado | **C** | T | `outlier_C_in_T` | reclasified_v1[gpt-5.2] | — |

### 14123 Jalisco — Zapotlan del Rey

**Trayectoria** (2010-2025): `CCCCCCCCCCCCTTTC`
**Patrón**: `outlier_year_T_in_C`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2022 | progresivo | **T** | C | `flip_minority_block_T_in_majority_C` | reclasified_v1[gpt-5.2] | — |
| 2023 | progresivo | **T** | C | `flip_minority_block_T_in_majority_C` | reclasified_v1[gpt-5.2] | — |
| 2024 | progresivo | **T** | C | `flip_minority_block_T_in_majority_C` | reclasified_v1[gpt-5.2] | — |

### 14023 Jalisco — Zapotlan el Grande

**Trayectoria** (2010-2025): `CCCCCCCCCCCCTCTT`
**Patrón**: `flip_x2[CTCT]`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2022 | progresivo | **T** | C | `outlier_T_in_C` | reclasified_v1[gpt-5.2] | — |
| 2023 | otro_no_clasificado | **C** | T | `outlier_C_in_T` | reclasified_v1[gpt-5.2] | — |

### 31003 Yucatan — Akil

**Trayectoria** (2010-2025): `TTTTTTTTTTTTTCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2023 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | gpt-5.4 | 2022\2022-12-30_4.pdf p.72-75 |
| 2024 | tarifa_millar | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2023\2023-12-29_3.pdf p.74-77 |
| 2025 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2024\2024-12-30_3.pdf p.86-89 |

### 31006 Yucatan — Buctzotz

**Trayectoria** (2010-2025): `TTTTTTTTTTTTTCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2023 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2022\2022-12-30_4.pdf p.153-155 |
| 2024 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2023\2023-12-29_3.pdf p.151-154 |
| 2025 | tarifa_millar | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2024\2024-12-30_3.pdf p.132-135 |

### 31008 Yucatan — Calotmul

**Trayectoria** (2010-2025): `TTTTTTTTTTTTTCCT`
**Patrón**: `outlier_year_C_in_T`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2023 | tasa_unica | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4-mini | 2022\2022-12-30_4.pdf p.202-204 |
| 2024 | tarifa_millar | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4-mini | 2023\2023-12-29_3.pdf p.199-201 |

### 31011 Yucatan — Celestun

**Trayectoria** (2010-2025): `TTTTTTTTTCCCCCTT`
**Patrón**: `outlier_year_C_in_T`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2019 | tasa_unica | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4 | 2018\2018-12-29_2.pdf p.47-49 |
| 2020 | tasa_unica | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4 | 2019\2019-12-27_2.pdf p.110-114 |
| 2021 | tasa_unica | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4 | 2020\2020-12-29_2.pdf p.90-94 |
| 2022 | tasa_unica | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4-mini | 2021\2021-12-31_3.pdf p.274-278 |
| 2023 | tarifa_millar | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4-mini | 2022\2022-12-30_4.pdf p.278-281 |

### 31021 Yucatan — Chichimila

**Trayectoria** (2010-2025): `TTTTTTCTTTTTCCCC`
**Patrón**: `flip_x2[TCTC]`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2016 | otro_no_clasificado | **C** | T | `outlier_C_in_T` | audit_no_ley | — |
| 2022 | cuota_fija_escalonada | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2021\2021-12-31_3.pdf p.479 |
| 2023 | cuota_fija_escalonada | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2022\2022-12-30_4.pdf p.496-497 |
| 2024 | cuota_fija_escalonada | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2023\2023-12-29_3.pdf p.480-481 |
| 2025 | cuota_fija_escalonada | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2024\2024-12-30_3.pdf p.334-335 |

### 31020 Yucatan — Chicxulub Pueblo

**Trayectoria** (2010-2025): `TTTTTTTTTTCTTTTT`
**Patrón**: `outlier_year_C_in_T`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2020 | tasa_unica | **C** | T | `outlier_C_in_T` | gpt-5.4-mini | 2019\2019-12-27_2.pdf p.135-138 |

### 31024 Yucatan — Chumayel

**Trayectoria** (2010-2025): `TTTCCTTTTTTTTTTT`
**Patrón**: `outlier_year_C_in_T`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2013 | cuota_fija_escalonada | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4-mini | 2012\2012-12-27_suplemento.pdf p.55-56 |
| 2014 | cuota_fija_escalonada | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4-mini | 2013\2013-12-31_3.pdf p.49-50 |

### 31013 Yucatan — Conkal

**Trayectoria** (2010-2025): `TTTTTTTTTTCCCCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2020 | tarifa_millar | **C** | T | `reversion_T_to_C` | gpt-5.4 | 2019\2019-12-27_2.pdf p.168-172 |
| 2021 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2020\2020-12-29_2.pdf p.152-157 |
| 2022 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2021\2021-12-31_3.pdf p.318-325 |
| 2023 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2022\2022-12-30_4.pdf p.320-327 |
| 2024 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2023\2023-12-29_3.pdf p.313-319 |
| 2025 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2024\2024-12-30_3.pdf p.235-241 |

### 31025 Yucatan — Dzan

**Trayectoria** (2010-2025): `TTTTTTTTTCCCCCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2019 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2018\2018-12-29_2.pdf p.145-146 |
| 2020 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2019\2019-12-24_2.pdf p.351-353 |
| 2021 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2020\2020-12-28_2.pdf p.375-379 |
| 2022 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2021\2021-12-31_3.pdf p.571-576 |
| 2023 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2022\2022-12-30_4.pdf p.597-602 |
| 2024 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2023\2023-12-29_3.pdf p.579-584 |
| 2025 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2024\2024-12-30_4.pdf p.199-203 |

### 31027 Yucatan — Dzidzantun

**Trayectoria** (2010-2025): `CCCTCCCCCCCCCCCC`
**Patrón**: `outlier_year_T_in_C`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2013 | progresivo | **T** | C | `outlier_T_in_C` | gpt-5.4-mini | 2012\2012-12-24_suplemento.pdf p.345-347 |

### 31035 Yucatan — Hoctun

**Trayectoria** (2010-2025): `TTCCCCCCCCCCCCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2012 | tarifa_millar | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2011\2011-12-29_suplemento.pdf p.73-75 |
| 2013 | tarifa_millar | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2012\2012-12-27_suplemento.pdf p.108-110 |
| 2014 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4 | 2013\2013-12-31_3.pdf p.102-103 |
| 2015 | tarifa_millar | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2014\2014-12-31_2.pdf p.129-131 |
| 2016 | tarifa_millar | **C** | T | `reversion_T_to_C` | imputed_confirmed_fill | — |
| 2017 | tarifa_millar | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2016\2016-12-28_2.pdf p.438-440 |
| 2018 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2017\2017-12-31_2.pdf p.243-245 |
| 2019 | tarifa_millar | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2018\2018-12-29_2.pdf p.171-173 |
| 2020 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2019\2019-12-24_2.pdf p.412-414 |
| 2021 | tasa_unica | **C** | T | `reversion_T_to_C` | imputed_confirmed_fill | 2020\2020-12-28_2.pdf |
| 2022 | tasa_unica | **C** | T | `reversion_T_to_C` | imputed_confirmed_fill | 2021\2021-12-31_3.pdf |
| 2023 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2022\2022-12-30_4.pdf p.816-818 |
| 2024 | tarifa_millar | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2023\2023-12-29_3.pdf p.789-791 |
| 2025 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | synthesized_short_form | 2024\2024-12-30_3.pdf p.472-479 |

### 31036 Yucatan — Homun

**Trayectoria** (2010-2025): `TTTTTTTTTTTTTTTC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2025 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2024\2024-12-30_4.pdf p.358-360 |

### 31041 Yucatan — Kanasin

**Trayectoria** (2010-2025): `TTTTTTTTTTTTCCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2022 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | synthesized_short_form | 2021\2021-12-31_3.pdf p.936-945 |
| 2023 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | synthesized_short_form | 2022\2022-12-30_4.pdf p.982-989 |
| 2024 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | synthesized_short_form | 2023\2023-12-29_3.pdf p.961-969 |
| 2025 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | synthesized_short_form | 2024\2024-12-30_3.pdf p.479-487 |

### 31043 Yucatan — Kaua

**Trayectoria** (2010-2025): `TTTTTTTTTTTTCCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2022 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4 | 2021\2021-12-31_3.pdf p.977-980 |
| 2023 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4 | 2022\2022-12-30_4.pdf p.1018-1021 |
| 2024 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4 | 2023\2023-12-29_3.pdf p.1002-1005 |
| 2025 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | gpt-5.4 | 2024\2024-12-30_3.pdf p.487-493 |

### 31044 Yucatan — Kinchil

**Trayectoria** (2010-2025): `TTTTTTTTTTTTTTCT`
**Patrón**: `outlier_year_C_in_T`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2024 | otro_no_clasificado | **C** | T | `outlier_C_in_T` | gpt-5.4 | 2023\2023-12-29_3.pdf p.1027-1029 |

### 31057 Yucatan — Panaba

**Trayectoria** (2010-2025): `TTTTTTTTTTCCCCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2020 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2019\2019-12-24_2.pdf p.657-658 |
| 2021 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2020\2020-12-28_2.pdf p.711-713 |
| 2022 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2021\2021-12-31_3.pdf p.1303-1304 |
| 2023 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2022\2022-12-30_4.pdf p.1351-1352 |
| 2024 | cuota_fija_simple | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2023\2023-12-29_3.pdf p.1330 |
| 2025 | cuota_fija_simple | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2024\2024-12-30_4.pdf p.771 |

### 31061 Yucatan — Rio Lagartos

**Trayectoria** (2010-2025): `TTTTTTTTTTCCCCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2020 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4 | 2019\2019-12-27_2.pdf p.660-662 |
| 2021 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4 | 2020\2020-12-29_2.pdf p.629-631 |
| 2022 | tasa_unica | **C** | T | `reversion_T_to_C` | imputed_confirmed_fill | — |
| 2023 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4 | 2022\2022-12-30_4.pdf p.1483-1486 |
| 2024 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4 | 2023\2023-12-29_3.pdf p.1473-1477 |
| 2025 | tasa_unica | **C** | T | `reversion_T_to_C` | imputed_ffill | 2024\2024-12-30_3.pdf |

### 31065 Yucatan — San Felipe

**Trayectoria** (2010-2025): `TTTTTTTTTTTCCCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2021 | tarifa_millar | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2020\2020-12-29_2.pdf |
| 2022 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2021\2021-12-31_3.pdf p.1523-1525 |
| 2023 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2022\2022-12-30_4.pdf p.1567-1570 |
| 2024 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2023\2023-12-29_3.pdf p.1558-1561 |
| 2025 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2024\2024-12-30_3.pdf p.649-652 |

### 31069 Yucatan — Sotuta

**Trayectoria** (2010-2025): `CTTCCCCTTTCTTTTT`
**Patrón**: `multi_flip[CTCTCT]`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2010 | otro_no_clasificado | **C** | T | `flip_minority_block_C_in_majority_T` | synthesized_short_form | 2009\2009-12-29_suplemento.pdf p.209-212 |
| 2013 | otro_no_clasificado | **C** | T | `flip_minority_block_C_in_majority_T` | synthesized_short_form | 2012\2012-12-24_suplemento.pdf p.558-562 |
| 2014 | otro_no_clasificado | **C** | T | `flip_minority_block_C_in_majority_T` | synthesized_short_form | 2013\2013-12-31_2.pdf p.524-527 |
| 2015 | otro_no_clasificado | **C** | T | `flip_minority_block_C_in_majority_T` | synthesized_short_form | 2014\2014-12-24_2.pdf p.654-659 |
| 2016 | otro_no_clasificado | **C** | T | `flip_minority_block_C_in_majority_T` | audit_no_ley | — |
| 2020 | tasa_unica | **C** | T | `outlier_C_in_T` | gpt-5.4 | 2019\2019-12-27_2.pdf p.776-779 |

### 31078 Yucatan — Tekanto

**Trayectoria** (2010-2025): `CTCTTTTTTTTTTTTT`
**Patrón**: `flip_x2[CTCT]`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2011 | progresivo | **T** | C | `outlier_T_in_C` | gpt-5.4-mini | 2010\2010-12-24_suplemento.pdf p.437-440 |
| 2012 | cuota_fija_escalonada | **C** | T | `outlier_C_in_T` | gpt-5.4-mini | 2011\2011-12-28_suplemento.pdf p.585-588 |

### 31081 Yucatan — Tekom

**Trayectoria** (2010-2025): `TTTTTTTTTTCCCCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2020 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | — |
| 2021 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2020\2020-12-29_2.pdf p.897-898 |
| 2022 | tasa_unica | **C** | T | `reversion_T_to_C` | imputed_confirmed_fill | — |
| 2023 | tasa_unica | **C** | T | `reversion_T_to_C` | imputed_confirmed_fill | — |
| 2024 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2023\2023-12-29_3.pdf p.1909-1910 |
| 2025 | tasa_unica | **C** | T | `reversion_T_to_C` | imputed_ffill | 2024\2024-12-30_4.pdf |

### 31087 Yucatan — Tetiz

**Trayectoria** (2010-2025): `TTTTTTTTTTCCCCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2020 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2019\2019-12-24_2.pdf p.927-929 |
| 2021 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2020\2020-12-28_2.pdf p.913-916 |
| 2022 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2021\2021-12-31_3.pdf p.1985-1989 |
| 2023 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2022\2022-12-30_4.pdf p.2033-2036 |
| 2024 | tasa_unica | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2023\2023-12-29_3.pdf p.2032-2035 |
| 2025 | tasa_unica | **C** | T | `reversion_T_to_C` | imputed_ffill | 2024\2024-12-30_3.pdf |

### 31092 Yucatan — Tixcacalcupul

**Trayectoria** (2010-2025): `TTTTTTTTTTTTTTTC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2025 | cuota_fija_escalonada | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2024\2024-12-30_4.pdf p.1199-1201 |

### 31095 Yucatan — Tixpehual

**Trayectoria** (2010-2025): `TTTTTTTTTTTCCCCC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2021 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | audit_no_ley | 2020\2020-12-28_2.pdf |
| 2022 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | synthesized_short_form | 2021\2021-12-31_3.pdf p.2172-2179 |
| 2023 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | synthesized_short_form | 2022\2022-12-30_4.pdf p.2226-2233 |
| 2024 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | synthesized_short_form | 2023\2023-12-29_3.pdf p.2223-2230 |
| 2025 | otro_no_clasificado | **C** | T | `reversion_T_to_C` | synthesized_short_form | 2024\2024-12-30_3.pdf p.916-923 |

### 31096 Yucatan — Tizimin

**Trayectoria** (2010-2025): `TTTTTTTTTTTTTTTC`
**Patrón**: `reversion_simple`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2025 | cuota_fija_escalonada | **C** | T | `reversion_T_to_C` | gpt-5.4-mini | 2024\2024-12-30_4.pdf p.1264-1272 |

### 31098 Yucatan — Tzucacab

**Trayectoria** (2010-2025): `TTTTTTTTTCCCCTTC`
**Patrón**: `flip_x2[TCTC]`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2019 | otro_no_clasificado | **C** | T | `flip_minority_block_C_in_majority_T` | synthesized_short_form | 2018\2018-12-29_2.pdf p.482-489 |
| 2020 | otro_no_clasificado | **C** | T | `flip_minority_block_C_in_majority_T` | synthesized_short_form | 2019\2019-12-24_2.pdf p.1009-1021 |
| 2021 | otro_no_clasificado | **C** | T | `flip_minority_block_C_in_majority_T` | synthesized_short_form | 2020\2020-12-29_2.pdf p.1108-1114 |
| 2022 | tasa_unica | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4-mini | 2021\2021-12-31_3.pdf p.2249-2253 |
| 2025 | tasa_unica | **C** | T | `flip_minority_block_C_in_majority_T` | gpt-5.4 | 2024\2024-12-30_4.pdf p.1332-1336 |

### 31101 Yucatan — Uman

**Trayectoria** (2010-2025): `TTTTTTTTTTTTTCTT`
**Patrón**: `outlier_year_C_in_T`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2023 | tarifa_millar | **C** | T | `outlier_C_in_T` | gpt-5.4-mini | 2022\2022-12-30_4.pdf p.2382-2393 |

### 31103 Yucatan — Xocchel

**Trayectoria** (2010-2025): `TTTTTTCTTTTTTTTT`
**Patrón**: `outlier_year_C_in_T`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2016 | otro_no_clasificado | **C** | T | `outlier_C_in_T` | audit_no_ley | — |

### 31104 Yucatan — Yaxcaba

**Trayectoria** (2010-2025): `CCCTTTCTTTTTTTTT`
**Patrón**: `flip_x2[CTCT]`

| Año | tipo_actual | T/C | esperado | motivo | modelo | pdf · pág |
|---:|---|:---:|:---:|---|---|---|
| 2016 | otro_no_clasificado | **C** | T | `outlier_C_in_T` | audit_no_ley | — |
