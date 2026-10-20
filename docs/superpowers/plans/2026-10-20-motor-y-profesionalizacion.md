# Motor de recomendaciones y profesionalización del panel — Plan de trabajo

**Fecha:** 2026-10-20
**Estado:** brainstorming capturado. La primera línea de ejecución es
"conectar las tuberías muertas" (ver §5). Todo lo demás espera turno.

**Premisa:** el panel es un HTML estático generado por Python, sin backend y sin
dependencias. Cualquier motor de recomendación tiene que vivir en el build
(Python), no en el navegador: la base de datos no está en el cliente.

---

## 1. Punto de partida: el activo invisible

El esquema tiene 3 capas y 18 tablas. El panel consume ~8 campos. Esto ya está
en la base y no se ve:

| Tabla / campo | Estado | Por qué importa |
|---|---|---|
| `title_relations` | tabla vacía, API lista (`src/relaciones.py`) | sagas, universos, remakes: la señal más fuerte y no existe |
| `works_origin` | vacía | "la adaptación de este libro/cómic" |
| `series_info` | en la cola de huecos | temporadas/episodios/estado: hoy "Serie de TV" es una etiqueta plana |
| `title_credits` extra | ya descargado (writer/producer/composer/cinematographer/editor) | "tus guionistas favoritos" es una sección con el dato ya en casa |
| `imdb_votes` | importado del CSV, sin usar | señal de popularidad vs. gusto: "sleepers" |
| `budget` / `box_office` | fase 2 | burbujas presupuesto vs. nota |
| `release_dates` (territorio) | fase 2 | fecha original vs. fecha en España |
| `personal_note` | columna muerta: el export de IMDb no trae notas | nadie la escribe |
| `date_rated` | sí está | temporal: tu año en películas, racha, "visto este mes" |
| `original_lang_iso`, `runtime_min_exact`, `tagline`, `csv_position` | sí están | contexto de ficha |

**Conclusión:** la interfaz no necesita ideas exóticas primero. Necesita dejar
de ignorar lo que ya se pagaron y guardaron.

---

## 2. Motor de recomendaciones

### 2.1 El límite honesto

1 usuario, 148 valoradas, 59 pendientes, 207 títulos. El filtrado colaborativo
es imposible (necesita miles de usuarios) y no se quiere: el caso es privado
por diseño. Un "motor de recomendaciones" comercial sería una llamada a una API
(coste + fuga de datos) o una caja negra.

Lo defendible es un motor **content-based explicable** sobre el perfil propio,
más reglas sobre el catálogo. Y el giro de producto que lo hace útil:

> El valor no está en recomendar títulos que no tienes. Está en **ordenar y
> justificar los 59 pendientes que ya tienes**.

Una cola de decisión con "por qué" visible es algo que un humano nota y una IA
genérica no. Determinista, gratis, auditable y explicable ("te encaja por:
Nolan, 2010s, ciencia ficción; tus Joyas en ese género promedian 8.7").

### 2.2 Capas de señal, de menos a más potente

| Capa | Señal | Origen | Peticiones API |
|---|---|---|---|
| A. Perfil de gusto | lift por género/director/actor/década/país = tu media en la faceta − tu media global | `titles` + `user_state` + `title_genres` + `title_credits` | 0 |
| B. Antiperfil | lo que te decepciona: misma faceta, `my_rating − imdb_rating` positivo | diff | 0 |
| C. Reglas narrativas | "si te gustó X → su saga, su director, su actor, su obra origen" | `title_relations`, `works_origin`, `title_cast` | 0–1 |
| D. Similitud textual | TF-IDF con *hashing trick* + coseno sobre sinopsis → "se parecen en: tiempo, memoria, traición" | `synopsis` | 0, stdlib puro (`Counter` + `math`) |
| E. Industria | `/similar` y `/recommendations` de TMDB | API | 2 por título (414) |

**Atajo clave:** `belongs_to_collection` viene **en la respuesta de detalle que
TMDB ya está haciendo**. Las sagas de los 207 títulos cuestan **0 peticiones
extra**: un campo más en el `fetch` existente.

### 2.3 Dónde vive el motor

| Opción | Qué es | Veredicto |
|---|---|---|
| A. Python en el build | `src/motor.py` lee la BD, calcula perfil + scores + razones, y lo vuelca en el JSON del panel (o en una tabla `recomendaciones(tt, score, razones, generado_en)`) | **Sí**: determinista, testeable en `unittest`, auditable |
| B. Cliente reordena | el JSON trae todo y el JS ordena/filtra | Necesario para lo interactivo, insuficiente para calcular el perfil |

**Decisión: A para el cálculo, B para la interacción.** Es el mismo patrón que
ya usan las facetas: Python genera la verdad, JS la explora.

### 2.4 El bloqueo real

`src/relaciones.py` existe, `tests/test_relaciones.py` existe, la tabla
`title_relations` está en el esquema… **pero no hay ningún hueco en
`listar_huecos()` que la rellene**: el pipeline nunca va a llenarla. Lo mismo
con `works_origin` y con `title_credits` extra (que sí es hueco, pero el panel
no lo muestra).

**El motor empieza por conectar la tubería, no por el algoritmo.**

---

## 3. Interfaz: siete ejes

> Regla del repo: **una idea visual a la vez**, se propone y solo se implementa
> la aceptada. Esto es el menú, no un plan.

1. **Perfil (hoy no existe).** Tu gusto en una pantalla: lift por
   género/director/actor, tu sesgo global vs IMDb, tu "exigencia" ya está.
   Es la pieza que hace explicables el motor y la cola de decisión.
2. **Decisión.** "Qué ver hoy" (ruleta determinista por día) · cola de
   pendientes priorizada · "una película para 90 min" · "títulos de <110 min
   con 7+ IMDb".
3. **Saga y contexto.** Con `title_relations`: ficha que muestra
   *colección → partes → tu nota en cada una*. Con `works_origin`: "la misma
   obra, dos versiones, tu veredicto en ambas".
4. **Tiempo.** Tu año en películas (heatmap por `date_rated`) · "visto este mes" ·
   racha de valoradas · "lo que viste después de X". Cero datos nuevos.
5. **Análisis.** Distribución de notas · dispersión tu-nota vs IMDb · burbujas
   presupuesto vs nota · mapa de países · **"sleepers"**: pocas votes y nota
   alta (`imdb_votes` sin usar).
6. **Craft / uso diario.** Búsqueda por persona (ya funciona: `buscaTexto`
   incluye directores y reparto) · exportar a Letterboxd/Trakt/CSV · modo cine
   · atajos de teclado · PWA offline · URL con filtros compartibles · alto
   contraste · `prefers-reduced-motion` ya está.
7. **Portfolio.** La demo pública usa un snapshot de un catálogo real y las
   notas son personales. El siguiente paso del MVP plan es una **demo
   reproducible con datos sintéticos**: sin datos personales, reproducible por
   cualquiera, y el único escenario donde se ven ideas que tu catálogo real no
   puede enseñar (sagas, década, todos los KPIs).

---

## 4. Divagar: tres horizontes

- **H1 — Este mes (rentable).** Eje 4 + eje 5 parcial + conectar sagas. Todo
  con datos que ya tienes. Coste de API: 0.
- **H2 — Este trimestre (producto).** Motor explicable (capas A–D) + cola de
  decisión + Perfil. Antes: **refactorizar `generar_vista.py` (71 KB, mezcla
  consulta/HTML/CSS/JS)**, que el MVP plan posponía al item 4 y que es la
  condición previa para todo lo demás.
- **H3 — Cuando 3–5 personas lo pidan (ya documentado en ROADMAP).**
  Multiusuario: la auditoría ya concluyó que la BD por usuario choca con los
  free tiers y que el aislamiento lógico con `user_id` basta. Trigger: "3–5
  personas pidiendo, o tiempo para el spike". No tocar antes.

**Ideas-species (riesgosas pero baratas):**
- Narrador determinista: "Tu 2026 en 12 frases" por reglas sobre tus datos. Sin
  IA, sin coste, sin fuga, reproducible. Un LLM local (Ollama) lo haría mejor
  pero rompe la regla de cero dependencias.
- "Cintas" de visionado: reordenar el catálogo en listas temáticas.
- Publicar el catálogo como dataset (anonimizando las notas, conservando los
  hechos de los títulos).
- Importar el watchlist de IMDb por export (la importación ya es idempotente).

---

## 5. Primera línea de ejecución: conectar las tuberías muertas

**Objetivo:** que las tablas que ya existen se llenen y se enseñen, sin gastar
una sola petición de API de más.

### 5.1 Colecciones (0 peticiones)

1. `db/schema.sql`: tabla `title_collections(tt, collection_id, collection_name,
   source, fetched_at)`. `collection_id` NULL = "consultado, no tiene
   colección" (cierra el hueco sin volver a pedirlo).
2. `db/migrations/0002_colecciones.sql`: documenta la versión (forward-only).
3. `src/proveedores/tmdb.py`: leer `belongs_to_collection` de la respuesta de
   detalle **que ya se pide** → `datos["coleccion"]`.
4. `src/scraper.py`:+nuevo campo del protocolo y su escritura en la tabla.
5. `src/huecos.py`: + hueco `coleccion`.
6. `src/respaldo.py`: `VERSION` → `0002_colecciones`.

### 5.2 Relations derivadas (0 peticiones)

`src/relaciones.py` + `derivar_relaciones_coleccion(db)`:

- **universe**: entre todos los pares de títulos de la misma colección (cierto).
- **sequel**: entre vecinos por año **si** comparten director o actor del
  reparto principal (cast_order ≤ 3) **y** el salto es de ≥ 1 año. Heurística,
  documentada como tal: el panel muestra la colección completa ordenada por
  año para que el usuario juzgue.

### 5.3works_origin

**No entra.** No hay fuente barata: ni TMDB ni OMDb dan la obra origen. Queda
documentado como hueco abierto, no como tarea.

### 5.4 Lo visual (una idea a la vez, se propone antes de implementarse)

1. Ficha: bloque "Colección / Saga" con las partes de tu catálogo y tu nota en
   cada una.
2. Sección "Tus guionistas favoritos" (`title_credits` extra, ya descargado).

---

## 6. Reglas que no se rompen

- Cero dependencias en tiempo de ejecución (stdlib).
- El CSV es delta; vacío jamás borra; cada cambio en `sync_diffs`.
- Enriquecido solo rellena faltantes; un título roto no aborta el lote.
- Migraciones forward-only; `db/views.sql` solo lectura.
- Secretos solo por entorno; nunca en código, `.env` ni Git.
- Panel: HTML estático en español, paginación 15+15, consultas parametrizadas,
  `html.escape` en todo texto de BD.
- Una idea visual por vez.
