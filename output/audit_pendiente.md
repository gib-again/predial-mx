# Auditoría — localizar sección predial faltante

Acompaña a `output/audit_pendiente.csv`.

**Total de huecos a auditar: 3**

- `schema_discontinuity`: 2
- `edge`: 1

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

### 31072 Yucatan — Suma

#### 2011 · `schema_discontinuity`

- **Vecino previo**:  2010 · `mixto`
- **Vecino siguiente**: 2013 · `mixto`
- **PDF candidato 2011**: `2011-01-03.pdf` (en `data/yucatan/pdf_raw/2011/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

#### 2012 · `schema_discontinuity`

- **Vecino previo**:  2010 · `mixto`
- **Vecino siguiente**: 2013 · `mixto`
- **PDF candidato 2012**: `2012-01-09.pdf` (en `data/yucatan/pdf_raw/2012/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.

### 31073 Yucatan — Tahdziu

#### 2025 · `edge`

- **Vecino previo**:  2024 · `otro_no_clasificado`
- **PDF candidato 2025**: (no hay PDFs en `data/yucatan/pdf_raw/2025/`)

Llena en CSV: `estatus`, `pdf_objetivo`, `paginas`, `notas`.
