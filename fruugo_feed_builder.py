#!/usr/bin/env python3
"""Build the Avenida Prestige Fruugo CSV from the private supplier feed.

Usage with a downloaded source file:
    python fruugo_feed_builder.py --source products.csv --output fruugo.csv

Usage in an automated job:
    SUPPLIER_FEED_URL='private-url' python fruugo_feed_builder.py --output fruugo.csv

The private supplier URL is intentionally never stored in this file.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import tempfile
import urllib.request
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


OUTPUT_FIELDS = [
    "ProductId", "SkuId", "EAN", "ISBN", "Brand", "Category",
    "Imageurl1", "Imageurl2", "Imageurl3", "StockStatus",
    "StockQuantity", "PackageWeight", "Language", "Title", "Description",
    "AttributeColor", "AttributeSize", "Attribute1", "Attribute2",
    "Attribute3", "Currency", "NormalPriceWithoutVAT", "VATRate",
]

WOMENS_HANDBAG_CATEGORY = "Apparel & Accessories > Handbags, Wallets & Cases > Handbags > Womens"
FANNY_PACK_CATEGORY = "Luggage & Bags > Fanny Packs"
WOMENS_SUNGLASSES_CATEGORY = (
    "Apparel & Accessories > Clothing Accessories > Sunglasses > Womens"
)

SELECTED = {
    "CO-43482": {"product_id":"AP10483378","ean":"8059978766175","brand":"Coccinelle","category":WOMENS_HANDBAG_CATEGORY,"title":"Coccinelle Lepaki Black Leather Women's Handbag","description":"Coccinelle Lepaki women's handbag in black leather. It features dual handles, a zip closure, an exterior pocket, an interior pocket and dedicated phone compartments.","color":"Black","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/10483375.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10483376.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10483377.jpeg"]},
    "FU-41816": {"product_id":"AP9928056","ean":"8050597739496","brand":"Furla","category":WOMENS_HANDBAG_CATEGORY,"title":"Furla Ava L Black Leather Tote Bag","description":"Furla Ava L tote bag in black leather. It features adjustable shoulder straps, a spacious interior, a zip closure and side drawstrings.","color":"Black","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/9928053.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/9928054.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/9928055.jpeg"]},
    "BAG4747": {"product_id":"AP9688410","ean":"8059579795581","brand":"Dolce & Gabbana","category":FANNY_PACK_CATEGORY,"title":"Dolce & Gabbana Green Nylon Waist Bag","description":"Dolce & Gabbana men's waist bag in nylon and calf leather. It features an adjustable waist strap, zip closure, exterior pockets and a metal logo plaque.","color":"Green","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/9688447.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/9688448.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/9688449.jpeg"]},
    "VE15562124886281BT": {"product_id":"AP10754546","ean":"8054034884251","brand":"Versace","category":WOMENS_HANDBAG_CATEGORY,"title":"Versace Beige Fabric Women's Handbag","description":"Versace women's beige fabric handbag with a front detail and a removable shoulder strap.","color":"Beige","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/10754539.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10754541.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10754544.jpeg"]},
    "TO15670356836617BT": {"product_id":"AP11172829","ean":"0197865145455","brand":"Tory Burch","category":WOMENS_HANDBAG_CATEGORY,"title":"Tory Burch Brown Leather Women's Crossbody Bag","description":"Tory Burch women's brown leather crossbody bag with a front logo detail and shoulder strap.","color":"Brown","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/11172823.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/11172825.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/11172827.jpeg"]},
    "GLA1189": {"product_id":"AP3772165","ean":"8053672820966","brand":"Dolce & Gabbana","category":WOMENS_SUNGLASSES_CATEGORY,"title":"Dolce & Gabbana DG4326 Black Gold Polarized Sunglasses","description":"Dolce & Gabbana DG4326 women's butterfly sunglasses with a black acetate frame, gold sequin detailing and grey polarized lenses with UVA and UVB protection.","color":"Black","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/3772414.jpg","https://brandsgateway-img.s3.fr-par.scw.cloud/3772391.jpg","https://brandsgateway-img.s3.fr-par.scw.cloud/3772392.jpg"]},
    "GLA1190": {"product_id":"AP4088252","ean":"8059226565543","brand":"Dolce & Gabbana","category":WOMENS_SUNGLASSES_CATEGORY,"title":"Dolce & Gabbana DG2202 Pink Gold Sunglasses","description":"Dolce & Gabbana DG2202 women's sunglasses with a pink and gold metal frame, rose sequin detailing and bordeaux lenses with UVA and UVB protection.","color":"Pink","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/4088258.jpg","https://brandsgateway-img.s3.fr-par.scw.cloud/4088259.jpg","https://brandsgateway-img.s3.fr-par.scw.cloud/4088260.jpg"]},
    "JA8547396157705BT": {"product_id":"AP8338001","ean":"3700943188991","brand":"Jacquemus","category":WOMENS_SUNGLASSES_CATEGORY,"title":"Jacquemus Yellow Acetate Aviator Sunglasses","description":"Jacquemus women's aviator sunglasses with a yellow acetate frame and dark lenses. A protective case is included.","color":"Yellow","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/8337959.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/8337982.jpeg",""]},
    "JA8547396387081BT": {"product_id":"AP8338007","ean":"3700943157188","brand":"Jacquemus","category":WOMENS_SUNGLASSES_CATEGORY,"title":"Jacquemus Light Blue Acetate Square Sunglasses","description":"Jacquemus women's square sunglasses with a light blue acetate frame and dark lenses. A protective case is included.","color":"Light Blue","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/8337975.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/8337994.jpeg",""]},
    "DS-1067498": {"product_id":"AP10822866","ean":"197737245115","brand":"Dsquared²","category":WOMENS_SUNGLASSES_CATEGORY,"title":"Dsquared² Multicolor Acetate Cat Eye Sunglasses","description":"Dsquared² women's cat eye sunglasses with a multicolor acetate frame and gradient brown lenses offering UV400 protection.","color":"Multicolor","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/10822862.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10822863.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10822864.jpeg"]},
}

FORBIDDEN_DESCRIPTION = re.compile(r"https?://|www\.|[\w.+-]+@[\w.-]+|\b(?:shipping|delivery)\b", re.IGNORECASE)


def margin_for(wholesale: Decimal) -> Decimal:
    if wholesale < Decimal("200"):
        return Decimal("80")
    if wholesale < Decimal("300"):
        return Decimal("100")
    return Decimal("120")


def price_without_vat(wholesale: Decimal) -> Decimal:
    shipping = Decimal("25")
    commission_multiplier = Decimal("0.80")
    result = (wholesale + shipping + margin_for(wholesale)) / commission_multiplier
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def download_source(url: str) -> Path:
    handle = tempfile.NamedTemporaryFile(prefix="supplier_", suffix=".csv", delete=False)
    path = Path(handle.name)
    handle.close()
    request = urllib.request.Request(url, headers={"User-Agent": "AvenidaPrestigeFeed/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=180) as response, path.open("wb") as target:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                target.write(chunk)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path


def load_selected(source: Path) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"Product Sku", "Wholesale Price", "Quantity"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing supplier columns: {sorted(missing)}")
        for row in reader:
            sku = row.get("Product Sku", "")
            if sku in SELECTED:
                found[sku] = row
                if len(found) == len(SELECTED):
                    break
    return found


def make_row(sku: str, product: dict[str, str], source: dict[str, str] | None) -> dict[str, str]:
    images = [
        (source or {}).get("Main Picture") or product["images"][0],
        (source or {}).get("Picture 1") or product["images"][1],
        (source or {}).get("Picture 2") or product["images"][2],
    ]
    if source is None:
        stock_status, stock_quantity, wholesale = "NOTAVAILABLE", "0", Decimal("0")
    else:
        quantity = max(0, int(Decimal(source.get("Quantity") or "0")))
        stock_status = "INSTOCK" if quantity > 2 else "OUTOFSTOCK"
        stock_quantity = str(quantity if quantity > 2 else 0)
        wholesale = Decimal(source.get("Wholesale Price") or "0")

    normal_price = "" if wholesale <= 0 else str(price_without_vat(wholesale))
    description = re.sub(r"\s+", " ", product["description"]).strip()
    if FORBIDDEN_DESCRIPTION.search(description):
        raise ValueError(f"Forbidden content in description for {sku}")

    return {
        "ProductId": product["product_id"], "SkuId": product["product_id"],
        "EAN": (source or {}).get("Upc Ean") or product["ean"], "ISBN": "",
        "Brand": product["brand"], "Category": product["category"],
        "Imageurl1": images[0], "Imageurl2": images[1], "Imageurl3": images[2],
        "StockStatus": stock_status, "StockQuantity": stock_quantity,
        "PackageWeight": "", "Language": "en", "Title": product["title"],
        "Description": description, "AttributeColor": product["color"],
        "AttributeSize": "", "Attribute1": "", "Attribute2": "", "Attribute3": "",
        "Currency": "EUR", "NormalPriceWithoutVAT": normal_price, "VATRate": "23",
    }


def build(source: Path, output: Path) -> None:
    selected_rows = load_selected(source)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Fruugo requires UTF-8 without BOM/signature.
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        for sku, product in SELECTED.items():
            writer.writerow(make_row(sku, product, selected_rows.get(sku)))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="Downloaded BrandsGateway CSV")
    parser.add_argument("--output", type=Path, default=Path("fruugo_feed.csv"))
    args = parser.parse_args()

    temporary_source: Path | None = None
    source = args.source
    if source is None:
        url = os.environ.get("SUPPLIER_FEED_URL", "").strip()
        if not url:
            parser.error("Provide --source or set SUPPLIER_FEED_URL")
        temporary_source = download_source(url)
        source = temporary_source

    try:
        build(source, args.output)
    finally:
        if temporary_source is not None:
            temporary_source.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
