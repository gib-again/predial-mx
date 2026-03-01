# Catálogo de esquemas de impuesto predial

Este documento registra los tipos de esquema de cálculo del impuesto predial
encontrados en las Leyes de Ingresos municipales.

## Tipos definidos

### `tarifa_millar`
- **Descripción**: Tasa(s) al millar sobre el valor catastral/fiscal, diferenciadas por tipo de predio.
- **Ejemplo**: Predio urbano = 2.3 al millar, predio rústico = 1.5 al millar.
- **Tabla**: `tabla_tarifa_millar`
- **Prevalencia**: Muy común en Coahuila.

### `progresivo`
- **Descripción**: Tabla por rangos de valor catastral. Cada rango tiene cuota fija + tasa marginal.
- **Ejemplo**: De $0.01 a $620,100: cuota $142.63 + 0.023% sobre excedente.
- **Tabla**: `tabla_progresiva`
- **Prevalencia**: Común en estados grandes (Jalisco, Estado de México).

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
- **Ejemplo**: Cuota fija + tasa al millar + recargo por uso comercial.
- **Tablas**: Múltiples, según lo que aplique.
- **Regla**: `comentarios` debe explicar la combinación.

### `desconocido`
- **Descripción**: Texto ambiguo, contradictorio o insuficiente para determinar el esquema.
- **Tablas**: Vacías.
- **Regla**: `esquema_valido = false`, `comentarios` debe explicar el problema.

## Registro de casos atípicos

_(Ir agregando conforme se procesen más estados)_
