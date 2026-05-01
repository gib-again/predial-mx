# Auditoría — localizar sección predial faltante

Acompaña a `output/audit_pendiente.csv`.

**Total de huecos a auditar: 82**

- `schema_discontinuity`: 40
- `sin_predial_residual`: 34
- `edge`: 8

## Tu trabajo

Por cada hueco listado, abre los PDFs de los **años vecinos** indicados (con sus páginas precisas) y compara con el PDF candidato del año del hueco. Tu salida son **4 campos** del CSV:

| Campo | Valor | Significado |
|---|---|---|
| `estatus` | `encontrado` | Localizaste la sección predial. Llena `pdf_objetivo` y `paginas`. |
| `estatus` | `no_existe_ley` | Confirmas que no se publicó Ley de Ingresos ese año. |
| `pdf_objetivo` | filename | PDF dentro de `data/{estado}/pdf_raw/.../` (ej. `2019-01-15.pdf`). Vacío si `no_existe_ley`. |
| `paginas` | `47-52` o `47` | Rango de páginas de la sección predial. Vacío si `no_existe_ley`. |
| `notas` | texto libre | Opcional. Cita de art./reforma, fuente alternativa, etc. |

Una vez llenados los campos, corre `python -m scripts.reextract_from_audit` para que el pipeline stage el focus_predial.txt y dispare la extracción LLM.

## Huecos por municipio

### 11007 Guanajuato — Celaya

#### 2019 · `schema_discontinuity`

- **Vecino previo**:  2018 · `tarifa_millar` · 2017_11492_Periodico_Número_228_Segunda_Parte_ocr.pdf p.86-99
- **Vecino siguiente**: 2020 · `progresivo` · 2019_13220_Periodico_Numero_260_Segunda_Parte_ocr.pdf p.111-126
- **PDF candidato 2019**: `2019_13182_Periodico_Numero_259_Septima_Parte.pdf` (en `data/guanajuato/pdf_raw/2019/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 11014 Guanajuato — Dolores Hidalgo Cuna de la Independencia Nacional

#### 2021 · `schema_discontinuity`

- **Vecino previo**:  2020 · `tarifa_millar` · 2019_13221_Periodico_Numero_260_Tercera_Parte_ocr.pdf p.117-124
- **Vecino siguiente**: 2022 · `mixto` · 2021_14624_Periodico_Numero_260_Séptima_Parte_ocr.pdf p.28-41
- **PDF candidato 2021**: `2021_14082_Periódico_Número_27_Segunda_Parte.pdf` (en `data/guanajuato/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 11015 Guanajuato — Guanajuato

#### 2021 · `schema_discontinuity`

- **Vecino previo**:  2020 · `tarifa_millar` · 2019_13221_Periodico_Numero_260_Tercera_Parte_ocr.pdf p.174-182
- **Vecino siguiente**: 2023 · `progresivo`
- **PDF candidato 2021**: `2021_14082_Periódico_Número_27_Segunda_Parte.pdf` (en `data/guanajuato/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2022 · `schema_discontinuity`

- **Vecino previo**:  2020 · `tarifa_millar` · 2019_13221_Periodico_Numero_260_Tercera_Parte_ocr.pdf p.174-182
- **Vecino siguiente**: 2023 · `progresivo`
- **PDF candidato 2022**: `2022_15505_Periódico_Numero_260_Tercera_Parte.pdf` (en `data/guanajuato/pdf_raw/2022/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 11017 Guanajuato — Irapuato

#### 2021 · `schema_discontinuity`

- **Vecino previo**:  2020 · `mixto` · 2019_13223_Periodico_Numero_260_Cuarta_Parte_ocr.pdf p.10-32
- **Vecino siguiente**: 2022 · `progresivo` · 2021_14625_Periodico_Numero_260_Octava_Parte_ocr.pdf p.28-225
- **PDF candidato 2021**: `2021_14082_Periódico_Número_27_Segunda_Parte.pdf` (en `data/guanajuato/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 11020 Guanajuato — Leon

#### 2013 · `schema_discontinuity`

- **Vecino previo**:  2012 · `progresivo` · 2011_3455_Periodico_Numero_204_Decima_Segunda_Parte_ocr.pdf p.116-128
- **Vecino siguiente**: 2014 · `mixto` · 2013_4928_Periodico_Numero_207_Septima_Parte_ocr.pdf p.130-145
- **PDF candidato 2013**: `2013_4923_Periodico_Numero_207_Segunda_Parte.pdf` (en `data/guanajuato/pdf_raw/2013/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2024 · `schema_discontinuity`

- **Vecino previo**:  2023 · `progresivo` · 2022_15519_Periodico_Numero_260_Decima_Quinta_Parte_ocr.pdf p.36-49
- **Vecino siguiente**: 2025 · `mixto` · 2024_17229_Periódico_Número_261_Décima_Cuarta_Parte_ocr.pdf p.185-198
- **PDF candidato 2024**: `2024_17194_Periódico_Número_261_Segunda_Parte.pdf` (en `data/guanajuato/pdf_raw/2024/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 11033 Guanajuato — San Luis de la Paz

#### 2024 · `schema_discontinuity`

- **Vecino previo**:  2023 · `tarifa_millar` · 2022_15525_Periodico_Numero_260_Vigesima_Primera_Parte_ocr.pdf p.18-26
- **Vecino siguiente**: 2025 · `progresivo` · 2024_17212_Periódico_Número_261_Vigésima_Primera_Parte_ocr.pdf p.25-36
- **PDF candidato 2024**: `2024_17194_Periódico_Número_261_Segunda_Parte.pdf` (en `data/guanajuato/pdf_raw/2024/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 11003 Guanajuato — San Miguel de Allende

#### 2013 · `schema_discontinuity`

- **Vecino previo**:  2012 · `tarifa_millar` · 2011_3456_Periodico_Numero_204_Decima_Tercera_Parte_ocr.pdf p.3-9
- **Vecino siguiente**: 2014 · `mixto` · 2013_4938_Periodico_Numero_207_Decima_Septima_Parte_ocr.pdf p.75-82
- **PDF candidato 2013**: `2013_4923_Periodico_Numero_207_Segunda_Parte.pdf` (en `data/guanajuato/pdf_raw/2013/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 11036 Guanajuato — Santiago Maravatio

#### 2024 · `schema_discontinuity`

- **Vecino previo**:  2023 · `tarifa_millar` · 2022_15526_Periodico_Numero_260_Vigesima_Segunda_Parte_ocr.pdf p.187-195
- **Vecino siguiente**: 2025 · `mixto` · 2024_17215_Periódico_Número_261_Vigésima_Cuarta_Parte_ocr.pdf
- **PDF candidato 2024**: `2024_17194_Periódico_Número_261_Segunda_Parte.pdf` (en `data/guanajuato/pdf_raw/2024/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 14071 Jalisco — San Cristobal de la Barranca

#### 2021 · `schema_discontinuity`

- **Vecino previo**:  2020 · `tarifa_millar`
- **Vecino siguiente**: 2022 · `progresivo`
- **PDF candidato 2021**: `JAL_RAW_2021_acatic.pdf` (en `data/jalisco/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 22005 Queretaro — Colon

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `tarifa_millar`
- **Vecino siguiente**: 2017 · `progresivo`
- **PDF candidato 2016**: `QRO_RAW_20161271-01.pdf` (en `data/queretaro/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2016 · `sin_predial_residual`

- **PDF candidato 2016**: (no hay PDFs en `data/queretaro/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 22011 Queretaro — El Marques

#### 2015 · `schema_discontinuity`

- **Vecino previo**:  2014 · `tarifa_millar`
- **Vecino siguiente**: 2017 · `progresivo`
- **PDF candidato 2015**: `QRO_RAW_20151298-01.pdf` (en `data/queretaro/pdf_raw/2015/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2014 · `tarifa_millar`
- **Vecino siguiente**: 2017 · `progresivo`
- **PDF candidato 2016**: `QRO_RAW_20161271-01.pdf` (en `data/queretaro/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 22011 Queretaro — El Marqués

#### 2015 · `sin_predial_residual`

- **PDF candidato 2015**: (no hay PDFs en `data/queretaro/pdf_raw/2015/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2015 · `sin_predial_residual`

- **PDF candidato 2015**: (no hay PDFs en `data/queretaro/pdf_raw/2015/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2015 · `sin_predial_residual`

- **PDF candidato 2015**: (no hay PDFs en `data/queretaro/pdf_raw/2015/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2016 · `sin_predial_residual`

- **PDF candidato 2016**: (no hay PDFs en `data/queretaro/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2016 · `sin_predial_residual`

- **PDF candidato 2016**: (no hay PDFs en `data/queretaro/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2016 · `sin_predial_residual`

- **PDF candidato 2016**: (no hay PDFs en `data/queretaro/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2025 · `sin_predial_residual`

- **PDF candidato 2025**: (no hay PDFs en `data/queretaro/pdf_raw/2025/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 22014 Queretaro — Querétaro

#### 2022 · `sin_predial_residual`

- **PDF candidato 2022**: (no hay PDFs en `data/queretaro/pdf_raw/2022/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31004 Yucatan — Baca

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `tasa_unica` · 2014\2014-12-24_2.pdf p.54-56
- **Vecino siguiente**: 2017 · `cuota_fija_escalonada` · 2016\2016-12-28_2.pdf p.44-47
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31005 Yucatan — Bokoba

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `progresivo` · 2014\2014-12-24_2.pdf p.64-66
- **Vecino siguiente**: 2017 · `mixto` · 2016\2016-12-29_2.pdf p.29-31
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31019 Yucatan — Chemax

#### 2022 · `schema_discontinuity`

- **Vecino previo**:  2021 · `mixto` · 2020\2020-12-28_2.pdf p.276-278
- **Vecino siguiente**: 2023 · `progresivo` · 2022\2022-12-30_4.pdf p.446-448
- **PDF candidato 2022**: `2022-01-13_2.pdf` (en `data/yucatan/pdf_raw/2022/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31021 Yucatan — Chichimila

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `progresivo` · 2014\2014-12-24_2.pdf p.320-321
- **Vecino siguiente**: 2017 · `mixto` · 2016\2016-12-28_2.pdf p.278-279
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31023 Yucatan — Chochola

#### 2017 · `edge`

- **Vecino previo**:  2012 · `otro_no_clasificado` · 2011\2011-12-28_suplemento.pdf p.296-299
- **Vecino siguiente**: 2019 · `otro_no_clasificado` · 2018\2018-12-28_2.pdf p.393-399
- **PDF candidato 2017**: `2017-01-03_1.pdf` (en `data/yucatan/pdf_raw/2017/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2018 · `edge`

- **Vecino previo**:  2012 · `otro_no_clasificado` · 2011\2011-12-28_suplemento.pdf p.296-299
- **Vecino siguiente**: 2019 · `otro_no_clasificado` · 2018\2018-12-28_2.pdf p.393-399
- **PDF candidato 2018**: `2018-01-15_1.pdf` (en `data/yucatan/pdf_raw/2018/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2022 · `schema_discontinuity`

- **Vecino previo**:  2021 · `otro_no_clasificado` · 2020\2020-12-29_2.pdf p.139-145
- **Vecino siguiente**: 2023 · `mixto` · 2022\2022-12-30_4.pdf p.542-546
- **PDF candidato 2022**: `2022-01-13_2.pdf` (en `data/yucatan/pdf_raw/2022/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31028 Yucatan — Dzilam de Bravo

#### 2021 · `edge`

- **Vecino previo**:  2016 · `cuota_fija_simple` · 2015\2015-12-23_2.pdf p.348-349
- **Vecino siguiente**: 2022 · `tasa_unica` · 2021\2021-12-31_3.pdf p.635-637
- **PDF candidato 2021**: `2021-01-04_1.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31028 Yucatan — Dzilám de Bravo

#### 2021 · `sin_predial_residual`

- **PDF candidato 2021**: `2020-12-29_2.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31034 Yucatan — Hocabá

#### 2019 · `sin_predial_residual`

- **PDF candidato 2019**: `2018-12-28_2.pdf` (en `data/yucatan/pdf_raw/2019/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2020 · `sin_predial_residual`

- **PDF candidato 2020**: `2019-12-27_2.pdf` (en `data/yucatan/pdf_raw/2020/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2021 · `sin_predial_residual`

- **PDF candidato 2021**: `2020-12-29_2.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2023 · `sin_predial_residual`

- **PDF candidato 2023**: `2022-12-30_4.pdf` (en `data/yucatan/pdf_raw/2023/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2024 · `sin_predial_residual`

- **PDF candidato 2024**: `2023-12-29_3.pdf` (en `data/yucatan/pdf_raw/2024/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2025 · `sin_predial_residual`

- **PDF candidato 2025**: `2024-12-30_3.pdf` (en `data/yucatan/pdf_raw/2025/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31038 Yucatan — Hunucma

#### 2020 · `edge`

- **Vecino previo**:  2015 · `tasa_unica` · 2014\2014-12-31_2.pdf p.158-164
- **Vecino siguiente**: 2024 · `progresivo` · 2023\2023-12-29_3.pdf p.853-859
- **PDF candidato 2020**: `2020-01-03_1.pdf` (en `data/yucatan/pdf_raw/2020/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2021 · `edge`

- **Vecino previo**:  2015 · `tasa_unica` · 2014\2014-12-31_2.pdf p.158-164
- **Vecino siguiente**: 2024 · `progresivo` · 2023\2023-12-29_3.pdf p.853-859
- **PDF candidato 2021**: `2021-01-04_1.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2022 · `edge`

- **Vecino previo**:  2015 · `tasa_unica` · 2014\2014-12-31_2.pdf p.158-164
- **Vecino siguiente**: 2024 · `progresivo` · 2023\2023-12-29_3.pdf p.853-859
- **PDF candidato 2022**: `2022-01-13_2.pdf` (en `data/yucatan/pdf_raw/2022/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2023 · `edge`

- **Vecino previo**:  2015 · `tasa_unica` · 2014\2014-12-31_2.pdf p.158-164
- **Vecino siguiente**: 2024 · `progresivo` · 2023\2023-12-29_3.pdf p.853-859
- **PDF candidato 2023**: `2023-01-12_2.pdf` (en `data/yucatan/pdf_raw/2023/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31039 Yucatan — Ixil

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `tasa_unica` · 2014\2014-12-31_2.pdf p.186-188
- **Vecino siguiente**: 2017 · `progresivo` · 2016\2016-12-29_2.pdf p.167-169
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31047 Yucatan — Mani

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `tasa_unica` · 2014\2014-12-31_2.pdf p.284-285
- **Vecino siguiente**: 2017 · `progresivo` · 2016\2016-12-29_2.pdf p.268-270
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31048 Yucatan — Maxcanu

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `progresivo` · 2014\2014-12-31_2.pdf p.293-297
- **Vecino siguiente**: 2017 · `mixto` · 2016\2016-12-29_2.pdf p.280-283
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31058 Yucatan — Peto

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `tasa_unica` · 2014\2014-12-31_2.pdf p.358
- **Vecino siguiente**: 2017 · `progresivo` · 2016\2016-12-28_2.pdf p.545-549
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31059 Yucatan — Progreso

#### 2014 · `schema_discontinuity`

- **Vecino previo**:  2013 · `mixto` · 2012\2012-12-27_suplemento.pdf p.336-343
- **Vecino siguiente**: 2015 · `progresivo` · 2014\2014-12-31_2.pdf p.382-389
- **PDF candidato 2014**: `2014-01-10_1.pdf` (en `data/yucatan/pdf_raw/2014/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31063 Yucatan — Samahil

#### 2014 · `schema_discontinuity`

- **Vecino previo**:  2013 · `mixto` · 2012\2012-12-24_suplemento.pdf p.520-523
- **Vecino siguiente**: 2015 · `progresivo` · 2014\2014-12-24_2.pdf p.610-613
- **PDF candidato 2014**: `2014-01-10_1.pdf` (en `data/yucatan/pdf_raw/2014/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31065 Yucatan — San Felipe

#### 2021 · `schema_discontinuity`

- **Vecino previo**:  2020 · `progresivo` · 2019\2019-12-27_2.pdf p.685-687
- **Vecino siguiente**: 2022 · `tasa_unica` · 2021\2021-12-31_3.pdf p.1523-1525
- **PDF candidato 2021**: `2021-01-04_1.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2021 · `sin_predial_residual`

- **PDF candidato 2021**: `2020-12-29_2.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31069 Yucatan — Sotuta

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `otro_no_clasificado` · 2014\2014-12-24_2.pdf p.654-659
- **Vecino siguiente**: 2017 · `progresivo` · 2016\2016-12-29_2.pdf p.474-477
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31075 Yucatan — Teabo

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `tarifa_millar` · 2014\2014-12-24_2.pdf p.694-696
- **Vecino siguiente**: 2017 · `progresivo` · 2016\2016-12-29_2.pdf p.539-541
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31079 Yucatan — Tekax

#### 2018 · `schema_discontinuity`

- **Vecino previo**:  2017 · `tasa_unica` · 2016\2016-12-29_2.pdf p.586-587
- **Vecino siguiente**: 2019 · `otro_no_clasificado` · 2018\2018-12-29_2.pdf p.417-424
- **PDF candidato 2018**: `2018-01-15_1.pdf` (en `data/yucatan/pdf_raw/2018/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2018 · `sin_predial_residual`

- **PDF candidato 2018**: `2017-12-31_3.pdf` (en `data/yucatan/pdf_raw/2018/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2025 · `sin_predial_residual`

- **PDF candidato 2025**: `2024-12-30_3.pdf` (en `data/yucatan/pdf_raw/2025/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31081 Yucatan — Tekom

#### 2020 · `edge`

- **Vecino previo**:  2015 · `progresivo` · 2014\2014-12-24_2.pdf p.741-744
- **Vecino siguiente**: 2021 · `tasa_unica` · 2020\2020-12-29_2.pdf p.897-898
- **PDF candidato 2020**: `2020-01-03_1.pdf` (en `data/yucatan/pdf_raw/2020/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31083 Yucatan — Telchac Puerto

#### 2021 · `schema_discontinuity`

- **Vecino previo**:  2020 · `mixto` · 2019\2019-12-27_2.pdf p.939-944
- **Vecino siguiente**: 2022 · `progresivo` · 2021\2021-12-31_3.pdf p.1873-1877
- **PDF candidato 2021**: `2021-01-04_1.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31085 Yucatan — Temozon

#### 2013 · `schema_discontinuity`

- **Vecino previo**:  2012 · `tasa_unica` · 2011\2011-12-29_suplemento.pdf p.479-481
- **Vecino siguiente**: 2014 · `tarifa_millar` · 2013\2013-12-31_3.pdf p.469-471
- **PDF candidato 2013**: `2013-01-15.pdf` (en `data/yucatan/pdf_raw/2013/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `tarifa_millar` · 2014\2014-12-31_2.pdf p.582-584
- **Vecino siguiente**: 2017 · `progresivo` · 2016\2016-12-29_2.pdf p.636-638
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31085 Yucatan — Temozón

#### 2013 · `sin_predial_residual`

- **PDF candidato 2013**: `2012-12-27_suplemento.pdf` (en `data/yucatan/pdf_raw/2013/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31090 Yucatan — Timucuy

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `mixto` · 2014\2014-12-31_2.pdf p.660-662
- **Vecino siguiente**: 2017 · `progresivo` · 2016\2016-12-29_2.pdf p.688-690
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31091 Yucatan — Tinum

#### 2020 · `schema_discontinuity`

- **Vecino previo**:  2019 · `progresivo` · 2018\2018-12-28_2.pdf p.1485-1490
- **Vecino siguiente**: 2022 · `mixto` · 2021\2021-12-31_3.pdf p.2087-2092
- **PDF candidato 2020**: `2020-01-03_1.pdf` (en `data/yucatan/pdf_raw/2020/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2021 · `schema_discontinuity`

- **Vecino previo**:  2019 · `progresivo` · 2018\2018-12-28_2.pdf p.1485-1490
- **Vecino siguiente**: 2022 · `mixto` · 2021\2021-12-31_3.pdf p.2087-2092
- **PDF candidato 2021**: `2021-01-04_1.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2021 · `sin_predial_residual`

- **PDF candidato 2021**: `2020-12-28_2.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31093 Yucatan — Tixkokob

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `progresivo` · 2014\2014-12-31_2.pdf p.699-702
- **Vecino siguiente**: 2017 · `mixto` · 2016\2016-12-28_2.pdf p.747-750
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31095 Yucatan — Tixpehual

#### 2021 · `schema_discontinuity`

- **Vecino previo**:  2020 · `progresivo` · 2019\2019-12-24_2.pdf p.994-997
- **Vecino siguiente**: 2022 · `otro_no_clasificado` · 2021\2021-12-31_3.pdf p.2172-2179
- **PDF candidato 2021**: `2021-01-04_1.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31100 Yucatan — Ucú

#### 2021 · `sin_predial_residual`

- **PDF candidato 2021**: `2020-12-28_2.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2022 · `sin_predial_residual`

- **PDF candidato 2022**: `2021-12-31_3.pdf` (en `data/yucatan/pdf_raw/2022/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2023 · `sin_predial_residual`

- **PDF candidato 2023**: `2022-12-30_4.pdf` (en `data/yucatan/pdf_raw/2023/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2024 · `sin_predial_residual`

- **PDF candidato 2024**: `2023-12-29_3.pdf` (en `data/yucatan/pdf_raw/2024/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2025 · `sin_predial_residual`

- **PDF candidato 2025**: `2024-12-30_4.pdf` (en `data/yucatan/pdf_raw/2025/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31102 Yucatan — Valladolid

#### 2018 · `sin_predial_residual`

- **PDF candidato 2018**: `2017-12-31_3.pdf` (en `data/yucatan/pdf_raw/2018/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2019 · `sin_predial_residual`

- **PDF candidato 2019**: `2018-12-28_2.pdf` (en `data/yucatan/pdf_raw/2019/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2020 · `sin_predial_residual`

- **PDF candidato 2020**: `2019-12-27_2.pdf` (en `data/yucatan/pdf_raw/2020/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2021 · `sin_predial_residual`

- **PDF candidato 2021**: `2020-12-29_2.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2022 · `sin_predial_residual`

- **PDF candidato 2022**: `2021-12-31_3.pdf` (en `data/yucatan/pdf_raw/2022/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2023 · `sin_predial_residual`

- **PDF candidato 2023**: `2022-12-30_4.pdf` (en `data/yucatan/pdf_raw/2023/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2024 · `sin_predial_residual`

- **PDF candidato 2024**: `2023-12-29_3.pdf` (en `data/yucatan/pdf_raw/2024/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2025 · `sin_predial_residual`

- **PDF candidato 2025**: `2024-12-30_4.pdf` (en `data/yucatan/pdf_raw/2025/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31103 Yucatan — Xocchel

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `progresivo` · 2014\2014-12-31_2.pdf p.850-852
- **Vecino siguiente**: 2017 · `mixto` · 2016\2016-12-29_2.pdf p.835-837
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31104 Yucatan — Yaxcaba

#### 2016 · `schema_discontinuity`

- **Vecino previo**:  2015 · `mixto` · 2014\2014-12-31_2.pdf p.868-870
- **Vecino siguiente**: 2017 · `progresivo` · 2016\2016-12-29_2.pdf p.848-850
- **PDF candidato 2016**: `2016-01-04_1.pdf` (en `data/yucatan/pdf_raw/2016/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31105 Yucatan — Yaxkukul

#### 2021 · `schema_discontinuity`

- **Vecino previo**:  2020 · `tasa_unica` · 2019\2019-12-24_2.pdf p.1072-1075
- **Vecino siguiente**: 2022 · `otro_no_clasificado` · 2021\2021-12-31_3.pdf p.2447-2449
- **PDF candidato 2021**: `2021-01-04_1.pdf` (en `data/yucatan/pdf_raw/2021/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.
