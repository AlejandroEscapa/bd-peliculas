"""Task 4: un título recién importado muestra huecos; al rellenar, desaparecen."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import get_connection
from src.huecos import listar_huecos
from src.sync import import_csv

FIXTURE = ROOT / "tests" / "fixtures" / "mini.csv"


class TestHuecos(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        import_csv(FIXTURE, self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_recien_importado_tiene_cast_sinopsis_poster(self):
        huecos = {h["campo"] for h in listar_huecos(self.db_path, "tt0111161")}
        self.assertTrue({"cast", "sinopsis", "poster"}.issubset(huecos))

    def test_al_rellenar_desaparecen_los_huecos(self):
        conn = get_connection(self.db_path)
        conn.execute(
            "UPDATE titles SET synopsis = 'S', poster_url = 'https://x/p.jpg', "
            "original_lang_iso = 'en', spain_release_date = '1995-02-24', "
            "runtime_min_exact = 142, budget_amount = 25000000, "
            "box_office_amount = 28000000 WHERE tt = 'tt0111161'")
        conn.execute("INSERT INTO people (name) VALUES ('Tim Robbins')")
        pid = conn.execute("SELECT id FROM people WHERE name = 'Tim Robbins'").fetchone()["id"]
        conn.execute(
            "INSERT INTO title_cast (tt, person_id, character_name, cast_order, source) "
            "VALUES ('tt0111161', ?, 'Andy Dufresne', 1, 'test')", (pid,))
        conn.execute(
            "INSERT INTO title_credits (tt, person_id, role, source) "
            "VALUES ('tt0111161', ?, 'writer', 'test')", (pid,))
        conn.execute("INSERT INTO title_countries (tt, country_code) VALUES ('tt0111161', 'US')")
        conn.commit()
        conn.close()
        huecos = {h["campo"] for h in listar_huecos(self.db_path, "tt0111161")}
        for campo in ("cast", "credits_extra", "idioma", "paises", "estreno_es",
                      "duracion_exacta", "sinopsis", "poster", "presupuesto", "taquilla"):
            self.assertNotIn(campo, huecos)

    def test_serie_pide_serie_info_y_pelicula_no(self):
        huecos_serie = {h["campo"] for h in listar_huecos(self.db_path, "tt2098220")}
        self.assertIn("serie_info", huecos_serie)
        huecos_peli = {h["campo"] for h in listar_huecos(self.db_path, "tt0111161")}
        self.assertNotIn("serie_info", huecos_peli)


if __name__ == "__main__":
    unittest.main()
