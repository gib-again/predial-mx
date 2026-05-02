"""
Registry de adaptadores de estado.

Para agregar un estado nuevo:
  1. Crear src/estados/{slug}/ con __init__.py, config.py, download.py, segment.py
  2. Importar y registrar aquí
"""

from src.estados.base import EstadoAdapter

_REGISTRY: dict[str, type[EstadoAdapter]] = {}


def register(cls: type[EstadoAdapter]):
    """Decorador para registrar un adaptador."""
    instance = cls()
    _REGISTRY[instance.slug] = cls
    return cls


def get_adapter(estado_slug: str) -> EstadoAdapter:
    """Factory: devuelve instancia del adaptador para el estado dado."""
    cls = _REGISTRY.get(estado_slug.lower())
    if cls is None:
        available = ", ".join(sorted(_REGISTRY.keys())) or "(ninguno)"
        raise ValueError(
            f"Estado '{estado_slug}' no registrado. Disponibles: {available}"
        )
    return cls()


def list_estados() -> list[str]:
    """Retorna lista de estados registrados."""
    return sorted(_REGISTRY.keys())


# ── Auto-importar adaptadores para que se registren ──
# Agregar una línea por cada estado implementado.
import src.estados.coahuila  # noqa: F401, E402
import src.estados.jalisco   # noqa: F401, E402
import src.estados.yucatan   # noqa: F401, E402
import src.estados.queretaro # noqa: F401, E402
import src.estados.tamaulipas # noqa: F401, E402
import src.estados.chihuahua # noqa: F401, E402
import src.estados.colima    # noqa: F401, E402
import src.estados.edomex    # noqa: F401, E402
import src.estados.sinaloa   # noqa: F401, E402
import src.estados.tabasco   # noqa: F401, E402
import src.estados.guanajuato # noqa: F401, E402
import src.estados.oaxaca     # noqa: F401, E402
import src.estados.sanluispotosi  # noqa: F401, E402