#!/usr/bin/env python3
"""anadir-pelicula: da de alta una película a mano y la deja enriquecida.

Uso:
    python scripts/anadir_pelicula.py --tt tt35511966 --nota 9
        [--titulo "La bola negra"] [--tipo "Película"] [--anio 2026]
        [--fecha 2026-10-21] [--sin-enriquecer] [--dry-run] [--json]

Qué hace:
  1. Da de alta el título (tt de IMDb) con su nota en la capa personal.
     Si el título ya estaba, no lo duplica: solo ajusta la nota.
  2. Lo enriquece con el proveedor combinado (TMDB + OMDb): sinopsis, póster,
     reparto, créditos, colección... solo rellena huecos, nunca pisa nada.

No rompe nada: si más tarde llega el export de IMDb con ese tt, el
importador lo reconoce como título existente y solo actualiza sus columnas
(título, año, géneros) sin tocar el enriquecido ni la nota.

    python scripts/anadir_pelicula.py --tt tt35511966 --nota 9
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.altas import anadir_pelicula
from src.db import DEFAULT_DB_PATH


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Da de alta una película a mano (tt de IMDb) y la enriquece.")
    ap.add_argument("--tt", required=True, help="tt de IMDb, p. ej. tt35511966")
    ap.add_argument("--nota", type=int, default=None,
                    help="Tu nota (1-10). Sin nota, solo se añade a la lista.")
    ap.add_argument("--fecha", default=None,
                    help="Fecha en la que la valoraste (YYYY-MM-DD). Por defecto, hoy.")
    ap.add_argument("--titulo", default=None, help="Título en español")
    ap.add_argument("--tipo", default="Película",
                    help="Tipo tal y como lo pone el export de IMDb "
                         "(Película, Serie de TV, Miniserie de TV)")
    ap.add_argument("--anio", type=int, default=None, help="Año")
    ap.add_argument("--url", default=None, help="URL de IMDb (por defecto, se deduce)")
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH), help="Ruta a la base SQLite")
    ap.add_argument("--sin-enriquecer", action="store_true",
                    help="No buscar datos en la web (solo el alta)")
    ap.add_argument("--dry-run", action="store_true",
                    help="Enseña lo que haría sin escribir nada")
    ap.add_argument("--json", action="store_true", help="Salida en JSON")
    args = ap.parse_args()

    if not Path(args.db).exists():
        print(f"error: no existe la base {args.db}", file=sys.stderr)
        return 2

    try:
        resumen = anadir_pelicula(
            args.db, args.tt, nota=args.nota, fecha=args.fecha,
            titulo=args.titulo, tipo=args.tipo, anio=args.anio, url=args.url,
            enriquecer_datos=not args.sin_enriquecer, dry_run=args.dry_run)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(resumen, indent=2, ensure_ascii=False))
        return 0

    print(f"{'nuevo' if resumen['nuevo'] else 'ya estaba'}: {resumen['tt']}"
          + (f"  nota {resumen['nota']}" if resumen["nota"] is not None else ""))
    if resumen["cambios"]:
        print("cambios: " + ", ".join(resumen["cambios"]))
    if resumen["rellenados"]:
        print("enriquecido: " + ", ".join(resumen["rellenados"]))
    if resumen.get("aviso"):
        print("aviso: " + resumen["aviso"], file=sys.stderr)
    if args.dry_run:
        print("(dry-run: no se ha escrito nada)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
