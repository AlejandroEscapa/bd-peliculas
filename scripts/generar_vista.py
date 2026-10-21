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
from src.motor import recomendar, resumen_perfil

CSS = """
:root { --bg: #f5f5f7; --card: #ffffff; --ink: #1d1d1f; --sub: #6e6e73;
--accent: #0071e3; --line: #e8e8ed; --radius: clamp(14px, 2vw, 18px);
--sp: clamp(16px, 4vw, 40px); --gap: clamp(10px, 2vw, 16px); }
* { box-sizing: border-box; margin: 0; }
[hidden] { display: none !important; }
html { -webkit-text-size-adjust: 100%; }
body { font-family: -apple-system, 'SF Pro Text', 'Segoe UI', Roboto, sans-serif;
background: var(--bg); color: var(--ink); overflow-wrap: break-word;
padding: var(--sp) clamp(16px, 4vw, 24px) calc(64px + env(safe-area-inset-bottom)); }
.wrap { max-width: 1120px; margin: 0 auto; }
header h1 { font-size: clamp(28px, 6vw, 40px); letter-spacing: -0.02em; }
header p { color: var(--sub); margin-top: 6px; font-size: clamp(14px, 2.5vw, 17px); }
.hdr { display: flex; flex-direction: column; gap: 14px; align-items: stretch; }
.buscador-global { position: relative; min-width: 0; width: 100%; }
.buscador-global input { width: 100%; min-height: 44px; padding: 11px 14px;
border: 1px solid var(--line); border-radius: 999px; font-size: 14px;
background: #fff; color: var(--ink); }
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
.kpis { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
gap: 10px; margin: 24px 0; }
.kpi { position: relative; min-width: 0; background: var(--card);
border-radius: var(--radius); padding: 13px 40px 13px 13px;
display: flex; flex-direction: column; justify-content: space-between; }
.kpi .n { font-size: clamp(19px, 2.9vw, 24px); font-weight: 700; letter-spacing: -0.02em;
white-space: nowrap; font-variant-numeric: tabular-nums; line-height: 1.15; }
.kpi .l { color: var(--sub); font-size: 11px; margin-top: 6px; line-height: 1.3;
min-height: 2.6em; }
.kpi .filtro-wrap { position: absolute; top: 2px; right: 2px; }
section { position: relative; background: var(--card); border-radius: var(--radius);
padding: 16px; margin-bottom: 14px; container-type: inline-size; }
section h2 { font-size: clamp(18px, 3vw, 21px); letter-spacing: -0.01em;
margin-bottom: 4px; }
section .hint { color: var(--sub); font-size: 13px; margin-bottom: 14px; }
.section-head { display: flex; align-items: flex-start; justify-content: space-between;
gap: 10px; margin-bottom: 14px; }
.section-head > div:first-child { min-width: 0; }
.section-head .hint { margin-bottom: 0; }
table { width: 100%; border-collapse: collapse; font-size: 14px;
table-layout: fixed; }
th { text-align: left; color: var(--sub); font-weight: 600; font-size: 11px;
text-transform: uppercase; letter-spacing: 0.07em; padding: 10px 12px;
border-bottom: 1px solid var(--line); vertical-align: bottom; }
td { padding: 11px 12px; border-bottom: 1px solid var(--line);
vertical-align: top; }
tr:last-child td { border-bottom: none; }
tbody tr[data-tt]:hover td { background: var(--bg); }
/* Tipos de columna: una cifra vive a la derecha, con cifras de ancho fijo
   (tabular-nums), y nunca se parte. */
.c-num { text-align: right; white-space: nowrap;
font-variant-numeric: tabular-nums; }
.c-titulo { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.c-razon { color: var(--sub); font-size: 13px; line-height: 1.5; }
.c-encaje { text-align: left; }
.motivo { color: var(--ink); }
.motivo-sec { display: block; color: var(--sub); font-size: 12px;
line-height: 1.45; }
.motivo-sec::before { content: "— "; color: var(--line); }
.motivo-vacio { color: var(--sub); }
.pill { display: inline-block; background: var(--accent); color: #fff;
border-radius: 999px; padding: 2px 10px; font-weight: 600; font-size: 13px; }
.bar { height: 8px; border-radius: 99px; background: var(--line); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent); border-radius: 99px; }
.grid2 { display: grid; grid-template-columns: 1fr; gap: var(--gap); }
a { color: var(--accent); text-decoration: none; }
td.t { white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.nw { white-space: nowrap; }
.np { color: var(--sub); font-weight: 700; font-size: 12px; letter-spacing: 0.1em; }
.more-wrap { display: flex; justify-content: center; padding-top: 14px; }
.more-btn { appearance: none; border: 1px solid var(--accent); background: #fff;
color: var(--accent); border-radius: 999px; min-height: 44px; padding: 8px 18px;
font-weight: 600; font-size: 13px; cursor: pointer; transition: transform .15s ease, background .15s ease; }
.more-btn:hover { background: var(--accent); color: #fff; }
.more-btn:active { transform: translateY(1px) scale(.98); }
.more-btn[hidden] { display: none; }
.count { color: var(--sub); font-size: 12px; text-align: center; margin-top: 8px; }
.search { width: 100%; min-height: 44px; padding: 11px 14px; border: 1px solid var(--line);
border-radius: 999px; font-size: 14px; margin-bottom: 12px; background: #fff; color: var(--ink); }
.overlay { position: fixed; inset: 0; background: rgba(0,0,0,.45); display: flex;
align-items: center; justify-content: center; padding: 20px; z-index: 50; }
.overlay[hidden] { display: none; }
.ficha { background: #fff; border-radius: 20px; max-width: 760px; width: 100%;
max-height: 88vh; overflow: auto; padding: 22px; position: relative; }
.ficha-cerrar { position: absolute; top: 12px; right: 12px; border: 1px solid var(--line);
background: #fff; border-radius: 999px; width: 44px; height: 44px; cursor: pointer; font-size: 18px; }
.ficha-cabecera { display: grid; grid-template-columns: 150px 1fr; gap: 18px; }
.ficha-lateral { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; }
.ficha img.poster { width: 100%; aspect-ratio: 2 / 3; object-fit: cover;
border-radius: 12px; background: var(--line); }
.ficha-lateral .poster-fallback { width: 100%; aspect-ratio: 2 / 3; border-radius: 12px;
font-size: 28px; }
.ficha-lateral .pill { font-size: 13px; }
.ficha-lateral a { font-size: 13px; font-weight: 600; }
.ficha h3 { font-size: clamp(20px, 4vw, 24px); letter-spacing: -0.01em; }
.ficha .meta { color: var(--sub); font-size: 13px; margin: 6px 0 12px; }
.ficha .sinopsis { font-size: 14px; line-height: 1.55; margin: 10px 0 0; }
.ficha .bloque { font-size: 13px; margin-top: 10px; }
.ficha .bloque b, .ficha-sinopsis b { display: block; font-size: 12px;
text-transform: uppercase; letter-spacing: 0.06em; color: var(--sub);
margin-bottom: 4px; }
.ficha-sinopsis { margin-top: 18px; padding-top: 14px; border-top: 1px solid var(--line); }
.ficha-sinopsis .leer-mas { display: none; }
.saga { display: grid; gap: 6px; }
.saga-nombre { font-size: 13px; color: var(--sub); }
.saga-item { display: flex; justify-content: space-between; gap: 12px; align-items: baseline;
width: 100%; text-align: left; padding: 8px 10px; border: 1px solid var(--line);
border-radius: 10px; background: var(--bg); color: var(--ink); cursor: pointer;
min-height: 44px; }
.saga-item:hover { border-color: var(--accent); }
.saga-item:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.saga-titulo { font-weight: 600; }
.saga-meta { color: var(--sub); font-size: 12px; white-space: nowrap; }
.tabla-tarjeta { table-layout: auto; }
.tabla-tarjeta thead { display: none; }
.tabla-tarjeta tr { display: block; border: 1px solid var(--line);
border-radius: 14px; padding: 14px 16px; margin-bottom: 8px; background: var(--bg); }
.tabla-tarjeta td { display: block; border: 0; padding: 0; }
.tabla-tarjeta .celda-tarjeta { display: block; }
.tarjeta-titulo { font-size: 16px; font-weight: 600; letter-spacing: -0.01em;
margin-bottom: 10px; }
.tarjeta-titulo .nw { white-space: normal; }
.tarjeta-datos { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr));
gap: 4px 12px; }
.dato-label { display: block; font-size: 10.5px; text-transform: uppercase;
letter-spacing: 0.07em; color: var(--sub); margin-bottom: 2px; }
.dato-valor { display: block; font-size: 15px; font-variant-numeric: tabular-nums; }
.dato-valor .pill { font-size: 13px; }
.encaje { display: flex; align-items: center; gap: 8px; }
.encaje .bar { flex: 1 1 auto; min-width: 36px; }
.encaje .n { color: var(--sub); font-size: 12px; font-variant-numeric: tabular-nums;
white-space: nowrap; }
.perfil-caja { display: grid; gap: 8px; align-content: start; }
.perfil-caja b { font-size: 13px; }
.perfil-alto-item, .perfil-bajo-item { display: grid;
grid-template-columns: minmax(0, 1fr) 90px 42px; gap: 10px; align-items: center;
font-size: 13px; }
.perfil-alto-nombre, .perfil-bajo-nombre { display: grid; min-width: 0; }
.perfil-alto-faceta, .perfil-bajo-faceta { color: var(--sub); font-size: 11px; }
.perfil-alto-barra, .perfil-bajo-barra { height: 8px; border-radius: 99px;
background: var(--line); overflow: hidden; }
.perfil-alto-barra i { display: block; height: 100%; background: var(--accent);
border-radius: 99px; }
.perfil-bajo-barra i { display: block; height: 100%; background: var(--sub);
border-radius: 99px; opacity: .55; }
.perfil-alto-valor, .perfil-bajo-valor { text-align: right;
font-variant-numeric: tabular-nums; font-size: 12px; color: var(--sub); }
tr[data-tt] { cursor: pointer; }
footer { color: var(--sub); font-size: 12px; text-align: center; margin-top: 26px; }
.poster-section { padding: 16px; }
.poster-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px; }
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
.filtro-wrap { position: relative; flex: 0 0 auto; }
.filtro-btn { display: inline-flex; align-items: center; justify-content: center;
width: 44px; height: 44px; padding: 0; position: relative; border: 1px solid var(--line);
background: #fff; color: var(--ink); border-radius: 999px; cursor: pointer; }
.kpi .filtro-btn { width: 32px; height: 32px; border-color: transparent;
background: transparent; }
.kpi .filtro-btn:hover { background: var(--bg); }
.kpi .filtro-btn svg { width: 15px; height: 15px; }
.filtro-btn:hover { background: var(--bg); }
.filtro-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.filtro-btn[disabled] { opacity: .4; cursor: not-allowed; }
.filtro-btn svg { width: 18px; height: 18px; }
.filtro-badge { position: absolute; top: -5px; right: -5px; min-width: 18px; height: 18px;
padding: 0 5px; border-radius: 999px; background: var(--accent); color: #fff;
font-size: 11px; font-weight: 700; display: flex; align-items: center; justify-content: center; }
.filtro-badge[hidden] { display: none; }
.filtro-panel { position: absolute; top: calc(100% + 8px); right: 0;
width: min(340px, calc(100vw - 40px)); max-height: min(70dvh, 520px); overflow: auto;
background: #fff; border: 1px solid var(--line); border-radius: 16px;
box-shadow: 0 18px 40px rgba(0,0,0,.16); padding: 14px; z-index: 40; }
.filtro-panel[hidden] { display: none; }
.filtro-panel h3 { font-size: 15px; margin-bottom: 8px; }
.filtro-grupo { border-top: 1px solid var(--line); padding: 10px 0; }
.filtro-grupo:first-of-type { border-top: 0; }
.filtro-grupo > strong { display: block; font-size: 11px; text-transform: uppercase;
letter-spacing: 0.06em; color: var(--sub); margin-bottom: 4px; }
.filtro-opcion { display: flex; align-items: center; gap: 10px; min-height: 44px;
font-size: 14px; cursor: pointer; }
.filtro-opcion input { width: 18px; height: 18px; accent-color: var(--accent); }
.filtro-select { width: 100%; min-height: 44px; padding: 8px 12px; border: 1px solid var(--line);
border-radius: 10px; background: #fff; color: var(--ink); font-size: 14px; }
.filtro-acciones { display: flex; gap: 8px; justify-content: space-between;
margin-top: 8px; padding-top: 10px; border-top: 1px solid var(--line); }
.filtro-limpiar, .filtro-cerrar { min-height: 44px; padding: 8px 14px; border-radius: 999px;
font-size: 13px; font-weight: 600; cursor: pointer; }
.filtro-limpiar { border: 0; background: var(--bg); color: var(--ink); }
.filtro-cerrar { border: 1px solid var(--accent); background: #fff; color: var(--accent); }
.chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px; }
.chips[hidden] { display: none; }
.chip { display: inline-flex; align-items: center; gap: 4px; min-height: 32px;
padding: 4px 10px; border-radius: 999px; border: 1px solid var(--line);
background: var(--bg); color: var(--ink); font-size: 12px; cursor: pointer; }
.chip:hover { border-color: var(--accent); color: var(--accent); }
.leer-mas { display: none; margin-top: 8px; border: 0; background: none;
color: var(--accent); font-size: 13px; font-weight: 600; cursor: pointer; min-height: 44px; }
.ancho-completo { width: 100%; }
@container (max-width: 640px) {
  .tabla-cards thead { display: none; }
  .tabla-cards, .tabla-cards tbody, .tabla-cards tr, .tabla-cards td { display: block; width: 100%; }
  .tabla-cards tr { border: 1px solid var(--line); border-radius: 14px; padding: 12px; margin-bottom: 10px; }
  .tabla-cards td { display: flex; justify-content: space-between; gap: 12px;
    border: 0; padding: 3px 0; }
  .tabla-cards td::before { content: attr(data-label); color: var(--sub);
    font-size: 12px; font-weight: 500; flex: 0 0 auto; }
  .tabla-cards td.t { display: block; font-size: 16px; font-weight: 600;
    white-space: normal; overflow: visible; text-overflow: clip; max-width: none; padding-bottom: 6px; }
  .tabla-cards td.t::before { display: none; }
  .tabla-cards .nw { white-space: normal; }
  .tabla-cards .bar { flex: 0 0 45%; }
  .tabla-cards td.c-num { text-align: right; }
  .tabla-cards td.c-num::before { margin-right: auto; }
  .tabla-cards { table-layout: auto; }
  .tabla-cards td.c-razon { display: block; }
  .tabla-cards td.c-razon::before { display: block; margin-bottom: 4px; }
  .tabla-cards td.c-razon .motivo-sec { margin-top: 2px; }
}
@media (max-width: 640px) {
  .tabla-cards thead { display: none; }
  .tabla-cards, .tabla-cards tbody, .tabla-cards tr, .tabla-cards td { display: block; width: 100%; }
  .tabla-cards tr { border: 1px solid var(--line); border-radius: 14px; padding: 12px; margin-bottom: 10px; }
  .tabla-cards td { display: flex; justify-content: space-between; gap: 12px; border: 0; padding: 3px 0; }
  .tabla-cards td::before { content: attr(data-label); color: var(--sub); font-size: 12px; font-weight: 500; }
  .tabla-cards td.t { display: block; font-size: 16px; font-weight: 600; white-space: normal;
    overflow: visible; text-overflow: clip; max-width: none; padding-bottom: 6px; }
  .tabla-cards td.t::before { display: none; }
  .tabla-cards .nw { white-space: normal; }
  .tabla-cards .bar { flex: 0 0 45%; }
  .tabla-cards { table-layout: auto; }
  .tabla-cards td.c-razon { display: block; }
  .tabla-cards td.c-razon::before { display: block; margin-bottom: 4px; }
  .tabla-cards td.c-razon .motivo-sec { margin-top: 2px; }
  .filtro-panel { position: fixed; left: 12px; right: 12px; bottom: calc(12px + env(safe-area-inset-bottom));
    top: auto; width: auto; max-height: 60dvh; }
  .overlay { padding: 0; }
  .ficha { width: 100%; height: 100dvh; max-height: none; border-radius: 0; }
  .ficha-cabecera { grid-template-columns: 96px 1fr; gap: 14px; }
  .ficha .sinopsis.plegada { display: -webkit-box; -webkit-box-orient: vertical;
    -webkit-line-clamp: 4; overflow: hidden; }
  .ficha-sinopsis .leer-mas { display: inline-flex; align-items: center; }
  .leer-mas { display: inline-flex; align-items: center; }
}
@media (min-width: 480px) { .poster-grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
@media (min-width: 640px) {
  .kpis { grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
  section, .poster-section { padding: 22px; }
  .poster-grid { grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
}
@media (min-width: 900px) {
  .kpis { grid-template-columns: repeat(5, minmax(0, 1fr)); }
  .grid2 { grid-template-columns: 1fr 1fr; }
  .hdr { flex-direction: row; align-items: flex-end; justify-content: space-between; }
  .buscador-global { width: auto; flex: 0 1 340px; }
  .poster-grid { grid-template-columns: repeat(5, minmax(0, 1fr)); }
}
@media (min-width: 1200px) {
  .kpis { grid-template-columns: repeat(7, minmax(0, 1fr)); }
}
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { transition: none !important; animation: none !important; }
}
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


ETIQUETAS_TABLA = {
    "top": ["Tu nota", "Título", "Tipo", "IMDb"],
    "joyas": ["Tú", "Título", "IMDb", "Diferencia"],
    "decepciones": ["Tú", "Título", "IMDb", "Diferencia"],
    "generos": ["Género", "Títulos", "Media"],
    "directores": ["Director", "Títulos", "Media"],
    "actores": ["Actor", "Títulos", "Media"],
    "decadas": ["Década", "Títulos", "Media IMDb"],
    "para-ti": ["Título", "Año", "IMDb", "Encaje", "Por qué"],
    "lista": ["Título", "Tipo", "Año", "Géneros", "IMDb", "Tu nota"],
    "seguimiento": ["Título", "Tipo", "IMDb"],
}


def fila_tabla(celdas: list[str], cls_first: str | None = None,
              etiquetas: list[str] | None = None,
              clases: list[str] | None = None) -> str:
    """Fila con etiquetas por celda para el modo tarjeta en móvil.

    `clases` da el tipo de cada columna (c-num, c-titulo, c-razon...): es lo
    que alinea los números a la derecha y evita que un "2004" se parta en dos
    líneas por un contenedor estrecho.
    """
    partes = []
    for i, celda in enumerate(celdas):
        attrs = []
        tipos = []
        if i == 0 and cls_first:
            tipos.append(cls_first)
        if clases and i < len(clases) and clases[i]:
            tipos.append(clases[i])
        if tipos:
            attrs.append(f'class="{" ".join(tipos)}"')
        if etiquetas and i < len(etiquetas):
            attrs.append(f'data-label="{html.escape(etiquetas[i], quote=True)}"')
        sufijo = (" " + " ".join(attrs)) if attrs else ""
        partes.append(f"<td{sufijo}>{celda}</td>")
    return "<tr>" + "".join(partes) + "</tr>"


ICONO_FILTRO = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" '
    'aria-hidden="true" focusable="false">'
    '<path d="M4 5h16l-6.5 7.5V19l-3 1.5v-8L4 5z"/></svg>')


def boton_filtro(id_seccion: str, etiqueta: str, disabled: bool = False) -> str:
    """Botón Apple-style y panel vacío que rellena el motor de filtros."""
    id_html = html.escape(id_seccion, quote=True)
    etiqueta_html = html.escape(etiqueta, quote=True)
    deshabilitado = " disabled" if disabled else ""
    return (
        '<div class="filtro-wrap">'
        f'<button type="button" class="filtro-btn" data-filtro="{id_html}" '
        f'aria-label="Filtrar {etiqueta_html}" aria-haspopup="dialog" '
        f'aria-expanded="false" aria-controls="filtro-{id_html}"{deshabilitado}>'
        f'{ICONO_FILTRO}<span class="filtro-badge" hidden></span></button>'
        f'<div class="filtro-panel" id="filtro-{id_html}" role="dialog" '
        f'aria-label="Filtros de {etiqueta_html}" hidden></div></div>')


def cabecera_simple(id_seccion: str, titulo: str, hint: str) -> str:
    """Cabecera de sección sin filtros: es información, no un control."""
    id_html = html.escape(id_seccion, quote=True)
    return (
        '<div class="section-head"><div>'
        f'<h2 id="titulo-{id_html}" tabindex="-1">{html.escape(titulo)}</h2>'
        f'<p class="hint">{html.escape(hint)}</p></div></div>')


def cabecera_seccion(id_seccion: str, titulo: str, hint: str,
                    disabled: bool = False) -> str:
    """Cabecera con título, pista, botón de filtro y chips activos."""
    id_html = html.escape(id_seccion, quote=True)
    titulo_html = html.escape(titulo)
    return (
        '<div class="section-head"><div>'
        f'<h2 id="titulo-{id_html}" tabindex="-1">{titulo_html}</h2>'
        f'<p class="hint">{html.escape(hint)}</p></div>'
        f'{boton_filtro(id_seccion, titulo, disabled)}</div>'
        f'<div class="chips" id="chips-{id_html}" aria-live="polite" hidden></div>')


def tarjeta_kpi(clave: str, valor: str, etiqueta: str,
                filtrable: bool = True) -> str:
    """KPI con botón de preset; el preset se aplica en Lista completa.

    Los KPIs que son un promedio puro (tu nota media, exigencia) no tienen
    equivalencia en una faceta: su botón sale deshabilitado.
    """
    id_html = html.escape(clave, quote=True)
    etiqueta_html = html.escape(etiqueta)
    deshabilitado = "" if filtrable else " disabled"
    return (
        f'<div class="kpi" data-kpi="{id_html}">'
        f'<div class="n">{valor}</div><div class="l">{etiqueta_html}</div>'
        '<div class="filtro-wrap">'
        f'<button type="button" class="filtro-btn" data-kpi-filtro="{id_html}" '
        f'aria-label="Filtrar {etiqueta_html}"{deshabilitado}>'
        f'{ICONO_FILTRO}</button></div></div>')


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
    exigencia = c.execute(
        "SELECT ROUND(AVG(u.my_rating - t.imdb_rating), 2) e "
        "FROM titles t "
        "JOIN user_state u ON u.tt = t.tt "
        "WHERE u.my_rating IS NOT NULL "
        "AND t.imdb_rating IS NOT NULL"
    ).fetchone()["e"]
    enr_total = c.execute("SELECT COUNT(*) n FROM titles").fetchone()["n"]
    enr_hechos = c.execute(
        "SELECT COUNT(*) n FROM titles t "
        "WHERE t.synopsis IS NOT NULL "
        "AND t.poster_url IS NOT NULL "
        "AND EXISTS (SELECT 1 FROM title_cast c WHERE c.tt = t.tt)"
    ).fetchone()["n"]
    decadas = c.execute(
        "SELECT (t.year / 10) * 10 AS decada, COUNT(*) AS titulos, "
        "ROUND(AVG(t.imdb_rating), 2) AS media "
        "FROM titles t "
        "WHERE t.year IS NOT NULL "
        "GROUP BY decada "
        "ORDER BY decada"
    ).fetchall()
    todas = c.execute(
        """SELECT t.tt, t.title_es, t.original_title, t.title_type, t.year,
                  t.imdb_rating, u.my_rating,
                  (SELECT GROUP_CONCAT(genre, ', ') FROM title_genres g WHERE g.tt = t.tt) AS generos
           FROM titles t LEFT JOIN user_state u ON u.tt = t.tt
           ORDER BY t.title_es COLLATE NOCASE""").fetchall()
    fichas = c.execute(
        """SELECT t.tt, t.title_es, t.original_title, t.url, t.title_type, t.year,
                  t.imdb_rating, u.my_rating, t.synopsis, t.poster_url,
                  t.runtime_min_csv, t.runtime_min_exact, u.date_rated,
                  u.watch_status
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
    coleccion_rows = c.execute(
        """SELECT c.collection_id, c.collection_name, c.tt,
                  COALESCE(t.title_es, t.original_title, '') AS titulo,
                  t.year, u.my_rating
           FROM title_collections c
           JOIN titles t ON t.tt = c.tt
           LEFT JOIN user_state u ON u.tt = c.tt
           WHERE c.collection_id IS NOT NULL
           ORDER BY c.collection_id, t.year, t.tt""").fetchall()
    # El motor calcula la cola de pendientes recomendada (con su porqué).
    recomendaciones = recomendar(c)
    perfil_resumen = resumen_perfil(c)
    c.close()

    e = html.escape
    kpis = ('<div class="kpis">'
            + tarjeta_kpi("total", str(total), "Títulos")
            + tarjeta_kpi("valoradas", str(valoradas), "Valoradas por ti")
            + tarjeta_kpi("pendientes", str(pendientes), "En seguimiento")
            + tarjeta_kpi("media", str(media or "-"), "Tu nota media",
                          filtrable=False)
            + tarjeta_kpi("faltan", str(faltan), "Sin enriquecer")
            + tarjeta_kpi("exigencia",
                          str(exigencia) if exigencia is not None else "-",
                          "Exigencia (tú − IMDb)", filtrable=False)
            + tarjeta_kpi("enriquecidos", f"{enr_hechos}/{enr_total}",
                          "Enriquecidos")
            + '</div>')
    posters_head = cabecera_seccion(
        "posters", "Tus favoritas, en cartel",
        "Top 10 por tu nota. Pulsa una para abrir la ficha.")
    top_head = cabecera_seccion(
        "top", "Tus favoritas", "Ordenadas por tu nota. 15 visibles, carga 15 más.")
    joyas_head = cabecera_seccion(
        "joyas", "Joyas que tú amas",
        "Tu nota supera a IMDb en 1.5+. 15 visibles, carga 15 más.")
    decep_head = cabecera_seccion(
        "decepciones", "Decepciones",
        "IMDb te supera en 1.5+. 15 visibles, carga 15 más.")
    generos_head = cabecera_simple(
        "generos", "Géneros que más te gustan",
        "Nota media de tus valoradas. 15 visibles, carga 15 más.")
    directores_head = cabecera_simple(
        "directores", "Directores frecuentes",
        "En tus títulos valorados. 15 visibles, carga 15 más.")
    actores_head = cabecera_simple(
        "actores", "Actores de confianza",
        "Tu nota media por actor (mínimo 2 títulos). 15 visibles, carga 15 más.")
    decadas_head = cabecera_simple(
        "decadas", "Notas por década",
        "Títulos y nota media IMDb por década.")
    lista_head = cabecera_seccion(
        "lista", "Lista completa",
        f"Los {len(todas)} títulos. Filtra sin recargar. 15 visibles, carga 15 más.")
    seguimiento_head = cabecera_seccion(
        "seguimiento", "En seguimiento",
        "Sin tu nota todavía. 15 visibles, carga 15 más.")

    posters = "".join(_tarjeta_poster(r) for r in top_posters) or (
        '<p class="empty">Aún no has valorado nada.</p>')
    posters_html = (
        '<section class="poster-section" id="seccion-posters" '
        'aria-labelledby="titulo-posters">'
        f'{posters_head}<div class="poster-grid">{posters}</div>'
        '<div class="count" id="count-posters" aria-live="polite"></div></section>')

    top_rows = "".join(
        fila_tabla([f'<span class="pill">{r["my_rating"]}</span>',
                    f'<span class="nw">{e(r["title_es"] or r["original_title"] or "")}'
                    f' <span style="color:var(--sub)">({r["year"] or "?"})</span></span>',
                    e(r["title_type"] or ""), str(r["imdb_rating"] or "-")],
                   etiquetas=ETIQUETAS_TABLA["top"],
                   clases=["c-num", "c-titulo", "c-txt", "c-num"])
        for r in top)
    gen_rows = "".join(
        fila_tabla([e(r["genero"]), str(r["titulos"]), str(r["nota_media"])],
                   etiquetas=ETIQUETAS_TABLA["generos"],
                   clases=["c-txt", "c-num", "c-num"])
        for r in generos)
    dir_rows = "".join(
        fila_tabla([e(r["director"]), str(r["titulos"]), str(r["nota_media"])],
                   etiquetas=ETIQUETAS_TABLA["directores"],
                   clases=["c-txt", "c-num", "c-num"])
        for r in directores) or fila_tabla(
            ["Sin datos aún", "", ""], etiquetas=ETIQUETAS_TABLA["directores"],
            clases=["c-txt", "c-num", "c-num"])
    actor_rows = "".join(
        fila_tabla([e(r["actor"]), str(r["titulos"]), str(r["media"])],
                   etiquetas=ETIQUETAS_TABLA["actores"])
        for r in actores) or fila_tabla(
            ["Sin reparto suficiente aún", "", ""],
            etiquetas=ETIQUETAS_TABLA["actores"])
    joya_rows = "".join(
        fila_tabla([f'<span class="pill">{r["my_rating"]}</span>',
                    f'<span class="nw">{e(r["title_es"] or r["original_title"] or "")}'
                    f' <span style="color:var(--sub)">({r["year"] or "?"})</span></span>',
                    str(r["imdb_rating"]), f'+{round(r["dif"], 1)}'],
                   etiquetas=ETIQUETAS_TABLA["joyas"])
        for r in joyas) or fila_tabla(
            ["Sin joyas con +1.5 sobre IMDb", "", "", ""],
            etiquetas=ETIQUETAS_TABLA["joyas"])
    decep_rows = "".join(
        fila_tabla([f'<span class="pill">{r["my_rating"]}</span>',
                    f'<span class="nw">{e(r["title_es"] or r["original_title"] or "")}'
                    f' <span style="color:var(--sub)">({r["year"] or "?"})</span></span>',
                    str(r["imdb_rating"]), f'-{round(r["dif"], 1)}'],
                   etiquetas=ETIQUETAS_TABLA["decepciones"])
        for r in decepciones) or fila_tabla(
            ["Sin decepciones de -1.5 bajo IMDb", "", "", ""],
            etiquetas=ETIQUETAS_TABLA["decepciones"])
    todas_tr = []
    for r in todas:
        tit = e(r["title_es"] or r["original_title"] or "")
        clave = e(((r["title_es"] or r["original_title"] or "") + " " + (r["generos"] or "")).lower())
        celdas = [f'{tit}', e(r["title_type"] or ""), str(r["year"] or "-"),
                  mostrar_generos(r["generos"]), str(r["imdb_rating"] or "-"),
                  (f'<span class="pill">{r["my_rating"]}</span>'
                   if r["my_rating"] is not None else '<span class="np" title="No puntuado">NP</span>')]
        fila = fila_tabla(
            celdas, cls_first="t", etiquetas=ETIQUETAS_TABLA["lista"],
            clases=["c-titulo", "c-txt", "c-num", "c-txt", "c-num", "c-num"]).replace(
            "<tr>", f'<tr data-r="{clave}" data-tt="{e(r["tt"] if "tt" in r.keys() else "")}">', 1)
        todas_tr.append(fila)
    all_rows = "".join(todas_tr)
    ntotal = len(todas)
    # Cola recomendada: pendientes ordenados por encaje, con su porqué.
    def _motivos(razones: list[str]) -> str:
        """El primer motivo pesa; los demas son contexto y van apagados."""
        if not razones:
            return '<span class="motivo-vacio">Sin motivo</span>'
        principal = f'<span class="motivo">{e(razones[0])}</span>'
        resto = "".join(f'<span class="motivo-sec">{e(r)}</span>' for r in razones[1:])
        return principal + resto

    para_ti_rows = "".join(
        fila_tabla([
            e(r["titulo"]),
            str(r["year"] or "-"),
            str(r["imdb"] if r["imdb"] is not None else "-"),
            (f'<div class="encaje"><div class="bar">'
             f'<i style="width:{r["encaje"]}%"></i></div>'
             f'<span class="n">{r["encaje"]}%</span></div>'),
            _motivos(r["razones"]),
        ], cls_first="t", etiquetas=ETIQUETAS_TABLA["para-ti"],
           clases=["c-titulo", "c-num", "c-num", "c-encaje", "c-razon"]).replace(
            "<tr>", f'<tr data-tt="{e(r["tt"])}">', 1)
        for r in recomendaciones)
    para_ti_head = cabecera_simple(
        "para-ti", "Para ti",
        "Tus pendientes ordenados por lo que encaja contigo, y por qué.")
    para_ti_html = ""
    if para_ti_rows:
        para_ti_html = (
            '<section id="seccion-para-ti" aria-labelledby="titulo-para-ti">'
            f'{para_ti_head}'
            '<table class="paginada tabla-cards" id="tabla-para-ti" '
            'data-seccion="para-ti" data-abre-ficha>'
            '<colgroup><col><col style="width:76px"><col style="width:76px">'
            '<col style="width:132px"><col></colgroup>'
            '<thead><tr><th class="c-titulo">Título</th><th class="c-num">Año</th>'
            '<th class="c-num">IMDb</th><th class="c-encaje">Encaje</th>'
            f'<th class="c-razon">Por qué</th></tr></thead>'
            f'<tbody>{para_ti_rows}</tbody></table></section>')

    # Mi perfil: tu gusto medido, con la evidencia (cuántos títulos) a la vista.
    perfil_html = ""
    if perfil_resumen["alto"] or perfil_resumen["bajo"]:
        def _perfil_items(items, clase):
            partes = []
            for it in items:
                ancho = min(100, int(abs(it["lift"]) * 22))
                partes.append(
                    f'<div class="{clase}-item">'
                    f'<span class="{clase}-nombre">{e(it["valor"])}'
                    f'<span class="{clase}-faceta">{e(it["faceta"])}'
                    f' · {it["n"]} títulos</span></span>'
                    f'<span class="{clase}-barra"><i style="width:{ancho}%"></i></span>'
                    f'<span class="{clase}-valor">{it["lift"]:+.1f}</span></div>')
            return "".join(partes)

        perfil_html = (
            '<section id="seccion-perfil" aria-labelledby="titulo-perfil">'
            '<div class="section-head"><div><h2 id="titulo-perfil" tabindex="-1">'
            'Mi perfil</h2><p class="hint">Tu gusto, medido: cuanto te sale cada '
            f'cosa frente a tu media ({perfil_resumen["media_global"]}), '
            f'sobre {perfil_resumen["n_valoradas"]} títulos valorados.</p></div></div>'
            '<div class="grid2">'
            f'<div class="perfil-caja"><b>Te sale alto</b>'
            f'{_perfil_items(perfil_resumen["alto"], "perfil-alto")}</div>'
            f'<div class="perfil-caja"><b>Te sale flojo</b>'
            f'{_perfil_items(perfil_resumen["bajo"], "perfil-bajo")}</div>'
            '</div></section>')
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
    # Colecciones: qué saga comparte y qué partes tienes tú, por año.
    colecciones: dict[int, dict] = {}
    for r in coleccion_rows:
        grupo = colecciones.setdefault(r["collection_id"], {
            "id": r["collection_id"],
            "nombre": r["collection_name"] or "",
            "partes": [],
        })
        grupo["partes"].append({
            "tt": r["tt"], "titulo": r["titulo"], "year": r["year"],
            "nota": r["my_rating"]})
    coleccion_por_tt: dict[str, dict] = {}
    for grupo in colecciones.values():
        for parte in grupo["partes"]:
            coleccion_por_tt[parte["tt"]] = grupo
    catalogo_map: dict[str, dict] = {}
    for r in fichas:
        tt = r["tt"]
        titulo = r["title_es"] or r["original_title"] or tt
        catalogo_map[tt] = {
            "titulo": titulo,
            "original": r["original_title"] or "",
            "url": r["url"] or "",
            "tipo": r["title_type"] or "",
            "year": r["year"],
            "imdb": r["imdb_rating"],
            "nota": r["my_rating"],
            "fecha": r["date_rated"] or "",
            "estado": "rated" if r["my_rating"] is not None else "watchlist",
            "duracion": r["runtime_min_exact"] or r["runtime_min_csv"],
            "sinopsis": r["synopsis"] or "",
            "poster": r["poster_url"] or "",
            "sin_sinopsis": not bool(r["synopsis"]),
            "sin_reparto": not bool(cast_por_tt.get(tt)),
            "diferencia": (
                round(r["my_rating"] - r["imdb_rating"], 1)
                if r["my_rating"] is not None and r["imdb_rating"] is not None
                else None),
            "reparto": [
                {"nombre": c["name"], "personaje": c["character"]}
                for c in cast_por_tt.get(tt, [])[:8]],
            "directores": dir_por_tt.get(tt, []),
            "paises": pais_por_tt.get(tt, []),
            "generos": gen_por_tt.get(tt, []),
            "coleccion": coleccion_por_tt.get(tt),
        }
    catalogo_json = json.dumps(catalogo_map, ensure_ascii=False).replace("</", "<\\/")
    pend_rows = "".join(
        fila_tabla([f'<span class="nw">{e(r["title_es"] or r["original_title"] or "")}'
                    f' <span style="color:var(--sub)">({r["year"] or "?"})</span></span>',
                    e(r["title_type"] or ""), str(r["imdb_rating"] or "-")],
                   cls_first="t", etiquetas=ETIQUETAS_TABLA["seguimiento"])
        for r in pend)

    dec_rows = "".join(
        fila_tabla([
            f'{int(r["decada"])}s',
            str(r["titulos"]),
            str(r["media"] or "-")
        ], etiquetas=ETIQUETAS_TABLA["decadas"],
            clases=["c-txt", "c-num", "c-num"])
        for r in decadas)

    js = """<script>
(function () {
  const PASO = 15;
  const CLAVE = 'db-peliculas:filtros:v1';
  const FICHAS = JSON.parse(document.getElementById('catalogo-data').textContent || '{}');
  const CATALOGO = Object.entries(FICHAS).map(([tt, f]) => Object.assign({ tt }, f));
  const texto = (v) => (v == null ? '' : String(v));
  const decadaDe = (f) => (f.year ? String(Math.floor(Number(f.year) / 10) * 10) : '');
  const MEDIA = (() => {
    const notas = CATALOGO.filter((x) => x.nota != null).map((x) => x.nota);
    return notas.length ? notas.reduce((a, b) => a + b, 0) / notas.length : 0;
  })();
  const buscaTexto = (f) => [
    f.titulo, f.original, (f.directores || []).join(' '),
    (f.reparto || []).map((x) => x.nombre).join(' '),
    (f.generos || []).join(' ')
  ].join(' ').toLowerCase();
  const mostrarGeneros = (lista) => {
    const partes = lista || [];
    let t = partes.slice(0, 3).join(', ');
    if (partes.length > 3) t += '...';
    return t || '-';
  };
  const valoresUnicos = (datos, obtener) => {
    const set = new Set();
    datos.forEach((f) => (obtener(f) || []).forEach((v) => { if (v) set.add(v); }));
    return [...set].sort((a, b) => a.localeCompare(b, 'es'))
      .map((v) => ({ valor: v, etiqueta: v }));
  };
  const opcion = (valor, etiqueta, soloEn) => ({ valor, etiqueta, soloEn });

  const FACETAS = {
    tipo: {
      etiqueta: 'Tipo',
      opciones: (datos) => valoresUnicos(datos, (f) => [f.tipo]),
      prueba: (f, v) => f.tipo === v
    },
    genero: {
      etiqueta: 'Género',
      opciones: (datos) => valoresUnicos(datos, (f) => f.generos || []),
      prueba: (f, v) => (f.generos || []).includes(v)
    },
    decada: {
      etiqueta: 'Década',
      opciones: (datos) => valoresUnicos(datos, (f) => [decadaDe(f)])
        .sort((a, b) => Number(b.valor) - Number(a.valor))
        .map((o) => ({ valor: o.valor, etiqueta: o.valor + '–' + (Number(o.valor) + 9) })),
      prueba: (f, v) => decadaDe(f) === v
    },
    nota: {
      etiqueta: 'Tu nota',
      opciones: () => [
        opcion('10', '10'), opcion('9', '9–9.9'), opcion('8', '8–8.9'),
        opcion('7', '7–7.9'), opcion('6', '6–6.9'), opcion('5', '5 o menos'),
        opcion('np', 'Sin nota', ['lista']),
        opcion('media_alta', 'Por encima de mi media'),
        opcion('media_baja', 'Por debajo de mi media')
      ],
      prueba: (f, v) => {
        const n = f.nota;
        if (v === 'np') return n == null;
        if (v === 'media_alta') return n != null && n > MEDIA;
        if (v === 'media_baja') return n != null && n < MEDIA;
        if (n == null) return false;
        if (v === '10') return n === 10;
        if (v === '5') return n < 6;
        const base = Number(v);
        return n >= base && n < base + 1;
      }
    },
    imdb: {
      etiqueta: 'IMDb',
      opciones: () => [
        opcion('9', '9+'), opcion('8', '8–8.9'), opcion('7', '7–7.9'),
        opcion('6', '6–6.9'), opcion('menos6', 'Menos de 6'),
        opcion('np', 'Sin IMDb', ['lista', 'seguimiento'])
      ],
      prueba: (f, v) => {
        const n = f.imdb;
        if (v === 'np') return n == null;
        if (n == null) return false;
        if (v === '9') return n >= 9;
        if (v === 'menos6') return n < 6;
        const base = Number(v);
        return n >= base && n < base + 1;
      }
    },
    estado: {
      etiqueta: 'Estado',
      opciones: () => [opcion('rated', 'Valorada'), opcion('watchlist', 'Pendiente')],
      prueba: (f, v) => f.estado === v
    },
    calidad: {
      etiqueta: 'Calidad de ficha',
      opciones: () => [
        opcion('sin_sinopsis', 'Sin sinopsis'), opcion('sin_reparto', 'Sin reparto'),
        opcion('sin_poster', 'Sin póster'), opcion('completa', 'Ficha completa')
      ],
      prueba: (f, v) => {
        if (v === 'sin_sinopsis') return !!f.sin_sinopsis;
        if (v === 'sin_reparto') return !!f.sin_reparto;
        if (v === 'sin_poster') return !f.poster;
        return !f.sin_sinopsis && !f.sin_reparto && !!f.poster;
      }
    },
    diferencia: {
      etiqueta: 'Diferencia con IMDb',
      opciones: () => [
        opcion('p15', '+1.5–1.9', ['joyas']),
        opcion('p20', '+2–2.4', ['joyas']),
        opcion('p25', '+2.5 o más', ['joyas']),
        opcion('n15', '−1.5–−1.9', ['decepciones']),
        opcion('n20', '−2–−2.4', ['decepciones']),
        opcion('n25', '−2.5 o menos', ['decepciones'])
      ],
      prueba: (f, v) => {
        const d = f.diferencia;
        if (d == null) return false;
        if (v === 'p15') return d >= 1.5 && d < 2;
        if (v === 'p20') return d >= 2 && d < 2.5;
        if (v === 'p25') return d >= 2.5;
        if (v === 'n15') return d <= -1.5 && d > -2;
        if (v === 'n20') return d <= -2 && d > -2.5;
        return d <= -2.5;
      }
    },
    orden: {
      etiqueta: 'Ordenar por',
      tipo: 'orden',
      opciones: (datos, seccion) => (SECCIONES[seccion].ordenes || [])
        .map((v) => ({ valor: v, etiqueta: ORDENES[v].etiqueta })),
      prueba: () => true
    }
  };

  const ORDENES = {
    nota_desc: { etiqueta: 'Tu nota (mayor primero)',
      cmp: (a, b) => (b.nota == null ? -1 : b.nota) - (a.nota == null ? -1 : a.nota) || a.titulo.localeCompare(b.titulo, 'es') },
    diferencia_desc: { etiqueta: 'Diferencia (mayor primero)',
      cmp: (a, b) => (b.diferencia || 0) - (a.diferencia || 0) || a.titulo.localeCompare(b.titulo, 'es') },
    diferencia_asc: { etiqueta: 'Diferencia (menor primero)',
      cmp: (a, b) => (a.diferencia || 0) - (b.diferencia || 0) || a.titulo.localeCompare(b.titulo, 'es') },
    titulo_asc: { etiqueta: 'Título (A–Z)',
      cmp: (a, b) => a.titulo.localeCompare(b.titulo, 'es') },
    imdb_desc: { etiqueta: 'IMDb (mayor primero)',
      cmp: (a, b) => (b.imdb == null ? -1 : b.imdb) - (a.imdb == null ? -1 : a.imdb) || a.titulo.localeCompare(b.titulo, 'es') },
    year_desc: { etiqueta: 'Año (más reciente)',
      cmp: (a, b) => (b.year || 0) - (a.year || 0) || a.titulo.localeCompare(b.titulo, 'es') }
  };

  const SECCIONES = {
    posters: {
      tabla: null, base: (f) => f.nota != null, limite: 10,
      facetas: ['tipo', 'genero', 'decada', 'nota', 'orden'],
      ordenes: ['nota_desc', 'titulo_asc', 'year_desc'], ordenDefecto: 'nota_desc'
    },
    top: {
      tabla: 'tabla-top', base: (f) => f.nota != null, limite: 60,
      facetas: ['tipo', 'genero', 'decada', 'nota', 'imdb', 'orden'],
      ordenes: ['nota_desc', 'imdb_desc', 'titulo_asc', 'year_desc'], ordenDefecto: 'nota_desc'
    },
    joyas: {
      tabla: 'tabla-joyas', tarjeta: true,
      base: (f) => f.diferencia != null && f.diferencia >= 1.5, limite: 30,
      facetas: ['tipo', 'genero', 'decada', 'nota', 'imdb', 'diferencia', 'orden'],
      ordenes: ['diferencia_desc', 'nota_desc', 'titulo_asc'], ordenDefecto: 'diferencia_desc'
    },
    decepciones: {
      tabla: 'tabla-decepciones', tarjeta: true,
      base: (f) => f.diferencia != null && f.diferencia <= -1.5, limite: 30,
      facetas: ['tipo', 'genero', 'decada', 'nota', 'imdb', 'diferencia', 'orden'],
      ordenes: ['diferencia_asc', 'nota_desc', 'titulo_asc'], ordenDefecto: 'diferencia_asc'
    },
    lista: {
      tabla: 'tabla-todas', base: () => true, limite: 0,
      facetas: ['tipo', 'genero', 'decada', 'estado', 'nota', 'imdb', 'calidad', 'orden'],
      ordenes: ['titulo_asc', 'nota_desc', 'imdb_desc', 'year_desc'], ordenDefecto: 'titulo_asc'
    },
    seguimiento: {
      tabla: 'tabla-seguimiento', base: (f) => f.nota == null, limite: 60,
      facetas: ['tipo', 'genero', 'decada', 'imdb', 'calidad', 'orden'],
      ordenes: ['imdb_desc', 'titulo_asc', 'year_desc'], ordenDefecto: 'imdb_desc'
    }
  };

  /* Presets de los KPIs: se aplican sobre la seccion 'lista'.
     Solo hay preset para los KPIs que equivalen a un conjunto de titulos.
     'media' y 'exigencia' son promedios: su boton queda deshabilitado. */
  const PRESET_KPI = {
    total: { facetas: {} },
    valoradas: { facetas: { estado: ['rated'] } },
    pendientes: { facetas: { estado: ['watchlist'] } },
    faltan: { facetas: { calidad: ['sin_sinopsis', 'sin_reparto', 'sin_poster'] } },
    enriquecidos: { facetas: { calidad: ['completa'] } }
  };

  const pill = (v) => {
    const s = document.createElement('span');
    s.className = 'pill';
    s.textContent = texto(v);
    return s;
  };
  const np = () => {
    const s = document.createElement('span');
    s.className = 'np';
    s.title = 'No puntuado';
    s.textContent = 'NP';
    return s;
  };
  const tituloCelda = (f) => {
    const span = document.createElement('span');
    span.className = 'nw';
    span.textContent = f.titulo;
    const anio = document.createElement('span');
    anio.style.color = 'var(--sub)';
    anio.textContent = ' (' + (f.year || '?') + ')';
    span.appendChild(anio);
    return span;
  };
  const COLUMNAS = {
    top: [
      { etiqueta: 'Tu nota', clase: 'c-num', valor: (f) => pill(f.nota) },
      { etiqueta: 'Título', clase: 't c-titulo', valor: tituloCelda },
      { etiqueta: 'Tipo', clase: 'c-txt', valor: (f) => f.tipo || '-' },
      { etiqueta: 'IMDb', clase: 'c-num', valor: (f) => (f.imdb == null ? '-' : texto(f.imdb)) }
    ],
    joyas: [
      { etiqueta: 'Tu nota', clase: 'c-num', valor: (f) => pill(f.nota) },
      { etiqueta: 'Título', clase: 't c-titulo', titulo: true, valor: tituloCelda },
      { etiqueta: 'IMDb', clase: 'c-num', valor: (f) => (f.imdb == null ? '-' : texto(f.imdb)) },
      { etiqueta: 'Diferencia', clase: 'c-num', valor: (f) => (f.diferencia > 0 ? '+' : '') + texto(f.diferencia) }
    ],
    decepciones: [
      { etiqueta: 'Tu nota', clase: 'c-num', valor: (f) => pill(f.nota) },
      { etiqueta: 'Título', clase: 't c-titulo', titulo: true, valor: tituloCelda },
      { etiqueta: 'IMDb', clase: 'c-num', valor: (f) => (f.imdb == null ? '-' : texto(f.imdb)) },
      { etiqueta: 'Diferencia', clase: 'c-num', valor: (f) => texto(f.diferencia) }
    ],
    lista: [
      { etiqueta: 'Título', clase: 't c-titulo', valor: (f) => f.titulo },
      { etiqueta: 'Tipo', clase: 'c-txt', valor: (f) => f.tipo || '-' },
      { etiqueta: 'Año', clase: 'c-num', valor: (f) => (f.year == null ? '-' : texto(f.year)) },
      { etiqueta: 'Géneros', clase: 'c-txt', valor: (f) => mostrarGeneros(f.generos) },
      { etiqueta: 'IMDb', clase: 'c-num', valor: (f) => (f.imdb == null ? '-' : texto(f.imdb)) },
      { etiqueta: 'Tu nota', clase: 'c-num', valor: (f) => (f.nota == null ? np() : pill(f.nota)) }
    ],
    seguimiento: [
      { etiqueta: 'Título', clase: 't c-titulo', valor: tituloCelda },
      { etiqueta: 'Tipo', clase: 'c-txt', valor: (f) => f.tipo || '-' },
      { etiqueta: 'IMDb', clase: 'c-num', valor: (f) => (f.imdb == null ? '-' : texto(f.imdb)) }
    ]
  };
  Object.keys(COLUMNAS).forEach((id) => { SECCIONES[id].columnas = COLUMNAS[id]; });

  const estadoFiltros = {};
  const paginadores = {};
  Object.keys(SECCIONES).forEach((id) => {
    estadoFiltros[id] = { facetas: {}, orden: SECCIONES[id].ordenDefecto, q: '' };
  });

  const opcionesFaceta = (clave, seccion) => {
    const faceta = FACETAS[clave];
    if (!faceta) return [];
    return faceta.opciones(CATALOGO, seccion)
      .filter((o) => !o.soloEn || o.soloEn.includes(seccion));
  };

  function filasDe(id) {
    const conf = SECCIONES[id];
    const est = estadoFiltros[id];
    let filas = CATALOGO.filter(conf.base);
    Object.keys(est.facetas).forEach((clave) => {
      const valores = est.facetas[clave] || [];
      const faceta = FACETAS[clave];
      if (!valores.length || !faceta) return;
      filas = filas.filter((f) => valores.some((v) => faceta.prueba(f, v)));
    });
    if (id === 'lista' && est.q) {
      const t = est.q.toLowerCase();
      filas = filas.filter((f) => buscaTexto(f).includes(t));
    }
    filas.sort((ORDENES[est.orden] || ORDENES[conf.ordenDefecto]).cmp);
    return filas;
  }

  function filaDe(conf, f) {
    const tr = document.createElement('tr');
    tr.dataset.tt = f.tt;
    if (conf.tarjeta) return filaDeTarjeta(conf, f);
    conf.columnas.forEach((col) => {
      const td = document.createElement('td');
      if (col.clase) td.className = col.clase;
      td.dataset.label = col.etiqueta;
      const v = col.valor(f);
      if (v instanceof Node) td.appendChild(v);
      else td.textContent = v;
      tr.appendChild(td);
    });
    return tr;
  }

  /* Fila tipo tarjeta: el titulo arriba y los datos en una fila alineada
     debajo (tu nota, IMDb, diferencia). */
  function filaDeTarjeta(conf, f) {
    const tr = document.createElement('tr');
    tr.dataset.tt = f.tt;
    const td = document.createElement('td');
    td.className = 'celda-tarjeta';
    td.colSpan = conf.columnas.length;
    const cabecera = document.createElement('div');
    cabecera.className = 'tarjeta-titulo';
    const colTitulo = conf.columnas.find((c) => c.titulo);
    if (colTitulo) {
      const v = colTitulo.valor(f);
      if (v instanceof Node) cabecera.appendChild(v);
      else cabecera.textContent = v;
    }
    td.appendChild(cabecera);
    const datos = document.createElement('div');
    datos.className = 'tarjeta-datos';
    conf.columnas.forEach((col) => {
      if (col.titulo) return;
      const caja = document.createElement('div');
      caja.className = 'dato';
      const etiqueta = document.createElement('span');
      etiqueta.className = 'dato-label';
      etiqueta.textContent = col.etiqueta;
      const valor = document.createElement('span');
      valor.className = 'dato-valor';
      const v = col.valor(f);
      if (v instanceof Node) valor.appendChild(v);
      else valor.textContent = v;
      caja.append(etiqueta, valor);
      datos.appendChild(caja);
    });
    td.appendChild(datos);
    tr.appendChild(td);
    return tr;
  }

  function montarPaginador(tabla, paso = PASO) {
    const wrap = document.createElement('div');
    wrap.className = 'more-wrap';
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'more-btn';
    const info = document.createElement('div');
    info.className = 'count';
    info.setAttribute('aria-live', 'polite');
    wrap.appendChild(btn);
    tabla.after(info);
    tabla.after(wrap);
    let visibles = paso;
    const filas = () => Array.from(tabla.querySelectorAll('tbody tr'))
      .filter((tr) => !tr.classList.contains('vacio'));
    const pintar = () => {
      const rows = filas();
      if (!rows.length) {
        btn.hidden = true;
        info.textContent = 'Sin resultados con estos filtros.';
        return;
      }
      const n = Math.min(visibles, rows.length);
      rows.forEach((tr, i) => { tr.style.display = i < n ? '' : 'none'; });
      info.textContent = 'Mostrando ' + n + ' de ' + rows.length;
      const restan = rows.length - n;
      btn.hidden = restan <= 0;
      if (restan > 0) btn.textContent = 'Cargar ' + paso + ' más (' + restan + ' restantes)';
    };
    btn.addEventListener('click', () => { visibles += paso; pintar(); });
    return {
      reiniciar() { visibles = paso; pintar(); },
      pintar
    };
  }

  function renderPosters(id) {
    const cont = document.querySelector('#seccion-posters .poster-grid');
    if (!cont) return;
    const conf = SECCIONES[id];
    const filas = filasDe(id);
    const visibles = conf.limite ? filas.slice(0, conf.limite) : filas;
    cont.replaceChildren();
    if (!visibles.length) {
      const p = document.createElement('p');
      p.className = 'empty';
      p.textContent = 'Sin resultados con estos filtros.';
      cont.appendChild(p);
    } else {
      visibles.forEach((f) => {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'poster-card' + (f.poster ? '' : ' no-poster');
        b.dataset.tt = f.tt;
        b.setAttribute('aria-label', 'Abrir ficha de ' + f.titulo);
        if (f.poster) {
          const img = document.createElement('img');
          img.src = f.poster;
          img.alt = 'Póster de ' + f.titulo;
          img.loading = 'lazy';
          b.appendChild(img);
        } else {
          const ini = document.createElement('span');
          ini.className = 'poster-fallback';
          ini.setAttribute('aria-hidden', 'true');
          ini.textContent = iniciales(f.titulo);
          b.appendChild(ini);
        }
        const nota = document.createElement('span');
        nota.className = 'poster-rating';
        nota.textContent = texto(f.nota);
        const titulo = document.createElement('span');
        titulo.className = 'poster-title';
        titulo.textContent = f.titulo;
        const anio = document.createElement('span');
        anio.className = 'poster-year';
        anio.textContent = f.year || '?';
        b.append(nota, titulo, anio);
        cont.appendChild(b);
      });
    }
    const info = document.getElementById('count-posters');
    if (info) info.textContent = 'Mostrando ' + visibles.length + ' de ' + filas.length;
  }

  function renderTabla(id) {
    const conf = SECCIONES[id];
    const tabla = document.getElementById(conf.tabla);
    if (!tabla) return;
    const tbody = tabla.querySelector('tbody');
    if (!tbody) return;
    const filas = filasDe(id);
    const visibles = conf.limite ? filas.slice(0, conf.limite) : filas;
    const frag = document.createDocumentFragment();
    if (!visibles.length) {
      const tr = document.createElement('tr');
      tr.className = 'vacio';
      const td = document.createElement('td');
      td.colSpan = conf.columnas.length;
      td.className = 'empty';
      td.textContent = 'Sin resultados con estos filtros.';
      tr.appendChild(td);
      frag.appendChild(tr);
    } else {
      visibles.forEach((f) => frag.appendChild(filaDe(conf, f)));
    }
    tbody.replaceChildren(frag);
    if (paginadores[id]) paginadores[id].reiniciar();
  }

  function renderSeccion(id) {
    if (!SECCIONES[id]) return;
    if (id === 'posters') renderPosters(id);
    else renderTabla(id);
    pintarChips(id);
  }

  function pintarChips(id) {
    const cont = document.getElementById('chips-' + id);
    const est = estadoFiltros[id];
    if (!cont || !est) return;
    cont.replaceChildren();
    let n = 0;
    Object.keys(est.facetas).forEach((clave) => {
      const faceta = FACETAS[clave];
      const valores = est.facetas[clave] || [];
      if (!faceta || !valores.length || clave === 'orden') return;
      const opciones = opcionesFaceta(clave, id);
      valores.forEach((valor) => {
        const op = opciones.find((o) => o.valor === valor);
        if (!op) return;
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'chip';
        b.textContent = faceta.etiqueta + ': ' + op.etiqueta + ' ×';
        b.setAttribute('aria-label', 'Quitar filtro ' + faceta.etiqueta + ': ' + op.etiqueta);
        b.addEventListener('click', () => alternarFaceta(id, clave, valor, false));
        cont.appendChild(b);
        n += 1;
      });
    });
    cont.hidden = n === 0;
    const panel = document.getElementById('filtro-' + id);
    if (panel && !panel.hidden) {
      panel.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        input.checked = (est.facetas[input.dataset.faceta] || []).includes(input.value);
      });
    }
    const badge = document.querySelector('[data-filtro="' + id + '"] .filtro-badge');
    if (badge) {
      badge.textContent = texto(n);
      badge.hidden = n === 0;
    }
  }

  function alternarFaceta(id, clave, valor, activo) {
    const est = estadoFiltros[id];
    const actuales = (est.facetas[clave] || []).filter((v) => v !== valor);
    if (activo) actuales.push(valor);
    if (actuales.length) est.facetas[clave] = actuales;
    else delete est.facetas[clave];
    renderSeccion(id);
    guardarSesion();
  }

  function limpiarFiltros(id) {
    estadoFiltros[id] = { facetas: {}, orden: SECCIONES[id].ordenDefecto, q: '' };
    if (id === 'lista') {
      const q = document.getElementById('q');
      if (q) q.value = '';
    }
    renderSeccion(id);
    const panel = document.getElementById('filtro-' + id);
    if (panel && !panel.hidden) construirPanel(id);
    guardarSesion();
  }

  function construirPanel(id) {
    const panel = document.getElementById('filtro-' + id);
    if (!panel) return;
    const est = estadoFiltros[id];
    panel.replaceChildren();
    const h = document.createElement('h3');
    h.textContent = 'Filtros';
    panel.appendChild(h);
    SECCIONES[id].facetas.forEach((clave) => {
      const faceta = FACETAS[clave];
      if (!faceta) return;
      const grupo = document.createElement('div');
      grupo.className = 'filtro-grupo';
      const etiqueta = document.createElement('strong');
      etiqueta.textContent = faceta.etiqueta;
      grupo.appendChild(etiqueta);
      if (clave === 'orden') {
        const sel = document.createElement('select');
        sel.className = 'filtro-select';
        sel.setAttribute('aria-label', faceta.etiqueta);
        opcionesFaceta('orden', id).forEach((o) => {
          const op = document.createElement('option');
          op.value = o.valor;
          op.textContent = o.etiqueta;
          if (est.orden === o.valor) op.selected = true;
          sel.appendChild(op);
        });
        sel.addEventListener('change', () => {
          est.orden = sel.value;
          renderSeccion(id);
          guardarSesion();
        });
        grupo.appendChild(sel);
      } else {
        opcionesFaceta(clave, id).forEach((o) => {
          const label = document.createElement('label');
          label.className = 'filtro-opcion';
          const input = document.createElement('input');
          input.type = 'checkbox';
          input.value = o.valor;
          input.dataset.faceta = clave;
          input.checked = (est.facetas[clave] || []).includes(o.valor);
          input.addEventListener('change', () => {
            alternarFaceta(id, clave, o.valor, input.checked);
          });
          const span = document.createElement('span');
          span.textContent = o.etiqueta;
          label.append(input, span);
          grupo.appendChild(label);
        });
      }
      panel.appendChild(grupo);
    });
    const acciones = document.createElement('div');
    acciones.className = 'filtro-acciones';
    const limpiar = document.createElement('button');
    limpiar.type = 'button';
    limpiar.className = 'filtro-limpiar';
    limpiar.textContent = 'Limpiar';
    limpiar.addEventListener('click', () => limpiarFiltros(id));
    const cerrar = document.createElement('button');
    cerrar.type = 'button';
    cerrar.className = 'filtro-cerrar';
    cerrar.textContent = 'Cerrar';
    cerrar.addEventListener('click', () => cerrarPanelFiltro(id));
    acciones.append(limpiar, cerrar);
    panel.appendChild(acciones);
  }

  function cerrarPanelFiltro(id, devolverFoco = true) {
    const panel = document.getElementById('filtro-' + id);
    if (!panel || panel.hidden) return;
    panel.hidden = true;
    const btn = document.querySelector('[data-filtro="' + id + '"]');
    if (btn) {
      btn.setAttribute('aria-expanded', 'false');
      if (devolverFoco) btn.focus();
    }
  }

  function cerrarPaneles() {
    Object.keys(SECCIONES).forEach((id) => cerrarPanelFiltro(id, false));
  }

  function cerrarPanelesConFoco() {
    const abierto = Object.keys(SECCIONES).find((id) => {
      const panel = document.getElementById('filtro-' + id);
      return panel && !panel.hidden;
    });
    if (abierto) cerrarPanelFiltro(abierto);
  }

  function aplicarPresetKPI(clave) {
    const preset = PRESET_KPI[clave];
    if (!preset) return;
    const est = estadoFiltros.lista;
    est.facetas = JSON.parse(JSON.stringify(preset.facetas || {}));
    est.q = '';
    const q = document.getElementById('q');
    if (q) q.value = '';
    renderSeccion('lista');
    guardarSesion();
    const reduce = typeof window.matchMedia === 'function'
      && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const sec = document.getElementById('lista');
    if (sec) {
      sec.scrollIntoView({ behavior: reduce ? 'auto' : 'smooth', block: 'start' });
      const titulo = document.getElementById('titulo-lista');
      if (titulo) titulo.focus();
    }
  }

  function abrirPanelFiltro(id) {
    if (!SECCIONES[id]) return;
    const panel = document.getElementById('filtro-' + id);
    const btn = document.querySelector('[data-filtro="' + id + '"]');
    if (!panel || !btn || btn.disabled) return;
    if (!panel.hidden) {
      cerrarPanelFiltro(id);
      return;
    }
    cerrarPaneles();
    construirPanel(id);
    panel.hidden = false;
    btn.setAttribute('aria-expanded', 'true');
    const primero = panel.querySelector('input, select, button');
    if (primero) primero.focus();
  }

  function guardarSesion() {
    try {
      sessionStorage.setItem(CLAVE, JSON.stringify(estadoFiltros));
    } catch (err) {
      /* Sin almacenamiento: los filtros viven solo en memoria. */
    }
  }

  function cargarSesion() {
    try {
      const crudo = sessionStorage.getItem(CLAVE);
      if (!crudo) return;
      const datos = JSON.parse(crudo);
      if (!datos || typeof datos !== 'object') return;
      Object.keys(SECCIONES).forEach((id) => {
        const guardado = datos[id];
        if (!guardado || typeof guardado !== 'object') return;
        const est = estadoFiltros[id];
        if (guardado.orden && SECCIONES[id].ordenes.includes(guardado.orden)) {
          est.orden = guardado.orden;
        }
        Object.keys(guardado.facetas || {}).forEach((clave) => {
          if (!SECCIONES[id].facetas.includes(clave) || !FACETAS[clave]) return;
          const valores = guardado.facetas[clave];
          if (!Array.isArray(valores)) return;
          const validos = opcionesFaceta(clave, id).map((o) => o.valor);
          const ok = valores.filter((v) => validos.includes(v));
          if (ok.length) est.facetas[clave] = ok;
        });
        if (id === 'lista' && typeof guardado.q === 'string') est.q = guardado.q;
      });
    } catch (err) {
      Object.keys(SECCIONES).forEach((id) => {
        estadoFiltros[id] = { facetas: {}, orden: SECCIONES[id].ordenDefecto, q: '' };
      });
    }
  }

  const iniciales = (titulo) => (titulo || '').split(/ +/).filter(Boolean).slice(0, 2)
    .map((p) => p[0]).join('').toUpperCase() || '?';
  const bg = document.getElementById('buscador-global');
  const rg = document.getElementById('resultados-global');
  const overlay = document.getElementById('overlay');
  const contenido = document.getElementById('ficha-contenido');
  const cerrarBtn = document.getElementById('ficha-cerrar');
  const plantilla = document.getElementById('ficha-plantilla');
  let seleccion = -1;
  let actual = [];
  let focoPrevio = null;
  const cerrarFicha = () => {
    if (overlay.hidden) return;
    overlay.hidden = true;
    contenido.replaceChildren();
    document.body.style.overflow = '';
    if (focoPrevio && typeof focoPrevio.focus === 'function') focoPrevio.focus();
  };
  const abrirFicha = (tt) => {
    const f = FICHAS[tt];
    if (!f || !plantilla) return;
    contenido.replaceChildren(plantilla.content.cloneNode(true));
    const q = (sel) => contenido.querySelector(sel);
    const h = q('#ficha-titulo');
    h.textContent = f.titulo;
    const meta = q('#ficha-meta');
    const partes = [f.year || '?', f.tipo || '',
      (f.duracion ? f.duracion + ' min' : ''),
      (f.nota != null ? 'Tu nota: ' + f.nota : 'Sin valorar'),
      (f.imdb != null ? 'IMDb: ' + f.imdb : '')].filter(Boolean);
    meta.textContent = partes.join(' · ');
    const img = q('#ficha-poster');
    const fallback = q('#ficha-poster-fallback');
    if (f.poster) {
      img.src = f.poster;
      img.alt = 'Póster de ' + f.titulo;
      img.hidden = false;
      fallback.hidden = true;
    } else {
      img.hidden = true;
      fallback.hidden = false;
      fallback.textContent = iniciales(f.titulo);
    }
    const nota = q('#ficha-nota');
    if (f.nota != null) {
      nota.textContent = f.nota;
      nota.hidden = false;
    } else {
      nota.hidden = true;
    }
    const imdb = q('#ficha-imdb');
    if (f.url) {
      imdb.href = f.url;
      imdb.hidden = false;
    } else {
      imdb.hidden = true;
    }
    const bloques = q('#ficha-bloques');
    const pasa = (titulo, textoBloque) => {
      if (!textoBloque) return;
      const b = document.createElement('div');
      b.className = 'bloque';
      const tt = document.createElement('b');
      tt.textContent = titulo;
      b.appendChild(tt);
      const p = document.createElement('div');
      p.textContent = textoBloque;
      b.appendChild(p);
      bloques.appendChild(b);
    };
    pasa('Reparto', (f.reparto || []).map((m) =>
      m.personaje ? m.nombre + ' como ' + m.personaje : m.nombre).join(', '));
    pasa('Dirección', (f.directores || []).join(', '));
    pasa('Géneros', (f.generos || []).join(', '));
    pasa('Países', (f.paises || []).join(', '));
    // Saga: las partes de la colección que tienes tú, por año y con tu nota.
    const col = f.coleccion;
    if (col && (col.partes || []).length) {
      const b = document.createElement('div');
      b.className = 'bloque';
      const cab = document.createElement('b');
      cab.textContent = 'Colección';
      b.appendChild(cab);
      const cont = document.createElement('div');
      cont.className = 'saga';
      const nombre = document.createElement('div');
      nombre.className = 'saga-nombre';
      nombre.textContent = col.nombre || 'Sin nombre';
      cont.appendChild(nombre);
      col.partes.forEach((p) => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = 'saga-item';
        item.dataset.tt = p.tt;
        const etiqueta = document.createElement('span');
        etiqueta.className = 'saga-titulo';
        etiqueta.textContent = p.titulo || p.tt;
        const meta = document.createElement('span');
        meta.className = 'saga-meta';
        meta.textContent = (p.year || '?') + ' · ' +
          (p.nota != null ? 'tu nota ' + p.nota : 'sin valorar');
        item.appendChild(etiqueta);
        item.appendChild(meta);
        item.addEventListener('click', () => abrirFicha(p.tt));
        cont.appendChild(item);
      });
      b.appendChild(cont);
      bloques.appendChild(b);
    }
    const sinopsis = q('#ficha-sinopsis-texto');
    sinopsis.textContent = f.sinopsis || 'Sin sinopsis disponible todavía.';
    const leerMas = q('#ficha-leer-mas');
    leerMas.hidden = true;
    requestAnimationFrame(() => {
      if (sinopsis.scrollHeight > sinopsis.clientHeight + 1) {
        leerMas.hidden = false;
        leerMas.addEventListener('click', () => {
          const plegada = sinopsis.classList.toggle('plegada');
          leerMas.textContent = plegada ? 'Leer más' : 'Leer menos';
          leerMas.setAttribute('aria-expanded', String(!plegada));
        });
      } else {
        sinopsis.classList.remove('plegada');
      }
    });
    focoPrevio = document.activeElement;
    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    cerrarBtn.focus();
  };
  window.abrirFicha = abrirFicha;
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
  document.addEventListener('keydown', (ev) => {
    if (ev.key === 'Escape') {
      cerrarPanelesConFoco();
      cerrarFicha();
      if (rg) { rg.hidden = true; if (bg) bg.setAttribute('aria-expanded', 'false'); }
    }
  });
  document.addEventListener('click', (ev) => {
    if (!ev.target.closest('.filtro-wrap')) cerrarPaneles();
  });
  const pintarGlobal = () => {
    rg.replaceChildren();
    seleccion = -1;
    if (!bg.value.trim()) { rg.hidden = true; bg.setAttribute('aria-expanded', 'false'); return; }
    const t = bg.value.toLowerCase().trim();
    actual = CATALOGO.filter((x) => buscaTexto(x).includes(t)).slice(0, 8);
    if (!actual.length) { rg.hidden = true; bg.setAttribute('aria-expanded', 'false'); return; }
    actual.forEach((x) => {
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
      t1.textContent = x.titulo;
      tx.appendChild(t1);
      const t2 = document.createElement('div');
      t2.className = 'rg-s';
      t2.textContent = [x.year || '?', x.tipo || '',
        (x.nota != null ? 'Tu nota ' + x.nota : '')].filter(Boolean).join(' · ');
      tx.appendChild(t2);
      b.appendChild(tx);
      b.addEventListener('click', () => {
        rg.hidden = true;
        bg.setAttribute('aria-expanded', 'false');
        bg.focus();
        abrirFicha(x.tt);
      });
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
        seleccion = ev.key === 'ArrowDown'
          ? Math.min(seleccion + 1, btns.length - 1)
          : Math.max(seleccion - 1, 0);
        btns.forEach((b, i) => b.setAttribute('aria-selected', i === seleccion ? 'true' : 'false'));
        if (btns[seleccion]) btns[seleccion].scrollIntoView({ block: 'nearest' });
      } else if (ev.key === 'Enter' && seleccion >= 0 && btns[seleccion]) {
        ev.preventDefault();
        const tt = btns[seleccion].dataset.tt;
        rg.hidden = true;
        abrirFicha(tt);
      }
    });
    document.addEventListener('click', (ev) => {
      if (!rg.hidden && !ev.target.closest('.buscador-global')) {
        rg.hidden = true;
        bg.setAttribute('aria-expanded', 'false');
      }
    });
  }
  const qInput = document.getElementById('q');
  let esperaBusqueda = null;
  if (qInput) {
    qInput.addEventListener('input', () => {
      clearTimeout(esperaBusqueda);
      esperaBusqueda = setTimeout(() => {
        estadoFiltros.lista.q = qInput.value.trim();
        renderSeccion('lista');
        guardarSesion();
      }, 120);
    });
  }
  const gridPosters = document.querySelector('#seccion-posters .poster-grid');
  if (gridPosters) gridPosters.addEventListener('click', (ev) => {
    const card = ev.target.closest('.poster-card');
    if (card && card.dataset.tt) abrirFicha(card.dataset.tt);
  });
  document.querySelectorAll('[data-filtro]').forEach((btn) => {
    btn.addEventListener('click', () => abrirPanelFiltro(btn.dataset.filtro));
  });
  document.querySelectorAll('[data-kpi-filtro]').forEach((btn) => {
    btn.addEventListener('click', () => aplicarPresetKPI(btn.dataset.kpiFiltro));
  });
  cargarSesion();
  if (qInput && estadoFiltros.lista.q) qInput.value = estadoFiltros.lista.q;
  Object.keys(SECCIONES).forEach((id) => {
    const conf = SECCIONES[id];
    if (conf.tabla) {
      const tabla = document.getElementById(conf.tabla);
      if (tabla) paginadores[id] = montarPaginador(tabla);
    }
  });
  document.querySelectorAll('table.paginada').forEach((tabla) => {
    if (paginadores[tabla.dataset.seccion]) return;
    montarPaginador(tabla).reiniciar();
  });
  document.querySelectorAll('table.paginada').forEach((tabla) => {
    const id = tabla.dataset.seccion;
    const conMotor = SECCIONES[id] && SECCIONES[id].tabla === tabla.id;
    const estatica = tabla.hasAttribute('data-abre-ficha');
    if (!conMotor && !estatica) return;
    tabla.addEventListener('click', (ev) => {
      const tr = ev.target.closest('tr[data-tt]');
      if (tr && tr.dataset.tt) abrirFicha(tr.dataset.tt);
    });
  });
  Object.keys(SECCIONES).forEach((id) => renderSeccion(id));
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
{para_ti_html}
{perfil_html}
<section id="seccion-top" aria-labelledby="titulo-top">{top_head}
<table class="paginada tabla-cards" id="tabla-top" data-seccion="top"><colgroup><col style="width:92px"><col><col style="width:150px"><col style="width:86px"></colgroup><thead><tr><th class="c-num">Tu nota</th><th class="c-titulo">Título</th><th class="c-txt">Tipo</th><th class="c-num">IMDb</th></tr></thead><tbody>{top_rows}</tbody></table></section>
<div class="grid2">
<section id="seccion-joyas" aria-labelledby="titulo-joyas">{joyas_head}
<table class="paginada tabla-tarjeta" id="tabla-joyas" data-seccion="joyas"><thead><tr><th>Tú</th><th>Título</th><th>IMDb</th><th>Dif</th></tr></thead><tbody>{joya_rows}</tbody></table></section>
<section id="seccion-decepciones" aria-labelledby="titulo-decepciones">{decep_head}
<table class="paginada tabla-tarjeta" id="tabla-decepciones" data-seccion="decepciones"><thead><tr><th>Tú</th><th>Título</th><th>IMDb</th><th>Dif</th></tr></thead><tbody>{decep_rows}</tbody></table></section>
</div>
<div class="grid2">
<section id="seccion-generos" aria-labelledby="titulo-generos">{generos_head}
<table class="paginada" id="tabla-generos" data-seccion="generos"><colgroup><col><col style="width:96px"><col style="width:96px"></colgroup><thead><tr><th class="c-txt">Género</th><th class="c-num">Títulos</th><th class="c-num">Media</th></tr></thead><tbody>{gen_rows}</tbody></table></section>
<section id="seccion-directores" aria-labelledby="titulo-directores">{directores_head}
<table class="paginada" id="tabla-directores" data-seccion="directores"><colgroup><col><col style="width:96px"><col style="width:96px"></colgroup><thead><tr><th class="c-txt">Director</th><th class="c-num">Títulos</th><th class="c-num">Media</th></tr></thead><tbody>{dir_rows}</tbody></table></section>
</div>
<div class="grid2">
<section id="seccion-actores" aria-labelledby="titulo-actores">{actores_head}
<table class="paginada" id="tabla-actores" data-seccion="actores"><colgroup><col><col style="width:96px"><col style="width:96px"></colgroup><thead><tr><th class="c-txt">Actor</th><th class="c-num">Títulos</th><th class="c-num">Media</th></tr></thead><tbody>{actor_rows}</tbody></table></section>
<section id="seccion-decadas" aria-labelledby="titulo-decadas">{decadas_head}
<table class="paginada" id="tabla-decadas" data-seccion="decadas"><colgroup><col><col style="width:96px"><col style="width:110px"></colgroup><thead><tr><th class="c-txt">Década</th><th class="c-num">Títulos</th><th class="c-num">Media IMDb</th></tr></thead><tbody>{dec_rows}</tbody></table></section>
</div>
<section id="lista" aria-labelledby="titulo-lista">{lista_head}
<input class="search" id="q" type="search" placeholder="Filtra por título o género…" aria-label="Filtrar lista completa">
<table class="paginada tabla-cards" id="tabla-todas" data-seccion="lista"><colgroup><col><col style="width:150px"><col style="width:72px"><col><col style="width:78px"><col style="width:104px"></colgroup><thead><tr><th class="c-titulo">Título</th><th class="c-txt">Tipo</th><th class="c-num">Año</th><th class="c-txt">Géneros</th><th class="c-num">IMDb</th><th>Tu nota</th></tr></thead><tbody>{all_rows}</tbody></table></section>
<section id="seccion-seguimiento" aria-labelledby="titulo-seguimiento">{seguimiento_head}
<table class="paginada tabla-cards" id="tabla-seguimiento" data-seccion="seguimiento"><colgroup><col><col style="width:150px"><col style="width:86px"></colgroup><thead><tr><th class="c-titulo">Título</th><th class="c-txt">Tipo</th><th class="c-num">IMDb</th></tr></thead><tbody>{pend_rows}</tbody></table></section>
<div class="overlay" id="overlay" hidden><div class="ficha" role="dialog" aria-modal="true" aria-labelledby="ficha-titulo">
<button class="ficha-cerrar" id="ficha-cerrar" aria-label="Cerrar ficha">×</button>
<div id="ficha-contenido"></div></div></div>
<template id="ficha-plantilla">
  <div class="ficha-cabecera">
    <div class="ficha-lateral">
      <img class="poster" id="ficha-poster" alt="" loading="lazy">
      <span class="poster-fallback" id="ficha-poster-fallback" aria-hidden="true"></span>
      <span class="pill" id="ficha-nota"></span>
      <a id="ficha-imdb" target="_blank" rel="noopener">Ver en IMDb</a>
    </div>
    <div class="ficha-datos">
      <h3 id="ficha-titulo"></h3>
      <div class="meta" id="ficha-meta"></div>
      <div id="ficha-bloques"></div>
    </div>
  </div>
  <div class="ficha-sinopsis bloque ancho-completo">
    <b>Sinopsis</b>
    <p class="sinopsis plegada" id="ficha-sinopsis-texto"></p>
    <button type="button" class="leer-mas" id="ficha-leer-mas"
            aria-expanded="false">Leer más</button>
  </div>
</template>
<footer>Generado desde tu base local · auto-regenerable con scripts/auto_vista.py</footer>
<script type="application/json" id="catalogo-data">{catalogo_json}</script>
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
