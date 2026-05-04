# Notas por estado

Particularidades del marco legal, fuente de datos, procesamiento y pipeline de cada estado.

---

## Resumen

| # | Estado | CVE | Municipios | OCR | Estrategia | JSONs |
|---|--------|-----|-----------|-----|------------|-------|
| 1 | Coahuila | 05 | 38 | No | Ley de ingresos por municipio (PO) → segmentación → LLM | ~608 |
| 2 | Jalisco | 14 | 125 | Sí | Ley de ingresos por municipio (PO) → OCR → segmentación → LLM | ~2,000 |
| 3 | Querétaro | 22 | 18 | No | Ley de ingresos por municipio (PO La Sombra de Arteaga) → segmentación → LLM | ~288 |
| 4 | Yucatán | 31 | 106 | No* | Ley de ingresos por municipio (DO) + Ley de Hacienda de Mérida → segmentación → LLM | ~1,696 |
| 5 | Tamaulipas | 28 | 43 | No | Ley de ingresos por municipio (PO) → segmentación → LLM | ~688 |
| 6 | Chihuahua | 08 | 67 | No | Tarifa estatal uniforme (Código Municipal) → hardcoded → expansión | 1,072 |
| 7 | Colima | 06 | 10 | No | Tarifa uniforme (Leyes de Hacienda Municipales) → hardcoded → expansión | 160 |
| 8 | Edo. México | 15 | 125 | No | Tarifa estatal uniforme (Código Financiero) → hardcoded → expansión | 2,000 |
| 9 | Sinaloa | 25 | 18 | No | Tarifa estatal uniforme (Ley de Hacienda) + actualización INPC → expansión | 288 |
| 10 | Tabasco | 27 | 17 | No | Tarifa estatal uniforme (Ley de Hacienda) → hardcoded → expansión | 272 |
| 11 | Guanajuato | 11 | 46 | Sí | Ley de ingresos por municipio (PO) → OCR → segmentación 2 niveles → LLM | ~736 |
| 12 | Oaxaca | 20 | 570 | Sí | Ley de ingresos por municipio (PO) → OCR + watermark cleanup → segmentación → LLM | en curso |
| 13 | San Luis Potosí | 24 | 58 | Sí* | Ley de ingresos por municipio (PO API JSON) → OCR adaptativo → segmentación → LLM | en curso |
| 14 | Sonora | 26 | 72 | Sí* | Boletín Oficial (scraping HTML índice Joomla) → OCR adaptativo → segmentación → LLM | en curso |

\* Yucatán: PDFs digitales en su mayoría; algunas tablas de tarifa son imágenes embebidas que requieren OCR selectivo.
\* San Luis Potosí: OCR adaptativo (sólo se aplica a PDFs con < 300 chars/página promedio; 2017+ son nativos y se saltan).
\* Sonora: OCR adaptativo (mismo umbral que SLP; los boletines de la era nueva 2019+ son nativos y se saltan, los antiguos pueden ser escaneos).

---

## Grupo A — Ley de ingresos por municipio (pipeline completo: descarga → segmentación → LLM)

### Coahuila
- **CVE_ENT**: 05 | **Municipios**: 38 | **Periodo**: 2010-2025
- **Fuente**: Periódico Oficial del Estado de Coahuila
- **URL del PO**: https://periodico.segobcoahuila.gob.mx
- **Tipo de sitio**: ASP clásico con DataTables; descarga por rango de fechas
- **OCR necesario**: No (PDFs con texto extraíble)
- **Marco legal**: Ley de Ingresos por municipio, publicada en diciembre del año anterior
- **Segmentación**: Patrón de cabecera: `NUMERO xxx.- LEY DE INGRESOS DEL MUNICIPIO DE {NOMBRE}`
- **Particularidades**:
  - Ejercicio 2017 requiere patch especial (PDFs organizados diferente ese año)
  - Primer estado implementado; sirvió como base para el patrón `EstadoAdapter`
  - Esquemas de predial variados: tasa fija, tasa por rango, tabla mixta

### Jalisco
- **CVE_ENT**: 14 | **Municipios**: 125 | **Periodo**: 2010-2025
- **Fuente**: Periódico Oficial del Estado de Jalisco
- **URL del PO**: API REST interna (descarga por municipio-ID, 1-125)
- **OCR necesario**: Sí (PDFs frecuentemente escaneados como imágenes)
- **Marco legal**: Ley de Ingresos por municipio
- **Segmentación**: Heurística por página con scoring + tablas ancla
- **Particularidades**:
  - Pipeline OCR con `ocrmypdf` obligatorio antes de segmentación
  - 125 municipios = estado con más municipios junto con Edo. México
  - Archivos RAR en algunos años (requiere `unrar` en el entorno)
  - Heurística de expansión de rango de páginas para capturar tablas completas

### Querétaro
- **CVE_ENT**: 22 | **Municipios**: 18 | **Periodo**: 2010-2025
- **Fuente**: Periódico Oficial "La Sombra de Arteaga"
- **URL del PO**: https://lasombradearteaga.segobqueretaro.gob.mx/{año}/indice{año}.pdf
- **OCR necesario**: No (PDFs digitales)
- **Marco legal**: Ley de Ingresos por municipio
- **Segmentación**: Escaneo secuencial con detección de leyes → secciones prediales
  - v3: corrige falsos positivos por párrafos de promulgación, entradas de ToC y tablas de ANEXOS/CRITERIOS
- **Particularidades**:
  - Índice anual en PDF permite descubrimiento automático de URLs
  - El Marqués 2016: detección especial requerida
  - Aliases de municipios (nombres con/sin acento, abreviaciones)
  - Esquema `tabla_mixta_rango` diseñado originalmente para Piedras Negras (Coahuila) pero presente también aquí

### Yucatán
- **CVE_ENT**: 31 | **Municipios**: 106 | **Periodo**: 2010-2025
- **Fuente**: Diario Oficial del Gobierno del Estado de Yucatán
- **URL del DO**: Descarga por año con HEAD requests para detección rápida de URLs válidas
- **OCR necesario**: Selectivo (algunas tablas de tarifa son imágenes embebidas en PDFs digitales)
- **Marco legal**: Ley de Ingresos por municipio + Ley de Hacienda del Municipio de Mérida (caso especial)
- **Segmentación**: Dos patrones de detección predial + manejo de mojibake en texto extraído
- **Particularidades**:
  - Mérida tiene Ley de Hacienda propia, separada de las Leyes de Ingresos del resto
  - Download optimizado de 10 horas → 10 minutos con HEAD requests
  - Mojibake frecuente en extracción de texto (encoding issues en PDFs)
  - 106 municipios, segundo estado con más municipios después de Jalisco/EdoMex

### Tamaulipas
- **CVE_ENT**: 28 | **Municipios**: 43 | **Periodo**: 2010-2025
- **Fuente**: Periódico Oficial del Estado de Tamaulipas
- **URL del PO**: URLs específicas por ejercicio (mapeadas en config)
- **OCR necesario**: No (PDFs digitales)
- **Marco legal**: Ley de Ingresos por municipio (compiladas en un solo PO por año)
- **Segmentación**: Detección regex de leyes + secciones prediales con regex `DEL` opcional
- **Particularidades**:
  - Skip de páginas variable al inicio de cada PO (índice, contenido administrativo)
  - Patrón regex: `LEY DE INGRESOS (DEL|) MUNICIPIO DE {NOMBRE}`
  - Meta CSV único consolidado (corrección de bug de múltiples CSVs por año)

### San Luis Potosí
- **CVE_ENT**: 24 | **Municipios**: 58 | **Periodo**: 2010-2025
- **Fuente**: Periódico Oficial del Estado de San Luis Potosí
- **URL del PO**: API JSON en https://periodicooficial.slp.gob.mx
  - Búsqueda: `/api/publicacion/busqueda/filtro/gt?fechaInicio=...&fechaFin=...&palabra=ley+de+ingresos`
  - Descarga: `/api/publicacion/imprimir/guest/{id}/documento`
- **OCR necesario**: Adaptativo. La mayoría 2017+ son texto nativo (saltados). 2015 y 2019 son escaneos puros (~100 chars/página vs ~3000 en nativos) → se aplica force-OCR con `ocrmypdf` (lang spa, deskew, rotate-pages). Threshold de detección: 300 chars/página promedio. Ver `src/estados/sanluispotosi/ocr.py`.
- **Marco legal**: Ley de Ingresos por municipio (1 ley por municipio, expedida por el Congreso del Estado)
- **Segmentación**: Un nivel (1 PDF = 1 ley municipal completa). Patrones priorizados:
  1. `SECCIÓN PRIMERA / PREDIAL` (canónico 2010+)
  2. `CAPÍTULO II + (PATRIMONIO opcional) + PREDIAL`
  3. `ARTÍCULO N + el impuesto predial se calculará`
  4. `TÍTULO SEGUNDO + DE LOS IMPUESTOS + CAPÍTULO I + PREDIAL` (variante histórica)
- **Resolución de PDF**: la segmentación prefiere automáticamente `pdf_ocr/{año}/{stem}_ocr.pdf` cuando existe; cae al `pdf_raw/` original en caso contrario.
- **Cobertura observada (2010-2025) — final con OCR**:

  | Año | Hits API | OK descarga | OCR | Segment exacto | Notas |
  |-----|----------|-------------|-----|----------------|-------|
  | 2010 | 17 | 0 | – | – | API sin PDFs (404 en endpoint de descarga) |
  | 2011 | 58 | 0 | – | – | API sin PDFs (404 en endpoint de descarga) |
  | 2012 | 51 | 50 | – | 50 | OK (nativos) |
  | 2013 | 39 | 38 | – | 37 | OK (nativos), 1 fallback (armadillo) |
  | 2014 | 40 | 24 | – | 23 | API parcial, 1 fallback (tamazunchale) |
  | 2015 | 51 | 36 | 28 | **34** | OCR aplicado → recuperados |
  | 2016 | 5 | 5 | 1 | 5 | **API casi vacía** (5/58); los 5 segmentados |
  | 2017 | 59 | 41 | 2 | 40 | API parcial |
  | 2018 | 59 | 44 | – | 43 | API parcial |
  | 2019 | 58 | 52 | 46 | **52** | OCR aplicado → recuperados |
  | 2020 | 87 | 60 | – | 57 | OK (con duplicados), 1 fallback |
  | 2021 | 0 | 0 | – | – | **API sin registros para fiscal 2021** |
  | 2022 | 61 | 60 | – | 57 | OK |
  | 2023 | 61 | 61 | – | 58 | OK |
  | 2024 | 59 | 59 | – | 58 | OK |
  | 2025 | 58 | 58 | – | 58 | OK |

- **Cobertura efectiva final**: 572/928 (62 %) con segmentación exacta sobre el universo total; 572/575 (99.5 %) sobre los PDFs descargables. Lo restante son leyes que la API no expone (2010, 2011, 2016, 2021, parciales 2014/2017/2018/2020).
- **Estrategia multi-fuente para download** (3 rutas complementarias en `src/estados/sanluispotosi/`):
  - **Ruta B (`download.py`, mode="wide")**: una sola query histórica al PO con rango `1857-06-06`..`2026-12-31`, palabra `"ley de ingresos"`. Recupera registros que la búsqueda per-año perdía (especialmente con títulos truncados). El parser cae a `fecha_publicacion` cuando el año queda recortado del título por la API. Cascada de 5 endpoints PDF para cada ID con 404. **Yield: +3 PDFs** (ciudad_valles 2014, villa_de_guadalupe 2016, villa_de_pozos 2024 — municipio nuevo).
  - **Ruta A (`download_congreso.py`, Playwright)**: scraper best-effort del Congreso del Estado SLP (`congresosanluis.gob.mx`). El sitio está protegido por Sucuri Cloud Proxy con JS challenge → requiere browser real. Para cada (muni, año) consulta el formulario de búsqueda interna. **Yield: 0 PDFs**. El Congreso publica leyes estatales vigentes, no archivo histórico de Leyes de Ingresos municipales. Subdominios de legislaturas pasadas (`lviii.*`, `lix.*`, `lx.*`, `lxi.*`) tienen DNS muerto. Módulo se mantiene como hook si en el futuro publican el archivo histórico.
  - **Ruta C (`download_wayback.py`)**: para IDs con `error:*:all_endpoints`, consulta Wayback Machine availability API y descarga snapshots si existen. **Yield: 0 PDFs**. El PO SLP no tiene snapshots preservados de los PDFs históricos en Wayback (`archived_snapshots: {}` para 2010-2011-2021).
- **Conclusión sobre 2010, 2011, 2021**: confirmados como **irrecuperables vía web** después de exhaustivo sondeo. Los PDFs nunca fueron preservados fuera del backend del PO, y el PO los perdió. Recurso último: archivo físico del Congreso (Vallejo 200, Centro Histórico SLP, ext. 1680). No automatizable.
- **Particularidades**:
  - **Limitaciones del fuente**:
    - Fiscal 2010, 2011, 2016 (parcial) y 2021 (total) ausentes o mínimos en la API; metadata existe pero el endpoint de descarga retorna 404 (todos los endpoints alternativos también, no es bug del adapter)
    - Fiscal 2015 y 2019: PDFs descargables pero como escaneos sin capa de texto → segmentación cae al fallback de 12 páginas iniciales → necesitan OCR previo
  - Variación de redacción del título entre años:
    - 2010-2023: "Ley de Ingresos **del** Municipio de X, S.L.P., para el ejercicio fiscal Y"
    - 2024+: "Se EXPIDE la Ley de Ingresos **para el** Municipio de X, S.L.P., para el ejercicio fiscal Y"
    - Regex `(?:del|para\s+el)\s+[Mm]unicipio\s+de\s+`
  - Typos comunes en datos antiguos: "Físcal" / "Físacal" / "Físascal" → regex tolerante con `[Ee]jercicio\s+\w+\s+(\d{4})`
  - Estructura interna de la ley (verificada con muestras 2018, 2024):
    - `CAPÍTULO I / IMPUESTOS SOBRE LOS INGRESOS / SECCIÓN ÚNICA / ESPECTÁCULOS PÚBLICOS` (no es predial)
    - `CAPÍTULO II / IMPUESTOS SOBRE EL PATRIMONIO / SECCIÓN PRIMERA / PREDIAL / ARTÍCULO 6°` ← aquí
    - `CAPÍTULO II / SECCIÓN SEGUNDA / DE PLUSVALÍA` ← aquí termina (no adquisición como en otros estados)
  - Sumario en página 1 incluye "Ley de Ingresos del municipio de X" → context_validator rechaza matches en primeros 1 500 chars
  - Cookies XSRF requeridas: warm-up GET a `/menu/consulta/periodico` para capturar `XSRF-TOKEN` y `poe_session` dinámicamente
  - Aliases de municipios (Matahuala→Matehuala, Soledad→Soledad de Graciano Sánchez, Armadillo→Armadillo de los Infante, etc.) para fuzzy match
  - Transición SMGZ→UMA en 2016-2018 puede aparecer mezclada en el texto extraído (no afecta tarifa al millar; sí afecta `minimo_predial` cuando está en unidades)

### Guanajuato
- **CVE_ENT**: 11 | **Municipios**: 46 | **Periodo**: 2012-2025
- **Fuente**: Periódico Oficial del Gobierno del Estado de Guanajuato
- **URL del PO**: API REST en backperiodico.guanajuato.gob.mx (búsqueda + descarga)
- **OCR necesario**: Sí (PDFs híbridos: texto legal digital + tablas de tarifas escaneadas)
- **Marco legal**: Ley de Ingresos por municipio, publicada en PO (dic del año anterior + ene del ejercicio)
- **Segmentación**: Dos niveles:
  1. Localizar leyes municipales dentro de cada PDF del PO (múltiples leyes por PDF)
  2. Extraer sección predial dentro de cada ley
- **Extracción LLM**: Structured output (JSON Schema enforced) + fallback PDF visión
- **Particularidades**:
  - Múltiples PDFs por año (10-15 partes del mismo número del PO)
  - PDFs híbridos: texto legal buscable, pero tablas de tarifas son imágenes escaneadas
  - OCR con `ocrmypdf --force-ocr` (sin --remove-background ni --clean por compatibilidad Windows)
  - Descarga vía API REST con paginación; filtros para excluir reformas, empréstitos, ley estatal
  - Municipio extraído del campo "asunto" del API (regex) para parchar campo "NO APLICA"
  - 46 municipios con aliases extensos para tolerancia a ruido OCR
    (dolores_hidalgo, san_miguel_allende, silao, etc.)
  - Fallback PDF visión: si OCR produce esquema inválido, se envía el PDF recortado
    como imagen al LLM con +1 página extra por si faltaba contenido
  - Primer estado en usar structured output; la funcionalidad quedó en src/core/llm_extract.py
    para beneficio de todos los estados

### Sonora
- **CVE_ENT**: 26 | **Municipios**: 72 | **Periodo**: 2010-2025
- **Fuente**: Boletín Oficial del Estado de Sonora
- **URL del PO**: https://boletinoficial.sonora.gob.mx (Joomla, sppagebuilder)
  - Índice anual: `?option=com_sppagebuilder&view=page&id={id_joomla}` (ID descubierto por barrido + match en `<title>`/`<h1>`)
  - Patrones de URL de PDFs:
    - Era nueva (2019+): `/images/boletines/{YEAR}/12/{YEAR}{TOMO}{NUM}{SECC}.pdf`
    - Era antigua (≤2018): `/boletin/images/boletinesPdf/{YEAR}/12/{YEAR}{TOMO}{NUM}{SECC}.pdf`
    - Edición Especial: `/images/boletines/{YEAR}/12/EE{ddmmaaaa}{seq}.pdf`
- **OCR necesario**: Adaptativo (mismo umbral SLP: 300 chars/pág). Esperamos era nueva 2019+ como nativos y boletines ≤2018 posiblemente escaneados.
- **Marco legal**: Ley de Ingresos y Presupuesto de Ingresos del Ayuntamiento del Municipio de X, Sonora, publicada en boletines especiales del 24-31 de diciembre del año N-1. Cada sección romana del boletín = 1 municipio.
- **Segmentación**: Un nivel (1 PDF = 1 ley municipal completa). Patrones priorizados:
  1. `TÍTULO SEGUNDO + CAPÍTULO PRIMERO + Impuesto Predial` (canónico)
  2. `CAPÍTULO PRIMERO + Impuesto Predial` (sin contexto previo)
  3. `ARTÍCULO N + el impuesto predial se causará/calculará`
  4. `IMPUESTO PREDIAL` como cabecera (fallback genérico)
- **Resolución de PDF**: la segmentación prefiere `pdf_ocr/{año}/{stem}_ocr.pdf` cuando existe; cae al `pdf_raw/` original en caso contrario.
- **Particularidades**:
  - El sitio bloquea con HTTP 403 a User-Agents no-navegador → se envía UA realista de Chrome.
  - Estructura predial: cuota fija + tasa progresiva al millar por rangos de valor catastral; rústicos por cuota fija por hectárea (ej. $450/ha en Cajeme 2024); mínimo en UMA desde 2017.
  - El esquema `tabla_progresiva` (con `cuota_fija` + `tasa_marginal` por fila) ya soporta este caso vía `src/core/schemas.py` → no requiere extensión.
  - Tomos romanos cambian cada año (CCII=2018, CCXII=2023, CCXIV=2024, CCXV=2025, CCXVII=2026).
  - Mapeo `año_pub → id_joomla` se descubre vía barrido adyacente desde semillas conocidas (ver `config.ID_JOOMLA_POR_ANIO_PUB`).
  - Si el HTML del índice viene vacío de `<a href>` a PDFs (caso poco probable en sppagebuilder), upgrade documentado a Playwright.
- **Cobertura objetivo**: 2010-2025 (15 ejercicios) × 72 municipios = 1,080 leyes potenciales. Datos reales pendientes tras primera corrida.

---

## Grupo B — Tarifa estatal uniforme (hardcoded + expansión)

Estos estados tienen una tarifa de predial definida en una ley estatal (Código Financiero, Código Municipal, o Ley de Hacienda Municipal) que aplica uniformemente a todos sus municipios. No requieren descarga de PDFs ni OCR; la tarifa se hardcodea y se expande a todos los municipios × años.

### Chihuahua
- **CVE_ENT**: 08 | **Municipios**: 67 | **Periodo**: 2010-2025
- **Fuente**: Código Municipal para el Estado de Chihuahua, Art. 149
- **URL**: https://www.congresochihuahua2.gob.mx/biblioteca/codigos/archivosCodigos/66.pdf
- **Tarifa**: 5 rangos progresivos, tasas al millar (2‰ a 6‰)
  - Rústicos: tasa fija 2‰
  - Minería: tasa fija 5‰
  - Mínimo: 2 UMA (2018+) / 2 SM (pre-2018)
- **Reformas**:
  - 2018: Cambio de SM a UMA como unidad de medida para el mínimo
- **Particularidades**:
  - Tarifa sin cambios significativos en el periodo
  - Cuota fija = $0 en todos los rangos; solo aplica tasa al millar
  - Catalogado inicialmente como "requiere OCR" pero la tarifa estatal uniforme eliminó esa necesidad

### Colima
- **CVE_ENT**: 06 | **Municipios**: 10 | **Periodo**: 2010-2025
- **Fuente**: Ley de Hacienda para cada municipio (Decretos 268-277, 2002), Art. 13
- **URL**: https://congresocol.gob.mx/web/Sistema/uploads/LegislacionEstatal/LeyesMunicipales/
- **Tarifa**: Idéntica en los 10 municipios:
  - Urbano edificado: 26 rangos progresivos (cuota fija en UMA/SM + tasa marginal)
  - Baldíos: tasa fija 6‰
  - Rústico: 9 rangos progresivos
  - Ejidal: cuota fija 3 UMA/SM
- **Reformas**:
  - Decreto 133 (22-nov-2016): cambio de SM a UMA en cuotas fijas (reforma clave)
  - Manzanillo: tabla actualizada dic-2025 (aplica desde 2026, fuera del periodo)
- **Particularidades**:
  - 10 municipios con leyes de hacienda individuales pero tablas idénticas
  - Cuota fija en UMA (no en pesos) → se multiplica por valor diario UMA/SM del ejercicio
  - Series SM (2010-2016) y UMA (2017-2025) almacenadas en catalogs/
  - Bonificaciones: 15%/13%/11% pronto pago (ene/feb/mar), 50% vulnerables

### Estado de México
- **CVE_ENT**: 15 | **Municipios**: 125 | **Periodo**: 2010-2025
- **Fuente**: Código Financiero del Estado de México y Municipios, Art. 109
- **URL**: https://legislacion.edomex.gob.mx/
- **Tarifa**: 13 rangos progresivos, cuota fija en pesos nominales + factor sobre excedente
  - Dos periodos: tabla 2009 (ejercicio 2010), tabla 2010 (ejercicios 2011-2025)
  - Diferencia solo en rangos 1-3 (cuota fija y factor actualizados)
  - Tabla 2025 disponible como referencia (aplica desde ejercicio 2026)
- **Reformas**:
  - G.G. 21-dic-2010: actualización de cuota fija y factor en rangos 1-3
  - G.G. 28-nov-2016: baldíos urbanos >200 m² → +15% sobre monto total (desde ejercicio 2017)
- **Particularidades**:
  - Cuota fija en pesos nominales (no UMA ni SM) — no requiere factor de conversión
  - Baldíos urbanos >200 m²: recargo del 15%
  - 125 municipios × 16 años = 2,000 JSONs (estado con más registros)
  - Rangos de valores catastrales idénticos en ambas tablas; solo cambian cuotas/factores en primeros 3

### Sinaloa
- **CVE_ENT**: 25 | **Municipios**: 18 | **Periodo**: 2010-2025
- **Fuente**: Ley de Hacienda Municipal del Estado de Sinaloa, Art. 35-36
- **URL**: https://www.congresosinaloa.gob.mx/leyes/
- **Tarifa**: 11 rangos progresivos con **columnas separadas** para construidos y baldíos:
  - Construidos: cuota fija + tasa al millar (2.5‰ a 6.57‰)
  - Baldíos: cuota fija + tasa al millar (4.5‰ a 9.07‰) — ~1.8× más que construidos
- **Actualización anual** (Art. 36): factor INPC = INPC_nov(Y-1) / INPC_nov(Y-2)
  - Se aplica a límites y cuotas fijas; las tasas al millar NO cambian
  - Factores verificados contra 8 PDFs publicados (2010, 2012-2017, 2019): coincidencia exacta
- **Rústicos productivos** (Art. 35-II): tasas sobre producción anual comercializada
  - Agricultura/acuicultura/ganadería: 1.0%
  - Porcicultura/avicultura: 0.5%
- **Particularidades**:
  - Único estado con actualización dinámica por INPC (no es hardcode estático)
  - Tabla ancla 2010, cadena año a año con redondeo a 2 decimales en cada paso
  - Serie INPC mensual en catalogs/INPC_2008-2025.csv
  - Campos de golf: régimen especial (Art. 35-IV), introducido 2013, sin impacto en tarifa general
  - Descuentos: 10% pronto pago (2 primeros meses), 50% casa habitación, 80% jubilados/pensionados

### Tabasco
- **CVE_ENT**: 27 | **Municipios**: 17 | **Periodo**: 2010-2025
- **Fuente**: Ley de Hacienda Municipal del Estado de Tabasco, Art. 94
- **URL**: https://congresotabasco.gob.mx/leyes/
- **Tarifa**: 5 rangos progresivos, cuota fija en pesos + tasa porcentual (0.7% a 1.1%)
  - Tabla reformada P.O. 30-dic-1995, **sin cambios en todo el periodo 2010-2025**
- **Base gravable especial**: valor FISCAL = valor catastral × porcentaje fiscal de zona
  - Porcentaje fiscal ≥ 20%, determinado por cada Cabildo, aprobado por Congreso (Art. 90)
  - Diferente a todos los demás estados donde la base es el valor catastral directamente
- **Mínimo anual** (Art. 98):
  - Rústico: 3 × v.d.u.m.a. | Urbano: 4 × v.d.u.m.a.
  - Pre-2017: en SM diarios | Post-2017: en UMA diarias (reforma P.O. 7808, 05-jul-2017)
- **Sobretasa baldíos** (Art. 97): 0-30% adicional, variable por municipio
- **Particularidades**:
  - Estado más sencillo: tabla estática, sin actualizaciones, sin conversión de unidades
  - La única variación año a año es el monto del impuesto mínimo (SM→UMA)
  - El porcentaje fiscal de zona introduce variabilidad municipal que NO está en la tarifa
  - Pago semestral (Art. 99), a diferencia de la mayoría que es anual/bimestral

---

## Notas de implementación

### Patrón general del pipeline

```
descarga (PO/DO) → master (PDF consolidado) → segmentación → [OCR] → extracción LLM → validación
```

Para estados del Grupo B (tarifa uniforme), el pipeline se simplifica a:

```
tarifa hardcoded → expansión (municipio × año) → validación
```

### Catálogos compartidos (catalogs/)

| Archivo | Contenido | Usado por |
|---------|-----------|-----------|
| `colima_sm_2010-2016.csv` | SM diario aplicable a Colima | Colima |
| `uma_2016-2025.csv` | UMA diaria nacional | Colima, Tabasco, Chihuahua |
| `INPC_2008-2025.csv` | Inflación mensual INPC | Sinaloa |
| `edomex_codigo_municipal_*.txt` | Tablas Art. 109 por periodo | Edo. México (referencia) |
| `sinaloa_tablas.zip` | PDFs de tablas publicadas | Sinaloa (verificación) |
| `sinaloa_ley_de_hacienda.pdf` | Art. 35-36 Ley de Hacienda | Sinaloa (referencia) |
| `tabasco_ley_de_hacienda.pdf` | Art. 87-105 Ley de Hacienda | Tabasco (referencia) |

### Ejecución

# Estado con pipeline completo (Grupo A)
python -m scripts.run_pipeline coahuila --steps download build segment extract validate

# Estado con tarifa hardcoded (Grupo B)
python -m scripts.run_pipeline chihuahua --steps extract validate

# Todos los estados registrados
python -m scripts.run_pipeline --all --steps extract validate
```bash
```