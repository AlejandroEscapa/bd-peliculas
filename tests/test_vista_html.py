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
        # 7 botones de filtro: las secciones con filtro (los KPI ya no lo llevan).
        self.assertGreaterEqual(pagina.count('class="filtro-btn"'), 7)
        for marcador in ('data-kpi="media"', 'data-seccion="top"',
                         'aria-haspopup="dialog"', 'class="filtro-panel"'):
            self.assertIn(marcador, pagina)
        # Los KPI no llevan filtro: son enlaces.
        self.assertNotIn('data-kpi-filtro', pagina)

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
                         "Exigencia (tú−IMDb)", "Enriquecidos"):
            self.assertIn(marcador, pagina)
        # Exigencia = media de (tu nota - IMDb): (10-9.2 + 9-9.0) / 2 = 0.4
        self.assertIn('<span class="n">0.4</span>', pagina)
        # El fixture no trae sinopsis, póster ni reparto: 0 de 3 enriquecidos.
        self.assertIn('<span class="n">0/3</span>', pagina)
        # Y ahora son enlaces navegables, no botones con filtro.
        self.assertIn('class="kpi" data-kpi="exigencia"', pagina)
        # La etiqueta larga se recorta en pantalla, pero el texto íntegro
        # queda en el title (y el aria-label no pierde información).
        self.assertIn('title="Exigencia (tu nota menos IMDb)"', pagina)

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

    def test_seccion_mi_perfil(self):
        pagina = self._generar_con_motor()
        self.assertIn('id="seccion-perfil"', pagina)
        self.assertIn("Mi perfil", pagina)
        self.assertIn("Te sale alto", pagina)
        self.assertIn("Te sale flojo", pagina)
        # Cada línea dice cuántas notas hay detrás: el lift sin evidencia engaña.
        self.assertIn("títulos</span>", pagina)
        self.assertIn("perfil-alto-item", pagina)

    def test_seccion_mi_perfil_no_aparece_sin_valoradas(self):
        pagina = self._generar_con_fixture()
        self.assertNotIn('id="seccion-perfil"', pagina)

    def test_notas_por_decada_es_filtrable(self):
        """Décadas usa el filtro estandar, como las demas secciones."""
        pagina = self._generar_con_fixture()
        self.assertIn('data-filtro="decadas"', pagina)
        self.assertIn('id="filtro-decadas"', pagina)
        self.assertIn('id="chips-decadas"', pagina)
        # Y el motor sabe agregarlas en cliente.
        self.assertIn("renderDecadas", pagina)
        self.assertIn("decada_asc", pagina)
        self.assertIn("decada_desc", pagina)

    def test_para_ti_tiene_altura_uniforme_y_motivos_plegables(self):
        pagina = self._generar_con_motor()
        # La celda del motivo tiene alto fijo: todas las filas miden lo mismo.
        self.assertIn(".c-razon { height: 6.4em;", pagina)
        self.assertIn("display: flex; flex-direction: column;", pagina)
        self.assertIn("justify-content: space-between;", pagina)
        # Y los motivos secundarios se pliegan tras un boton.
        self.assertIn("motivo-mas", pagina)
        self.assertIn(".motivo-sec { display: none", pagina)
        self.assertIn(".c-razon.abierta .motivo-sec { display: block", pagina)
        # Al abrir, la celda puede crecer (y el boton no se solapa).
        self.assertIn(".c-razon.abierta { height: auto; justify-content: flex-start; }",
                      pagina)

    def test_para_ti_el_motivo_se_corta_a_dos_lineas(self):
        pagina = self._generar_con_motor()
        # Tres lineas de motivo + boton descuadran la tabla: el motivo se
        # corta a dos y el boton va en su propia linea.
        self.assertIn("-webkit-line-clamp: 2;", pagina)
        self.assertIn(".c-razon .motivo { align-self: stretch; width: 100%; }", pagina)

    def test_los_kpi_no_reservan_una_doble_linea(self):
        pagina = self._generar_con_fixture()
        # La etiqueta del KPI vive en una sola linea y se recorta si no cabe.
        self.assertIn(".kpi .l { grid-area: l;", pagina)
        self.assertIn("white-space: nowrap; overflow: hidden; text-overflow: ellipsis;",
                      pagina)
        # Y no se reserva hueco para una segunda linea.
        self.assertNotIn("min-height: 2.6em", pagina)
        # El recorte es legible: el texto integro queda en el title.
        for etiqueta in re.findall(r'<a class="kpi"[^>]*>', pagina):
            self.assertIn("title=", etiqueta)

    def test_las_cifras_van_centradas(self):
        pagina = self._generar_con_fixture()
        # Las cifras no se parten y van centradas.
        self.assertIn("overflow-wrap: break-word", pagina)
        self.assertNotIn("overflow-wrap: anywhere", pagina)
        self.assertIn(".c-num { text-align: center; white-space: nowrap;", pagina)
        self.assertIn('class="c-num"', pagina)

    def test_tipo_va_centrado_como_el_resto_de_cifras(self):
        pagina = self._generar_con_fixture()
        # "Tipo" es texto corto: centrado como las cifras.
        self.assertIn(".c-centro { text-align: center; }", pagina)
        for tabla in ("tabla-top", "tabla-todas", "tabla-seguimiento"):
            inicio = pagina.index(f'id="{tabla}"')
            bloque = pagina[inicio:pagina.index("</table>", inicio)]
            self.assertIn('class="c-centro" data-label="Tipo"', bloque, tabla)
        # Y ya no hace falta una clase aparte para centrar cifras.
        self.assertNotIn("tabla-centrada", pagina)

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

    def test_los_kpi_navegan_y_no_filtran(self):
        """Los KPI son enlaces a su sección: sin embudo y sin filtros."""
        import re
        pagina = self._generar_con_fixture()
        self.assertNotIn("data-kpi-filtro", pagina)
        self.assertNotIn("PRESET_KPI", pagina)
        self.assertNotIn("aplicarPresetKPI", pagina)
        self.assertIn("navegarA(destino)", pagina)
        for clave in ("total", "valoradas", "pendientes", "media", "faltan",
                      "exigencia", "enriquecidos"):
            self.assertIn(f'data-kpi="{clave}"', pagina)
        # Cada KPI apunta a una sección que existe en la página.
        for href in re.findall(r'class="kpi"[^>]*href="#([^"]+)"', pagina):
            self.assertIn(f'id="{href}"', pagina, href)

    def test_seccion_notas_por_decada(self):
        pagina = self._generar_con_fixture()
        for marcador in ('id="seccion-decadas"', 'id="tabla-decadas"',
                         "Notas por década"):
            self.assertIn(marcador, pagina)
        # Una fila por década, en lista básica: valor, títulos y media.
        for decada in ("1970s", "1990s", "2010s"):
            self.assertIn(f">{decada}<", pagina)
        inicio = pagina.index('id="tabla-decadas"')
        bloque = pagina[inicio:pagina.index("</table>", inicio)]
        self.assertIn('class="c-num"', bloque)
        self.assertNotIn('class="bar"', bloque)

    def test_las_las_agregadas_son_lista_basica(self):
        """Géneros, directores, actores y décadas: tres columnas, sin barras."""
        pagina = self._generar_con_fixture()
        for tabla in ("tabla-generos", "tabla-directores", "tabla-actores",
                      "tabla-decadas"):
            inicio = pagina.index(f'id="{tabla}"')
            bloque = pagina[inicio:pagina.index("</table>", inicio)]
            self.assertNotIn('class="bar"', bloque, tabla)
            self.assertIn('class="c-num"', bloque, tabla)
            # La barra se fue: solo valor, títulos y media.
            self.assertEqual(bloque.count("</th>"), 3, tabla)
            # Sin botón de filtro muerto en las secciones de información.
            self.assertNotIn('data-filtro="generos"', pagina)
            self.assertNotIn('data-filtro="actores"', pagina)

    def test_la_web_se_siente_como_un_zoom_del_navegador(self):
        pagina = self._generar_con_fixture()
        # Zoom del navegador aplicado al elemento raíz.
        self.assertIn("html { zoom: 1.1; }", pagina)

    def test_las_tiras_plegadas_centran_sus_textos(self):
        pagina = self._generar_con_fixture()
        # Plegada, la cabecera no deja margen suelta: si no, el par
        # título+descripción queda por encima del centro de la tira.
        self.assertIn("section.plegada .section-head { margin-bottom: 0; }", pagina)

    def test_las_cabeceras_no_cuentan_la_paginacion(self):
        pagina = self._generar_con_fixture()
        # El botón "Cargar 15 más" y el "Mostrando X de Y" ya lo dicen.
        for sobrante in ("15 visibles", "carga 15 más", "Pulsa una para abrir la ficha",
                         "Filtra sin recargar"):
            self.assertNotIn(sobrante, pagina)

    def test_joyas_y_decepciones_son_tarjeta(self):
        """Título arriba (centrado) y los tres datos alineados debajo."""
        pagina = self._generar_con_fixture()
        for tabla in ("tabla-joyas", "tabla-decepciones"):
            self.assertIn(f'class="paginada tabla-tarjeta" id="{tabla}"', pagina)
        # El motor dibuja la tarjeta: título y datos.
        self.assertIn("filaDeTarjeta", pagina)
        self.assertIn("tarjeta-datos", pagina)
        self.assertIn("tarjeta: true", pagina)
        # El título va centrado y con más aire hasta los datos.
        self.assertIn(".tarjeta-titulo { font-size: 16px;", pagina)
        self.assertIn("text-align: center; }", pagina)
        self.assertIn("margin-top: 18px; }", pagina)

    def test_las_secciones_se_plegan(self):
        pagina = self._generar_con_motor()
        # Todas menos el strip de pósters son plegables.
        for sec in ("para-ti", "perfil", "top", "joyas", "decepciones",
                    "generos", "directores", "actores", "decadas", "lista",
                    "seguimiento"):
            self.assertIn(f'data-plegable="{sec}"', pagina)
        self.assertNotIn('data-plegable="posters"', pagina)
        # El mando: un botón que cubre la cabecera y una flecha a la derecha.
        self.assertIn('class="plegable-tap" data-plegable=', pagina)
        self.assertIn('class="chevron"', pagina)
        self.assertIn(".section-acciones", pagina)
        # Y el JS sabe plegar y desplegar (y desplegar al navegar por un KPI).
        self.assertIn("prepararPlegables()", pagina)
        self.assertIn("function plegar(seccion, abierta)", pagina)
        self.assertIn("desplegar(destino)", pagina)
        # "Para ti" es la única que arranca abierta.
        self.assertIn('data-plegable="para-ti" data-abierto="1"', pagina)

    def test_la_ficha_muestra_la_coleccion_bajo_la_sinopsis(self):
        pagina = self._generar_con_fixture()
        # La colección va en su propio bloque, debajo de la sinopsis.
        self.assertIn('id="ficha-coleccion"', pagina)
        self.assertIn("ficha-coleccion", pagina)
        # Y la nota ya no se repite bajo el póster.
        self.assertNotIn('id="ficha-nota"', pagina)
        # La meta de la ficha sigue llevándola.
        self.assertIn("'Tu nota: ' + f.nota", pagina)

    def test_actores_tiene_las_cifras_centradas(self):
        pagina = self._generar_con_fixture()
        inicio = pagina.index('id="tabla-actores"')
        bloque = pagina[inicio:pagina.index("</table>", inicio)]
        self.assertIn('class="c-num" data-label="Títulos"', bloque)
        self.assertIn('class="c-num" data-label="Media"', bloque)

    def test_mi_perfil_las_filas_miden_como_tus_favoritas(self):
        pagina = self._generar_con_fixture()
        # Cada item mide 42 px, como una fila de "Tus favoritas".
        self.assertIn("font-size: 13px; height: 42px; }", pagina)
        # Y el subtítulo va en su propio elemento para que quede alineado.
        self.assertIn("perfil-alto-titulo", pagina)
        self.assertIn("perfil-alto-faceta", pagina)


if __name__ == "__main__":
    unittest.main()
