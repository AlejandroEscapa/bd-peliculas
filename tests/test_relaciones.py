"""Task 5: universos/secuelas/remakes y obras origen (libros, cómics, manga)."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import get_connection
from src.relaciones import add_origin, add_relation, saga_de
from src.sync import import_csv

FIXTURE = ROOT / "tests" / "fixtures" / "mini.csv"


class TestRelaciones(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        import_csv(FIXTURE, self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_relacion_universo_y_consulta_saga(self):
        add_relation(self.db_path, "tt0111161", "tt0068646", "universe", source="test")
        saga = saga_de(self.db_path, "tt0111161")
        self.assertEqual(len(saga), 1)
        self.assertEqual(saga[0]["tt"], "tt0068646")
        # Visible desde el otro extremo también.
        self.assertEqual(len(saga_de(self.db_path, "tt0068646")), 1)

    def test_no_autorrelacion_ni_duplicados(self):
        with self.assertRaises(ValueError):
            add_relation(self.db_path, "tt0111161", "tt0111161", "sequel")
        add_relation(self.db_path, "tt0111161", "tt0068646", "sequel", source="test")
        add_relation(self.db_path, "tt0111161", "tt0068646", "sequel", source="test")
        conn = get_connection(self.db_path)
        try:
            n = conn.execute("SELECT COUNT(*) AS n FROM title_relations").fetchone()["n"]
            self.assertEqual(n, 1)
        finally:
            conn.close()

    def test_tipo_desconocido_se_rechaza(self):
        with self.assertRaises(ValueError):
            add_relation(self.db_path, "tt0111161", "tt0068646", "invento")

    def test_obra_origen_libro(self):
        add_origin(self.db_path, "tt0111161", "Rita Hayworth and Shawshank Redemption",
                   "book", author="Stephen King", source="test")
        conn = get_connection(self.db_path)
        try:
            fila = conn.execute("SELECT * FROM works_origin WHERE tt = 'tt0111161'").fetchone()
            self.assertEqual((fila["work_type"], fila["author"]), ("book", "Stephen King"))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
