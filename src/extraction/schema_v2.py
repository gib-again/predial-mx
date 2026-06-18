"""Schema v2 — discriminated union sobre `tipo_esquema`.

DEPRECADO: usar schema_v3 para nuevas extracciones.  Los submodelos compartidos
(_coerce_to_float, MinimoPredial, CuotaFijaAdicional, MetaExtraccion,
FilaCuotaFijaSimple, FilaCuotaFijaEscalonada, ColumnaValor, FilaMixta,
_validate_brackets) se definen canónicamente en schema_v3 y se re-importan aquí
para compatibilidad retro.

Variantes:
  - tarifa_millar          catálogo categórico de tasas al millar
  - progresivo             brackets con tasa marginal > 0
  - tasa_unica             una sola tasa
  - cuota_fija_simple      una sola cuota fija, sin rangos
  - cuota_fija_escalonada  brackets con monto fijo por rango (no tasa)
  - mixto                  brackets con columnas heterogéneas
  - otro_no_clasificado    escape hatch tipado (descripción + tabla cruda + categoría)
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.extraction.schema_v3 import (  # noqa: F401 — re-exported for v2 consumers
    ColumnaValor,
    CuotaFijaAdicional,
    FilaCuotaFijaEscalonada,
    FilaCuotaFijaSimple,
    FilaMixta,
    MetaExtraccion,
    MinimoPredial,
    _coerce_to_float,
    _validate_brackets,
)


# ── Filas v2 (difieren de v3: sin campo `unidad` en FilaTarifaMillar/FilaProgresiva) ──

class FilaTarifaMillar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grupo: str = Field(description="general | rustico | urbano | otro")
    clave: str = Field(description="identificador_corto_en_snake_case")
    descripcion: str = Field(description="Texto descriptivo corto del renglón")
    tasa_millar: float = Field(description="Tasa al millar (número decimal)")
    periodicidad: str = Field("anual", description="anual | bimestral")
    cuota_fija_adicional: CuotaFijaAdicional | None = Field(
        default=None,
        description="Cuota fija adicional cobrada junto con la tasa. null si no aplica.",
    )

    _coerce_tasa = field_validator("tasa_millar", mode="before")(_coerce_to_float)


class FilaProgresiva(BaseModel):
    """Bracket con tasa marginal sobre el excedente."""
    model_config = ConfigDict(extra="forbid")

    n_rango: int = Field(description="Número de rango (1, 2, 3, ...)")
    inferior: float = Field(description="Límite inferior del rango (≥ 0)", ge=0)
    superior: float | None = Field(
        description="Límite superior del rango. null para el último bracket abierto.",
    )
    cuota_fija: float = Field(description="Cuota base del bracket; puede ser 0 en el primero")
    tasa_marginal: float = Field(description="Tasa sobre el excedente del límite inferior")

    _coerce_inferior = field_validator("inferior", mode="before")(_coerce_to_float)
    _coerce_superior = field_validator("superior", mode="before")(_coerce_to_float)
    _coerce_cuota = field_validator("cuota_fija", mode="before")(_coerce_to_float)
    _coerce_tasa = field_validator("tasa_marginal", mode="before")(_coerce_to_float)


class FilaTasaUnica(BaseModel):
    model_config = ConfigDict(extra="forbid")

    descripcion: str = Field(description="Texto descriptivo corto")
    tasa: float = Field(description="Valor numérico de la tasa o monto por unidad")
    base_calculo: str = Field(
        description=(
            "valor_catastral | valor_fiscal | superficie_m2 | superficie_ha | otro. "
            "Usar superficie_m2 cuando la tarifa es '$X por m²' y superficie_ha "
            "para '$X por hectárea'."
        )
    )
    unidad: Literal[
        "al_millar", "al_ciento", "porcentaje",
        "por_metro_cuadrado", "por_hectarea", "pesos",
    ] = Field(
        description=(
            "Unidad de la tasa. al_millar/al_ciento/porcentaje cuando la base es "
            "valor_catastral; por_metro_cuadrado/por_hectarea cuando la base es "
            "superficie; pesos cuando la 'tasa' es realmente una cuota plana."
        )
    )
    cuota_fija_adicional: CuotaFijaAdicional | None = Field(
        default=None,
        description=(
            "Cuota fija que se cobra ADEMÁS de la tasa única (ej. '$50 + 1.5 al "
            "millar anual'). null si la tarifa es solo la tasa."
        ),
    )

    _coerce_tasa = field_validator("tasa", mode="before")(_coerce_to_float)



# ── Variantes v2 ──

class TarifaMillarSchema(BaseModel):
    """Catálogo de tasas al millar aplicadas sobre valor catastral.

    Una o varias filas categóricas (urbano/rústico/edificado/baldío). NO usar si
    los renglones representan rangos por valor catastral — eso es `progresivo`
    o `cuota_fija_escalonada`.
    """
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["tarifa_millar"]
    tabla: list[FilaTarifaMillar] = Field(
        min_length=1,
        description="Una fila por categoría de predio con su tasa al millar.",
    )
    minimo_predial: MinimoPredial | None = None
    comentarios: str = ""
    clasificacion_justificacion: str | None = Field(
        None,
        description=(
            "Opcional. Si lo llenas, úsalo para señalar peculiaridades menores "
            "(ej. tarifa secundaria de frutos civiles documentada aparte)."
        ),
    )


class ProgresivoSchema(BaseModel):
    """Tabla por rangos de valor catastral con tasa marginal sobre el excedente.

    EXIGE que al menos un bracket tenga `tasa_marginal > 0`. Si todos son 0 y la
    cuota fija varía entre brackets, NO es progresivo — es `cuota_fija_escalonada`.
    """
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["progresivo"]
    tabla: list[FilaProgresiva] = Field(
        min_length=2,
        description="Brackets de valor catastral con tasa marginal positiva en al menos uno.",
    )
    minimo_predial: MinimoPredial | None = None
    comentarios: str = ""
    clasificacion_justificacion: str | None = Field(
        None,
        description=(
            "Opcional. Si lo llenas, úsalo para señalar peculiaridades menores."
        ),
    )

    @model_validator(mode="after")
    def _check_progresivo(self) -> "ProgresivoSchema":
        if not any(row.tasa_marginal > 0 for row in self.tabla):
            raise ValueError(
                "progresivo requiere any(tasa_marginal > 0); si todos son 0, "
                "reclasificar como cuota_fija_escalonada"
            )
        _validate_brackets(self.tabla)
        return self


class TasaUnicaSchema(BaseModel):
    """Una sola tasa aplicada uniformemente al valor catastral, sin categorías ni rangos."""
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["tasa_unica"]
    tabla: list[FilaTasaUnica] = Field(
        min_length=1,
        max_length=1,
        description="Exactamente una entrada con la tasa única.",
    )
    minimo_predial: MinimoPredial | None = None
    comentarios: str = ""
    clasificacion_justificacion: str | None = Field(
        None,
        description=(
            "Opcional. Si lo llenas, úsalo para señalar peculiaridades menores."
        ),
    )


class CuotaFijaSimpleSchema(BaseModel):
    """Cuota fija anual única, sin rangos por valor catastral ni categorías.

    Si hay categorías o rangos en la mecánica PRINCIPAL, usar `tarifa_millar` o
    `cuota_fija_escalonada`. El campo `tarifas_secundarias` permite documentar
    cobros menores (frutos civiles, agropecuarios) sin forzar reclasificación
    a `mixto` cuando esos cobros NO son la mecánica predominante del predial.
    """
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["cuota_fija_simple"]
    tabla: list[FilaCuotaFijaSimple] = Field(
        min_length=1,
        max_length=1,
        description="Exactamente una entrada con el monto fijo principal.",
    )
    tarifas_secundarias: list[str] | None = Field(
        default=None,
        description=(
            "Tarifas paralelas no estructurales (frutos civiles, predios "
            "agropecuarios sobre rentas, etc.) descritas en prosa libre. "
            "Una entrada por tarifa secundaria. null o lista vacía si no aplica. "
            "NO usar para registrar la mecánica principal — esa va en `tabla`."
        ),
    )
    minimo_predial: MinimoPredial | None = None
    comentarios: str = ""
    clasificacion_justificacion: str | None = Field(
        None,
        description=(
            "Opcional. Si lo llenas, úsalo para señalar peculiaridades menores."
        ),
    )


class CuotaFijaEscalonadaSchema(BaseModel):
    """Tabla por rangos de valor catastral donde cada rango paga un MONTO FIJO (no tasa).

    Usar cuando el documento muestra brackets con cuotas en pesos que NO escalan por
    tasa marginal. 2+ filas requeridas; montos no decrecientes entre rangos.
    """
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["cuota_fija_escalonada"]
    tabla: list[FilaCuotaFijaEscalonada] = Field(
        min_length=2,
        description="Brackets de valor catastral con monto fijo por rango.",
    )
    minimo_predial: MinimoPredial | None = None
    comentarios: str = ""
    clasificacion_justificacion: str | None = Field(
        None,
        description=(
            "Opcional. Si lo llenas, úsalo para señalar peculiaridades menores."
        ),
    )

    @model_validator(mode="after")
    def _check_cuota_fija_escalonada(self) -> "CuotaFijaEscalonadaSchema":
        montos = [r.monto for r in self.tabla]
        for i in range(len(montos) - 1):
            if montos[i] > montos[i + 1]:
                raise ValueError(
                    f"cuota_fija_escalonada: montos deben ser no decrecientes "
                    f"(rango {self.tabla[i].n_rango}={montos[i]} > "
                    f"rango {self.tabla[i+1].n_rango}={montos[i+1]})"
                )
        _validate_brackets(self.tabla)
        return self


class MixtoSchema(BaseModel):
    """Estructura híbrida: brackets que combinan tasa marginal Y cuota fija con varias
    columnas heterogéneas que no caben en las otras variantes. Si reduce a una de las
    anteriores, usar esa.
    """
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["mixto"]
    tabla: list[FilaMixta] = Field(
        min_length=2,
        description="Brackets con columnas heterogéneas (mezcla de tasa y cuota).",
    )
    minimo_predial: MinimoPredial | None = None
    comentarios: str = Field(
        description="Obligatorio: describir la mezcla y por qué no encaja en las variantes simples."
    )
    clasificacion_justificacion: str | None = Field(
        None,
        description=(
            "Texto de 1-3 líneas que articula la heterogeneidad detectada por el "
            "TEST DE HETEROGENEIDAD (prompt V3). Formato sugerido: "
            "'Heterogeneidad en [FILA|COLUMNA|BRACKET]: [filas/cols con unidad U] "
            "vs [filas/cols con unidad V]. Patrón: [A|B|C|otro].' "
            "Opcional por compatibilidad retro; el prompt V3 lo pedirá no vacío."
        ),
    )

    @model_validator(mode="after")
    def _check_mixto(self) -> "MixtoSchema":
        if not self.comentarios.strip():
            raise ValueError("mixto requiere comentarios no vacíos describiendo la mezcla")
        _validate_brackets(self.tabla)
        return self


class OtroNoClasificadoSchema(BaseModel):
    """ESCAPE HATCH tipado.

    Usar si la estructura no encaja en las variantes anteriores, o si no se encontró
    tabla alguna (segmento vacío, municipio sin impuesto detectable, error de
    segmentación). Exige justificación textual y categoría — NO inventar campos.
    Preferir esto sobre forzar una clasificación incorrecta.
    """
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["otro_no_clasificado"]
    categoria: Literal[
        "estructura_no_estandar",
        "segmento_vacio",
        "error_segmentacion",
        "municipio_sin_impuesto",
    ] = Field(
        description=(
            "Por qué se cae al escape hatch — guía para QA downstream. "
            "estructura_no_estandar: tabla existe pero no encaja en las 6 variantes. "
            "segmento_vacio: el chunk llegó sin contenido tarifario. "
            "error_segmentacion: texto fragmentado o cortado. "
            "municipio_sin_impuesto: el documento parece no establecer predial."
        ),
    )
    descripcion_estructural: str = Field(
        description=(
            "1-3 oraciones explicando qué se observó y por qué no aplica ninguna "
            "variante. OBLIGATORIA — no permitir vacío."
        ),
    )
    tabla_cruda: list[dict] = Field(
        default_factory=list,
        description=(
            "Filas tal cual aparecen en el documento, claves libres. "
            "Lista vacía válida cuando no se encontró tabla."
        ),
    )
    minimo_predial: MinimoPredial | None = None
    comentarios: str = ""
    clasificacion_justificacion: str | None = Field(
        None,
        description=(
            "Opcional. Si lo llenas, úsalo para señalar peculiaridades menores."
        ),
    )

    @model_validator(mode="after")
    def _check_descripcion(self) -> "OtroNoClasificadoSchema":
        if not self.descripcion_estructural.strip():
            raise ValueError("otro_no_clasificado requiere descripcion_estructural no vacía")
        return self


# ── Discriminated union ──

PredialSchemaV2 = Annotated[
    Union[
        TarifaMillarSchema,
        ProgresivoSchema,
        TasaUnicaSchema,
        CuotaFijaSimpleSchema,
        CuotaFijaEscalonadaSchema,
        MixtoSchema,
        OtroNoClasificadoSchema,
    ],
    Field(discriminator="tipo_esquema"),
]


class PredialOutputV2(BaseModel):
    """Wrapper raíz: el JSON siempre tiene clave 'predial' en la raíz.

    El campo `_meta` se acepta tanto por nombre (`meta`) como por alias (`_meta`)
    gracias a `populate_by_name=True`, lo que permite leer JSONs existentes que
    usan la clave subrayada y serializar con el mismo nombre al guardar.
    """
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    predial: PredialSchemaV2
    meta: MetaExtraccion | None = Field(
        default=None,
        alias="_meta",
        description="Metadata de extracción (fuente, modelo).",
    )
