"""Schema v3 — contenedor multi-tarifa con transcripción fiel de tasas.

Cambios principales respecto a v2:
  1. Contenedor `TarifaPredial` agrupa ambito + base_gravable + esquema.
     `PredialV3.tarifas` es una lista de tarifas paralelas (≥1).
  2. `FilaProgresiva` y `FilaTarifaMillar` añaden `unidad` para tasas fieles
     (sin reescalar: "1.58 al millar" → tasa=1.58, unidad=al_millar).
  3. `BloqueProgresivo` permite escalas progresivas diferenciadas por categoría.
  4. `FilaTasaUnica` pierde `base_calculo` (plegado en `TarifaPredial.base_gravable`).
  5. `CuotaFijaSimpleSchema` pierde `tarifas_secundarias` (superado por multi-tarifa).
  6. Todas las variantes pierden `minimo_predial`, `comentarios`,
     `clasificacion_justificacion` (suben a nivel tarifa/raíz).

Reutiliza de schema_v2 los submodelos sin cambios:
  _coerce_to_float, MinimoPredial, CuotaFijaAdicional, MetaExtraccion,
  FilaCuotaFijaSimple, FilaCuotaFijaEscalonada, ColumnaValor, FilaMixta,
  _validate_brackets.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.extraction.schema_v2 import (
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

__all__ = [
    "MinimoPredial",
    "CuotaFijaAdicional",
    "MetaExtraccion",
    "FilaTarifaMillar",
    "FilaProgresiva",
    "FilaTasaUnica",
    "FilaCuotaFijaSimple",
    "FilaCuotaFijaEscalonada",
    "ColumnaValor",
    "FilaMixta",
    "BloqueProgresivo",
    "TarifaMillarSchema",
    "ProgresivoSchema",
    "TasaUnicaSchema",
    "CuotaFijaSimpleSchema",
    "CuotaFijaEscalonadaSchema",
    "MixtoSchema",
    "OtroNoClasificadoSchema",
    "EsquemaPredial",
    "TarifaPredial",
    "PredialV3",
    "ProcedenciaInfo",
    "PredialOutputV3",
]


# ── Filas modificadas para v3 ──

class FilaTarifaMillar(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grupo: str = Field(description="general | rustico | urbano | otro")
    clave: str = Field(description="identificador_corto_en_snake_case")
    descripcion: str = Field(description="Texto descriptivo corto del renglón")
    tasa_millar: float = Field(description="Tasa al millar fiel al texto (sin reescalar)")
    unidad: Literal["al_millar", "al_ciento", "porcentaje"] = Field(
        "al_millar",
        description="Escala de tasa_millar. Default al_millar; cubre catálogos raros en %.",
    )
    periodicidad: str = Field("anual", description="anual | bimestral")
    cuota_fija_adicional: CuotaFijaAdicional | None = Field(
        default=None,
        description="Cuota fija adicional cobrada junto con la tasa. null si no aplica.",
    )

    _coerce_tasa = field_validator("tasa_millar", mode="before")(_coerce_to_float)


class FilaProgresiva(BaseModel):
    """Bracket con tasa marginal sobre el excedente. v3: incluye `unidad`."""
    model_config = ConfigDict(extra="forbid")

    n_rango: int = Field(description="Número de rango (1, 2, 3, ...)")
    inferior: float = Field(description="Límite inferior del rango (≥ 0)", ge=0)
    superior: float | None = Field(
        description="Límite superior del rango. null para el último bracket abierto.",
    )
    cuota_fija: float = Field(
        description="Cuota base del bracket en pesos; puede ser 0 en el primero",
    )
    tasa_marginal: float = Field(
        description="Tasa sobre el excedente, fiel al texto (sin reescalar)",
    )
    unidad: Literal["al_millar", "al_ciento", "porcentaje"] = Field(
        description="Escala de tasa_marginal. OBLIGATORIO — sin este campo el número es ambiguo.",
    )

    _coerce_inferior = field_validator("inferior", mode="before")(_coerce_to_float)
    _coerce_superior = field_validator("superior", mode="before")(_coerce_to_float)
    _coerce_cuota = field_validator("cuota_fija", mode="before")(_coerce_to_float)
    _coerce_tasa = field_validator("tasa_marginal", mode="before")(_coerce_to_float)


class FilaTasaUnica(BaseModel):
    """v3: sin `base_calculo` (plegado en `TarifaPredial.base_gravable`)."""
    model_config = ConfigDict(extra="forbid")

    descripcion: str = Field(description="Texto descriptivo corto")
    tasa: float = Field(description="Valor numérico fiel al texto (sin reescalar)")
    unidad: Literal[
        "al_millar", "al_ciento", "porcentaje",
        "por_metro_cuadrado", "por_hectarea", "pesos",
    ] = Field(
        description=(
            "Escala de la tasa. al_millar/al_ciento/porcentaje para base valor; "
            "por_metro_cuadrado/por_hectarea para superficie; pesos para cuota plana."
        ),
    )
    cuota_fija_adicional: CuotaFijaAdicional | None = Field(
        default=None,
        description="Cuota fija cobrada ADEMÁS de la tasa. null si no aplica.",
    )

    _coerce_tasa = field_validator("tasa", mode="before")(_coerce_to_float)


# ── Bloque progresivo (nuevo en v3) ──

class BloqueProgresivo(BaseModel):
    """Tabla progresiva para UNA categoría. Brackets independientes entre bloques."""
    model_config = ConfigDict(extra="forbid")

    categoria: str = Field(
        description=(
            "Categoría de predio en snake_case. 'general' si la escala "
            "progresiva no se diferencia por tipo de predio."
        ),
    )
    tabla: list[FilaProgresiva] = Field(min_length=2)


# ── Variantes v3 (sin minimo_predial / comentarios / clasificacion_justificacion) ──

class TarifaMillarSchema(BaseModel):
    """Catálogo de tasas al millar por categoría de predio."""
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["tarifa_millar"]
    tabla: list[FilaTarifaMillar] = Field(
        min_length=1,
        description="Una fila por categoría de predio con su tasa.",
    )


class ProgresivoSchema(BaseModel):
    """Brackets con tasa marginal, organizados en bloques por categoría."""
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["progresivo"]
    bloques: list[BloqueProgresivo] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_progresivo(self) -> "ProgresivoSchema":
        all_rows = [r for b in self.bloques for r in b.tabla]
        if not any(r.tasa_marginal > 0 for r in all_rows):
            raise ValueError(
                "progresivo requiere any(tasa_marginal > 0); si todos "
                "son 0, usar cuota_fija_escalonada"
            )
        for b in self.bloques:
            _validate_brackets(b.tabla)
        cats = [b.categoria for b in self.bloques]
        if len(cats) != len(set(cats)):
            raise ValueError("categorías duplicadas entre bloques")
        return self


class TasaUnicaSchema(BaseModel):
    """Una sola tasa aplicada uniformemente."""
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["tasa_unica"]
    tabla: list[FilaTasaUnica] = Field(
        min_length=1,
        max_length=1,
        description="Exactamente una entrada con la tasa única.",
    )


class CuotaFijaSimpleSchema(BaseModel):
    """Cuota fija única, sin rangos ni categorías."""
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["cuota_fija_simple"]
    tabla: list[FilaCuotaFijaSimple] = Field(
        min_length=1,
        max_length=1,
        description="Exactamente una entrada con el monto fijo.",
    )


class CuotaFijaEscalonadaSchema(BaseModel):
    """Brackets con monto fijo por rango (sin tasa marginal)."""
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["cuota_fija_escalonada"]
    tabla: list[FilaCuotaFijaEscalonada] = Field(
        min_length=2,
        description="Brackets con monto fijo por rango.",
    )

    @model_validator(mode="after")
    def _check_cuota_fija_escalonada(self) -> "CuotaFijaEscalonadaSchema":
        montos = [r.monto for r in self.tabla]
        for i in range(len(montos) - 1):
            if montos[i] > montos[i + 1]:
                raise ValueError(
                    f"cuota_fija_escalonada: montos deben ser no decrecientes "
                    f"(rango {self.tabla[i].n_rango}={montos[i]} > "
                    f"rango {self.tabla[i + 1].n_rango}={montos[i + 1]})"
                )
        _validate_brackets(self.tabla)
        return self


class MixtoSchema(BaseModel):
    """Brackets con columnas heterogéneas (mezcla de tasa y cuota fija)."""
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["mixto"]
    tabla: list[FilaMixta] = Field(
        min_length=2,
        description="Brackets con columnas heterogéneas.",
    )

    @model_validator(mode="after")
    def _check_mixto(self) -> "MixtoSchema":
        _validate_brackets(self.tabla)
        return self


class OtroNoClasificadoSchema(BaseModel):
    """Escape hatch tipado."""
    model_config = ConfigDict(extra="forbid")

    tipo_esquema: Literal["otro_no_clasificado"]
    categoria: Literal[
        "estructura_no_estandar",
        "segmento_vacio",
        "error_segmentacion",
        "municipio_sin_impuesto",
    ] = Field(
        description=(
            "Por qué se cae al escape hatch. "
            "estructura_no_estandar: tabla existe pero no encaja. "
            "segmento_vacio: sin contenido tarifario. "
            "error_segmentacion: texto fragmentado/cortado. "
            "municipio_sin_impuesto: no establece predial."
        ),
    )
    descripcion_estructural: str = Field(
        description="1-3 oraciones explicando qué se observó. OBLIGATORIA.",
    )
    tabla_cruda: list[dict] = Field(
        default_factory=list,
        description="Filas tal cual del documento, claves libres. Vacío si no hay tabla.",
    )

    @model_validator(mode="after")
    def _check_descripcion(self) -> "OtroNoClasificadoSchema":
        if not self.descripcion_estructural.strip():
            raise ValueError("otro_no_clasificado requiere descripcion_estructural no vacía")
        return self


# ── Discriminated union ──

EsquemaPredial = Annotated[
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


# ── Contenedor de tarifa y raíz v3 ──

class TarifaPredial(BaseModel):
    """Una tarifa del predial. Un municipio-año puede tener varias en paralelo
    (urbano con brackets + rústico plano + agropecuario por hectárea)."""
    model_config = ConfigDict(extra="forbid")

    ambito: Literal[
        "urbano", "suburbano", "rustico", "rural",
        "agropecuario", "general", "otro",
    ] = Field(
        description=(
            "Alcance de ESTA tarifa = la partición de predios a la que aplica "
            "como bloque legalmente distinto. 'general' si aplica a todos."
        ),
    )
    ambito_detalle: str | None = Field(
        None,
        description="Texto libre para precisar el ámbito o cuando ambito='otro'.",
    )
    base_gravable: Literal[
        "valor_catastral", "valor_fiscal", "valor_real",
        "superficie_m2", "superficie_ha", "renta_civil", "otro",
    ] = Field(
        description=(
            "Base sobre la que se calcula ESTA tarifa. valor_catastral por defecto; "
            "superficie_m2/ha para cuotas por superficie; valor_fiscal/valor_real "
            "cuando la ley lo nombra; renta_civil para frutos civiles."
        ),
    )
    esquema: EsquemaPredial = Field(
        description="Estructura tarifaria (1 de las 7 variantes).",
    )
    minimo_predial: MinimoPredial | None = Field(
        None,
        description=(
            "Override del mínimo SOLO si esta tarifa tiene piso propio "
            "distinto al del municipio. null si usa el mínimo general."
        ),
    )


class PredialV3(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tarifas: list[TarifaPredial] = Field(
        min_length=1,
        description=(
            "Todas las tarifas del predial. Cada tarifa paralela es una "
            "entrada; NO volcar tarifas en prosa."
        ),
    )
    minimo_predial_general: MinimoPredial | None = Field(
        None,
        description=(
            "Mínimo a nivel municipio (común). Las tarifas con piso "
            "propio lo sobrescriben en su campo minimo_predial."
        ),
    )
    comentarios: str = ""


# ── Procedencia (metadata de orquestador, no del LLM) ──

class ProcedenciaInfo(BaseModel):
    """Registro del archivo y páginas de la etapa de extracción ganadora."""
    model_config = ConfigDict(extra="forbid")

    archivo_pdf: str | None = Field(
        None, description="Ruta relativa del PDF a abrir en HITL.",
    )
    archivo_txt: str | None = Field(
        None, description="Ruta relativa del TXT usado, o null.",
    )
    paginas: list[int] | None = Field(
        None, description="Páginas 1-indexed dentro de archivo_pdf.",
    )
    fuente_ganadora: Literal["txt", "pdf_reocr", "pdf_vision"] = Field(
        description="Etapa que produjo la extracción aceptada.",
    )
    origen_override: bool = Field(
        False, description="True si se usó un override manual de PDF.",
    )


# ── Output raíz ──

class PredialOutputV3(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    predial: PredialV3
    meta: MetaExtraccion | None = Field(
        default=None,
        alias="_meta",
        description="Metadata de extracción (fuente, modelo). Siempre null en output LLM.",
    )
