# Reporte de balance — panel v2 (con reglas extendidas)

Rango temporal: **2010–2025** (16 años).
Estados incluidos: 13 (excluido: Oaxaca).

Reglas aplicadas (en orden):
`confirmed_fill` → `ffill` → `bfill` → `closure_fill` → `tipo_only_fill` → `uniform_state_fill`.
Estados con `uniform_state_fill`: Chihuahua, Colima, Estado de México, Sinaloa, Tabasco.

## 1. Métricas globales

- Municipios en universo (excl. Oaxaca): **746**
- Cobertura ideal (ajustada por creation_year): 11,894 celdas
- Panel balanceado: **11,825** celdas (**99.4%** cobertura)
  - Observaciones crudas: 10,782
  - Imputadas: 1,043
    - `confirmed_fill`: 511
    - `bfill`: 223
    - `ffill`: 161
    - `closure_fill`: 87
    - `tipo_only_fill`: 24
    - `uniform_state_fill`: 4
- Huecos remanentes: **69** (0.6%)

## 2. Cobertura por estado

| Estado | Munis | Ideal | Crudo | Balanceado | Cov. cruda | Cov. balanceada | Huecos |
|---|---:|---:|---:|---:|---:|---:|---:|
| Chihuahua | 67 | 1072 | 1072 | 1072 | 100.0% | 100.0% | 0 |
| Coahuila de Zaragoza | 38 | 608 | 579 | 608 | 95.2% | 100.0% | 0 |
| Colima | 10 | 160 | 160 | 160 | 100.0% | 100.0% | 0 |
| Guanajuato | 46 | 736 | 594 | 736 | 80.7% | 100.0% | 0 |
| Jalisco | 125 | 2000 | 1976 | 2000 | 98.8% | 100.0% | 0 |
| Mexico | 125 | 2000 | 2000 | 2000 | 100.0% | 100.0% | 0 |
| Queretaro | 18 | 288 | 286 | 288 | 99.3% | 100.0% | 0 |
| Sinaloa | 20 | 292 | 288 | 292 | 98.6% | 100.0% | 0 |
| Tabasco | 17 | 272 | 272 | 272 | 100.0% | 100.0% | 0 |
| Tamaulipas | 43 | 688 | 685 | 688 | 99.6% | 100.0% | 0 |
| Yucatan | 106 | 1696 | 1522 | 1696 | 89.7% | 100.0% | 0 |
| San Luis Potosi | 59 | 930 | 578 | 925 | 62.2% | 99.5% | 5 |
| Sonora | 72 | 1152 | 770 | 1088 | 66.8% | 94.4% | 64 |

## 3. Fuentes de desbalance

### 3.1 Municipios sin ningún dato observado (2)

Para los munis en estados uniformes (Chihuahua, Colima, EdoMex, Sinaloa, Tabasco) la regla `uniform_state_fill` ya completó la cobertura. Los demás siguen sin dato y requieren búsqueda manual.

| cvegeo | Estado | Municipio | Cubierto via uniform_state_fill |
|---|---|---|:---:|
| 25019 | Sinaloa | Eldorado | sí |
| 25020 | Sinaloa | Juan Jose Rios | sí |

### 3.2 Huecos remanentes por motivo (102)

| Motivo | Conteo | Significado |
|---|---:|---|
| `schema_discontinuity` | 88 | tipo_esquema/rangos/monto_max difieren entre las observaciones que rodean el hueco; tipo_only_fill solo aplica si tipo_esquema coincide. |
| `long_gap` | 9 | Hueco > 4 años desde la observación más cercana → ffill/bfill no aplican; closure_fill tampoco (extremos no coinciden). |
| `edge` | 5 | Hueco al inicio/fin de la ventana sin observación cercana del lado faltante. |

### 3.3 Huecos remanentes por estado

| Estado | Huecos remanentes |
|---|---:|
| Sonora | 69 |
| Yucatan | 25 |
| San Luis Potosi | 5 |
| Guanajuato | 3 |

### 3.4 Discontinuidades de esquema en gaps ≤ 4 años (109)

De estas, **88** son cambios de `tipo_esquema` (siguen bloqueando imputación) y **21** son solo cambios de rangos/monto (cubiertas por `tipo_only_fill`).

| cvegeo | Estado | Municipio | Año A | Año B | Gap | tipo coincide | Cambio |
|---|---|---|---:|---:|---:|:---:|---|
| 26021 | Sonora | La Colorada | 2012 | 2017 | 4 | **no** | tipo:tarifa_millar→progresivo | rangos:→11 | monto_max:→2316072.0 |
| 26031 | Sonora | Huachinera | 2012 | 2017 | 4 | **no** | tipo:tarifa_millar→progresivo | rangos:→11 | monto_max:→2316072.0 |
| 26039 | Sonora | Naco | 2010 | 2015 | 4 | **no** | tipo:tarifa_millar→mixto | rangos:→11 | monto_max:→2316072.0 |
| 26048 | Sonora | Puerto Peñasco | 2011 | 2016 | 4 | **no** | tipo:tarifa_millar→otro_no_clasificado |
| 26050 | Sonora | Rayon | 2010 | 2015 | 4 | **no** | tipo:progresivo→mixto | rangos:8→6 | monto_max:1060473.0→441864.0 |
| 26060 | Sonora | Saric | 2012 | 2017 | 4 | **no** | tipo:progresivo→tarifa_millar | rangos:7→ | monto_max:706982.0→ |
| 31028 | Yucatan | Dzilam de Bravo | 2016 | 2021 | 4 | **no** | tipo:cuota_fija_simple→tasa_unica |
| 31034 | Yucatan | Hocaba | 2014 | 2019 | 4 | **no** | tipo:otro_no_clasificado→desconocido |
| 31079 | Yucatan | Tekax | 2020 | 2025 | 4 | **no** | tipo:tasa_unica→otro_no_clasificado |
| 31081 | Yucatan | Tekom | 2015 | 2020 | 4 | **no** | tipo:progresivo→tasa_unica | rangos:7→ | monto_max:10000.0→ |
| 31102 | Yucatan | Valladolid | 2013 | 2018 | 4 | **no** | tipo:mixto→progresivo | rangos:5→ | monto_max:135000.0→ |
| 26049 | Sonora | Quiriego | 2013 | 2017 | 3 | **no** | tipo:tarifa_millar→progresivo | rangos:→5 | monto_max:→259920.0 |
| 26061 | Sonora | Soyopa | 2013 | 2017 | 3 | **no** | tipo:tarifa_millar→progresivo | rangos:→11 | monto_max:→2316072.0 |
| 26010 | Sonora | Bacerac | 2010 | 2013 | 2 | **no** | tipo:progresivo→tarifa_millar | rangos:8→ | monto_max:1060473.0→ |
| 26017 | Sonora | Caborca | 2014 | 2017 | 2 | **no** | tipo:mixto→progresivo |
| 26020 | Sonora | Carbo | 2014 | 2017 | 2 | **no** | tipo:mixto→progresivo |
| 26020 | Sonora | Carbo | 2017 | 2020 | 2 | **no** | tipo:progresivo→tarifa_millar | rangos:11→ | monto_max:2316072.0→ |
| 26024 | Sonora | Divisaderos | 2014 | 2017 | 2 | **no** | tipo:mixto→tarifa_millar | rangos:4→ | monto_max:144400.0→ |
| 26029 | Sonora | Guaymas | 2014 | 2017 | 2 | **no** | tipo:tasa_unica→tarifa_millar |
| 26041 | Sonora | Nacozari de Garcia | 2014 | 2017 | 2 | **no** | tipo:mixto→progresivo |
| 26042 | Sonora | Navojoa | 2020 | 2023 | 2 | **no** | tipo:tarifa_millar→progresivo | rangos:→12 | monto_max:→10850000.0 |
| 26049 | Sonora | Quiriego | 2020 | 2023 | 2 | **no** | tipo:progresivo→tarifa_millar | rangos:5→ | monto_max:259920.0→ |
| 26052 | Sonora | Sahuaripa | 2020 | 2023 | 2 | **no** | tipo:progresivo→tarifa_millar | rangos:7→ | monto_max:706982.0→ |
| 26053 | Sonora | San Felipe de Jesus | 2020 | 2023 | 2 | **no** | tipo:progresivo→tarifa_millar | rangos:5→ | monto_max:259920.0→ |
| 26054 | Sonora | San Javier | 2011 | 2014 | 2 | **no** | tipo:progresivo→mixto | monto_max:2516072.0→2316072.0 |
| 26054 | Sonora | San Javier | 2020 | 2023 | 2 | **no** | tipo:tarifa_millar→progresivo | rangos:→11 | monto_max:→2316072.0 |
| 26055 | Sonora | San Luis Rio Colorado | 2013 | 2016 | 2 | **no** | tipo:progresivo→tarifa_millar | rangos:2→ | monto_max:34000.0→ |
| 26069 | Sonora | Yecora | 2020 | 2023 | 2 | **no** | tipo:tarifa_millar→progresivo | rangos:→11 | monto_max:→2316072.0 |
| 26072 | Sonora | San Ignacio Rio Muerto | 2013 | 2016 | 2 | **no** | tipo:tarifa_millar→progresivo | rangos:→11 | monto_max:→2316072.0 |
| 11017 | Guanajuato | Irapuato | 2020 | 2022 | 1 | **no** | tipo:mixto→progresivo |
| ... | | | | | | | (+79 más) |

### 3.5 Top municipios con más huecos remanentes

| cvegeo | Estado | Municipio | Huecos |
|---|---|---|---:|
| 24032 | San Luis Potosi | Santa Maria del Rio | 5 |
| 26020 | Sonora | Carbo | 5 |
| 26044 | Sonora | onavas | 5 |
| 26054 | Sonora | San Javier | 5 |
| 26039 | Sonora | Naco | 4 |
| 26048 | Sonora | Puerto Peñasco | 4 |
| 26050 | Sonora | Rayon | 4 |
| 31028 | Yucatan | Dzilam de Bravo | 4 |
| 31034 | Yucatan | Hocaba | 4 |
| 31079 | Yucatan | Tekax | 4 |
| 31081 | Yucatan | Tekom | 4 |
| 31102 | Yucatan | Valladolid | 4 |
| 26017 | Sonora | Caborca | 3 |
| 26053 | Sonora | San Felipe de Jesus | 3 |
| 26055 | Sonora | San Luis Rio Colorado | 3 |
| 26066 | Sonora | Ures | 3 |
| 26069 | Sonora | Yecora | 3 |
| 26010 | Sonora | Bacerac | 2 |
| 26014 | Sonora | Baviacora | 2 |
| 26019 | Sonora | Cananea | 2 |

## 4. Sugerencias human-in-the-loop

Una fila por muni con huecos. Ordenadas por número de huecos (descendente).

**Resumen por motivo principal:**
- `schema_discontinuity`: 40 munis
- `long_gap`: 3 munis
- `edge`: 2 munis

| cvegeo | Estado | Municipio | Huecos | Años | Motivo | Obs válidas | Acción sugerida |
|---|---|---|---:|---|---|---:|---|
| 24032 | San Luis Potosi | Santa Maria del Rio | 5 | 2010,2011,2012,2013,2014 | `long_gap` | 6 | Hueco temporal largo (>4 años): 2010–2014. Re-ejecutar la extracción para esos años con `python -m scripts.run_pipeline san luis potosi --steps download,segment,extract` y validar los PDFs en `data/san luis potosi/pdf_raw/`. |
| 26020 | Sonora | Carbo | 5 | 2015,2016,2018,2019,2024 | `schema_discontinuity` | 9 | Auditar manualmente PDFs de los años 2015, 2016, 2018 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26044 | Sonora | onavas | 5 | 2010,2011,2012,2018,2024 | `long_gap` | 6 | Hueco temporal largo (>4 años): 2010–2024. Re-ejecutar la extracción para esos años con `python -m scripts.run_pipeline sonora --steps download,segment,extract` y validar los PDFs en `data/sonora/pdf_raw/`. |
| 26054 | Sonora | San Javier | 5 | 2012,2013,2021,2022,2024 | `schema_discontinuity` | 10 | Auditar manualmente PDFs de los años 2012, 2013, 2021 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26039 | Sonora | Naco | 4 | 2011,2012,2013,2014 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2011, 2012, 2013 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26048 | Sonora | Puerto Peñasco | 4 | 2012,2013,2014,2015 | `schema_discontinuity` | 11 | Auditar manualmente PDFs de los años 2012, 2013, 2014 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26050 | Sonora | Rayon | 4 | 2011,2012,2013,2014 | `schema_discontinuity` | 8 | Auditar manualmente PDFs de los años 2011, 2012, 2013 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31028 | Yucatan | Dzilam de Bravo | 4 | 2017,2018,2019,2020 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2017, 2018, 2019 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31034 | Yucatan | Hocaba | 4 | 2015,2016,2017,2018 | `schema_discontinuity` | 11 | Auditar manualmente PDFs de los años 2015, 2016, 2017 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31079 | Yucatan | Tekax | 4 | 2021,2022,2023,2024 | `schema_discontinuity` | 10 | Auditar manualmente PDFs de los años 2021, 2022, 2023 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31081 | Yucatan | Tekom | 4 | 2016,2017,2018,2019 | `schema_discontinuity` | 9 | Auditar manualmente PDFs de los años 2016, 2017, 2018 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31102 | Yucatan | Valladolid | 4 | 2014,2015,2016,2017 | `schema_discontinuity` | 11 | Auditar manualmente PDFs de los años 2014, 2015, 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26017 | Sonora | Caborca | 3 | 2015,2016,2021 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2015, 2016, 2021 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26053 | Sonora | San Felipe de Jesus | 3 | 2016,2021,2022 | `schema_discontinuity` | 7 | Auditar manualmente PDFs de los años 2021, 2022 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26055 | Sonora | San Luis Rio Colorado | 3 | 2014,2015,2022 | `schema_discontinuity` | 9 | Auditar manualmente PDFs de los años 2014, 2015, 2022 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26066 | Sonora | Ures | 3 | 2018,2019,2021 | `edge` | 7 | Hueco al borde de la ventana (2018–2021). Probable que falte el PDF más reciente o el más antiguo. Revisar `data/sonora/pdf_raw/` y completar. |
| 26069 | Sonora | Yecora | 3 | 2013,2021,2022 | `schema_discontinuity` | 10 | Auditar manualmente PDFs de los años 2013, 2021, 2022 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26010 | Sonora | Bacerac | 2 | 2011,2012 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2011, 2012 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26014 | Sonora | Baviacora | 2 | 2013,2018 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2013, 2018 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26019 | Sonora | Cananea | 2 | 2015,2022 | `schema_discontinuity` | 10 | Auditar manualmente PDFs de los años 2015, 2022 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26024 | Sonora | Divisaderos | 2 | 2015,2016 | `schema_discontinuity` | 13 | Auditar manualmente PDFs de los años 2015, 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26041 | Sonora | Nacozari de Garcia | 2 | 2015,2016 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2015, 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26042 | Sonora | Navojoa | 2 | 2021,2022 | `schema_discontinuity` | 10 | Auditar manualmente PDFs de los años 2021, 2022 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26059 | Sonora | Santa Cruz | 2 | 2015,2016 | `edge` | 6 | Hueco al borde de la ventana (2015–2016). Probable que falte el PDF más reciente o el más antiguo. Revisar `data/sonora/pdf_raw/` y completar. |
| 11017 | Guanajuato | Irapuato | 1 | 2021 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2021 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 11020 | Guanajuato | Leon | 1 | 2013 | `schema_discontinuity` | 13 | Auditar manualmente PDFs de los años 2013 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 11031 | Guanajuato | San Francisco del Rincon | 1 | 2025 | `long_gap` | 8 | Hueco temporal largo (>4 años): 2025–2025. Re-ejecutar la extracción para esos años con `python -m scripts.run_pipeline guanajuato --steps download,segment,extract` y validar los PDFs en `data/guanajuato/pdf_raw/`. |
| 26001 | Sonora | Aconchi | 1 | 2019 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2019 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26007 | Sonora | Atil | 1 | 2019 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2019 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26012 | Sonora | Bacum | 1 | 2011 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2011 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26013 | Sonora | Banamichi | 1 | 2019 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2019 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26022 | Sonora | Cucurpe | 1 | 2015 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2015 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26023 | Sonora | Cumpas | 1 | 2019 | `schema_discontinuity` | 13 | Auditar manualmente PDFs de los años 2019 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26033 | Sonora | Huatabampo | 1 | 2014 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2014 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26035 | Sonora | Imuris | 1 | 2016 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26037 | Sonora | Mazatan | 1 | 2022 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2022 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26047 | Sonora | Pitiquito | 1 | 2022 | `schema_discontinuity` | 10 | Auditar manualmente PDFs de los años 2022 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26063 | Sonora | Tepache | 1 | 2015 | `schema_discontinuity` | 11 | Auditar manualmente PDFs de los años 2015 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26068 | Sonora | Villa Pesqueira | 1 | 2019 | `schema_discontinuity` | 7 | Auditar manualmente PDFs de los años 2019 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 26070 | Sonora | General Plutarco Elias Calles | 1 | 2019 | `schema_discontinuity` | 13 | Auditar manualmente PDFs de los años 2019 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31048 | Yucatan | Maxcanu | 1 | 2016 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31090 | Yucatan | Timucuy | 1 | 2016 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31093 | Yucatan | Tixkokob | 1 | 2016 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31103 | Yucatan | Xocchel | 1 | 2016 | `schema_discontinuity` | 15 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31104 | Yucatan | Yaxcaba | 1 | 2016 | `schema_discontinuity` | 14 | Auditar manualmente PDFs de los años 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |

## 5. Comandos útiles para reextracción

```bash
# Reextracción de un muni-año específico (revisar primero el PDF crudo)
python -m scripts.run_pipeline {estado} --steps extract --slug {slug} --year {YYYY}

# Auditar discontinuidad: comparar JSON antes y después
python -m scripts.regression_v1_v2 --cvegeo {cvegeo} --years {YYYY,YYYY}

# Marcar una observación como 'excluir' en el audit CSV correspondiente
# (data/{estado}/qa/audit_{PREFIJO}.csv) para que el panel la ignore.
```
