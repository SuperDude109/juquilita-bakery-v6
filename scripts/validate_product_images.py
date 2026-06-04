#!/usr/bin/env python3
"""Validate Juquilita product-card image resolution and write a CSV report."""
from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from product_image_mapping import (  # noqa: E402
    CANONICAL_MAP_PATH,
    CONFIDENCE_VALUES,
    IMAGE_REQUIRED_STATUSES,
    PRODUCT_IMAGE_STATUSES,
    canonical_key_for_names,
    image_file_exists,
    load_entries,
    resolve_product_image,
)


DB_PATH = ROOT / "data" / "bakery.db"
REPORT_PATH = ROOT / "reports" / "product_image_validation_report.csv"
GENERIC_ALT_TEXT = {"image", "photo", "food", "bread", "placeholder", "product image", "bakery item"}
BAD_FILENAME_SUBSTRINGS = (
    "placeholder",
    "emoji",
    "sample",
    "generated",
    "missing",
    "breadstick-icon",
    "baguette-icon",
    "croissant-icon",
    "pastry-icon",
)
BAD_FILENAME_TOKENS = ("icon", "fallback", "chili", "pepper")
ORDER_RESOLUTION_PATTERNS = (
    re.compile(r"image.{0,80}(idx|index|position)", re.I | re.S),
    re.compile(r"(idx|index|position).{0,80}image", re.I | re.S),
    re.compile(r"productGrid.{0,160}(idx|index|position)", re.I | re.S),
)


def normalized_alt(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def filename_has_bad_marker(value: str) -> str:
    name = Path(value or "").name.lower()
    if not name:
        return ""
    for marker in BAD_FILENAME_SUBSTRINGS:
        if marker in name:
            return marker
    for marker in BAD_FILENAME_TOKENS:
        if re.search(rf"(^|[-_]){re.escape(marker)}([-_.]|$)", name):
            return marker
    return ""


def frontend_uses_order_resolution() -> bool:
    source = (ROOT / "public" / "app.js").read_text(encoding="utf-8")
    image_lines = "\n".join(line for line in source.splitlines() if "image" in line.lower() or "product-art" in line)
    return any(pattern.search(image_lines) for pattern in ORDER_RESOLUTION_PATTERNS)


def validate_map(entries: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    keys = [str(entry.get("canonicalKey") or "").strip() for entry in entries]
    for key, count in Counter(keys).items():
        if not key:
            failures.append("canonical map contains an empty canonicalKey")
        elif count > 1:
            failures.append(f"canonical map duplicates canonicalKey {key}")
    for entry in entries:
        key = str(entry.get("canonicalKey") or "").strip()
        status = str(entry.get("imageStatus") or "").strip()
        confidence = str(entry.get("confidence") or "").strip()
        filename = str(entry.get("imageFilename") or "").strip()
        alt = str(entry.get("altText") or "").strip()
        if status not in PRODUCT_IMAGE_STATUSES:
            failures.append(f"{key}: invalid imageStatus {status}")
        if confidence not in CONFIDENCE_VALUES:
            failures.append(f"{key}: invalid confidence {confidence}")
        if status in IMAGE_REQUIRED_STATUSES and not filename:
            failures.append(f"{key}: {status} is missing imageFilename")
        if status in IMAGE_REQUIRED_STATUSES and filename and not image_file_exists(filename):
            failures.append(f"{key}: image file does not exist: {filename}")
        if not alt:
            failures.append(f"{key}: altText is empty")
        elif normalized_alt(alt) in GENERIC_ALT_TEXT:
            failures.append(f"{key}: altText is generic: {alt}")
        bad_marker = filename_has_bad_marker(filename)
        if bad_marker:
            failures.append(f"{key}: imageFilename contains decorative marker {bad_marker}")
    return failures


def validate_products(entries: list[dict[str, Any]], db_path: Path) -> list[dict[str, str]]:
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM products WHERE is_active=1 ORDER BY id").fetchall()

    map_keys = {str(entry.get("canonicalKey") or "").strip() for entry in entries}
    product_keys = [str(row["canonical_key"] or "").strip() for row in rows]
    duplicate_product_keys = {key for key, count in Counter(product_keys).items() if key and count > 1}
    order_resolution_failure = frontend_uses_order_resolution()
    report: list[dict[str, str]] = []

    for row in rows:
        product = dict(row)
        product["canonical_key"] = product.get("canonical_key") or canonical_key_for_names(product["name_es"], product["name_en"])
        resolved = resolve_product_image(product, entries)
        expected_url = f"/imported/website/{resolved['image_filename']}" if resolved["image_filename"] else ""
        failures: list[str] = []
        canonical_key = str(row["canonical_key"] or "").strip()
        if not canonical_key:
            failures.append("canonicalKey is missing")
        if canonical_key in duplicate_product_keys:
            failures.append("canonicalKey is duplicated")
        if canonical_key and canonical_key not in map_keys:
            failures.append("canonicalKey is not present in canonical map")
        if resolved["image_status"] not in PRODUCT_IMAGE_STATUSES:
            failures.append("resolved image status is invalid")
        if resolved["image_status"] in IMAGE_REQUIRED_STATUSES and not resolved["image_filename"]:
            failures.append("image filename is missing for verified/fallback status")
        if resolved["image_status"] in IMAGE_REQUIRED_STATUSES and not image_file_exists(resolved["image_filename"]):
            failures.append("resolved image file does not exist")
        if not resolved["image_alt"]:
            failures.append("alt text is empty")
        elif normalized_alt(resolved["image_alt"]) in GENERIC_ALT_TEXT:
            failures.append("alt text is generic")
        bad_marker = filename_has_bad_marker(resolved["image_filename"] or str(row["image_url"] or ""))
        if bad_marker:
            failures.append(f"image filename contains decorative marker {bad_marker}")
        if resolved["image_status"] in IMAGE_REQUIRED_STATUSES and str(row["image_url"] or "") != expected_url:
            failures.append("legacyVerified/categoryFallback image resolves to a different image")
        if resolved["image_status"] == "needsOwnerPhoto" and str(row["image_url"] or ""):
            failures.append("needsOwnerPhoto product resolves to a product image")
        if order_resolution_failure:
            failures.append("frontend image code appears to resolve by index/order/position")

        report.append({
            "product_id": str(row["id"]),
            "product_display_name": f"{row['name_es']} / {row['name_en']}",
            "canonical_key": canonical_key,
            "resolved_image_filename": resolved["image_filename"],
            "image_status": resolved["image_status"],
            "alt_text": resolved["image_alt"],
            "validation_result": "fail" if failures else "pass",
            "failure_reason": "; ".join(failures),
        })
    return report


def write_report(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "product_id",
        "product_display_name",
        "canonical_key",
        "resolved_image_filename",
        "image_status",
        "alt_text",
        "validation_result",
        "failure_reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--map", type=Path, default=CANONICAL_MAP_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()

    entries = load_entries(args.map)
    map_failures = validate_map(entries)
    rows = validate_products(entries, args.db)
    if map_failures:
        rows.insert(0, {
            "product_id": "map",
            "product_display_name": "canonical map",
            "canonical_key": "",
            "resolved_image_filename": "",
            "image_status": "",
            "alt_text": "",
            "validation_result": "fail",
            "failure_reason": "; ".join(map_failures),
        })
    write_report(rows, args.report)
    failures = [row for row in rows if row["validation_result"] == "fail"]
    print(f"Validated {len(rows)} product image rows. Report: {args.report}")
    if failures:
        for row in failures[:12]:
            print(f"FAIL {row['product_id']} {row['product_display_name']}: {row['failure_reason']}")
        if len(failures) > 12:
            print(f"... {len(failures) - 12} more failures")
        raise SystemExit(1)
    print("All product image validations passed.")


if __name__ == "__main__":
    main()
