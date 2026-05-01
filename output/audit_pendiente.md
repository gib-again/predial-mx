# Documento de auditoría — huecos pendientes

Acompaña a `output/audit_pendiente.csv` (formato rellenable).

**Total de filas a auditar: 119**

Por motivo:
- `sin_predial_residual`: 71
- `schema_discontinuity`: 40
- `edge`: 8

## Cómo llenar el CSV

Por cada fila, después de revisar el PDF candidato:

| Columna | Qué llenar |
|---|---|
| `tipo_esquema_decidido` | Uno de: `tarifa_millar`, `progresivo`, `tasa_unica`, `cuota_fija_simple`, `cuota_fija_escalonada`, `mixto`, `otro_no_clasificado`, o `imputable` si confirma que aplica imputación. |
| `numero_rangos_decidido` | Entero si `tipo_esquema_decidido` ∈ {progresivo, cuota_fija_escalonada, mixto}; vacío si no aplica. |
| `monto_max_rango_decidido` | Float (valor máximo del campo `superior` no-nulo); vacío si no aplica. |
| `es_reforma_real` | `sí` si el cambio entre años observados es una reforma genuina (en cuyo caso el hueco queda como missing); `no` si fue error de extracción; `N/A` para `edge` o `sin_predial_residual`. |
| `decision_final` | `imputar` (aplicar valor al hueco), `excluir` (marcar como missing definitivo), `reextraer` (re-correr LLM con prompt mejorado), `manual_fill` (insertar valores decididos). |
| `comentarios_auditor` | Notas libres. Cita el artículo/página del PDF si es manual_fill. |
| `auditor`, `fecha` | Identificación del revisor y fecha YYYY-MM-DD. |

## Munis a auditar

### Guanajuato — Celaya (11007)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2019 | `schema_discontinuity` | tarifa_millar | progresivo | 2018 | 2020 | 2019_13182_Periodico_Numero_259_Septima_Parte.pdf |

### Guanajuato — Dolores Hidalgo Cuna de la Independencia Nacional (11014)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2021 | `schema_discontinuity` | tarifa_millar | mixto | 2020 | 2022 | 2021_14082_Periódico_Número_27_Segunda_Parte.pdf |

### Guanajuato — Guanajuato (11015)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2021 | `schema_discontinuity` | tarifa_millar | progresivo | 2020 | 2023 | 2021_14082_Periódico_Número_27_Segunda_Parte.pdf |
| 2022 | `schema_discontinuity` | tarifa_millar | progresivo | 2020 | 2023 | 2022_15505_Periódico_Numero_260_Tercera_Parte.pdf |

### Guanajuato — Irapuato (11017)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2021 | `schema_discontinuity` | mixto | progresivo | 2020 | 2022 | 2021_14082_Periódico_Número_27_Segunda_Parte.pdf |

### Guanajuato — Leon (11020)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2013 | `schema_discontinuity` | progresivo | mixto | 2012 | 2014 | 2013_4923_Periodico_Numero_207_Segunda_Parte.pdf |
| 2024 | `schema_discontinuity` | progresivo | mixto | 2023 | 2025 | 2024_17194_Periódico_Número_261_Segunda_Parte.pdf |

### Guanajuato — San Luis de la Paz (11033)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2024 | `schema_discontinuity` | tarifa_millar | progresivo | 2023 | 2025 | 2024_17194_Periódico_Número_261_Segunda_Parte.pdf |

### Guanajuato — San Miguel de Allende (11003)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2013 | `schema_discontinuity` | tarifa_millar | mixto | 2012 | 2014 | 2013_4923_Periodico_Numero_207_Segunda_Parte.pdf |

### Guanajuato — Santiago Maravatio (11036)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2024 | `schema_discontinuity` | tarifa_millar | mixto | 2023 | 2025 | 2024_17194_Periódico_Número_261_Segunda_Parte.pdf |

### Jalisco — San Cristobal de la Barranca (14071)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2021 | `schema_discontinuity` | tarifa_millar | progresivo | 2020 | 2022 | JAL_RAW_2021_acatic.pdf |

### Queretaro — Colon (22005)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | tarifa_millar | progresivo | 2015 | 2017 | QRO_RAW_20161271-01.pdf |

### Queretaro — El Marques (22011)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2015 | `schema_discontinuity` | tarifa_millar | progresivo | 2014 | 2017 | QRO_RAW_20151298-01.pdf |
| 2016 | `schema_discontinuity` | tarifa_millar | progresivo | 2014 | 2017 | QRO_RAW_20161271-01.pdf |

### Yucatan — Baca (31004)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | tasa_unica | cuota_fija_escalonada | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Bokoba (31005)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | progresivo | mixto | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Cacalchén (31007)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2019 | `sin_predial_residual` | — | — | — | — | 2018-12-28_2.pdf |

### Yucatan — Cansahcab (31009)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_3.pdf |

### Yucatan — Chemax (31019)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2022 | `schema_discontinuity` | mixto | progresivo | 2021 | 2023 | 2022-01-13_2.pdf |

### Yucatan — Chichimila (31021)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | progresivo | mixto | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Chicxulub Pueblo (31020)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2010 | `sin_predial_residual` | — | — | — | — | 2009-12-28_suplemento.pdf |

### Yucatan — Chochola (31023)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2017 | `edge` | otro_no_clasificado | otro_no_clasificado | 2012 | 2019 | 2017-01-03_1.pdf |
| 2018 | `edge` | otro_no_clasificado | otro_no_clasificado | 2012 | 2019 | 2018-01-15_1.pdf |
| 2022 | `schema_discontinuity` | otro_no_clasificado | mixto | 2021 | 2023 | 2022-01-13_2.pdf |

### Yucatan — Cuzamá (31015)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2021 | `sin_predial_residual` | — | — | — | — | 2020-12-28_2.pdf |
| 2022 | `sin_predial_residual` | — | — | — | — | 2021-12-31_3.pdf |

### Yucatan — Dzidzantun (31027)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2017 | `sin_predial_residual` | — | — | — | — | 2016-12-29_2.pdf |

### Yucatan — Dzidzantún (31027)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2015 | `sin_predial_residual` | — | — | — | — | 2014-12-24_2.pdf |

### Yucatan — Dzilam de Bravo (31028)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2017 | `sin_predial_residual` | — | — | — | — | 2016-12-29_2.pdf |
| 2018 | `sin_predial_residual` | — | — | — | — | 2017-12-31_3.pdf |
| 2019 | `sin_predial_residual` | — | — | — | — | 2018-12-28_2.pdf |
| 2021 | `edge` | cuota_fija_simple | tasa_unica | 2016 | 2022 | 2021-01-04_1.pdf |

### Yucatan — Dzilám de Bravo (31028)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2020 | `sin_predial_residual` | — | — | — | — | 2019-12-27_2.pdf |
| 2021 | `sin_predial_residual` | — | — | — | — | 2020-12-29_2.pdf |

### Yucatan — Hocabá (31034)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2017 | `sin_predial_residual` | — | — | — | — | 2016-12-28_2.pdf |
| 2018 | `sin_predial_residual` | — | — | — | — | 2017-12-31_2.pdf |
| 2019 | `sin_predial_residual` | — | — | — | — | 2018-12-28_2.pdf |
| 2020 | `sin_predial_residual` | — | — | — | — | 2019-12-27_2.pdf |
| 2021 | `sin_predial_residual` | — | — | — | — | 2020-12-29_2.pdf |
| 2023 | `sin_predial_residual` | — | — | — | — | 2022-12-30_4.pdf |
| 2024 | `sin_predial_residual` | — | — | — | — | 2023-12-29_3.pdf |
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_3.pdf |

### Yucatan — Hoctún (31035)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2021 | `sin_predial_residual` | — | — | — | — | 2020-12-28_2.pdf |
| 2022 | `sin_predial_residual` | — | — | — | — | 2021-12-31_3.pdf |

### Yucatan — Hunucma (31038)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2020 | `edge` | tasa_unica | progresivo | 2015 | 2024 | 2020-01-03_1.pdf |
| 2021 | `edge` | tasa_unica | progresivo | 2015 | 2024 | 2021-01-04_1.pdf |
| 2022 | `edge` | tasa_unica | progresivo | 2015 | 2024 | 2022-01-13_2.pdf |
| 2023 | `edge` | tasa_unica | progresivo | 2015 | 2024 | 2023-01-12_2.pdf |

### Yucatan — Ixil (31039)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | tasa_unica | progresivo | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Izamal (31040)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2022 | `sin_predial_residual` | — | — | — | — | 2021-12-31_3.pdf |
| 2023 | `sin_predial_residual` | — | — | — | — | 2022-12-30_4.pdf |
| 2024 | `sin_predial_residual` | — | — | — | — | 2023-12-29_3.pdf |
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_4.pdf |

### Yucatan — Mani (31047)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | tasa_unica | progresivo | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Maxcanu (31048)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | progresivo | mixto | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Motul (31052)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2015 | `sin_predial_residual` | — | — | — | — | 2014-12-24_2.pdf |
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_3.pdf |

### Yucatan — Peto (31058)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | tasa_unica | progresivo | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Progreso (31059)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2014 | `schema_discontinuity` | mixto | progresivo | 2013 | 2015 | 2014-01-10_1.pdf |

### Yucatan — Río Lagartos (31061)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_3.pdf |

### Yucatan — Samahil (31063)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2014 | `schema_discontinuity` | mixto | progresivo | 2013 | 2015 | 2014-01-10_1.pdf |

### Yucatan — San Felipe (31065)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2021 | `schema_discontinuity` | progresivo | tasa_unica | 2020 | 2022 | 2021-01-04_1.pdf |
| 2021 | `sin_predial_residual` | — | — | — | — | 2020-12-29_2.pdf |

### Yucatan — Seyé (31067)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2019 | `sin_predial_residual` | — | — | — | — | 2018-12-28_2.pdf |

### Yucatan — Sotuta (31069)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | otro_no_clasificado | progresivo | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Suma de Hidalgo ()

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2022 | `sin_predial_residual` | — | — | — | — | 2021-12-31_3.pdf |

### Yucatan — Tahdziú (31073)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2015 | `sin_predial_residual` | — | — | — | — | 2014-12-24_2.pdf |

### Yucatan — Teabo (31075)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | tarifa_millar | progresivo | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Tecoh (31076)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2024 | `sin_predial_residual` | — | — | — | — | 2023-12-29_3.pdf |
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_4.pdf |

### Yucatan — Tekantó (31078)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_3.pdf |

### Yucatan — Tekax (31079)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2015 | `sin_predial_residual` | — | — | — | — | 2014-12-31_2.pdf |
| 2018 | `schema_discontinuity` | tasa_unica | otro_no_clasificado | 2017 | 2019 | 2018-01-15_1.pdf |
| 2018 | `sin_predial_residual` | — | — | — | — | 2017-12-31_3.pdf |
| 2021 | `sin_predial_residual` | — | — | — | — | 2020-12-29_2.pdf |
| 2022 | `sin_predial_residual` | — | — | — | — | 2021-12-31_3.pdf |
| 2023 | `sin_predial_residual` | — | — | — | — | 2022-12-30_4.pdf |
| 2024 | `sin_predial_residual` | — | — | — | — | 2023-12-29_3.pdf |
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_3.pdf |

### Yucatan — Tekom (31081)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2020 | `edge` | progresivo | tasa_unica | 2015 | 2021 | 2020-01-03_1.pdf |
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_4.pdf |

### Yucatan — Telchac Puerto (31083)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2021 | `schema_discontinuity` | mixto | progresivo | 2020 | 2022 | 2021-01-04_1.pdf |

### Yucatan — Temax (31084)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2024 | `sin_predial_residual` | — | — | — | — | 2023-12-29_3.pdf |
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_3.pdf |

### Yucatan — Temozon (31085)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2013 | `schema_discontinuity` | tasa_unica | tarifa_millar | 2012 | 2014 | 2013-01-15.pdf |
| 2016 | `schema_discontinuity` | tarifa_millar | progresivo | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Temozón (31085)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2013 | `sin_predial_residual` | — | — | — | — | 2012-12-27_suplemento.pdf |

### Yucatan — Tetiz (31087)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_3.pdf |

### Yucatan — Teya (31088)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_4.pdf |

### Yucatan — Timucuy (31090)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | mixto | progresivo | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Tinum (31091)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2020 | `schema_discontinuity` | progresivo | mixto | 2019 | 2022 | 2020-01-03_1.pdf |
| 2021 | `schema_discontinuity` | progresivo | mixto | 2019 | 2022 | 2021-01-04_1.pdf |
| 2021 | `sin_predial_residual` | — | — | — | — | 2020-12-28_2.pdf |

### Yucatan — Tixkokob (31093)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | progresivo | mixto | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Tixpehual (31095)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2021 | `schema_discontinuity` | progresivo | otro_no_clasificado | 2020 | 2022 | 2021-01-04_1.pdf |

### Yucatan — Tixpéual ()

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2021 | `sin_predial_residual` | — | — | — | — | 2020-12-28_2.pdf |

### Yucatan — Uayma (31099)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_3.pdf |

### Yucatan — Ucú (31100)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2018 | `sin_predial_residual` | — | — | — | — | 2017-12-31_2.pdf |
| 2019 | `sin_predial_residual` | — | — | — | — | 2018-12-28_2.pdf |
| 2020 | `sin_predial_residual` | — | — | — | — | 2019-12-24_2.pdf |
| 2021 | `sin_predial_residual` | — | — | — | — | 2020-12-28_2.pdf |
| 2022 | `sin_predial_residual` | — | — | — | — | 2021-12-31_3.pdf |
| 2023 | `sin_predial_residual` | — | — | — | — | 2022-12-30_4.pdf |
| 2024 | `sin_predial_residual` | — | — | — | — | 2023-12-29_3.pdf |
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_4.pdf |

### Yucatan — Ucú, del Estado de ()

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2017 | `sin_predial_residual` | — | — | — | — | 2016-12-28_2.pdf |

### Yucatan — Valladolid (31102)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2015 | `sin_predial_residual` | — | — | — | — | 2014-12-31_2.pdf |
| 2017 | `sin_predial_residual` | — | — | — | — | 2016-12-29_2.pdf |
| 2018 | `sin_predial_residual` | — | — | — | — | 2017-12-31_3.pdf |
| 2019 | `sin_predial_residual` | — | — | — | — | 2018-12-28_2.pdf |
| 2020 | `sin_predial_residual` | — | — | — | — | 2019-12-27_2.pdf |
| 2021 | `sin_predial_residual` | — | — | — | — | 2020-12-29_2.pdf |
| 2022 | `sin_predial_residual` | — | — | — | — | 2021-12-31_3.pdf |
| 2023 | `sin_predial_residual` | — | — | — | — | 2022-12-30_4.pdf |
| 2024 | `sin_predial_residual` | — | — | — | — | 2023-12-29_3.pdf |
| 2025 | `sin_predial_residual` | — | — | — | — | 2024-12-30_4.pdf |

### Yucatan — Xocchel (31103)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | progresivo | mixto | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Yaxcaba (31104)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2016 | `schema_discontinuity` | mixto | progresivo | 2015 | 2017 | 2016-01-04_1.pdf |

### Yucatan — Yaxkukul (31105)

| Año | Motivo | tipo prev | tipo next | Año prev | Año next | PDF candidato |
|---|---|---|---|---:|---:|---|
| 2021 | `schema_discontinuity` | tasa_unica | otro_no_clasificado | 2020 | 2022 | 2021-01-04_1.pdf |
