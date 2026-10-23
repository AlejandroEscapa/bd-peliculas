# Roadmap — Catálogo personal (db-peliculas)

> Orden de ataque con los planes pendientes (2026-10-23):
> [`docs/2026-10-23-reporte-pendientes.md`](docs/2026-10-23-reporte-pendientes.md).

Estado a 2026-10-22 (publicado desde la base real): 208 títulos, 149 valoradas, 0 títulos sin enriquecer (208/208), 45 colecciones de TMDB (11 sagas con más de una parte en tu catálogo), 54 relaciones de saga. Suite 140/140 OK.
Panel en `preview/dashboard.html`: responsive mobile-first, buscador global, ficha overlay con sinopsis al final y la Colección debajo a todo el ancho, strip de pósters, motor de filtros por sección (facetas + orden) y paginación reactiva, Joyas/Decepciones + Géneros/Directores/Actores, KPIs extra (Exigencia y Enriquecidos X/208), Notas por década y "Para ti" (pendientes ordenados por encaje, con su porqué y las filas a la misma altura). **Todas las secciones se pliegan** (menos el strip de pósters; "Para ti" abre) y el panel **se sirve con un zoom del 110%**. Todo centrado menos títulos, "por qué" y géneros.
Tuberías conectadas (2026-10-20): colecciones de TMDB (`belongs_to_collection`, 0 peticiones extra) en `title_collections`, con relaciones saga derivadas en `title_relations`; `schema_version` ya se registra al aplicar el esquema. La ficha muestra el bloque "Colección" con las partes de tu catálogo, por año y con tu nota.
Altas a mano (2026-10-22): `scripts/anadir_pelicula.py` da de alta una película con su nota y la enriquece, sin duplicar y sin que el CSV posterior la pise (skill global `anadir-peliculas`).
Watcher `scripts/auto_vista.py` verificado. Suite 140/140 OK.

## Trampa de TMDB (2026-10-21)

`GET /find/{imdb_id}` **exige `external_source=imdb_id`**: sin ese parámetro
responde 404 (`status_code` 34) y el scraper se queda solo con OMDb, que no
trae `belongs_to_collection` (el hueco `coleccion` no se cierra nunca) ni
frescura el resto de campos de TMDB. Fix en `src/proveedores/tmdb.py`
(`_get` acepta parámetros extra) con test de regresión.

## Rediseño de la interfaz (2026-10-21)

- Sistema de columnas: tipos `c-num` (cifras a la derecha, con cifras de ancho
  fijo y nunca partidas), `c-titulo`, `c-razon`, `c-encaje`, y `<colgroup>` por
  tabla. La causa de que un "2004" saliera partido era `overflow-wrap: anywhere`
  en el body: ahora es `break-word`.
- Joyas y Decepciones pasan a **tarjeta**: título arriba y los tres datos
  (tu nota, IMDb, diferencia) en una fila alineada debajo.
- Géneros, Directores, Actores y Décadas vuelven a ser **lista básica** de tres
  columnas (valor, títulos, media), sin la barra de distribución que los
  descuadraba y sin el botón de filtro muerto.
- Los KPI ya no se cortan ("177/207") y las etiquetas quedan alineadas.
- Verificado con capturas reales en Edge headless (CDP), escritorio y móvil.

## Ajustes de interfaz (2026-10-21, sobre el rediseño)

- Los **KPI ya no filtran**: son enlaces que llevan a la sección que explica el
  número (Títulos → Lista completa, Valoradas → Tus favoritas, Tu nota media y
  Exigencia → Mi perfil, En seguimiento → En seguimiento). Fuera el embudo, fuera
  el motor de presets. Si "Mi perfil" no tiene nada que enseñar (catálogo
  pequeño), esos KPI llevan a la lista en vez de a un ancla inexistente.
- **"Para ti" con altura uniforme**: la celda del motivo reserva el alto del
  motivo más largo, así que todas las filas miden lo mismo. Los motivos
  secundarios se pliegan tras un botón "+N más" que los despliega en sitio.
- **"Tus favoritas" con las cifras centradas**: en una tabla corta, una
  columna estrecha alineada a la derecha parece perdida.
- **"Notas por década" filtrable**: deja de ser una tabla estática y usa el
  filtro estándar (tipo, década, tu nota y orden). El motor agrega en cliente
  los títulos que pasan el filtro.

## Alineación y KPI (2026-10-22, sobre el rediseño)

- **Todo centrado menos títulos, "por qué" y géneros**: son los que ocupan. Las
  cifras (`c-num`) pasan de alinear a la derecha a centrarse — tu nota, IMDb,
  año, nº de títulos, media y diferencia — y el texto corto ("Tipo") usa la
  clase nueva `c-centro`. Se va la clase `tabla-centrada`, que ya solo
  servía para centrarlas en una tabla.
- **KPI que ocupan su espacio**: cada tarjeta es una rejilla de dos filas
  (número y flecha arriba, etiqueta abajo) y la etiqueta vive en **una sola
  línea** que llega hasta los márgenes. Se acaba el `min-height: 2.6em` que
  reservaba una segunda línea vacía. Si la etiqueta no cabe, se recorta con
  puntos suspensivos y el texto íntegro queda en el `title` (y el
  `aria-label` no pierde información). "Exigencia (tú − IMDb)" pasa a
  "Exigencia (tú−IMDb)" para que quepa entera.
- **"Para ti" con todas las filas a la misma altura**: la celda del motivo
  tiene alto fijo (6.4em, padding incluido) y es una columna flexible: el
  motivo ocupa todo el ancho y el botón "+N más" va en su propia línea, con
  `space-between` para que todos los botones caigan a la misma altura. El
  motivo se corta a dos líneas (con `…`) para que el botón nunca se solape.
  Al abrir los motivos secundarios, la celda crece (`height: auto`).

## Secciones plegables (2026-10-22)

- **Todas las secciones menos las pills** se pliegan: el strip de pósters
  ("Tus favoritas, en cartel") se queda siempre visible. Plegada, una sección
  es una tira con el título, una descripción corta (con el texto íntegro en
  el `title`) y la flecha de la derecha.
- **El mando es un botón de verdad** (`plegable-tap`) transparente que cubre
  toda la cabecera: se pliega con clic en el título, en la descripción o en
  la flecha, y con Enter o Espacio desde el teclado. `aria-expanded` y
  `aria-controls` van con él, y la flecha gira al desplegar.
- **"Para ti" arranca abierta**; el resto, plegadas. Si un KPI lleva a una
  sección plegada, esta se despliega antes de llevarte allí (si no, el KPI
  apuntaría a una tira sin contenido).
- La cabecera pasa a ser una fila: título, descripción y acciones (filtro y
  flecha) en la misma línea. En móvil la descripción baja a su propia línea.

## Ficha y listas (2026-10-22)

- **La colección va debajo de la sinopsis** y ocupa todo el ancho de la ficha:
  las partes de la saga son tarjetas en rejilla (`auto-fill`), no una columna
  estrecha. La nota ya no se repite bajo el póster (está en la línea de
  metadatos, con el título).
- **Actores de confianza** tenía las cifras sin clase de columna: los
  números quedaban a la izquierda mientras la cabecera pedía el centro. Ahora
  usa las mismas clases que las demás tablas (`c-num`).
- **Joyas y Decepciones**: el título con su año va centrado y con más aire
  hasta la fila de datos (tu nota, IMDb, diferencia).
- **"Mi perfil"**: cada item mide 42 px, como una fila de "Tus favoritas", y
  el subtítulo va en su propio elemento para que caiga alineado en todas las
  filas.

## Zoom, tiras centradas y cabeceras limpias (2026-10-22)

- **Zoom del 110%** con `html { zoom: 1.1 }`: es el mismo mecanismo que el
  zoom del navegador, aplicado al elemento raíz, así que escala tipografía,
  espaciados, bordes y radios de una vez. Verificado: sin scroll horizontal y
  la ficha (position: fixed) sigue cubriendo la ventana. Donde el navegador no
  lo soporta (Safari < 16.4, Firefox < 126) la web funciona igual, solo que
  sin escalar.
- **Tiras plegadas centradas**: la cabecera conservaba su `margin-bottom`
  cuando el cuerpo se ocultaba, así que el par título+descripción quedaba
  14 px por encima del centro. Con `section.plegada .section-head { margin-bottom: 0 }`
  el desvío medido es 0 px.
- **Cabeceras sin texto de paginación**: fuera "15 visibles, carga 15 más",
  "Pulsa una para abrir la ficha" y "Filtra sin recargar". El botón "Cargar
  15 más (45 restantes)" y el "Mostrando 15 de 60" de debajo de cada tabla ya
  cuentan lo mismo, y las tiras plegadas quedan más limpias.

## Publicar sin perder nada (2026-10-21)

- `scripts/publicar.py` sustituye al `generar_vista.py` + `git commit` a mano: copia la base, genera a un temporal, **compara con el snapshot publicado** y solo lo sustituye si no pierde títulos, valoradas, sinopsis, pósteres ni reparto. Si pierde algo, sale con código 3 sin tocar nada.
- El scraper también hace copia de seguridad antes de enriquecer (`--sin-backup` para saltarla).

## Base semilla (2026-10-21)

- `scripts/semilla.py` construye `data/semilla.db` a partir del snapshot publicado: los mismos 207 títulos con **notas sintéticas** (deterministas, correlacionadas con el IMDb y con una preferencia por géneros) y las **sagas reales** detectadas por título. Sirve para iterar la interfaz sin la base real ni red, y para la demo pública en `/demo`.
- `preview/semilla.html` es el artefacto de esa demo; se regenera con `python scripts/semilla.py && python scripts/generar_vista.py --db data/semilla.db --salida preview/semilla.html`.

## PENDIENTES AL LLEGAR A CASA (2026-10-20) — HECHOS (2026-10-21)

> **Handoff completo** (guion, verificaciones, mapa del código, decisiones
> tomadas y trampas conocidas): [`docs/superpowers/plans/2026-10-20-handoff.md`](docs/superpowers/plans/2026-10-20-handoff.md).
>
> **Prompt para el agente de casa** (autónomo, listo para copiar y pegar):
> [`docs/superpowers/plans/2026-10-21-handoff-casa.md`](docs/superpowers/plans/2026-10-21-handoff-casa.md).

> **Todo está commiteado y pusheado** (`main` = `origin/main`), suite
> 140/140 en verde, y **la vista está publicada desde la base real**:
> `preview/dashboard.html` lleva el rediseño, el motor depurado, los KPI
> navegables, **las sagas**, las secciones plegables y el zoom del 110%.
>
> **Estado (2026-10-21):** ejecutados los 3 pasos del prompt de handoff sobre
> la base real (`data/catalogo.db`, 207 títulos / 148 valoradas *en ese
> momento*; hoy son 208 / 149 con "La bola negra" añadida a mano).
>
> - **Bloqueo encontrado y arreglado**: TMDB ya no responde `/find/{tt}` sin
>   `external_source=imdb_id` (404, `status_code` 34), así que el scraper
>   caía a OMDb y el hueco `coleccion` no se cerraba nunca. Fix en
>   `src/proveedores/tmdb.py` (commit `add9574`) + test de regresión.
> - Scraper: 207/207 títulos, 0 fallos, `coleccion` rellenada en los 207
>   (45 colecciones, 11 con más de una parte en tu catálogo).
> - `derivar_relaciones.py`: 45 colecciones, 54 relaciones nuevas (37
>   `universe`, 17 `sequel`).
> - `publicar.py --dry-run` → sin pérdidas; `--push` → commit `f35f727`,
>   CI en verde, Vercel redesplegó.
> - El guard, métrica a métrica: títulos 207 → 207, valoradas 148 → 148,
>   con sinopsis 177 → 207, con póster 177 → 207, con reparto 177 → 207,
>   con géneros 207 → 207, directores 141 → 144, actores 427 → 609,
>   recomendaciones 35 → 35.

### 1. Regenerar desde tu base real (~25 min) — HECHO

Ya está publicado; esto lo deja **definitivo** (y de paso añade las sagas).

- [x] **Rellenar el hueco `coleccion`** — el scraper lee
      `belongs_to_collection` de la respuesta de detalle que TMDB ya te
      pedía, así que **no gastas peticiones extra**. Ojo: el scraper ahora
      aplica el esquema vigente, tu base gana la tabla `title_collections`
      sola (no hace falta reimportar el CSV).
      ```bat
      python scripts/scrapear_peliculas.py --proveedor src.proveedores.combinado:ProveedorCombinado --limite 207 --delay 1.5
      ```
      Verificado: `listar_huecos()` ya no devuelve ningún hueco `coleccion`.
- [x] **Derivar las sagas** (idempotente, se puede repetir sin miedo):
      ```bat
      python scripts/derivar_relaciones.py
      ```
      Verificado: "45 colecciones, 54 relaciones nuevas".
- [x] **Regenerar el snapshot** (esto es lo que faltaba para que se vieran
      los KPIs nuevos y la sección por década). Ojo: **no** se hace a mano;
      lo hace `publicar.py`, que compara antes de sustituir.
      ```bat
      python scripts/publicar.py --dry-run
      ```
- [x] **Publicar el snapshot** (el código ya está subido; esto es lo único
      que queda por ver):
      ```bat
      python scripts/publicar.py --push
      ```
      El push dispara el CI de GitHub Actions y Vercel redespliega.

### 2. Comprobar en el navegador (~10 min) — HECHO

- [x] Los **7 KPIs** (salen "Exigencia" y "Enriquecidos", que no estaban en el
      snapshot publicado) y la sección **"Notas por década"**.
- [x] Los botones de los KPIs: **antes estaban muertos** (la rama los dejó sin
      wiring). Ahora "Valoradas" y "Sin enriquecer" aplican un preset sobre
      Lista completa. "Tu nota media" y "Exigencia" salen **deshabilitados**:
      son promedios, no conjuntos de títulos.
- [x] La **ficha** con el bloque "Colección": partes de tu saga por año, con tu
      nota, y el clic en una parte abre su ficha.
- [ ] En móvil: responsive, sinopsis plegada con "Leer más".

### 3. Decidir la siguiente idea visual (una por vez)

Lo siguiente sigue siendo lo siguiente (cada idea se propone y solo se
implementa la aceptada):

- [ ] "Tus guionistas favoritos" — el dato (`title_credits` extra: guionista,
      productor, compositor) **ya está descargado**, solo es mostrarlo. Los
      datos de ejemplo: Nolan/Jonathan Nolan 9.0 de media, Villeneuve 9.5,
      Tolkien 8.67, Rowling 6.86.
- [x] "Mi perfil" — lift por género/director/actor (tu media en la faceta
      menos tu media global). **Hecho y publicado** (2026-10-22): la sección
      existe en el panel, con sus tests en `tests/test_motor.py`; solo queda,
      si se quiere, afinarla con lift reales.
- [ ] "Qué ver hoy" — ruleta determinista por día sobre los pendientes.
- [ ] Bloque "Colección" **completo**: las partes que no tienes (1 petición
      por colección, y las colecciones son pocas).
- [ ] Mapa de países (sigue en la lista desde el principio).
- [ ] Recordar qué secciones estaban plegadas (hoy se reinicia en cada
      visita: "Para ti" abierta y el resto plegadas).

### 4. Backlog de datos

- [ ] Fase 2 TMDB: `estreno_es`, `presupuesto`/`taquilla`, `serie_info`.
- [ ] Los títulos que TMDB-find no resolvió (reintentar tras fase 2 o con
      OMDb-solo; OMDb tiene 1000 peticiones/día).
- [ ] `runtime_min_exact` de "La bola negra": IMDb dice 2h 40min (160) y
      TMDB 155. Se queda el de la web hasta que llegue el export.

### 5. NO tocar ahora

- [ ] Multiusuario: aparcado, con su análisis de free tiers en la sección
      "Aparcado" de este mismo archivo. Solo si 3-5 personas lo piden.
- [ ] `works_origin`: no hay fuente barata (ni TMDB ni OMDb dan la obra
      origen). Queda documentado, no es una tarea.
- [ ] Refactor de `generar_vista.py` (71 KB): solo cuando toque implementar el
      motor de verdad; el MVP plan lo tenía como item 4.

### Notas de seguridad

- Red de seguridad del WIP original: `stash@{0}` y
  `%TEMP%\local_wip_2026-10-20.patch`. Cuando el push esté hecho, `stash@{0}`
  se puede borrar (`git stash drop`).
- Las claves (`TMDB_BEARER`, `OMDB_API_KEY`) están en tu entorno de Windows,
  fuera del repo. Si abres una terminal nueva, recupera su valor o re-ejecuta
  el `setx`; nunca las pegues en un fichero.


## Aparcado (2026-10-19): expansión, conectividad y escalado

**Estado:** pendiente de decisión. No hay spike ejecutado ni código de esta
línea. No se implementa por ahora; se retoma cuando haya necesidad real.

**Objetivo si se retoma:** que hasta 10 amigos usen la herramienta con su
export de IMDb, cada uno con sus notas, desde web y móvil, con coste recurrente
0 y una base técnica que no sea un juguete.

**Punto de partida (no decidido):**

- Círculo privado, gratis, sin monetización. Nada de registro público.
- La idea inicial era una BD SQLite por usuario (`users/{uuid}/catalogo.db`) y
  un `control.db` central solo para cuentas, sesiones, invitaciones y jobs.
- PWA primero; app nativa solo si el uso real la justifica.
- TMDB/OMDb son gratis, pero OMDb limita a 1.000 peticiones/día y es no
  comercial; TMDB exige atribución y uso no comercial.

**Hallazgo de la auditoría (2026-10-19):** “una BD por usuario” es la
restricción que más complica todo. El aislamiento lógico con `user_id` basta
para notas privadas y es lo que usan los SaaS serios; la BD física obliga a N
migraciones, N backups y N jobs, y choca con los free tiers. Si se exige
aislamiento físico, las únicas vías gratis son Turso (100 bases) o una VM con
SQLite; no D1 (10 bases) ni Supabase/Neon (una base).

**Candidatos gratis verificados (2026):**

- **Cloudflare full stack:** Workers 100k peticiones/día y 10 ms de CPU; D1
  5 GB, 5 M lecturas/día, 100k escrituras/día y 10 bases; Queues gratis desde
  feb-2026 con 10k operaciones/día; R2 10 GB; Pages. Una D1 con `user_id`,
  PWA y auth propia. Reescritura a TypeScript; si los 10 ms no llegan,
  Workers Paid cuesta 5 $/mes.
- **Oracle Always Free + Python:** 2 OCPU/12 GB, 200 GB de disco; Docker +
  Caddy + FastAPI + SQLite. Reutiliza dominio y tests; riesgo de reclamación
  por inactividad (7 días con CPU/red/memoria <20%), parches y backups.
- **Supabase/Neon:** Supabase 500 MB, 500k Edge invocations, 150 s/2 s de CPU,
  pero se pausa tras 7 días sin actividad; Neon 1 GB y 100 CU-horas con
  autosuspend a los 5 min. Auth resuelta en Supabase; no hay BD por usuario.
- **Turso + Workers:** 100 bases, 5 GB, 500 M lecturas y 10 M escrituras al
  mes; única vía gestionada que conserva BD física por amigo, a cambio de dos
  proveedores y reescritura.
- **PC de casa + Tailscale Funnel:** 0 €, Python intacto, URL `*.ts.net` sin
  dominio; Funnel en beta, ancho de banda no publicado y dependes de tu equipo.
- **Descartados:** Fly/Render/Railway free con SQLite persistente, Firestore
  (NoSQL; Functions exige Blaze; no es BD física) y Vercel Hobby como worker
  (cron diario y términos de uso personal/no comercial).

**Spike pendiente (2 días, sin código de producto):**

1. Desplegar Worker + D1 + Queue + Pages gratis.
2. Importar un CSV real de 207 filas para dos usuarios y aislar sus notas.
3. Enriquecer un título desde la cola y medir CPU, escrituras y operaciones.
4. Criterio: import correcto, dos usuarios sin cruces, un título enriquecido,
   cero planes de pago y ningún error de CPU. Si falla, evaluar Oracle.

**Decisiones abiertas:**

- Aislamiento lógico (`user_id`) frente a BD física por usuario.
- Cloudflare (cero ops, reescritura) frente a Oracle (reutiliza Python, ops).
- Auth propia frente a Supabase Auth.
- Qué significa “app”: PWA primero; nativa solo con uso que la justifique.

**Por qué se aparca:** auth, worker, backups, migraciones, despliegue y soporte
son un proyecto de semanas; hoy la app local cubre el uso.

**Disparador para retomarlo:** 3-5 personas pidiéndolo, o disponer de tiempo
para el spike y la beta.

**Referencia:** `docs/superpowers/specs/2026-10-19-multiusuario-f0-design.md`
(superada; no implementar tal cual).

## Pendiente de ejecutar (tú, en terminal nueva con tus vars)

- [x] Lote completo 137 ejecutado por el usuario con `fallos: 0` (1633 → 1032 huecos). Quedan ~50 títulos que TMDB-find no resolvió: reintentar tras fase 2 o con OMDb-solo.
- [x] Mezcla de la rama `feat/responsive-filtros` (responsive, ficha overlay con sinopsis, motor de filtros por sección) y del WIP local (KPIs Exigencia/Enriquecidos, Notas por década, botones de KPI con preset).
- [x] Presets de KPI operativos (la rama los dejó muertos: abrían un panel `kpi-*` que no existe en `SECCIONES`).
- [x] Regenerar ~~`python scripts/auto_vista.py --una-vez`~~ — **obsoleto**: el snapshot ya se regenera y publica con `scripts/publicar.py` (commits `d172684` y `be7593d`), que además guarda contra pérdidas.

## Fase 2 TMDB (diseño aprobado, sin empezar)

- [ ] `estreno_es` (207): endpoint `/release_dates`, territorio ES.
- [ ] `presupuesto` / `taquilla` (207): vienen a 0 en detalle básico; definir regla (0 = desconocido, no borrar).
- [ ] `serie_info` (37): detalle TV no resuelto por `find` en esas series; revisar causa.

## Recomendadas beta (aparcada a tu orden)

- Motor propuesto: híbrido (afinidad local por género/director/cast + similitud textual TF-IDF sobre sinopsis). Sin filtrado colaborativo: con un solo usuario no hay señal de otros que aprender.
- **Hecho (2026-10-20): `src/motor.py`** calcula la cola de pendientes con su porqué (afinidad, antiperfil, saga, similitud) y el panel la enseña en la sección "Para ti". Determinista, sin red y sin dependencias. CLI: `python scripts/recomendar.py`.
- **Ya está el combustible**: `title_relations` se rellena sola desde las colecciones de TMDB (0 peticiones extra) y `title_collections` ya se persiste.
- Especificación completa y orden de ataque: [`docs/superpowers/plans/2026-10-20-motor-y-profesionalizacion.md`](docs/superpowers/plans/2026-10-20-motor-y-profesionalizacion.md).

## Ideas de interfaz (una por una, como pediste)

Hechas: buscador Lista completa, Joyas/Decepciones ±1.5, Actores de confianza, buscador global + ficha overlay con sinopsis, strip de pósters, filtros por sección y orden, layout responsive, KPIs extra (Exigencia + Enriquecidos X/207), Notas por década (barras CSS), bloque "Colección" en la ficha con las partes de tu saga, sección "Para ti" (pendientes ordenados por encaje, cada uno con su porqué) y "Mi perfil" (tu gusto medido, con la evidencia a la vista).
Descartadas por ahora, a debat si las quieres:

- [ ] Últimas valoradas + Maratón corto (<110 min, 7+ IMDb).
- [ ] Ruleta «Qué ver hoy» (3 pendientes 7.5+, determinista por día).
- [ ] Mapa de países (con `title_countries`, barras CSS).
- [ ] Tus guionistas favoritos (`title_credits` extra, ya descargado).

## Despliegue web

- Estado: desplegado en Vercel y GitHub (`https://github.com/AlejandroEscapa/bd-peliculas`).
- **Código y HTML publicados** (2026-10-21/22): `preview/dashboard.html` sale de la base real y lleva los 7 KPIs, "Notas por década", el bloque "Colección", "Para ti" y los botones de KPI operativos.
- `vercel.json` reescribe `/` → `/preview/dashboard.html`.
- `preview/dashboard.html` no tiene dependencias; se sirve como estático (Vercel) o en local.
- Opción B (gestionado Cloudflare): herramientas `sites_*` disponibles si quieres preview/producción con D1/R2 y auth; este proyecto hoy es SQLite local + HTML estático, así que habría que adaptarlo antes.

## Claves (fijadas por ti con `setx`, fuera del repo)

- `TMDB_BEARER`, `OMDB_API_KEY` como variables de usuario Windows. Los scripts las leen del entorno; nada en `.env`, código ni Git. Tras `setx`, reabre la terminal.
