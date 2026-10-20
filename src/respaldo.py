"""Backup portable: volcado SQL + manifiesto de versión y conteos."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .db import get_connection

VERSION = "0002_colecciones"


def backup(db_path: str | Path, destino: str | Path) -> dict:
    db_path, destino = Path(db_path), Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    sello = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    dump_path = destino / f"catalogo-{sello}.sql"

    conn = get_connection(db_path)
    try:
        tablas = [r["name"] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
        conteos = {t: conn.execute(f"SELECT COUNT(*) AS n FROM \"{t}\"").fetchone()["n"]
                   for t in tablas}
        with open(dump_path, "w", encoding="utf-8") as f:
            for linea in conn.iterdump():
                f.write(linea + "\n")
    finally:
        conn.close()

    manifiesto = {"version_esquema": VERSION, "sello": sello, "tablas": conteos,
                  "dump": dump_path.name}
    (destino / f"catalogo-{sello}.json").write_text(
        json.dumps(manifiesto, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifiesto


def restore(dump_path: str | Path, db_path: str | Path) -> Path:
    """Restaura un volcado en una base vacía. No borra el dump."""
    db_path = Path(db_path)
    if db_path.exists():
        raise FileExistsError(f"restore solo sobre base vacía: {db_path} ya existe")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(Path(dump_path).read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    return db_path
