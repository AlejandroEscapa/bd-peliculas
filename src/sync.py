"""Ingesta del CSV de IMDb: entrada delta, nunca destructiva.

Reglas:
- Clave estable: Const (tt). Sin tt válido la fila va a cuarentena.
- Solo escribe columnas CSV-own (títulos, tipo, año, runtime_csv,
  rating/votos, fecha csv, géneros, directores con fuente imdb_csv,
  capa personal). Jamás toca columnas web-own (sinopsis, poster,
  reparto, idioma, países, fechas por territorio, dinero, series…).
- Vacío en CSV jamás borra: solo actualiza si el valor nuevo no es vacío
  y es distinto al guardado.
"""
from __future__ import annotations

import csv
import re
import sqlite3
from pathlib import Path

from .db import get_connection, init_db

TT_RE = re.compile(r"^tt\d{7,8}$")

# Campos de titles que el CSV sí puede actualizar (públicos del export).
CSV_OWN_TITLES = (
    "title_es", "original_title", "url", "title_type", "year",
    "runtime_min_csv", "imdb_rating", "imdb_votes", "release_date_csv",
)


def _to_int(value: str | None) -> int | None:
    if value is None:
        return None
    value = value.strip().replace(",", "")
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _to_float(value: str | None) -> float | None:
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _to_rating(value: str | None) -> int | None:
    n = _to_int(value)
    if n is None:
        return None
    return n if 1 <= n <= 10 else None


def _split_list(value: str | None) -> list[str]:
    if not value:
        return []
    return [p.strip() for p in value.split(",") if p.strip()]


def _get_or_create_person(cur: sqlite3.Cursor, name: str) -> int:
    cur.execute("INSERT OR IGNORE INTO people (name) VALUES (?)", (name,))
    row = cur.execute("SELECT id FROM people WHERE name = ?", (name,)).fetchone()
    return int(row["id"])


def _sync_genres(cur: sqlite3.Cursor, tt: str, genres: list[str]) -> bool:
    """Sincroniza géneros del CSV (lista completa por título). Devuelve si cambió.

    Celda vacía = dato desconocido, no "cero géneros": en ese caso no se
    toca nada. Vacío en el CSV jamás borra lo que ya había.
    """
    if not genres:
        return False
    for g in genres:
        cur.execute("INSERT OR IGNORE INTO genres (name) VALUES (?)", (g,))
    actual = {r["genre"] for r in cur.execute(
        "SELECT genre FROM title_genres WHERE tt = ?", (tt,))}
    deseado = set(genres)
    if actual == deseado:
        return False
    for g in deseado - actual:
        cur.execute("INSERT OR IGNORE INTO title_genres (tt, genre) VALUES (?, ?)", (tt, g))
    for g in actual - deseado:
        cur.execute("DELETE FROM title_genres WHERE tt = ? AND genre = ?", (tt, g))
    return True


def _sync_directors(cur: sqlite3.Cursor, tt: str, directors: list[str]) -> bool:
    """Directores del CSV (fuente imdb_csv). Solo toca rol director con esa fuente.

    Igual que los géneros: si la celda viene vacía, no se borra nada.
    """
    if not directors:
        return False
    ids_deseados = {_get_or_create_person(cur, d) for d in directors}
    actuales = {r["person_id"] for r in cur.execute(
        "SELECT person_id FROM title_credits "
        "WHERE tt = ? AND role = 'director' AND (source = 'imdb_csv' OR source IS NULL)",
        (tt,))}
    if actuales == ids_deseados:
        return False
    cur.execute(
        "DELETE FROM title_credits WHERE tt = ? AND role = 'director' "
        "AND (source = 'imdb_csv' OR source IS NULL)", (tt,))
    for pid in ids_deseados:
        cur.execute(
            "INSERT OR IGNORE INTO title_credits (tt, person_id, role, source) "
            "VALUES (?, ?, 'director', 'imdb_csv')", (tt, pid))
    return True


def import_csv(
    csv_path: str | Path,
    db_path: str | Path | None = None,
) -> dict:
    """Importa un export de IMDb. Devuelve el resumen del sync."""
    from .db import DEFAULT_DB_PATH
    db_path = Path(db_path) if db_path else DEFAULT_DB_PATH
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        return _import(conn, Path(csv_path))
    finally:
        conn.close()


def _import(conn: sqlite3.Connection, csv_path: Path) -> dict:
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO sync_runs (csv_path) VALUES (?)", (str(csv_path),))
    run_id = cur.lastrowid

    total = nuevos = actualizados = cuarentena = 0
    ndiffs = 0

    def diff(tt: str, campo: str, anterior, nuevo, tipo: str):
        nonlocal ndiffs
        cur.execute(
            "INSERT INTO sync_diffs (run_id, tt, campo, anterior, nuevo, tipo) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, tt, campo,
             None if anterior is None else str(anterior),
             None if nuevo is None else str(nuevo), tipo))
        ndiffs += 1

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader, start=2):  # línea 1 = cabecera
            total += 1
            tt = (row.get("Const") or "").strip()
            if not TT_RE.match(tt):
                cuarentena += 1
                cur.execute(
                    "INSERT INTO import_quarantine (run_id, row_num, motivo, raw_line) "
                    "VALUES (?, ?, ?, ?)",
                    (run_id, i, "tt_invalido_o_ausente",
                     (row.get("Title") or "")[:200]))
                continue

            titulo = {
                "title_es": (row.get("Title") or "").strip() or None,
                "original_title": (row.get("Original Title") or "").strip() or None,
                "url": (row.get("URL") or "").strip() or None,
                "title_type": (row.get("Title Type") or "").strip() or None,
                "year": _to_int(row.get("Year")),
                "runtime_min_csv": _to_int(row.get("Runtime (mins)")),
                "imdb_rating": _to_float(row.get("IMDb Rating")),
                "imdb_votes": _to_int(row.get("Num Votes")),
                "release_date_csv": (row.get("Release Date") or "").strip() or None,
            }
            rating = _to_rating(row.get("Your Rating"))
            date_rated = (row.get("Date Rated") or "").strip() or None
            watch = "rated" if rating is not None else "watchlist"

            existe = cur.execute(
                "SELECT * FROM titles WHERE tt = ?", (tt,)).fetchone()

            if existe is None:
                cur.execute(
                    """INSERT INTO titles
                       (tt, title_es, original_title, url, title_type, year,
                        runtime_min_csv, imdb_rating, imdb_votes, release_date_csv)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (tt, titulo["title_es"], titulo["original_title"], titulo["url"],
                     titulo["title_type"], titulo["year"], titulo["runtime_min_csv"],
                     titulo["imdb_rating"], titulo["imdb_votes"], titulo["release_date_csv"]))
                cur.execute(
                    """INSERT INTO user_state
                       (tt, my_rating, date_rated, watch_status,
                        csv_created, csv_modified, csv_position)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (tt, rating, date_rated, watch,
                     (row.get("Created") or "").strip() or None,
                     (row.get("Modified") or "").strip() or None,
                     _to_int(row.get("Position"))))
                _sync_genres(cur, tt, _split_list(row.get("Genres")))
                _sync_directors(cur, tt, _split_list(row.get("Directors")))
                diff(tt, "titulo", None, titulo["original_title"] or titulo["title_es"],
                     "nuevo_titulo")
                nuevos += 1
                continue

            # Título existente: actualizar solo CSV-own con valor no vacío y distinto.
            cambiado = False
            for campo in CSV_OWN_TITLES:
                nuevo = titulo[campo]
                if nuevo is None or nuevo == "":
                    continue
                if existe[campo] != nuevo:
                    cur.execute(f"UPDATE titles SET {campo} = ?, updated_at = datetime('now') "
                                "WHERE tt = ?", (nuevo, tt))
                    diff(tt, campo, existe[campo], nuevo, "campo_publico")
                    cambiado = True

            if _sync_genres(cur, tt, _split_list(row.get("Genres"))):
                diff(tt, "genres", None, row.get("Genres"), "campo_publico")
                cambiado = True
            if _sync_directors(cur, tt, _split_list(row.get("Directors"))):
                diff(tt, "directors", None, row.get("Directors"), "campo_publico")
                cambiado = True

            est = cur.execute(
                "SELECT * FROM user_state WHERE tt = ?", (tt,)).fetchone()
            if est is None:
                cur.execute(
                    "INSERT INTO user_state (tt, my_rating, date_rated, watch_status) "
                    "VALUES (?, ?, ?, ?)", (tt, rating, date_rated, watch))
                diff(tt, "my_rating", None, rating, "rating_cambiado")
                cambiado = True
            else:
                # Vacío en CSV jamás borra tu nota: solo se escribe si hay valor nuevo.
                if rating is not None and est["my_rating"] != rating:
                    cur.execute(
                        "UPDATE user_state SET my_rating = ?, date_rated = ?, "
                        "watch_status = 'rated', updated_at = datetime('now') WHERE tt = ?",
                        (rating, date_rated, tt))
                    diff(tt, "my_rating", est["my_rating"], rating, "rating_cambiado")
                    cambiado = True
                elif (rating is not None and est["date_rated"] != date_rated
                        and date_rated):
                    cur.execute(
                        "UPDATE user_state SET date_rated = ?, updated_at = datetime('now') "
                        "WHERE tt = ?", (date_rated, tt))
                    diff(tt, "date_rated", est["date_rated"], date_rated, "rating_cambiado")
                    cambiado = True
                # Fechas del CSV y posición siempre se refrescan si vienen informadas.
                for campo, col in (("Created", "csv_created"), ("Modified", "csv_modified")):
                    v = (row.get(campo) or "").strip() or None
                    if v and est[col] != v:
                        cur.execute(
                            f"UPDATE user_state SET {col} = ? WHERE tt = ?", (v, tt))
                        cambiado = True
                pos = _to_int(row.get("Position"))
                if pos is not None and est["csv_position"] != pos:
                    cur.execute("UPDATE user_state SET csv_position = ? WHERE tt = ?",
                                (pos, tt))
                    cambiado = True

            if cambiado:
                actualizados += 1

    cur.execute(
        "UPDATE sync_runs SET total_rows = ?, nuevos = ?, actualizados = ?, "
        "en_cuarentena = ?, diffs = ? WHERE id = ?",
        (total, nuevos, actualizados, cuarentena, ndiffs, run_id))
    conn.commit()
    return {"run_id": run_id, "total": total, "nuevos": nuevos,
            "actualizados": actualizados, "cuarentena": cuarentena, "diffs": ndiffs}
