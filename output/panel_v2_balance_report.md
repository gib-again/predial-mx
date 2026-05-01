# Reporte de balance — panel v2 (con reglas extendidas)

Rango temporal: **2010–2025** (16 años).
Estados incluidos: 11 (excluido: Oaxaca).

Reglas aplicadas (en orden):
`confirmed_fill` → `ffill` → `bfill` → `closure_fill` → `tipo_only_fill` → `uniform_state_fill`.
Estados con `uniform_state_fill`: Chihuahua, Colima, Estado de México, Sinaloa, Tabasco.

## 1. Métricas globales

- Municipios en universo (excl. Oaxaca): **615**
- Cobertura ideal (ajustada por creation_year): 9,812 celdas
- Panel balanceado: **9,738** celdas (**99.2%** cobertura)
  - Observaciones crudas: 9,369
  - Imputadas: 369
    - `confirmed_fill`: 240
    - `ffill`: 88
    - `bfill`: 17
    - `tipo_only_fill`: 13
    - `closure_fill`: 7
    - `uniform_state_fill`: 4
- Huecos remanentes: **74** (0.8%)

## 2. Cobertura por estado

| Estado | Munis | Ideal | Crudo | Balanceado | Cov. cruda | Cov. balanceada | Huecos |
|---|---:|---:|---:|---:|---:|---:|---:|
| Chihuahua | 67 | 1072 | 1072 | 1072 | 100.0% | 100.0% | 0 |
| Coahuila de Zaragoza | 38 | 608 | 579 | 608 | 95.2% | 100.0% | 0 |
| Colima | 10 | 160 | 160 | 160 | 100.0% | 100.0% | 0 |
| Jalisco | 125 | 2000 | 1975 | 1999 | 98.8% | 100.0% | 1 |
| Mexico | 125 | 2000 | 2000 | 2000 | 100.0% | 100.0% | 0 |
| Sinaloa | 20 | 292 | 288 | 292 | 98.6% | 100.0% | 0 |
| Tabasco | 17 | 272 | 272 | 272 | 100.0% | 100.0% | 0 |
| Tamaulipas | 43 | 688 | 685 | 688 | 99.6% | 100.0% | 0 |
| Queretaro | 18 | 288 | 275 | 285 | 95.5% | 99.0% | 3 |
| Guanajuato | 46 | 736 | 587 | 726 | 79.8% | 98.6% | 10 |
| Yucatan | 106 | 1696 | 1476 | 1636 | 87.0% | 96.5% | 60 |

## 3. Fuentes de desbalance

### 3.1 Municipios sin ningún dato observado (2)

Para los munis en estados uniformes (Chihuahua, Colima, EdoMex, Sinaloa, Tabasco) la regla `uniform_state_fill` ya completó la cobertura. Los demás siguen sin dato y requieren búsqueda manual.

| cvegeo | Estado | Municipio | Cubierto via uniform_state_fill |
|---|---|---|:---:|
| 25019 | Sinaloa | Eldorado | sí |
| 25020 | Sinaloa | Juan Jose Rios | sí |

### 3.2 Huecos remanentes por motivo (74)

| Motivo | Conteo | Significado |
|---|---:|---|
| `schema_discontinuity` | 40 | tipo_esquema/rangos/monto_max difieren entre las observaciones que rodean el hueco; tipo_only_fill solo aplica si tipo_esquema coincide. |
| `long_gap` | 26 | Hueco > 4 años desde la observación más cercana → ffill/bfill no aplican; closure_fill tampoco (extremos no coinciden). |
| `edge` | 8 | Hueco al inicio/fin de la ventana sin observación cercana del lado faltante. |

### 3.3 Huecos remanentes por estado

| Estado | Huecos remanentes |
|---|---:|
| Yucatan | 60 |
| Guanajuato | 10 |
| Queretaro | 3 |
| Jalisco | 1 |

### 3.4 Discontinuidades de esquema en gaps ≤ 4 años (52)

De estas, **42** son cambios de `tipo_esquema` (siguen bloqueando imputación) y **10** son solo cambios de rangos/monto (cubiertas por `tipo_only_fill`).

| cvegeo | Estado | Municipio | Año A | Año B | Gap | tipo coincide | Cambio |
|---|---|---|---:|---:|---:|:---:|---|
| 11015 | Guanajuato | Guanajuato | 2020 | 2023 | 2 | **no** | tipo:tarifa_millar→progresivo | rangos:→7 | monto_max:→9600000.0 |
| 22011 | Queretaro | El Marques | 2014 | 2017 | 2 | **no** | tipo:tarifa_millar→progresivo | rangos:→25 | monto_max:→919090835.66 |
| 31091 | Yucatan | Tinum | 2019 | 2022 | 2 | **no** | tipo:progresivo→mixto |
| 11003 | Guanajuato | San Miguel de Allende | 2012 | 2014 | 1 | **no** | tipo:tarifa_millar→mixto | rangos:→6 | monto_max:→9000.0 |
| 11007 | Guanajuato | Celaya | 2018 | 2020 | 1 | **no** | tipo:tarifa_millar→progresivo | rangos:→5 | monto_max:→18335436.71 |
| 11014 | Guanajuato | Dolores Hidalgo Cuna de la Independencia Nacional | 2020 | 2022 | 1 | **no** | tipo:tarifa_millar→mixto | rangos:→10 | monto_max:→2900000.0 |
| 11017 | Guanajuato | Irapuato | 2020 | 2022 | 1 | **no** | tipo:mixto→progresivo |
| 11020 | Guanajuato | Leon | 2012 | 2014 | 1 | **no** | tipo:progresivo→mixto |
| 11020 | Guanajuato | Leon | 2023 | 2025 | 1 | **no** | tipo:progresivo→mixto | rangos:6→9 | monto_max:49673145.6→198692582.4 |
| 11033 | Guanajuato | San Luis de la Paz | 2023 | 2025 | 1 | **no** | tipo:tarifa_millar→progresivo | rangos:→9 | monto_max:→1200000.0 |
| 11036 | Guanajuato | Santiago Maravatio | 2023 | 2025 | 1 | **no** | tipo:tarifa_millar→mixto | rangos:→7 | monto_max:→4226664.64 |
| 14071 | Jalisco | San Cristobal de la Barranca | 2020 | 2022 | 1 | **no** | tipo:tarifa_millar→progresivo | rangos:→10 | monto_max:→52000000.0 |
| 22005 | Queretaro | Colon | 2015 | 2017 | 1 | **no** | tipo:tarifa_millar→progresivo | rangos:→25 | monto_max:→100143891.1 |
| 28040 | Tamaulipas | Valle Hermoso | 2017 | 2019 | 1 | **no** | tipo:progresivo→mixto |
| 31004 | Yucatan | Baca | 2015 | 2017 | 1 | **no** | tipo:tasa_unica→cuota_fija_escalonada | rangos:→7 | monto_max:→800000.0 |
| 31005 | Yucatan | Bokoba | 2015 | 2017 | 1 | **no** | tipo:progresivo→mixto | rangos:7→6 |
| 31007 | Yucatan | Cacalchen | 2018 | 2020 | 1 | **no** | tipo:progresivo→mixto |
| 31019 | Yucatan | Chemax | 2021 | 2023 | 1 | **no** | tipo:mixto→progresivo |
| 31021 | Yucatan | Chichimila | 2015 | 2017 | 1 | **no** | tipo:progresivo→mixto |
| 31023 | Yucatan | Chochola | 2021 | 2023 | 1 | **no** | tipo:otro_no_clasificado→mixto | rangos:→2 | monto_max:→22000.0 |
| 31033 | Yucatan | Halacho | 2022 | 2024 | 1 | **no** | tipo:progresivo→mixto |
| 31039 | Yucatan | Ixil | 2015 | 2017 | 1 | **no** | tipo:tasa_unica→progresivo | rangos:→6 | monto_max:→15500.0 |
| 31046 | Yucatan | Mama | 2015 | 2017 | 1 | **no** | tipo:tasa_unica→tarifa_millar |
| 31047 | Yucatan | Mani | 2015 | 2017 | 1 | **no** | tipo:tasa_unica→progresivo | rangos:→6 | monto_max:→100000.0 |
| 31048 | Yucatan | Maxcanu | 2015 | 2017 | 1 | **no** | tipo:progresivo→mixto |
| 31058 | Yucatan | Peto | 2015 | 2017 | 1 | **no** | tipo:tasa_unica→progresivo | rangos:→12 | monto_max:→2000000.0 |
| 31059 | Yucatan | Progreso | 2013 | 2015 | 1 | **no** | tipo:mixto→progresivo |
| 31062 | Yucatan | Sacalum | 2015 | 2017 | 1 | **no** | tipo:mixto→otro_no_clasificado | rangos:7→ | monto_max:49900.0→ |
| 31063 | Yucatan | Samahil | 2013 | 2015 | 1 | **no** | tipo:mixto→progresivo |
| 31065 | Yucatan | San Felipe | 2020 | 2022 | 1 | **no** | tipo:progresivo→tasa_unica | rangos:7→ | monto_max:10000.0→ |
| ... | | | | | | | (+22 más) |

### 3.5 Top municipios con más huecos remanentes

| cvegeo | Estado | Municipio | Huecos |
|---|---|---|---:|
| 31102 | Yucatan | Valladolid | 8 |
| 31034 | Yucatan | Hocaba | 7 |
| 31073 | Yucatan | Tahdziu | 5 |
| 31100 | Yucatan | Ucu | 5 |
| 31038 | Yucatan | Hunucma | 4 |
| 31023 | Yucatan | Chochola | 3 |
| 11015 | Guanajuato | Guanajuato | 2 |
| 11020 | Guanajuato | Leon | 2 |
| 22011 | Queretaro | El Marques | 2 |
| 31079 | Yucatan | Tekax | 2 |
| 31085 | Yucatan | Temozon | 2 |
| 31091 | Yucatan | Tinum | 2 |
| 11003 | Guanajuato | San Miguel de Allende | 1 |
| 11007 | Guanajuato | Celaya | 1 |
| 11014 | Guanajuato | Dolores Hidalgo Cuna de la Independencia Nacional | 1 |
| 11017 | Guanajuato | Irapuato | 1 |
| 11033 | Guanajuato | San Luis de la Paz | 1 |
| 11036 | Guanajuato | Santiago Maravatio | 1 |
| 14071 | Jalisco | San Cristobal de la Barranca | 1 |
| 22005 | Queretaro | Colon | 1 |

## 4. Sugerencias human-in-the-loop

Una fila por muni con huecos. Ordenadas por número de huecos (descendente).

**Resumen por motivo principal:**
- `schema_discontinuity`: 34 munis
- `edge`: 4 munis
- `long_gap`: 4 munis

| cvegeo | Estado | Municipio | Huecos | Años | Motivo | Obs válidas | Acción sugerida |
|---|---|---|---:|---|---|---:|---|
| 31102 | Yucatan | Valladolid | 8 | 2018,2019,2020,2021,2022,2023,2024,2025 | `long_gap` | 4 | Hueco temporal largo (>4 años): 2018–2025. Re-ejecutar la extracción para esos años con `python -m scripts.run_pipeline yucatan --steps download,segment,extract` y validar los PDFs en `data/yucatan/pdf_raw/`. |
| 31034 | Yucatan | Hocaba | 7 | 2019,2020,2021,2022,2023,2024,2025 | `long_gap` | 4 | Hueco temporal largo (>4 años): 2019–2025. Re-ejecutar la extracción para esos años con `python -m scripts.run_pipeline yucatan --steps download,segment,extract` y validar los PDFs en `data/yucatan/pdf_raw/`. |
| 31073 | Yucatan | Tahdziu | 5 | 2021,2022,2023,2024,2025 | `long_gap` | 6 | Hueco temporal largo (>4 años): 2021–2025. Re-ejecutar la extracción para esos años con `python -m scripts.run_pipeline yucatan --steps download,segment,extract` y validar los PDFs en `data/yucatan/pdf_raw/`. |
| 31100 | Yucatan | Ucu | 5 | 2021,2022,2023,2024,2025 | `long_gap` | 7 | Hueco temporal largo (>4 años): 2021–2025. Re-ejecutar la extracción para esos años con `python -m scripts.run_pipeline yucatan --steps download,segment,extract` y validar los PDFs en `data/yucatan/pdf_raw/`. |
| 31038 | Yucatan | Hunucma | 4 | 2020,2021,2022,2023 | `edge` | 8 | Hueco al borde de la ventana (2020–2023). Probable que falte el PDF más reciente o el más antiguo. Revisar `data/yucatan/pdf_raw/` y completar. |
| 31023 | Yucatan | Chochola | 3 | 2017,2018,2022 | `edge` | 8 | Hueco al borde de la ventana (2017–2022). Probable que falte el PDF más reciente o el más antiguo. Revisar `data/yucatan/pdf_raw/` y completar. |
| 11015 | Guanajuato | Guanajuato | 2 | 2021,2022 | `schema_discontinuity` | 10 | Auditar manualmente PDFs de los años 2021, 2022 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 11020 | Guanajuato | Leon | 2 | 2013,2024 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2013, 2024 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 22011 | Queretaro | El Marques | 2 | 2015,2016 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2015, 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31079 | Yucatan | Tekax | 2 | 2018,2025 | `schema_discontinuity` | 8 | Auditar manualmente PDFs de los años 2018 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31085 | Yucatan | Temozon | 2 | 2013,2016 | `schema_discontinuity` | 13 | Auditar manualmente PDFs de los años 2013, 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31091 | Yucatan | Tinum | 2 | 2020,2021 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2020, 2021 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 11003 | Guanajuato | San Miguel de Allende | 1 | 2013 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2013 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 11007 | Guanajuato | Celaya | 1 | 2019 | `schema_discontinuity` | 11 | Auditar manualmente PDFs de los años 2019 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 11014 | Guanajuato | Dolores Hidalgo Cuna de la Independencia Nacional | 1 | 2021 | `schema_discontinuity` | 13 | Auditar manualmente PDFs de los años 2021 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 11017 | Guanajuato | Irapuato | 1 | 2021 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2021 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 11033 | Guanajuato | San Luis de la Paz | 1 | 2024 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2024 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 11036 | Guanajuato | Santiago Maravatio | 1 | 2024 | `schema_discontinuity` | 13 | Auditar manualmente PDFs de los años 2024 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 14071 | Jalisco | San Cristobal de la Barranca | 1 | 2021 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2021 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 22005 | Queretaro | Colon | 1 | 2016 | `schema_discontinuity` | 13 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31004 | Yucatan | Baca | 1 | 2016 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31005 | Yucatan | Bokoba | 1 | 2016 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31019 | Yucatan | Chemax | 1 | 2022 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2022 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31021 | Yucatan | Chichimila | 1 | 2016 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31028 | Yucatan | Dzilam de Bravo | 1 | 2021 | `edge` | 11 | Hueco al borde de la ventana (2021–2021). Probable que falte el PDF más reciente o el más antiguo. Revisar `data/yucatan/pdf_raw/` y completar. |
| 31039 | Yucatan | Ixil | 1 | 2016 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31047 | Yucatan | Mani | 1 | 2016 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31048 | Yucatan | Maxcanu | 1 | 2016 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31058 | Yucatan | Peto | 1 | 2016 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31059 | Yucatan | Progreso | 1 | 2014 | `schema_discontinuity` | 13 | Auditar manualmente PDFs de los años 2014 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31063 | Yucatan | Samahil | 1 | 2014 | `schema_discontinuity` | 13 | Auditar manualmente PDFs de los años 2014 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31065 | Yucatan | San Felipe | 1 | 2021 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2021 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31069 | Yucatan | Sotuta | 1 | 2016 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31075 | Yucatan | Teabo | 1 | 2016 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31081 | Yucatan | Tekom | 1 | 2020 | `edge` | 8 | Hueco al borde de la ventana (2020–2020). Probable que falte el PDF más reciente o el más antiguo. Revisar `data/yucatan/pdf_raw/` y completar. |
| 31083 | Yucatan | Telchac Puerto | 1 | 2021 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2021 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31090 | Yucatan | Timucuy | 1 | 2016 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31093 | Yucatan | Tixkokob | 1 | 2016 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31095 | Yucatan | Tixpehual | 1 | 2021 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2021 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31103 | Yucatan | Xocchel | 1 | 2016 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31104 | Yucatan | Yaxcaba | 1 | 2016 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31105 | Yucatan | Yaxkukul | 1 | 2021 | `schema_discontinuity` | 13 | Auditar manualmente PDFs de los años 2021 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |

## 5. Comandos útiles para reextracción

```bash
# Reextracción de un muni-año específico (revisar primero el PDF crudo)
python -m scripts.run_pipeline {estado} --steps extract --slug {slug} --year {YYYY}

# Auditar discontinuidad: comparar JSON antes y después
python -m scripts.regression_v1_v2 --cvegeo {cvegeo} --years {YYYY,YYYY}

# Marcar una observación como 'excluir' en el audit CSV correspondiente
# (data/{estado}/qa/audit_{PREFIJO}.csv) para que el panel la ignore.
```
