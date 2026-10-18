"""Task 6: proveedor intercambiable, límites y lote que no aborta (sin red)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import get_connection
from src.huecos import listar_huecos
from src.scraper import ProveedorBase, enriquecer
from src.sync import import_csv

FIXTURE = ROOT / "tests" / "fixtures" / "mini.csv"


class ProveedorFalso(ProveedorBase):
    nombre = "falso-test"

    def fetch(self, tt: str) -> dict:
        if tt == "tt0000000":
            raise RuntimeError("título roto simulado")
        return {
            "cast": [{"name": "Tim Robbins", "character": "Andy", "order": 1}],
            "sinopsis": {"text": "Sinopsis falsa", "source": "falso-test"},
            "poster": "https://falso/poster.jpg",
            "idioma": "en",
            "paises": ["US"],
            "rating_imdb": {"rating": 1.0, "votes": 1},  # NO debe pisar el 9.3 del CSV
        }


class TestScrapear(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        import_csv(FIXTURE, self.db_path)
        self.prov = ProveedorFalso()

    def tearDown(self):
        self.tmp.cleanup()

    def test_rellena_huecos_con_procedencia(self):
        r = enriquecer(self.db_path, "tt0111161", self.prov)
        self.assertIn("cast", r["rellenados"])
        self.assertIn("sinopsis", r["rellenados"])
        conn = get_connection(self.db_path)
        try:
            reparto = conn.execute(
                "SELECT p.name, c.source FROM title_cast c "
                "JOIN people p ON p.id = c.person_id WHERE c.tt = 'tt0111161'").fetchone()
            self.assertEqual(tuple(reparto), ("Tim Robbins", "falso-test"))
            huecos = {h["campo"] for h in listar_huecos(self.db_path, "tt0111161")}
            self.assertNotIn("cast", huecos)
            self.assertNotIn("sinopsis", huecos)
        finally:
            conn.close()

    def test_no_pisa_rating_del_csv_ni_tu_nota(self):
        enriquecer(self.db_path, "tt0068646", self.prov)
        conn = get_connection(self.db_path)
        try:
            t = conn.execute(
                "SELECT imdb_rating FROM titles WHERE tt = 'tt0068646'").fetchone()
            self.assertEqual(t["imdb_rating"], 9.2)  # el 1.0 falso no entra
            u = conn.execute(
                "SELECT my_rating FROM user_state WHERE tt = 'tt0068646'").fetchone()
            self.assertEqual(u["my_rating"], 10)
        finally:
            conn.close()

    def test_fallo_de_un_titulo_no_aborta_el_lote(self):
        ok = enriquecer(self.db_path, "tt0111161", self.prov)
        self.assertNotIn("error", ok)
        with self.assertRaises(RuntimeError):
            enriquecer(self.db_path, "tt0000000", self.prov)
        # El título bueno sigue completo aunque otro falle.
        huecos = {h["campo"] for h in listar_huecos(self.db_path, "tt0111161")}
        self.assertNotIn("cast", huecos)

    def test_dry_run_no_escribe(self):
        enriquecer(self.db_path, "tt0111161", self.prov, dry_run=True)
        huecos = {h["campo"] for h in listar_huecos(self.db_path, "tt0111161")}
        self.assertIn("cast", huecos)


if __name__ == "__main__":
    unittest.main()
