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
    "CO-43482": {"product_id":"AP10483378","ean":"8059978766175","brand":"Coccinelle","category":WOMENS_HANDBAG_CATEGORY,"title":"Coccinelle Lepaki Black Leather Women's Handbag","description":"Coccinelle Lepaki women's handbag in black leather, designed with a refined structured silhouette for everyday use. Crafted from 100% leather, the bag features two shoulder handles, a secure zip closure, an exterior pocket and an interior pocket with dedicated phone compartments to keep essentials organised. The understated black finish and signature Coccinelle logo give the design a polished, timeless character that works easily with both casual and more formal outfits. Dimensions: approximately 32 x 20 x 10 cm. Colour: black. Material: 100% leather. Country of origin: Italy. MPN: E1U4A120101_NE001. Condition: new with tags.","color":"Black","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/10483375.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10483376.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10483377.jpeg"]},
    "FU-41816": {"product_id":"AP9928056","ean":"8050597739496","brand":"Furla","category":WOMENS_HANDBAG_CATEGORY,"title":"Furla Ava L Black Leather Tote Bag","description":"Furla Ava L women's tote bag in black leather, combining a clean contemporary silhouette with practical everyday capacity. The spacious interior is secured with a zip closure, while adjustable shoulder straps allow a comfortable personalised carry. Side drawstrings add shape and character to the design, and the discreet Furla logo completes the elegant black finish. Dimensions: approximately 36 x 29 x 14 cm. Colour: black. Material: 100% leather. Country of origin: China. MPN: WB02059BX4329_NE3924S. Condition: new with tags.","color":"Black","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/9928053.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/9928054.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/9928055.jpeg"]},
    "BAG4747": {"product_id":"AP9688410","ean":"8059579795581","brand":"Dolce & Gabbana","category":FANNY_PACK_CATEGORY,"title":"Dolce & Gabbana Green Nylon Waist Bag","description":"Dolce & Gabbana men's waist bag in green nylon with calf-leather details, created for practical hands-free carrying with a luxury finish. The bag features an adjustable waist strap, zip closure, exterior pockets and engraved metal hardware with a front logo plaque. Its compact multi-compartment construction keeps everyday essentials organised while remaining easy to wear across the waist or body. Measurements: approximately 24 x 16 x 5 cm. Strap: approximately 115 x 4 cm. Outer composition: 15% nylon, 80% polyamide and 5% calf leather. Interior: 80% polyamide and 20% calf leather. Colour: green. Made in Italy. Condition: new with tags.","color":"Green","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/9688447.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/9688448.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/9688449.jpeg"]},
    "VE15562124886281BT": {"product_id":"AP10754546","ean":"8054034884251","brand":"Versace","category":WOMENS_HANDBAG_CATEGORY,"title":"Versace Beige Fabric Women's Handbag","description":"Versace women's handbag in beige fabric with a refined structured look and signature fashion-house detailing. The design features a decorative front detail and a removable shoulder strap, allowing the bag to be styled in different ways depending on the occasion. The neutral beige colour makes it easy to coordinate with both light and darker wardrobes, while the compact luxury design gives it a polished everyday appeal. Colour: beige. Main material: fabric. MPN: 10126461A133041KD4V. Product code: F86757. Condition: new with tags.","color":"Beige","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/10754539.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10754541.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10754544.jpeg"]},
    "TO15670356836617BT": {"product_id":"AP11172829","ean":"0197865145455","brand":"Tory Burch","category":WOMENS_HANDBAG_CATEGORY,"title":"Tory Burch Brown Leather Women's Crossbody Bag","description":"Tory Burch women's crossbody bag crafted in brown leather with a clean, versatile silhouette designed for everyday wear. The rich brown leather is finished with the brand's front logo detail, while the shoulder strap allows comfortable hands-free carrying. Its understated design makes it easy to pair with casual, business or travel looks while retaining the distinctive Tory Burch aesthetic. Colour: brown. Material: leather. EAN: 0197865145455. Supplier SKU: TO15670356836617BT. Condition: new with tags.","color":"Brown","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/11172823.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/11172825.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/11172827.jpeg"]},
    "GLA1189": {"product_id":"AP3772165","ean":"8053672820966","brand":"Dolce & Gabbana","category":WOMENS_SUNGLASSES_CATEGORY,"title":"Dolce & Gabbana DG4326 Black Gold Polarized Sunglasses","description":"Dolce & Gabbana DG4326 women's butterfly sunglasses featuring a black acetate frame with gold sequin detailing for a distinctive statement look. The grey lenses are polarised to help reduce glare and provide 100% UVA and UVB protection, making the model suitable for bright outdoor conditions. The combination of the sculpted butterfly silhouette, black frame and gold embellishment creates a glamorous finish while retaining practical sun protection. Model: DG4326. Frame material: 100% acetate. Frame colour: black and gold. Lens colour: grey. Lens type: polarised. UV protection: 100% UVA/UVB protection. Condition: new with tags.","color":"Black","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/3772414.jpg","https://brandsgateway-img.s3.fr-par.scw.cloud/3772391.jpg","https://brandsgateway-img.s3.fr-par.scw.cloud/3772392.jpg"]},
    "GLA1190": {"product_id":"AP4088252","ean":"8059226565543","brand":"Dolce & Gabbana","category":WOMENS_SUNGLASSES_CATEGORY,"title":"Dolce & Gabbana DG2202 Pink Gold Sunglasses","description":"Dolce & Gabbana DG2202 women's sunglasses in a pink and gold metal frame with rose sequin embroidery, combining decorative detailing with a refined statement silhouette. The bordeaux lenses provide 100% UVA and UVB protection for everyday sun use, while the metal construction gives the frame a polished, elegant finish. The colour combination and embroidered detailing make this special-edition design particularly distinctive. Model: DG2202. Frame material: 100% metal. Frame colours: pink and gold. Lens colour: bordeaux. UV protection: 100% UVA/UVB protection. Made in Italy. Condition: new with tags.","color":"Pink","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/4088258.jpg","https://brandsgateway-img.s3.fr-par.scw.cloud/4088259.jpg","https://brandsgateway-img.s3.fr-par.scw.cloud/4088260.jpg"]},
    "JA8547396157705BT": {"product_id":"AP8338001","ean":"3700943188991","brand":"Jacquemus","category":WOMENS_SUNGLASSES_CATEGORY,"title":"Jacquemus Yellow Acetate Aviator Sunglasses","description":"Jacquemus women's aviator-style sunglasses in yellow acetate, designed with a bold colour and clean contemporary lines. The frame is made from acetate and fitted with dark lenses, while the Jacquemus logo adds a discreet branded finish. A protective case is included for storage. Measurements: total width approximately 14.6 cm; lens diameter 4.6 cm; bridge 1.0 cm; temple length 14.7 cm. Frame material: acetate. Colour: yellow. Lens colour: dark. Style: aviator/pilot. MPN: 221AC0295040250. Product code: F77997. Condition: new with tags.","color":"Yellow","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/8337959.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/8337982.jpeg",""]},
    "JA8547396387081BT": {"product_id":"AP8338007","ean":"3700943157188","brand":"Jacquemus","category":WOMENS_SUNGLASSES_CATEGORY,"title":"Jacquemus Light Blue Acetate Square Sunglasses","description":"Jacquemus women's square sunglasses in light blue acetate with silver-tone accents, offering a modern geometric silhouette and a distinctive pastel finish. The design combines an acetate front with steel components and dark lenses, while a protective case is included for storage. Measurements: total width approximately 14.5 cm; lens diameter 5.1 cm; bridge 1.1 cm; temple length 15.5 cm. Frame material: acetate with steel components. Primary colour: light blue; secondary colour: silver. Lens colour: dark. MPN: 226AC4315041330. Product code: F78001. Condition: new with tags.","color":"Light Blue","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/8337975.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/8337994.jpeg",""]},
    "DS-1067498": {"product_id":"AP10822866","ean":"197737245115","brand":"Dsquared²","category":WOMENS_SUNGLASSES_CATEGORY,"title":"Dsquared² Multicolor Acetate Cat Eye Sunglasses","description":"Dsquared² women's cat-eye sunglasses with a multicolour acetate full-rim frame and gradient brown lenses. The sculpted cat-eye shape gives the model a distinctive fashion-led profile, while category 3 lenses are designed for strong sunlight conditions. The lenses provide UV400 / 100% UV protection. A protective case is included. Measurements: lens width 52 mm; lens height 46 mm; bridge width 22 mm; frame width 145 mm; temple length 135 mm. Frame material: acetate. Lens material: plastic. Lens colour: brown. Lens effect: gradient. Filter category: 3. Spring hinge: no. Model: D2 0207/S 086HA. Condition: new with tags.","color":"Multicolor","images":["https://brandsgateway-img.s3.fr-par.scw.cloud/10822862.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10822863.jpeg","https://brandsgateway-img.s3.fr-par.scw.cloud/10822864.jpeg"]},
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
        "AttributeSize": "",
        # Fruugo Attribute1 is mapped in Catalogue Settings to "CE Mark".
        # Sunglasses are PPE for protection against sunlight under Regulation (EU) 2016/425
        # and therefore require CE marking. Fruugo expects "1" when the CE mark is present.
        "Attribute1": "1" if product["category"] == WOMENS_SUNGLASSES_CATEGORY else "",
        "Attribute2": "", "Attribute3": "",
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
