"""Colecciones de TMDB (sagas) y relaciones derivadas: cero peticiones extra.

Cubre el camino completo: el proveedor lee `belongs_to_collection` de la
respuesta de detalle que ya se pedía, el scraper lo guarda (incluso cuando no
hay colección, para cerrar el hueco) y las relaciones se derivan localmente.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import get_connection, init_db
from src.huecos import listar_huecos
from src.relaciones import colecciones_de, derivar_relaciones_coleccion, saga_de
from src.scraper import enriquecer

FIXTURE = ROOT / "tests" / "fixtures" / "mini.csv"


class ProveedorFalso:
    """Proveedor mínimo con la forma del protocolo del scraper."""

    nombre = "falso"

    def __init__(self, coleccion):
        self.coleccion = coleccion

    def fetch(self, tt):
        return {"coleccion": self.coleccion}


class TestColecciones(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "test.db"
        init_db(self.db_path)

    def _titulo(self, tt, titulo, anio):
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO titles (tt, title_es, title_type, year) "
                "VALUES (?, ?, 'Película', ?)", (tt, titulo, anio))
            conn.commit()
        finally:
            conn.close()

    def _persona(self, nombre):
        conn = get_connection(self.db_path)
        try:
            conn.execute("INSERT OR IGNORE INTO people (name) VALUES (?)", (nombre,))
            conn.commit()
            return conn.execute(
                "SELECT id FROM people WHERE name = ?", (nombre,)).fetchone()["id"]
        finally:
            conn.close()

    def _credito(self, tt, nombre, rol):
        pid = self._persona(nombre)
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO title_credits (tt, person_id, role) VALUES (?, ?, ?)",
                (tt, pid, rol))
            conn.commit()
        finally:
            conn.close()

    def _cast(self, tt, nombre, orden):
        pid = self._persona(nombre)
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "INSERT OR IGNORE INTO title_cast (tt, person_id, character_name, cast_order) "
                "VALUES (?, ?, '', ?)", (tt, pid, orden))
            conn.commit()
        finally:
            conn.close()

    # --- esquema y version ---

    def test_tabla_de_colecciones_existe_y_version_aplicada(self):
        conn = get_connection(self.db_path)
        try:
            tablas = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("title_collections", tablas)
            versiones = {r["version"] for r in conn.execute(
                "SELECT version FROM schema_version")}
            self.assertIn("0001_base", versiones)
            self.assertIn("0002_colecciones", versiones)
        finally:
            conn.close()

    # --- hueco y cierre ---

    def test_base_de_version_anterior_gana_la_tabla_al_reaplicar_esquema(self):
        """Una base creada antes de la migración se actualiza sin perder datos."""
        conn = get_connection(self.db_path)
        try:
            conn.execute("INSERT INTO titles (tt, title_es) VALUES ('tt0000081', 'Viejo')")
            conn.execute("DROP TABLE title_collections")
            conn.commit()
        finally:
            conn.close()
        init_db(self.db_path)
        conn = get_connection(self.db_path)
        try:
            tablas = {r["name"] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("title_collections", tablas)
            n = conn.execute("SELECT COUNT(*) AS n FROM titles").fetchone()["n"]
            self.assertEqual(n, 1)  # los datos siguen ahí
        finally:
            conn.close()

    def test_hueco_de_coleccion_se_cierra_sin_peticion_extra(self):
        self._titulo("tt0000011", "A", 1999)
        conn = get_connection(self.db_path)
        try:
            huecos = {h["campo"] for h in listar_huecos(self.db_path)}
            self.assertIn("coleccion", huecos)
        finally:
            conn.close()

        # El proveedor dice que no tiene colección: se guarda igualmente.
        r = enriquecer(self.db_path, "tt0000011", ProveedorFalso(None))
        self.assertIn("coleccion", r["rellenados"])

        conn = get_connection(self.db_path)
        try:
            huecos = {h["campo"] for h in listar_huecos(self.db_path)}
            self.assertNotIn("coleccion", huecos)
            fila = conn.execute(
                "SELECT * FROM title_collections WHERE tt = 'tt0000011'").fetchone()
            self.assertIsNotNone(fila)
            self.assertIsNone(fila["collection_id"])
        finally:
            conn.close()

    def test_coleccion_se_guarda_con_id_y_nombre(self):
        self._titulo("tt0000012", "B", 2003)
        enriquecer(self.db_path, "tt0000012",
                   ProveedorFalso({"id": 2344, "nombre": "The Matrix Collection"}))
        conn = get_connection(self.db_path)
        try:
            fila = conn.execute(
                "SELECT * FROM title_collections WHERE tt = 'tt0000012'").fetchone()
            self.assertEqual(fila["collection_id"], 2344)
            self.assertEqual(fila["collection_name"], "The Matrix Collection")
            self.assertEqual(fila["source"], "falso")
        finally:
            conn.close()

    def test_solo_faltantes_no_reescribe_una_coleccion_ya_conocida(self):
        self._titulo("tt0000013", "C", 1999)
        enriquecer(self.db_path, "tt0000013",
                   ProveedorFalso({"id": 2344, "nombre": "The Matrix Collection"}))
        r = enriquecer(self.db_path, "tt0000013",
                       ProveedorFalso({"id": 9999, "nombre": "Otra"}))
        self.assertNotIn("coleccion", r["rellenados"])
        conn = get_connection(self.db_path)
        try:
            fila = conn.execute(
                "SELECT collection_id FROM title_collections WHERE tt = 'tt0000013'"
            ).fetchone()
            self.assertEqual(fila["collection_id"], 2344)
        finally:
            conn.close()

    # --- relaciones derivadas ---

    def test_derivacion_crea_universe_entre_todos_los_pares(self):
        for tt, anio in (("tt0000021", 1999), ("tt0000022", 2003), ("tt0000023", 2021)):
            self._titulo(tt, tt, anio)
            enriquecer(self.db_path, tt,
                       ProveedorFalso({"id": 2344, "nombre": "The Matrix Collection"}))
        res = derivar_relaciones_coleccion(self.db_path)
        self.assertEqual(res["colecciones"], 1)
        self.assertEqual(res["relaciones_nuevas"], 3)  # 3 pares -> universe
        saga = saga_de(self.db_path, "tt0000021")
        self.assertEqual(len(saga), 2)

    def test_secuela_solo_con_protagonista_compartido_y_salto_de_un_ano(self):
        self._titulo("tt0000031", "Primera", 1999)
        self._titulo("tt0000032", "Segunda", 2003)
        for tt in ("tt0000031", "tt0000032"):
            enriquecer(self.db_path, tt,
                       ProveedorFalso({"id": 2344, "nombre": "The Matrix Collection"}))
        # Sin nadie en común: solo universe.
        derivar_relaciones_coleccion(self.db_path)
        tipos = {r["relation_type"] for r in saga_de(self.db_path, "tt0000031")}
        self.assertEqual(tipos, {"universe"})

        # Ahora comparten actor principal.
        self._cast("tt0000031", "Keanu Reeves", 1)
        self._cast("tt0000032", "Keanu Reeves", 1)
        res = derivar_relaciones_coleccion(self.db_path)
        self.assertEqual(res["relaciones_nuevas"], 1)
        conn = get_connection(self.db_path)
        try:
            fila = conn.execute(
                "SELECT * FROM title_relations WHERE from_tt = 'tt0000031' "
                "AND to_tt = 'tt0000032' AND relation_type = 'sequel'").fetchone()
            self.assertIsNotNone(fila)
            self.assertEqual(fila["source"], "tmdb_coleccion")
        finally:
            conn.close()

    def test_secuela_no_se_inventa_entre_titulos_del_mismo_ano(self):
        self._titulo("tt0000041", "A", 2003)
        self._titulo("tt0000042", "B", 2003)
        for tt in ("tt0000041", "tt0000042"):
            enriquecer(self.db_path, tt,
                       ProveedorFalso({"id": 2344, "nombre": "The Matrix Collection"}))
        self._cast("tt0000041", "Actor X", 1)
        self._cast("tt0000042", "Actor X", 1)
        derivar_relaciones_coleccion(self.db_path)
        conn = get_connection(self.db_path)
        try:
            n = conn.execute(
                "SELECT COUNT(*) AS n FROM title_relations WHERE relation_type = 'sequel'"
            ).fetchone()["n"]
            self.assertEqual(n, 0)
        finally:
            conn.close()

    def test_derivacion_es_idempotente(self):
        for tt in ("tt0000051", "tt0000052"):
            self._titulo(tt, tt, 1999)
            enriquecer(self.db_path, tt,
                       ProveedorFalso({"id": 2344, "nombre": "The Matrix Collection"}))
        primero = derivar_relaciones_coleccion(self.db_path)
        segundo = derivar_relaciones_coleccion(self.db_path)
        self.assertEqual(primero["relaciones_nuevas"], 1)
        self.assertEqual(segundo["relaciones_nuevas"], 0)

    def test_colecciones_de_agrupa_con_nota_y_orden(self):
        self._titulo("tt0000061", "Viejo", 1999)
        self._titulo("tt0000062", "Nuevo", 2003)
        for tt in ("tt0000061", "tt0000062"):
            enriquecer(self.db_path, tt,
                       ProveedorFalso({"id": 2344, "nombre": "The Matrix Collection"}))
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "INSERT INTO user_state (tt, my_rating, watch_status) "
                "VALUES ('tt0000062', 9, 'rated')")
            conn.commit()
        finally:
            conn.close()
        grupos = colecciones_de(self.db_path)
        self.assertEqual(len(grupos), 1)
        partes = grupos[0]["titulos"]
        self.assertEqual([p["tt"] for p in partes], ["tt0000061", "tt0000062"])
        self.assertIsNone(partes[0]["my_rating"])
        self.assertEqual(partes[1]["my_rating"], 9)

    def test_titulos_sin_coleccion_no_generan_grupos(self):
        self._titulo("tt0000071", "Solitario", 1999)
        enriquecer(self.db_path, "tt0000071", ProveedorFalso(None))
        self.assertEqual(colecciones_de(self.db_path), [])
        res = derivar_relaciones_coleccion(self.db_path)
        self.assertEqual(res["colecciones"], 0)
        self.assertEqual(res["relaciones_nuevas"], 0)


class TestProveedorTMDBColeccion(unittest.TestCase):
    """El proveedor lee belongs_to_collection de la respuesta que ya pide."""

    def test_coleccion_leida_del_detalle(self):
        from src.proveedores.tmdb import ProveedorTMDB
        prov = ProveedorTMDB(bearer="TEST")
        find = {"movie_results": [{"id": 603, "overview": "S"}], "tv_results": []}
        detalle = {"overview": "S", "runtime": 136,
                   "belongs_to_collection": {"id": 2344, "name": "The Matrix Collection"}}
        credits = {"cast": [], "crew": []}
        with patch.object(ProveedorTMDB, "_get_json", side_effect=[find, detalle, credits]):
            datos = prov.fetch("tt0133093")
        self.assertEqual(datos["coleccion"]["id"], 2344)
        self.assertEqual(datos["coleccion"]["nombre"], "The Matrix Collection")

    def test_sin_coleccion_devuelve_none(self):
        from src.proveedores.tmdb import ProveedorTMDB
        prov = ProveedorTMDB(bearer="TEST")
        find = {"movie_results": [{"id": 603, "overview": "S"}], "tv_results": []}
        detalle = {"overview": "S", "runtime": 136}
        credits = {"cast": [], "crew": []}
        with patch.object(ProveedorTMDB, "_get_json", side_effect=[find, detalle, credits]):
            datos = prov.fetch("tt0133093")
        self.assertIsNone(datos["coleccion"])


if __name__ == "__main__":
    unittest.main()
