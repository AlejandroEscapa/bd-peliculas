"""Proveedores web TMDB/OMDb/combinado: mapeo a formato scraper (red simulada)."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


class TestProveedores(unittest.TestCase):
    def test_tmdb_mapea_cast_creditos_sinopsis_poster_es(self):
        from src.proveedores.tmdb import ProveedorTMDB
        prov = ProveedorTMDB(bearer="TEST")
        find = {"movie_results": [{"id": 283995, "title": "Guardianes de la galaxia Vol. 2",
                                   "overview": "Sinopsis ES", "poster_path": "/p.jpg",
                                   "original_language": "en",
                                   "origin_country": ["US"],
                                   "runtime": 136, "budget": 200000000, "revenue": 863000000}],
                "tv_results": []}
        detalle_es = {"overview": "Sinopsis ES", "poster_path": "/p.jpg",
                        "original_language": "en", "production_countries": [{"iso_3166_1": "US"}],
                        "runtime": 136, "budget": 200000000, "revenue": 863000000}
        credits = {"cast": [{"name": "Chris Pratt", "character": "Star-Lord", "order": 0}],
                   "crew": [{"name": "James Gunn", "job": "Director"},
                            {"name": "James Gunn", "job": "Writer"}]}
        with patch.object(ProveedorTMDB, "_get_json", side_effect=[find, detalle_es, credits]):
            try:
                datos = prov.fetch("tt3896198")
            except TypeError:
                self.fail("fetch(tt) debe aceptar el tt de IMDb")
        self.assertEqual(datos["sinopsis"]["text"], "Sinopsis ES")
        self.assertTrue(datos["poster"]["url"].endswith("/p.jpg"))
        self.assertEqual(datos["cast"][0]["name"], "Chris Pratt")
        roles = {(c["name"], c["role"]) for c in datos["credits_extra"]}
        self.assertIn(("James Gunn", "director"), roles)
        self.assertIn("idioma", datos)

    def test_tmdb_fallback_en_cuando_es_vacio(self):
        from src.proveedores.tmdb import ProveedorTMDB
        prov = ProveedorTMDB(bearer="TEST")
        find_es = {"movie_results": [{"id": 1, "overview": "", "poster_path": "/p.jpg",
                                      "original_language": "en"}],
                   "tv_results": []}
        find_en = {"movie_results": [], "tv_results": []}
        detalle_en = {"overview": "English fallback", "poster_path": "/p.jpg",
                      "original_language": "en", "runtime": 100}
        credits = {"cast": [], "crew": []}
        with patch.object(ProveedorTMDB, "_get_json",
                          side_effect=[find_es, detalle_en, credits, find_en]):
            datos = prov.fetch("tt0000001")
        self.assertEqual(datos["sinopsis"]["text"], "English fallback")

    def test_tmdb_busca_con_external_source_imdb_id(self):
        """Sin external_source, /find/ responde 404 y no se encuentra nada."""
        from src.proveedores.tmdb import ProveedorTMDB
        prov = ProveedorTMDB(bearer="TEST")
        find = {"movie_results": [], "tv_results": []}
        with patch.object(ProveedorTMDB, "_get_json", return_value=find) as mock:
            prov.fetch("tt0000001")
        url = mock.call_args_list[0].args[0]
        self.assertIn("external_source=imdb_id", url)

    def test_omdb_mapea_rating_sin_pisar_formato(self):
        from src.proveedores.omdb import ProveedorOMDB
        prov = ProveedorOMDB(api_key="TEST")
        payload = {"Response": "True", "Plot": "Plot EN", "Poster": "http://x/poster.jpg",
                   "imdbRating": "7.6", "imdbVotes": "849,165", "Runtime": "136 min",
                   "Language": "English", "Country": "United States",
                   "Director": "James Gunn", "Actors": "Chris Pratt, Zoe Saldana"}
        with patch.object(ProveedorOMDB, "_get_json", return_value=payload):
            datos = prov.fetch("tt3896198")
        self.assertEqual(datos["rating_imdb"]["rating"], 7.6)
        self.assertEqual(datos["rating_imdb"]["votes"], 849165)
        self.assertEqual(datos["duracion_exacta"], 136)
        self.assertTrue(datos["poster"]["url"].startswith("http"))

    def test_combinado_fusiona_sin_pisar_tmdb(self):
        from src.proveedores.combinado import ProveedorCombinado

        class FakeTMDB:
            nombre = "tmdb"
            def fetch(self, tt):
                return {"sinopsis": {"text": "ES", "source": "tmdb"},
                        "poster": {"url": "http://tmdb/p.jpg", "source": "tmdb"}}

        class FakeOMDB:
            nombre = "omdb"
            def fetch(self, tt):
                return {"sinopsis": {"text": "EN", "source": "omdb"},
                        "poster": {"url": "http://omdb/p.jpg", "source": "omdb"},
                        "rating_imdb": {"rating": 7.6, "votes": 10}}

        prov = ProveedorCombinado(tmdb=FakeTMDB(), omdb=FakeOMDB())
        datos = prov.fetch("tt3896198")
        self.assertEqual(datos["sinopsis"]["text"], "ES")
        self.assertEqual(datos["rating_imdb"]["rating"], 7.6)

    def test_sin_keys_error_claro(self):
        from src.proveedores.tmdb import ProveedorTMDB
        from src.proveedores.omdb import ProveedorOMDB
        import os
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                ProveedorTMDB()
            with self.assertRaises(RuntimeError):
                ProveedorOMDB()


if __name__ == "__main__":
    unittest.main()
