"""Panel HTML: contiene la lista completa y las secciones KPI."""
import re
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.generar_vista import generar
from src.sync import import_csv

FIXTURE = ROOT / "tests" / "fixtures" / "mini.csv"


class TestVistaHtml(unittest.TestCase):
    def _generar_con_fixture(self, *, poster=None, sin_notas=False):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / "test.db"
        import_csv(FIXTURE, db_path)
        conn = sqlite3.connect(db_path)
        if poster:
            conn.execute("UPDATE titles SET poster_url = ? WHERE tt = 'tt0068646'", (poster,))
        if sin_notas:
            conn.execute("UPDATE user_state SET my_rating = NULL")
        conn.commit()
        conn.close()
        return generar(db_path)

    def _bloque_posters(self, pagina):
        inicio = pagina.index('class="poster-grid"')
        return pagina[inicio:pagina.index("</section>", inicio)]

    def test_poster_strip_solo_valoradas(self):
        bloque = self._bloque_posters(self._generar_con_fixture())
        self.assertEqual(bloque.count('class="poster-card'), 2)
        self.assertIn('data-tt="tt0068646"', bloque)
        self.assertIn('data-tt="tt2098220"', bloque)

    def test_poster_sin_url_usa_iniciales(self):
        bloque = self._bloque_posters(self._generar_con_fixture())
        self.assertIn("poster-fallback", bloque)
        self.assertIn(">EP<", bloque)

    def test_poster_usa_url(self):
        bloque = self._bloque_posters(
            self._generar_con_fixture(poster="https://example.com/padrino.jpg"))
        self.assertIn('src="https://example.com/padrino.jpg"', bloque)
        self.assertIn('alt="Póster de El padrino"', bloque)

    def test_sin_valoradas_muestra_estado_vacio(self):
        bloque = self._bloque_posters(self._generar_con_fixture(sin_notas=True))
        self.assertIn("Aún no has valorado nada.", bloque)
        self.assertEqual(bloque.count('class="poster-card'), 0)

    def test_poster_escapa_html(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / "test.db"
        import_csv(FIXTURE, db_path)
        conn = sqlite3.connect(db_path)
        conn.execute("UPDATE titles SET title_es = '<script>alert(1)</script>' WHERE tt = 'tt0068646'")
        conn.commit()
        conn.close()
        bloque = self._bloque_posters(generar(db_path))
        self.assertNotIn("<script>alert(1)</script>", bloque)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", bloque)

    def test_catalogo_con_campos_de_filtro(self):
        pagina = self._generar_con_fixture()
        self.assertIn('id="catalogo-data"', pagina)
        for campo in ('"titulo"', '"tipo"', '"year"', '"nota"', '"imdb"',
                      '"fecha"', '"estado"', '"duracion"', '"sinopsis"',
                      '"poster"', '"sin_sinopsis"', '"sin_reparto"',
                      '"diferencia"', '"reparto"', '"directores"',
                      '"paises"', '"generos"'):
            self.assertIn(campo, pagina)

    def test_tablas_llevan_data_label(self):
        pagina = self._generar_con_fixture()
        inicio = pagina.index('id="tabla-top"')
        bloque = pagina[inicio:pagina.index("</table>", inicio)]
        celdas = re.findall(r"<td[^>]*>", bloque)
        self.assertTrue(celdas)
        self.assertTrue(all("data-label=" in celda for celda in celdas))

    def test_css_responsive_y_controles_de_filtro(self):
        pagina = self._generar_con_fixture()
        for marcador in ("@container", "clamp(", "100dvh", "[hidden]",
                         "prefers-reduced-motion", "env(safe-area-inset-bottom)"):
            self.assertIn(marcador, pagina)
        self.assertGreaterEqual(pagina.count('class="filtro-btn"'), 10)
        for marcador in ('data-kpi="media"', 'data-seccion="top"',
                         'aria-haspopup="dialog"', 'class="filtro-panel"'):
            self.assertIn(marcador, pagina)

    def test_ficha_sinopsis_al_final_y_ancho_completo(self):
        pagina = self._generar_con_fixture()
        inicio = pagina.index('<template id="ficha-plantilla"')
        plantilla = pagina[inicio:pagina.index("</template>", inicio)]
        self.assertLess(plantilla.index('class="ficha-cabecera"'),
                        plantilla.index('class="ficha-sinopsis'))
        self.assertIn('class="ficha-sinopsis bloque ancho-completo"', plantilla)
        self.assertIn('id="ficha-sinopsis-texto"', plantilla)
        self.assertIn('id="ficha-leer-mas"', plantilla)

    def test_ficha_plegable_en_movil(self):
        pagina = self._generar_con_fixture()
        for marcador in ("-webkit-line-clamp", "aria-expanded", "Leer más"):
            self.assertIn(marcador, pagina)

    def test_catalogo_escapa_cierre_de_script(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / "test.db"
        import_csv(FIXTURE, db_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE titles SET synopsis = '</script><script>alert(1)</script>' "
            "WHERE tt = 'tt0068646'")
        conn.commit()
        conn.close()
        pagina = generar(db_path)
        self.assertNotIn("</script><script>alert(1)", pagina)
        self.assertIn("<\\/script>", pagina)

    def test_marcadores_de_accesibilidad(self):
        pagina = self._generar_con_fixture()
        for marcador in (                         "info.setAttribute('aria-live', 'polite')",
                         'aria-haspopup="listbox"', 'aria-autocomplete="list"',
                         'role="dialog"', 'aria-modal="true"'):
            self.assertIn(marcador, pagina)

    def test_motor_de_filtros_y_paginador(self):
        pagina = self._generar_con_fixture()
        self.assertNotIn('id="indice-data"', pagina)
        for marcador in ("montarPaginador", "sessionStorage",
                         "db-peliculas:filtros:v1", "renderSeccion",
                         "aria-live", "alternarFaceta"):
            self.assertIn(marcador, pagina)
        self.assertIn("Sin resultados con estos filtros.", pagina)

    def test_estado_vacio_y_sesion_tolerante_a_fallos(self):
        pagina = self._generar_con_fixture()
        self.assertGreaterEqual(pagina.count("Sin resultados con estos filtros."), 2)
        self.assertIn("catch (err)", pagina)
        self.assertIn("sessionStorage.getItem(CLAVE)", pagina)

    def test_lista_completa_con_todos_los_titulos(self):
        tmp = tempfile.TemporaryDirectory()
        db_path = Path(tmp.name) / "test.db"
        import_csv(FIXTURE, db_path)
        pagina = generar(db_path)
        # Los 3 títulos del fixture aparecen en la lista completa.
        for titulo in ("Cadena perpetua", "El padrino", "Hunter"):
            self.assertIn(titulo, pagina)
        # Sin nota se marca NP (no 'pendiente').
        self.assertIn('>NP<', pagina)
        self.assertNotIn('>pendiente<', pagina)
        # Géneros limitados a 3 en muestra (Hunter trae 5: 3 + '...').
        self.assertIn('...', pagina)
        # Secciones KPI presentes.
        for seccion in ("Tus favoritas", "En seguimiento", "Lista completa"):
            self.assertIn(seccion, pagina)
        # Buscador global + ficha overlay.
        for marcador in ('id="buscador-global"', 'id="resultados-global"',
                          'id="overlay"', 'id="ficha-plantilla"', 'abrirFicha'):
            self.assertIn(marcador, pagina)
        tmp.cleanup()

    def test_kpis_exigencia_y_enriquecidos(self):
        pagina = self._generar_con_fixture()
        for marcador in ('data-kpi="exigencia"', 'data-kpi="enriquecidos"',
                         "Exigencia (tú − IMDb)", "Enriquecidos"):
            self.assertIn(marcador, pagina)
        # Exigencia = media de (tu nota - IMDb): (10-9.2 + 9-9.0) / 2 = 0.4
        self.assertIn('<div class="n">0.4</div>', pagina)
        # El fixture no trae sinopsis, póster ni reparto: 0 de 3 enriquecidos.
        self.assertIn('<div class="n">0/3</div>', pagina)

    def _generar_con_colecciones(self, *tts):
        """Página con tts dentro de una misma colección de saga."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / "test.db"
        import_csv(FIXTURE, db_path)
        conn = sqlite3.connect(db_path)
        for tt in tts:
            conn.execute(
                "INSERT OR REPLACE INTO title_collections "
                "(tt, collection_id, collection_name, source) "
                "VALUES (?, 2344, 'Coleccion Test', 'test')", (tt,))
        conn.commit()
        conn.close()
        return generar(db_path)

    def _generar_con_motor(self):
        """Página con el catálogo del motor (valoradas + pendientes con señales)."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        db_path = Path(tmp.name) / "test.db"
        import_csv(ROOT / "tests" / "fixtures" / "motor.csv", db_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "UPDATE titles SET synopsis = ? WHERE tt = 'tt9000020'",
            ("Una nave y su estación sobreviven en el espacio cuando el motor falla.",))
        conn.execute(
            "UPDATE titles SET synopsis = ? WHERE tt = 'tt9000019'",
            ("Una cripta de sal esconde un misterio de terror bajo la iglesia.",))
        conn.execute(
            "INSERT OR REPLACE INTO title_collections "
            "(tt, collection_id, collection_name, source) VALUES "
            "('tt9000020', 2344, 'Saga Orbital', 'test')")
        conn.execute(
            "INSERT OR REPLACE INTO title_collections "
            "(tt, collection_id, collection_name, source) VALUES "
            "('tt9000014', 2344, 'Saga Orbital', 'test')")
        conn.commit()
        conn.close()
        return generar(db_path)

    def test_seccion_para_ti_con_motivos(self):
        pagina = self._generar_con_motor()
        self.assertIn('id="seccion-para-ti"', pagina)
        self.assertIn('id="tabla-para-ti"', pagina)
        self.assertIn("Por qué", pagina)
        # Cada fila lleva su motivo y abre la ficha.
        self.assertIn("data-tt=", pagina)
        self.assertIn("Comparte saga con", pagina)
        self.assertIn("te sale alto", pagina)
        self.assertIn("data-abre-ficha", pagina)

    def test_seccion_para_ti_no_aparece_sin_pendientes_justificables(self):
        """Sin señales no hay sección: mejor vacío que ruido."""
        pagina = self._generar_con_fixture()
        self.assertNotIn('id="seccion-para-ti"', pagina)

    def test_coleccion_en_el_catalogo_json(self):
        pagina = self._generar_con_colecciones("tt0111161", "tt0068646")
        self.assertIn('"coleccion"', pagina)
        self.assertIn("Coleccion Test", pagina)

    def test_titulo_sin_coleccion_no_inventa_ninguna(self):
        pagina = self._generar_con_colecciones("tt0111161")
        self.assertIn('"coleccion": null', pagina)

    def test_ficha_muestra_la_saga_con_partes_y_notas(self):
        pagina = self._generar_con_colecciones("tt0111161", "tt0068646")
        for marcador in ("saga-item", "saga-nombre", "saga-meta",
                         "abrirFicha(p.tt)", ".saga-item {", "'Colección'"):
            self.assertIn(marcador, pagina)

    def test_boton_kpi_aplica_preset_en_lista(self):
        pagina = self._generar_con_fixture()
        for clave in ("total", "valoradas", "pendientes", "faltan",
                      "enriquecidos"):
            self.assertIn(f'data-kpi-filtro="{clave}"', pagina)
        self.assertIn("PRESET_KPI", pagina)
        self.assertIn("aplicarPresetKPI", pagina)
        # Tu nota media y Exigencia son promedios: sin preset, botón off.
        self.assertIn('data-kpi-filtro="media" aria-label="Filtrar Tu nota media" disabled',
                       pagina)
        self.assertIn('data-kpi-filtro="exigencia"', pagina)
        self.assertIn("Exigencia (tú − IMDb)", pagina)

    def test_seccion_notas_por_decada(self):
        pagina = self._generar_con_fixture()
        for marcador in ('id="seccion-decadas"', 'id="tabla-decadas"',
                         "Notas por década"):
            self.assertIn(marcador, pagina)
        # Una fila por década con su barra de distribución.
        for decada in ("1970s", "1990s", "2010s"):
            self.assertIn(f">{decada}<", pagina)
        inicio = pagina.index('id="tabla-decadas"')
        bloque = pagina[inicio:pagina.index("</table>", inicio)]
        self.assertIn('class="bar"', bloque)


if __name__ == "__main__":
    unittest.main()
