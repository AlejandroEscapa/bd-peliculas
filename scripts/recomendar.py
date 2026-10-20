#!/usr/bin/env python3
"""recomendar: ordena tus pendientes por lo que encaja contigo y dice por qué.

Uso:
    python scripts/recomendar.py [--db ruta/catalogo.db] [--limite 10] [--json]

No hay azar, no hay red y no hay modelo: el motor (`src/motor.py`) solo usa
tus notas y los hechos de los títulos. Cada título sale con su motivo, que es
justo lo que lo hace útil: un "te recomiendo esto" sin explicación no sirve
para decidir.

    python scripts/recomendar.py
    python scripts/recomendar.py --limite 5 --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import DEFAULT_DB_PATH, get_connection
from src.motor import perfil, recomendar


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Ordena tus pendientes por encaje y explica el porqué.")
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Ruta a la base SQLite")
    ap.add_argument("--limite", type=int, default=10, help="Cuántos enseñar")
    ap.add_argument("--perfil", action="store_true", help="Enseñar el perfil de gusto")
    ap.add_argument("--json", action="store_true", help="Salida en JSON")
    args = ap.parse_args()

    conn = get_connection(args.db)
    try:
        if args.perfil:
            p = perfil(conn)
            print(f"Tu media global: {p['global']} (sobre {p['n_valoradas']} valoradas)\n")
            for faceta in ("genero", "director", "actor", "decada", "pais"):
                valores = p["facetas"].get(faceta, {})
                if not valores:
                    continue
                print(f"{faceta}:")
                for valor, d in sorted(valores.items(), key=lambda kv: -kv[1]["lift"]):
                    print(f"  {valor:28} n={d['n']:2}  media={d['media']:4.1f}  "
                          f"lift={d['lift']:+.2f}  vs IMDb={d['diff_imdb']:+.2f}")
            print()

        resultados = recomendar(conn, limite=args.limite)
    finally:
        conn.close()

    if args.json:
        print(json.dumps(resultados, indent=2, ensure_ascii=False))
        return 0

    if not resultados:
        print("No hay pendientes que recomendar (o no tienes nada valorado todavía).")
        return 0

    for i, r in enumerate(resultados, 1):
        print(f"{i:2}. {r['titulo']} ({r['year'] or '?'})"
              f"  IMDb {r['imdb'] if r['imdb'] is not None else '-'}"
              f"  encaje {r['encaje']}%")
        for motivo in r["razones"]:
            print(f"      · {motivo}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
