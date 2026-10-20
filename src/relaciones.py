"""Relaciones entre títulos y obras origen (universos, secuelas, libros…)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

from .db import get_connection

RELATION_TYPES = {"sequel", "prequel", "universe", "remake", "spinoff", "adaptation", "related"}
WORK_TYPES = {"book", "comic", "manga", "play", "other"}


def add_relation(
    db_path: str | Path,
    from_tt: str,
    to_tt: str,
    relation_type: str,
    source: str | None = None,
) -> None:
    if relation_type not in RELATION_TYPES:
        raise ValueError(f"relation_type desconocido: {relation_type}")
    if from_tt == to_tt:
        raise ValueError("un título no puede relacionarse consigo mismo")
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO title_relations (from_tt, to_tt, relation_type, source) "
            "VALUES (?, ?, ?, ?)", (from_tt, to_tt, relation_type, source))
        conn.commit()
    finally:
        conn.close()


def add_origin(
    db_path: str | Path,
    tt: str,
    work_title: str,
    work_type: str,
    author: str | None = None,
    source: str | None = None,
) -> None:
    if work_type not in WORK_TYPES:
        raise ValueError(f"work_type desconocido: {work_type}")
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO works_origin (tt, work_title, work_type, author, source) "
            "VALUES (?, ?, ?, ?, ?)", (tt, work_title, work_type, author, source))
        conn.commit()
    finally:
        conn.close()


def saga_de(db_path: str | Path, tt: str) -> list[dict]:
    """Títulos relacionados con tt en cualquier dirección."""
    conn = get_connection(db_path)
    try:
        filas = conn.execute(
            """SELECT t.tt, t.original_title, r.relation_type FROM title_relations r
               JOIN titles t ON t.tt = CASE WHEN r.from_tt = ? THEN r.to_tt ELSE r.from_tt END
               WHERE r.from_tt = ? OR r.to_tt = ?""", (tt, tt, tt)).fetchall()
        return [dict(f) for f in filas]
    finally:
        conn.close()


def colecciones_de(db_path: str | Path) -> list[dict]:
    """Colecciones con al menos un título del catálogo, con sus partes."""
    conn = get_connection(db_path)
    try:
        filas = conn.execute(
            """SELECT c.collection_id, c.collection_name, t.tt, t.title_es,
                      t.original_title, t.year, u.my_rating, u.watch_status
               FROM title_collections c
               JOIN titles t ON t.tt = c.tt
               LEFT JOIN user_state u ON u.tt = t.tt
               WHERE c.collection_id IS NOT NULL
               ORDER BY c.collection_id, t.year, t.tt""").fetchall()
        grupos: dict[int, dict] = {}
        for f in filas:
            g = grupos.setdefault(f["collection_id"], {
                "collection_id": f["collection_id"],
                "collection_name": f["collection_name"] or "",
                "titulos": [],
            })
            g["titulos"].append(dict(f))
        return list(grupos.values())
    finally:
        conn.close()


def derivar_relaciones_coleccion(db_path: str | Path) -> dict:
    """Deduce relaciones saga a partir de las colecciones de TMDB.

    - "universe": entre todos los pares de títulos de la misma colección. Es
      un hecho: comparten colección.
    - "sequel": entre vecinos por año de la misma colección cuando comparten
      director o actor principal (cast_order <= 3) y el salto es de al menos
      un año. Es una heurística: el panel muestra la colección entera
      ordenada por año para que el usuario juzgue.

    Idempotente: se apoya en INSERT OR IGNORE, así que repetirla no duplica.
    """
    conn = get_connection(db_path)
    try:
        creado = 0
        colecciones = colecciones_de(db_path)
        for grupo in colecciones:
            partes = grupo["titulos"]
            for i, a in enumerate(partes):
                for b in partes[i + 1:]:
                    if _relacion(conn, a["tt"], b["tt"], "universe", "tmdb_coleccion"):
                        creado += 1
            # Secuela: vecino por año con director o actor principal en común.
            for a, b in zip(partes, partes[1:]):
                if a["year"] is None or b["year"] is None:
                    continue
                if b["year"] - a["year"] < 1:
                    continue
                if not _comparten_protagonista(conn, a["tt"], b["tt"]):
                    continue
                if _relacion(conn, a["tt"], b["tt"], "sequel", "tmdb_coleccion"):
                    creado += 1
        conn.commit()
        return {"colecciones": len(colecciones), "relaciones_nuevas": creado}
    finally:
        conn.close()


def _relacion(conn, from_tt: str, to_tt: str, tipo: str, source: str) -> bool:
    """Inserta la relación si es válida y no existía. True si es nueva."""
    if from_tt == to_tt or tipo not in RELATION_TYPES:
        return False
    cur = conn.execute(
        "INSERT OR IGNORE INTO title_relations (from_tt, to_tt, relation_type, source) "
        "VALUES (?, ?, ?, ?)", (from_tt, to_tt, tipo, source))
    return bool(cur.rowcount)


def _comparten_protagonista(conn, tt_a: str, tt_b: str) -> bool:
    """True si comparten director o algún actor del reparto principal."""
    n = conn.execute(
        """SELECT COUNT(*) AS n FROM (
             SELECT person_id FROM title_credits
             WHERE tt = ? AND role = 'director'
             INTERSECT
             SELECT person_id FROM title_credits
             WHERE tt = ? AND role = 'director'
           )""", (tt_a, tt_b)).fetchone()["n"]
    if n:
        return True
    n = conn.execute(
        """SELECT COUNT(*) AS n FROM (
             SELECT person_id FROM title_cast WHERE tt = ? AND cast_order <= 3
             INTERSECT
             SELECT person_id FROM title_cast WHERE tt = ? AND cast_order <= 3
           )""", (tt_a, tt_b)).fetchone()["n"]
    return bool(n)
