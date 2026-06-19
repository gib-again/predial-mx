"""Test extraction v3: 5 munis × 4 years per Grupo A state (excluding Oaxaca).

Runs extract → reports summary. HITL detectors run separately after.
"""
from __future__ import annotations

import csv
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

STATE_CVE_ENT = {
    "coahuila": "05", "guanajuato": "11", "jalisco": "14",
    "queretaro": "22", "sanluispotosi": "24", "sonora": "26",
    "tamaulipas": "28", "yucatan": "31",
}

TEST_PLAN: dict[str, tuple[list[str], list[int]]] = {
    "coahuila":      (["escobedo","acuna","monclova","lamadrid","juarez"], [2020,2021,2022,2023]),
    "guanajuato":    (["abasolo","manuel_doblado","salamanca","valle_de_santiago","victoria"], [2022,2023,2024,2025]),
    "jalisco":       (["casimiro_castillo","tequila","ayotlan","tapalpa","villa_hidalgo"], [2020,2021,2022,2023]),
    "queretaro":     (["cadereyta_de_montes","san_joaquin","amealco_de_bonfil","tequisquiapan","arroyo_seco"], [2020,2021,2022,2023]),
    "sanluispotosi": (["el_naranjo","guadalcazar","tancanhuitz","villa_de_arista","alaquines"], [2022,2023,2024,2025]),
    "sonora":        (["cucurpe","benito_juarez","bacum","carbo","huasabas"], [2020,2021,2022,2023]),
    "tamaulipas":    (["camargo","jimenez","padilla","abasolo","mainero"], [2020,2021,2022,2023]),
    "yucatan":       (["sotuta","acanceh","mococha","dzan","ixil"], [2020,2021,2022,2023]),
}


def _is_empty_json(p: Path) -> bool:
    """True if missing or JSON has predial=null (failed extraction)."""
    if not p or not p.exists():
        return True
    try:
        import json
        d = json.loads(p.read_text(encoding="utf-8"))
        return d.get("predial") is None
    except Exception:
        return True


def _load_catalog() -> dict[tuple[str, str], str]:
    """(cve_ent, slug) -> cvegeo"""
    from src.core.text_utils import slugify

    cat_path = ROOT / "catalogs" / "municipios_inegi.csv"
    out = {}
    with cat_path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            out[(row["CVE_ENT"], slugify(row["NOM_MUN"]))] = row["CVEGEO"]
    return out


def main() -> None:
    from src.extraction.llm_extract_v3 import extraer_municipio

    catalog = _load_catalog()

    t0 = time.time()
    total = 0
    ok = 0
    revision = 0
    errors: list[str] = []

    estados = sys.argv[1:] if len(sys.argv) > 1 else list(TEST_PLAN.keys())

    for estado in estados:
        if estado not in TEST_PLAN:
            print(f"[SKIP] {estado} not in test plan")
            continue
        munis, years = TEST_PLAN[estado]
        cve_ent = STATE_CVE_ENT[estado]
        print(f"\n{'='*60}")
        print(f"  ESTADO: {estado.upper()}")
        print(f"  Munis: {munis}")
        print(f"  Years: {years}")
        print(f"{'='*60}\n")

        for slug in munis:
            cvegeo = catalog.get((cve_ent, slug))
            if not cvegeo:
                print(f"  [ERROR] {estado}/{slug}: CVEGEO not found")
                errors.append(f"{estado}/{slug}: CVEGEO not found")
                total += len(years)
                continue
            from src.core.corpus import resolve_json
            # Skip-check contra la ubicación canónica nueva (data/{estado}/
            # json_predial/{anio}/), incluido overlay HITL.  Antes apuntaba al
            # predial-mx-v3/ retirado → re-extraía todo y gastaba API.
            pending_years = [
                y for y in years
                if _is_empty_json(resolve_json(estado, y, slug))
            ]
            if not pending_years:
                print(f"  [SKIP] {estado}/{slug}: all years exist")
                total += len(years)
                ok += len(years)
                continue
            try:
                results = extraer_municipio(
                    estado=estado,
                    cvegeo=cvegeo,
                    anios=pending_years,
                    slug_override=slug,
                )
                for r in results:
                    total += 1
                    if r.output:
                        ok += 1
                    if r.requiere_revision:
                        revision += 1
                    if r.razon and "ERROR" in r.razon.upper():
                        errors.append(f"{estado}/{slug}/{r.anio}: {r.razon}")
            except Exception as e:
                print(f"  [EXCEPTION] {estado}/{slug}: {e}")
                errors.append(f"{estado}/{slug}: {e}")
                total += len(years)

    elapsed = time.time() - t0
    print(f"\n{'='*60}")
    print("  TEST EXTRACTION SUMMARY")
    print(f"{'='*60}")
    print(f"  Total:    {total}")
    print(f"  OK:       {ok}")
    print(f"  Revision: {revision}")
    print(f"  Errors:   {len(errors)}")
    print(f"  Time:     {elapsed:.1f}s")
    if errors:
        print("\n  Error details:")
        for e in errors:
            print(f"    - {e}")
    print()


if __name__ == "__main__":
    main()
