#!/usr/bin/env python3
"""Use the Desktop juquilita_relabel_output image package in the app."""
from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from product_image_mapping import apply_product_image_map

PUBLIC_DIR = ROOT / "public"
TARGET_DIR = PUBLIC_DIR / "imported" / "website"
MANIFEST_PATH = TARGET_DIR / "manifest.json"
DB_PATH = ROOT / "data" / "bakery.db"
DEFAULT_RELABEL_DIR = Path("/Users/tt/Desktop/juquilita_relabel_output")

PRODUCT_OVERRIDES = {
    "rosca de reyes": "rosca-reyes",
    "tres leches": "tres-leches-rebanada",
    "fruit tart": "tarta-fruta",
    "cake display": "pastel-decorado",
    "tier cake": "pastel-decorado",
    "anniversary": "pastel-decorado",
    "baptism": "pastel-decorado",
    "celebration cake": "pastel-decorado",
    "pan de muerto": "pan-muerto-yema-carita",
    "strawberry jam thumbprint": "lima-fresa",
    "rainbow sprinkle cookies": "galleta-grajea",
    "vanilla conchas": "concha",
    "pink conchas": "concha",
    "small colorful conchas": "concha",
    "assorted colorful conchas": "concha",
    "bavarian cream pastry cones": "barquillo-bavaria",
    "cream filled croissant cones": "cono-danes-bavaria",
    "sugar polvorones": "polvoron-azucar",
    "pink streak sugar polvorones": "polvoron-rosa",
    "round sprinkle cookies": "galleta-grajea",
    "pineapple canastas": "canasta",
    "strawberry canastas": "canasta",
    "golden rolled puff pastry sticks": "banderilla",
    "lattice top fruit turnovers": "dorado-fresa-manzana",
    "round pineapple fruit turnovers": "empanada-pina",
    "bavarian cream filled oval rolls": "dona-rellena-bavaria",
    "stuffed savory breads": "pan-relleno",
    "pan de yema": "pan-de-yema",
    "plain vanilla cupcakes": "mini-cake-tres-leches",
    "vanilla cupcakes": "mini-cake-tres-leches",
    "chocolate cream cupcakes": "mini-cake-tres-leches",
    "mini cakes": "mini-cake-tres-leches",
    "refrigerated dessert display": "",
    "bread display case": "",
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_pages(value: str) -> list[str]:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]


def infer_product_slug(row: dict[str, Any]) -> str:
    explicit = str(row.get("product_slug_from_page") or "").strip()
    if explicit:
        return explicit
    text = " ".join(str(row.get(key) or "") for key in ("label", "alt_text", "new_filename")).lower()
    for needle, slug in sorted(PRODUCT_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True):
        if needle in text:
            return slug
    return ""


def copy_images(relabel_dir: Path) -> list[dict[str, Any]]:
    metadata_path = relabel_dir / "juquilita_image_relabels.json"
    image_dir = relabel_dir / "renamed_images"
    if not metadata_path.exists():
        raise SystemExit(f"Missing metadata: {metadata_path}")
    if not image_dir.exists():
        raise SystemExit(f"Missing image directory: {image_dir}")

    rows = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise SystemExit("Relabel JSON must be a list.")

    if TARGET_DIR.exists():
        shutil.rmtree(TARGET_DIR)
    TARGET_DIR.mkdir(parents=True, exist_ok=True)

    images = []
    for row in rows:
        filename = str(row.get("new_filename") or "").strip()
        if not filename:
            continue
        src = image_dir / filename
        if not src.exists():
            raise SystemExit(f"Missing relabeled image: {src}")
        dst = TARGET_DIR / filename
        shutil.copy2(src, dst)
        local_url = "/" + str(dst.relative_to(PUBLIC_DIR)).replace("\\", "/")
        images.append({
            "source_url": row.get("source_url", ""),
            "source_pages": parse_pages(row.get("source_pages", "")),
            "local_url": local_url,
            "label": row.get("label", ""),
            "alt_text": row.get("alt_text", "") or row.get("label", ""),
            "all_labels": [value for value in [row.get("original_page_label", ""), row.get("label", "")] if value],
            "product_slug": infer_product_slug(row),
            "width": int(row.get("width") or 0),
            "height": int(row.get("height") or 0),
            "format": dst.suffix.lstrip(".").lower(),
            "sort_order": int(row.get("sort_order") or 100),
            "confidence": row.get("confidence", ""),
            "basis": row.get("basis", ""),
            "original_filename": row.get("original_filename", ""),
            "new_filename": filename,
        })
    return images


def apply_to_db(manifest: dict[str, Any]) -> int:
    if not DB_PATH.exists():
        return 0
    applied = 0
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        con.execute("DELETE FROM product_images WHERE source IN ('old_website_import','relabel_import') OR image_url LIKE '/imported/website/%'")
        con.execute("UPDATE products SET image_url='', image_alt='', photo_status='needs_real_photo', updated_at=? WHERE image_url LIKE '/imported/website/%'", (manifest["imported_at"],))
        for image in sorted(manifest.get("images", []), key=lambda item: int(item.get("sort_order") or 100)):
            slug = str(image.get("product_slug") or "").strip()
            local_url = str(image.get("local_url") or "").strip()
            if not slug or not local_url:
                continue
            product = con.execute("SELECT id FROM products WHERE slug=?", (slug,)).fetchone()
            if not product:
                continue
            alt_text = str(image.get("alt_text") or image.get("label") or slug)
            con.execute(
                """
                INSERT INTO product_images(product_id,image_url,alt_text,image_status,source,is_primary,sort_order,uploaded_by,uploaded_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                """,
                (product["id"], local_url, alt_text, "approved", "relabel_import", 0, int(image.get("sort_order") or 100), None, manifest["imported_at"]),
            )
            applied += 1
        apply_product_image_map(con, PUBLIC_DIR)
    return applied


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--relabel-dir", type=Path, default=DEFAULT_RELABEL_DIR)
    parser.add_argument("--no-db", action="store_true", help="Write files and manifest without updating SQLite.")
    args = parser.parse_args()

    images = copy_images(args.relabel_dir)
    manifest = {
        "source": "juquilita_relabel_output",
        "source_package": str(args.relabel_dir),
        "source_pages": ["https://www.juquilitabakerypyp.com/", "https://www.juquilitabakerypyp.com/new-index-1/"],
        "imported_at": utc_now(),
        "image_count": len(images),
        "matched_product_count": len({image["product_slug"] for image in images if image.get("product_slug")}),
        "images": images,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    if not args.no_db:
        manifest["db_records_applied"] = apply_to_db(manifest)
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Imported {manifest['image_count']} relabeled images; matched {manifest['matched_product_count']} products; applied {manifest.get('db_records_applied', 0)} DB image records.")


if __name__ == "__main__":
    main()
