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
import json
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
.hdr { display: flex; gap: 16px; align-items: flex-end; justify-content: space-between; flex-wrap: wrap; }
.buscador-global { position: relative; min-width: 280px; flex: 0 1 340px; }
.buscador-global input { width: 100%; padding: 10px 14px; border: 1px solid var(--line);
border-radius: 999px; font-size: 14px; background: #fff; color: var(--ink); }
.resultados-global { position: absolute; top: calc(100% + 6px); left: 0; right: 0;
background: #fff; border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
box-shadow: 0 12px 32px rgba(0,0,0,.12); z-index: 30; }
.resultados-global[hidden] { display: none; }
.resultados-global button { display: flex; gap: 10px; align-items: center; width: 100%;
border: none; background: #fff; padding: 8px 10px; cursor: pointer; text-align: left; font-size: 14px; }
.resultados-global button[aria-selected="true"], .resultados-global button:hover { background: var(--bg); }
.resultados-global img { width: 34px; height: 50px; object-fit: cover; border-radius: 6px; background: var(--line); }
.resultados-global .rg-t { font-weight: 600; }
.resultados-global .rg-s { color: var(--sub); font-size: 12px; }
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex;
align-items: center; justify-content: center; padding: 20px; z-index: 50; }
.overlay[hidden] { display: none; }
.ficha { background: #fff; border-radius: 20px; max-width: 760px; width: 100%;
max-height: 88vh; overflow: auto; padding: 22px; position: relative; }
.ficha-cerrar { position: absolute; top: 12px; right: 12px; border: 1px solid var(--line);
background: #fff; border-radius: 999px; width: 32px; height: 32px; cursor: pointer; font-size: 16px; }
.ficha-grid { display: grid; grid-template-columns: 150px 1fr; gap: 18px; }
@media (max-width: 600px) { .ficha-grid { grid-template-columns: 1fr; } }
.ficha img.poster { width: 150px; border-radius: 12px; background: var(--line); }
.ficha h3 { font-size: 24px; letter-spacing: -0.01em; }
.ficha .meta { color: var(--sub); font-size: 13px; margin: 6px 0 12px; }
.ficha .sinopsis { font-size: 14px; line-height: 1.55; margin: 10px 0; }
.ficha .bloque { font-size: 13px; margin-top: 10px; }
.ficha .bloque b { display: block; font-size: 12px; text-transform: uppercase;
letter-spacing: 0.06em; color: var(--sub); margin-bottom: 4px; }
tr[data-tt] { cursor: pointer; }
footer { color: var(--sub); font-size: 12px; text-align: center; margin-top: 26px; }
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
    top_posters = c.execute(
        """SELECT t.tt, t.title_es, t.original_title, t.year, u.my_rating, t.poster_url
           FROM titles t JOIN user_state u ON u.tt = t.tt
           WHERE u.my_rating IS NOT NULL
           ORDER BY u.my_rating DESC, u.date_rated DESC
           LIMIT 10"""
    ).fetchall()
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
        """SELECT t.tt, t.title_es, t.original_title, t.title_type, t.year,
                  t.imdb_rating, u.my_rating,
                  (SELECT GROUP_CONCAT(genre, ', ') FROM title_genres g WHERE g.tt = t.tt) AS generos
           FROM titles t LEFT JOIN user_state u ON u.tt = t.tt
           ORDER BY t.title_es COLLATE NOCASE""").fetchall()
    fichas = c.execute(
        """SELECT t.tt, t.title_es, t.original_title, t.url, t.title_type, t.year,
                  t.imdb_rating, u.my_rating, t.synopsis, t.poster_url
           FROM titles t LEFT JOIN user_state u ON u.tt = t.tt""").fetchall()
    cast_rows = c.execute(
        """SELECT tc.tt, p.name, tc.character_name FROM title_cast tc
           JOIN people p ON p.id = tc.person_id
           ORDER BY tc.tt, tc.cast_order""").fetchall()
    director_rows = c.execute(
        """SELECT tc.tt, p.name FROM title_credits tc
           JOIN people p ON p.id = tc.person_id
           WHERE tc.role = 'director' ORDER BY tc.tt, p.name""").fetchall()
    pais_rows = c.execute(
        "SELECT tt, country_code FROM title_countries ORDER BY tt, country_code"
    ).fetchall()
    genero_rows = c.execute(
        "SELECT tt, genre FROM title_genres ORDER BY tt, genre"
    ).fetchall()
    c.close()

    e = html.escape
    kpis = (f'<div class="kpis">'
            f'<div class="kpi"><div class="n">{total}</div><div class="l">Títulos</div></div>'
            f'<div class="kpi"><div class="n">{valoradas}</div><div class="l">Valoradas por ti</div></div>'
            f'<div class="kpi"><div class="n">{pendientes}</div><div class="l">En seguimiento</div></div>'
            f'<div class="kpi"><div class="n">{media or "-"}</div><div class="l">Tu nota media</div></div>'
            f'<div class="kpi"><div class="n">{faltan}</div><div class="l">Sin enriquecer</div></div>'
            f'</div>')

    posters = "".join(_tarjeta_poster(r) for r in top_posters) or (
        '<p class="empty">Aún no has valorado nada.</p>')
    posters_html = (
        '<section class="poster-section" aria-labelledby="posters-title">'
        '<div class="section-head"><h2 id="posters-title">Tus favoritas, en cartel</h2>'
        '<span class="hint">Top 10 por tu nota. Pulsa una para abrir la ficha.</span></div>'
        f'<div class="poster-grid">{posters}</div></section>')

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
        fila = fila_tabla(celdas, cls_first="t").replace(
            "<tr>", f'<tr data-r="{clave}" data-tt="{e(r["tt"] if "tt" in r.keys() else "")}">', 1)
        todas_tr.append(fila)
    all_rows = "".join(todas_tr)
    ntotal = len(todas)
    cast_por_tt: dict[str, list[dict]] = {}
    for r in cast_rows:
        cast_por_tt.setdefault(r["tt"], []).append(
            {"name": r["name"], "character": r["character_name"] or ""})
    dir_por_tt: dict[str, list[str]] = {}
    for r in director_rows:
        dir_por_tt.setdefault(r["tt"], []).append(r["name"])
    pais_por_tt: dict[str, list[str]] = {}
    for r in pais_rows:
        pais_por_tt.setdefault(r["tt"], []).append(r["country_code"])
    gen_por_tt: dict[str, list[str]] = {}
    for r in genero_rows:
        gen_por_tt.setdefault(r["tt"], []).append(r["genre"])
    indice = []
    fichas_map: dict[str, dict] = {}
    for r in fichas:
        tt = r["tt"]
        titulo = r["title_es"] or r["original_title"] or tt
        indice.append({
            "tt": tt,
            "t": titulo,
            "o": r["original_title"] or "",
            "y": r["year"],
            "tipo": r["title_type"] or "",
            "nota": r["my_rating"],
            "imdb": r["imdb_rating"],
            "poster": r["poster_url"] or "",
            "d": ", ".join(dir_por_tt.get(tt, [])),
            "a": ", ".join(x["name"] for x in cast_por_tt.get(tt, [])[:8]),
            "g": ", ".join(gen_por_tt.get(tt, [])),
        })
        fichas_map[tt] = {
            "titulo": titulo,
            "original": r["original_title"] or "",
            "url": r["url"] or "",
            "tipo": r["title_type"] or "",
            "year": r["year"],
            "imdb": r["imdb_rating"],
            "nota": r["my_rating"],
            "sinopsis": r["synopsis"] or "",
            "poster": r["poster_url"] or "",
            "cast": cast_por_tt.get(tt, [])[:8],
            "directores": dir_por_tt.get(tt, []),
            "paises": pais_por_tt.get(tt, []),
            "generos": gen_por_tt.get(tt, []),
        }
    indice_json = json.dumps(indice, ensure_ascii=False).replace("</", "<\\/")
    fichas_json = json.dumps(fichas_map, ensure_ascii=False).replace("</", "<\\/")
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
    info.setAttribute("aria-live", "polite");
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
  // Buscador global + ficha overlay.
  const indice = JSON.parse(document.getElementById('indice-data').textContent || '[]');
  const fichas = JSON.parse(document.getElementById('fichas-data').textContent || '{}');
  const bg = document.getElementById('buscador-global');
  const rg = document.getElementById('resultados-global');
  const overlay = document.getElementById('overlay');
  const contenido = document.getElementById('ficha-contenido');
  const cerrarBtn = document.getElementById('ficha-cerrar');
  let sel = -1;
  let actual = [];
  let focoPrevio = null;
  const cerrarFicha = () => {
    if (overlay.hidden) return;
    overlay.hidden = true;
    contenido.innerHTML = '';
    document.body.style.overflow = '';
    if (focoPrevio && typeof focoPrevio.focus === 'function') focoPrevio.focus();
  };
  const abrirFicha = (tt) => {
    const f = fichas[tt];
    if (!f) return;
    contenido.innerHTML = '';
    const grid = document.createElement('div');
    grid.className = 'ficha-grid';
    if (f.poster) {
      const img = document.createElement('img');
      img.className = 'poster';
      img.src = f.poster;
      img.alt = 'Póster de ' + f.titulo;
      img.loading = 'lazy';
      grid.appendChild(img);
    }
    const lado = document.createElement('div');
    const h = document.createElement('h3');
    h.id = 'ficha-titulo';
    h.textContent = f.titulo;
    lado.appendChild(h);
    const meta = document.createElement('div');
    meta.className = 'meta';
    const partes = [f.year || '?', f.tipo || '',
      (f.nota != null ? 'Tu nota: ' + f.nota : 'Sin valorar'),
      (f.imdb != null ? 'IMDb: ' + f.imdb : '')].filter(Boolean);
    meta.textContent = partes.join(' · ');
    lado.appendChild(meta);
    const pasa = (titulo, texto) => {
      if (!texto) return;
      const b = document.createElement('div');
      b.className = 'bloque';
      const tt2 = document.createElement('b');
      tt2.textContent = titulo;
      b.appendChild(tt2);
      const p = document.createElement('div');
      p.textContent = texto;
      if (titulo === 'Sinopsis') p.className = 'sinopsis';
      b.appendChild(p);
      lado.appendChild(b);
    };
    pasa('Sinopsis', f.sinopsis || 'Sin sinopsis disponible todavía.');
    pasa('Reparto', (f.cast || []).map((m) => m.character ? m.name + ' como ' + m.character : m.name).join(', '));
    pasa('Dirección', (f.directores || []).join(', '));
    pasa('Géneros', (f.generos || []).join(', '));
    pasa('Países', (f.paises || []).join(', '));
    if (f.url) {
      const b = document.createElement('div');
      b.className = 'bloque';
      const a = document.createElement('a');
      a.href = f.url;
      a.target = '_blank';
      a.rel = 'noopener';
      a.textContent = 'Ver en IMDb';
      b.appendChild(a);
      lado.appendChild(b);
    }
    grid.appendChild(lado);
    contenido.appendChild(grid);
    focoPrevio = document.activeElement;
    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    cerrarBtn.focus();
  };
  window.abrirFicha = abrirFicha;
  document.querySelectorAll('.poster-card').forEach((card) => {
    card.addEventListener('click', () => {
      const tt = card.dataset.tt;
      if (tt) abrirFicha(tt);
    });
  });
  if (cerrarBtn) cerrarBtn.addEventListener('click', cerrarFicha);
  overlay.addEventListener('click', (ev) => { if (ev.target === overlay) cerrarFicha(); });
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
  document.addEventListener('keydown', (ev) => { if (ev.key === 'Escape') { cerrarFicha(); if (rg) { rg.hidden = true; if (bg) bg.setAttribute('aria-expanded', 'false'); } } });
  const pintarGlobal = () => {
    rg.innerHTML = '';
    sel = -1;
    if (!bg.value.trim()) { rg.hidden = true; bg.setAttribute('aria-expanded', 'false'); return; }
    const t = bg.value.toLowerCase().trim();
    actual = indice.filter((x) => ((x.t || '') + ' ' + (x.o || '') + ' ' + (x.d || '') + ' ' + (x.a || '') + ' ' + (x.g || '')).toLowerCase().includes(t)).slice(0, 8);
    if (!actual.length) { rg.hidden = true; bg.setAttribute('aria-expanded', 'false'); return; }
    actual.forEach((x, i) => {
      const b = document.createElement('button');
      b.type = 'button';
      b.setAttribute('role', 'option');
      b.dataset.tt = x.tt;
      if (x.poster) {
        const img = document.createElement('img');
        img.src = x.poster;
        img.alt = '';
        img.loading = 'lazy';
        b.appendChild(img);
      }
      const tx = document.createElement('span');
      const t1 = document.createElement('div');
      t1.className = 'rg-t';
      t1.textContent = x.t;
      tx.appendChild(t1);
      const t2 = document.createElement('div');
      t2.className = 'rg-s';
      t2.textContent = [x.y || '?', x.tipo || '', (x.nota != null ? 'Tu nota ' + x.nota : '')].filter(Boolean).join(' · ');
      tx.appendChild(t2);
      b.appendChild(tx);
      b.addEventListener('click', () => { rg.hidden = true; bg.setAttribute('aria-expanded', 'false'); abrirFicha(x.tt); });
      rg.appendChild(b);
    });
    rg.hidden = false;
    bg.setAttribute('aria-expanded', 'true');
  };
  if (bg && rg) {
    bg.addEventListener('input', pintarGlobal);
    bg.addEventListener('keydown', (ev) => {
      const btns = Array.from(rg.querySelectorAll('button'));
      if (ev.key === 'ArrowDown' || ev.key === 'ArrowUp') {
        ev.preventDefault();
        sel = ev.key === 'ArrowDown' ? Math.min(sel + 1, btns.length - 1) : Math.max(sel - 1, 0);
        btns.forEach((b, i) => b.setAttribute('aria-selected', i === sel ? 'true' : 'false'));
        if (btns[sel]) btns[sel].scrollIntoView({ block: 'nearest' });
      } else if (ev.key === 'Enter' && sel >= 0 && btns[sel]) {
        ev.preventDefault();
        const tt = btns[sel].dataset.tt;
        rg.hidden = true;
        abrirFicha(tt);
      }
    });
    document.addEventListener('click', (ev) => { if (!rg.hidden && !ev.target.closest('.buscador-global')) { rg.hidden = true; bg.setAttribute('aria-expanded', 'false'); } });
  }
  if (tblTodas) tblTodas.addEventListener('click', (ev) => {
    const tr = ev.target.closest('tr[data-tt]');
    if (tr && tr.dataset.tt) abrirFicha(tr.dataset.tt);
  });
})();
</script>"""

    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Mi catálogo — stats</title><style>{CSS}</style></head><body><div class="wrap">
<header><div class="hdr"><div><h1>Mi catálogo</h1><p>{total} títulos de IMDb · {valoradas} valorados · {pendientes} en seguimiento</p></div>
<div class="buscador-global"><input id="buscador-global" type="search" placeholder="Buscar título, director, actor…" aria-label="Buscador global" autocomplete="off" role="combobox" aria-haspopup="listbox" aria-autocomplete="list" aria-expanded="false" aria-controls="resultados-global">
<div class="resultados-global" id="resultados-global" role="listbox" hidden></div></div></div></header>
{kpis}
{posters_html}
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
<div class="overlay" id="overlay" hidden><div class="ficha" role="dialog" aria-modal="true" aria-labelledby="ficha-titulo">
<button class="ficha-cerrar" id="ficha-cerrar" aria-label="Cerrar ficha">×</button>
<div id="ficha-contenido"></div></div></div>
<footer>Generado desde tu base local · auto-regenerable con scripts/auto_vista.py</footer>
<script type="application/json" id="indice-data">{indice_json}</script>
<script type="application/json" id="fichas-data">{fichas_json}</script>
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
