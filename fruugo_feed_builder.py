#!/usr/bin/env python3
"""Build Avenida Prestige's 500-SKU Fruugo feed.

400 BrandsGateway products are refreshed from SUPPLIER_FEED_URL on every run.
100 watch rows are loaded from the validated Timeshop snapshot in data/watch_snapshot.b64.
"""

from __future__ import annotations

import argparse
import base64
import csv
import html
import io
import json
import os
import re
import tempfile
import urllib.request
import zlib
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SELECTION_FILE = ROOT / "data" / "bg_selection.json"
WATCH_SNAPSHOT_FILE = ROOT / "data" / "watch_snapshot.b64"

OUTPUT_FIELDS = [
    "ProductId", "SkuId", "EAN", "ISBN", "Brand", "Category",
    "Imageurl1", "Imageurl2", "Imageurl3", "StockStatus",
    "StockQuantity", "PackageWeight", "Language", "Title", "Description",
    "AttributeColor", "AttributeSize", "Attribute1", "Attribute2",
    "Attribute3", "Currency", "NormalPriceWithoutVAT", "VATRate",
]

BAG_CATEGORY = "Apparel & Accessories > Handbags, Wallets & Cases > Handbags > Womens"
SUNGLASS_CATEGORY = "Apparel & Accessories > Clothing Accessories > Sunglasses > Womens"
FORBIDDEN_DESCRIPTION = re.compile(
    r"https?://|www\.|[\w.+-]+@[\w.-]+|\b(?:shipping|delivery)\b",
    re.IGNORECASE,
)


def load_selection() -> tuple[list[str], list[str]]:
    data = json.loads(SELECTION_FILE.read_text(encoding="utf-8"))
    bags = [str(x) for x in data["bags"]]
    sunglasses = [str(x) for x in data["sunglasses"]]
    if len(bags) != 350 or len(sunglasses) != 50:
        raise ValueError(f"Expected 350 bags + 50 sunglasses, got {len(bags)} + {len(sunglasses)}")
    return bags, sunglasses


def decimal_value(value: str | None) -> Decimal:
    try:
        return Decimal(
            str(value or "0")
            .replace("EUR", "")
            .replace("€", "")
            .replace(",", ".")
            .strip()
        )
    except Exception:
        return Decimal("0")


def clean(value: str | None) -> str:
    value = html.unescape(value or "")
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"https?://\S+|www\.\S+", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"[\w.+-]+@[\w.-]+\.\w+", " ", value)
    value = re.sub(
        r"\b(?:shipping|delivery)\b[^.;]*[.;]?",
        " ",
        value,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s+", " ", value).strip(" •|-")


def margin_for(wholesale: Decimal) -> Decimal:
    if wholesale < Decimal("200"):
        return Decimal("80")
    if wholesale < Decimal("300"):
        return Decimal("100")
    return Decimal("120")


def price_without_vat(wholesale: Decimal) -> Decimal:
    result = (wholesale + Decimal("25") + margin_for(wholesale)) / Decimal("0.80")
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def download_source(url: str) -> Path:
    handle = tempfile.NamedTemporaryFile(prefix="supplier_", suffix=".csv", delete=False)
    path = Path(handle.name)
    handle.close()
    request = urllib.request.Request(url, headers={"User-Agent": "AvenidaPrestigeFeed/2.0"})
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


def load_bg(source: Path, wanted: set[str]) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    with source.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"Product Id", "Wholesale Price", "Quantity", "Upc Ean", "Main Picture"}
        missing = required.difference(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing supplier columns: {sorted(missing)}")
        for row in reader:
            pid = (row.get("Product Id") or "").strip()
            if pid in wanted:
                found[pid] = row
                if len(found) == len(wanted):
                    break
    return found


def title_for(row: dict[str, str]) -> str:
    brand = clean(row.get("Brand"))
    name = clean(row.get("Name"))
    return name if name.lower().startswith(brand.lower()) else clean(f"{brand} {name}")


def description_for(row: dict[str, str]) -> str:
    brand = clean(row.get("Brand"))
    name = clean(row.get("Name"))
    base = clean(row.get("Description Plain") or row.get("Description") or "")
    parts = [f"{brand} {name}.", base]
    for key, label in [
        ("Material", "Material"),
        ("Color", "Colour"),
        ("Dimensions / Measurements", "Dimensions"),
        ("Origin", "Country of origin"),
        ("MPN", "Manufacturer part number"),
        ("Product Code", "Product code"),
    ]:
        value = clean(row.get(key))
        if value:
            parts.append(f"{label}: {value}.")
    parts.append("Condition: new with tags.")
    result = clean(" ".join(parts))[:1800]
    if FORBIDDEN_DESCRIPTION.search(result):
        raise ValueError(f"Forbidden content in description for {row.get('Product Id')}")
    return result


def make_bg_row(pid: str, source: dict[str, str] | None, sunglasses: bool) -> dict[str, str]:
    product_id = f"AP{pid}"
    category = SUNGLASS_CATEGORY if sunglasses else BAG_CATEGORY
    if not sunglasses:
        bag_text = f"{source.get('Name', '') if source else ''} {source.get('Subcategory', '') if source else ''}".lower()
        if any(term in bag_text for term in ("belt bag", "fanny", "waist bag")):
            category = "Luggage & Bags > Fanny Packs"

    if source is None:
        row = {field: "" for field in OUTPUT_FIELDS}
        row.update(
            {
                "ProductId": product_id,
                "SkuId": product_id,
                "Category": category,
                "StockStatus": "NOTAVAILABLE",
                "StockQuantity": "0",
                "Language": "en",
                "Attribute1": "1" if sunglasses else "",
                "Currency": "EUR",
                "VATRate": "23",
            }
        )
        return row

    quantity = max(0, int(decimal_value(source.get("Quantity"))))
    wholesale = decimal_value(source.get("Wholesale Price"))
    mpn = clean(source.get("MPN") or source.get("Product Code"))
    model = clean(source.get("Product Code") or source.get("MPN"))

    return {
        "ProductId": product_id,
        "SkuId": product_id,
        "EAN": clean(source.get("Upc Ean")),
        "ISBN": "",
        "Brand": clean(source.get("Brand")),
        "Category": category,
        "Imageurl1": source.get("Main Picture") or "",
        "Imageurl2": source.get("Picture 1") or "",
        "Imageurl3": source.get("Picture 2") or "",
        "StockStatus": "INSTOCK" if quantity > 2 else "OUTOFSTOCK",
        "StockQuantity": str(quantity if quantity > 2 else 0),
        "PackageWeight": clean(source.get("Weight")),
        "Language": "en",
        "Title": title_for(source),
        "Description": description_for(source),
        "AttributeColor": clean(source.get("Color")),
        "AttributeSize": clean(source.get("Size")),
        "Attribute1": "1" if sunglasses else "",
        "Attribute2": mpn,
        "Attribute3": model,
        "Currency": "EUR",
        "NormalPriceWithoutVAT": str(price_without_vat(wholesale)) if wholesale > 0 else "",
        "VATRate": "23",
    }


def load_watch_snapshot() -> list[dict[str, str]]:
    encoded = WATCH_SNAPSHOT_FILE.read_text(encoding="ascii").strip()
    raw = zlib.decompress(base64.b64decode(encoded)).decode("utf-8")
    rows = [
        {field: row.get(field, "") for field in OUTPUT_FIELDS}
        for row in csv.DictReader(io.StringIO(raw))
    ]
    if len(rows) != 100:
        raise ValueError(f"Expected 100 watch rows, got {len(rows)}")
    return rows


def build(source: Path, output: Path) -> None:
    bag_ids, sunglass_ids = load_selection()
    live = load_bg(source, set(bag_ids) | set(sunglass_ids))

    rows = [make_bg_row(pid, live.get(pid), False) for pid in bag_ids]
    rows.extend(make_bg_row(pid, live.get(pid), True) for pid in sunglass_ids)
    rows.extend(load_watch_snapshot())

    if len(rows) != 500:
        raise RuntimeError(f"Expected 500 rows, got {len(rows)}")

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=OUTPUT_FIELDS, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="Downloaded BrandsGateway CSV")
    parser.add_argument("--output", type=Path, default=Path("docs/fruugo.csv"))
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
