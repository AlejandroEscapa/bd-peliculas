# F0 — Catálogo multiusuario para círculo privado

- Fecha: 2026-10-19
- Estado: **superada el 2026-10-19**. El diseño de catálogo compartido con
  Postgres quedó descartado al fijar una BD por usuario. Se conserva como
  registro de análisis; no implementar tal cual. Ver `ROADMAP.md`.
- Alcance: F0 (base multiusuario). No incluye PWA, registro público ni app nativa.

## 1. Objetivo

Convertir el catálogo local de un usuario en una aplicación web para un
círculo privado de 10-20 personas, donde cada persona importa su export de
IMDb y obtiene su catálogo enriquecido, compartiendo un catálogo canónico de
títulos para no multiplicar llamadas a TMDB.

Criterio de éxito de F0: cinco amigos pueden entrar por invitación, subir su
CSV y ver su catálogo sin intervención manual, con aislamiento estricto entre
usuarios y sin romper ninguna regla de negocio existente.

## 2. Decisiones fijadas

| Decisión | Elección | Motivo |
|---|---|---|
| Audiencia | Círculo privado, gratis, sin monetización | Encaja con TMDB no comercial y evita moderación, cuotas y renegociar datos |
| Catálogo | Canónico y compartido por `tt` | Elimina el coste repetido de API; el amigo 20 casi no cuesta |
| Capa personal | Delta por usuario | Cada cual tiene sus notas, estado y fechas |
| Backend | FastAPI + Postgres + worker propio | Reutiliza el dominio Python y sus tests; sin Redis en F0 |
| Frontend | Next.js App Router + TypeScript | Base para la PWA de F1 |
| Base de datos | Postgres 16+ (Neon o Supabase) | Escrituras concurrentes, jobs con `SKIP LOCKED`, backups gestionados |
| SQLite | Se retira como motor de la app | Mantener dos dialectos es deuda; queda solo para backup/export |
| Auth | Invitación + email/contraseña + sesión en BD | 20 cuentas no justifican proveedor externo; sin dependencia de email en F0 |
| Jobs | Cola en Postgres | Volumen bajo; un servicio menos que operar |

## 3. No objetivos de F0

- Registro abierto, verificación de email, recuperación Self-Service.
- PWA, offline, notificaciones push.
- App nativa o wrapper Capacitor/Expo.
- Recomendador, listas compartidas, perfiles públicos.
- Fase 2 de TMDB (`estreno_es`, presupuesto/taquilla, `serie_info`).
- Sincronización automática con Trakt.
- Monetización. Si aparece, obliga a revisar la fuente de datos y la licencia.

## 4. Arquitectura

Monolito modular en un repo:

```
domain/            reglas puras: sync, huecos, scraper, proveedores
api/               FastAPI: auth, catálogo, imports, admin
worker/            bucle de jobs: ingesta, enriquecimiento, refresco
web/               Next.js App Router + TypeScript
infra/             compose, migraciones Alembic, CI
scripts/           CLIs existentes, adaptadas a DATABASE_URL
```

Reglas de dependencia:

- `domain/` no importa FastAPI, Next ni variables de entorno de despliegue.
- `domain/` recibe una conexión y un `user_id` donde aplique; nunca abre la
  base por ruta.
- `api/` y `worker/` comparten `domain/` y los mismos repositorios.
- `web/` solo habla con la API; no accede a la base.

El CLI actual se conserva y apunta a Postgres mediante `DATABASE_URL`, para
poder operar y depurar sin levantar la web.

## 5. Modelo de datos

Una sola revisión Alembic inicial para Postgres, `0001_postgres_multiusuario`,
que crea el esquema objetivo. Las migraciones SQLite (`0001_base`) quedan como
registro histórico y dejan de aplicarse. No se edita ninguna migración ya
aplicada en producción.

### 5.1 Identidad y sesiones

```sql
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE users (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email         citext NOT NULL UNIQUE,
  password_hash text NOT NULL,
  display_name  text NOT NULL,
  is_admin      boolean NOT NULL DEFAULT false,
  created_at    timestamptz NOT NULL DEFAULT now(),
  deleted_at    timestamptz
);

CREATE TABLE invites (
  code       text PRIMARY KEY,
  created_by uuid REFERENCES users(id) ON DELETE SET NULL,
  used_by    uuid REFERENCES users(id) ON DELETE SET NULL,
  expires_at timestamptz NOT NULL,
  used_at    timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE sessions (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash   text NOT NULL UNIQUE,
  created_at   timestamptz NOT NULL DEFAULT now(),
  last_seen_at timestamptz NOT NULL DEFAULT now(),
  expires_at   timestamptz NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions (user_id);
```

- Contraseñas con `argon2id` (`argon2-cffi`).
- Token de sesión: 32 bytes aleatorios; se guarda SHA-256, nunca el valor.
- Cookie `sid`: `HttpOnly`, `Secure`, `SameSite=Lax`, `Path=/`, 30 días.
- Renovación deslizante: se actualiza `expires_at` como máximo una vez al día
  para no escribir en cada petición.
- Sin email en F0: el admin restablece contraseñas por CLI y entrega una
  contraseña temporal de un solo uso por un canal privado.

### 5.2 Catálogo canónico

Se conservan `titles`, `genres`, `title_genres`, `people`, `title_credits`,
`title_cast`, `title_countries`, `release_dates`, `series_info`,
`title_relations`, `works_origin` y `media_refs` con estas traducciones:

- `INTEGER PRIMARY KEY AUTOINCREMENT` → `GENERATED ALWAYS AS IDENTITY`.
- `TEXT` de fechas → `timestamptz` donde sea fecha técnica; las fechas de
  negocio (`release_date_csv`, `date_rated`, `rel_date`) siguen `text` o
  `date` según su formato real, sin reinterpretarlas.
- `datetime('now')` → `now()`.
- `CHECK (tt GLOB 'tt[0-9]*')` → `CHECK (tt ~ '^tt[0-9]{7,8}$')`.
- `INSERT OR IGNORE` → `ON CONFLICT DO NOTHING`.
- `INSERT OR REPLACE` → `ON CONFLICT (...) DO UPDATE SET ...`.
- `cursor.lastrowid` → `RETURNING id`.
- Marcadores `?` → `%s`; filas con `psycopg.rows.dict_row` para conservar el
  acceso por nombre.

La migración inicial crea además dos columnas nuevas en `titles`:

```sql
enriched_at    timestamptz,
refresh_due_at timestamptz
```

`enriched_at` y `refresh_due_at` los gestiona el worker; el CSV no los toca.

### 5.3 Capa personal

```sql
CREATE TABLE user_state (
  user_id       uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  tt            text NOT NULL REFERENCES titles(tt) ON DELETE CASCADE,
  my_rating     integer CHECK (my_rating BETWEEN 1 AND 10),
  date_rated    text,
  watch_status  text NOT NULL DEFAULT 'watchlist'
                CHECK (watch_status IN ('rated','watchlist')),
  personal_note text,
  csv_created   text,
  csv_modified  text,
  csv_position  integer,
  updated_at    timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (user_id, tt)
);
CREATE INDEX idx_user_state_status ON user_state (user_id, watch_status);
CREATE INDEX idx_user_state_rating ON user_state (user_id, my_rating);
```

`sync_runs`, `sync_diffs` e `import_quarantine` ganan `user_id NOT NULL` con
`ON DELETE CASCADE`. `sync_diffs` lo lleva desnormalizado para poder auditar y
filtrar sin unir por `run_id`.

### 5.4 Cola de enriquecimiento

```sql
CREATE TABLE title_jobs (
  tt              text NOT NULL REFERENCES titles(tt) ON DELETE CASCADE,
  kind            text NOT NULL CHECK (kind IN ('enrich','refresh')),
  status          text NOT NULL DEFAULT 'pending'
                  CHECK (status IN ('pending','running','done','retry','dead')),
  attempts        integer NOT NULL DEFAULT 0,
  last_error      text,
  next_attempt_at timestamptz NOT NULL DEFAULT now(),
  locked_at       timestamptz,
  locked_by       text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tt, kind)
);
CREATE INDEX idx_title_jobs_ready ON title_jobs (status, next_attempt_at);

-- Cuota diaria de proveedores, compartida por todos los procesos
CREATE TABLE api_usage (
  day      date    NOT NULL,
  provider text    NOT NULL,
  count    integer NOT NULL DEFAULT 0,
  PRIMARY KEY (day, provider)
);
```

La cola es **global**, no por usuario. Un `tt` se enriquece una vez y sirve a
todos. Al importar, se calculan los huecos del catálogo y se hace
`INSERT ... ON CONFLICT DO NOTHING` de los trabajos que falten.

El trabajo de refresco no se queda `done` para siempre: el mantenimiento
reactiva a `pending` los `tt` con `refresh_due_at <= now()` y sin trabajo
activo. `api_usage` permite que el tope diario de OMDb sobreviva a reinicios
y sea correcto si algún día hay más de un worker.

### 5.5 Vistas

`db/views.sql` no se porta: las vistas actuales están atadas a un único
usuario. Los KPI pasan a consultas del repositorio con `WHERE user_id = %s`.
No se exponen vistas SQL a la API.

## 6. Contratos de API

Prefijo `/api/v1`. JSON, errores `application/problem+json`.
Autenticación por cookie de sesión. Toda consulta se filtra por el usuario
autenticado; ningún `user_id` se acepta desde el cliente.

| Método | Ruta | Auth | Descripción |
|---|---|---|---|
| POST | `/auth/accept-invite` | pública | Crea cuenta con código de invitación |
| POST | `/auth/login` | pública | Crea sesión |
| POST | `/auth/logout` | sesión | Invalida la sesión actual |
| GET | `/me` | sesión | Perfil y rol |
| DELETE | `/me` | sesión | Borra la capa personal y la cuenta |
| GET | `/me/export` | sesión | Export JSON de sus datos |
| POST | `/imports` | sesión | Sube CSV (multipart), crea run y encola |
| GET | `/imports/{run_id}` | sesión | Estado y resumen del run |
| GET | `/titles` | sesión | Catálogo paginado y filtrado |
| GET | `/titles/{tt}` | sesión | Ficha completa |
| PATCH | `/user-state/{tt}` | sesión | Nota, estado o nota personal |
| GET | `/stats` | sesión | KPIs del usuario |
| POST | `/admin/invites` | admin | Crea invitación |
| POST | `/admin/users/{id}/reset-password` | admin | Genera contraseña temporal y la devuelve una sola vez al admin |
| GET | `/admin/jobs` | admin | Estado de la cola |

### 6.1 Formato de lista

```json
{
  "items": [
    {
      "tt": "tt0111161",
      "title_es": "Cadena perpetua",
      "original_title": "The Shawshank Redemption",
      "year": 1994,
      "title_type": "Película",
      "imdb_rating": 9.3,
      "my_rating": 10,
      "watch_status": "rated",
      "poster_url": "https://image.tmdb.org/t/p/w500/...",
      "genres": ["Drama"]
    }
  ],
  "page": 1,
  "per_page": 15,
  "total": 207
}
```

Filtros: `q` (título ES/original, director, actor, género), `genero`,
`status`, `min_rating`, `max_rating`, `sort` (`rating_desc`, `year_desc`,
`title_asc`). `per_page` máximo 100; por defecto 15.

### 6.2 Detalle

Incluye sinopsis y su fuente, reparto con personaje, equipo, países, géneros,
fechas, duración, dinero y series. Si falta un bloque, se devuelve `null` o
lista vacía; el frontend muestra el fallback acordado.

### 6.3 Errores

Formato `application/problem+json` con `type`, `title`, `status` y `detail`.

- `400` CSV inválido o parámetros fuera de rango.
- `401` sin sesión válida.
- `404` recurso inexistente **o de otro usuario** (no se revela existencia).
- `409` invitación usada o email ya registrado.
- `413` CSV mayor de 5 MB.
- `422` validación de esquema.
- `429` rate limit de login.

### 6.4 UI mínima de F0

F0 no rediseña el panel. Entrega solo lo necesario para validar el flujo
multiusuario:

- Aceptar invitación, login y logout.
- Subida de CSV con estado del run.
- Lista de catálogo paginada 15+15 y ficha en overlay, reutilizando el HTML,
  la paleta y el comportamiento ya probados.
- Página de créditos con el aviso de TMDB.

La búsqueda global, los filtros avanzados y la PWA son F1.

### 6.5 Subida de CSV

- `multipart/form-data`, campo `file`, máximo 5 MB y 10.000 filas.
- Codificación `utf-8-sig`; cabeceras mínimas: `Const`, `Your Rating`,
  `Title`, `Title Type`, `Year`, `Genres`, `Directors`.
- `tt` inválido va a `import_quarantine`, no aborta el run.
- Respuesta `202` con `run_id`; el cliente consulta el estado.

## 7. Ingesta y trabajos

### 7.1 Flujo

1. La API guarda el CSV en `STORAGE_DIR` (volumen persistente del worker;
   los ficheros de 20 personas son diminutos) y crea `sync_runs` en estado
   `pending` con la ruta y un hash del contenido.
2. El worker reclama el run con `FOR UPDATE SKIP LOCKED`.
3. Ejecuta `domain.sync.import_csv(conn, user_id, path)` con las reglas
   intactas: vacío no borra, diffs auditados, cuarentena por `tt` inválido.
4. Calcula huecos globales y encola `title_jobs` que falten.
5. Marca el run como `done` con su resumen; los errores de parseo quedan en
   cuarentena y no tumban el run.

### 7.2 Enriquecimiento

- Reclama trabajos `pending`/`retry` con `next_attempt_at <= now()` usando
  `FOR UPDATE SKIP LOCKED` y lock por `tt`.
- Llama al proveedor combinado existente, con `solo_faltantes=True`.
- Un fallo por título no aborta el lote; se registra `last_error`.
- Backoff: 1 min, 5 min, 30 min, 2 h, 12 h. Máximo 6 intentos; después
  `dead` y visible en admin.
- Token bucket global de 20 rps. En F0 corre **un solo worker**; si se
  escala a varios, el bucket pasa a Postgres.
- Contador diario de OMDb en `api_usage`, con tope 900 y reinicio por fecha
  UTC; al llegar al tope, el trabajo vuelve a `pending` para el día siguiente.
- Respeto de `429` de TMDB con backoff y `Retry-After` si viene.
- Al terminar, `titles.enriched_at = now()` y
  `refresh_due_at = now() + 180 días`.

### 7.3 Refresco automático

Un job de mantenimiento encola `kind='refresh'` para títulos con
`refresh_due_at <= now()`. Refresca metadatos caducados sin tocar
`user_state`. Es la parte "se actualiza solo"; las notas del usuario no se
pueden sincronizar sin re-subir el CSV o conectar Trakt en una fase futura.

### 7.4 Observabilidad

- Logs JSON con `run_id`, `tt`, `attempt` y duración.
- `/healthz` (proceso vivo) y `/readyz` (base de datos accesible).
- `title_jobs` es la fuente de verdad del estado; el admin ve pendientes,
  reintentos y muertos.
- Sin Sentry en F0; se evalúa cuando haya beta real.

## 8. Seguridad y datos

- Invitaciones de un solo uso, caducidad 7 días, creadas por admin.
- `argon2id`, mínimo 12 caracteres, rate limit de login por email e IP.
- Sesiones revocables; logout borra la fila.
- Mutaciones con verificación de `Origin`/`Referer` contra `APP_ORIGIN`, y
  `SameSite=Lax` como segunda barrera.
- Consultas siempre parametrizadas; nada de SQL construido con entrada.
- Aislamiento: todo repositorio recibe `user_id` y lo aplica en el `WHERE`;
  los tests cubren el caso de dos usuarios con el mismo `tt`.
- Secretos solo por entorno: `DATABASE_URL`, `SESSION_SECRET`,
  `TMDB_BEARER`, `OMDB_API_KEY`, `APP_ORIGIN`, `STORAGE_*`. Nunca en Git ni
  en el bundle del navegador.
- Subida: límite de tamaño, comprobación de cabeceras y parseo defensivo.
- Borrado de cuenta: `ON DELETE CASCADE` sobre su capa personal, runs, diffs
  y cuarentena; los títulos canónicos permanecen.
- Backup nocturno `pg_dump` con retención de 14 días y prueba de restauración
  documentada.

## 9. Migración de datos existentes

Script `scripts/migrar_a_postgres.py`, idempotente y con `--dry-run`:

1. Crea el esquema con Alembic.
2. Crea el usuario admin inicial a partir de `ADMIN_EMAIL` y una contraseña
   temporal introducida por consola (nunca por argumento).
3. Copia `titles`, géneros, personas, créditos, cast, países, fechas, series,
   relaciones, obras y medios.
4. Copia `user_state` asignando todo al admin.
5. Copia `sync_runs`, `sync_diffs` e `import_quarantine` con ese `user_id`.
6. Verifica conteos contra el SQLite de origen y aborta si no cuadran.

Conteos de referencia del catálogo actual: 207 títulos, 207 estados, 470
filas de cast, 485 créditos, 669 géneros, 227 diffs, 157 sinopsis y 157
pósters. La migración no modifica el SQLite original.

## 10. Pruebas

La suite SQLite actual es la especificación de comportamiento: sus 35 casos
se portan a Postgres y deben seguir pasando. No se debilita ninguna regla.

- Framework: `pytest` para lo nuevo; los casos portados conservan su
  intención y sus aserciones.
- Base de datos de test: Postgres efímero (servicio en CI o contenedor),
  migraciones aplicadas y transacción revertida por test.
- Los casos portados conservan nombre y aserción; si un caso no se puede
  portar por una diferencia real de motor, se documenta y se sustituye por
  uno equivalente, nunca se elimina sin reemplazo.
- Nuevos tests obligatorios:
  - Aislamiento: dos usuarios, mismo `tt`, notas distintas; cada uno ve solo
    lo suyo y un `run_id` ajeno devuelve 404.
  - Auth: login correcto/incorrecto, cookie ausente, sesión caducada,
    invitación usada, `Origin` inválido en mutación.
  - Import: idempotencia, cuarentena, vacío que no borra, CSV gigante.
  - Jobs: reintento con backoff, paso a `dead`, un título roto no aborta el
    lote, no se duplica el trabajo de un `tt`.
  - Migración: conteos y muestras equivalentes entre SQLite y Postgres.
- CI: `ruff`, `pytest`, `tsc --noEmit` y build de Next.

## 11. Despliegue y operación

- Local: `docker compose up` con `postgres`, `api`, `worker`, `web`.
- Producción: Postgres gestionado (Neon o Supabase), API y worker en Fly.io o
  Railway, web en Vercel.
- Coste esperado: 0-15 €/mes para el círculo privado.
- Variables documentadas en `infra/.env.example` solo con nombres, sin
  valores.
- GitHub Actions: tests y migraciones en cada push; despliegue manual en F0.
- Atribución TMDB visible en la web (`Créditos`), con el aviso literal:
  «This product uses the TMDB API but is not endorsed or certified by TMDB.»
  y el logo aprobado, sin más protagonismo que el de la app.

## 12. Criterios de aceptación de F0

1. `docker compose up` levanta los cuatro servicios y `/readyz` responde 200.
2. La migración copia el catálogo con conteos idénticos y deja intacto el
   SQLite original.
3. El CLI `scripts/actualizar_peliculas.py` funciona contra Postgres con
   `DATABASE_URL`.
4. Dos usuarios con el mismo `tt` mantienen notas distintas y no se ven entre
   sí; acceder a un recurso ajeno devuelve 404.
5. Reimportar el mismo CSV produce 0 nuevos y 0 diffs.
6. Un fallo simulado del proveedor genera reintento con backoff y acaba en
   `dead` tras 6 intentos, sin abortar el resto del lote.
7. Los 35 casos de comportamiento siguen verdes sobre Postgres, más los
   nuevos de tenencia, auth, import y jobs.
8. Ningún secreto aparece en el repo ni en el bundle del navegador.
9. Una copia de seguridad se restaura con éxito en un entorno limpio.

## 13. Riesgos

| Riesgo | Impacto | Mitigación |
|---|---|---|
| Portar SQL de SQLite a Postgres introduce regresiones | Alto | Suite de caracterización portada caso a caso; migración con verificación de conteos |
| Acoplamiento del dominio a `sqlite3.Row` | Medio | `dict_row` de psycopg y conexión inyectada |
| Bugs de auth o CSRF | Alto | Sesiones en BD, `Origin` check, tests negativos, revisión de seguridad |
| Pérdida de datos en la migración | Alto | Backup previo, `--dry-run`, verificación de conteos, SQLite intacto |
| Crecimiento de alcance hacia PWA o registro público | Medio | F0 cerrado; cada fase con su propia spec |
| Límite de TMDB/OMDb al crecer el grupo | Bajo | Catálogo compartido, dedupe, backoff y tope diario de OMDb |

## 14. Siguiente paso

Revisión de esta spec por el usuario. Tras su aprobación, se escribirá el
plan de implementación con tareas ordenadas, verificación por tarea y
estrategia de migración paso a paso. No se implementa nada antes de eso.
