# Arquitectura Definitiva: `predial-mx`
## Pipeline de extracción de tasas de impuesto predial municipal

---

## 1. Parámetros del proyecto

| Parámetro | Valor |
|-----------|-------|
| Ejercicios fiscales | 2010–2025 (16 años) |
| Estados objetivo | 10–15 (4 completados: Coahuila, Jalisco, Querétaro, Yucatán) |
| Catálogo de municipios | INEGI, disponible para todo México |
| LLM | API de GPT-5.1 (OpenAI Responses API) |
| OCR | Tesseract local (solo para estados con PDFs escaneados) |
| Entregables | JSONs individuales + CSV panel consolidado |
| Fase posterior | Índice de carga legal (escalar comparable entre municipios) |
| Periódicos Oficiales | Todos disponibles en línea |

---

## 2. Estructura de directorio

```
predial-mx/
│
├── pyproject.toml                  # Dependencias (un solo env para todo)
├── README.md                       # Documentación del proyecto
├── .gitignore
│
├── catalogs/                       # Catálogos de referencia (INEGI, etc.)
│   ├── municipios_inegi.csv        # Catálogo completo de municipios
│   └── estados_target.csv          # Lista de estados a procesar con metadata
│
├── src/
│   ├── __init__.py
│   │
│   ├── core/                       # Lógica compartida — NO varía por estado
│   │   ├── __init__.py
│   │   ├── pdf_utils.py            # Lectura de PDFs, offsets, recorte
│   │   ├── text_utils.py           # Normalización, slugify, parseo de montos
│   │   ├── ocr.py                  # Wrapper Tesseract + detección de escaneado
│   │   ├── llm_extract.py          # Llamadas a OpenAI, prompts, retry logic
│   │   ├── validation.py           # Validación estructural + interanual
│   │   ├── schemas.py              # Modelos Pydantic del JSON de salida
│   │   ├── consolidate.py          # Generación del CSV panel
│   │   └── constants.py            # Constantes globales (EJERCICIO_INI, EJERCICIO_FIN, etc.)
│   │
│   └── estados/                    # Un módulo por estado
│       ├── __init__.py             # Registry de adaptadores
│       ├── base.py                 # Clase abstracta EstadoAdapter
│       │
│       ├── coahuila/
│       │   ├── __init__.py
│       │   ├── config.py           # URLs, prefijo de archivos, flags (needs_ocr, etc.)
│       │   ├── download.py         # Scraping del PO de Coahuila (hoy: 01_coah_*)
│       │   └── segment.py          # Master + sección predial (hoy: 03, 04, 05, 10)
│       │
│       ├── jalisco/
│       │   ├── __init__.py
│       │   ├── config.py
│       │   ├── download.py
│       │   └── segment.py
│       │
│       ├── queretaro/
│       │   └── ...
│       │
│       └── yucatan/
│           └── ...
│
├── data/                           # Datos por estado (estructura idéntica)
│   ├── coahuila/
│   │   ├── pdf_raw/                # PDFs descargados del PO
│   │   │   └── {ejercicio}/        # Subdirectorio por año
│   │   ├── pdf_ocr/                # PDFs post-OCR (solo si needs_ocr=True)
│   │   │   └── {ejercicio}/
│   │   ├── meta/                   # CSVs de índice y bitácora
│   │   │   ├── ley_ingresos_index.csv
│   │   │   ├── predial_master.csv
│   │   │   └── predial_sections.csv
│   │   ├── focus_predial/          # Texto y PDF recortados de sección predial
│   │   │   └── {ejercicio}/
│   │   │       ├── {ESTADO}_{ejercicio}_{muni_slug}.txt
│   │   │       └── {ESTADO}_{ejercicio}_{muni_slug}.pdf
│   │   └── json_predial/           # Salida del LLM
│   │       └── {ejercicio}/
│   │           └── {ESTADO}_{ejercicio}_{muni_slug}.json
│   │
│   ├── jalisco/
│   │   └── ...  (misma estructura)
│   └── ...
│
├── output/                         # Productos finales consolidados
│   ├── predial_panel.csv           # Panel: 1 fila por (estado, municipio, año)
│   ├── quality_report.csv          # Anomalías, cobertura, flags
│   └── schema_summary.csv          # Distribución de tipos de esquema
│
├── scripts/                        # Puntos de entrada CLI
│   ├── run_pipeline.py             # Orquestador principal
│   └── consolidate_panel.py        # Genera el CSV panel desde todos los JSONs
│
├── docs/                           # Documentación de decisiones
│   ├── esquemas_predial.md         # Catálogo de tipos de esquema encontrados
│   └── notas_por_estado.md         # Particularidades de cada PO
│
└── tests/
    ├── test_text_utils.py
    ├── test_validation.py
    └── fixtures/                   # JSONs de ejemplo para tests
```

### Notas sobre la estructura de `data/`

**Convención de nombres de archivo unificada**:
```
{PREFIJO_ESTADO}_{ejercicio}_{muni_slug}.{ext}
```

Donde `PREFIJO_ESTADO` es un código corto por estado:

| Estado | Prefijo | Ejemplo de archivo |
|--------|---------|-------------------|
| Coahuila | `COAH` | `COAH_2018_saltillo.json` |
| Jalisco | `JAL` | `JAL_2020_guadalajara.json` |
| Querétaro | `QRO` | `QRO_2015_queretaro.json` |
| Yucatán | `YUC` | `YUC_2022_merida.json` |

Esta convención ya la usas en Coahuila; solo hay que estandarizarla.

---

## 3. Código compartido (`core/`)

### 3.1 `core/pdf_utils.py`

Unifica las funciones que hoy están duplicadas en tus scripts 03, 04, 05 y 10:

```python
"""Utilidades para lectura, indexación y recorte de PDFs."""

from pathlib import Path
from typing import Optional
import pdfplumber
from pypdf import PdfReader, PdfWriter


def build_text_and_offsets(pdf_path: Path) -> tuple[str, list[int]]:
    """
    Lee un PDF y devuelve:
      - raw_text: texto concatenado de todas las páginas
      - page_starts: índice de carácter donde inicia cada página (0-based)

    Hoy tienes esta función copiada en:
      03_coah_predial_master.py (línea ~30)
      04_patch_predial_master_2017.py (línea ~14)
      10_coah_predial_sections.py (línea ~30)
    """
    parts = []
    page_starts = []
    cursor = 0
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_starts.append(cursor)
            t = page.extract_text() or ""
            parts.append(t)
            parts.append("\n")
            cursor += len(t) + 1
    return "".join(parts), page_starts


def idx_to_page(idx: int, page_starts: list[int]) -> int:
    """Convierte índice de carácter a número de página (1-based)."""
    page = 0
    for i, start in enumerate(page_starts):
        if start <= idx:
            page = i
        else:
            break
    return page + 1


def save_pdf_slice(
    pdf_path: Path,
    page_start: int,
    page_end: int,
    out_path: Path,
) -> None:
    """Recorta un PDF entre page_start y page_end (1-based, inclusive)."""
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    n_pages = len(reader.pages)
    s = max(1, page_start)
    e = min(n_pages, page_end)
    for p in range(s - 1, e):
        writer.add_page(reader.pages[p])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("wb") as f:
        writer.write(f)


def is_scanned_pdf(pdf_path: Path, sample_pages: int = 3) -> bool:
    """
    Heurística: si las primeras N páginas tienen muy poco texto
    extraíble, probablemente es un PDF escaneado que necesita OCR.
    """
    with pdfplumber.open(pdf_path) as pdf:
        pages_to_check = pdf.pages[:sample_pages]
        total_chars = sum(len(p.extract_text() or "") for p in pages_to_check)
    # Umbral: menos de 50 caracteres por página en promedio
    return (total_chars / max(len(pages_to_check), 1)) < 50
```

### 3.2 `core/text_utils.py`

```python
"""Normalización de texto, slugify, y parseo de montos."""

import re
from unidecode import unidecode


def norm(s: str) -> str:
    """Sin acentos, mayúsculas, stripped. Usada para matching de municipios."""
    return unidecode((s or "").strip()).upper()


def slugify(s: str) -> str:
    """Convierte nombre de municipio a slug filesystem-safe."""
    n = norm(s)
    return (
        n.replace(" ", "_")
         .replace("/", "_")
         .replace(".", "")
         .lower()
    ) or "sin_municipio"


def parse_monto_to_float(monto_str) -> float | None:
    """
    Parsea montos en formato US ($1,234.56) y europeo ($1.234,56).
    Maneja: '$620,100.00', '$183.818,00', '60,000', '$0,01', etc.

    Hoy está en 25_json_consistency.py líneas 65-133.
    """
    if monto_str is None:
        return None
    if isinstance(monto_str, (int, float)):
        return float(monto_str)

    s = str(monto_str).strip()
    s = re.sub(r"[^0-9,.\-]", "", s)
    if not re.search(r"\d", s):
        return None

    has_dot = "." in s
    has_comma = "," in s

    if has_dot and has_comma:
        last_dot = s.rfind(".")
        if last_dot < s.rfind(","):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif has_comma and not has_dot:
        if s.count(",") > 1:
            s = s.replace(".", "").replace(",", ".")
        else:
            left, right = s.split(",")
            if len(right) in (1, 2):
                s = s.replace(".", "").replace(",", ".")
            else:
                s = s.replace(",", "")
    else:
        s = s.replace(",", "")

    try:
        return float(s)
    except Exception:
        return None
```

### 3.3 `core/schemas.py` — Modelo de datos

```python
"""
Modelos Pydantic que definen la estructura del JSON de salida del LLM.

Beneficios sobre la validación manual actual:
  1. Tipado fuerte — errores se detectan al instanciar, no en post-proceso
  2. Serialización/deserialización automática (json <-> objeto Python)
  3. Documentación viva — el esquema ES el código
  4. Compatible con OpenAI Structured Outputs si decides usarlo después
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class TipoEsquema(str, Enum):
    TARIFA_MILLAR = "tarifa_millar"
    PROGRESIVO    = "progresivo"
    TASA_UNICA    = "tasa_unica"
    CUOTA_FIJA    = "cuota_fija"
    MIXTO         = "mixto"
    DESCONOCIDO   = "desconocido"


class FilaTarifaMillar(BaseModel):
    """Una fila en la tabla de tasas al millar (por tipo de predio)."""
    grupo: str = Field(description="general | rustico | urbano | otro")
    clave: str = Field(description="identificador_corto_en_snake_case")
    descripcion: str = Field(description="Texto descriptivo corto de la ley")
    tasa_millar: Optional[float] = Field(None, description="Tasa al millar (decimal)")
    cuota_fija: Optional[float] = Field(0.0, description="Cuota fija en pesos")


class FilaProgresiva(BaseModel):
    """Una fila en la tabla progresiva por rangos de valor."""
    n_rango: str
    inferior: Optional[str] = Field(description="Límite inferior, copiado literal")
    superior: Optional[str] = Field(description="Límite superior, copiado literal. null si rango abierto")
    cuota_fija: Optional[str] = Field(description="Cuota fija, copiada literal")
    tasa_marginal: Optional[str] = Field(description="Tasa marginal, solo número decimal")


class FilaTasaUnica(BaseModel):
    """Para municipios con una sola tasa aplicable a todos los predios."""
    descripcion: str
    tasa: float = Field(description="Valor numérico de la tasa")
    base_calculo: str = Field(description="valor_catastral | valor_fiscal | otro")
    unidad: str = Field(description="porcentaje | al_millar | al_millar_bimestral")


class FilaCuotaFija(BaseModel):
    """Para municipios con monto fijo por predio sin referencia a valor."""
    descripcion: str
    monto: float = Field(description="Monto fijo en pesos")
    periodicidad: str = Field("anual", description="anual | bimestral | mensual")


class PredialSchema(BaseModel):
    """Esquema raíz del JSON de salida del LLM."""
    tipo_esquema: TipoEsquema
    esquema_valido: bool
    comentarios: str = ""
    tabla_tarifa_millar: list[FilaTarifaMillar] = []
    tabla_progresiva: list[FilaProgresiva] = []
    tabla_tasa_unica: list[FilaTasaUnica] = []
    tabla_cuota_fija: list[FilaCuotaFija] = []


class PredialOutput(BaseModel):
    """Wrapper: el JSON siempre tiene clave 'predial' en la raíz."""
    predial: PredialSchema
```

### 3.4 `core/constants.py`

```python
"""Constantes globales del proyecto."""

EJERCICIO_INI = 2010
EJERCICIO_FIN = 2025  # inclusive

# Prefijos por estado (para nombres de archivo)
PREFIJOS_ESTADO = {
    "coahuila":  "COAH",
    "jalisco":   "JAL",
    "queretaro": "QRO",
    "yucatan":   "YUC",
    # agregar conforme se incorporen estados
}
```

---

## 4. Adaptadores por estado

### 4.1 Clase base abstracta

```python
# src/estados/base.py

from abc import ABC, abstractmethod
from pathlib import Path
from src.core.constants import EJERCICIO_INI, EJERCICIO_FIN


class EstadoAdapter(ABC):
    """
    Interfaz que cada estado debe implementar.

    Solo download() y segment() son específicos por estado.
    OCR, extracción LLM y validación son genéricos.
    """

    @property
    @abstractmethod
    def slug(self) -> str:
        """Ej: 'coahuila'"""

    @property
    @abstractmethod
    def prefijo(self) -> str:
        """Ej: 'COAH' — para nombres de archivo"""

    @property
    def ejercicio_range(self) -> range:
        """Override si un estado tiene rango distinto."""
        return range(EJERCICIO_INI, EJERCICIO_FIN + 1)

    @property
    def needs_ocr(self) -> bool:
        """Override si el estado tiene PDFs escaneados."""
        return False

    @property
    def data_dir(self) -> Path:
        return Path(f"data/{self.slug}")

    @property
    def pdf_raw_dir(self) -> Path:
        return self.data_dir / "pdf_raw"

    @property
    def meta_dir(self) -> Path:
        return self.data_dir / "meta"

    @property
    def focus_dir(self) -> Path:
        return self.data_dir / "focus_predial"

    @property
    def json_dir(self) -> Path:
        return self.data_dir / "json_predial"

    # --- Métodos abstractos (específicos por estado) ---

    @abstractmethod
    def download(self) -> Path:
        """
        Descarga PDFs del Periódico Oficial.
        Retorna ruta al CSV índice de leyes descargadas.
        """

    @abstractmethod
    def build_master(self) -> Path:
        """
        Construye master: (municipio, año) → PDF, páginas de la ley.
        Retorna ruta al master CSV.
        """

    @abstractmethod
    def extract_predial_sections(self) -> Path:
        """
        Localiza sección de predial, genera TXT y PDF recortados.
        Retorna ruta al CSV bitácora.
        """

    # --- Métodos concretos (compartidos) ---

    def run_ocr(self):
        """Aplica OCR si needs_ocr=True. Usa core/ocr.py."""
        if not self.needs_ocr:
            print(f"  [{self.slug}] OCR no requerido, saltando.")
            return
        from src.core.ocr import process_directory
        process_directory(self.pdf_raw_dir, self.data_dir / "pdf_ocr")

    def run_llm_extraction(self):
        """Llama al LLM para cada TXT. Usa core/llm_extract.py."""
        from src.core.llm_extract import extract_all
        extract_all(
            txt_dir=self.focus_dir,
            json_dir=self.json_dir,
            prefijo=self.prefijo,
        )

    def run_validation(self):
        """Valida JSONs. Usa core/validation.py."""
        from src.core.validation import validate_all
        validate_all(
            json_dir=self.json_dir,
            prefijo=self.prefijo,
            out_csv=self.meta_dir / f"{self.slug}_predial_summary.csv",
        )
```

### 4.2 Registry de adaptadores

```python
# src/estados/__init__.py

from src.estados.coahuila import CoahuilaAdapter
from src.estados.jalisco import JaliscoAdapter
from src.estados.queretaro import QueretaroAdapter
from src.estados.yucatan import YucatanAdapter

_REGISTRY = {
    "coahuila": CoahuilaAdapter,
    "jalisco": JaliscoAdapter,
    "queretaro": QueretaroAdapter,
    "yucatan": YucatanAdapter,
}

def get_adapter(estado_slug: str):
    """Factory: devuelve instancia del adaptador para el estado dado."""
    cls = _REGISTRY.get(estado_slug.lower())
    if cls is None:
        available = ", ".join(sorted(_REGISTRY.keys()))
        raise ValueError(
            f"Estado '{estado_slug}' no registrado. Disponibles: {available}"
        )
    return cls()
```

### 4.3 Ejemplo: adaptador de Coahuila

```python
# src/estados/coahuila/__init__.py

from src.estados.base import EstadoAdapter
from pathlib import Path


class CoahuilaAdapter(EstadoAdapter):

    @property
    def slug(self) -> str:
        return "coahuila"

    @property
    def prefijo(self) -> str:
        return "COAH"

    @property
    def needs_ocr(self) -> bool:
        return False

    def download(self) -> Path:
        from src.estados.coahuila.download import run_download
        return run_download(self)

    def build_master(self) -> Path:
        from src.estados.coahuila.segment import run_build_master
        return run_build_master(self)

    def extract_predial_sections(self) -> Path:
        from src.estados.coahuila.segment import run_extract_sections
        return run_extract_sections(self)
```

Dentro de `download.py` y `segment.py` viviría el código que hoy tienes en tus scripts 01, 03, 04, 05, 10 — pero importando funciones de `core/` en lugar de redefinirlas.

---

## 5. Orquestador CLI

```python
#!/usr/bin/env python3
# scripts/run_pipeline.py
"""
Orquestador principal del pipeline de extracción de predial.

Uso:
    python scripts/run_pipeline.py coahuila                          # Todo el pipeline
    python scripts/run_pipeline.py coahuila --steps download         # Solo descarga
    python scripts/run_pipeline.py coahuila --steps segment,extract  # Parcial
    python scripts/run_pipeline.py jalisco --from-step extract       # Desde extracción
    python scripts/run_pipeline.py --all --steps validate            # Validar todos

Pasos disponibles (en orden):
    download  → Descarga de PDFs del Periódico Oficial
    ocr       → OCR con Tesseract (solo si el estado lo requiere)
    master    → Construcción del master (municipio, año) → PDF
    segment   → Extracción de sección predial (TXT + PDF recortado)
    extract   → Extracción LLM (GPT-5.1)
    validate  → Validación estructural + interanual
"""

import argparse
import sys
from src.estados import get_adapter, _REGISTRY

STEPS_ORDERED = ["download", "ocr", "master", "segment", "extract", "validate"]

STEP_METHODS = {
    "download": lambda a: a.download(),
    "ocr":      lambda a: a.run_ocr(),
    "master":   lambda a: a.build_master(),
    "segment":  lambda a: a.extract_predial_sections(),
    "extract":  lambda a: a.run_llm_extraction(),
    "validate": lambda a: a.run_validation(),
}


def run_estado(estado_slug: str, steps: list[str]):
    adapter = get_adapter(estado_slug)
    print(f"\n{'#'*60}")
    print(f"  ESTADO: {adapter.slug.upper()}")
    print(f"  Pasos: {', '.join(steps)}")
    print(f"{'#'*60}")

    for step in steps:
        print(f"\n{'─'*40}")
        print(f"  Paso: {step}")
        print(f"{'─'*40}")
        try:
            STEP_METHODS[step](adapter)
        except Exception as e:
            print(f"  [ERROR] {step}: {e}")
            raise


def main():
    parser = argparse.ArgumentParser(description="Pipeline predial-mx")
    parser.add_argument("estado", nargs="?", help="Slug del estado (o --all)")
    parser.add_argument("--all", action="store_true", help="Procesar todos los estados")
    parser.add_argument("--steps", default="all",
                        help="Pasos separados por coma, o 'all'")
    parser.add_argument("--from-step", default=None,
                        help="Ejecutar desde este paso en adelante")
    args = parser.parse_args()

    # Determinar pasos
    if args.from_step:
        idx = STEPS_ORDERED.index(args.from_step)
        steps = STEPS_ORDERED[idx:]
    elif args.steps == "all":
        steps = STEPS_ORDERED
    else:
        steps = [s.strip() for s in args.steps.split(",")]

    for s in steps:
        if s not in STEPS_ORDERED:
            print(f"[ERROR] Paso desconocido: '{s}'")
            print(f"  Disponibles: {', '.join(STEPS_ORDERED)}")
            sys.exit(1)

    # Determinar estados
    if args.all:
        estados = sorted(_REGISTRY.keys())
    elif args.estado:
        estados = [args.estado]
    else:
        parser.print_help()
        sys.exit(1)

    for estado in estados:
        run_estado(estado, steps)

    print("\n✓ Pipeline completado.")


if __name__ == "__main__":
    main()
```

---

## 6. Esquema JSON expandido

### 6.1 Tipos de esquema

Basado en lo que has encontrado en 4 estados, el enum expandido es:

| Tipo | Cuándo aplica | Qué captura |
|------|---------------|-------------|
| `tarifa_millar` | Tasa(s) al millar diferenciadas por tipo de predio | `tabla_tarifa_millar` |
| `progresivo` | Tabla por rangos de valor catastral con cuota fija + tasa marginal | `tabla_progresiva` |
| `tasa_unica` | Un solo porcentaje o tasa al millar para todos los predios | `tabla_tasa_unica` |
| `cuota_fija` | Monto fijo por predio sin referencia al valor | `tabla_cuota_fija` |
| `mixto` | Combinación que no encaja en los anteriores | Cualquier tabla + `comentarios` obligatorio |
| `desconocido` | Texto ambiguo o contradictorio | Tablas vacías + `comentarios` obligatorio |

### 6.2 Regla para el system prompt

Agrega al prompt actual (después de la definición de `tabla_progresiva`):

```
- "tasa_unica": cuando el impuesto se calcula con UNA SOLA tasa (porcentaje o al millar)
  aplicable a todos los predios por igual, sin distinción de tipo ni rangos.
  Cada objeto en "tabla_tasa_unica":
  {
    "descripcion": "texto corto",
    "tasa": 0.003,
    "base_calculo": "valor_catastral | valor_fiscal | otro",
    "unidad": "porcentaje | al_millar | al_millar_bimestral"
  }

- "cuota_fija": cuando el impuesto es un monto fijo por predio, sin referencia al valor.
  Cada objeto en "tabla_cuota_fija":
  {
    "descripcion": "texto corto",
    "monto": 350.00,
    "periodicidad": "anual | bimestral | mensual"
  }

- "mixto": cuando el esquema combina elementos de los tipos anteriores de forma
  que no encaja limpiamente en una sola categoría. Llena las tablas relevantes
  y explica la combinación en "comentarios".
```

### 6.3 Impacto en el índice de carga legal

Para hacer comparables los esquemas, tu índice de carga legal necesitará una **propiedad de referencia** (valor catastral medio). Con el esquema expandido, la fórmula sería:

| Tipo | Cálculo de carga para propiedad de valor V |
|------|---------------------------------------------|
| `tarifa_millar` | `V × tasa_millar / 1000 + cuota_fija` (para el grupo relevante) |
| `progresivo` | Cuota fija del rango + `(V - límite_inferior) × tasa_marginal` |
| `tasa_unica` | `V × tasa` (ajustando unidad) |
| `cuota_fija` | `monto` (independiente de V) |
| `mixto` | Caso por caso, requiere lógica ad-hoc |

Este cálculo vive en la fase posterior, pero el JSON debe capturar suficiente detalle para habilitarlo.

---

## 7. Validación mejorada

Tu script `25_json_consistency.py` ya tiene buenas validaciones. Propongo consolidarlas en `core/validation.py` y agregar:

### 7.1 Validaciones existentes (conservar)
- Coherencia `tipo_esquema` ↔ tablas no vacías
- Tipos de datos correctos (`tasa_millar` numérica, `n_rango` parseable a int)
- Continuidad de rangos progresivos (solapes/huecos)
- Regla interanual: si T es progresivo válido, T+1 debería serlo

### 7.2 Validaciones nuevas propuestas

```python
# Reglas adicionales para core/validation.py

def check_interanual_extended(rows_by_muni: dict):
    """
    Reglas interanuales más robustas:
    1. Continuidad de tipo_esquema (no solo progresivo)
    2. Número de rangos/filas no debería cambiar drásticamente (±50%)
    3. Tasas no deberían cambiar más de un factor razonable año a año
    """
    for muni, years in rows_by_muni.items():
        years_sorted = sorted(years, key=lambda r: r["anio"])
        for i in range(len(years_sorted) - 1):
            cur, nxt = years_sorted[i], years_sorted[i + 1]

            # Cambio de tipo de esquema
            if (cur["tipo_esquema"] != nxt["tipo_esquema"]
                and cur["esquema_valido"] and nxt["esquema_valido"]):
                nxt["anomalias"].append(
                    f"cambio_esquema_{cur['tipo_esquema']}_a_{nxt['tipo_esquema']}"
                )

            # Cambio brusco en número de rangos
            n_cur = cur["n_prog_rows"] or cur["n_tarifa_rows"]
            n_nxt = nxt["n_prog_rows"] or nxt["n_tarifa_rows"]
            if n_cur > 0 and n_nxt > 0:
                ratio = n_nxt / n_cur
                if ratio > 2.0 or ratio < 0.5:
                    nxt["anomalias"].append(
                        f"cambio_brusco_n_rangos_{n_cur}_a_{n_nxt}"
                    )


def check_coverage(estado_slug: str, ejercicio_range: range, expected_munis: int):
    """
    Verifica cobertura: ¿cuántos (municipio, año) faltan?
    Reporta porcentaje de completitud.
    """
    ...
```

---

## 8. Dependencias unificadas

```toml
# pyproject.toml
[project]
name = "predial-mx"
version = "0.1.0"
description = "Extracción de tasas de impuesto predial municipal desde Periódicos Oficiales"
requires-python = ">=3.10"

dependencies = [
    # Scraping y descarga
    "requests>=2.31",
    "beautifulsoup4>=4.12",
    "lxml>=4.9",

    # PDF
    "pdfplumber>=0.10",
    "pypdf>=3.15",

    # Texto
    "unidecode>=1.3",

    # OCR
    "pytesseract>=0.3.10",
    "Pillow>=10.0",

    # LLM
    "openai>=1.30",

    # Validación y schemas
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "ruff",        # Linter rápido
]
```

**Setup (una sola vez)**:
```bash
cd predial-mx
python -m venv .venv
source .venv/bin/activate      # Linux/Mac
# .venv\Scripts\activate       # Windows
pip install -e ".[dev]"
```

Esto reemplaza tus 4 virtualenvs separados con uno solo.

---

## 9. Git: lo mínimo que necesitas

Git es un sistema de control de versiones. Para tu caso, necesitas solo 5 comandos:

### 9.1 Setup inicial (una vez)

```bash
cd predial-mx
git init                          # Inicializa el repositorio
git add .                         # Agrega todos los archivos
git commit -m "Estructura inicial del monorepo"  # Primer "snapshot"
```

### 9.2 Flujo diario

```bash
# Después de hacer cambios:
git add .                                        # Prepara los cambios
git commit -m "Agrego adaptador de Jalisco"      # Guarda el snapshot

# Para ver qué ha cambiado:
git status                                       # Archivos modificados
git log --oneline                                # Historial de commits
```

### 9.3 `.gitignore` — Qué NO rastrear

```gitignore
# PDFs crudos y OCR (pesados, regenerables)
data/*/pdf_raw/
data/*/pdf_ocr/

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/

# OS
.DS_Store
Thumbs.db

# API keys
.env
```

**¿Qué SÍ va en Git?**
- Todo el código (`src/`, `scripts/`, `tests/`)
- Catálogos (`catalogs/`)
- CSVs de metadatos (`data/*/meta/`)
- JSONs de salida del LLM (`data/*/json_predial/`) — son tu resultado y quieres trazabilidad
- TXT de secciones predial (`data/*/focus_predial/`) — son ligeros y útiles para reproducir
- Documentación (`docs/`, `README.md`)
- Productos finales (`output/`)

### 9.4 Respaldo remoto (recomendado)

Crea un repositorio privado en GitHub y conecta:

```bash
# Una vez, después de crear el repo en github.com:
git remote add origin https://github.com/TU_USUARIO/predial-mx.git
git push -u origin main

# Después de cada commit:
git push
```

Esto te da respaldo automático y puedes acceder desde cualquier máquina.

---

## 10. Plan de migración paso a paso

### Fase 1: Infraestructura (1–2 horas)
1. Crear directorio `predial-mx/` con la estructura completa
2. Crear `pyproject.toml`, `.gitignore`, `README.md`
3. Crear el virtualenv único
4. `git init` + primer commit

### Fase 2: Código compartido (2–3 horas)
5. Crear `core/pdf_utils.py` consolidando las funciones duplicadas
6. Crear `core/text_utils.py` con `norm()`, `slugify()`, `parse_monto_to_float()`
7. Crear `core/schemas.py` con los modelos Pydantic
8. Crear `core/constants.py`
9. Crear `estados/base.py` con la clase abstracta
10. Commit: "Agrego módulos core y clase base de adaptador"

### Fase 3: Migrar Coahuila como piloto (3–4 horas)
11. Mover datos existentes a `data/coahuila/` con la nueva estructura
12. Crear `estados/coahuila/` con `config.py`, `download.py`, `segment.py`
13. Refactorizar scripts 01, 03, 04, 05, 10 usando imports de `core/`
14. Migrar `20_llm_extract.py` a `core/llm_extract.py` (generalizado)
15. Migrar `25_json_consistency.py` a `core/validation.py` (generalizado)
16. **Verificar**: los JSONs generados deben ser idénticos a los actuales
17. Commit: "Migro Coahuila como primer adaptador completo"

### Fase 4: Migrar los 3 estados restantes (1–2 horas por estado)
18. Jalisco → `estados/jalisco/`
19. Querétaro → `estados/queretaro/`
20. Yucatán → `estados/yucatan/`
21. Verificar cada uno contra su salida anterior

### Fase 5: Expandir esquema JSON (2–3 horas)
22. Actualizar `core/schemas.py` con los tipos nuevos
23. Actualizar el system prompt en `core/llm_extract.py`
24. Actualizar `core/validation.py` con las reglas nuevas
25. Re-procesar los municipios que habían quedado como `desconocido`

### Fase 6: Consolidación (1–2 horas)
26. Crear `scripts/consolidate_panel.py`
27. Generar `output/predial_panel.csv`
28. Generar `output/quality_report.csv`

**Tiempo estimado total**: 15–20 horas de trabajo, distribuidas como prefieras.

---

## 11. Checklist de verificación post-migración

Para cada estado migrado, verificar:

- [ ] `python scripts/run_pipeline.py {estado} --steps download` produce los mismos PDFs
- [ ] `python scripts/run_pipeline.py {estado} --steps master,segment` produce los mismos TXT
- [ ] `python scripts/run_pipeline.py {estado} --steps extract` produce JSONs equivalentes
- [ ] `python scripts/run_pipeline.py {estado} --steps validate` no genera anomalías nuevas
- [ ] El CSV summary tiene el mismo número de filas y distribución de tipos

Para agregar un estado nuevo:

- [ ] Crear `src/estados/{slug}/` con `config.py`, `download.py`, `segment.py`
- [ ] Registrar en `src/estados/__init__.py`
- [ ] `python scripts/run_pipeline.py {slug}` corre sin errores
- [ ] Revisar `quality_report.csv` para detectar esquemas atípicos
