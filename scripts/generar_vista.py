#!/usr/bin/env python3
"""Genera un panel HTML estático con tus stats (sin servidor ni dependencias).

Uso:
    python scripts/generar_vista.py [--db data/catalogo.db] [--salida preview/dashboard.html]

Interfaz simple: 5 KPIs + favoritas + géneros + directores + lista + seguimiento.
Todas las listas muestran 15 filas y un botón para cargar 15 más (JS puro).
"""
from __future__ import annotations

import argparse
import html
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import DEFAULT_DB_PATH

CSS = """
:root { --bg: #f5f5f7; --card: #ffffff; --ink: #1d1d1f; --sub: #6e6e73;
--accent: #0071e3; --line: #e8e8ed; --radius: 18px; }
* { box-sizing: border-box; margin: 0; }
body { font-family: -apple-system, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
background: var(--bg); color: var(--ink); padding: 40px 20px 80px; }
.wrap { max-width: 1080px; margin: 0 auto; }
header h1 { font-size: 40px; letter-spacing: -0.02em; }
header p { color: var(--sub); margin-top: 6px; font-size: 17px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
gap: 14px; margin: 28px 0; }
.kpi { background: var(--card); border-radius: var(--radius); padding: 18px; }
.kpi .n { font-size: 34px; font-weight: 700; letter-spacing: -0.02em; }
.kpi .l { color: var(--sub); font-size: 13px; margin-top: 4px; }
section { background: var(--card); border-radius: var(--radius);
padding: 22px; margin-bottom: 16px; }
section h2 { font-size: 21px; letter-spacing: -0.01em; margin-bottom: 4px; }
section .hint { color: var(--sub); font-size: 13px; margin-bottom: 14px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th { text-align: left; color: var(--sub); font-weight: 500; font-size: 12px;
text-transform: uppercase; letter-spacing: 0.06em; padding: 8px 10px;
border-bottom: 1px solid var(--line); }
td { padding: 9px 10px; border-bottom: 1px solid var(--line); }
tr:last-child td { border-bottom: none; }
.pill { display: inline-block; background: var(--accent); color: #fff;
border-radius: 999px; padding: 2px 10px; font-weight: 600; font-size: 13px; }
.bar { height: 8px; border-radius: 99px; background: var(--line); overflow: hidden;
min-width: 90px; }
.bar i { display: block; height: 100%; background: var(--accent); border-radius: 99px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 760px) { .grid2 { grid-template-columns: 1fr; } header h1 { font-size: 30px; } }
a { color: var(--accent); text-decoration: none; }
td.t { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 340px; }
.nw { white-space: nowrap; }
.np { color: var(--sub); font-weight: 700; font-size: 12px; letter-spacing: 0.1em; }
.more-wrap { display: flex; justify-content: center; padding-top: 14px; }
.more-btn { appearance: none; border: 1px solid var(--accent); background: #fff;
color: var(--accent); border-radius: 999px; padding: 8px 18px; font-weight: 600;
font-size: 13px; cursor: pointer; transition: transform .15s ease, background .15s ease; }
.more-btn:hover { background: var(--accent); color: #fff; }
.more-btn:active { transform: translateY(1px) scale(.98); }
.more-btn[hidden] { display: none; }
.count { color: var(--sub); font-size: 12px; text-align: center; margin-top: 8px; }
.search { width: 100%; padding: 10px 14px; border: 1px solid var(--line);
border-radius: 999px; font-size: 14px; margin-bottom: 12px; background: #fff; color: var(--ink); }
footer { color: var(--sub); font-size: 12px; text-align: center; margin-top: 26px; }
"""


def mostrar_generos(valor: str | None, limite: int = 3) -> str:
    """Solo muestra: primeros N géneros + '...' si hay más. No toca datos."""
    if not valor:
        return "-"
    partes = [p.strip() for p in valor.split(",") if p.strip()]
    visibles = partes[:limite]
    resto = len(partes) - len(visibles)
    texto = ", ".join(visibles)
    if resto > 0:
        texto += "..."
    return html.escape(texto)


def fila_tabla(celdas: list[str], cls_first: str | None = None) -> str:
    celdas = list(celdas)
    if cls_first and celdas:
        celdas[0] = f'<td class="{cls_first}">{celdas[0]}</td>'
        resto = "".join(f"<td>{c}</td>" for c in celdas[1:])
        return f"<tr>{celdas[0]}{resto}</tr>"
    return "<tr>" + "".join(f"<td>{c}</td>" for c in celdas) + "</tr>"


def generar(db_path: Path) -> str:
    c = sqlite3.connect(str(db_path))
    c.row_factory = sqlite3.Row
    total = c.execute("SELECT COUNT(*) n FROM titles").fetchone()["n"]
    valoradas = c.execute(
        "SELECT COUNT(*) n FROM user_state WHERE my_rating IS NOT NULL").fetchone()["n"]
    pendientes = total - valoradas
    media = c.execute(
        "SELECT ROUND(AVG(my_rating), 2) m FROM user_state WHERE my_rating IS NOT NULL"
    ).fetchone()["m"]
    top = c.execute("SELECT * FROM v_top_rated LIMIT 60").fetchall()
    generos = c.execute("SELECT * FROM v_generos_fav").fetchall()
    directores = c.execute("SELECT * FROM v_directores_fav LIMIT 30").fetchall()
    pend = c.execute("SELECT * FROM v_pendientes LIMIT 60").fetchall()
    actores = c.execute(
        "SELECT p.name actor, COUNT(*) titulos, ROUND(AVG(u.my_rating), 2) media "
        "FROM title_cast tc JOIN people p ON p.id = tc.person_id "
        "JOIN user_state u ON u.tt = tc.tt "
        "WHERE u.my_rating IS NOT NULL GROUP BY p.name HAVING COUNT(*) >= 2 "
        "ORDER BY media DESC, titulos DESC LIMIT 30").fetchall()
    joyas = c.execute(
        "SELECT t.title_es, t.original_title, t.year, u.my_rating, t.imdb_rating, "
        "(u.my_rating - t.imdb_rating) dif FROM titles t "
        "JOIN user_state u ON u.tt = t.tt "
        "WHERE u.my_rating IS NOT NULL AND t.imdb_rating IS NOT NULL "
        "AND (u.my_rating - t.imdb_rating) >= 1.5 "
        "ORDER BY dif DESC, u.my_rating DESC LIMIT 30").fetchall()
    decepciones = c.execute(
        "SELECT t.title_es, t.original_title, t.year, u.my_rating, t.imdb_rating, "
        "(t.imdb_rating - u.my_rating) dif FROM titles t "
        "JOIN user_state u ON u.tt = t.tt "
        "WHERE u.my_rating IS NOT NULL AND t.imdb_rating IS NOT NULL "
        "AND (t.imdb_rating - u.my_rating) >= 1.5 "
        "ORDER BY dif DESC LIMIT 30").fetchall()
    faltan = c.execute("SELECT COUNT(*) n FROM v_sin_enriquecer").fetchone()["n"]
    todas = c.execute(
        """SELECT t.title_es, t.original_title, t.title_type, t.year,
                  t.imdb_rating, u.my_rating,
                  (SELECT GROUP_CONCAT(genre, ', ') FROM title_genres g WHERE g.tt = t.tt) AS generos
           FROM titles t LEFT JOIN user_state u ON u.tt = t.tt
           ORDER BY t.title_es COLLATE NOCASE""").fetchall()
    c.close()

    e = html.escape
    kpis = (f'<div class="kpis">'
            f'<div class="kpi"><div class="n">{total}</div><div class="l">Títulos</div></div>'
            f'<div class="kpi"><div class="n">{valoradas}</div><div class="l">Valoradas por ti</div></div>'
            f'<div class="kpi"><div class="n">{pendientes}</div><div class="l">En seguimiento</div></div>'
            f'<div class="kpi"><div class="n">{media or "-"}</div><div class="l">Tu nota media</div></div>'
            f'<div class="kpi"><div class="n">{faltan}</div><div class="l">Sin enriquecer</div></div>'
            f'</div>')

    top_rows = "".join(
        fila_tabla([f'<span class="pill">{r["my_rating"]}</span>',
                    f'<span class="nw">{e(r["title_es"] or r["original_title"] or "")}'
                    f' <span style="color:var(--sub)">({r["year"] or "?"})</span></span>',
                    e(r["title_type"] or ""), str(r["imdb_rating"] or "-")])
        for r in top)
    max_g = max([r["titulos"] for r in generos] or [1])
    gen_rows = "".join(
        fila_tabla([e(r["genero"]), str(r["titulos"]),
                    f'<div class="bar"><i style="width:{100 * r["titulos"] // max_g}%"></i></div>',
                    str(r["nota_media"])])
        for r in generos)
    dir_rows = "".join(
        fila_tabla([e(r["director"]), str(r["titulos"]), str(r["nota_media"])])
        for r in directores) or fila_tabla(["Sin datos aún", "", ""])
    actor_rows = "".join(
        fila_tabla([e(r["actor"]), str(r["titulos"]), str(r["media"])])
        for r in actores) or fila_tabla(["Sin reparto suficiente aún", "", ""])
    joya_rows = "".join(
        fila_tabla([f'<span class="pill">{r["my_rating"]}</span>',
                    f'<span class="nw">{e(r["title_es"] or r["original_title"] or "")}'
                    f' <span style="color:var(--sub)">({r["year"] or "?"})</span></span>',
                    str(r["imdb_rating"]), f'+{round(r["dif"], 1)}'])
        for r in joyas) or fila_tabla(["Sin joyas con +1.5 sobre IMDb", "", "", ""])
    decep_rows = "".join(
        fila_tabla([f'<span class="pill">{r["my_rating"]}</span>',
                    f'<span class="nw">{e(r["title_es"] or r["original_title"] or "")}'
                    f' <span style="color:var(--sub)">({r["year"] or "?"})</span></span>',
                    str(r["imdb_rating"]), f'-{round(r["dif"], 1)}'])
        for r in decepciones) or fila_tabla(["Sin decepciones de -1.5 bajo IMDb", "", "", ""])
    todas_tr = []
    for r in todas:
        tit = e(r["title_es"] or r["original_title"] or "")
        clave = e(((r["title_es"] or r["original_title"] or "") + " " + (r["generos"] or "")).lower())
        celdas = [f'{tit}', e(r["title_type"] or ""), str(r["year"] or "-"),
                  mostrar_generos(r["generos"]), str(r["imdb_rating"] or "-"),
                  (f'<span class="pill">{r["my_rating"]}</span>'
                   if r["my_rating"] is not None else '<span class="np" title="No puntuado">NP</span>')]
        fila = fila_tabla(celdas, cls_first="t").replace("<tr>", f'<tr data-r="{clave}">', 1)
        todas_tr.append(fila)
    all_rows = "".join(todas_tr)
    ntotal = len(todas)
    pend_rows = "".join(
        fila_tabla([f'<span class="nw">{e(r["title_es"] or r["original_title"] or "")}'
                    f' <span style="color:var(--sub)">({r["year"] or "?"})</span></span>',
                    e(r["title_type"] or ""), str(r["imdb_rating"] or "-")],
                   cls_first="t")
        for r in pend)

    js = """<script>
(function () {
  const PASO = 15;
  document.querySelectorAll('table.paginada').forEach((tbl) => {
    const rows = Array.from(tbl.querySelectorAll('tbody tr'));
    if (rows.length <= PASO) return;
    let visibles = PASO;
    const wrap = document.createElement('div');
    wrap.className = 'more-wrap';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'more-btn';
    const info = document.createElement('div');
    info.className = 'count';
    const pintar = () => {
      rows.forEach((tr, i) => { tr.style.display = i < visibles ? '' : 'none'; });
      const restan = rows.length - visibles;
      if (restan <= 0) { btn.hidden = true; info.textContent = 'Mostrando ' + rows.length + ' de ' + rows.length; }
      else { btn.hidden = false; btn.textContent = 'Cargar 15 más (' + restan + ' restantes)'; info.textContent = 'Mostrando ' + visibles + ' de ' + rows.length; }
    };
    btn.addEventListener('click', () => { visibles += PASO; tbl.dataset.n = visibles; pintar(); });
    tbl.after(info);
    tbl.after(wrap);
    wrap.appendChild(btn);
    tbl.dataset.n = visibles;
    pintar();
  });
  const q = document.getElementById('q');
  const tblTodas = document.getElementById('tabla-todas');
  if (q && tblTodas) q.addEventListener('input', () => {
    const t = q.value.toLowerCase().trim();
    const rows = Array.from(tblTodas.querySelectorAll('tbody tr'));
    const section = tblTodas.closest('section');
    const wrap = section ? section.querySelector('.more-wrap') : null;
    const info = section ? section.querySelector('.count') : null;
    if (!t) {
      const n = parseInt(tblTodas.dataset.n || PASO, 10);
      rows.forEach((tr, i) => { tr.style.display = i < n ? '' : 'none'; });
      if (wrap) wrap.style.display = '';
      return;
    }
    let vistos = 0;
    rows.forEach((tr) => {
      const ok = (tr.dataset.r || '').includes(t);
      tr.style.display = ok ? '' : 'none';
      if (ok) vistos += 1;
    });
    if (wrap) wrap.style.display = 'none';
    if (info) info.textContent = vistos + ' resultados para "' + q.value + '"';
  });
})();
</script>"""

    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mi catálogo — stats</title><style>{CSS}</style></head><body><div class="wrap">
<header><h1>Mi catálogo</h1><p>{total} títulos de IMDb · {valoradas} valorados · {pendientes} en seguimiento</p></header>
{kpis}
<section><h2>Tus favoritas</h2><div class="hint">Ordenadas por tu nota. 15 visibles, carga 15 más.</div>
<table class="paginada"><thead><tr><th>Tu nota</th><th>Título</th><th>Tipo</th><th>IMDb</th></tr></thead><tbody>{top_rows}</tbody></table></section>
<div class="grid2">
<section><h2>Joyas que tú amas</h2><div class="hint">Tu nota supera a IMDb en 1.5+. 15 visibles, carga 15 más.</div>
<table class="paginada"><thead><tr><th>Tú</th><th>Título</th><th>IMDb</th><th>Dif</th></tr></thead><tbody>{joya_rows}</tbody></table></section>
<section><h2>Decepciones</h2><div class="hint">IMDb te supera en 1.5+. 15 visibles, carga 15 más.</div>
<table class="paginada"><thead><tr><th>Tú</th><th>Título</th><th>IMDb</th><th>Dif</th></tr></thead><tbody>{decep_rows}</tbody></table></section>
</div>
<div class="grid2">
<section><h2>Géneros que más te gustan</h2><div class="hint">Nota media de tus valoradas. 15 visibles, carga 15 más.</div>
<table class="paginada"><thead><tr><th>Género</th><th>Títulos</th><th></th><th>Media</th></tr></thead><tbody>{gen_rows}</tbody></table></section>
<section><h2>Directores frecuentes</h2><div class="hint">En tus títulos valorados. 15 visibles, carga 15 más.</div>
<table class="paginada"><thead><tr><th>Director</th><th>Títulos</th><th>Media</th></tr></thead><tbody>{dir_rows}</tbody></table></section>
</div>
<section><h2>Actores de confianza</h2><div class="hint">Tu nota media por actor (mínimo 2 títulos). 15 visibles, carga 15 más.</div>
<table class="paginada"><thead><tr><th>Actor</th><th>Títulos</th><th>Media</th></tr></thead><tbody>{actor_rows}</tbody></table></section>
<section id="lista"><h2>Lista completa</h2><div class="hint">Los {ntotal} títulos. Filtra sin recargar. 15 visibles, carga 15 más.</div>
<input class="search" id="q" type="search" placeholder="Filtra por título o género…" aria-label="Filtrar lista completa">
<table class="paginada" id="tabla-todas"><thead><tr><th>Título</th><th>Tipo</th><th>Año</th><th>Géneros</th><th>IMDb</th><th>Tu nota</th></tr></thead><tbody>{all_rows}</tbody></table></section>
<section><h2>En seguimiento</h2><div class="hint">Sin tu nota todavía. 15 visibles, carga 15 más.</div>
<table class="paginada"><thead><tr><th>Título</th><th>Tipo</th><th>IMDb</th></tr></thead><tbody>{pend_rows}</tbody></table></section>
<footer>Generado desde tu base local · auto-regenerable con scripts/auto_vista.py</footer>
</div>{js}</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH))
    ap.add_argument("--salida", default=str(ROOT / "preview" / "dashboard.html"))
    args = ap.parse_args()
    salida = Path(args.salida)
    salida.parent.mkdir(parents=True, exist_ok=True)
    salida.write_text(generar(Path(args.db)), encoding="utf-8")
    print(str(salida))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
