"""Tests para src/extraction/schema_v2.py — discriminated union sobre tipo_esquema.

Regression tests sobre los JSON reales de Chichimilá (Yucatán):
  - 2010: progresivo legítimo (tasa_marginal > 0 en todos los brackets) → valida.
  - 2022: progresivo con tasa_marginal=0 en todos los brackets (el bug) → falla.
  - 2023: cuota_fija (v1) con rangos codificados en descripción; re-mapeado a
          cuota_fija_escalonada (v2) → valida.
"""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.extraction.schema_v2 import (
    CuotaFijaEscalonadaSchema,
    PredialOutputV2,
    ProgresivoSchema,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _to_float(v):
    """Coerce a v1 string/int/float monetario a float, robusta a `$`, `,`,
    espacios y comillas tipográficas (U+2019) que aparecen en docs legales mexicanos."""
    if v is None or isinstance(v, (int, float)):
        return v
    s = (
        str(v)
        .strip()
        .replace("$", "")
        .replace(",", "")
        .replace("\u2019", "")
        .replace("'", "")
        .replace(" ", "")
    )
    return float(s) if s else None


def _v1_progresivo_to_v2(predial_v1: dict) -> dict:
    """Map a v1 progresivo predial dict to v2 schema input.

    - Drops v1-only keys (esquema_valido, tabla_*, unidad_cuota_fija per row).
    - Maps "En Adelante"/"En adelante" → None para superior del último bracket.
    - Snapea cent-gap artifacts (convención "0.01 a N.00, N.01 a ...") para que
      brackets queden contiguos como exige _validate_brackets.
    """
    rows = []
    for r in predial_v1["tabla_progresiva"]:
        sup = r.get("superior")
        sup_v2 = (
            None
            if (isinstance(sup, str) and "adelante" in sup.lower())
            else _to_float(sup)
        )
        rows.append(
            {
                "n_rango": int(r["n_rango"]),
                "inferior": _to_float(r["inferior"]),
                "superior": sup_v2,
                "cuota_fija": _to_float(r["cuota_fija"]),
                "tasa_marginal": _to_float(r["tasa_marginal"]),
            }
        )
    for i in range(len(rows) - 1):
        rows[i + 1]["inferior"] = rows[i]["superior"]

    return {
        "tipo_esquema": "progresivo",
        "tabla": rows,
        "minimo_predial": predial_v1.get("minimo_predial"),
        "comentarios": predial_v1.get("comentarios", ""),
    }


def _v1_cuota_fija_to_v2_escalonada(
    predial_v1: dict, brackets: list[tuple[float, float | None]]
) -> dict:
    """Re-mapea v1 `cuota_fija` (una fila por rango, rango codificado en descripción)
    a v2 `cuota_fija_escalonada` con (inferior, superior) explícitos por fila.

    `brackets` es la lista de (inferior, superior) en el mismo orden que
    predial_v1['tabla_cuota_fija']. Brackets se snapean para quedar contiguos.
    """
    v1_rows = predial_v1["tabla_cuota_fija"]
    assert len(v1_rows) == len(brackets), "mismatch entre v1 rows y brackets provistos"

    snapped: list[tuple[float, float | None]] = []
    for i, (inf, sup) in enumerate(brackets):
        snapped_inf = inf if i == 0 else brackets[i - 1][1]
        snapped.append((snapped_inf, sup))

    tabla = []
    for i, (row, (inf, sup)) in enumerate(zip(v1_rows, snapped), start=1):
        tabla.append(
            {
                "n_rango": i,
                "inferior": inf,
                "superior": sup,
                "monto": _to_float(row["monto"]),
            }
        )
    return {
        "tipo_esquema": "cuota_fija_escalonada",
        "tabla": tabla,
        "minimo_predial": predial_v1.get("minimo_predial"),
        "comentarios": predial_v1.get("comentarios", ""),
    }


class TestChichimilaSchemaV2:
    """Regression tests sobre los JSON reales de Chichimilá (Yucatán)."""

    def test_2010_validates_as_progresivo(self):
        raw = _load("YUC_PREDIAL_2010_chichimila.json")
        v2_predial = _v1_progresivo_to_v2(raw["predial"])
        out = PredialOutputV2.model_validate({"predial": v2_predial})

        assert isinstance(out.predial, ProgresivoSchema)
        assert len(out.predial.tabla) == 9
        assert all(row.tasa_marginal > 0 for row in out.predial.tabla)
        assert out.predial.tabla[-1].superior is None  # último rango abierto

    def test_2022_fails_under_v2_schema(self):
        """2022 declara tipo_esquema=progresivo pero todos los tasa_marginal son 0:
        v2 lo rechaza vía _check_progresivo (must_have_marginal_rate)."""
        raw = _load("YUC_PREDIAL_2022_chichimila.json")
        v2_predial = _v1_progresivo_to_v2(raw["predial"])

        with pytest.raises(ValidationError) as exc:
            PredialOutputV2.model_validate({"predial": v2_predial})

        msg = str(exc.value)
        assert "tasa_marginal" in msg
        assert "cuota_fija_escalonada" in msg

    def test_2023_remapped_to_cuota_fija_escalonada(self):
        """2023 declara cuota_fija (v1) con 8 entradas. Re-mapeado a
        cuota_fija_escalonada (v2) con rangos explícitos extraídos de la
        descripción, valida correctamente."""
        raw = _load("YUC_PREDIAL_2023_chichimila.json")
        brackets: list[tuple[float, float | None]] = [
            (0.01, 10000.00),
            (10000.01, 20000.00),
            (20000.01, 50000.00),
            (50000.01, 80000.00),
            (80000.01, 100000.00),
            (100000.01, 500000.00),
            (500000.01, 1000000.00),
            (1000000.01, None),
        ]
        v2_predial = _v1_cuota_fija_to_v2_escalonada(raw["predial"], brackets)
        out = PredialOutputV2.model_validate({"predial": v2_predial})

        assert isinstance(out.predial, CuotaFijaEscalonadaSchema)
        assert len(out.predial.tabla) == 8
        assert out.predial.tabla[-1].superior is None
        montos = [r.monto for r in out.predial.tabla]
        assert montos == sorted(montos)  # no decrecientes
