#!/usr/bin/env python3
"""Backup portable de la base: volcado SQL + manifiesto JSON.

Uso:
    python scripts/backup.py [--db data/catalogo.db] [--destino backups/]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import DEFAULT_DB_PATH
from src.respaldo import backup


def main() -> int:
    ap = argparse.ArgumentParser(description="Vuelca la base a SQL + manifiesto.")
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH))
    ap.add_argument("--destino", default=str(ROOT / "backups"))
    args = ap.parse_args()
    mani = backup(args.db, args.destino)
    print(json.dumps(mani, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
