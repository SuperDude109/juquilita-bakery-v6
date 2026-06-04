#!/usr/bin/env python3
"""Create a SQLite hot backup for Juquilita Bakery v6."""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "data" / "bakery.db"
BACKUPS = ROOT / "backups"


def main() -> None:
    if not DB.exists():
        raise SystemExit(f"Database not found: {DB}")
    BACKUPS.mkdir(exist_ok=True)
    target = BACKUPS / f"bakery-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.db"
    with sqlite3.connect(DB) as src, sqlite3.connect(target) as dst:
        src.backup(dst)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    print(f"backup={target}")
    print(f"bytes={target.stat().st_size}")
    print(f"sha256={digest}")


if __name__ == "__main__":
    main()
