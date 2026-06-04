#!/usr/bin/env python3
"""Import Juquilita Bakery website images into the local app.

The script downloads image assets from the old Squarespace website, stores
browser-ready local copies under public/imported/website, writes a manifest, and
optionally applies product image mappings to data/bakery.db.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sqlite3
import ssl
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    from bs4 import BeautifulSoup  # type: ignore
except Exception as exc:  # pragma: no cover - operator-facing script.
    raise SystemExit("beautifulsoup4 is required for this importer.") from exc

try:
    from PIL import Image, ImageOps  # type: ignore
except Exception:  # pragma: no cover - importer can keep originals without PIL.
    Image = None
    ImageOps = None


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
ASSET_DIR = PUBLIC_DIR / "imported" / "website"
MANIFEST_PATH = ASSET_DIR / "manifest.json"
DB_PATH = ROOT / "data" / "bakery.db"
SOURCE_PAGES = [
    "https://www.juquilitabakerypyp.com/",
    "https://www.juquilitabakerypyp.com/new-index-1/",
]
USER_AGENT = "JuquilitaBakeryImageImporter/1.0"
MAX_EDGE = 1600


LABEL_OVERRIDES = {
    "bolillos": "bolillo",
    "telera": "telera",
    "polvorones": "polvoron-azucar",
    "polvorones de azucar": "polvoron-azucar",
    "polvorones mexican sugar cookies": "polvoron-rosa",
    "polvorones con azucar rosa": "polvoron-rosa",
    "lima polvorones sugar cookie with strawberry jam": "lima-fresa",
    "polvorones con fresa arriba": "lima-fresa",
    "zurrapa": "zurrapa",
    "polvorones de 3 colores": "zurrapa",
    "sprinkled polvorones": "polvoron-grajea",
    "polvorones de grajea": "polvoron-grajea",
    "smiley cookies": "galleta-carita",
    "galletas de carita": "galleta-carita",
    "heart shaped sprinkled cookies": "galleta-corazon",
    "galletas de corazon": "galleta-corazon",
    "polvoron de pedasos de chocolate sugar cookie with chocolate": "polvoron-chocolate",
    "sprinkled cookies": "galleta-grajea",
    "galletas de grajea chispas": "galleta-grajea",
    "polvorones de nuez small sugar cookie with pecans": "polvoron-nuez",
    "sandia watermelon shaped cookies": "sandia-cookie",
    "conchas": "concha",
    "chilindrinas de chocolate": "chilindrina-chocolate",
    "bisquit": "bisquit",
    "magdalenas with sprinkles": "magdalena-grajea",
    "magdalenas plain": "magdalena-simple",
    "marranitos": "marranito",
    "piedras": "piedra",
    "ladrillos": "ladrillo",
    "cuerno": "cuerno",
    "aretes": "arete",
    "aretes pink": "arete-rosa",
    "monos con ajonjolin bows with sesame on top": "mono-ajonjolin",
    "yoyos de ajonjolin": "yoyo-ajonjolin",
    "yoyos de grajea yoyo with sprinkles": "yoyo-grajea",
    "rehilete esponjado": "rehilete-esponjado",
    "nopal": "nopal",
    "borrachos": "borracho",
    "borracho de chocolate": "borracho-chocolate",
    "nubes": "nube",
    "bigotes": "bigote",
    "corbata o mono bowtie": "corbata-mono",
    "chirimoyas": "chirimoya",
    "alcatraz": "alcatraz",
    "boquitas": "boquita",
    "troncos": "tronco",
    "elotitos": "elotito",
    "gusano polveado": "gusano-polveado",
    "lenguas": "lengua",
    "piez": "piez",
    "piez de chocolate": "piez-chocolate",
    "cuernitos polveadas de chocolate": "cuernito-chocolate",
    "panadero de chocolate": "panadero-chocolate",
    "panadero": "panadero",
    "nueces polveadas": "nueces-polveadas",
    "nueces normal": "nueces-normal",
    "empanadas de crema bavaria bavarian cream filled empanadas": "empanada-bavaria",
    "empanadas de calabaza pumpkin empanadas": "empanada-calabaza",
    "empanadas de manzana apple empanadas": "empanada-manzana",
    "empanadas de pina pineapple empanadas": "empanada-pina",
    "taquitos de fresa strawberry filled": "taquito-fresa",
    "taquitos de crema bavaria bavarian cream filled": "taquito-bavaria",
    "empanaditas de cajeta": "empanadita-cajeta",
    "empanaditas de pina pineapple filled": "empanadita-pina",
    "mantecadas con grajea vanilla cupcake with sprinkles": "magdalena-grajea",
    "mantecadas con nuez vanilla cupcake with pecan": "mantecada-nuez",
    "mantecadas con grajea de chocolate vanilla cupcake with chocolate sprinkles": "mantecada-chocolate",
    "ojos de buey eyes": "ojos-buey",
    "ninos envueltos": "nino-envuelto",
    "nino envuelto": "nino-envuelto",
    "mechudos": "mechudo",
    "tomatillos": "tomatillo",
    "pinguino penguins": "pinguino",
    "cubiletes de queso mexican cheese pie cheesecake": "cubilete-queso",
    "budin mexican bread pudding": "budin-clasico",
    "churros": "churro-simple",
    "besos yo yo s kisses or yo yo s": "beso-yoyo",
    "rebanada con mantequilla slice with butter and sugar": "rebanada-mantequilla",
    "donas de azucar sugar donuts": "dona-azucar",
    "trenzas": "trenza",
    "donas rellenas": "dona-rellena-bavaria",
    "donas de chocolate chocolate covered donuts": "dona-chocolate",
    "cuerno de danes danish style croissant": "cuerno-danes",
    "conos de danes relleno de crema bavaria danish style cones with bavarian cream": "cono-danes-bavaria",
    "orejas elephant ears": "oreja",
    "barquillos de crema bavaria puff pastry cones with bavarian cream": "barquillo-bavaria",
    "banderilla": "banderilla",
    "empanadas doradas apple or strawberry turnovers": "dorado-fresa-manzana",
    "canastas baskets": "canasta",
    "taquitos dorados de pina o guayaba con queso": "taquito-dorado-guayaba-queso",
    "manteconchas": "manteconcha",
    "flautas de fresa": "flauta-fresa",
    "flautas de pina": "flauta-pina",
    "pan de muerto": "pan-muerto-yema-carita",
    "rosca de reyes": "rosca-reyes",
}


def normalize(text: str) -> str:
    text = unquote(text or "").lower()
    text = text.replace("+", " ")
    text = re.sub(r"[\u0300-\u036f]", "", text)
    replacements = {"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ñ": "n", "ü": "u"}
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slugify(text: str, fallback: str = "image") -> str:
    slug = normalize(text).replace(" ", "-").strip("-")
    return slug[:80] or fallback


def canonical_url(url: str) -> str:
    if url.startswith("//"):
        url = "https:" + url
    parts = urlsplit(url)
    if "squarespace" in parts.netloc:
        return urlunsplit((parts.scheme or "https", parts.netloc, parts.path, "", ""))
    return url


def filename_from_url(url: str) -> str:
    path = unquote(urlsplit(url).path)
    base = Path(path).name
    if not base or "." not in base:
        qs = urlsplit(url).query
        match = re.search(r"badge=([^&]+)", qs)
        base = match.group(1) if match else "image.jpg"
    return base


def fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urlopen(req, timeout=30) as res:
            return res.read()
    except URLError as exc:
        if "CERTIFICATE_VERIFY_FAILED" not in str(exc.reason):
            raise
        with urlopen(req, timeout=30, context=ssl._create_unverified_context()) as res:
            return res.read()


def image_urls_from(img: Any) -> list[str]:
    urls = []
    for attr in ("data-image", "data-src", "src"):
        value = img.get(attr)
        if value and not value.startswith("data:"):
            urls.append(canonical_url(value))
    srcset = img.get("srcset") or ""
    for part in srcset.split(","):
        value = part.strip().split(" ")[0]
        if value and not value.startswith("data:"):
            urls.append(canonical_url(value))
    out = []
    seen = set()
    for url in urls:
        if url not in seen:
            seen.add(url)
            out.append(url)
    return out


def label_for_image(img: Any) -> str:
    label = (img.get("alt") or "").strip()
    item = img.find_parent("article", class_="Index-gallery-item")
    if item:
        parts = []
        heading = item.select_one(".Index-gallery-item-content-heading")
        body = item.select_one(".Index-gallery-item-content-body")
        if heading:
            parts.append(" ".join(heading.get_text(" ", strip=True).split()))
        if body:
            parts.append(" ".join(body.get_text(" ", strip=True).split()))
        if parts:
            label = " - ".join(parts)
    if not label:
        caption_parent = img.find_parent("figure")
        caption = caption_parent.find("figcaption") if caption_parent else None
        if caption:
            label = " ".join(caption.get_text(" ", strip=True).split())
    return label


def extract_records() -> list[dict[str, Any]]:
    by_url: dict[str, dict[str, Any]] = {}
    for page in SOURCE_PAGES:
        html = fetch(page).decode("utf-8", errors="replace")
        soup = BeautifulSoup(html, "html.parser")
        for img in soup.find_all("img"):
            urls = image_urls_from(img)
            if not urls:
                continue
            label = label_for_image(img)
            for url in urls:
                record = by_url.setdefault(url, {"source_url": url, "source_pages": [], "labels": []})
                if page not in record["source_pages"]:
                    record["source_pages"].append(page)
                if label and label not in record["labels"]:
                    record["labels"].append(label)
    return list(by_url.values())


def load_products() -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        return [dict(row) for row in con.execute("SELECT slug,name_es,name_en,search_terms,category_key FROM products WHERE is_active=1").fetchall()]


def product_for(record: dict[str, Any], products: list[dict[str, Any]]) -> str:
    labels = " ".join(record.get("labels") or [])
    base = filename_from_url(record["source_url"])
    haystack = normalize(labels + " " + base)
    for key, slug in sorted(LABEL_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True):
        if key in haystack:
            return slug
    best_slug = ""
    best_score = 0
    words = set(haystack.split())
    for product in products:
        product_blob = normalize(" ".join(str(product.get(k, "")) for k in ("slug", "name_es", "name_en", "search_terms")))
        product_words = set(product_blob.split())
        score = len(words & product_words)
        if normalize(product["slug"]).replace("-", " ") in haystack:
            score += 6
        if score > best_score:
            best_slug = product["slug"]
            best_score = score
    return best_slug if best_score >= 2 else ""


def save_image(raw: bytes, path: Path) -> tuple[int, int, str]:
    if Image is None or ImageOps is None:
        path.write_bytes(raw)
        return 0, 0, path.suffix.lstrip(".").lower()
    with Image.open(io.BytesIO(raw)) as img:
        img = ImageOps.exif_transpose(img)
        width, height = img.size
        if max(width, height) > MAX_EDGE:
            scale = MAX_EDGE / max(width, height)
            img = img.resize((int(width * scale), int(height * scale)))
            width, height = img.size
        if img.mode in {"RGBA", "LA"}:
            path = path.with_suffix(".png")
            img.save(path, "PNG", optimize=True)
            return width, height, "png"
        path = path.with_suffix(".jpg")
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(path, "JPEG", quality=84, optimize=True, progressive=True)
        return width, height, "jpg"


def apply_to_db(manifest: dict[str, Any]) -> int:
    if not DB_PATH.exists():
        return 0
    applied = 0
    with sqlite3.connect(DB_PATH) as con:
        con.row_factory = sqlite3.Row
        for image in manifest.get("images", []):
            slug = image.get("product_slug") or ""
            if not slug:
                continue
            product = con.execute("SELECT id,image_url FROM products WHERE slug=?", (slug,)).fetchone()
            if not product:
                continue
            exists = con.execute("SELECT 1 FROM product_images WHERE product_id=? AND image_url=?", (product["id"], image["local_url"])).fetchone()
            is_primary = 0 if product["image_url"] and product["image_url"] != image["local_url"] else 1
            if not exists:
                con.execute(
                    """
                    INSERT INTO product_images(product_id,image_url,alt_text,image_status,source,is_primary,sort_order,uploaded_by,uploaded_at)
                    VALUES(?,?,?,?,?,?,?,?,?)
                    """,
                    (product["id"], image["local_url"], image.get("label") or slug, "approved", "old_website_import", is_primary, image.get("sort_order", 100), None, manifest["imported_at"]),
                )
            if is_primary:
                con.execute(
                    "UPDATE products SET image_url=?, image_alt=?, photo_status='real_photo_verified', updated_at=? WHERE id=?",
                    (image["local_url"], image.get("label") or slug, manifest["imported_at"], product["id"]),
                )
                con.execute("UPDATE photo_shot_list SET status='approved', updated_at=? WHERE product_id=? AND status!='approved'", (manifest["imported_at"], product["id"]))
            applied += 1
    return applied


def import_images(skip_download: bool = False, apply_db: bool = True) -> dict[str, Any]:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    products = load_products()
    records = extract_records()
    images = []
    used_names: dict[str, int] = {}
    for idx, record in enumerate(records, start=1):
        label = (record.get("labels") or [""])[0] or filename_from_url(record["source_url"])
        name_seed = label if label and not re.match(r"^IMG[_-]|\d", label, re.I) else filename_from_url(record["source_url"])
        base_slug = slugify(name_seed, f"image-{idx}")
        used_names[base_slug] = used_names.get(base_slug, 0) + 1
        suffix = f"-{used_names[base_slug]}" if used_names[base_slug] > 1 else ""
        target = ASSET_DIR / f"{idx:03d}-{base_slug}{suffix}.jpg"
        width = height = 0
        fmt = "unknown"
        existing = sorted(ASSET_DIR.glob(f"{idx:03d}-{base_slug}{suffix}.*"))
        if skip_download and existing:
            local_path = existing[0]
        else:
            raw = fetch(record["source_url"])
            local_path = target
            try:
                width, height, fmt = save_image(raw, local_path)
                if fmt == "png":
                    local_path = local_path.with_suffix(".png")
            except Exception:
                local_path = target.with_suffix(Path(filename_from_url(record["source_url"])).suffix or ".img")
                local_path.write_bytes(raw)
        local_url = "/" + str(local_path.relative_to(PUBLIC_DIR)).replace("\\", "/")
        product_slug = product_for(record, products)
        images.append({
            "source_url": record["source_url"],
            "source_pages": record["source_pages"],
            "local_url": local_url,
            "label": label,
            "all_labels": record.get("labels") or [],
            "product_slug": product_slug,
            "width": width,
            "height": height,
            "format": fmt,
            "sort_order": idx,
        })
        print(f"{idx:03d}/{len(records)} {local_url} {('-> ' + product_slug) if product_slug else ''}")
        time.sleep(0.02)
    manifest = {
        "source": "https://www.juquilitabakerypyp.com/",
        "source_pages": SOURCE_PAGES,
        "imported_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "image_count": len(images),
        "matched_product_count": len({i["product_slug"] for i in images if i["product_slug"]}),
        "images": images,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    if apply_db:
        applied = apply_to_db(manifest)
        manifest["db_records_applied"] = applied
        MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-download", action="store_true", help="Reuse existing files where possible.")
    parser.add_argument("--no-db", action="store_true", help="Do not update data/bakery.db.")
    args = parser.parse_args()
    manifest = import_images(skip_download=args.skip_download, apply_db=not args.no_db)
    matched = manifest.get("matched_product_count", 0)
    applied = manifest.get("db_records_applied", 0)
    print(f"Imported {manifest['image_count']} images; matched {matched} products; applied {applied} DB image records.")


if __name__ == "__main__":
    main()
