"""Conexión y creación de la base local (sqlite3 stdlib, sin dependencias)."""
from __future__ import annotations

import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "db" / "schema.sql"
VIEWS_PATH = ROOT / "db" / "views.sql"
DEFAULT_DB_PATH = ROOT / "data" / "catalogo.db"


def get_connection(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> Path:
    """Crea el esquema si no existe. Idempotente (CREATE TABLE IF NOT EXISTS)."""
    db_path = Path(db_path)
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn = get_connection(db_path)
    try:
        conn.executescript(sql)
        if VIEWS_PATH.exists():
            conn.executescript(VIEWS_PATH.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    return db_path
