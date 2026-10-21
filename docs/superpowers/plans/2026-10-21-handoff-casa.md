# Handoff para el agente de casa (2026-10-21)

> Esto es un **prompt listo para copiar y pegar** a tu agente. Está escrito para
> que pueda ejecutarlo sin contexto previo: incluye el estado real, los
> comandos exactos, las reglas del repo y cómo debe informarte al terminar.
>
> El bloque de abajo es lo que le pasas. El resto del fichero es el mismo
> contenido en forma legible, por si prefieres leerlo tú antes.

---

## El prompt (copiar desde aquí)

````text
Trabaja en el repo C:\Users\alejandrolivares\Desktop\mis-herramientas\bd-peliculas.
Es un catálogo personal de IMDb: SQLite + Python stdlib (cero dependencias) y
un panel HTML estático que se regenera desde la base. Todo el código está ya
commiteado y pusheado. Tu trabajo NO es escribir código nuevo: es terminar la
publicación pendiente usando la base de datos real, que solo existe en esta
máquina.

## 1. Antes de tocar nada, comprueba que la base es la buena

    cd C:\Users\alejandrolivares\Desktop\mis-herramientas\bd-peliculas
    git pull
    python -c "import sqlite3; c=sqlite3.connect('data/catalogo.db'); print(c.execute('SELECT COUNT(*) FROM titles').fetchone()[0], c.execute('SELECT COUNT(*) FROM user_state WHERE my_rating IS NOT NULL').fetchone()[0])"

Tiene que imprimir 207 títulos y 148 valoradas. Si no, PARA y avisa: no
sigas. Puede ser un resto de una ejecución con una ruta equivocada; hay copias
en backups/ (python scripts/backup.py). No publiques con una base vacía.

## 2. Qué falta y por qué

El panel publicado (https://bd-peliculas-weld.vercel.app) se generó fuera de
esta máquina, desde una reconstrucción fiel del catálogo ya publicado. Se
comprobó que era equivalente: mismos 207 tt, mismas notas, mismos actores y
directores, y las tablas (actores, directores, tus favoritas, joyas,
decepciones, lista, seguimiento) salen idénticas fila a fila.

Lo único que le faltan son las SAGAS. El hueco "coleccion" se añadió al
pipeline (TMDB devuelve `belongs_to_collection` en la respuesta de detalle que
ya se pedía, así que no cuesta ninguna petición extra), pero el scraper no se
ha ejecutado desde que ese hueco existe. Por eso `title_collections` está
vacía y la ficha no muestra el bloque "Colección".

## 3. Los tres pasos, en este orden

### Paso 1 — rellenar el hueco `coleccion` (5-10 min)

    python scripts/scrapear_peliculas.py --proveedor src.proveedores.combinado:ProveedorCombinado --limite 207 --delay 1.5

Vuelve a pedir el detalle de los 207 títulos. No es un coste nuevo de API (el
campo venía en respuestas que ya se pagaban), pero el hueco está abierto en
todos y hay que rehacerlos. Deja copia de seguridad en backups/.

Comprueba que el hueco desapareció:

    python -c "from src.huecos import listar_huecos; print(sum(1 for h in listar_huecos('data/catalogo.db') if h['campo']=='coleccion'))"

Debe imprimir 0.

### Paso 2 — derivar las sagas (instantáneo, idempotente)

    python scripts/derivar_relaciones.py

Imprime "N colecciones, M relaciones nuevas". Si M es 0 no es un error:
significa que ningún par de tus títulos comparte colección. Si N es 0, el paso 1
no ha funcionado: vuelve a él.

### Paso 3 — publicar con el guard (NO uses generar_vista.py a mano)

    python scripts/publicar.py --dry-run

Compara el snapshot nuevo con el publicado. Si el nuevo tiene menos títulos,
valoradas, sinopsis, pósteres, reparto, directores o actores distintos, PARA
y avisa (código de salida 3): no se toca nada. Si dice que no pierde nada:

    python scripts/publicar.py --push

Ese script copia la base, genera a un temporal, compara, y solo entonces
sustituye el HTML, hace commit y push. El push dispara el CI y Vercel
redespliega.

## 4. Verifica (no te fíes del "hecho")

- En la web, abre la ficha de un título de una saga (Harry Potter, Dune, El
  Señor de los Anillos, Batman, Spider-Man, Alien, Sinister, Narcos,
  Jujutsu Kaisen, Depredador, Guardianes, El hoyo) y comprueba que aparece el
  bloque "Colección" con las partes de tu catálogo, por año y con tu nota.
- La sección "Para ti" sigue con sus motivos y los botones "+N más".
- "Notas por década" sigue con su embudo de filtro.
- Los KPI de arriba son enlaces, sin embudo, y llevan a su sección.
- GitHub Actions en verde y `git status` limpio.

## 5. Reglas del repo (no negociables)

- El CSV de IMDb es ENTRADA DELTA: solo escribe las columnas que posee y un
  campo vacío jamás borra un enriquecimiento. No toques `user_state`.
- El enriquecido solo rellena huecos (INSERT OR IGNORE). Un título roto no
  puede abortar el lote.
- `db/views.sql` es solo lectura. Las migraciones son forward-only.
- Cero dependencias en tiempo de ejecución: solo stdlib. Nada de pip.
- Secretos solo por entorno (`TMDB_BEARER`, `OMDB_API_KEY`): nunca en código,
  ni en `.env`, ni en Git. No los imprimas en logs ni en tu informe.
- El panel es HTML estático en español, paginación 15+15, consultas
  parametrizadas y `html.escape` en todo texto que venga de la base.
- Una idea visual a la vez: se propone y solo se implementa la aceptada.
- Antes de commitear: `python -m unittest discover -s tests` en verde (121).

## 6. Lo que NO debes hacer

- No uses `scripts/semilla.py` para el panel real: esa base es la de trabajo,
  con notas sintéticas, y sirve para la demo (`/demo`). El panel real sale de
  `data/catalogo.db`.
- No inventes datos: los nombres de colección vienen de TMDB. Si una saga no
  aparece, es que TMDB no la tiene para ese título.
- No borres `data/` ni `backups/`, ni rehagas el generador entero: son 1600
  líneas con el JS dentro de un f-string y se rompe fácil.
- No toques la lógica del motor (`src/motor.py`) sin motivo. `PESOS`,
  `UMBRAL_LIFT` (0.5) y `MIN_MUESTRAS` (2) están calibrados contra tus 148
  notas; si los tocas, enséñame antes el antes/después con datos reales.
- No publiques sin pasar por `publicar.py`.

## 7. Si te queda tiempo (el roadmap, una cosa cada vez)

En este orden, y solo si los pasos 1-3 están verdes y publicados:

1. "Tus guionistas favoritos": el dato (`title_credits` con rol writer,
   producer, composer) ya está descargado; es solo enseñarlo.
2. "Mi perfil": la sección ya existe; se puede afinar con los lift reales.
3. Cola de decisión / "Qué ver hoy": el motor ya calcula encaje y motivos;
   falta la pieza de producto.
4. Fase 2 TMDB: `estreno_es`, `presupuesto`/`taquilla`, `serie_info`.

El porqué de cada uno está en ROADMAP.md y en
docs/superpowers/plans/2026-10-20-motor-y-profesionalizacion.md.

## 8. Informe final

Dime, en este orden y con la salida real pegada:

1. Qué comandos ejecutaste y qué devolvieron.
2. La comparación del guard: antes y después, métrica a métrica.
3. Qué ha cambiado en el panel (con captura si puedes).
4. Estado del CI y si el push llegó a `origin/main`.
5. Lo que te ha sustituido, lo que no pudiste hacer, y qué recomiendas ahora.
````

---

## Notas para ti (no son parte del prompt)

**Por qué el prompt es autónomo:** no da por supuesto que ningún informe mío
llegue a casa. Lleva el estado, los comandos, las reglas y el formato de
informe. Un agente que solo reciba ese bloque puede terminar el trabajo sin
preguntar nada, salvo que la base no sea la buena — y para eso hay una
condición de parada explícita (§1).

**Lo que hay que vigilar al ejecutarlo:**

- El paso 1 **vuelve a pedir los 207 títulos**. No es un coste nuevo de API
  (el campo `belongs_to_collection` venía en respuestas que ya se pagaban),
  pero el hueco está abierto en todos, así que hay que rehacer las peticiones.
  Con `--delay 1.5` son unos 5-10 minutos. Ojo con el límite de OMDb
  (1000 peticiones/día).
- El paso 3 **es el que protege tu trabajo**: `publicar.py` copia la base,
  compara el snapshot nuevo con el publicado y se niega a publicar si el panel
  pierde algo. Si sale con código 3, no ha tocado nada.
- El paso 1 **solo puede fallar sin daño**: el enriquecido rellena huecos con
  `INSERT OR IGNORE`, nunca borra, y el guard impide publicar un panel peor.
- La condición de parada del §1 (207/148) es la que evitó que yo cometiera un
  error hoy: un comando con una ruta equivocada me dejó un
  `data/catalogo.db` **vacío** en este entorno. Por eso `generar_vista.py`
  ahora falla con un mensaje claro si la base no existe o tiene 0 títulos, y
  por eso el prompt pide comprobar el recuento antes de nada.
