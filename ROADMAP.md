# Roadmap — Catálogo personal (db-peliculas)

Estado a 2026-10-20 (tras lote 137, fallos 0): 207 títulos, 1032 huecos. Sinopsis 157/207, pósters 156, cast 470 filas. Restan ~50 sin resolver por TMDB-find + fase 2 (fecha ES, dinero, serie_info).
Panel en `preview/dashboard.html`: responsive mobile-first, buscador global, ficha overlay con sinopsis al final, strip de pósters, motor de filtros por sección (facetas + orden) y paginación reactiva, Joyas/Decepciones + Géneros/Directores/Actores, KPIs extra (Exigencia y Enriquecidos X/207), Notas por década y "Para ti" (pendientes ordenados por encaje, con su porqué).
Tuberías conectadas (2026-10-20): colecciones de TMDB (`belongs_to_collection`, 0 peticiones extra) en `title_collections`, con relaciones saga derivadas en `title_relations`; `schema_version` ya se registra al aplicar el esquema. La ficha muestra el bloque "Colección" con las partes de tu catálogo, por año y con tu nota.
Watcher `scripts/auto_vista.py` verificado. Suite 94/94 OK.

## Base semilla (2026-10-21)

- `scripts/semilla.py` construye `data/semilla.db` a partir del snapshot publicado: los mismos 207 títulos con **notas sintéticas** (deterministas, correlacionadas con el IMDb y con una preferencia por géneros) y las **sagas reales** detectadas por título. Sirve para iterar la interfaz sin la base real ni red, y para la demo pública en `/demo`.
- `preview/semilla.html` es el artefacto de esa demo; se regenera con `python scripts/semilla.py && python scripts/generar_vista.py --db data/semilla.db --salida preview/semilla.html`.

## PENDIENTES AL LLEGAR A CASA (2026-10-20)

> **Handoff completo** (guion, verificaciones, mapa del código, decisiones
> tomadas y trampas conocidas): [`docs/superpowers/plans/2026-10-20-handoff.md`](docs/superpowers/plans/2026-10-20-handoff.md).

> Estado al dejar el PC: **el código está publicado** en `origin/main`
> (suite 94/94 en verde). Lo que **no** está publicado es el snapshot:
> `preview/dashboard.html` sigue siendo el viejo, porque regenerarlo exige
> tu `data/catalogo.db`, que no existe fuera de tu máquina. Handoff completo:
> `docs/superpowers/plans/2026-10-20-handoff.md`.

### 1. Publicar lo que ya está hecho (~20 min)

- [ ] **Rellenar el hueco `coleccion`** — el scraper lee
      `belongs_to_collection` de la respuesta de detalle que TMDB ya te
      pedía, así que **no gastas peticiones extra**. Ojo: el scraper ahora
      aplica el esquema vigente, tu base gana la tabla `title_collections`
      sola (no hace falta reimportar el CSV).
      ```bat
      python scripts/scrapear_peliculas.py --proveedor src.proveedores.combinado:ProveedorCombinado --limite 207 --delay 1.5
      ```
      Verificar: el hueco `coleccion` desaparece de `listar_huecos()`.
- [ ] **Derivar las sagas** (idempotente, se puede repetir sin miedo):
      ```bat
      python scripts/derivar_relaciones.py
      ```
      Verificar: imprime "N colecciones, M relaciones nuevas". Si `M = 0`, tus
      títulos no comparten saga (normal si tienes pocas de una misma
      colección): no es un error.
- [ ] **Regenerar el snapshot** (esto es lo que faltaba para que se vieran
      los KPIs nuevos y la sección por década):
      ```bat
      python scripts/generar_vista.py
      ```
      Verificar: `preview/dashboard.html` pesa más que antes y la ficha de un
      título con saga muestra el bloque "Colección".
- [ ] **Publicar el snapshot** (el código ya está subido; esto es lo único
      que queda por ver):
      ```bat
      git add preview/dashboard.html
      git commit -m "chore: regenera el snapshot del panel"
      git push origin main
      ```
      El push dispara el CI de GitHub Actions y Vercel redespliega.

### 2. Comprobar en el navegador (~10 min)

- [ ] Los **7 KPIs** (salen "Exigencia" y "Enriquecidos", que no estaban en el
      snapshot publicado) y la sección **"Notas por década"**.
- [ ] Los botones de los KPIs: **antes estaban muertos** (la rama los dejó sin
      wiring). Ahora "Valoradas" y "Sin enriquecer" aplican un preset sobre
      Lista completa. "Tu nota media" y "Exigencia" salen **deshabilitados**:
      son promedios, no conjuntos de títulos.
- [ ] La **ficha** con el bloque "Colección": partes de tu saga por año, con tu
      nota, y el clic en una parte abre su ficha.
- [ ] En móvil: responsive, sinopsis plegada con "Leer más".

### 3. Decidir la siguiente idea visual (una por vez)

- [ ] "Tus guionistas favoritos" — el dato (`title_credits` extra: guionista,
      productor, compositor) **ya está descargado**, solo es mostrarlo.
- [ ] "Mi perfil" — lift por género/director/actor (tu media en la faceta
      menos tu media global). Es la pieza que hace explicable el motor.
- [ ] "Qué ver hoy" — ruleta determinista por día sobre los pendientes.
- [ ] Bloque "Colección" **completo**: las partes que no tienes (1 petición
      por colección, y las colecciones son pocas).
- [ ] Mapa de países (sigue en la lista desde el principio).

### 4. Backlog de datos

- [ ] Fase 2 TMDB: `estreno_es`, `presupuesto`/`taquilla`, `serie_info`.
- [ ] Los ~50 títulos que TMDB-find no resolvió (reintentar tras fase 2 o con
      OMDb-solo; OMDb tiene 1000 peticiones/día).

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
- [ ] Regenerar: `python scripts/auto_vista.py --una-vez` (o dejar el watcher abierto). **Requiere tu base**: la copia sin `data/catalogo.db` no puede. Ver "PENDIENTES AL LLEGAR A CASA".

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

Hechas: buscador Lista completa, Joyas/Decepciones ±1.5, Actores de confianza, buscador global + ficha overlay con sinopsis, strip de pósters, filtros por sección y orden, layout responsive, KPIs extra (Exigencia + Enriquecidos X/207), Notas por década (barras CSS), bloque "Colección" en la ficha con las partes de tu saga, sección "Para ti" (pendientes ordenados por encaje, cada uno con su porqué).
Descartadas por ahora, a debat si las quieres:

- [ ] Últimas valoradas + Maratón corto (<110 min, 7+ IMDb).
- [ ] Ruleta «Qué ver hoy» (3 pendientes 7.5+, determinista por día).
- [ ] Mapa de países (con `title_countries`, barras CSS).
- [ ] Tus guionistas favoritos (`title_credits` extra, ya descargado).
- [ ] Mi perfil: lift por género/director/actor (tu media en la faceta − tu media global).

## Despliegue web

- Estado: desplegado en Vercel y GitHub (`https://github.com/AlejandroEscapa/bd-peliculas`).
- **Ojo: el código está publicado, el HTML todavía no.** `preview/dashboard.html` sigue siendo el de la rama (5 KPIs, sin "Notas por década", sin bloque "Colección", sin "Para ti" y con los botones de KPI muertos), porque regenerarlo necesita tu base. Se pone al día con el punto 1 de "PENDIENTES AL LLEGAR A CASA".
- `vercel.json` reescribe `/` → `/preview/dashboard.html`.
- `preview/dashboard.html` no tiene dependencias; se sirve como estático (Vercel) o en local.
- Opción B (gestionado Cloudflare): herramientas `sites_*` disponibles si quieres preview/producción con D1/R2 y auth; este proyecto hoy es SQLite local + HTML estático, así que habría que adaptarlo antes.

## Claves (fijadas por ti con `setx`, fuera del repo)

- `TMDB_BEARER`, `OMDB_API_KEY` como variables de usuario Windows. Los scripts las leen del entorno; nada en `.env`, código ni Git. Tras `setx`, reabre la terminal.
