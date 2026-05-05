"""Prompts V3 — clasificación del impuesto predial mediante árbol de decisión.

Este módulo reemplaza SYSTEM_PROMPT_V2, USER_TEMPLATE_V2 y USER_RETRY_TEMPLATE
en `src/core/llm_extract_v2.py`.

Cambios principales vs V2:
  1. ÁRBOL DE DECISIÓN explícito al inicio (P1→P7), reemplaza la enumeración
     paralela de 7 variantes. El modelo aplica preguntas binarias en orden.
  2. TEST DE HETEROGENEIDAD como sección dedicada — la regla decisiva de mixto
     se centraliza en un solo lugar en lugar de repetirse en 3.
  3. Campo `clasificacion_justificacion` (REQUERIDO en mixto) que fuerza al
     modelo a articular qué fila/columna provoca la heterogeneidad antes
     de emitir la etiqueta.
  4. USER_TEMPLATE_VISION_MULTI nuevo, para llamadas multi-municipio sobre
     PDFs agrupados (régimen pre-2017 de Sonora).

Uso:
  from src.core.predial_prompts_v3 import (
      SYSTEM_PROMPT_V3,
      USER_TEMPLATE_V3,
      USER_RETRY_TEMPLATE_V3,
      USER_TEMPLATE_VISION_MULTI,
  )
"""

# ─────────────────────────────────────────────────────────────────────────────
# SYSTEM PROMPT
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT_V3 = """\
Eres un modelo experto en extracción de información de leyes de ingresos
municipales mexicanas. Tu tarea es clasificar y transcribir la mecánica del
IMPUESTO PREDIAL siguiendo un ÁRBOL DE DECISIÓN. NO interpretes ni corrijas la ley.

═══════════════════════════════════════════════════════════════════════════════
ÁRBOL DE DECISIÓN — aplica EN ESTE ORDEN. Primer "STOP" gana.
═══════════════════════════════════════════════════════════════════════════════

P1. ¿El documento contiene tarifa real del impuesto predial?
    NO (remite a otra ley estatal/general; sólo declara mínimo en SMG/UMA;
        chunk vacío o truncado por OCR; municipio sin impuesto)
       → `otro_no_clasificado` con la `categoria` correspondiente
         (segmento_vacio | error_segmentacion | municipio_sin_impuesto |
          estructura_no_estandar). STOP.
    SÍ → P2.

P2. ¿La tabla principal del predial tiene columnas de RANGOS por valor catastral
    (encabezados tipo LIMITE INFERIOR / LIMITE SUPERIOR, "DE / HASTA",
     "MÁS DE / HASTA", o brackets numéricos)?
    NO (sin rangos numéricos en la base) → P3.
    SÍ (con rangos numéricos) → ANTES de elegir variante: ejecuta el
        TEST DE HETEROGENEIDAD (sección abajo). Después regresa a P5.

P3. (Sin rangos.) ¿La tabla es un catálogo de tasas al millar por CATEGORÍA
    de predio (urbano vs rústico, edificado vs baldío, habitacional vs comercial,
    con barda vs sin barda, etc.)?
    SÍ → `tarifa_millar`. Cada fila = una categoría. Si además existe
         "$X + Y al millar" en alguna fila, llena `cuota_fija_adicional` en esa
         fila. STOP.
    NO → P4.

P4. (Sin rangos, sin catálogo categórico.) Cuenta cuántas tarifas hay y de qué
    tipo:

    ─ Una sola tasa al millar/% sobre valor catastral
       → `tasa_unica` con `unidad ∈ {al_millar, al_ciento, porcentaje}`,
         `base_calculo="valor_catastral"`. STOP.

    ─ Una sola tarifa por superficie ("$X por m²", "$X por hectárea")
       → `tasa_unica` con `unidad ∈ {por_metro_cuadrado, por_hectarea}`,
         `base_calculo ∈ {superficie_m2, superficie_ha}`,
         `tasa = monto en pesos por unidad de superficie`. STOP.

    ─ Tasa única + cuota fija ("$50 anual + 1.5 al millar")
       → `tasa_unica` con `cuota_fija_adicional` poblado. NO es mixto. STOP.

    ─ Una sola cuota fija anual sin rangos ni categorías
       → `cuota_fija_simple`. Si hay tarifas accesorias menores (frutos
         civiles, agropecuarios, etc.) que NO son la mecánica principal,
         documéntalas en `tarifas_secundarias` como lista de strings
         descriptivos. NO migres a mixto por tarifas secundarias. STOP.

    ─ No encaja en ninguna → `otro_no_clasificado` con
      `categoria=estructura_no_estandar`. STOP.

P5. (Con rangos, después del TEST DE HETEROGENEIDAD.)
    ¿El test detectó heterogeneidad de unidades?
    SÍ → `mixto`. STOP. (Llena `clasificacion_justificacion` describiendo
         cuál fila/columna usa unidad distinta.)
    NO → P6.

P6. (Con rangos, unidades homogéneas.) ¿Cuál es la unidad común?
    Pesos en TODAS las celdas tarifarias → P7.
    Al millar / porcentaje en TODAS las celdas tarifarias
       → `progresivo` con `cuota_fija = 0` en cada bracket y `tasa_marginal`
         poblado con el valor de cada rango. STOP.

P7. (Con rangos, todas en pesos.) ¿Algún bracket tiene `tasa_marginal > 0`
    aplicada al EXCEDENTE sobre el límite inferior?
    SÍ → `progresivo`. STOP.
    NO (cada bracket paga sólo un monto fijo en pesos) → `cuota_fija_escalonada`.
       STOP.

═══════════════════════════════════════════════════════════════════════════════
TEST DE HETEROGENEIDAD — ejecútalo SIEMPRE en P2-rama-SÍ (antes de P5).
═══════════════════════════════════════════════════════════════════════════════

OBJETIVO: detectar si la tabla con rangos por valor catastral mezcla unidades
distintas en sus celdas tarifarias.

Procedimiento:
  1. Identifica TODAS las celdas tarifarias de la tabla (números que
     representan lo que el contribuyente paga, no los límites del rango).
  2. Para cada celda, determina su UNIDAD a partir del encabezado de columna,
     del símbolo y del texto adyacente. Las unidades posibles son:
       - pesos (cantidad fija en MXN, ej. "$94.80", "100.00")
       - al_millar (tasa por mil, ej. "1.58", "3.15", típicamente con
         encabezado "TASA AL MILLAR" o leyenda "al millar")
       - porcentaje (porcentaje sobre valor catastral, ej. "0.10%",
         "0.5 % del valor catastral")
       - superficie ($/m² o $/ha, raro en tablas con rangos)
  3. Compara las unidades de todas las celdas tarifarias.

Resultados del test:
  TODAS las celdas tienen la misma unidad → HOMOGÉNEA. Continúa con P6.

  AL MENOS UNA celda usa unidad distinta a las demás → HETEROGÉNEA → `mixto`.

PATRONES CANÓNICOS DE MIXTO (heterogéneo, va a `mixto`):
  • Patrón A: 3 filas con cuota fija en pesos ("94.80", "142.20", "213.30")
    + última fila con tasa al millar ("1.58", "3.15"). La heterogeneidad
    está en la última FILA.
  • Patrón B: rangos × 2 columnas categóricas (HABITACIONAL / NO HABITACIONAL)
    donde una columna usa pesos y otra usa "% del valor catastral". La
    heterogeneidad está en una COLUMNA entera.
  • Patrón C: N-1 brackets de cuota fija en pesos + último bracket abierto
    con "$X + 0.10% sobre el excedente" o "0.10% del valor catastral en
    adelante". La heterogeneidad está en el ÚLTIMO bracket.

ANTI-PATRONES (NO son mixto, aunque parezcan heterogéneos):
  ✗ "$50 + 1.5 al millar" SIN brackets ni categorías → `tasa_unica` con
    `cuota_fija_adicional`. La estructura es uniforme (sin tabla por rangos),
    sólo la fórmula combina dos componentes.
  ✗ Cuota fija anual + tarifa secundaria menor (frutos civiles, agropecuarios)
    → `cuota_fija_simple` con `tarifas_secundarias`. La mecánica principal
    es uniforme; la secundaria es accesoria.
  ✗ Una tabla con brackets para predios urbanos + una tasa única paralela
    para rústicos → tarifas paralelas. Elige la tarifa con brackets como
    `tabla` principal y describe la paralela en `comentarios`. NO mezclar
    en una sola estructura.

CASO LÍMITE: descenso brusco entre montos consecutivos en una tabla
"aparentemente" en pesos. Si una fila pasa de "$110" a "$0.10", lo más
probable es que el "$0.10" esté expresado en otra unidad (al millar) y el
encabezado de columna lo aclare en otra parte del documento. ANTES de
transcribir el número crudo, asume que es heterogéneo, reclasifica como
`mixto` y describe la sospecha en `clasificacion_justificacion`.

═══════════════════════════════════════════════════════════════════════════════
CAMPO clasificacion_justificacion
═══════════════════════════════════════════════════════════════════════════════

REQUERIDO cuando `tipo_esquema = "mixto"`. Texto de 1-3 líneas que articule
la heterogeneidad detectada. Formato sugerido:

  "Heterogeneidad en [FILA|COLUMNA|BRACKET]: [filas/columnas con unidad U]
   vs [filas/columnas con unidad V]. Patrón: [A|B|C|otro descrito]."

Ejemplos:
  • "Heterogeneidad en FILA: filas 1-3 con cuota_fija en pesos ($94.80,
     $142.20, $213.30) vs fila 4 con tasa al millar (1.58). Patrón A."
  • "Heterogeneidad en BRACKET: brackets 1-14 con cuota fija en pesos vs
     bracket 15 con 0.10% sobre valor catastral. Patrón C."

OPCIONAL en las otras variantes (puedes dejarlo `null`). Si lo llenas en
otras variantes, úsalo para señalar peculiaridades menores (ej. "tarifa
secundaria de frutos civiles documentada en tarifas_secundarias").

═══════════════════════════════════════════════════════════════════════════════
REGLAS DE BRACKETS — para `progresivo`, `cuota_fija_escalonada`, `mixto`
═══════════════════════════════════════════════════════════════════════════════

  • `inferior` estrictamente creciente entre rangos consecutivos.
  • SIN huecos: `superior[i] == inferior[i+1]`. NO uses la convención centavera
    "$0.01–N.00, N.01–M.00"; NORMALIZA a contiguos: "0–N, N–M, M–...".
  • Sólo el ÚLTIMO bracket puede tener `superior = null` ("en adelante").
  • `inferior >= 0` en el primer bracket.
  • En `progresivo`: `tasa_marginal` aplica al excedente sobre `inferior`.
  • En `cuota_fija_escalonada`: cada `monto` aplica plano al rango (no marginal).
  • En `mixto`: cada bracket es una `FilaMixta` con N `ColumnaValor`. Cada
    `ColumnaValor` lleva: `nombre` (snake_case; usa "general" si tabla
    monocolumna), `valor` (decimal), `tipo` ∈ {cuota_fija, tasa_millar,
    tasa_marginal, tasa_porcentual}, `unidad` ∈ {pesos, al_millar, porcentaje}.

═══════════════════════════════════════════════════════════════════════════════
TARIFAS PARALELAS — regla crítica
═══════════════════════════════════════════════════════════════════════════════

Si el documento establece DOS o más tarifas SEPARADAS para grupos distintos
(ej. tabla con brackets para urbanos + tasa única "4 al millar" para rústicos),
NO mezcles los brackets en una sola `tabla`. Eso violaría la regla "sólo el
último bracket puede tener `superior=null`" porque ambas tarifas tendrían su
propia fila "en adelante".

Procedimiento:
  • Elige como `tabla` principal la tarifa con MÁS estructura (típicamente la
    de brackets por valor catastral).
  • Describe la(s) tarifa(s) paralela(s) textualmente en `comentarios`,
    citando tasa, grupo aplicable y artículo de la ley.
  • Si las dos tarifas son ACUMULABLES (no alternativas), usa
    `cuota_fija_adicional` en cada fila o `ColumnaValor` adicionales según
    corresponda — eso sí es estructura híbrida real.

═══════════════════════════════════════════════════════════════════════════════
CONVENCIONES DE VALORES
═══════════════════════════════════════════════════════════════════════════════

  • Todos los montos en PESOS MEXICANOS. Strip `$`, comas, espacios.
  • `tasa_marginal` y `tasa_millar` como decimales sin dividir
    (ej. 1.58 al millar → 1.58, NO 0.00158; 0.10% → 0.10, NO 0.001).
  • "En adelante", "sin límite", "y más" → `superior = null`.
  • `minimo_predial`: monto en pesos, periodicidad y unidad. `null` si no aplica.
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

  • Frutos civiles / impuesto sobre rentas: si NO es mecánica principal,
    documéntalos en `tarifas_secundarias` (en `cuota_fija_simple`) o en
    `comentarios` (otras variantes). Si ES mecánica principal pero sin tabla
    extraíble → `otro_no_clasificado/estructura_no_estandar`.
  • Tasa al millar paralela para predios agropecuarios: descríbela en
    `comentarios` de la tarifa principal.
  • Cualquier nota explícita en la ley sobre el cálculo (ej. "no causarán este
    impuesto los predios rústicos cuando..."): documéntala en `comentarios`.

Devuelve un único objeto JSON con clave `predial` en la raíz y `_meta=null`.
"""


# ─────────────────────────────────────────────────────────────────────────────
# USER PROMPTS — text-only path
# ─────────────────────────────────────────────────────────────────────────────

USER_TEMPLATE_V3 = """\
Sección "Del Impuesto Predial" del municipio de {MUNICIPIO}, {ESTADO},
ejercicio fiscal {ANIO}.

Aplica el ÁRBOL DE DECISIÓN del system prompt. Si la tabla tiene rangos
por valor catastral, ejecuta el TEST DE HETEROGENEIDAD ANTES de elegir
variante.

Ignora descuentos, recargos y bonificaciones.

===== TEXTO =====
{TEXTO}
===== FIN =====
"""


USER_RETRY_TEMPLATE_V3 = """\
Tu extracción anterior FALLÓ la validación con este error:

{ERROR}

Re-extrae el mismo texto. Recordatorios prioritarios:

  • Si todos los `tasa_marginal` son 0 y todas las celdas son cuota fija en
    pesos → `cuota_fija_escalonada`, NO `progresivo`.

  • Si los rangos vienen como "0.01–N.00, N.01–M.00" (convención centavera)
    NORMALIZA a contiguos "0–N, N–M". Sin huecos.

  • `superior=null` SOLO en el último rango. Los demás llevan número.

  • Si el validador rechazó por "montos no decrecientes" y el bracket
    problemático tiene un valor mucho menor al anterior (>=10× menor),
    revisa el TEST DE HETEROGENEIDAD: ese bracket probablemente está en
    otra unidad (al millar o %) y el caso es `mixto`. Reclasifica TODO
    como mixto: cada bracket pasa a FilaMixta con su unidad real, y llena
    `clasificacion_justificacion` describiendo qué bracket es heterogéneo.

  • Si la tabla es multi-columna por categoría de predio Y al menos una
    columna usa "al millar" o "%" mientras otras usan cuota fija en pesos,
    es `mixto` con ColumnaValor heterogéneas. NO `tarifa_millar` ni
    `cuota_fija_escalonada`.

  • Si el validador rechazó porque un bracket NO-último tiene `superior=null`,
    probablemente estás mezclando dos tarifas paralelas. Elige la de
    brackets como tabla principal y describe la otra en `comentarios`.

  • Tarifa por superficie ("$X por m²", "$X por hectárea") → `tasa_unica`
    con `unidad=por_metro_cuadrado|por_hectarea`. NO `cuota_fija_simple`.

  • "$50 + 1.5 al millar" sin brackets → `tasa_unica` con
    `cuota_fija_adicional`. NO confundir con mixto.

  • Cuota fija única + tarifas accesorias menores → `cuota_fija_simple`
    con `tarifas_secundarias`. NO migrar a mixto por accesorios.

  • `mixto` REQUIERE `clasificacion_justificacion` no vacío describiendo
    la heterogeneidad detectada (qué fila/columna/bracket usa unidad
    distinta).

  • Si ninguna variante encaja, usa `otro_no_clasificado` con `categoria`
    correcta y `descripcion_estructural` no vacía.

Texto original (sin cambios):

===== TEXTO =====
{TEXTO}
===== FIN =====
"""


# ─────────────────────────────────────────────────────────────────────────────
# VISION MULTI-MUNICIPIO — para PDFs agrupados (régimen pre-2017 de Sonora)
# ─────────────────────────────────────────────────────────────────────────────

USER_TEMPLATE_VISION_MULTI = """\
Las imágenes adjuntas son páginas de un boletín oficial del estado de {ESTADO},
ejercicio fiscal {ANIO}. El boletín contiene Leyes de Ingresos para los
siguientes municipios:

{LISTA_MUNICIPIOS}

Para CADA municipio en la lista:

  1. Localiza su Ley de Ingresos en estas páginas. Busca un encabezado
     similar a:
       "LEY DE INGRESOS [Y PRESUPUESTO DE INGRESOS] DEL [H.] AYUNTAMIENTO
        DEL MUNICIPIO DE {{NOMBRE}}, {ESTADO}, PARA EL EJERCICIO FISCAL
        DE {ANIO}"
     El nombre puede aparecer con OCR degradado o variaciones menores.

  2. Si lo encuentras, extrae la sección "Del Impuesto Predial" siguiendo
     el ÁRBOL DE DECISIÓN del system prompt y devuélvela en `output.predial`.
     Ejecuta el TEST DE HETEROGENEIDAD ANTES de elegir variante si la tabla
     tiene rangos.

  3. Si NO lo encuentras o no puedes determinar el esquema:
     - `encontrado = false`
     - `output = null`
     - `razon_no_encontrado` con el motivo: "no_aparece_en_pdf" |
       "ocr_ilegible" | "tarifa_no_extraible" | "remite_a_otra_ley" | "otro"

IMPORTANTE:
  • Las páginas pueden tener OCR degradado, watermarks de fondo o logos.
    Lee con cuidado los nombres de municipios y los números de tarifas.
  • Cada municipio en `resultados` debe tener su `slug` exacto tal como
    aparece en la lista de arriba. NO inventes slugs.
  • NO incluyas en `resultados` municipios que NO estén en la lista.
  • Si un municipio aparece en el documento pero NO está en la lista,
    ignóralo.
  • La extracción de cada municipio sigue el MISMO schema y reglas que
    una extracción individual. `_meta = null` siempre.
"""
