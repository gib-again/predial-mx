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

- [Grupo G-01: `segmento_vacio` / `solo_encabezado` (37 casos)](#grupo-g-01-segmento-vacio-solo-encabezado)
- [Grupo G-02: `estructura_no_estandar` / `dos_tarifas_paralelas` (12 casos)](#grupo-g-02-estructura-no-estandar-dos-tarifas-paralelas)
- [Grupo G-03: `segmento_vacio` / `seccion_ausente` (12 casos)](#grupo-g-03-segmento-vacio-seccion-ausente)
- [Grupo G-04: `municipio_sin_impuesto` / `otro_patron` (7 casos)](#grupo-g-04-municipio-sin-impuesto-otro-patron)
- [Grupo G-05: `estructura_no_estandar` / `otro_patron` (6 casos)](#grupo-g-05-estructura-no-estandar-otro-patron)
- [Grupo G-06: `estructura_no_estandar` / `solo_valores_unitarios` (6 casos)](#grupo-g-06-estructura-no-estandar-solo-valores-unitarios)
- [Grupo G-07: `error_segmentacion` / `solo_valores_unitarios` (4 casos)](#grupo-g-07-error-segmentacion-solo-valores-unitarios)
- [Grupo G-08: `segmento_vacio` / `articulado_ausente` (3 casos)](#grupo-g-08-segmento-vacio-articulado-ausente)
- [Grupo G-09: `segmento_vacio` / `mecanica_ausente` (3 casos)](#grupo-g-09-segmento-vacio-mecanica-ausente)
- [Grupo G-10: `estructura_no_estandar` / `factor_sin_tabla` (2 casos)](#grupo-g-10-estructura-no-estandar-factor-sin-tabla)
- [Grupo G-11: `municipio_sin_impuesto` / `solo_valores_unitarios` (2 casos)](#grupo-g-11-municipio-sin-impuesto-solo-valores-unitarios)
- [Grupo G-12: `segmento_vacio` / `otro_patron` (2 casos)](#grupo-g-12-segmento-vacio-otro-patron)
- [Grupo G-13: `error_segmentacion` / `dos_tarifas_paralelas` (1 casos)](#grupo-g-13-error-segmentacion-dos-tarifas-paralelas)
- [Grupo G-14: `error_segmentacion` / `otro_patron` (1 casos)](#grupo-g-14-error-segmentacion-otro-patron)
- [Grupo G-15: `estructura_no_estandar` / `ejidal_comunal` (1 casos)](#grupo-g-15-estructura-no-estandar-ejidal-comunal)
- [Grupo G-16: `municipio_sin_impuesto` / `ejidal_comunal` (1 casos)](#grupo-g-16-municipio-sin-impuesto-ejidal-comunal)
- [Grupo G-17: `municipio_sin_impuesto` / `mecanica_ausente` (1 casos)](#grupo-g-17-municipio-sin-impuesto-mecanica-ausente)
- [Grupo G-18: `segmento_vacio` / `contenido_ausente` (1 casos)](#grupo-g-18-segmento-vacio-contenido-ausente)
- [Grupo G-19: `segmento_vacio` / `solo_valores_unitarios` (1 casos)](#grupo-g-19-segmento-vacio-solo-valores-unitarios)
- [Grupo G-20: `segmento_vacio` / `texto_truncado` (1 casos)](#grupo-g-20-segmento-vacio-texto-truncado)
- [Casos `requiere_revision` (21 casos)](#casos-requiere_revision-excluyendo-otro_no_clasificado)

> ℹ️ Se excluyeron **122 JSONs sintéticos** (`_meta.modelo == 'synthesized_short_form'`) que no requieren HITL.

## Casos `otro_no_clasificado` (104 casos en 20 grupos)

## Grupo G-01: `segmento_vacio` / `solo_encabezado` (37 casos)

### `coahuila/ocampo/2010` (cvegeo 05023)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_ocampo.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_ocampo.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El segmento proporcionado sólo contiene el encabezado del capítulo 'DEL IMPUESTO PREDIAL' y no incluye ningún artículo, tabla, cuota, tasa, rango o mecánica de cálculo. No es posible clasificar la estructura tarifaria con el texto disponible.
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
  > El segmento proporcionado sólo contiene encabezados del título, capítulo y sección del Impuesto Predial, pero no incluye ninguna tabla, tasa, rango o cuota de cálculo. No es posible identificar la mecánica del impuesto con el texto disponible.
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
  > El segmento proporcionado sólo contiene encabezados del título, capítulo y sección del Impuesto Predial, sin texto tarifario, tablas, rangos, tasas ni cuotas aplicables. No es posible identificar la mecánica de cálculo con la información disponible.
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
  > El texto proporcionado no contiene el apartado tarifario del Impuesto Predial; sólo aparecen encabezados, páginas preliminares y páginas en blanco/omisas sin tablas, rangos, tasas ni cuotas aplicables. No es posible transcribir la mecánica de cálculo porque el segmento predial llegó vacío.
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

### `guanajuato/atarjea/2025` (cvegeo 11006)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_atarjea.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_atarjea.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El segmento proporcionado no contiene el texto del artículo o tabla del Impuesto Predial; sólo aparecen encabezados, metadatos y numeración de páginas. No es posible identificar una mecánica de cálculo sin inventar contenido.
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

### `guanajuato/atarjea/2026` (cvegeo 11006)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_atarjea.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_atarjea.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria del impuesto predial ni tablas, cuotas, tasas o brackets de cálculo. Solo aparece el encabezado del decreto y un resumen general de ingresos, sin mecánica del predial detectable.
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
  > El texto proporcionado no contiene el articulado ni la tabla de mecánica del Impuesto Predial; sólo aparecen encabezados, metadatos y referencias a páginas. No es posible identificar brackets, tasas o cuotas sin inventar información.
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
  > El texto proporcionado no contiene el articulado ni tablas del Impuesto Predial de Cortazar; sólo aparecen portadas, encabezados y páginas en blanco o sin contenido tarifario visible entre las páginas indicadas. No es posible extraer la mecánica de cálculo sin inventar información.
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
  > El texto proporcionado no contiene el segmento tarifario del Impuesto Predial; sólo aparecen páginas de encabezado y numeración, sin artículo, tabla, rangos, tasas o cuotas del predial. No es posible identificar una mecánica de cálculo a partir del extracto.
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
  > El texto proporcionado para la sección de impuesto predial no contiene tablas, tarifas, rangos, tasas ni cuotas del predial; sólo aparecen páginas en blanco o encabezados generales de la ley. No es posible extraer la mecánica de cálculo sin una estructura tarifaria visible.
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

### `guanajuato/cueramaro/2026` (cvegeo 11012)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_cueramaro.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_cueramaro.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria del Impuesto Predial; sólo aparecen portadas y páginas iniciales con el encabezado de la ley, pero no se observan tablas, cuotas ni tasas aplicables al predial. No hay mecánica de cálculo extraíble en el segmento compartido.
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
  > El fragmento proporcionado no contiene el articulado ni tablas del Impuesto Predial; únicamente aparecen páginas en blanco/encabezados y la referencia al capítulo, sin mecánica de cálculo visible. No es posible identificar rangos, tasas o cuotas para clasificar en alguna de las variantes tarifarias.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección del Impuesto Predial ni tabla tarifaria legible; sólo aparece el encabezado general de la ley y páginas en blanco o sin contenido tarifario extraído. No es posible identificar una mecánica de cálculo verificable para predial sin inventar datos.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no incluye el contenido de la sección del Impuesto Predial; sólo aparecen portada, encabezados y páginas en blanco o sin transcripción tarifaria. No es posible identificar tabla, tasas, rangos o cuotas para clasificar en alguna de las variantes de predial.
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

### `guanajuato/huanimaro/2015` (cvegeo 11016)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2015_huanimaro.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2015_huanimaro.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección normativa del impuesto predial ni tablas o artículos con mecánica de cálculo. Sólo aparecen portadas, encabezados y páginas en blanco/irrelevantes para predial, por lo que no es posible extraer una tarifa o esquema de cálculo.
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

### `guanajuato/huanimaro/2026` (cvegeo 11016)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_huanimaro.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_huanimaro.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria del Impuesto Predial; sólo aparecen encabezados generales y páginas en blanco/omisas entre las páginas 131-148. No hay tabla, tasas, rangos ni cuotas que permitan clasificar la mecánica de cálculo.
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
  > El texto proporcionado no contiene la sección normativa del Impuesto Predial ni una tabla o mecánica de cálculo; sólo aparecen encabezados, páginas del periódico oficial y rubros generales de ingresos. No hay filas, rangos, tasas ni cuotas prediales extraíbles sin inventar información.
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
  > El texto proporcionado no contiene la mecánica del impuesto predial; sólo aparece el encabezado del municipio, el monto estimado de ingreso por concepto de impuesto predial y páginas en blanco o sin contenido tarifario visible. No hay tablas, cuotas, tasas ni brackets para transcribir.
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
  > El texto proporcionado incluye el encabezado y páginas del periódico oficial, pero no contiene el articulado ni tabla del Impuesto Predial de Jerécuaro dentro del segmento visible. No hay mecánica de cálculo verificable para transcribir sin inventar contenido.
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

### `guanajuato/leon/2020` (cvegeo 11020)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2020_leon.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2020_leon.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado para la sección de predial no contiene la mecánica de cálculo del impuesto: las páginas indicadas aparecen vacías de tablas tarifarias y sólo se observan encabezados, definiciones y páginas en blanco dentro del segmento extraído. No es posible identificar una tarifa, brackets, cuotas o tasas aplicables sin inventar información.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el apartado tarifario del Impuesto Predial; sólo aparecen encabezados generales y páginas en blanco/omitidas entre las páginas 3-20. No es posible identificar una mecánica de cálculo, tablas de cuotas ni tasas aplicables.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no incluye la sección sustantiva del Impuesto Predial ni una tabla o artículo con la mecánica de cálculo. Sólo aparecen encabezados generales, páginas en blanco y una referencia al capítulo, sin contenido tarifario recuperable.
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
  > El texto proporcionado no contiene el articulado ni tablas de la sección 'Del Impuesto Predial'; sólo aparecen portadas, encabezados y páginas en blanco/omisas del periódico oficial. No hay mecánica de cálculo verificable para transcribir sin inventar contenido.
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

### `guanajuato/romita/2025` (cvegeo 11026)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_romita.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_romita.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria del impuesto predial ni tablas o artículos con la mecánica de cálculo. Sólo aparece el encabezado del impuesto predial dentro del cuadro de ingresos estimados y páginas en blanco/intermedias sin contenido tarifario visible en el segmento suministrado.
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
  > El segmento proporcionado no contiene el texto normativo de la sección 'Del Impuesto Predial' ni tablas o artículos tarifarios legibles; sólo aparecen encabezados, paginación y una referencia general al documento. No es posible extraer la mecánica de cálculo del impuesto predial con este contenido.
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

### `guanajuato/salvatierra/2025` (cvegeo 11028)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_salvatierra.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_salvatierra.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado sólo muestra el encabezado del impuesto predial dentro del clasificador de ingresos y páginas intermedias en blanco, pero no contiene el artículo, tabla o mecánica de cálculo del impuesto predial. No es posible extraer una tarifa o esquema sin inventar datos.
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
  > El texto proporcionado no contiene la sección tarifaria del Impuesto Predial ni tablas o artículos con mecánica de cálculo; únicamente aparecen portadas/páginas de referencia y encabezados generales de la ley. No es posible identificar rangos, tasas, cuotas o categorías aplicables al predial con este segmento.
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
  > El texto proporcionado no contiene la sección tarifaria del impuesto predial ni tablas, rangos o tasas aplicables; sólo aparecen portadas, encabezados y referencias generales de páginas. No es posible identificar la mecánica de cálculo del predial con este segmento.
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
  > El texto proporcionado no contiene el articulado ni tablas del Impuesto Predial; después del encabezado y páginas iniciales, el contenido tarifario del predial no aparece en el segmento. No es posible identificar mecánica de cálculo, brackets ni tasas sin inventar información.
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
  > El texto proporcionado no contiene la sección ni una tabla o mecánica tarifaria del Impuesto Predial. Sólo aparece el encabezado general de la ley y páginas en blanco/omisas para el tramo predial, sin renglones, rangos, tasas o cuotas aplicables.
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
  > El texto proporcionado no contiene el apartado tarifario del Impuesto Predial ni tablas o artículos con cuotas, tasas o brackets de cálculo. Solo aparecen encabezados, datos de identificación del municipio y páginas en blanco/omisión del contenido sustantivo entre las páginas 161-178.
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
  > El texto proporcionado para la sección de impuesto predial no contiene la mecánica de cálculo ni tablas tarifarias; sólo aparecen páginas con encabezados y montos globales del capítulo de impuestos, sin renglones del artículo del predial. No es posible identificar una tarifa, cuota o esquema de cálculo del impuesto predial con este segmento.
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
  > El texto proporcionado no contiene la sección tarifaria del Impuesto Predial ni una tabla/mecánica de cálculo legible; sólo aparecen encabezados y páginas sin el articulado o cuadros de cuotas/tasas. No es posible identificar brackets, tasas o cuotas sin inventar información.
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
  > El texto proporcionado no contiene el contenido de la sección 'Del Impuesto Predial' ni tabla tarifaria alguna; sólo aparecen metadatos del documento y encabezados/paginación. No es posible identificar una mecánica de cálculo del impuesto predial a partir de este segmento.
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
  > El texto proporcionado sólo contiene el encabezado del Capítulo I y el inicio del Artículo 13, pero no incluye la mecánica de cálculo del impuesto predial ni tablas, tarifas o cuotas. No es posible clasificar en ninguna de las seis variantes tarifarias con el segmento recibido.
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
  > El texto proporcionado sólo contiene el encabezado del Capítulo I y el inicio del Artículo 13, pero no incluye la mecánica de cálculo del impuesto predial ni tablas, cuotas o tasas. Con este segmento no es posible clasificar el esquema tarifario.
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

### `yucatan/yaxcaba/2011` (cvegeo 31104)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2011_yaxcaba.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2011_yaxcaba.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_encabezado`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la tabla o mecánica de cuotas del Artículo 4; sólo aparece el encabezado y luego una tasa para predios causados sobre rentas o frutos civiles en el Artículo 5, que no corresponde a la mecánica general del impuesto predial. No se puede estructurar la tabla principal sin inventar información.
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

## Grupo G-02: `estructura_no_estandar` / `dos_tarifas_paralelas` (12 casos)

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

### `yucatan/sanahcat/2010` (cvegeo 31064)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2010_sanahcat.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2010_sanahcat.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El texto establece dos mecánicas paralelas para el impuesto predial con bases distintas: una cuota de 15 centavos por metro cuadrado de extensión del predio y, por separado, una tasa de 10 al millar anual sobre el valor registrado o catastral para predios destinados a la producción agropecuaria. No encaja en las variantes disponibles porque la mecánica principal usa base de cálculo por superficie, no una tasa única sobre valor catastral ni una cuota fija simple.
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

### `yucatan/sanahcat/2011` (cvegeo 31064)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2011_sanahcat.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2011_sanahcat.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El artículo establece dos mecánicas paralelas para el impuesto predial con bases de cálculo distintas: una cuota por superficie de 15 centavos por m2 para el predio causante y, separadamente, una tasa de 10 al millar anual sobre el valor registrado o catastral para predios destinados a la producción agropecuaria. Esta combinación no encaja en una sola de las variantes tipadas porque no es una tabla de rangos ni una tarifa categórica homogénea sobre la misma base.
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

### `yucatan/sanahcat/2012` (cvegeo 31064)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2012_sanahcat.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2012_sanahcat.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El texto establece dos mecánicas paralelas para el impuesto predial con bases gravables distintas: una cuota de 15 centavos por metro cuadrado para el predio causante y, por separado, una tasa de 10 al millar anual sobre el valor registrado o catastral para predios destinados a la producción agropecuaria. No encaja limpiamente en una sola de las variantes estándar porque no es una tabla por rangos ni una sola tasa uniforme para toda la población.
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

### `yucatan/sanahcat/2014` (cvegeo 31064)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2014_sanahcat.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2014_sanahcat.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El texto establece dos mecánicas distintas para el impuesto predial: una cuota por superficie de 15 centavos por m2 para el predio causante y, por separado, una tasa de 10 al millar anual sobre el valor registrado o catastral para predios destinados a la producción agropecuaria. La base de cálculo principal es superficie, lo que no encaja en las variantes tipadas disponibles para predial en este esquema.
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

### `yucatan/sanahcat/2017` (cvegeo 31064)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2017_sanahcat.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2017_sanahcat.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El artículo 13 establece dos mecánicas paralelas y de distinta base gravable: una cuota de 15 centavos por m2 de superficie del predio y, por separado, para predios destinados a la producción agropecuaria, una tasa de 10 al millar anual sobre el valor registrado o catastral. Esto no encaja en las variantes tipadas disponibles, porque la regla general no usa valor catastral sino superficie, y la tarifa agropecuaria es una tarifa paralela para un grupo específico.
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

### `yucatan/sanahcat/2018` (cvegeo 31064)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2018_sanahcat.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2018_sanahcat.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El artículo establece dos mecánicas distintas de impuesto predial sobre bases de cálculo diferentes: una cuota de 15 centavos por m2 de extensión del predio causante y, separadamente, una tasa de 10 al millar anual sobre el valor registrado o catastral para predios destinados a la producción agropecuaria. Esto no encaja en las siete variantes tipadas, porque la mecánica principal no usa valor catastral ni una cuota fija simple anual, sino una tasa por superficie.
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

### `yucatan/sanahcat/2019` (cvegeo 31064)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2019_sanahcat.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2019_sanahcat.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El texto establece dos mecánicas distintas para el impuesto predial: una cuota por superficie de 15 centavos por m2 para el predio causante y, por separado, una tasa de 10 al millar anual sobre el valor registrado o catastral para predios destinados a la producción agropecuaria. No encaja en las variantes tipadas porque la base principal es superficie, no valor catastral, y además existe una tarifa paralela distinta para otro grupo de predios.
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

### `yucatan/sanahcat/2020` (cvegeo 31064)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2020_sanahcat.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2020_sanahcat.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El texto establece dos mecánicas paralelas para el impuesto predial: una cuota por superficie de 20 centavos por m2 para el predio causante y, por separado, una tasa de 10 al millar anual sobre el valor registrado o catastral para predios destinados a la producción agropecuaria. La base principal es superficie, no valor catastral por rangos ni una sola tasa uniforme sobre la misma base, por lo que no encaja en las seis variantes tipadas.
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

### `yucatan/sanahcat/2022` (cvegeo 31064)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2022_sanahcat.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2022_sanahcat.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El texto establece dos mecánicas distintas para el impuesto predial: una cuota por superficie de 20 centavos por m2 del predio causante y, por separado, una tasa de 10 al millar anual sobre el valor registrado o catastral para predios destinados a la producción agropecuaria. No encaja en las variantes tipadas porque la regla general no usa valor catastral sino superficie, y además existe una tarifa paralela por valor catastral para un grupo específico.
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

### `yucatan/seye/2011` (cvegeo 31067)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2011_seye.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2011_seye.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El texto presenta dos mecánicas distintas dentro del capítulo: una tarifa fija anual por tipo de predio (urbano y rústico) en el artículo 13, y además una imposición sobre rentas o frutos civiles en el artículo 15, que corresponde a un gravamen sobre ingresos y no a la mecánica típica por valor catastral. No encaja limpiamente en las variantes simples de cálculo del predial sobre valor catastral.
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
  > El texto no presenta una mecánica única de cálculo del impuesto predial. Incluye una tabla de valores unitarios de terreno para determinar valor catastral, una tabla de licencias de construcción por m2 y metro lineal que no corresponde al predial, una tarifa paralela para predios agropecuarios de 10 al millar anual, y además un impuesto sobre rentas o frutos civiles con tarifas porcentuales mensuales. No es posible reducirlo limpiamente a una sola de las variantes tarifarias solicitadas sin mezclar figuras distintas.
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

## Grupo G-03: `segmento_vacio` / `seccion_ausente` (12 casos)

### `coahuila/parras/2010` (cvegeo 05024)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_parras.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_parras.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección del Impuesto Predial; inicia en una referencia a incentivos y luego pasa al Capítulo Segundo del Impuesto Sobre Adquisición de Inmuebles. No hay tabla, tasa, cuota o mecánica de cálculo del predial identificable en el fragmento.
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

### `guanajuato/acambaro/2025` (cvegeo 11002)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_acambaro.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_acambaro.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > En el texto proporcionado no aparece la sección tarifaria del Impuesto Predial; sólo se observa el índice de ingresos y páginas generales, sin mecánica de cálculo, tablas de cuotas ni tasas aplicables al predial. Por ello no es posible clasificar la estructura en alguna de las variantes tarifarias solicitadas.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no incluye la sección tarifaria del Impuesto Predial ni tablas o artículos de cálculo; sólo aparecen páginas de portada, índice general y numeración de páginas sin mecánica de determinación del impuesto. No es posible extraer una tarifa o esquema de cálculo sin inventar contenido.
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

### `guanajuato/celaya/2024` (cvegeo 11007)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2024_celaya.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2024_celaya.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > En el texto proporcionado no aparece la sección normativa del Impuesto Predial ni una tabla tarifaria de cálculo; sólo se observan páginas con el índice y montos estimados de ingresos, y las páginas señaladas para predial están vacías o sin transcripción legible del articulado. No es posible extraer mecánica de cálculo sin inventar contenido.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > En el texto proporcionado no aparece la sección normativa o tabla del Impuesto Predial; sólo se observan páginas de ingresos estimados y rubros generales, sin mecánica de cálculo, cuotas, tasas ni rangos catastrales aplicables al predial. Por ello no es posible clasificar la estructura tarifaria del impuesto predial con este segmento.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección normativa del Impuesto Predial ni tablas o tarifas aplicables; únicamente aparecen páginas de portada/índice y saltos de página sin el articulado correspondiente. No es posible identificar mecánica de cálculo del predial con este segmento.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección o tabla del Impuesto Predial; sólo aparecen páginas generales y saltos de página sin mecánica tarifaria. No es posible identificar cuotas, tasas, rangos ni categorías aplicables al predial.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección del Impuesto Predial ni una tabla o mecánica de cálculo municipal. Sólo aparecen avisos, transitorios y tarifas del Periódico Oficial, sin datos tarifarios de predial para Purísima del Rincón.
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
  > En el texto proporcionado no aparece la sección normativa del Impuesto Predial ni una tabla de tarifas/cálculo; sólo se observan páginas de ingresos estimados y clasificador de rubros, sin mecánica de determinación del predial. No es posible extraer una tarifa o esquema de cálculo sin inventar contenido.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección normativa del Impuesto Predial ni una tabla o artículo con la mecánica de cálculo. Solo aparece el índice de ingresos donde se menciona 'Impuesto predial' y luego páginas vacías/omitidas sin disposición tarifaria. No es posible extraer brackets, tasas o cuotas sin inventar información.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la sección tarifaria del impuesto predial ni tablas, cuotas o tasas aplicables; sólo aparecen páginas de cabecera y espacios en blanco entre las páginas 170 y 187. No es posible extraer mecánica de cálculo sin contenido tarifario visible.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `seccion_ausente`
- **descripcion_estructural**:
  > El texto proporcionado contiene la ley de ingresos y el rubro de impuesto predial en estimaciones globales, pero no incluye la sección normativa o tarifa específica del impuesto predial (tablas, tasas, cuotas o brackets). No es posible extraer la mecánica de cálculo sin la disposición tarifaria correspondiente.
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

## Grupo G-04: `municipio_sin_impuesto` / `otro_patron` (7 casos)

### `coahuila/nadadores/2010` (cvegeo 05021)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_nadadores.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_nadadores.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto proporcionado no contiene una mecánica del Impuesto Predial. La única tasa visible corresponde al Impuesto Sobre Adquisición de Inmuebles (3%), por lo que no es posible extraer una tabla de predial sin inventar información.
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
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > En el texto proporcionado sólo aparece la estimación global del rubro 'Impuesto predial' dentro del artículo 1, pero no se incluye la sección normativa o tabla de cálculo del impuesto predial. El segmento está vacío respecto de la mecánica tarifaria, por lo que no es posible clasificarlo en una de las seis variantes estructurales.
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
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto proporcionado no contiene una tabla o mecánica tarifaria del impuesto predial para San Francisco del Rincón. Únicamente aparecen disposiciones administrativas sobre la tramitación y conservación de la cuota mínima para contribuyentes ya registrados, sin exponer tasas, rangos, cuotas o fórmula de cálculo del predial.
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

### `guanajuato/silao_de_la_victoria/2026` (cvegeo 11037)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2026_silao_de_la_victoria.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2026_silao_de_la_victoria.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El segmento proporcionado sólo establece una cuota mínima anual del impuesto predial y una disposición de descuento por pronto pago. No contiene una mecánica de cálculo del impuesto (tarifa, rangos, tasa única o cuotas escalonadas) para determinar la base del predial.
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

### `guanajuato/tierra_blanca/2024` (cvegeo 11040)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2024_tierra_blanca.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2024_tierra_blanca.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > En el segmento proporcionado no aparece una mecánica de cálculo del impuesto predial: sólo se observa un artículo de recurso de revisión para predios sin edificar y un artículo de ajustes tarifarios. No se incluyen tasas, cuotas, brackets ni tabla aplicable al predial.
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

### `tamaulipas/miguel_aleman/2012` (cvegeo 28025)

- **JSON**: [`predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2012_miguel_aleman.json`](predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2012_miguel_aleman.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El segmento sólo establece una cuota mínima anual de tres salarios mínimos para el impuesto predial y menciona bonificaciones para ciertos supuestos y por pronto pago. No aparece tabla de tarifas, rangos de valor catastral ni tasas aplicables para calcular la mecánica general del impuesto.
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

### `tamaulipas/miguel_aleman/2013` (cvegeo 28025)

- **JSON**: [`predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2013_miguel_aleman.json`](predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2013_miguel_aleman.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto sólo establece una cuota mínima anual de tres salarios mínimos para el impuesto predial, pero no contiene tabla, rangos, tasa al millar ni fórmula de cálculo adicional para determinar la base del impuesto. La sección transcrita se limita a bonificaciones y a una cuota mínima, sin mecánica estructural completa del gravamen.
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

## Grupo G-05: `estructura_no_estandar` / `otro_patron` (6 casos)

### `tamaulipas/nuevo_laredo/2024` (cvegeo 28027)

- **JSON**: [`predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2024_nuevo_laredo.json`](predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2024_nuevo_laredo.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto proporcionado sólo contiene la base jurídica del impuesto predial y reglas especiales de aplicación/recargos para predios urbanos no edificados y fraccionamientos, pero no incluye ninguna tabla o catálogo de tasas/cuotas del impuesto. No es posible extraer una mecánica de cálculo completa de las variantes tarifarias solicitadas.
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
  > El texto no presenta una tabla tarifaria completa del impuesto predial ni un esquema de brackets, cuota fija o tasa única. Solo describe la base del cálculo (valor catastral) y remite a una tasa no transcrita en el fragmento, además de reglas de incremento para ciertos predios y un mínimo anual en UMA. Con el segmento proporcionado no es posible reconstruir la mecánica tarifaria principal sin inventar datos.
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

### `yucatan/kaua/2023` (cvegeo 31043)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2023_kaua.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2023_kaua.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto no presenta una tabla tarifaria única del predial en forma de tarifa_millar, progresivo, tasa_unica, cuota_fija_simple, cuota_fija_escalonada o mixto. La mecánica principal es una fórmula general: valor catastral por 0.00025, con una cuota fija de $50.00 si el valor catastral es menor o igual a $200,000.00; además, el artículo 14 introduce topes de incremento respecto del ejercicio anterior. La mecánica de cálculo queda combinada con una regla de cuota fija por umbral y un factor general, pero no se estructura como un esquema estándar de brackets o tarifas categóricas.
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

### `yucatan/mani/2014` (cvegeo 31047)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2014_mani.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2014_mani.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto del Artículo 13 establece una mecánica combinada: una cuota fija de 50.00 pesos y además una tasa del 0.25% sobre el valor catastral, sin rangos ni categorías. No encaja en las variantes permitidas porque no es tasa única pura, no es cuota fija simple y tampoco hay brackets para modelarlo como progresivo o mixto.
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

### `yucatan/tekit/2014` (cvegeo 31080)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2014_tekit.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2014_tekit.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto del Artículo 13 establece el impuesto predial con una cuota fija de 50.00 pesos aplicando además una tasa de 0.15% sobre el valor catastral, sin tabla de rangos ni catálogo por categorías. Esa combinación de cuota fija más tasa porcentual única no encaja exactamente en las variantes tipadas disponibles, ya que `tasa_unica` no contempla cuota fija adicional y `cuota_fija_simple` no contempla tasa porcentual adicional.
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

### `yucatan/yaxcaba/2010` (cvegeo 31104)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2010_yaxcaba.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2010_yaxcaba.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El segmento de predial sólo indica en el Artículo 4 que el cobro se realizará conforme a cuotas, pero no incluye la tabla o mecánica correspondiente. El único detalle tarifario visible está en el Artículo 5 y corresponde a predial causado sobre la base de rentas o frutos civiles, con tasas mensuales sobre la contraprestación, lo cual no encaja en las variantes estándar solicitadas para impuesto predial sobre valor catastral.
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

## Grupo G-06: `estructura_no_estandar` / `solo_valores_unitarios` (6 casos)

### `guanajuato/valle_de_santiago/2021` (cvegeo 11042)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2021_valle_de_santiago.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2021_valle_de_santiago.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El segmento proporcionado no contiene la mecánica de cálculo del impuesto predial en forma de tarifa, tasa única, progresión o cuota fija escalonada. Lo visible son tablas de valores unitarios catastrales (terreno urbano, construcción y predios rústicos) usadas para avalúo, pero no aparece una tabla tarifaria de determinación del impuesto. Por ello no es posible clasificarlo en las variantes tarifarias solicitadas sin inventar datos.
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

### `yucatan/dzidzantun/2012` (cvegeo 31027)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2012_dzidzantun.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2012_dzidzantun.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto no presenta una mecánica tarifaria estándar del impuesto predial clasificable en una de las seis variantes principales. La "tabla" visible corresponde a una tabla de valores de terreno por ubicación y una tabla de valores unitarios de construcción, es decir, insumos catastrales, no una tarifa de cálculo del impuesto. Aunque aparece una frase sobre aplicar un factor y sumar cuota fija anual, el segmento no proporciona una tabla completa de brackets o tasas del predial aprovechable sin inferencia.
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

## Grupo G-07: `error_segmentacion` / `solo_valores_unitarios` (4 casos)

### `guanajuato/leon/2019` (cvegeo 11020)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2019_leon.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2019_leon.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `error_segmentacion`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El texto del impuesto predial contiene tablas progresivas para predios sin edificaciones, pero la OCR está severamente fragmentada y no permite reconstruir con certeza todos los brackets, límites y tasas marginales sin inventar datos. Además, el segmento incluye extensamente tablas catastrales de valores unitarios (artículos 6 y 7), que no son la tarifa del impuesto y contaminan la extracción.
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

## Grupo G-08: `segmento_vacio` / `articulado_ausente` (3 casos)

### `guanajuato/acambaro/2024` (cvegeo 11002)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2024_acambaro.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2024_acambaro.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `articulado_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el articulado ni tabla de mecánica del Impuesto Predial; sólo aparecen páginas del índice/CRI y páginas en blanco o sin el segmento tarifario. No es posible transcribir una estructura de cálculo sin inventarla.
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

### `guanajuato/apaseo_el_alto/2025` (cvegeo 11004)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_apaseo_el_alto.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_apaseo_el_alto.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `articulado_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el artículo, tabla o mecánica específica del Impuesto Predial; sólo aparecen páginas de índice/ingresos estimados y el renglón '1201 Impuesto predial' sin desglose tarifario. No es posible transcribir una mecánica de cálculo sin inventarla.
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
- **categoria**: `segmento_vacio`  ·  **tag**: `articulado_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene el artículo ni la tabla específica de la mecánica del Impuesto Predial. Solo aparecen disposiciones de ajustes, recurso de revisión y referencias indirectas al artículo 21 de otra sección, pero no la tarifa o estructura de cálculo del predial. No es posible clasificar la mecánica sin inventarla.
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

## Grupo G-09: `segmento_vacio` / `mecanica_ausente` (3 casos)

### `coahuila/nava/2010` (cvegeo 05022)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_nava.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_nava.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `mecanica_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la mecánica del Impuesto Predial del municipio de Nava, Coahuila. El fragmento visible corresponde a incentivos y luego al Impuesto Sobre Adquisición de Inmuebles, por lo que no aparece una tabla o regla tarifaria del predial para extraer.
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

### `coahuila/progreso/2010` (cvegeo 05026)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_progreso.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_progreso.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `mecanica_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no incluye la mecánica del Impuesto Predial; sólo aparecen disposiciones de incentivos para ciertos contribuyentes y luego inicia el Capítulo Segundo del Impuesto sobre Adquisición de Inmuebles. No hay tabla, tasa, cuota o brackets del predial para transcribir.
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

### `guanajuato/tarandacuao/2025` (cvegeo 11038)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_tarandacuao.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_tarandacuao.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `mecanica_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no contiene la mecánica tarifaria del impuesto predial (tasas, cuotas o brackets). La sección visible sólo muestra referencias generales, páginas en blanco/omitidas y una cuota mínima anual en el artículo de facilidades administrativas, pero no la tabla base de cálculo del predial. Por ello no es posible clasificar la estructura con las variantes tarifarias solicitadas.
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

## Grupo G-10: `estructura_no_estandar` / `factor_sin_tabla` (2 casos)

### `yucatan/cansahcab/2023` (cvegeo 31009)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2023_cansahcab.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2023_cansahcab.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `factor_sin_tabla`
- **descripcion_estructural**:
  > El texto contiene varias mecánicas distintas del impuesto predial: una fórmula general con factor 0.00025 sobre valor catastral, una cuota fija de 1 UMA para predios con valor catastral igual o menor a 200,000, una tabla de cuotas en UMA para predios rústicos por superficie, y además una tabla aparte para predial sobre rentas o frutos civiles. No existe una sola tabla homogénea que encaje limpiamente en tarifa_millar, progresivo, cuota fija escalonada o mixto sin mezclar bases de cálculo distintas.
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

### `yucatan/mayapan/2025` (cvegeo 31049)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2025_mayapan.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2025_mayapan.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `factor_sin_tabla`
- **descripcion_estructural**:
  > El texto no presenta una sola mecánica estándar de cálculo de predial. Para predial base valor catastral, el artículo indica un factor de 0.00025 sobre el valor catastral actualizado y además una cuota fija de $150.00 para predios con valor catastral igual o menor a $200,000.00; sin embargo, también incluye una tarifa distinta sobre rentas o frutos civiles en el Art. 8 (2% habitacional y 5% comercial), que corresponde a otra base de cálculo. Por ello no encaja limpiamente en una sola de las variantes tarifarias solicitadas.
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

## Grupo G-11: `municipio_sin_impuesto` / `solo_valores_unitarios` (2 casos)

### `guanajuato/tierra_blanca/2018` (cvegeo 11040)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2018_tierra_blanca.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2018_tierra_blanca.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El segmento proporcionado contiene tablas de valores unitarios de terreno y construcción para avalúo catastral, pero no presenta una mecánica de cálculo del impuesto predial con cuotas, tasas al millar, brackets de valor catastral ni tarifa aplicable. No se observa artículo o tabla de determinación del impuesto predial propiamente dicho dentro del texto entregado.
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
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El segmento proporcionado corresponde a tablas de valores unitarios de terreno y construcción para avalúo catastral, factores de zona, frente, forma, superficie, fondo, topografía y valores base rústicos, pero no muestra una tabla o mecánica de tasas/cuotas del impuesto predial (ni tarifa al millar, ni cuotas fijas por rangos, ni tasa única). Por ello no es posible clasificar la mecánica del impuesto predial con la información visible.
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

## Grupo G-12: `segmento_vacio` / `otro_patron` (2 casos)

### `guanajuato/salvatierra/2024` (cvegeo 11028)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2024_salvatierra.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2024_salvatierra.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto proporcionado para la sección de impuesto predial no contiene tablas ni artículos tarifarios visibles; solo aparecen páginas en blanco o marcadores de página, sin mecánica de cálculo recuperable. No es posible identificar cuotas, tasas, rangos ni categorías del predial con este segmento.
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

### `tamaulipas/ciudad_madero/2020` (cvegeo 28009)

- **JSON**: [`predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2020_ciudad_madero.json`](predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2020_ciudad_madero.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto proporcionado no incluye la tabla de tarifas del Artículo 9; únicamente aparece la frase introductoria 'Se aplicará la siguiente tarifa para predios urbanos del municipio' y luego continúa con reglas de incrementos y mínimos. Sin la tabla de cuotas/tasas no es posible clasificar la mecánica de cálculo en una de las variantes tarifarias.
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

## Grupo G-13: `error_segmentacion` / `dos_tarifas_paralelas` (1 casos)

### `yucatan/mococha/2010` (cvegeo 31051)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2010_mococha.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2010_mococha.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `error_segmentacion`  ·  **tag**: `dos_tarifas_paralelas`
- **descripcion_estructural**:
  > El segmento contiene principalmente tablas de valores unitarios de terreno y construcción (catastro), pero no incluye la tabla tarifaria del impuesto predial por rangos o cuotas a la que alude la frase 'A la cantidad que se exceda del límite inferior...'. Sólo es visible una tarifa paralela para predios destinados a la producción agropecuaria de 10 al millar anual sobre el valor registrado o catastral, por lo que no hay información suficiente para reconstruir la tabla principal sin inventar rangos o montos.
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

## Grupo G-14: `error_segmentacion` / `otro_patron` (1 casos)

### `guanajuato/santa_cruz_de_juventino_rosas/2025` (cvegeo 11035)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2025_santa_cruz_de_juventino_rosas.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2025_santa_cruz_de_juventino_rosas.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `error_segmentacion`  ·  **tag**: `otro_patron`
- **descripcion_estructural**:
  > El texto describe expresamente una mecánica progresiva del impuesto predial con valor fiscal, límite inferior, tasa marginal y cuota fija, pero la tabla de TASAS no aparece en el segmento proporcionado. El contenido entre las páginas referidas está ausente o sustituido por encabezados de página y después cambia a otros conceptos distintos al predial, por lo que no es posible reconstruir válidamente los rangos ni las tasas.
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

## Grupo G-15: `estructura_no_estandar` / `ejidal_comunal` (1 casos)

### `yucatan/sanahcat/2015` (cvegeo 31064)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2015_sanahcat.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2015_sanahcat.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `estructura_no_estandar`  ·  **tag**: `ejidal_comunal`
- **descripcion_estructural**:
  > El texto no presenta una tabla tarifaria estándar por valor catastral ni una cuota fija simple/escalonada. La mecánica principal indica 15 centavos por m2 de extensión del predio, y además establece una tarifa paralela distinta para predios destinados a la producción agropecuaria: 10 al millar anual sobre el valor registrado o catastral. No encaja de forma limpia en las variantes simples porque mezcla una base por superficie con una tasa al millar sobre valor catastral.
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

## Grupo G-16: `municipio_sin_impuesto` / `ejidal_comunal` (1 casos)

### `yucatan/sanahcat/2016` (cvegeo 31064)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2016_sanahcat.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2016_sanahcat.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `ejidal_comunal`
- **descripcion_estructural**:
  > El texto no presenta una tabla tarifaria por rangos ni un esquema clasificable en las variantes esperadas. Sólo se lee una regla general: '15 centavos por m2' y, para predios destinados a producción agropecuaria, '10 al millar anual sobre el valor registrado o catastral'. No hay estructura de brackets, categorías tarifarias comparables ni una tabla desarrollable en cuota fija/progresiva/tasa única.
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

## Grupo G-17: `municipio_sin_impuesto` / `mecanica_ausente` (1 casos)

### `tamaulipas/nuevo_laredo/2013` (cvegeo 28027)

- **JSON**: [`predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2013_nuevo_laredo.json`](predial-mx-v2/tamaulipas/TAMPS_PREDIAL_2013_nuevo_laredo.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `municipio_sin_impuesto`  ·  **tag**: `mecanica_ausente`
- **descripcion_estructural**:
  > El segmento proporcionado sólo muestra renglones de recaudación/partidas presupuestales (propiedad urbana, suburbana y rústica) con montos agregados, pero no contiene la mecánica de determinación del impuesto predial: no hay tasas, cuotas, rangos de valor catastral ni tablas aplicables. No es posible transcribir una fórmula de cálculo a partir de este fragmento.
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

## Grupo G-18: `segmento_vacio` / `contenido_ausente` (1 casos)

### `guanajuato/apaseo_el_grande/2019` (cvegeo 11005)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2019_apaseo_el_grande.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2019_apaseo_el_grande.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `contenido_ausente`
- **descripcion_estructural**:
  > El texto proporcionado no incluye el contenido de la sección 'Del Impuesto Predial' ni alguna tabla o artículo con la mecánica de cálculo; sólo aparecen metadatos y páginas de portadilla del periódico oficial. No es posible transcribir una tarifa sin el segmento tarifario.
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

## Grupo G-19: `segmento_vacio` / `solo_valores_unitarios` (1 casos)

### `guanajuato/uriangato/2018` (cvegeo 11041)

- **JSON**: [`predial-mx-v2/guanajuato/GTO_PREDIAL_2018_uriangato.json`](predial-mx-v2/guanajuato/GTO_PREDIAL_2018_uriangato.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `solo_valores_unitarios`
- **descripcion_estructural**:
  > El fragmento proporcionado contiene únicamente encabezados, referencias a tablas de valores unitarios y factores de valuación (terreno/construcción), pero no incluye una mecánica tarifaria completa del impuesto predial con tasas, cuotas o brackets aplicables. No se observa una tabla de cálculo del predial transcribible sin inventar contenido.
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

## Grupo G-20: `segmento_vacio` / `texto_truncado` (1 casos)

### `coahuila/muzquiz/2010` (cvegeo 05020)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2010_muzquiz.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2010_muzquiz.json)
- **tipo actual** (LLM): `otro_no_clasificado`
- **categoria**: `segmento_vacio`  ·  **tag**: `texto_truncado`
- **descripcion_estructural**:
  > El texto proporcionado inicia a media frase y corresponde a reglas de diferimiento/actualización del impuesto, pero no incluye la tabla o mecánica tarifaria del Impuesto Predial. No hay brackets, cuotas, tasas al millar ni una cuota fija identificable para transcribir.
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


## Casos `requiere_revision` excluyendo `otro_no_clasificado` (21 casos)

### `coahuila/hidalgo/2013` (cvegeo 05013)

- **JSON**: [`predial-mx-v2/coahuila/COAH_PREDIAL_2013_hidalgo.json`](predial-mx-v2/coahuila/COAH_PREDIAL_2013_hidalgo.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=api_error: APIConnectionError: Connection error. | mini_e2=api_error: APIConnectionError: Connection error. | full_e3=api_error: APIConnectionError: Connection error.`
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

### `yucatan/chemax/2022` (cvegeo 31019)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2022_chemax.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2022_chemax.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, brackets 5→6: hueco detectado (superior=15000.0, siguiente inferior=15500.01) | mini_e2=  • predial.mixto: Value error, brackets 5→6: hueco detectado (superior=15000.0, siguiente i`
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

### `yucatan/conkal/2021` (cvegeo 31013)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2021_conkal.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2021_conkal.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/dzemul/2010` (cvegeo 31026)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2010_dzemul.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2010_dzemul.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/dzemul/2012` (cvegeo 31026)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2012_dzemul.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2012_dzemul.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/dzemul/2013` (cvegeo 31026)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2013_dzemul.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2013_dzemul.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/dzemul/2015` (cvegeo 31026)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2015_dzemul.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2015_dzemul.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/dzilam_gonzalez/2014` (cvegeo 31029)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2014_dzilam_gonzalez.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2014_dzilam_gonzalez.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/dzilam_gonzalez/2015` (cvegeo 31029)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2015_dzilam_gonzalez.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2015_dzilam_gonzalez.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/dzilam_gonzalez/2016` (cvegeo 31029)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2016_dzilam_gonzalez.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2016_dzilam_gonzalez.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/dzilam_gonzalez/2018` (cvegeo 31029)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2018_dzilam_gonzalez.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2018_dzilam_gonzalez.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/dzilam_gonzalez/2021` (cvegeo 31029)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2021_dzilam_gonzalez.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2021_dzilam_gonzalez.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/dzilam_gonzalez/2022` (cvegeo 31029)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2022_dzilam_gonzalez.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2022_dzilam_gonzalez.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/ixil/2011` (cvegeo 31039)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2011_ixil.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2011_ixil.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/ixil/2012` (cvegeo 31039)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2012_ixil.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2012_ixil.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/mani/2015` (cvegeo 31047)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2015_mani.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2015_mani.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/rio_lagartos/2024` (cvegeo 31061)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2024_rio_lagartos.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2024_rio_lagartos.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/tekit/2018` (cvegeo 31080)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2018_tekit.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2018_tekit.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/telchac_pueblo/2013` (cvegeo 31082)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2013_telchac_pueblo.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2013_telchac_pueblo.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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

### `yucatan/telchac_pueblo/2019` (cvegeo 31082)

- **JSON**: [`predial-mx-v2/yucatan/YUC_PREDIAL_2019_telchac_pueblo.json`](predial-mx-v2/yucatan/YUC_PREDIAL_2019_telchac_pueblo.json)
- **tipo actual** (LLM): `FALTA_PREDIAL`
- **razon**: `valido_3x_fallido | mini_e1=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | mini_e2=  • predial.mixto: Value error, bracket 1: superior=None solo permitido en el último rango | full_e3=  • predia`
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
