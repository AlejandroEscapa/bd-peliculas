"""Altas manuales: la película entra, no se duplica y el CSV no la pisa."""
import csv
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.altas import anadir_pelicula
from src.db import get_connection
from src.sync import import_csv

CABECERA = [
    "Position", "Const", "Created", "Modified", "Description", "Title",
    "Original Title", "URL", "Title Type", "IMDb Rating", "Runtime (mins)",
    "Year", "Genres", "Num Votes", "Release Date", "Directors", "Your Rating",
    "Date Rated",
]


class ProveedorFalso:
    """Proveedor de laboratorio: devuelve datos fijos, sin red."""

    nombre = "falso"

    def fetch(self, tt):
        return {
            "sinopsis": {"text": "Sinopsis de prueba", "source": "falso"},
            "poster": {"url": "https://x/poster.jpg", "source": "falso"},
            "cast": [{"name": "Actor Uno", "character": "Heroe", "order": 1}],
            "coleccion": {"id": 42, "nombre": "Saga de prueba"},
        }


class TestAltas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"

    def tearDown(self):
        self.tmp.cleanup()

    def _alta(self, **kwargs):
        params = dict(tt="tt35511966", nota=9, fecha="2026-10-21",
                      titulo="La bola negra", anio=2026,
                      proveedor=ProveedorFalso())
        params.update(kwargs)
        return anadir_pelicula(self.db_path, **params)

    def _csv(self, filas):
        p = Path(self.tmp.name) / "export.csv"
        with open(p, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(CABECERA)
            w.writerows(filas)
        return p

    def test_alta_crea_titulo_y_nota(self):
        resumen = self._alta()
        self.assertTrue(resumen["nuevo"])
        conn = get_connection(self.db_path)
        try:
            t = conn.execute("SELECT * FROM titles WHERE tt = 'tt35511966'").fetchone()
            self.assertEqual(t["title_es"], "La bola negra")
            self.assertEqual(t["year"], 2026)
            self.assertEqual(t["url"], "https://www.imdb.com/title/tt35511966/")
            e = conn.execute("SELECT * FROM user_state WHERE tt = 'tt35511966'").fetchone()
            self.assertEqual(e["my_rating"], 9)
            self.assertEqual(e["watch_status"], "rated")
        finally:
            conn.close()

    def test_alta_enriquece_solo_huecos(self):
        self._alta()
        conn = get_connection(self.db_path)
        try:
            self.assertEqual(
                conn.execute("SELECT synopsis FROM titles WHERE tt = 'tt35511966'")
                .fetchone()["synopsis"], "Sinopsis de prueba")
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM title_cast WHERE tt = 'tt35511966'")
                .fetchone()["n"], 1)
            self.assertEqual(
                conn.execute("SELECT collection_name FROM title_collections "
                             "WHERE tt = 'tt35511966'").fetchone()["collection_name"],
                "Saga de prueba")
        finally:
            conn.close()

    def test_repetir_no_duplica_y_actualiza_la_nota(self):
        self._alta()
        resumen = self._alta(nota=10)
        self.assertFalse(resumen["nuevo"])
        conn = get_connection(self.db_path)
        try:
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM titles WHERE tt = 'tt35511966'")
                .fetchone()["n"], 1)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM user_state WHERE tt = 'tt35511966'")
                .fetchone()["n"], 1)
            self.assertEqual(
                conn.execute("SELECT my_rating FROM user_state WHERE tt = 'tt35511966'")
                .fetchone()["my_rating"], 10)
        finally:
            conn.close()

    def test_alta_sin_nota_no_borra_la_nota_que_ya_habia(self):
        self._alta(nota=9)
        self._alta(nota=None)
        conn = get_connection(self.db_path)
        try:
            self.assertEqual(
                conn.execute("SELECT my_rating FROM user_state WHERE tt = 'tt35511966'")
                .fetchone()["my_rating"], 9)
        finally:
            conn.close()

    def test_tt_invalido_falla(self):
        with self.assertRaises(ValueError):
            anadir_pelicula(self.db_path, "no-es-un-tt", nota=9,
                            proveedor=ProveedorFalso(), enriquecer_datos=False)

    def test_csv_posterior_no_pisa_el_alta(self):
        """La garantía: el export de IMDb puede llegar después y no rompe nada."""
        self._alta()
        csv_path = self._csv([[
            "1", "tt35511966", "2026-10-21", "2026-10-21", "", "La bola negra",
            "La bola negra", "https://www.imdb.com/title/tt35511966/", "Película",
            "7.0", "155", "2026", "Drama", "820", "2026-09-25", "", "9",
            "2026-10-21",
        ]])
        import_csv(csv_path, self.db_path)
        conn = get_connection(self.db_path)
        try:
            # 1. No hay duplicados.
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM titles WHERE tt = 'tt35511966'")
                .fetchone()["n"], 1)
            # 2. Tu nota sigue ahí (y ahora viene del CSV, que también dice 9).
            e = conn.execute("SELECT * FROM user_state WHERE tt = 'tt35511966'").fetchone()
            self.assertEqual(e["my_rating"], 9)
            self.assertEqual(e["watch_status"], "rated")
            # 3. El enriquecido web sigue intacto: el CSV no lo posee.
            t = conn.execute("SELECT * FROM titles WHERE tt = 'tt35511966'").fetchone()
            self.assertEqual(t["synopsis"], "Sinopsis de prueba")
            self.assertEqual(t["poster_url"], "https://x/poster.jpg")
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM title_cast WHERE tt = 'tt35511966'")
                .fetchone()["n"], 1)
            self.assertEqual(
                conn.execute("SELECT COUNT(*) AS n FROM title_collections "
                             "WHERE tt = 'tt35511966'").fetchone()["n"], 1)
            # 4. Lo que el CSV sí posee, el CSV manda.
            self.assertEqual(t["imdb_rating"], 7.0)
            self.assertEqual(t["title_type"], "Película")
            generos = [r["genre"] for r in conn.execute(
                "SELECT genre FROM title_genres WHERE tt = 'tt35511966'")]
            self.assertEqual(generos, ["Drama"])
        finally:
            conn.close()

    def test_csv_sin_nota_no_borra_la_nota_manually(self):
        """Si el export no trae nota (o la trae vacía), la tuya se queda."""
        self._alta(nota=9)
        csv_path = self._csv([[
            "1", "tt35511966", "2026-10-21", "2026-10-21", "", "La bola negra",
            "La bola negra", "https://www.imdb.com/title/tt35511966/", "Película",
            "7.0", "155", "2026", "Drama", "820", "2026-09-25", "", "", "",
        ]])
        import_csv(csv_path, self.db_path)
        conn = get_connection(self.db_path)
        try:
            self.assertEqual(
                conn.execute("SELECT my_rating FROM user_state WHERE tt = 'tt35511966'")
                .fetchone()["my_rating"], 9)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
