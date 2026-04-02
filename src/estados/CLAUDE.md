# Estados — Guía para adaptadores

## Checklist para nuevo estado

1. Investigar estructura del Periódico Oficial (tomos vs individuales, API vs HTML)
2. Descargar 2-3 PDFs de muestra (año reciente, antiguo, municipio grande)
3. Identificar patrón de URLs y esquema de predial dominante
4. Verificar si necesita OCR (probar flags cross-platform, ver BEST_PRACTICES.md §3)
5. Implementar `config.py` (URLs, prefijo, años, flags, municipios/aliases)
6. Implementar `download.py`
7. Si OCR: implementar `ocr.py` (ocrmypdf --force-ocr + flags cross-platform)
8. Implementar `segment.py` (validar con muestras)
9. Agregar aliases de municipios (tolerancia a ruido OCR si aplica)
10. Agregar prefijo a `src/core/constants.py` (`PREFIJOS_ESTADO`)
11. Agregar import + `@register` en `src/estados/__init__.py`
12. Agregar entrada en `docs/notas_por_estado.md`
13. Test: pipeline completo download → [ocr] → segment → extract → validate

## Estructura de un adaptador

```
src/estados/{slug}/
├── __init__.py    # Clase adapter + @register
├── config.py      # URLs, PREFIJO, años, flags, MUNICIPIOS, ALIASES
├── download.py    # Descarga PDFs del Periódico Oficial
├── segment.py     # Localiza leyes → extrae sección predial → TXT/PDF
├── ocr.py         # (Opcional) OCR con ocrmypdf
└── tarifa_base.py # (Opcional) Lógica de tarifa base estatal
```

## Regex de segmentación probados

```python
# Inicio de sección predial
r"(?:IMPUESTO|DEL\s+IMPUESTO)\s+(?:SOBRE\s+)?(?:LA\s+)?PROPIEDAD\s+(?:RA[IÍ]Z|INMOBILIARIA)"
r"(?:IMPUESTO\s+)?PREDIAL"
r"ART[IÍ]CULO\s+\d+.*?PREDIAL"

# Fin (inicio de siguiente impuesto)
r"(?:IMPUESTO\s+SOBRE\s+)?(?:TRASLACI[OÓ]N|ADQUISICI[OÓ]N)\s+DE\s+(?:DOMINIO|INMUEBLES)"
r"IMPUESTO\s+SOBRE\s+ESPECT[AÁ]CULOS"
```

## Esquemas dominantes por estado

| Estado | Esquema | Notas |
|--------|---------|-------|
| Coahuila | mixto | Multi-columna (habitacional, no hab, con/sin barda) |
| Jalisco | tarifa_millar | Bimestral por tipo de predio |
| Querétaro | tasa_unica | Factor sobre valor catastral |
| Yucatán | variado | Mezcla tasa plana, progresivo, factor decimal |
| Tamaulipas | tarifa_millar | Por tipo de predio |
| Chihuahua | progresivo | 5 rangos + tasa fija rústicos |
| Colima | progresivo | 26 rangos urbano, 9 rústico, UMA |
| Edomex | progresivo | 13 rangos, pesos nominales |
| Sinaloa | progresivo | 11 rangos, INPC anual |
| Tabasco | progresivo | 5 rangos, estática desde 1995 |
| Guanajuato | tarifa_millar | Con cuota_fija_adicional en algunos |
| Oaxaca | — | Recién agregado |

## Trampas comunes en segmentación

- Promulgación ("SE EXPIDE LA LEY...") al inicio del tomo ≠ contenido de la ley
- Entradas de índice/TOC mencionan "predial" pero no son la sección
- Tablas de valores catastrales (Yucatán, Tamaulipas) son catastro, no tarifa
- Mojibake por OCR: normalizar texto antes de aplicar regex
