#!/usr/bin/env python3
"""derivar-relaciones: deduce relaciones de saga a partir de las colecciones.

Uso:
    python scripts/derivar_relaciones.py [--db ruta/catalogo.db]

Las colecciones se rellenan al enriquecer (el proveedor lee
`belongs_to_collection` de la respuesta de detalle de TMDB, sin peticiones
extra). Este script solo las convierte en relaciones:

  - "universe": entre todos los pares de títulos de la misma colección.
  - "sequel": entre vecinos por año que comparten director o actor principal.

Es idempotente: repetirlo no duplica nada.

    python scripts/scrapear_peliculas.py --proveedor src.proveedores.combinado:ProveedorCombinado
    python scripts/derivar_relaciones.py
    python scripts/generar_vista.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import DEFAULT_DB_PATH, init_db
from src.relaciones import derivar_relaciones_coleccion


def main() -> int:
    ap = argparse.ArgumentParser(description="Deriva relaciones de saga desde las colecciones.")
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Ruta a la base SQLite")
    args = ap.parse_args()

    if not Path(args.db).exists():
        print(f"error: no existe la base {args.db}", file=sys.stderr)
        print("       (si querias la semilla: python scripts/semilla.py)", file=sys.stderr)
        return 2

    init_db(args.db)
    resumen = derivar_relaciones_coleccion(args.db)
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    print(f"{resumen['colecciones']} colecciones, "
          f"{resumen['relaciones_nuevas']} relaciones nuevas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
