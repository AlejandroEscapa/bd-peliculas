# Portfolio-ready MVP polish — bd-peliculas

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convertir el catálogo local en un proyecto que se sostenga solo en GitHub y en el portfolio: CI que lo demuestre, un panel que enseñe el enriquecido y una ficha accesible, sin romper el contrato 15 + 15 ni añadir dependencias.

**Architecture:** Se mantiene Python stdlib + SQLite y el panel HTML generado. La presentación vive en `README.md`, `.github/workflows/ci.yml` y `scripts/generar_vista.py`; el modelo de datos, los CLIs y los proveedores no se tocan.

**Tech Stack:** Python 3.11+, SQLite, `unittest`, HTML/CSS/JS estático, GitHub Actions, Vercel.

**Spec:** [`README.md`](../../../README.md), [`ROADMAP.md`](../../../ROADMAP.md) y la petición de portfolio del 2026-10-19.

## Global Constraints

- Runtime sin dependencias: solo stdlib de Python (`sqlite3`, `csv`, `json`, `html`, `unittest`).
- `data/`, `backups/`, `*.db` y `.env` nunca se versionan; claves solo por entorno (`TMDB_BEARER`, `OMDB_API_KEY`).
- Panel en español, estático, paginación 15 + 15 con `table.paginada` y `.more-btn`.
- Toda consulta parametrizada; todo texto de BD pasa por `html.escape`.
- La suite actual (35 tests) debe seguir verde; los tests nuevos usan `unittest`, no `pytest`.
- Una sola idea visual en este plan: el strip de pósters. Cualquier otro rediseño se propone aparte.
- URL viva: `https://bd-peliculas-weld.vercel.app` · repo: `https://github.com/AlejandroEscapa/bd-peliculas`.

## Review Focus

- **Título sin póster:** el strip debe mostrar un fallback legible, nunca un `<img>` roto.
- **Catálogo sin valoradas:** `generar()` no puede reventar ni mostrar un strip vacío sin explicación.
- **Texto hostil de la BD:** un título con `<`, `&` o `</script>` debe salir escapado, no ejecutarse.
- **Teclado en la ficha:** abrir con Enter, cerrar con Escape y devolver el foco al elemento que abrió; Tab no debe escapar del diálogo.
- **15 + 15:** el strip no puede alterar el número inicial de filas de las tablas paginadas.

## Ya entregado (2026-10-19)

- Ficha del portfolio: [`src/data/projects.ts`](C:/Users/Developer/Desktop/Proyectos/Portfolio/main/dev-portfolio/src/data/projects.ts), [`src/i18n/translations.ts`](C:/Users/Developer/Desktop/Proyectos/Portfolio/main/dev-portfolio/src/i18n/translations.ts) y `public/bd-peliculas-preview.png`. Tests dirigidos (19/19) y `npm run build` en verde.
- GitHub: descripción, homepage y topics actualizados.
- [`README.md`](../../../README.md), [`LICENSE`](../../../LICENSE) y [`docs/assets/dashboard.png`](../../assets/dashboard.png).

## Backlog priorizado

1. **Strip de pósters (elegido).** Es la mejora con más impacto por línea: usa datos que ya existen (`poster_url`, `my_rating`), enseña el enriquecido y convierte el panel en algo que se puede enseñar sin explicarlo. No sustituye la tabla ni rompe el 15 + 15.
2. **CI + accesibilidad (soporte).** Sin CI el repo no demuestra la suite; sin foco atrapado, la ficha es incómoda con teclado. Son tareas pequeñas con retorno alto.
3. **Demo reproducible (siguiente).** Un `scripts/demo.py` con un CSV sintético permitiría clonar y ver el panel sin datos personales. Queda fuera para no inventar pósters ni mezclar datos reales.
4. **Refactor del generador (después).** `scripts/generar_vista.py` mezcla consulta, HTML y CSS. Separar datos, plantilla y estáticos bajaría el coste de cada iteración, pero no cambia lo que el usuario ve; no entra en el MVP.
5. **Stats visuales (no ahora).** Distribución de notas, décadas o países son una segunda idea visual. La regla del repo es una cada vez: primero el strip, luego se propone otra.

**No entra:** multiusuario, auth, Postgres, framework de frontend ni app nativa. Es un sistema personal y el coste no está justificado.

## File Structure

- Create: `.github/workflows/ci.yml` — matriz de tests en GitHub Actions.
- Create: `pyproject.toml` — metadatos y versión mínima de Python.
- Modify: `README.md` — badge de CI.
- Modify: `scripts/generar_vista.py` — CSS, HTML y JS del strip y de la ficha.
- Modify: `tests/test_vista_html.py` — tests del strip, del vacío y del escapado.
- Regenerate: `preview/dashboard.html` — artefacto que sirve Vercel.

---

### Task 1: CI y metadatos de proyecto

**Files:**
- Create: `.github/workflows/ci.yml`
- Create: `pyproject.toml`
- Modify: `README.md` (badge de CI)

**Interfaces:**
- Consumes: la suite existente `python -m unittest discover -s tests`.
- Produces: el check `tests` que GitHub muestra en el README y en cada PR.

- [ ] **Step 1: Crear `pyproject.toml`**

```toml
[project]
name = "bd-peliculas"
version = "1.0.0"
description = "Catálogo personal de IMDb en SQLite con importación delta y panel estático"
readme = "README.md"
requires-python = ">=3.11"
license = { text = "MIT" }
authors = [{ name = "Alejandro Olivares Escapa" }]
dependencies = []
```

- [ ] **Step 2: Crear `.github/workflows/ci.yml`**

```yaml
name: tests

on:
  push:
  pull_request:

jobs:
  tests:
    runs-on: ubuntu-latest
    strategy:
      fail-fast: false
      matrix:
        python-version: ["3.11", "3.12", "3.13", "3.14"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Suite
        run: python -m unittest discover -s tests -v
```

- [ ] **Step 3: Verificar que la suite local sigue verde**

Run: `python -m unittest discover -s tests`
Expected: `Ran 35 tests` y `OK`.

- [ ] **Step 4: Añadir el badge al README**

Inserta debajo del título:

```markdown
[![tests](https://github.com/AlejandroEscapa/bd-peliculas/actions/workflows/ci.yml/badge.svg)](https://github.com/AlejandroEscapa/bd-peliculas/actions/workflows/ci.yml)
```

- [ ] **Step 5: Comprobar el workflow**

Run: `grep -q 'python-version' .github/workflows/ci.yml && grep -q 'unittest discover' .github/workflows/ci.yml && echo OK`
Expected: `OK`.

- [ ] **Step 6: Commit**

```bash
git add .github/workflows/ci.yml pyproject.toml README.md
git commit -m "ci: suite en matriz de Python y metadatos del proyecto"
```

---

### Task 2: Strip de pósters (la única idea visual del plan)

**Files:**
- Modify: `scripts/generar_vista.py` — consulta, helper de iniciales, HTML, CSS y listener.
- Modify: `tests/test_vista_html.py` — cinco tests nuevos.
- Regenerate: `preview/dashboard.html`.

**Interfaces:**
- Consumes: `generar(db_path: Path) -> str`, las tablas `titles` y `user_state`, y la función JS existente `abrirFicha(tt: string)`.
- Produces: un `<div class="poster-grid">` con hasta 10 `<button class="poster-card" data-tt="…">`; los tests lo localizan por ese marcador.

- [ ] **Step 1: Añadir el test que falla**

En `tests/test_vista_html.py`, añade `import sqlite3` y estos helpers/tests dentro de `TestVistaHtml`:

```python
def _generar_con_fixture(self, *, poster=None, sin_notas=False):
    tmp = tempfile.TemporaryDirectory()
    self.addCleanup(tmp.cleanup)
    db_path = Path(tmp.name) / "test.db"
    import_csv(FIXTURE, db_path)
    conn = sqlite3.connect(db_path)
    if poster:
        conn.execute("UPDATE titles SET poster_url = ? WHERE tt = 'tt0068646'", (poster,))
    if sin_notas:
        conn.execute("UPDATE user_state SET my_rating = NULL")
    conn.commit()
    conn.close()
    return generar(db_path)

def _bloque_posters(self, pagina):
    inicio = pagina.index('class="poster-grid"')
    return pagina[inicio:pagina.index("</section>", inicio)]

def test_poster_strip_solo_valoradas(self):
    bloque = self._bloque_posters(self._generar_con_fixture())
    self.assertEqual(bloque.count('class="poster-card'), 2)
    self.assertIn('data-tt="tt0068646"', bloque)
    self.assertIn('data-tt="tt2098220"', bloque)

def test_poster_sin_url_usa_iniciales(self):
    bloque = self._bloque_posters(self._generar_con_fixture())
    self.assertIn("poster-fallback", bloque)
    self.assertIn(">EP<", bloque)

def test_poster_usa_url(self):
    bloque = self._bloque_posters(
        self._generar_con_fixture(poster="https://example.com/padrino.jpg"))
    self.assertIn('src="https://example.com/padrino.jpg"', bloque)
    self.assertIn('alt="Póster de El padrino"', bloque)

def test_sin_valoradas_muestra_estado_vacio(self):
    bloque = self._bloque_posters(self._generar_con_fixture(sin_notas=True))
    self.assertIn("Aún no has valorado nada.", bloque)
    self.assertEqual(bloque.count('class="poster-card'), 0)

def test_poster_escapa_html(self):
    tmp = tempfile.TemporaryDirectory()
    self.addCleanup(tmp.cleanup)
    db_path = Path(tmp.name) / "test.db"
    import_csv(FIXTURE, db_path)
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE titles SET title_es = '<script>alert(1)</script>' WHERE tt = 'tt0068646'")
    conn.commit()
    conn.close()
    bloque = self._bloque_posters(generar(db_path))
    self.assertNotIn("<script>alert(1)</script>", bloque)
    self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", bloque)
```

- [ ] **Step 2: Ejecutar y ver el fallo**

Run: `python -m unittest tests.test_vista_html -v`
Expected: FAIL con `ValueError: substring not found` porque `poster-grid` aún no existe.

- [ ] **Step 3: Añadir la consulta de los 10 mejores**

En `generar()`, después de la consulta `top`:

```python
top_posters = c.execute(
    """SELECT t.tt, t.title_es, t.original_title, t.year, u.my_rating, t.poster_url
       FROM titles t JOIN user_state u ON u.tt = t.tt
       WHERE u.my_rating IS NOT NULL
       ORDER BY u.my_rating DESC, u.date_rated DESC
       LIMIT 10"""
).fetchall()
```

- [ ] **Step 4: Añadir el helper y el HTML del strip**

Antes de `def generar(...)`, añade:

```python
def _iniciales(titulo: str) -> str:
    partes = [p for p in titulo.split() if p]
    return "".join(p[0] for p in partes[:2]).upper() or "?"


def _tarjeta_poster(r: sqlite3.Row, e=html.escape) -> str:
    titulo = r["title_es"] or r["original_title"] or ""
    if r["poster_url"]:
        media = (f'<img src="{e(r["poster_url"])}" '
                 f'alt="Póster de {e(titulo)}" loading="lazy">')
        clase = "poster-card"
    else:
        media = f'<span class="poster-fallback" aria-hidden="true">{e(_iniciales(titulo))}</span>'
        clase = "poster-card no-poster"
    return (f'<button type="button" class="{clase}" data-tt="{e(r["tt"])}" '
            f'aria-label="Abrir ficha de {e(titulo)}">'
            f'{media}<span class="poster-rating">{r["my_rating"]}</span>'
            f'<span class="poster-title">{e(titulo)}</span>'
            f'<span class="poster-year">{r["year"] or "?"}</span></button>')
```

En `generar()`, después de `kpis`, construye el bloque:

```python
posters = "".join(_tarjeta_poster(r) for r in top_posters) or (
    '<p class="empty">Aún no has valorado nada.</p>')
posters_html = (
    '<section class="poster-section" aria-labelledby="posters-title">'
    '<div class="section-head"><h2 id="posters-title">Tus favoritas, en cartel</h2>'
    '<span class="hint">Top 10 por tu nota. Pulsa una para abrir la ficha.</span></div>'
    f'<div class="poster-grid">{posters}</div></section>')
```

Inserta `{posters_html}` justo después de `{kpis}` en el `return`.

- [ ] **Step 5: Añadir CSS**

Dentro de `CSS`, antes de `footer`:

```css
.poster-section { padding: 22px; }
.section-head { display: flex; align-items: baseline; justify-content: space-between;
gap: 12px; flex-wrap: wrap; margin-bottom: 14px; }
.poster-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; }
.poster-card { position: relative; border: none; background: none; padding: 0;
text-align: left; cursor: pointer; border-radius: 12px; }
.poster-card img, .poster-fallback { width: 100%; aspect-ratio: 2 / 3; object-fit: cover;
border-radius: 12px; background: var(--line); display: flex; align-items: center;
justify-content: center; }
.poster-fallback { font-size: 30px; font-weight: 700; color: var(--sub);
background: linear-gradient(135deg, #e8e8ed, #d9d9e0); }
.poster-card img { display: block; transition: transform .18s ease; }
.poster-card:hover img { transform: scale(1.02); }
.poster-card:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.poster-rating { position: absolute; top: 8px; left: 8px; background: var(--accent);
color: #fff; border-radius: 999px; padding: 2px 9px; font-size: 12px; font-weight: 700; }
.poster-title { display: block; margin-top: 8px; font-size: 13px; font-weight: 600;
white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.poster-year { display: block; color: var(--sub); font-size: 12px; }
.empty { color: var(--sub); font-size: 14px; }
@media (max-width: 760px) { .poster-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
```

- [ ] **Step 6: Conectar los pósters con la ficha**

En el JS, justo después de `window.abrirFicha = abrirFicha;`, añade:

```javascript
document.querySelectorAll('.poster-card').forEach((card) => {
  card.addEventListener('click', () => {
    const tt = card.dataset.tt;
    if (tt) abrirFicha(tt);
  });
});
```

- [ ] **Step 7: Ejecutar los tests**

Run: `python -m unittest discover -s tests`
Expected: `Ran 40 tests` y `OK`.

- [ ] **Step 8: Regenerar el panel real y verlo**

Run: `python scripts/generar_vista.py --db catalogo.db`
Expected: imprime `preview/dashboard.html`; `grep -c 'class="poster-card' preview/dashboard.html` devuelve 10.

Después, sirve el panel (`python -m http.server 8000`) y abre `http://127.0.0.1:8000/preview/dashboard.html`; pulsa el primer póster y comprueba que `#overlay` deja de estar `hidden`. Cierra con Escape.

- [ ] **Step 9: Commit**

```bash
git add scripts/generar_vista.py tests/test_vista_html.py preview/dashboard.html
git commit -m "feat: strip de pósters en el panel con fallback y ficha"
```

---

### Task 3: Foco y teclado en la ficha

**Files:**
- Modify: `scripts/generar_vista.py` — foco, `aria-live` y cierre con Escape.
- Modify: `tests/test_vista_html.py` — test de marcadores de accesibilidad.
- Regenerate: `preview/dashboard.html`.

**Interfaces:**
- Consumes: `abrirFicha`, `cerrarFicha`, el overlay y el buscador global.
- Produces: `cerrarFicha` devuelve el foco al disparador; el overlay atrapa Tab; el contador de búsqueda se anuncia.

- [ ] **Step 1: Añadir el test que falla**

```python
def test_marcadores_de_accesibilidad(self):
    pagina = self._generar_con_fixture()
    for marcador in ('aria-live="polite"', 'aria-haspopup="listbox"',
                     'aria-autocomplete="list"', 'role="dialog"',
                     'aria-modal="true"'):
        self.assertIn(marcador, pagina)
```

- [ ] **Step 2: Ejecutar y ver el fallo**

Run: `python -m unittest tests.test_vista_html -v`
Expected: FAIL en el primer marcador ausente.

- [ ] **Step 3: Atributos del buscador**

En el HTML del `<input id="buscador-global">`, añade `aria-haspopup="listbox"` y `aria-autocomplete="list"`. En el JS que crea `info`, añade `info.setAttribute("aria-live", "polite");`.

- [ ] **Step 4: Foco y trampa de Tab**

En el JS del overlay:

```javascript
let focoPrevio = null;
const cerrarFicha = () => {
  if (overlay.hidden) return;
  overlay.hidden = true;
  contenido.innerHTML = '';
  document.body.style.overflow = '';
  if (focoPrevio && typeof focoPrevio.focus === 'function') focoPrevio.focus();
};
```

En `abrirFicha`, antes de `cerrarBtn.focus();`:

```javascript
focoPrevio = document.activeElement;
document.body.style.overflow = 'hidden';
```

Añade el trap una sola vez, fuera de `abrirFicha`:

```javascript
overlay.addEventListener('keydown', (ev) => {
  if (ev.key !== 'Tab' || overlay.hidden) return;
  const focusables = [...overlay.querySelectorAll(
    'button, a[href], [tabindex]:not([tabindex="-1"])')];
  if (!focusables.length) return;
  const first = focusables[0];
  const last = focusables[focusables.length - 1];
  if (ev.shiftKey && document.activeElement === first) {
    ev.preventDefault();
    last.focus();
  } else if (!ev.shiftKey && document.activeElement === last) {
    ev.preventDefault();
    first.focus();
  }
});
```

- [ ] **Step 5: Verificar el foco de verdad**

Run: `python scripts/generar_vista.py --db catalogo.db` y abre el panel en el navegador.

Comprueba, en este orden:
1. Tab hasta un póster y pulsa Enter: la ficha se abre y el foco está en el botón de cerrar.
2. Tab recorre solo elementos de la ficha; Shift+Tab tampoco sale.
3. Escape cierra y el foco vuelve al póster que abrió.

Expected: los tres pasos se cumplen; si falla el 3, `focoPrevio` no se está guardando antes de `cerrarBtn.focus()`.

- [ ] **Step 6: Ejecutar la suite**

Run: `python -m unittest discover -s tests`
Expected: `Ran 41 tests` y `OK`.

- [ ] **Step 7: Commit**

```bash
git add scripts/generar_vista.py tests/test_vista_html.py preview/dashboard.html
git commit -m "a11y: foco atrapado y devuelto en la ficha; anuncios de búsqueda"
```
