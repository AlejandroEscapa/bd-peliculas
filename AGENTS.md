# AGENTS.md — db-peliculas

Catálogo personal IMDb en SQLite + panel HTML estático. Python stdlib, sin dependencias.

## Comandos

```bat
cd C:\Users\Usuario\Desktop\db-peliculas
python scripts/actualizar_peliculas.py "C:\ruta\al-export.csv"
python scripts/anadir_pelicula.py --tt tt35511966 --nota 9 --titulo "La bola negra" --anio 2026
python scripts/scrapear_peliculas.py --proveedor src.proveedores.combinado:ProveedorCombinado --limite 5 --delay 1.5
python scripts/generar_vista.py
python scripts/publicar.py --dry-run
python scripts/auto_vista.py --una-vez
python -m unittest discover -s tests
```

## Altas a mano

`scripts/anadir_pelicula.py` da de alta un título (tt de IMDb) con su nota y
lo enriquece; no duplica si ya está y no borra nada. El CSV que llegue después
lo reconoce como título existente y solo escribe sus columnas. Está documentado
en la skill global `anadir-peliculas` (`~/.agents/skills/anadir-peliculas/`).

## Reglas duras

- CSV es entrada delta: la fuente manda por columna, vacío jamás borra, diffs en `sync_diffs`, sin `tt` válido a cuarentena. Solo escribe columnas CSV-own (`src/sync.py::CSV_OWN_TITLES` + géneros/directores `imdb_csv` + nota no-nula nueva).
- Enriquecido solo rellena faltantes (`solo_faltantes=True`, `INSERT OR IGNORE`); la cola sale de `src/huecos.py::listar_huecos`. Un título roto no aborta el lote.
- Migraciones forward-only en `db/migrations/`; no editar las aplicadas. Vistas solo-lectura en `db/views.sql`.
- Secretos solo por entorno (`TMDB_BEARER`, `OMDB_API_KEY`). Nunca en código, `.env` ni Git. No reproducir valores en chat/logs.
- Panel: HTML estático sin dependencias, en español, paginación 15+15 (`table.paginada` + `.more-btn`), consultas parametrizadas, `html.escape` en todo texto de BD.
- Tests stdlib (`python -m unittest discover -s tests`, 131 tests). Toda idea visual se propone de una en una y solo se implementa la aceptada.
