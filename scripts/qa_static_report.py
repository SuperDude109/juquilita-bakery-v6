#!/usr/bin/env python3
"""Run lightweight static checks over public HTML, CSS, and JS files."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
checks = []

for html in PUBLIC.glob("*.html"):
    text = html.read_text(encoding="utf-8", errors="ignore")
    checks.append((html.name, "has title", "<title>" in text))
    checks.append((html.name, "has viewport", "name=\"viewport\"" in text))
    checks.append((html.name, "has lang", "<html lang=" in text))

for css in PUBLIC.glob("*.css"):
    text = css.read_text(encoding="utf-8", errors="ignore")
    checks.append((css.name, "has focus styles", ":focus" in text or "focus-visible" in text))

failures = [c for c in checks if not c[2]]
for file_name, label, ok in checks:
    print(f"{file_name}: {label}: {'pass' if ok else 'fail'}")

raise SystemExit(1 if failures else 0)
