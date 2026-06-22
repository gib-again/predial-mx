# Conflictos de merge entre ramas (estado al 2026-06-22)

Análisis previo al push de `feat/hitl-cvegeo-canonico`. Generado con
`git merge-tree --write-tree` (detección sin merge real). Sirve de guía para
quien integre las ramas a `main`.

## Estado de la rama actual

- `feat/hitl-cvegeo-canonico`: **17 commits adelante de `origin/main`, 0 atrás**.
  `origin/main` es ancestro de HEAD → integración a `main` por **fast-forward
  limpio**, sin divergencia. El push es de una rama nueva (no existía en remoto).

## Ramas remotas — resultado del merge contra HEAD

| Rama remota | Commits propios (no en HEAD) | Resultado |
|---|---:|---|
| `tier2-shared-segment-utilities` | 0 | ✅ limpio (ya contenida) |
| `feat/grupo-progresiva` | 0 | ✅ limpio (ya contenida) |
| `claude/infallible-nash` | 0 | ✅ limpio (ya contenida) |
| `feat/scripts-reorganization-hitl-tooling` | 6 | ⚠️ **CONFLICTOS** |

## Conflictos con `feat/scripts-reorganization-hitl-tooling`

Merge-base común: `3ad6f4b` (Oaxaca: fill canónico). Ambas ramas divergieron ahí.
Esa rama aporta 6 commits (SLP download/pipeline, Sonora visión multi-municipio,
panel pragmático balanceado, reorganización de `scripts/temps/` + tooling HITL,
estandarización de PDFs focus_predial).

### 1. `CLAUDE.md` — conflicto de contenido
Ambas ramas editaron el doc raíz. **Resolución:** merge manual — conservar la
sección HITL unificado + cvegeo de esta rama y fundir las notas de SLP/Sonora/
tooling de la otra.

### 2. `data/{sanluispotosi,sonora}/meta/segment.csv` — add/add
Ambas ramas crearon estos segment.csv con esquemas distintos. **Resolución:**
quedarse con el **esquema único canónico (cvegeo)** de esta rama
(`src/core/segment_schema.py`, Causa A). El segment.csv de la otra rama es
pre-canónico. Tras el merge, re-correr `canonicalize_segment` por si acaso.

### 3. `predial-mx-v2/**/*.json` (~16 archivos) — modify/delete
Esta rama **eliminó el corpus v2 completo** (commit `1659f31`, migración a v3).
La otra rama modificó algunos de esos JSON (GTO y YUC san_francisco_del_rincon,
sacalum, teabo, etc.). **Resolución:** mantener la **eliminación** — v2 está
retirado (ver `docs/SCHEMA_EVOLUTION.md`); las modificaciones de la otra rama
son sobre artefactos muertos.

### 4. `scripts/*.py` — rename/rename (2 archivos)
- `scripts/apply_treatment_audit.py`
- `scripts/audit_treatment_anomalies.py`

Esta rama los movió a `scripts/_archive/`; la otra a `scripts/temps/`. Ambas los
consideran no-core (scripts DiD obsoletos). **Resolución:** elegir **un** destino
—`scripts/_archive/` es lo correcto (son DiD completados/obsoletos, ver
`scripts/_archive/README.md`)— y descartar el otro rename.

## Recomendación de orden de integración

1. Mergear primero `feat/hitl-cvegeo-canonico` a `main` (fast-forward, sin
   conflicto).
2. Luego rebasear/mergear `feat/scripts-reorganization-hitl-tooling` sobre el
   nuevo `main`, resolviendo los 4 grupos de arriba (todos con resolución
   determinada: conservar canónico/v3, descartar v2/pre-canónico).
