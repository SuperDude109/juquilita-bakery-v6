#!/usr/bin/env python3
"""CI wrapper for canonical product image validation."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    subprocess.check_call([sys.executable, "scripts/validate_product_images.py"], cwd=ROOT)


if __name__ == "__main__":
    main()
