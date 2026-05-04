# Auditoría — localizar sección predial faltante

Acompaña a `output/audit_pendiente.csv`.

**Total de huecos a auditar: 0**


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
