"""Huecos de enriquecimiento: qué le falta a cada título desde la web.

Cada hueco es una fila {tt, campo}. Campos:
cast, credits_extra, idioma, paises, estreno_es, duracion_exacta,
rating_imdb, sinopsis, poster, presupuesto, taquilla, serie_info, coleccion.

"coleccion" se cierra con la fila de title_collections: si el título no
pertenece a ninguna colección se guarda con collection_id NULL, de modo que
no se vuelve a pedir.
"""
from __future__ import annotations

from pathlib import Path

from .db import get_connection


def listar_huecos(
    db_path: str | Path,
    tt: str | None = None,
) -> list[dict]:
    conn = get_connection(db_path)
    try:
        if tt:
            titulos = [r for r in conn.execute("SELECT * FROM titles WHERE tt = ?", (tt,))]
        else:
            titulos = list(conn.execute("SELECT * FROM titles"))
        huecos: list[dict] = []
        for t in titulos:
            tid = t["tt"]

            def falta(condicion: bool, campo: str):
                if condicion:
                    huecos.append({"tt": tid, "campo": campo})

            n_cast = conn.execute(
                "SELECT COUNT(*) AS n FROM title_cast WHERE tt = ?", (tid,)).fetchone()["n"]
            falta(n_cast == 0, "cast")

            n_extra = conn.execute(
                "SELECT COUNT(*) AS n FROM title_credits WHERE tt = ? AND role != 'director'",
                (tid,)).fetchone()["n"]
            falta(n_extra == 0, "credits_extra")

            falta(not t["original_lang_iso"], "idioma")

            n_paises = conn.execute(
                "SELECT COUNT(*) AS n FROM title_countries WHERE tt = ?", (tid,)).fetchone()["n"]
            falta(n_paises == 0, "paises")

            n_es = conn.execute(
                "SELECT COUNT(*) AS n FROM release_dates WHERE tt = ? AND territory = 'ES'",
                (tid,)).fetchone()["n"]
            falta(not t["spain_release_date"] and n_es == 0, "estreno_es")

            falta(t["runtime_min_exact"] is None, "duracion_exacta")
            falta(t["imdb_rating"] is None, "rating_imdb")
            falta(not t["synopsis"], "sinopsis")

            n_poster = conn.execute(
                "SELECT COUNT(*) AS n FROM media_refs WHERE tt = ? AND kind = 'poster'",
                (tid,)).fetchone()["n"]
            falta(not t["poster_url"] and n_poster == 0, "poster")

            falta(t["budget_amount"] is None, "presupuesto")
            falta(t["box_office_amount"] is None, "taquilla")

            es_serie = (t["title_type"] or "").lower().startswith("serie")
            if es_serie:
                hay = conn.execute(
                    "SELECT 1 FROM series_info WHERE tt = ?", (tid,)).fetchone()
                falta(hay is None, "serie_info")

            n_col = conn.execute(
                "SELECT COUNT(*) AS n FROM title_collections WHERE tt = ?", (tid,)
            ).fetchone()["n"]
            falta(n_col == 0, "coleccion")
        return huecos
    finally:
        conn.close()
