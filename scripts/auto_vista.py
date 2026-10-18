#!/usr/bin/env python3
"""Auto-regenera preview/dashboard.html cuando data/catalogo.db cambia.

Uso:
    python scripts/auto_vista.py                      # vigila y regenera
    python scripts/auto_vista.py --una-vez             # solo regenera una vez
    python scripts/auto_vista.py --cada 2.0 --db data/catalogo.db --salida preview/dashboard.html

Solo stdlib. No toca claves ni red. Para parar: Ctrl+C.
Flujo recomendado:
    1) deja esto abierto en una terminal,
    2) en otra: python scripts/actualizar_peliculas.py tu.csv
    3) el panel se regenera solo al detectar el cambio.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from generar_vista import generar  # type: ignore
from src.db import DEFAULT_DB_PATH


def regenerar(db: Path, salida: Path) -> None:
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(generar(db), encoding="utf-8")
    print(f"panel OK: {salida} <- {db}", flush=True)


def main() -> int:
    ap = argparse.ArgumentParser(description="Vigila la BD y regenera el panel.")
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH))
    ap.add_argument("--salida", default=str(ROOT / "preview" / "dashboard.html"))
    ap.add_argument("--cada", type=float, default=2.0, help="Segundos entre chequeos")
    ap.add_argument("--una-vez", action="store_true", help="Regenera una vez y sale")
    args = ap.parse_args()

    db = Path(args.db)
    salida = Path(args.salida)
    regenerar(db, salida)
    if args.una_vez:
        return 0

    print(f"vigilando {db} cada {args.cada}s… Ctrl+C para parar", flush=True)
    ultimo = db.stat().st_mtime if db.exists() else 0.0
    try:
        while True:
            time.sleep(max(0.5, args.cada))
            mt = db.stat().st_mtime if db.exists() else 0.0
            if mt != ultimo:
                ultimo = mt
                try:
                    regenerar(db, salida)
                except Exception as e:  # no tumbar el watcher por un regenerado
                    print(f"error regenerando: {e}", flush=True)
    except KeyboardInterrupt:
        print("\nwatcher parado", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
