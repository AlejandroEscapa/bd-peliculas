"""Task 3: cada diferencia se detecta, se tipa y se registra sin destruir."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import get_connection
from src.sync import import_csv

FIXTURE = ROOT / "tests" / "fixtures" / "mini.csv"


class TestDiffs(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "test.db"
        import_csv(FIXTURE, self.db_path)

    def tearDown(self):
        self.tmp.cleanup()

    def _csv_con_nota(self, tt: str, nota: str, fecha: str) -> Path:
        lineas = FIXTURE.read_text(encoding="utf-8").splitlines()
        for i, ln in enumerate(lineas):
            if tt in ln:
                partes = ln.rsplit(",", 2)
                lineas[i] = f"{partes[0]},{nota},{fecha}"
        p = Path(self.tmp.name) / "cambio.csv"
        p.write_text("\n".join(lineas) + "\n", encoding="utf-8")
        return p

    def test_detecta_cambio_de_rating_10_a_7(self):
        otro = self._csv_con_nota("tt0068646", "7", "2026-10-01")
        resumen = import_csv(otro, self.db_path)
        self.assertEqual(resumen["actualizados"], 1)
        conn = get_connection(self.db_path)
        try:
            d = conn.execute(
                "SELECT campo, anterior, nuevo, tipo FROM sync_diffs "
                "WHERE tt = 'tt0068646' AND campo = 'my_rating' "
                "ORDER BY id DESC LIMIT 1").fetchone()
            self.assertIsNotNone(d)
            self.assertEqual((d["anterior"], d["nuevo"], d["tipo"]), ("10", "7", "rating_cambiado"))
            nota = conn.execute(
                "SELECT my_rating FROM user_state WHERE tt = 'tt0068646'").fetchone()
            self.assertEqual(nota["my_rating"], 7)
        finally:
            conn.close()

    def test_conflicto_protegido_no_sobrescribe_enriquecimiento(self):
        conn = get_connection(self.db_path)
        conn.execute(
            "UPDATE titles SET synopsis = ?, poster_url = ?, "
            "original_lang_iso = ? WHERE tt = 'tt0068646'",
            ("Sinopsis web", "https://x/poster.jpg", "en"))
        conn.commit()
        conn.close()
        # El CSV no trae esos campos: reimportar no los toca ni genera diff sobre ellos.
        import_csv(FIXTURE, self.db_path)
        conn = get_connection(self.db_path)
        try:
            fila = conn.execute(
                "SELECT synopsis, poster_url, original_lang_iso FROM titles "
                "WHERE tt = 'tt0068646'").fetchone()
            self.assertEqual(tuple(fila), ("Sinopsis web", "https://x/poster.jpg", "en"))
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM sync_diffs "
                "WHERE campo IN ('synopsis', 'poster_url', 'original_lang_iso')").fetchone()["n"]
            self.assertEqual(n, 0)
        finally:
            conn.close()

    def test_resumen_del_run_queda_auditado(self):
        conn = get_connection(self.db_path)
        try:
            run = conn.execute(
                "SELECT total_rows, nuevos, en_cuarentena FROM sync_runs "
                "ORDER BY id DESC LIMIT 1").fetchone()
            self.assertEqual((run["total_rows"], run["nuevos"], run["en_cuarentena"]),
                             (4, 3, 1))
        finally:
            conn.close()


if __name__ == "__main__":
    unittest.main()
