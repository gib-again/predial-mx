"""Re-extrae con v2 una muestra dirigida (18 casos cross-estado).

Output:
  - predial-mx-v2/{estado}/*.json
  - imprime tabla resumen.
"""
from __future__ import annotations

from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

from src.extraction.llm_extract_v2 import extraer_municipio  # noqa: E402

CASES: list[tuple[str, str, int, str]] = [
    # (estado, cvegeo, anio, slug)  -- slug usado solo para display
    ("yucatan", "31048", 2010, "maxcanu"),
    ("yucatan", "31055", 2010, "opichen"),
    ("yucatan", "31027", 2012, "dzidzantun"),
    ("yucatan", "31074", 2012, "tahmek"),
    ("yucatan", "31001", 2010, "abala"),
    ("yucatan", "31006", 2010, "buctzotz"),
    ("yucatan", "31003", 2010, "akil"),
    ("yucatan", "31007", 2010, "cacalchen"),
    ("coahuila", "05025", 2012, "piedras_negras"),
    ("coahuila", "05025", 2013, "piedras_negras"),
    ("coahuila", "05025", 2014, "piedras_negras"),
    ("coahuila", "05025", 2015, "piedras_negras"),
    ("tamaulipas", "28038", 2024, "tampico"),
    ("tamaulipas", "28032", 2024, "reynosa"),
    ("jalisco", "14039", 2024, "guadalajara"),
    ("jalisco", "14120", 2024, "zapopan"),
    ("guanajuato", "11020", 2025, "leon"),
    ("guanajuato", "11017", 2025, "irapuato"),
]


def main() -> int:
    grouped: dict[tuple[str, str], list[int]] = defaultdict(list)
    for est, cvegeo, anio, _ in CASES:
        grouped[(est, cvegeo)].append(anio)

    rows = []
    for (estado, cvegeo), anios in grouped.items():
        print(f"\n[sample] {estado} {cvegeo} anios={anios}")
        results = extraer_municipio(estado, cvegeo, sorted(anios))
        for r in results:
            tipo = r.output.predial.tipo_esquema if r.output else ""
            rows.append({
                "estado": estado,
                "anio": r.anio,
                "slug": r.slug,
                "tipo_v2": tipo,
                "intentos": r.intentos,
                "revision": r.requiere_revision,
                "razon": (r.razon or "")[:80],
                "tok_in": r.tokens_in,
                "tok_out": r.tokens_out,
            })

    print("\n" + "=" * 100)
    print(f"{'estado':<12} {'anio':>5} {'slug':<28} {'tipo_v2':<26} {'int':>3} {'rev':>4} {'tok_in':>7}")
    print("-" * 100)
    for r in sorted(rows, key=lambda x: (x["estado"], x["anio"], x["slug"])):
        rev = "SI" if r["revision"] else ""
        print(f"{r['estado']:<12} {r['anio']:>5} {r['slug']:<28} {r['tipo_v2']:<26} {r['intentos']:>3} {rev:>4} {r['tok_in']:>7}")
        if r["razon"]:
            print(f"             razon: {r['razon']}")
    print("=" * 100)
    print(f"total: {len(rows)} casos | tok_in={sum(r['tok_in'] for r in rows)} tok_out={sum(r['tok_out'] for r in rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
