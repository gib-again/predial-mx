"""Tests para la categoría remite_a_ley_externa (esquema + detector D5).

Captura explícita del caso en que la ley de ingresos no fija la tarifa del
predial sino que remite a la Ley de Hacienda Municipal / Código Fiscal.
"""

import pytest

from src.extraction.schema_v2 import OtroNoClasificadoSchema as V2Otro
from src.extraction.schema_v3 import OtroNoClasificadoSchema as V3Otro
from src.hitl.detectors import det_otro_no_clasificado


@pytest.mark.parametrize("Model", [V2Otro, V3Otro])
def test_categoria_remite_valida(Model):
    o = Model(
        tipo_esquema="otro_no_clasificado",
        categoria="remite_a_ley_externa",
        descripcion_estructural="Remite a la Ley de Hacienda Municipal.",
    )
    assert o.categoria == "remite_a_ley_externa"


def _doc(categoria: str) -> dict:
    return {"predial": {"tarifas": [{
        "ambito": "general",
        "esquema": {
            "tipo_esquema": "otro_no_clasificado",
            "categoria": categoria,
            "descripcion_estructural": "x",
        },
    }]}}


def test_detector_remite_es_baja_severidad():
    rows = det_otro_no_clasificado(_doc("remite_a_ley_externa"), "guanajuato",
                                   "abasolo", 2024, "p.json")
    assert len(rows) == 1
    assert rows[0].severidad == "SEV3"
    assert rows[0].detector == "remite_a_ley_externa"


def test_detector_otra_categoria_sigue_sev1():
    rows = det_otro_no_clasificado(_doc("estructura_no_estandar"), "guanajuato",
                                   "abasolo", 2024, "p.json")
    assert len(rows) == 1
    assert rows[0].severidad == "SEV1"
    assert rows[0].detector == "otro_no_clasificado"
