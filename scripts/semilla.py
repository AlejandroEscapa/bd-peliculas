#!/usr/bin/env python3
"""semilla: base de trabajo reproducible para probar la interfaz sin la real.

La base de verdad (`data/catalogo.db`) no se versiona: es personal y son
justo los datos que hacen interesante el panel. Este script construye una base
equivalente a partir del `catalogo-data` del snapshot publicado
(`preview/dashboard.html`), que sí está en el repo.

    python scripts/semilla.py
    python scripts/generar_vista.py --db data/semilla.db --salida preview/semilla.html

Por defecto las notas son **sintéticas**: deterministas, correlacionadas con
el IMDb y con una preferencia por géneros, para que el motor tenga señal y
todas las secciones se pueblen (Joyas, Decepciones, Actores, década, "Para
ti"). Con `--notas reales` reproduces el panel publicado tal cual, para
comparar cambios antes/después.

Las **colecciones (sagas) son reales** y se detectan por título: Harry Potter,
Dune, El Señor de los Anillos, Spider-Man, Batman, Alien, Sinister, Narcos,
Jujutsu Kaisen, Depredador, Guardianes, El hoyo. Así el bloque "Colección" de
la ficha tiene algo que enseñar sin depender de que el scraper haya corrido.

Nada de esto toca tu base real: escribe siempre en `data/semilla.db`.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import init_db

# Preferencia por género de la "persona" sintética. Con esto el motor
# encuentra una subida real: Terror sale flojo, Animación sube.
AFINIDAD_GENERO = {
    "Animación": 1.3, "Historia": 1.0, "Documental": 0.7, "Crimen": 0.5,
    "Aventura": 0.3, "Acción": 0.2, "Ciencia ficción": 0.2, "Bélico": 0.2,
    "Fantasía": 0.1, "Familiar": 0.1, "Música": 0.1, "Deporte": -0.3,
    "Romance": -0.7, "Misterio": -0.6, "Suspense": -0.5, "Comedia": -1.6,
    "Terror": -1.5,
}

# Franquicias reales del catálogo: nombre de la colección -> fragmentos del
# título que la identifican.
FRANQUICIAS = {
    "Colección Harry Potter": ["harry potter"],
    "Colección Dune": ["dune"],
    "El Señor de los Anillos": ["el señor de los anillos"],
    "Spider-Man": ["spider-man"],
    "Batman": ["batman begins", "the batman", "el caballero oscuro"],
    "Alien": ["alien"],
    "Guardianes de la Galaxia": ["guardianes de la galaxia"],
    "Sinister": ["sinister"],
    "Narcos": ["narcos"],
    "Jujutsu Kaisen": ["jujutsu kaisen"],
    "Depredador": ["depredador", "predator"],
    "El hoyo": ["el hoyo"],
}

# Probabilidad de que un título esté valorado en la semilla.
PROB_VALORADO = 0.72


def _normalizar(texto: str) -> str:
    plano = unicodedata.normalize("NFKD", (texto or "").lower())
    return "".join(c for c in plano if not unicodedata.combining(c))


def _aleatorio(tt: str, sal: str = "") -> float:
    """Número estable en [0,1) a partir del tt: la misma semilla, siempre igual."""
    digest = hashlib.sha256(f"{tt}|{sal}".encode("utf-8")).hexdigest()
    return int(digest[:8], 16) / 0xFFFFFFFF


def _nota_sintetica(tt: str, imdb: float | None, generos: list[str]) -> int | None:
    if _aleatorio(tt, "valorado") >= PROB_VALORADO:
        return None
    base = imdb if imdb is not None else 6.8
    afinidad = max((AFINIDAD_GENERO.get(g, 0.0) for g in generos), default=0.0)
    ruido = (_aleatorio(tt, "nota") - 0.5) * 2.6
    nota = base + afinidad + ruido
    return max(1, min(10, int(round(nota))))


def _colecciones_de(titulo: str) -> tuple[int, str] | None:
    normal = _normalizar(titulo)
    for nombre, fragmentos in FRANQUICIAS.items():
        if any(_normalizar(f) in normal for f in fragmentos):
            # crc32 y no hash(): el hash de Python cambia entre procesos y la
            # semilla tiene que ser reproducible.
            return (zlib.crc32(nombre.encode("utf-8")) % 900000 + 1000, nombre)
    return None


def _leer_catalogo(snapshot: Path) -> dict:
    html = snapshot.read_text(encoding="utf-8")
    m = re.search(r'<script type="application/json" id="catalogo-data">(.*?)</script>',
                  html, re.S)
    if not m:
        raise SystemExit(
            f"error: {snapshot} no tiene el bloque catalogo-data.\n"
            "      Genera el panel primero: python scripts/generar_vista.py")
    return json.loads(m.group(1))


def construir_semilla(snapshot: Path, destino: Path, notas_reales: bool = False,
                      forzar: bool = False) -> dict:
    """Crea la base semilla y devuelve un resumen.

    Por seguridad NO rehace una base que ya existe: sin `forzar=True` se
    niega, para no borrar el catálogo real por un `--db` mal escrito.
    """
    catalogo = _leer_catalogo(snapshot)

    if destino.exists():
        if not forzar:
            raise SystemExit(
                f"error: {destino} ya existe. No se toca.\n"
                "       Usa --forzar para rehacerla desde cero, o escribe en otra ruta.")
        destino.unlink()
    init_db(destino)

    import sqlite3
    conn = sqlite3.connect(destino)
    try:
        valoradas = 0
        con_coleccion = 0
        for tt, f in catalogo.items():
            nota = f.get("nota") if notas_reales else _nota_sintetica(
                tt, f.get("imdb"), f.get("generos") or [])
            if nota is not None:
                valoradas += 1
            conn.execute(
                "INSERT OR REPLACE INTO titles (tt, title_es, original_title, url, "
                "title_type, year, imdb_rating, synopsis, poster_url) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (tt, f.get("titulo"), f.get("original"), f.get("url"), f.get("tipo"),
                 f.get("year"), f.get("imdb"), f.get("sinopsis") or None,
                 f.get("poster") or None))
            conn.execute(
                "INSERT OR REPLACE INTO user_state (tt, my_rating, watch_status) "
                "VALUES (?, ?, ?)",
                (tt, nota, "rated" if nota is not None else "watchlist"))
            for g in f.get("generos") or []:
                conn.execute("INSERT OR IGNORE INTO genres (name) VALUES (?)", (g,))
                conn.execute(
                    "INSERT OR IGNORE INTO title_genres (tt, genre) VALUES (?, ?)", (tt, g))
            for d in f.get("directores") or []:
                conn.execute("INSERT OR IGNORE INTO people (name) VALUES (?)", (d,))
                pid = conn.execute("SELECT id FROM people WHERE name = ?", (d,)).fetchone()[0]
                conn.execute(
                    "INSERT OR IGNORE INTO title_credits (tt, person_id, role) "
                    "VALUES (?, ?, 'director')", (tt, pid))
            for i, a in enumerate(f.get("reparto") or [], start=1):
                conn.execute("INSERT OR IGNORE INTO people (name) VALUES (?)", (a["nombre"],))
                pid = conn.execute(
                    "SELECT id FROM people WHERE name = ?", (a["nombre"],)).fetchone()[0]
                conn.execute(
                    "INSERT OR IGNORE INTO title_cast "
                    "(tt, person_id, character_name, cast_order) VALUES (?, ?, ?, ?)",
                    (tt, pid, a.get("personaje") or "", i))
            for p in f.get("paises") or []:
                conn.execute(
                    "INSERT OR IGNORE INTO title_countries (tt, country_code) VALUES (?, ?)",
                    (tt, p))
            col = _colecciones_de(f.get("titulo") or "")
            if col:
                conn.execute(
                    "INSERT OR REPLACE INTO title_collections "
                    "(tt, collection_id, collection_name, source) VALUES (?, ?, ?, 'semilla')",
                    (tt, col[0], col[1]))
                con_coleccion += 1
            if (f.get("tipo") or "").lower().startswith(("serie", "miniserie")):
                temporadas = 1 + int(_aleatorio(tt, "temp") * 6)
                conn.execute(
                    "INSERT OR REPLACE INTO series_info "
                    "(tt, seasons, episodes, status, source) VALUES (?, ?, ?, 'Finished', 'semilla')",
                    (tt, temporadas, temporadas * (6 + int(_aleatorio(tt, "ep") * 6))))
        conn.commit()
    finally:
        conn.close()

    return {
        "titulos": len(catalogo),
        "valoradas": valoradas,
        "pendientes": len(catalogo) - valoradas,
        "con_coleccion": con_coleccion,
        "notas": "reales" if notas_reales else "sinteticas",
        "db": str(destino),
    }


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Construye una base semilla para probar la interfaz.")
    ap.add_argument("--desde", default=str(ROOT / "preview" / "dashboard.html"),
                    help="Snapshot del que sacar los hechos del catálogo")
    ap.add_argument("--db", default=str(ROOT / "data" / "semilla.db"),
                    help="Dónde escribir la base semilla")
    ap.add_argument("--notas", choices=("sinteticas", "reales"), default="sinteticas",
                    help="Sintéticas (por defecto) o las reales del snapshot")
    ap.add_argument("--forzar", action="store_true",
                    help="Rehacer la base aunque ya exista (puede borrar la que haya)")
    args = ap.parse_args()

    origen = Path(args.desde)
    if not origen.exists():
        print(f"error: no existe {origen}", file=sys.stderr)
        return 2

    resumen = construir_semilla(origen, Path(args.db),
                                notas_reales=args.notas == "reales",
                                forzar=args.forzar)
    print(json.dumps(resumen, indent=2, ensure_ascii=False))
    print("\nAhora:")
    print(f"  python scripts/generar_vista.py --db {args.db} --salida preview/semilla.html")
    print("  start preview/semilla.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
