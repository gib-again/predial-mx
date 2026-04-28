# Reporte taxonómico — extracciones predial v2

Fuente: `predial-mx-v2/`  ·  Estados: coahuila, guanajuato, tamaulipas, yucatan  ·  Total JSONs: **3248**

## 1. Distribución por `tipo_corregido`

### Global

| Tipo | Casos | % |
|---|---:|---:|
| `tarifa_millar` | 1689 | 52.0% |
| `progresivo` | 859 | 26.4% |
| `mixto` | 343 | 10.6% |
| `tasa_unica` | 170 | 5.2% |
| `otro_no_clasificado` | 104 | 3.2% |
| `cuota_fija_simple` | 42 | 1.3% |
| `FALTA_PREDIAL` | 21 | 0.6% |
| `cuota_fija_escalonada` | 20 | 0.6% |
| **Total** | **3248** | 100.0% |

### Por estado

| Estado | `tarifa_millar` | `progresivo` | `mixto` | `tasa_unica` | `otro_no_clasificado` | `cuota_fija_simple` | `FALTA_PREDIAL` | `cuota_fija_escalonada` | Total |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| coahuila | 535 | 18 | 17 | 0 | 8 | 0 | 1 | 0 | **579** |
| guanajuato | 487 | 50 | 24 | 3 | 58 | 5 | 0 | 0 | **627** |
| tamaulipas | 600 | 60 | 18 | 0 | 6 | 1 | 0 | 0 | **685** |
| yucatan | 67 | 731 | 284 | 167 | 32 | 36 | 20 | 20 | **1357** |

## 2. Casos `otro_no_clasificado` agrupados por similitud

Total casos: **104**  ·  Grupos distintos: **20**  ·  Criterio: `(categoria, tag_semántico)` — el tag se asigna por keywords-regex sobre `descripcion_estructural`. Una descripción que matchea el primer patrón gana ese tag (early-match-wins).

### Grupo #1 — 37 caso(s)  ·  `solo_encabezado`

- **categoria**: `segmento_vacio`
- **tag**: `solo_encabezado`
- **estados**: coahuila(3), guanajuato(31), yucatan(3)
- **rango años**: 2010–2026 (10 años distintos)
- **muni-años afectados**: 37

**descripcion_estructural (ejemplar)**:

> El texto proporcionado para la sección de predial no contiene la mecánica de cálculo del impuesto: las páginas indicadas aparecen vacías de tablas tarifarias y sólo se observan encabezados, definiciones y páginas en blanco dentro del segmento extraído. No es posible identificar una tarifa, brackets, cuotas o tasas aplicables sin inventar información.

<details><summary>Lista completa (37 casos)</summary>

- `coahuila` · ocampo (2010) — cvegeo 05023
- `coahuila` · piedras_negras (2010) — cvegeo 05025
- `coahuila` · ramos_arizpe (2010) — cvegeo 05027
- `guanajuato` · abasolo (2025) — cvegeo 11001
- `guanajuato` · atarjea (2025) — cvegeo 11006
- `guanajuato` · atarjea (2026) — cvegeo 11006
- `guanajuato` · comonfort (2025) — cvegeo 11009
- `guanajuato` · cortazar (2023) — cvegeo 11011
- `guanajuato` · cortazar (2025) — cvegeo 11011
- `guanajuato` · cortazar (2026) — cvegeo 11011
- `guanajuato` · cueramaro (2026) — cvegeo 11012
- `guanajuato` · dolores_hidalgo_cuna_de_la_independencia_nacional (2025) — cvegeo 11014
- `guanajuato` · dolores_hidalgo_cuna_de_la_independencia_nacional (2026) — cvegeo 11014
- `guanajuato` · guanajuato (2026) — cvegeo 11015
- `guanajuato` · huanimaro (2015) — cvegeo 11016
- `guanajuato` · huanimaro (2026) — cvegeo 11016
- `guanajuato` · irapuato (2025) — cvegeo 11017
- `guanajuato` · jaral_del_progreso (2024) — cvegeo 11018
- `guanajuato` · jerecuaro (2023) — cvegeo 11019
- `guanajuato` · leon (2020) — cvegeo 11020
- `guanajuato` · moroleon (2026) — cvegeo 11021
- `guanajuato` · purisima_del_rincon (2024) — cvegeo 11025
- `guanajuato` · purisima_del_rincon (2026) — cvegeo 11025
- `guanajuato` · romita (2025) — cvegeo 11026
- `guanajuato` · salamanca (2024) — cvegeo 11027
- `guanajuato` · salvatierra (2025) — cvegeo 11028
- `guanajuato` · san_diego_de_la_union (2024) — cvegeo 11029
- `guanajuato` · san_diego_de_la_union (2025) — cvegeo 11029
- `guanajuato` · san_felipe (2025) — cvegeo 11030
- `guanajuato` · san_luis_de_la_paz (2026) — cvegeo 11033
- `guanajuato` · santiago_maravatio (2025) — cvegeo 11036
- `guanajuato` · uriangato (2020) — cvegeo 11041
- `guanajuato` · victoria (2021) — cvegeo 11043
- `guanajuato` · yuriria (2018) — cvegeo 11046
- `yucatan` · progreso (2010) — cvegeo 31059
- `yucatan` · progreso (2011) — cvegeo 31059
- `yucatan` · yaxcaba (2011) — cvegeo 31104

</details>

### Grupo #2 — 12 caso(s)  ·  `dos_tarifas_paralelas`

- **categoria**: `estructura_no_estandar`
- **tag**: `dos_tarifas_paralelas`
- **estados**: yucatan(12)
- **rango años**: 2010–2025 (10 años distintos)
- **muni-años afectados**: 12

**descripcion_estructural (ejemplar)**:

> El artículo 4 describe una mecánica progresiva por rangos de valor catastral con cuota fija y factor sobre el excedente, pero en el texto proporcionado no aparecen los límites inferior/superior ni la tabla de rangos y tasas; además se incluyen tablas de valores unitarios de terreno y construcción que son catastro, no la tarifa del impuesto. El artículo 6 sí establece una tasa paralela para predios agropecuarios (12 al millar anual), pero no viene estructurada como tabla completa de predial. Por ello no es posible clasificar con precisión en las variantes tarifarias solicitadas sin inventar los brackets faltantes.

<details><summary>Lista completa (12 casos)</summary>

- `yucatan` · akil (2025) — cvegeo 31003
- `yucatan` · sanahcat (2010) — cvegeo 31064 — escalado
- `yucatan` · sanahcat (2011) — cvegeo 31064 — escalado
- `yucatan` · sanahcat (2012) — cvegeo 31064 — escalado
- `yucatan` · sanahcat (2014) — cvegeo 31064 — escalado
- `yucatan` · sanahcat (2017) — cvegeo 31064 — escalado
- `yucatan` · sanahcat (2018) — cvegeo 31064 — escalado
- `yucatan` · sanahcat (2019) — cvegeo 31064 — escalado
- `yucatan` · sanahcat (2020) — cvegeo 31064 — escalado
- `yucatan` · sanahcat (2022) — cvegeo 31064 — escalado
- `yucatan` · seye (2011) — cvegeo 31067
- `yucatan` · yaxkukul (2022) — cvegeo 31105

</details>

### Grupo #3 — 12 caso(s)  ·  `seccion_ausente`

- **categoria**: `segmento_vacio`
- **tag**: `seccion_ausente`
- **estados**: coahuila(1), guanajuato(11)
- **rango años**: 2010–2026 (6 años distintos)
- **muni-años afectados**: 12

**descripcion_estructural (ejemplar)**:

> En el texto proporcionado no aparece la sección normativa del Impuesto Predial ni una tabla tarifaria de cálculo; sólo se observan páginas con el índice y montos estimados de ingresos, y las páginas señaladas para predial están vacías o sin transcripción legible del articulado. No es posible extraer mecánica de cálculo sin inventar contenido.

<details><summary>Lista completa (12 casos)</summary>

- `coahuila` · parras (2010) — cvegeo 05024
- `guanajuato` · acambaro (2025) — cvegeo 11002
- `guanajuato` · apaseo_el_grande (2025) — cvegeo 11005
- `guanajuato` · celaya (2024) — cvegeo 11007
- `guanajuato` · comonfort (2023) — cvegeo 11009
- `guanajuato` · cueramaro (2025) — cvegeo 11012
- `guanajuato` · irapuato (2026) — cvegeo 11017
- `guanajuato` · purisima_del_rincon (2021) — cvegeo 11025
- `guanajuato` · salamanca (2025) — cvegeo 11027
- `guanajuato` · santa_catarina (2026) — cvegeo 11034
- `guanajuato` · santa_cruz_de_juventino_rosas (2026) — cvegeo 11035
- `guanajuato` · valle_de_santiago (2025) — cvegeo 11042

</details>

### Grupo #4 — 7 caso(s)  ·  `otro_patron`

- **categoria**: `municipio_sin_impuesto`
- **tag**: `otro_patron`
- **estados**: coahuila(1), guanajuato(4), tamaulipas(2)
- **rango años**: 2010–2026 (6 años distintos)
- **muni-años afectados**: 7

**descripcion_estructural (ejemplar)**:

> El texto sólo establece una cuota mínima anual de tres salarios mínimos para el impuesto predial, pero no contiene tabla, rangos, tasa al millar ni fórmula de cálculo adicional para determinar la base del impuesto. La sección transcrita se limita a bonificaciones y a una cuota mínima, sin mecánica estructural completa del gravamen.

<details><summary>Lista completa (7 casos)</summary>

- `coahuila` · nadadores (2010) — cvegeo 05021
- `guanajuato` · salvatierra (2026) — cvegeo 11028
- `guanajuato` · san_francisco_del_rincon (2021) — cvegeo 11031
- `guanajuato` · silao_de_la_victoria (2026) — cvegeo 11037
- `guanajuato` · tierra_blanca (2024) — cvegeo 11040
- `tamaulipas` · miguel_aleman (2012) — cvegeo 28025
- `tamaulipas` · miguel_aleman (2013) — cvegeo 28025

</details>

### Grupo #5 — 6 caso(s)  ·  `otro_patron`

- **categoria**: `estructura_no_estandar`
- **tag**: `otro_patron`
- **estados**: tamaulipas(2), yucatan(4)
- **rango años**: 2010–2024 (4 años distintos)
- **muni-años afectados**: 6

**descripcion_estructural (ejemplar)**:

> El texto no presenta una tabla tarifaria única del predial en forma de tarifa_millar, progresivo, tasa_unica, cuota_fija_simple, cuota_fija_escalonada o mixto. La mecánica principal es una fórmula general: valor catastral por 0.00025, con una cuota fija de $50.00 si el valor catastral es menor o igual a $200,000.00; además, el artículo 14 introduce topes de incremento respecto del ejercicio anterior. La mecánica de cálculo queda combinada con una regla de cuota fija por umbral y un factor general, pero no se estructura como un esquema estándar de brackets o tarifas categóricas.

<details><summary>Lista completa (6 casos)</summary>

- `tamaulipas` · nuevo_laredo (2024) — cvegeo 28027
- `tamaulipas` · san_fernando (2023) — cvegeo 28035
- `yucatan` · kaua (2023) — cvegeo 31043
- `yucatan` · mani (2014) — cvegeo 31047 — escalado
- `yucatan` · tekit (2014) — cvegeo 31080 — escalado
- `yucatan` · yaxcaba (2010) — cvegeo 31104 — escalado

</details>

### Grupo #6 — 6 caso(s)  ·  `solo_valores_unitarios`

- **categoria**: `estructura_no_estandar`
- **tag**: `solo_valores_unitarios`
- **estados**: guanajuato(1), yucatan(5)
- **rango años**: 2010–2025 (4 años distintos)
- **muni-años afectados**: 6

**descripcion_estructural (ejemplar)**:

> El texto no presenta una tarifa del impuesto predial clasificable en una de las variantes permitidas. En el Artículo 12 sólo se indica una cuota fija de $10.00 más el resultado de un factor sobre el valor catastral, junto con un procedimiento de valuación del inmueble y tablas de valores unitarios de terreno y construcción; esas tablas son de catastro/valuación, no una tabla tarifaria de predial. No hay brackets, tasa uniforme explícita, ni catálogo de tasas por categoría que permita estructurar la mecánica como tarifa_millar, progresivo, cuota fija escalonada o mixto.

<details><summary>Lista completa (6 casos)</summary>

- `guanajuato` · valle_de_santiago (2021) — cvegeo 11042
- `yucatan` · dzidzantun (2010) — cvegeo 31027 — escalado
- `yucatan` · dzidzantun (2012) — cvegeo 31027
- `yucatan` · tekanto (2010) — cvegeo 31078
- `yucatan` · tepakan (2025) — cvegeo 31086
- `yucatan` · xocchel (2025) — cvegeo 31103

</details>

### Grupo #7 — 4 caso(s)  ·  `solo_valores_unitarios`

- **categoria**: `error_segmentacion`
- **tag**: `solo_valores_unitarios`
- **estados**: guanajuato(1), yucatan(3)
- **rango años**: 2019–2025 (3 años distintos)
- **muni-años afectados**: 4

**descripcion_estructural (ejemplar)**:

> El texto sí menciona que el impuesto se determinará con una tabla y que se calcula con diferencia contra límite inferior, factor aplicable y cuota fija, lo que sugiere una tarifa progresiva o escalonada; sin embargo, la tabla tarifaria del impuesto predial no aparece en el segmento. El contenido visible corresponde a valores unitarios catastrales de terreno y construcción, que no son la tarifa del impuesto, por lo que no es posible reconstruir válidamente los rangos, cuotas fijas o factores aplicables.

<details><summary>Lista completa (4 casos)</summary>

- `guanajuato` · leon (2019) — cvegeo 11020 — escalado
- `yucatan` · akil (2023) — cvegeo 31003 — escalado
- `yucatan` · tunkas (2023) — cvegeo 31097 — escalado
- `yucatan` · tunkas (2025) — cvegeo 31097 — escalado

</details>

### Grupo #8 — 3 caso(s)  ·  `articulado_ausente`

- **categoria**: `segmento_vacio`
- **tag**: `articulado_ausente`
- **estados**: guanajuato(3)
- **rango años**: 2024–2025 (2 años distintos)
- **muni-años afectados**: 3

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no contiene el artículo ni la tabla específica de la mecánica del Impuesto Predial. Solo aparecen disposiciones de ajustes, recurso de revisión y referencias indirectas al artículo 21 de otra sección, pero no la tarifa o estructura de cálculo del predial. No es posible clasificar la mecánica sin inventarla.

<details><summary>Lista completa (3 casos)</summary>

- `guanajuato` · acambaro (2024) — cvegeo 11002
- `guanajuato` · apaseo_el_alto (2025) — cvegeo 11004
- `guanajuato` · tierra_blanca (2025) — cvegeo 11040

</details>

### Grupo #9 — 3 caso(s)  ·  `mecanica_ausente`

- **categoria**: `segmento_vacio`
- **tag**: `mecanica_ausente`
- **estados**: coahuila(2), guanajuato(1)
- **rango años**: 2010–2025 (2 años distintos)
- **muni-años afectados**: 3

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no contiene la mecánica tarifaria del impuesto predial (tasas, cuotas o brackets). La sección visible sólo muestra referencias generales, páginas en blanco/omitidas y una cuota mínima anual en el artículo de facilidades administrativas, pero no la tabla base de cálculo del predial. Por ello no es posible clasificar la estructura con las variantes tarifarias solicitadas.

<details><summary>Lista completa (3 casos)</summary>

- `coahuila` · nava (2010) — cvegeo 05022
- `coahuila` · progreso (2010) — cvegeo 05026
- `guanajuato` · tarandacuao (2025) — cvegeo 11038

</details>

### Grupo #10 — 2 caso(s)  ·  `factor_sin_tabla`

- **categoria**: `estructura_no_estandar`
- **tag**: `factor_sin_tabla`
- **estados**: yucatan(2)
- **rango años**: 2023–2025 (2 años distintos)
- **muni-años afectados**: 2

**descripcion_estructural (ejemplar)**:

> El texto no presenta una sola mecánica estándar de cálculo de predial. Para predial base valor catastral, el artículo indica un factor de 0.00025 sobre el valor catastral actualizado y además una cuota fija de $150.00 para predios con valor catastral igual o menor a $200,000.00; sin embargo, también incluye una tarifa distinta sobre rentas o frutos civiles en el Art. 8 (2% habitacional y 5% comercial), que corresponde a otra base de cálculo. Por ello no encaja limpiamente en una sola de las variantes tarifarias solicitadas.

<details><summary>Lista completa (2 casos)</summary>

- `yucatan` · cansahcab (2023) — cvegeo 31009
- `yucatan` · mayapan (2025) — cvegeo 31049

</details>

### Grupo #11 — 2 caso(s)  ·  `solo_valores_unitarios`

- **categoria**: `municipio_sin_impuesto`
- **tag**: `solo_valores_unitarios`
- **estados**: guanajuato(2)
- **rango años**: 2018–2026 (2 años distintos)
- **muni-años afectados**: 2

**descripcion_estructural (ejemplar)**:

> El segmento proporcionado corresponde a tablas de valores unitarios de terreno y construcción para avalúo catastral, factores de zona, frente, forma, superficie, fondo, topografía y valores base rústicos, pero no muestra una tabla o mecánica de tasas/cuotas del impuesto predial (ni tarifa al millar, ni cuotas fijas por rangos, ni tasa única). Por ello no es posible clasificar la mecánica del impuesto predial con la información visible.

<details><summary>Lista completa (2 casos)</summary>

- `guanajuato` · tierra_blanca (2018) — cvegeo 11040
- `guanajuato` · uriangato (2026) — cvegeo 11041

</details>

### Grupo #12 — 2 caso(s)  ·  `otro_patron`

- **categoria**: `segmento_vacio`
- **tag**: `otro_patron`
- **estados**: guanajuato(1), tamaulipas(1)
- **rango años**: 2020–2024 (2 años distintos)
- **muni-años afectados**: 2

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no incluye la tabla de tarifas del Artículo 9; únicamente aparece la frase introductoria 'Se aplicará la siguiente tarifa para predios urbanos del municipio' y luego continúa con reglas de incrementos y mínimos. Sin la tabla de cuotas/tasas no es posible clasificar la mecánica de cálculo en una de las variantes tarifarias.

<details><summary>Lista completa (2 casos)</summary>

- `guanajuato` · salvatierra (2024) — cvegeo 11028
- `tamaulipas` · ciudad_madero (2020) — cvegeo 28009

</details>

### Grupo #13 — 1 caso(s)  ·  `dos_tarifas_paralelas`

- **categoria**: `error_segmentacion`
- **tag**: `dos_tarifas_paralelas`
- **estados**: yucatan(1)
- **rango años**: 2010
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El segmento contiene principalmente tablas de valores unitarios de terreno y construcción (catastro), pero no incluye la tabla tarifaria del impuesto predial por rangos o cuotas a la que alude la frase 'A la cantidad que se exceda del límite inferior...'. Sólo es visible una tarifa paralela para predios destinados a la producción agropecuaria de 10 al millar anual sobre el valor registrado o catastral, por lo que no hay información suficiente para reconstruir la tabla principal sin inventar rangos o montos.

<details><summary>Lista completa (1 casos)</summary>

- `yucatan` · mococha (2010) — cvegeo 31051 — escalado

</details>

### Grupo #14 — 1 caso(s)  ·  `otro_patron`

- **categoria**: `error_segmentacion`
- **tag**: `otro_patron`
- **estados**: guanajuato(1)
- **rango años**: 2025
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto describe expresamente una mecánica progresiva del impuesto predial con valor fiscal, límite inferior, tasa marginal y cuota fija, pero la tabla de TASAS no aparece en el segmento proporcionado. El contenido entre las páginas referidas está ausente o sustituido por encabezados de página y después cambia a otros conceptos distintos al predial, por lo que no es posible reconstruir válidamente los rangos ni las tasas.

<details><summary>Lista completa (1 casos)</summary>

- `guanajuato` · santa_cruz_de_juventino_rosas (2025) — cvegeo 11035 — escalado

</details>

### Grupo #15 — 1 caso(s)  ·  `ejidal_comunal`

- **categoria**: `estructura_no_estandar`
- **tag**: `ejidal_comunal`
- **estados**: yucatan(1)
- **rango años**: 2015
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto no presenta una tabla tarifaria estándar por valor catastral ni una cuota fija simple/escalonada. La mecánica principal indica 15 centavos por m2 de extensión del predio, y además establece una tarifa paralela distinta para predios destinados a la producción agropecuaria: 10 al millar anual sobre el valor registrado o catastral. No encaja de forma limpia en las variantes simples porque mezcla una base por superficie con una tasa al millar sobre valor catastral.

<details><summary>Lista completa (1 casos)</summary>

- `yucatan` · sanahcat (2015) — cvegeo 31064

</details>

### Grupo #16 — 1 caso(s)  ·  `ejidal_comunal`

- **categoria**: `municipio_sin_impuesto`
- **tag**: `ejidal_comunal`
- **estados**: yucatan(1)
- **rango años**: 2016
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto no presenta una tabla tarifaria por rangos ni un esquema clasificable en las variantes esperadas. Sólo se lee una regla general: '15 centavos por m2' y, para predios destinados a producción agropecuaria, '10 al millar anual sobre el valor registrado o catastral'. No hay estructura de brackets, categorías tarifarias comparables ni una tabla desarrollable en cuota fija/progresiva/tasa única.

<details><summary>Lista completa (1 casos)</summary>

- `yucatan` · sanahcat (2016) — cvegeo 31064

</details>

### Grupo #17 — 1 caso(s)  ·  `mecanica_ausente`

- **categoria**: `municipio_sin_impuesto`
- **tag**: `mecanica_ausente`
- **estados**: tamaulipas(1)
- **rango años**: 2013
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El segmento proporcionado sólo muestra renglones de recaudación/partidas presupuestales (propiedad urbana, suburbana y rústica) con montos agregados, pero no contiene la mecánica de determinación del impuesto predial: no hay tasas, cuotas, rangos de valor catastral ni tablas aplicables. No es posible transcribir una fórmula de cálculo a partir de este fragmento.

<details><summary>Lista completa (1 casos)</summary>

- `tamaulipas` · nuevo_laredo (2013) — cvegeo 28027

</details>

### Grupo #18 — 1 caso(s)  ·  `contenido_ausente`

- **categoria**: `segmento_vacio`
- **tag**: `contenido_ausente`
- **estados**: guanajuato(1)
- **rango años**: 2019
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto proporcionado no incluye el contenido de la sección 'Del Impuesto Predial' ni alguna tabla o artículo con la mecánica de cálculo; sólo aparecen metadatos y páginas de portadilla del periódico oficial. No es posible transcribir una tarifa sin el segmento tarifario.

<details><summary>Lista completa (1 casos)</summary>

- `guanajuato` · apaseo_el_grande (2019) — cvegeo 11005

</details>

### Grupo #19 — 1 caso(s)  ·  `solo_valores_unitarios`

- **categoria**: `segmento_vacio`
- **tag**: `solo_valores_unitarios`
- **estados**: guanajuato(1)
- **rango años**: 2018
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El fragmento proporcionado contiene únicamente encabezados, referencias a tablas de valores unitarios y factores de valuación (terreno/construcción), pero no incluye una mecánica tarifaria completa del impuesto predial con tasas, cuotas o brackets aplicables. No se observa una tabla de cálculo del predial transcribible sin inventar contenido.

<details><summary>Lista completa (1 casos)</summary>

- `guanajuato` · uriangato (2018) — cvegeo 11041

</details>

### Grupo #20 — 1 caso(s)  ·  `texto_truncado`

- **categoria**: `segmento_vacio`
- **tag**: `texto_truncado`
- **estados**: coahuila(1)
- **rango años**: 2010
- **muni-años afectados**: 1

**descripcion_estructural (ejemplar)**:

> El texto proporcionado inicia a media frase y corresponde a reglas de diferimiento/actualización del impuesto, pero no incluye la tabla o mecánica tarifaria del Impuesto Predial. No hay brackets, cuotas, tasas al millar ni una cuota fija identificable para transcribir.

<details><summary>Lista completa (1 casos)</summary>

- `coahuila` · muzquiz (2010) — cvegeo 05020

</details>

## 3. Casos `requiere_revision` excluyendo `otro_no_clasificado`

Total: **21**

| Estado | Año | Slug | tipo_corregido | Escalado | Razón |
|---|---:|---|---|:-:|---|
| coahuila | 2013 | hidalgo | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=api_error: APIConnectionError: Connection error. \| mini_e2=api_error: APIConnectionError: Connection error. \| |
| yucatan | 2022 | chemax | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, brackets 5→6: hueco detectado (superior=15000.0, siguiente inferior=15500.01) \ |
| yucatan | 2021 | conkal | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2010 | dzemul | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2012 | dzemul | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2013 | dzemul | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2015 | dzemul | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2014 | dzilam_gonzalez | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2015 | dzilam_gonzalez | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2016 | dzilam_gonzalez | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2018 | dzilam_gonzalez | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2021 | dzilam_gonzalez | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2022 | dzilam_gonzalez | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2011 | ixil | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2012 | ixil | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2012 | kinchil | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente inferior=70000.01) \ |
| yucatan | 2015 | mani | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2024 | rio_lagartos | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2018 | tekit | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2013 | telchac_pueblo | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |
| yucatan | 2019 | telchac_pueblo | `FALTA_PREDIAL` | ✓ | valido_3x_fallido \| mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango \| mini_e2=  • predi |

## 4. Métricas resumen

- Total JSONs: **3248**
- Schema-validados (load + Pydantic v2): **3227** (99.4%)
- `otro_no_clasificado`: **104** (3.2%) en 20 grupos
- `requiere_revision` total: **125** (3.8%)
- Escalados a fallback (`gpt-5.4`): **152** (4.7%)
