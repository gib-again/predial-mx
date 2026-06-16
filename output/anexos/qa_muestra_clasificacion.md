# QA muestra aleatoria de clasificaciones (seed=42, k=3)

Fuente: `output/panel_v2_raw.csv` (observaciones, sin imputación; clasificación canónica schema_v2 vía la capa de validación).

## Tarifa al millar  — `tarifa_millar`  (4622 casos en pool)

### Acambaro, Guanajuato (2022)
- **clasificado como**: `tarifa_millar`
- **n_filas**: 8
- **JSON**: `predial-mx-v2/guanajuato/GTO_PREDIAL_2022_acambaro.json`
- **TXT segmento**: (TXT no encontrado)
- **comentarios extractor**: Artículo 4 establece tasas anuales al millar por antigüedad y por tipo de inmueble (urbanos y suburbanos con/sin edificaciones, rústicos). Se transcribe como tarifa_millar porque la mecánica es categórica, no por rangos catastrales. El texto OCR muestra una tabla con posibles duplicidades/artefactos
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "grupo": "urbano",
    "clave": "inmuebles_urbanos_y_suburbanos_con_edificaciones",
    "descripcion": "A la entrada en vigor de la presente Ley.",
    "tasa_millar": 0.0024,
    "periodicidad": "anual",
    "cuota_fija_adicional": null
  },
  {
    "grupo": "urbano",
    "clave": "inmuebles_urbanos_y_suburbanos_con_edificaciones_2002_a_2021",
    "descripcion": "Durante los años 2002 y hasta el 2021 inclusive.",
    "tasa_millar": 0.0024,
    "periodicidad": "anual",
    "cuota_fija_adicional": null
  },
  {
    "grupo": "urbano",
    "clave": "inmuebles_urbanos_y_suburbanos_con_edificaciones_1993_a_2001",
    "descripcion": "Con anterioridad al año 2002 y hasta 1993 inclusive.",
    "tasa_millar": 0.008,
    "periodicidad": "anual",
    "cuota_fija_adicional": null
  }
]
```

### Ezequiel Montes, Queretaro (2019)
- **clasificado como**: `tarifa_millar`
- **n_filas**: 6
- **JSON**: `predial-mx-v2/queretaro/QRO_PREDIAL_2019_ezequiel_montes.json`
- **TXT segmento**: `data/queretaro/focus_predial/2019/QRO_PREDIAL_2019_ezequiel_montes.txt`
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "grupo": "urbano",
    "clave": "predio_urbano_edificado",
    "descripcion": "Predio Urbano edificado",
    "tasa_millar": 1.6,
    "periodicidad": "anual",
    "cuota_fija_adicional": null
  },
  {
    "grupo": "urbano",
    "clave": "predio_urbano_baldio",
    "descripcion": "Predio Urbano baldío",
    "tasa_millar": 8.0,
    "periodicidad": "anual",
    "cuota_fija_adicional": null
  },
  {
    "grupo": "rustico",
    "clave": "predio_rustico",
    "descripcion": "Predio rústico",
    "tasa_millar": 1.2,
    "periodicidad": "anual",
    "cuota_fija_adicional": null
  }
]
```

### San Martin Hidalgo, Jalisco (2022)
- **clasificado como**: `tarifa_millar`
- **n_filas**: 3
- **JSON**: `predial-mx-v2/jalisco/JAL_PREDIAL_2022_san_martin_hidalgo.json`
- **TXT segmento**: `data/jalisco/focus_predial/2022/JAL_PREDIAL_2022_san_martin_hidalgo.txt`
- **mínimo predial**: 1.0 uma (bimestral)
- **comentarios extractor**: El texto establece una tasa bimestral al millar diferenciada para predios rústicos y urbanos (edificados y no edificados). Además, indica cuotas fijas adicionales en UMAD por bimestre. Se ignoran reducciones/beneficios/condonaciones. El mínimo predial aparece en el Art. 24: 'En ningún caso el impues
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "grupo": "rustico",
    "clave": "rustico_valor_fiscal",
    "descripcion": "Predios rústicos: Para predios cuyo valor real se determine en los términos de la Ley de Hacienda Municipal del Estado de Jalisco, sobre el valor fiscal determinado",
    "tasa_millar": 0.21,
    "periodicidad": "bimestral",
    "cuota_fija_adicional": {
      "monto": 0.22,
      "periodicidad": "bimestral",
      "unidad": "uma"
    }
  },
  {
    "grupo": "urbano",
    "clave": "urbano_edificado",
    "descripcion": "Predios urbanos: Predios edificados cuyo valor real se determine en los términos de la Ley de Hacienda Municipal del Estado de Jalisco, sobre el valor determinado",
    "tasa_millar": 0.21,
    "periodicidad": "bimestral",
    "cuota_fija_adicional": {
      "monto": 0.3,
      "periodicidad": "bimestral",
      "unidad": "uma"
    }
  },
  {
    "grupo": "urbano",
    "clave": "urbano_no_edificado",
    "descripcion": "Predios urbanos: Predios no edificados, cuyo valor real se determine en los términos de la Ley de Hacienda Municipal del Estado de Jalisco, sobre el valor determinado",
    "tasa_millar": 0.32,
    "periodicidad": "bimestral",
    "cuota_fija_adicional": {
      "monto": 0.3,
      "periodicidad": "bimestral",
      "unidad": "uma"
    }
  }
]
```

## Progresivo (tasa marginal)  — `progresivo`  (5258 casos en pool)

### Tecoh, Yucatan (2014)
- **clasificado como**: `progresivo`
- **n_filas**: 7
- **JSON**: `predial-mx-v2/yucatan/YUC_PREDIAL_2014_tecoh.json`
- **TXT segmento**: `data/yucatan/focus_predial/2014/YUC_PREDIAL_2014_tecoh.txt`
- **comentarios extractor**: Art. 13: tabla principal del impuesto predial sobre valor catastral con cuotas fijas bimestrales implícitas por dividirse entre seis; se transcribe la mecánica anual de la tarifa. Tarifa paralela no incluida en la tabla principal: predios destinados a la producción agropecuaria pagan 10 al millar an
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "n_rango": 1,
    "inferior": 0.0,
    "superior": 20000.0,
    "cuota_fija": 12.0,
    "tasa_marginal": 0.0009
  },
  {
    "n_rango": 2,
    "inferior": 20000.0,
    "superior": 40000.0,
    "cuota_fija": 22.0,
    "tasa_marginal": 0.0009
  },
  {
    "n_rango": 3,
    "inferior": 40000.0,
    "superior": 60000.0,
    "cuota_fija": 32.0,
    "tasa_marginal": 0.0009
  }
]
```

### Nopaltepec, Mexico (2020)
- **clasificado como**: `progresivo`
- **n_filas**: 13
- **JSON**: `predial-mx-v2/edomex/MEX_PREDIAL_2020_nopaltepec.json`
- **TXT segmento**: (código estatal hardcoded)
- **comentarios extractor**: Hardcoded → v2 desde Código Financiero del Estado de México (Art. 109).
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "n_rango": 1,
    "inferior": 1.0,
    "superior": 180970.0,
    "cuota_fija": 170.0,
    "tasa_marginal": 0.000331
  },
  {
    "n_rango": 2,
    "inferior": 180971.0,
    "superior": 343840.0,
    "cuota_fija": 230.0,
    "tasa_marginal": 0.00135
  },
  {
    "n_rango": 3,
    "inferior": 343841.0,
    "superior": 554420.0,
    "cuota_fija": 450.0,
    "tasa_marginal": 0.0014
  }
]
```

### Santa Barbara, Chihuahua (2010)
- **clasificado como**: `progresivo`
- **n_filas**: 5
- **JSON**: `predial-mx-v2/chihuahua/CHIH_PREDIAL_2010_santa_barbara.json`
- **TXT segmento**: (código estatal hardcoded)
- **comentarios extractor**: Hardcoded → v2 desde Código Municipal de Chihuahua (urbano). lim_sup derivado del lim_inf del siguiente rango.
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "n_rango": 1,
    "inferior": 0.0,
    "superior": 183240.0,
    "cuota_fija": 0.0,
    "tasa_marginal": 0.002
  },
  {
    "n_rango": 2,
    "inferior": 183240.0,
    "superior": 366480.0,
    "cuota_fija": 366.48,
    "tasa_marginal": 0.003
  },
  {
    "n_rango": 3,
    "inferior": 366480.0,
    "superior": 641340.0,
    "cuota_fija": 916.2,
    "tasa_marginal": 0.004
  }
]
```

## Tasa única  — `tasa_unica`  (3876 casos en pool)

### Santa Lucia Miahuatlan, Oaxaca (2011)
- **clasificado como**: `tasa_unica`
- **n_filas**: 1
- **JSON**: `data/oaxaca/json_predial/2011/OAX_PREDIAL_2011_santa_lucia_miahuatlan.json`
- **TXT segmento**: `data/oaxaca/focus_predial/2011/OAX_PREDIAL_2011_santa_lucia_miahuatlan.txt`
- **mínimo predial**: 75.0 pesos (anual)
- **comentarios extractor**: La ley establece una tasa del 0.5% anual sobre el valor catastral del inmueble (Santa Lucía Miahuatlán, Oaxaca, ejercicio fiscal 2011). Se capturan mínimos para urbano y rústico; el impuesto se causa anualmente y puede pagarse en 6 partes bimestrales (periodicidad de cálculo anual).
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "descripcion": "Tasa del 0.5% anual sobre el valor catastral del inmueble",
    "tasa": 0.005,
    "base_calculo": "valor_catastral",
    "unidad": "porcentaje",
    "cuota_fija_adicional": null
  }
]
```

### San Baltazar Loxicha, Oaxaca (2011)
- **clasificado como**: `tasa_unica`
- **n_filas**: 1
- **JSON**: `data/oaxaca/json_predial/2011/OAX_PREDIAL_2011_san_baltazar_loxicha.json`
- **TXT segmento**: `data/oaxaca/focus_predial/2011/OAX_PREDIAL_2011_san_baltazar_loxicha.txt`
- **mínimo predial**: 150.0 pesos (anual)
- **comentarios extractor**: El texto indica que la tasa del Impuesto Predial es 0.5% anual sobre el valor catastral (Art. 5) y establece un mínimo de $150.00 (Art. 6). No se observa una tabla por tipo de predio ni esquema progresivo.
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "descripcion": "0.5% anual sobre el valor catastral del inmueble",
    "tasa": 0.005,
    "base_calculo": "valor_catastral",
    "unidad": "porcentaje",
    "cuota_fija_adicional": null
  }
]
```

### Valerio Trujano, Oaxaca (2013)
- **clasificado como**: `tasa_unica`
- **n_filas**: 1
- **JSON**: `data/oaxaca/json_predial/2013/OAX_PREDIAL_2013_valerio_trujano.json`
- **TXT segmento**: `data/oaxaca/focus_predial/2013/OAX_PREDIAL_2013_valerio_trujano.txt`
- **comentarios extractor**: En las páginas proporcionadas (Octava Sección 13-14) se observa el Apartado A. Del Impuesto Predial. Se establece una tasa única del 0.5% anual sobre el valor catastral del inmueble (Art. 18). No se aprecia una tabla de tasas por tipo de predio. El Art. 19 menciona un mínimo, pero lo define de forma
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "descripcion": "La tasa de este impuesto será del 0.5% anual sobre el valor catastral del inmueble.",
    "tasa": 0.005,
    "base_calculo": "valor_catastral",
    "unidad": "porcentaje",
    "cuota_fija_adicional": null
  }
]
```

## Cuota fija (tarifa única)  — `cuota_fija`  (77 casos en pool)

### Teya, Yucatan (2023)
- **clasificado como**: `cuota_fija_simple`
- **n_filas**: 1
- **JSON**: `predial-mx-v2/yucatan/YUC_PREDIAL_2023_teya.json`
- **TXT segmento**: `data/yucatan/focus_predial/2023/YUC_PREDIAL_2023_teya.txt`
- **comentarios extractor**: Art. 13 establece una tarifa de cuota fija anual para predios urbanos ($60.00) y una cuota fija anual para predios rústicos ($40.00). Art. 15 regula un impuesto sobre rentas o frutos civiles (4% mensual para casas habitación y 4% mensual para actividades), que corresponde a una base distinta del pre
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "descripcion": "Por predios urbanos",
    "monto": 60.0,
    "periodicidad": "anual",
    "unidad": "pesos"
  }
]
```

### Santa Maria Yucuhiti, Oaxaca (2011)
- **clasificado como**: `cuota_fija_simple`
- **n_filas**: 1
- **JSON**: `data/oaxaca/json_predial/2011/OAX_PREDIAL_2011_santa_maria_yucuhiti.json`
- **TXT segmento**: `data/oaxaca/focus_predial/2011/OAX_PREDIAL_2011_santa_maria_yucuhiti.txt`
- **comentarios extractor**: El texto establece únicamente una cuota fija anual para el pago del Impuesto Predial (Art. 4). La división en seis pagos bimestrales (Art. 5) se considera forma de pago, no cambia la mecánica (cuota fija anual). No se menciona tasa al millar, tabla de rangos, ni mínimo predial.
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "descripcion": "Cuota fija anual por impuesto predial",
    "monto": 55.0,
    "periodicidad": "anual",
    "unidad": "pesos"
  }
]
```

### Yaxkukul, Yucatan (2021)
- **clasificado como**: `cuota_fija`
- **n_filas**: 0
- **JSON**: `predial-mx-v2/yucatan/YUC_PREDIAL_2021_yaxkukul.json`
- **TXT segmento**: `data/yucatan/focus_predial/2021/YUC_PREDIAL_2021_yaxkukul.txt`
- **comentarios extractor**: Artículo 13 establece cuota fija para predio urbano y predio rústico por hectárea. Se ignoran valores catastrales, licencias de construcción y frutos civiles por estar fuera del alcance.
- **preview tabla** (primeras 3 filas):
```json
(sin tabla)
```

## Mixto  — `mixto`  (483 casos en pool)

### Tixmehuac, Yucatan (2011)
- **clasificado como**: `mixto`
- **n_filas**: 11
- **JSON**: `predial-mx-v2/yucatan/YUC_PREDIAL_2011_tixmehuac.json`
- **TXT segmento**: `data/yucatan/focus_predial/2011/YUC_PREDIAL_2011_tixmehuac.txt`
- **comentarios extractor**: Art. 4: la tabla principal para predios calculados con base en valor catastral es mixta porque usa brackets por valor catastral con cuota fija anual y factor para aplicar al excedente del límite inferior (0.2000). Además, el texto establece una tarifa paralela para predios rústicos por hectáreas (1 
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "n_rango": 1,
    "inferior": 0.01,
    "superior": 5000.0,
    "columnas": [
      {
        "nombre": "general",
        "valor": 15.0,
        "tipo": "cuota_fija",
        "unidad": "pesos"
      }
    ]
  },
  {
    "n_rango": 2,
    "inferior": 5000.01,
    "superior": 10000.0,
    "columnas": [
      {
        "nombre": "general",
        "valor": 16.0,
        "tipo": "cuota_fija",
        "unidad": "pesos"
      }
    ]
  },
  {
    "n_rango": 3,
    "inferior": 10000.01,
    "superior": 15000.0,
    "columnas": [
      {
        "nombre": "general",
        "valor": 17.0,
        "tipo": "cuota_fija",
        "unidad": "pesos"
      }
    ]
  }
]
```

### Suma, Yucatan (2025)
- **clasificado como**: `mixto`
- **n_filas**: 7
- **JSON**: `predial-mx-v2/yucatan/YUC_PREDIAL_2025_suma_de_hidalgo.json`
- **TXT segmento**: `data/yucatan/focus_predial/2025/YUC_PREDIAL_2025_suma_de_hidalgo.txt`
- **comentarios extractor**: Art. 6: además de la tabla por valor catastral (renglones con cuota fija anual en pesos + factor porcentual sobre el excedente), el artículo establece tarifas separadas para predios habitacionales ($90.00) y comerciales ($100.00) como montos fijos, y para predios destinados a la producción agropecua
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "n_rango": 1,
    "inferior": 0.01,
    "superior": 4000.0,
    "columnas": [
      {
        "nombre": "general",
        "valor": 8.0,
        "tipo": "cuota_fija",
        "unidad": "pesos"
      },
      {
        "nombre": "general",
        "valor": 0.002,
        "tipo": "tasa_marginal",
        "unidad": "porcentaje"
      }
    ]
  },
  {
    "n_rango": 2,
    "inferior": 4000.01,
    "superior": 5500.0,
    "columnas": [
      {
        "nombre": "general",
        "valor": 11.0,
        "tipo": "cuota_fija",
        "unidad": "pesos"
      },
      {
        "nombre": "general",
        "valor": 0.003,
        "tipo": "tasa_marginal",
        "unidad": "porcentaje"
      }
    ]
  },
  {
    "n_rango": 3,
    "inferior": 5500.01,
    "superior": 6500.0,
    "columnas": [
      {
        "nombre": "general",
        "valor": 14.0,
        "tipo": "cuota_fija",
        "unidad": "pesos"
      },
      {
        "nombre": "general",
        "valor": 0.0035,
        "tipo": "tasa_marginal",
        "unidad": "porcentaje"
      }
    ]
  }
]
```

### Chemax, Yucatan (2018)
- **clasificado como**: `mixto`
- **n_filas**: 7
- **JSON**: `predial-mx-v2/yucatan/YUC_PREDIAL_2018_chemax.json`
- **TXT segmento**: `data/yucatan/focus_predial/2018/YUC_PREDIAL_2018_chemax.txt`
- **comentarios extractor**: Art. 13: la tarifa principal para base en valor catastral es una tabla por rangos con cuota fija anual y factor sobre el excedente; sin embargo, el texto muestra '0.001 %' en todos los renglones, por lo que la estructura combina cuota fija en pesos con un factor porcentual uniforme. Se normalizó el 
- **preview tabla** (primeras 3 filas):
```json
[
  {
    "n_rango": 1,
    "inferior": 0.0,
    "superior": 5000.0,
    "columnas": [
      {
        "nombre": "general",
        "valor": 90.0,
        "tipo": "cuota_fija",
        "unidad": "pesos"
      }
    ]
  },
  {
    "n_rango": 2,
    "inferior": 5000.0,
    "superior": 7500.0,
    "columnas": [
      {
        "nombre": "general",
        "valor": 120.0,
        "tipo": "cuota_fija",
        "unidad": "pesos"
      }
    ]
  },
  {
    "n_rango": 3,
    "inferior": 7500.0,
    "superior": 10500.0,
    "columnas": [
      {
        "nombre": "general",
        "valor": 150.0,
        "tipo": "cuota_fija",
        "unidad": "pesos"
      }
    ]
  }
]
```
