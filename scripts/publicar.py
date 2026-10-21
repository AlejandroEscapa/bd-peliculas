#!/usr/bin/env python3
"""publicar: regenera el snapshot y lo publica solo si no pierde nada.

El paso peligroso de este repo es siempre el mismo: regenerar el panel y
hacer commit del HTML. Si la base está a medias (un import que falló, un CSV
vacío, un scraper que se comió medio catálogo), el snapshot nuevo tiene menos
datos y se publica tal cual: el panel pierde cosas sin que nadie se entere.

Este script hace ese paso en condiciones seguras:

  1. Copia de seguridad de la base (volcado SQL + manifiesto).
  2. Genera el snapshot a un fichero temporal, sin tocar el publicado.
  3. Lo compara con el que hay en el repo. Si el nuevo tiene menos títulos,
     menos valoradas, menos sinopsis, menos pósteres o menos reparto, PARA y
     no toca nada.
  4. Si está bien, lo deja en su sitio, hace commit y, si pides, push.

    python scripts/publicar.py --dry-run    # enseña, no toca nada
    python scripts/publicar.py
    python scripts/publicar.py --push
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import DEFAULT_DB_PATH
from src.respaldo import backup

# Métricas que, si bajan, significa que el catálogo ha empeorado.
METRICAS = (
    ("titulos", "títulos"),
    ("valoradas", "títulos valorados"),
    ("con_sinopsis", "con sinopsis"),
    ("con_poster", "con póster"),
    ("con_reparto", "con reparto"),
    ("con_generos", "con géneros"),
    ("directores", "directores distintos"),
    ("actores", "actores distintos"),
)


def metricas_de(snapshot: Path) -> dict:
    """Cuenta lo que tiene un snapshot: títulos, valoradas, sinopsis, etc."""
    if not snapshot.exists():
        return {}
    html = snapshot.read_text(encoding="utf-8")
    m = re.search(r'<script type="application/json" id="catalogo-data">(.*?)</script>',
                  html, re.S)
    if not m:
        return {}
    data = json.loads(m.group(1))
    actores = {a["nombre"] for f in data.values() for a in (f.get("reparto") or [])}
    directores = {d for f in data.values() for d in (f.get("directores") or [])}
    return {
        "titulos": len(data),
        "valoradas": sum(1 for f in data.values() if f.get("nota") is not None),
        "con_sinopsis": sum(1 for f in data.values() if f.get("sinopsis")),
        "con_poster": sum(1 for f in data.values() if f.get("poster")),
        "con_reparto": sum(1 for f in data.values() if f.get("reparto")),
        "con_generos": sum(1 for f in data.values() if f.get("generos")),
        "directores": len(directores),
        "actores": len(actores),
        "recomendaciones": _contar_recomendaciones(html),
    }


def _contar_recomendaciones(html: str) -> int:
    """Filas de la sección "Para ti" (las que llevan motivo y encaje)."""
    m = re.search(r'id="tabla-para-ti".*?</table>', html, re.S)
    if not m:
        return 0
    return len(re.findall(r'<tr data-tt="[^"]+">', m.group(0)))


def comparar(nuevo: Path, publicado: Path) -> dict:
    """Compara dos snapshots. Devuelve qué se gana y qué se pierde."""
    antes = metricas_de(publicado)
    despues = metricas_de(nuevo)
    if not despues:
        return {"antes": antes, "despues": despues, "pierde": [], "gana": [], "error": "no se pudo leer el snapshot nuevo"}
    pierde, gana = [], []
    for clave, etiqueta in METRICAS:
        a, d = antes.get(clave, 0), despues.get(clave, 0)
        if d < a:
            pierde.append(f"{etiqueta}: {a} -> {d} (faltan {a - d})")
        elif d > a:
            gana.append(f"{etiqueta}: {a} -> {d} (+{d - a})")
    return {"antes": antes, "despues": despues, "pierde": pierde, "gana": gana, "error": ""}


def _git(*args: str) -> tuple[int, str]:
    proc = subprocess.run(["git", *args], cwd=str(ROOT), capture_output=True, text=True)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Regenera el snapshot y lo publica solo si no pierde nada.")
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH))
    ap.add_argument("--salida", default=str(ROOT / "preview" / "dashboard.html"))
    ap.add_argument("--push", action="store_true", help="Hacer push al remoto")
    ap.add_argument("--dry-run", action="store_true",
                    help="Compara y enseña, pero no escribe ni hace commit")
    ap.add_argument("--sin-backup", action="store_true", help="No copiar la base antes")
    args = ap.parse_args()

    db = Path(args.db)
    if not db.exists():
        print(f"error: no existe la base {db}", file=sys.stderr)
        return 2

    # 1. Copia de seguridad antes de tocar nada.
    if not args.sin_backup:
        manifiesto = backup(db, ROOT / "backups")
        print(f"copia de seguridad: {manifiesto['dump']}")

    # 2. Generar a un temporal: el snapshot publicado no se toca todavía.
    salida = Path(args.salida)
    with tempfile.TemporaryDirectory() as tmp:
        candidato = Path(tmp) / salida.name
        codigo = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "generar_vista.py"),
             "--db", str(db), "--salida", str(candidato)],
            cwd=str(ROOT)).returncode
        if codigo != 0:
            print("error: el generador falló; no se toca nada", file=sys.stderr)
            return codigo

        # 3. Comparar.
        informe = comparar(candidato, salida)
        print("\n--- antes (publicado) ---")
        print(json.dumps(informe["antes"], indent=2, ensure_ascii=False))
        print("--- después (nuevo) ---")
        print(json.dumps(informe["despues"], indent=2, ensure_ascii=False))
        if informe["gana"]:
            print("\nmejoras:")
            for linea in informe["gana"]:
                print(f"  + {linea}")
        if informe["pierde"]:
            print("\nPERDIDAS (no se publica):")
            for linea in informe["pierde"]:
                print(f"  - {linea}")
            print("\nEl snapshot NO se toca. Revisa la base y vuelve a intentarlo.")
            return 3
        print("\nEl snapshot nuevo no pierde nada.")

        if args.dry_run:
            print("(dry-run: no se escribe nada)")
            return 0

        # 4. Publicar.
        salida.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(candidato, salida)
        print(f"\nescrito {salida}")

    codigo, salida_git = _git("add", str(salida.relative_to(ROOT)))
    if codigo != 0:
        print(salida_git, file=sys.stderr)
        return codigo
    codigo, salida_git = _git("commit", "-m", "chore: regenera el snapshot del panel")
    if codigo != 0:
        if "nothing to commit" in salida_git.lower():
            print("no habia cambios que publicar")
            return 0
        print(salida_git, file=sys.stderr)
        return codigo
    print("commit hecho")

    if args.push:
        codigo, salida_git = _git("push", "origin", "main")
        print(salida_git)
        if codigo != 0:
            return codigo
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
