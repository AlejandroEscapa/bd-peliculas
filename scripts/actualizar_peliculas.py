#!/usr/bin/env python3
"""actualizar-peliculas: adjunta un export CSV de IMDb sin destruir nada.

Uso:
    python scripts/actualizar_peliculas.py ruta/al/export.csv [--db ruta/catalogo.db]

El CSV es entrada delta: inserta títulos nuevos, actualiza solo campos
propios del CSV y registra cada diferencia en sync_diffs. El
enriquecimiento web/manual queda intacto.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import DEFAULT_DB_PATH
from src.sync import import_csv


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingiere un CSV de IMDb sin destruir datos.")
    ap.add_argument("csv", help="Ruta al CSV exportado de IMDb")
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Ruta a la base SQLite")
    args = ap.parse_args()

    if not Path(args.csv).exists():
        print(f"error: no existe el CSV: {args.csv}", file=sys.stderr)
        return 2
    resumen = import_csv(args.csv, args.db)
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    print(f"sync #{resumen['run_id']}: {resumen['nuevos']} nuevos, "
          f"{resumen['actualizados']} actualizados, {resumen['cuarentena']} en cuarentena, "
          f"{resumen['diffs']} diferencias registradas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
