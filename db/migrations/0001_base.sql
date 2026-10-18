-- Migración 0001: esquema base (forward-only, no destructiva).
-- El esquema canónico vive en db/schema.sql; este archivo documenta la
-- versión inicial aplicada. No editar: futuros cambios van en 0002_*.sql.
CREATE TABLE IF NOT EXISTS schema_version (
  version TEXT PRIMARY KEY,
  applied_at TEXT NOT NULL DEFAULT (datetime('now'))
);
INSERT OR IGNORE INTO schema_version (version) VALUES ('0001_base');
