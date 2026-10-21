"""Semilla: base de trabajo reproducible a partir del snapshot publicado.

Comprueba lo que de verdad importa de una semilla: que sea determinista
(la misma entrada da siempre la misma base), que tenga la estructura que el
panel necesita (géneros, reparto, directores, colecciones) y que no se
parezca nada de tu base real cuando pides notas sintéticas.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.semilla import construir_semilla
from src.db import get_connection

SNAPSHOT_MINIMO = """<!DOCTYPE html><html><body>
<script type="application/json" id="catalogo-data">{datos}</script>
</body></html>"""

CATALOGO = {
    "tt0000001": {
        "titulo": "Harry Potter y la piedra filosofal", "original": "Harry Potter 1",
        "url": "u1", "tipo": "Película", "year": 2001, "imdb": 7.6, "nota": 9,
        "duracion": 152, "sinopsis": "Un niño descubre que es mago y va al colegio.",
        "poster": "p1", "generos": ["Fantasía", "Aventura"],
        "directores": ["Chris Columbus"], "reparto": [{"nombre": "Daniel Radcliffe", "personaje": "Harry"}],
        "paises": ["GB"]},
    "tt0000002": {
        "titulo": "Harry Potter y la cámara secreta", "original": "Harry Potter 2",
        "url": "u2", "tipo": "Película", "year": 2002, "imdb": 7.4, "nota": None,
        "duracion": 153, "sinopsis": "El colegio tiene una cámara y un monstruo.",
        "poster": "p2", "generos": ["Fantasía", "Misterio"],
        "directores": ["Chris Columbus"], "reparto": [{"nombre": "Daniel Radcliffe", "personaje": "Harry"}],
        "paises": ["GB"]},
    "tt0000003": {
        "titulo": "Una peli suelta", "original": "A lonely film",
        "url": "u3", "tipo": "Película", "year": 2010, "imdb": 5.0, "nota": 3,
        "duracion": 90, "sinopsis": "Nadie la ve y nadie la recuerda.",
        "poster": "", "generos": ["Terror"], "directores": [], "reparto": [], "paises": []},
}


class TestSemilla(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.snapshot = self.dir / "snapshot.html"
        self.snapshot.write_text(
            SNAPSHOT_MINIMO.format(datos=json.dumps(CATALOGO)), encoding="utf-8")

    def _resumen(self, db_name="semilla.db", **kwargs):
        destino = self.dir / db_name
        resumen = construir_semilla(self.snapshot, destino, **kwargs)
        return destino, resumen

    def _consulta(self, db, sql, params=()):
        conn = get_connection(db)
        try:
            return [dict(r) for r in conn.execute(sql, params)]
        finally:
            conn.close()

    def test_crea_la_estructura_que_necesita_el_panel(self):
        db, resumen = self._resumen()
        self.assertEqual(resumen["titulos"], 3)
        self.assertEqual(self._consulta(db, "SELECT COUNT(*) n FROM title_genres")[0]["n"], 5)
        self.assertEqual(self._consulta(db, "SELECT COUNT(*) n FROM title_cast")[0]["n"], 2)
        self.assertEqual(self._consulta(db, "SELECT COUNT(*) n FROM title_credits")[0]["n"], 2)
        self.assertEqual(self._consulta(db, "SELECT COUNT(*) n FROM title_countries")[0]["n"], 2)

    def test_detecta_las_sagas_reales(self):
        db, resumen = self._resumen()
        self.assertEqual(resumen["con_coleccion"], 2)  # los dos Harry Potter
        nombres = {r["collection_name"] for r in
                   self._consulta(db, "SELECT DISTINCT collection_name FROM title_collections")}
        self.assertEqual(len(nombres), 1)
        self.assertIn("Harry Potter", nombres.pop())

    def test_es_determinista(self):
        db1, _ = self._resumen("a.db")
        db2, _ = self._resumen("b.db")
        self.assertEqual(
            self._consulta(db1, "SELECT tt, my_rating FROM user_state ORDER BY tt"),
            self._consulta(db2, "SELECT tt, my_rating FROM user_state ORDER BY tt"))
        self.assertEqual(
            self._consulta(db1, "SELECT tt, collection_id FROM title_collections ORDER BY tt"),
            self._consulta(db2, "SELECT tt, collection_id FROM title_collections ORDER BY tt"))

    def test_las_notas_sinteticas_no_son_las_reales(self):
        db, resumen = self._resumen()
        self.assertEqual(resumen["notas"], "sinteticas")
        notas = {r["tt"]: r["my_rating"] for r in
                 self._consulta(db, "SELECT tt, my_rating FROM user_state")}
        for tt, f in CATALOGO.items():
            self.assertNotEqual(notas[tt], f["nota"],
                                f"{tt}: la nota sintetica coincide con la real")
            if notas[tt] is not None:
                self.assertGreaterEqual(notas[tt], 1)
                self.assertLessEqual(notas[tt], 10)

    def test_con_notas_reales_se_reproducen_las_del_snapshot(self):
        db, resumen = self._resumen("reales.db", notas_reales=True)
        self.assertEqual(resumen["notas"], "reales")
        notas = {r["tt"]: r["my_rating"] for r in
                 self._consulta(db, "SELECT tt, my_rating FROM user_state")}
        for tt, f in CATALOGO.items():
            self.assertEqual(notas[tt], f["nota"])

    def test_las_series_tienen_series_info(self):
        db, _ = self._resumen()
        self.assertEqual(
            self._consulta(db, "SELECT COUNT(*) n FROM series_info")[0]["n"], 0)
        # Con una serie, sí.
        catalogo = dict(CATALOGO)
        catalogo["tt0000004"] = dict(CATALOGO["tt0000003"], titulo="Serie de TV", tipo="Serie de TV")
        self.snapshot.write_text(
            SNAPSHOT_MINIMO.format(datos=json.dumps(catalogo)), encoding="utf-8")
        db, _ = self._resumen("serie.db")
        self.assertEqual(
            self._consulta(db, "SELECT COUNT(*) n FROM series_info")[0]["n"], 1)

    def test_no_reescribe_una_base_existente_sin_forzar(self):
        """Seguridad: un --db mal escrito no puede borrar el catálogo real."""
        db, _ = self._resumen()
        conn = get_connection(db)
        try:
            conn.execute("INSERT INTO titles (tt, title_es) VALUES ('tt9999999', 'Mia')")
            conn.commit()
        finally:
            conn.close()
        with self.assertRaises(SystemExit):
            construir_semilla(self.snapshot, db)
        self.assertEqual(
            self._consulta(db, "SELECT COUNT(*) n FROM titles WHERE tt = 'tt9999999'")[0]["n"], 1)

    def test_con_forzar_si_rehace_la_base(self):
        db, _ = self._resumen()
        conn = get_connection(db)
        try:
            conn.execute("INSERT INTO titles (tt, title_es) VALUES ('tt9999999', 'Mia')")
            conn.commit()
        finally:
            conn.close()
        construir_semilla(self.snapshot, db, forzar=True)
        self.assertEqual(
            self._consulta(db, "SELECT COUNT(*) n FROM titles WHERE tt = 'tt9999999'")[0]["n"], 0)


if __name__ == "__main__":
    unittest.main()
