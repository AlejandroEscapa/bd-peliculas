# Reporte de planes pendientes — 2026-10-23

**Qué es esto:** fotografía de lo que queda por hacer, hecha revisando
`ROADMAP.md`, `README.md` y `docs/superpowers/plans/`, con la suite y el árbol
de Git verificados. Sirve como orden de ataque desde casa; el porqué de cada
item sigue en `ROADMAP.md`.

**Estado verificado (2026-10-23):** 208 títulos, 149 valoradas, 0 sin
enriquecer · suite `python -m unittest discover -s tests` → **140/140 OK** ·
árbol limpio y sin stash · el snapshot publicado ya sale de la base real.

---

## 1. Inmediato

- [ ] **Comprobar en móvil**: responsive y sinopsis plegada con "Leer más".
      Es el único checkbox sin tachar del bloque "Comprobar en el navegador"
      de `ROADMAP.md`. Se hace en el navegador, no hay código que tocar.
- [x] ~~Regenerar con `python scripts/auto_vista.py --una-vez`~~ — **obsoleto**:
      el snapshot ya está regenerado y publicado desde la base real (commits
      `d172684` y `be7593d`, vía `scripts/publicar.py`).

## 2. Siguiente idea visual (una por vez, como manda la regla del repo)

En el orden que el propio handoff marca como prioritario:

1. [ ] **"Tus guionistas favoritos"** — el dato (`title_credits` con rol
       writer/producer/composer) **ya está descargado**; solo es mostrarlo.
       Ejemplos reales: Nolan/Jonathan Nolan 9.0 de media, Villeneuve 9.5,
       Tolkien 8.67, Rowling 6.86. Es el #1 de `2026-10-21-handoff-casa.md`.
2. [ ] **"Qué ver hoy" / cola de decisión** — `src/motor.py` ya calcula
       encaje y motivos ("Para ti"); falta la pieza de producto.
3. [ ] **Bloque "Colección" completo** — las partes de la saga que *no*
       tienes: 1 petición por colección (son 45, y las que importan son 11).
4. [ ] **Mapa de países** — `title_countries` ya está en el esquema.
5. [ ] **Recordar qué secciones estaban plegadas** — hoy se reinicia en cada
       visita ("Para ti" abierta, el resto plegadas).

Nota: "Mi perfil" (lift por género/director/actor) **ya está hecho y
publicado** — la sección existe en el panel con sus lifts y sus tests —; solo
queda, si se quiere, afinarla con los lift reales.

## 3. Backlog de datos — Fase 2 TMDB (diseño aprobado, sin empezar)

Único item sin marcar del roadmap del `README.md`:

- [ ] `estreno_es` (207): endpoint `/release_dates`, territorio ES.
- [ ] `presupuesto` / `taquilla` (207): vienen a 0 en el detalle básico;
      definir la regla (0 = desconocido, no borrar).
- [ ] `serie_info` (37): el detalle TV no lo resuelve `find`; revisar causa.
- [ ] Los ~50 títulos que TMDB-find no resolvió: reintentar tras fase 2 o con
      OMDb-solo (OMDb: 1000 peticiones/día).
- [ ] `runtime_min_exact` de "La bola negra": IMDb 160 min vs TMDB 155; se
      queda el de la web hasta que llegue el export.

## 4. NO tocar ahora (aparcados con disparador)

- [ ] **Multiusuario** — solo si 3-5 personas lo piden, o si hay tiempo para
      el spike de 2 días (Worker+D1+Queue+Pages). Análisis de free tiers ya
      hecho en la sección "Aparcado" de `ROADMAP.md`.
- [ ] **`works_origin`** — no hay fuente barata; documentado, no es tarea.
- [ ] **Refactor de `generar_vista.py`** (71 KB) — condición previa del
      horizonte H2 del plan del motor; no antes.
- [ ] **Recomendadas beta** — lo esencial ya está (`src/motor.py`); lo que
      queda es la cola de decisión (ver punto 2.2).

## 5. Documentación (hecho, pero los checkboxes mentían)

- [x] `2026-10-19-portfolio-mvp.md` y `2026-10-19-responsive-filtros-ficha.md`
      **están ejecutados y commiteados** (CI, strip de pósters, buscador
      accesible, ficha overlay, motor de filtros, presets de KPI). Sus
      checkboxes no se tacharon en su día; ahora llevan un aviso de estado en
      la cabecera.
- [x] `2026-10-20-handoff.md`: bloque Colección, botones de KPI y ficha con
      saga **hechos y publicados** (2026-10-21). Sigue pendiente solo lo de
      móvil.
- [x] `ROADMAP.md` "Despliegue web": ya no dice que el HTML esté sin
      publicar, y "Mi perfil" y la regeneración del snapshot quedan tachados.

## Orden sugerido

1. Comprobar en móvil (10 min, navegador).
2. Elegir la siguiente idea visual — "Tus guionistas favoritos" va el
   primero; recuerda la regla del repo: **una idea visual a la vez, propuesta
   antes de implementarse**.
3. Fase 2 de TMDB cuando quieras meter mano en datos.

**Ojo:** casi todo lo de datos y publicación necesita `data/catalogo.db`
(tu base real), que no viaja en el repo: se ejecuta en tu PC, no en un clon
limpio. Antes de tocar nada: `python -m unittest discover -s tests` en verde
(140) y `python scripts/publicar.py --dry-run` como guard.
