"""Proveedor combinado: TMDB primero, OMDb solo parcha huecos (nunca pisa).

Uso: python scripts/scrapear_peliculas.py --proveedor src.proveedores.combinado:ProveedorCombinado
Escalable a móvil: devuelve URLs absolutas y JSON serializable, sin binarios.
"""
from __future__ import annotations

from src.scraper import ProveedorBase


class ProveedorCombinado(ProveedorBase):
    nombre = "combinado-tmdb-omdb"

    def __init__(self, tmdb=None, omdb=None) -> None:
        if tmdb is None:
            from .tmdb import ProveedorTMDB
            tmdb = ProveedorTMDB()
        if omdb is None:
            try:
                from .omdb import ProveedorOMDB
                omdb = ProveedorOMDB()
            except RuntimeError:
                omdb = None  # sin key OMDb: funciona solo con TMDB
        self._tmdb = tmdb
        self._omdb = omdb

    @staticmethod
    def _vacio(valor) -> bool:
        if valor is None:
            return True
        if isinstance(valor, str) and not valor.strip():
            return True
        if isinstance(valor, (list, dict)) and not valor:
            return True
        return False

    def fetch(self, tt: str) -> dict:
        datos: dict = {}
        try:
            datos = dict(self._tmdb.fetch(tt) or {})
        except Exception:
            datos = {}
        if not self._omdb:
            return datos
        faltan = [k for k in ("rating_imdb", "sinopsis", "poster", "duracion_exacta",
                              "idioma", "paises", "cast", "credits_extra", "serie_info")
                  if self._vacio(datos.get(k))]
        if not faltan:
            return datos
        try:
            parche = self._omdb.fetch(tt) or {}
        except Exception:
            return datos
        for k in faltan:
            if not self._vacio(parche.get(k)):
                datos[k] = parche[k]
        return datos
