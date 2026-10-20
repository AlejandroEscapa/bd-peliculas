# Diseño responsive, ficha y filtros del panel

**Estado:** aprobado el 2026-10-19.
**Alcance:** `preview/dashboard.html` generado por `scripts/generar_vista.py`.
**Restricciones:** HTML estático, Python stdlib, sin dependencias, sin peticiones al servidor y sin cambios de esquema.

## Decisiones validadas

1. Las tablas se convierten en **tarjetas apiladas** en contenedores estrechos. Las otras dos estrategias quedan documentadas abajo para poder recuperarlas sin rediseñar.
2. Los filtros **recalculan los agregados** desde el catálogo filtrado: géneros, directores, actores, joyas y decepciones responden al subconjunto activo.
3. El icono de cada KPI **aplica un preset a Lista completa** y desplaza la vista hasta ella. No modifica otras secciones.
4. UI de filtros: **popover + chips + `sessionStorage`**. Los filtros sobreviven a una recarga de la pestaña y se limpian al cerrarla.
5. La sinopsis es el **último bloque de la ficha** y ocupa todo el ancho. En escritorio se muestra completa; en móvil se pliega a 4 líneas con «Leer más».
6. Facetas disponibles: tipo, género, década, tu nota, IMDb, diferencia con IMDb, estado, calidad del dato y ordenación. Cada sección muestra solo las que tengan sentido para lo que calcula.

## Estrategias de tabla

### Estrategia 1 — Tarjetas apiladas (elegida)

Cada `td` lleva `data-label="..."`. Bajo un contenedor de 640 px, `thead` desaparece y cada `tr` pasa a ser una tarjeta; el título ocupa la primera línea y el resto de campos se muestran como pares etiqueta/valor.

```css
.seccion { container-type: inline-size; }

@container (max-width: 640px) {
  .tabla-cards thead { display: none; }
  .tabla-cards tr { display: block; border: 1px solid var(--line); border-radius: 14px; padding: 12px; }
  .tabla-cards td { display: flex; justify-content: space-between; gap: 12px; border: 0; }
  .tabla-cards td::before { content: attr(data-label); color: var(--sub); }
}
```

- **Ventajas:** no hay scroll lateral, se lee a 320 px, funciona con lector de pantalla y mantiene el orden lógico del DOM.
- **Coste:** más altura y una regla CSS por tabla; la primera celda necesita un tratamiento especial para no repetir el título.
- **Uso:** todas las tablas del panel. La consulta de contenedor permite que una tabla a media anchura en escritorio también use tarjetas si le falta espacio.

### Estrategia 2 — Scroll horizontal con primera columna fija

La tabla conserva su estructura; un contenedor con `overflow-x: auto` permite desplazarse y la primera columna se queda fija.

```css
.tabla-scroll { overflow-x: auto; overscroll-behavior-inline: contain; }
.tabla-scroll table { min-width: 680px; }
.tabla-scroll th:first-child,
.tabla-scroll td:first-child {
  position: sticky; left: 0; background: var(--card); z-index: 1;
  box-shadow: 1px 0 0 var(--line);
}
.tabla-scroll:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
```

- **Ventajas:** comparación numérica densa, muchas columnas, poca altura.
- **Coste:** gesto lateral y columnas ocultas; en móvil compite con el swipe del navegador. El contenedor debe ser focusable (`tabindex="0"`, `role="region"`, `aria-label`) para que se pueda recorrer con teclado.
- **Uso:** solo si en el futuro una tabla supera 8 columnas o necesita comparar cifras en horizontal. No se implementa ahora.

### Estrategia 3 — Híbrido por sección

Tarjetas para Lista completa y scroll horizontal para las tablas analíticas de géneros, directores y actores.

- **Ventajas:** cada tabla usa el patrón que mejor le sienta.
- **Coste:** dos comportamientos que explicar y dos rutas de CSS/JS que mantener; la misma tabla puede cambiar de patrón según la sección.
- **Uso:** descartado en esta iteración por inconsistencia. Queda como referencia si las tablas analíticas ganan muchas columnas.

## Breakpoints y layout

Enfoque mobile-first. Los cortes son de contenido, no de dispositivo:

| Corte | Qué cambia |
|---|---|
| base (320 px+) | una columna, padding fluido, KPIs 2×2, pósters 2 columnas, tablas en tarjetas |
| 480 px | pósters 3 columnas |
| 640 px | KPIs 3 columnas, padding mayor, pósters 4 columnas |
| 900 px | KPIs 5 columnas, `grid2` a 2 columnas, header en fila, pósters 5 columnas |
| 1200 px | `max-width` de 1120 px; sin más cambios estructurales |

Reglas:

- Tipografía fluida con `clamp()` en `h1`, `h2`, cifras KPI y espaciado.
- `100dvh` en la ficha móvil; nunca `100vh` a secas.
- `env(safe-area-inset-bottom)` en el padding inferior.
- Targets táctiles de 44×44 px como mínimo.
- `overflow-wrap: anywhere` en títulos y textos largos; `min-width: 0` en hijos de grid/flex.
- `@media (prefers-reduced-motion: reduce)` desactiva transiciones.
- `:focus-visible` visible en todos los controles.

## Ficha de película

Estructura nueva, en este orden:

1. **Cabecera** en dos columnas: póster, tu nota y enlace a IMDb a la izquierda; título, metadatos, reparto, dirección, géneros y países a la derecha.
2. **Sinopsis** fuera de la cabecera, al final, a todo el ancho del contenedor. Es el último bloque; no hay nada después salvo el cierre.
3. En móvil la ficha ocupa `100dvh`, el póster baja a 96 px y la sinopsis se pliega a 4 líneas con un botón «Leer más» (`aria-expanded`). El botón solo aparece si el texto supera ~280 caracteres.
4. Se conserva el diálogo accesible: `role="dialog"`, `aria-modal="true"`, foco atrapado, Escape y devolución del foco al disparador.

## Filtros

### Modelo

Cada sección tiene su propio estado. Dentro de una faceta, las opciones se suman con OR; entre facetas se combinan con AND. La ordenación es única por sección.

```js
{
  lista: { facetas: { genero: ["Drama"], nota: ["10"] }, orden: "titulo_asc", q: "" },
  top:   { facetas: { tipo: ["Película"] }, orden: "nota_desc" }
}
```

- Clave de sesión: `db-peliculas:filtros:v1`.
- Al restaurar se validan sección, faceta y opción; cualquier valor desconocido se ignora.
- `sessionStorage` va envuelto en `try/catch`: en `file://`, modo privado o almacenamiento lleno el panel funciona sin memoria.
- «Limpiar» borra solo la sección abierta. Los chips permiten quitar una faceta concreta.
- El badge del icono cuenta grupos de facetas activos, no selecciones sueltas.

### Matriz por sección

| Sección | Base | Facetas | Orden por defecto |
|---|---|---|---|
| Pósters | valoradas | tipo, género, década, tu nota, orden | tu nota ↓ |
| Tus favoritas | valoradas | tipo, género, década, tu nota, IMDb, orden | tu nota ↓ |
| Joyas | diferencia ≥ +1.5 | tipo, género, década, tu nota, IMDb, diferencia, orden | diferencia ↓ |
| Decepciones | diferencia ≤ −1.5 | tipo, género, década, tu nota, IMDb, diferencia, orden | diferencia ↓ |
| Géneros | valoradas | tipo, década, mínimo de títulos, nota media, orden | títulos ↓ |
| Directores | valoradas | tipo, década, mínimo de títulos, nota media, orden | títulos ↓ |
| Actores | valoradas, mínimo 2 títulos | tipo, década, mínimo de títulos, nota media, orden | títulos ↓ |
| Lista completa | todas | tipo, género, década, estado, tu nota, IMDb, calidad, orden | título A-Z |
| En seguimiento | sin nota | tipo, género, década, IMDb, calidad, orden | IMDb ↓ |

«Calidad del dato» ofrece: sin sinopsis, sin reparto, sin póster y ficha completa. «Diferencia con IMDb» solo aparece en joyas y decepciones. «Mínimo de títulos» y «nota media» solo en las tres secciones agregadas.

### Presets de KPI

Todos aplican sobre **Lista completa**, sustituyen sus filtros y hacen scroll hasta la sección. El icono del KPI no cambia otras secciones.

| KPI | Presets |
|---|---|
| Títulos | Ver todo |
| Valoradas por ti | Solo valoradas |
| En seguimiento | Solo pendientes |
| Tu nota media | Por encima de la media, por debajo de la media, sin nota |
| Sin enriquecer | Sin sinopsis, sin reparto, sin póster |

### UI y accesibilidad

- Icono de embudo inline SVG, 18 px, dentro de un botón de 44×44 px. Solo icono, con `aria-label` explícito y badge numérico.
- `aria-haspopup="dialog"`, `aria-expanded`, `aria-controls`.
- Panel `role="dialog"` con título, checkboxes/radios nativos, botón de cierre y «Limpiar».
- Chips de filtros activos con botón de quitar y `aria-label="Quitar filtro …"`.
- Resumen de resultados en `aria-live="polite"`.
- Escape cierra y devuelve el foco al icono; clic fuera cierra.
- Todo texto de la base se pinta con `textContent`, nunca con `innerHTML`.

## Contrato de datos

Un único `<script type="application/json" id="catalogo-data">` con un objeto indexado por `tt`. Sustituye a `indice-data` y `fichas-data` para no duplicar el catálogo.

```json
{
  "tt0068646": {
    "titulo": "El padrino",
    "original": "The Godfather",
    "url": "https://www.imdb.com/title/tt0068646/",
    "tipo": "Película",
    "year": 1972,
    "imdb": 9.2,
    "nota": 10,
    "fecha": "2026-09-12",
    "estado": "rated",
    "duracion": 175,
    "sinopsis": "…",
    "poster": "https://…",
    "sin_sinopsis": false,
    "sin_reparto": false,
    "diferencia": 0.8,
    "reparto": [{ "nombre": "Marlon Brando", "personaje": "Vito Corleone" }],
    "directores": ["Francis Ford Coppola"],
    "paises": ["US"],
    "generos": ["Crimen", "Drama"]
  }
}
```

- `estado` se deriva de `nota`: `rated` si hay nota, `watchlist` si no.
- `diferencia` es `nota − imdb`, redondeada a un decimal, o `null`.
- `sin_sinopsis` y `sin_reparto` son booleanos calculados en Python.
- El JSON escapa `</` para no cerrar el `<script>`.
- Las filas renderizadas en servidor siguen existiendo como fallback sin JavaScript y siguen pasando por `html.escape`.

## Verificación

- `unittest` cubre estructura, datos, etiquetas, escapado y marcadores de accesibilidad.
- El navegador cubre lo que el HTML estático no puede: 320/375/768/1440 px, overflow horizontal, filtros combinados, recálculo de agregados, sesión, teclado y ficha.
- Criterio de responsive: `document.documentElement.scrollWidth <= window.innerWidth` en los cuatro anchos.
- Criterio de filtros: toda combinación sin resultados muestra un estado vacío, no una tabla rota ni un error de consola.

## Fuera de alcance

- Modo oscuro, PWA, multiusuario, filtros en servidor y nuevas dependencias.
- Cambios de esquema o migraciones.
- Reescribir `ROADMAP.md` o la spec multiusuario, que tienen cambios locales sin commitear.
