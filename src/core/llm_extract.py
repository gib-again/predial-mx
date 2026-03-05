"""
Extracción de datos de predial mediante LLM (OpenAI) con Structured Output.

Tres modos de operación:

  1. SÍNCRONO (default): Chat Completions API con structured output + prompt caching.
     El JSON Schema se aplica token a token → output siempre tiene la forma correcta.
     Fallback progresivo: TXT primero → si inválido, PDF vía visión (+1 página).
     Ideal para pruebas o corridas pequeñas (<50 archivos).

  2. BATCH (--batch): Genera archivo JSONL para la Batch API de OpenAI (50% descuento).
     Solo usa TXT (paso 1). Después de recibir resultados, ejecutar en modo síncrono
     para que el fallback PDF procese los que quedaron inválidos.

  3. SÍNCRONO SIN STRUCTURED OUTPUT (legacy): Para modelos que no soportan json_schema (Si 
     quisiera ahorrar y usar modelos como gpt-4o-mini o anteriores).
     Activar con: export OPENAI_STRUCTURED_OUTPUT=0

Uso desde CLI:
    # 1. Enviar batches
     python -m scripts.run_pipeline guanajuato --steps extract --batch

    # 2. Esperar (hasta 24h) y verificar estado
     python -c "from src.core.llm_extract import check_all_batches; check_all_batches(['batch_id_aquí'])"

    # 3. Descargar resultados del batch
     python -m scripts.batch_download yucatan

    # 4. Síncrono para fallback PDF de los que quedaron inválidos
     python -m scripts.run_pipeline guanajuato --steps extract
"""

import json
import os
import time
import base64
from pathlib import Path
from typing import Any

from openai import OpenAI

from src.core.text_utils import parse_predial_filename

# ── Configuración del modelo ──

OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.2")
OPENAI_VISION_MODEL = os.environ.get("OPENAI_VISION_MODEL", OPENAI_MODEL)

# Activar/desactivar structured output (default: activado)
USE_STRUCTURED_OUTPUT = os.environ.get("OPENAI_STRUCTURED_OUTPUT", "1") == "1"

# Límite de tokens por sub-batch
BATCH_TOKEN_LIMIT = int(os.environ.get("BATCH_TOKEN_LIMIT", "900000"))
BATCH_MAX_REQUESTS = int(os.environ.get("BATCH_MAX_REQUESTS", "40000"))

# Cliente lazy
_client: OpenAI | None = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "Variable de entorno OPENAI_API_KEY no definida. "
                "Definir con: export $env:OPENAI_API_KEY='sk-...'"
            )
        _client = OpenAI(api_key=api_key)
    return _client


# ══════════════════════════════════════════════════════════════
# JSON Schema para Structured Output
# ══════════════════════════════════════════════════════════════

PREDIAL_JSON_SCHEMA = {
    "name": "predial_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "predial": {
                "type": "object",
                "properties": {
                    "tipo_esquema": {
                        "type": "string",
                        "enum": [
                            "tarifa_millar", "progresivo", "tasa_unica",
                            "cuota_fija", "mixto", "desconocido",
                        ],
                    },
                    "esquema_valido": {"type": "boolean"},
                    "comentarios": {"type": "string"},
                    "minimo_predial": {
                        "anyOf": [
                            {
                                "type": "object",
                                "properties": {
                                    "monto": {"type": "number"},
                                    "periodicidad": {"type": "string"},
                                    "unidad": {"type": "string"},
                                },
                                "required": ["monto", "periodicidad", "unidad"],
                                "additionalProperties": False,
                            },
                            {"type": "null"},
                        ],
                    },
                    "tabla_tarifa_millar": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "grupo": {"type": "string"},
                                "clave": {"type": "string"},
                                "descripcion": {"type": "string"},
                                "tasa_millar": {"type": "number"},
                                "periodicidad": {"type": "string"},
                                "cuota_fija_adicional": {
                                    "anyOf": [
                                        {
                                            "type": "object",
                                            "properties": {
                                                "monto": {"type": "number"},
                                                "periodicidad": {"type": "string"},
                                                "unidad": {"type": "string"},
                                            },
                                            "required": ["monto", "periodicidad", "unidad"],
                                            "additionalProperties": False,
                                        },
                                        {"type": "null"},
                                    ],
                                },
                            },
                            "required": [
                                "grupo", "clave", "descripcion",
                                "tasa_millar", "periodicidad",
                                "cuota_fija_adicional",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "tabla_progresiva": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "n_rango": {"type": "string"},
                                "inferior": {"type": "string"},
                                "superior": {"type": "string"},
                                "cuota_fija": {"type": "string"},
                                "tasa_marginal": {"type": "string"},
                                "unidad_cuota_fija": {"type": "string"},
                            },
                            "required": [
                                "n_rango", "inferior", "superior",
                                "cuota_fija", "tasa_marginal",
                                "unidad_cuota_fija",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "tabla_tasa_unica": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "descripcion": {"type": "string"},
                                "tasa": {"type": "number"},
                                "base_calculo": {"type": "string"},
                                "unidad": {"type": "string"},
                            },
                            "required": [
                                "descripcion", "tasa",
                                "base_calculo", "unidad",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "tabla_cuota_fija": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "descripcion": {"type": "string"},
                                "monto": {"type": "number"},
                                "periodicidad": {"type": "string"},
                                "unidad": {"type": "string"},
                            },
                            "required": [
                                "descripcion", "monto", "periodicidad",
                                "unidad",
                            ],
                            "additionalProperties": False,
                        },
                    },
                    "tabla_mixta_rango": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "n_rango": {"type": "string"},
                                "inferior": {"type": "string"},
                                "superior": {"type": "string"},
                                "columnas": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "nombre": {"type": "string"},
                                            "valor": {"type": "number"},
                                            "tipo": {"type": "string"},
                                            "unidad": {"type": "string"},
                                        },
                                        "required": ["nombre", "valor", "tipo", "unidad"],
                                        "additionalProperties": False,
                                    },
                                },
                            },
                            "required": [
                                "n_rango", "inferior", "superior", "columnas",
                            ],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": [
                    "tipo_esquema", "esquema_valido", "comentarios",
                    "minimo_predial", "tabla_tarifa_millar",
                    "tabla_progresiva", "tabla_tasa_unica",
                    "tabla_cuota_fija", "tabla_mixta_rango",
                ],
                "additionalProperties": False,
            },
        },
        "required": ["predial"],
        "additionalProperties": False,
    },
}

# ══════════════════════════════════════════════════════════════
# Prompts
# ══════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """\
Eres un modelo experto en extracción de información de leyes de ingresos municipales mexicanas.
Tu tarea NO es interpretar ni corregir la ley, sólo transcribir y estructurar la información del impuesto predial
en un objeto JSON con una forma muy precisa.

El texto que recibes corresponde únicamente a la sección del Impuesto Predial de una Ley de Ingresos municipal.
Puede incluir descuentos, condonaciones, recargos u otros estímulos: IGNÓRALOS y concentrarte en la forma
básica de cálculo del impuesto.

ESTRUCTURA EXACTA DEL JSON (no agregues claves fuera de esto):

{
  "predial": {
    "tipo_esquema": "tarifa_millar | progresivo | tasa_unica | cuota_fija | mixto | desconocido",
    "esquema_valido": true,
    "comentarios": "",
    "minimo_predial": null,
    "tabla_tarifa_millar": [],
    "tabla_progresiva": [],
    "tabla_tasa_unica": [],
    "tabla_cuota_fija": [],
    "tabla_mixta_rango": []
  }
}

═══ CLASIFICACIÓN DE tipo_esquema ═══

"tarifa_millar" (MÁS COMÚN): El impuesto se calcula multiplicando el valor catastral/fiscal por una tasa
  al millar. Puede haber VARIAS tasas según tipo de predio (urbano, rústico, industrial, etc.).
  REGLA CLAVE: si hay múltiples tasas al millar POR TIPO DE PREDIO, sigue siendo "tarifa_millar",
  NO es "mixto". Es el patrón más frecuente en México.
  IMPORTANTE: A veces, ADEMÁS de la tasa al millar, se cobra una CUOTA FIJA ADICIONAL por predio
  (ej: "$150 más 3.5 al millar sobre el valor catastral"). Esto sigue siendo "tarifa_millar";
  la cuota fija adicional se captura en el campo "cuota_fija_adicional" de cada fila.

"progresivo": El impuesto usa una tabla de rangos de valor catastral con columnas:
  límite inferior, límite superior, cuota fija, tasa marginal sobre el excedente.
  IMPORTANTE: solo aplica cuando hay UNA SOLA columna de cuotas/tasas para todos los predios.

"tasa_unica": UNA SOLA tasa (porcentaje o al millar) idéntica para todos los predios sin distinción.

"cuota_fija": Monto fijo por predio, sin referencia al valor catastral.

"mixto": Cuando la ley establece MECANISMOS DISTINTOS que requieren más de una tabla. Casos comunes:
  a) Tabla de cuotas fijas por rango y tipo de predio (urbano) + tasa al millar (rústico).
  b) Rangos bajos pagan cuota fija y a partir de cierto valor pagan al millar.
  c) Tabla con MÚLTIPLES COLUMNAS de valores según tipo de predio para los mismos rangos.
  NO marques como "mixto" solo porque hay un mínimo o un solo tipo adicional (rústico con tasa única).

"desconocido": El texto es insuficiente, truncado, o no contiene la mecánica de cálculo.

═══ PATRÓN ESPECIAL: TABLAS CON MÚLTIPLES COLUMNAS POR TIPO DE PREDIO ═══

Algunas leyes (común en Coahuila) presentan una tabla donde:
- Las filas son rangos de valor catastral (inferior, superior)
- Las columnas son tipos de predio (habitacional, no habitacional, con barda, sin barda)
- Cada celda puede ser una cuota fija (pesos) o una tasa al millar

Ejemplo:
  INFERIOR    SUPERIOR      HABITACIONAL   NO HABITACIONAL   CON BARDA   SIN BARDA
  0.00        60,000.00     102.00         134.64            120.00      189.00
  60,000.01   90,000.00     142.20         189.00            180.00      283.50
  135,000.01  En Adelante   1.58 al millar 2.10 al millar    2.10        3.15

Para este patrón usa tipo_esquema = "mixto" y llena tabla_mixta_rango:
  {
    "n_rango": "1",
    "inferior": "0.00",
    "superior": "60,000.00",
    "columnas": {
      "habitacional": {"valor": 102.00, "tipo": "cuota_fija", "unidad": "pesos"},
      "no_habitacional": {"valor": 134.64, "tipo": "cuota_fija", "unidad": "pesos"},
      "con_barda": {"valor": 120.00, "tipo": "cuota_fija", "unidad": "pesos"},
      "sin_barda": {"valor": 189.00, "tipo": "cuota_fija", "unidad": "pesos"}
    }
  }
  Para filas con tasa al millar:
  {
    "n_rango": "4",
    "inferior": "135,000.01",
    "superior": "En Adelante",
    "columnas": {
      "habitacional": {"valor": 1.58, "tipo": "tasa_millar", "unidad": "al_millar"},
      "no_habitacional": {"valor": 2.10, "tipo": "tasa_millar", "unidad": "al_millar"},
      "con_barda": {"valor": 2.10, "tipo": "tasa_millar", "unidad": "al_millar"},
      "sin_barda": {"valor": 3.15, "tipo": "tasa_millar", "unidad": "al_millar"}
    }
  }

Si además hay rústicos con una tasa diferente, agrégala en tabla_tarifa_millar.
NO aplanes la tabla en filas progresivas consecutivas (una por columna).

═══ CAMPO minimo_predial ═══

Casi todas las leyes establecen un monto mínimo ("en ningún caso será inferior a $X").
Captúralo así:

  "minimo_predial": {"monto": 42.00, "periodicidad": "bimestral", "unidad": "pesos"}

Valores posibles de "unidad": "pesos" | "uma" | "vsm" | "dias_sm"
  - Si dice "$42.00" o un monto en pesos → "pesos"
  - Si dice "2 UMA" o "dos veces la UMA" → "uma" (monto = 2)
  - Si dice "2 salarios mínimos" o "2 VSM" → "vsm" (monto = 2)
  - Si dice "X días de salario mínimo" → "dias_sm" (monto = X)

Si no existe mínimo, usa null. Este campo es INDEPENDIENTE del tipo de esquema.

═══ TABLAS ═══

tabla_tarifa_millar (si tipo_esquema = "tarifa_millar" o componente millar en "mixto"):
  {
    "grupo": "urbano | rustico | general | otro",
    "clave": "identificador_snake_case",
    "descripcion": "texto corto copiado de la ley",
    "tasa_millar": 5.0,
    "periodicidad": "anual | bimestral",
    "cuota_fija_adicional": null
  }
  - Si dice "hasta X al millar", usa X como el valor.
  - Si dice "1.33 veces lo fijado para predios con edificación", calcula el resultado.
  - Si además de la tasa al millar se cobra una cuota fija (ej: "$150 más 3.5 al millar"),
    usa cuota_fija_adicional:
    "cuota_fija_adicional": {"monto": 150.00, "periodicidad": "anual", "unidad": "pesos"}
  - Si NO hay cuota fija adicional, usa null.

tabla_progresiva (si tipo_esquema = "progresivo"):
  {
    "n_rango": "1",
    "inferior": "$0.01",
    "superior": "$620,100.00",
    "cuota_fija": "$142.63",
    "tasa_marginal": "0.00023",
    "unidad_cuota_fija": "pesos"
  }
  - inferior/superior: copia literal (incluyendo $, comas).
  - Último rango abierto: "En adelante" en superior.
  - tasa_marginal: solo número decimal.
  - unidad_cuota_fija: "pesos" | "uma" | "vsm" | "dias_sm"
    La mayoría son "pesos". Colima usa "uma" (pre-2017: "vsm").

tabla_tasa_unica (si tipo_esquema = "tasa_unica"):
  {
    "descripcion": "texto corto",
    "tasa": 0.003,
    "base_calculo": "valor_catastral | valor_fiscal | otro",
    "unidad": "porcentaje | al_millar | al_millar_bimestral"
  }

tabla_cuota_fija (si tipo_esquema = "cuota_fija"):
  {
    "descripcion": "texto corto",
    "monto": 350.00,
    "periodicidad": "anual | bimestral | mensual",
    "unidad": "pesos"
  }
  - unidad: "pesos" | "uma" | "vsm" | "dias_sm". Default "pesos" si el texto
    muestra montos en $ sin mención de UMA/VSM.

═══ REGLAS CLAVE ═══

1. Solo UNA tabla principal por esquema, excepto "mixto" que puede tener varias.
2. "minimo_predial" es INDEPENDIENTE — NO debe causar "mixto".
3. NUNCA inventes valores. Si falta algo esencial → null y esquema_valido = false.
4. Texto truncado o solo encabezados → "desconocido", esquema_valido = false.
5. Múltiples tasas al millar por tipo de predio SIN tabla de rangos → "tarifa_millar".
6. Tabla de rangos con VARIAS COLUMNAS por tipo de predio → "mixto" + tabla_mixta_rango.
7. "esquema_valido" = true cuando TODOS los valores necesarios están presentes.

8.  REGLA CRÍTICA — Conversión de "%" en tasas al millar:
    En Jalisco y otros estados, las tasas bimestrales al millar se expresan 
    frecuentemente con signo "%". Esto NO es un porcentaje real sino la 
    representación local de la tasa al millar. 
    SIEMPRE divide entre 100 para obtener el valor al millar correcto:
    - "20%" → tasa_millar = 0.20
    - "23%" → tasa_millar = 0.23  
    - "35%" → tasa_millar = 0.35
    - "10%" → tasa_millar = 0.10
    Esto NO es inventar valores. Es la conversión correcta y obligatoria.
    Si el encabezado dice "tasa bimestral al millar" y los valores tienen "%",
    APLICA esta conversión y marca esquema_valido = true.
    NO dejes tasa_millar en 0 por esta ambigüedad.

═══ CASOS ESPECIALES A IGNORAR ═══

IGNORA completamente los siguientes casos que exceden el alcance de esta base de datos:
- Predios de EXTRACCIÓN EJIDAL que pagan conforme a un porcentaje del valor de su producción
  anual comercializada (ej: "3% al valor de producción anual").
- "Frutos civiles" (impuesto sobre rentas de inmuebles). NO es impuesto predial.
- Derechos por servicios catastrales, avalúos, o expedición de constancias.
- Cualquier base de cálculo que NO sea el valor catastral/fiscal del inmueble
  (producción, rentas, superficie cultivada, etc.).
Si estos son los ÚNICOS mecanismos mencionados, clasifica como "desconocido" y
en comentarios escribe: "Solo menciona esquemas fuera de alcance (producción, frutos civiles, etc.)".
Si coexisten con un esquema válido (ej: tarifa al millar para urbanos + producción para ejidales),
extrae SOLO el esquema válido e ignora el resto.

═══ CONVENCIONES DE UNIDADES (IMPORTANTE) ═══

Las unidades son IMPLÍCITAS y fijas para la mayoría de los esquemas:

  • minimo_predial.monto → SIEMPRE en pesos mexicanos.
  • tabla_progresiva: inferior, superior, cuota_fija → SIEMPRE en pesos mexicanos.
  • tabla_progresiva: tasa_marginal → SIEMPRE como factor decimal (proporción, no porcentaje).
    Ejemplo: si la ley dice "0.023%" o "0.23 al millar", transcribe "0.00023".
  • tabla_tarifa_millar: tasa_millar → SIEMPRE como tasa al millar (numérica).
  • tabla_tarifa_millar: cuota_fija_adicional → monto en pesos, UMA o VSM según contexto.
  • tabla_tasa_unica: ya tiene campo "unidad" → llenar con "al_millar" | "porcentaje" | etc.
  • tabla_cuota_fija: monto → SIEMPRE en pesos mexicanos.

  • tabla_mixta_rango: inferior, superior → SIEMPRE en pesos mexicanos.
  • tabla_mixta_rango: columnas → AQUÍ SÍ debes ser EXPLÍCITO con la unidad de cada celda:
    {"valor": 102.00, "tipo": "cuota_fija", "unidad": "pesos"}
    {"valor": 1.58,   "tipo": "tasa_millar", "unidad": "al_millar"}
    Valores posibles de "unidad":
      - Si tipo="cuota_fija": "pesos" | "uma" | "vsm" | "dias_sm"
      - Si tipo="tasa_millar": "al_millar" | "porcentaje" | "factor_decimal" | "pesos_m2"
    Si la ley no es explícita sobre la unidad, inferir del contexto:
      - Montos > 50 y sin mención de UMA/VSM → "pesos"
      - Texto dice "UMA" o "Unidad de Medida y Actualización" → "uma"
      - Texto dice "salario mínimo" o "VSM" → "vsm"
      - Tasas escritas como "X al millar" → "al_millar"
      - Tasas escritas como "X%" → "porcentaje"
      - Factores decimales pequeños (0.001, 0.00025) → "factor_decimal"

Devuelve SIEMPRE un único objeto JSON válido con la clave "predial" en la raíz, sin texto adicional.
"""

USER_TEMPLATE = """\
Texto de la sección "Del Impuesto Predial" de la Ley de Ingresos del municipio de {MUNICIPIO}, {ESTADO}, \
para el ejercicio fiscal {ANIO}.

IGNORA descuentos, recargos, bonificaciones, condonaciones y estímulos.
Extrae SOLO la mecánica básica de cálculo y devuelve el JSON según las instrucciones del sistema.

Recuerda:
- Múltiples tasas al millar por tipo de predio → "tarifa_millar" (NO "mixto")
- Si hay cuota fija ADICIONAL a la tasa al millar → usa "cuota_fija_adicional" en cada fila
- "hasta X al millar" → usa X como la tasa
- Mínimo predial → campo "minimo_predial", NO afecta tipo_esquema
- Texto truncado o sin mecánica de cálculo → "desconocido"
- IGNORA las "TABLAS DE VALORES UNITARIOS DE TERRENO Y CONSTRUCCIÓN" (son valores catastrales
  para determinar la base del impuesto, NO la tarifa). Los valores por m2 de concreto, hierro,
  zinc, cartón, por sección/manzana, rústicos por hectárea son CATASTRO, no tarifa.
- Si el impuesto se calcula como: valor_catastral × factor (ej: 0.00025, 0.001, 0.0015),
  clasifica como "tasa_unica" con la tasa expresada como el factor decimal.
- Si hay una tabla progresiva (límite inferior, superior, cuota fija, factor sobre excedente),
  clasifica como "progresivo" aunque TAMBIÉN haya valores catastrales en el mismo texto.
- Los predios rústicos con cuota por hectárea o "10 al millar" son un componente adicional
  de tarifa_millar; agrégalo como un grupo "rustico" en tabla_tarifa_millar.
- Los "frutos civiles" (rentas) son un impuesto SEPARADO. IGNÓRALOS.
- Predios de extracción ejidal con base en producción → IGNORAR (fuera de alcance).

===== TEXTO =====
{TEXTO_PREDIAL}
===== FIN =====
"""

USER_TEMPLATE_VISION = """\
Estas son las páginas de la sección del Impuesto Predial de la Ley de Ingresos del municipio \
de {MUNICIPIO}, {ESTADO}, para el ejercicio fiscal {ANIO}.

IGNORA descuentos, recargos, bonificaciones, condonaciones y estímulos.
Extrae SOLO la mecánica básica de cálculo y devuelve el JSON según las instrucciones del sistema.

IMPORTANTE: Las tablas de tarifas pueden estar en imágenes escaneadas.
Lee cuidadosamente los números de las tablas (tasas al millar, cuotas, rangos de valor catastral).
"""

# ══════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════

def _build_messages(anio: int, municipio_nombre: str, estado_nombre: str,
                    texto_predial: str) -> list[dict]:
    """Construye la lista de mensajes para Chat Completions (modo texto)."""
    user_content = USER_TEMPLATE.format(
        ANIO=anio,
        MUNICIPIO=municipio_nombre,
        ESTADO=estado_nombre,
        TEXTO_PREDIAL=texto_predial.strip(),
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _build_vision_messages(anio: int, municipio_nombre: str, estado_nombre: str,
                           images_b64: list[str]) -> list[dict]:
    """Construye mensajes multimodal para Chat Completions (modo visión)."""
    user_text = USER_TEMPLATE_VISION.format(
        ANIO=anio,
        MUNICIPIO=municipio_nombre,
        ESTADO=estado_nombre,
    )

    user_parts: list[dict] = [{"type": "text", "text": user_text}]

    for b64 in images_b64:
        user_parts.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/png;base64,{b64}",
                "detail": "high",
            },
        })

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_parts},
    ]


def _parse_llm_response(raw_text: str) -> dict[str, Any]:
    """Parsea la respuesta del LLM a dict, manejando markdown fences."""
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            lines = [l for l in lines if not l.strip().startswith("```")]
            cleaned = "\n".join(lines)
        data = json.loads(cleaned)

    if "predial" not in data:
        raise ValueError('El JSON devuelto no contiene la clave "predial".')
    return data


def _is_valid_extraction(data: dict) -> bool:
    """Verifica si la extracción LLM produjo un esquema válido."""
    predial = data.get("predial", {})

    if not predial.get("esquema_valido", False):
        return False
    if predial.get("tipo_esquema") == "desconocido":
        return False

    tipo = predial.get("tipo_esquema", "")
    if tipo == "tarifa_millar" and not predial.get("tabla_tarifa_millar"):
        return False
    if tipo == "progresivo" and not predial.get("tabla_progresiva"):
        return False
    if tipo == "tasa_unica" and not predial.get("tabla_tasa_unica"):
        return False
    if tipo == "mixto" and not predial.get("tabla_mixta_rango"):
        return False

    # Sanity check: detectar valores claramente erróneos (ej: tasa al millar de 200)
    if not _sanity_check_extraction(data):
        return False

    return True


def _encode_pdf_pages(pdf_path: Path) -> list[str]:
    """Renderiza páginas del PDF como imágenes PNG en base64 a 200 DPI."""
    import fitz

    images = []
    with fitz.open(str(pdf_path)) as doc:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            pix = page.get_pixmap(dpi=200)
            img_bytes = pix.tobytes("png")
            b64 = base64.b64encode(img_bytes).decode("utf-8")
            images.append(b64)
    return images


# ══════════════════════════════════════════════════════════════
# Llamada LLM (texto) con structured output
# ══════════════════════════════════════════════════════════════

def call_llm(
    texto_predial: str,
    anio: int,
    municipio_nombre: str,
    estado_nombre: str = "",
    max_retries: int = 3,
) -> dict[str, Any]:
    """
    Llamada síncrona con structured output (si habilitado).
    Compatible hacia atrás: si OPENAI_STRUCTURED_OUTPUT=0, usa el modo legacy.
    """
    client = _get_client()
    messages = _build_messages(anio, municipio_nombre, estado_nombre, texto_predial)

    kwargs: dict[str, Any] = {
        "model": OPENAI_MODEL,
        "messages": messages,
    }

    if USE_STRUCTURED_OUTPUT:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": PREDIAL_JSON_SCHEMA,
        }

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(**kwargs)

            raw_text = response.choices[0].message.content
            data = json.loads(raw_text) if USE_STRUCTURED_OUTPUT else _parse_llm_response(raw_text)

            if "predial" not in data:
                raise ValueError('El JSON devuelto no contiene la clave "predial".')

            # Log de cache hit
            usage = response.usage
            if usage and hasattr(usage, "prompt_tokens_details"):
                details = usage.prompt_tokens_details
                if details and hasattr(details, "cached_tokens"):
                    cached = details.cached_tokens or 0
                    if cached > 0:
                        print(f"    [CACHE] {cached} tokens cacheados de {usage.prompt_tokens}")

            return data

        except (json.JSONDecodeError, ValueError) as e:
            print(f"    [ERROR] Respuesta mal formada (intento {attempt}): {e}")
            if attempt < max_retries:
                time.sleep(2)
            last_error = e

        except Exception as e:
            print(f"    [ERROR] API (intento {attempt}): {e}")
            if attempt < max_retries:
                wait = 2 ** attempt
                print(f"    Esperando {wait}s antes de reintentar...")
                time.sleep(wait)
            last_error = e

    raise last_error  # type: ignore


def call_llm_vision(
    pdf_path: Path,
    anio: int,
    municipio_nombre: str,
    estado_nombre: str = "",
    max_retries: int = 3,
) -> dict[str, Any]:
    """
    Llamada LLM con el PDF como imágenes (visión) + structured output.
    Fallback cuando el OCR del TXT no produjo un esquema válido.
    """
    client = _get_client()
    images_b64 = _encode_pdf_pages(pdf_path)

    if not images_b64:
        raise ValueError(f"No se pudieron renderizar páginas de {pdf_path}")

    messages = _build_vision_messages(anio, municipio_nombre, estado_nombre, images_b64)

    kwargs: dict[str, Any] = {
        "model": OPENAI_VISION_MODEL,
        "messages": messages,
        "max_completion_tokens": 4096,
    }

    if USE_STRUCTURED_OUTPUT:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": PREDIAL_JSON_SCHEMA,
        }

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(**kwargs)
            raw_text = response.choices[0].message.content
            data = json.loads(raw_text) if USE_STRUCTURED_OUTPUT else _parse_llm_response(raw_text)
            return data

        except Exception as e:
            print(f"      [ERROR] Vision intento {attempt}: {e}")
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            last_error = e

    raise last_error  # type: ignore


# Extensión de TXT (+5pp antes, +2pp después) para fallback intermedio
# ══════════════════════════════════════════════════════════════

# Páginas de contexto para TXT extendido
TXT_EXT_PAGES_BEFORE = 5
TXT_EXT_PAGES_AFTER = 2


def _diagnose_extraction(data: dict | None) -> str:
    """
    Genera un diagnóstico legible de por qué la extracción falló o es sospechosa.
    Retorna un string con el resumen del problema.
    """
    if data is None:
        return "sin_respuesta: el LLM no devolvió datos"

    predial = data.get("predial", {})
    tipo = predial.get("tipo_esquema", "?")
    valido = predial.get("esquema_valido", False)
    comentarios = predial.get("comentarios", "")

    parts = [f"tipo={tipo}, valido={valido}"]

    if tipo == "desconocido":
        parts.append("diagnóstico=texto_insuficiente_o_truncado")
        if comentarios:
            parts.append(f"comentario_llm={comentarios[:120]}")
        return " | ".join(parts)

    # Revisar tablas vacías cuando se esperaban llenas
    tablas_map = {
        "tarifa_millar": "tabla_tarifa_millar",
        "progresivo": "tabla_progresiva",
        "tasa_unica": "tabla_tasa_unica",
        "cuota_fija": "tabla_cuota_fija",
        "mixto": "tabla_mixta_rango",
    }
    tabla_key = tablas_map.get(tipo)
    if tabla_key and not predial.get(tabla_key):
        parts.append(f"diagnóstico=tabla_{tipo}_vacía")
        return " | ".join(parts)

    # Revisar filas individuales con problemas
    if tipo == "tarifa_millar":
        for i, fila in enumerate(predial.get("tabla_tarifa_millar", [])):
            tasa = fila.get("tasa_millar")
            if tasa is not None and tasa > 50:
                parts.append(
                    f"diagnóstico=tasa_sospechosa_fila_{i} "
                    f"(grupo={fila.get('grupo')}, tasa_millar={tasa})"
                )

    if not valido and comentarios:
        parts.append(f"comentario_llm={comentarios[:120]}")

    return " | ".join(parts)


def _sanity_check_extraction(data: dict) -> bool:
    """
    Verificación post-extracción para detectar valores claramente erróneos.
    Retorna True si pasa el sanity check, False si hay problemas.

    Ej: Una tasa al millar > 50 es casi seguramente un error de interpretación
    (100 al millar = 10% del valor catastral por bimestre → implausible).
    """
    predial = data.get("predial", {})
    tipo = predial.get("tipo_esquema", "")

    if tipo == "tarifa_millar":
        for fila in predial.get("tabla_tarifa_millar", []):
            tasa = fila.get("tasa_millar")
            if tasa is not None and tasa > 50:
                return False

    if tipo == "tasa_unica":
        for fila in predial.get("tabla_tasa_unica", []):
            tasa = fila.get("tasa")
            unidad = fila.get("unidad", "")
            # >10% anual sobre valor catastral es implausible
            if unidad == "porcentaje" and tasa is not None and tasa > 10:
                return False
            if unidad == "al_millar" and tasa is not None and tasa > 50:
                return False

    return True


def get_extended_txt(focus_txt: Path, adapter=None) -> str | None:
    """
    Genera texto extendido: N páginas de contexto antes y después del recorte,
    extraídas del source PDF vía segment.csv.

    Soporta dos formatos de segment.csv:
      - Oaxaca/Guanajuato: columnas txt_file, source_pdf, ejercicio, predial_page_start/end
      - Jalisco: columnas municipio, anio, pdf_used, predial_page_start/end

    Retorna el texto extendido, o None si no puede extender.
    """
    if adapter is None:
        print("      [ext_txt] adapter es None")
        return None

    import fitz
    import csv

    meta_csv = adapter.meta_dir / "segment.csv"
    if not meta_csv.exists():
        print(f"      [ext_txt] No existe {meta_csv}")
        return None

    target_name = focus_txt.stem  # ej: JAL_PREDIAL_2012_san_juan_de_los_lagos

    try:
        with meta_csv.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []

            # Detectar formato del CSV
            has_txt_file = "txt_file" in headers      # Oaxaca/Guanajuato
            has_pdf_used = "pdf_used" in headers       # Jalisco

            for row in reader:
                # ── Matching: encontrar la fila que corresponde a este TXT ──
                matched = False
                if has_txt_file:
                    txt_base = row.get("txt_file", "").replace(".txt", "")
                    if txt_base == target_name:
                        matched = True
                elif has_pdf_used:
                    # Jalisco: reconstruir el nombre del TXT desde municipio + anio
                    mun = row.get("municipio", "")
                    anio = row.get("anio", "")
                    if mun and anio:
                        from src.core.text_utils import slugify
                        expected = f"{adapter.prefijo}_PREDIAL_{anio}_{slugify(mun)}"
                        if expected == target_name:
                            matched = True

                if not matched:
                    continue

                # ── Extraer datos de la fila ──
                pred_start_raw = row.get("predial_page_start", "0")
                pred_end_raw = row.get("predial_page_end", "0")

                try:
                    pred_start = int(float(pred_start_raw)) - 1   # 1-based → 0-based
                    pred_end = int(float(pred_end_raw))            # 1-based inclusive → 0-based exclusive
                except (ValueError, TypeError):
                    print(f"      [ext_txt] Páginas no numéricas: start={pred_start_raw}, end={pred_end_raw}")
                    return None

                if pred_end <= 0:
                    print(f"      [ext_txt] pred_end inválido: {pred_end}")
                    return None

                # ── Localizar el source PDF ──
                source = None

                if has_pdf_used:
                    # Jalisco: pdf_used es la ruta completa
                    pdf_used = Path(row.get("pdf_used", ""))
                    if pdf_used.exists():
                        source = pdf_used

                if source is None and has_txt_file:
                    source_pdf_name = row.get("source_pdf", "")
                    ejercicio = row.get("ejercicio", "")
                    if source_pdf_name:
                        # Oaxaca/Guanajuato: source_pdf explícito en el CSV
                        for base_dir in [adapter.pdf_ocr_dir, adapter.pdf_raw_dir]:
                            for sub in [ejercicio, ""]:
                                candidate = base_dir / sub / source_pdf_name if sub else base_dir / source_pdf_name
                                if candidate.exists():
                                    source = candidate
                                    break
                            if source:
                                break
                    elif ejercicio:
                        # Tamaulipas y otros: sin source_pdf, buscar por decreto o glob
                        decreto = row.get("decreto", "")
                        if decreto:
                            # Buscar PDF que contenga el decreto en el nombre
                            for base_dir in [adapter.pdf_ocr_dir, adapter.pdf_raw_dir]:
                                for sub in [ejercicio, ""]:
                                    search_dir = base_dir / sub if sub else base_dir
                                    if search_dir.exists():
                                        for pdf_file in search_dir.glob("*.pdf"):
                                            if decreto.replace(" ", "_").lower() in pdf_file.stem.lower() or decreto.lower() in pdf_file.stem.lower():
                                                source = pdf_file
                                                break
                                    if source:
                                        break
                        if source is None:
                            # Último recurso: buscar cualquier PDF del ejercicio que contenga el slug
                            slug = row.get("slug", "")
                            if slug:
                                for base_dir in [adapter.pdf_ocr_dir, adapter.pdf_raw_dir]:
                                    search_dir = base_dir / ejercicio
                                    if search_dir.exists():
                                        matches = [p for p in search_dir.glob("*.pdf") if slug in p.stem.lower()]
                                        if len(matches) == 1:
                                            source = matches[0]
                                            break

                if source is None and ejercicio:
                    # Fallback: buscar en pdf_raw/ejercicio/ un PDF que contenga
                    # las páginas indicadas (tomo consolidado)
                    for base_dir in [adapter.pdf_raw_dir, adapter.pdf_ocr_dir]:
                        search_dir = base_dir / ejercicio
                        if search_dir.exists():
                            pdfs = sorted(search_dir.glob("*.pdf"))
                            if len(pdfs) == 1:
                                source = pdfs[0]
                                break
                            # Si hay varios, intentar match por slug o decreto
                            slug = row.get("slug", "")
                            decreto = row.get("decreto", "")
                            for pdf_file in pdfs:
                                stem_lower = pdf_file.stem.lower()
                                if slug and slug in stem_lower:
                                    source = pdf_file
                                    break
                                if decreto and decreto.lower().replace(" ", "_") in stem_lower:
                                    source = pdf_file
                                    break
                        if source:
                            break

                if source is None:
                    print(f"      [ext_txt] Source PDF no encontrado para {target_name}")
                    return None

                # ── Extraer texto extendido ──
                with fitz.open(str(source)) as doc:
                    n_pages = len(doc)
                    ext_start = max(0, pred_start - TXT_EXT_PAGES_BEFORE)
                    ext_end = min(n_pages, pred_end + TXT_EXT_PAGES_AFTER)

                    if ext_start >= pred_start and ext_end <= pred_end:
                        print(f"      [ext_txt] Sin margen: pages={pred_start}-{pred_end} de {n_pages}")
                        return None

                    parts = []
                    for p in range(ext_start, ext_end):
                        text = doc[p].get_text("text")
                        if text and text.strip():
                            parts.append(text)

                    if not parts:
                        print(f"      [ext_txt] Páginas extendidas sin texto")
                        return None

                    return "\n\n".join(parts)

        print(f"      [ext_txt] {target_name} no encontrado en segment.csv")
        return None

    except Exception as e:
        print(f"      [ext_txt] Error: {e}")
        return None




# ══════════════════════════════════════════════════════════════
# Extensión de PDF (+1 página) para fallback visión
# ══════════════════════════════════════════════════════════════

def get_extended_pdf(focus_pdf: Path, adapter=None) -> Path:
    """
    Genera un PDF extendido con ±1 página adicional del source PDF.
    Agrega 1 página ANTES del inicio y 1 página DESPUÉS del final del recorte
    original, para dar más contexto al LLM en el fallback de visión.
    Busca el source en segment.csv del adapter. Si no puede extender,
    retorna el PDF original.
    """
    if adapter is None:
        return focus_pdf

    import fitz
    import csv

    meta_csv = adapter.meta_dir / "segment.csv"
    if not meta_csv.exists():
        return focus_pdf

    target_name = focus_pdf.stem

    try:
        with meta_csv.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                txt_base = row.get("txt_file", "").replace(".txt", "")
                if txt_base == target_name:
                    source_pdf_name = row.get("source_pdf", "")
                    pred_start = int(row.get("predial_page_start", 0))
                    pred_end = int(row.get("predial_page_end", 0))
                    ejercicio = row.get("ejercicio", "")

                    if not source_pdf_name or not pred_end:
                        return focus_pdf

                    source = adapter.pdf_ocr_dir / ejercicio / source_pdf_name
                    if not source.exists():
                        source = adapter.pdf_raw_dir / ejercicio / source_pdf_name
                    if not source.exists():
                        return focus_pdf

                    with fitz.open(str(source)) as doc:
                        n_pages = len(doc)
                        # Calcular páginas extra disponibles
                        # pred_start/pred_end son 0-based page indices
                        page_before = pred_start - 1 if pred_start > 0 else None
                        page_after = pred_end if pred_end < n_pages else None

                        if page_before is None and page_after is None:
                            return focus_pdf

                        ext_path = focus_pdf.with_name(focus_pdf.stem + "_ext.pdf")
                        ext_doc = fitz.open()

                        # +1 página ANTES del recorte
                        if page_before is not None:
                            ext_doc.insert_pdf(doc, from_page=page_before, to_page=page_before)

                        # Recorte original
                        with fitz.open(str(focus_pdf)) as orig:
                            ext_doc.insert_pdf(orig)

                        # +1 página DESPUÉS del recorte
                        if page_after is not None:
                            ext_doc.insert_pdf(doc, from_page=page_after, to_page=page_after)

                        ext_doc.save(str(ext_path))
                        ext_doc.close()
                        return ext_path
                    break
    except Exception:
        pass

    return focus_pdf

# ══════════════════════════════════════════════════════════════
# MODO 2: Batch API (50% descuento)
# ══════════════════════════════════════════════════════════════

def _estimate_tokens(text: str) -> int:
    """Estimación rápida de tokens (~4 chars por token en español)."""
    return len(text) // 4


def create_batch_files(
    txt_dir: Path,
    json_dir: Path,
    prefijo: str,
    estado_nombre: str = "",
    token_limit: int = BATCH_TOKEN_LIMIT,
    max_requests: int = BATCH_MAX_REQUESTS,
) -> list[Path]:
    """Genera JSONL para la Batch API. Incluye structured output si habilitado."""
    if not txt_dir.exists():
        raise FileNotFoundError(f"No existe {txt_dir}")

    pattern = f"{prefijo}_PREDIAL_*.txt"
    txt_files = sorted(txt_dir.rglob(pattern))

    if not estado_nombre:
        estado_nombre = prefijo.capitalize()

    system_tokens = _estimate_tokens(SYSTEM_PROMPT)

    pending = []
    for txt_path in txt_files:
        try:
            anio, slug, nombre_mpio = parse_predial_filename(txt_path, prefijo)
        except Exception:
            continue

        out_path = json_dir / str(anio) / f"{prefijo}_PREDIAL_{anio}_{slug}.json"
        if out_path.exists():
            continue

        texto = txt_path.read_text(encoding="utf-8", errors="ignore").strip()
        if not texto:
            continue

        messages = _build_messages(anio, nombre_mpio, estado_nombre, texto)
        custom_id = f"{prefijo}_{anio}_{slug}"

        user_tokens = _estimate_tokens(texto)
        req_tokens = system_tokens + user_tokens + 500

        pending.append({
            "custom_id": custom_id,
            "messages": messages,
            "est_tokens": req_tokens,
        })

    if not pending:
        print("  No hay requests pendientes (todos los JSON ya existen).")
        return []

    batch_dir = json_dir.parent / "meta"
    batch_dir.mkdir(parents=True, exist_ok=True)

    jsonl_paths = []
    batch_idx = 1
    current_tokens = 0
    current_requests = 0
    current_file = None

    def _open_new_batch():
        nonlocal batch_idx, current_tokens, current_requests, current_file
        if current_file:
            current_file.close()
        path = batch_dir / f"batch_{prefijo}_{batch_idx:03d}.jsonl"
        current_file = path.open("w", encoding="utf-8")
        jsonl_paths.append(path)
        current_tokens = 0
        current_requests = 0
        batch_idx += 1
        return current_file

    current_file = None
    for req in pending:
        if (current_file is None
                or current_tokens + req["est_tokens"] > token_limit
                or current_requests >= max_requests):
            current_file = _open_new_batch()

        body: dict[str, Any] = {
            "model": OPENAI_MODEL,
            "messages": req["messages"],
        }

        if USE_STRUCTURED_OUTPUT:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": PREDIAL_JSON_SCHEMA,
            }

        batch_request = {
            "custom_id": req["custom_id"],
            "method": "POST",
            "url": "/v1/chat/completions",
            "body": body,
        }

        current_file.write(json.dumps(batch_request, ensure_ascii=False) + "\n")
        current_tokens += req["est_tokens"]
        current_requests += 1

    if current_file:
        current_file.close()

    print(f"  Requests pendientes: {len(pending)}")
    print(f"  Sub-batches generados: {len(jsonl_paths)}")
    for i, p in enumerate(jsonl_paths, 1):
        with p.open("r", encoding="utf-8") as f:
            n = sum(1 for _ in f)
        print(f"    [{i}] {p.name}: {n} requests")

    return jsonl_paths


def submit_batch(jsonl_path: Path) -> str:
    """Sube un archivo JSONL a OpenAI y crea un batch."""
    client = _get_client()

    print(f"  Subiendo {jsonl_path.name} a OpenAI...")
    with jsonl_path.open("rb") as f:
        file_obj = client.files.create(file=f, purpose="batch")

    print(f"  Archivo subido: {file_obj.id}")

    batch = client.batches.create(
        input_file_id=file_obj.id,
        endpoint="/v1/chat/completions",
        completion_window="24h",
    )

    print(f"  Batch creado: {batch.id} (estado: {batch.status})")
    return batch.id


def submit_all_batches(jsonl_paths: list[Path]) -> list[str]:
    """Sube todos los sub-batches a OpenAI."""
    batch_ids = []
    for i, path in enumerate(jsonl_paths, 1):
        print(f"\n  ── Sub-batch {i}/{len(jsonl_paths)} ──")
        bid = submit_batch(path)
        batch_ids.append(bid)
    return batch_ids


def check_batch(batch_id: str):
    """Muestra el estado de un batch."""
    client = _get_client()
    batch = client.batches.retrieve(batch_id)

    print(f"  Batch: {batch.id}")
    print(f"  Estado: {batch.status}")
    print(f"  Completados: {batch.request_counts.completed}/{batch.request_counts.total}")
    print(f"  Fallidos: {batch.request_counts.failed}")

    if batch.status == "completed" and batch.output_file_id:
        print(f"  Output file: {batch.output_file_id}")
        print(f"  Listo para descargar.")


def check_all_batches(batch_ids: list[str]):
    """Muestra el estado de múltiples batches."""
    for i, bid in enumerate(batch_ids, 1):
        print(f"\n  ── Sub-batch {i}/{len(batch_ids)} ──")
        check_batch(bid)


def download_batch_results(
    batch_id: str,
    output_file_id: str,
    prefijo: str,
    json_dir: Path,
):
    """Descarga resultados de un batch completado y guarda JSONs."""
    client = _get_client()

    print(f"  Descargando resultados del batch {batch_id}...")
    content = client.files.content(output_file_id)

    ok = 0
    errores = 0

    for line in content.text.strip().split("\n"):
        if not line.strip():
            continue

        result = json.loads(line)
        custom_id = result["custom_id"]
        response = result.get("response", {})
        status_code = response.get("status_code", 0)
        body = response.get("body", {})

        parts = custom_id.split("_", 2)
        if len(parts) < 3:
            print(f"    [SKIP] custom_id mal formado: {custom_id}")
            errores += 1
            continue

        anio_str = parts[1]
        slug = "_".join(parts[2:])

        try:
            anio = int(anio_str)
        except ValueError:
            if len(parts) >= 4 and parts[1] == "PREDIAL":
                anio = int(parts[2])
                slug = "_".join(parts[3:])
            else:
                errores += 1
                continue

        if status_code != 200:
            print(f"    [ERROR] {custom_id}: HTTP {status_code}")
            errores += 1
            continue

        choices = body.get("choices", [])
        if not choices:
            errores += 1
            continue

        raw_text = choices[0].get("message", {}).get("content", "")
        try:
            data = json.loads(raw_text) if USE_STRUCTURED_OUTPUT else _parse_llm_response(raw_text)
        except Exception as e:
            print(f"    [ERROR] {custom_id}: parseo fallido: {e}")
            errores += 1
            continue

        # Agregar metadata
        data["_meta"] = {"fuente": "txt", "modelo": OPENAI_MODEL}

        out_dir = json_dir / str(anio)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{prefijo}_PREDIAL_{anio}_{slug}.json"

        with out_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        ok += 1

    print(f"  Batch procesado: {ok} OK, {errores} errores")

    # ══════════════════════════════════════════════════════════════
# Entry point principal (llamado por el pipeline)
# ══════════════════════════════════════════════════════════════

def extract_all(
    txt_dir: Path,
    json_dir: Path,
    prefijo: str,
    estado_nombre: str = "",
    batch_mode: bool = False,
    adapter=None,
    pdf_fallback: bool = True,
):
    """
    Extrae datos de predial de todos los TXT en txt_dir.

    Args:
        batch_mode: Si True, genera JSONL y lo sube como batch.
        adapter: Si se proporciona, habilita fallback PDF con extensión +1 página.
        pdf_fallback: Si True y hay PDF disponible, intenta visión cuando TXT falla.
    """
    if not txt_dir.exists():
        print(f"  [ERROR] No existe directorio de TXT: {txt_dir}")
        return

    pattern = f"{prefijo}_PREDIAL_*.txt"
    txt_files = sorted(txt_dir.rglob(pattern))

    if not txt_files:
        print(f"  No se encontraron TXT con patrón '{pattern}' en {txt_dir}")
        return

    if not estado_nombre:
        estado_nombre = prefijo.capitalize()

    # ── Modo BATCH ──
    if batch_mode:
        jsonl_paths = create_batch_files(txt_dir, json_dir, prefijo, estado_nombre)
        if not jsonl_paths:
            return

        batch_ids = submit_all_batches(jsonl_paths)

        ids_file = json_dir.parent / "meta" / f"batch_{prefijo}_ids.json"
        ids_file.parent.mkdir(parents=True, exist_ok=True)
        with ids_file.open("w") as f:
            json.dump({
                "prefijo": prefijo,
                "model": OPENAI_MODEL,
                "structured_output": USE_STRUCTURED_OUTPUT,
                "batch_ids": batch_ids,
                "jsonl_files": [str(p) for p in jsonl_paths],
            }, f, indent=2)

        print(f"\n  ══ {len(batch_ids)} batch(es) enviado(s) ══")
        print(f"  Modelo: {OPENAI_MODEL}")
        print(f"  Structured output: {'sí' if USE_STRUCTURED_OUTPUT else 'no'}")
        for i, bid in enumerate(batch_ids, 1):
            print(f"    [{i}] {bid}")
        print(f"\n  IDs guardados en: {ids_file}")
        if pdf_fallback:
            print(f"\n  Después de recibir resultados, ejecutar en modo síncrono")
            print(f"  para el fallback PDF de los esquemas inválidos:")
            print(f"    python scripts/run_pipeline.py {prefijo.lower()} --steps extract")
        return

    # ── Modo SÍNCRONO con fallback ──
    print(f"  Encontrados {len(txt_files)} archivos TXT.")
    mode_desc = "structured output" if USE_STRUCTURED_OUTPUT else "legacy"
    if pdf_fallback:
        mode_desc += " + fallback PDF visión"
    print(f"  Modo: síncrono ({mode_desc})")
    print(f"  Modelo: {OPENAI_MODEL}")

    stats = {"total": 0, "ok_txt": 0, "ok_pdf": 0, "skipped": 0, "errors": 0}

    for txt_path in txt_files:
        stats["total"] += 1

        try:
            anio, slug, nombre_mpio = parse_predial_filename(txt_path, prefijo)
        except Exception as e:
            print(f"\n  [SKIP] {txt_path.name}: {e}")
            stats["errors"] += 1
            continue

        out_dir = json_dir / str(anio)
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{prefijo}_PREDIAL_{anio}_{slug}.json"

        # Si ya existe y es válido, skip; si inválido, re-intentar con fallbacks
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
                if _is_valid_extraction(existing):
                    stats["skipped"] += 1
                    continue
                print(f"\n  >>> {nombre_mpio} {anio} (re-intento, esquema inválido)")
            except Exception:
                stats["skipped"] += 1
                continue
        else:
            print(f"\n  >>> {nombre_mpio} {anio}")

        # ── Paso 1: TXT (recorte original) ──
        try:
            texto = txt_path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            print(f"    [ERROR] Leyendo TXT: {e}")
            stats["errors"] += 1
            continue

        if not texto.strip():
            print("    [ERROR] TXT vacío.")
            stats["errors"] += 1
            continue

        data = None
        used_pdf = False
        used_ext_txt = False

        try:
            print(f"    [1/3] TXT ({len(texto)} chars)...")
            data = call_llm(texto, anio, nombre_mpio, estado_nombre)
        except Exception as e:
            print(f"    [ERROR] LLM TXT: {e}")

        # ── Paso 2: Si TXT falló → TXT extendido (+5pp antes, +2pp después) ──
        if pdf_fallback and (data is None or not _is_valid_extraction(data)):
            diag = _diagnose_extraction(data)
            print(f"    [1/3] TXT → inválido ({diag})")

            ext_texto = get_extended_txt(txt_path, adapter)
            if ext_texto and len(ext_texto) > len(texto) + 500:
                try:
                    print(f"    [2/3] TXT extendido ({len(ext_texto)} chars, +{TXT_EXT_PAGES_BEFORE}pp/-{TXT_EXT_PAGES_AFTER}pp)...")
                    data_ext = call_llm(ext_texto, anio, nombre_mpio, estado_nombre)
                    if _is_valid_extraction(data_ext):
                        data = data_ext
                        used_ext_txt = True
                        print(f"    [2/3] TXT ext → válido ✓")
                    else:
                        diag2 = _diagnose_extraction(data_ext)
                        print(f"    [2/3] TXT ext → también inválido ({diag2})")
                        if data is None:
                            data = data_ext
                except Exception as e:
                    print(f"    [ERROR] LLM TXT extendido: {e}")
            else:
                reason = "ext_texto=None" if ext_texto is None else f"ext_texto={len(ext_texto)} chars vs original={len(texto)} chars (diff<500)"
                print(f"    [2/3] Sin contexto adicional ({reason}), skip TXT extendido")

        # ── Paso 3: Si TXT extendido también falló → PDF visión ──
        if pdf_fallback and not used_ext_txt and (data is None or not _is_valid_extraction(data)):
            pdf_path = txt_path.with_suffix(".pdf")
            if pdf_path.exists():
                import fitz
                try:
                    with fitz.open(str(pdf_path)) as check_doc:
                        n_pages = len(check_doc)
                except Exception:
                    n_pages = 0

                if n_pages > 20:
                    print(f"    [3/3] PDF tiene {n_pages} páginas — demasiado grande, skip")
                    print(f"    [REVISAR] Segmentación posiblemente falló para este municipio")
                elif n_pages > 0:
                    try:
                        ext_pdf = get_extended_pdf(pdf_path, adapter)
                        n_extra = " (±1pp)" if ext_pdf != pdf_path else ""
                        print(f"    [3/3] PDF visión ({n_pages}pp{n_extra})...")

                        data_pdf = call_llm_vision(ext_pdf, anio, nombre_mpio, estado_nombre)

                        if _is_valid_extraction(data_pdf):
                            data = data_pdf
                            used_pdf = True
                            print(f"    [3/3] PDF → válido ✓")
                        else:
                            diag3 = _diagnose_extraction(data_pdf)
                            print(f"    [3/3] PDF → también inválido ({diag3})")
                            if data is None:
                                data = data_pdf

                        if ext_pdf != pdf_path and ext_pdf.exists():
                            ext_pdf.unlink()

                    except Exception as e:
                        print(f"    [ERROR] Vision PDF: {e}")
                else:
                    print(f"    [3/3] PDF vacío o ilegible")
            else:
                print(f"    [3/3] No hay PDF para fallback")

        if data is None:
            stats["errors"] += 1
            continue

        # Agregar metadata
        data["_meta"] = {
            "fuente": "pdf_vision" if used_pdf else ("txt_extendido" if used_ext_txt else "txt"),
            "modelo": OPENAI_VISION_MODEL if used_pdf else OPENAI_MODEL,
        }

        try:
            with out_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            if used_pdf:
                stats["ok_pdf"] += 1
                print(f"    [OK] → {out_path.name} (vía PDF)")
            elif used_ext_txt:
                stats["ok_ext_txt"] = stats.get("ok_ext_txt", 0) + 1
                print(f"    [OK] → {out_path.name} (vía TXT extendido)")
            else:
                stats["ok_txt"] += 1
                print(f"    [OK] → {out_path.name}")
        except Exception as e:
            print(f"    [ERROR] Guardando: {e}")
            stats["errors"] += 1

    print(f"\n  ── Resumen extracción LLM ──")
    print(f"  TXT encontrados    : {stats['total']}")
    print(f"  JSON vía TXT       : {stats['ok_txt']}")
    if pdf_fallback:
        if stats.get("ok_ext_txt", 0):
            print(f"  JSON vía TXT extend: {stats['ok_ext_txt']}")
        print(f"  JSON vía PDF visión: {stats['ok_pdf']}")
    print(f"  Saltados (existían): {stats['skipped']}")
    print(f"  Errores            : {stats['errors']}")