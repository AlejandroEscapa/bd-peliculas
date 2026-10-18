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
