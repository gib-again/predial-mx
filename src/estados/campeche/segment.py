"""
Segmentacion predial para Campeche (hardcoded versionado).

Por cada (municipio, anio) escribe un focus con el bloque de tarifa del Art. 26
de la VERSION vigente ese anio (extraido de la Ley de Hacienda de los Municipios)
y una fila canonica en segment.csv.
"""

from __future__ import annotations

from pathlib import Path

from src.core.catalog import build_cvegeo, cvegeo_to_nombre
from src.core.segment_schema import STATUS_OK, SegmentRow, write_segment_csv
from src.estados.campeche import config
from src.estados.campeche.leyes import predial_focus


def _focus_path(anio: int, slug: str) -> Path:
    return (Path("data") / config.ESTADO_SLUG / "focus_predial" / str(anio)
            / f"{config.PREFIJO}_PREDIAL_{anio}_{slug}.txt")


def run_segment(adapter, year: str | None = None) -> Path:
    meta_dir = Path("data") / config.ESTADO_SLUG / "meta"
    meta_dir.mkdir(parents=True, exist_ok=True)
    segment_csv = meta_dir / "segment.csv"

    print("=== Campeche: segmentacion predial (Ley de Hacienda de los Municipios) ===")

    cache: dict[tuple[str, str], str | None] = {}
    rows: list[SegmentRow] = []
    n_ok = n_missing = 0

    for cve_mun, _nombre, slug, _tabla in config.MUNICIPIOS:
        cvegeo = build_cvegeo(config.CVE_ENT, cve_mun)
        for anio in range(config.YEAR_MIN, config.YEAR_MAX + 1):
            if year and str(anio) != str(year):
                continue
            ver = config.version_para_anio(slug, anio)
            if ver is None:
                continue  # muni no existe ese anio (nuevos antes de su creacion)
            version_id, revisar = ver
            key = (slug, version_id)
            if key not in cache:
                cache[key] = predial_focus(slug, version_id)
            texto = cache[key]

            focus = _focus_path(anio, slug)
            focus.parent.mkdir(parents=True, exist_ok=True)
            if texto:
                header = (
                    f"# Estado: {config.ESTADO_NOMBRE}\n"
                    f"# Municipio: {cvegeo_to_nombre(cvegeo)} ({slug})\n"
                    f"# Ejercicio: {anio}\n"
                    f"# Fuente: Ley de Hacienda de los Municipios, Art. 26, version '{version_id}'"
                    f"{' [ENTRADA DE MUNICIPIO NUEVO - REVISAR HITL]' if revisar else ''}\n\n"
                )
                focus.write_text(header + texto, encoding="utf-8")
                n_ok += 1
            else:
                n_missing += 1
            rows.append(SegmentRow(
                cvegeo=cvegeo,
                estado_slug=config.ESTADO_SLUG,
                municipio_slug=slug,
                municipio_raw=cvegeo_to_nombre(cvegeo),
                anio=anio,
                status=STATUS_OK,
                source_pdf=f"LHaciendaMunicipios:{version_id}",
                predial_found=bool(texto),
                predial_method=f"ley_hacienda_art26:{version_id}" + ("?revisar" if revisar else ""),
                txt_file=focus.name if texto else "",
                txt_chars=len(texto) if texto else 0,
                confidence=1.0 if texto else 0.0,
            ))

    write_segment_csv(rows, segment_csv)
    print(f"  Focus escritos: {n_ok} | sin texto: {n_missing}")
    print(f"  segment.csv: {segment_csv} ({len(rows)} filas)")
    return segment_csv
