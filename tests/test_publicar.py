"""Publicar: el snapshot commiteado no se degrada en silencio.

El riesgo real de este repo: regenerar el panel desde una base a medias y
publicar un HTML con menos datos. Estos tests comprueban que el guard lo ve
y que no toca nada.
"""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.publicar import comparar, metricas_de
from src.db import get_connection
from src.sync import import_csv

CSV = """Position,Const,Created,Modified,Description,Title,Original Title,URL,Title Type,IMDb Rating,Runtime (mins),Year,Genres,Num Votes,Release Date,Directors,Your Rating,Date Rated
1,tt9000101,2026-01-01,2026-01-01,,"Uno","One",https://www.imdb.com/title/tt9000101/,Película,7.0,100,2001,"Drama",1000,2001-01-01,"Director Uno",8,2026-01-02
2,tt9000102,2026-01-01,2026-01-01,,"Dos","Two",https://www.imdb.com/title/tt9000102/,Película,6.5,110,2002,"Comedia",900,2002-01-01,"Director Dos",7,2026-01-03
"""

CSV_CORTO = """Position,Const,Created,Modified,Description,Title,Original Title,URL,Title Type,IMDb Rating,Runtime (mins),Year,Genres,Num Votes,Release Date,Directors,Your Rating,Date Rated
1,tt9000101,2026-01-01,2026-01-01,,"Uno","One",https://www.imdb.com/title/tt9000101/,Película,7.0,100,2001,"Drama",1000,2001-01-01,"Director Uno",8,2026-01-02
"""


class TestPublicar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)

    def _db(self, nombre, csv_texto=CSV):
        db = self.dir / nombre
        csv = self.dir / f"{nombre}.csv"
        csv.write_text(csv_texto, encoding="utf-8")
        import_csv(csv, db)
        return db

    def _generar(self, db, salida):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "generar_vista.py"),
             "--db", str(db), "--salida", str(salida)],
            cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return salida

    def test_metricas_lee_lo_que_importa(self):
        db = self._db("a.db")
        salida = self._generar(db, self.dir / "a.html")
        m = metricas_de(salida)
        self.assertEqual(m["titulos"], 2)
        self.assertEqual(m["valoradas"], 2)
        self.assertEqual(m["con_generos"], 2)

    def test_comparar_detecta_que_no_se_ha_perdido_nada(self):
        db = self._db("b.db")
        salida = self._generar(db, self.dir / "b.html")
        informe = comparar(salida, salida)
        self.assertEqual(informe["pierde"], [])
        self.assertEqual(informe["gana"], [])

    def test_comparar_detecta_perdidas(self):
        grande = self._generar(self._db("c.db"), self.dir / "c.html")
        pequeno = self._generar(self._db("d.db", CSV_CORTO), self.dir / "d.html")
        informe = comparar(pequeno, grande)
        self.assertTrue(informe["pierde"])
        self.assertTrue(any("títulos: 2 -> 1" in p for p in informe["pierde"]))

    def test_el_script_no_publica_un_snapshot_que_pierde_datos(self):
        """El guard de punta a punta: sale con codigo 3 y no toca el publicado."""
        grande = self._generar(self._db("e.db"), self.dir / "e.html")
        pequeno_db = self._db("f.db", CSV_CORTO)
        antes = grande.read_text(encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "publicar.py"),
             "--db", str(pequeno_db), "--salida", str(grande),
             "--sin-backup"],
            cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 3, proc.stdout + proc.stderr)
        self.assertIn("PERDIDAS", proc.stdout)
        self.assertEqual(grande.read_text(encoding="utf-8"), antes,
                         "el snapshot publicado no debe cambiar")

    def test_en_dry_run_no_se_toca_nada(self):
        db = self._db("g.db")
        salida = self._generar(db, self.dir / "g.html")
        antes = salida.read_text(encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "publicar.py"),
             "--db", str(db), "--salida", str(salida), "--dry-run", "--sin-backup"],
            cwd=str(ROOT), capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(salida.read_text(encoding="utf-8"), antes)

    def test_el_snapshot_publicado_no_se_toca_si_el_generador_falla(self):
        db = self._db("h.db")
        salida = self._generar(db, self.dir / "h.html")
        antes = salida.read_text(encoding="utf-8")
        # Base rota: el generador falla y nada debe cambiar.
        roto = self.dir / "roto.db"
        roto.write_bytes(b"esto no es una base de datos")
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "publicar.py"),
             "--db", str(roto), "--salida", str(salida), "--sin-backup"],
            cwd=str(ROOT), capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(salida.read_text(encoding="utf-8"), antes)


if __name__ == "__main__":
    unittest.main()
