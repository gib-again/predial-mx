"""
Configuración específica del Estado de México.

125 municipios. Tarifa estatal uniforme del Código Financiero del Estado de México
y Municipios (Art. 109). Aplica igual a todos los municipios.

Periodos de tarifa:
  - Ejercicio 2010: tabla original (G.G. 26-dic-2007).
  - Ejercicios 2011-2025: tabla con rangos 1-3 reformados (G.G. 21-dic-2010).
  - Ejercicio 2026: tabla completamente nueva (nice-to-have, fuera del periodo).

Baldíos urbanos >200 m²: tasa adicional 15% (G.G. 28-nov-2016, aplica desde 2017).
Cuota fija en PESOS nominales (no UMA ni SM) — no requiere factor de conversión.
"""

from __future__ import annotations

ESTADO_SLUG = "edomex"
PREFIJO = "MEX"
ESTADO_NOMBRE = "México"
CVE_ENT = "15"
NEEDS_OCR = False  # Tarifa hardcoded del Código Financiero estatal

YEAR_MIN = 2010
YEAR_MAX = 2025

# Ejercicio 2010 usa la tabla publicada G.G. 26-dic-2007 (tabla "2009").
# Ejercicios 2011+ usan la tabla con rangos 1-3 reformados G.G. 21-dic-2010.
YEAR_TABLA_REFORMA = 2011

# Año a partir del cual aplica la tasa adicional del 15% en baldíos >200m².
YEAR_BALDIO_15PCT = 2017  # Reforma G.G. 28-nov-2016, aplica desde ejercicio 2017

# ── 125 municipios del Estado de México ─────────────────────
# Fuente: INEGI catálogo AGEEML (CVE_ENT=15).
# Generamos la lista con claves 001-125.
MUNICIPIOS: list[tuple[str, str, str]] = [
    ("001", "Acambay de Ruíz Castañeda", "acambay"),
    ("002", "Acolman", "acolman"),
    ("003", "Aculco", "aculco"),
    ("004", "Almoloya de Alquisiras", "almoloya_de_alquisiras"),
    ("005", "Almoloya de Juárez", "almoloya_de_juarez"),
    ("006", "Almoloya del Río", "almoloya_del_rio"),
    ("007", "Amanalco", "amanalco"),
    ("008", "Amatepec", "amatepec"),
    ("009", "Amecameca", "amecameca"),
    ("010", "Apaxco", "apaxco"),
    ("011", "Atenco", "atenco"),
    ("012", "Atizapán", "atizapan"),
    ("013", "Atizapán de Zaragoza", "atizapan_de_zaragoza"),
    ("014", "Atlacomulco", "atlacomulco"),
    ("015", "Atlautla", "atlautla"),
    ("016", "Axapusco", "axapusco"),
    ("017", "Ayapango", "ayapango"),
    ("018", "Calimaya", "calimaya"),
    ("019", "Capulhuac", "capulhuac"),
    ("020", "Coacalco de Berriozábal", "coacalco"),
    ("021", "Coatepec Harinas", "coatepec_harinas"),
    ("022", "Cocotitlán", "cocotitlan"),
    ("023", "Coyotepec", "coyotepec"),
    ("024", "Cuautitlán", "cuautitlan"),
    ("025", "Chalco", "chalco"),
    ("026", "Chapa de Mota", "chapa_de_mota"),
    ("027", "Chapultepec", "chapultepec"),
    ("028", "Chiautla", "chiautla"),
    ("029", "Chicoloapan", "chicoloapan"),
    ("030", "Chiconcuac", "chiconcuac"),
    ("031", "Chimalhuacán", "chimalhuacan"),
    ("032", "Donato Guerra", "donato_guerra"),
    ("033", "Ecatepec de Morelos", "ecatepec"),
    ("034", "Ecatzingo", "ecatzingo"),
    ("035", "Huehuetoca", "huehuetoca"),
    ("036", "Hueypoxtla", "hueypoxtla"),
    ("037", "Huixquilucan", "huixquilucan"),
    ("038", "Isidro Fabela", "isidro_fabela"),
    ("039", "Ixtapaluca", "ixtapaluca"),
    ("040", "Ixtapan de la Sal", "ixtapan_de_la_sal"),
    ("041", "Ixtapan del Oro", "ixtapan_del_oro"),
    ("042", "Ixtlahuaca", "ixtlahuaca"),
    ("043", "Xalatlaco", "xalatlaco"),
    ("044", "Jaltenco", "jaltenco"),
    ("045", "Jilotepec", "jilotepec"),
    ("046", "Jilotzingo", "jilotzingo"),
    ("047", "Jiquipilco", "jiquipilco"),
    ("048", "Jocotitlán", "jocotitlan"),
    ("049", "Joquicingo", "joquicingo"),
    ("050", "Juchitepec", "juchitepec"),
    ("051", "Lerma", "lerma"),
    ("052", "Malinalco", "malinalco"),
    ("053", "Melchor Ocampo", "melchor_ocampo"),
    ("054", "Metepec", "metepec"),
    ("055", "Mexicaltzingo", "mexicaltzingo"),
    ("056", "Morelos", "morelos"),
    ("057", "Naucalpan de Juárez", "naucalpan"),
    ("058", "Nezahualcóyotl", "nezahualcoyotl"),
    ("059", "Nextlalpan", "nextlalpan"),
    ("060", "Nicolás Romero", "nicolas_romero"),
    ("061", "Nopaltepec", "nopaltepec"),
    ("062", "Ocoyoacac", "ocoyoacac"),
    ("063", "Ocuilan", "ocuilan"),
    ("064", "El Oro", "el_oro"),
    ("065", "Otumba", "otumba"),
    ("066", "Otzoloapan", "otzoloapan"),
    ("067", "Otzolotepec", "otzolotepec"),
    ("068", "Ozumba", "ozumba"),
    ("069", "Papalotla", "papalotla"),
    ("070", "La Paz", "la_paz"),
    ("071", "Polotitlán", "polotitlan"),
    ("072", "Rayón", "rayon"),
    ("073", "San Antonio la Isla", "san_antonio_la_isla"),
    ("074", "San Felipe del Progreso", "san_felipe_del_progreso"),
    ("075", "San Martín de las Pirámides", "san_martin_de_las_piramides"),
    ("076", "San Mateo Atenco", "san_mateo_atenco"),
    ("077", "San Simón de Guerrero", "san_simon_de_guerrero"),
    ("078", "Santo Tomás", "santo_tomas"),
    ("079", "Soyaniquilpan de Juárez", "soyaniquilpan"),
    ("080", "Sultepec", "sultepec"),
    ("081", "Tecámac", "tecamac"),
    ("082", "Tejupilco", "tejupilco"),
    ("083", "Temamatla", "temamatla"),
    ("084", "Temascalapa", "temascalapa"),
    ("085", "Temascalcingo", "temascalcingo"),
    ("086", "Temascaltepec", "temascaltepec"),
    ("087", "Temoaya", "temoaya"),
    ("088", "Tenancingo", "tenancingo"),
    ("089", "Tenango del Aire", "tenango_del_aire"),
    ("090", "Tenango del Valle", "tenango_del_valle"),
    ("091", "Teoloyucan", "teoloyucan"),
    ("092", "Teotihuacán", "teotihuacan"),
    ("093", "Tepetlaoxtoc", "tepetlaoxtoc"),
    ("094", "Tepetlixpa", "tepetlixpa"),
    ("095", "Tepotzotlán", "tepotzotlan"),
    ("096", "Tequixquiac", "tequixquiac"),
    ("097", "Texcaltitlán", "texcaltitlan"),
    ("098", "Texcalyacac", "texcalyacac"),
    ("099", "Texcoco", "texcoco"),
    ("100", "Tezoyuca", "tezoyuca"),
    ("101", "Tianguistenco", "tianguistenco"),
    ("102", "Timilpan", "timilpan"),
    ("103", "Tlalmanalco", "tlalmanalco"),
    ("104", "Tlalnepantla de Baz", "tlalnepantla"),
    ("105", "Tlatlaya", "tlatlaya"),
    ("106", "Toluca", "toluca"),
    ("107", "Tonatico", "tonatico"),
    ("108", "Tultepec", "tultepec"),
    ("109", "Tultitlán", "tultitlan"),
    ("110", "Valle de Bravo", "valle_de_bravo"),
    ("111", "Villa de Allende", "villa_de_allende"),
    ("112", "Villa del Carbón", "villa_del_carbon"),
    ("113", "Villa Guerrero", "villa_guerrero"),
    ("114", "Villa Victoria", "villa_victoria"),
    ("115", "Xonacatlán", "xonacatlan"),
    ("116", "Zacazonapan", "zacazonapan"),
    ("117", "Zacualpan", "zacualpan"),
    ("118", "Zinacantepec", "zinacantepec"),
    ("119", "Zumpahuacán", "zumpahuacan"),
    ("120", "Zumpango", "zumpango"),
    ("121", "Cuautitlán Izcalli", "cuautitlan_izcalli"),
    ("122", "Valle de Chalco Solidaridad", "valle_de_chalco"),
    ("123", "Luvianos", "luvianos"),
    ("124", "San José del Rincón", "san_jose_del_rincon"),
    ("125", "Tonanitla", "tonanitla"),
]
