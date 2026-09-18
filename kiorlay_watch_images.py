from io import BytesIO
from pathlib import Path

import requests
from PIL import Image

PRODUCTS = {
    "CVZ0054RBLS": [
        "https://b2b.timeshop24.com/media/catalog/product/c/v/cvz0054rbls_1.jpg",
        "https://b2b.timeshop24.com/media/catalog/product/c/a/carl_von_zeyten_box_15_1.jpg",
    ],
    "8590-3": [
        "https://b2b.timeshop24.com/media/catalog/product/z/e/zeppelin-8590-3-herrenuhr-friedrichshafen-automatik-002.jpg",
        "https://b2b.timeshop24.com/media/catalog/product/z/e/zeppelin-8590-3-herrenuhr-friedrichshafen-automatik-mood-004.jpg",
        "https://b2b.timeshop24.com/media/catalog/product/z/e/zeppelin-8590-3-herrenuhr-friedrichshafen-automatik-mood-002.jpg",
    ],
    "SM30207.05": [
        "https://b2b.timeshop24.com/media/catalog/product/s/m/sm30207_05_front.jpg",
        "https://b2b.timeshop24.com/media/catalog/product/s/m/sm30207_05.jpg",
        "https://b2b.timeshop24.com/media/catalog/product/s/w/swiss-military-chrono-ag-box_214_40.jpg",
    ],
    "VEAFA0124": [
        "https://b2b.timeshop24.com/media/catalog/product/v/e/veafa0124.jpg",
        "https://b2b.timeshop24.com/media/catalog/product/v/e/versace_box_256.jpg",
    ],
    "242029": [
        "https://b2b.timeshop24.com/media/catalog/product/v/i/victorinox_242029_front_1.jpg",
        "https://b2b.timeshop24.com/media/catalog/product/v/i/victorinox_242029_front_2.jpg",
        "https://b2b.timeshop24.com/media/catalog/product/v/i/victorinox_242029_side_1.jpg",
    ],
}

CANVAS = 1200
INNER = 0.78

def resize_for_kiorlay(content: bytes) -> Image.Image:
    img = Image.open(BytesIO(content)).convert("RGB")
    gray = img.convert("L")
    bbox = gray.point(lambda p: 255 if p < 245 else 0).getbbox()
    if bbox:
        img = img.crop(bbox)

    max_size = int(CANVAS * INNER)
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", (CANVAS, CANVAS), "white")
    x = (CANVAS - img.width) // 2
    y = (CANVAS - img.height) // 2
    canvas.paste(img, (x, y))
    return canvas

def main():
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0"})
    for ref, urls in PRODUCTS.items():
        for index, url in enumerate(urls, start=1):
            response = session.get(url, timeout=60)
            response.raise_for_status()
            image = resize_for_kiorlay(response.content)
            out = Path(f"{ref}_{index}.jpg")
            image.save(out, "JPEG", quality=92, optimize=True)
            print(f"saved {out} from {url}")

if __name__ == "__main__":
    main()
