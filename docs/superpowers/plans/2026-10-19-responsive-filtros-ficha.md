# Panel responsive, ficha con sinopsis y filtros por sección — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir el panel en una interfaz mobile-first, mover la sinopsis al final de la ficha a todo el ancho y añadir filtros por sección y KPI que recalculen el catálogo en cliente.

**Architecture:** Se mantiene un único HTML estático generado por Python. El catálogo se serializa una sola vez en `catalogo-data`; un motor JavaScript renderiza las tablas desde ese JSON, aplica facetas por sección y recalcula los agregados. El HTML de servidor queda como fallback sin JavaScript y conserva la paginación 15 + 15.

**Tech Stack:** Python 3.11+ stdlib, SQLite, HTML/CSS/JavaScript sin build, `unittest`.

**Spec:** `docs/responsive-design.md`

## Global Constraints

- Python 3.11+ y solo stdlib. No añadir `pip`, `npm`, frameworks ni dependencias de test.
- El panel sigue siendo un único HTML estático: sin `fetch`, sin servidor y sin claves en el navegador.
- La paginación 15 + 15 (`table.paginada` + `.more-btn`) se conserva en todas las tablas.
- Todo texto procedente de SQLite se escapa con `html.escape` en Python y se pinta con `textContent` en JavaScript.
- No tocar el esquema, `db/migrations/`, `.env`, secretos ni consultas no parametrizadas.
- UI en español. Targets táctiles de 44×44 px como mínimo.
- Mantener buscador global, ficha modal, foco atrapado, Escape y devolución del foco.
- No tocar `ROADMAP.md` ni `docs/superpowers/specs/2026-10-19-multiusuario-f0-design.md`: tienen cambios locales sin commitear.
- No hacer push. Los commits se quedan locales hasta que el usuario lo pida.
- Las tres piezas (responsive, ficha, filtros) van en commits separados para poder revertir una sin las otras.

## Review Focus

1. **Títulos incompletos:** sin póster, sin sinopsis, sin reparto, sin año o sin nota. Deben mostrar fallback y no romper filtros ni agregados. Tests en tareas 2, 4 y 5.
2. **Texto hostil:** títulos, géneros o sinopsis con `<`, `&`, comillas y `</script>`. El JSON no debe cerrar el script y el DOM no debe inyectar HTML. Test en tarea 2.
3. **Cero resultados:** una combinación de facetas que deje una sección vacía debe mostrar un estado vacío, ocultar el paginador y no lanzar errores. Test en tarea 5.
4. **Almacenamiento no disponible o corrupto:** `sessionStorage` bloqueado, lleno o con JSON inválido. El panel debe arrancar con filtros vacíos. Test en tarea 5.
5. **Móvil estrecho y zoom:** 320 px y 200 % de zoom sin overflow horizontal, popover dentro del viewport y controles de 44 px. Verificación de navegador en tareas 3 y 7.
6. **Cambios rápidos:** alternar facetas o escribir en el buscador no debe duplicar listeners ni dejar filas de un estado anterior. Verificación de navegador en tarea 5.

---

### Task 1: Cerrar la spec y la línea base

**Files:**
- Revisar: `docs/responsive-design.md`
- Verificar: `tests/test_vista_html.py`

**Interfaces:**
- Consumes: nada.
- Produces: spec aprobada y suite base de 41 tests en verde.

- [ ] **Step 1: Confirmar la línea base**

Run: `python -m unittest discover -s tests`
Expected: `Ran 41 tests` y `OK`.

- [ ] **Step 2: Revisar que la spec contiene las tres estrategias y las decisiones**

Run: `grep -c '^### Estrategia' docs/responsive-design.md`
Expected: `3`.

Run: `grep -n 'Tarjetas apiladas (elegida)\|recalculan los agregados\|sessionStorage\|sinopsis es el' docs/responsive-design.md`
Expected: aparecen las cuatro decisiones.

- [ ] **Step 3: Commit**

```bash
git add docs/responsive-design.md docs/superpowers/plans/2026-10-19-responsive-filtros-ficha.md
git commit -m "docs: decisiones y plan de responsive, ficha y filtros"
```

---

### Task 2: Catálogo JSON de filtros y etiquetas de tabla

**Files:**
- Modify: `scripts/generar_vista.py:139-147` (`fila_tabla`), `scripts/generar_vista.py:168-350` (consultas y mapas), `scripts/generar_vista.py:567-604` (HTML final)
- Test: `tests/test_vista_html.py`

**Interfaces:**
- Consumes: `fichas`, `cast_por_tt`, `dir_por_tt`, `pais_por_tt`, `gen_por_tt` ya calculados en `generar()`.
- Produces:
  - `fila_tabla(celdas: list[str], cls_first: str | None = None, etiquetas: list[str] | None = None) -> str`. Si `etiquetas` no es `None`, cada `<td>` lleva `data-label="<etiqueta>"`; las etiquetas se escapan con `html.escape`.
  - `<script type="application/json" id="catalogo-data">` con el contrato de `docs/responsive-design.md`. `indice-data` y `fichas-data` se mantienen temporalmente para no romper el JS existente; se retiran en las tareas 4 y 5.
  - Cada tabla lleva `data-seccion`: `top`, `joyas`, `decepciones`, `generos`, `directores`, `actores`, `lista`, `seguimiento`, y un `id` estable: `tabla-top`, `tabla-joyas`, `tabla-decepciones`, `tabla-generos`, `tabla-directores`, `tabla-actores`, `tabla-todas`, `tabla-seguimiento`.
  - Cada KPI lleva `data-kpi`: `total`, `valoradas`, `pendientes`, `media`, `faltan`.

- [ ] **Step 1: Escribir los tests que fallan**

Añadir `import re` al inicio de `tests/test_vista_html.py` y estos tests:

```python
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
```

No tocar todavía las aserciones de `indice-data` y `fichas-data`; se retiran en las tareas 4 y 5.

- [ ] **Step 2: Ejecutar y ver el fallo**

Run: `python -m unittest tests.test_vista_html -v`
Expected: FAIL por `id="catalogo-data"` ausente y por celdas sin `data-label`.

- [ ] **Step 3: Implementar el contrato de datos**

En `generar()`, ampliar la consulta de `fichas` con `t.runtime_min_csv`, `t.runtime_min_exact`, `u.date_rated` y `u.watch_status`. Construir un único `catalogo_map` indexado por `tt` con las claves exactas del contrato:

```python
"titulo": titulo,
"original": r["original_title"] or "",
"url": r["url"] or "",
"tipo": r["title_type"] or "",
"year": r["year"],
"imdb": r["imdb_rating"],
"nota": r["my_rating"],
"fecha": r["date_rated"] or "",
"estado": "rated" if r["my_rating"] is not None else "watchlist",
"duracion": r["runtime_min_exact"] or r["runtime_min_csv"],
"sinopsis": r["synopsis"] or "",
"poster": r["poster_url"] or "",
"sin_sinopsis": not bool(r["synopsis"]),
"sin_reparto": not bool(cast_por_tt.get(tt)),
"diferencia": (round(r["my_rating"] - r["imdb_rating"], 1)
               if r["my_rating"] is not None and r["imdb_rating"] is not None
               else None),
"reparto": [{"nombre": c["name"], "personaje": c["character"]}
            for c in cast_por_tt.get(tt, [])[:8]],
"directores": dir_por_tt.get(tt, []),
"paises": pais_por_tt.get(tt, []),
"generos": gen_por_tt.get(tt, []),
```

Mantener temporalmente `indice_json` y `fichas_json` para el JS actual. Añadir la serialización nueva:

```python
catalogo_json = json.dumps(catalogo_map, ensure_ascii=False).replace("</", "<\\/")
```

- [ ] **Step 4: Añadir las etiquetas de celda**

Implementar el parámetro `etiquetas` en `fila_tabla`. Pasar etiquetas en todas las llamadas:

| Tabla | Etiquetas |
|---|---|
| top | `["Tu nota", "Título", "Tipo", "IMDb"]` |
| joyas | `["Tú", "Título", "IMDb", "Diferencia"]` |
| decepciones | `["Tú", "Título", "IMDb", "Diferencia"]` |
| generos | `["Género", "Títulos", "Distribución", "Media"]` |
| directores | `["Director", "Títulos", "Media"]` |
| actores | `["Actor", "Títulos", "Media"]` |
| lista | `["Título", "Tipo", "Año", "Géneros", "IMDb", "Tu nota"]` |
| seguimiento | `["Título", "Tipo", "IMDb"]` |

Añadir `data-seccion` a cada `<table>` y `data-kpi` a cada tarjeta KPI. En el HTML final, añadir el tercer script JSON:

```html
<script type="application/json" id="catalogo-data">{catalogo_json}</script>
```

- [ ] **Step 5: Ejecutar los tests**

Run: `python -m unittest tests.test_vista_html -v`
Expected: PASS, incluidos los tests nuevos.

- [ ] **Step 6: Commit**

```bash
git add scripts/generar_vista.py tests/test_vista_html.py
git commit -m "feat: catálogo JSON único y etiquetas para tablas responsive"
```

---

### Task 3: Layout mobile-first, tarjetas de tabla y controles de filtro

**Files:**
- Modify: `scripts/generar_vista.py:24-124` (CSS), `scripts/generar_vista.py:168-350` (helpers y HTML)
- Test: `tests/test_vista_html.py`

**Interfaces:**
- Consumes: `fila_tabla(..., etiquetas)` de la tarea 2, `data-seccion` y `data-kpi`.
- Produces:
  - `ICONO_FILTRO: str` (SVG inline, `aria-hidden="true"`).
  - `boton_filtro(id_seccion: str, etiqueta: str, disabled: bool = False) -> str` con `class="filtro-btn"`, `aria-haspopup="dialog"`, `aria-expanded="false"`, `aria-controls="filtro-<id>"`.
  - `cabecera_seccion(id_seccion: str, titulo: str, hint: str, disabled: bool = False) -> str` con `h2 tabindex="-1"`, `p.hint`, botón y `<div class="filtro-panel" id="filtro-<id>" role="dialog" aria-label="Filtros de <titulo>" hidden>`.
  - `tarjeta_kpi(clave: str, valor: str, etiqueta: str) -> str` con `class="kpi"`, `data-kpi` y botón de filtro.
  - CSS con `@container (max-width: 640px)`, `clamp()`, `100dvh`, `env(safe-area-inset-bottom)` y `prefers-reduced-motion`.

- [ ] **Step 1: Escribir el test que falla**

```python
def test_css_responsive_y_controles_de_filtro(self):
    pagina = self._generar_con_fixture()
    for marcador in ("@container", "clamp(", "100dvh",
                     "prefers-reduced-motion", "env(safe-area-inset-bottom)"):
        self.assertIn(marcador, pagina)
    self.assertGreaterEqual(pagina.count('class="filtro-btn"'), 10)
    for marcador in ('data-kpi="media"', 'data-seccion="top"',
                     'aria-haspopup="dialog"', 'class="filtro-panel"'):
        self.assertIn(marcador, pagina)
```

- [ ] **Step 2: Ejecutar y ver el fallo**

Run: `python -m unittest tests.test_vista_html -v`
Expected: FAIL por los marcadores CSS y los botones ausentes.

- [ ] **Step 3: Reescribir el CSS mobile-first**

Sustituir el bloque actual por estas reglas base, conservando nombres existentes:

- `:root` con `--sp: clamp(16px, 4vw, 40px)`, `--radius: clamp(14px, 2vw, 18px)`.
- `body` con padding fluido y `padding-bottom: calc(64px + env(safe-area-inset-bottom))`.
- `header h1` con `font-size: clamp(28px, 6vw, 40px)`; `header p` con `clamp(14px, 2.5vw, 17px)`.
- `.kpis`: 2 columnas con `minmax(0, 1fr)`; 3 a 640 px; 5 a 900 px.
- `.kpi`: `position: relative; padding: 14px`; `.kpi .n` con `clamp(26px, 6vw, 34px)`.
- `.grid2`: 1 columna; 2 a 900 px.
- `.poster-grid`: 2 columnas; 3 a 480 px; 4 a 640 px; 5 a 900 px.
- `section`: `container-type: inline-size; padding: 16px;` y 22 px a 640 px.
- `.hdr`: columna; fila a 900 px. `.buscador-global` a ancho completo en móvil y `min-width: 0`.
- Tablas: `table-layout: auto`, `td` con `overflow-wrap: anywhere`; en `@container (max-width: 640px)` aplicar tarjetas:

```css
.tabla-cards thead { display: none; }
.tabla-cards, .tabla-cards tbody, .tabla-cards tr, .tabla-cards td { display: block; width: 100%; }
.tabla-cards tr { border: 1px solid var(--line); border-radius: 14px; padding: 12px; margin-bottom: 10px; }
.tabla-cards td { display: flex; justify-content: space-between; gap: 12px; border: 0; padding: 3px 0; }
.tabla-cards td::before { content: attr(data-label); color: var(--sub); font-size: 12px; font-weight: 500; }
.tabla-cards td.t { font-size: 16px; font-weight: 600; white-space: normal; overflow: visible; text-overflow: clip; max-width: none; }
.tabla-cards td.t::before { display: none; }
.tabla-cards .nw { white-space: normal; }
```

Añadir un fallback `@media (max-width: 760px)` con las mismas reglas para navegadores sin container queries.

- [ ] **Step 4: Añadir estilos de filtro y accesibilidad**

Definir `.filtro-wrap`, `.filtro-btn` (44×44, borde redondeado, fondo blanco), `.filtro-badge`, `.filtro-panel` (posición absoluta a la derecha, `width: min(340px, calc(100vw - 40px))`, `max-height: 70dvh`, scroll), `.filtro-grupo`, `.filtro-opcion`, `.chips`, `.chip`, `.leer-mas`, `.ancho-completo`.

Incluir `:focus-visible`, `@media (prefers-reduced-motion: reduce)` y `@media (max-width: 640px)` para la ficha a `100dvh` (la estructura de la ficha llega en la tarea 4).

- [ ] **Step 5: Implementar los helpers y sustituir el HTML**

`boton_filtro` devuelve:

```html
<button type="button" class="filtro-btn" data-filtro="<id>"
        aria-label="Filtrar <etiqueta>" aria-haspopup="dialog"
        aria-expanded="false" aria-controls="filtro-<id>">
  <svg ... aria-hidden="true" focusable="false">…</svg>
  <span class="filtro-badge" hidden></span>
</button>
```

`cabecera_seccion` envuelve el `h2` y el `hint` en un `div`, y el botón + panel en `div.filtro-wrap`. Añadir la clase `tabla-cards` a las ocho tablas (`class="paginada tabla-cards"`), además de sus `id` y `data-seccion`. Sustituir las cabeceras actuales de Pósters, Tus favoritas, Joyas, Decepciones, Géneros, Directores, Actores, Lista completa y En seguimiento.

Sustituir las cinco tarjetas KPI por `tarjeta_kpi(...)`. Los botones de las secciones agregadas (`generos`, `directores`, `actores`) se generan con `disabled=True` y `data-pendiente="true"` hasta la tarea 6.

- [ ] **Step 6: Ejecutar los tests**

Run: `python -m unittest tests.test_vista_html -v`
Expected: PASS.

- [ ] **Step 7: Verificar en navegador**

Run: `python -m http.server 8001 --bind 127.0.0.1`
Abrir `http://127.0.0.1:8001/preview/dashboard.html` en el navegador de preview.

Para 320, 375, 768 y 1440 px comprobar:

```js
document.documentElement.scrollWidth <= window.innerWidth
```

Expected: `true` en los cuatro. A 375 px, `getComputedStyle(document.querySelector('.kpis')).gridTemplateColumns.split(' ').length === 2`; a 768 px, `3`; a 1440 px, `5`. El `thead` está oculto y la primera fila es `display: block` a 375 px; a 1440 px vuelve a `table-row`. El botón `.filtro-btn` mide al menos 44×44.

- [ ] **Step 8: Commit**

```bash
git add scripts/generar_vista.py tests/test_vista_html.py
git commit -m "feat: layout responsive y controles de filtro"
```

---

### Task 4: Ficha con la sinopsis al final y a todo el ancho

**Files:**
- Modify: `scripts/generar_vista.py:88-110` (CSS de ficha), `scripts/generar_vista.py:363-566` (`abrirFicha`), `scripts/generar_vista.py:567-604` (HTML)
- Test: `tests/test_vista_html.py`

**Interfaces:**
- Consumes: `catalogo-data` con `reparto`, `directores`, `paises`, `generos`, `sinopsis`, `poster`, `nota`, `url`.
- Produces:
  - `<template id="ficha-plantilla">` con `.ficha-cabecera`, `.ficha-lateral`, `.ficha-datos` y `.ficha-sinopsis.bloque.ancho-completo` como último bloque.
  - IDs `ficha-poster`, `ficha-poster-fallback`, `ficha-nota`, `ficha-imdb`, `ficha-titulo`, `ficha-meta`, `ficha-bloques`, `ficha-sinopsis-texto`, `ficha-leer-mas`.
  - `iniciales(titulo: string) -> string`: dos iniciales en mayúsculas o `?`, reutilizada por la ficha y por los pósters.
  - `FICHAS: Record<string, fila>` cargado de `catalogo-data`; `abrirFicha` usa `FICHAS[tt]`.
  - `abrirFicha(tt)` clona la plantilla, rellena con `textContent` y activa el plegado móvil.

- [ ] **Step 1: Escribir el test que falla**

```python
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
```

- [ ] **Step 2: Ejecutar y ver el fallo**

Run: `python -m unittest tests.test_vista_html -v`
Expected: FAIL por la plantilla y los marcadores ausentes.

- [ ] **Step 3: Crear la plantilla y reescribir `abrirFicha`**

La plantilla debe tener esta estructura, con la sinopsis **después** de la cabecera:

```html
<template id="ficha-plantilla">
  <div class="ficha-cabecera">
    <div class="ficha-lateral">
      <img class="poster" id="ficha-poster" alt="" loading="lazy">
      <span class="poster-fallback" id="ficha-poster-fallback" aria-hidden="true"></span>
      <span class="pill" id="ficha-nota"></span>
      <a id="ficha-imdb" target="_blank" rel="noopener">Ver en IMDb</a>
    </div>
    <div class="ficha-datos">
      <h3 id="ficha-titulo"></h3>
      <div class="meta" id="ficha-meta"></div>
      <div id="ficha-bloques"></div>
    </div>
  </div>
  <div class="ficha-sinopsis bloque ancho-completo">
    <b>Sinopsis</b>
    <p class="sinopsis plegada" id="ficha-sinopsis-texto"></p>
    <button type="button" class="leer-mas" id="ficha-leer-mas"
            aria-expanded="false">Leer más</button>
  </div>
</template>
```

Al inicio del script, cargar `const FICHAS = JSON.parse(document.getElementById('catalogo-data').textContent || '{}');`. `abrirFicha` clona la plantilla con `contenido.replaceChildren(plantilla.content.cloneNode(true))`, rellena título, meta, bloques, póster, nota y enlace desde `FICHAS[tt]`. El póster se oculta si no hay URL y se muestran las iniciales en `ficha-poster-fallback`. El enlace se oculta si no hay URL. Los bloques se crean con `textContent`; no usar `innerHTML` con datos.

El botón «Leer más» se muestra solo si `sinopsis.length > 280`. Alterna `.plegada`, cambia el texto a «Leer menos» y actualiza `aria-expanded`. Si no hay sinopsis, muestra «Sin sinopsis disponible todavía.» y oculta el botón.

- [ ] **Step 4: Ajustar el CSS de la ficha**

- `.ficha-cabecera { display: grid; grid-template-columns: 160px 1fr; gap: 20px; }`
- `.ficha-lateral { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }`
- `.ficha-sinopsis { grid-column: 1 / -1; width: 100%; margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--line); }`
- `.ficha .sinopsis.plegada` en móvil: `display: -webkit-box; -webkit-box-orient: vertical; -webkit-line-clamp: 4; overflow: hidden;`
- En móvil, `.overlay { padding: 0; }`, `.ficha` ocupa `width: 100%; height: 100dvh; max-height: none; border-radius: 0;`, `.ficha-cabecera` usa `grid-template-columns: 96px 1fr` y `.ficha img.poster` baja a `width: 96px`.
- `.leer-mas` solo visible en móvil; en escritorio se oculta con `display: none`.

- [ ] **Step 5: Conservar el diálogo accesible**

Mantener `role="dialog"`, `aria-modal="true"`, `aria-labelledby="ficha-titulo"`, foco atrapado, Escape, clic en el fondo y devolución del foco. Al cerrar, limpiar el contenido clonado.

- [ ] **Step 6: Ejecutar los tests**

Actualizar `test_lista_completa_con_todos_los_titulos`: cambiar `id="fichas-data"` por `id="catalogo-data"`; `id="indice-data"` sigue hasta la tarea 5.

Run: `python -m unittest tests.test_vista_html -v`
Expected: PASS.

- [ ] **Step 7: Verificar en navegador**

Abrir un póster. En 1440 px, comprobar que `.ficha-sinopsis` es el último hijo de `#ficha-contenido`, que su ancho es igual al del contenedor y que el texto está completo. En 375 px, comprobar que el párrafo tiene `-webkit-line-clamp: 4`, que «Leer más» lo expande y que `aria-expanded` pasa a `true`. Abrir un título sin póster y comprobar el fallback de iniciales; abrir uno sin sinopsis y comprobar el texto de fallback. Probar Escape y comprobar que el foco vuelve al póster.

- [ ] **Step 8: Commit**

```bash
git add scripts/generar_vista.py tests/test_vista_html.py
git commit -m "feat: sinopsis al final de la ficha y plegado móvil"
```

---

### Task 5: Motor de filtros, paginación y secciones de títulos

**Files:**
- Modify: `scripts/generar_vista.py:352-566` (JavaScript), `scripts/generar_vista.py:567-604` (HTML)
- Test: `tests/test_vista_html.py`

**Interfaces:**
- Consumes: `catalogo-data`, `FICHAS` de la tarea 4 y los botones/paneles de la tarea 3.
- Produces:
  - `CATALOGO: Array<{tt: string, ...}>` derivado de `Object.entries(FICHAS)`.
  - `FACETAS: Record<string, {etiqueta, tipo, opciones(datos, seccion), prueba(fila, valor)}>`.
  - `SECCIONES: Record<string, {base, facetas, columnas, ordenDefecto, limite, facetasGrupo?, minimo?}>` para `posters`, `top`, `joyas`, `decepciones`, `lista`, `seguimiento`.
  - `estadoFiltros: Record<string, {facetas: Object, orden: string, q: string}>`.
  - `montarPaginador(tabla: HTMLTableElement, paso = 15) -> {reiniciar(): void}`.
  - `renderSeccion(id: string): void`, `abrirPanelFiltro(id)`, `cerrarPanelFiltro(id)`, `alternarFaceta(id, faceta, valor)`, `limpiarFiltros(id)`, `pintarChips(id)`, `guardarSesion()`, `cargarSesion()`.
  - Clave `db-peliculas:filtros:v1` en `sessionStorage`.

- [ ] **Step 1: Escribir el test que falla**

```python
def test_motor_de_filtros_y_paginador(self):
    pagina = self._generar_con_fixture()
    self.assertNotIn('id="indice-data"', pagina)
    for marcador in ("montarPaginador", "sessionStorage",
                     "db-peliculas:filtros:v1", "renderSeccion",
                     "aria-live", "alternarFaceta"):
        self.assertIn(marcador, pagina)
```

- [ ] **Step 2: Ejecutar y ver el fallo**

Run: `python -m unittest tests.test_vista_html -v`
Expected: FAIL por los marcadores del motor.

- [ ] **Step 3: Montar el catálogo y las facetas**

```js
const CATALOGO = Object.entries(FICHAS).map(([tt, f]) => ({ tt, ...f }));
const MEDIA = (() => {
  const notas = CATALOGO.filter((x) => x.nota != null).map((x) => x.nota);
  return notas.length ? notas.reduce((a, b) => a + b, 0) / notas.length : 0;
})();
```

Implementar `FACETAS` con:

- `tipo`, `genero`, `decada`: opciones calculadas desde `CATALOGO`, ordenadas.
- `nota`: 10, 9, 8, 7, 6, 5 o menos, sin nota, por encima de la media, por debajo de la media. En secciones de valoradas no mostrar «sin nota».
- `imdb`: 9+, 8–8.9, 7–7.9, 6–6.9, menos de 6, sin IMDb.
- `estado`: valorada / pendiente.
- `calidad`: sin sinopsis, sin reparto, sin póster, ficha completa.
- `diferencia`: +1.5–1.9, +2–2.4, +2.5 o más en Joyas; −1.5–−1.9, −2–−2.4, −2.5 o menos en Decepciones.
- `orden`: opciones por sección.

Cada opción tiene `{valor, etiqueta}` y `prueba(fila, valor)` que devuelve booleano. Los rangos se evalúan con `>=` y `<`. `opciones(datos, seccion)` oculta las opciones imposibles: «sin nota» solo en Lista completa, y la diferencia positiva solo en Joyas / la negativa solo en Decepciones.

- [ ] **Step 4: Configurar las secciones de títulos**

Definir `SECCIONES` con:

| Sección | `base` | Facetas | Límite | Orden por defecto |
|---|---|---|---|---|
| `posters` | `nota != null` | tipo, genero, decada, nota, orden | 10 | `nota_desc` |
| `top` | `nota != null` | tipo, genero, decada, nota, imdb, orden | 60 | `nota_desc` |
| `joyas` | `diferencia >= 1.5` | tipo, genero, decada, nota, imdb, diferencia, orden | 30 | `diferencia_desc` |
| `decepciones` | `diferencia <= -1.5` | tipo, genero, decada, nota, imdb, diferencia, orden | 30 | `diferencia_asc` |
| `lista` | todas | tipo, genero, decada, estado, nota, imdb, calidad, orden | sin límite | `titulo_asc` |
| `seguimiento` | `nota == null` | tipo, genero, decada, imdb, calidad, orden | 60 | `imdb_desc` |

Cada columna se define como `{etiqueta, valor(fila), clase}`. Para píldoras y barras, `valor` devuelve un nodo DOM creado con `document.createElement` y `textContent`. Para los pósters, `renderPosters` reutiliza la estructura de `_tarjeta_poster` y el fallback de iniciales.

- [ ] **Step 5: Paginación reutilizable**

Sustituir el bucle actual de `table.paginada` por:

```js
function montarPaginador(tabla, paso = 15) {
  let visibles = paso;
  const wrap = document.createElement('div');
  const btn = document.createElement('button');
  const info = document.createElement('div');
  // ... crear .more-wrap, .more-btn y .count con aria-live
  const pintar = () => { /* mostrar/ocultar filas y actualizar textos */ };
  btn.addEventListener('click', () => { visibles += paso; pintar(); });
  return {
    reiniciar() { visibles = paso; pintar(); }
  };
}
```

`renderSeccion` reemplaza el `tbody` con un `DocumentFragment`, resetea el paginador y actualiza el contador. El botón debe decir «Cargar 15 más (N restantes)» y el contador «Mostrando X de Y». Si hay 15 o menos filas, el botón se oculta.

- [ ] **Step 6: Popover, chips y sesión**

- `abrirPanelFiltro(id)` rellena el panel con grupos de checkboxes/radios, botón «Limpiar» y botón de cierre. `aria-expanded` del disparador pasa a `true`.
- `cerrarPanelFiltro(id)` cierra, devuelve el foco al botón y actualiza `aria-expanded`.
- `alternarFaceta` actualiza el estado, vuelve a renderizar, pinta chips y guarda la sesión.
- `pintarChips` crea un botón por valor activo con `aria-label="Quitar filtro <faceta>: <valor>"`.
- `guardarSesion` y `cargarSesion` van envueltos en `try/catch`; validan que la sección, faceta y opción existan antes de restaurar.
- Clic fuera cierra el panel. Escape cierra el panel y la ficha; el foco vuelve al disparador correspondiente.
- El resumen de resultados se anuncia en un `div` con `aria-live="polite"`.

- [ ] **Step 7: Integrar el buscador**

El input `#q` actualiza `estadoFiltros.lista.q` con debounce de 120 ms y llama a `renderSeccion('lista')`. La búsqueda cubre título, original, directores, reparto y géneros. No debe ocultar filas del DOM a mano; el render se encarga.

El buscador global deja de leer `indice-data`: usa `CATALOGO` para filtrar y `FICHAS` para abrir la ficha. Eliminar el `<script id="indice-data">` y su variable `indice` del HTML/JS. Actualizar `test_lista_completa_con_todos_los_titulos` para que ya no espere `indice-data`.

- [ ] **Step 8: Ejecutar los tests**

Run: `python -m unittest tests.test_vista_html -v`
Expected: PASS.

- [ ] **Step 9: Verificar en navegador**

- Abrir «Tus favoritas», marcar `Drama`: las filas se reducen, aparece el chip, el badge muestra `1` y el contador vuelve a «Mostrando 15 de N».
- Pulsar «Cargar 15 más»: aparecen 30; cambiar una faceta: vuelve a 15.
- Recargar: el filtro sigue activo. Cerrar la pestaña y abrir otra: no se restaura.
- Introducir `zzzz` en el buscador: la tabla muestra estado vacío, el paginador se oculta y no hay errores en consola.
- Corromper `sessionStorage` con `sessionStorage.setItem('db-peliculas:filtros:v1', '{')` y recargar: el panel arranca limpio.
- Abrir el panel de filtros y comprobar que Escape cierra y devuelve el foco.
- Alternar cinco facetas seguidas y comprobar que no se duplican chips ni listeners; el contador final coincide con el número de filas visibles.

- [ ] **Step 10: Commit**

```bash
git add scripts/generar_vista.py tests/test_vista_html.py
git commit -m "feat: motor de filtros y paginación reactiva"
```

---

### Task 6: Agregados recalculados y presets de KPI

**Files:**
- Modify: `scripts/generar_vista.py:352-566` (JavaScript)
- Test: `tests/test_vista_html.py`

**Interfaces:**
- Consumes: `CATALOGO`, `SECCIONES`, `estadoFiltros`, `renderSeccion` y `montarPaginador` de la tarea 5.
- Produces:
  - `agrupar(datos, obtener: (fila) => string[], etiqueta: string) -> Array<{nombre, titulos, media}>`.
  - `SECCIONES.generos`, `SECCIONES.directores`, `SECCIONES.actores` con facetas `tipo`, `decada`, `min_titulos`, `media`, `orden`.
  - `PRESETS_KPI` y `aplicarPresetKPI(kpi, presetId)`.
  - Botones de filtro de las tres secciones agregadas sin `disabled` ni `data-pendiente`.

- [ ] **Step 1: Escribir el test que falla**

```python
def test_agregados_y_presets_de_kpi(self):
    pagina = self._generar_con_fixture()
    for marcador in ("agrupar(", "min_titulos", "PRESETS_KPI",
                     "aplicarPresetKPI", "media_alta", "media_baja"):
        self.assertIn(marcador, pagina)
    self.assertNotIn('data-pendiente="true"', pagina)
```

- [ ] **Step 2: Ejecutar y ver el fallo**

Run: `python -m unittest tests.test_vista_html -v`
Expected: FAIL por los marcadores y los botones pendientes.

- [ ] **Step 3: Implementar los agregados**

```js
function agrupar(datos, obtener, etiqueta) {
  const mapa = new Map();
  datos.forEach((fila) => {
    (obtener(fila) || []).forEach((valor) => {
      const actual = mapa.get(valor) || { nombre: valor, titulos: 0, suma: 0 };
      actual.titulos += 1;
      if (fila.nota != null) actual.suma += fila.nota;
      mapa.set(valor, actual);
    });
  });
  return [...mapa.values()].map((g) => ({
    ...g,
    media: g.titulos ? Math.round((g.suma / g.titulos) * 100) / 100 : null
  }));
}
```

- `generos`: `base = valoradas`, `agrupar(datos, f => f.generos)`, facetas tipo/década sobre los títulos y `min_titulos`/`media` sobre los grupos.
- `directores`: igual con `f => f.directores`.
- `actores`: igual con `f => f.reparto.map(x => x.nombre)`, mínimo 2 títulos por defecto.
- Marcar `facetasGrupo = ["min_titulos", "media"]` en las tres secciones; el resto de facetas se aplica antes de agrupar. `generos` y `directores` usan mínimo 1 por defecto; `actores`, mínimo 2.
- Para `min_titulos` usar radios `2+`, `3+`, `5+`, `10+`. Para `media` usar rangos `9+`, `8–8.9`, `7–7.9`, `6–6.9`, `<6`.
- La barra de distribución se calcula con el máximo de títulos del subconjunto filtrado.
- Si no hay grupos, renderizar una fila con `colspan` y el texto «Sin resultados con estos filtros.».

- [ ] **Step 4: Implementar los presets de KPI**

```js
const PRESETS_KPI = {
  total: [{ id: 'todo', etiqueta: 'Ver todo', filtros: {} }],
  valoradas: [{ id: 'valoradas', etiqueta: 'Solo valoradas',
                filtros: { estado: ['rated'] } }],
  pendientes: [{ id: 'pendientes', etiqueta: 'Solo pendientes',
                 filtros: { estado: ['watchlist'] } }],
  media: [
    { id: 'media_alta', etiqueta: 'Por encima de mi media',
      filtros: { nota: ['media_alta'] } },
    { id: 'media_baja', etiqueta: 'Por debajo de mi media',
      filtros: { nota: ['media_baja'] } },
    { id: 'sin_nota', etiqueta: 'Sin nota', filtros: { nota: ['np'] } }
  ],
  faltan: [
    { id: 'sin_sinopsis', etiqueta: 'Sin sinopsis',
      filtros: { calidad: ['sin_sinopsis'] } },
    { id: 'sin_reparto', etiqueta: 'Sin reparto',
      filtros: { calidad: ['sin_reparto'] } },
    { id: 'sin_poster', etiqueta: 'Sin póster',
      filtros: { calidad: ['sin_poster'] } }
  ]
};
```

`aplicarPresetKPI` reemplaza `estadoFiltros.lista` con los filtros del preset, vacía `#q` y `q`, renderiza la lista, pinta chips, guarda la sesión, cierra el panel, hace `scrollIntoView({block: 'start'})` sobre `#lista` y enfoca el `h2` de la sección (`tabindex="-1"`).

- [ ] **Step 5: Activar los botones agregados**

Quitar `disabled` y `data-pendiente` de las secciones `generos`, `directores` y `actores`. Conectar sus paneles a `abrirPanelFiltro`.

- [ ] **Step 6: Ejecutar los tests**

Run: `python -m unittest tests.test_vista_html -v`
Expected: PASS.

- [ ] **Step 7: Verificar en navegador**

- En «Géneros», filtrar por década `1990`: los recuentos y las medias cambian respecto al estado sin filtro; la barra se recalcula.
- En «Directores», fijar mínimo `3+`: desaparecen los directores con menos títulos.
- En «Actores», filtrar por tipo `Película`: solo quedan actores con películas valoradas.
- Pulsar el icono del KPI «En seguimiento» y «Solo pendientes`: la Lista completa baja, muestra solo filas `NP`, el chip aparece y el badge cuenta 1.
- Pulsar el icono del KPI «Tu nota media» y «Por encima de mi media»: todas las filas visibles tienen nota mayor que la media calculada.
- Limpiar desde el chip: vuelve el estado completo y el paginador se resetea.

- [ ] **Step 8: Commit**

```bash
git add scripts/generar_vista.py tests/test_vista_html.py
git commit -m "feat: agregados filtrados y presets de KPI"
```

---

### Task 7: Documentación, captura y verificación final

**Files:**
- Modify: `README.md`, `AGENTS.md`, `preview/dashboard.html`, `docs/assets/dashboard.png`
- Verify: `tests/test_vista_html.py`, `docs/responsive-design.md`

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: documentación actualizada, panel regenerado y evidencia de la matriz responsive.

- [ ] **Step 1: Actualizar README**

Añadir a «Qué es» una viñeta sobre el panel responsive y los filtros. Añadir un enlace a [`docs/responsive-design.md`](docs/responsive-design.md) en «Decisiones de diseño». Actualizar el recuento de tests al número real.

- [ ] **Step 2: Actualizar AGENTS.md**

Cambiar `41 tests` por el recuento real. No cambiar comandos ni reglas.

- [ ] **Step 3: Regenerar el panel**

Run: `python scripts/generar_vista.py`
Expected: `preview/dashboard.html` actualizado.

- [ ] **Step 4: Ejecutar la suite completa**

Run: `python -m unittest discover -s tests`
Expected: todos los tests OK. Guardar el número exacto para README y AGENTS.

- [ ] **Step 5: Comprobar sintaxis 3.11**

Run:

```bash
python - <<'PY'
import ast
from pathlib import Path
for p in ("scripts/generar_vista.py", "tests/test_vista_html.py"):
    ast.parse(Path(p).read_text(encoding="utf-8"), filename=p,
              feature_version=(3, 11))
    print("OK", p)
PY
```

Expected: `OK` para ambos.

- [ ] **Step 6: Matriz de navegador final**

A 320, 375, 768 y 1440 px:

```js
document.documentElement.scrollWidth <= window.innerWidth
```

Expected: `true` en los cuatro. Comprobar además: KPIs 2/2/3/5 columnas; pósters 2/3/4/5; tablas en tarjetas a 375 y normales a 1440; panel de filtros dentro del viewport; sin errores en consola; ficha con sinopsis al final y «Leer más» solo en móvil. Repetir a 320 px con zoom del 200 % y confirmar que no aparece scroll horizontal.

- [ ] **Step 7: Actualizar la captura**

Con el panel a 1440 px, capturar `docs/assets/dashboard.png` y comprobar que se ve el strip de pósters, la cabecera y al menos una sección con el icono de filtro.

- [ ] **Step 8: Revisar el diff**

Run: `git diff --check`
Expected: sin errores.

Run: `git status --short`
Expected: solo los archivos de este plan; `ROADMAP.md` y la spec multiusuario siguen sin tocar.

- [ ] **Step 9: Commit**

```bash
git add README.md AGENTS.md preview/dashboard.html docs/assets/dashboard.png docs/responsive-design.md
git commit -m "docs: panel responsive, filtros y captura actualizada"
```

---

## Self-review

- **Cobertura de la spec:** responsive (tareas 3 y 7), sinopsis al final (tarea 4), filtros por KPI/sección/lista (tareas 5 y 6), estrategias de tabla documentadas (tarea 1), sesión y chips (tarea 5), accesibilidad (tareas 3, 4 y 5).
- **Contrato de datos:** una sola fuente `catalogo-data`; las claves usadas por el motor (`nota`, `imdb`, `diferencia`, `generos`, `directores`, `reparto`, `sin_sinopsis`, `sin_reparto`, `year`, `tipo`) están definidas en la tarea 2 y consumidas en las tareas 5 y 6.
- **Paginación:** se reemplaza el bucle global por `montarPaginador`; todas las tablas pasan por `renderSeccion` o conservan el paginador genérico hasta la tarea 6.
- **Riesgo principal:** el tamaño del JavaScript generado. Se mitiga con funciones pequeñas, render genérico por columnas y verificación en navegador después de cada tarea.
