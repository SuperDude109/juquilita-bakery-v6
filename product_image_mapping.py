"""Canonical product image resolution for Juquilita product cards."""
from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
PUBLIC_DIR = ROOT / "public"
CANONICAL_MAP_PATH = ROOT / "juquilita_canonical_product_image_map.json"
IMPORTED_IMAGE_DIR = PUBLIC_DIR / "imported" / "website"
COMING_SOON_LOGO_FILENAME = "010-juquilita-bakery-logo.png"
COMING_SOON_LOGO_URL = f"/imported/website/{COMING_SOON_LOGO_FILENAME}"

PRODUCT_IMAGE_STATUSES = {"legacyVerified", "categoryFallback", "needsOwnerPhoto"}
IMAGE_REQUIRED_STATUSES = {"legacyVerified", "categoryFallback"}
CONFIDENCE_VALUES = {"high", "medium", "low"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_key(text: str) -> str:
    normalized = unicodedata.normalize("NFD", str(text or "").lower())
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", without_marks).strip("-") or "item"


def normalize_label(text: str) -> str:
    normalized = unicodedata.normalize("NFD", str(text or "").lower())
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", without_marks)).strip()


def canonical_key_for_names(name_es: str, name_en: str) -> str:
    return f"{normalize_key(name_es)}__{normalize_key(name_en)}"


def display_name_for_product(product: dict[str, Any] | sqlite3.Row) -> str:
    return f"{product['name_es']} / {product['name_en']}"


@lru_cache(maxsize=4)
def load_entries(path: Path = CANONICAL_MAP_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path} must contain a list of product image map entries.")
    return [dict(entry) for entry in data]


def entry_indexes(entries: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_key: dict[str, dict[str, Any]] = {}
    by_legacy_label: dict[str, dict[str, Any]] = {}
    for entry in entries:
        key = str(entry.get("canonicalKey") or "").strip()
        if key:
            by_key[key] = entry
        label = str(entry.get("legacyPageLabel") or "").strip()
        if label:
            by_legacy_label[normalize_label(label)] = entry
    return by_key, by_legacy_label


def local_url_for_filename(filename: str) -> str:
    return f"/imported/website/{Path(filename).name}" if filename else ""


def image_file_exists(filename: str, public_dir: Path = PUBLIC_DIR) -> bool:
    if not filename:
        return False
    path = (public_dir / "imported" / "website" / Path(filename).name).resolve()
    return str(path).startswith(str(public_dir.resolve())) and path.exists()


def fallback_alt_for(product: dict[str, Any] | sqlite3.Row) -> str:
    return f"Photo coming soon for {product['name_en']}."


def resolve_product_image(
    product: dict[str, Any] | sqlite3.Row,
    entries: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    entries = load_entries() if entries is None else entries
    by_key, by_legacy_label = entry_indexes(entries)
    canonical_key = str(product["canonical_key"] if "canonical_key" in product.keys() else "").strip() if isinstance(product, sqlite3.Row) else str(product.get("canonical_key") or "").strip()
    entry = by_key.get(canonical_key) if canonical_key else None

    # Only allow the legacy-label fallback when a product has not been assigned
    # a canonical key. This prevents old slugs or grid order from becoming the
    # effective image key.
    if not entry and not canonical_key:
        display_name = display_name_for_product(product)
        entry = by_legacy_label.get(normalize_label(display_name))

    if not entry:
        if not canonical_key:
            canonical_key = canonical_key_for_names(product["name_es"], product["name_en"])
        return {
            "canonical_key": canonical_key,
            "image_url": "",
            "image_filename": "",
            "image_alt": fallback_alt_for(product),
            "image_status": "needsOwnerPhoto",
            "image_confidence": "low",
            "image_source_url": "",
            "placeholder_image_url": COMING_SOON_LOGO_URL,
        }

    filename = str(entry.get("imageFilename") or "").strip()
    status = str(entry.get("imageStatus") or "needsOwnerPhoto").strip()
    if status not in PRODUCT_IMAGE_STATUSES:
        status = "needsOwnerPhoto"
    image_url = local_url_for_filename(filename) if status in IMAGE_REQUIRED_STATUSES and filename else ""
    alt_text = str(entry.get("altText") or "").strip() or fallback_alt_for(product)
    return {
        "canonical_key": str(entry.get("canonicalKey") or canonical_key).strip(),
        "image_url": image_url,
        "image_filename": filename if image_url else "",
        "image_alt": alt_text,
        "image_status": status,
        "image_confidence": str(entry.get("confidence") or "low").strip(),
        "image_source_url": str(entry.get("sourceUrl") or "").strip(),
        "placeholder_image_url": COMING_SOON_LOGO_URL,
    }


def add_column_if_missing(con: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_product_image_columns(con: sqlite3.Connection) -> None:
    for column, definition in {
        "canonical_key": "TEXT DEFAULT ''",
        "product_image_status": "TEXT DEFAULT 'needsOwnerPhoto'",
        "product_image_confidence": "TEXT DEFAULT 'low'",
        "product_image_filename": "TEXT DEFAULT ''",
        "product_image_source_url": "TEXT DEFAULT ''",
    }.items():
        add_column_if_missing(con, "products", column, definition)
    con.execute("CREATE INDEX IF NOT EXISTS idx_products_canonical_key ON products(canonical_key)")


def apply_product_image_map(con: sqlite3.Connection, public_dir: Path = PUBLIC_DIR) -> None:
    ensure_product_image_columns(con)
    entries = load_entries()
    imported_at = utc_now()
    products = con.execute("SELECT * FROM products WHERE is_active=1").fetchall()
    for product in products:
        existing_key = str(product["canonical_key"] or "").strip() if "canonical_key" in product.keys() else ""
        canonical_key = existing_key or canonical_key_for_names(product["name_es"], product["name_en"])
        product_dict = dict(product)
        product_dict["canonical_key"] = canonical_key
        resolved = resolve_product_image(product_dict, entries)
        status = resolved["image_status"]
        image_url = resolved["image_url"]
        filename = resolved["image_filename"]
        alt_text = resolved["image_alt"]
        photo_status = "real_photo_verified" if status == "legacyVerified" else ("category_fallback" if status == "categoryFallback" else "needs_real_photo")
        con.execute(
            """
            UPDATE products
            SET canonical_key=?, image_url=?, image_alt=?, photo_status=?,
                product_image_status=?, product_image_confidence=?,
                product_image_filename=?, product_image_source_url=?, updated_at=?
            WHERE id=?
            """,
            (
                resolved["canonical_key"], image_url, alt_text, photo_status,
                status, resolved["image_confidence"], filename,
                resolved["image_source_url"], imported_at, product["id"],
            ),
        )
        con.execute("UPDATE product_images SET is_primary=0 WHERE product_id=?", (product["id"],))
        if image_url and image_file_exists(filename, public_dir):
            exists = con.execute("SELECT id FROM product_images WHERE product_id=? AND image_url=?", (product["id"], image_url)).fetchone()
            if exists:
                con.execute(
                    "UPDATE product_images SET alt_text=?, image_status='approved', source='canonical_map', is_primary=1, uploaded_at=? WHERE id=?",
                    (alt_text, imported_at, exists["id"]),
                )
            else:
                con.execute(
                    """
                    INSERT INTO product_images(product_id,image_url,alt_text,image_status,source,is_primary,sort_order,uploaded_by,uploaded_at)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (product["id"], image_url, alt_text, "approved", "canonical_map", 1, 10, None, imported_at),
                )
