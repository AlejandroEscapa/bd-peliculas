"""Altas puntuales: meter una película a mano sin esperar al export de IMDb.

Por qué existe: el export de IMDb llega por rachas, pero a veces quieres tener
algo en el catálogo ya (la acabas de ver en el cine y le pones nota). Este
módulo hace ese alta sin romper nada:

- La clave es el tt de IMDb. Si el título ya existe, **no se duplica**: solo
  se ajusta lo que se pide (la nota).
- **Nunca borra**: una nota que no se indica no borra la nota que ya había, y
  un campo vacío no pisa un dato que ya estaba.
- El CSV manda cuando llega: cuando el export de IMDb traiga ese tt, el
  importador lo reconoce como título existente y solo actualiza sus columnas
  (título, año, géneros, nota…) sin tocar el enriquecido web (sinopsis,
  póster, reparto, colección) ni la nota que pusiste a mano.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from .db import get_connection, init_db
from .scraper import enriquecer

TT_RE = re.compile(r"^tt\d{7,8}$")

# Columnas de `titles` que puede escribir un alta manual. Son las mismas
# que el CSV posee: si el export llega después, las sobrescribe con su
# valor (que es la fuente de verdad de esos campos).
CAMPOS_ALTA = ("title_es", "original_title", "url", "title_type", "year")


def _titulo_por_defecto(tt: str) -> str:
    return f"https://www.imdb.com/title/{tt}/"


def anadir_pelicula(
    db_path: str | Path,
    tt: str,
    nota: int | None = None,
    fecha: str | None = None,
    titulo: str | None = None,
    tipo: str | None = "Película",
    anio: int | None = None,
    url: str | None = None,
    original: str | None = None,
    proveedor=None,
    enriquecer_datos: bool = True,
    dry_run: bool = False,
) -> dict:
    """Da de alta un título (o ajusta la nota si ya estaba). Devuelve un resumen."""
    tt = (tt or "").strip()
    if not TT_RE.match(tt):
        raise ValueError(f"tt invalido: {tt!r} (se espera tt########)")

    if nota is not None and not (1 <= nota <= 10):
        raise ValueError(f"nota invalida: {nota} (1-10)")

    init_db(db_path)
    conn = get_connection(db_path)
    cambios: list[str] = []
    try:
        cur = conn.cursor()
        fila = cur.execute("SELECT * FROM titles WHERE tt = ?", (tt,)).fetchone()
        nuevo = fila is None

        valores = {
            "title_es": titulo,
            "original_title": original,
            "url": url,
            "title_type": tipo,
            "year": anio,
        }
        if nuevo:
            valores["url"] = url or _titulo_por_defecto(tt)
            cur.execute(
                """INSERT INTO titles
                   (tt, title_es, original_title, url, title_type, year)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tt, valores["title_es"], valores["original_title"],
                 valores["url"], valores["title_type"], valores["year"]))
            cambios.append("titulo_nuevo")
        else:
            for campo, valor in valores.items():
                if valor is None or valor == "":
                    continue  # vacío jamás pisa lo que ya estaba
                if fila[campo] != valor:
                    cur.execute(
                        f"UPDATE titles SET {campo} = ?, "
                        f"updated_at = datetime('now') WHERE tt = ?", (valor, tt))
                    cambios.append(campo)

        # Capa personal: la nota es lo único que se toca aquí.
        est = cur.execute("SELECT * FROM user_state WHERE tt = ?", (tt,)).fetchone()
        fecha = fecha or (date.today().isoformat() if nota is not None else None)
        if est is None:
            cur.execute(
                """INSERT INTO user_state (tt, my_rating, date_rated, watch_status)
                   VALUES (?, ?, ?, ?)""",
                (tt, nota, fecha, "rated" if nota is not None else "watchlist"))
            cambios.append("nota_nueva")
        elif nota is not None and est["my_rating"] != nota:
            cur.execute(
                """UPDATE user_state SET my_rating = ?, date_rated = ?,
                   watch_status = 'rated', updated_at = datetime('now') WHERE tt = ?""",
                (nota, fecha, tt))
            cambios.append("nota_actualizada")
        # nota is None -> no se toca la nota existente. Nunca se borra.

        if dry_run:
            conn.rollback()
            return {"tt": tt, "nuevo": nuevo, "nota": nota,
                    "cambios": cambios, "rellenados": [], "dry_run": True}
        conn.commit()
    finally:
        conn.close()

    rellenados: list[str] = []
    error_enriquecido = None
    if enriquecer_datos and not dry_run:
        if proveedor is None:
            from .proveedores.combinado import ProveedorCombinado
            proveedor = ProveedorCombinado()
        resultado = enriquecer(db_path, tt, proveedor, solo_faltantes=True)
        rellenados = resultado.get("rellenados", [])
        if resultado.get("error"):
            error_enriquecido = "no se ha podido enriquecer (revisa el tt)"

    return {"tt": tt, "nuevo": nuevo, "nota": nota, "cambios": cambios,
            "rellenados": rellenados, "aviso": error_enriquecido}
