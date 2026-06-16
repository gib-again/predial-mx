# Reporte de ambigüedad en identificadores tarifarios

Corpus: **12145 JSONs** procesados, **30035 filas** con identificador (tarifa_millar=24562, mixto=5473), **4119 identificadores únicos** por (tipo_esquema, estado, grupo, clave).

Cubre dos esquemas:

- `tarifa_millar`: campo `clave` agrupado por `grupo` (urbano, rústico, ...).
- `mixto`: campo `nombre` en cada `columna`; el `grupo` queda vacío.

## 1. Inconsistencias slugify

14 identificadores donde `slugify(clave) != clave` (0.3% del total).

Ejemplos (primeros 20):

| tipo_esquema | estado | grupo | clave actual | slugify_sugerido |
|---|---|---|---|---|
| `tarifa_millar` | coahuila | `rustico` | `rústicos_industriales_eólica_ejecución` | `rusticos_industriales_eolica_ejecucion` |
| `tarifa_millar` | coahuila | `rustico` | `rústicos_industriales_eólica_desarrollo` | `rusticos_industriales_eolica_desarrollo` |
| `tarifa_millar` | coahuila | `rustico` | `rústicos_industriales_eólica_proyecto` | `rusticos_industriales_eolica_proyecto` |
| `tarifa_millar` | guanajuato | `urbano` | `años_2002_2010` | `anos_2002_2010` |
| `tarifa_millar` | guanajuato | `urbano` | `años_2002_2010_sin_edificaciones` | `anos_2002_2010_sin_edificaciones` |
| `tarifa_millar` | guanajuato | `rustico` | `años_2002_2010` | `anos_2002_2010` |
| `tarifa_millar` | guanajuato | `urbano` | `años_2002_a_2014` | `anos_2002_a_2014` |
| `tarifa_millar` | guanajuato | `rustico` | `rústico` | `rustico` |
| `tarifa_millar` | guanajuato | `rustico` | `rústico_anteriores_1993` | `rustico_anteriores_1993` |
| `tarifa_millar` | sanluispotosi | `rustico` | `rusticos_proPIedad_privada` | `rusticos_propiedad_privada` |
| `tarifa_millar` | tamaulipas | `general` | `casa_hogar_o_predios_filantrópicos` | `casa_hogar_o_predios_filantropicos` |
| `tarifa_millar` | yucatan | `urbano` | `predios_urbanos_ubicados_en_comisarías` | `predios_urbanos_ubicados_en_comisarias` |
| `tarifa_millar` | yucatan | `rustico` | `predios_rústicos` | `predios_rusticos` |
| `mixto` | yucatan | `` | `rústicos_fuera_de_zona_industrial` | `rusticos_fuera_de_zona_industrial` |

## 2. Fragmentación intra-(tipo, estado, grupo)

Top 20 combinaciones con mayor número de identificadores distintos — fragmentación alta indica el mismo concepto se nombra de muchas formas dentro de un mismo (esquema, estado, grupo):

| tipo_esquema | estado | grupo | n_claves | ejemplos |
|---|---|---|---:|---|
| `tarifa_millar` | Jalisco | `urbano` | 696 | edificado_valor_determinado, edificados, edificados_valor_determinado, … (+693) |
| `tarifa_millar` | Guanajuato | `urbano` | 614 | 1993_2002_edificado, 1993_2002_sin_edificacion, 2002_2009_con_edificaciones, … (+611) |
| `tarifa_millar` | Guanajuato | `general` | 450 | 2002_2014, 2002_a_2010_edificados, 2002_a_2010_rusticos, … (+447) |
| `tarifa_millar` | Jalisco | `rustico` | 402 | cerril_improductivo_eriazo_valor_determinado_lhm, cerril_improductivo_o_erialazo_valor_determinado, cerril_improductivo_o_eriazo, … (+399) |
| `tarifa_millar` | Guanajuato | `rustico` | 307 | 1993_2002, 2002_2009, 2002_2010, … (+304) |
| `tarifa_millar` | San Luis Potosí | `urbano` | 299 | baldios, comercio_o_servicios, comercio_o_servicios_con_edificacion_o_sin_ella, … (+296) |
| `tarifa_millar` | Sonora | `rustico` | 215 | acuicola_1, acuicola_2, acuicola_3, … (+212) |
| `tarifa_millar` | Tamaulipas | `urbano` | 122 | adquirentes_lotes_fraccionamientos_sin_construccion_dos_anos, adquirentes_lotes_fraccionamientos_sin_construir_dos_anos, baldio, … (+119) |
| `tarifa_millar` | San Luis Potosí | `rustico` | 112 | instituciones_religiosas, predios_de_produccion_privada_o_ejidal, predios_de_propiedad_ejidal, … (+109) |
| `tarifa_millar` | Jalisco | `general` | 89 | edificados_y_no_edificados_no_excede_70000, general_base_fiscal_registrada_10_millar, general_base_fiscal_registrada_tasas_diferentes, … (+86) |
| `tarifa_millar` | Coahuila | `urbano` | 72 | comercial, comercial_con_edificacion, comercial_sin_edificacion, … (+69) |
| `tarifa_millar` | Coahuila | `rustico` | 69 | minimo_rustico, predio_rustico, predio_rustico_industrial, … (+66) |
| `tarifa_millar` | San Luis Potosí | `general` | 64 | comercio_o_servicios, comercios_u_oficinas, habitacional_distintos_con_edificacion_o_cercados, … (+61) |
| `tarifa_millar` | Oaxaca | `general` | 51 | avaluo_comercial, bases_gravables_de_1_a_3_millones, bases_gravables_de_3_a_4_millones, … (+48) |
| `tarifa_millar` | Guanajuato | `otro` | 45 | anio_2002_a_2013, anios_2002_a_2013_sin_edificaciones, anterior_1993, … (+42) |
| `tarifa_millar` | Tamaulipas | `otro` | 34 | baldio_urbano, casa_hogar_filantripicos, casa_hogar_filantropicos, … (+31) |
| `tarifa_millar` | Oaxaca | `urbano` | 33 | centro_alta, centro_baja, centro_media, … (+30) |
| `tarifa_millar` | Coahuila | `general` | 32 | comercial_urbano_con_edificacion, comercial_urbano_sin_edificacion, concesiones_uso_goce_predios_rusticos, … (+29) |
| `mixto` | Guanajuato | `` | 32 | general, habitacional_con_edificaciones, habitacional_general, … (+29) |
| `tarifa_millar` | San Luis Potosí | `otro` | 29 | instituciones_religiosas, instituciones_religiosas_en_general, predios_de_propiedad_ejidal, … (+26) |

## 3. Solapamiento inter-estado por concepto

Para conceptos típicos del predial, ¿qué claves los representan en cada estado? Las divergencias indican oportunidades de consolidación nomenclatural.

### `urbano_edificado` — 1373 claves en 7 estados

- **Coahuila**: `comercial_urbano_con_edificacion`, `comercial_urbano_sin_edificacion`, `predio_urbano_no_edificado_sin_barda`, `predios_urbanos_comerciales_con_edificacion`, `predios_urbanos_comerciales_sin_edificacion` … (+36)
- **Guanajuato**: `anteriores_1993_urbano_suburbano_con_edificacion`, `anteriores_1993_urbano_suburbano_sin_edificacion`, `anteriores_2002_hasta_1993_urbano_suburbano_con_edificacion`, `anteriores_2002_hasta_1993_urbano_suburbano_sin_edificacion`, `general_urbano_con_edificaciones` … (+507)
- **Jalisco**: `general_y_urbanos_edificados_valores_anteriores_2000`, `predios_en_general_urbanos_edificados_valores_anteriores_2000`, `predios_en_general_urbanos_edificados_valores_anteriores_2000_adeudos`, `predios_en_general_y_urbanos_edificados_valores_anteriores_2000`, `predios_en_general_y_urbanos_edificados_valores_anteriores_2000_adeudos` … (+651)
- **Querétaro**: `predio_urbano_edificado`, `urbano_edificado`
- **San Luis Potosí**: `predios_urbanos_suburbanos_con_edificacion_habitacional_hasta_230000`, `predios_urbanos_suburbanos_con_edificacion_habitacional_mayor_230000`, `predios_urbanos_suburbanos_sin_edificacion_bardeados_cercados_limpios`, `predios_urbanos_suburbanos_sin_edificacion_sin_bardear_sin_cercado`, `predios_urbanos_y_suburbanos_con_edificacion_de_uso_habitacional_hasta_230000` … (+78)
- **Sonora**: `predios_urbanos_edificados`, `predios_urbanos_edificados_rango_1`, `predios_urbanos_edificados_rango_10`, `predios_urbanos_edificados_rango_11`, `predios_urbanos_edificados_rango_2` … (+10)
- **Tamaulipas**: `predios_suburbanos_con_edificaciones`, `predios_urbanos_con_edificacion_inferior_a_la_quinta_parte_del_terreno`, `predios_urbanos_con_edificacion_inferior_a_quinta_parte`, `predios_urbanos_con_edificacion_inferior_a_quinta_parte_del_terreno`, `predios_urbanos_con_edificacion_inferior_a_un_quinto_del_terreno` … (+59)

### `urbano_baldio` — 63 claves en 6 estados

- **Coahuila**: `predios_urbanos_baldios`, `predios_urbanos_baldios_centro`, `predios_urbanos_baldios_en_centro`, `predios_urbanos_no_baldios`, `urbano_baldio` … (+4)
- **Guanajuato**: `urbano_suburbano_baldio`, `urbano_y_suburbano_baldio`
- **Jalisco**: `urbano_baldio`, `urbano_baldio_dentro_zona_edificada`, `urbano_baldio_dentro_zonas_edificadas`, `urbano_baldio_dentro_zonas_edificadas_valor_determinado_lhmej`, `urbano_baldio_fuera_zona_edificada` … (+12)
- **Querétaro**: `predio_urbano_baldio`, `urbano_baldio`
- **San Luis Potosí**: `urbanos_suburbanos_comercio_o_servicios_lotes_baldios_cercados`, `urbanos_suburbanos_comercio_o_servicios_lotes_baldios_no_cercados`, `urbanos_suburbanos_habitacionales_baldios`, `urbanos_suburbanos_lotes_baldios_cercado`, `urbanos_suburbanos_lotes_baldios_cercados` … (+6)
- **Tamaulipas**: `baldio_urbano`, `predios_urbanos_baldios`, `predios_urbanos_sin_edificacion_baldios`, `predios_urbanos_sin_edificaciones_baldios`, `predios_urbanos_suburbanos_baldios` … (+17)

### `urbano_generico` — 1769 claves en 8 estados

- **Coahuila**: `comercial_urbano_con_edificacion`, `comercial_urbano_sin_edificacion`, `industrial_urbano`, `predio_urbano`, `predio_urbano_no_edificado_sin_barda` … (+65)
- **Guanajuato**: `anteriores_1993_urbano_suburbano_con_edificacion`, `anteriores_1993_urbano_suburbano_sin_edificacion`, `anteriores_2002_hasta_1993_urbano_suburbano_con_edificacion`, `anteriores_2002_hasta_1993_urbano_suburbano_sin_edificacion`, `entrada_vigor_urbanos_suburbanos` … (+609)
- **Jalisco**: `cambio_de_rustico_a_urbano`, `cambio_rustico_a_urbano`, `cambio_rustico_a_urbano_0_1_por_ciento_mas_cuota`, `cambio_rustico_a_urbano_tasa_0_1_por_ciento`, `cambio_rustico_a_urbano_tasa_bimestral_0_1_por_ciento` … (+682)
- **Querétaro**: `predio_urbano_baldio`, `predio_urbano_edificado`, `urbano_baldio`, `urbano_edificado`
- **San Luis Potosí**: `predios_urbanos_suburbanos_comercio_servicios`, `predios_urbanos_suburbanos_comercio_servicios_oficinas_industrial`, `predios_urbanos_suburbanos_con_edificacion_habitacional_hasta_230000`, `predios_urbanos_suburbanos_con_edificacion_habitacional_mayor_230000`, `predios_urbanos_suburbanos_habitacional_1` … (+249)
- **Sonora**: `general_urbano`, `predios_construidos_urbanos`, `predios_rurales_hectarea_sub_urbano_carreteras`, `predios_rurales_hectarea_sub_urbano_casco_urbano`, `predios_rurales_sub_urbano_carreteras` … (+19)
- **Tamaulipas**: `baldio_urbano`, `comercial_industrial_urbano_suburbano`, `habitacional_urbano_suburbano`, `predios_suburbanos`, `predios_suburbanos_con_edificaciones` … (+102)
- **Yucatán**: `predios_urbanos`, `predios_urbanos_comisarias`, `predios_urbanos_tekax`, `predios_urbanos_ubicados_en_comisarías`, `predios_urbanos_ubicados_en_tekax` … (+4)

### `rustico` — 894 claves en 8 estados

- **Coahuila**: `concesiones_uso_goce_predios_rusticos`, `minimo_rustico`, `predio_rustico`, `predio_rustico_industrial`, `predio_rustico_industrial_eolica_desarrollo` … (+66)
- **Guanajuato**: `2002_a_2010_rusticos`, `anio_2002_2010_rustico`, `anios_2002_2011_rustico`, `anios_2002_a_2013_rustico`, `anios_2002_a_2013_rusticos` … (+275)
- **Jalisco**: `cambio_de_rustico_a_urbano`, `cambio_rustico_a_urbano`, `cambio_rustico_a_urbano_0_1_por_ciento_mas_cuota`, `cambio_rustico_a_urbano_tasa_0_1_por_ciento`, `cambio_rustico_a_urbano_tasa_bimestral_0_1_por_ciento` … (+405)
- **Querétaro**: `predio_rustico`, `rustico`
- **San Luis Potosí**: `predios_rusticos`, `predios_rusticos_agroindustrial`, `predios_rusticos_comercial`, `predios_rusticos_de_propiedad_ejidal`, `predios_rusticos_de_propiedad_privada` … (+78)
- **Sonora**: `predios_rusticos`, `predios_rusticos_edificaciones`, `predios_rusticos_ejidales_comunales`, `predios_rusticos_ejidales_o_comunales`, `predios_rusticos_ejidales_o_comunales_edificados` … (+9)
- **Tamaulipas**: `predio_rustico`, `predios_rusticos`, `predios_suburbanos_y_rusticos`, `predios_urbanos_suburbanos_rusticos`, `predios_urbanos_suburbanos_y_rusticos` … (+11)
- **Yucatán**: `costera_rustica`, `predios_rusticos`, `predios_rusticos_produccion_agropecuaria`, `predios_rústicos`, `rustico` … (+13)

### `ejidal` — 106 claves en 5 estados

- **Coahuila**: `predios_rusticos_y_ejidal_titulado`, `predios_rusticos_y_ejidales_titulados`, `predios_rusticos_y_extraccion_ejidal`, `predios_rusticos_y_extraccion_ejidal_titulados`, `predios_urbano_habitacional_o_solares_en_congregaciones_ejidos` … (+12)
- **Oaxaca**: `predios_pertenecientes_a_nucleos_agrarios_de_poblacion_ejidal_o_comunal`
- **Querétaro**: `predio_de_produccion_agricola_con_dominio_pleno_proveniente_de_ejido`, `predio_de_produccion_agricola_con_dominio_pleno_que_provenga_de_ejido`, `predio_de_produccion_agricola_condominio_pleno_que_provenga_de_ejido`, `predio_produccion_agricola_con_dominio_pleno_provenga_de_ejido`, `predio_produccion_agricola_con_dominio_pleno_proveniente_de_ejido` … (+16)
- **San Luis Potosí**: `predios_de_produccion_privada_o_ejidal`, `predios_de_propiedad_ejidal`, `predios_de_propiedad_ejidal_de_uso_comercial_y_o_turistica`, `predios_de_propiedad_ejidal_de_uso_ganadero_y_o_agricola`, `predios_de_propiedad_ejidal_de_uso_industrial_o_agroindustrial` … (+51)
- **Sonora**: `predial_ejidal`, `predial_ejidal_agostadero_praderas_naturales`, `predial_ejidal_con_riego_de_agua_de_presa_o_rio_irregularmente_aun_dentro_de_distritos`, `predial_ejidal_distrito_de_riego_con_derecho_a_agua_de_presa_regularmente`, `predios_ejidales` … (+6)

### `comercial` — 110 claves en 6 estados

- **Coahuila**: `comercial`, `comercial_con_edificacion`, `comercial_o_de_servicios`, `comercial_sin_edificacion`, `comercial_urbano_con_edificacion` … (+16)
- **Jalisco**: `urbano_agropecuario_comercial_industrial`, `urbano_naturaleza_agropecuaria_comercial_industrial`, `urbanos_agropecuaria_comercial_industrial_edificados_no_edificados`, `urbanos_naturaleza_agropecuaria_comercial_industrial`, `urbanos_naturaleza_agropecuaria_comercial_o_industrial` … (+1)
- **Oaxaca**: `avaluo_comercial`, `comercio_establecido_terreno_hasta_200m2_construccion_hasta_159m2`, `comercio_establecido_terreno_mayor_a_200m2_o_construccion_mayor_a_160m2`
- **San Luis Potosí**: `comercio_o_servicios`, `comercio_o_servicios_con_edificacion_o_sin_ella`, `comercio_o_servicios_con_o_sin_edificacion`, `comercio_servicios`, `comercio_u_oficina` … (+61)
- **Tamaulipas**: `comercial_e_industrial`, `comercial_industrial_servicios`, `comercial_industrial_urbano_suburbano`, `comercio_y_oficinas`, `predios_urbanos_con_edificaciones_comerciales_industriales_o_de_servicios` … (+7)
- **Yucatán**: `comercial`, `zona_turistica_uxmal_y_recursos_naturales_comercial`

### `habitacional` — 193 claves en 6 estados

- **Coahuila**: `habitacional`, `habitacional_edificado`, `habitacional_edificado_con_barda`, `habitacional_edificado_sin_barda`, `habitacional_no_edificado_con_barda` … (+19)
- **Guanajuato**: `habitacional_con_edificaciones`, `habitacional_general`, `habitacional_urbano_suburbano_con_edificaciones`
- **Oaxaca**: `casa_habitacion_interes_social_terreno_hasta_120m2_construccion_hasta_120m2`, `casa_habitacion_terreno_mayor_a_120m2_o_construccion_mayor_a_120m2`
- **San Luis Potosí**: `habitacional`, `habitacional_baldio`, `habitacional_con_edificacion_o_cercado`, `habitacional_con_edificacion_o_cercados`, `habitacional_distinto_con_edificacion_o_cercado` … (+149)
- **Tamaulipas**: `habitacional`, `habitacional_residencial`, `habitacional_urbano_suburbano`, `predios_no_edificados_habitacional_residencial`, `predios_urbanos_con_edificaciones_habitacionales` … (+4)
- **Yucatán**: `habitacional`

### `industrial` — 216 claves en 6 estados

- **Coahuila**: `industrial`, `industrial_comercial_o_servicios`, `industrial_con_edificacion`, `industrial_sin_edificacion`, `industrial_urbano` … (+54)
- **Jalisco**: `urbano_agropecuario_comercial_industrial`, `urbano_naturaleza_agropecuaria_comercial_industrial`, `urbanos_agropecuaria_comercial_industrial_edificados_no_edificados`, `urbanos_naturaleza_agropecuaria_comercial_industrial`, `urbanos_naturaleza_agropecuaria_comercial_o_industrial` … (+1)
- **San Luis Potosí**: `industrial`, `industrial_dentro_zona_industrial`, `industrial_fuera_de_zona_industrial`, `industrial_fuera_de_zona_industrial_con_edificacion_o_sin_ella`, `industrial_fuera_zona_industrial` … (+110)
- **Sonora**: `industrial`, `industrial_1`, `industrial_2`, `industrial_3`, `industrial_4` … (+9)
- **Tamaulipas**: `comercial_e_industrial`, `comercial_industrial_servicios`, `comercial_industrial_urbano_suburbano`, `industrial_y_otros`, `predios_suburbanos_de_uso_industrial` … (+15)
- **Yucatán**: `rústicos_fuera_de_zona_industrial`, `zona_industrial_tablajes_catastrales`

## 4. Frecuencia global (top 20)

| tipo_esquema | estado | grupo | clave | n_apariciones | n_municipios |
|---|---|---|---|---:|---:|
| `mixto` | Yucatán | `` | `general` | 2927 | 75 |
| `mixto` | Sonora | `` | `general` | 1238 | 45 |
| `tarifa_millar` | Tamaulipas | `rustico` | `predios_rusticos` | 443 | 36 |
| `tarifa_millar` | Coahuila | `urbano` | `predios_urbanos` | 441 | 36 |
| `tarifa_millar` | Coahuila | `rustico` | `predios_rusticos` | 429 | 36 |
| `tarifa_millar` | Jalisco | `urbano` | `urbano_edificado_valor_determinado` | 381 | 86 |
| `tarifa_millar` | Jalisco | `rustico` | `rustico_valor_fiscal_determinado` | 367 | 79 |
| `tarifa_millar` | Jalisco | `urbano` | `urbano_no_edificado_valor_determinado` | 358 | 79 |
| `tarifa_millar` | San Luis Potosí | `rustico` | `rusticos_propiedad_privada` | 336 | 55 |
| `tarifa_millar` | San Luis Potosí | `rustico` | `rusticos_propiedad_ejidal` | 334 | 55 |
| `tarifa_millar` | Tamaulipas | `urbano` | `predios_urbanos_con_edificaciones` | 309 | 24 |
| `tarifa_millar` | Jalisco | `general` | `predios_en_general_base_fiscal_registrada` | 297 | 81 |
| `tarifa_millar` | Sonora | `rustico` | `predios_rurales` | 278 | 27 |
| `tarifa_millar` | Tamaulipas | `urbano` | `predios_suburbanos_con_edificaciones` | 270 | 24 |
| `tarifa_millar` | Jalisco | `rustico` | `rustico_valor_fiscal` | 266 | 36 |
| `tarifa_millar` | Jalisco | `rustico` | `rustico_valores_anteriores_2000` | 257 | 38 |
| `tarifa_millar` | Jalisco | `rustico` | `construcciones_en_predios_rusticos_tasa_inciso_b` | 249 | 32 |
| `tarifa_millar` | Tamaulipas | `urbano` | `predios_urbanos_y_suburbanos_sin_edificaciones_baldios` | 246 | 24 |
| `tarifa_millar` | San Luis Potosí | `urbano` | `urbanos_y_suburbanos_habitacionales_no_cercados` | 243 | 53 |
| `tarifa_millar` | San Luis Potosí | `urbano` | `urbanos_suburbanos_habitacionales_no_cercados` | 230 | 53 |

## Propuestas de consolidación

Recomendaciones derivadas del análisis (ver `output/anexos/bitacora_acciones_pendientes.md` P-102):

1. Aplicar `text_utils.slugify` automático en validator de `FilaTarifaMillar.clave` para normalizar mayúsculas/signos (elimina inconsistencias de la sección 1).
2. Definir un set canónico de claves por grupo (urbano_edificado, urbano_baldio, rustico, ejidal, etc.) y reformular el prompt del extractor para preferirlas. Reduce la fragmentación de la sección 2.
3. Para los conceptos de la sección 3, considerar un mapeo canónico que renombre los slugs durante consolidación del panel.