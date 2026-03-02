"""
Modelos Pydantic que definen la estructura del JSON de salida del LLM.

Beneficios sobre la validación manual del script 25 original:
  1. Tipado fuerte — errores se detectan al instanciar
  2. Serialización/deserialización automática (JSON ↔ objeto Python)
  3. Documentación viva — el esquema ES el código
  4. Compatible con OpenAI Structured Outputs (json_schema en response_format)

El esquema expandido incluye tipos nuevos respecto al original:
  - tasa_unica:  una sola tasa para todos los predios
  - cuota_fija:  monto fijo por predio
  - mixto:       combinación de los anteriores

Changelog:
  - v1: Schema inicial con tarifa_millar, progresivo, tasa_unica, cuota_fija, mixto
  - v2: Agregar minimo_predial, tabla_mixta_rango, ColumnaValor
  - v3: Agregar cuota_fija_adicional a FilaTarifaMillar (tarifa millar + cuota fija)
        Agregar MetaExtraccion para tracking de fuente (txt vs pdf_vision)
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class TipoEsquema(str, Enum):
    """Tipos de esquema de cálculo del impuesto predial."""
    TARIFA_MILLAR = "tarifa_millar"
    PROGRESIVO    = "progresivo"
    TASA_UNICA    = "tasa_unica"
    CUOTA_FIJA    = "cuota_fija"
    MIXTO         = "mixto"
    DESCONOCIDO   = "desconocido"


# ── Submodelos ──

class MinimoPredial(BaseModel):
    """Monto mínimo del impuesto predial (independiente del esquema)."""
    monto: float = Field(description="Monto mínimo en pesos")
    periodicidad: str = Field("bimestral", description="anual | bimestral | mensual")


class CuotaFijaAdicional(BaseModel):
    """
    Cuota fija que se cobra ADEMÁS de la tasa al millar.
    Ej: "$150 más 3.5 al millar sobre el valor catastral".
    Encontrado en: Guanajuato (varios municipios).
    """
    monto: float = Field(description="Monto de la cuota fija adicional")
    periodicidad: str = Field("anual", description="anual | bimestral | mensual")
    unidad: str = Field("pesos", description="pesos | uma | vsm | dias_sm")


class MetaExtraccion(BaseModel):
    """Metadata de la extracción LLM. Incluida en cada JSON de salida."""
    fuente: str = Field(description="txt | pdf_vision — fuente usada para la extracción")
    modelo: str = Field(description="Modelo LLM usado (ej: gpt-5.2)")


# ── Filas de cada tipo de tabla ──

class FilaTarifaMillar(BaseModel):
    """Una fila en la tabla de tasas al millar (por tipo de predio)."""
    grupo: str = Field(description="general | rustico | urbano | otro")
    clave: str = Field(description="identificador_corto_en_snake_case")
    descripcion: str = Field(description="Texto descriptivo corto de la ley")
    tasa_millar: Optional[float] = Field(None, description="Tasa al millar (número decimal)")
    periodicidad: str = Field("anual", description="anual | bimestral")
    cuota_fija_adicional: Optional[CuotaFijaAdicional] = Field(
        None,
        description=(
            "Cuota fija adicional que se cobra junto con la tasa al millar. "
            "Ej: '$150 más 3.5 al millar'. null si no aplica."
        ),
    )


class FilaProgresiva(BaseModel):
    """Una fila en la tabla progresiva por rangos de valor catastral."""
    n_rango: str = Field(description="Número de rango como string ('1', '2', ...)")
    inferior: Optional[str] = Field(None, description="Límite inferior, copiado literal del texto")
    superior: Optional[str] = Field(None, description="Límite superior, copiado literal. null si rango abierto")
    cuota_fija: Optional[str] = Field(None, description="Cuota fija, copiada literal del texto")
    tasa_marginal: Optional[str] = Field(None, description="Tasa marginal, solo número decimal como string")


class FilaTasaUnica(BaseModel):
    """Para municipios con una sola tasa aplicable a todos los predios."""
    descripcion: str = Field(description="Texto descriptivo corto")
    tasa: float = Field(description="Valor numérico de la tasa")
    base_calculo: str = Field(description="valor_catastral | valor_fiscal | otro")
    unidad: str = Field(description="porcentaje | al_millar | al_millar_bimestral")


class FilaCuotaFija(BaseModel):
    """Para municipios con monto fijo por predio sin referencia a valor catastral."""
    descripcion: str = Field(description="Texto descriptivo corto")
    monto: float = Field(description="Monto fijo en pesos")
    periodicidad: str = Field("anual", description="anual | bimestral | mensual")


class ColumnaValor(BaseModel):
    """Valor de una celda en tabla mixta por rango × tipo de predio."""
    valor: float = Field(description="Monto en pesos (cuota fija) o tasa al millar")
    tipo: str = Field(description="cuota_fija | tasa_millar")
    unidad: str = Field(
        "pesos",
        description=(
            "Unidad del valor. "
            "Si tipo='cuota_fija': pesos | uma | vsm | dias_sm. "
            "Si tipo='tasa_millar': al_millar | porcentaje | factor_decimal | pesos_m2. "
            "Default: pesos para cuotas, al_millar para tasas."
        ),
    )


class FilaMixtaRango(BaseModel):
    """Fila en tabla mixta multi-columna (rangos × tipos de predio)."""
    n_rango: str = Field(description="Número de rango como string")
    inferior: str = Field(description="Límite inferior")
    superior: str = Field(description="Límite superior o 'En Adelante'")
    columnas: dict[str, ColumnaValor] = Field(
        description="Clave = tipo de predio (snake_case), valor = ColumnaValor"
    )


# ── Schema principal ──

class PredialSchema(BaseModel):
    """
    Esquema del impuesto predial para un municipio en un ejercicio fiscal.

    Solo una de las tablas debe estar poblada, correspondiente al tipo_esquema.
    Las demás deben estar vacías (excepto "mixto").

    minimo_predial es independiente del tipo de esquema — casi todos los
    municipios lo establecen.
    """
    tipo_esquema: TipoEsquema
    esquema_valido: bool
    comentarios: str = ""
    minimo_predial: Optional[MinimoPredial] = None
    tabla_tarifa_millar: list[FilaTarifaMillar] = []
    tabla_progresiva: list[FilaProgresiva] = []
    tabla_tasa_unica: list[FilaTasaUnica] = []
    tabla_cuota_fija: list[FilaCuotaFija] = []
    tabla_mixta_rango: list[FilaMixtaRango] = []


class PredialOutput(BaseModel):
    """Wrapper raíz: el JSON siempre tiene clave 'predial' en la raíz."""
    predial: PredialSchema
    _meta: Optional[MetaExtraccion] = Field(
        None,
        alias="_meta",
        description="Metadata de extracción (fuente, modelo). Presente en JSONs generados con llm_extract v2+.",
    )