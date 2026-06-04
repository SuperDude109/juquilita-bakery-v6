#!/usr/bin/env python3
"""Validate storefront product prices against the original Juquilita menu."""
from __future__ import annotations

import argparse
import csv
import sqlite3
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from product_image_mapping import canonical_key_for_names  # noqa: E402


DB_PATH = ROOT / "data" / "bakery.db"
REPORT_PATH = ROOT / "reports" / "product_price_validation_report.csv"
SOURCE_URL = "https://www.juquilitabakerypyp.com/new-index-1/"


def money(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def add_price(expected: dict[str, dict[str, str]], slugs: list[str], price: str, source_group: str, source_lines: str) -> None:
    for slug in slugs:
        expected[slug] = {
            "expected_base_price": price,
            "expected_order_mode": "order",
            "price_status": "officialMenu",
            "source_group": source_group,
            "source_url": SOURCE_URL,
            "source_lines": source_lines,
        }


def add_quote(expected: dict[str, dict[str, str]], slugs: list[str], source_group: str, source_lines: str) -> None:
    for slug in slugs:
        expected[slug] = {
            "expected_base_price": "",
            "expected_order_mode": "quote",
            "price_status": "quote",
            "source_group": source_group,
            "source_url": SOURCE_URL,
            "source_lines": source_lines,
        }


def expected_prices() -> dict[str, dict[str, str]]:
    expected: dict[str, dict[str, str]] = {}
    add_price(expected, ["bolillo", "telera", "panbasos"], "0.80", "Savory daily breads", "48-72")
    add_price(expected, ["bolinachos"], "2.25", "Bolinachos", "74-80")
    add_price(expected, ["pan-relleno"], "2.75", "Stuffed bread", "82-87")
    add_price(expected, ["relleno-chorizo"], "3.99", "Filled Chorizo", "89-95")
    add_price(expected, [
        "polvoron-azucar", "polvoron-rosa", "lima-fresa", "zurrapa", "polvoron-grajea",
        "galleta-carita", "galleta-corazon", "polvoron-chocolate", "galleta-grajea",
        "polvoron-nuez", "sandia-cookie",
    ], "0.90", "Galletas y polvorones", "99-105")
    add_price(expected, [
        "concha", "chilindrina-chocolate", "rehilete-esponjado", "nopal", "borracho",
        "borracho-chocolate", "nube", "bigote", "corbata-mono", "chirimoya", "alcatraz",
        "boquita", "tronco", "elotito", "gusano-polveado", "lengua", "panadero",
        "panadero-chocolate", "nueces-normal",
    ], "0.90", "Spongy/fluffy bread", "107-112")
    add_price(expected, [
        "pan-manteca", "piedra", "ladrillo", "cuerno", "arete", "arete-rosa",
        "mono-ajonjolin", "yoyo-ajonjolin", "yoyo-grajea", "piez", "piez-chocolate",
        "cuernito-chocolate", "nueces-polveadas",
    ], "0.90", "Shortening bread", "114-120")
    add_price(expected, ["bisquit", "magdalena-simple", "magdalena-grajea", "marranito", "mantecada-nuez", "mantecada-chocolate"], "0.90", "Madalenas, Bisquit, Marranito", "122-128")
    add_price(expected, ["empanadita-cajeta", "empanadita-pina"], "0.65", "Mini bread", "130-135")
    add_price(expected, ["pan-amarillo", "pan-serrano", "pan-de-yema", "semitas", "ojaldra"], "0.90", "Oaxacan style bread", "137-143")
    add_price(expected, ["oreja", "campechana", "banderilla", "reganada", "rebanada-mantequilla", "churro-simple"], "1.00", "Puff pastry with no filling and others", "145-151")
    add_price(expected, ["dona-azucar", "trenza", "dona-glaseada"], "1.15", "Donuts", "153-159")
    add_price(expected, ["empanada-bavaria", "empanada-calabaza", "empanada-manzana", "empanada-pina"], "1.15", "Filled empanadas", "161-166")
    add_price(expected, ["dona-chocolate", "dona-rellena-bavaria"], "1.25", "Chocolate or filled donuts", "168-174")
    add_price(expected, ["cubilete-queso", "beso-yoyo", "ojos-buey", "taquito-fresa", "taquito-bavaria", "manteconcha", "flauta-fresa", "flauta-pina"], "1.25", "Other dessert style options", "176-181")
    add_price(expected, ["budin-clasico", "budin-durazno-coco"], "1.89", "Bread pudding", "183-189")
    add_price(expected, ["cuerno-danes", "cono-danes-bavaria", "barquillo-bavaria", "dorado-fresa-manzana", "canasta", "taquito-dorado-guayaba-queso"], "1.99", "Filled puff pastries", "191-196")
    add_price(expected, ["churro-fresa", "churro-chocolate", "churro-cajeta"], "2.50", "Filled churros", "198-204")
    add_price(expected, ["pinguino", "tomatillo", "mechudo", "nino-envuelto"], "2.75", "Pinguinos, tomatillos, mechudos, nino envueltos", "206-212")
    add_price(expected, ["mil-hojas-bavaria", "mil-hojas-guayaba"], "3.50", "Decorated cakes and mil hojas", "214-219")
    add_price(expected, ["tarta-fruta"], "3.99", "Fruit tarts", "221-227")
    add_price(expected, ["tres-leches-rebanada"], "3.25", "Tres leches cake slice", "230-238")
    add_price(expected, ["flan-individual"], "3.49", "Individual flan", "240-246")
    add_price(expected, ["chocoflan-individual"], "3.89", "Individual chocoflan", "248-254")
    add_price(expected, ["pastel-cuarto"], "45.00", "1/4 sheet cake", "256-263")
    add_price(expected, ["pastel-medio"], "70.00", "1/2 sheet cake", "265-271")
    add_price(expected, ["pastel-plancha"], "100.00", "Full sheet cake", "273-279")
    add_price(expected, ["mini-cake-tres-leches"], "21.99", "Mini cakes", "281-289")
    add_price(expected, ["flan-charola", "chocoflan-10"], "34.99", "Extra goods flan and chocoflan", "291-304")
    add_quote(expected, ["pastel-decorado"], "Decorated cakes vary by decoration/flavor", "305-310")
    add_quote(expected, ["pan-muerto-azucar", "pan-muerto-rosa", "pan-muerto-yema-carita", "rosca-reyes"], "Seasonal specialty breads without listed menu price", "22-42")
    return expected


def validate(db_path: Path) -> list[dict[str, str]]:
    expected = expected_prices()
    with sqlite3.connect(db_path) as con:
        con.row_factory = sqlite3.Row
        rows = con.execute("SELECT * FROM products WHERE is_active=1 ORDER BY id").fetchall()
    report: list[dict[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        seen.add(row["slug"])
        expected_row = expected.get(row["slug"])
        actual_price = money(row["base_price"])
        failures: list[str] = []
        if not expected_row:
            failures.append("product is missing from official price map")
            expected_price = None
            expected_mode = ""
            price_status = ""
            source_group = ""
            source_lines = ""
            source_url = ""
        else:
            expected_price = money(expected_row["expected_base_price"])
            expected_mode = expected_row["expected_order_mode"]
            price_status = expected_row["price_status"]
            source_group = expected_row["source_group"]
            source_lines = expected_row["source_lines"]
            source_url = expected_row["source_url"]
            if expected_mode == "quote":
                if row["order_mode"] != "quote":
                    failures.append("expected quote order mode")
                if actual_price is not None:
                    failures.append("quote item has base price")
            else:
                if row["order_mode"] != "order":
                    failures.append("expected orderable product")
                if actual_price != expected_price:
                    failures.append(f"base price mismatch: expected {expected_price}, got {actual_price}")
        canonical_key = row["canonical_key"] or canonical_key_for_names(row["name_es"], row["name_en"])
        report.append({
            "product_id": str(row["id"]),
            "product_slug": row["slug"],
            "product_display_name": f"{row['name_es']} / {row['name_en']}",
            "canonical_key": canonical_key,
            "actual_base_price": "" if actual_price is None else f"{actual_price:.2f}",
            "expected_base_price": "" if expected_price is None else f"{expected_price:.2f}",
            "actual_order_mode": row["order_mode"],
            "expected_order_mode": expected_mode,
            "price_status": price_status,
            "source_group": source_group,
            "source_url": source_url,
            "source_lines": source_lines,
            "validation_result": "fail" if failures else "pass",
            "failure_reason": "; ".join(failures),
        })
    for slug in sorted(set(expected) - seen):
        expected_row = expected[slug]
        report.append({
            "product_id": "",
            "product_slug": slug,
            "product_display_name": "",
            "canonical_key": "",
            "actual_base_price": "",
            "expected_base_price": expected_row["expected_base_price"],
            "actual_order_mode": "",
            "expected_order_mode": expected_row["expected_order_mode"],
            "price_status": expected_row["price_status"],
            "source_group": expected_row["source_group"],
            "source_url": expected_row["source_url"],
            "source_lines": expected_row["source_lines"],
            "validation_result": "fail",
            "failure_reason": "official price map product is missing from database",
        })
    return report


def write_report(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "product_id", "product_slug", "product_display_name", "canonical_key",
        "actual_base_price", "expected_base_price", "actual_order_mode", "expected_order_mode",
        "price_status", "source_group", "source_url", "source_lines",
        "validation_result", "failure_reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DB_PATH)
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    args = parser.parse_args()
    rows = validate(args.db)
    write_report(rows, args.report)
    failures = [row for row in rows if row["validation_result"] == "fail"]
    print(f"Validated {len(rows)} product price rows. Report: {args.report}")
    if failures:
        for row in failures[:12]:
            print(f"FAIL {row['product_slug']}: {row['failure_reason']}")
        if len(failures) > 12:
            print(f"... {len(failures) - 12} more failures")
        raise SystemExit(1)
    print("All product price validations passed.")


if __name__ == "__main__":
    main()
