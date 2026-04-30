# Reporte taxonómico — extracciones predial v2

Fuente: `predial-mx-v2/`  ·  Estados: coahuila, guanajuato, tamaulipas, yucatan  ·  Total JSONs: **3371**

De los 3371 JSONs: **3254** vienen del LLM y **117** son sintéticos (`modelo='synthesized_short_form'`, markers deterministas del fallback `_extract_short_form_predial` del segmentador de Yucatán para leyes en formato corto).

## 1. Distribución por `tipo_corregido`

### Global

| Tipo | Casos | % |
|---|---:|---:|
| `tarifa_millar` | 1714 | 50.8% |
| `progresivo` | 840 | 24.9% |
| `mixto` | 385 | 11.4% |
| `tasa_unica` | 222 | 6.6% |
| `otro_no_clasificado` | 144 | 4.3% |
| `cuota_fija_simple` | 43 | 1.3% |
| `cuota_fija_escalonada` | 20 | 0.6% |
| `FALTA_PREDIAL` | 3 | 0.1% |
| **Total** | **3371** | 100.0% |

### Por estado

| Estado | `tarifa_millar` | `progresivo` | `mixto` | `tasa_unica` | `otro_no_clasificado` | `cuota_fija_simple` | `cuota_fija_escalonada` | `FALTA_PREDIAL` | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| coahuila | 541 | 18 | 17 | 0 | 3 | 0 | 0 | 0 | **579** |
| guanajuato | 519 | 62 | 30 | 1 | 9 | 6 | 0 | 1 | **628** |
| tamaulipas | 603 | 61 | 18 | 0 | 0 | 3 | 0 | 0 | **685** |
| yucatan | 51 | 699 | 320 | 221 | 132 | 34 | 20 | 2 | **1479** |

## 2. Casos `otro_no_clasificado` agrupados por similitud

Total casos: **144**  ·  Grupos distintos: **10**  ·  Criterio: `(categoria, tag_semántico)` — el tag se asigna por keywords-regex sobre `descripcion_estructural`. Una descripción que matchea el primer patrón gana ese tag (early-match-wins).

### Grupo #1 — 120 caso(s)  ·  `otro_patron`

- **categoria**: `municipio_sin_impuesto`
- **tag**: `otro_patron`
- **estados**: guanajuato(1), yucatan(119)
- **rango años**: 2010–2103 (17 años distintos)
- **muni-años afectados**: 120

**descripcion_estructural (ejemplar)**:

> El segmento no contiene una mecánica de cálculo del impuesto predial. Sólo incluye el pronóstico de ingreso ('Impuesto predial $8,884,740.00') dentro del artículo de clasificaciones de ingresos, y la nota del segmentador indica expresamente que la ley de ingresos corta no trae tarifas, tasas, montos al millar ni rangos, remitiendo a la Ley General de Hacienda Municipal del Estado de Yucatán.

<details><summary>Lista completa (120 casos)</summary>

- `guanajuato` · tierra_blanca (2025) — cvegeo 11040
- `yucatan` · acanceh (2010) — cvegeo 31002
- `yucatan` · acanceh (2011) — cvegeo 31002
- `yucatan` · acanceh (2012) — cvegeo 31002
- `yucatan` · chochola (2010) — cvegeo 31023
- `yucatan` · chochola (2012) — cvegeo 31023
- `yucatan` · chochola (2019) — cvegeo 31023
- `yucatan` · chochola (2020) — cvegeo 31023
- `yucatan` · chochola (2021) — cvegeo 31023
- `yucatan` · conkal (2023) — cvegeo 31013
- `yucatan` · conkal (2024) — cvegeo 31013
- `yucatan` · dzidzantun (2014) — cvegeo 31027
- `yucatan` · dzidzantun (2019) — cvegeo 31027
- `yucatan` · dzidzantun (2020) — cvegeo 31027
- `yucatan` · dzidzantun (2022) — cvegeo 31027
- `yucatan` · dzidzantun (2023) — cvegeo 31027
- `yucatan` · dzidzantun (2024) — cvegeo 31027
- `yucatan` · dzidzantun (2025) — cvegeo 31027
- `yucatan` · hocaba (2010) — cvegeo 31034
- `yucatan` · hocaba (2011) — cvegeo 31034
- `yucatan` · hocaba (2012) — cvegeo 31034
- `yucatan` · hocaba (2014) — cvegeo 31034
- `yucatan` · hoctun (2025) — cvegeo 31035
- `yucatan` · kanasin (2022) — cvegeo 31041
- `yucatan` · kanasin (2023) — cvegeo 31041
- `yucatan` · kanasin (2024) — cvegeo 31041
- `yucatan` · kanasin (2025) — cvegeo 31041
- `yucatan` · motul (2010) — cvegeo 31052
- `yucatan` · motul (2011) — cvegeo 31052
- `yucatan` · motul (2012) — cvegeo 31052
- `yucatan` · motul (2013) — cvegeo 31052
- `yucatan` · motul (2014) — cvegeo 31052
- `yucatan` · motul (2016) — cvegeo 31052
- `yucatan` · motul (2017) — cvegeo 31052
- `yucatan` · motul (2018) — cvegeo 31052
- `yucatan` · motul (2019) — cvegeo 31052
- `yucatan` · motul (2020) — cvegeo 31052
- `yucatan` · motul (2022) — cvegeo 31052
- `yucatan` · motul (2023) — cvegeo 31052
- `yucatan` · motul (2024) — cvegeo 31052
- `yucatan` · muna (2010) — cvegeo 31053
- `yucatan` · muna (2011) — cvegeo 31053
- `yucatan` · muna (2012) — cvegeo 31053
- `yucatan` · muna (2013) — cvegeo 31053
- `yucatan` · muna (2014) — cvegeo 31053
- `yucatan` · muna (2015) — cvegeo 31053
- `yucatan` · muna (2017) — cvegeo 31053
- `yucatan` · muna (2018) — cvegeo 31053
- `yucatan` · muna (2019) — cvegeo 31053
- `yucatan` · sacalum (2010) — cvegeo 31062
- `yucatan` · sacalum (2011) — cvegeo 31062
- `yucatan` · sacalum (2012) — cvegeo 31062
- `yucatan` · sacalum (2013) — cvegeo 31062
- `yucatan` · sacalum (2014) — cvegeo 31062
- `yucatan` · sacalum (2017) — cvegeo 31062
- `yucatan` · sacalum (2018) — cvegeo 31062
- `yucatan` · sacalum (2019) — cvegeo 31062
- `yucatan` · sacalum (2020) — cvegeo 31062
- `yucatan` · sacalum (2021) — cvegeo 31062
- `yucatan` · sacalum (2022) — cvegeo 31062
- `yucatan` · sacalum (2023) — cvegeo 31062
- `yucatan` · sacalum (2024) — cvegeo 31062
- `yucatan` · sacalum (2025) — cvegeo 31062
- `yucatan` · sotuta (2010) — cvegeo 31069
- `yucatan` · sotuta (2013) — cvegeo 31069
- `yucatan` · sotuta (2014) — cvegeo 31069
- `yucatan` · sotuta (2015) — cvegeo 31069
- `yucatan` · tahdziu (2010) — cvegeo 31073
- `yucatan` · tahdziu (2011) — cvegeo 31073
- `yucatan` · tahdziu (2012) — cvegeo 31073
- `yucatan` · tahdziu (2013) — cvegeo 31073
- `yucatan` · tahdziu (2014) — cvegeo 31073
- `yucatan` · tahdziu (2016) — cvegeo 31073
- `yucatan` · tekal_de_venegas (2010) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2011) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2012) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2013) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2014) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2015) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2016) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2017) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2018) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2019) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2020) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2021) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2022) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2023) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2024) — cvegeo 31077
- `yucatan` · tekal_de_venegas (2025) — cvegeo 31077
- `yucatan` · tekax (2019) — cvegeo 31079
- `yucatan` · temax (2010) — cvegeo 31084
- `yucatan` · temax (2012) — cvegeo 31084
- `yucatan` · temax (2014) — cvegeo 31084
- `yucatan` · temax (2015) — cvegeo 31084
- `yucatan` · temax (2016) — cvegeo 31084
- `yucatan` · temax (2017) — cvegeo 31084
- `yucatan` · temax (2018) — cvegeo 31084
- `yucatan` · temax (2019) — cvegeo 31084
- `yucatan` · temax (2020) — cvegeo 31084
- `yucatan` · temax (2021) — cvegeo 31084
- `yucatan` · temax (2022) — cvegeo 31084
- `yucatan` · temax (2023) — cvegeo 31084
- `yucatan` · temax (2103) — cvegeo 31084
- `yucatan` · tixpehual (2022) — cvegeo 31095
- `yucatan` · tixpehual (2023) — cvegeo 31095
- `yucatan` · tixpehual (2024) — cvegeo 31095
- `yucatan` · tixpehual (2025) — cvegeo 31095
- `yucatan` · tzucacab (2019) — cvegeo 31098
- `yucatan` · tzucacab (2020) — cvegeo 31098
- `yucatan` · tzucacab (2021) — cvegeo 31098
- `yucatan` · uayma (2010) — cvegeo 31099
- `yucatan` · uayma (2011) — cvegeo 31099
- `yucatan` · uayma (2014) — cvegeo 31099
- `yucatan` · uayma (2021) — cvegeo 31099
- `yucatan` · uayma (2022) — cvegeo 31099
- `yucatan` · uayma (2023) — cvegeo 31099
- `yucatan` · uayma (2024) — cvegeo 31099
- `yucatan` · valladolid (2010) — cvegeo 31102
- `yucatan` · valladolid (2011) — cvegeo 31102
- `yucatan` · valladolid (2012) — cvegeo 31102

</details>

### Grupo #2 — 9 caso(s)  ·  `solo_encabezado`

- **categoria**: `segmento_vacio`
- **tag**: `solo_encabezado`
- **estados**: coahuila(3), guanajuato(6)
- **rango años**: 2010–2025 (6 años distintos)
- **muni-años afectados**: 9

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no incluye el contenido tarifario del impuesto predial; sólo aparecen encabezados, sumarios de ingresos y páginas en blanco o sin transcripción legible de la sección correspondiente. No es posible extraer una mecánica de cálculo sin inventar la tabla o el artículo aplicable.

<details><summary>Lista completa (9 casos)</summary>

- `coahuila` · ocampo (2010) — cvegeo 05023
- `coahuila` · piedras_negras (2010) — cvegeo 05025
- `coahuila` · ramos_arizpe (2010) — cvegeo 05027
- `guanajuato` · cortazar (2023) — cvegeo 11011
- `guanajuato` · irapuato (2025) — cvegeo 11017
- `guanajuato` · san_diego_de_la_union (2024) — cvegeo 11029
- `guanajuato` · san_francisco_del_rincon (2021) — cvegeo 11031
- `guanajuato` · valle_de_santiago (2025) — cvegeo 11042
- `guanajuato` · yuriria (2018) — cvegeo 11046

</details>

### Grupo #3 — 3 caso(s)  ·  `solo_valores_unitarios`

- **categoria**: `error_segmentacion`
- **tag**: `solo_valores_unitarios`
- **estados**: yucatan(3)
- **rango años**: 2023–2025 (2 años distintos)
- **muni-años afectados**: 3

**descripcion_estructural (ejemplar)**:

> El texto sí menciona que el impuesto se determinará con una tabla y que se calcula con diferencia contra límite inferior, factor aplicable y cuota fija, lo que sugiere una tarifa progresiva o escalonada; sin embargo, la tabla tarifaria del impuesto predial no aparece en el segmento. El contenido visible corresponde a valores unitarios catastrales de terreno y construcción, que no son la tarifa del impuesto, por lo que no es posible reconstruir válidamente los rangos, cuotas fijas o factores aplicables.

<details><summary>Lista completa (3 casos)</summary>

- `yucatan` · akil (2023) — cvegeo 31003 — escalado
- `yucatan` · tunkas (2023) — cvegeo 31097 — escalado
- `yucatan` · tunkas (2025) — cvegeo 31097 — escalado

</details>

### Grupo #4 — 3 caso(s)  ·  `dos_tarifas_paralelas`

- **categoria**: `estructura_no_estandar`
- **tag**: `dos_tarifas_paralelas`
- **estados**: yucatan(3)
- **rango años**: 2012–2025 (3 años distintos)
- **muni-años afectados**: 3

**descripcion_estructural (ejemplar)**:

> El texto no presenta una mecánica única de predial sobre valor catastral clasificable en una sola tabla. Primero aparece una tabla de valores unitarios de terreno y de construcción para el cálculo del valor catastral, pero no una tarifa de impuesto predial. Después, el Artículo 14 establece dos mecánicas paralelas: predios agropecuarios al 10 al millar anual sobre valor catastral, y predios con base en rentas o frutos civiles al 5% mensual para habitación y comercial. La estructura tarifaria principal del impuesto predial no queda extraíble en una sola de las variantes cerradas sin mezclar mecánicas heterogéneas.

<details><summary>Lista completa (3 casos)</summary>

- `yucatan` · akil (2025) — cvegeo 31003
- `yucatan` · dzidzantun (2012) — cvegeo 31027
- `yucatan` · yaxkukul (2022) — cvegeo 31105

</details>

### Grupo #5 — 3 caso(s)  ·  `solo_valores_unitarios`

- **categoria**: `estructura_no_estandar`
- **tag**: `solo_valores_unitarios`
- **estados**: yucatan(3)
- **rango años**: 2010–2024 (2 años distintos)
- **muni-años afectados**: 3

**descripcion_estructural (ejemplar)**:

> El texto no presenta una mecánica tarifaria del impuesto predial directamente sobre la base imponible. El artículo 13 establece valores unitarios de terreno y construcción para integrar el valor catastral, y el artículo 14 añade una tarifa para predios agropecuarios (10 al millar) y otra sobre rentas o frutos civiles (5% mensual) para predios habitación y comerciales. No hay una tabla única del predial sobre valor catastral que encaje de forma limpia en una de las seis estructuras estándar sin mezclar mecánicas distintas.

<details><summary>Lista completa (3 casos)</summary>

- `yucatan` · dzidzantun (2010) — cvegeo 31027 — escalado
- `yucatan` · tekanto (2010) — cvegeo 31078
- `yucatan` · yaxkukul (2024) — cvegeo 31105

</details>

### Grupo #6 — 2 caso(s)  ·  `mecanica_ausente`

- **categoria**: `municipio_sin_impuesto`
- **tag**: `mecanica_ausente`
- **estados**: yucatan(2)
- **rango años**: 2025
- **muni-años afectados**: 2

**descripcion_estructural (ejemplar)**:

> El segmento sólo contiene el pronóstico presupuestal de ingresos por concepto, incluyendo una cifra global de 'Impuesto predial', pero no establece tarifa, tasa, cuota fija, monto al millar ni rangos de valor catastral. La nota del segmentador indica además que la mecánica del impuesto se rige por la Ley General de Hacienda Municipal del Estado de Yucatán, por lo que esta ley municipal no contiene la mecánica de cálculo del predial.

<details><summary>Lista completa (2 casos)</summary>

- `yucatan` · conkal (2025) — cvegeo 31013
- `yucatan` · kaua (2025) — cvegeo 31043 — escalado

</details>

### Grupo #7 — 1 caso(s)  ·  `solo_valores_catastro`

- **categoria**: `estructura_no_estandar`
- **tag**: `solo_valores_catastro`
- **estados**: yucatan(1)
- **rango años**: 2024
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto transcrito no contiene una tarifa del impuesto predial en forma de cuotas, rangos o tasas por valor catastral; contiene principalmente una tabla de valores catastrales/unitarios de terreno y construcción para determinar la base gravable. Solo aparece de forma separada una tarifa identificable para predios destinados a la producción agropecuaria de 10 al millar anual sobre el valor registrado o catastral, pero no se observa en el segmento la mecánica principal completa del impuesto predial para los demás predios.

<details><summary>Lista completa (1 casos)</summary>

- `yucatan` · kinchil (2024) — cvegeo 31044 — escalado

</details>

### Grupo #8 — 1 caso(s)  ·  `seccion_ausente`

- **categoria**: `municipio_sin_impuesto`
- **tag**: `seccion_ausente`
- **estados**: yucatan(1)
- **rango años**: 2022
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El segmento no contiene mecánica de cálculo del impuesto predial. Solo aparece el artículo de pronóstico presupuestal con el monto global de 'Impuesto predial' dentro del rubro de impuestos sobre el patrimonio, sin tarifas, tasas, rangos, bases de cálculo ni remisión expresa a una tabla aplicable dentro del texto proporcionado. La nota del segmentador indica además que la ley corta no incluye la sección tarifaria y que las contribuciones se rigen por la Ley General de Hacienda Municipal del Estado de Yucatán.

<details><summary>Lista completa (1 casos)</summary>

- `yucatan` · conkal (2022) — cvegeo 31013

</details>

### Grupo #9 — 1 caso(s)  ·  `ocr_ilegible`

- **categoria**: `segmento_vacio`
- **tag**: `ocr_ilegible`
- **estados**: guanajuato(1)
- **rango años**: 2025
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no contiene la sección tarifaria legible del Impuesto Predial para Acámbaro 2025. Las páginas incluidas muestran principalmente encabezados, listados de ingresos y ruido/OCR, pero no una tabla o mecánica de cálculo extraíble del predial.

<details><summary>Lista completa (1 casos)</summary>

- `guanajuato` · acambaro (2025) — cvegeo 11002

</details>

### Grupo #10 — 1 caso(s)  ·  `seccion_ausente`

- **categoria**: `segmento_vacio`
- **tag**: `seccion_ausente`
- **estados**: guanajuato(1)
- **rango años**: 2021
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no contiene la sección tarifaria del Impuesto Predial del municipio; sólo incluye avisos del Periódico Oficial y un artículo de ajuste de cantidades. No hay tabla, tasa, cuota ni mecánica de cálculo del predial extraíble en este segmento.

<details><summary>Lista completa (1 casos)</summary>

- `guanajuato` · purisima_del_rincon (2021) — cvegeo 11025 — escalado

</details>

## 3. Casos `requiere_revision` excluyendo `otro_no_clasificado`

Total: **3**

| Estado | Año | Slug | tipo_corregido | Escalado | Razón |
|---|---:|---|---|:-:|---|
| guanajuato | 2011 | victoria | `FALTA_PREDIAL` |  | texto_fuente_no_encontrado |
| yucatan | 2022 | chemax | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| e1=  • predial.progresivo: Value error, brackets 5→6: hueco detectado (superior=15000.0, siguiente inferior=15500.01) \ |
| yucatan | 2010 | kinchil | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| e1=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente inferior=70000.01) \| e2= |

## 4. Métricas resumen

- Total JSONs: **3371**
- Schema-validados (load + Pydantic v2): **3368** (99.9%)
- `otro_no_clasificado`: **144** (4.3%) en 10 grupos
- `requiere_revision` total: **30** (0.9%)
- Escalados a fallback (`gpt-5.4`): **172** (5.1%)
