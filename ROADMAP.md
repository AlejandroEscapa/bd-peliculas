# Roadmap — Catálogo personal (db-peliculas)

Estado a 2026-10-19 (tras lote 137, fallos 0): 207 títulos, 1032 huecos. Sinopsis 157/207, pósters 156, cast 470 filas. Restan ~50 sin resolver por TMDB-find + fase 2 (fecha ES, dinero, serie_info).
Panel simple en `preview/dashboard.html`: buscador + Joyas/Decepciones + Actores de confianza + KPIs extra (Exigencia y Enriquecidos X/207) + Notas por década,
paginación 15+15. Watcher `scripts/auto_vista.py` verificado. Suite 35/35 OK.

## Pendiente de ejecutar (tú, en terminal nueva con tus vars)

- [x] Lote completo 137 ejecutado por el usuario con `fallos: 0` (1633 → 1032 huecos). Quedan ~50 títulos que TMDB-find no resolvió: reintentar tras fase 2 o con OMDb-solo.
- [ ] Regenerar: `python scripts/auto_vista.py --una-vez` (o dejar el watcher abierto).

## Fase 2 TMDB (diseño aprobado, sin empezar)

- [ ] `estreno_es` (207): endpoint `/release_dates`, territorio ES.
- [ ] `presupuesto` / `taquilla` (207): vienen a 0 en detalle básico; definir regla (0 = desconocido, no borrar).
- [ ] `serie_info` (37): detalle TV no resuelto por `find` en esas series; revisar causa.

## Recomendadas beta (aparcada a tu orden)

- Motor propuesto: híbrido (afinidad local por género/director/cast + TMDB `/recommendations` solo para huecos). Sin esquema nuevo en beta; si escala, tabla `title_relations` ya existe (`universe`, `related`…).

## Ideas de interfaz (una por una, como pediste)

Hechas: buscador Lista completa, Joyas/Decepciones ±1.5, Actores de confianza, KPIs extra (Exigencia + Enriquecidos X/207), Notas por década (barras CSS).
Descartadas por ahora, a debatir si las quieres:

- [ ] Últimas valoradas + Maratón corto (<110 min, 7+ IMDb).
- [ ] Ruleta «Qué ver hoy» (3 pendientes 7.5+, determinista por día).
- [ ] Mapa de países (con `title_countries`, barras CSS).

## Despliegue web

- Estado: desplegado en Vercel y GitHub (`https://github.com/AlejandroEscapa/bd-peliculas`).
- `vercel.json` reescribe `/` → `/preview/dashboard.html`.
- `preview/dashboard.html` no tiene dependencias; se sirve como estático (Vercel) o en local.
- Opción B (gestionado Cloudflare): herramientas `sites_*` disponibles si quieres preview/producción con D1/R2 y auth; este proyecto hoy es SQLite local + HTML estático, así que habría que adaptarlo antes.

## Claves (fijadas por ti con `setx`, fuera del repo)

- `TMDB_BEARER`, `OMDB_API_KEY` como variables de usuario Windows. Los scripts las leen del entorno; nada en `.env`, código ni Git. Tras `setx`, reabre la terminal.
