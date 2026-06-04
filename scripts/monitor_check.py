#!/usr/bin/env python3
"""Simple uptime and deep-health check for Juquilita Bakery v6."""
from __future__ import annotations

import json
import sys
import urllib.request

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000/api/health/deep"

try:
    with urllib.request.urlopen(URL, timeout=8) as response:
        payload = json.loads(response.read().decode("utf-8"))
except Exception as exc:
    print(f"status=failed error={exc}")
    raise SystemExit(2)

print(json.dumps(payload, indent=2))
raise SystemExit(0 if payload.get("ok") else 1)
