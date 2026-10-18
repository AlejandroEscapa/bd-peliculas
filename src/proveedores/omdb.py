"""Proveedor OMDb (parche): rating_imdb por tt + fallbacks (sinopsis, póster,
duración, idioma, países, directores/actores). Solo stdlib. Key por entorno.
"""
from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request

from src.scraper import ProveedorBase

_IDIOMAS = {
    "english": "en", "spanish": "es", "español": "es", "french": "fr",
    "francés": "fr", "german": "de", "alemán": "de", "italian": "it",
    "japanese": "ja", "japonés": "ja", "portuguese": "pt", "catalan": "ca",
    "catalán": "ca", "korean": "ko", "coreano": "ko", "chinese": "zh",
}
_PAISES = {
    "united states": "US", "usa": "US", "spain": "ES", "españa": "ES",
    "united kingdom": "GB", "uk": "GB", "france": "FR", "germany": "DE",
    "italy": "IT", "japan": "JP", "japón": "JP", "canada": "CA",
    "south korea": "KR", "mexico": "MX", "méxico": "MX",
}


class ProveedorOMDB(ProveedorBase):
    nombre = "omdb"

    def __init__(self, api_key: str | None = None, timeout: int = 20) -> None:
        key = api_key or os.environ.get("OMDB_API_KEY")
        if not key:
            raise RuntimeError("Falta OMDB_API_KEY en el entorno")
        self._key = key
        self._timeout = timeout

    def _get_json(self, url: str) -> dict:
        req = urllib.request.Request(url, headers={"accept": "application/json"})
        with urllib.request.urlopen(req, timeout=self._timeout) as r:
            return json.load(r)

    @staticmethod
    def _nombres(campo: str) -> list[str]:
        return [p.strip() for p in (campo or "").split(",") if p.strip() and p.strip() != "N/A"]

    def fetch(self, tt: str) -> dict:
        url = f"http://www.omdbapi.com/?i={urllib.parse.quote(tt)}&apikey={urllib.parse.quote(self._key)}"
        d = self._get_json(url)
        if d.get("Response") != "True":
            return {}
        datos: dict = {}
        try:
            rating = float(d.get("imdbRating", ""))
            votes = int(re.sub(r"\D", "", d.get("imdbVotes", "") or ""))
            datos["rating_imdb"] = {"rating": rating, "votes": votes}
        except (ValueError, TypeError):
            pass
        plot = (d.get("Plot") or "").strip()
        if plot and plot != "N/A":
            datos["sinopsis"] = {"text": plot, "source": self.nombre}
        poster = (d.get("Poster") or "").strip()
        if poster and poster != "N/A":
            datos["poster"] = {"url": poster, "source": self.nombre}
        m = re.search(r"(\d+)", d.get("Runtime") or "")
        if m:
            datos["duracion_exacta"] = int(m.group(1))
        langs = self._nombres(d.get("Language", ""))
        if langs:
            iso = _IDIOMAS.get(langs[0].lower())
            if iso:
                datos["idioma"] = iso
        paises = []
        for p in self._nombres(d.get("Country", "")):
            code = _PAISES.get(p.lower())
            if code and code not in paises:
                paises.append(code)
        if paises:
            datos["paises"] = paises
        extra = [{"name": n, "role": "director"} for n in self._nombres(d.get("Director", ""))]
        for n in self._nombres(d.get("Writer", ""))[:5]:
            extra.append({"name": n, "role": "writer"})
        if extra:
            datos["credits_extra"] = extra
        actores = self._nombres(d.get("Actors", ""))[:15]
        if actores:
            datos["cast"] = [{"name": n, "character": "", "order": i + 1}
                             for i, n in enumerate(actores)]
        return datos
