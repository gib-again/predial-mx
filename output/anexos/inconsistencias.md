# Inconsistencias de clasificación schema_v2 — cuantificación

Corpus: **16955 JSONs** (predial-mx-v2/ + data/oaxaca/ vía reclasificar).

## Resumen

| Detector | n | pool | % del pool | pool |
|---|---:|---:|---:|---|
| `mixto_monocolumna_cuotafija` | 106 | 514 | 20.62% | mixto |
| `tabla_vacia` | 443 | 16095 | 2.75% | tipos reales |
| `legacy_cuota_fija` | 0 | 16955 | 0.00% | todo el corpus |
| `legacy_desconocido` | 0 | 16955 | 0.00% | todo el corpus |
| `rangos_no_monotonos` | 68 | 5983 | 1.14% | progresivo+mixto |
| `tarifa_millar_factor` | 2249 | 5296 | 42.47% | tarifa_millar |
| `tasa_unica_unidad_factor` | 4611 | 4733 | 97.42% | tasa_unica |
| `cuota_es_minimo` | 10 | 64 | 15.62% | cuota_fija_simple+legacy |
| `desc_transitorios` | 4 | 16095 | 0.02% | tipos con desc |

## Distribución de tipos en el corpus

| tipo_esquema | n |
|---|---:|
| `progresivo` | 5469 |
| `tarifa_millar` | 5296 |
| `tasa_unica` | 4733 |
| `otro_no_clasificado` | 860 |
| `mixto` | 514 |
| `cuota_fija_simple` | 64 |
| `cuota_fija_escalonada` | 19 |

## Muestras por detector (primeros 5)

### `mixto_monocolumna_cuotafija` — 106 casos

- **Cumpas, Sonora (2013)** — tipo=`mixto` — col='general'
  - `predial-mx-v2/sonora/SON_PREDIAL_2013_cumpas.json`
- **Arizpe, Sonora (2014)** — tipo=`mixto` — col='general'
  - `predial-mx-v2/sonora/SON_PREDIAL_2014_arizpe.json`
- **Atil, Sonora (2014)** — tipo=`mixto` — col='general'
  - `predial-mx-v2/sonora/SON_PREDIAL_2014_atil.json`
- **Bacadehuachi, Sonora (2014)** — tipo=`mixto` — col='general'
  - `predial-mx-v2/sonora/SON_PREDIAL_2014_bacadehuachi.json`
- **General Plutarco Elias Calles, Sonora (2014)** — tipo=`mixto` — col='general'
  - `predial-mx-v2/sonora/SON_PREDIAL_2014_general_plutarco_elias_calles.json`
- … y 101 más (ver `inconsistencias_detalle.csv`).

### `tabla_vacia` — 443 casos

- **Lamadrid, Coahuila (2025)** — tipo=`tarifa_millar` — tarifa_millar
  - `predial-mx-v2/coahuila/COAH_PREDIAL_2025_lamadrid.json`
- **Matamoros, Coahuila (2025)** — tipo=`tarifa_millar` — tarifa_millar
  - `predial-mx-v2/coahuila/COAH_PREDIAL_2025_matamoros.json`
- **Monclova, Coahuila (2025)** — tipo=`tarifa_millar` — tarifa_millar
  - `predial-mx-v2/coahuila/COAH_PREDIAL_2025_monclova.json`
- **Morelos, Coahuila (2025)** — tipo=`tarifa_millar` — tarifa_millar
  - `predial-mx-v2/coahuila/COAH_PREDIAL_2025_morelos.json`
- **Muzquiz, Coahuila (2025)** — tipo=`tarifa_millar` — tarifa_millar
  - `predial-mx-v2/coahuila/COAH_PREDIAL_2025_muzquiz.json`
- … y 438 más (ver `inconsistencias_detalle.csv`).

### `legacy_cuota_fija` — 0 casos

_sin hallazgos_

### `legacy_desconocido` — 0 casos

_sin hallazgos_

### `rangos_no_monotonos` — 68 casos

- **Celaya, Guanajuato (2020)** — tipo=`progresivo` — cuota_fija 2060.0→0.0 (rango 3→4)
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2020_celaya.json`
- **San Francisco del Rincon, Guanajuato (2020)** — tipo=`progresivo` — cuota_fija 7740.0→3140.0 (rango 7→8)
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2020_san_francisco_del_rincon.json`
- **Abasolo, Guanajuato (2022)** — tipo=`progresivo` — cuota_fija 2291.79→2046.38 (rango 9→10)
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2022_abasolo.json`
- **Celaya, Guanajuato (2022)** — tipo=`progresivo` — cuota_fija 1530.0→0.0 (rango 4→5)
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2022_celaya.json`
- **Moroleon, Guanajuato (2024)** — tipo=`progresivo` — cuota_fija 3212.9→0.0 (rango 5→6)
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2024_moroleon.json`
- … y 63 más (ver `inconsistencias_detalle.csv`).

### `tarifa_millar_factor` — 2249 casos

- **Acuna, Coahuila (2010)** — tipo=`tarifa_millar` — max=0.00500
  - `predial-mx-v2/coahuila/COAH_PREDIAL_2010_acuna.json`
- **Arteaga, Coahuila (2010)** — tipo=`tarifa_millar` — max=0.00300
  - `predial-mx-v2/coahuila/COAH_PREDIAL_2010_arteaga.json`
- **Cuatro Cienegas, Coahuila (2010)** — tipo=`tarifa_millar` — max=0.00200
  - `predial-mx-v2/coahuila/COAH_PREDIAL_2010_cuatro_cienegas.json`
- **Frontera, Coahuila (2010)** — tipo=`tarifa_millar` — max=0.00300
  - `predial-mx-v2/coahuila/COAH_PREDIAL_2010_frontera.json`
- **General Cepeda, Coahuila (2010)** — tipo=`tarifa_millar` — max=0.00750
  - `predial-mx-v2/coahuila/COAH_PREDIAL_2010_general_cepeda.json`
- … y 2244 más (ver `inconsistencias_detalle.csv`).

### `tasa_unica_unidad_factor` — 4611 casos

- **San Miguel de Allende, Guanajuato (2010)** — tipo=`tasa_unica` — porcentaje, tasa=0.00443
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2010_san_miguel_de_allende.json`
- **Nogales, Sonora (2012)** — tipo=`tasa_unica` — porcentaje, tasa=0.01
  - `predial-mx-v2/sonora/SON_PREDIAL_2012_nogales.json`
- **Nogales, Sonora (2013)** — tipo=`tasa_unica` — porcentaje, tasa=0.01
  - `predial-mx-v2/sonora/SON_PREDIAL_2013_nogales.json`
- **Baca, Yucatán (2010)** — tipo=`tasa_unica` — porcentaje, tasa=0.0015
  - `predial-mx-v2/yucatan/YUC_PREDIAL_2010_baca.json`
- **Dzemul, Yucatán (2010)** — tipo=`tasa_unica` — porcentaje, tasa=0.002
  - `predial-mx-v2/yucatan/YUC_PREDIAL_2010_dzemul.json`
- … y 4606 más (ver `inconsistencias_detalle.csv`).

### `cuota_es_minimo` — 10 casos

- **Santa Cruz de Juventino Rosas, Guanajuato (2021)** — tipo=`cuota_fija_simple` — desc=minim*;monto==minimo_predial (monto=313.26)
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2021_santa_cruz_de_juventino_rosas.json`
- **Villagran, Guanajuato (2021)** — tipo=`cuota_fija_simple` — desc=minim*;monto==minimo_predial (monto=262.16)
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2021_villagran.json`
- **Santa Catarina, Guanajuato (2025)** — tipo=`cuota_fija_simple` — desc=minim*;monto==minimo_predial (monto=294.51)
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2025_santa_catarina.json`
- **Uriangato, Guanajuato (2025)** — tipo=`cuota_fija_simple` — desc=minim*;monto==minimo_predial (monto=395.61)
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2025_uriangato.json`
- **Acambaro, Guanajuato (2026)** — tipo=`cuota_fija_simple` — desc=minim* (monto=360.6)
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2026_acambaro.json`
- … y 5 más (ver `inconsistencias_detalle.csv`).

### `desc_transitorios` — 4 casos

- **Salamanca, Guanajuato (2019)** — tipo=`tarifa_millar` — hit='vigencia' en desc='Inmuebles urbanos y suburbanos con edificaciones, al inicio de la vigencia de la'
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2019_salamanca.json`
- **Villagran, Guanajuato (2019)** — tipo=`tarifa_millar` — hit='vigencia' en desc='Inmuebles que cuenten con un valor determinado o modificado; vigencia desde la e'
  - `predial-mx-v2/guanajuato/GTO_PREDIAL_2019_villagran.json`
- **Telchac Pueblo, Yucatán (2011)** — tipo=`tasa_unica` — hit='salario mínim' en desc='Impuesto predial determinado multiplicando el valor catastral por 0.015 por cien'
  - `predial-mx-v2/yucatan/YUC_PREDIAL_2011_telchac_pueblo.json`
- **Telchac Pueblo, Yucatán (2012)** — tipo=`tasa_unica` — hit='salario mínim' en desc='Impuesto predial determinado multiplicando el valor catastral por 0.015 por cien'
  - `predial-mx-v2/yucatan/YUC_PREDIAL_2012_telchac_pueblo.json`
