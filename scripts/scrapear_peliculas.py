#!/usr/bin/env python3
"""scrapear-peliculas: completa la info faltante título a título.

Uso:
    python scripts/scrapear_peliculas.py --proveedor ruta.modulo:Clase [--tt tt0111161]
        [--solo-faltantes] [--limite 20] [--delay 1.5] [--dry-run] [--db ruta/catalogo.db]

El proveedor es una clase con atributo `nombre` y método `fetch(tt)`.
Límites por defecto: 1.5 s entre peticiones, fallos por título no abortan
el lote. Sin login ni cookies: solo datos públicos.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import DEFAULT_DB_PATH, init_db
from src.huecos import listar_huecos
from src.scraper import enriquecer


def cargar_proveedor(ref: str):
    modulo, _, clase = ref.partition(":")
    mod = importlib.import_module(modulo)
    return getattr(mod, clase)() if clase else mod


def main() -> int:
    ap = argparse.ArgumentParser(description="Completa huecos web con un proveedor.")
    ap.add_argument("--proveedor", required=True, help="modulo:Clase del proveedor")
    ap.add_argument("--tt", default=None, help="Un solo título (tt…)")
    ap.add_argument("--solo-faltantes", action="store_true", default=True)
    ap.add_argument("--limite", type=int, default=20)
    ap.add_argument("--delay", type=float, default=1.5, help="Segundos entre peticiones")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = ap.parse_args()

    # Aplica el esquema vigente (idempotente): así una base de una versión
    # anterior gana las tablas nuevas sin necesitar un import previo.
    init_db(args.db)

    proveedor = cargar_proveedor(args.proveedor)
    tts = [args.tt] if args.tt else sorted({h["tt"] for h in listar_huecos(args.db)})
    tts = tts[:args.limite]

    resultados, fallos = [], 0
    for i, tt in enumerate(tts):
        if i and args.delay > 0:
            time.sleep(args.delay)
        try:
            r = enriquecer(args.db, tt, proveedor,
                           solo_faltantes=args.solo_faltantes, dry_run=args.dry_run)
            resultados.append(r)
        except Exception as e:  # un título roto no aborta el lote
            fallos += 1
            resultados.append({"tt": tt, "error": str(e)[:200]})
    print(json.dumps({"resultados": resultados, "fallos": fallos},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
