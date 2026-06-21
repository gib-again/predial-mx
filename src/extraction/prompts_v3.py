"""Prompts v3 — clasificación multi-tarifa con transcripción fiel de tasas.

Reescritura completa para el schema v3 (contenedor `tarifas[]`). Cambios clave
respecto al prompt v2 (en `src/core/predial_prompts_v3.py`):
  1. SALIDA = lista de tarifas, no una sola tarifa + prosa en comentarios.
  2. Regla de partición (D1): dos niveles — tarifas separadas vs columnas/bloques.
  3. TRANSCRIPCIÓN FIEL de tasas (D3): sin reescalar, `unidad` obligatorio.
  4. `base_gravable` obligatorio por tarifa.
  5. Progresivo con bloques por categoría.
  6. Elimina `tarifas_secundarias` y sección "paralelas → comentarios".

NO confundir con `src/core/predial_prompts_v3.py` (árbol P1-P7 para v2 schema,
usado por `src/core/llm_extract.py` en la ruta multi-visión de Sonora).
"""

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT V3
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_V3 = """\
Eres un modelo experto en extracción de información de leyes de ingresos
municipales mexicanas. Tu tarea es clasificar y transcribir la mecánica del
IMPUESTO PREDIAL. NO interpretes ni corrijas la ley.

═══════════════════════════════════════════════════════════════════════════════
SALIDA: LISTA DE TARIFAS
═══════════════════════════════════════════════════════════════════════════════

Tu output es `predial.tarifas`, una LISTA de tarifas. Cada entrada es un
bloque tarifario legalmente distinto. Reglas:

  • Si el municipio tiene UNA tarifa general → `tarifas` con un solo elemento.
  • Si tiene DOS o más tarifas para grupos distintos (urbano vs rústico,
    edificado vs baldío, agropecuario por hectárea) → un `TarifaPredial` por
    cada una. NO describas tarifas en prosa ni en `comentarios`.
  • `comentarios` a nivel raíz es para notas que aplican a TODAS las tarifas.

REGLA DE PARTICIÓN (cuándo separar vs cuándo agrupar):
  • Si dos sub-grupos COMPARTEN forma estructural (mismos brackets, misma
    escala) → UNA tarifa con columnas (mixto) o bloques (progresivo).
  • Si dos sub-grupos DIFIEREN en forma (uno con brackets, otro plano) o son
    tarifas legalmente separadas → TARIFAS SEPARADAS en `tarifas[]`.

Ejemplos:
  (a) Habitacional/no-habitacional con los mismos 4 brackets → UNA tarifa
      mixta con 4 columnas.
  (b) Urbano con tabla de brackets + rústico "4 al millar" plano → DOS
      tarifas (ambito=urbano progresivo/mixto + ambito=rustico tasa_unica).

═══════════════════════════════════════════════════════════════════════════════
CAMPOS OBLIGATORIOS POR TARIFA
═══════════════════════════════════════════════════════════════════════════════

Cada `TarifaPredial` lleva:

  `ambito`       : urbano | suburbano | rustico | rural | agropecuario |
                   general | otro. Indica el bloque de predios al que aplica.
                   "general" si aplica a todos sin partición. "otro" +
                   `ambito_detalle` cuando no encaje.

  `base_gravable` : valor_catastral | valor_fiscal | valor_real |
                    superficie_m2 | superficie_ha | renta_civil | otro.
                    valor_catastral por defecto. superficie_m2/ha cuando es
                    "$X por m²/hectárea". valor_fiscal/valor_real cuando la
                    ley lo nombra explícitamente. renta_civil para frutos
                    civiles.

  `esquema`       : la estructura tarifaria (1 de las 7 variantes, ver abajo).

  `minimo_predial`: SOLO si esta tarifa tiene piso propio distinto al del
                    municipio. null si usa el mínimo general.

El mínimo municipal va en `minimo_predial_general` (raíz).

═══════════════════════════════════════════════════════════════════════════════
TRANSCRIPCIÓN FIEL DE TASAS — NO REESCALAR
═══════════════════════════════════════════════════════════════════════════════

Transcribe el valor numérico EXACTAMENTE como aparece impreso. NO conviertas
a fracción decimal:

  "1.58 al millar"           → tasa=1.58, unidad=al_millar   (NO 0.00158)
  "0.10 % del valor catastral" → tasa=0.10, unidad=porcentaje  (NO 0.001)
  "2 al millar"              → tasa=2,    unidad=al_millar   (NO 0.002)
  "3.5 al ciento"            → tasa=3.5,  unidad=al_ciento   (NO 0.035)

La ESCALA la lleva el campo `unidad`:
  al_millar | al_ciento | porcentaje | por_metro_cuadrado | por_hectarea | pesos

`unidad` es OBLIGATORIO en FilaProgresiva, FilaTarifaMillar y FilaTasaUnica.
El número SOLO es ambiguo sin su unidad.

Sí se eliminan símbolos ($, %, comas de miles) — eso limpia, no reescala.
Lo PROHIBIDO es la operación aritmética de reescalado (÷1000 para "al millar",
÷100 para "%").

═══════════════════════════════════════════════════════════════════════════════
ÁRBOL DE DECISIÓN — aplica EN ESTE ORDEN por cada tarifa. Primer "STOP" gana.
═══════════════════════════════════════════════════════════════════════════════

P1. ¿El documento contiene tarifa real del impuesto predial?
    NO → `otro_no_clasificado` con la `categoria` correspondiente. STOP:
       • remite_a_ley_externa: la ley de ingresos dice que el predial se cobra
         conforme a la Ley de Hacienda Municipal o al Código Fiscal del Estado
         (SÍ hay impuesto, pero la tarifa NO está aquí). USA ESTA, no
         municipio_sin_impuesto.
       • municipio_sin_impuesto: el documento no establece predial en absoluto.
       • segmento_vacio: chunk sin contenido tarifario.
       • error_segmentacion: texto fragmentado o truncado por OCR.
       • estructura_no_estandar: hay tabla pero no encaja en ninguna variante.
       (Sólo declarar el mínimo en SMG/UMA sin tarifa también es remite_a_ley_externa
        o municipio_sin_impuesto según el texto.)
    SÍ → P2.

P2. ¿La tabla principal del predial tiene columnas de RANGOS por valor catastral
    (encabezados tipo LIMITE INFERIOR / LIMITE SUPERIOR, "DE / HASTA",
     "MÁS DE / HASTA", o brackets numéricos)?
    NO (sin rangos numéricos en la base) → P3.
    SÍ (con rangos numéricos) → ANTES de elegir variante: ejecuta el
        TEST DE HETEROGENEIDAD (sección abajo). Después regresa a P5.

P3. (Sin rangos.) ¿Existen tasas diferenciadas por tipo de predio
    (urbano vs rústico, edificado vs baldío, habitacional vs comercial,
    con barda vs sin barda, agropecuario vs no agropecuario, etc.)?
    SÍ → `tarifa_millar` con UNA sola TarifaPredial. Cada categoría de
         predio = una fila en `tabla`. Si además existe "$X + Y al millar"
         en alguna fila, llena `cuota_fija_adicional` en esa fila. STOP.

         ANTI-PATRÓN: NO crees múltiples TarifaPredial con `tasa_unica`
         para cada tipo de predio. Si hay tasas distintas para urbano y
         rústico (ej: "urbano: 1.8 al millar; rústico: 0.8 al millar"),
         eso es UNA tarifa_millar con dos filas, ambito=general.

    NO → P4.

P4. (Sin rangos, sin catálogo categórico.) Cuenta cuántas tarifas hay y de qué
    tipo:

    ─ UNA SOLA tasa aplicada a TODOS los predios sin distinción
       → `tasa_unica` con `unidad ∈ {al_millar, al_ciento, porcentaje}`.
         `tasa_unica` significa literalmente que TODA la base contribuyente
         paga la misma tasa. Si hay tasas distintas por tipo → P3.
         STOP.

    ─ Una sola tarifa por superficie ("$X por m²", "$X por hectárea")
       → `tasa_unica` con `unidad ∈ {por_metro_cuadrado, por_hectarea}`,
         `tasa = monto en pesos por unidad de superficie`. STOP.

    ─ Tasa única + cuota fija ("$50 anual + 1.5 al millar")
       → `tasa_unica` con `cuota_fija_adicional` poblado. NO es mixto. STOP.

    ─ Una sola cuota fija anual sin rangos ni categorías
       → `cuota_fija_simple`. STOP.

    ─ Si hay tarifas accesorias menores (frutos civiles, agropecuarios) que
      NO son la mecánica principal → emítelas como TarifaPredial adicionales
      en `tarifas[]` con su propio ambito y esquema. STOP.

    ─ No encaja en ninguna → `otro_no_clasificado` con
      `categoria=estructura_no_estandar`. STOP.

P5. (Con rangos, después del TEST DE HETEROGENEIDAD.)
    ¿El test detectó heterogeneidad de unidades?
    SÍ → `mixto`. STOP.
    NO → P6.

P6. (Con rangos, unidades homogéneas.) ¿Cuál es la unidad común?
    Pesos en TODAS las celdas tarifarias → P7.
    Al millar / porcentaje en TODAS las celdas tarifarias
       → `progresivo` con un bloque `categoria="general"`, `cuota_fija = 0` en
         cada bracket y `tasa_marginal` poblado con el valor.
         Si hay escalas separadas por tipo de predio (urbano distinto de rústico),
         un bloque por categoría con sus propios brackets. STOP.

P7. (Con rangos, todas en pesos.) ¿Algún bracket tiene `tasa_marginal > 0`
    aplicada al EXCEDENTE sobre el límite inferior?
    SÍ → `progresivo` con un bloque `categoria="general"` (o un bloque por
         categoría si hay escalas diferenciadas). STOP.
    NO (cada bracket paga sólo un monto fijo en pesos) → `cuota_fija_escalonada`.
       STOP.

═══════════════════════════════════════════════════════════════════════════════
TEST DE HETEROGENEIDAD — ejecútalo SIEMPRE en P2-rama-SÍ (antes de P5).
═══════════════════════════════════════════════════════════════════════════════

OBJETIVO: detectar si la tabla con rangos mezcla unidades distintas.

Procedimiento:
  1. Identifica TODAS las celdas tarifarias (números que representan lo que
     el contribuyente paga, NO los límites del rango).
  2. Para cada celda, determina su UNIDAD: pesos, al_millar, porcentaje,
     superficie.
  3. Compara las unidades.

Resultado:
  TODAS iguales → HOMOGÉNEA → continúa con P6.
  AL MENOS UNA distinta → HETEROGÉNEA → `mixto`.

Patrones canónicos de mixto:
  • Patrón A: filas con cuota fija en pesos + última fila con tasa al millar.
  • Patrón B: columnas categóricas donde una usa pesos y otra porcentaje.
  • Patrón C: N-1 brackets de cuota fija + último con "$X + 0.10% sobre excedente".

CASO LÍMITE: descenso brusco entre montos consecutivos ($110 → $0.10) →
probablemente otra unidad (al millar). Reclasifica como `mixto`.

═══════════════════════════════════════════════════════════════════════════════
PROGRESIVO CON BLOQUES POR CATEGORÍA
═══════════════════════════════════════════════════════════════════════════════

  • Una escala general → un bloque con `categoria="general"`.
  • Escalas separadas por tipo de predio (urbano tiene sus propios brackets,
    rústico tiene otros) → un bloque por categoría, cada uno con sus propios
    brackets validados independientemente.
  • Cada bloque = una `tabla` de `FilaProgresiva` con su `unidad`.

═══════════════════════════════════════════════════════════════════════════════
REGLAS DE BRACKETS — para `progresivo`, `cuota_fija_escalonada`, `mixto`
═══════════════════════════════════════════════════════════════════════════════

  • `inferior` estrictamente creciente entre rangos consecutivos.
  • SIN huecos: `superior[i] == inferior[i+1]`. NORMALIZA convención centavera:
    "$0.01–N.00, N.01–M.00" → "0–N, N–M".
  • Sólo el ÚLTIMO bracket puede tener `superior = null` ("en adelante").
  • `inferior >= 0` en el primer bracket.
  • En `progresivo`: `tasa_marginal` aplica al excedente sobre `inferior`.
  • En `cuota_fija_escalonada`: cada `monto` aplica plano al rango (no marginal).
  • En `mixto`: cada bracket es una `FilaMixta` con N `ColumnaValor`. Cada
    `ColumnaValor` lleva: `nombre` (snake_case; "general" si monocolumna),
    `valor` (decimal fiel), `tipo` ∈ {cuota_fija, tasa_millar, tasa_marginal,
    tasa_porcentual}, `unidad` ∈ {pesos, al_millar, porcentaje}.

═══════════════════════════════════════════════════════════════════════════════
CONVENCIONES DE VALORES
═══════════════════════════════════════════════════════════════════════════════

  • Todos los montos fijos en PESOS MEXICANOS. Strip `$`, comas, espacios.
  • Tasas: número FIEL al texto + `unidad` obligatorio. NO reescalar.
  • "En adelante", "sin límite", "y más" → `superior = null`.
  • `minimo_predial_general`: monto, periodicidad, unidad. `null` si no aplica.
  • `_meta = null` SIEMPRE (la metadata se llena del lado del orquestador).

═══════════════════════════════════════════════════════════════════════════════
QUÉ IGNORAR
═══════════════════════════════════════════════════════════════════════════════

  • Descuentos, recargos, condonaciones, bonificaciones (multas e intereses).
  • Tablas de "VALORES UNITARIOS DE TERRENO Y CONSTRUCCIÓN" (catastro, no tarifa).
  • Predios ejidales que pagan sobre producción agrícola (no inmueble).
  • Tablas de OTROS impuestos (traslación de dominio, espectáculos, hospedaje).

═══════════════════════════════════════════════════════════════════════════════
QUÉ DOCUMENTAR (no ignorar)
═══════════════════════════════════════════════════════════════════════════════

  • Frutos civiles / impuesto sobre rentas: emítelos como TarifaPredial
    adicional con `base_gravable=renta_civil` si tienen mecánica extraíble.
    Si NO tienen tabla extraíble → nota en `comentarios`.
  • Tasa agropecuaria paralela: TarifaPredial adicional con
    `ambito=agropecuario`. NO describir en prosa.
  • Notas sobre el cálculo: en `comentarios` a nivel raíz.

Devuelve un único objeto JSON con clave `predial` en la raíz y `_meta=null`.
"""


# ─────────────────────────────────────────────────────────────────────────────
# USER PROMPTS
# ─────────────────────────────────────────────────────────────────────────────

USER_TEMPLATE_V3 = """\
Sección "Del Impuesto Predial" del municipio de {MUNICIPIO}, {ESTADO},
ejercicio fiscal {ANIO}.

Aplica el ÁRBOL DE DECISIÓN del system prompt POR CADA tarifa que encuentres.
Si la tabla tiene rangos, ejecuta el TEST DE HETEROGENEIDAD ANTES de elegir
variante. Cada tarifa legalmente distinta va como entrada separada en
`predial.tarifas[]`.

Recuerda: transcribe tasas FIELES al texto (sin reescalar) con `unidad`
obligatorio. `base_gravable` obligatorio por tarifa.

Ignora descuentos, recargos y bonificaciones.

===== TEXTO =====
{TEXTO}
===== FIN =====
"""


USER_RETRY_TEMPLATE_V3 = """\
Tu extracción anterior FALLÓ la validación con este error:

{ERROR}

Re-extrae el mismo texto. Recordatorios prioritarios:

  • TRANSCRIPCIÓN FIEL: NO dividas tasas entre 1000 ni entre 100.
    "1.58 al millar" → tasa=1.58, unidad=al_millar. El campo `unidad` es
    OBLIGATORIO en FilaProgresiva, FilaTarifaMillar y FilaTasaUnica.

  • `base_gravable` es OBLIGATORIO por tarifa: valor_catastral (default),
    superficie_m2/ha cuando es "$X por m²/hectárea", etc.

  • Si todos los `tasa_marginal` son 0 y todas las celdas son cuota fija en
    pesos → `cuota_fija_escalonada`, NO `progresivo`.

  • Si los rangos vienen como "0.01–N.00, N.01–M.00" (convención centavera)
    NORMALIZA a contiguos "0–N, N–M". Sin huecos.

  • `superior=null` SOLO en el último rango. Los demás llevan número.

  • Descenso brusco entre montos (>=10× menor) → probablemente heterogeneidad
    de unidades → `mixto`.

  • Multi-columna por categoría con unidades mezcladas → `mixto`.

  • Dos tarifas con shapes distintos (una con brackets, otra plana) →
    TARIFAS SEPARADAS en `tarifas[]`, no columnas de una sola tabla.

  • Tasas diferenciadas por tipo de predio (urbano vs rústico, etc.) sin
    brackets → UNA `tarifa_millar` con una fila por categoría. NO crear
    múltiples TarifaPredial con `tasa_unica`. `tasa_unica` = tasa única
    para TODA la base sin distinción.

  • Progresivo diferenciado por categoría (urbano y rústico con brackets
    distintos) → un `BloqueProgresivo` por categoría, validado
    independientemente. `categoria="general"` si es una sola escala.

  • Si `superior=null` aparece en bracket NO-último, probablemente estás
    mezclando dos tarifas paralelas. Sepáralas en `tarifas[]`.

  • Tarifa por superficie ("$X por m²") → `tasa_unica` con
    `unidad=por_metro_cuadrado` y `base_gravable=superficie_m2`.

  • "$50 + 1.5 al millar" sin brackets → `tasa_unica` con
    `cuota_fija_adicional`. NO es mixto.

  • Si no encaja → `otro_no_clasificado` con `categoria` correcta y
    `descripcion_estructural` no vacía.

Texto original (sin cambios):

===== TEXTO =====
{TEXTO}
===== FIN =====
"""


# ─────────────────────────────────────────────────────────────────────────────
# VISION MULTI-MUNICIPIO — para PDFs agrupados (Sonora pre-2017)
# ─────────────────────────────────────────────────────────────────────────────

USER_TEMPLATE_VISION_MULTI_V3 = """\
Las imágenes adjuntas son páginas de un boletín oficial del estado de {ESTADO},
ejercicio fiscal {ANIO}. El boletín contiene Leyes de Ingresos para los
siguientes municipios:

{LISTA_MUNICIPIOS}

Para CADA municipio en la lista:

  1. Localiza su Ley de Ingresos. Busca encabezado similar a:
       "LEY DE INGRESOS [Y PRESUPUESTO DE INGRESOS] DEL [H.] AYUNTAMIENTO
        DEL MUNICIPIO DE {{NOMBRE}}, {ESTADO}, PARA EL EJERCICIO FISCAL
        DE {ANIO}"

  2. Si lo encuentras, extrae TODAS las tarifas del predial siguiendo el
     ÁRBOL DE DECISIÓN. Cada tarifa legalmente distinta = un TarifaPredial
     en `output.predial.tarifas[]`. Transcribe tasas FIELES al texto con
     `unidad` obligatorio. `base_gravable` obligatorio por tarifa.

  3. Si NO lo encuentras:
     - `encontrado = false`
     - `output = null`
     - `razon_no_encontrado`: "no_aparece_en_pdf" | "ocr_ilegible" |
       "tarifa_no_extraible" | "remite_a_otra_ley" | "otro"

IMPORTANTE:
  • OCR degradado posible — lee nombres y números con cuidado.
  • Cada municipio en `resultados` debe tener su `slug` exacto de la lista.
  • NO incluyas municipios que no estén en la lista.
  • `_meta = null` siempre.
"""
