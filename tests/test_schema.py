"""Task 1: el esquema base existe, tt es único y las FK están activas."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import get_connection, init_db

EXPECTED_TABLES = {
    "titles", "user_state", "genres", "title_genres", "people",
    "title_credits", "title_cast", "title_countries", "release_dates",
    "series_info", "title_relations", "works_origin", "media_refs",
    "sync_runs", "sync_diffs", "import_quarantine",
}


class TestSchema(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        init_db(self.db_path)
        self.conn = get_connection(self.db_path)

    def tearDown(self):
        self.conn.close()
        self.tmp.cleanup()

    def test_todas_las_tablas_existen(self):
        tablas = {
            r["name"] for r in
            self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        self.assertTrue(EXPECTED_TABLES.issubset(tablas), f"faltan: {EXPECTED_TABLES - tablas}")

    def test_tt_es_clave_primaria_unica(self):
        self.conn.execute(
            "INSERT INTO titles (tt, original_title) VALUES ('tt0111161', 'The Shawshank Redemption')"
        )
        self.conn.commit()
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO titles (tt, original_title) VALUES ('tt0111161', 'Duplicado')"
            )

    def test_tt_con_formato_invalido_se_rechaza(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("INSERT INTO titles (tt) VALUES ('no-es-tt')")

    def test_fk_user_state_exige_titulo(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute(
                "INSERT INTO user_state (tt, my_rating) VALUES ('tt9999999', 9)"
            )

    def test_insercion_minima_titulo_mas_estado(self):
        self.conn.execute(
            "INSERT INTO titles (tt, original_title, title_type) "
            "VALUES ('tt0068646', 'The Godfather', 'Película')"
        )
        self.conn.execute(
            "INSERT INTO user_state (tt, my_rating, watch_status) "
            "VALUES ('tt0068646', 10, 'rated')"
        )
        self.conn.commit()
        fila = self.conn.execute(
            "SELECT t.original_title, u.my_rating FROM titles t "
            "JOIN user_state u ON u.tt = t.tt WHERE t.tt = 'tt0068646'"
        ).fetchone()
        self.assertEqual(fila["original_title"], "The Godfather")
        self.assertEqual(fila["my_rating"], 10)

    def test_init_db_es_idempotente(self):
        init_db(self.db_path)  # segunda aplicación no rompe nada
        n = self.conn.execute("SELECT COUNT(*) AS n FROM titles").fetchone()["n"]
        self.assertEqual(n, 0)


if __name__ == "__main__":
    unittest.main()
