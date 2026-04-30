# Bitácora de revisión HITL — extracciones predial v2

> Working document. Tus anotaciones aquí alimentan mejoras del prompt/schema.
> Regenera con `python -m scripts.generar_bitacora` (no sobreescribe). Pasa
> `--force` para regenerar desde cero (BORRA anotaciones).

## Alcance y documentos relacionados

- **Esta bitácora** cubre extracciones LLM con `tipo_esquema=otro_no_clasificado`
  o `requiere_revision=True` en los 4 estados re-extraídos: Coahuila, Guanajuato,
  Tamaulipas, Yucatán. Foco: calidad de extracción / clasificación.
- **`output/audit_pendiente.md` + `output/audit_pendiente.csv`** cubren huecos
  del panel balanceado (motivos `sin_predial_residual`, `schema_discontinuity`,
  `edge`) — foco: cobertura temporal y reformas. Si un caso aparece en ambos,
  resuelve el del panel primero (decisión de imputación) y referencia su veredicto.
- **Sintéticos `short_form`** (122 JSONs en Yucatán generados por
  `scripts/synthesize_short_form_jsons.py` cuando el segmentador detectó leyes
  de ingreso en formato corto) **se excluyen automáticamente** de esta bitácora —
  son markers deterministas, no errores LLM. Identificables por
  `_meta.modelo == "synthesized_short_form"`.
- **Estados fuera de scope (no incluidos)**: Colima, Edomex, Sinaloa, Tabasco.
  Si quieres extenderlos, edita `ESTADOS` en `scripts/generar_bitacora.py`.

## Cómo usar

Para cada caso listado:

1. Abre el JSON en `predial-mx-v2/...` y compáralo contra el TXT fuente en
   `data/{estado}/focus_predial/{anio}/...`.
2. Marca `[x] revisado` cuando termines.
3. Llena los campos con los valores válidos del esquema de abajo.
4. Si el caso pertenece a un patrón transversal, agrégalo a la sección
   **Patrones detectados** y referencia su `P-XX` en `patron:` del caso.

Después de varias revisiones, comparte el archivo conmigo: extraigo los
campos automáticamente y propongo fixes basados en los patrones acumulados.

## Esquema de campos (no editar la tabla)

| Campo | Valores válidos |
|---|---|
| `revisado` | `[ ]` pendiente · `[x]` hecho |
| `veredicto` | `correcto` · `incorrecto` · `parcial` · `invalido` |
| `tipo_correcto` | `tarifa_millar` · `progresivo` · `tasa_unica` · `cuota_fija_simple` · `cuota_fija_escalonada` · `mixto` · `otro_no_clasificado` · `n/a` |
| `causa_raiz` | `segmentacion` · `prompt` · `schema` · `ocr` · `documento_ambiguo` · `api_error` · `clasificacion_correcta` · `otro` |
| `patron` | `P-XX` (id de la sección de patrones) · vacío si caso aislado |
| `notas` | prosa libre |
| `accion` | prosa libre — fix sugerido o `n/a` |

### Convenciones de veredicto

- **`correcto`** — el LLM clasificó bien (incluye casos `otro_no_clasificado`
  legítimos, p.ej. errata documental real).
- **`incorrecto`** — el LLM clasificó mal y hay clasificación correcta posible.
- **`parcial`** — clasificación mejor que nada pero pierde información (ej.
  capturó una de dos tarifas paralelas).
- **`invalido`** — el JSON está vacío / FALTA_PREDIAL / api_error sin recovery.

---

## Patrones detectados

> Acumula aquí los hallazgos transversales que afectan a múltiples casos.
> Cada `P-XX` representa un cambio de código pendiente.

### P-00: ejemplo (borra al agregar el primero)

- **casos**: estado/slug/anio, …
- **diagnostico**: descripción del patrón
- **fix_propuesto**: qué cambiar (prompt, schema, segment, etc.)
- **prioridad**: alta · media · baja
- **estado**: pending · in_progress · done

---


## Tabla de contenidos

- [Grupo G-01: `segmento_vacio` / `solo_encabezado` (9 casos)](#grupo-g-01-segmento-vacio-solo-encabezado)
- [Grupo G-02: `error_segmentacion` / `solo_valores_unitarios` (3 casos)](#grupo-g-02-error-segmentacion-solo-valores-unitarios)
- [Grupo G-03: `estructura_no_estandar` / `dos_tarifas_paralelas` (3 casos)](#grupo-g-03-estructura-no-estandar-dos-tarifas-paralelas)
- [Grupo G-04: `estructura_no_estandar` / `solo_valores_unitarios` (3 casos)](#grupo-g-04-estructura-no-estandar-solo-valores-unitarios)
- [Grupo G-05: `municipio_sin_impuesto` / `otro_patron` (3 casos)](#grupo-g-05-municipio-sin-impuesto-otro-patron)
- [Grupo G-06: `municipio_sin_impuesto` / `mecanica_ausente` (2 casos)](#grupo-g-06-municipio-sin-impuesto-mecanica-ausente)
- [Grupo G-07: `estructura_no_estandar` / `solo_valores_catastro` (1 casos)](#grupo-g-07-estructura-no-estandar-solo-valores-catastro)
- [Grupo G-08: `municipio_sin_impuesto` / `seccion_ausente` (1 casos)](#grupo-g-08-municipio-sin-impuesto-seccion-ausente)
- [Grupo G-09: `segmento_vacio` / `ocr_ilegible` (1 casos)](#grupo-g-09-segmento-vacio-ocr-ilegible)
- [Grupo G-10: `segmento_vacio` / `seccion_ausente` (1 casos)](#grupo-g-10-segmento-vacio-seccion-ausente)
- [Casos `requiere_revision` (3 casos)](#casos-requiere_revision-excluyendo-otro_no_clasificado)

> ℹ️ Se excluyeron **117 JSONs sintéticos** (`_meta.modelo == 'synthesized_short_form'`) que no requieren HITL.

## Casos `otro_no_clasificado` (27 casos en 10 grupos)

## Grupo G-01: `segmento_vacio` / `solo_encabezado` (9 casos)

### `coahuila/ocampo/2010` (cvegeo 05023)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_ocampo.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_ocampo.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El segmento proporcionado sólo contiene el encabezado 'DEL IMPUESTO PREDIAL' sin texto tarifario, tablas, cuotas, tasas ni rangos de cálculo. No es posible extraer la mecánica del impuesto predial con este contenido.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `coahuila/piedras_negras/2010` (cvegeo 05025)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_piedras_negras.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_piedras_negras.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El segmento proporcionado sólo contiene el encabezado de la sección 'Del Impuesto Predial' y no incluye texto tarifario, tablas, rangos ni tasas para extraer la mecánica de cálculo.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `coahuila/ramos_arizpe/2010` (cvegeo 05027)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_ramos_arizpe.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_ramos_arizpe.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El segmento proporcionado sólo contiene el encabezado del capítulo 'Del Impuesto Predial' y no incluye texto tarifario, tablas, cuotas, tasas ni brackets. No es posible extraer una mecánica de cálculo sin contenido normativo adicional.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `guanajuato/cortazar/2023` (cvegeo 11011)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2023_cortazar.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2023_cortazar.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado para la sección de impuesto predial no contiene la mecánica tarifaria ni tablas de cálculo; sólo aparecen portadas, encabezados y páginas en blanco o sin contenido extraíble entre las páginas 162 y 179. No es posible transcribir una tarifa sin inventarla.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `guanajuato/irapuato/2025` (cvegeo 11017)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_irapuato.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_irapuato.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no incluye el contenido tarifario del impuesto predial; sólo aparecen encabezados, sumarios de ingresos y páginas en blanco o sin transcripción legible de la sección correspondiente. No es posible extraer una mecánica de cálculo sin inventar la tabla o el artículo aplicable.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `guanajuato/san_diego_de_la_union/2024` (cvegeo 11029)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2024_san_diego_de_la_union.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2024_san_diego_de_la_union.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria del impuesto predial ni tablas o artículos con mecánica de cálculo; sólo aparecen encabezados generales y páginas en blanco/omitidas dentro del bloque de predial. No es posible extraer una estructura de cálculo sin inventar datos.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `guanajuato/san_francisco_del_rincon/2021` (cvegeo 11031)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2021_san_francisco_del_rincon.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2021_san_francisco_del_rincon.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado sólo contiene encabezado y pie de página del periódico oficial, sin contenido tarifario ni articulado del Impuesto Predial. No es posible extraer mecánica de cálculo.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `guanajuato/valle_de_santiago/2025` (cvegeo 11042)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_valle_de_santiago.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_valle_de_santiago.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado sólo muestra el encabezado presupuestal '1201 impuesto predial' con su estimado de recaudación, pero no incluye el artículo o tabla que describa la mecánica de cálculo del impuesto. No hay rangos, tasas, cuotas ni categorías extraíbles para estructurar el predial.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `guanajuato/yuriria/2018` (cvegeo 11046)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2018_yuriria.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2018_yuriria.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección del Impuesto Predial ni ninguna tabla, cuota o tasa aplicable; sólo aparece el encabezado del decreto y referencia al periódico oficial. No es posible extraer la mecánica de cálculo.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

## Grupo G-02: `error_segmentacion` / `solo_valores_unitarios` (3 casos)

### `yucatan/akil/2023` (cvegeo 31003)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2023_akil.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2023_akil.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `error_segmentacion`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto describe la mecánica de un esquema progresivo ('límites inferior y superior', 'cuota fija' y aplicación de un 'factor' al excedente), pero la tabla tarifaria con los rangos y factores no aparece en el segmento proporcionado. Sólo se observan tablas catastrales de valores unitarios y una tarifa paralela para predios destinados a la producción agropecuaria de 10 al millar anual.
- **razon**: `clasificado_como_otro_no_clasificado_tras_escalacion`
- **escalado**: sí (gpt-5.4)

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `yucatan/tunkas/2023` (cvegeo 31097)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2023_tunkas.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2023_tunkas.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `error_segmentacion`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto menciona que el impuesto se determinará con una tabla y describe una mecánica de diferencia entre valor catastral, límite inferior, factor aplicable y cuota fija, lo que sugiere una tarifa progresiva o escalonada. Sin embargo, la tabla del impuesto predial no aparece en el segmento: sólo se incluyen valores unitarios de terreno y construcción catastral, que no son la tarifa del impuesto.
- **razon**: `clasificado_como_otro_no_clasificado_tras_escalacion`
- **escalado**: sí (gpt-5.4)

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `yucatan/tunkas/2025` (cvegeo 31097)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2025_tunkas.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2025_tunkas.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `error_segmentacion`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto sí menciona que el impuesto se determinará con una tabla y que se calcula con diferencia contra límite inferior, factor aplicable y cuota fija, lo que sugiere una tarifa progresiva o escalonada; sin embargo, la tabla tarifaria del impuesto predial no aparece en el segmento. El contenido visible corresponde a valores unitarios catastrales de terreno y construcción, que no son la tarifa del impuesto, por lo que no es posible reconstruir válidamente los rangos, cuotas fijas o factores aplicables.
- **razon**: `clasificado_como_otro_no_clasificado_tras_escalacion`
- **escalado**: sí (gpt-5.4)

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

## Grupo G-03: `estructura_no_estandar` / `dos_tarifas_paralelas` (3 casos)

### `yucatan/akil/2025` (cvegeo 31003)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2025_akil.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2025_akil.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El artículo 4 describe una mecánica progresiva por rangos de valor catastral con cuota fija y factor sobre el excedente, pero en el texto proporcionado no aparecen los límites inferior/superior ni la tabla de rangos y tasas; además se incluyen tablas de valores unitarios de terreno y construcción que son catastro, no la tarifa del impuesto. El artículo 6 sí establece una tasa paralela para predios agropecuarios (12 al millar anual), pero no viene estructurada como tabla completa de predial. Por ello no es posible clasificar con precisión en las variantes tarifarias solicitadas sin inventar los brackets faltantes.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `yucatan/dzidzantun/2012` (cvegeo 31027)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2012_dzidzantun.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2012_dzidzantun.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El artículo 14 mezcla una tabla de valores unitarios de terreno (insumo catastral) con una mecánica de cálculo que sólo indica que al excedente del límite inferior se le aplica un factor de la tarifa y se suma una cuota fija anual, pero en el texto proporcionado no aparecen los brackets completos ni los valores de la tasa/cuota fija anual respectiva. Además contiene una tarifa paralela para predios agropecuarios de $2.00 por hectárea, separada de la mecánica principal.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `yucatan/yaxkukul/2022` (cvegeo 31105)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2022_yaxkukul.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2022_yaxkukul.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El texto no presenta una mecánica única de predial sobre valor catastral clasificable en una sola tabla. Primero aparece una tabla de valores unitarios de terreno y de construcción para el cálculo del valor catastral, pero no una tarifa de impuesto predial. Después, el Artículo 14 establece dos mecánicas paralelas: predios agropecuarios al 10 al millar anual sobre valor catastral, y predios con base en rentas o frutos civiles al 5% mensual para habitación y comercial. La estructura tarifaria principal del impuesto predial no queda extraíble en una sola de las variantes cerradas sin mezclar mecánicas heterogéneas.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

## Grupo G-04: `estructura_no_estandar` / `solo_valores_unitarios` (3 casos)

### `yucatan/dzidzantun/2010` (cvegeo 31027)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2010_dzidzantun.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2010_dzidzantun.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El segmento no contiene una tabla tarifaria operable del impuesto predial por rangos, tasas al millar o cuota fija, sino tablas de valores catastrales de terreno por calle y valores unitarios de construcción por material/zona. Aunque aparece la frase 'A la cantidad que se exceda del límite inferior...', no se muestran los rangos, límites ni factores de la tarifa correspondiente, por lo que la mecánica del impuesto quedó truncada o ausente.
- **razon**: `clasificado_como_otro_no_clasificado_tras_escalacion`
- **escalado**: sí (gpt-5.4)

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `yucatan/tekanto/2010` (cvegeo 31078)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2010_tekanto.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2010_tekanto.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto no presenta una tarifa predial clasificable en las variantes solicitadas. La mecánica principal remite a tablas de valores unitarios de terreno y construcción por zona y tipo de material, que son insumo catastral y no una tarifa de cálculo del impuesto en las variantes dadas. Además, el Art. 15 establece el impuesto sobre rentas o frutos civiles, que debe ignorarse según la consigna.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `yucatan/yaxkukul/2024` (cvegeo 31105)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2024_yaxkukul.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2024_yaxkukul.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto no presenta una mecánica tarifaria del impuesto predial directamente sobre la base imponible. El artículo 13 establece valores unitarios de terreno y construcción para integrar el valor catastral, y el artículo 14 añade una tarifa para predios agropecuarios (10 al millar) y otra sobre rentas o frutos civiles (5% mensual) para predios habitación y comerciales. No hay una tabla única del predial sobre valor catastral que encaje de forma limpia en una de las seis estructuras estándar sin mezclar mecánicas distintas.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

## Grupo G-05: `municipio_sin_impuesto` / `otro_patron` (3 casos)

### `guanajuato/tierra_blanca/2025` (cvegeo 11040)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_tierra_blanca.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_tierra_blanca.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto proporcionado no contiene una mecánica de cálculo del impuesto predial. El fragmento visible corresponde a descuentos de servicios de agua, servicios catastrales, medios de defensa y ajustes tarifarios, pero no aparece una tarifa, tabla o tasa del impuesto predial para Tierra Blanca, Guanajuato.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `yucatan/conkal/2023` (cvegeo 31013)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2023_conkal.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2023_conkal.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El segmento no contiene una mecánica de cálculo del impuesto predial. Sólo incluye el pronóstico de ingreso ('Impuesto predial $8,884,740.00') dentro del artículo de clasificaciones de ingresos, y la nota del segmentador indica expresamente que la ley de ingresos corta no trae tarifas, tasas, montos al millar ni rangos, remitiendo a la Ley General de Hacienda Municipal del Estado de Yucatán.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `yucatan/conkal/2024` (cvegeo 31013)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2024_conkal.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2024_conkal.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El segmento sólo contiene el pronóstico presupuestal del rubro 'Impuesto predial' en el Artículo 5, pero no incluye tarifas, tasas, rangos, cuotas ni mecánica de cálculo. La propia nota del segmentador indica que la ley corta remite a la Ley General de Hacienda Municipal del Estado de Yucatán para la regulación aplicable.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

## Grupo G-06: `municipio_sin_impuesto` / `mecanica_ausente` (2 casos)

### `yucatan/conkal/2025` (cvegeo 31013)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2025_conkal.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2025_conkal.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `mecanica_ausente`
- **descripcion_estructural**:
  > El segmento no contiene la mecánica de cálculo del impuesto predial. Únicamente aparece el pronóstico presupuestal del artículo 5 con el concepto 'Impuesto predial' por $19,143,850.00, sin tarifas, tasas, rangos, cuotas o remisión articulada a la Ley General de Hacienda Municipal del Estado de Yucatán dentro del texto proporcionado.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `yucatan/kaua/2025` (cvegeo 31043)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2025_kaua.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2025_kaua.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `mecanica_ausente`
- **descripcion_estructural**:
  > El segmento sólo contiene el pronóstico presupuestal de ingresos por concepto, incluyendo una cifra global de 'Impuesto predial', pero no establece tarifa, tasa, cuota fija, monto al millar ni rangos de valor catastral. La nota del segmentador indica además que la mecánica del impuesto se rige por la Ley General de Hacienda Municipal del Estado de Yucatán, por lo que esta ley municipal no contiene la mecánica de cálculo del predial.
- **razon**: `clasificado_como_otro_no_clasificado`
- **escalado**: sí (gpt-5.4)

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

## Grupo G-07: `estructura_no_estandar` / `solo_valores_catastro` (1 casos)

### `yucatan/kinchil/2024` (cvegeo 31044)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2024_kinchil.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2024_kinchil.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_catastro`
- **descripcion_estructural**:
  > El texto transcrito no contiene una tarifa del impuesto predial en forma de cuotas, rangos o tasas por valor catastral; contiene principalmente una tabla de valores catastrales/unitarios de terreno y construcción para determinar la base gravable. Solo aparece de forma separada una tarifa identificable para predios destinados a la producción agropecuaria de 10 al millar anual sobre el valor registrado o catastral, pero no se observa en el segmento la mecánica principal completa del impuesto predial para los demás predios.
- **razon**: `clasificado_como_otro_no_clasificado`
- **escalado**: sí (gpt-5.4)

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

## Grupo G-08: `municipio_sin_impuesto` / `seccion_ausente` (1 casos)

### `yucatan/conkal/2022` (cvegeo 31013)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2022_conkal.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2022_conkal.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > El segmento no contiene mecánica de cálculo del impuesto predial. Solo aparece el artículo de pronóstico presupuestal con el monto global de 'Impuesto predial' dentro del rubro de impuestos sobre el patrimonio, sin tarifas, tasas, rangos, bases de cálculo ni remisión expresa a una tabla aplicable dentro del texto proporcionado. La nota del segmentador indica además que la ley corta no incluye la sección tarifaria y que las contribuciones se rigen por la Ley General de Hacienda Municipal del Estado de Yucatán.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

## Grupo G-09: `segmento_vacio` / `ocr_ilegible` (1 casos)

### `guanajuato/acambaro/2025` (cvegeo 11002)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_acambaro.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_acambaro.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `ocr_ilegible`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria legible del Impuesto Predial para Acámbaro 2025. Las páginas incluidas muestran principalmente encabezados, listados de ingresos y ruido/OCR, pero no una tabla o mecánica de cálculo extraíble del predial.
- **razon**: `clasificado_como_otro_no_clasificado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

## Grupo G-10: `segmento_vacio` / `seccion_ausente` (1 casos)

### `guanajuato/purisima_del_rincon/2021` (cvegeo 11025)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2021_purisima_del_rincon.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2021_purisima_del_rincon.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria del Impuesto Predial del municipio; sólo incluye avisos del Periódico Oficial y un artículo de ajuste de cantidades. No hay tabla, tasa, cuota ni mecánica de cálculo del predial extraíble en este segmento.
- **razon**: `clasificado_como_otro_no_clasificado`
- **escalado**: sí (gpt-5.4)

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---


## Casos `requiere_revision` excluyendo `otro_no_clasificado` (3 casos)

### `guanajuato/victoria/2011` (cvegeo 11043)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2011_victoria.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2011_victoria.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `texto_fuente_no_encontrado`

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `yucatan/chemax/2022` (cvegeo 31019)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2022_chemax.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2022_chemax.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | e1=  • predial.progresivo: Value error, brackets 5→6: hueco detectado (superior=15000.0, siguiente inferior=15500.01) | e2=  • predial.progresivo: Value error, brackets 5→6: hueco detectado (superior=15000.0, siguiente i`
- **escalado**: sí (gpt-5.4)

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---

### `yucatan/kinchil/2010` (cvegeo 31044)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2010_kinchil.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2010_kinchil.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | e1=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente inferior=70000.01) | e2=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente inferior=70`
- **escalado**: sí (gpt-5.4)

**Revisión**:

- [ ] revisado
- veredicto: 
- tipo_correcto: 
- causa_raiz: 
- patron: 
- notas: 
- accion: 

---
