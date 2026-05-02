# Reporte de balance — panel v2 (con reglas extendidas)

Rango temporal: **2010–2025** (16 años).
Estados incluidos: 11 (excluido: Oaxaca).

Reglas aplicadas (en orden):
`confirmed_fill` → `ffill` → `bfill` → `closure_fill` → `tipo_only_fill` → `uniform_state_fill`.
Estados con `uniform_state_fill`: Chihuahua, Colima, Estado de México, Sinaloa, Tabasco.

## 1. Métricas globales

- Municipios en universo (excl. Oaxaca): **615**
- Cobertura ideal (ajustada por creation_year): 9,812 celdas
- Panel balanceado: **9,812** celdas (**100.0%** cobertura)
  - Observaciones crudas: 9,452
  - Imputadas: 360
    - `confirmed_fill`: 255
    - `ffill`: 50
    - `bfill`: 16
    - `tipo_only_fill`: 8
    - `closure_fill`: 7
    - `uniform_state_fill`: 4
- Huecos remanentes: **0** (0.0%)

## 2. Cobertura por estado

| Estado | Munis | Ideal | Crudo | Balanceado | Cov. cruda | Cov. balanceada | Huecos |
|---|---:|---:|---:|---:|---:|---:|---:|
| Chihuahua | 67 | 1072 | 1072 | 1072 | 100.0% | 100.0% | 0 |
| Coahuila de Zaragoza | 38 | 608 | 579 | 608 | 95.2% | 100.0% | 0 |
| Colima | 10 | 160 | 160 | 160 | 100.0% | 100.0% | 0 |
| Guanajuato | 46 | 736 | 597 | 736 | 81.1% | 100.0% | 0 |
| Jalisco | 125 | 2000 | 1976 | 2000 | 98.8% | 100.0% | 0 |
| Mexico | 125 | 2000 | 2000 | 2000 | 100.0% | 100.0% | 0 |
| Queretaro | 18 | 288 | 286 | 288 | 99.3% | 100.0% | 0 |
| Sinaloa | 20 | 292 | 288 | 292 | 98.6% | 100.0% | 0 |
| Tabasco | 17 | 272 | 272 | 272 | 100.0% | 100.0% | 0 |
| Tamaulipas | 43 | 688 | 685 | 688 | 99.6% | 100.0% | 0 |
| Yucatan | 106 | 1696 | 1537 | 1696 | 90.6% | 100.0% | 0 |

## 3. Fuentes de desbalance

### 3.1 Municipios sin ningún dato observado (2)

Para los munis en estados uniformes (Chihuahua, Colima, EdoMex, Sinaloa, Tabasco) la regla `uniform_state_fill` ya completó la cobertura. Los demás siguen sin dato y requieren búsqueda manual.

| cvegeo | Estado | Municipio | Cubierto via uniform_state_fill |
|---|---|---|:---:|
| 25019 | Sinaloa | Eldorado | sí |
| 25020 | Sinaloa | Juan Jose Rios | sí |

### 3.2 Huecos remanentes por motivo (20)

| Motivo | Conteo | Significado |
|---|---:|---|
| `schema_discontinuity` | 20 | tipo_esquema/rangos/monto_max difieren entre las observaciones que rodean el hueco; tipo_only_fill solo aplica si tipo_esquema coincide. |

### 3.3 Huecos remanentes por estado

| Estado | Huecos remanentes |
|---|---:|
| Yucatan | 20 |

### 3.4 Discontinuidades de esquema en gaps ≤ 4 años (18)

De estas, **10** son cambios de `tipo_esquema` (siguen bloqueando imputación) y **8** son solo cambios de rangos/monto (cubiertas por `tipo_only_fill`).

| cvegeo | Estado | Municipio | Año A | Año B | Gap | tipo coincide | Cambio |
|---|---|---|---:|---:|---:|:---:|---|
| 31028 | Yucatan | Dzilam de Bravo | 2016 | 2021 | 4 | **no** | tipo:cuota_fija_simple→tasa_unica |
| 31034 | Yucatan | Hocaba | 2014 | 2019 | 4 | **no** | tipo:otro_no_clasificado→desconocido |
| 31079 | Yucatan | Tekax | 2020 | 2025 | 4 | **no** | tipo:tasa_unica→otro_no_clasificado |
| 31081 | Yucatan | Tekom | 2015 | 2020 | 4 | **no** | tipo:progresivo→tasa_unica | rangos:7→ | monto_max:10000.0→ |
| 31102 | Yucatan | Valladolid | 2013 | 2018 | 4 | **no** | tipo:mixto→progresivo | rangos:5→ | monto_max:135000.0→ |
| 28040 | Tamaulipas | Valle Hermoso | 2017 | 2019 | 1 | **no** | tipo:progresivo→mixto |
| 31007 | Yucatan | Cacalchen | 2018 | 2020 | 1 | **no** | tipo:progresivo→mixto |
| 31033 | Yucatan | Halacho | 2022 | 2024 | 1 | **no** | tipo:progresivo→mixto |
| 31046 | Yucatan | Mama | 2015 | 2017 | 1 | **no** | tipo:tasa_unica→tarifa_millar |
| 31062 | Yucatan | Sacalum | 2015 | 2017 | 1 | **no** | tipo:mixto→otro_no_clasificado | rangos:7→ | monto_max:49900.0→ |
| 22011 | Queretaro | El Marques | 2019 | 2021 | 1 | sí | monto_max:999999999.0→6127678.41 |
| 31002 | Yucatan | Acanceh | 2015 | 2017 | 1 | sí | monto_max:20000.0→400000.0 |
| 31014 | Yucatan | Cuncunul | 2020 | 2022 | 1 | sí | monto_max:10000.0→30000.0 |
| 31020 | Yucatan | Chicxulub Pueblo | 2015 | 2017 | 1 | sí | rangos:7→10 | monto_max:10000.0→1500000.0 |
| 31039 | Yucatan | Ixil | 2018 | 2020 | 1 | sí | monto_max:15500.0→15000.0 |
| 31041 | Yucatan | Kanasin | 2015 | 2017 | 1 | sí | rangos:4→7 | monto_max:300000.0→900000.01 |
| 31089 | Yucatan | Ticul | 2015 | 2017 | 1 | sí | monto_max:70000.0→40000.0 |
| 31091 | Yucatan | Tinum | 2015 | 2017 | 1 | sí | rangos:7→14 | monto_max:50000.0→1300000.0 |

### 3.5 Top municipios con más huecos remanentes

| cvegeo | Estado | Municipio | Huecos |
|---|---|---|---:|
| 31028 | Yucatan | Dzilam de Bravo | 4 |
| 31034 | Yucatan | Hocaba | 4 |
| 31079 | Yucatan | Tekax | 4 |
| 31081 | Yucatan | Tekom | 4 |
| 31102 | Yucatan | Valladolid | 4 |

## 4. Sugerencias human-in-the-loop

Una fila por muni con huecos. Ordenadas por número de huecos (descendente).

**Resumen por motivo principal:**
- `schema_discontinuity`: 5 munis

| cvegeo | Estado | Municipio | Huecos | Años | Motivo | Obs válidas | Acción sugerida |
|---|---|---|---:|---|---|---:|---|
| 31028 | Yucatan | Dzilam de Bravo | 4 | 2017,2018,2019,2020 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2017, 2018, 2019 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31034 | Yucatan | Hocaba | 4 | 2015,2016,2017,2018 | `schema_discontinuity` | 11 | Auditar manualmente PDFs de los años 2015, 2016, 2017 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31079 | Yucatan | Tekax | 4 | 2021,2022,2023,2024 | `schema_discontinuity` | 10 | Auditar manualmente PDFs de los años 2021, 2022, 2023 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31081 | Yucatan | Tekom | 4 | 2016,2017,2018,2019 | `schema_discontinuity` | 9 | Auditar manualmente PDFs de los años 2016, 2017, 2018 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |
| 31102 | Yucatan | Valladolid | 4 | 2014,2015,2016,2017 | `schema_discontinuity` | 12 | Auditar manualmente PDFs de los años 2014, 2015, 2016 — el esquema cambió entre observaciones cercanas (gap ≤ 4). Confirmar si la transición es real (reforma) o si hubo un error de extracción en uno de los extremos. Si es real, los huecos deben quedar como missing (no imputables). |

## 5. Comandos útiles para reextracción

```bash
# Reextracción de un muni-año específico (revisar primero el PDF crudo)
python -m scripts.run_pipeline {estado} --steps extract --slug {slug} --year {YYYY}

# Auditar discontinuidad: comparar JSON antes y después
python -m scripts.regression_v1_v2 --cvegeo {cvegeo} --years {YYYY,YYYY}

# Marcar una observación como 'excluir' en el audit CSV correspondiente
# (data/{estado}/qa/audit_{PREFIJO}.csv) para que el panel la ignore.
```
