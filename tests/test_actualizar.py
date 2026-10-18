"""Task 2: ingesta idempotente, cuarentena y no destructiva."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import get_connection, init_db
from src.sync import import_csv

FIXTURE = ROOT / "tests" / "fixtures" / "mini.csv"


class TestActualizar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"

    def tearDown(self):
        self.tmp.cleanup()

    def test_importa_nuevos_y_manda_sin_tt_a_cuarentena(self):
        resumen = import_csv(FIXTURE, self.db_path)
        self.assertEqual(resumen["total"], 4)
        self.assertEqual(resumen["nuevos"], 3)
        self.assertEqual(resumen["cuarentena"], 1)
        conn = get_connection(self.db_path)
        try:
            n = conn.execute("SELECT COUNT(*) AS n FROM titles").fetchone()["n"]
            self.assertEqual(n, 3)
            q = conn.execute("SELECT motivo FROM import_quarantine").fetchone()
            self.assertEqual(q["motivo"], "tt_invalido_o_ausente")
        finally:
            conn.close()

    def test_reimport_idempotente_sin_duplicados(self):
        r1 = import_csv(FIXTURE, self.db_path)
        r2 = import_csv(FIXTURE, self.db_path)
        self.assertEqual(r2["nuevos"], 0)
        self.assertEqual(r2["actualizados"], 0)
        self.assertEqual(r2["diffs"], 0)
        self.assertGreater(r1["diffs"], 0)
        conn = get_connection(self.db_path)
        try:
            n = conn.execute("SELECT COUNT(*) AS n FROM titles").fetchone()["n"]
            self.assertEqual(n, 3)
        finally:
            conn.close()

    def test_vacio_en_csv_no_borra_enriquecimiento(self):
        import_csv(FIXTURE, self.db_path)
        conn = get_connection(self.db_path)
        conn.execute(
            "UPDATE titles SET synopsis = ?, poster_url = ? WHERE tt = 'tt0111161'",
            ("Sinopsis añadida a mano", "https://ejemplo/poster.jpg"))
        conn.commit()
        conn.close()
        # Reimportar: el CSV no trae sinopsis/poster; deben seguir intactos.
        resumen = import_csv(FIXTURE, self.db_path)
        self.assertEqual(resumen["actualizados"], 0)
        conn = get_connection(self.db_path)
        try:
            fila = conn.execute(
                "SELECT synopsis, poster_url FROM titles WHERE tt = 'tt0111161'"
            ).fetchone()
            self.assertEqual(fila["synopsis"], "Sinopsis añadida a mano")
            self.assertEqual(fila["poster_url"], "https://ejemplo/poster.jpg")
        finally:
            conn.close()

    def test_rating_vacio_no_borra_tu_nota(self):
        import_csv(FIXTURE, self.db_path)
        # Simular CSV posterior donde El padrino pierde su nota (vacío).
        otro = Path(self.tmp.name) / "otro.csv"
        lineas = FIXTURE.read_text(encoding="utf-8").splitlines()
        # Vaciar Your Rating de la fila de El padrino (últimas 2 columnas).
        for i, ln in enumerate(lineas):
            if "tt0068646" in ln:
                lineas[i] = ln.replace(",10,2026-09-12", ",,")
        otro.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        import_csv(otro, self.db_path)
        conn = get_connection(self.db_path)
        try:
            fila = conn.execute(
                "SELECT my_rating FROM user_state WHERE tt = 'tt0068646'"
            ).fetchone()
            self.assertEqual(fila["my_rating"], 10)
        finally:
            conn.close()

    def test_generos_y_directores_se_guardan(self):
        import_csv(FIXTURE, self.db_path)
        conn = get_connection(self.db_path)
        try:
            generos = [r["genre"] for r in conn.execute(
                "SELECT genre FROM title_genres WHERE tt = 'tt0068646' ORDER BY genre")]
            self.assertEqual(generos, ["Crimen", "Drama"])
            dirs = [r["name"] for r in conn.execute(
                "SELECT p.name FROM title_credits c JOIN people p ON p.id = c.person_id "
                "WHERE c.tt = 'tt0111161' AND c.role = 'director'")]
            self.assertEqual(dirs, ["Frank Darabont"])
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
