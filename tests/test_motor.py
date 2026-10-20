"""Motor de recomendaciones: perfil, antiperfil, saga y similitud textual.

El fixture tiene 8 títulos valorados y 4 pendientes, con las notas montadas
para que cada capa del motor tenga un caso claro:

  - Terror te gusta mucho (media 8.5) y Comedia te sale flojo (5.5).
  - Elena Vasquez es tu director de confianza; Paula Soto, el contrario.
  - "Acción" tiene una sola muestra valorada: no debe contar como preferencia.
  - IMDb te gana en Comedia: es antiperfil.
  - Una saga une una valorada con una pendiente.
  - Una pendiente comparte casi todo el vocabulario de una valorada con un 9.
"""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import get_connection
from src.motor import _tokens, indice_sinopsis, perfil, recomendar
from src.sync import import_csv

FIXTURE = ROOT / "tests" / "fixtures" / "motor.csv"

# La sinopsis de tt9000022 comparte vocabulario con las valoradas con 9
# (Estación Once): por eso debe aparecer el motivo de similitud.
SINopsis = {
    "tt9000011": "Una niebla espesa cubre el pueblo y esconde lo que ocurre en la casa.",
    "tt9000012": "La niebla y el secreto se esconden tras la puerta de la casa.",
    "tt9000013": "Una nave parte hacia el cielo de hierro con una misión imposible.",
    "tt9000014": "Una nave y su estación sobreviven en el espacio cuando el motor del reactor falla.",
    "tt9000015": "Un mar de polvo cubre el planeta y la expedición busca agua.",
    "tt9000016": "Una boda de invierno reúne a la familia y exhale los conflictos.",
    "tt9000017": "El vermut del norte se sirve en una barra mientras se habla de negocios.",
    "tt9000018": "Un puerto, un canto y una familia que espera a quien no vuelve.",
    "tt9000019": "Una cripta de sal esconde un misterio de terror bajo la iglesia.",
    "tt9000020": "Una señal llega desde el espacio exterior y nadie contesta.",
    "tt9000021": "Un martes cualquiera con sus planes triviales.",
    "tt9000022": "Una nave llega a una estación y el motor del reactor falla: la luz revela el secreto.",
}

ACTORES = {
    "tt9000011": ["Rita Sol"],
    "tt9000012": ["Rita Sol"],
    "tt9000018": ["Rita Sol"],
    "tt9000019": ["Rita Sol"],
    "tt9000006": ["Bruno Cid"],
    "tt9000007": ["Bruno Cid"],
    "tt9000021": ["Bruno Cid"],
}

COLECCIONES = {
    "tt9000014": (2344, "Saga Orbital"),
    "tt9000020": (2344, "Saga Orbital"),
}


class TestMotor(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_path = Path(self.tmp.name) / "test.db"
        import_csv(FIXTURE, self.db_path)
        conn = sqlite3.connect(self.db_path)
        try:
            for tt, texto in SINopsis.items():
                conn.execute("UPDATE titles SET synopsis = ? WHERE tt = ?", (texto, tt))
            for tt, actores in ACTORES.items():
                for orden, nombre in enumerate(actores, start=1):
                    conn.execute(
                        "INSERT OR IGNORE INTO people (name) VALUES (?)", (nombre,))
                    pid = conn.execute(
                        "SELECT id FROM people WHERE name = ?", (nombre,)).fetchone()[0]
                    conn.execute(
                        "INSERT OR IGNORE INTO title_cast "
                        "(tt, person_id, character_name, cast_order) VALUES (?, ?, '', ?)",
                        (tt, pid, orden))
            for tt, (cid, nombre) in COLECCIONES.items():
                conn.execute(
                    "INSERT OR REPLACE INTO title_collections "
                    "(tt, collection_id, collection_name, source) VALUES (?, ?, ?, 'test')",
                    (tt, cid, nombre))
            conn.commit()
        finally:
            conn.close()
        self.conn = get_connection(self.db_path)
        self.addCleanup(self.conn.close)

    # ------------------------------------------------------------- perfil

    def test_perfil_calcula_lift_sobre_la_media_global(self):
        p = perfil(self.conn)
        self.assertEqual(p["global"], 7.5)
        self.assertEqual(p["n_valoradas"], 8)
        terror = p["facetas"]["genero"]["Terror"]
        self.assertEqual(terror["n"], 2)
        self.assertAlmostEqual(terror["media"], 8.5)
        self.assertAlmostEqual(terror["lift"], 1.0)
        comedia = p["facetas"]["genero"]["Comedia"]
        self.assertAlmostEqual(comedia["lift"], -2.0)

    def test_faceta_con_una_sola_muestra_no_cuenta(self):
        p = perfil(self.conn)
        # "Acción" solo aparece en un título valorado: es ruido, no preferencia.
        self.assertNotIn("Acción", p["facetas"].get("genero", {}))
        # "Misterio" solo está en pendientes: sin muestras valoradas, no hay perfil.
        self.assertNotIn("Misterio", p["facetas"].get("genero", {}))
        # Los 90 tienen 3 valoradas: sí cuentan.
        self.assertIn("1990", p["facetas"]["decada"])

    def test_antiprofil_detecta_donde_imdb_te_gana(self):
        p = perfil(self.conn)
        self.assertIn("genero:Comedia", p["antiperfil"])
        self.assertNotIn("genero:Terror", p["antiperfil"])

    def test_perfil_vacio_sin_titulos_valorados(self):
        conn = get_connection(self.db_path)
        try:
            conn.execute("UPDATE user_state SET my_rating = NULL")
            conn.commit()
            p = perfil(conn)
            self.assertEqual(p["n_valoradas"], 0)
            self.assertEqual(p["facetas"], {})
        finally:
            conn.close()

    # ---------------------------------------------------------- similitud

    def test_tokens_quitan_acentos_y_stopwords(self):
        tokens = _tokens("La acción, el género y la noche")
        self.assertIn("accion", tokens)
        self.assertIn("genero", tokens)
        self.assertNotIn("la", tokens)
        self.assertNotIn("el", tokens)

    def test_indice_sinopsis_es_estable_entre_ejecuciones(self):
        v1, idf1 = indice_sinopsis(self.conn)
        v2, idf2 = indice_sinopsis(self.conn)
        self.assertEqual(v1, v2)
        self.assertEqual(idf1, idf2)
        self.assertTrue(v1)

    # ------------------------------------------------------------ motor

    def _por_tt(self, resultados):
        return {r["tt"]: r for r in resultados}

    def test_recomienda_solo_pendientes(self):
        resultados = recomendar(self.conn)
        tts = {r["tt"] for r in resultados}
        self.assertEqual(tts, {"tt9000019", "tt9000020", "tt9000021", "tt9000022"})

    def test_el_pendiente_de_comedia_queda_el_ultimo(self):
        resultados = recomendar(self.conn)
        self.assertEqual(resultados[-1]["tt"], "tt9000021")
        self.assertLess(resultados[-1]["score"], 0)

    def test_motivo_de_genero_positivo(self):
        r = self._por_tt(recomendar(self.conn))["tt9000019"]
        motivos = " | ".join(r["razones"])
        self.assertIn("Terror", motivos)
        self.assertIn("te sale alto", motivos)

    def test_motivo_de_genero_negativo(self):
        r = self._por_tt(recomendar(self.conn))["tt9000021"]
        motivos = " | ".join(r["razones"])
        self.assertIn("Comedia", motivos)
        self.assertIn("flojo", motivos)

    def test_antiperfil_aparece_en_los_motivos(self):
        r = self._por_tt(recomendar(self.conn))["tt9000021"]
        motivos = " | ".join(r["razones"])
        self.assertIn("IMDb suele ganarte", motivos)

    def test_regla_de_saga(self):
        r = self._por_tt(recomendar(self.conn))["tt9000020"]
        motivos = " | ".join(r["razones"])
        self.assertIn("Comparte saga con", motivos)
        self.assertIn("Estación Once", motivos)

    def test_similitud_textual_explica_el_parecido(self):
        r = self._por_tt(recomendar(self.conn))["tt9000022"]
        motivos = " | ".join(r["razones"])
        self.assertIn("Se parece a", motivos)

    def test_los_motivos_usan_capas_distintas_cuando_existen(self):
        """Con saga, similitud o antiperfil disponibles, el motivo aparece."""
        from src.motor import _elegir_motivos
        puntos = [
            (1.0, "afinidad", "genero:Terror", "El género Terror te sale alto"),
            (0.9, "afinidad", "director:X", "El director X te sale alto"),
            (1.5, "saga", "saga:Y", "Comparte saga con Y"),
            (-1.0, "antiperfil", "anti:genero:Z", "En el género Z, IMDb suele ganarte"),
        ]
        motivos = _elegir_motivos(puntos)
        self.assertEqual(len(motivos), 3)
        self.assertIn("Comparte saga con Y", motivos)
        self.assertIn("En el género Z, IMDb suele ganarte", motivos)

    def test_no_repite_motivo_de_la_misma_faceta(self):
        from src.motor import _elegir_motivos
        puntos = [
            (1.0, "afinidad", "genero:Terror", "El género Terror te sale alto"),
            (0.9, "afinidad", "genero:Terror", "Otra vez Terror"),
            (0.5, "afinidad", "director:X", "El director X te sale alto"),
        ]
        motivos = _elegir_motivos(puntos)
        self.assertNotIn("Otra vez Terror", motivos)

    def test_director_de_confianza_suma_y_el_contrario_resta(self):
        resultados = self._por_tt(recomendar(self.conn))
        self.assertGreater(resultados["tt9000022"]["score"], 0)
        self.assertLess(resultados["tt9000021"]["score"], 0)

    def test_encaje_entre_0_y_100(self):
        for r in recomendar(self.conn):
            self.assertGreaterEqual(r["encaje"], 0)
            self.assertLessEqual(r["encaje"], 100)

    def test_maximo_tres_motivos(self):
        for r in recomendar(self.conn):
            self.assertLessEqual(len(r["razones"]), 3)
            self.assertTrue(r["razones"])

    def test_es_determinista(self):
        primero = recomendar(self.conn)
        segundo = recomendar(self.conn)
        self.assertEqual(primero, segundo)

    def test_sin_pendientes_no_devuelve_nada(self):
        conn = get_connection(self.db_path)
        try:
            conn.execute(
                "UPDATE user_state SET my_rating = 7 WHERE my_rating IS NULL")
            conn.commit()
            self.assertEqual(recomendar(conn), [])
        finally:
            conn.close()

    def test_limite_recorta_la_lista(self):
        self.assertEqual(len(recomendar(self.conn, limite=2)), 2)

    def test_no_recomienda_lo_que_no_puede_justificar(self):
        """Sin señales, el pendiente no entra: un motivo vacío no explica nada."""
        conn = get_connection(self.db_path)
        try:
            # Deja un pendiente sin género, director, década ni saga conocida.
            conn.execute(
                "INSERT INTO titles (tt, title_es, title_type, year, imdb_rating) "
                "VALUES ('tt9000099', 'Sin pistas', 'Película', 2031, 9.9)")
            conn.execute(
                "INSERT INTO user_state (tt, watch_status) VALUES ('tt9000099', 'watchlist')")
            conn.commit()
            tts = {r["tt"] for r in recomendar(conn)}
            self.assertNotIn("tt9000099", tts)
        finally:
            conn.close()

    def test_min_muestras_configurable(self):
        p = perfil(self.conn, min_muestras=3)
        self.assertNotIn("Comedia", p["facetas"]["genero"])


if __name__ == "__main__":
    unittest.main()
