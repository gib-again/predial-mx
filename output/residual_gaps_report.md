# Reporte de huecos residuales — decisión pendiente

Tras `apply_discovered_laws` + `reextract_from_audit` + `balance_panel_v2`, siguen sin cobertura **3** muni-años distribuidos en **2** municipios.

## Resumen

**Por estado:**

| Estado | Huecos residuales |
|---|---:|
| Yucatan | 3 |

**Por motivo:**

| Motivo | Conteo |
|---|---:|
| `schema_discontinuity` | 2 |
| `edge` | 1 |

## Munis residuales — decisión sugerida

Cada muni listado abajo causa desbalance. La columna **decisión sugerida** te indica qué cabe hacer: aceptar la imputación parcial, marcar el muni como missing intencional, o reabrir investigación.

### 31072 Yucatan — Suma

- Años faltantes (2): 2011, 2012
- Observaciones válidas en universo: 12
- Motivos: schema_discontinuity
- Estatus auditor: no_existe_ley
- **Decisión sugerida**: **Marcar missing**: auditor confirmó que no hay Ley de Ingresos. Considera ejecutar `reextract_from_audit` para emitir JSONs sintéticos `audit_no_ley` que cubran el panel.

### 31073 Yucatan — Tahdziu

- Años faltantes (1): 2025
- Observaciones válidas en universo: 10
- Motivos: edge
- Estatus auditor: (no audited)
- **Decisión sugerida**: **Revisar manualmente**: motivos mixtos (edge). Ver vecinos observados (10 obs).
