-- Catálogo personal IMDb — esquema base v1
-- Criterio: 3 capas separadas. Clave estable: tt (Const IMDb).
-- Regla dura: vacío en CSV jamás borra enriquecimiento web.
-- Motor: SQLite local. Migración forward-only (ver db/migrations/).

PRAGMA foreign_keys = ON;

-- 1) Título canónico (hechos del título)
CREATE TABLE IF NOT EXISTS titles (
  tt TEXT PRIMARY KEY CHECK (tt GLOB 'tt[0-9]*'),
  title_es TEXT,
  original_title TEXT,
  url TEXT,
  title_type TEXT,
  year INTEGER,
  runtime_min_csv INTEGER,
  runtime_min_exact INTEGER,
  imdb_rating REAL,
  imdb_votes INTEGER,
  release_date_csv TEXT,
  spain_release_date TEXT,
  original_lang_iso TEXT,
  synopsis TEXT,
  synopsis_source TEXT,
  tagline TEXT,
  poster_url TEXT,
  poster_source TEXT,
  budget_amount REAL,
  budget_currency TEXT,
  budget_source TEXT,
  box_office_amount REAL,
  box_office_currency TEXT,
  box_office_source TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- 2) Capa personal (solo del usuario, 1 usuario en esta fase)
CREATE TABLE IF NOT EXISTS user_state (
  tt TEXT PRIMARY KEY REFERENCES titles(tt) ON DELETE CASCADE,
  my_rating INTEGER CHECK (my_rating IS NULL OR (my_rating >= 1 AND my_rating <= 10)),
  date_rated TEXT,
  watch_status TEXT NOT NULL DEFAULT 'watchlist'
    CHECK (watch_status IN ('rated', 'watchlist')),
  personal_note TEXT,
  csv_created TEXT,
  csv_modified TEXT,
  csv_position INTEGER,
  updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Catálogos
CREATE TABLE IF NOT EXISTS genres (
  name TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS title_genres (
  tt TEXT NOT NULL REFERENCES titles(tt) ON DELETE CASCADE,
  genre TEXT NOT NULL REFERENCES genres(name),
  PRIMARY KEY (tt, genre)
);

CREATE TABLE IF NOT EXISTS people (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE
);

-- Créditos (directores vienen del CSV con fuente imdb_csv; el resto desde web)
CREATE TABLE IF NOT EXISTS title_credits (
  tt TEXT NOT NULL REFERENCES titles(tt) ON DELETE CASCADE,
  person_id INTEGER NOT NULL REFERENCES people(id),
  role TEXT NOT NULL
    CHECK (role IN ('director','writer','producer','composer','cinematographer','editor','other')),
  source TEXT,
  url_source TEXT,
  fetched_at TEXT,
  PRIMARY KEY (tt, person_id, role)
);

-- Reparto con personaje y orden (hueco web, Task 4/6)
CREATE TABLE IF NOT EXISTS title_cast (
  tt TEXT NOT NULL REFERENCES titles(tt) ON DELETE CASCADE,
  person_id INTEGER NOT NULL REFERENCES people(id),
  character_name TEXT NOT NULL DEFAULT '',
  cast_order INTEGER,
  source TEXT,
  url_source TEXT,
  fetched_at TEXT,
  PRIMARY KEY (tt, person_id, character_name)
);

CREATE TABLE IF NOT EXISTS title_countries (
  tt TEXT NOT NULL REFERENCES titles(tt) ON DELETE CASCADE,
  country_code TEXT NOT NULL,
  PRIMARY KEY (tt, country_code)
);

-- Fechas por territorio (ES es la fecha única pedida; el resto convive)
CREATE TABLE IF NOT EXISTS release_dates (
  tt TEXT NOT NULL REFERENCES titles(tt) ON DELETE CASCADE,
  territory TEXT NOT NULL,
  rel_date TEXT NOT NULL,
  source TEXT,
  PRIMARY KEY (tt, territory)
);

-- Series: temporadas, episodios, estado
CREATE TABLE IF NOT EXISTS series_info (
  tt TEXT PRIMARY KEY REFERENCES titles(tt) ON DELETE CASCADE,
  seasons INTEGER,
  episodes INTEGER,
  status TEXT,
  end_date TEXT,
  source TEXT
);

-- Relaciones entre títulos (MUY IMPORTANTE: secuelas, universos, remakes…)
CREATE TABLE IF NOT EXISTS title_relations (
  from_tt TEXT NOT NULL REFERENCES titles(tt) ON DELETE CASCADE,
  to_tt TEXT NOT NULL REFERENCES titles(tt) ON DELETE CASCADE,
  relation_type TEXT NOT NULL
    CHECK (relation_type IN ('sequel','prequel','universe','remake','spinoff','adaptation','related')),
  source TEXT,
  PRIMARY KEY (from_tt, to_tt, relation_type),
  CHECK (from_tt != to_tt)
);

-- Obras origen (libros, cómics, manga… en los que está basado)
CREATE TABLE IF NOT EXISTS works_origin (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tt TEXT NOT NULL REFERENCES titles(tt) ON DELETE CASCADE,
  work_title TEXT NOT NULL,
  work_type TEXT NOT NULL
    CHECK (work_type IN ('book','comic','manga','play','other')),
  author TEXT,
  source TEXT,
  UNIQUE (tt, work_title, work_type)
);

-- Referencias visuales (posters / carátulas; solo URL + origen en esta fase)
CREATE TABLE IF NOT EXISTS media_refs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  tt TEXT NOT NULL REFERENCES titles(tt) ON DELETE CASCADE,
  kind TEXT NOT NULL CHECK (kind IN ('poster','still','trailer','other')),
  url TEXT NOT NULL,
  source TEXT
);

-- Auditoría de syncs
CREATE TABLE IF NOT EXISTS sync_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  started_at TEXT NOT NULL DEFAULT (datetime('now')),
  csv_path TEXT,
  total_rows INTEGER NOT NULL DEFAULT 0,
  nuevos INTEGER NOT NULL DEFAULT 0,
  actualizados INTEGER NOT NULL DEFAULT 0,
  en_cuarentena INTEGER NOT NULL DEFAULT 0,
  diffs INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sync_diffs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER NOT NULL REFERENCES sync_runs(id) ON DELETE CASCADE,
  tt TEXT NOT NULL,
  campo TEXT NOT NULL,
  anterior TEXT,
  nuevo TEXT,
  tipo TEXT NOT NULL
    CHECK (tipo IN ('nuevo_titulo','rating_cambiado','campo_publico','conflicto_protegido'))
);

CREATE TABLE IF NOT EXISTS import_quarantine (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER REFERENCES sync_runs(id) ON DELETE CASCADE,
  row_num INTEGER,
  motivo TEXT NOT NULL,
  raw_line TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

-- Índices con propósito (solo lo consultado)
CREATE INDEX IF NOT EXISTS idx_titles_title ON titles(title_es);
CREATE INDEX IF NOT EXISTS idx_titles_year ON titles(year);
CREATE INDEX IF NOT EXISTS idx_titles_rating ON titles(imdb_rating);
CREATE INDEX IF NOT EXISTS idx_user_rating ON user_state(my_rating);
CREATE INDEX IF NOT EXISTS idx_user_status ON user_state(watch_status);
CREATE INDEX IF NOT EXISTS idx_genres_genre ON title_genres(genre);
CREATE INDEX IF NOT EXISTS idx_diffs_run ON sync_diffs(run_id);
CREATE INDEX IF NOT EXISTS idx_diffs_tt ON sync_diffs(tt);
