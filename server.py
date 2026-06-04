#!/usr/bin/env python3
"""Juquilita Bakery v6 stabilization, bakery-case UX, and operations prototype.

Run:
    python3 server.py --init-db
    python3 server.py

This is a standard-library app for local planning/demo use. It deliberately
implements many production concepts, but it is not a drop-in production system.
"""
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import hmac
import io
import json
import logging
import mimetypes
import os
import re
import secrets
import shutil
import sqlite3
import struct
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from hashlib import pbkdf2_hmac
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

try:
    import sentry_sdk  # type: ignore
except Exception:  # Optional production dependency.
    sentry_sdk = None

import seeds
from product_image_mapping import (
    COMING_SOON_LOGO_URL,
    apply_product_image_map,
    canonical_key_for_names,
    resolve_product_image,
)

BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "bakery.db"
SCHEMA_PATH = BASE_DIR / "schema.sql"
SESSION_COOKIE = "jb6_session"
PBKDF_ITERATIONS = 210_000
MAX_BODY_BYTES = 8_000_000
APP_VERSION = "v6"
BACKUP_DIR = BASE_DIR / "backups"
LOG_DIR = BASE_DIR / "logs"
ORDER_STATUSES = {"received", "confirmed", "needs_deposit", "baking", "ready", "completed", "canceled"}
QUOTE_STATUSES = {"new", "reviewing", "quoted", "accepted", "declined", "converted", "canceled"}
APP_STATUSES = {"pending", "approved", "declined", "needs_info"}
PLACEHOLDER_MARKERS = ("replace", "example.com", "test_or_live", "EAAA...", "sk_test_", "local-demo", "...")


logger = logging.getLogger("juquilita")
logging.basicConfig(level=os.environ.get("JB_LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(message)s")
if os.environ.get("SENTRY_DSN") and sentry_sdk:
    sentry_sdk.init(dsn=os.environ["SENTRY_DSN"], enable_logs=True, traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")))


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def production_mode() -> bool:
    return os.environ.get("JB_ENV", "").strip().lower() == "production" or env_bool("JB_PRODUCTION")


def production_placeholder(value: str) -> bool:
    lowered = value.strip().lower()
    return not lowered or any(marker.lower() in lowered for marker in PLACEHOLDER_MARKERS)


def require_env(name: str, *, min_len: int = 1, allow_placeholder: bool = False) -> str:
    value = os.environ.get(name, "").strip()
    if len(value) < min_len:
        raise RuntimeError(f"{name} must be set for production.")
    if not allow_placeholder and production_placeholder(value):
        raise RuntimeError(f"{name} must be a real production value, not a placeholder.")
    return value


def validate_production_config() -> None:
    if not production_mode():
        return
    public_url = require_env("JB_PUBLIC_BASE_URL", min_len=12)
    if not public_url.startswith("https://"):
        raise RuntimeError("JB_PUBLIC_BASE_URL must use https:// in production.")
    require_env("JB_SECRET_KEY", min_len=32)
    require_env("JB_TOKEN_PEPPER", min_len=32)
    if not env_bool("JB_SECURE_COOKIES"):
        raise RuntimeError("JB_SECURE_COOKIES=1 is required for production.")
    if not env_bool("JB_ASSUME_HTTPS"):
        raise RuntimeError("JB_ASSUME_HTTPS=1 is required for production.")
    provider = os.environ.get("JB_PAYMENT_PROVIDER", "").strip().lower()
    if provider not in {"stripe", "square"}:
        raise RuntimeError("JB_PAYMENT_PROVIDER must be stripe or square in production; mock is local-only.")
    if provider == "stripe":
        require_env("STRIPE_SECRET_KEY", min_len=20)
        require_env("STRIPE_WEBHOOK_SECRET", min_len=20)
    if provider == "square":
        require_env("SQUARE_ACCESS_TOKEN", min_len=20)
        require_env("SQUARE_LOCATION_ID", min_len=4)
        require_env("SQUARE_WEBHOOK_SIGNATURE_KEY", min_len=20)
        require_env("SQUARE_WEBHOOK_NOTIFICATION_URL", min_len=12)
    require_env("SENDGRID_API_KEY", min_len=20)
    require_env("SENDGRID_FROM_EMAIL", min_len=6)
    require_env("TWILIO_ACCOUNT_SID", min_len=20)
    require_env("TWILIO_AUTH_TOKEN", min_len=20)
    require_env("TWILIO_FROM_PHONE", min_len=10)
    if not DB_PATH.exists() and not os.environ.get("JB_ADMIN_EMAIL"):
        raise RuntimeError("JB_ADMIN_EMAIL and JB_ADMIN_PASSWORD are required for first production database initialization.")
    if os.environ.get("JB_ADMIN_EMAIL"):
        require_env("JB_ADMIN_EMAIL", min_len=6)
        require_env("JB_ADMIN_PASSWORD", min_len=14)


def validate_production_database() -> None:
    if not production_mode() or not DB_PATH.exists():
        return
    with connect() as con:
        demo = con.execute("SELECT email FROM users WHERE email IN ('admin@juquilita.local','guest@juquilita.local','wholesale@taqueria.local') LIMIT 1").fetchone()
        if demo:
            raise RuntimeError(f"Production database still contains demo account {demo['email']}. Rebuild with JB_ADMIN_EMAIL/JB_ADMIN_PASSWORD or deactivate demo users.")


def security_headers(*, html: bool = False) -> dict[str, str]:
    headers = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    }
    if production_mode():
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if html:
        headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data: https:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'self'; frame-ancestors 'none'"
    return headers


class AppError(Exception):
    def __init__(self, message: str, status: int = 400, details: Any | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.details = details


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat() + "Z"


def today_str() -> str:
    return date.today().isoformat()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def rows_to_dicts(rows: Iterable[sqlite3.Row]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows]


def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PBKDF_ITERATIONS)
    return digest.hex(), salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    actual_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(actual_hash, password_hash)


def clean_text(value: Any, max_len: int = 500) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text[:max_len]


def valid_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def valid_phone(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone)
    return len(digits) >= 10


def parse_money(value: Any, field: str, *, allow_none: bool = False, min_value: float = 0, max_value: float = 10000) -> float | None:
    if value in (None, "") and allow_none:
        return None
    try:
        number = round(float(value), 2)
    except (TypeError, ValueError):
        raise AppError(f"{field} must be a number.")
    if number < min_value or number > max_value:
        raise AppError(f"{field} must be between {min_value} and {max_value}.")
    return number


def parse_int(value: Any, field: str, *, min_value: int = 0, max_value: int = 100000) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise AppError(f"{field} must be a whole number.")
    if number < min_value or number > max_value:
        raise AppError(f"{field} must be between {min_value} and {max_value}.")
    return number


def json_dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


def load_json(text: str, fallback: Any = None) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return fallback


def read_schema() -> str:
    return SCHEMA_PATH.read_text(encoding="utf-8")


def table_columns(con: sqlite3.Connection, table: str) -> set[str]:
    return {row["name"] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}


def add_column_if_missing(con: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    if column not in table_columns(con, table):
        con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_v6_schema(con: sqlite3.Connection) -> None:
    """Lightweight migrations for users who start v6 against an older local DB."""
    for column, definition in {
        "customer_language": "TEXT NOT NULL DEFAULT 'en'",
        "substitution_preference": "TEXT NOT NULL DEFAULT 'call_me'",
        "receipt_token": "TEXT DEFAULT ''",
        "cancellation_cutoff_at": "TEXT DEFAULT ''",
        "edit_cutoff_at": "TEXT DEFAULT ''",
        "pickup_shelf": "TEXT DEFAULT ''",
        "staff_notes": "TEXT DEFAULT ''",
    }.items():
        add_column_if_missing(con, "orders", column, definition)
    for column, definition in {
        "reference_image_url": "TEXT DEFAULT ''",
        "complexity_tier": "TEXT DEFAULT ''",
        "servings": "INTEGER NOT NULL DEFAULT 0",
        "colors": "TEXT DEFAULT ''",
        "exact_inscription_confirmed": "INTEGER NOT NULL DEFAULT 0",
        "pickup_handling": "TEXT DEFAULT ''",
        "quote_public_token": "TEXT DEFAULT ''",
        "expires_at": "TEXT DEFAULT ''",
    }.items():
        add_column_if_missing(con, "quote_requests", column, definition)
    for column, definition in {
        "visual_tags": "TEXT DEFAULT ''",
        "visual_shape": "TEXT DEFAULT ''",
        "public_status": "TEXT NOT NULL DEFAULT 'public'",
        "public_notes": "TEXT DEFAULT ''",
        "canonical_key": "TEXT DEFAULT ''",
        "product_image_status": "TEXT DEFAULT 'needsOwnerPhoto'",
        "product_image_confidence": "TEXT DEFAULT 'low'",
        "product_image_filename": "TEXT DEFAULT ''",
        "product_image_source_url": "TEXT DEFAULT ''",
    }.items():
        add_column_if_missing(con, "products", column, definition)
    for column, definition in {
        "consent_date": "TEXT DEFAULT ''",
        "approved_story_at": "TEXT DEFAULT ''",
        "rights_notes": "TEXT DEFAULT ''",
    }.items():
        add_column_if_missing(con, "partners", column, definition)
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_orders_receipt_token ON orders(receipt_token) WHERE receipt_token != ''")
    con.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_quote_public_token ON quote_requests(quote_public_token) WHERE quote_public_token != ''")


def product_visual_shape(row: sqlite3.Row | dict[str, Any]) -> str:
    text = (str(row["slug"]) + " " + str(row["name_es"]) + " " + str(row["name_en"]) + " " + str(row.get("search_terms", "") if isinstance(row, dict) else row["search_terms"] or "")).lower()
    checks = [
        ("shell", ["concha", "shell"]), ("pig", ["marranito", "pig", "puerquito"]),
        ("heart", ["corazon", "heart"]), ("ring", ["arete", "rosca", "ring"]),
        ("filled", ["relleno", "filled", "empanada", "taquito", "flauta", "churro-fresa", "cajeta"]),
        ("flaky", ["oreja", "hojaldre", "danes", "mil-hojas", "pastry", "turnover"]),
        ("cookie", ["galleta", "polvoron", "cookie", "sandia"]), ("slice", ["slice", "rebanada", "tres leches"]),
        ("cake", ["cake", "pastel", "flan", "chocoflan", "tart"]), ("roll", ["bolillo", "telera", "panbaso", "roll"]),
    ]
    for shape, keys in checks:
        if any(k in text for k in keys):
            return shape
    return "other"


def product_visual_tags(row: sqlite3.Row | dict[str, Any]) -> str:
    base = []
    for key in ["slug", "name_es", "name_en", "subcategory", "search_terms", "category_key"]:
        try:
            val = row[key]
        except Exception:
            val = ""
        if val:
            base.append(str(val))
    shape = product_visual_shape(row)
    extras = {
        "shell": "shell shaped round sugar topping pan dulce",
        "pig": "pig animal molasses brown cookie",
        "heart": "heart shaped sprinkle sugar cookie",
        "ring": "round ring rosca arete",
        "filled": "filled stuffed fruit cream cajeta bavarian pumpkin pineapple apple",
        "flaky": "flaky puff pastry elephant ear hojaldre danish",
        "cookie": "cookie flat sugar sprinkles jam pecan watermelon",
        "slice": "slice square cake dessert tres leches",
        "cake": "cake party birthday quinceanera wedding custard flan dessert",
        "roll": "savory roll sandwich torta bolillo telera",
    }
    base.append(shape)
    base.append(extras.get(shape, "bakery case pan dulce"))
    return " ".join(base)


def product_completeness(row: sqlite3.Row | dict[str, Any], verification_status: str = "") -> int:
    get = row.get if isinstance(row, dict) else lambda k, default=None: row[k] if k in row.keys() else default
    score = 0
    score += 12 if get("name_es") else 0
    score += 10 if get("name_en") else 0
    score += 10 if get("description_es") else 0
    score += 10 if get("description_en") else 0
    score += 12 if get("base_price") is not None or get("order_mode") == "quote" else 0
    score += 12 if get("image_url") else 0
    score += 8 if get("search_terms") else 0
    score += 8 if get("allergen_notes") or get("ingredient_notes") else 0
    score += 8 if get("lead_time_hours") is not None else 0
    score += 10 if verification_status == "owner_verified" else 0
    return min(score, 100)


def seed_v3_extensions(con: sqlite3.Connection) -> None:
    """Idempotent v3 seed data that can run against an existing v2 database."""
    # Settings added after v2. These are scaffolds until production providers are configured.
    extra_settings = [
        ("payment_provider", "mock", "text", "Payment provider: mock, stripe, or square"),
        ("deposit_payment_mode", "mock_intent", "text", "Deposit collection mode for demos"),
        ("receipt_footer", "Thank you for supporting Juquilita Bakery. Gracias por su compra.", "text", "Receipt footer"),
        ("admin_order_alert_email", "Juquilitabakery@outlook.com", "text", "Owner email for order alerts"),
        ("admin_order_alert_phone", "(423) 307-9003", "text", "Text number for order alerts"),
        ("photos_required_before_launch", "true", "boolean", "Require real product photos before public launch"),
        ("owner_catalog_verified", "false", "boolean", "Owner has verified product master list"),
        ("pos_import_provider", "csv", "text", "Future POS import provider"),
        ("review_request_enabled", "false", "boolean", "Review request automation enabled"),
        ("delivery_enabled", "false", "boolean", "Delivery option enabled"),
    ]
    for key, value, value_type, label in extra_settings:
        con.execute(
            "INSERT OR IGNORE INTO settings(key,value,value_type,label,updated_at) VALUES(?,?,?,?,?)",
            (key, value, value_type, label, now_iso()),
        )

    # Catalog verification rows for every product.
    products = con.execute("SELECT id, slug, name_es, price_basis, photo_status FROM products").fetchall()
    for product in products:
        status = "needs_photo" if product["photo_status"] == "needs_real_photo" else "unverified"
        con.execute(
            """
            INSERT OR IGNORE INTO catalog_verifications(product_id,status,verified_by,source_name,source_url,source_notes,last_verified_at,next_review_at)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (
                product["id"], status, "", "Uploaded Juquilita menu and official Juquilita website",
                "https://www.juquilitabakerypyp.com/", product["price_basis"] or "Seeded from planning research.",
                "", (date.today() + timedelta(days=30)).isoformat(),
            ),
        )

    # Basic allergen vocabulary and automated mapping from product notes.
    allergens = [
        ("wheat", "Wheat", "Trigo", "Most breads contain wheat flour."),
        ("dairy", "Dairy", "Lácteos", "Many products use milk, butter, cream, or cheese."),
        ("egg", "Egg", "Huevo", "Pan de yema, cakes, custards, and many pastries use egg."),
        ("nuts", "Tree nuts", "Nueces", "Some cookies, cakes, and toppings may contain pecan or almond."),
        ("soy", "Soy", "Soya", "Possible in chocolate, shortening, or packaged toppings."),
    ]
    for row in allergens:
        con.execute("INSERT OR IGNORE INTO allergens(key,name_en,name_es,notes) VALUES(?,?,?,?)", row)
    for product in con.execute("SELECT id, allergen_notes FROM products").fetchall():
        notes = (product["allergen_notes"] or "").lower()
        for key, *_ in allergens:
            if key in notes or (key == "nuts" and ("pecan" in notes or "almond" in notes or "nuez" in notes)):
                con.execute("INSERT OR IGNORE INTO product_allergens(product_id,allergen_key,cross_contact) VALUES(?,?,1)", (product["id"], key))

    if con.execute("SELECT COUNT(*) AS n FROM suppliers").fetchone()["n"] == 0:
        suppliers = [
            ("Primary bakery dry goods supplier", "Owner to verify", "", "", 2, "TBD", "Flour, sugar, yeast, shortening, and packaging."),
            ("Dairy and produce supplier", "Owner to verify", "", "", 1, "TBD", "Milk, cream, eggs, fruit, and cake fillings."),
            ("Packaging and cake boards", "Owner to verify", "", "", 3, "TBD", "Boxes, bags, labels, boards, candles, and seasonal rosca packaging."),
        ]
        for row in suppliers:
            con.execute("INSERT INTO suppliers(name,contact_name,phone,email,lead_days,minimum_order,notes,updated_at) VALUES(?,?,?,?,?,?,?,?)", (*row, now_iso()))

    if con.execute("SELECT COUNT(*) AS n FROM ingredients").fetchone()["n"] == 0:
        ingredients = [
            ("All-purpose flour", "Harina", "lb", 250, 80), ("Sugar", "Azúcar", "lb", 160, 50),
            ("Eggs", "Huevos", "each", 360, 120), ("Milk", "Leche", "gal", 24, 8),
            ("Yeast", "Levadura", "lb", 12, 4), ("Shortening", "Manteca vegetal", "lb", 80, 25),
            ("Whipped topping", "Crema batida", "qt", 40, 12), ("Fruit filling", "Relleno de fruta", "lb", 60, 20),
            ("Cake boxes", "Cajas de pastel", "each", 140, 40), ("Bread bags", "Bolsas para pan", "each", 900, 250),
        ]
        for name_en, name_es, unit, qty, reorder in ingredients:
            con.execute("INSERT INTO ingredients(name_en,name_es,unit,current_qty,reorder_point,updated_at) VALUES(?,?,?,?,?,?)", (name_en, name_es, unit, qty, reorder, now_iso()))

    if con.execute("SELECT COUNT(*) AS n FROM seo_pages").fetchone()["n"] == 0:
        pages = [
            ("mexican-bakery-morristown-tn", "Mexican Bakery in Morristown, TN", "Order Oaxacan-style Mexican bread, pan dulce, tres leches cakes, flan, and seasonal breads in Morristown, Tennessee.", "Mexican bakery Morristown TN", "draft", "Local landing page with address, hours, bread gallery, pickup ordering, and cake quote CTA."),
            ("oaxacan-bread", "Oaxacan Bread and Pan de Yema", "Learn about Juquilita Bakery's Oaxacan-style pan amarillo, serrano bread, pan de yema, semitas, and seasonal breads.", "Oaxacan bread", "draft", "Education page explaining Oaxacan bread styles and pairing with Mexican hot chocolate."),
            ("tres-leches-cakes", "Tres Leches Cakes and Custom Cake Quotes", "Request tres leches cakes, fruit-filled sheet cakes, flan, chocoflan, and custom celebration cakes.", "tres leches cakes Morristown", "draft", "Cake form, flavor grid, fillings, quote expectations, deposit details."),
            ("rosca-de-reyes", "Rosca de Reyes Preorders", "Reserve Rosca de Reyes with size options, pickup windows, and hidden figurine planning.", "Rosca de Reyes Morristown", "draft", "Seasonal preorder page for January with explanation and pickup capacity."),
            ("pan-de-muerto", "Pan de Muerto Preorders", "Reserve sugar, pink sugar, or Oaxacan-style Pan de Muerto for Día de los Muertos.", "Pan de Muerto Morristown", "draft", "Seasonal preorder page for October and November."),
            ("custom-cakes", "Custom Cakes for Birthdays, Weddings, Quinceañeras, and Parties", "Submit cake inspiration, flavors, fillings, inscriptions, event date, and pickup details.", "custom cakes Morristown TN", "draft", "Custom cake workflow and gallery placeholder."),
        ]
        for row in pages:
            con.execute("INSERT INTO seo_pages(slug,title,meta_description,target_keyword,status,content_outline,updated_at) VALUES(?,?,?,?,?,?,?)", (*row, now_iso()))

    if con.execute("SELECT COUNT(*) AS n FROM content_blocks").fetchone()["n"] == 0:
        blocks = [
            ("homepage_announcement", "Seasonal preorder announcement", "Seasonal preorder windows can be opened here by the admin.", "Los administradores pueden abrir pedidos de temporada aquí.", "homepage"),
            ("pickup_instructions", "Pickup instructions", "Pickup is at 325 South Cumberland Street, Morristown, TN. Bring your order number and call or text if timing changes.", "Recoja en 325 South Cumberland Street, Morristown, TN. Traiga su número de pedido y llame o mande texto si cambia la hora.", "checkout"),
            ("cake_deposit_policy", "Cake deposit policy", "Large cakes, seasonal breads, and custom work may require a deposit before production starts.", "Pasteles grandes, panes de temporada y trabajos personalizados pueden requerir depósito antes de comenzar.", "quote"),
        ]
        for row in blocks:
            con.execute("INSERT INTO content_blocks(block_key,title,body_en,body_es,placement,is_active,updated_at) VALUES(?,?,?,?,?,1,?)", (*row, now_iso()))

    # Launch checklist generated from the 100-item execution backlog.
    checklist_titles = [
        ("NEXT-001","Owner verification meeting","P0"),("NEXT-002","Final product master list","P0"),("NEXT-003","Product grouping cleanup","P0"),("NEXT-004","Real product photos","P0"),("NEXT-005","Photo naming system","P0"),("NEXT-006","Product photo upload tool","P0"),("NEXT-007","Cake quote flow rebuild","P0"),("NEXT-008","Seasonal preorder flow","P0"),("NEXT-009","Deposit payment integration","P0"),("NEXT-010","Full payment option","P0"),("NEXT-011","Tax calculation verification","P0"),("NEXT-012","Receipt generation","P0"),("NEXT-013","Customer SMS confirmation","P0"),("NEXT-014","Customer email confirmation","P0"),("NEXT-015","Admin alert system","P0"),("NEXT-016","Business-hours enforcement audit","P0"),("NEXT-017","Pickup slot capacity design","P0"),("NEXT-018","Lead-time rules by product","P0"),("NEXT-019","Inventory method decision","P0"),("NEXT-020","Production ticket print view","P0"),("NEXT-021","Daily production summary printout","P0"),("NEXT-022","Admin order filters","P0"),("NEXT-023","Admin calendar view","P0"),("NEXT-024","Quote approval workflow","P0"),("NEXT-025","Quote-to-order conversion","P0"),("NEXT-026","Wholesale approval policy","P0"),("NEXT-027","Wholesale application review","P0"),("NEXT-028","Standing order builder","P0"),("NEXT-029","Standing order pause/resume","P0"),("NEXT-030","Real partner approval system","P0"),
        ("NEXT-031","Replace demo credentials","P1"),("NEXT-032","Password reset","P1"),("NEXT-033","Admin two-factor authentication","P1"),("NEXT-034","Staff roles","P1"),("NEXT-035","Remove public admin link","P1"),("NEXT-036","Production framework migration","P1"),("NEXT-037","Database migration system","P1"),("NEXT-038","PostgreSQL migration","P1"),("NEXT-039","Environment secrets","P1"),("NEXT-040","HTTPS deployment","P1"),("NEXT-041","Automated backups","P1"),("NEXT-042","Monitoring and error logging","P1"),("NEXT-043","Audit log viewer","P1"),("NEXT-044","Security testing","P1"),("NEXT-045","Accessibility audit","P1"),("NEXT-046","Mobile QA on real devices","P1"),("NEXT-047","Full Spanish translation review","P1"),("NEXT-048","Full English copy review","P1"),("NEXT-049","Search synonym expansion","P1"),("NEXT-050","Visual browsing mode","P1"),("NEXT-051","Product availability badges","P1"),("NEXT-052","Sold-out substitution prompts","P1"),("NEXT-053","Cart substitution approval","P1"),("NEXT-054","Checkout friction audit","P1"),("NEXT-055","One-click reorder","P1"),("NEXT-056","Customer order tracking page","P1"),("NEXT-057","Cancellation request flow","P1"),("NEXT-058","Order edit request flow","P1"),("NEXT-059","Pickup instructions","P1"),("NEXT-060","Store open/closed banner","P1"),
        ("NEXT-061","POS import path","P2"),("NEXT-062","Historical sales upload","P2"),("NEXT-063","Forecast confidence score","P2"),("NEXT-064","Weather integration","P2"),("NEXT-065","Local event calendar","P2"),("NEXT-066","Ingredient inventory","P2"),("NEXT-067","Ingredient forecasting","P2"),("NEXT-068","Supplier list","P2"),("NEXT-069","Cost of goods tracking","P2"),("NEXT-070","Promo margin warnings","P2"),("NEXT-071","Bundle builder","P2"),("NEXT-072","Product variant pricing","P2"),("NEXT-073","Cake decoration tiers","P2"),("NEXT-074","Reference image upload","P2"),("NEXT-075","Cake decorator notes","P2"),("NEXT-076","Cake production schedule","P2"),("NEXT-077","Wholesale invoice system","P2"),("NEXT-078","Wholesale payment terms","P2"),("NEXT-079","Wholesale price tiers","P2"),("NEXT-080","Wholesale minimums","P2"),("NEXT-081","Delivery option model","P2"),("NEXT-082","Product labels","P2"),("NEXT-083","Allergen management","P2"),("NEXT-084","Ingredient display policy","P2"),("NEXT-085","Nutrition policy","P2"),("NEXT-086","Multilocation readiness","P2"),("NEXT-087","Customer segmentation","P2"),("NEXT-088","Loyalty program","P2"),("NEXT-089","Abandoned cart recovery","P2"),("NEXT-090","Review request automation","P2"),
        ("NEXT-091","SEO pages","P3"),("NEXT-092","Google Business Profile alignment","P3"),("NEXT-093","Social media sharing cards","P3"),("NEXT-094","Seasonal campaign pages","P3"),("NEXT-095","Admin content editor","P3"),("NEXT-096","Image compression pipeline","P3"),("NEXT-097","Performance budget","P3"),("NEXT-098","Automated test expansion","P3"),("NEXT-099","User acceptance test script","P3"),("NEXT-100","Pilot launch plan","P3"),
    ]
    for code, title, priority in checklist_titles:
        status = "done" if code in {"NEXT-006","NEXT-012","NEXT-015","NEXT-020","NEXT-021","NEXT-024","NEXT-025","NEXT-028","NEXT-029","NEXT-030","NEXT-035","NEXT-043","NEXT-060","NEXT-066","NEXT-068","NEXT-083","NEXT-091","NEXT-095","NEXT-099"} else "todo"
        if code in {"NEXT-009","NEXT-010","NEXT-013","NEXT-014","NEXT-061","NEXT-062","NEXT-064","NEXT-065","NEXT-077","NEXT-078"}:
            status = "in_progress"
        con.execute("INSERT OR IGNORE INTO launch_checklist(code,title,priority,owner_role,status,notes,updated_at) VALUES(?,?,?,?,?,?,?)", (code, title, priority, "Owner/Admin", status, "Seeded from v3 implementation backlog.", now_iso()))

    if con.execute("SELECT COUNT(*) AS n FROM uat_scenarios").fetchone()["n"] == 0:
        scenarios = [
            ("Retail customer", "Find conchas by visual/search terms, add 12 to basket, choose a valid pickup slot, and submit pay-at-pickup order.", "Order is accepted, inventory decreases, receipt link works, notifications are queued."),
            ("Cake customer", "Submit decorated cake quote with flavor, filling, inscription, budget, event date, and reference URL.", "Quote enters admin queue with all required production details."),
            ("Admin", "Approve a quote with price and deposit, then convert it to an order.", "Order, payment intent, audit log, and customer notification are created."),
            ("Wholesale buyer", "Create or pause a standing order for bolillos and teleras.", "Standing order appears on account and admin operations views."),
            ("Bakery owner", "Review product verification dashboard and upload a real product image.", "Product image appears on storefront and verification status updates."),
            ("Cashier", "Print receipt and production ticket for a pickup order.", "Printable pages have order number, pickup time, balance, and item list."),
        ]
        for row in scenarios:
            con.execute("INSERT INTO uat_scenarios(role_name,scenario,expected_result,status,notes,updated_at) VALUES(?,?,?,?,?,?)", (*row, "untested", "", now_iso()))


def seed_v4_extensions(con: sqlite3.Connection) -> None:
    """Idempotent v4 seed data: customer self-service, costing, SEO publishing, local events, and growth tools."""
    extra_settings = [
        ("sales_tax_verified", "false", "boolean", "Owner/accountant verified tax rules"),
        ("password_reset_mode", "mock_outbox", "text", "Password reset mode for local prototype"),
        ("email_provider", "mock_outbox", "text", "Email provider configuration"),
        ("sms_provider", "mock_outbox", "text", "SMS provider configuration"),
        ("customer_change_window_hours", "12", "number", "Hours before pickup when customers may request changes"),
        ("loyalty_enabled", "true", "boolean", "Loyalty ledger enabled"),
        ("loyalty_points_per_dollar", "1", "number", "Points earned per dollar in demo mode"),
        ("delivery_enabled", "false", "boolean", "Delivery model enabled"),
        ("public_reviews_enabled", "true", "boolean", "Product review collection enabled"),
        ("label_printing_enabled", "true", "boolean", "Pickup bag/product label printing enabled"),
    ]
    for key, value, value_type, label in extra_settings:
        con.execute(
            "INSERT OR IGNORE INTO settings(key,value,value_type,label,updated_at) VALUES(?,?,?,?,?)",
            (key, value, value_type, label, now_iso()),
        )

    # Upgrade ingredient costing defaults. Costs are rough placeholders for margin simulations only.
    ingredient_costs = {
        "All-purpose flour": 0.62, "Sugar": 0.74, "Eggs": 0.23, "Milk": 3.75,
        "Yeast": 4.25, "Shortening": 1.58, "Whipped topping": 4.80,
        "Fruit filling": 2.35, "Cake boxes": 0.92, "Bread bags": 0.04,
    }
    for name, cost in ingredient_costs.items():
        try:
            con.execute("UPDATE ingredients SET cost_per_unit=? WHERE name_en=?", (cost, name))
        except sqlite3.OperationalError:
            pass

    # Attach simple recipe/cost maps for high-volume products. Owner must replace with true recipes.
    def ingredient_id(name: str) -> int | None:
        row = con.execute("SELECT id FROM ingredients WHERE name_en=?", (name,)).fetchone()
        return int(row["id"]) if row else None
    recipe_map = {
        "bolillo": [("All-purpose flour", 0.14), ("Yeast", 0.004), ("Sugar", 0.008), ("Bread bags", 0.03)],
        "telera": [("All-purpose flour", 0.16), ("Yeast", 0.004), ("Sugar", 0.01), ("Bread bags", 0.03)],
        "concha": [("All-purpose flour", 0.15), ("Sugar", 0.04), ("Eggs", 0.15), ("Shortening", 0.035), ("Bread bags", 0.04)],
        "marranito": [("All-purpose flour", 0.13), ("Sugar", 0.035), ("Eggs", 0.10), ("Bread bags", 0.04)],
        "empanada-bavaria": [("All-purpose flour", 0.12), ("Sugar", 0.03), ("Eggs", 0.12), ("Fruit filling", 0.06), ("Bread bags", 0.04)],
        "tres-leches-rebanada": [("All-purpose flour", 0.11), ("Sugar", 0.07), ("Eggs", 0.45), ("Milk", 0.04), ("Whipped topping", 0.08)],
        "pastel-cuarto": [("All-purpose flour", 1.8), ("Sugar", 1.2), ("Eggs", 18), ("Milk", 0.9), ("Whipped topping", 1.5), ("Fruit filling", 1.2), ("Cake boxes", 1)],
    }
    for slug, parts in recipe_map.items():
        prow = con.execute("SELECT id FROM products WHERE slug=?", (slug,)).fetchone()
        if not prow:
            continue
        for name, qty in parts:
            iid = ingredient_id(name)
            if iid:
                con.execute("INSERT OR IGNORE INTO product_ingredients(product_id,ingredient_id,qty_per_unit) VALUES(?,?,?)", (prow["id"], iid, qty))

    if con.execute("SELECT COUNT(*) AS n FROM delivery_zones").fetchone()["n"] == 0:
        zones = [
            ("Pickup only", "Morristown", 0, 0, "disabled", "Default launch mode. Pickup is safer until staffing and delivery routes are verified."),
            ("Morristown wholesale route", "Morristown", 150, 0, "quote_only", "Possible future delivery for approved premium buyers."),
            ("Nearby event delivery", "Hamblen County", 250, 25, "quote_only", "Owner approval required for cakes and event trays."),
        ]
        for row in zones:
            con.execute("INSERT INTO delivery_zones(name,city,min_order,fee,status,notes,updated_at) VALUES(?,?,?,?,?,?,?)", (*row, now_iso()))

    if con.execute("SELECT COUNT(*) AS n FROM local_events").fetchone()["n"] == 0:
        year = date.today().year
        events = [
            ("Graduation cake season", f"{year}-05-15", "school", "high", 1.35, "Promote cake quote lead times and pickup slot capacity."),
            ("Weekend breakfast rush", f"{year}-06-06", "weekly", "medium", 1.18, "Increase bolillo, telera, concha, and coffee-pairing bread prep."),
            ("Quinceañera and party season", f"{year}-07-12", "community", "high", 1.28, "Watch custom cake queue and decorator capacity."),
            ("Día de los Muertos preorder window", f"{year}-10-15", "seasonal", "very_high", 1.75, "Open Pan de Muerto campaign pages and deposit workflow."),
        ]
        for row in events:
            con.execute("INSERT INTO local_events(title,event_date,event_type,expected_impact,demand_multiplier,notes,is_active,updated_at) VALUES(?,?,?,?,?,?,1,?)", (*row, now_iso()))

    if con.execute("SELECT COUNT(*) AS n FROM weather_adjustments").fetchone()["n"] == 0:
        weather = [
            ("Heavy rain", "rain", 0.88, "all", "Expect lower walk-in traffic; push pickup reminders and reduce fragile pastry overproduction."),
            ("Cold morning", "cold", 1.12, "breads,desserts", "Hot chocolate pairings and pan de yema may move faster."),
            ("Snow or school closure", "snow", 0.70, "all", "Reduce same-day production unless preorders are strong."),
            ("Holiday week", "holiday", 1.45, "seasonal,cakes,breads", "Increase preorder messaging, packaging, and pickup staffing."),
        ]
        for row in weather:
            con.execute("INSERT INTO weather_adjustments(label,condition_key,demand_multiplier,categories,prep_notes,is_active,updated_at) VALUES(?,?,?,?,?,1,?)", (*row, now_iso()))

    templates = [
        ("order_received_email", "email", "Juquilita order received", "Your order {{order_code}} was received for {{pickup_date}} at {{pickup_time}}."),
        ("order_ready_sms", "sms", "Order ready", "Juquilita Bakery: your order {{order_code}} is ready for pickup."),
        ("quote_offer_email", "email", "Juquilita quote ready", "Your bakery quote {{quote_code}} is ready. Deposit required: {{deposit}}."),
        ("change_request_admin", "admin", "Customer change request", "Review change request for {{order_code}}."),
        ("review_request_email", "email", "How was your bread?", "Tell us how your Juquilita order tasted and help improve the menu."),
    ]
    for row in templates:
        con.execute("INSERT OR IGNORE INTO notification_templates(template_key,channel,subject,body,is_active,updated_at) VALUES(?,?,?,?,1,?)", (*row, now_iso()))

    # Publish core SEO pages in the prototype so the storefront can link to real landing pages.
    for slug in ["mexican-bakery-morristown-tn", "oaxacan-bread", "tres-leches-cakes", "rosca-de-reyes", "pan-de-muerto", "custom-cakes"]:
        con.execute("UPDATE seo_pages SET status='published', updated_at=? WHERE slug=?", (now_iso(), slug))

    # Sample approved reviews to prove the review flow. These remain demo-labelled in body text.
    if con.execute("SELECT COUNT(*) AS n FROM product_reviews").fetchone()["n"] == 0:
        samples = [("concha", "Demo customer", "demo-review@example.test", 5, "Soft and fresh", "Demo review: conchas were easy to find in the app and pickup was clear."),
                   ("tres-leches-rebanada", "Demo customer", "demo-review@example.test", 5, "Great cake slice", "Demo review: tres leches description and price were clear."),]
        for slug, name, email, rating, title, body in samples:
            prow = con.execute("SELECT id FROM products WHERE slug=?", (slug,)).fetchone()
            con.execute("INSERT INTO product_reviews(product_id,customer_name,customer_email,rating,title,body,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?, ?,?)", (prow["id"] if prow else None, name, email, rating, title, body, "approved", now_iso(), now_iso()))

    # Backfill loyalty points for seeded completed orders with user accounts.
    if con.execute("SELECT COUNT(*) AS n FROM loyalty_ledger").fetchone()["n"] == 0:
        for order in con.execute("SELECT id,user_id,total,order_code FROM orders WHERE user_id IS NOT NULL AND status='completed'").fetchall():
            points = int(round(float(order["total"] or 0)))
            if points:
                con.execute("INSERT INTO loyalty_ledger(user_id,order_id,points,reason,created_at) VALUES(?,?,?,?,?)", (order["user_id"], order["id"], points, f"Seeded points from {order['order_code']}", now_iso()))

    # Show additional backlog progress in v4.
    done_codes = {"NEXT-032", "NEXT-052", "NEXT-055", "NEXT-057", "NEXT-058", "NEXT-063", "NEXT-065", "NEXT-067", "NEXT-069", "NEXT-070", "NEXT-071", "NEXT-077", "NEXT-082", "NEXT-088", "NEXT-090", "NEXT-093", "NEXT-094", "NEXT-096"}
    for code in done_codes:
        con.execute("UPDATE launch_checklist SET status='in_progress', notes=?, updated_at=? WHERE code=? AND status!='done'", ("v4 adds functional scaffold or demo implementation for this item.", now_iso(), code))


def seed_v5_extensions(con: sqlite3.Connection) -> None:
    """Idempotent v5 seed data for live integrations, staff permissions, QA, backups, recipes, and photos."""
    settings = [
        ("payment_provider", os.environ.get("JB_PAYMENT_PROVIDER", "mock"), "text", "Payment provider: mock, stripe, or square"),
        ("stripe_webhook_required", "true", "boolean", "Use Stripe webhook events before marking provider payments paid"),
        ("square_environment", os.environ.get("SQUARE_ENV", "sandbox"), "text", "Square environment: sandbox or production"),
        ("sendgrid_enabled", "false", "boolean", "Enable SendGrid email delivery when API keys are configured"),
        ("twilio_sms_enabled", "false", "boolean", "Enable Twilio SMS delivery when credentials are configured"),
        ("password_reset_token_minutes", "120", "number", "Password reset link lifetime in minutes"),
        ("admin_2fa_required", "false", "boolean", "Require 2FA for all staff/admin accounts after setup"),
        ("staff_permissions_enabled", "true", "boolean", "Use staff permission checks for admin operations"),
        ("backup_retention_days", "30", "number", "Local backup retention window"),
        ("monitoring_contact_email", os.environ.get("JB_MONITORING_EMAIL", "Juquilitabakery@outlook.com"), "text", "Monitoring alert recipient"),
        ("accessibility_target", "WCAG 2.2 AA", "text", "Accessibility QA target"),
        ("mobile_qa_breakpoints", "360,390,430,768,1024", "text", "Mobile/tablet QA widths"),
    ]
    for key, value, value_type, label in settings:
        con.execute("INSERT OR IGNORE INTO settings(key,value,value_type,label,updated_at) VALUES(?,?,?,?,?)", (key, value, value_type, label, now_iso()))
    env_setting_overrides = {
        "payment_provider": os.environ.get("JB_PAYMENT_PROVIDER"),
        "square_environment": os.environ.get("SQUARE_ENV"),
        "monitoring_contact_email": os.environ.get("JB_MONITORING_EMAIL"),
    }
    for key, value in env_setting_overrides.items():
        if value:
            con.execute("UPDATE settings SET value=?, updated_at=? WHERE key=?", (value, now_iso(), key))

    permissions = [
        ("admin:*", "Owner all access", "system", "Can perform every admin action."),
        ("admin:dashboard", "View dashboard", "system", "Can open the admin dashboard."),
        ("orders:manage", "Manage orders", "orders", "Can update order statuses and production queue."),
        ("catalog:manage", "Manage catalog", "catalog", "Can edit products, variants, bundles, inventory, and availability."),
        ("catalog:verify", "Verify catalog", "catalog", "Can mark owner verification status."),
        ("photos:manage", "Manage photos", "catalog", "Can upload and approve product photos."),
        ("quotes:manage", "Manage quotes", "quotes", "Can reply to and convert quotes."),
        ("finance:manage", "Manage payments and invoices", "finance", "Can mark payments and create invoices."),
        ("notifications:manage", "Manage notification statuses", "communications", "Can update outbox statuses."),
        ("notifications:send", "Send notification queue", "communications", "Can send queued email/SMS through providers."),
        ("wholesale:manage", "Manage wholesale", "wholesale", "Can approve applications and standing orders."),
        ("marketing:manage", "Manage promotions", "marketing", "Can create promotions and campaigns."),
        ("partners:manage", "Manage partner showcase", "marketing", "Can publish partner cards after consent."),
        ("forecast:manage", "Manage forecast inputs", "operations", "Can edit seasonal events, local events, and weather rules."),
        ("settings:manage", "Manage hours and settings", "system", "Can edit store settings, hours, closures."),
        ("content:manage", "Manage SEO/content", "marketing", "Can edit SEO pages and content blocks."),
        ("launch:manage", "Manage launch checklist", "system", "Can update launch readiness items."),
        ("opsdata:manage", "Manage POS data", "operations", "Can stage/import POS CSV rows."),
        ("recipes:manage", "Manage recipes", "recipes", "Can edit recipe ingredient quantities."),
        ("recipes:verify", "Verify recipes", "recipes", "Can owner-verify recipe cards/yields."),
        ("suppliers:manage", "Manage suppliers", "suppliers", "Can edit suppliers and supplier price quotes."),
        ("customers:manage", "Manage customers", "customers", "Can moderate reviews and change requests."),
        ("qa:manage", "Manage QA", "qa", "Can record accessibility/mobile/security/performance audits."),
        ("staff:manage", "Manage staff", "staff", "Can create staff and assign permissions."),
        ("system:backup", "Run backups", "system", "Can create local SQLite backups."),
    ]
    for row in permissions:
        con.execute("INSERT OR IGNORE INTO permission_catalog(permission_key,label,category,description) VALUES(?,?,?,?)", row)

    roles = [
        ("owner", "Owner", "Full access to business, finance, security, and launch controls.", ["admin:*"]),
        ("manager", "Manager", "Daily operations, catalog, orders, promotions, and staff workflow.", ["admin:dashboard","orders:manage","catalog:manage","catalog:verify","photos:manage","quotes:manage","wholesale:manage","marketing:manage","partners:manage","forecast:manage","settings:manage","content:manage","launch:manage","customers:manage","notifications:manage","notifications:send","qa:manage"]),
        ("cashier", "Cashier", "Order queue, receipts, customer requests, and notification outbox.", ["admin:dashboard","orders:manage","customers:manage","notifications:manage"]),
        ("baker", "Baker", "Production queue, inventory visibility, recipes, and forecast input.", ["admin:dashboard","orders:manage","catalog:manage","recipes:manage","forecast:manage"]),
        ("decorator", "Cake decorator", "Cake quotes, cake production, product photos, and recipe notes.", ["admin:dashboard","quotes:manage","photos:manage","recipes:manage","recipes:verify"]),
        ("wholesale_manager", "Wholesale manager", "Wholesale buyers, standing orders, invoices, and partner cards.", ["admin:dashboard","wholesale:manage","orders:manage","finance:manage","partners:manage","notifications:manage","notifications:send"]),
    ]
    for role_key, label, desc, role_perms in roles:
        con.execute("INSERT OR IGNORE INTO staff_roles(role_key,label,description) VALUES(?,?,?)", (role_key, label, desc))
        for perm in role_perms:
            con.execute("INSERT OR IGNORE INTO staff_role_permissions(role_key,permission_key) VALUES(?,?)", (role_key, perm))

    admin_email = os.environ.get("JB_ADMIN_EMAIL", "admin@juquilita.local" if not production_mode() else "").lower()
    admin = con.execute("SELECT id FROM users WHERE lower(email)=lower(?)", (admin_email,)).fetchone() if admin_email else None
    if admin:
        con.execute("INSERT OR IGNORE INTO staff_permissions(user_id,permission_key,granted_by,created_at) VALUES(?,?,?,?)", (admin["id"], "admin:*", admin["id"], now_iso()))
        con.execute("INSERT OR IGNORE INTO user_staff_roles(user_id,role_key,assigned_by,created_at) VALUES(?,?,?,?)", (admin["id"], "owner", admin["id"], now_iso()))
    if not production_mode():
        demo_staff = [
            ("cashier@juquilita.local", "CashierPass2026!", "Demo Cashier", "cashier", "423-555-0201", "cashier"),
            ("baker@juquilita.local", "BakerPass2026!", "Demo Baker", "baker", "423-555-0202", "baker"),
            ("decorator@juquilita.local", "DecoratorPass2026!", "Demo Cake Decorator", "decorator", "423-555-0203", "decorator"),
        ]
        for email, password, name, role, phone, role_key in demo_staff:
            if not con.execute("SELECT 1 FROM users WHERE lower(email)=lower(?)", (email,)).fetchone():
                uid = seed_user(con, email, password, name, role, "Juquilita Bakery", phone, role_key)
                con.execute("INSERT OR IGNORE INTO user_staff_roles(user_id,role_key,assigned_by,created_at) VALUES(?,?,?,?)", (uid, role_key, admin["id"] if admin else None, now_iso()))

    # Create a photo shot list row for every product still missing a verified real photo.
    for product in con.execute("SELECT id,slug,name_es,name_en,category_key FROM products WHERE is_active=1 AND (photo_status!='real_photo_verified' OR image_url='')").fetchall():
        priority = "P0" if product["category_key"] in {"breads", "sweet_breads", "cakes", "seasonal"} else "P1"
        instructions = f"Shoot {product['name_es']} / {product['name_en']} on a clean bakery tray, 45-degree angle, one close crop, one case-context shot, no stock photos. File name: {product['slug']}-001.jpg."
        con.execute("INSERT OR IGNORE INTO photo_shot_list(product_id,shot_type,priority,status,instructions,due_on,assigned_to,updated_at) VALUES(?,?,?,?,?,?,?,?)", (product["id"], "primary product photo", priority, "needed", instructions, (date.today()+timedelta(days=14)).isoformat(), "Owner/Admin", now_iso()))

    # Recipe verification placeholders for products with ingredient links.
    for row in con.execute("SELECT DISTINCT product_id FROM product_ingredients").fetchall():
        con.execute("INSERT OR IGNORE INTO recipe_verifications(product_id,recipe_version,yield_qty,yield_unit,labor_minutes,owner_verified,notes,updated_at) VALUES(?,?,?,?,?,?,?,?)", (row["product_id"], "v1", 1, "each", 0, 0, "Owner must verify actual batch yield, labor, and ingredient quantities before using margin report for pricing.", now_iso()))

    # Seed planned QA runs and actionable manual checks.
    qa_seed = [
        ("accessibility", "WCAG 2.2 AA manual + Lighthouse", "/", "planned", "Run keyboard, screen reader, labels, focus, contrast, forms, and cart drawer checks."),
        ("mobile", "Real device QA", "/", "planned", "Test iPhone/Android checkout, cart, product filters, account, and admin tables."),
        ("security", "OWASP manual smoke test", "/admin.html", "planned", "Test login throttling, CSRF, staff permissions, reset links, and 2FA."),
        ("performance", "Lighthouse + image budget", "/", "planned", "Run after real product photos are uploaded and compressed."),
    ]
    if con.execute("SELECT COUNT(*) AS n FROM qa_audit_runs").fetchone()["n"] == 0:
        for audit_type, tool, target, status, summary in qa_seed:
            cur = con.execute("INSERT INTO qa_audit_runs(audit_type,tool_name,target_url,status,summary,created_at) VALUES(?,?,?,?,?,?)", (audit_type, tool, target, status, summary, now_iso()))
            run_id = int(cur.lastrowid)
            if audit_type == "accessibility":
                items = ["keyboard-order", "visible-focus", "form-labels", "modal-focus-trap", "alt-text", "color-contrast", "language-toggle", "error-message-announcements"]
            elif audit_type == "mobile":
                items = ["360px-checkout", "390px-cart-drawer", "430px-product-grid", "admin-table-scroll", "touch-targets", "pickup-time-form"]
            elif audit_type == "security":
                items = ["admin-2fa", "password-reset-expiry", "csrf-mutations", "staff-role-boundaries", "demo-credential-removal"]
            else:
                items = ["image-compression", "largest-contentful-paint", "script-size", "database-query-count"]
            for key in items:
                con.execute("INSERT INTO qa_audit_items(run_id,audit_type,check_key,status,severity,notes,updated_at) VALUES(?,?,?,?,?,?,?)", (run_id, audit_type, key, "todo", "high" if key in {"admin-2fa","visible-focus","form-labels","360px-checkout"} else "medium", "Seeded v5 readiness check.", now_iso()))

    # Mark backlog items that v5 materially advances.
    v5_items = ["NEXT-009","NEXT-010","NEXT-013","NEXT-014","NEXT-032","NEXT-033","NEXT-034","NEXT-040","NEXT-041","NEXT-042","NEXT-045","NEXT-046","NEXT-066","NEXT-067","NEXT-068","NEXT-069"]
    for code in v5_items:
        con.execute("UPDATE launch_checklist SET status=CASE WHEN status='done' THEN status ELSE 'in_progress' END, notes=?, updated_at=? WHERE code=?", ("v5 adds production adapter, workflow, endpoint, or QA scaffold for this item. Owner credentials and live service setup still required.", now_iso(), code))


def seed_v6_extensions(con: sqlite3.Connection) -> None:
    """Idempotent v6 data for bakery-case UX, privacy, seasonal campaigns, production boards, and launch mode."""
    v6_settings = [
        ("public_requires_owner_verified", "false", "boolean", "Hide non-verified products from public ordering when true"),
        ("phase_one_launch_mode", "true", "boolean", "Keep public launch focused on core order, quote, receipt, notification, and production workflows"),
        ("receipt_email_required", "true", "boolean", "Require tracking verification before exposing private receipt links"),
        ("default_substitution_preference", "call_me", "text", "Default substitution behavior: call_me, similar_ok, refund_item"),
        ("guest_checkout_primary", "true", "boolean", "Keep guest checkout prominent"),
        ("apple_google_pay_planned", "square_requires_https", "text", "Square wallet options require HTTPS and provider setup"),
        ("sms_10dlc_registration_status", "not_started", "text", "A2P 10DLC status for Twilio SMS launch"),
        ("core_web_vitals_budget", "LCP<=2.5s;INP<=200ms;CLS<=0.1", "text", "Performance launch budget"),
    ]
    for key, value, value_type, label in v6_settings:
        con.execute("INSERT OR IGNORE INTO settings(key,value,value_type,label,updated_at) VALUES(?,?,?,?,?)", (key, value, value_type, label, now_iso()))

    for p in con.execute("SELECT id, slug, name_es, name_en, category_key, subcategory, search_terms FROM products WHERE is_active=1").fetchall():
        shape = product_visual_shape(p)
        tags = product_visual_tags(p)
        con.execute("UPDATE products SET visual_shape=COALESCE(NULLIF(visual_shape,''),?), visual_tags=COALESCE(NULLIF(visual_tags,''),?), public_status=COALESCE(NULLIF(public_status,''),'public') WHERE id=?", (shape, tags, p["id"]))

    campaigns = [
        ("pan-de-muerto", "Pan de Muerto preorder", "Preventa de Pan de Muerto", f"{date.today().year}-10-01", f"{date.today().year}-11-03", f"{date.today().year}-10-27", "Pickup waves should be configured for Oct 31, Nov 1, and Nov 2. Track sugar, pink sugar, and Oaxacan yema face styles separately.", 350, "active", "Seasonal Day of the Dead bread with white sugar, pink sugar, and Oaxacan yema face styles.", "Pan tradicional de Día de Muertos con azúcar blanca, azúcar rosa y pan de yema oaxaqueño con carita."),
        ("rosca-de-reyes", "Rosca de Reyes preorder", "Preventa de Rosca de Reyes", f"{date.today().year+1}-01-01", f"{date.today().year+1}-01-07", f"{date.today().year+1}-01-03", "Configure small, medium, and large rosca sizes with figurine counts and pickup waves before January 6.", 250, "draft", "Rosca made with egg-yolk dough, candied citrus fruit, and figurine planning by size.", "Rosca hecha con masa de pan de yema, fruta cristalizada y figuras según tamaño."),
    ]
    for c in campaigns:
        con.execute("""
            INSERT OR IGNORE INTO seasonal_campaigns(slug,title_en,title_es,season_start,season_end,preorder_cutoff,pickup_window_notes,max_orders,status,story_en,story_es,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (*c, now_iso()))
    for campaign in con.execute("SELECT id, slug, preorder_cutoff FROM seasonal_campaigns").fetchall():
        if con.execute("SELECT COUNT(*) AS n FROM seasonal_pickup_windows WHERE campaign_id=?", (campaign["id"],)).fetchone()["n"] == 0:
            base_date = campaign["preorder_cutoff"]
            for starts, ends, cap in [("07:00","10:00",60),("10:00","13:00",70),("13:00","17:00",70)]:
                con.execute("INSERT INTO seasonal_pickup_windows(campaign_id,pickup_date,starts_at,ends_at,capacity,reserved,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (campaign["id"], base_date, starts, ends, cap, 0, "open", "Seeded v6 planning window. Owner must adjust dates and capacities.", now_iso(), now_iso()))

    # Seed today's and tomorrow's bakery case batches for highly visible items.
    batch_slugs = ["bolillo", "telera", "concha", "marranito", "oreja", "churro-simple", "empanada-pina", "tres-leches-slice"]
    for slug in batch_slugs:
        product = con.execute("SELECT id FROM products WHERE slug=?", (slug,)).fetchone()
        if not product:
            continue
        for day_offset, label, ready, qty in [(0,"morning case","07:00",80),(0,"midday refresh","12:00",50),(1,"tomorrow morning","07:00",80)]:
            batch_date = (date.today()+timedelta(days=day_offset)).isoformat()
            if not con.execute("SELECT 1 FROM product_batches WHERE product_id=? AND batch_date=? AND batch_label=?", (product["id"], batch_date, label)).fetchone():
                con.execute("INSERT INTO product_batches(product_id,batch_date,batch_label,expected_ready_at,produced_qty,reserved_qty,sold_qty,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (product["id"], batch_date, label, ready, qty, 0, 0, "ready" if day_offset == 0 and ready <= "12:00" else "planned", "Seeded bakery-case batch planning row.", now_iso(), now_iso()))

    # Seed a demo wholesale standing order so the generation workflow has realistic local data.
    premium_user = None if production_mode() else con.execute("SELECT id FROM users WHERE email='wholesale@taqueria.local'").fetchone()
    if premium_user and not con.execute("SELECT 1 FROM standing_orders WHERE user_id=? AND name=?", (premium_user["id"], "Friday bolillo and concha pack")).fetchone():
        cur = con.execute("INSERT INTO standing_orders(user_id,business_name,name,weekday,pickup_time,notes,is_active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (premium_user["id"], "Demo Taqueria", "Friday bolillo and concha pack", 4, "07:00", "Demo standing order for wholesale run generation. Replace with an approved real business order before launch.", 1, now_iso(), now_iso()))
        standing_id = int(cur.lastrowid)
        for slug, qty in [("bolillo", 60), ("telera", 24), ("concha", 24)]:
            product = con.execute("SELECT id FROM products WHERE slug=?", (slug,)).fetchone()
            if product:
                con.execute("INSERT INTO standing_order_items(standing_order_id,product_id,quantity,variant_summary) VALUES(?,?,?,?)", (standing_id, product["id"], qty, ""))

    # Consent-first partner approval example remains unpublished until a real partner approves copy.
    for partner in con.execute("SELECT id,name,contact_email,has_consent,story FROM partners WHERE has_consent=1").fetchall():
        con.execute("INSERT OR IGNORE INTO partner_approvals(partner_id,approval_type,approved_by_name,approved_by_email,approval_date,approved_copy,rights_notes,created_at) VALUES(?,?,?,?,?,?,?,?)", (partner["id"], "public_showcase", partner["name"], partner["contact_email"] or "", today_str(), partner["story"], "v6 consent record seeded from partner consent flag. Replace with signed/emailed approval before public launch.", now_iso()))

    # Tighten launch checklist notes for the v6 focus.
    v6_items = ["NEXT-001","NEXT-002","NEXT-004","NEXT-007","NEXT-008","NEXT-020","NEXT-021","NEXT-028","NEXT-030","NEXT-045","NEXT-046","NEXT-050","NEXT-051","NEXT-053","NEXT-056","NEXT-060","NEXT-087","NEXT-091","NEXT-094","NEXT-096","NEXT-100"]
    for code in v6_items:
        con.execute("UPDATE launch_checklist SET status=CASE WHEN status='done' THEN status ELSE 'in_progress' END, notes=?, updated_at=? WHERE code=?", ("v6 adds customer-facing bakery-case UX, receipt privacy, campaign windows, production tasks, or launch-mode controls. Requires owner/photo/provider validation before public launch.", now_iso(), code))


def apply_imported_site_images(con: sqlite3.Connection) -> None:
    manifest_path = PUBLIC_DIR / "imported" / "website" / "manifest.json"
    if not manifest_path.exists():
        apply_product_image_map(con, PUBLIC_DIR)
        return
    manifest = load_json(manifest_path.read_text(encoding="utf-8"), {})
    imported_at = clean_text(manifest.get("imported_at") or now_iso(), 40)
    image_source = "relabel_import" if manifest.get("source") == "juquilita_relabel_output" else "old_website_import"
    for image in manifest.get("images", []):
        product_slug = clean_text(image.get("product_slug"), 140)
        local_url = clean_text(image.get("local_url"), 500)
        if not product_slug or not local_url:
            continue
        local_path = (PUBLIC_DIR / local_url.lstrip("/")).resolve()
        if not str(local_path).startswith(str(PUBLIC_DIR.resolve())) or not local_path.exists():
            continue
        product = con.execute("SELECT id,image_url FROM products WHERE slug=?", (product_slug,)).fetchone()
        if not product:
            continue
        alt_text = clean_text(image.get("alt_text") or image.get("label") or product_slug, 300)
        exists = con.execute("SELECT 1 FROM product_images WHERE product_id=? AND image_url=?", (product["id"], local_url)).fetchone()
        is_primary = 1 if not product["image_url"] or product["image_url"] == local_url else 0
        if not exists:
            con.execute(
                """
                INSERT INTO product_images(product_id,image_url,alt_text,image_status,source,is_primary,sort_order,uploaded_by,uploaded_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (product["id"], local_url, alt_text, "approved", image_source, is_primary, parse_int(image.get("sort_order") or 100, "sort order", min_value=0, max_value=10000), None, imported_at),
            )
        if is_primary:
            con.execute("UPDATE products SET image_url=?, image_alt=?, photo_status='real_photo_verified', updated_at=? WHERE id=?", (local_url, alt_text, imported_at, product["id"]))
            con.execute("UPDATE photo_shot_list SET status='approved', updated_at=? WHERE product_id=? AND status!='approved'", (imported_at, product["id"]))
    apply_product_image_map(con, PUBLIC_DIR)


def init_db(force: bool = False) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if force and DB_PATH.exists():
        DB_PATH.unlink()
    with connect() as con:
        con.executescript(read_schema())
        ensure_v6_schema(con)
        row = con.execute("SELECT COUNT(*) AS n FROM products").fetchone()
        if row["n"] == 0:
            seed_database(con)
        seed_v3_extensions(con)
        seed_v4_extensions(con)
        seed_v5_extensions(con)
        seed_v6_extensions(con)
        apply_imported_site_images(con)


def seed_user(con: sqlite3.Connection, email: str, password: str, name: str, role: str,
              business_name: str = "", phone: str = "", wholesale_tier: str = "retail") -> int:
    password_hash, salt = hash_password(password)
    cur = con.execute(
        """
        INSERT INTO users(email,password_hash,salt,name,role,business_name,phone,wholesale_tier,is_active,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,1,?,?)
        """,
        (email.lower(), password_hash, salt, name, role, business_name, phone, wholesale_tier, now_iso(), now_iso()),
    )
    return int(cur.lastrowid)


def seed_database(con: sqlite3.Connection) -> None:
    for row in seeds.CATEGORIES:
        con.execute(
            "INSERT INTO categories(key,name_en,name_es,sort_order,description_en,description_es) VALUES(?,?,?,?,?,?)",
            (row["key"], row["name_en"], row["name_es"], row["sort_order"], row["description_en"], row["description_es"]),
        )
    for row in seeds.SETTINGS:
        con.execute(
            "INSERT INTO settings(key,value,value_type,label,updated_at) VALUES(?,?,?,?,?)",
            (row["key"], row["value"], row["value_type"], row["label"], now_iso()),
        )
    for row in seeds.BUSINESS_HOURS:
        con.execute(
            """
            INSERT INTO business_hours(weekday,day_en,day_es,opens_at,closes_at,slot_capacity,is_closed,profile,updated_at)
            VALUES(?,?,?,?,?,?,0,?,?)
            """,
            (row["weekday"], row["day_en"], row["day_es"], row["opens_at"], row["closes_at"], row["slot_capacity"], row["profile"], now_iso()),
        )

    product_ids: dict[str, int] = {}
    for item in seeds.PRODUCTS:
        cur = con.execute(
            """
            INSERT INTO products(
                slug,name_es,name_en,category_key,subcategory,description_es,description_en,base_price,wholesale_price,unit,
                stock_count,stock_policy,lead_time_hours,order_mode,is_featured,is_bulk_friendly,is_seasonal,season_start,season_end,
                search_terms,image_url,image_alt,image_accent,icon,photo_status,price_basis,allergen_notes,ingredient_notes,margin_estimate,
                is_active,created_at,updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)
            """,
            (
                item["slug"], item["name_es"], item["name_en"], item["category_key"], item["subcategory"],
                item["description_es"], item["description_en"], item["base_price"], item["wholesale_price"], item["unit"],
                item["stock_count"], item["stock_policy"], item["lead_time_hours"], item["order_mode"], item["is_featured"],
                item["is_bulk_friendly"], item["is_seasonal"], item["season_start"], item["season_end"], item["search_terms"],
                "", f"{item['name_es']} / {item['name_en']}", item["image_accent"], item["icon"], item["photo_status"], item["price_basis"],
                item["allergen_notes"], item["ingredient_notes"], item["margin_estimate"], now_iso(), now_iso(),
            ),
        )
        product_ids[item["slug"]] = int(cur.lastrowid)

    sort_by_product: dict[str, int] = {}
    for variant in seeds.VARIANTS:
        product_id = product_ids.get(variant["product_slug"])
        if not product_id:
            continue
        sort_by_product[variant["product_slug"]] = sort_by_product.get(variant["product_slug"], 0) + 10
        con.execute(
            """
            INSERT INTO product_variants(product_id,variant_type,name_es,name_en,price_delta,wholesale_delta,is_default,sort_order)
            VALUES(?,?,?,?,?,?,?,?)
            """,
            (product_id, variant["variant_type"], variant["name_es"], variant["name_en"], variant["price_delta"], variant["wholesale_delta"], variant["is_default"], sort_by_product[variant["product_slug"]]),
        )

    for bundle in seeds.BUNDLES:
        con.execute(
            "INSERT INTO bundles(slug,name_en,name_es,description_en,description_es,items_json,sort_order,is_active) VALUES(?,?,?,?,?,?,?,1)",
            (bundle["slug"], bundle["name_en"], bundle["name_es"], bundle["description_en"], bundle["description_es"], bundle["items_json"], bundle["sort_order"]),
        )
    for promo in seeds.PROMOTIONS:
        con.execute(
            """
            INSERT INTO promotions(title,code,discount_type,discount_value,min_subtotal,applies_to_role,category_key,starts_on,ends_on,is_active,max_redemptions,per_customer_limit,auto_apply,notes,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (promo["title"], promo["code"], promo["discount_type"], promo["discount_value"], promo["min_subtotal"], promo["applies_to_role"], promo["category_key"], promo["starts_on"], promo["ends_on"], promo["is_active"], promo["max_redemptions"], promo["per_customer_limit"], promo["auto_apply"], promo["notes"], now_iso(), now_iso()),
        )
    for partner in seeds.PARTNERS:
        con.execute(
            """
            INSERT INTO partners(name,category,city,website,contact_name,contact_email,phone,story,highlight,public_visible,has_consent,monthly_volume_estimate,is_demo,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (partner["name"], partner["category"], partner["city"], partner["website"], partner["contact_name"], partner["contact_email"], partner["phone"], partner["story"], partner["highlight"], partner["public_visible"], partner["has_consent"], partner["monthly_volume_estimate"], partner["is_demo"], now_iso(), now_iso()),
        )
    for event in seeds.EVENTS:
        con.execute(
            """
            INSERT INTO seasonal_events(title,event_date,start_date,end_date,focus_categories,focus_products,demand_multiplier,prep_notes,marketing_notes,labor_notes,is_active,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,1,?)
            """,
            (event["title"], event["event_date"], event["start_date"], event["end_date"], event["focus_categories"], event["focus_products"], event["demand_multiplier"], event["prep_notes"], event["marketing_notes"], event["labor_notes"], now_iso()),
        )

    if production_mode():
        admin_email = require_env("JB_ADMIN_EMAIL", min_len=6).lower()
        admin_password = require_env("JB_ADMIN_PASSWORD", min_len=14)
        admin_id = seed_user(con, admin_email, admin_password, os.environ.get("JB_ADMIN_NAME", "Bakery Owner"), "admin", "Juquilita Bakery", os.environ.get("JB_ADMIN_PHONE", ""), "owner")
        con.execute("INSERT OR IGNORE INTO staff_permissions(user_id,permission_key,granted_by,created_at) VALUES(?,?,?,?)", (admin_id, "admin:*", admin_id, now_iso()))
        con.execute("INSERT OR IGNORE INTO user_staff_roles(user_id,role_key,assigned_by,created_at) VALUES(?,?,?,?)", (admin_id, "owner", admin_id, now_iso()))
        return
    seed_user(con, "admin@juquilita.local", "AdminPass2026!", "Bakery Admin", "admin", "Juquilita Bakery", "423-307-8244", "owner")
    seed_user(con, "guest@juquilita.local", "GuestPass2026!", "Guest Customer", "guest", "", "", "retail")
    premium_id = seed_user(con, "wholesale@taqueria.local", "PanDulce2026!", "Wholesale Buyer", "premium", "Demo Taquería Account", "423-555-0147", "pan dulce partner")
    seed_sample_orders(con, premium_id, product_ids)


def seed_sample_orders(con: sqlite3.Connection, premium_user_id: int, product_ids: dict[str, int]) -> None:
    # Enough realistic history for forecasts and production summaries to show meaningful output.
    samples = [
        ("Maria Lopez", "maria@example.test", "423-555-0101", "", "guest", -12, "09:30", [("concha", 8), ("oreja", 4), ("tres-leches-rebanada", 2)]),
        ("Wholesale Buyer", "wholesale@taqueria.local", "423-555-0147", "Demo Taquería Account", "premium", -9, "07:30", [("bolillo", 60), ("telera", 36), ("panbasos", 30)]),
        ("James Carter", "james@example.test", "423-555-0155", "", "guest", -7, "16:00", [("empanada-bavaria", 12), ("churro-cajeta", 6)]),
        ("Wholesale Buyer", "wholesale@taqueria.local", "423-555-0147", "Demo Taquería Account", "premium", -4, "07:00", [("concha", 48), ("marranito", 24), ("polvoron-azucar", 30)]),
        ("Ana Rivera", "ana@example.test", "423-555-0177", "", "guest", -2, "11:00", [("pastel-cuarto", 1), ("tarta-fruta", 6)]),
        ("Walk-In Pickup", "walkin@example.test", "423-555-0199", "", "guest", 1, "10:30", [("dona-azucar", 10), ("churro-simple", 10), ("flan-individual", 2)]),
    ]
    product_rows = {row["slug"]: row for row in con.execute("SELECT * FROM products").fetchall()}
    for idx, (name, email, phone, business, role, offset, pickup_time, lines) in enumerate(samples, start=1):
        subtotal = 0.0
        prepared = []
        for slug, qty in lines:
            p = product_rows[slug]
            price = p["wholesale_price"] if role == "premium" and p["wholesale_price"] is not None else p["base_price"]
            line_total = round(price * qty, 2)
            subtotal += line_total
            prepared.append((p, qty, price, line_total))
        discount = round(subtotal * 0.08, 2) if role == "premium" and subtotal >= 75 else 0
        total = round(subtotal - discount, 2)
        order_code = f"JB5-{(utc_now() + timedelta(days=offset)).strftime('%y%m%d')}-{idx:03d}"
        cur = con.execute(
            """
            INSERT INTO orders(order_code,user_id,customer_name,customer_email,customer_phone,business_name,customer_type,pickup_date,pickup_time,fulfillment,payment_method,notes,subtotal,discount,tax,total,deposit_due,promo_code,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (order_code, premium_user_id if role == "premium" else None, name, email, phone, business, role, (date.today() + timedelta(days=offset)).isoformat(), pickup_time, "pickup", "pay_at_pickup", "Seeded planning order", round(subtotal, 2), discount, 0, total, 0, "PANMAYOR" if discount else "", "completed" if offset < -2 else "received", (utc_now() + timedelta(days=offset)).replace(microsecond=0).isoformat() + "Z", now_iso()),
        )
        order_id = int(cur.lastrowid)
        for p, qty, price, line_total in prepared:
            con.execute(
                """
                INSERT INTO order_items(order_id,product_id,product_slug,product_name,unit_price,quantity,variant_summary,options_json,line_total,production_category)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (order_id, p["id"], p["slug"], f"{p['name_es']} / {p['name_en']}", price, qty, "", "{}", line_total, p["category_key"]),
            )


@dataclass
class SessionUser:
    id: int
    email: str
    name: str
    role: str
    business_name: str
    phone: str
    wholesale_tier: str
    csrf_token: str

    def public(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "business_name": self.business_name,
            "phone": self.phone,
            "wholesale_tier": self.wholesale_tier,
            "csrf_token": self.csrf_token,
        }


def get_session_user(handler: BaseHTTPRequestHandler) -> SessionUser | None:
    raw = handler.headers.get("Cookie", "")
    if not raw:
        return None
    cookie = SimpleCookie()
    try:
        cookie.load(raw)
    except Exception:
        return None
    morsel = cookie.get(SESSION_COOKIE)
    if not morsel:
        return None
    token = morsel.value
    with connect() as con:
        row = con.execute(
            """
            SELECT u.*, s.csrf_token FROM sessions s
            JOIN users u ON u.id=s.user_id
            WHERE s.token=? AND s.expires_at > ? AND u.is_active=1
            """,
            (token, now_iso()),
        ).fetchone()
        if not row:
            return None
        return SessionUser(
            id=int(row["id"]), email=row["email"], name=row["name"], role=row["role"],
            business_name=row["business_name"], phone=row["phone"], wholesale_tier=row["wholesale_tier"],
            csrf_token=row["csrf_token"],
        )


def require_user(handler: BaseHTTPRequestHandler, *, role: str | None = None) -> SessionUser:
    user = get_session_user(handler)
    if not user:
        raise AppError("Login required.", 401)
    if role:
        if role == "admin" and user.role in STAFF_ROLES:
            return user
        if user.role != role:
            raise AppError("You do not have access to this area.", 403)
    return user


def require_csrf(handler: BaseHTTPRequestHandler, user: SessionUser) -> None:
    token = handler.headers.get("X-CSRF-Token", "")
    if not token or not secrets.compare_digest(token, user.csrf_token):
        raise AppError("Security token missing or expired. Refresh and sign in again.", 403)


def client_ip(handler: BaseHTTPRequestHandler) -> str:
    forwarded = handler.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:80]
    return handler.client_address[0] if handler.client_address else "local"


def create_session(con: sqlite3.Connection, user_id: int, handler: BaseHTTPRequestHandler) -> tuple[str, str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    expires = (utc_now() + timedelta(days=7)).replace(microsecond=0).isoformat() + "Z"
    con.execute(
        "INSERT INTO sessions(token,user_id,csrf_token,created_at,expires_at,user_agent,ip_address) VALUES(?,?,?,?,?,?,?)",
        (token, user_id, csrf, now_iso(), expires, handler.headers.get("User-Agent", "")[:300], client_ip(handler)),
    )
    return token, csrf, expires


def cookie_header(token: str = "", *, clear: bool = False) -> str:
    secure = "; Secure" if env_bool("JB_SECURE_COOKIES") or production_mode() else ""
    same_site = "Strict" if production_mode() else "Lax"
    if clear:
        return f"{SESSION_COOKIE}=; HttpOnly; SameSite={same_site}; Path=/; Max-Age=0{secure}"
    return f"{SESSION_COOKIE}={token}; HttpOnly; SameSite={same_site}; Path=/; Max-Age={7*24*60*60}{secure}"


def audit(con: sqlite3.Connection, handler: BaseHTTPRequestHandler | None, user: SessionUser | None,
          action: str, entity_type: str, entity_id: str | int, before: Any = None, after: Any = None) -> None:
    con.execute(
        """
        INSERT INTO audit_log(actor_user_id,actor_email,action,entity_type,entity_id,before_json,after_json,ip_address,created_at)
        VALUES(?,?,?,?,?,?,?,?,?)
        """,
        (user.id if user else None, user.email if user else "", action, entity_type, str(entity_id),
         json_dumps(before) if before is not None else "", json_dumps(after) if after is not None else "",
         client_ip(handler) if handler else "system", now_iso()),
    )


def setting_map(con: sqlite3.Connection) -> dict[str, str]:
    return {row["key"]: row["value"] for row in con.execute("SELECT key,value FROM settings").fetchall()}


def product_public(row: sqlite3.Row, role: str, variants: list[dict[str, Any]] | None = None,
                   allergens: list[dict[str, Any]] | None = None, primary_image: dict[str, Any] | None = None,
                   is_favorite: bool = False, verification_status: str = "") -> dict[str, Any]:
    data = dict(row)
    if not data.get("canonical_key"):
        data["canonical_key"] = canonical_key_for_names(data["name_es"], data["name_en"])
    resolved_image = resolve_product_image(data)
    data["canonical_key"] = resolved_image["canonical_key"]
    data["image_url"] = resolved_image["image_url"]
    data["image_alt"] = resolved_image["image_alt"]
    data["product_image_status"] = resolved_image["image_status"]
    data["product_image_confidence"] = resolved_image["image_confidence"]
    data["product_image_filename"] = resolved_image["image_filename"]
    data["product_image_source_url"] = resolved_image["image_source_url"]
    data["photo_placeholder_url"] = resolved_image["placeholder_image_url"] or COMING_SOON_LOGO_URL
    if primary_image and not data.get("image_url") and data["product_image_status"] in {"legacyVerified", "categoryFallback"}:
        data["image_url"] = primary_image.get("image_url", "")
        data["image_alt"] = primary_image.get("alt_text", data.get("image_alt", ""))
    base = data["base_price"]
    wholesale = data["wholesale_price"]
    if role == "premium" and wholesale is not None:
        data["effective_price"] = round(float(wholesale), 2)
        data["price_label"] = "wholesale"
    elif base is not None:
        data["effective_price"] = round(float(base), 2)
        data["price_label"] = "retail"
    else:
        data["effective_price"] = None
        data["price_label"] = "quote"
    data["verification_status"] = verification_status or "unverified"
    data["visual_shape"] = data.get("visual_shape") or product_visual_shape(data)
    data["visual_tags"] = data.get("visual_tags") or product_visual_tags(data)
    data["completeness_score"] = product_completeness(data, data["verification_status"])
    data["photo_ready"] = bool(data.get("image_url") and data.get("product_image_status") in {"legacyVerified", "categoryFallback"})
    data["can_order"] = bool(data["is_active"] and data["order_mode"] == "order" and base is not None and data.get("public_status", "public") != "hidden")
    data["variants"] = variants or []
    data["allergens"] = allergens or []
    data["is_favorite"] = is_favorite
    data["cost_warning"] = False
    return data


def load_catalog(con: sqlite3.Connection, role: str = "guest", user_id: int | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    categories = rows_to_dicts(con.execute("SELECT * FROM categories ORDER BY sort_order, name_en").fetchall())
    rows = con.execute(
        """
        SELECT p.*, c.name_en AS category_name_en, c.name_es AS category_name_es
        FROM products p
        JOIN categories c ON c.key=p.category_key
        WHERE p.is_active=1
        ORDER BY c.sort_order, p.subcategory, p.name_es
        """
    ).fetchall()
    ids = [str(row["id"]) for row in rows]
    variants_by_product: dict[int, list[dict[str, Any]]] = {}
    allergens_by_product: dict[int, list[dict[str, Any]]] = {}
    images_by_product: dict[int, dict[str, Any]] = {}
    verification_by_product: dict[int, str] = {}
    favorite_ids: set[int] = set()
    if ids:
        query = f"SELECT * FROM product_variants WHERE product_id IN ({','.join(['?']*len(ids))}) ORDER BY variant_type, sort_order, id"
        for v in con.execute(query, ids).fetchall():
            variants_by_product.setdefault(int(v["product_id"]), []).append(dict(v))
        aq = f"""SELECT pa.product_id, a.key, a.name_en, a.name_es, pa.cross_contact
                 FROM product_allergens pa JOIN allergens a ON a.key=pa.allergen_key
                 WHERE pa.product_id IN ({','.join(['?']*len(ids))}) ORDER BY a.name_en"""
        for a in con.execute(aq, ids).fetchall():
            allergens_by_product.setdefault(int(a["product_id"]), []).append(dict(a))
        iq = f"""SELECT * FROM product_images WHERE product_id IN ({','.join(['?']*len(ids))}) AND image_status!='archived'
                 ORDER BY is_primary DESC, sort_order ASC, uploaded_at DESC"""
        for img in con.execute(iq, ids).fetchall():
            images_by_product.setdefault(int(img["product_id"]), dict(img))
        vq = f"SELECT product_id,status FROM catalog_verifications WHERE product_id IN ({','.join(['?']*len(ids))})"
        for vr in con.execute(vq, ids).fetchall():
            verification_by_product[int(vr["product_id"])] = vr["status"]
        if user_id:
            fq = f"SELECT product_id FROM customer_favorites WHERE user_id=? AND product_id IN ({','.join(['?']*len(ids))})"
            favorite_ids = {int(r["product_id"]) for r in con.execute(fq, [user_id] + ids).fetchall()}
    require_verified = False
    try:
        require_verified = role not in {"admin", "owner", "manager", "cashier", "baker", "decorator", "wholesale_manager"} and (setting_map(con).get("public_requires_owner_verified", "false").lower() == "true")
    except Exception:
        require_verified = False
    products = []
    for row in rows:
        status = verification_by_product.get(int(row["id"]), "unverified")
        if require_verified and status != "owner_verified" and row["order_mode"] == "order":
            continue
        products.append(product_public(row, role, variants_by_product.get(int(row["id"]), []), allergens_by_product.get(int(row["id"]), []), images_by_product.get(int(row["id"])), int(row["id"]) in favorite_ids, status))
    return categories, products


def active_promotions(con: sqlite3.Connection, role: str = "guest") -> list[dict[str, Any]]:
    rows = con.execute(
        """
        SELECT * FROM promotions
        WHERE is_active=1 AND starts_on <= ? AND ends_on >= ?
        ORDER BY auto_apply DESC, ends_on ASC, discount_value DESC
        """,
        (today_str(), today_str()),
    ).fetchall()
    out = []
    for row in rows:
        promo = dict(row)
        if promo["applies_to_role"] in ("all", role):
            out.append(promo)
    return out


def build_bootstrap(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    user = get_session_user(handler)
    role = user.role if user else "guest"
    with connect() as con:
        categories, products = load_catalog(con, role, user.id if user else None)
        partners = rows_to_dicts(con.execute("SELECT * FROM partners WHERE public_visible=1 ORDER BY has_consent DESC, monthly_volume_estimate DESC").fetchall())
        events = rows_to_dicts(con.execute("SELECT * FROM seasonal_events WHERE is_active=1 ORDER BY start_date").fetchall())
        bundles = rows_to_dicts(con.execute("SELECT * FROM bundles WHERE is_active=1 ORDER BY sort_order").fetchall())
        hours = rows_to_dicts(con.execute("SELECT * FROM business_hours ORDER BY weekday").fetchall())
        settings = setting_map(con)
        content_blocks = rows_to_dicts(con.execute("SELECT * FROM content_blocks WHERE is_active=1 ORDER BY placement, block_key").fetchall())
        seo_pages = rows_to_dicts(con.execute("SELECT slug,title,meta_description,target_keyword,status FROM seo_pages WHERE status='published' ORDER BY slug").fetchall())
        delivery_zones = rows_to_dicts(con.execute("SELECT * FROM delivery_zones ORDER BY status DESC, min_order").fetchall())
        local_events = rows_to_dicts(con.execute("SELECT * FROM local_events WHERE is_active=1 ORDER BY event_date LIMIT 20").fetchall())
        seasonal_campaigns = rows_to_dicts(con.execute("SELECT * FROM seasonal_campaigns WHERE status IN ('active','draft','paused') ORDER BY season_start LIMIT 20").fetchall())
        for campaign in seasonal_campaigns:
            campaign["pickup_windows"] = rows_to_dicts(con.execute("SELECT * FROM seasonal_pickup_windows WHERE campaign_id=? ORDER BY pickup_date, starts_at", (campaign["id"],)).fetchall())
        product_batches = rows_to_dicts(con.execute("SELECT pb.*, p.slug, p.name_es, p.name_en FROM product_batches pb JOIN products p ON p.id=pb.product_id WHERE pb.batch_date BETWEEN ? AND ? ORDER BY pb.batch_date, pb.expected_ready_at LIMIT 120", (today_str(), (date.today()+timedelta(days=3)).isoformat())).fetchall())
        visual_shapes = rows_to_dicts(con.execute("SELECT COALESCE(NULLIF(visual_shape,''),'other') AS visual_shape, COUNT(*) AS count FROM products WHERE is_active=1 GROUP BY COALESCE(NULLIF(visual_shape,''),'other') ORDER BY count DESC").fetchall())
        reviews = rows_to_dicts(con.execute("SELECT pr.*, p.slug, p.name_es, p.name_en FROM product_reviews pr LEFT JOIN products p ON p.id=pr.product_id WHERE pr.status='approved' ORDER BY pr.created_at DESC LIMIT 20").fetchall())
        order_history: list[dict[str, Any]] = []
        standing_orders: list[dict[str, Any]] = []
        change_requests: list[dict[str, Any]] = []
        loyalty_summary = {"points": 0, "events": []}
        if user:
            order_history = rows_to_dicts(con.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user.id,)).fetchall())
            standing_orders = load_standing_orders(con, user.id)
            change_requests = rows_to_dicts(con.execute("SELECT ocr.*, o.order_code, o.pickup_date, o.pickup_time FROM order_change_requests ocr JOIN orders o ON o.id=ocr.order_id WHERE ocr.user_id=? OR lower(ocr.customer_email)=lower(?) ORDER BY ocr.created_at DESC LIMIT 20", (user.id, user.email)).fetchall())
            loyalty_events = rows_to_dicts(con.execute("SELECT * FROM loyalty_ledger WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user.id,)).fetchall())
            loyalty_summary = {"points": sum(int(x["points"]) for x in loyalty_events), "events": loyalty_events}
        return {
            "user": user.public() if user else None,
            "categories": categories,
            "products": products,
            "promotions": active_promotions(con, role),
            "partners": partners,
            "events": events,
            "bundles": bundles,
            "hours": hours,
            "settings": settings,
            "store_status": store_status(con),
            "order_history": order_history,
            "standing_orders": standing_orders,
            "content_blocks": content_blocks,
            "seo_pages": seo_pages,
            "delivery_zones": delivery_zones,
            "local_events": local_events,
            "seasonal_campaigns": seasonal_campaigns,
            "product_batches": product_batches,
            "visual_shapes": visual_shapes,
            "reviews": reviews,
            "change_requests": change_requests,
            "loyalty_summary": loyalty_summary,
        }


def load_standing_orders(con: sqlite3.Connection, user_id: int) -> list[dict[str, Any]]:
    rows = con.execute("SELECT * FROM standing_orders WHERE user_id=? ORDER BY weekday,pickup_time", (user_id,)).fetchall()
    result = []
    for row in rows:
        data = dict(row)
        data["items"] = rows_to_dicts(con.execute(
            """
            SELECT soi.*, p.slug, p.name_es, p.name_en FROM standing_order_items soi
            JOIN products p ON p.id=soi.product_id
            WHERE soi.standing_order_id=?
            """, (row["id"],)
        ).fetchall())
        result.append(data)
    return result


def parse_local_pickup(pickup_date: str, pickup_time: str) -> datetime:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", pickup_date):
        raise AppError("Choose a valid pickup date.")
    if not re.match(r"^\d{2}:\d{2}$", pickup_time):
        raise AppError("Choose a valid pickup time.")
    try:
        return datetime.fromisoformat(f"{pickup_date}T{pickup_time}:00")
    except ValueError:
        raise AppError("Choose a valid pickup date and time.")


def store_status(con: sqlite3.Connection, at_dt: datetime | None = None) -> dict[str, Any]:
    at_dt = at_dt or datetime.now()
    weekday = at_dt.weekday()
    row = con.execute("SELECT * FROM business_hours WHERE weekday=?", (weekday,)).fetchone()
    if not row:
        return {"is_open": False, "message_en": "Hours are not configured.", "message_es": "No hay horario configurado."}
    closure = con.execute("SELECT * FROM closures WHERE closure_date=?", (at_dt.date().isoformat(),)).fetchone()
    if closure and closure["is_closed"]:
        return {"is_open": False, "message_en": f"Closed today: {closure['reason']}", "message_es": f"Cerrado hoy: {closure['reason']}", "opens_at": "", "closes_at": ""}
    opens = closure["opens_at"] if closure and closure["opens_at"] else row["opens_at"]
    closes = closure["closes_at"] if closure and closure["closes_at"] else row["closes_at"]
    open_dt = datetime.fromisoformat(f"{at_dt.date().isoformat()}T{opens}:00")
    close_dt = datetime.fromisoformat(f"{at_dt.date().isoformat()}T{closes}:00")
    is_open = open_dt <= at_dt <= close_dt and not bool(row["is_closed"])
    return {
        "is_open": is_open,
        "message_en": "Open now" if is_open else f"Closed. Next window today: {opens} to {closes}.",
        "message_es": "Abierto ahora" if is_open else f"Cerrado. Horario de hoy: {opens} a {closes}.",
        "opens_at": opens,
        "closes_at": closes,
        "slot_capacity": row["slot_capacity"],
        "day_en": row["day_en"],
        "day_es": row["day_es"],
    }


def validate_pickup(con: sqlite3.Connection, pickup_date: str, pickup_time: str, max_lead_hours: int) -> None:
    pickup_dt = parse_local_pickup(pickup_date, pickup_time)
    now = datetime.now()
    if pickup_dt < now:
        raise AppError("Pickup time must be in the future.")
    if max_lead_hours and pickup_dt < now + timedelta(hours=max_lead_hours):
        raise AppError(f"This basket needs at least {max_lead_hours} hours notice. Choose a later pickup time.")
    closure = con.execute("SELECT * FROM closures WHERE closure_date=?", (pickup_date,)).fetchone()
    if closure and closure["is_closed"]:
        raise AppError(f"The bakery is closed that day: {closure['reason']}.")
    row = con.execute("SELECT * FROM business_hours WHERE weekday=?", (pickup_dt.weekday(),)).fetchone()
    if not row or row["is_closed"]:
        raise AppError("The bakery is closed on that pickup day.")
    opens = closure["opens_at"] if closure and closure["opens_at"] else row["opens_at"]
    closes = closure["closes_at"] if closure and closure["closes_at"] else row["closes_at"]
    if not (opens <= pickup_time <= closes):
        raise AppError(f"Pickup must be during bakery hours: {opens} to {closes}.")
    count = con.execute(
        "SELECT COUNT(*) AS n FROM orders WHERE pickup_date=? AND pickup_time=? AND status NOT IN ('canceled','completed')",
        (pickup_date, pickup_time),
    ).fetchone()["n"]
    if int(count) >= int(row["slot_capacity"]):
        raise AppError("That pickup window is full. Choose another time.")


def get_product_by_slug(con: sqlite3.Connection, slug: str) -> sqlite3.Row:
    row = con.execute("SELECT * FROM products WHERE slug=? AND is_active=1", (slug,)).fetchone()
    if not row:
        raise AppError(f"Product not found: {slug}")
    return row


def get_variants(con: sqlite3.Connection, product_id: int, variant_ids: list[int], role: str) -> tuple[float, str, list[dict[str, Any]]]:
    if not variant_ids:
        return 0, "", []
    clean_ids = [parse_int(v, "variant", min_value=1, max_value=1_000_000) for v in variant_ids]
    placeholders = ",".join(["?"] * len(clean_ids))
    rows = con.execute(f"SELECT * FROM product_variants WHERE product_id=? AND id IN ({placeholders})", [product_id] + clean_ids).fetchall()
    if len(rows) != len(clean_ids):
        raise AppError("One selected option is not valid for this product.")
    delta = 0.0
    labels = []
    variants = []
    for row in rows:
        d = row["wholesale_delta"] if role == "premium" else row["price_delta"]
        delta += float(d or 0)
        labels.append(f"{row['variant_type']}: {row['name_es']} / {row['name_en']}")
        variants.append(dict(row))
    return round(delta, 2), "; ".join(labels), variants


def prepare_order_lines(con: sqlite3.Connection, raw_items: list[dict[str, Any]], role: str) -> tuple[list[dict[str, Any]], float, int, list[str]]:
    if not raw_items:
        raise AppError("Your basket is empty.")
    if len(raw_items) > 60:
        raise AppError("Too many different line items. Split the order or request a quote.")
    lines: list[dict[str, Any]] = []
    subtotal = 0.0
    max_lead = 0
    warnings: list[str] = []
    for item in raw_items:
        slug = clean_text(item.get("slug"), 120)
        qty = parse_int(item.get("quantity"), "quantity", min_value=1, max_value=750)
        product = get_product_by_slug(con, slug)
        if product["order_mode"] != "order" or product["base_price"] is None:
            raise AppError(f"{product['name_es']} requires a quote request before ordering.")
        if product["stock_policy"] == "track" and qty > int(product["stock_count"]):
            raise AppError(f"Only {product['stock_count']} of {product['name_es']} are currently available.")
        if product["order_mode"] == "inactive":
            raise AppError(f"{product['name_es']} is paused right now.")
        variant_delta, variant_summary, variants = get_variants(con, int(product["id"]), item.get("variant_ids", []) or [], role)
        base_price = product["wholesale_price"] if role == "premium" and product["wholesale_price"] is not None else product["base_price"]
        unit_price = round(float(base_price) + variant_delta, 2)
        if unit_price < 0:
            raise AppError("Invalid product price. Contact the bakery.")
        line_total = round(unit_price * qty, 2)
        subtotal += line_total
        max_lead = max(max_lead, int(product["lead_time_hours"] or 0))
        if product["stock_policy"] == "made_to_order":
            warnings.append(f"{product['name_es']} is made to order and needs {product['lead_time_hours']} hours notice.")
        if qty >= 48 and not product["is_bulk_friendly"]:
            warnings.append(f"Large quantity for {product['name_es']} may need confirmation.")
        lines.append({
            "product": dict(product),
            "quantity": qty,
            "unit_price": unit_price,
            "line_total": line_total,
            "variant_summary": variant_summary,
            "variants": variants,
            "options": item.get("options", {}) if isinstance(item.get("options", {}), dict) else {},
        })
    return lines, round(subtotal, 2), max_lead, warnings


def promo_eligible_amount(lines: list[dict[str, Any]], category_key: str) -> float:
    if category_key == "all":
        return round(sum(line["line_total"] for line in lines), 2)
    return round(sum(line["line_total"] for line in lines if line["product"]["category_key"] == category_key), 2)


def compute_promo(con: sqlite3.Connection, lines: list[dict[str, Any]], subtotal: float, role: str, customer_email: str,
                  user_id: int | None, promo_code: str = "") -> tuple[dict[str, Any] | None, float]:
    candidates = active_promotions(con, role)
    chosen: dict[str, Any] | None = None
    if promo_code:
        for p in candidates:
            if p["code"].upper() == promo_code.upper():
                chosen = p
                break
        if not chosen:
            raise AppError("That promotion code is not active or does not apply to this account.")
    else:
        auto_promos = [p for p in candidates if p["auto_apply"]]
        if auto_promos:
            chosen = auto_promos[0]
    if not chosen:
        return None, 0.0
    if subtotal < float(chosen["min_subtotal"]):
        raise AppError(f"Promotion requires a subtotal of at least ${float(chosen['min_subtotal']):.2f}.")
    eligible = promo_eligible_amount(lines, chosen["category_key"])
    if eligible <= 0:
        raise AppError("Promotion does not apply to the products in this basket.")
    if chosen["max_redemptions"]:
        count = con.execute("SELECT COUNT(*) AS n FROM promo_redemptions WHERE promotion_id=?", (chosen["id"],)).fetchone()["n"]
        if int(count) >= int(chosen["max_redemptions"]):
            raise AppError("That promotion has reached its redemption limit.")
    if chosen["per_customer_limit"]:
        count = con.execute("SELECT COUNT(*) AS n FROM promo_redemptions WHERE promotion_id=? AND lower(customer_email)=lower(?)", (chosen["id"], customer_email)).fetchone()["n"]
        if int(count) >= int(chosen["per_customer_limit"]):
            raise AppError("That promotion has already been used for this email.")
    if chosen["discount_type"] == "percent":
        value = min(float(chosen["discount_value"]), 50.0)
        discount = round(eligible * (value / 100), 2)
    else:
        discount = min(round(float(chosen["discount_value"]), 2), eligible)
    return chosen, discount


def create_notification(con: sqlite3.Connection, channel: str, recipient: str, subject: str, body: str,
                        related_type: str, related_id: int) -> None:
    status = "queued"
    try:
        pref = None
        if channel == "sms":
            pref = con.execute("SELECT * FROM notification_preferences WHERE phone=? ORDER BY updated_at DESC LIMIT 1", (recipient,)).fetchone()
            if pref and int(pref["do_not_text"]):
                status = "blocked_preference"
        elif channel == "email":
            pref = con.execute("SELECT * FROM notification_preferences WHERE lower(email)=lower(?) ORDER BY updated_at DESC LIMIT 1", (recipient,)).fetchone()
            if pref and int(pref["do_not_email"]):
                status = "blocked_preference"
    except Exception:
        status = "queued"
    con.execute(
        "INSERT INTO notifications(channel,recipient,subject,body,status,related_type,related_id,created_at) VALUES(?,?,?,?,?,?,?,?)",
        (channel, recipient, subject, body, status, related_type, related_id, now_iso()),
    )


STAFF_ROLES = {"owner", "admin", "manager", "cashier", "baker", "decorator", "wholesale_manager"}
ADMIN_ROUTE_PERMISSIONS = {
    "/api/admin/dashboard": "admin:dashboard",
    "/api/admin/order-status": "orders:manage",
    "/api/admin/product-update": "catalog:manage",
    "/api/admin/product-create": "catalog:manage",
    "/api/admin/variant-create": "catalog:manage",
    "/api/admin/product-verify": "catalog:verify",
    "/api/admin/photo-upload": "photos:manage",
    "/api/admin/promotion-create": "marketing:manage",
    "/api/admin/partner-save": "partners:manage",
    "/api/admin/quote-status": "quotes:manage",
    "/api/admin/quote-offer": "quotes:manage",
    "/api/admin/quote-convert": "quotes:manage",
    "/api/admin/wholesale-decision": "wholesale:manage",
    "/api/admin/event-save": "forecast:manage",
    "/api/admin/local-event-save": "forecast:manage",
    "/api/admin/weather-adjustment-save": "forecast:manage",
    "/api/admin/hours-save": "settings:manage",
    "/api/admin/closure-save": "settings:manage",
    "/api/admin/settings-save": "settings:manage",
    "/api/admin/launch-save": "launch:manage",
    "/api/admin/seo-save": "content:manage",
    "/api/admin/content-save": "content:manage",
    "/api/admin/uat-save": "qa:manage",
    "/api/admin/qa-run": "qa:manage",
    "/api/admin/qa-item-save": "qa:manage",
    "/api/admin/pos-import": "opsdata:manage",
    "/api/admin/change-request-status": "customers:manage",
    "/api/admin/review-status": "customers:manage",
    "/api/admin/bundle-save": "catalog:manage",
    "/api/admin/ingredient-save": "recipes:manage",
    "/api/admin/supplier-save": "suppliers:manage",
    "/api/admin/supplier-quote-save": "suppliers:manage",
    "/api/admin/product-ingredient-save": "recipes:manage",
    "/api/admin/recipe-verify": "recipes:verify",
    "/api/admin/invoice-create": "finance:manage",
    "/api/admin/refund-create": "finance:manage",
    "/api/admin/tax-export": "finance:manage",
    "/api/admin/production-task-status": "orders:manage",
    "/api/admin/standing-order-generate": "wholesale:manage",
    "/api/admin/payment-mark": "finance:manage",
    "/api/admin/payment-refresh": "finance:manage",
    "/api/admin/notification-status": "notifications:manage",
    "/api/admin/notification-send": "notifications:send",
    "/api/admin/backup-run": "system:backup",
    "/api/admin/staff-save": "staff:manage",
}


def token_digest(token: str) -> str:
    pepper = require_env("JB_TOKEN_PEPPER", min_len=32) if production_mode() else os.environ.get("JB_TOKEN_PEPPER", "juquilita-local-demo-pepper")
    return hmac.new(pepper.encode("utf-8"), token.encode("utf-8"), hashlib.sha256).hexdigest()


def public_base_url(handler: BaseHTTPRequestHandler | None = None) -> str:
    configured = os.environ.get("JB_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if configured:
        return configured
    if handler:
        scheme = "https" if os.environ.get("JB_ASSUME_HTTPS") == "1" else "http"
        host = handler.headers.get("Host", "127.0.0.1:8000")
        return f"{scheme}://{host}".rstrip("/")
    return "http://127.0.0.1:8000"


def url_origin(handler: BaseHTTPRequestHandler | None = None) -> str:
    return public_base_url(handler)


def http_post(url: str, *, headers: dict[str, str], body: bytes, timeout: int = 12) -> dict[str, Any]:
    req = Request(url, data=body, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout) as res:
            raw = res.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")[:1000]
        raise AppError("External provider rejected the request.", 502, {"status": exc.code, "body": raw})
    except URLError as exc:
        raise AppError("External provider is unreachable.", 502, {"reason": str(exc.reason)[:300]})


def provider_ready(provider: str) -> tuple[bool, str]:
    provider = provider.lower().strip()
    if provider == "stripe":
        missing = [k for k in ["STRIPE_SECRET_KEY"] if not os.environ.get(k)]
        return (not missing, f"Missing {', '.join(missing)}" if missing else "Stripe configured")
    if provider == "square":
        missing = [k for k in ["SQUARE_ACCESS_TOKEN", "SQUARE_LOCATION_ID"] if not os.environ.get(k)]
        return (not missing, f"Missing {', '.join(missing)}" if missing else "Square configured")
    if production_mode():
        return (False, "Mock provider is disabled in production.")
    return (True, "Mock provider")


def create_stripe_checkout(*, payment_id: int, amount: float, description: str, success_url: str, cancel_url: str,
                           customer_email: str = "") -> dict[str, Any]:
    key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not key:
        return {"configured": False, "reference": f"STRIPE-CONFIG-{payment_id}", "checkout_url": "configure-STRIPE_SECRET_KEY", "message": "Stripe secret key is not configured."}
    cents = int(round(amount * 100))
    fields = {
        "mode": "payment",
        "payment_method_types[0]": "card",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": f"payment_intent:{payment_id}",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(cents),
        "line_items[0][price_data][product_data][name]": description[:120],
        "line_items[0][quantity]": "1",
        "metadata[payment_intent_id]": str(payment_id),
        "metadata[source_app]": "juquilita_bakery_v6",
    }
    if customer_email:
        fields["customer_email"] = customer_email
    payload = urlencode(fields).encode("utf-8")
    result = http_post("https://api.stripe.com/v1/checkout/sessions", headers={
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/x-www-form-urlencoded",
    }, body=payload)
    return {"configured": True, "reference": result.get("id", f"stripe-{payment_id}"), "checkout_url": result.get("url", ""), "message": "Stripe Checkout Session created.", "raw": result}


def create_square_payment_link(*, payment_id: int, amount: float, description: str, success_url: str) -> dict[str, Any]:
    token = os.environ.get("SQUARE_ACCESS_TOKEN", "")
    location_id = os.environ.get("SQUARE_LOCATION_ID", "")
    if not token or not location_id:
        missing = ", ".join(k for k in ["SQUARE_ACCESS_TOKEN", "SQUARE_LOCATION_ID"] if not os.environ.get(k))
        return {"configured": False, "reference": f"SQUARE-CONFIG-{payment_id}", "checkout_url": f"configure-{missing}", "message": f"{missing} is not configured."}
    base = os.environ.get("SQUARE_API_BASE", "").rstrip("/")
    if not base:
        base = "https://connect.squareupsandbox.com" if os.environ.get("SQUARE_ENV", "sandbox").lower() == "sandbox" else "https://connect.squareup.com"
    cents = int(round(amount * 100))
    body = json.dumps({
        "idempotency_key": f"juquilita-{payment_id}-{int(time.time())}",
        "quick_pay": {
            "name": description[:120],
            "price_money": {"amount": cents, "currency": "USD"},
            "location_id": location_id,
        },
        "checkout_options": {"redirect_url": success_url},
        "pre_populated_data": {},
    }).encode("utf-8")
    result = http_post(f"{base}/v2/online-checkout/payment-links", headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Square-Version": os.environ.get("SQUARE_VERSION", "2026-05-21"),
    }, body=body)
    link = result.get("payment_link", {})
    return {"configured": True, "reference": link.get("id", f"square-{payment_id}"), "checkout_url": link.get("url", ""), "message": "Square payment link created.", "raw": result}


def create_external_checkout(con: sqlite3.Connection, *, payment_id: int, order_id: int | None, quote_id: int | None,
                             provider: str, amount: float, kind: str) -> dict[str, Any]:
    provider = (provider or "mock").lower().strip()
    if production_mode() and provider == "mock":
        raise AppError("Mock payments are disabled in production. Configure Stripe or Square.", 500)
    description = f"Juquilita Bakery {kind} payment"
    customer_email = ""
    order_code = ""
    if order_id:
        order = con.execute("SELECT order_code, customer_email, customer_name FROM orders WHERE id=?", (order_id,)).fetchone()
        if order:
            order_code = order["order_code"]
            customer_email = order["customer_email"]
            description = f"Juquilita Bakery order {order_code} {kind}"
    elif quote_id:
        quote = con.execute("SELECT quote_code, customer_email, customer_name FROM quote_requests WHERE id=?", (quote_id,)).fetchone()
        if quote:
            order_code = quote["quote_code"]
            customer_email = quote["customer_email"]
            description = f"Juquilita Bakery quote {order_code} {kind}"
    base = public_base_url()
    success_url = f"{base}/payment-success.html?payment_id={payment_id}"
    cancel_url = f"{base}/receipt?code={order_code}" if order_code.startswith("JB") else f"{base}/index.html"
    if provider == "stripe":
        return create_stripe_checkout(payment_id=payment_id, amount=amount, description=description, success_url=success_url, cancel_url=cancel_url, customer_email=customer_email)
    if provider == "square":
        return create_square_payment_link(payment_id=payment_id, amount=amount, description=description, success_url=success_url)
    return {"configured": True, "reference": f"MOCK-{utc_now().strftime('%y%m%d')}-{payment_id}", "checkout_url": f"/receipt?code={order_code}" if order_code else "/index.html", "message": "Mock payment intent. Configure Stripe or Square for real cards."}


def base32_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode_base32(secret: str) -> bytes:
    secret = re.sub(r"\s+", "", secret).upper()
    padding = "=" * ((8 - len(secret) % 8) % 8)
    return base64.b32decode(secret + padding)


def totp_code(secret: str, for_time: int | None = None, step: int = 30, digits: int = 6) -> str:
    counter = int((for_time if for_time is not None else time.time()) // step)
    key = _decode_base32(secret)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code_int = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7fffffff
    return str(code_int % (10 ** digits)).zfill(digits)


def verify_totp(secret: str, code: str, last_used_step: int = 0, window: int = 1) -> tuple[bool, int]:
    code = re.sub(r"\s+", "", str(code or ""))
    if not re.fullmatch(r"\d{6}", code):
        return False, 0
    now_step = int(time.time() // 30)
    for offset in range(-window, window + 1):
        step_value = now_step + offset
        if step_value <= last_used_step:
            continue
        if secrets.compare_digest(totp_code(secret, step_value * 30), code):
            return True, step_value
    return False, 0


def has_permission(con: sqlite3.Connection, user: SessionUser, permission_key: str) -> bool:
    if user.role in {"owner", "admin"}:
        return True
    keys = {permission_key, "admin:*"}
    placeholders = ",".join("?" for _ in keys)
    direct = con.execute(f"SELECT 1 FROM staff_permissions WHERE user_id=? AND permission_key IN ({placeholders})", [user.id, *keys]).fetchone()
    if direct:
        return True
    role_perm = con.execute(
        f"""
        SELECT 1 FROM user_staff_roles usr
        JOIN staff_role_permissions srp ON srp.role_key=usr.role_key
        WHERE usr.user_id=? AND srp.permission_key IN ({placeholders})
        """, [user.id, *keys]
    ).fetchone()
    return bool(role_perm)


def require_permission(handler: BaseHTTPRequestHandler, permission_key: str) -> SessionUser:
    user = require_user(handler, role="admin")
    with connect() as con:
        if not has_permission(con, user, permission_key):
            raise AppError("Your staff account does not have this permission.", 403)
    return user


def require_route_permission(handler: BaseHTTPRequestHandler, path: str) -> None:
    permission = ADMIN_ROUTE_PERMISSIONS.get(path)
    if permission:
        require_permission(handler, permission)


def two_factor_required_for_user(con: sqlite3.Connection, user_row: sqlite3.Row) -> bool:
    enabled = con.execute("SELECT is_enabled FROM two_factor_auth WHERE user_id=?", (user_row["id"],)).fetchone()
    if enabled and int(enabled["is_enabled"]):
        return True
    # Production can force 2FA for all admin/staff accounts after owner setup.
    required = con.execute("SELECT value FROM settings WHERE key='admin_2fa_required'").fetchone()
    return bool(required and required["value"] == "true" and user_row["role"] in STAFF_ROLES)


def setup_two_factor(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler)
    require_csrf(handler, user)
    if user.role not in STAFF_ROLES:
        raise AppError("Two-factor setup is currently required for staff/admin accounts.", 403)
    secret = base32_secret()
    recovery_codes = [f"{secrets.randbelow(10**8):08d}" for _ in range(8)]
    recovery_hashes = [token_digest(code) for code in recovery_codes]
    issuer = os.environ.get("JB_TOTP_ISSUER", "Juquilita Bakery")
    label = f"{issuer}:{user.email}"
    otpauth = f"otpauth://totp/{label}?secret={secret}&issuer={issuer.replace(' ', '%20')}&digits=6&period=30"
    with connect() as con:
        con.execute("""
            INSERT INTO two_factor_auth(user_id,secret_base32,is_enabled,recovery_codes_json,last_used_step,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET secret_base32=excluded.secret_base32,is_enabled=0,recovery_codes_json=excluded.recovery_codes_json,last_used_step=0,updated_at=excluded.updated_at
        """, (user.id, secret, 0, json_dumps(recovery_hashes), 0, now_iso(), now_iso()))
        audit(con, handler, user, "2fa_setup_started", "user", user.id, None, {})
    return {"ok": True, "secret_base32": secret, "otpauth_uri": otpauth, "recovery_codes": recovery_codes, "message": "Enter the current 6-digit code from your authenticator app to confirm."}


def confirm_two_factor(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler)
    require_csrf(handler, user)
    code = clean_text(data.get("code"), 20)
    with connect() as con:
        row = con.execute("SELECT * FROM two_factor_auth WHERE user_id=?", (user.id,)).fetchone()
        if not row:
            raise AppError("Start two-factor setup first.")
        ok, step_value = verify_totp(row["secret_base32"], code, int(row["last_used_step"] or 0))
        if not ok:
            raise AppError("Invalid two-factor code.", 401)
        con.execute("UPDATE two_factor_auth SET is_enabled=1,last_used_step=?,confirmed_at=?,updated_at=? WHERE user_id=?", (step_value, now_iso(), now_iso(), user.id))
        audit(con, handler, user, "2fa_enabled", "user", user.id, None, {})
    return {"ok": True, "enabled": True}


def disable_two_factor(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler)
    require_csrf(handler, user)
    password = str(data.get("password") or "")
    with connect() as con:
        row = con.execute("SELECT * FROM users WHERE id=?", (user.id,)).fetchone()
        if not row or not verify_password(password, row["password_hash"], row["salt"]):
            raise AppError("Password confirmation failed.", 401)
        con.execute("UPDATE two_factor_auth SET is_enabled=0, updated_at=? WHERE user_id=?", (now_iso(), user.id))
        audit(con, handler, user, "2fa_disabled", "user", user.id, None, {})
    return {"ok": True, "enabled": False}


def verify_two_factor_login(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> tuple[dict[str, Any], str]:
    challenge_token = clean_text(data.get("challenge_token"), 200)
    code = clean_text(data.get("code"), 40)
    with connect() as con:
        ch = con.execute("SELECT * FROM two_factor_challenges WHERE token=? AND verified_at='' AND expires_at > ?", (challenge_token, now_iso())).fetchone()
        if not ch:
            raise AppError("Two-factor challenge expired. Sign in again.", 401)
        user_row = con.execute("SELECT * FROM users WHERE id=? AND is_active=1", (ch["user_id"],)).fetchone()
        tf = con.execute("SELECT * FROM two_factor_auth WHERE user_id=?", (ch["user_id"],)).fetchone()
        if not user_row or not tf or not int(tf["is_enabled"]):
            raise AppError("Two-factor is not configured for this account.", 401)
        ok, step_value = verify_totp(tf["secret_base32"], code, int(tf["last_used_step"] or 0))
        if not ok:
            # Recovery codes are single-use. They are hashed with the same token digest helper.
            recovery_hashes = load_json(tf["recovery_codes_json"], []) or []
            code_hash = token_digest(code)
            if code_hash in recovery_hashes:
                recovery_hashes.remove(code_hash)
                con.execute("UPDATE two_factor_auth SET recovery_codes_json=?,updated_at=? WHERE user_id=?", (json_dumps(recovery_hashes), now_iso(), ch["user_id"]))
                ok = True
                step_value = int(tf["last_used_step"] or 0)
        if not ok:
            raise AppError("Invalid two-factor code.", 401)
        con.execute("UPDATE two_factor_challenges SET verified_at=? WHERE token=?", (now_iso(), challenge_token))
        con.execute("UPDATE two_factor_auth SET last_used_step=?,updated_at=? WHERE user_id=?", (step_value, now_iso(), ch["user_id"]))
        token, csrf, _ = create_session(con, int(user_row["id"]), handler)
        user = {"id": user_row["id"], "email": user_row["email"], "name": user_row["name"], "role": user_row["role"], "business_name": user_row["business_name"], "phone": user_row["phone"], "wholesale_tier": user_row["wholesale_tier"], "csrf_token": csrf}
        audit(con, handler, None, "2fa_login", "user", user_row["id"], None, {"email": user_row["email"]})
    return {"ok": True, "user": user}, cookie_header(token)


def send_email_sendgrid(to_email: str, subject: str, body: str) -> dict[str, Any]:
    key = os.environ.get("SENDGRID_API_KEY", "")
    from_email = os.environ.get("SENDGRID_FROM_EMAIL", os.environ.get("JB_FROM_EMAIL", ""))
    from_name = os.environ.get("SENDGRID_FROM_NAME", "Juquilita Bakery")
    if not key or not from_email:
        raise AppError("SendGrid is not configured. Set SENDGRID_API_KEY and SENDGRID_FROM_EMAIL.", 400)
    payload = json.dumps({
        "personalizations": [{"to": [{"email": to_email}], "subject": subject}],
        "from": {"email": from_email, "name": from_name},
        "content": [{"type": "text/plain", "value": body}],
    }).encode("utf-8")
    return http_post("https://api.sendgrid.com/v3/mail/send", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, body=payload)


def send_sms_twilio(to_phone: str, body: str) -> dict[str, Any]:
    sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
    token = os.environ.get("TWILIO_AUTH_TOKEN", "")
    from_phone = os.environ.get("TWILIO_FROM_PHONE", os.environ.get("JB_SMS_FROM_PHONE", ""))
    if not sid or not token or not from_phone:
        raise AppError("Twilio SMS is not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, and TWILIO_FROM_PHONE.", 400)
    auth = base64.b64encode(f"{sid}:{token}".encode("utf-8")).decode("ascii")
    payload = urlencode({"To": to_phone, "From": from_phone, "Body": body[:1500]}).encode("utf-8")
    return http_post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"}, body=payload)


def process_notification_queue(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_permission(handler, "notifications:send")
    require_csrf(handler, user)
    limit = parse_int(data.get("limit") or 25, "limit", min_value=1, max_value=100)
    dry_run = bool(data.get("dry_run", False))
    processed = []
    with connect() as con:
        rows = con.execute("SELECT * FROM notifications WHERE status IN ('queued','failed') ORDER BY created_at LIMIT ?", (limit,)).fetchall()
        for n in rows:
            status = "sent"
            provider = "manual" if dry_run else ("sendgrid" if n["channel"] == "email" else "twilio" if n["channel"] == "sms" else "dashboard")
            provider_ref = "dry-run" if dry_run else ""
            response = ""
            try:
                if dry_run or n["channel"] == "admin":
                    response = "dry run" if dry_run else "dashboard notification retained"
                elif n["channel"] == "email":
                    result = send_email_sendgrid(n["recipient"], n["subject"], n["body"])
                    provider_ref = str(result.get("message_id") or result.get("id") or "sendgrid-accepted")
                    response = json_dumps(result)[:1000]
                elif n["channel"] == "sms":
                    result = send_sms_twilio(n["recipient"], n["body"])
                    provider_ref = str(result.get("sid") or "twilio-accepted")
                    response = json_dumps(result)[:1000]
            except Exception as exc:
                status = "failed"
                response = exc.message if isinstance(exc, AppError) else str(exc)[:1000]
            con.execute("""
                UPDATE notifications SET status=?, provider=?, provider_reference=?, provider_response=?, attempts=attempts+1,
                    last_attempt_at=?, sent_at=CASE WHEN ?='sent' THEN ? ELSE sent_at END
                WHERE id=?
            """, (status, provider, provider_ref, response, now_iso(), status, now_iso(), n["id"]))
            con.execute("INSERT INTO notification_attempts(notification_id,status,provider,provider_reference,response,attempted_at) VALUES(?,?,?,?,?,?)", (n["id"], status, provider, provider_ref, response, now_iso()))
            processed.append({"id": n["id"], "channel": n["channel"], "status": status, "provider": provider})
        audit(con, handler, user, "process_notifications", "notification", "batch", None, {"count": len(processed), "dry_run": dry_run})
    return {"ok": True, "processed": processed}


def confirm_password_reset(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    token = clean_text(data.get("token"), 300)
    password = str(data.get("password") or "")
    if len(password) < 10:
        raise AppError("Password must be at least 10 characters.")
    digest = token_digest(token)
    with connect() as con:
        row = con.execute("SELECT prt.*, u.email, u.name FROM password_reset_tokens prt JOIN users u ON u.id=prt.user_id WHERE prt.token_hash=? AND prt.status='requested'", (digest,)).fetchone()
        if not row:
            raise AppError("Reset link is invalid or already used.", 400)
        if row["expires_at"] <= now_iso():
            con.execute("UPDATE password_reset_tokens SET status='expired' WHERE id=?", (row["id"],))
            raise AppError("Reset link has expired.", 400)
        password_hash, salt = hash_password(password)
        con.execute("UPDATE users SET password_hash=?, salt=?, updated_at=? WHERE id=?", (password_hash, salt, now_iso(), row["user_id"]))
        con.execute("UPDATE password_reset_tokens SET status='used', used_at=? WHERE id=?", (now_iso(), row["id"]))
        con.execute("DELETE FROM sessions WHERE user_id=?", (row["user_id"],))
        create_notification(con, "email", row["email"], "Juquilita password changed", "Your password was changed. If you did not request this, call the bakery immediately.", "password_reset", row["user_id"])
        audit(con, handler, None, "password_reset_confirm", "user", row["user_id"], None, {"email": row["email"]})
    return {"ok": True, "message": "Password reset. You can sign in with the new password."}


def run_sqlite_backup(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_permission(handler, "system:backup")
    require_csrf(handler, user)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    started = now_iso()
    backup_name = f"bakery-{utc_now().strftime('%Y%m%d-%H%M%S')}.db"
    target = BACKUP_DIR / backup_name
    with connect() as con:
        cur = con.execute("INSERT INTO backup_runs(backup_type,status,file_path,started_at,notes) VALUES('sqlite','started',?,?,?)", (str(target), started, "SQLite online backup started from admin console."))
        backup_id = int(cur.lastrowid)
    status = "success"
    notes = ""
    checksum = ""
    size = 0
    try:
        src = sqlite3.connect(DB_PATH)
        dst = sqlite3.connect(target)
        with dst:
            src.backup(dst)
        dst.close(); src.close()
        raw = target.read_bytes()
        checksum = hashlib.sha256(raw).hexdigest()
        size = len(raw)
        notes = "SQLite backup completed. Copy this file off-server for real disaster recovery."
    except Exception as exc:
        status = "failed"
        notes = str(exc)[:1000]
    with connect() as con:
        con.execute("UPDATE backup_runs SET status=?,file_size_bytes=?,checksum_sha256=?,finished_at=?,notes=? WHERE id=?", (status, size, checksum, now_iso(), notes, backup_id))
        audit(con, handler, user, "run_backup", "backup", backup_id, None, {"status": status, "file": str(target)})
    if status != "success":
        raise AppError("Backup failed.", 500, {"notes": notes})
    return {"ok": True, "backup_id": backup_id, "file_path": str(target), "file_size_bytes": size, "checksum_sha256": checksum}


def deep_health() -> dict[str, Any]:
    checks: dict[str, Any] = {"time": now_iso(), "version": APP_VERSION, "ok": True, "environment": "production" if production_mode() else "local"}
    try:
        with connect() as con:
            checks["db"] = {"ok": True, "products": con.execute("SELECT COUNT(*) AS n FROM products").fetchone()["n"], "queued_notifications": con.execute("SELECT COUNT(*) AS n FROM notifications WHERE status='queued'").fetchone()["n"]}
            settings = setting_map(con)
            provider = settings.get("payment_provider", "mock")
            ready, message = provider_ready(provider)
            checks["payments"] = {"provider": provider, "ready": ready, "message": message}
            checks["email"] = {"ready": bool(os.environ.get("SENDGRID_API_KEY") and os.environ.get("SENDGRID_FROM_EMAIL"))}
            checks["sms"] = {"ready": bool(os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN") and os.environ.get("TWILIO_FROM_PHONE"))}
            checks["security"] = {
                "secure_cookies": env_bool("JB_SECURE_COOKIES") or production_mode(),
                "assume_https": env_bool("JB_ASSUME_HTTPS"),
                "public_base_url": bool(os.environ.get("JB_PUBLIC_BASE_URL", "").strip()),
                "token_pepper": bool(os.environ.get("JB_TOKEN_PEPPER", "").strip()),
                "demo_accounts_present": bool(con.execute("SELECT 1 FROM users WHERE email IN ('admin@juquilita.local','guest@juquilita.local','wholesale@taqueria.local') LIMIT 1").fetchone()),
            }
            if production_mode():
                checks["ok"] = checks["ok"] and ready and checks["email"]["ready"] and checks["sms"]["ready"] and not checks["security"]["demo_accounts_present"]
    except Exception as exc:
        checks["ok"] = False
        checks["db"] = {"ok": False, "error": str(exc)[:300]}
    try:
        usage = shutil.disk_usage(BASE_DIR)
        checks["disk"] = {"free_mb": round(usage.free / 1024 / 1024, 1), "total_mb": round(usage.total / 1024 / 1024, 1)}
    except Exception:
        pass
    return checks


def run_static_qa(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_permission(handler, "qa:manage")
    require_csrf(handler, user)
    audit_type = clean_text(data.get("audit_type") or "accessibility", 40)
    if audit_type not in {"accessibility", "mobile", "security", "performance"}:
        raise AppError("Invalid QA audit type.")
    target_url = clean_text(data.get("target_url") or "/", 300)
    findings: list[tuple[str, str, str, str]] = []
    html_files = [PUBLIC_DIR / "index.html", PUBLIC_DIR / "admin.html"]
    for file in html_files:
        text = file.read_text(encoding="utf-8")
        if audit_type == "accessibility":
            checks = [
                ("html-lang", "pass" if re.search(r"<html[^>]+lang=", text, re.I) else "fail", "high", f"{file.name} should declare a language."),
                ("viewport", "pass" if 'name="viewport"' in text else "fail", "high", f"{file.name} should define viewport for zoom/mobile."),
                ("form-labels", "manual", "medium", f"Review visible labels and ARIA labels in {file.name}."),
                ("keyboard-focus", "manual", "high", f"Run keyboard-only traversal on {file.name}."),
            ]
        elif audit_type == "mobile":
            checks = [
                ("viewport", "pass" if 'name="viewport"' in text else "fail", "high", f"{file.name} has viewport meta."),
                ("cart-drawer-small-screen", "manual", "high", "Test cart, checkout, admin tables on 360px width."),
                ("tap-targets", "manual", "medium", "Confirm buttons and chips are easy to tap."),
            ]
        elif audit_type == "security":
            checks = [
                ("no-prefilled-passwords", "pass" if "AdminPass2026" not in text else "fail", "critical", f"{file.name} must not prefill demo passwords."),
                ("admin-link-hidden", "pass" if "admin.html" not in (PUBLIC_DIR/"index.html").read_text(encoding="utf-8") else "manual", "medium", "Admin link should stay out of public navigation."),
            ]
        else:
            checks = [
                ("image-compression", "manual", "medium", "Run Lighthouse and compress real photos into responsive sizes."),
                ("script-size", "manual", "low", "Measure JS and CSS after final photo upload."),
            ]
        findings.extend(checks)
    score = round(sum(1 for _, status, _, _ in findings if status == "pass") / max(len(findings), 1) * 100, 1)
    status = "pass" if score >= 90 and all(f[1] != "fail" for f in findings) else "needs_manual_review"
    with connect() as con:
        cur = con.execute("INSERT INTO qa_audit_runs(audit_type,tool_name,target_url,score,status,summary,report_path,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?)", (audit_type, "v6 static QA scaffold", target_url, score, status, f"{len(findings)} checks created. Run Lighthouse/manual device tests before launch.", "", user.id, now_iso()))
        run_id = int(cur.lastrowid)
        for key, item_status, severity, notes in findings:
            con.execute("INSERT INTO qa_audit_items(run_id,audit_type,check_key,status,severity,notes,updated_at) VALUES(?,?,?,?,?,?,?)", (run_id, audit_type, key, item_status, severity, notes, now_iso()))
        audit(con, handler, user, "run_qa_audit", "qa_audit", run_id, None, {"audit_type": audit_type, "score": score})
    return {"ok": True, "run_id": run_id, "score": score, "status": status, "findings": [{"key": k, "status": st, "severity": sv, "notes": nt} for k, st, sv, nt in findings]}


def save_qa_item(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_permission(handler, "qa:manage")
    require_csrf(handler, user)
    item_id = parse_int(data.get("item_id"), "QA item id", min_value=1, max_value=10_000_000)
    status = clean_text(data.get("status"), 40)
    if status not in {"todo", "pass", "fail", "manual", "not_applicable"}:
        raise AppError("Invalid QA item status.")
    with connect() as con:
        before = con.execute("SELECT * FROM qa_audit_items WHERE id=?", (item_id,)).fetchone()
        if not before:
            raise AppError("QA item not found.", 404)
        con.execute("UPDATE qa_audit_items SET status=?, notes=?, updated_at=? WHERE id=?", (status, clean_text(data.get("notes") or before["notes"], 1200), now_iso(), item_id))
        audit(con, handler, user, "update_qa_item", "qa_item", item_id, dict(before), {"status": status})
    return {"ok": True}


def save_supplier_quote(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_permission(handler, "suppliers:manage")
    require_csrf(handler, user)
    supplier_id = int(data.get("supplier_id") or 0) or None
    ingredient_id = int(data.get("ingredient_id") or 0) or None
    quoted_unit = clean_text(data.get("quoted_unit") or "case", 40)
    quoted_qty = parse_money(data.get("quoted_qty") or 1, "quoted quantity", min_value=0.0001, max_value=1_000_000)
    quoted_total = parse_money(data.get("quoted_total") or 0, "quoted total", min_value=0, max_value=1_000_000)
    effective_on = clean_text(data.get("effective_on") or today_str(), 20)
    status = clean_text(data.get("status") or "draft", 40)
    if status not in {"draft", "owner_verified", "expired", "rejected"}:
        raise AppError("Invalid supplier quote status.")
    with connect() as con:
        cur = con.execute("""
            INSERT INTO supplier_price_quotes(supplier_id,ingredient_id,quoted_unit,quoted_qty,quoted_total,effective_on,source_doc,verified_by,status,notes,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
        """, (supplier_id, ingredient_id, quoted_unit, quoted_qty, quoted_total, effective_on, clean_text(data.get("source_doc"), 500), user.email if status == "owner_verified" else "", status, clean_text(data.get("notes"), 1200), now_iso(), now_iso()))
        quote_id = int(cur.lastrowid)
        if ingredient_id and quoted_qty and status == "owner_verified":
            con.execute("UPDATE ingredients SET cost_per_unit=?, updated_at=? WHERE id=?", (round(float(quoted_total) / float(quoted_qty), 4), now_iso(), ingredient_id))
        audit(con, handler, user, "save_supplier_quote", "supplier_price_quote", quote_id, None, {"status": status})
    return {"ok": True, "quote_id": quote_id}


def verify_recipe(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_permission(handler, "recipes:verify")
    require_csrf(handler, user)
    product_id = parse_int(data.get("product_id"), "product id", min_value=1, max_value=10_000_000)
    recipe_version = clean_text(data.get("recipe_version") or "v1", 30)
    fields = {
        "yield_qty": parse_money(data.get("yield_qty") or 1, "yield quantity", min_value=0.001, max_value=100000),
        "yield_unit": clean_text(data.get("yield_unit") or "each", 40),
        "labor_minutes": parse_money(data.get("labor_minutes") or 0, "labor minutes", min_value=0, max_value=10000),
        "owner_verified": 1 if data.get("owner_verified", True) else 0,
        "verified_by": clean_text(data.get("verified_by") or user.email, 160),
        "verified_at": now_iso() if data.get("owner_verified", True) else "",
        "notes": clean_text(data.get("notes"), 1200),
        "updated_at": now_iso(),
    }
    with connect() as con:
        if not con.execute("SELECT 1 FROM products WHERE id=?", (product_id,)).fetchone():
            raise AppError("Product not found.", 404)
        con.execute("""
            INSERT INTO recipe_verifications(product_id,recipe_version,yield_qty,yield_unit,labor_minutes,owner_verified,verified_by,verified_at,notes,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(product_id,recipe_version) DO UPDATE SET yield_qty=excluded.yield_qty,yield_unit=excluded.yield_unit,labor_minutes=excluded.labor_minutes,owner_verified=excluded.owner_verified,verified_by=excluded.verified_by,verified_at=excluded.verified_at,notes=excluded.notes,updated_at=excluded.updated_at
        """, (product_id, recipe_version, fields["yield_qty"], fields["yield_unit"], fields["labor_minutes"], fields["owner_verified"], fields["verified_by"], fields["verified_at"], fields["notes"], fields["updated_at"]))
        audit(con, handler, user, "verify_recipe", "product", product_id, None, {"version": recipe_version, "owner_verified": fields["owner_verified"]})
    return {"ok": True}


def save_staff(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_permission(handler, "staff:manage")
    require_csrf(handler, user)
    email = clean_text(data.get("email"), 160).lower()
    name = clean_text(data.get("name"), 120)
    role = clean_text(data.get("role") or "cashier", 40)
    phone = clean_text(data.get("phone"), 80)
    permissions = data.get("permissions") or []
    if isinstance(permissions, str):
        permissions = [x.strip() for x in permissions.split(",") if x.strip()]
    if role not in STAFF_ROLES or not valid_email(email) or len(name) < 2:
        raise AppError("Valid staff name, email, and role are required.")
    with connect() as con:
        existing = con.execute("SELECT * FROM users WHERE lower(email)=lower(?)", (email,)).fetchone()
        if existing:
            staff_id = existing["id"]
            before = dict(existing)
            con.execute("UPDATE users SET name=?, role=?, phone=?, updated_at=? WHERE id=?", (name, role, phone, now_iso(), staff_id))
        else:
            password = str(data.get("temporary_password") or secrets.token_urlsafe(12))
            staff_id = seed_user(con, email, password, name, role, "Juquilita Bakery", phone, role)
            before = None
            create_notification(con, "email", email, "Juquilita staff account", f"Your staff account was created. Temporary password: {password}. Change it after login.", "staff", staff_id)
        con.execute("DELETE FROM staff_permissions WHERE user_id=?", (staff_id,))
        con.execute("DELETE FROM user_staff_roles WHERE user_id=?", (staff_id,))
        con.execute("INSERT OR IGNORE INTO user_staff_roles(user_id,role_key,assigned_by,created_at) VALUES(?,?,?,?)", (staff_id, role, user.id, now_iso()))
        for perm in permissions:
            if con.execute("SELECT 1 FROM permission_catalog WHERE permission_key=?", (perm,)).fetchone():
                con.execute("INSERT OR IGNORE INTO staff_permissions(user_id,permission_key,granted_by,created_at) VALUES(?,?,?,?)", (staff_id, perm, user.id, now_iso()))
        audit(con, handler, user, "save_staff", "user", staff_id, before, {"role": role, "permissions": permissions})
    return {"ok": True, "staff_id": staff_id}



def verify_stripe_webhook_signature(handler: BaseHTTPRequestHandler) -> None:
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    if not secret:
        return
    header = handler.headers.get("Stripe-Signature", "")
    parts = {}
    for item in header.split(","):
        if "=" in item:
            key, value = item.split("=", 1)
            parts.setdefault(key.strip(), []).append(value.strip())
    timestamps = parts.get("t") or []
    signatures = parts.get("v1") or []
    if not timestamps or not signatures:
        raise AppError("Missing Stripe webhook signature.", 400)
    try:
        ts = int(timestamps[0])
    except ValueError:
        raise AppError("Invalid Stripe webhook timestamp.", 400)
    if abs(int(time.time()) - ts) > 300:
        raise AppError("Stripe webhook timestamp is outside tolerance.", 400)
    raw = getattr(handler, "raw_body", b"")
    signed_payload = f"{ts}.".encode("utf-8") + raw
    expected = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    if not any(secrets.compare_digest(expected, sig) for sig in signatures):
        raise AppError("Invalid Stripe webhook signature.", 400)


def verify_square_webhook_signature(handler: BaseHTTPRequestHandler) -> None:
    secret = os.environ.get("SQUARE_WEBHOOK_SIGNATURE_KEY", "")
    if not secret:
        return
    signature = handler.headers.get("X-Square-HmacSha256-Signature") or handler.headers.get("X-Square-Signature") or ""
    if not signature:
        raise AppError("Missing Square webhook signature.", 400)
    notification_url = os.environ.get("SQUARE_WEBHOOK_NOTIFICATION_URL", f"{public_base_url(handler)}/api/webhooks/square")
    raw = getattr(handler, "raw_body", b"")
    expected = base64.b64encode(hmac.new(secret.encode("utf-8"), notification_url.encode("utf-8") + raw, hashlib.sha256).digest()).decode("ascii")
    if not secrets.compare_digest(expected, signature):
        raise AppError("Invalid Square webhook signature.", 400)


def handle_square_webhook(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    verify_square_webhook_signature(handler)
    event_type = clean_text(data.get("type") or data.get("event_type") or "square.event", 120)
    payload_text = json_dumps(data)[:5000]
    matched = []
    with connect() as con:
        for row in con.execute("SELECT id,provider_reference FROM payment_intents WHERE provider='square' AND provider_reference!='' AND status='requires_payment'").fetchall():
            if row["provider_reference"] and row["provider_reference"] in payload_text:
                matched.append(int(row["id"]))
        status_text = payload_text.upper()
        new_status = "paid" if any(x in status_text for x in ["COMPLETED", "APPROVED", "PAID"]) else "provider_event"
        for payment_id in matched:
            con.execute("UPDATE payment_intents SET status=?, provider_response=?, updated_at=? WHERE id=?", (new_status, payload_text, now_iso(), payment_id))
        con.execute("INSERT INTO integration_events(provider,event_type,related_type,related_id,status,payload_json,created_at) VALUES(?,?,?,?,?,?,?)", ("square", event_type, "payment_intent", matched[0] if matched else 0, "processed", payload_text, now_iso()))
    return {"ok": True, "received": True, "matched_payment_intents": matched}

def handle_stripe_webhook(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    verify_stripe_webhook_signature(handler)
    event_type = clean_text(data.get("type"), 120)
    obj = (data.get("data") or {}).get("object") if isinstance(data.get("data"), dict) else {}
    payment_intent_id = None
    if isinstance(obj, dict):
        meta = obj.get("metadata") or {}
        try:
            payment_intent_id = int(meta.get("payment_intent_id")) if meta.get("payment_intent_id") else None
        except Exception:
            payment_intent_id = None
    with connect() as con:
        status = "processed"
        if event_type in {"checkout.session.completed", "checkout.session.async_payment_succeeded"} and payment_intent_id:
            con.execute("UPDATE payment_intents SET status='paid', provider_response=?, updated_at=? WHERE id=?", (json_dumps(data)[:2000], now_iso(), payment_intent_id))
        elif event_type in {"checkout.session.async_payment_failed", "payment_intent.payment_failed"} and payment_intent_id:
            con.execute("UPDATE payment_intents SET status='failed', provider_response=?, updated_at=? WHERE id=?", (json_dumps(data)[:2000], now_iso(), payment_intent_id))
        else:
            status = "ignored"
        con.execute("INSERT INTO integration_events(provider,event_type,related_type,related_id,status,payload_json,created_at) VALUES(?,?,?,?,?,?,?)", ("stripe", event_type, "payment_intent", payment_intent_id or 0, status, json_dumps(data)[:5000], now_iso()))
    return {"ok": True, "status": status}



def make_receipt_token() -> str:
    return "rct_" + secrets.token_urlsafe(32)


def order_cutoff_times(pickup_date: str, pickup_time: str, max_lead_hours: int) -> tuple[str, str]:
    try:
        pickup_dt = parse_local_pickup(pickup_date, pickup_time)
    except AppError:
        return "", ""
    edit_cutoff = pickup_dt - timedelta(hours=max(2, min(max_lead_hours or 2, 24)))
    cancel_cutoff = pickup_dt - timedelta(hours=max(4, min(max_lead_hours or 4, 48)))
    return cancel_cutoff.replace(microsecond=0).isoformat(), edit_cutoff.replace(microsecond=0).isoformat()


def create_order_production_tasks(con: sqlite3.Connection, order_id: int, order_code: str, pickup_date: str, pickup_time: str, customer_type: str, lines: list[dict[str, Any]], notes: str = "") -> None:
    due_at = f"{pickup_date}T{pickup_time}:00"
    categories = {line["product"]["category_key"] for line in lines}
    title_base = f"{order_code} pickup {pickup_time}"
    con.execute("INSERT INTO production_tasks(order_id,assigned_role,task_type,title,due_at,priority,status,public_notes,internal_notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (order_id, "cashier", "pickup_pack", f"Pack and verify {title_base}", due_at, "high" if customer_type == "premium" else "normal", "todo", "Confirm order, receipt, payment due, and substitutions.", notes[:800], now_iso(), now_iso()))
    con.execute("INSERT INTO production_tasks(order_id,assigned_role,task_type,title,due_at,priority,status,public_notes,internal_notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (order_id, "baker", "bread_production", f"Bake totals for {title_base}", due_at, "high" if customer_type == "premium" else "normal", "todo", "Use production summary totals before marking ready.", notes[:800], now_iso(), now_iso()))
    if "cakes" in categories or "seasonal" in categories:
        con.execute("INSERT INTO production_tasks(order_id,assigned_role,task_type,title,due_at,priority,status,public_notes,internal_notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (order_id, "decorator", "custom_finish", f"Finish custom/seasonal items for {title_base}", due_at, "high", "todo", "Verify decoration, inscription, packaging, and refrigeration needs.", notes[:800], now_iso(), now_iso()))
    if customer_type == "premium":
        con.execute("INSERT INTO production_tasks(order_id,assigned_role,task_type,title,due_at,priority,status,public_notes,internal_notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (order_id, "wholesale_manager", "wholesale_pack", f"Wholesale pack list for {title_base}", due_at, "high", "todo", "Check standing-order notes, invoice terms, and business pickup contact.", notes[:800], now_iso(), now_iso()))


def place_order(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    session_user = get_session_user(handler)
    role = session_user.role if session_user else "guest"
    if role == "admin":
        role = "guest"
    customer = data.get("customer", {}) if isinstance(data.get("customer", {}), dict) else {}
    name = clean_text(customer.get("name") or (session_user.name if session_user else ""), 120)
    email = clean_text(customer.get("email") or (session_user.email if session_user else ""), 160).lower()
    phone = clean_text(customer.get("phone") or (session_user.phone if session_user else ""), 60)
    business_name = clean_text(customer.get("business_name") or (session_user.business_name if session_user else ""), 160)
    pickup_date = clean_text(data.get("pickup_date"), 20)
    pickup_time = clean_text(data.get("pickup_time"), 20)
    notes = clean_text(data.get("notes"), 1000)
    customer_language = clean_text(data.get("customer_language") or customer.get("language") or "en", 10).lower()
    if customer_language not in {"en", "es"}:
        customer_language = "en"
    substitution_preference = clean_text(data.get("substitution_preference") or customer.get("substitution_preference") or "call_me", 60)
    if substitution_preference not in {"call_me", "similar_ok", "refund_item"}:
        raise AppError("Choose a valid substitution preference.")
    promo_code = clean_text(data.get("promo_code"), 40).upper()
    payment_method = clean_text(data.get("payment_method") or "pay_at_pickup", 80)
    if payment_method not in {"pay_at_pickup", "deposit_pending", "deposit_card", "full_card", "manual_invoice"}:
        raise AppError("Choose a valid payment method.")
    if len(name) < 2:
        raise AppError("Customer name is required.")
    if not valid_email(email):
        raise AppError("A valid email is required.")
    if not valid_phone(phone):
        raise AppError("A valid phone number is required.")
    if role == "premium" and not business_name:
        raise AppError("Business name is required for premium wholesale checkout.")
    items = data.get("items")
    if not isinstance(items, list):
        raise AppError("Basket items are required.")
    with connect() as con:
        settings = setting_map(con)
        lines, subtotal, max_lead, warnings = prepare_order_lines(con, items, role)
        validate_pickup(con, pickup_date, pickup_time, max_lead)
        promo, discount = compute_promo(con, lines, subtotal, role, email, session_user.id if session_user else None, promo_code)
        tax_rate = float(settings.get("sales_tax_rate", "0") or 0)
        tax = round(max(subtotal - discount, 0) * tax_rate, 2)
        total = round(subtotal - discount + tax, 2)
        has_deposit_item = any(line["product"]["category_key"] in ("cakes", "seasonal") or line["product"]["stock_policy"] == "made_to_order" for line in lines)
        threshold = float(settings.get("large_order_deposit_threshold", "75") or 75)
        deposit_rate = float(settings.get("cake_deposit_rate", "0.40") or 0.40)
        deposit_due = round(total * deposit_rate, 2) if has_deposit_item or total >= threshold else 0.0
        if payment_method == "full_card":
            deposit_due = total
        status = "needs_deposit" if deposit_due > 0 and payment_method in {"deposit_pending", "deposit_card", "full_card", "manual_invoice"} else "received"
        order_code = f"JB6-{utc_now().strftime('%y%m%d')}-{secrets.randbelow(9000)+1000}"
        receipt_token = make_receipt_token()
        cancellation_cutoff_at, edit_cutoff_at = order_cutoff_times(pickup_date, pickup_time, max_lead)
        cur = con.execute(
            """
            INSERT INTO orders(order_code,user_id,customer_name,customer_email,customer_phone,business_name,customer_type,pickup_date,pickup_time,fulfillment,payment_method,notes,customer_language,substitution_preference,receipt_token,cancellation_cutoff_at,edit_cutoff_at,subtotal,discount,tax,total,deposit_due,promo_code,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (order_code, session_user.id if session_user else None, name, email, phone, business_name, role, pickup_date, pickup_time, "pickup", payment_method, notes, customer_language, substitution_preference, receipt_token, cancellation_cutoff_at, edit_cutoff_at, subtotal, discount, tax, total, deposit_due, promo["code"] if promo else "", status, now_iso(), now_iso()),
        )
        order_id = int(cur.lastrowid)
        for line in lines:
            p = line["product"]
            con.execute(
                """
                INSERT INTO order_items(order_id,product_id,product_slug,product_name,unit_price,quantity,variant_summary,options_json,line_total,production_category)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                """,
                (order_id, p["id"], p["slug"], f"{p['name_es']} / {p['name_en']}", line["unit_price"], line["quantity"], line["variant_summary"], json_dumps(line["options"]), line["line_total"], p["category_key"]),
            )
            if p["stock_policy"] == "track":
                con.execute("UPDATE products SET stock_count=stock_count-?, updated_at=? WHERE id=?", (line["quantity"], now_iso(), p["id"]))
                con.execute("INSERT INTO inventory_movements(product_id,change_qty,reason,order_id,user_id,created_at) VALUES(?,?,?,?,?,?)", (p["id"], -line["quantity"], "customer_order", order_id, session_user.id if session_user else None, now_iso()))
        if promo:
            con.execute("INSERT INTO promo_redemptions(promotion_id,order_id,user_id,customer_email,redeemed_at) VALUES(?,?,?,?,?)", (promo["id"], order_id, session_user.id if session_user else None, email, now_iso()))
        create_order_production_tasks(con, order_id, order_code, pickup_date, pickup_time, role, lines, notes)
        con.execute("INSERT OR REPLACE INTO notification_preferences(email,phone,preferred_channel,language_preference,do_not_text,do_not_email,source,updated_at) VALUES(?,?,?,?,?,?,?,?)", (email, phone, "sms", customer_language, 0, 0, "checkout", now_iso()))
        payment_intent = None
        if deposit_due > 0 and payment_method in {"deposit_card", "full_card"}:
            provider = settings.get("payment_provider", "mock") or "mock"
            payment_intent = create_payment_intent_record(con, order_id=order_id, quote_id=None, amount=deposit_due, kind="full" if payment_method == "full_card" else "deposit", provider=provider, notes="Checkout payment placeholder. Configure Stripe/Square before production.")
        create_notification(con, "email", email, f"Juquilita order {order_code}", f"Your pickup order was received for {pickup_date} at {pickup_time}. Total: ${total:.2f}", "order", order_id)
        create_notification(con, "sms", phone, f"Order {order_code}", f"Juquilita received your order for {pickup_date} {pickup_time}. Total ${total:.2f}", "order", order_id)
        create_notification(con, "admin", "bakery_counter", f"New order {order_code}", f"{name} placed {len(lines)} line item(s), pickup {pickup_date} {pickup_time}.", "order", order_id)
        if session_user and settings.get("loyalty_enabled", "true") == "true":
            points_per_dollar = float(settings.get("loyalty_points_per_dollar", "1") or 1)
            points = int(round(total * points_per_dollar))
            if points > 0:
                con.execute("INSERT INTO loyalty_ledger(user_id,order_id,points,reason,created_at) VALUES(?,?,?,?,?)", (session_user.id, order_id, points, f"Order {order_code}", now_iso()))
        audit(con, handler, session_user, "create_order", "order", order_id, None, {"order_code": order_code, "total": total})
        return {"ok": True, "order_id": order_id, "order_code": order_code, "total": total, "deposit_due": deposit_due, "payment_intent": payment_intent, "receipt_url": f"/receipt?token={receipt_token}", "receipt_token": receipt_token, "warnings": warnings, "promo_applied": promo["code"] if promo else ""}


def create_quote(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = get_session_user(handler)
    product_slug = clean_text(data.get("product_slug"), 140)
    name = clean_text(data.get("customer_name") or (user.name if user else ""), 120)
    email = clean_text(data.get("customer_email") or (user.email if user else ""), 160).lower()
    phone = clean_text(data.get("customer_phone") or (user.phone if user else ""), 60)
    if len(name) < 2:
        raise AppError("Name is required for a quote.")
    if not valid_email(email):
        raise AppError("Valid email is required for a quote.")
    if not valid_phone(phone):
        raise AppError("Valid phone is required for a quote.")
    with connect() as con:
        product_id = None
        if product_slug:
            product = con.execute("SELECT id FROM products WHERE slug=?", (product_slug,)).fetchone()
            product_id = product["id"] if product else None
        quote_code = f"Q6-{utc_now().strftime('%y%m%d')}-{secrets.randbelow(9000)+1000}"
        quote_public_token = "qte_" + secrets.token_urlsafe(24)
        exact_confirmed = 1 if data.get("exact_inscription_confirmed") in {True, "true", "on", "1", 1} else 0
        expires_at = (utc_now() + timedelta(days=14)).replace(microsecond=0).isoformat() + "Z"
        cur = con.execute(
            """
            INSERT INTO quote_requests(quote_code,user_id,product_id,customer_name,customer_email,customer_phone,business_name,event_type,event_date,pickup_date,pickup_time,quantity,budget,flavor,filling,inscription,style_notes,reference_url,reference_image_url,complexity_tier,servings,colors,exact_inscription_confirmed,pickup_handling,quote_public_token,expires_at,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (quote_code, user.id if user else None, product_id, name, email, phone, clean_text(data.get("business_name"), 160), clean_text(data.get("event_type"), 120), clean_text(data.get("event_date"), 20), clean_text(data.get("pickup_date"), 20), clean_text(data.get("pickup_time"), 20), parse_int(data.get("quantity") or 1, "quantity", min_value=1, max_value=500), clean_text(data.get("budget"), 80), clean_text(data.get("flavor"), 120), clean_text(data.get("filling"), 120), clean_text(data.get("inscription"), 200), clean_text(data.get("style_notes"), 1500), clean_text(data.get("reference_url"), 300), clean_text(data.get("reference_image_url") or data.get("reference_url"), 600), clean_text(data.get("complexity_tier"), 80), parse_int(data.get("servings") or 0, "servings", min_value=0, max_value=5000), clean_text(data.get("colors"), 200), exact_confirmed, clean_text(data.get("pickup_handling"), 300), quote_public_token, expires_at, "new", now_iso(), now_iso()),
        )
        quote_id = int(cur.lastrowid)
        con.execute("INSERT INTO production_tasks(quote_id,assigned_role,task_type,title,due_at,priority,status,public_notes,internal_notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)", (quote_id, "decorator", "quote_review", f"Review quote {quote_code}", clean_text(data.get("pickup_date"), 20) + "T" + (clean_text(data.get("pickup_time"), 20) or "17:00") + ":00", "high" if clean_text(data.get("event_type"),120).lower() in {"wedding","quinceanera","quinceañera"} else "normal", "todo", "Review size, flavor, decoration, inscription, deposit, and pickup handling.", clean_text(data.get("style_notes"), 1500), now_iso(), now_iso()))
        create_notification(con, "email", email, f"Juquilita quote {quote_code}", "Your quote request was received. The bakery can review details and respond.", "quote", quote_id)
        create_notification(con, "admin", "bakery_counter", f"New quote {quote_code}", f"{name} requested a quote for {data.get('event_type','a bakery item')}.", "quote", quote_id)
        audit(con, handler, user, "create_quote", "quote", quote_id, None, {"quote_code": quote_code})
        return {"ok": True, "quote_id": quote_id, "quote_code": quote_code, "quote_token": quote_public_token, "expires_at": expires_at}


def apply_wholesale(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = get_session_user(handler)
    business = clean_text(data.get("business_name"), 160)
    contact = clean_text(data.get("contact_name") or (user.name if user else ""), 120)
    email = clean_text(data.get("email") or (user.email if user else ""), 160).lower()
    phone = clean_text(data.get("phone") or (user.phone if user else ""), 60)
    business_type = clean_text(data.get("business_type"), 120)
    if not business or not contact or not business_type:
        raise AppError("Business name, contact name, and business type are required.")
    if not valid_email(email) or not valid_phone(phone):
        raise AppError("Valid email and phone are required.")
    weekly_units = parse_int(data.get("expected_weekly_units") or 0, "expected weekly units", min_value=0, max_value=50000)
    with connect() as con:
        user_id = user.id if user else None
        if user and user.role == "guest":
            con.execute("UPDATE users SET role='pending_premium', business_name=?, phone=?, updated_at=? WHERE id=?", (business, phone, now_iso(), user.id))
        cur = con.execute(
            """
            INSERT INTO wholesale_applications(user_id,business_name,contact_name,email,phone,business_type,expected_weekly_units,requested_products,delivery_or_pickup,notes,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (user_id, business, contact, email, phone, business_type, weekly_units, clean_text(data.get("requested_products"), 600), clean_text(data.get("delivery_or_pickup") or "pickup", 40), clean_text(data.get("notes"), 1000), "pending", now_iso(), now_iso()),
        )
        app_id = int(cur.lastrowid)
        create_notification(con, "admin", "owner", f"Wholesale application: {business}", f"{contact} requested premium buying for {weekly_units} expected units/week.", "wholesale_application", app_id)
        audit(con, handler, user, "create_wholesale_application", "wholesale_application", app_id, None, {"business": business})
        return {"ok": True, "application_id": app_id, "status": "pending"}


def create_standing_order(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler)
    require_csrf(handler, user)
    if user.role not in {"premium", "admin"}:
        raise AppError("Standing orders are available to approved premium buyers.", 403)
    name = clean_text(data.get("name"), 120)
    weekday = parse_int(data.get("weekday"), "weekday", min_value=0, max_value=6)
    pickup_time = clean_text(data.get("pickup_time"), 10)
    business = clean_text(data.get("business_name") or user.business_name, 160)
    items = data.get("items")
    if not name or not business or not isinstance(items, list) or not items:
        raise AppError("Standing order name, business, and items are required.")
    with connect() as con:
        cur = con.execute(
            """
            INSERT INTO standing_orders(user_id,business_name,name,weekday,pickup_time,notes,is_active,created_at,updated_at)
            VALUES(?,?,?,?,?,?,1,?,?)
            """,
            (user.id, business, name, weekday, pickup_time, clean_text(data.get("notes"), 600), now_iso(), now_iso()),
        )
        standing_id = int(cur.lastrowid)
        for raw in items[:40]:
            slug = clean_text(raw.get("slug"), 120)
            qty = parse_int(raw.get("quantity"), "quantity", min_value=1, max_value=1000)
            product = get_product_by_slug(con, slug)
            con.execute("INSERT INTO standing_order_items(standing_order_id,product_id,quantity,variant_summary) VALUES(?,?,?,?)", (standing_id, product["id"], qty, clean_text(raw.get("variant_summary"), 300)))
        audit(con, handler, user, "create_standing_order", "standing_order", standing_id, None, {"name": name})
        return {"ok": True, "standing_order_id": standing_id}


def summarize_orders(con: sqlite3.Connection) -> dict[str, Any]:
    today = date.today()
    metrics = {}
    metrics["open_orders"] = con.execute("SELECT COUNT(*) AS n FROM orders WHERE status NOT IN ('completed','canceled')").fetchone()["n"]
    metrics["today_pickups"] = con.execute("SELECT COUNT(*) AS n FROM orders WHERE pickup_date=? AND status NOT IN ('canceled')", (today.isoformat(),)).fetchone()["n"]
    metrics["quote_requests"] = con.execute("SELECT COUNT(*) AS n FROM quote_requests WHERE status IN ('new','reviewing')").fetchone()["n"]
    metrics["pending_wholesale"] = con.execute("SELECT COUNT(*) AS n FROM wholesale_applications WHERE status='pending'").fetchone()["n"]
    metrics["low_stock"] = con.execute("SELECT COUNT(*) AS n FROM products WHERE stock_policy='track' AND stock_count < 20 AND is_active=1").fetchone()["n"]
    metrics["needs_photo"] = con.execute("SELECT COUNT(*) AS n FROM products WHERE is_active=1 AND (photo_status!='real_photo_verified' OR image_url='')").fetchone()["n"]
    metrics["payments_open"] = con.execute("SELECT COUNT(*) AS n FROM payment_intents WHERE status='requires_payment'").fetchone()["n"]
    metrics["change_requests"] = con.execute("SELECT COUNT(*) AS n FROM order_change_requests WHERE status IN ('new','reviewing')").fetchone()["n"]
    metrics["reviews_pending"] = con.execute("SELECT COUNT(*) AS n FROM product_reviews WHERE status='new'").fetchone()["n"]
    metrics["invoices_open"] = con.execute("SELECT COUNT(*) AS n FROM invoices WHERE status IN ('draft','sent') AND balance_due > 0").fetchone()["n"]
    metrics["p0_open"] = con.execute("SELECT COUNT(*) AS n FROM launch_checklist WHERE priority='P0' AND status!='done'").fetchone()["n"]
    revenue = con.execute("SELECT COALESCE(SUM(total),0) AS total FROM orders WHERE status NOT IN ('canceled') AND created_at >= ?", ((utc_now() - timedelta(days=30)).replace(microsecond=0).isoformat() + "Z",)).fetchone()["total"]
    metrics["revenue_30d"] = round(float(revenue or 0), 2)
    return metrics


def production_summary(con: sqlite3.Connection, days: int = 7) -> list[dict[str, Any]]:
    end = (date.today() + timedelta(days=days)).isoformat()
    rows = con.execute(
        """
        SELECT oi.product_slug, oi.product_name, oi.production_category, SUM(oi.quantity) AS quantity, MIN(o.pickup_date) AS first_pickup, MAX(o.pickup_date) AS last_pickup
        FROM order_items oi JOIN orders o ON o.id=oi.order_id
        WHERE o.pickup_date BETWEEN ? AND ? AND o.status NOT IN ('completed','canceled')
        GROUP BY oi.product_slug, oi.product_name, oi.production_category
        ORDER BY oi.production_category, quantity DESC
        """,
        (date.today().isoformat(), end),
    ).fetchall()
    return rows_to_dicts(rows)


def build_forecast(con: sqlite3.Connection) -> dict[str, Any]:
    since = (utc_now() - timedelta(days=90)).replace(microsecond=0).isoformat() + "Z"
    rows = con.execute(
        """
        SELECT oi.product_slug, oi.product_name, oi.production_category, SUM(oi.quantity) AS qty
        FROM order_items oi JOIN orders o ON o.id=oi.order_id
        WHERE o.created_at >= ? AND o.status NOT IN ('canceled')
        GROUP BY oi.product_slug, oi.product_name, oi.production_category
        ORDER BY qty DESC
        LIMIT 20
        """,
        (since,),
    ).fetchall()
    baseline = rows_to_dicts(rows)
    total_units = sum(float(row["qty"] or 0) for row in baseline) or 1
    events = rows_to_dicts(con.execute("SELECT * FROM seasonal_events WHERE is_active=1 ORDER BY start_date").fetchall())
    event_forecasts = []
    for event in events:
        multiplier = float(event["demand_multiplier"] or 1)
        focus_tokens = {x.strip() for x in (event["focus_products"] + "," + event["focus_categories"]).split(",") if x.strip()}
        relevant = []
        for row in baseline:
            weight = 1.0
            if row["product_slug"] in focus_tokens or row["production_category"] in focus_tokens:
                weight = multiplier
            projected = round(float(row["qty"] or 0) * weight / 6, 1)
            if weight > 1 or len(relevant) < 6:
                relevant.append({"product_slug": row["product_slug"], "product_name": row["product_name"], "projected_units": projected, "basis": "90-day order history plus event multiplier"})
        # Coarse ingredient estimates for operational planning.
        projected_units = sum(x["projected_units"] for x in relevant[:10])
        ingredients = {
            "flour_lb": round(projected_units * 0.16, 1),
            "eggs_est": int(round(projected_units * 0.22)),
            "sugar_lb": round(projected_units * 0.05, 1),
            "packaging_units": int(round(projected_units * 1.08)),
        }
        event_forecasts.append({"event": event, "products": relevant[:10], "ingredient_estimate": ingredients})
    local_events = rows_to_dicts(con.execute("SELECT * FROM local_events WHERE is_active=1 ORDER BY event_date LIMIT 20").fetchall())
    weather_adjustments = rows_to_dicts(con.execute("SELECT * FROM weather_adjustments WHERE is_active=1 ORDER BY demand_multiplier DESC").fetchall())
    pos_rows = con.execute("SELECT COUNT(*) AS n FROM pos_sales_rows").fetchone()["n"]
    app_orders = con.execute("SELECT COUNT(*) AS n FROM orders WHERE created_at >= ?", (since,)).fetchone()["n"]
    if pos_rows >= 500:
        confidence = "medium"
    elif app_orders >= 50 or pos_rows >= 100:
        confidence = "low-medium"
    else:
        confidence = "prototype"
    return {"baseline_top_products": baseline, "total_units_in_sample": total_units, "events": event_forecasts, "local_events": local_events, "weather_adjustments": weather_adjustments, "confidence": confidence, "pos_rows": pos_rows, "app_order_sample": app_orders, "caveat": "Forecast uses local app order history, staged POS rows, manual local events, and weather adjustment rules. Connect real POS history before relying on it for purchasing."}

def catalog_health(con: sqlite3.Connection) -> dict[str, Any]:
    total = con.execute("SELECT COUNT(*) AS n FROM products WHERE is_active=1").fetchone()["n"]
    verified = con.execute("SELECT COUNT(*) AS n FROM catalog_verifications WHERE status='owner_verified'").fetchone()["n"]
    needs_photo = con.execute("SELECT COUNT(*) AS n FROM products WHERE is_active=1 AND (photo_status!='real_photo_verified' OR image_url='')").fetchone()["n"]
    quote_items = con.execute("SELECT COUNT(*) AS n FROM products WHERE is_active=1 AND order_mode='quote'").fetchone()["n"]
    p0_open = con.execute("SELECT COUNT(*) AS n FROM launch_checklist WHERE priority='P0' AND status!='done'").fetchone()["n"]
    return {"active_products": total, "owner_verified": verified, "needs_photo": needs_photo, "quote_items": quote_items, "p0_open": p0_open}


def ensure_custom_quote_product(con: sqlite3.Connection) -> int:
    row = con.execute("SELECT id FROM products WHERE slug='custom-quote-service'").fetchone()
    if row:
        return int(row["id"])
    cur = con.execute(
        """
        INSERT INTO products(slug,name_es,name_en,category_key,subcategory,description_es,description_en,base_price,wholesale_price,unit,stock_count,stock_policy,lead_time_hours,order_mode,is_featured,is_bulk_friendly,is_seasonal,search_terms,image_alt,image_accent,icon,photo_status,price_basis,allergen_notes,ingredient_notes,margin_estimate,is_active,created_at,updated_at)
        VALUES('custom-quote-service','Cotización personalizada','Custom quote service','cakes','custom','Producto interno para convertir cotizaciones en pedidos.','Internal product used to convert approved quotes into orders.',NULL,NULL,'quote',0,'quote',24,'quote',0,0,0,'custom quote cake seasonal','Custom quote service','marigold','🧾','not_applicable','Internal v3 quote conversion helper.','varies by quote','Owner-verified after quote approval.',0.60,0,?,?)
        """,
        (now_iso(), now_iso()),
    )
    return int(cur.lastrowid)


def create_payment_intent_record(con: sqlite3.Connection, *, order_id: int | None, quote_id: int | None, amount: float,
                                 kind: str, provider: str, notes: str = "") -> dict[str, Any]:
    amount = round(float(amount), 2)
    provider = (provider or "mock").lower().strip()
    if provider not in {"mock", "stripe", "square"}:
        provider = "mock"
    if amount <= 0:
        raise AppError("Payment amount must be greater than zero.")
    provider_reference = f"{provider.upper()}-{utc_now().strftime('%y%m%d')}-{secrets.randbelow(900000)+100000}"
    checkout_url = f"/receipt?code={provider_reference}" if provider == "mock" else "provider-checkout-pending"
    cur = con.execute(
        """
        INSERT INTO payment_intents(order_id,quote_id,provider,kind,amount,status,provider_reference,checkout_url,notes,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)
        """,
        (order_id, quote_id, provider, kind, amount, "requires_payment", provider_reference, checkout_url, notes, now_iso(), now_iso()),
    )
    payment_id = int(cur.lastrowid)
    external = create_external_checkout(con, payment_id=payment_id, order_id=order_id, quote_id=quote_id, provider=provider, amount=amount, kind=kind)
    provider_reference = external.get("reference") or provider_reference
    checkout_url = external.get("checkout_url") or checkout_url
    provider_notes = (notes + "\n" + external.get("message", "")).strip()
    con.execute(
        "UPDATE payment_intents SET provider_reference=?, checkout_url=?, notes=?, updated_at=? WHERE id=?",
        (provider_reference, checkout_url, provider_notes[:1000], now_iso(), payment_id),
    )
    con.execute(
        "INSERT INTO integration_events(provider,event_type,related_type,related_id,status,payload_json,created_at) VALUES(?,?,?,?,?,?,?)",
        (provider, "payment_checkout_created", "payment_intent", payment_id, "processed" if external.get("configured") else "failed", json_dumps({k:v for k,v in external.items() if k != "raw"})[:5000], now_iso()),
    )
    return {"id": payment_id, "provider": provider, "kind": kind, "amount": amount, "status": "requires_payment", "provider_reference": provider_reference, "checkout_url": checkout_url, "notes": provider_notes}


def render_receipt_html(con: sqlite3.Connection, receipt_ref: str, *, lookup: str = "token") -> str:
    ref = clean_text(receipt_ref, 120)
    if lookup == "code":
        order = con.execute("SELECT * FROM orders WHERE order_code=?", (ref,)).fetchone()
    else:
        order = con.execute("SELECT * FROM orders WHERE receipt_token=? AND receipt_token!=''", (ref,)).fetchone()
    if not order:
        # Also allow a mock payment reference to display a concise placeholder.
        pi = con.execute("SELECT * FROM payment_intents WHERE provider_reference=?", (ref,)).fetchone()
        if pi:
            return f"""<!doctype html><html><head><meta charset='utf-8'><title>Payment placeholder</title><link rel='stylesheet' href='styles.css'></head><body class='receipt-page'><main class='receipt'><h1>Payment placeholder</h1><p>This mock payment intent is for ${float(pi['amount']):.2f}. Configure Stripe or Square before production.</p><p><b>Reference:</b> {esc_html(ref)}</p><script>window.print&&false</script></main></body></html>"""
        raise AppError("Receipt not found.", 404)
    items = con.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order["id"],)).fetchall()
    payments = con.execute("SELECT * FROM payment_intents WHERE order_id=? ORDER BY created_at", (order["id"],)).fetchall()
    settings = setting_map(con)
    item_rows = "".join(f"<tr><td>{int(i['quantity'])}</td><td>{esc_html(i['product_name'])}<br><small>{esc_html(i['variant_summary'] or '')}</small></td><td>${float(i['unit_price']):.2f}</td><td>${float(i['line_total']):.2f}</td></tr>" for i in items)
    payment_rows = "".join(f"<li>{esc_html(pmt['kind'])}: ${float(pmt['amount']):.2f} • {esc_html(pmt['status'])} • {esc_html(pmt['provider_reference'])}</li>" for pmt in payments) or "<li>No deposit recorded yet.</li>"
    balance_due = max(float(order["total"] or 0) - sum(float(p["amount"] or 0) for p in payments if p["status"] in {"paid", "manual_received"}), 0)
    return f"""<!doctype html>
<html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Receipt {esc_html(order['order_code'])}</title><link rel='stylesheet' href='styles.css'></head>
<body class='receipt-page'><main class='receipt'>
<header><h1>Juquilita Bakery</h1><p>Panadería y Pastelería<br>{esc_html(settings.get('address',''))}<br>{esc_html(settings.get('phone',''))} • {esc_html(settings.get('email',''))}</p></header>
<section class='receipt-meta'><div><b>Order</b><span>{esc_html(order['order_code'])}</span></div><div><b>Pickup</b><span>{esc_html(order['pickup_date'])} {esc_html(order['pickup_time'])}</span></div><div><b>Status</b><span>{esc_html(order['status'])}</span></div><div><b>Customer</b><span>{esc_html(order['customer_name'])}<br>{esc_html(order['customer_phone'])}</span></div><div><b>Substitution</b><span>{esc_html(order['substitution_preference'] if 'substitution_preference' in order.keys() else 'call_me')}</span></div></section>
<table class='data-table receipt-table'><thead><tr><th>Qty</th><th>Item</th><th>Unit</th><th>Total</th></tr></thead><tbody>{item_rows}</tbody></table>
<section class='receipt-totals'><p><span>Subtotal</span><b>${float(order['subtotal']):.2f}</b></p><p><span>Discount</span><b>${float(order['discount']):.2f}</b></p><p><span>Tax</span><b>${float(order['tax']):.2f}</b></p><p><span>Total</span><b>${float(order['total']):.2f}</b></p><p><span>Balance due</span><b>${balance_due:.2f}</b></p></section>
<section><h2>Payments</h2><ul>{payment_rows}</ul></section>
<section><h2>Notes</h2><p>{esc_html(order['notes'] or '')}</p></section>
<footer>{esc_html(settings.get('receipt_footer','Thank you.'))}</footer>
<button onclick='window.print()' class='primary-action no-print'>Print receipt</button>
</main></body></html>"""


def esc_html(value: Any) -> str:
    return str(value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#39;")


def render_ticket_html(con: sqlite3.Connection, order_id: int) -> str:
    order = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
    if not order:
        raise AppError("Order not found.", 404)
    items = con.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY production_category, id", (order_id,)).fetchall()
    rows = "".join(f"<li><b>{int(i['quantity'])} ×</b> {esc_html(i['product_name'])}<br><small>{esc_html(i['variant_summary'] or '')}</small></li>" for i in items)
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Kitchen ticket {esc_html(order['order_code'])}</title><link rel='stylesheet' href='styles.css'></head><body class='receipt-page'><main class='receipt ticket'><h1>Production ticket</h1><h2>{esc_html(order['order_code'])}</h2><p><b>Pickup:</b> {esc_html(order['pickup_date'])} {esc_html(order['pickup_time'])}<br><b>Customer:</b> {esc_html(order['customer_name'])} • {esc_html(order['customer_phone'])}</p><ol>{rows}</ol><p><b>Notes:</b> {esc_html(order['notes'] or '')}</p><button onclick='window.print()' class='primary-action no-print'>Print ticket</button></main></body></html>"""


def track_order(handler: BaseHTTPRequestHandler, query: dict[str, list[str]]) -> dict[str, Any]:
    code = clean_text((query.get("code") or [""])[0], 80)
    email = clean_text((query.get("email") or [""])[0], 160).lower()
    if not code or not valid_email(email):
        raise AppError("Order code and email are required.")
    with connect() as con:
        order = con.execute("SELECT * FROM orders WHERE order_code=? AND lower(customer_email)=lower(?)", (code, email)).fetchone()
        if not order:
            raise AppError("Order not found for that email.", 404)
        data = dict(order)
        data["receipt_url"] = f"/receipt?token={order['receipt_token']}" if order["receipt_token"] else ""
        data["items"] = rows_to_dicts(con.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order["id"],)).fetchall())
        data["payments"] = rows_to_dicts(con.execute("SELECT * FROM payment_intents WHERE order_id=? ORDER BY created_at", (order["id"],)).fetchall())
        return {"ok": True, "order": data}



def request_password_reset(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    email = clean_text(data.get("email"), 160).lower()
    if not valid_email(email):
        raise AppError("A valid email is required.")
    ip = client_ip(handler)
    with connect() as con:
        # Generic response protects account enumeration. The actual reset email is queued only for real accounts.
        recent = con.execute("SELECT COUNT(*) AS n FROM password_reset_tokens WHERE requester_ip=? AND requested_at>=?", (ip, (utc_now() - timedelta(hours=1)).replace(microsecond=0).isoformat() + "Z")).fetchone()["n"]
        if int(recent) > 10:
            return {"ok": True, "message": "If that account exists, a reset message was queued."}
        user = con.execute("SELECT id,email,name FROM users WHERE lower(email)=lower(?) AND is_active=1", (email,)).fetchone()
        if user:
            token = secrets.token_urlsafe(40)
            digest = token_digest(token)
            expires = (utc_now() + timedelta(hours=2)).replace(microsecond=0).isoformat() + "Z"
            reset_link = f"{public_base_url(handler)}/reset.html?token={token}"
            con.execute("""
                INSERT INTO password_reset_tokens(user_id,token,token_hash,token_suffix,requester_ip,status,requested_at,expires_at)
                VALUES(?,?,?,?,?,?,?,?)
            """, (user["id"], digest, digest, token[-6:], ip, "requested", now_iso(), expires))
            create_notification(con, "email", email, "Reset your Juquilita Bakery password", f"Use this secure reset link within 2 hours:\n\n{reset_link}\n\nIf you did not request this, ignore this email.", "password_reset", user["id"])
            audit(con, handler, None, "request_password_reset", "user", user["id"], None, {"email": email, "token_suffix": token[-6:]})
        return {"ok": True, "message": "If that account exists, a reset message was queued."}


def favorite_product(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler)
    require_csrf(handler, user)
    slug = clean_text(data.get("slug"), 140)
    enabled = 1 if data.get("enabled", True) else 0
    with connect() as con:
        product = con.execute("SELECT id FROM products WHERE slug=? AND is_active=1", (slug,)).fetchone()
        if not product:
            raise AppError("Product not found.", 404)
        if enabled:
            con.execute("INSERT OR IGNORE INTO customer_favorites(user_id,product_id,created_at) VALUES(?,?,?)", (user.id, product["id"], now_iso()))
        else:
            con.execute("DELETE FROM customer_favorites WHERE user_id=? AND product_id=?", (user.id, product["id"]))
        audit(con, handler, user, "toggle_favorite", "product", product["id"], None, {"enabled": enabled})
        return {"ok": True, "enabled": bool(enabled)}


def reorder_from_order(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler)
    require_csrf(handler, user)
    order_id = parse_int(data.get("order_id"), "order id", min_value=1, max_value=10_000_000)
    with connect() as con:
        order = con.execute("SELECT * FROM orders WHERE id=? AND (user_id=? OR lower(customer_email)=lower(?))", (order_id, user.id, user.email)).fetchone()
        if not order:
            raise AppError("Order not found for this account.", 404)
        items = []
        for item in con.execute("SELECT oi.*, p.order_mode, p.is_active FROM order_items oi JOIN products p ON p.id=oi.product_id WHERE oi.order_id=?", (order_id,)).fetchall():
            if item["is_active"] and item["order_mode"] == "order":
                items.append({"slug": item["product_slug"], "quantity": int(item["quantity"]), "variant_ids": []})
        if not items:
            raise AppError("No orderable items are available to reorder.")
        return {"ok": True, "items": items, "source_order_code": order["order_code"]}


def request_order_change(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = get_session_user(handler)
    if user:
        require_csrf(handler, user)
    order_code = clean_text(data.get("order_code"), 80)
    email = clean_text(data.get("email") or (user.email if user else ""), 160).lower()
    request_type = clean_text(data.get("request_type"), 40)
    reason = clean_text(data.get("reason"), 1200)
    if request_type not in {"cancel", "edit", "reschedule", "substitution"}:
        raise AppError("Choose a valid change request type.")
    if not order_code or not valid_email(email) or len(reason) < 5:
        raise AppError("Order code, email, and a clear reason are required.")
    with connect() as con:
        order = con.execute("SELECT * FROM orders WHERE order_code=? AND lower(customer_email)=lower(?)", (order_code, email)).fetchone()
        if not order:
            raise AppError("Order not found for that email.", 404)
        if order["status"] in {"completed", "canceled"}:
            raise AppError("Completed or canceled orders cannot be changed.")
        cur = con.execute(
            """
            INSERT INTO order_change_requests(order_id,user_id,request_type,customer_email,customer_phone,reason,requested_payload,status,admin_notes,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (order["id"], user.id if user else order["user_id"], request_type, email, clean_text(data.get("phone") or order["customer_phone"], 80), reason, json_dumps(data.get("requested_payload", {})), "new", "", now_iso(), now_iso()),
        )
        rid = int(cur.lastrowid)
        create_notification(con, "admin", "bakery_counter", f"Change request for {order_code}", f"Customer requested {request_type}: {reason}", "order_change_request", rid)
        create_notification(con, "email", email, f"Change request received for {order_code}", "The bakery will review your request before changing the order.", "order_change_request", rid)
        audit(con, handler, user, "create_order_change_request", "order", order["id"], None, {"request_type": request_type})
        return {"ok": True, "request_id": rid, "status": "new"}


def submit_product_review(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = get_session_user(handler)
    if user:
        require_csrf(handler, user)
    slug = clean_text(data.get("product_slug"), 140)
    name = clean_text(data.get("customer_name") or (user.name if user else ""), 120)
    email = clean_text(data.get("customer_email") or (user.email if user else ""), 160).lower()
    rating = parse_int(data.get("rating"), "rating", min_value=1, max_value=5)
    body = clean_text(data.get("body"), 1200)
    title = clean_text(data.get("title"), 160)
    order_code = clean_text(data.get("order_code"), 80)
    if not name or not valid_email(email) or len(body) < 5:
        raise AppError("Name, email, rating, and review text are required.")
    with connect() as con:
        product = con.execute("SELECT id FROM products WHERE slug=?", (slug,)).fetchone() if slug else None
        order = con.execute("SELECT id FROM orders WHERE order_code=? AND lower(customer_email)=lower(?)", (order_code, email)).fetchone() if order_code else None
        cur = con.execute(
            """
            INSERT INTO product_reviews(product_id,order_id,user_id,customer_name,customer_email,rating,title,body,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (product["id"] if product else None, order["id"] if order else None, user.id if user else None, name, email, rating, title, body, "new", now_iso(), now_iso()),
        )
        rid = int(cur.lastrowid)
        create_notification(con, "admin", "owner", "New product review", f"{name} left a {rating}-star review. Review before publishing.", "product_review", rid)
        audit(con, handler, user, "submit_review", "product_review", rid, None, {"rating": rating})
        return {"ok": True, "review_id": rid, "status": "new"}


def save_change_request_status(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    request_id = parse_int(data.get("request_id"), "request id", min_value=1, max_value=10_000_000)
    status = clean_text(data.get("status"), 40)
    if status not in {"new", "reviewing", "approved", "declined", "completed"}:
        raise AppError("Invalid request status.")
    notes = clean_text(data.get("admin_notes"), 1200)
    with connect() as con:
        before = con.execute("SELECT ocr.*, o.order_code FROM order_change_requests ocr JOIN orders o ON o.id=ocr.order_id WHERE ocr.id=?", (request_id,)).fetchone()
        if not before:
            raise AppError("Change request not found.", 404)
        con.execute("UPDATE order_change_requests SET status=?, admin_notes=?, updated_at=? WHERE id=?", (status, notes, now_iso(), request_id))
        create_notification(con, "email", before["customer_email"], f"Change request update for {before['order_code']}", f"Status: {status}. {notes}", "order_change_request", request_id)
        audit(con, handler, user, "update_change_request", "order_change_request", request_id, dict(before), {"status": status})
        return {"ok": True}


def save_review_status(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    review_id = parse_int(data.get("review_id"), "review id", min_value=1, max_value=10_000_000)
    status = clean_text(data.get("status"), 40)
    if status not in {"new", "approved", "hidden"}:
        raise AppError("Invalid review status.")
    with connect() as con:
        before = con.execute("SELECT * FROM product_reviews WHERE id=?", (review_id,)).fetchone()
        if not before:
            raise AppError("Review not found.", 404)
        con.execute("UPDATE product_reviews SET status=?, updated_at=? WHERE id=?", (status, now_iso(), review_id))
        audit(con, handler, user, "update_review_status", "product_review", review_id, dict(before), {"status": status})
        return {"ok": True}


def save_bundle(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    slug = clean_text(data.get("slug"), 120).lower()
    if not re.match(r"^[a-z0-9-]+$", slug):
        raise AppError("Bundle slug must use lowercase letters, numbers, and hyphens.")
    items_text = clean_text(data.get("items_json"), 4000)
    try:
        items = json.loads(items_text)
    except Exception:
        raise AppError("Bundle items must be valid JSON like {\"bolillo\": 12}.")
    if not isinstance(items, dict) or not items:
        raise AppError("Bundle needs at least one product quantity.")
    with connect() as con:
        for product_slug, qty in items.items():
            parse_int(qty, f"quantity for {product_slug}", min_value=1, max_value=5000)
            if not con.execute("SELECT 1 FROM products WHERE slug=?", (product_slug,)).fetchone():
                raise AppError(f"Unknown product in bundle: {product_slug}")
        before = con.execute("SELECT * FROM bundles WHERE slug=?", (slug,)).fetchone()
        fields = (slug, clean_text(data.get("name_en"), 160), clean_text(data.get("name_es"), 160), clean_text(data.get("description_en"), 600), clean_text(data.get("description_es"), 600), json_dumps(items), parse_int(data.get("sort_order") or 100, "sort order", min_value=0, max_value=10000), 1 if data.get("is_active", True) else 0)
        if before:
            con.execute("UPDATE bundles SET name_en=?, name_es=?, description_en=?, description_es=?, items_json=?, sort_order=?, is_active=? WHERE slug=?", (fields[1], fields[2], fields[3], fields[4], fields[5], fields[6], fields[7], slug))
            bid = before["id"]
        else:
            cur = con.execute("INSERT INTO bundles(slug,name_en,name_es,description_en,description_es,items_json,sort_order,is_active) VALUES(?,?,?,?,?,?,?,?)", fields)
            bid = int(cur.lastrowid)
        audit(con, handler, user, "save_bundle", "bundle", bid, dict(before) if before else None, {"slug": slug})
        return {"ok": True, "bundle_id": bid}


def save_ingredient(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    ingredient_id = int(data.get("id") or 0)
    fields = {
        "name_en": clean_text(data.get("name_en"), 160), "name_es": clean_text(data.get("name_es"), 160),
        "unit": clean_text(data.get("unit") or "lb", 30),
        "current_qty": parse_money(data.get("current_qty") or 0, "current quantity", min_value=0, max_value=1_000_000),
        "reorder_point": parse_money(data.get("reorder_point") or 0, "reorder point", min_value=0, max_value=1_000_000),
        "cost_per_unit": parse_money(data.get("cost_per_unit") or 0, "cost per unit", min_value=0, max_value=10000),
        "updated_at": now_iso(),
    }
    if not fields["name_en"] or not fields["name_es"]:
        raise AppError("Ingredient names are required.")
    with connect() as con:
        if ingredient_id:
            before = con.execute("SELECT * FROM ingredients WHERE id=?", (ingredient_id,)).fetchone()
            if not before:
                raise AppError("Ingredient not found.", 404)
            con.execute("UPDATE ingredients SET name_en=?,name_es=?,unit=?,current_qty=?,reorder_point=?,cost_per_unit=?,updated_at=? WHERE id=?", (*fields.values(), ingredient_id))
            iid = ingredient_id
        else:
            cur = con.execute("INSERT INTO ingredients(name_en,name_es,unit,current_qty,reorder_point,cost_per_unit,updated_at) VALUES(?,?,?,?,?,?,?)", tuple(fields.values()))
            iid = int(cur.lastrowid)
            before = None
        audit(con, handler, user, "save_ingredient", "ingredient", iid, dict(before) if before else None, fields)
        return {"ok": True, "ingredient_id": iid}


def save_supplier(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    supplier_id = int(data.get("id") or 0)
    fields = {
        "name": clean_text(data.get("name"), 180), "contact_name": clean_text(data.get("contact_name"), 120),
        "phone": clean_text(data.get("phone"), 80), "email": clean_text(data.get("email"), 160),
        "lead_days": parse_int(data.get("lead_days") or 1, "lead days", min_value=0, max_value=90),
        "minimum_order": clean_text(data.get("minimum_order"), 120), "notes": clean_text(data.get("notes"), 1200),
        "updated_at": now_iso(),
    }
    if not fields["name"]:
        raise AppError("Supplier name is required.")
    with connect() as con:
        if supplier_id:
            before = con.execute("SELECT * FROM suppliers WHERE id=?", (supplier_id,)).fetchone()
            if not before:
                raise AppError("Supplier not found.", 404)
            con.execute("UPDATE suppliers SET name=?,contact_name=?,phone=?,email=?,lead_days=?,minimum_order=?,notes=?,updated_at=? WHERE id=?", (*fields.values(), supplier_id))
            sid = supplier_id
        else:
            cur = con.execute("INSERT INTO suppliers(name,contact_name,phone,email,lead_days,minimum_order,notes,updated_at) VALUES(?,?,?,?,?,?,?,?)", tuple(fields.values()))
            sid = int(cur.lastrowid)
            before = None
        audit(con, handler, user, "save_supplier", "supplier", sid, dict(before) if before else None, fields)
        return {"ok": True, "supplier_id": sid}


def save_product_ingredient(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    product_id = parse_int(data.get("product_id"), "product id", min_value=1, max_value=10_000_000)
    ingredient_id = parse_int(data.get("ingredient_id"), "ingredient id", min_value=1, max_value=10_000_000)
    qty = parse_money(data.get("qty_per_unit"), "quantity per unit", min_value=0, max_value=100000)
    with connect() as con:
        if not con.execute("SELECT 1 FROM products WHERE id=?", (product_id,)).fetchone() or not con.execute("SELECT 1 FROM ingredients WHERE id=?", (ingredient_id,)).fetchone():
            raise AppError("Product or ingredient not found.", 404)
        con.execute("INSERT INTO product_ingredients(product_id,ingredient_id,qty_per_unit) VALUES(?,?,?) ON CONFLICT(product_id,ingredient_id) DO UPDATE SET qty_per_unit=excluded.qty_per_unit", (product_id, ingredient_id, qty))
        audit(con, handler, user, "save_product_ingredient", "product", product_id, None, {"ingredient_id": ingredient_id, "qty": qty})
        return {"ok": True}


def save_local_event(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    title = clean_text(data.get("title"), 180)
    event_date = clean_text(data.get("event_date"), 20)
    try:
        date.fromisoformat(event_date)
    except ValueError:
        raise AppError("Event date must be valid.")
    with connect() as con:
        cur = con.execute("INSERT INTO local_events(title,event_date,event_type,expected_impact,demand_multiplier,notes,is_active,updated_at) VALUES(?,?,?,?,?,?,?,?)", (title, event_date, clean_text(data.get("event_type") or "community", 80), clean_text(data.get("expected_impact") or "normal", 80), parse_money(data.get("demand_multiplier") or 1, "demand multiplier", min_value=0.1, max_value=5), clean_text(data.get("notes"), 1200), 1 if data.get("is_active", True) else 0, now_iso()))
        audit(con, handler, user, "save_local_event", "local_event", int(cur.lastrowid), None, {"title": title})
        return {"ok": True, "event_id": int(cur.lastrowid)}


def save_weather_adjustment(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    label = clean_text(data.get("label"), 160)
    condition_key = clean_text(data.get("condition_key"), 80).lower()
    if not label or not condition_key:
        raise AppError("Weather label and key are required.")
    with connect() as con:
        cur = con.execute("INSERT INTO weather_adjustments(label,condition_key,demand_multiplier,categories,prep_notes,is_active,updated_at) VALUES(?,?,?,?,?,?,?)", (label, condition_key, parse_money(data.get("demand_multiplier") or 1, "demand multiplier", min_value=0.1, max_value=5), clean_text(data.get("categories") or "all", 300), clean_text(data.get("prep_notes"), 1000), 1 if data.get("is_active", True) else 0, now_iso()))
        audit(con, handler, user, "save_weather_adjustment", "weather_adjustment", int(cur.lastrowid), None, {"label": label})
        return {"ok": True, "adjustment_id": int(cur.lastrowid)}


def create_invoice(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    order_id = parse_int(data.get("order_id"), "order id", min_value=1, max_value=10_000_000)
    with connect() as con:
        order = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not order:
            raise AppError("Order not found.", 404)
        paid = con.execute("SELECT COALESCE(SUM(amount),0) AS n FROM payment_intents WHERE order_id=? AND status IN ('paid','manual_received')", (order_id,)).fetchone()["n"]
        balance = max(float(order["total"] or 0) - float(paid or 0), 0)
        invoice_code = f"INV-{utc_now().strftime('%y%m%d')}-{secrets.randbelow(9000)+1000}"
        cur = con.execute("INSERT INTO invoices(invoice_code,user_id,order_id,business_name,contact_email,subtotal,discount,tax,total,balance_due,terms,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (invoice_code, order["user_id"], order_id, order["business_name"] or order["customer_name"], order["customer_email"], order["subtotal"], order["discount"], order["tax"], order["total"], balance, clean_text(data.get("terms") or "Due on pickup", 120), "sent", clean_text(data.get("notes"), 600), now_iso(), now_iso()))
        iid = int(cur.lastrowid)
        create_notification(con, "email", order["customer_email"], f"Juquilita invoice {invoice_code}", f"Invoice total ${float(order['total']):.2f}; balance due ${balance:.2f}.", "invoice", iid)
        audit(con, handler, user, "create_invoice", "invoice", iid, None, {"invoice_code": invoice_code, "order_id": order_id})
        return {"ok": True, "invoice_id": iid, "invoice_code": invoice_code}


def save_notification_status(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    notification_id = parse_int(data.get("notification_id"), "notification id", min_value=1, max_value=10_000_000)
    status = clean_text(data.get("status"), 40)
    if status not in {"queued", "sent", "failed", "canceled"}:
        raise AppError("Invalid notification status.")
    with connect() as con:
        before = con.execute("SELECT * FROM notifications WHERE id=?", (notification_id,)).fetchone()
        if not before:
            raise AppError("Notification not found.", 404)
        con.execute("UPDATE notifications SET status=?, sent_at=? WHERE id=?", (status, now_iso() if status == "sent" else before["sent_at"], notification_id))
        audit(con, handler, user, "update_notification_status", "notification", notification_id, dict(before), {"status": status})
        return {"ok": True}


def product_margin_report(con: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = con.execute(
        """
        SELECT p.id,p.slug,p.name_es,p.name_en,p.base_price,p.wholesale_price,p.margin_estimate,
               COALESCE(SUM(pi.qty_per_unit * i.cost_per_unit),0) AS ingredient_cost
        FROM products p
        LEFT JOIN product_ingredients pi ON pi.product_id=p.id
        LEFT JOIN ingredients i ON i.id=pi.ingredient_id
        WHERE p.is_active=1
        GROUP BY p.id
        ORDER BY ingredient_cost DESC, p.name_es
        LIMIT 180
        """
    ).fetchall()
    report = []
    for row in rows:
        price = float(row["base_price"] or 0)
        cost = float(row["ingredient_cost"] or 0)
        gross_margin = round((price - cost) / price, 3) if price > 0 else None
        report.append({**dict(row), "gross_margin": gross_margin, "margin_warning": bool(gross_margin is not None and gross_margin < 0.35)})
    return report


def customer_admin_summary(con: sqlite3.Connection) -> dict[str, Any]:
    users = rows_to_dicts(con.execute("SELECT id,email,name,role,business_name,phone,wholesale_tier,is_active,created_at FROM users ORDER BY created_at DESC LIMIT 100").fetchall())
    change_requests = rows_to_dicts(con.execute("SELECT ocr.*, o.order_code, o.pickup_date, o.pickup_time FROM order_change_requests ocr JOIN orders o ON o.id=ocr.order_id ORDER BY ocr.created_at DESC LIMIT 100").fetchall())
    reviews = rows_to_dicts(con.execute("SELECT pr.*, p.slug,p.name_es,p.name_en FROM product_reviews pr LEFT JOIN products p ON p.id=pr.product_id ORDER BY pr.created_at DESC LIMIT 120").fetchall())
    favorites = rows_to_dicts(con.execute("SELECT cf.created_at,u.email,u.name,p.slug,p.name_es,p.name_en FROM customer_favorites cf JOIN users u ON u.id=cf.user_id JOIN products p ON p.id=cf.product_id ORDER BY cf.created_at DESC LIMIT 100").fetchall())
    loyalty = rows_to_dicts(con.execute("SELECT u.email,u.name,COALESCE(SUM(ll.points),0) AS points FROM users u LEFT JOIN loyalty_ledger ll ON ll.user_id=u.id GROUP BY u.id ORDER BY points DESC LIMIT 100").fetchall())
    return {"users": users, "change_requests": change_requests, "reviews": reviews, "favorites": favorites, "loyalty": loyalty}


def render_seo_page(con: sqlite3.Connection, slug: str) -> str:
    page = con.execute("SELECT * FROM seo_pages WHERE slug=?", (clean_text(slug, 160),)).fetchone()
    if not page or page["status"] != "published":
        raise AppError("Page not found.", 404)
    settings = setting_map(con)
    blocks = rows_to_dicts(con.execute("SELECT * FROM content_blocks WHERE is_active=1 ORDER BY placement, block_key").fetchall())
    outline = esc_html(page["content_outline"] or "")
    block_html = "".join(f"<article class='seo-card'><h2>{esc_html(b['title'])}</h2><p>{esc_html(b['body_en'])}</p><small>{esc_html(b['body_es'])}</small></article>" for b in blocks[:4])
    schema = json_dumps({
        "@context": "https://schema.org",
        "@type": "Bakery",
        "name": "Juquilita Bakery",
        "telephone": settings.get("phone", ""),
        "email": settings.get("email", ""),
        "address": settings.get("address", ""),
        "servesCuisine": ["Mexican bakery", "Oaxacan bread", "Pan dulce"],
        "url": f"/page/{slug}",
        "description": page["meta_description"],
    })
    return f"""<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>{esc_html(page['title'])}</title><meta name='description' content='{esc_html(page['meta_description'])}'><meta property='og:title' content='{esc_html(page['title'])}'><meta property='og:description' content='{esc_html(page['meta_description'])}'><meta property='og:type' content='website'><script type='application/ld+json'>{esc_html(schema)}</script><link rel='stylesheet' href='/styles.css'></head><body><header class='site-header'><a class='brand' href='/index.html'><span class='brand-mark'>JB</span><span><strong>Juquilita Bakery</strong><small>Panadería y Pastelería</small></span></a><nav class='top-nav'><a href='/index.html#menu'>Menu</a><a href='/index.html#quotes'>Quotes</a><a href='/index.html#wholesale'>Wholesale</a></nav></header><main class='section-shell seo-page'><p class='eyebrow'>{esc_html(page['target_keyword'])}</p><h1>{esc_html(page['title'])}</h1><p class='hero-text'>{esc_html(page['meta_description'])}</p><section class='seo-card'><h2>Page plan</h2><p>{outline}</p></section>{block_html}<section class='seo-card'><h2>Visit or contact</h2><p>{esc_html(settings.get('address',''))}<br>{esc_html(settings.get('phone',''))} • {esc_html(settings.get('email',''))}</p><a class='primary-action' href='/index.html#menu'>Order from the menu</a></section></main></body></html>"""


def render_labels_html(con: sqlite3.Connection, label_date: str) -> str:
    user_orders = con.execute("SELECT * FROM orders WHERE pickup_date=? AND status NOT IN ('canceled') ORDER BY pickup_time, customer_name", (label_date,)).fetchall()
    label_cards = []
    for order in user_orders:
        items = con.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY product_name", (order["id"],)).fetchall()
        lines = "".join(f"<li>{int(i['quantity'])} × {esc_html(i['product_name'])}</li>" for i in items)
        label_cards.append(f"<article class='bag-label'><h2>{esc_html(order['order_code'])}</h2><p><b>{esc_html(order['customer_name'])}</b><br>{esc_html(order['pickup_time'])} • {esc_html(order['customer_phone'])}</p><ul>{lines}</ul><small>{esc_html(order['notes'] or '')}</small></article>")
    if not label_cards:
        label_cards.append("<article class='bag-label'><h2>No labels</h2><p>No active orders for this date.</p></article>")
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>Pickup labels {esc_html(label_date)}</title><link rel='stylesheet' href='/styles.css'></head><body class='receipt-page'><main class='label-sheet'><h1>Pickup labels: {esc_html(label_date)}</h1><button onclick='window.print()' class='primary-action no-print'>Print labels</button><section class='label-grid'>{''.join(label_cards)}</section></main></body></html>"""

def upload_product_photo(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    product_id = parse_int(data.get("product_id"), "product id", min_value=1, max_value=10_000_000)
    data_url = str(data.get("data_url") or "")
    alt_text = clean_text(data.get("alt_text"), 300)
    status = clean_text(data.get("image_status") or "approved", 40)
    if status not in {"placeholder", "needs_reshoot", "approved", "archived"}:
        raise AppError("Invalid image status.")
    with connect() as con:
        product = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not product:
            raise AppError("Product not found.", 404)
        match = re.match(r"^data:image/(png|jpeg|jpg|webp);base64,(.+)$", data_url, re.I | re.S)
        if not match:
            raise AppError("Upload must be a PNG, JPG, or WEBP data URL.")
        ext = "jpg" if match.group(1).lower() in {"jpg", "jpeg"} else match.group(1).lower()
        try:
            raw = base64.b64decode(match.group(2), validate=True)
        except Exception:
            raise AppError("Image data is invalid.")
        if len(raw) > 5_000_000:
            raise AppError("Image must be under 5 MB for this local prototype.")
        upload_dir = PUBLIC_DIR / "uploads" / "products"
        upload_dir.mkdir(parents=True, exist_ok=True)
        filename = f"{product['slug']}-{utc_now().strftime('%Y%m%d%H%M%S')}-{secrets.token_hex(3)}.{ext}"
        path = upload_dir / filename
        path.write_bytes(raw)
        url = f"/uploads/products/{filename}"
        if data.get("is_primary", True):
            con.execute("UPDATE product_images SET is_primary=0 WHERE product_id=?", (product_id,))
        cur = con.execute(
            """
            INSERT INTO product_images(product_id,image_url,alt_text,image_status,source,is_primary,sort_order,uploaded_by,uploaded_at)
            VALUES(?,?,?,?,?,?,?,?,?)
            """,
            (product_id, url, alt_text or f"{product['name_es']} / {product['name_en']}", status, "admin_upload", 1 if data.get("is_primary", True) else 0, parse_int(data.get("sort_order") or 10, "sort order", min_value=0, max_value=10000), user.id, now_iso()),
        )
        con.execute("UPDATE products SET image_url=?, image_alt=?, photo_status=?, updated_at=? WHERE id=?", (url, alt_text or product["image_alt"], "real_photo_verified" if status == "approved" else "needs_real_photo", now_iso(), product_id))
        con.execute("UPDATE catalog_verifications SET status=CASE WHEN status='needs_photo' THEN 'unverified' ELSE status END, source_notes=source_notes || ' Photo uploaded.', next_review_at=? WHERE product_id=?", ((date.today()+timedelta(days=180)).isoformat(), product_id))
        audit(con, handler, user, "upload_product_photo", "product", product_id, None, {"image_url": url, "image_status": status})
        return {"ok": True, "image_id": int(cur.lastrowid), "image_url": url}


def verify_product(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    product_id = parse_int(data.get("product_id"), "product id", min_value=1, max_value=10_000_000)
    status = clean_text(data.get("status") or "owner_verified", 40)
    if status not in {"unverified", "owner_verified", "needs_price_check", "needs_photo", "retired"}:
        raise AppError("Invalid verification status.")
    with connect() as con:
        product = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not product:
            raise AppError("Product not found.", 404)
        before = con.execute("SELECT * FROM catalog_verifications WHERE product_id=?", (product_id,)).fetchone()
        con.execute(
            """
            INSERT INTO catalog_verifications(product_id,status,verified_by,source_name,source_url,source_notes,last_verified_at,next_review_at)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(product_id) DO UPDATE SET status=excluded.status, verified_by=excluded.verified_by, source_name=excluded.source_name, source_url=excluded.source_url, source_notes=excluded.source_notes, last_verified_at=excluded.last_verified_at, next_review_at=excluded.next_review_at
            """,
            (product_id, status, user.email, clean_text(data.get("source_name") or "Owner/admin verification", 160), clean_text(data.get("source_url") or "", 500), clean_text(data.get("source_notes") or "", 1000), now_iso(), clean_text(data.get("next_review_at") or (date.today()+timedelta(days=180)).isoformat(), 20)),
        )
        if status == "retired":
            con.execute("UPDATE products SET is_active=0, updated_at=? WHERE id=?", (now_iso(), product_id))
        audit(con, handler, user, "verify_product", "product", product_id, dict(before) if before else None, {"status": status})
        return {"ok": True, "product_id": product_id, "status": status}


def save_quote_offer(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    quote_id = parse_int(data.get("quote_id"), "quote id", min_value=1, max_value=10_000_000)
    amount = parse_money(data.get("amount"), "quote amount", min_value=0.01, max_value=10000)
    deposit = parse_money(data.get("deposit_required") or 0, "deposit", min_value=0, max_value=10000)
    expires_on = clean_text(data.get("expires_on") or (date.today()+timedelta(days=7)).isoformat(), 20)
    message = clean_text(data.get("message") or f"Quote approved at ${amount:.2f}. Deposit required: ${deposit:.2f}.", 1500)
    with connect() as con:
        quote = con.execute("SELECT * FROM quote_requests WHERE id=?", (quote_id,)).fetchone()
        if not quote:
            raise AppError("Quote not found.", 404)
        con.execute("UPDATE quote_requests SET status='quoted', admin_estimate=?, admin_notes=?, updated_at=? WHERE id=?", (f"{amount:.2f}", message, now_iso(), quote_id))
        con.execute("INSERT INTO quote_messages(quote_id,sender_type,message,amount,deposit_required,expires_on,created_by,created_at) VALUES(?,?,?,?,?,?,?,?)", (quote_id, "admin", message, amount, deposit, expires_on, user.id, now_iso()))
        if deposit and deposit > 0:
            provider = setting_map(con).get("payment_provider", "mock") or "mock"
            create_payment_intent_record(con, order_id=None, quote_id=quote_id, amount=deposit, kind="deposit", provider=provider, notes="Quote deposit placeholder")
        create_notification(con, "email", quote["customer_email"], f"Juquilita quote {quote['quote_code']} is ready", message, "quote", quote_id)
        audit(con, handler, user, "quote_offer", "quote", quote_id, dict(quote), {"amount": amount, "deposit": deposit})
        return {"ok": True, "quote_id": quote_id, "amount": amount, "deposit_required": deposit}


def convert_quote_to_order(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    quote_id = parse_int(data.get("quote_id"), "quote id", min_value=1, max_value=10_000_000)
    with connect() as con:
        quote = con.execute("SELECT * FROM quote_requests WHERE id=?", (quote_id,)).fetchone()
        if not quote:
            raise AppError("Quote not found.", 404)
        price = parse_money(data.get("amount") or quote["admin_estimate"] or 0, "quote amount", min_value=0.01, max_value=10000)
        deposit = parse_money(data.get("deposit_due") or 0, "deposit", min_value=0, max_value=10000)
        pickup_date = clean_text(data.get("pickup_date") or quote["pickup_date"] or date.today().isoformat(), 20)
        pickup_time = clean_text(data.get("pickup_time") or quote["pickup_time"] or "12:00", 20)
        validate_pickup(con, pickup_date, pickup_time, 0)
        product_id = quote["product_id"] or ensure_custom_quote_product(con)
        product = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        order_code = f"JB5-{utc_now().strftime('%y%m%d')}-{secrets.randbelow(9000)+1000}"
        tax_rate = float(setting_map(con).get("sales_tax_rate", "0") or 0)
        tax = round(price * tax_rate, 2)
        total = round(price + tax, 2)
        cur = con.execute(
            """
            INSERT INTO orders(order_code,user_id,customer_name,customer_email,customer_phone,business_name,customer_type,pickup_date,pickup_time,fulfillment,payment_method,notes,subtotal,discount,tax,total,deposit_due,promo_code,status,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (order_code, quote["user_id"], quote["customer_name"], quote["customer_email"], quote["customer_phone"], quote["business_name"], "quote", pickup_date, pickup_time, "pickup", "quote_invoice", f"Converted from quote {quote['quote_code']}. {quote['style_notes'] or ''}", price, 0, tax, total, deposit or 0, "", "needs_deposit" if deposit else "confirmed", now_iso(), now_iso()),
        )
        order_id = int(cur.lastrowid)
        con.execute(
            """
            INSERT INTO order_items(order_id,product_id,product_slug,product_name,unit_price,quantity,variant_summary,options_json,line_total,production_category)
            VALUES(?,?,?,?,?,?,?,?,?,?)
            """,
            (order_id, product_id, product["slug"], f"{product['name_es']} / {product['name_en']}", price, 1, "Custom approved quote", json_dumps({"quote_id": quote_id, "quote_code": quote["quote_code"], "flavor": quote["flavor"], "filling": quote["filling"], "inscription": quote["inscription"]}), price, product["category_key"]),
        )
        if deposit and deposit > 0:
            provider = setting_map(con).get("payment_provider", "mock") or "mock"
            create_payment_intent_record(con, order_id=order_id, quote_id=quote_id, amount=deposit, kind="deposit", provider=provider, notes="Converted quote deposit")
        con.execute("UPDATE quote_requests SET status='converted', updated_at=? WHERE id=?", (now_iso(), quote_id))
        create_notification(con, "email", quote["customer_email"], f"Juquilita order {order_code}", f"Your quote was converted to order {order_code}. Total ${total:.2f}.", "order", order_id)
        audit(con, handler, user, "convert_quote_to_order", "quote", quote_id, dict(quote), {"order_id": order_id, "total": total})
        return {"ok": True, "order_id": order_id, "order_code": order_code, "total": total, "deposit_due": deposit or 0}


def mark_payment(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    payment_id = parse_int(data.get("payment_id"), "payment id", min_value=1, max_value=10_000_000)
    status = clean_text(data.get("status") or "manual_received", 40)
    if status not in {"paid", "manual_received", "failed", "canceled"}:
        raise AppError("Invalid payment status.")
    with connect() as con:
        before = con.execute("SELECT * FROM payment_intents WHERE id=?", (payment_id,)).fetchone()
        if not before:
            raise AppError("Payment not found.", 404)
        con.execute("UPDATE payment_intents SET status=?, notes=?, updated_at=? WHERE id=?", (status, clean_text(data.get("notes"), 1000), now_iso(), payment_id))
        if before["order_id"] and status in {"paid", "manual_received"}:
            order = con.execute("SELECT * FROM orders WHERE id=?", (before["order_id"],)).fetchone()
            if order and order["status"] == "needs_deposit":
                con.execute("UPDATE orders SET status='confirmed', updated_at=? WHERE id=?", (now_iso(), before["order_id"]))
        audit(con, handler, user, "mark_payment", "payment_intent", payment_id, dict(before), {"status": status})
        return {"ok": True}


def update_standing_order(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler)
    require_csrf(handler, user)
    standing_id = parse_int(data.get("standing_order_id"), "standing order id", min_value=1, max_value=10_000_000)
    is_active = 1 if data.get("is_active", True) else 0
    with connect() as con:
        row = con.execute("SELECT * FROM standing_orders WHERE id=?", (standing_id,)).fetchone()
        if not row:
            raise AppError("Standing order not found.", 404)
        if user.role != "admin" and row["user_id"] != user.id:
            raise AppError("You cannot edit this standing order.", 403)
        con.execute("UPDATE standing_orders SET is_active=?, notes=?, updated_at=? WHERE id=?", (is_active, clean_text(data.get("notes") or row["notes"], 600), now_iso(), standing_id))
        audit(con, handler, user, "update_standing_order", "standing_order", standing_id, dict(row), {"is_active": is_active})
        return {"ok": True}


def save_closure(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    closure_date = clean_text(data.get("closure_date"), 20)
    try:
        date.fromisoformat(closure_date)
    except ValueError:
        raise AppError("Closure date is invalid.")
    reason = clean_text(data.get("reason") or "Special schedule", 200)
    opens_at = clean_text(data.get("opens_at"), 10)
    closes_at = clean_text(data.get("closes_at"), 10)
    is_closed = 1 if data.get("is_closed", True) else 0
    if not is_closed:
        if not re.match(r"^\d{2}:\d{2}$", opens_at) or not re.match(r"^\d{2}:\d{2}$", closes_at):
            raise AppError("Special hours must use HH:MM format.")
    with connect() as con:
        existing = con.execute("SELECT * FROM closures WHERE closure_date=?", (closure_date,)).fetchone()
        if existing:
            con.execute("UPDATE closures SET reason=?, opens_at=?, closes_at=?, is_closed=? WHERE closure_date=?", (reason, opens_at, closes_at, is_closed, closure_date))
            cid = existing["id"]
        else:
            cur = con.execute("INSERT INTO closures(closure_date,reason,opens_at,closes_at,is_closed,created_at) VALUES(?,?,?,?,?,?)", (closure_date, reason, opens_at, closes_at, is_closed, now_iso()))
            cid = int(cur.lastrowid)
        audit(con, handler, user, "save_closure", "closure", cid, dict(existing) if existing else None, data)
        return {"ok": True, "closure_id": cid}


def save_launch_item(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    code = clean_text(data.get("code"), 20)
    status = clean_text(data.get("status"), 40)
    if status not in {"todo", "in_progress", "blocked", "done"}:
        raise AppError("Invalid launch status.")
    with connect() as con:
        before = con.execute("SELECT * FROM launch_checklist WHERE code=?", (code,)).fetchone()
        if not before:
            raise AppError("Checklist item not found.", 404)
        con.execute("UPDATE launch_checklist SET status=?, notes=?, updated_at=? WHERE code=?", (status, clean_text(data.get("notes") or before["notes"], 1000), now_iso(), code))
        audit(con, handler, user, "update_launch_checklist", "launch_checklist", code, dict(before), {"status": status})
        return {"ok": True}


def save_seo_page(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    page_id = int(data.get("id") or 0)
    slug = clean_text(data.get("slug"), 160).lower()
    if not re.match(r"^[a-z0-9-]+$", slug):
        raise AppError("SEO slug must use lowercase letters, numbers, and hyphens.")
    fields = {
        "slug": slug,
        "title": clean_text(data.get("title"), 180),
        "meta_description": clean_text(data.get("meta_description"), 320),
        "target_keyword": clean_text(data.get("target_keyword"), 160),
        "status": clean_text(data.get("status") or "draft", 40),
        "content_outline": clean_text(data.get("content_outline"), 2500),
        "updated_at": now_iso(),
    }
    if fields["status"] not in {"draft", "review", "published"}:
        raise AppError("Invalid SEO status.")
    if not fields["title"] or not fields["meta_description"]:
        raise AppError("SEO title and description are required.")
    with connect() as con:
        if page_id:
            before = con.execute("SELECT * FROM seo_pages WHERE id=?", (page_id,)).fetchone()
            if not before:
                raise AppError("SEO page not found.", 404)
            con.execute("UPDATE seo_pages SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE id=?", list(fields.values()) + [page_id])
            audit(con, handler, user, "update_seo_page", "seo_page", page_id, dict(before), fields)
            return {"ok": True, "page_id": page_id}
        cur = con.execute("INSERT INTO seo_pages(slug,title,meta_description,target_keyword,status,content_outline,updated_at) VALUES(?,?,?,?,?,?,?)", tuple(fields.values()))
        audit(con, handler, user, "create_seo_page", "seo_page", int(cur.lastrowid), None, fields)
        return {"ok": True, "page_id": int(cur.lastrowid)}


def save_content_block(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    block_key = clean_text(data.get("block_key"), 120).lower()
    if not re.match(r"^[a-z0-9_:-]+$", block_key):
        raise AppError("Block key must use letters, numbers, underscores, colons, or hyphens.")
    fields = {
        "block_key": block_key,
        "title": clean_text(data.get("title"), 160),
        "body_en": clean_text(data.get("body_en"), 2000),
        "body_es": clean_text(data.get("body_es"), 2000),
        "placement": clean_text(data.get("placement") or "homepage", 80),
        "is_active": 1 if data.get("is_active", True) else 0,
        "updated_at": now_iso(),
    }
    with connect() as con:
        before = con.execute("SELECT * FROM content_blocks WHERE block_key=?", (block_key,)).fetchone()
        if before:
            con.execute("UPDATE content_blocks SET title=?, body_en=?, body_es=?, placement=?, is_active=?, updated_at=? WHERE block_key=?", (fields["title"], fields["body_en"], fields["body_es"], fields["placement"], fields["is_active"], fields["updated_at"], block_key))
        else:
            con.execute("INSERT INTO content_blocks(block_key,title,body_en,body_es,placement,is_active,updated_at) VALUES(?,?,?,?,?,?,?)", tuple(fields.values()))
        audit(con, handler, user, "save_content_block", "content_block", block_key, dict(before) if before else None, fields)
        return {"ok": True}


def create_product_variant(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    product_id = parse_int(data.get("product_id"), "product id", min_value=1, max_value=10_000_000)
    variant_type = clean_text(data.get("variant_type") or "option", 80)
    name_es = clean_text(data.get("name_es"), 160)
    name_en = clean_text(data.get("name_en"), 160)
    if not name_es or not name_en:
        raise AppError("Variant names are required.")
    with connect() as con:
        if not con.execute("SELECT 1 FROM products WHERE id=?", (product_id,)).fetchone():
            raise AppError("Product not found.", 404)
        cur = con.execute("INSERT INTO product_variants(product_id,variant_type,name_es,name_en,price_delta,wholesale_delta,is_default,sort_order) VALUES(?,?,?,?,?,?,?,?)", (product_id, variant_type, name_es, name_en, parse_money(data.get("price_delta") or 0, "price delta", min_value=0, max_value=500), parse_money(data.get("wholesale_delta") or 0, "wholesale delta", min_value=0, max_value=500), 1 if data.get("is_default") else 0, parse_int(data.get("sort_order") or 100, "sort order", min_value=0, max_value=10000)))
        audit(con, handler, user, "create_variant", "product", product_id, None, {"variant_id": int(cur.lastrowid)})
        return {"ok": True, "variant_id": int(cur.lastrowid)}


def save_uat_status(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    scenario_id = parse_int(data.get("scenario_id"), "scenario id", min_value=1, max_value=10_000_000)
    status = clean_text(data.get("status"), 40)
    if status not in {"untested", "pass", "fail", "needs_change"}:
        raise AppError("Invalid UAT status.")
    with connect() as con:
        before = con.execute("SELECT * FROM uat_scenarios WHERE id=?", (scenario_id,)).fetchone()
        if not before:
            raise AppError("UAT scenario not found.", 404)
        con.execute("UPDATE uat_scenarios SET status=?, notes=?, updated_at=? WHERE id=?", (status, clean_text(data.get("notes") or before["notes"], 1000), now_iso(), scenario_id))
        audit(con, handler, user, "update_uat", "uat_scenario", scenario_id, dict(before), {"status": status})
        return {"ok": True}


def import_pos_csv(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    csv_text = str(data.get("csv_text") or "")
    if len(csv_text) > 250_000:
        raise AppError("CSV import is too large for this local prototype.")
    reader = csv.DictReader(io.StringIO(csv_text))
    required = {"customer_name", "customer_email", "customer_phone", "pickup_date", "pickup_time", "product_slug", "quantity", "unit_price"}
    if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
        raise AppError("CSV must include customer_name, customer_email, customer_phone, pickup_date, pickup_time, product_slug, quantity, and unit_price.")
    rows = list(reader)
    with connect() as con:
        cur = con.execute("INSERT INTO pos_import_batches(source,filename,row_count,imported_by,status,notes,created_at) VALUES(?,?,?,?,?,?,?)", (clean_text(data.get("source") or "csv", 80), clean_text(data.get("filename") or "uploaded.csv", 180), len(rows), user.id, "mapped", "Rows staged and parsed into pos_sales_rows for forecast confidence. This still does not mutate customer orders automatically.", now_iso()))
        batch_id = int(cur.lastrowid)
        for row in rows:
            con.execute("""
                INSERT INTO pos_sales_rows(batch_id,customer_name,customer_email,customer_phone,pickup_date,pickup_time,product_slug,quantity,unit_price,raw_json,created_at)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """, (batch_id, clean_text(row.get("customer_name"), 160), clean_text(row.get("customer_email"), 160), clean_text(row.get("customer_phone"), 80), clean_text(row.get("pickup_date"), 20), clean_text(row.get("pickup_time"), 20), clean_text(row.get("product_slug"), 140), parse_int(row.get("quantity"), "quantity", min_value=0, max_value=100000), parse_money(row.get("unit_price"), "unit price", min_value=0, max_value=5000), json_dumps(row), now_iso()))
        audit(con, handler, user, "import_pos_csv", "pos_import_batch", batch_id, None, {"rows": len(rows)})
        return {"ok": True, "batch_id": batch_id, "row_count": len(rows), "status": "mapped"}




def record_analytics_event(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = get_session_user(handler)
    event_name = clean_text(data.get("event_name") or data.get("name"), 120)
    if not event_name:
        raise AppError("Event name is required.")
    payload = data.get("payload") if isinstance(data.get("payload"), dict) else {}
    page_path = clean_text(data.get("page_path") or handler.headers.get("Referer", ""), 300)
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
    except Exception:
        pass
    session_token = cookie.get(SESSION_COOKIE).value if cookie.get(SESSION_COOKIE) else "anonymous"
    with connect() as con:
        con.execute("INSERT INTO analytics_events(session_token,user_id,event_name,event_payload_json,page_path,created_at) VALUES(?,?,?,?,?,?)", (session_token[:120], user.id if user else None, event_name, json_dumps(payload)[:2000], page_path, now_iso()))
    return {"ok": True}


def save_customer_preferences(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler)
    require_csrf(handler, user)
    lang = clean_text(data.get("language_preference") or "en", 10).lower()
    if lang not in {"en", "es"}:
        lang = "en"
    preferred = clean_text(data.get("preferred_channel") or "sms", 20)
    if preferred not in {"sms", "email", "phone"}:
        raise AppError("Invalid preferred channel.")
    sub = clean_text(data.get("substitution_preference") or "call_me", 60)
    if sub not in {"call_me", "similar_ok", "refund_item"}:
        raise AppError("Invalid substitution preference.")
    with connect() as con:
        con.execute("INSERT OR REPLACE INTO customer_preferences(user_id,language_preference,preferred_channel,do_not_text,do_not_email,substitution_preference,saved_pickup_name,updated_at) VALUES(?,?,?,?,?,?,?,?)", (user.id, lang, preferred, 1 if data.get("do_not_text") else 0, 1 if data.get("do_not_email") else 0, sub, clean_text(data.get("saved_pickup_name"), 120), now_iso()))
        con.execute("INSERT OR REPLACE INTO notification_preferences(email,phone,preferred_channel,language_preference,do_not_text,do_not_email,source,updated_at) VALUES(?,?,?,?,?,?,?,?)", (user.email, user.phone, preferred, lang, 1 if data.get("do_not_text") else 0, 1 if data.get("do_not_email") else 0, "account", now_iso()))
        audit(con, handler, user, "save_customer_preferences", "user", user.id, None, {"language": lang, "preferred": preferred})
    return {"ok": True}


def save_customer_event(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler)
    require_csrf(handler, user)
    label = clean_text(data.get("label"), 120)
    event_type = clean_text(data.get("event_type"), 80)
    event_date = clean_text(data.get("event_date"), 20)
    if not label or not event_type or not re.match(r"^\d{4}-\d{2}-\d{2}$", event_date):
        raise AppError("Saved event label, type, and date are required.")
    reminder = parse_int(data.get("reminder_days_before") or 14, "reminder days", min_value=0, max_value=365)
    with connect() as con:
        cur = con.execute("INSERT INTO customer_saved_events(user_id,label,event_type,event_date,notes,reminder_days_before,is_active,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?)", (user.id, label, event_type, event_date, clean_text(data.get("notes"), 800), reminder, 1, now_iso(), now_iso()))
        event_id = int(cur.lastrowid)
        audit(con, handler, user, "save_customer_event", "customer_saved_event", event_id, None, {"label": label})
    return {"ok": True, "event_id": event_id}


def update_production_task(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    task_id = parse_int(data.get("task_id"), "task id", min_value=1, max_value=10_000_000)
    status = clean_text(data.get("status"), 40)
    if status not in {"todo", "doing", "blocked", "done", "canceled"}:
        raise AppError("Invalid task status.")
    notes = clean_text(data.get("notes"), 1000)
    with connect() as con:
        before = con.execute("SELECT * FROM production_tasks WHERE id=?", (task_id,)).fetchone()
        if not before:
            raise AppError("Production task not found.", 404)
        con.execute("UPDATE production_tasks SET status=?, internal_notes=COALESCE(NULLIF(?,''),internal_notes), updated_at=? WHERE id=?", (status, notes, now_iso(), task_id))
        con.execute("INSERT INTO production_task_events(task_id,actor_user_id,old_status,new_status,notes,created_at) VALUES(?,?,?,?,?,?)", (task_id, user.id, before["status"], status, notes, now_iso()))
        audit(con, handler, user, "update_production_task", "production_task", task_id, dict(before), {"status": status})
    return {"ok": True}


def create_payment_refund(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    payment_id = parse_int(data.get("payment_intent_id") or 0, "payment intent id", min_value=0, max_value=10_000_000)
    order_id = parse_int(data.get("order_id") or 0, "order id", min_value=0, max_value=10_000_000)
    amount = parse_money(data.get("amount"), "refund amount", min_value=0.01, max_value=10000)
    reason = clean_text(data.get("reason"), 300)
    if not reason:
        raise AppError("Refund reason is required.")
    with connect() as con:
        cur = con.execute("INSERT INTO payment_refunds(payment_intent_id,order_id,amount,reason,status,provider_reference,notes,created_by,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (payment_id or None, order_id or None, amount, reason, "manual_recorded", clean_text(data.get("provider_reference"), 160), clean_text(data.get("notes"), 800), user.id, now_iso(), now_iso()))
        refund_id = int(cur.lastrowid)
        audit(con, handler, user, "create_refund_record", "payment_refund", refund_id, None, {"amount": amount, "reason": reason})
    return {"ok": True, "refund_id": refund_id, "status": "manual_recorded"}


def run_tax_export(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    start_date = clean_text(data.get("start_date") or today_str(), 20)
    end_date = clean_text(data.get("end_date") or start_date, 20)
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", start_date) or not re.match(r"^\d{4}-\d{2}-\d{2}$", end_date):
        raise AppError("Start and end dates are required.")
    export_dir = DATA_DIR / "tax_exports"
    export_dir.mkdir(parents=True, exist_ok=True)
    with connect() as con:
        rows = con.execute("SELECT order_code,customer_name,pickup_date,subtotal,discount,tax,total,payment_method,status FROM orders WHERE pickup_date BETWEEN ? AND ? ORDER BY pickup_date,order_code", (start_date, end_date)).fetchall()
        gross = round(sum(float(r["subtotal"] or 0) for r in rows), 2)
        discounts = round(sum(float(r["discount"] or 0) for r in rows), 2)
        taxable = round(max(gross - discounts, 0), 2)
        tax = round(sum(float(r["tax"] or 0) for r in rows), 2)
        fname = f"tax-export-{start_date}-to-{end_date}-{secrets.token_hex(4)}.csv"
        path = export_dir / fname
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["order_code","customer_name","pickup_date","subtotal","discount","tax","total","payment_method","status"])
            for r in rows:
                writer.writerow([r["order_code"], r["customer_name"], r["pickup_date"], r["subtotal"], r["discount"], r["tax"], r["total"], r["payment_method"], r["status"]])
        cur = con.execute("INSERT INTO tax_export_runs(start_date,end_date,gross_sales,discounts,taxable_sales,tax_collected,order_count,csv_path,created_by,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)", (start_date, end_date, gross, discounts, taxable, tax, len(rows), str(path.relative_to(BASE_DIR)), user.id, now_iso()))
        export_id = int(cur.lastrowid)
        audit(con, handler, user, "run_tax_export", "tax_export", export_id, None, {"orders": len(rows), "tax": tax})
    return {"ok": True, "export_id": export_id, "order_count": len(rows), "tax_collected": tax, "csv_path": str(path.relative_to(BASE_DIR))}


def generate_standing_order_schedule(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    start_date = clean_text(data.get("start_date") or today_str(), 20)
    end_date = clean_text(data.get("end_date") or "", 20)
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", start_date):
        raise AppError("Start date is required.")
    start = date.fromisoformat(start_date)
    if end_date and re.match(r"^\d{4}-\d{2}-\d{2}$", end_date):
        end = date.fromisoformat(end_date)
        if end < start:
            raise AppError("End date must be after start date.")
        days = min((end - start).days + 1, 60)
    else:
        days = parse_int(data.get("days") or 14, "days", min_value=1, max_value=60)
    standing_order_id = parse_int(data.get("standing_order_id") or 0, "standing order id", min_value=0, max_value=10_000_000)
    created = 0
    skipped = 0
    with connect() as con:
        blackouts = {r["blackout_date"] for r in con.execute("SELECT blackout_date FROM wholesale_blackout_dates").fetchall()}
        if standing_order_id:
            orders = con.execute("SELECT * FROM standing_orders WHERE is_active=1 AND id=?", (standing_order_id,)).fetchall()
            if not orders:
                raise AppError("Active standing order not found.", 404)
        else:
            orders = con.execute("SELECT * FROM standing_orders WHERE is_active=1").fetchall()
        for offset in range(days):
            target_date = start + timedelta(days=offset)
            target = target_date.isoformat()
            weekday = target_date.weekday()
            for so in orders:
                if int(so["weekday"]) != weekday:
                    continue
                if target in blackouts:
                    skipped += 1
                    status = "skipped"
                    note = "Skipped because target date is blacked out."
                else:
                    status = "scheduled"
                    note = "Scheduled by v6 standing-order generator. Staff should review before converting to a customer order."
                if not con.execute("SELECT 1 FROM standing_order_runs WHERE standing_order_id=? AND target_date=?", (so["id"], target)).fetchone():
                    con.execute("INSERT INTO standing_order_runs(standing_order_id,target_date,status,notes,created_at,updated_at) VALUES(?,?,?,?,?,?)", (so["id"], target, status, note, now_iso(), now_iso()))
                    created += 1
        audit(con, handler, user, "generate_standing_order_schedule", "standing_order_runs", "bulk", None, {"created": created, "skipped": skipped, "days": days, "standing_order_id": standing_order_id})
    return {"ok": True, "created": created, "skipped": skipped, "days": days}



def admin_dashboard(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    with connect() as con:
        if not has_permission(con, user, "admin:dashboard"):
            raise AppError("Your staff account does not have dashboard access.", 403)
        categories, products = load_catalog(con, "admin")
        orders = rows_to_dicts(con.execute("SELECT * FROM orders ORDER BY pickup_date DESC, pickup_time DESC LIMIT 80").fetchall())
        for order in orders:
            order["items"] = rows_to_dicts(con.execute("SELECT * FROM order_items WHERE order_id=? ORDER BY id", (order["id"],)).fetchall())
        quotes = rows_to_dicts(con.execute("SELECT qr.*, p.name_es AS product_name_es, p.name_en AS product_name_en FROM quote_requests qr LEFT JOIN products p ON p.id=qr.product_id ORDER BY qr.created_at DESC LIMIT 80").fetchall())
        apps = rows_to_dicts(con.execute("SELECT * FROM wholesale_applications ORDER BY created_at DESC LIMIT 60").fetchall())
        promos = rows_to_dicts(con.execute("SELECT * FROM promotions ORDER BY starts_on DESC, id DESC").fetchall())
        partners = rows_to_dicts(con.execute("SELECT * FROM partners ORDER BY public_visible DESC, monthly_volume_estimate DESC").fetchall())
        events = rows_to_dicts(con.execute("SELECT * FROM seasonal_events ORDER BY start_date").fetchall())
        hours = rows_to_dicts(con.execute("SELECT * FROM business_hours ORDER BY weekday").fetchall())
        settings = rows_to_dicts(con.execute("SELECT * FROM settings ORDER BY key").fetchall())
        audit_rows = rows_to_dicts(con.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT 120").fetchall())
        notifications = rows_to_dicts(con.execute("SELECT * FROM notifications ORDER BY created_at DESC LIMIT 120").fetchall())
        inventory = rows_to_dicts(con.execute("SELECT id,slug,name_es,name_en,stock_count,stock_policy,order_mode,base_price,wholesale_price,category_key FROM products WHERE is_active=1 ORDER BY stock_count ASC LIMIT 160").fetchall())
        catalog_verifications = rows_to_dicts(con.execute("SELECT cv.*, p.slug, p.name_es, p.name_en, p.base_price, p.photo_status, p.image_url FROM catalog_verifications cv JOIN products p ON p.id=cv.product_id WHERE p.is_active=1 ORDER BY CASE cv.status WHEN 'needs_photo' THEN 0 WHEN 'needs_price_check' THEN 1 WHEN 'unverified' THEN 2 WHEN 'owner_verified' THEN 3 ELSE 4 END, p.name_es LIMIT 220").fetchall())
        product_images = rows_to_dicts(con.execute("SELECT pi.*, p.slug, p.name_es FROM product_images pi JOIN products p ON p.id=pi.product_id ORDER BY pi.uploaded_at DESC LIMIT 120").fetchall())
        payment_intents = rows_to_dicts(con.execute("SELECT pi.*, o.order_code, o.customer_name FROM payment_intents pi LEFT JOIN orders o ON o.id=pi.order_id ORDER BY pi.created_at DESC LIMIT 120").fetchall())
        standing_orders = rows_to_dicts(con.execute("SELECT so.*, u.email AS user_email FROM standing_orders so JOIN users u ON u.id=so.user_id ORDER BY so.weekday, so.pickup_time LIMIT 120").fetchall())
        for so in standing_orders:
            so["items"] = rows_to_dicts(con.execute("SELECT soi.*, p.slug, p.name_es, p.name_en FROM standing_order_items soi JOIN products p ON p.id=soi.product_id WHERE soi.standing_order_id=?", (so["id"],)).fetchall())
        closures = rows_to_dicts(con.execute("SELECT * FROM closures ORDER BY closure_date DESC LIMIT 80").fetchall())
        launch_items = rows_to_dicts(con.execute("SELECT * FROM launch_checklist ORDER BY priority, code").fetchall())
        seo_pages = rows_to_dicts(con.execute("SELECT * FROM seo_pages ORDER BY status, slug").fetchall())
        content_blocks = rows_to_dicts(con.execute("SELECT * FROM content_blocks ORDER BY placement, block_key").fetchall())
        uat_scenarios = rows_to_dicts(con.execute("SELECT * FROM uat_scenarios ORDER BY role_name, id").fetchall())
        suppliers = rows_to_dicts(con.execute("SELECT * FROM suppliers ORDER BY name").fetchall())
        ingredients = rows_to_dicts(con.execute("SELECT * FROM ingredients ORDER BY name_en").fetchall())
        pos_imports = rows_to_dicts(con.execute("SELECT * FROM pos_import_batches ORDER BY created_at DESC LIMIT 60").fetchall())
        pos_sales = rows_to_dicts(con.execute("SELECT * FROM pos_sales_rows ORDER BY created_at DESC LIMIT 120").fetchall())
        customers = customer_admin_summary(con)
        invoices = rows_to_dicts(con.execute("SELECT inv.*, o.order_code FROM invoices inv LEFT JOIN orders o ON o.id=inv.order_id ORDER BY inv.created_at DESC LIMIT 120").fetchall())
        margin_report = product_margin_report(con)
        local_events = rows_to_dicts(con.execute("SELECT * FROM local_events ORDER BY event_date DESC LIMIT 120").fetchall())
        weather_adjustments = rows_to_dicts(con.execute("SELECT * FROM weather_adjustments ORDER BY updated_at DESC LIMIT 120").fetchall())
        delivery_zones = rows_to_dicts(con.execute("SELECT * FROM delivery_zones ORDER BY status DESC, min_order").fetchall())
        notification_templates = rows_to_dicts(con.execute("SELECT * FROM notification_templates ORDER BY channel, template_key").fetchall())
        supplier_quotes = rows_to_dicts(con.execute("SELECT spq.*, s.name AS supplier_name, i.name_en AS ingredient_name FROM supplier_price_quotes spq LEFT JOIN suppliers s ON s.id=spq.supplier_id LEFT JOIN ingredients i ON i.id=spq.ingredient_id ORDER BY spq.effective_on DESC, spq.id DESC LIMIT 120").fetchall())
        recipe_verifications = rows_to_dicts(con.execute("SELECT rv.*, p.slug, p.name_es, p.name_en FROM recipe_verifications rv JOIN products p ON p.id=rv.product_id ORDER BY rv.owner_verified ASC, p.name_es LIMIT 180").fetchall())
        photo_shot_list = rows_to_dicts(con.execute("SELECT psl.*, p.slug, p.name_es, p.name_en FROM photo_shot_list psl LEFT JOIN products p ON p.id=psl.product_id ORDER BY CASE psl.priority WHEN 'P0' THEN 0 WHEN 'P1' THEN 1 WHEN 'P2' THEN 2 ELSE 3 END, psl.status, p.name_es LIMIT 220").fetchall())
        qa_runs = rows_to_dicts(con.execute("SELECT * FROM qa_audit_runs ORDER BY created_at DESC LIMIT 80").fetchall())
        qa_items = rows_to_dicts(con.execute("SELECT qai.*, qar.tool_name, qar.target_url FROM qa_audit_items qai LEFT JOIN qa_audit_runs qar ON qar.id=qai.run_id ORDER BY qai.updated_at DESC LIMIT 180").fetchall())
        backups = rows_to_dicts(con.execute("SELECT * FROM backup_runs ORDER BY started_at DESC LIMIT 50").fetchall())
        monitoring_events = rows_to_dicts(con.execute("SELECT * FROM monitoring_events ORDER BY created_at DESC LIMIT 80").fetchall())
        integration_events = rows_to_dicts(con.execute("SELECT * FROM integration_events ORDER BY created_at DESC LIMIT 120").fetchall())
        permission_catalog = rows_to_dicts(con.execute("SELECT * FROM permission_catalog ORDER BY category, permission_key").fetchall())
        staff_roles = rows_to_dicts(con.execute("SELECT * FROM staff_roles ORDER BY role_key").fetchall())
        staff_users = rows_to_dicts(con.execute("SELECT id,email,name,role,phone,business_name,wholesale_tier,is_active,created_at,updated_at FROM users WHERE role IN ('owner','admin','manager','cashier','baker','decorator','wholesale_manager') ORDER BY role,name").fetchall())
        for staff in staff_users:
            staff["permissions"] = [r["permission_key"] for r in con.execute("SELECT permission_key FROM staff_permissions WHERE user_id=? ORDER BY permission_key", (staff["id"],)).fetchall()]
            staff["roles"] = [r["role_key"] for r in con.execute("SELECT role_key FROM user_staff_roles WHERE user_id=? ORDER BY role_key", (staff["id"],)).fetchall()]
        production_tasks = rows_to_dicts(con.execute("SELECT pt.*, o.order_code, o.customer_name, qr.quote_code FROM production_tasks pt LEFT JOIN orders o ON o.id=pt.order_id LEFT JOIN quote_requests qr ON qr.id=pt.quote_id ORDER BY CASE pt.status WHEN 'blocked' THEN 0 WHEN 'todo' THEN 1 WHEN 'doing' THEN 2 ELSE 3 END, pt.due_at LIMIT 180").fetchall())
        seasonal_campaigns = rows_to_dicts(con.execute("SELECT * FROM seasonal_campaigns ORDER BY season_start LIMIT 80").fetchall())
        seasonal_windows = rows_to_dicts(con.execute("SELECT spw.*, sc.slug, sc.title_en FROM seasonal_pickup_windows spw JOIN seasonal_campaigns sc ON sc.id=spw.campaign_id ORDER BY pickup_date, starts_at LIMIT 120").fetchall())
        product_batches = rows_to_dicts(con.execute("SELECT pb.*, p.slug, p.name_es, p.name_en FROM product_batches pb JOIN products p ON p.id=pb.product_id ORDER BY pb.batch_date DESC, pb.expected_ready_at LIMIT 160").fetchall())
        analytics_summary = rows_to_dicts(con.execute("SELECT event_name, COUNT(*) AS count FROM analytics_events WHERE created_at >= ? GROUP BY event_name ORDER BY count DESC LIMIT 30", ((utc_now()-timedelta(days=30)).replace(microsecond=0).isoformat()+"Z",)).fetchall())
        payment_refunds = rows_to_dicts(con.execute("SELECT pr.*, o.order_code FROM payment_refunds pr LEFT JOIN orders o ON o.id=pr.order_id ORDER BY pr.created_at DESC LIMIT 100").fetchall())
        tax_exports = rows_to_dicts(con.execute("SELECT * FROM tax_export_runs ORDER BY created_at DESC LIMIT 80").fetchall())
        standing_runs = rows_to_dicts(con.execute("SELECT sor.*, so.name, so.business_name, u.email AS user_email FROM standing_order_runs sor JOIN standing_orders so ON so.id=sor.standing_order_id JOIN users u ON u.id=so.user_id ORDER BY sor.target_date DESC LIMIT 120").fetchall())
        notification_preferences = rows_to_dicts(con.execute("SELECT * FROM notification_preferences ORDER BY updated_at DESC LIMIT 120").fetchall())
        customer_events = rows_to_dicts(con.execute("SELECT cse.*, u.email FROM customer_saved_events cse LEFT JOIN users u ON u.id=cse.user_id ORDER BY event_date LIMIT 120").fetchall())
        provider_summary = {"payment": provider_ready((setting_map(con)).get("payment_provider", "mock")), "email_ready": bool(os.environ.get("SENDGRID_API_KEY") and os.environ.get("SENDGRID_FROM_EMAIL")), "sms_ready": bool(os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN") and os.environ.get("TWILIO_FROM_PHONE"))}
        return {
            "user": user.public(),
            "metrics": summarize_orders(con),
            "categories": categories,
            "products": products,
            "orders": orders,
            "quotes": quotes,
            "wholesale_applications": apps,
            "promotions": promos,
            "partners": partners,
            "events": events,
            "hours": hours,
            "settings": settings,
            "production_summary": production_summary(con),
            "forecast": build_forecast(con),
            "audit": audit_rows,
            "notifications": notifications,
            "inventory": inventory,
            "catalog_health": catalog_health(con),
            "catalog_verifications": catalog_verifications,
            "product_images": product_images,
            "payment_intents": payment_intents,
            "standing_orders": standing_orders,
            "closures": closures,
            "launch_checklist": launch_items,
            "seo_pages": seo_pages,
            "content_blocks": content_blocks,
            "uat_scenarios": uat_scenarios,
            "suppliers": suppliers,
            "ingredients": ingredients,
            "pos_imports": pos_imports,
            "pos_sales": pos_sales,
            "customers": customers,
            "invoices": invoices,
            "margin_report": margin_report,
            "local_events": local_events,
            "weather_adjustments": weather_adjustments,
            "delivery_zones": delivery_zones,
            "notification_templates": notification_templates,
            "supplier_quotes": supplier_quotes,
            "recipe_verifications": recipe_verifications,
            "photo_shot_list": photo_shot_list,
            "qa_runs": qa_runs,
            "qa_items": qa_items,
            "backups": backups,
            "monitoring_events": monitoring_events,
            "integration_events": integration_events,
            "permission_catalog": permission_catalog,
            "staff_roles": staff_roles,
            "staff_users": staff_users,
            "provider_summary": provider_summary,
            "production_tasks": production_tasks,
            "seasonal_campaigns": seasonal_campaigns,
            "seasonal_windows": seasonal_windows,
            "product_batches": product_batches,
            "analytics_summary": analytics_summary,
            "payment_refunds": payment_refunds,
            "tax_exports": tax_exports,
            "standing_runs": standing_runs,
            "notification_preferences": notification_preferences,
            "customer_events": customer_events,
        }


def update_order_status(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    order_id = parse_int(data.get("order_id"), "order id", min_value=1, max_value=10_000_000)
    status = clean_text(data.get("status"), 40)
    if status not in ORDER_STATUSES:
        raise AppError("Invalid order status.")
    reason = clean_text(data.get("reason"), 500)
    with connect() as con:
        before = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
        if not before:
            raise AppError("Order not found.", 404)
        con.execute("UPDATE orders SET status=?, status_reason=?, updated_at=? WHERE id=?", (status, reason, now_iso(), order_id))
        audit(con, handler, user, "update_order_status", "order", order_id, dict(before), {"status": status, "reason": reason})
        create_notification(con, "admin", "order_log", f"Order {before['order_code']} changed", f"Status changed to {status} by {user.email}.", "order", order_id)
        if status == "ready":
            create_notification(con, "sms", before["customer_phone"], f"Order {before['order_code']} ready", f"Juquilita Bakery: your order {before['order_code']} is ready for pickup.", "order", order_id)
        if status == "completed":
            create_notification(con, "email", before["customer_email"], f"How was your Juquilita order {before['order_code']}?", "Leave a quick review so the bakery can improve products and pickup timing.", "review_request", order_id)
        return {"ok": True}


def update_product(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    product_id = parse_int(data.get("id"), "product id", min_value=1, max_value=10_000_000)
    fields = {}
    allowed = {
        "name_es": (str, 160), "name_en": (str, 160), "description_es": (str, 1200), "description_en": (str, 1200),
        "subcategory": (str, 120), "search_terms": (str, 800), "image_url": (str, 500), "image_alt": (str, 300),
        "allergen_notes": (str, 800), "ingredient_notes": (str, 800), "photo_status": (str, 60), "order_mode": (str, 40), "stock_policy": (str, 40),
    }
    for key, (_, max_len) in allowed.items():
        if key in data:
            value = clean_text(data.get(key), max_len)
            if key == "order_mode" and value not in {"order", "quote", "inactive"}:
                raise AppError("order_mode must be order, quote, or inactive.")
            if key == "stock_policy" and value not in {"track", "made_to_order", "quote", "do_not_track"}:
                raise AppError("Invalid stock policy.")
            fields[key] = value
    if "base_price" in data:
        fields["base_price"] = parse_money(data.get("base_price"), "base price", allow_none=True, min_value=0, max_value=5000)
    if "wholesale_price" in data:
        fields["wholesale_price"] = parse_money(data.get("wholesale_price"), "wholesale price", allow_none=True, min_value=0, max_value=5000)
    if "stock_count" in data:
        fields["stock_count"] = parse_int(data.get("stock_count"), "stock count", min_value=0, max_value=1_000_000)
    if "lead_time_hours" in data:
        fields["lead_time_hours"] = parse_int(data.get("lead_time_hours"), "lead time", min_value=0, max_value=720)
    if "margin_estimate" in data:
        fields["margin_estimate"] = float(parse_money(data.get("margin_estimate"), "margin estimate", min_value=0, max_value=1))
    if not fields:
        raise AppError("No product fields supplied.")
    fields["updated_at"] = now_iso()
    with connect() as con:
        before = con.execute("SELECT * FROM products WHERE id=?", (product_id,)).fetchone()
        if not before:
            raise AppError("Product not found.", 404)
        if fields.get("wholesale_price") is not None and fields.get("base_price", before["base_price"]) is not None and fields["wholesale_price"] > fields.get("base_price", before["base_price"]):
            raise AppError("Wholesale price should not exceed retail price.")
        assignments = ", ".join(f"{key}=?" for key in fields)
        con.execute(f"UPDATE products SET {assignments} WHERE id=?", list(fields.values()) + [product_id])
        audit(con, handler, user, "update_product", "product", product_id, dict(before), fields)
        return {"ok": True}


def create_product(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    slug = clean_text(data.get("slug"), 140).lower()
    if not re.match(r"^[a-z0-9-]+$", slug):
        raise AppError("Product slug must use lowercase letters, numbers, and hyphens.")
    name_es = clean_text(data.get("name_es"), 160)
    name_en = clean_text(data.get("name_en"), 160)
    category_key = clean_text(data.get("category_key"), 80)
    if not name_es or not name_en or not category_key:
        raise AppError("Spanish name, English name, and category are required.")
    base_price = parse_money(data.get("base_price"), "base price", allow_none=True, min_value=0, max_value=5000)
    wholesale_price = parse_money(data.get("wholesale_price"), "wholesale price", allow_none=True, min_value=0, max_value=5000)
    if wholesale_price is not None and base_price is not None and wholesale_price > base_price:
        raise AppError("Wholesale price should not exceed retail price.")
    with connect() as con:
        if not con.execute("SELECT 1 FROM categories WHERE key=?", (category_key,)).fetchone():
            raise AppError("Category does not exist.")
        cur = con.execute(
            """
            INSERT INTO products(slug,name_es,name_en,category_key,subcategory,description_es,description_en,base_price,wholesale_price,unit,stock_count,stock_policy,lead_time_hours,order_mode,is_featured,is_bulk_friendly,is_seasonal,search_terms,image_alt,image_accent,icon,photo_status,price_basis,allergen_notes,ingredient_notes,margin_estimate,is_active,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,?,?)
            """,
            (slug, name_es, name_en, category_key, clean_text(data.get("subcategory"), 120), clean_text(data.get("description_es"), 1200), clean_text(data.get("description_en"), 1200), base_price, wholesale_price, clean_text(data.get("unit") or "each", 40), parse_int(data.get("stock_count") or 0, "stock count", min_value=0, max_value=1_000_000), clean_text(data.get("stock_policy") or "track", 40), parse_int(data.get("lead_time_hours") or 0, "lead time", min_value=0, max_value=720), clean_text(data.get("order_mode") or ("quote" if base_price is None else "order"), 40), 1 if data.get("is_featured") else 0, 1 if data.get("is_bulk_friendly") else 0, 1 if data.get("is_seasonal") else 0, clean_text(data.get("search_terms"), 800), f"{name_es} / {name_en}", clean_text(data.get("image_accent") or "marigold", 60), clean_text(data.get("icon") or "🥐", 12), clean_text(data.get("photo_status") or "needs_real_photo", 60), clean_text(data.get("price_basis") or "Admin-created product", 500), clean_text(data.get("allergen_notes"), 800), clean_text(data.get("ingredient_notes"), 800), float(data.get("margin_estimate") or 0.58), now_iso(), now_iso()),
        )
        product_id = int(cur.lastrowid)
        con.execute("INSERT OR IGNORE INTO catalog_verifications(product_id,status,verified_by,source_name,source_url,source_notes,last_verified_at,next_review_at) VALUES(?,?,?,?,?,?,?,?)", (product_id, "unverified", user.email, "Admin-created product", "", "Needs owner verification before public launch.", "", (date.today()+timedelta(days=30)).isoformat()))
        audit(con, handler, user, "create_product", "product", product_id, None, {"slug": slug})
        return {"ok": True, "product_id": product_id}


def create_promotion(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    title = clean_text(data.get("title"), 160)
    code = clean_text(data.get("code"), 40).upper()
    discount_type = clean_text(data.get("discount_type") or "percent", 20)
    if not title or not re.match(r"^[A-Z0-9_-]{3,40}$", code):
        raise AppError("Promotion title and a clean code are required.")
    if discount_type not in {"percent", "fixed"}:
        raise AppError("Discount type must be percent or fixed.")
    discount_value = parse_money(data.get("discount_value"), "discount value", min_value=0.01, max_value=50 if discount_type == "percent" else 500)
    min_subtotal = parse_money(data.get("min_subtotal") or 0, "minimum subtotal", min_value=0, max_value=10000)
    starts = clean_text(data.get("starts_on"), 20)
    ends = clean_text(data.get("ends_on"), 20)
    try:
        start_d = date.fromisoformat(starts)
        end_d = date.fromisoformat(ends)
    except ValueError:
        raise AppError("Promotion dates must be valid.")
    if end_d < start_d:
        raise AppError("Promotion end date must be after the start date.")
    role = clean_text(data.get("applies_to_role") or "all", 40)
    if role not in {"all", "guest", "premium", "pending_premium"}:
        raise AppError("Invalid promotion role target.")
    with connect() as con:
        category_key = clean_text(data.get("category_key") or "all", 80)
        if category_key != "all" and not con.execute("SELECT 1 FROM categories WHERE key=?", (category_key,)).fetchone():
            raise AppError("Promotion category does not exist.")
        cur = con.execute(
            """
            INSERT INTO promotions(title,code,discount_type,discount_value,min_subtotal,applies_to_role,category_key,starts_on,ends_on,is_active,max_redemptions,per_customer_limit,auto_apply,notes,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (title, code, discount_type, discount_value, min_subtotal, role, category_key, starts, ends, 1 if data.get("is_active", True) else 0, parse_int(data.get("max_redemptions") or 0, "max redemptions", min_value=0, max_value=1_000_000), parse_int(data.get("per_customer_limit") or 0, "per customer limit", min_value=0, max_value=1000), 1 if data.get("auto_apply") else 0, clean_text(data.get("notes"), 1000), now_iso(), now_iso()),
        )
        promo_id = int(cur.lastrowid)
        audit(con, handler, user, "create_promotion", "promotion", promo_id, None, {"code": code, "discount_value": discount_value})
        return {"ok": True, "promotion_id": promo_id}


def save_partner(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    partner_id = int(data.get("id") or 0)
    fields = {
        "name": clean_text(data.get("name"), 160),
        "category": clean_text(data.get("category"), 120),
        "city": clean_text(data.get("city"), 120),
        "website": clean_text(data.get("website"), 500),
        "contact_name": clean_text(data.get("contact_name"), 120),
        "contact_email": clean_text(data.get("contact_email"), 160),
        "phone": clean_text(data.get("phone"), 80),
        "story": clean_text(data.get("story"), 1000),
        "highlight": clean_text(data.get("highlight"), 200),
        "public_visible": 1 if data.get("public_visible") else 0,
        "has_consent": 1 if data.get("has_consent") else 0,
        "logo_url": clean_text(data.get("logo_url"), 500),
        "monthly_volume_estimate": parse_int(data.get("monthly_volume_estimate") or 0, "monthly volume", min_value=0, max_value=1_000_000),
        "is_demo": 1 if data.get("is_demo") else 0,
        "updated_at": now_iso(),
    }
    if not fields["name"] or not fields["story"] or not fields["highlight"]:
        raise AppError("Partner name, story, and highlight are required.")
    if fields["public_visible"] and not fields["has_consent"]:
        raise AppError("Public partner cards require consent before publishing.")
    with connect() as con:
        if partner_id:
            before = con.execute("SELECT * FROM partners WHERE id=?", (partner_id,)).fetchone()
            if not before:
                raise AppError("Partner not found.", 404)
            assignments = ", ".join(f"{k}=?" for k in fields)
            con.execute(f"UPDATE partners SET {assignments} WHERE id=?", list(fields.values()) + [partner_id])
            audit(con, handler, user, "update_partner", "partner", partner_id, dict(before), fields)
            return {"ok": True, "partner_id": partner_id}
        cur = con.execute(
            """
            INSERT INTO partners(name,category,city,website,contact_name,contact_email,phone,story,highlight,public_visible,has_consent,logo_url,monthly_volume_estimate,is_demo,created_at,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (fields["name"], fields["category"], fields["city"], fields["website"], fields["contact_name"], fields["contact_email"], fields["phone"], fields["story"], fields["highlight"], fields["public_visible"], fields["has_consent"], fields["logo_url"], fields["monthly_volume_estimate"], fields["is_demo"], now_iso(), now_iso()),
        )
        new_id = int(cur.lastrowid)
        audit(con, handler, user, "create_partner", "partner", new_id, None, fields)
        return {"ok": True, "partner_id": new_id}


def update_quote_status(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    quote_id = parse_int(data.get("quote_id"), "quote id", min_value=1, max_value=10_000_000)
    status = clean_text(data.get("status"), 40)
    if status not in QUOTE_STATUSES:
        raise AppError("Invalid quote status.")
    with connect() as con:
        before = con.execute("SELECT * FROM quote_requests WHERE id=?", (quote_id,)).fetchone()
        if not before:
            raise AppError("Quote not found.", 404)
        con.execute("UPDATE quote_requests SET status=?, admin_estimate=?, admin_notes=?, updated_at=? WHERE id=?", (status, clean_text(data.get("admin_estimate"), 200), clean_text(data.get("admin_notes"), 1000), now_iso(), quote_id))
        audit(con, handler, user, "update_quote", "quote", quote_id, dict(before), {"status": status})
        return {"ok": True}


def decide_wholesale(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    app_id = parse_int(data.get("application_id"), "application id", min_value=1, max_value=10_000_000)
    status = clean_text(data.get("status"), 40)
    if status not in APP_STATUSES:
        raise AppError("Invalid application status.")
    with connect() as con:
        app = con.execute("SELECT * FROM wholesale_applications WHERE id=?", (app_id,)).fetchone()
        if not app:
            raise AppError("Application not found.", 404)
        con.execute("UPDATE wholesale_applications SET status=?, updated_at=? WHERE id=?", (status, now_iso(), app_id))
        if status == "approved" and app["user_id"]:
            con.execute("UPDATE users SET role='premium', business_name=?, phone=?, wholesale_tier='approved wholesale', updated_at=? WHERE id=?", (app["business_name"], app["phone"], now_iso(), app["user_id"]))
        audit(con, handler, user, "decide_wholesale", "wholesale_application", app_id, dict(app), {"status": status})
        return {"ok": True}


def save_event(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    event_id = int(data.get("id") or 0)
    required = ["title", "event_date", "start_date", "end_date"]
    if any(not clean_text(data.get(key), 160) for key in required):
        raise AppError("Event title and dates are required.")
    fields = {
        "title": clean_text(data.get("title"), 160),
        "event_date": clean_text(data.get("event_date"), 20),
        "start_date": clean_text(data.get("start_date"), 20),
        "end_date": clean_text(data.get("end_date"), 20),
        "focus_categories": clean_text(data.get("focus_categories"), 400),
        "focus_products": clean_text(data.get("focus_products"), 600),
        "demand_multiplier": float(parse_money(data.get("demand_multiplier") or 1, "demand multiplier", min_value=0, max_value=10)),
        "prep_notes": clean_text(data.get("prep_notes"), 1200),
        "marketing_notes": clean_text(data.get("marketing_notes"), 1200),
        "labor_notes": clean_text(data.get("labor_notes"), 1200),
        "is_active": 1 if data.get("is_active", True) else 0,
        "updated_at": now_iso(),
    }
    with connect() as con:
        if event_id:
            before = con.execute("SELECT * FROM seasonal_events WHERE id=?", (event_id,)).fetchone()
            if not before:
                raise AppError("Event not found.", 404)
            con.execute("UPDATE seasonal_events SET " + ", ".join(f"{k}=?" for k in fields) + " WHERE id=?", list(fields.values()) + [event_id])
            audit(con, handler, user, "update_event", "seasonal_event", event_id, dict(before), fields)
            return {"ok": True, "event_id": event_id}
        cur = con.execute(
            """
            INSERT INTO seasonal_events(title,event_date,start_date,end_date,focus_categories,focus_products,demand_multiplier,prep_notes,marketing_notes,labor_notes,is_active,updated_at)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            tuple(fields.values()),
        )
        new_id = int(cur.lastrowid)
        audit(con, handler, user, "create_event", "seasonal_event", new_id, None, fields)
        return {"ok": True, "event_id": new_id}


def save_hours(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    rows = data.get("hours")
    if not isinstance(rows, list):
        raise AppError("Hours rows are required.")
    with connect() as con:
        for raw in rows:
            weekday = parse_int(raw.get("weekday"), "weekday", min_value=0, max_value=6)
            opens_at = clean_text(raw.get("opens_at"), 10)
            closes_at = clean_text(raw.get("closes_at"), 10)
            if not re.match(r"^\d{2}:\d{2}$", opens_at) or not re.match(r"^\d{2}:\d{2}$", closes_at):
                raise AppError("Hours must use HH:MM format.")
            capacity = parse_int(raw.get("slot_capacity") or 6, "slot capacity", min_value=1, max_value=1000)
            con.execute("UPDATE business_hours SET opens_at=?, closes_at=?, slot_capacity=?, is_closed=?, updated_at=? WHERE weekday=?", (opens_at, closes_at, capacity, 1 if raw.get("is_closed") else 0, now_iso(), weekday))
        audit(con, handler, user, "update_hours", "business_hours", "all", None, rows)
        return {"ok": True}


def save_settings(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> dict[str, Any]:
    user = require_user(handler, role="admin")
    require_csrf(handler, user)
    settings = data.get("settings")
    if not isinstance(settings, dict):
        raise AppError("Settings object is required.")
    allowed = {"sales_tax_rate", "default_slot_capacity", "cake_deposit_rate", "large_order_deposit_threshold", "phone", "text_phone", "email", "address", "payment_provider", "deposit_payment_mode", "receipt_footer", "admin_order_alert_email", "admin_order_alert_phone", "photos_required_before_launch", "owner_catalog_verified", "pos_import_provider", "review_request_enabled", "delivery_enabled", "stripe_webhook_required", "square_environment", "sendgrid_enabled", "twilio_sms_enabled", "password_reset_token_minutes", "admin_2fa_required", "staff_permissions_enabled", "backup_retention_days", "monitoring_contact_email", "accessibility_target", "mobile_qa_breakpoints"}
    with connect() as con:
        for key, value in settings.items():
            if key not in allowed:
                continue
            val = clean_text(value, 500)
            if key in {"sales_tax_rate", "cake_deposit_rate"}:
                num = float(parse_money(val, key, min_value=0, max_value=1))
                val = f"{num:.4f}"
            if key == "large_order_deposit_threshold":
                num = parse_money(val, key, min_value=0, max_value=5000)
                val = f"{num:.2f}"
            if key == "default_slot_capacity":
                val = str(parse_int(val, key, min_value=1, max_value=1000))
            con.execute("UPDATE settings SET value=?, updated_at=? WHERE key=?", (val, now_iso(), key))
        audit(con, handler, user, "update_settings", "settings", "selected", None, settings)
        return {"ok": True}


def handle_login(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> tuple[dict[str, Any], str]:
    email = clean_text(data.get("email"), 160).lower()
    password = str(data.get("password") or "")
    ip = client_ip(handler)
    if not valid_email(email):
        raise AppError("Use a valid email and password.", 401)
    with connect() as con:
        cutoff = (utc_now() - timedelta(minutes=15)).replace(microsecond=0).isoformat() + "Z"
        failures = con.execute("SELECT COUNT(*) AS n FROM login_attempts WHERE lower(email)=lower(?) AND ip_address=? AND was_successful=0 AND attempted_at>=?", (email, ip, cutoff)).fetchone()["n"]
        if int(failures) >= 8:
            raise AppError("Too many login attempts. Try again later.", 429)
        row = con.execute("SELECT * FROM users WHERE lower(email)=lower(?) AND is_active=1", (email,)).fetchone()
        if not row or not verify_password(password, row["password_hash"], row["salt"]):
            con.execute("INSERT INTO login_attempts(email,ip_address,was_successful,attempted_at) VALUES(?,?,0,?)", (email, ip, now_iso()))
            raise AppError("Use a valid email and password.", 401)
        con.execute("INSERT INTO login_attempts(email,ip_address,was_successful,attempted_at) VALUES(?,?,1,?)", (email, ip, now_iso()))
        if two_factor_required_for_user(con, row):
            tf = con.execute("SELECT is_enabled FROM two_factor_auth WHERE user_id=?", (row["id"],)).fetchone()
            if not tf or not int(tf["is_enabled"]):
                audit(con, handler, None, "login_blocked_2fa_required", "user", row["id"], None, {"email": email})
                raise AppError("Two-factor authentication must be enabled before this staff account can sign in.", 403)
            challenge = secrets.token_urlsafe(32)
            expires = (utc_now() + timedelta(minutes=8)).replace(microsecond=0).isoformat() + "Z"
            con.execute("INSERT INTO two_factor_challenges(token,user_id,created_at,expires_at,ip_address,user_agent) VALUES(?,?,?,?,?,?)", (challenge, row["id"], now_iso(), expires, ip, handler.headers.get("User-Agent", "")[:300]))
            audit(con, handler, None, "login_requires_2fa", "user", row["id"], None, {"email": email})
            return {"ok": True, "requires_2fa": True, "challenge_token": challenge, "email": email}, cookie_header(clear=True)
        token, csrf, _ = create_session(con, int(row["id"]), handler)
        user = {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"], "business_name": row["business_name"], "phone": row["phone"], "wholesale_tier": row["wholesale_tier"], "csrf_token": csrf}
        audit(con, handler, None, "login", "user", row["id"], None, {"email": email})
        return {"ok": True, "user": user}, cookie_header(token)


def handle_register(handler: BaseHTTPRequestHandler, data: dict[str, Any]) -> tuple[dict[str, Any], str]:
    name = clean_text(data.get("name"), 120)
    email = clean_text(data.get("email"), 160).lower()
    phone = clean_text(data.get("phone"), 80)
    password = str(data.get("password") or "")
    if len(name) < 2 or not valid_email(email) or not valid_phone(phone):
        raise AppError("Name, valid email, and valid phone are required.")
    if len(password) < 10:
        raise AppError("Password must be at least 10 characters.")
    with connect() as con:
        try:
            user_id = seed_user(con, email, password, name, "guest", "", phone, "retail")
        except sqlite3.IntegrityError:
            raise AppError("An account already exists for that email.")
        token, csrf, _ = create_session(con, user_id, handler)
        audit(con, handler, None, "register", "user", user_id, None, {"email": email})
        return {"ok": True, "user": {"id": user_id, "email": email, "name": name, "role": "guest", "business_name": "", "phone": phone, "wholesale_tier": "retail", "csrf_token": csrf}}, cookie_header(token)


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    try:
        length = int(handler.headers.get("Content-Length", "0") or 0)
    except ValueError:
        raise AppError("Invalid Content-Length header.", 400)
    if length > MAX_BODY_BYTES:
        raise AppError("Request body is too large.", 413)
    if length <= 0:
        handler.raw_body = b""
        return {}
    raw = handler.rfile.read(length)
    handler.raw_body = raw
    try:
        data = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError:
        raise AppError("Request body must be valid JSON.")
    if not isinstance(data, dict):
        raise AppError("Request body must be a JSON object.")
    return data


class BakeryHandler(BaseHTTPRequestHandler):
    server_version = "JuquilitaBakeryV6/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        if os.environ.get("JB_QUIET") == "1":
            return
        super().log_message(fmt, *args)

    def send_json(self, data: Any, status: int = 200, extra_headers: dict[str, str] | None = None) -> None:
        payload = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        for key, value in security_headers().items():
            self.send_header(key, value)
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def send_html(self, html: str, status: int = 200) -> None:
        payload = html.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        for key, value in security_headers(html=True).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(payload)

    def send_headers_only(self, *, status: int = 200, content_type: str = "text/plain; charset=utf-8", content_length: int = 0, html: bool = False, cache_control: str = "no-store") -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Cache-Control", cache_control)
        for key, value in security_headers(html=html).items():
            self.send_header(key, value)
        self.end_headers()

    def send_app_error(self, error: Exception) -> None:
        if isinstance(error, AppError):
            self.send_json({"ok": False, "error": error.message, "details": error.details}, error.status)
            return
        self.send_json({"ok": False, "error": "Unexpected server error."}, 500)
        raise error

    def do_GET(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path == "/api/health":
                self.send_json({"ok": True, "time": now_iso(), "version": APP_VERSION})
            elif path == "/api/health/deep":
                self.send_json(deep_health())
            elif path == "/api/bootstrap":
                self.send_json(build_bootstrap(self))
            elif path == "/api/admin/dashboard":
                self.send_json(admin_dashboard(self))
            elif path == "/api/order/track":
                self.send_json(track_order(self, parse_qs(parsed.query)))
            elif path == "/receipt":
                qs = parse_qs(parsed.query)
                token = (qs.get("token") or [""])[0]
                code = (qs.get("code") or [""])[0]
                with connect() as con:
                    if token:
                        self.send_html(render_receipt_html(con, token, lookup="token"))
                    elif code:
                        require_user(self, role="admin")
                        self.send_html(render_receipt_html(con, code, lookup="code"))
                    else:
                        raise AppError("Receipt token is required.", 400)
            elif path == "/ticket":
                require_user(self, role="admin")
                with connect() as con:
                    self.send_html(render_ticket_html(con, parse_int((parse_qs(parsed.query).get("order_id") or [0])[0], "order id", min_value=1, max_value=10_000_000)))
            elif path == "/labels":
                require_user(self, role="admin")
                label_date = clean_text((parse_qs(parsed.query).get("date") or [today_str()])[0], 20)
                with connect() as con:
                    self.send_html(render_labels_html(con, label_date))
            elif path.startswith("/page/"):
                slug = path.split("/page/", 1)[1].strip("/")
                with connect() as con:
                    self.send_html(render_seo_page(con, slug))
            elif path == "/api/account/orders":
                user = require_user(self)
                with connect() as con:
                    orders = rows_to_dicts(con.execute("SELECT * FROM orders WHERE user_id=? ORDER BY created_at DESC LIMIT 50", (user.id,)).fetchall())
                    for order in orders:
                        order["items"] = rows_to_dicts(con.execute("SELECT * FROM order_items WHERE order_id=?", (order["id"],)).fetchall())
                    self.send_json({"orders": orders, "standing_orders": load_standing_orders(con, user.id)})
            else:
                self.serve_static(path)
        except Exception as exc:
            self.send_app_error(exc)

    def do_HEAD(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            if path in {"/api/health", "/api/health/deep", "/api/bootstrap"}:
                self.send_headers_only(content_type="application/json; charset=utf-8")
                return
            if path == "/":
                path = "/index.html"
            rel = path.lstrip("/")
            if rel.startswith("api/"):
                raise AppError("Route not found.", 404)
            file_path = (PUBLIC_DIR / rel).resolve()
            if not str(file_path).startswith(str(PUBLIC_DIR.resolve())):
                raise AppError("Forbidden.", 403)
            if not file_path.exists() or not file_path.is_file():
                raise AppError("File not found.", 404)
            mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
            cache_control = "no-cache" if file_path.suffix in {".html", ".js", ".css"} else "no-store"
            self.send_headers_only(content_type=mime, content_length=file_path.stat().st_size, html=file_path.suffix == ".html", cache_control=cache_control)
        except Exception as exc:
            self.send_app_error(exc)

    def do_POST(self) -> None:
        try:
            parsed = urlparse(self.path)
            path = parsed.path
            data = read_json_body(self)
            if path.startswith("/api/admin/"):
                require_route_permission(self, path)
            if path == "/api/auth/login":
                payload, cookie = handle_login(self, data)
                self.send_json(payload, 200, {"Set-Cookie": cookie})
            elif path == "/api/auth/register":
                payload, cookie = handle_register(self, data)
                self.send_json(payload, 201, {"Set-Cookie": cookie})
            elif path == "/api/auth/2fa/verify":
                payload, cookie = verify_two_factor_login(self, data)
                self.send_json(payload, 200, {"Set-Cookie": cookie})
            elif path == "/api/auth/logout":
                user = get_session_user(self)
                with connect() as con:
                    if user:
                        con.execute("DELETE FROM sessions WHERE user_id=? AND csrf_token=?", (user.id, user.csrf_token))
                self.send_json({"ok": True}, 200, {"Set-Cookie": cookie_header(clear=True)})
            elif path == "/api/checkout":
                self.send_json(place_order(self, data), 201)
            elif path == "/api/quote":
                self.send_json(create_quote(self, data), 201)
            elif path == "/api/wholesale/apply":
                self.send_json(apply_wholesale(self, data), 201)
            elif path == "/api/account/password-reset":
                self.send_json(request_password_reset(self, data))
            elif path == "/api/account/password-reset/confirm":
                self.send_json(confirm_password_reset(self, data))
            elif path == "/api/account/2fa/setup":
                self.send_json(setup_two_factor(self, data))
            elif path == "/api/account/2fa/confirm":
                self.send_json(confirm_two_factor(self, data))
            elif path == "/api/account/2fa/disable":
                self.send_json(disable_two_factor(self, data))
            elif path == "/api/account/favorite":
                self.send_json(favorite_product(self, data))
            elif path == "/api/account/reorder":
                self.send_json(reorder_from_order(self, data))
            elif path == "/api/account/order-change-request":
                self.send_json(request_order_change(self, data), 201)
            elif path == "/api/account/review":
                self.send_json(submit_product_review(self, data), 201)
            elif path == "/api/account/standing-orders":
                self.send_json(create_standing_order(self, data), 201)
            elif path == "/api/account/standing-orders/update":
                self.send_json(update_standing_order(self, data))
            elif path == "/api/account/preferences":
                self.send_json(save_customer_preferences(self, data))
            elif path == "/api/account/saved-event":
                self.send_json(save_customer_event(self, data), 201)
            elif path == "/api/analytics/event":
                self.send_json(record_analytics_event(self, data), 201)
            elif path == "/api/admin/order-status":
                self.send_json(update_order_status(self, data))
            elif path == "/api/admin/product-update":
                self.send_json(update_product(self, data))
            elif path == "/api/admin/product-create":
                self.send_json(create_product(self, data), 201)
            elif path == "/api/admin/promotion-create":
                self.send_json(create_promotion(self, data), 201)
            elif path == "/api/admin/partner-save":
                self.send_json(save_partner(self, data))
            elif path == "/api/admin/quote-status":
                self.send_json(update_quote_status(self, data))
            elif path == "/api/admin/wholesale-decision":
                self.send_json(decide_wholesale(self, data))
            elif path == "/api/admin/event-save":
                self.send_json(save_event(self, data))
            elif path == "/api/admin/hours-save":
                self.send_json(save_hours(self, data))
            elif path == "/api/admin/settings-save":
                self.send_json(save_settings(self, data))
            elif path == "/api/admin/photo-upload":
                self.send_json(upload_product_photo(self, data), 201)
            elif path == "/api/admin/product-verify":
                self.send_json(verify_product(self, data))
            elif path == "/api/admin/payment-mark":
                self.send_json(mark_payment(self, data))
            elif path == "/api/admin/quote-offer":
                self.send_json(save_quote_offer(self, data))
            elif path == "/api/admin/quote-convert":
                self.send_json(convert_quote_to_order(self, data), 201)
            elif path == "/api/admin/closure-save":
                self.send_json(save_closure(self, data))
            elif path == "/api/admin/launch-save":
                self.send_json(save_launch_item(self, data))
            elif path == "/api/admin/seo-save":
                self.send_json(save_seo_page(self, data))
            elif path == "/api/admin/content-save":
                self.send_json(save_content_block(self, data))
            elif path == "/api/admin/variant-create":
                self.send_json(create_product_variant(self, data), 201)
            elif path == "/api/admin/uat-save":
                self.send_json(save_uat_status(self, data))
            elif path == "/api/admin/pos-import":
                self.send_json(import_pos_csv(self, data), 201)
            elif path == "/api/admin/change-request-status":
                self.send_json(save_change_request_status(self, data))
            elif path == "/api/admin/review-status":
                self.send_json(save_review_status(self, data))
            elif path == "/api/admin/bundle-save":
                self.send_json(save_bundle(self, data))
            elif path == "/api/admin/ingredient-save":
                self.send_json(save_ingredient(self, data))
            elif path == "/api/admin/supplier-save":
                self.send_json(save_supplier(self, data))
            elif path == "/api/admin/product-ingredient-save":
                self.send_json(save_product_ingredient(self, data))
            elif path == "/api/admin/local-event-save":
                self.send_json(save_local_event(self, data))
            elif path == "/api/admin/weather-adjustment-save":
                self.send_json(save_weather_adjustment(self, data))
            elif path == "/api/admin/supplier-quote-save":
                self.send_json(save_supplier_quote(self, data), 201)
            elif path == "/api/admin/recipe-verify":
                self.send_json(verify_recipe(self, data))
            elif path == "/api/admin/qa-run":
                self.send_json(run_static_qa(self, data), 201)
            elif path == "/api/admin/qa-item-save":
                self.send_json(save_qa_item(self, data))
            elif path == "/api/admin/backup-run":
                self.send_json(run_sqlite_backup(self, data), 201)
            elif path == "/api/admin/notification-send":
                self.send_json(process_notification_queue(self, data))
            elif path == "/api/admin/staff-save":
                self.send_json(save_staff(self, data))
            elif path == "/api/admin/invoice-create":
                self.send_json(create_invoice(self, data), 201)
            elif path == "/api/admin/production-task-status":
                self.send_json(update_production_task(self, data))
            elif path == "/api/admin/refund-create":
                self.send_json(create_payment_refund(self, data), 201)
            elif path == "/api/admin/tax-export":
                self.send_json(run_tax_export(self, data), 201)
            elif path == "/api/admin/standing-order-generate":
                self.send_json(generate_standing_order_schedule(self, data), 201)
            elif path == "/api/admin/notification-status":
                self.send_json(save_notification_status(self, data))
            elif path == "/api/webhooks/stripe":
                self.send_json(handle_stripe_webhook(self, data))
            elif path == "/api/webhooks/square":
                self.send_json(handle_square_webhook(self, data))
            else:
                raise AppError("Route not found.", 404)
        except Exception as exc:
            self.send_app_error(exc)

    def serve_static(self, path: str) -> None:
        if path == "/":
            path = "/index.html"
        rel = path.lstrip("/")
        if rel.startswith("api/"):
            raise AppError("Route not found.", 404)
        file_path = (PUBLIC_DIR / rel).resolve()
        if not str(file_path).startswith(str(PUBLIC_DIR.resolve())):
            raise AppError("Forbidden.", 403)
        if not file_path.exists() or not file_path.is_file():
            raise AppError("File not found.", 404)
        content = file_path.read_bytes()
        mime = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(content)))
        for key, value in security_headers(html=file_path.suffix == ".html").items():
            self.send_header(key, value)
        if file_path.suffix in {".html", ".js", ".css"}:
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(content)


def run(host: str, port: int) -> None:
    validate_production_config()
    if DB_PATH.exists():
        validate_production_database()
    init_db(force=False)
    validate_production_database()
    httpd = ThreadingHTTPServer((host, port), BakeryHandler)
    scheme = "https" if production_mode() or env_bool("JB_ASSUME_HTTPS") else "http"
    print(f"Juquilita Bakery v6 running at {scheme}://{host}:{port}")
    if production_mode():
        print("Production mode enabled. Demo credentials are disabled.")
    else:
        print("Demo logins:")
        print("  Admin: admin@juquilita.local / AdminPass2026!")
        print("  Premium: wholesale@taqueria.local / PanDulce2026!")
        print("  Guest: guest@juquilita.local / GuestPass2026!")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--init-db", action="store_true", help="Rebuild data/bakery.db from schema and seeds.")
    args = parser.parse_args()
    try:
        if args.init_db:
            if production_mode():
                require_env("JB_ADMIN_EMAIL", min_len=6)
                require_env("JB_ADMIN_PASSWORD", min_len=14)
            validate_production_config()
            init_db(force=True)
            print(f"Initialized {DB_PATH}")
            return
        run(args.host, args.port)
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
