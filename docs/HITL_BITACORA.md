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

- [Grupo G-01: `segmento_vacio` / `solo_encabezado` (30 casos)](#grupo-g-01-segmento-vacio-solo-encabezado)
- [Grupo G-02: `estructura_no_estandar` / `solo_valores_unitarios` (8 casos)](#grupo-g-02-estructura-no-estandar-solo-valores-unitarios)
- [Grupo G-03: `municipio_sin_impuesto` / `otro_patron` (8 casos)](#grupo-g-03-municipio-sin-impuesto-otro-patron)
- [Grupo G-04: `segmento_vacio` / `articulado_ausente` (6 casos)](#grupo-g-04-segmento-vacio-articulado-ausente)
- [Grupo G-05: `estructura_no_estandar` / `dos_tarifas_paralelas` (4 casos)](#grupo-g-05-estructura-no-estandar-dos-tarifas-paralelas)
- [Grupo G-06: `error_segmentacion` / `solo_valores_unitarios` (3 casos)](#grupo-g-06-error-segmentacion-solo-valores-unitarios)
- [Grupo G-07: `segmento_vacio` / `mecanica_ausente` (3 casos)](#grupo-g-07-segmento-vacio-mecanica-ausente)
- [Grupo G-08: `estructura_no_estandar` / `otro_patron` (2 casos)](#grupo-g-08-estructura-no-estandar-otro-patron)
- [Grupo G-09: `municipio_sin_impuesto` / `solo_valores_unitarios` (2 casos)](#grupo-g-09-municipio-sin-impuesto-solo-valores-unitarios)
- [Grupo G-10: `segmento_vacio` / `otro_patron` (2 casos)](#grupo-g-10-segmento-vacio-otro-patron)
- [Grupo G-11: `segmento_vacio` / `seccion_ausente` (2 casos)](#grupo-g-11-segmento-vacio-seccion-ausente)
- [Grupo G-12: `estructura_no_estandar` / `mecanica_ausente` (1 casos)](#grupo-g-12-estructura-no-estandar-mecanica-ausente)
- [Grupo G-13: `estructura_no_estandar` / `ocr_ilegible` (1 casos)](#grupo-g-13-estructura-no-estandar-ocr-ilegible)
- [Grupo G-14: `municipio_sin_impuesto` / `dos_tarifas_paralelas` (1 casos)](#grupo-g-14-municipio-sin-impuesto-dos-tarifas-paralelas)
- [Grupo G-15: `municipio_sin_impuesto` / `mecanica_ausente` (1 casos)](#grupo-g-15-municipio-sin-impuesto-mecanica-ausente)
- [Grupo G-16: `segmento_vacio` / `ocr_ilegible` (1 casos)](#grupo-g-16-segmento-vacio-ocr-ilegible)
- [Grupo G-17: `segmento_vacio` / `texto_truncado` (1 casos)](#grupo-g-17-segmento-vacio-texto-truncado)
- [Casos `requiere_revision` (5 casos)](#casos-requiere_revision-excluyendo-otro_no_clasificado)

> ℹ️ Se excluyeron **117 JSONs sintéticos** (`_meta.modelo == 'synthesized_short_form'`) que no requieren HITL.

## Casos `otro_no_clasificado` (76 casos en 17 grupos)

## Grupo G-01: `segmento_vacio` / `solo_encabezado` (30 casos)

### `coahuila/ocampo/2010` (cvegeo 05023)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_ocampo.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_ocampo.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El segmento proporcionado sólo contiene el encabezado de la sección "Del Impuesto Predial" y no incluye artículo, tabla, rangos, tasas ni cuota aplicable. No es posible transcribir la mecánica de cálculo con el contenido recibido.
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
  > El texto proporcionado sólo contiene el encabezado del capítulo 'Del Impuesto Predial' y no incluye ningún artículo, tabla o mecánica de cálculo. No es posible extraer una tarifa sin contenido tarifario.
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
  > El texto proporcionado sólo contiene el encabezado del capítulo "Del Impuesto Predial" y no incluye artículos, tablas, tarifas ni mecánica de cálculo. No es posible extraer una estructura tarifaria sin inventarla.
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

### `guanajuato/abasolo/2025` (cvegeo 11001)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_abasolo.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_abasolo.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el apartado tarifario del Impuesto Predial ni tablas, cuotas o tasas aplicables. Sólo aparecen encabezados y páginas en blanco/omitidas entre las páginas 3 y 20, sin mecánica de cálculo extraíble.
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

### `guanajuato/acambaro/2024` (cvegeo 11002)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2024_acambaro.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2024_acambaro.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria del impuesto predial ni tablas de cálculo; sólo aparecen páginas del índice y páginas en blanco/encabezados sin mecánica extraíble. No hay rangos, tasas, cuotas ni artículo tarifario visible para transcribir la mecánica.
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

### `guanajuato/apaseo_el_grande/2025` (cvegeo 11005)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_apaseo_el_grande.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_apaseo_el_grande.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria del impuesto predial ni tablas o artículos con la mecánica de cálculo; sólo aparecen encabezados y páginas en blanco/omitidas dentro del rango señalado. No es posible extraer una tarifa sin inventarla.
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

### `guanajuato/comonfort/2025` (cvegeo 11009)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_comonfort.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_comonfort.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el artículo o tabla del Impuesto Predial; sólo aparecen encabezados y páginas en blanco/omisiones entre las páginas 3-20. No hay mecánica tarifaria extraíble para clasificar en alguna de las variantes.
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

### `guanajuato/cortazar/2025` (cvegeo 11011)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_cortazar.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_cortazar.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no incluye el contenido tarifario del Impuesto Predial; sólo aparecen encabezados, paginación y el inicio del documento sin la sección con tablas o mecánica de cálculo. No es posible extraer una estructura de predial a partir de este segmento.
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

### `guanajuato/cortazar/2026` (cvegeo 11011)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_cortazar.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_cortazar.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado para la sección de impuesto predial no contiene la mecánica tarifaria; las páginas mostradas están vacías o sólo incluyen encabezados y no aparece tabla, cuota, tasa ni artículo aplicable del predial. No es posible extraer un esquema de cálculo sin inventar información.
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

### `guanajuato/cueramaro/2025` (cvegeo 11012)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_cueramaro.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_cueramaro.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni tablas del apartado de Impuesto Predial; sólo aparecen encabezados de páginas y metadatos del documento. No es posible extraer una mecánica de cálculo sin contenido tarifario.
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

### `guanajuato/dolores_hidalgo_cuna_de_la_independencia_nacional/2025` (cvegeo 11014)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_dolores_hidalgo_cuna_de_la_independencia_nacional.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_dolores_hidalgo_cuna_de_la_independencia_nacional.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado para la sección de impuesto predial no contiene la mecánica tarifaria ni tablas de cálculo; únicamente aparece el encabezado presupuestal con el monto estimado del impuesto predial y páginas en blanco/sin contenido legible de la sección. No es posible extraer una tarifa, cuota o esquema de cálculo sin inventarlo.
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

### `guanajuato/irapuato/2026` (cvegeo 11017)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_irapuato.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_irapuato.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni la tabla del Impuesto Predial; sólo aparecen portadas, encabezados y páginas en blanco/omisas para las páginas señaladas. No es posible extraer la mecánica de cálculo porque el segmento tarifario no está presente en el material recibido.
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

### `guanajuato/jaral_del_progreso/2024` (cvegeo 11018)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2024_jaral_del_progreso.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2024_jaral_del_progreso.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El fragmento proporcionado no contiene la sección tarifaria del impuesto predial; sólo aparece el encabezado del municipio, la estimación de ingresos y páginas en blanco/omitidas para las páginas 4 a 20. No hay tabla, cuotas, tasas ni brackets extraíbles para estructurar la mecánica de cálculo.
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

### `guanajuato/jerecuaro/2023` (cvegeo 11019)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2023_jerecuaro.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2023_jerecuaro.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni tabla del Impuesto Predial; sólo aparecen portadas y páginas en blanco/encabezados de la ley. No es posible extraer mecánica de cálculo porque el segmento tarifario no viene incluido en el texto recibido.
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

### `guanajuato/purisima_del_rincon/2026` (cvegeo 11025)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_purisima_del_rincon.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_purisima_del_rincon.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado para la sección de impuesto predial no contiene la mecánica tarifaria ni tablas de cálculo; únicamente aparecen encabezados de páginas y datos editoriales del periódico oficial. No es posible extraer una estructura de predial sin contenido tarifario.
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

### `guanajuato/salamanca/2024` (cvegeo 11027)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2024_salamanca.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2024_salamanca.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado para la sección de Impuesto Predial no contiene tablas ni artículos tarifarios del predial; sólo aparecen páginas de portada/índice y encabezados de la ley, sin mecánica de cálculo extraíble. No es posible identificar tarifa, cuotas, rangos o tasas del impuesto predial en este fragmento.
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

### `guanajuato/salvatierra/2024` (cvegeo 11028)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2024_salvatierra.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2024_salvatierra.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado sólo contiene el encabezado de la Ley de Ingresos y la estimación global del impuesto predial, pero no incluye tablas, tarifas ni mecánica de cálculo del predial en las páginas mostradas. No es posible extraer la estructura tarifaria sin inventarla.
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

### `guanajuato/salvatierra/2026` (cvegeo 11028)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_salvatierra.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_salvatierra.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado sólo muestra el encabezado de la Ley de Ingresos y el monto estimado del impuesto predial, pero no incluye la sección tarifaria ni tablas o artículos con la mecánica de cálculo del predial. No hay datos extraíbles de cuotas, tasas o rangos.
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
  > El texto proporcionado no incluye contenido tarifario del Impuesto Predial; las páginas mostradas sólo contienen portada, encabezados y numeración, sin tablas, cuotas, tasas, rangos o artículos con mecánica de cálculo. No es posible extraer la mecánica sin inventarla.
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

### `guanajuato/san_diego_de_la_union/2025` (cvegeo 11029)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_san_diego_de_la_union.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_san_diego_de_la_union.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el artículo ni la tabla del Impuesto Predial; sólo aparecen encabezados generales y páginas en blanco/omisas entre las páginas 3 y 20. No es posible extraer mecánica de cálculo sin el contenido tarifario.
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

### `guanajuato/san_felipe/2025` (cvegeo 11030)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_san_felipe.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_san_felipe.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni tablas del apartado 'Del Impuesto Predial'; sólo aparece el encabezado general del decreto y páginas en blanco o sin contenido tarifario extraíble para predial. No es posible transcribir una mecánica de cálculo sin inventarla.
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
  > El texto proporcionado no contiene mecánica de cálculo del impuesto predial; sólo aparecen encabezados de fecha, página y periódico oficial. No hay tabla, cuotas, tasas ni rangos extraíbles para clasificar en otra variante.
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

### `guanajuato/san_luis_de_la_paz/2026` (cvegeo 11033)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_san_luis_de_la_paz.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_san_luis_de_la_paz.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria del impuesto predial ni una tabla o mecánica de cálculo extraíble. Sólo aparecen encabezados generales y páginas en blanco/omisas respecto al predial.
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

### `guanajuato/santa_catarina/2026` (cvegeo 11034)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_santa_catarina.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_santa_catarina.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado para la sección de Impuesto Predial no contiene la mecánica de cálculo ni tablas tarifarias; únicamente aparece el encabezado del impuesto en el cuadro de ingresos estimados y luego páginas vacías respecto al predial. No es posible extraer una tarifa sin inventarla.
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

### `guanajuato/santiago_maravatio/2025` (cvegeo 11036)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_santiago_maravatio.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_santiago_maravatio.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el apartado tarifario del Impuesto Predial ni tablas o artículos con la mecánica de cálculo; sólo aparecen encabezados y numeración de páginas. No es posible extraer una tasa, cuota o esquema de cobro sin inventar información.
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

### `guanajuato/uriangato/2020` (cvegeo 11041)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2020_uriangato.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2020_uriangato.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni una tabla tarifaria de la sección del Impuesto Predial; sólo aparecen páginas de encabezado y sumario con el monto estimado del impuesto predial, sin mecánica de cálculo extraíble. No es posible transcribir tasas, brackets o cuotas sin inventar contenido.
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

### `guanajuato/victoria/2021` (cvegeo 11043)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2021_victoria.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2021_victoria.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado incluye únicamente encabezados y páginas en blanco/omisas para la sección de predial; no aparece tabla, artículo ni mecánica de cálculo del impuesto predial en el segmento recibido. No es posible extraer la estructura tarifaria sin inventarla.
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
  > El texto proporcionado no contiene la sección tarifaria del impuesto predial ni tablas de cuotas o tasas; sólo aparecen encabezados, metadatos del documento y numeración de páginas. No es posible extraer la mecánica de cálculo sin contenido tarifario.
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

### `yucatan/progreso/2010` (cvegeo 31059)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2010_progreso.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2010_progreso.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El segmento proporcionado está truncado y sólo contiene el encabezado del Capítulo I y la definición general de impuestos; no aparece la mecánica de cálculo del impuesto predial ni tabla, rangos, tasas o cuotas aplicables. Con este contenido no es posible extraer una tarifa predial estructurada sin inventar información.
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

### `yucatan/progreso/2011` (cvegeo 31059)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2011_progreso.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2011_progreso.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El fragmento proporcionado sólo contiene el encabezado del Capítulo I y el inicio del artículo 13, pero no incluye la mecánica tarifaria del impuesto predial ni tablas, cuotas o tasas. No es posible extraer una estructura de cálculo a partir de este segmento truncado.
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

## Grupo G-02: `estructura_no_estandar` / `solo_valores_unitarios` (8 casos)

### `guanajuato/celaya/2018` (cvegeo 11007)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2018_celaya.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2018_celaya.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto proporcionado no contiene una mecánica tarifaria de cobro del impuesto predial extraíble como tabla de tasas, cuotas fijas o brackets. Lo visible corresponde principalmente a tablas de valores unitarios de terreno y construcción, factores agrológicos y criterios de valuación para avalúos, que son insumos catastrales y no la tarifa del impuesto. La única referencia al impuesto predial en el artículo 4 aparece truncada e incompleta, sin permitir reconstruir la tasa o cuota aplicable.
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

### `guanajuato/uriangato/2018` (cvegeo 11041)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2018_uriangato.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2018_uriangato.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El segmento proporcionado no contiene la mecánica de liquidación del impuesto predial en forma extraíble. El texto visible corresponde principalmente a tablas y factores para valuación catastral (valores unitarios de terreno y construcción, factores de forma, superficie, fondo, topografía y pavimento), pero no muestra una tabla tarifaria aplicable del predial ni una cuota fija/tasa sobre base de cálculo que pueda transcribirse sin inferencia. Por ello no encaja de manera segura en tarifa_millar, progresivo, tasa_unica, cuota_fija_simple, cuota_fija_escalonada o mixto.
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

### `guanajuato/uriangato/2026` (cvegeo 11041)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_uriangato.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_uriangato.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto proporcionado corresponde a la sección de valuación catastral y tablas de valores unitarios de terreno y construcción (Artículos 5 y 6), no a una mecánica de tasa/cuota del impuesto predial extraíble en alguna de las variantes tipificadas. No se observa una tabla tarifaria del predial con brackets, cuotas, tasas al millar o cuota fija anual; por tanto no es posible estructurar la mecánica de cálculo sin inventar.
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

### `yucatan/tepakan/2025` (cvegeo 31086)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2025_tepakan.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2025_tepakan.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto no presenta una tarifa del impuesto predial clasificable en una de las variantes permitidas. En el Artículo 12 sólo se indica una cuota fija de $10.00 más el resultado de un factor sobre el valor catastral, junto con un procedimiento de valuación del inmueble y tablas de valores unitarios de terreno y construcción; esas tablas son de catastro/valuación, no una tabla tarifaria de predial. No hay brackets, tasa uniforme explícita, ni catálogo de tasas por categoría que permita estructurar la mecánica como tarifa_millar, progresivo, cuota fija escalonada o mixto.
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

### `yucatan/xocchel/2025` (cvegeo 31103)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2025_xocchel.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2025_xocchel.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto no contiene una tabla del impuesto predial sobre valor catastral con brackets aplicables; la sección mostrada corresponde principalmente a valores unitarios de terreno y construcción (catastro), que deben ignorarse. Lo único tarifario detectable es el Art. 5 sobre rentas o frutos civiles, con tasas mensuales de 2% y 5% por tipo de predio, pero eso no es la mecánica estándar de predial sobre valor catastral solicitada por el esquema.
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

### `yucatan/yaxkukul/2023` (cvegeo 31105)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2023_yaxkukul.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2023_yaxkukul.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto no presenta una tarifa predial directamente calculable como tabla de cobro del impuesto principal. El Artículo 13 contiene valores unitarios de terreno y construcción para integrar el valor catastral; el Artículo 14 establece una tasa al millar para predios agropecuarios y una tabla de rentas/frutos civiles, pero la mecánica principal del predial base valor catastral no queda estructurada en rangos o cuotas extraíbles sin una norma complementaria de cálculo. Por ello no encaja limpiamente en las variantes tarifarias previstas.
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

## Grupo G-03: `municipio_sin_impuesto` / `otro_patron` (8 casos)

### `guanajuato/acambaro/2025` (cvegeo 11002)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_acambaro.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_acambaro.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > En el texto proporcionado no aparece una sección tarifaria del Impuesto Predial con mecánica de cálculo. Sólo se observa el listado de ingresos estimados donde se menciona el rubro 1201 Impuesto predial, pero no se incluyen tablas, rangos, tasas o cuotas para su determinación dentro del segmento enviado.
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

### `guanajuato/tierra_blanca/2025` (cvegeo 11040)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_tierra_blanca.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_tierra_blanca.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > En el texto proporcionado no aparece la mecánica tarifaria del impuesto predial (tabla, cuotas, tasas o brackets). El segmento visible sólo contiene un recurso de revisión para inmuebles sin edificar que permite aplicar la tasa general de inmuebles urbanos y suburbanos, pero no transcribe esa tasa ni la base de cálculo del predial. Por ello no es posible extraer una mecánica estructural del impuesto predial desde este fragmento.
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
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > En el texto proporcionado sólo aparece la previsión recaudatoria del rubro 'Impuesto predial' en el clasificador de ingresos, pero no se incluye ningún artículo, tabla o mecánica de cálculo del impuesto. No hay rangos, tasas, cuotas ni reglas aplicables extraíbles dentro del segmento enviado.
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

### `yucatan/conkal/2022` (cvegeo 31013)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2022_conkal.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2022_conkal.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El segmento no contiene una mecánica de cálculo del impuesto predial. Solo aparece el pronóstico de ingresos del Artículo 5 con el renglón 'Impuesto predial' como monto presupuestal, y la propia nota del segmentador indica que la ley no incluye tarifas, tasas, montos al millar ni rangos para predial. Se remite a la Ley General de Hacienda Municipal del Estado de Yucatán, por lo que no es posible extraer una tabla tarifaria municipal desde este texto.
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
  > El segmento sólo contiene el pronóstico presupuestal del concepto "Impuesto predial" dentro del artículo de ingresos, pero no incluye tarifas, tasas, rangos, cuotas ni mecánica de cálculo. La propia nota del segmentador indica que las contribuciones se rigen por la Ley General de Hacienda Municipal del Estado de Yucatán, por lo que no hay estructura tarifaria municipal extraíble en este texto.
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
  > El segmento proporcionado solo contiene el pronóstico de ingresos para 'Impuesto predial' dentro del artículo de clasificación de impuestos, pero no incluye tarifas, tasas, rangos, cuota fija ni mecánica de cálculo. Además, la nota del segmentador indica expresamente que las contribuciones se rigen por la Ley General de Hacienda Municipal del Estado de Yucatán y que no hay sección tarifaria en esta ley de ingresos corta.
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

### `yucatan/conkal/2025` (cvegeo 31013)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2025_conkal.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2025_conkal.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El segmento sólo muestra el pronóstico presupuestal del concepto 'Impuesto predial' dentro del Artículo 5, pero no contiene tarifas, tasas, rangos, cuotas ni mecánica de cálculo. El propio texto indica que las contribuciones se rigen por la Ley General de Hacienda Municipal del Estado de Yucatán, por lo que no es posible extraer una estructura tarifaria del segmento proporcionado.
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
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El segmento sólo muestra el pronóstico de ingresos para "Impuesto predial" en el artículo de clasificación de ingresos, con un monto estimado de $80,456.00, pero no contiene reglas, tasas, rangos, cuotas o bases de cálculo. La propia nota del segmentador indica que las contribuciones se rigen por la Ley General de Hacienda Municipal del Estado de Yucatán y no por una mecánica tarifaria en esta ley de ingresos.
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

## Grupo G-04: `segmento_vacio` / `articulado_ausente` (6 casos)

### `guanajuato/apaseo_el_alto/2025` (cvegeo 11004)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_apaseo_el_alto.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_apaseo_el_alto.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `articulado_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni una tabla tarifaria visible del Impuesto Predial para Apaseo el Alto; sólo aparecen páginas de índice/ingresos estimados y no la mecánica de cálculo. No es posible extraer una tarifa sin inventarla.
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

### `guanajuato/comonfort/2023` (cvegeo 11009)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2023_comonfort.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2023_comonfort.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `articulado_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni tabla tarifaria del Impuesto Predial del municipio. Solo aparecen páginas con estimaciones de ingreso y no se incluye la mecánica de cálculo, por lo que no es posible extraer una estructura tarifaria.
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

### `guanajuato/dolores_hidalgo_cuna_de_la_independencia_nacional/2026` (cvegeo 11014)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_dolores_hidalgo_cuna_de_la_independencia_nacional.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_dolores_hidalgo_cuna_de_la_independencia_nacional.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `articulado_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni tablas del Impuesto Predial; sólo aparecen páginas de portada/índice y saltos de página dentro del rango 129-146, sin mecánica tarifaria extraíble. No es posible identificar cuotas, tasas o brackets del predial a partir del fragmento.
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

### `guanajuato/guanajuato/2026` (cvegeo 11015)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_guanajuato.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_guanajuato.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `articulado_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni una tabla tarifaria del Impuesto Predial; sólo aparecen páginas de portada/índice y saltos de página sin mecánica de cálculo extraíble. No es posible identificar tasas, cuotas, rangos o categorías del predial con este fragmento.
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

### `guanajuato/purisima_del_rincon/2024` (cvegeo 11025)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2024_purisima_del_rincon.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2024_purisima_del_rincon.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `articulado_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni tablas del apartado de impuesto predial; solo aparecen páginas iniciales del periódico y una referencia general al capítulo de ingresos. No hay mecánica tarifaria extraíble sobre valor catastral, superficies, cuotas o rangos.
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

### `guanajuato/santa_cruz_de_juventino_rosas/2026` (cvegeo 11035)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_santa_cruz_de_juventino_rosas.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_santa_cruz_de_juventino_rosas.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `articulado_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni tablas de cálculo del Impuesto Predial; las páginas indicadas aparecen vacías o sin contenido tarifario legible sobre predial. No es posible extraer una mecánica de cálculo sin inventar información.
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

## Grupo G-05: `estructura_no_estandar` / `dos_tarifas_paralelas` (4 casos)

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

### `yucatan/kinchil/2024` (cvegeo 31044)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2024_kinchil.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2024_kinchil.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El texto transcrito no contiene una tarifa del impuesto predial en alguna de las siete variantes, sino una tabla de valores catastrales/unitarios de suelo y construcción para determinar la base gravable. Solo aparece de forma tarifaria una disposición paralela para predios destinados a la producción agropecuaria de 10 al millar anual sobre el valor registrado o catastral, pero no se presenta la mecánica principal del impuesto en forma extraíble.
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

### `yucatan/yaxkukul/2022` (cvegeo 31105)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2022_yaxkukul.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2022_yaxkukul.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El texto no contiene una tarifa estructural del impuesto predial sobre valor catastral por rangos o categorías inmobiliarias, sino tablas de valores unitarios catastrales ($ por sección, metro lineal y $ por m2) para calcular el valor catastral. Además, sólo establece de forma paralela una tasa de 10 al millar anual para predios destinados a la producción agropecuaria y un impuesto sobre rentas o frutos civiles mensuales del 5%, sin una mecánica principal extraíble de predial general para inmuebles urbanos.
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

## Grupo G-06: `error_segmentacion` / `solo_valores_unitarios` (3 casos)

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

## Grupo G-07: `segmento_vacio` / `mecanica_ausente` (3 casos)

### `coahuila/nava/2010` (cvegeo 05022)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_nava.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_nava.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `mecanica_ausente`
- **descripcion_estructural**:
  > El texto proporcionado del apartado "Del Impuesto Predial" no contiene la mecánica de cálculo del predial; sólo aparecen incentivos, condiciones de aplicación y después inicia el capítulo de otro impuesto. No hay tabla, cuota fija, tasa, rangos ni categorías del impuesto predial extraíbles en el fragmento.
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

### `guanajuato/purisima_del_rincon/2021` (cvegeo 11025)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2021_purisima_del_rincon.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2021_purisima_del_rincon.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `mecanica_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la mecánica del impuesto predial. Sólo aparecen disposiciones de ajuste de cantidades, avisos del Periódico Oficial y tarifas editoriales, sin tabla ni regla de cálculo del predial.
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

### `tamaulipas/nuevo_laredo/2013` (cvegeo 28027)

- **JSON**: [`predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2013_nuevo_laredo.json`](predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2013_nuevo_laredo.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `mecanica_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la mecánica de cálculo del impuesto predial. Solo aparecen rubros presupuestales de recaudación/ingresos ('Impuesto sobre la propiedad urbana, suburbana y rústica', 'Impuesto sobre la propiedad urbana', 'Impuesto sobre la propiedad rústica') con montos agregados, pero no tablas, cuotas, tasas ni rangos aplicables al cálculo.
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

## Grupo G-08: `estructura_no_estandar` / `otro_patron` (2 casos)

### `tamaulipas/nuevo_laredo/2024` (cvegeo 28027)

- **JSON**: [`predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2024_nuevo_laredo.json`](predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2024_nuevo_laredo.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto proporcionado sólo establece que el impuesto se causa sobre el valor catastral de los bienes raíces y remite a las fracciones del artículo 10, pero en el segmento enviado no aparecen las tarifas o tablas de cálculo aplicables. Las fracciones visibles contienen exclusiones y aumentos por incumplimiento, no la mecánica tarifaria principal extraíble.
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

### `tamaulipas/san_fernando/2023` (cvegeo 28035)

- **JSON**: [`predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2023_san_fernando.json`](predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2023_san_fernando.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto no presenta una tabla tarifaria extraíble de impuesto predial con rangos o categorías de tasa. Sólo indica que la base es el valor catastral y remite a una tasa señalada en el artículo, pero en el fragmento proporcionado no aparece dicha tasa. Sí aparecen reglas de incremento para predios urbanos no edificados y con edificación inferior a la quinta parte del terreno, además de mínimos en UMA, pero no la mecánica completa de cálculo.
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

## Grupo G-09: `municipio_sin_impuesto` / `solo_valores_unitarios` (2 casos)

### `guanajuato/tierra_blanca/2018` (cvegeo 11040)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2018_tierra_blanca.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2018_tierra_blanca.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto proporcionado contiene únicamente tablas de valores unitarios de terreno y construcción para la valuación catastral (urbanos, suburbanos y rústicos), así como criterios de avalúo. No aparece una mecánica de cálculo del impuesto predial con tasas, cuotas, brackets o tarifa aplicable para determinar el impuesto.
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

### `guanajuato/valle_de_santiago/2021` (cvegeo 11042)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2021_valle_de_santiago.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2021_valle_de_santiago.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto proporcionado incluye valores unitarios de terreno y construcción para avalúo catastral, pero no aparece la mecánica tarifaria del impuesto predial (tabla de cuotas, tasas al millar, progresividad o cuota fija) dentro del segmento entregado. Por ello no es posible extraer la liquidación del predial sin inventar reglas no visibles.
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

## Grupo G-10: `segmento_vacio` / `otro_patron` (2 casos)

### `guanajuato/cortazar/2023` (cvegeo 11011)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2023_cortazar.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2023_cortazar.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto proporcionado incluye únicamente la portada y páginas en blanco o sin contenido tarifario visible para la sección de impuesto predial. No se observa tabla, cuotas, tasas ni mecánica de cálculo extraíble en el segmento enviado.
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

### `guanajuato/moroleon/2026` (cvegeo 11021)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_moroleon.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_moroleon.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El insumo proporcionado no contiene el texto tarifario de la sección de impuesto predial; sólo aparecen páginas iniciales y numeración, sin tablas, rangos, tasas ni cuotas aplicables. No es posible extraer la mecánica de cálculo a partir de este segmento.
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

## Grupo G-11: `segmento_vacio` / `seccion_ausente` (2 casos)

### `guanajuato/celaya/2024` (cvegeo 11007)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2024_celaya.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2024_celaya.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria del impuesto predial de Celaya, Guanajuato, para 2024. Solo aparecen páginas de índices y montos globales de ingresos, sin tablas, brackets ni tasas del predial extraíbles.
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

### `guanajuato/salamanca/2025` (cvegeo 11027)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_salamanca.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_salamanca.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > En el texto proporcionado no aparece la sección tarifaria del impuesto predial ni artículos con mecánica de cálculo; sólo se observa el clasificador de ingresos con el monto estimado de la recaudación por impuesto predial. No hay tabla, rangos, tasas ni cuota fija extraíbles para transcribir la mecánica.
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

## Grupo G-12: `estructura_no_estandar` / `mecanica_ausente` (1 casos)

### `coahuila/progreso/2010` (cvegeo 05026)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_progreso.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_progreso.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `mecanica_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la mecánica tarifaria del impuesto predial. Sólo aparecen incentivos/bonificaciones para ciertos contribuyentes (pensionados, instituciones, empresas) y luego inicia el capítulo de otro impuesto (adquisición de inmuebles). No hay tabla, tasa, cuota o rangos aplicables al predial extraíbles en este fragmento.
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

## Grupo G-13: `estructura_no_estandar` / `ocr_ilegible` (1 casos)

### `guanajuato/yuriria/2025` (cvegeo 11046)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_yuriria.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_yuriria.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `ocr_ilegible`
- **descripcion_estructural**:
  > El texto sí contiene tasas del impuesto predial, pero la mecánica principal no es una sola tabla homogénea: para inmuebles urbanos y suburbanos hay una tabla por antigüedad/estado de edificación con tres columnas ('con edificaciones', 'sin edificaciones' y una columna de tasa con texto deteriorado/OCR), y para inmuebles rústicos aparece además una base de valores por hectárea y por m² con factores agrológicos. El fragmento OCR está seriamente corrompido en los renglones de tasas, por lo que no es posible transcribir con seguridad una estructura tarifaria consistente sin inventar datos.
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

## Grupo G-14: `municipio_sin_impuesto` / `dos_tarifas_paralelas` (1 casos)

### `yucatan/kinchil/2021` (cvegeo 31044)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2021_kinchil.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2021_kinchil.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El texto del capítulo de predial no contiene una tarifa del impuesto predial extraíble; únicamente remite a la Ley de Hacienda del Municipio de Kinchil, Yucatán, para el pago del impuesto, y luego inserta tablas de valores catastrales/unitarios de suelo y construcción. La única tasa expresa observada es una tarifa paralela para predios destinados a la producción agropecuaria de 10 al millar anual sobre el valor registrado o catastral, pero no se proporciona la mecánica principal del impuesto predial para los demás predios.
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

## Grupo G-15: `municipio_sin_impuesto` / `mecanica_ausente` (1 casos)

### `coahuila/nadadores/2010` (cvegeo 05021)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_nadadores.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_nadadores.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `mecanica_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la mecánica del Impuesto Predial. El contenido visible corresponde al Impuesto sobre Adquisición de Inmuebles y a reglas de diferimiento/pago de ese impuesto, no a una tabla o tarifa de predial.
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

## Grupo G-16: `segmento_vacio` / `ocr_ilegible` (1 casos)

### `guanajuato/irapuato/2025` (cvegeo 11017)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_irapuato.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_irapuato.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `ocr_ilegible`
- **descripcion_estructural**:
  > El texto proporcionado no incluye el contenido tarifario del Impuesto Predial; sólo aparecen páginas de portada/índice y páginas en blanco o sin OCR útil entre las páginas 3 a 20. No es posible extraer una mecánica de cálculo sin una tabla o artículo visible.
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

## Grupo G-17: `segmento_vacio` / `texto_truncado` (1 casos)

### `coahuila/muzquiz/2010` (cvegeo 05020)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_muzquiz.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_muzquiz.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `texto_truncado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la mecánica de cálculo del impuesto predial; sólo aparecen disposiciones sobre diferimiento del pago y una referencia incompleta a adquisiciones de inmuebles. No hay tabla, cuota, tasa ni brackets extraíbles para estructurar el predial.
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


## Casos `requiere_revision` excluyendo `otro_no_clasificado` (5 casos)

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

### `yucatan/chemax/2024` (cvegeo 31019)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2024_chemax.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2024_chemax.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.progresivo: Value error, brackets 5→6: hueco detectado (superior=15000.0, siguiente inferior=15500.01) | mini_e2=  • predial.mixto: Value error, brackets 5→6: hueco detectado (superior=15000.0, siguie`
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

### `yucatan/kinchil/2012` (cvegeo 31044)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2012_kinchil.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2012_kinchil.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente inferior=70000.01) | mini_e2=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente i`
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

### `yucatan/kinchil/2013` (cvegeo 31044)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2013_kinchil.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2013_kinchil.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente inferior=70000.0) | mini_e2=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente in`
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

### `yucatan/kinchil/2015` (cvegeo 31044)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2015_kinchil.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2015_kinchil.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente inferior=70000.01) | mini_e2=  • predial.mixto: Value error, brackets 6→7: hueco detectado (superior=60000.0, siguiente i`
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
