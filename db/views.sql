-- Vistas de lectura para el futuro frontend (solo SELECT, nada inventado).

-- Tus valoraciones, de mayor a menor.
CREATE VIEW IF NOT EXISTS v_top_rated AS
SELECT t.tt, t.title_es, t.original_title, t.title_type, t.year,
       u.my_rating, u.date_rated, t.imdb_rating
FROM titles t JOIN user_state u ON u.tt = t.tt
WHERE u.my_rating IS NOT NULL
ORDER BY u.my_rating DESC, u.date_rated DESC;

-- Géneros que más te gustan (solo valoradas).
CREATE VIEW IF NOT EXISTS v_generos_fav AS
SELECT g.genre AS genero, COUNT(*) AS titulos,
       ROUND(AVG(u.my_rating), 2) AS nota_media
FROM title_genres g
JOIN user_state u ON u.tt = g.tt
WHERE u.my_rating IS NOT NULL
GROUP BY g.genre
ORDER BY nota_media DESC, titulos DESC;

-- Directores más frecuentes en tus valoradas.
CREATE VIEW IF NOT EXISTS v_directores_fav AS
SELECT p.name AS director, COUNT(*) AS titulos,
       ROUND(AVG(u.my_rating), 2) AS nota_media
FROM title_credits c
JOIN people p ON p.id = c.person_id
JOIN user_state u ON u.tt = c.tt
WHERE c.role = 'director' AND u.my_rating IS NOT NULL
GROUP BY p.name
ORDER BY titulos DESC, nota_media DESC;

-- Pendientes: en seguimiento sin tu nota.
CREATE VIEW IF NOT EXISTS v_pendientes AS
SELECT t.tt, t.title_es, t.original_title, t.title_type, t.year, t.imdb_rating
FROM titles t JOIN user_state u ON u.tt = t.tt
WHERE u.my_rating IS NULL
ORDER BY t.imdb_rating DESC;

-- Títulos sin enriquecer (sin sinopsis o sin reparto).
CREATE VIEW IF NOT EXISTS v_sin_enriquecer AS
SELECT t.tt, t.title_es,
       CASE WHEN t.synopsis IS NULL THEN 1 ELSE 0 END AS falta_sinopsis,
       CASE WHEN NOT EXISTS (SELECT 1 FROM title_cast c WHERE c.tt = t.tt)
            THEN 1 ELSE 0 END AS falta_reparto
FROM titles t
WHERE t.synopsis IS NULL
   OR NOT EXISTS (SELECT 1 FROM title_cast c WHERE c.tt = t.tt);
