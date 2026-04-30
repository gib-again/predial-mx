# Reporte taxonómico — extracciones predial v2

Fuente: `predial-mx-v2/`  ·  Estados: coahuila, guanajuato, tamaulipas, yucatan  ·  Total JSONs: **3371**

De los 3371 JSONs: **3254** vienen del LLM y **117** son sintéticos (`modelo='synthesized_short_form'`, markers deterministas del fallback `_extract_short_form_predial` del segmentador de Yucatán para leyes en formato corto).

## 1. Distribución por `tipo_corregido`

### Global

| Tipo | Casos | % |
|---|---:|---:|
| `tarifa_millar` | 1683 | 49.9% |
| `progresivo` | 830 | 24.6% |
| `mixto` | 378 | 11.2% |
| `tasa_unica` | 217 | 6.4% |
| `otro_no_clasificado` | 193 | 5.7% |
| `cuota_fija_simple` | 45 | 1.3% |
| `cuota_fija_escalonada` | 20 | 0.6% |
| `FALTA_PREDIAL` | 5 | 0.1% |
| **Total** | **3371** | 100.0% |

### Por estado

| Estado | `tarifa_millar` | `progresivo` | `mixto` | `tasa_unica` | `otro_no_clasificado` | `cuota_fija_simple` | `cuota_fija_escalonada` | `FALTA_PREDIAL` | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| coahuila | 537 | 18 | 17 | 0 | 7 | 0 | 0 | 0 | **579** |
| guanajuato | 496 | 49 | 29 | 1 | 46 | 6 | 0 | 1 | **628** |
| tamaulipas | 600 | 61 | 18 | 0 | 3 | 3 | 0 | 0 | **685** |
| yucatan | 50 | 702 | 314 | 216 | 137 | 36 | 20 | 4 | **1479** |

## 2. Casos `otro_no_clasificado` agrupados por similitud

Total casos: **193**  ·  Grupos distintos: **17**  ·  Criterio: `(categoria, tag_semántico)` — el tag se asigna por keywords-regex sobre `descripcion_estructural`. Una descripción que matchea el primer patrón gana ese tag (early-match-wins).

### Grupo #1 — 125 caso(s)  ·  `otro_patron`

- **categoria**: `municipio_sin_impuesto`
- **tag**: `otro_patron`
- **estados**: guanajuato(3), yucatan(122)
- **rango años**: 2010–2103 (17 años distintos)
- **muni-años afectados**: 125

**descripcion_estructural (ejemplar)**:

> El segmento no contiene una mecánica de cálculo del impuesto predial. Solo aparece el pronóstico de ingresos del Artículo 5 con el renglón 'Impuesto predial' como monto presupuestal, y la propia nota del segmentador indica que la ley no incluye tarifas, tasas, montos al millar ni rangos para predial. Se remite a la Ley General de Hacienda Municipal del Estado de Yucatán, por lo que no es posible extraer una tabla tarifaria municipal desde este texto.

<details><summary>Lista completa (125 casos)</summary>

- `guanajuato` · acambaro (2025) — cvegeo 11002
- `guanajuato` · tierra_blanca (2025) — cvegeo 11040
- `guanajuato` · valle_de_santiago (2025) — cvegeo 11042
- `yucatan` · acanceh (2010) — cvegeo 31002
- `yucatan` · acanceh (2011) — cvegeo 31002
- `yucatan` · acanceh (2012) — cvegeo 31002
- `yucatan` · chochola (2010) — cvegeo 31023
- `yucatan` · chochola (2012) — cvegeo 31023
- `yucatan` · chochola (2019) — cvegeo 31023
- `yucatan` · chochola (2020) — cvegeo 31023
- `yucatan` · chochola (2021) — cvegeo 31023
- `yucatan` · conkal (2022) — cvegeo 31013
- `yucatan` · conkal (2023) — cvegeo 31013
- `yucatan` · conkal (2024) — cvegeo 31013
- `yucatan` · conkal (2025) — cvegeo 31013
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
- `yucatan` · kaua (2025) — cvegeo 31043
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

### Grupo #2 — 30 caso(s)  ·  `solo_encabezado`

- **categoria**: `segmento_vacio`
- **tag**: `solo_encabezado`
- **estados**: coahuila(3), guanajuato(25), yucatan(2)
- **rango años**: 2010–2026 (9 años distintos)
- **muni-años afectados**: 30

**descripcion_estructural (ejemplar)**:

> El texto proporcionado para la sección de impuesto predial no contiene la mecánica tarifaria ni tablas de cálculo; únicamente aparece el encabezado presupuestal con el monto estimado del impuesto predial y páginas en blanco/sin contenido legible de la sección. No es posible extraer una tarifa, cuota o esquema de cálculo sin inventarlo.

<details><summary>Lista completa (30 casos)</summary>

- `coahuila` · ocampo (2010) — cvegeo 05023
- `coahuila` · piedras_negras (2010) — cvegeo 05025
- `coahuila` · ramos_arizpe (2010) — cvegeo 05027
- `guanajuato` · abasolo (2025) — cvegeo 11001
- `guanajuato` · acambaro (2024) — cvegeo 11002
- `guanajuato` · apaseo_el_grande (2025) — cvegeo 11005
- `guanajuato` · comonfort (2025) — cvegeo 11009
- `guanajuato` · cortazar (2025) — cvegeo 11011
- `guanajuato` · cortazar (2026) — cvegeo 11011
- `guanajuato` · cueramaro (2025) — cvegeo 11012
- `guanajuato` · dolores_hidalgo_cuna_de_la_independencia_nacional (2025) — cvegeo 11014
- `guanajuato` · irapuato (2026) — cvegeo 11017
- `guanajuato` · jaral_del_progreso (2024) — cvegeo 11018
- `guanajuato` · jerecuaro (2023) — cvegeo 11019
- `guanajuato` · purisima_del_rincon (2026) — cvegeo 11025
- `guanajuato` · salamanca (2024) — cvegeo 11027
- `guanajuato` · salvatierra (2024) — cvegeo 11028
- `guanajuato` · salvatierra (2026) — cvegeo 11028
- `guanajuato` · san_diego_de_la_union (2024) — cvegeo 11029
- `guanajuato` · san_diego_de_la_union (2025) — cvegeo 11029
- `guanajuato` · san_felipe (2025) — cvegeo 11030
- `guanajuato` · san_francisco_del_rincon (2021) — cvegeo 11031
- `guanajuato` · san_luis_de_la_paz (2026) — cvegeo 11033
- `guanajuato` · santa_catarina (2026) — cvegeo 11034
- `guanajuato` · santiago_maravatio (2025) — cvegeo 11036
- `guanajuato` · uriangato (2020) — cvegeo 11041
- `guanajuato` · victoria (2021) — cvegeo 11043
- `guanajuato` · yuriria (2018) — cvegeo 11046
- `yucatan` · progreso (2010) — cvegeo 31059
- `yucatan` · progreso (2011) — cvegeo 31059

</details>

### Grupo #3 — 8 caso(s)  ·  `solo_valores_unitarios`

- **categoria**: `estructura_no_estandar`
- **tag**: `solo_valores_unitarios`
- **estados**: guanajuato(3), yucatan(5)
- **rango años**: 2010–2026 (5 años distintos)
- **muni-años afectados**: 8

**descripcion_estructural (ejemplar)**:

> El texto no presenta una tarifa del impuesto predial clasificable en una de las variantes permitidas. En el Artículo 12 sólo se indica una cuota fija de $10.00 más el resultado de un factor sobre el valor catastral, junto con un procedimiento de valuación del inmueble y tablas de valores unitarios de terreno y construcción; esas tablas son de catastro/valuación, no una tabla tarifaria de predial. No hay brackets, tasa uniforme explícita, ni catálogo de tasas por categoría que permita estructurar la mecánica como tarifa_millar, progresivo, cuota fija escalonada o mixto.

<details><summary>Lista completa (8 casos)</summary>

- `guanajuato` · celaya (2018) — cvegeo 11007
- `guanajuato` · uriangato (2018) — cvegeo 11041
- `guanajuato` · uriangato (2026) — cvegeo 11041
- `yucatan` · dzidzantun (2010) — cvegeo 31027 — escalado
- `yucatan` · tekanto (2010) — cvegeo 31078
- `yucatan` · tepakan (2025) — cvegeo 31086
- `yucatan` · xocchel (2025) — cvegeo 31103
- `yucatan` · yaxkukul (2023) — cvegeo 31105

</details>

### Grupo #4 — 6 caso(s)  ·  `articulado_ausente`

- **categoria**: `segmento_vacio`
- **tag**: `articulado_ausente`
- **estados**: guanajuato(6)
- **rango años**: 2023–2026 (4 años distintos)
- **muni-años afectados**: 6

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no contiene el articulado ni tablas del Impuesto Predial; sólo aparecen páginas de portada/índice y saltos de página dentro del rango 129-146, sin mecánica tarifaria extraíble. No es posible identificar cuotas, tasas o brackets del predial a partir del fragmento.

<details><summary>Lista completa (6 casos)</summary>

- `guanajuato` · apaseo_el_alto (2025) — cvegeo 11004
- `guanajuato` · comonfort (2023) — cvegeo 11009
- `guanajuato` · dolores_hidalgo_cuna_de_la_independencia_nacional (2026) — cvegeo 11014
- `guanajuato` · guanajuato (2026) — cvegeo 11015
- `guanajuato` · purisima_del_rincon (2024) — cvegeo 11025
- `guanajuato` · santa_cruz_de_juventino_rosas (2026) — cvegeo 11035

</details>

### Grupo #5 — 4 caso(s)  ·  `dos_tarifas_paralelas`

- **categoria**: `estructura_no_estandar`
- **tag**: `dos_tarifas_paralelas`
- **estados**: yucatan(4)
- **rango años**: 2012–2025 (4 años distintos)
- **muni-años afectados**: 4

**descripcion_estructural (ejemplar)**:

> El artículo 4 describe una mecánica progresiva por rangos de valor catastral con cuota fija y factor sobre el excedente, pero en el texto proporcionado no aparecen los límites inferior/superior ni la tabla de rangos y tasas; además se incluyen tablas de valores unitarios de terreno y construcción que son catastro, no la tarifa del impuesto. El artículo 6 sí establece una tasa paralela para predios agropecuarios (12 al millar anual), pero no viene estructurada como tabla completa de predial. Por ello no es posible clasificar con precisión en las variantes tarifarias solicitadas sin inventar los brackets faltantes.

<details><summary>Lista completa (4 casos)</summary>

- `yucatan` · akil (2025) — cvegeo 31003
- `yucatan` · dzidzantun (2012) — cvegeo 31027
- `yucatan` · kinchil (2024) — cvegeo 31044 — escalado
- `yucatan` · yaxkukul (2022) — cvegeo 31105 — escalado

</details>

### Grupo #6 — 3 caso(s)  ·  `solo_valores_unitarios`

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

### Grupo #7 — 3 caso(s)  ·  `mecanica_ausente`

- **categoria**: `segmento_vacio`
- **tag**: `mecanica_ausente`
- **estados**: coahuila(1), guanajuato(1), tamaulipas(1)
- **rango años**: 2010–2021 (3 años distintos)
- **muni-años afectados**: 3

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no contiene la mecánica de cálculo del impuesto predial. Solo aparecen rubros presupuestales de recaudación/ingresos ('Impuesto sobre la propiedad urbana, suburbana y rústica', 'Impuesto sobre la propiedad urbana', 'Impuesto sobre la propiedad rústica') con montos agregados, pero no tablas, cuotas, tasas ni rangos aplicables al cálculo.

<details><summary>Lista completa (3 casos)</summary>

- `coahuila` · nava (2010) — cvegeo 05022
- `guanajuato` · purisima_del_rincon (2021) — cvegeo 11025
- `tamaulipas` · nuevo_laredo (2013) — cvegeo 28027

</details>

### Grupo #8 — 2 caso(s)  ·  `otro_patron`

- **categoria**: `estructura_no_estandar`
- **tag**: `otro_patron`
- **estados**: tamaulipas(2)
- **rango años**: 2023–2024 (2 años distintos)
- **muni-años afectados**: 2

**descripcion_estructural (ejemplar)**:

> El texto no presenta una tabla tarifaria extraíble de impuesto predial con rangos o categorías de tasa. Sólo indica que la base es el valor catastral y remite a una tasa señalada en el artículo, pero en el fragmento proporcionado no aparece dicha tasa. Sí aparecen reglas de incremento para predios urbanos no edificados y con edificación inferior a la quinta parte del terreno, además de mínimos en UMA, pero no la mecánica completa de cálculo.

<details><summary>Lista completa (2 casos)</summary>

- `tamaulipas` · nuevo_laredo (2024) — cvegeo 28027
- `tamaulipas` · san_fernando (2023) — cvegeo 28035

</details>

### Grupo #9 — 2 caso(s)  ·  `solo_valores_unitarios`

- **categoria**: `municipio_sin_impuesto`
- **tag**: `solo_valores_unitarios`
- **estados**: guanajuato(2)
- **rango años**: 2018–2021 (2 años distintos)
- **muni-años afectados**: 2

**descripcion_estructural (ejemplar)**:

> El texto proporcionado incluye valores unitarios de terreno y construcción para avalúo catastral, pero no aparece la mecánica tarifaria del impuesto predial (tabla de cuotas, tasas al millar, progresividad o cuota fija) dentro del segmento entregado. Por ello no es posible extraer la liquidación del predial sin inventar reglas no visibles.

<details><summary>Lista completa (2 casos)</summary>

- `guanajuato` · tierra_blanca (2018) — cvegeo 11040
- `guanajuato` · valle_de_santiago (2021) — cvegeo 11042

</details>

### Grupo #10 — 2 caso(s)  ·  `otro_patron`

- **categoria**: `segmento_vacio`
- **tag**: `otro_patron`
- **estados**: guanajuato(2)
- **rango años**: 2023–2026 (2 años distintos)
- **muni-años afectados**: 2

**descripcion_estructural (ejemplar)**:

> El insumo proporcionado no contiene el texto tarifario de la sección de impuesto predial; sólo aparecen páginas iniciales y numeración, sin tablas, rangos, tasas ni cuotas aplicables. No es posible extraer la mecánica de cálculo a partir de este segmento.

<details><summary>Lista completa (2 casos)</summary>

- `guanajuato` · cortazar (2023) — cvegeo 11011
- `guanajuato` · moroleon (2026) — cvegeo 11021

</details>

### Grupo #11 — 2 caso(s)  ·  `seccion_ausente`

- **categoria**: `segmento_vacio`
- **tag**: `seccion_ausente`
- **estados**: guanajuato(2)
- **rango años**: 2024–2025 (2 años distintos)
- **muni-años afectados**: 2

**descripcion_estructural (ejemplar)**:

> En el texto proporcionado no aparece la sección tarifaria del impuesto predial ni artículos con mecánica de cálculo; sólo se observa el clasificador de ingresos con el monto estimado de la recaudación por impuesto predial. No hay tabla, rangos, tasas ni cuota fija extraíbles para transcribir la mecánica.

<details><summary>Lista completa (2 casos)</summary>

- `guanajuato` · celaya (2024) — cvegeo 11007
- `guanajuato` · salamanca (2025) — cvegeo 11027

</details>

### Grupo #12 — 1 caso(s)  ·  `mecanica_ausente`

- **categoria**: `estructura_no_estandar`
- **tag**: `mecanica_ausente`
- **estados**: coahuila(1)
- **rango años**: 2010
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no contiene la mecánica tarifaria del impuesto predial. Sólo aparecen incentivos/bonificaciones para ciertos contribuyentes (pensionados, instituciones, empresas) y luego inicia el capítulo de otro impuesto (adquisición de inmuebles). No hay tabla, tasa, cuota o rangos aplicables al predial extraíbles en este fragmento.

<details><summary>Lista completa (1 casos)</summary>

- `coahuila` · progreso (2010) — cvegeo 05026

</details>

### Grupo #13 — 1 caso(s)  ·  `ocr_ilegible`

- **categoria**: `estructura_no_estandar`
- **tag**: `ocr_ilegible`
- **estados**: guanajuato(1)
- **rango años**: 2025
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto sí contiene tasas del impuesto predial, pero la mecánica principal no es una sola tabla homogénea: para inmuebles urbanos y suburbanos hay una tabla por antigüedad/estado de edificación con tres columnas ('con edificaciones', 'sin edificaciones' y una columna de tasa con texto deteriorado/OCR), y para inmuebles rústicos aparece además una base de valores por hectárea y por m² con factores agrológicos. El fragmento OCR está seriamente corrompido en los renglones de tasas, por lo que no es posible transcribir con seguridad una estructura tarifaria consistente sin inventar datos.

<details><summary>Lista completa (1 casos)</summary>

- `guanajuato` · yuriria (2025) — cvegeo 11046

</details>

### Grupo #14 — 1 caso(s)  ·  `dos_tarifas_paralelas`

- **categoria**: `municipio_sin_impuesto`
- **tag**: `dos_tarifas_paralelas`
- **estados**: yucatan(1)
- **rango años**: 2021
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto del capítulo de predial no contiene una tarifa del impuesto predial extraíble; únicamente remite a la Ley de Hacienda del Municipio de Kinchil, Yucatán, para el pago del impuesto, y luego inserta tablas de valores catastrales/unitarios de suelo y construcción. La única tasa expresa observada es una tarifa paralela para predios destinados a la producción agropecuaria de 10 al millar anual sobre el valor registrado o catastral, pero no se proporciona la mecánica principal del impuesto predial para los demás predios.

<details><summary>Lista completa (1 casos)</summary>

- `yucatan` · kinchil (2021) — cvegeo 31044 — escalado

</details>

### Grupo #15 — 1 caso(s)  ·  `mecanica_ausente`

- **categoria**: `municipio_sin_impuesto`
- **tag**: `mecanica_ausente`
- **estados**: coahuila(1)
- **rango años**: 2010
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no contiene la mecánica del Impuesto Predial. El contenido visible corresponde al Impuesto sobre Adquisición de Inmuebles y a reglas de diferimiento/pago de ese impuesto, no a una tabla o tarifa de predial.

<details><summary>Lista completa (1 casos)</summary>

- `coahuila` · nadadores (2010) — cvegeo 05021

</details>

### Grupo #16 — 1 caso(s)  ·  `ocr_ilegible`

- **categoria**: `segmento_vacio`
- **tag**: `ocr_ilegible`
- **estados**: guanajuato(1)
- **rango años**: 2025
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no incluye el contenido tarifario del Impuesto Predial; sólo aparecen páginas de portada/índice y páginas en blanco o sin OCR útil entre las páginas 3 a 20. No es posible extraer una mecánica de cálculo sin una tabla o artículo visible.

<details><summary>Lista completa (1 casos)</summary>

- `guanajuato` · irapuato (2025) — cvegeo 11017

</details>

### Grupo #17 — 1 caso(s)  ·  `texto_truncado`

- **categoria**: `segmento_vacio`
- **tag**: `texto_truncado`
- **estados**: coahuila(1)
- **rango años**: 2010
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no contiene la mecánica de cálculo del impuesto predial; sólo aparecen disposiciones sobre diferimiento del pago y una referencia incompleta a adquisiciones de inmuebles. No hay tabla, cuota, tasa ni brackets extraíbles para estructurar el predial.

<details><summary>Lista completa (1 casos)</summary>

- `coahuila` · muzquiz (2010) — cvegeo 05020

</details>

## 3. Casos `requiere_revision` excluyendo `otro_no_clasificado`

Total: **5**

| Estado | Año | Slug | tipo_corregido | Escalado | Razón |
|---|---:|---|---|:-:|---|
| guanajuato | 2011 | victoria | `FALTA_PREDIAL` |  | texto_fuente_no_encontrado |
| yucatan | 2024 | chemax | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.progresivo: Value error, brackets 5→6: hueco detectado (superior=15000.0, siguiente inferior=15500. |
| yucatan | 2012 | kinchil | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente inferior=70000.01) \ |
| yucatan | 2013 | kinchil | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente inferior=70000.0) \| |
| yucatan | 2015 | kinchil | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente inferior=70000.01) \ |

## 4. Métricas resumen

- Total JSONs: **3371**
- Schema-validados (load + Pydantic v2): **3366** (99.9%)
- `otro_no_clasificado`: **193** (5.7%) en 17 grupos
- `requiere_revision` total: **81** (2.4%)
- Escalados a fallback (`gpt-5.4`): **123** (3.6%)
