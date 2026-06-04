#!/usr/bin/env python3
"""Basic smoke tests for the Juquilita Bakery v6 prototype.

Run from project root:
    python3 tests/smoke_test.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from http.cookiejar import CookieJar
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://127.0.0.1:8765"
jar = CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
csrf = ""


def request(path: str, data=None, expect_error=False):
    body = None
    headers = {"Content-Type": "application/json"}
    if csrf:
        headers["X-CSRF-Token"] = csrf
    if data is not None:
        body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=body, headers=headers, method="POST" if data is not None else "GET")
    try:
        with opener.open(req, timeout=4) as res:
            payload = json.loads(res.read().decode("utf-8"))
            if expect_error:
                raise AssertionError(f"Expected error from {path}, got {payload}")
            return payload
    except urllib.error.HTTPError as exc:
        payload = json.loads(exc.read().decode("utf-8"))
        if not expect_error:
            raise AssertionError(f"Unexpected error from {path}: {payload}")
        return payload


def raw_get(path: str) -> str:
    req = urllib.request.Request(BASE + path)
    with opener.open(req, timeout=4) as res:
        return res.read().decode("utf-8")


def wait_ready():
    for _ in range(30):
        try:
            request("/api/health")
            return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("server did not start")


def main():
    subprocess.check_call([sys.executable, "server.py", "--init-db"], cwd=ROOT)
    proc = subprocess.Popen([sys.executable, "-u", "server.py", "--port", "8765"], cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        wait_ready()
        boot = request("/api/bootstrap")
        assert len(boot["products"]) >= 100, len(boot["products"])
        assert any(p["slug"] == "rosca-reyes" and p["order_mode"] == "quote" for p in boot["products"])

        quote = request("/api/quote", {
            "product_slug": "rosca-reyes", "customer_name": "Test Quote", "customer_email": "quote@example.com",
            "customer_phone": "4235550101", "event_type": "Día de Reyes", "quantity": 1, "complexity_tier": "seasonal",
            "servings": 12, "colors": "classic", "pickup_handling": "Keep flat",
            "exact_inscription_confirmed": True, "reference_image_url": "https://example.com/rosca-reference.jpg"
        })
        assert quote["quote_code"].startswith("Q6-")

        blocked = request("/api/checkout", {
            "customer": {"name": "Quote Block", "email": "block@example.com", "phone": "4235550102"},
            "pickup_date": (date.today() + timedelta(days=5)).isoformat(), "pickup_time": "10:30",
            "items": [{"slug": "rosca-reyes", "quantity": 1}]
        }, expect_error=True)
        assert "requires a quote" in blocked["error"]

        pickup_date = (date.today() + timedelta(days=5)).isoformat()
        order = request("/api/checkout", {
            "customer": {"name": "Smoke Customer", "email": "smoke@example.com", "phone": "4235550103"},
            "pickup_date": pickup_date, "pickup_time": "10:30",
            "items": [{"slug": "bolillo", "quantity": 3}, {"slug": "concha", "quantity": 2}],
            "promo_code": "",
            "customer_language": "en",
            "substitution_preference": "similar_ok"
        })
        assert order["order_code"].startswith("JB6-")
        assert order["receipt_url"].startswith("/receipt?token=")

        login = request("/api/auth/login", {"email": "admin@juquilita.local", "password": "AdminPass2026!"})
        global csrf
        csrf = login["user"]["csrf_token"]
        admin = request("/api/admin/dashboard")
        assert admin["metrics"]["open_orders"] >= 1
        assert len(admin["launch_checklist"]) == 100
        assert admin["catalog_health"]["active_products"] >= 100
        assert "seo_pages" in admin and admin["seo_pages"]
        assert "provider_summary" in admin and "staff_users" in admin and admin["staff_users"]
        assert "seasonal_campaigns" in admin and len(admin["seasonal_campaigns"]) >= 2
        assert "product_batches" in admin and admin["product_batches"]
        assert "production_tasks" in admin and len(admin["production_tasks"]) >= 2
        assert "analytics_summary" in admin

        event = request("/api/analytics/event", {"event_name": "smoke_checkout_view", "payload": {"source": "smoke"}})
        assert event["ok"] is True

        deep = request("/api/health/deep")
        assert deep["ok"] is True and "db" in deep

        qa = request("/api/admin/qa-run", {"audit_type": "accessibility", "target_url": BASE})
        assert qa["run_id"] and qa["score"] >= 0

        task_update = request("/api/admin/production-task-status", {"task_id": admin["production_tasks"][0]["id"], "status": "doing", "notes": "Smoke rush board update"})
        assert task_update["ok"] is True

        refund = request("/api/admin/refund-create", {"order_id": order["order_id"], "amount": 0.50, "reason": "Smoke refund record", "notes": "No real payment moved"})
        assert refund["refund_id"]

        tax_export = request("/api/admin/tax-export", {"start_date": pickup_date, "end_date": pickup_date})
        assert tax_export["order_count"] >= 1 and tax_export["csv_path"].endswith(".csv")

        standing_run = request("/api/admin/standing-order-generate", {"start_date": date.today().isoformat(), "days": 14})
        assert standing_run["ok"] is True and standing_run["created"] >= 1

        supplier_quote = request("/api/admin/supplier-quote-save", {
            "supplier_id": admin["suppliers"][0]["id"] if admin["suppliers"] else "",
            "ingredient_id": admin["ingredients"][0]["id"], "quoted_unit": "case", "quoted_qty": 50,
            "quoted_total": 40.00, "status": "owner_verified", "notes": "Smoke supplier cost"
        })
        assert supplier_quote["quote_id"]

        recipe = request("/api/admin/recipe-verify", {"product_id": admin["products"][0]["id"], "recipe_version": "smoke", "yield_qty": 1, "yield_unit": "each", "labor_minutes": 1, "owner_verified": True, "notes": "Smoke recipe verification"})
        assert recipe["ok"] is True

        staff = request("/api/admin/staff-save", {"name": "Smoke Cashier", "email": "smoke.cashier@example.com", "role": "cashier", "temporary_password": "SmokeCashierPass2026!", "permissions": "admin:dashboard"})
        assert staff["staff_id"]

        backup = request("/api/admin/backup-run", {"reason": "smoke test backup"})
        assert backup["ok"] is True and backup["file_size_bytes"] > 0

        tracked = request(f"/api/order/track?code={order['order_code']}&email=smoke@example.com")
        assert tracked["order"]["order_code"] == order["order_code"]
        assert tracked["order"]["receipt_url"].startswith("/receipt?token=")
        receipt_html = raw_get(tracked["order"]["receipt_url"])
        assert order["order_code"] in receipt_html
        public_code_receipt = raw_get(f"/receipt?code={order['order_code']}")
        assert order["order_code"] in public_code_receipt

        page_html = raw_get("/page/oaxacan-bread")
        assert "Oaxacan" in page_html

        reset = request("/api/account/password-reset", {"email": "guest@juquilita.local"})
        assert reset["ok"] is True
        with sqlite3.connect(ROOT / "data" / "bakery.db") as con:
            con.row_factory = sqlite3.Row
            note = con.execute("SELECT body FROM notifications WHERE subject='Reset your Juquilita Bakery password' ORDER BY id DESC LIMIT 1").fetchone()
        token_match = re.search(r"token=([^\s]+)", note["body"])
        assert token_match
        confirmed = request("/api/account/password-reset/confirm", {"token": token_match.group(1), "password": "GuestPass2026!Reset"})
        assert confirmed["ok"] is True

        change = request("/api/account/order-change-request", {"order_code": order["order_code"], "email": "smoke@example.com", "request_type": "edit", "reason": "Smoke test change request"})
        assert change["status"] == "new"

        review = request("/api/account/review", {"product_slug": "concha", "customer_name": "Smoke Customer", "customer_email": "smoke@example.com", "rating": 5, "body": "Smoke test review text"})
        assert review["status"] == "new"

        offer = request("/api/admin/quote-offer", {"quote_id": quote["quote_id"], "amount": 38.50, "deposit_required": 10, "message": "Smoke quote offer"})
        assert offer["amount"] == 38.5

        invoice = request("/api/admin/invoice-create", {"order_id": order["order_id"], "terms": "Due on pickup"})
        assert invoice["invoice_code"].startswith("INV-")

        pos = request("/api/admin/pos-import", {"filename": "smoke.csv", "csv_text": "customer_name,customer_email,customer_phone,pickup_date,pickup_time,product_slug,quantity,unit_price\nSmoke,smoke@example.com,4235550103,2026-06-01,10:00,bolillo,4,0.80"})
        assert pos["status"] == "mapped" and pos["row_count"] == 1

        bundle = request("/api/admin/bundle-save", {"slug": "smoke-bundle", "name_en": "Smoke Bundle", "name_es": "Paquete Smoke", "description_en": "Test", "description_es": "Prueba", "items_json": "{\"bolillo\": 2}", "sort_order": 10, "is_active": True})
        assert bundle["bundle_id"]

        bad_price = request("/api/admin/product-update", {"id": 1, "base_price": -1}, expect_error=True)
        assert "base price" in bad_price["error"].lower()

        bad_promo = request("/api/admin/promotion-create", {
            "title": "Bad Promo", "code": "BAD999", "discount_type": "percent", "discount_value": 999,
            "min_subtotal": 0, "category_key": "all", "applies_to_role": "all",
            "starts_on": (date.today()+timedelta(days=5)).isoformat(), "ends_on": date.today().isoformat()
        }, expect_error=True)
        assert "discount value" in bad_promo["error"].lower() or "end date" in bad_promo["error"].lower()

        sent = request("/api/admin/notification-send", {"dry_run": True, "limit": 10})
        assert "processed" in sent
        print("Smoke tests passed.")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
