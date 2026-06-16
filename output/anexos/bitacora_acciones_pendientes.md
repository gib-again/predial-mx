# Bitácora de acciones pendientes

Tareas de verificación manual y mejoras al pipeline pendientes de
ejecución. Complementa `docs/HITL_BITACORA.md` (que cubre casos
`otro_no_clasificado` y dudas LLM específicas).

Convención de IDs: `P-NNN` (pendientes generales).

---

## Verificación ley-por-ley de estados con tarifa estatal uniforme

Los 5 estados hardcoded (`scripts.temps.detectar_cambios_interanuales` los
omite por default) usan tarifa estatal uniforme codificada en
`src/core/adapters_hardcoded.py`. Por construcción son 100% sticky. Falta
**verificar manualmente** que la fuente legal vigente coincide con la tarifa
codificada y que ninguna ley de ingresos municipal la overridea para algún
ejercicio.

### P-001 Chihuahua — Código Municipal del Estado de Chihuahua (Arts. 148-149)

- [ ] Verificar contra texto vigente del Código (versión más reciente).
- [ ] Confirmar que ninguna ley de ingresos municipal override la tarifa estatal
      durante 2010–2025.
- [ ] Validar que la actualización por inflación (si aplica) está reflejada.
- **Fuente esperada**: <https://www.congresochihuahua2.gob.mx/biblioteca/codigos/archivosCodigos/70.pdf>
- **Estructura adapter**: `src/core/adapters_hardcoded.py:adapt_chihuahua`
- **Notas**: …

### P-002 Colima — Ley de Hacienda para los Municipios del Estado de Colima (Art. 13)

- [ ] Verificar contra texto vigente de la Ley de Hacienda.
- [ ] Confirmar que aplica a los 10 municipios sin variaciones por LIM.
- [ ] Validar tabla `urbano_edificado.rangos` ejemplificada en
      `data/colima/json_predial/2010/COL_2010_armeria.json`.
- **Fuente esperada**: <https://congresocol.gob.mx/web/www/leyes/index.php>
- **Estructura adapter**: `src/core/adapters_hardcoded.py:adapt_colima`
- **Notas**: …

### P-003 Estado de México — Código Financiero del Estado de México y Municipios (Art. 109)

- [ ] Verificar contra texto vigente del Código Financiero.
- [ ] Confirmar que los 125 municipios de Edomex no tienen LIM overrides
      durante 2010–2025.
- [ ] Validar actualización de límites por INPC anual.
- **Fuente esperada**: <https://legislacion.edomex.gob.mx/>
- **Estructura adapter**: `src/core/adapters_hardcoded.py:adapt_edomex`
- **Notas**: …

### P-004 Sinaloa — Ley de Hacienda Municipal del Estado de Sinaloa (Arts. 35-36)

- [ ] Verificar contra texto vigente.
- [ ] Confirmar que `metodo_extraccion = "hardcoded_tarifa_base_2010_actualizada_inpc"`
      describe correctamente cómo se reconstruye la tarifa por año.
- [ ] Validar la separación `urbano.construido` vs `urbano.baldio` en
      `data/sinaloa/json_predial/2010/SIN_2010_ahome.json`.
- **Fuente esperada**: <https://www.congresosinaloa.gob.mx/leyes/>
- **Estructura adapter**: `src/core/adapters_hardcoded.py:adapt_sinaloa`
- **Notas**: …

### P-005 Tabasco — Ley de Hacienda Municipal del Estado de Tabasco (Art. 94)

- [ ] Verificar contra texto vigente.
- [ ] Confirmar que aplica uniformemente a los 17 municipios.
- [ ] Validar las cuotas/factores en `data/tabasco/json/2010/TAB_2010_balancan.json`.
- **Fuente esperada**: <https://congresotabasco.gob.mx/leyes/>
- **Estructura adapter**: `src/core/adapters_hardcoded.py:adapt_tabasco`
- **Notas**: …

---

## Mejoras al pipeline / aplicador pendientes

### P-100 Aplicador HITL debe procesar decisión `re_segmentar`

El revisor HTML (`scripts/temps/hitl_revisor_server.py`) ofrece 5 decisiones
en su dropdown, incluyendo `re_segmentar` para casos donde el segmento
está mal recortado (corta antes de la tarifa, agarra transitorios, etc.).
Actualmente `scripts/temps/aplicar_decisiones_hitl.py` solo procesa
`{aceptar_nuevo, propagar_previo, reextraer, cambio_real_documentado}` y
ignora `re_segmentar`.

- [ ] Extender `aplicar_decisiones_hitl.py` para consumir `re_segmentar`.
- [ ] Emitir `output/anexos/cola_resegmentar.csv` con paths a re-procesar
      (estado, año, slug, json_path, hint).
- [ ] **Backup obligatorio** antes de re-segmentar: copiar el segmento
      actual a `data/<estado>/focus_predial_backup_pre_resegment/<año>/`
      con timestamp en nombre, para auditoría y rollback.
- [ ] Registrar en bitácora `hitl_bitacora.csv` el re_segmentar con
      `(estado, muni, año, timestamp, hash_segmento_antiguo)`.
- [ ] Documentar que tras `re_segmentar` los outputs derivados
      (`qa_inconsistencias.md`, `docs/HITL_BITACORA.md`,
      `output/audit_pendiente.csv`) tienen entradas stale para ese
      `(muni, año)`; estrategia: re-correr `qa_inconsistencias.py` sobre
      el caso afectado.

### P-101 Rastreo explícito del PDF/TXT fuente en `_meta.source_path`

Hoy el rastreo del PDF de origen se hace por convención de nombre
(`focus_predial/<año>/<prefix>_PREDIAL_<año>_<slug>.{txt,pdf}`). Si la
extracción usó un override (`focus_predial_overrides/`) o el archivo fue
mutado después de la extracción, no hay registro explícito.

- [ ] Agregar `_meta.source_path` (string absoluta o relativa al root)
      en futuras extracciones LLM.
- [ ] Actualizar `src/extraction/schema_v2.MetaExtraccion` para incluir
      el campo (opcional para preservar retrocompatibilidad).
- [ ] Modificar `src/core/llm_extract.py` para poblarlo al extraer.
- [ ] Actualizar `hitl_revisor_server.py` para usar el path explícito
      cuando esté disponible, en vez del path inferido por convención.

### P-102 Slugify automático para `FilaTarifaMillar.clave`

Los `clave` de tarifa_millar los genera el LLM libremente; el prompt no
da instrucción explícita y `text_utils.slugify` no se aplica al output.
Esto produce fragmentación intra-estado (Guanajuato tiene claves largas
con rangos temporales hardcoded en el slug).

- [ ] Decidir: ¿slugify automático en `FilaTarifaMillar` validator?
      ¿Instruir al prompt explícitamente? ¿Reporte exploratorio (ver
      `scripts/temps/reporte_claves_tarifa_millar.py`) y consolidación
      manual?
- [ ] Ver `output/anexos/claves_tarifa_millar_resumen.md` para el
      diagnóstico actual de fragmentación.

### P-103 Validator anti `mixto` mono-columna `cuota_fija`

`scripts/temps/qa_inconsistencias.py` detectó 106 casos (20.6% del pool
mixto) donde la tabla mixto tiene una sola columna con todas
`tipo=cuota_fija`. Eso es exactamente `cuota_fija_escalonada`, no mixto.

- [ ] Agregar validator en `MixtoSchema` (`src/extraction/schema_v2.py`)
      que rechace tablas mono-columna mono-tipo, forzando reclasificación
      a `cuota_fija_escalonada` vía `reclasificar()`.
- [ ] Regression test con los 5 casos top de Sonora 2013–2014.

### P-104 Re-extraer 443 tablas vacías

`qa_inconsistencias` detectó 443 casos con `tipo_esquema` asignado pero
`tabla=[]`. Los primeros 5 son Coahuila 2025 — sugiere problema
sistemático para ese año.

- [ ] Re-extraer priorizando Coahuila 2025.
- [ ] Inspeccionar el patrón: ¿qué fue distinto en la segmentación de
      esos archivos?

### P-105 PDFs huérfanos restantes en focus_predial (post-backfill)

Tras `scripts/temps/backfill_focus_pdfs.py --estado yucatan` la cobertura
PDF subió de 2.7% a 98.4% en Yucatán. Quedan 39 huérfanos (TXT sin PDF
homónimo) que el backfill no pudo resolver automáticamente:

- **Yucatán: 24** — probablemente short_form (sin `predial_found=true` en
  segment.csv) o casos con `predial_page_start/end` ausentes.
- **Guanajuato: 8**, **Querétaro: 3**, **Sonora: 2**, **Jalisco: 1**,
  **Tamaulipas: 1**.

Acciones:
- [ ] Inspeccionar los 24 huérfanos de Yucatán; si son short_form,
      generar PDF copiando la página de mención (usando ley_page_start/end
      del segment.csv).
- [ ] Para los 15 huérfanos de otros estados, revisar caso a caso si el
      `segment.py` correspondiente no escribió el PDF o si el PDF se
      perdió por race.
- [ ] Auditar que los `segment.py` de **coahuila, guanajuato, jalisco,
      oaxaca, queretaro, sanluispotosi, sonora, tamaulipas** llamen al
      helper `src.core.segment_utils.save_focus_pdf` en su flujo (yucatán
      ya lo hace tras P-105). El patrón documentado en
      `src/estados/CLAUDE.md` lo requiere.
