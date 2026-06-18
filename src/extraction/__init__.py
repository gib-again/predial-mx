"""Extraction layer: schemas Pydantic, extractores LLM, utilidades compartidas.

Canonical source: schema_v3, llm_extract_v3, llm_utils.
Legacy: schema_v2, llm_extract_v2 (thin wrappers).
"""

from src.extraction.schema_v3 import (
    ColumnaValor,
    CuotaFijaAdicional,
    FilaCuotaFijaEscalonada,
    FilaCuotaFijaSimple,
    FilaMixta,
    MetaExtraccion,
    MinimoPredial,
    OtroNoClasificadoSchema,
)

from src.extraction.schema_v2 import (
    CuotaFijaEscalonadaSchema,
    CuotaFijaSimpleSchema,
    MixtoSchema,
    PredialOutputV2,
    PredialSchemaV2,
    ProgresivoSchema,
    TarifaMillarSchema,
    TasaUnicaSchema,
)

# v2-only row types (differ from v3 versions)
from src.extraction.schema_v2 import (
    FilaProgresiva,
    FilaTarifaMillar,
    FilaTasaUnica,
)

__all__ = [
    "ColumnaValor",
    "CuotaFijaAdicional",
    "CuotaFijaEscalonadaSchema",
    "CuotaFijaSimpleSchema",
    "FilaCuotaFijaEscalonada",
    "FilaCuotaFijaSimple",
    "FilaMixta",
    "FilaProgresiva",
    "FilaTarifaMillar",
    "FilaTasaUnica",
    "MetaExtraccion",
    "MinimoPredial",
    "MixtoSchema",
    "OtroNoClasificadoSchema",
    "PredialOutputV2",
    "PredialSchemaV2",
    "ProgresivoSchema",
    "TarifaMillarSchema",
    "TasaUnicaSchema",
]
