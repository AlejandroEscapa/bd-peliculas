"""Task 7: vistas KPI con datos reales y backup que restaura sin pérdidas."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import get_connection
from src.respaldo import backup, restore
from src.sync import import_csv

FIXTURE = ROOT / "tests" / "fixtures" / "mini.csv"


class TestVistas(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        import_csv(FIXTURE, self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_top_rated_devuelve_tus_notas_primero(self):
        conn = get_connection(self.db_path)
        try:
            filas = conn.execute("SELECT tt, my_rating FROM v_top_rated").fetchall()
            self.assertEqual(len(filas), 2)  # 2 valoradas en el fixture
            self.assertEqual(filas[0]["tt"], "tt0068646")  # nota 10
            self.assertEqual(filas[0]["my_rating"], 10)
        finally:
            conn.close()

    def test_generos_fav_agrupa(self):
        conn = get_connection(self.db_path)
        try:
            filas = conn.execute("SELECT genero FROM v_generos_fav").fetchall()
            generos = {f["genero"] for f in filas}
            self.assertTrue({"Crimen", "Drama"}.issubset(generos))
        finally:
            conn.close()

    def test_pendientes_son_las_sin_nota(self):
        conn = get_connection(self.db_path)
        try:
            filas = conn.execute("SELECT tt FROM v_pendientes").fetchall()
            self.assertEqual([f["tt"] for f in filas], ["tt0111161"])
        finally:
            conn.close()

    def test_backup_restaura_sin_perdidas(self):
        destino = Path(self.tmp.name) / "backups"
        mani = backup(self.db_path, destino)
        self.assertEqual(mani["tablas"].get("titles"), 3)
        dump = destino / mani["dump"]
        self.assertTrue(dump.exists())
        restaurada = Path(self.tmp.name) / "restored.db"
        restore(dump, restaurada)
        conn = get_connection(restaurada)
        try:
            n = conn.execute("SELECT COUNT(*) AS n FROM titles").fetchone()["n"]
            self.assertEqual(n, 3)
            nota = conn.execute(
                "SELECT my_rating FROM user_state WHERE tt = 'tt0068646'").fetchone()
            self.assertEqual(nota["my_rating"], 10)
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
