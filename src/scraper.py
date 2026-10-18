"""scrapear-peliculas: completa huecos web con un proveedor intercambiable.

El proveedor (API gratis, web, Wikipedia…) se implementa aparte; este
módulo solo sabe escribir su respuesta en las tablas web-own con
procedencia. Nunca toca user_state ni borra nada.

Protocolo del proveedor: objeto con atributo `nombre` y método
`fetch(tt) -> dict`, donde cada clave es un campo de hueco y el valor
un payload con esa forma:
  cast: [{"name", "character", "order"}]
  credits_extra: [{"name", "role"}]
  idioma: "en" | {"code": "en"}
  paises: ["US", "ES"]
  estreno_es: "1995-02-24"
  duracion_exacta: 142
  rating_imdb: {"rating": 9.3, "votes": 123} (solo rellena si está vacío)
  sinopsis: {"text": …, "source": …} | "texto…" (fuente = proveedor)
  poster: {"url": …, "source": …} | "https://…"
  presupuesto / taquilla: {"amount": N, "currency": "USD"}
  serie_info: {"seasons", "episodes", "status", "end_date"}
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .db import get_connection
from .huecos import listar_huecos


class ProveedorBase:
    nombre = "base"

    def fetch(self, tt: str) -> dict:  # pragma: no cover - lo implementa cada fuente
        raise NotImplementedError


def _ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _persona(cur, nombre: str) -> int:
    cur.execute("INSERT OR IGNORE INTO people (name) VALUES (?)", (nombre,))
    return int(cur.execute("SELECT id FROM people WHERE name = ?", (nombre,)).fetchone()["id"])


def enriquecer(
    db_path: str | Path,
    tt: str,
    proveedor: ProveedorBase,
    solo_faltantes: bool = True,
    dry_run: bool = False,
) -> dict:
    """Aplica la respuesta del proveedor a un título. Devuelve lo rellenado."""
    datos = proveedor.fetch(tt)
    fuente = getattr(proveedor, "nombre", "web")
    rellenados: list[str] = []
    omitidos: list[str] = []

    faltantes = {h["campo"] for h in listar_huecos(db_path, tt)} if solo_faltantes else set()

    def toca(campo: str) -> bool:
        return (not solo_faltantes) or (campo in faltantes)

    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        ahora = _ahora()

        if "cast" in datos and toca("cast"):
            for i, m in enumerate(datos["cast"] or []):
                pid = _persona(cur, m["name"])
                cur.execute(
                    "INSERT OR IGNORE INTO title_cast "
                    "(tt, person_id, character_name, cast_order, source, fetched_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (tt, pid, m.get("character", ""), m.get("order", i + 1), fuente, ahora))
            rellenados.append("cast")
        if "credits_extra" in datos and toca("credits_extra"):
            for c in datos["credits_extra"] or []:
                pid = _persona(cur, c["name"])
                cur.execute(
                    "INSERT OR IGNORE INTO title_credits (tt, person_id, role, source, fetched_at) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (tt, pid, c.get("role", "other"), fuente, ahora))
            rellenados.append("credits_extra")

        titulo = cur.execute("SELECT * FROM titles WHERE tt = ?", (tt,)).fetchone()
        if titulo is None:
            return {"tt": tt, "rellenados": [], "omitidos": ["titulo_inexistente"], "error": True}

        simples = {
            "idioma": ("original_lang_iso",),
            "estreno_es": ("spain_release_date",),
            "duracion_exacta": ("runtime_min_exact",),
            "sinopsis": ("synopsis",),
            "poster": ("poster_url",),
        }
        for campo, (columna,) in simples.items():
            if campo not in datos or not toca(campo):
                continue
            valor = datos[campo]
            if isinstance(valor, dict):
                texto = valor.get("text") or valor.get("url") or valor.get("code")
                origen = valor.get("source", fuente)
            else:
                texto, origen = valor, fuente
            if texto is None or (isinstance(texto, str) and not texto.strip()):
                omitidos.append(campo)
                continue
            if campo == "idioma" and isinstance(texto, str):
                texto = texto.strip().lower()[:2]
            cur.execute(f"UPDATE titles SET {columna} = ? WHERE tt = ?", (texto, tt))
            if campo == "sinopsis":
                cur.execute("UPDATE titles SET synopsis_source = ? WHERE tt = ?", (origen, tt))
            if campo == "poster":
                cur.execute("UPDATE titles SET poster_source = ? WHERE tt = ?", (origen, tt))
                cur.execute(
                    "INSERT INTO media_refs (tt, kind, url, source) VALUES (?, 'poster', ?, ?)",
                    (tt, texto, origen))
            rellenados.append(campo)

        if "paises" in datos and toca("paises"):
            for p in datos["paises"] or []:
                cur.execute("INSERT OR IGNORE INTO title_countries (tt, country_code) "
                            "VALUES (?, ?)", (tt, p.strip().upper()))
            rellenados.append("paises")

        if "estreno_es" in datos and datos["estreno_es"]:
            fecha = datos["estreno_es"]
            cur.execute("INSERT OR REPLACE INTO release_dates (tt, territory, rel_date, source) "
                        "VALUES (?, 'ES', ?, ?)", (tt, fecha, fuente))

        # rating_imdb: el CSV manda; la web solo rellena si está vacío.
        if "rating_imdb" in datos and toca("rating_imdb"):
            payload = datos["rating_imdb"]
            if titulo["imdb_rating"] is None and payload:
                cur.execute("UPDATE titles SET imdb_rating = ?, imdb_votes = ? WHERE tt = ?",
                            (payload.get("rating"), payload.get("votes"), tt))
                rellenados.append("rating_imdb")
            else:
                omitidos.append("rating_imdb")

        for campo, prefijo in (("presupuesto", "budget"), ("taquilla", "box_office")):
            if campo in datos and toca(campo) and datos[campo]:
                p = datos[campo]
                cur.execute(
                    f"UPDATE titles SET {prefijo}_amount = ?, {prefijo}_currency = ?, "
                    f"{prefijo}_source = ? WHERE tt = ?",
                    (p.get("amount"), p.get("currency"), fuente, tt))
                rellenados.append(campo)

        if "serie_info" in datos and toca("serie_info") and datos["serie_info"]:
            s = datos["serie_info"]
            cur.execute(
                "INSERT OR REPLACE INTO series_info "
                "(tt, seasons, episodes, status, end_date, source) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (tt, s.get("seasons"), s.get("episodes"), s.get("status"),
                 s.get("end_date"), fuente))
            rellenados.append("serie_info")

        if dry_run:
            conn.rollback()
            return {"tt": tt, "rellenados": rellenados, "omitidos": omitidos, "dry_run": True}
        conn.commit()
        return {"tt": tt, "rellenados": rellenados, "omitidos": omitidos}
    finally:
        conn.close()
