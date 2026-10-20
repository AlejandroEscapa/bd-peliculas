-- Migración 0002: colecciones de TMDB (sagas y universos).
-- Forward-only, no destructiva. El esquema canónico vive en db/schema.sql;
-- este archivo documenta la versión aplicada. No editar: futuros cambios van
-- en 0003_*.sql.
--
-- Qué añade: la colección/franquicia a la que pertenece cada título, tomada
-- de `belongs_to_collection` de la respuesta de detalle de TMDB. No cuesta
-- peticiones extra: el campo ya venía en la respuesta que el scraper pedía.
--
-- collection_id NULL = se consultó y el título no pertenece a ninguna
-- colección. Así el hueco se cierra sin volver a pedirlo.
CREATE TABLE IF NOT EXISTS title_collections (
  tt TEXT PRIMARY KEY REFERENCES titles(tt) ON DELETE CASCADE,
  collection_id INTEGER,
  collection_name TEXT,
  source TEXT,
  fetched_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_collections_id ON title_collections(collection_id);

INSERT OR IGNORE INTO schema_version (version) VALUES ('0002_colecciones');
