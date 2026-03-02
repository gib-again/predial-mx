# Catálogo de esquemas de impuesto predial

Este documento registra los tipos de esquema de cálculo del impuesto predial
encontrados en las Leyes de Ingresos municipales.

## Tipos definidos

### `tarifa_millar`
- **Descripción**: Tasa(s) al millar sobre el valor catastral/fiscal, diferenciadas por tipo de predio.
- **Ejemplo**: Predio urbano = 2.3 al millar, predio rústico = 1.5 al millar.
- **Tabla**: `tabla_tarifa_millar`
- **Prevalencia**: Muy común en Coahuila, Guanajuato.
- **Variante con cuota fija adicional** *(v3)*: Algunos municipios cobran una cuota fija
  ADEMÁS de la tasa al millar (ej: "$150 más 3.5 al millar sobre el valor catastral").
  Esto se captura en el campo `cuota_fija_adicional` de cada fila de `tabla_tarifa_millar`.
  NO convierte el esquema en "mixto" — sigue siendo `tarifa_millar`.

### `progresivo`
- **Descripción**: Tabla por rangos de valor catastral. Cada rango tiene cuota fija + tasa marginal.
- **Ejemplo**: De $0.01 a $620,100: cuota $142.63 + 0.023% sobre excedente.
- **Tabla**: `tabla_progresiva`
- **Prevalencia**: Común en estados grandes (Jalisco, Estado de México, Chihuahua, Sinaloa, Tabasco).

### `tasa_unica`
- **Descripción**: Una sola tasa aplicable a todos los predios por igual.
- **Ejemplo**: 0.3% sobre valor catastral.
- **Tabla**: `tabla_tasa_unica`
- **Prevalencia**: Municipios pequeños o rurales.

### `cuota_fija`
- **Descripción**: Monto fijo por predio, sin referencia al valor catastral.
- **Ejemplo**: $350 anuales por predio.
- **Tabla**: `tabla_cuota_fija`
- **Prevalencia**: Municipios muy rurales.

### `mixto`
- **Descripción**: Combinación de los anteriores que no encaja limpiamente en un solo tipo.
- **Ejemplo**: Tabla multi-columna por rango × tipo de predio (cuota fija en rangos bajos,
  tasa al millar en rangos altos, diferenciada por habitacional/no habitacional).
- **Tablas**: `tabla_mixta_rango` + otras según aplique.
- **Regla**: `comentarios` debe explicar la combinación.
- **Prevalencia**: Coahuila (Piedras Negras, etc.), Querétaro.

### `desconocido`
- **Descripción**: Texto ambiguo, contradictorio o insuficiente para determinar el esquema.
- **Tablas**: Vacías.
- **Regla**: `esquema_valido = false`, `comentarios` debe explicar el problema.

## Registro de casos atípicos

### Tarifa al millar con cuota fija adicional
- **Encontrado en**: Guanajuato (varios municipios)
- **Descripción**: La ley establece una tasa al millar + un monto fijo adicional por predio.
- **Schema**: `tabla_tarifa_millar[].cuota_fija_adicional` (campo nullable, agregado en v3)
- **Ejemplo**: "El impuesto se determinará aplicando 3.5 al millar sobre el valor catastral,
  más una cuota fija de $150.00 anuales."
- **Decisión**: Sigue siendo `tarifa_millar`, NO es `mixto`.

### Predios de extracción ejidal (fuera de alcance)
- **Encontrado en**: Guanajuato, Sinaloa
- **Descripción**: Predios ejidales que pagan conforme a un porcentaje del valor de su
  producción anual comercializada (ej: "3% al valor de producción anual").
- **Decisión**: IGNORAR — la base de datos solo cubre esquemas basados en valor catastral/fiscal.
- **Instrucción al LLM**: Si coexiste con un esquema válido, extraer solo el esquema válido.
  Si es el único mecanismo → `desconocido` con comentario explicativo.

### Frutos civiles (fuera de alcance)
- **Encontrado en**: Varios estados
- **Descripción**: Impuesto sobre rentas de inmuebles. NO es impuesto predial.
- **Decisión**: IGNORAR siempre.

### Derechos catastrales (fuera de alcance)
- **Encontrado en**: Varios estados
- **Descripción**: Cobros por servicios catastrales, avalúos, expedición de constancias.
- **Decisión**: IGNORAR — no son parte del impuesto predial.