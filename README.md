# Catálogo personal de películas y series

Base de datos local (SQLite, sin dependencias) para tu lista de IMDb.
El CSV de IMDb es **entrada delta, nunca la verdad**: importar de nuevo
no borra tu enriquecimiento (sinopsis, reparto, posters, relaciones).

## Estructura

- `db/schema.sql` — esquema canónico (3 capas: título, capa personal, enriquecimiento web).
- `db/migrations/` — migraciones forward-only (no editar las aplicadas).
- `db/views.sql` — vistas KPI (`v_top_rated`, `v_generos_fav`, `v_directores_fav`, `v_pendientes`, `v_sin_enriquecer`).
- `src/` — `db.py`, `sync.py`, `huecos.py`, `relaciones.py`, `scraper.py`, `respaldo.py`.
- `scripts/` — CLIs: `actualizar_peliculas.py`, `scrapear_peliculas.py`, `backup.py`.
- `tests/` — 29 tests (stdlib `unittest`, sin instalación).
- `data/catalogo.db` — tu base (no se versiona, ver `.gitignore`).

## Uso

```bash
# 1. Crear la base e importar tu export de IMDb
python scripts/actualizar_peliculas.py "C:\ruta\a\tu-export.csv"

# 2. Reimportar otro export más adelante (solo suma y registra diffs)
python scripts/actualizar_peliculas.py "C:\ruta\a\nuevo-export.csv"

# 3. Ver qué le falta a cada título (huecos web)
python -c "from src.huecos import listar_huecos; import json; print(json.dumps(listar_huecos('data/catalogo.db'), indent=1, ensure_ascii=False))"

# 4. Enriquecer desde una fuente (proveedor propio, datos públicos)
python scripts/scrapear_peliculas.py --proveedor mi_paquete:MiProveedor --limite 20 --delay 1.5

# 5. Backup
python scripts/backup.py
```

El proveedor de `scrapear-peliculas` es cualquier clase con atributo
`nombre` y método `fetch(tt) -> dict` (ver `src/scraper.py` para el
formato). Sin login ni cookies: solo datos públicos, con pausa entre
peticiones y fallos aislados por título.

## Proveedores web (TMDB + OMDb)

```bash
# Keys por entorno (nunca en código)
set TMDB_BEARER=<tu-jwt-tmdb> & set OMDB_API_KEY=<tu-key-omdb>

# Combinado: TMDB primero (es-ES, fallback en-US), OMDb parcha huecos
python scripts/scrapear_peliculas.py \
  --proveedor src.proveedores.combinado:ProveedorCombinado --limite 20 --delay 1.5 --dry-run
```

Sin `OMDB_API_KEY` el combinado funciona solo con TMDB. Pósters: se guarda
URL absoluta (`image.tmdb.org` a `w500`, apta para web/móvil), no binarios.

## Tests

```bash
python -m unittest discover -s tests
```

## Reglas duras

- Clave estable: el `tt` de IMDb. Sin `tt` válido la fila va a cuarentena.
- Vacío en CSV jamás borra: ni tu nota, ni sinopsis, ni posters, ni reparto.
- Todo lo web guarda `fuente` y fecha; el rating de IMDb del CSV manda
  sobre la web (la web solo rellena si está vacío).
