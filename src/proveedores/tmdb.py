"""Proveedor TMDB (fuente principal): sinopsis es-ES con fallback en-US, reparto,
equipo, póster, idioma, países, duración, presupuesto/taquilla y serie_info.

Solo stdlib (urllib). Clave por entorno: TMDB_BEARER (JWT v4, recomendado)
o TMDB_API_KEY (v3, como ?api_key=). Sin red en tests: se simula _get_json.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

from src.scraper import ProveedorBase

BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p/w500"
LANG_ES = "es-ES"
LANG_EN = "en-US"

_JOB_A_ROL = {
    "Director": "director",
    "Writer": "writer",
    "Screenplay": "writer",
    "Author": "writer",
    "Producer": "producer",
    "Executive Producer": "producer",
    "Composer": "composer",
    "Original Music Composer": "composer",
    "Music": "composer",
    "Cinematographer": "cinematographer",
    "Director of Photography": "cinematographer",
    "Editor": "editor",
}


class ProveedorTMDB(ProveedorBase):
    nombre = "tmdb"

    def __init__(self, bearer: str | None = None, timeout: int = 20) -> None:
        token = bearer or os.environ.get("TMDB_BEARER") or os.environ.get("TMDB_API_KEY")
        if not token:
            raise RuntimeError("Falta TMDB_BEARER (o TMDB_API_KEY) en el entorno")
        self._token = token
        self._timeout = timeout
        self._es_bearer = token.startswith("eyJ")

    def _get_json(self, url: str) -> dict:
        headers = {"accept": "application/json"}
        if self._es_bearer:
            headers["Authorization"] = f"Bearer {self._token}"
        else:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}api_key={urllib.parse.quote(self._token)}"
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=self._timeout) as r:
            return json.load(r)

    def _get(self, path: str, lang: str, params: dict | None = None) -> dict:
        query = {"language": urllib.parse.quote(lang)}
        for k, v in (params or {}).items():
            query[k] = urllib.parse.quote(str(v))
        url = f"{BASE}{path}?{'&'.join(f'{k}={v}' for k, v in query.items())}"
        return self._get_json(url)

    def fetch(self, tt: str) -> dict:
        # `external_source` es obligatorio: sin él, /find/ responde 404
        # (status_code 34) y la película no se encuentra.
        encontrado = self._get(f"/find/{tt}", LANG_ES,
                               {"external_source": "imdb_id"})
        pelis = encontrado.get("movie_results") or []
        series = encontrado.get("tv_results") or []
        if pelis:
            kind, base = "movie", pelis[0]
        elif series:
            kind, base = "tv", series[0]
        else:
            return {}
        mid = base.get("id")
        if not mid:
            return {}
        detalle = self._get(f"/{kind}/{mid}", LANG_ES)
        if not (detalle.get("overview") or "").strip():
            detalle_en = self._get(f"/{kind}/{mid}", LANG_EN)
            for k in ("overview", "poster_path", "original_language"):
                if not (detalle.get(k) or "") and detalle_en.get(k):
                    detalle[k] = detalle_en[k]
        try:
            creditos = self._get(f"/{kind}/{mid}/credits", LANG_ES)
        except Exception:
            creditos = {"cast": [], "crew": []}

        datos: dict = {}
        sinopsis = (detalle.get("overview") or "").strip()
        if sinopsis:
            datos["sinopsis"] = {"text": sinopsis, "source": self.nombre}
        poster = detalle.get("poster_path")
        if poster:
            datos["poster"] = {"url": f"{IMG}{poster}", "source": self.nombre}
        lang = (detalle.get("original_language") or "").strip()
        if lang:
            datos["idioma"] = lang[:2].lower()
        paises = list(detalle.get("origin_country") or [])
        for c in detalle.get("production_countries") or []:
            code = (c.get("iso_3166_1") or "").strip().upper()
            if code and code not in paises:
                paises.append(code)
        if paises:
            datos["paises"] = paises
        runtime = detalle.get("runtime")
        if runtime is None:
            ert = detalle.get("episode_run_time") or []
            runtime = next((x for x in ert if x), None)
        if runtime:
            datos["duracion_exacta"] = int(runtime)
        if detalle.get("budget"):
            datos["presupuesto"] = {"amount": detalle["budget"], "currency": "USD"}
        if detalle.get("revenue"):
            datos["taquilla"] = {"amount": detalle["revenue"], "currency": "USD"}
        if kind == "tv":
            datos["serie_info"] = {
                "seasons": detalle.get("number_of_seasons"),
                "episodes": detalle.get("number_of_episodes"),
                "status": detalle.get("status"),
                "end_date": detalle.get("last_air_date") or None,
            }
        # La colección/franquicia (saga) viene en la misma respuesta de detalle:
        # cero peticiones extra. None = consultado, no tiene colección.
        coleccion = detalle.get("belongs_to_collection") or {}
        cid = coleccion.get("id")
        datos["coleccion"] = (
            {"id": int(cid), "nombre": coleccion.get("name") or ""}
            if cid else None
        )

        cast = []
        for i, m in enumerate((creditos.get("cast") or [])[:15]):
            if m.get("name"):
                cast.append({"name": m["name"], "character": m.get("character") or "",
                             "order": m.get("order", i + 1)})
        if cast:
            datos["cast"] = cast
        extra = []
        vistos = set()
        for c in creditos.get("crew") or []:
            nombre = c.get("name")
            rol = _JOB_A_ROL.get(c.get("job") or "", "other")
            if nombre and (nombre, rol) not in vistos:
                vistos.add((nombre, rol))
                extra.append({"name": nombre, "role": rol})
        if extra:
            datos["credits_extra"] = extra
        return datos
