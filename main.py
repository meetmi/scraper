"""
Multi-site car scraper — main entrypoint
========================================
Supports: webuycars.co.za, cars.co.za
Add new sites by implementing a SiteAdapter subclass in adapters/
and registering it in adapters/__init__.py.

Firestore target doc shape (scrape_config/car_scrape_targets):
{
  "targets": [
    {
      "label":    "wbc-toyota-fortuner",
      "site":     "webuycars",
      "url":      "https://www.webuycars.co.za/buy-a-car?...",
      "maxPages": 5,
      "enabled":  true
    },
    {
      "label":    "carsza-toyota-fortuner",
      "site":     "carsza",
      "url":      "https://www.cars.co.za/usedcars/?make_model_variant=Toyota[Fortuner]&sort=sort_rank&price_type=listing_price",
      "maxPages": 5,
      "enabled":  true
    }
  ]
}
"""

import os
import re
import uuid
import logging
from datetime import datetime, UTC

import firebase_admin
from firebase_admin import credentials, firestore
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions

from adapters import get_adapter

# ── Working directory ─────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

_run_ts  = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = os.path.join(LOG_DIR, f"run_{_run_ts}.log")

_fmt             = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_fmt)
_file_handler    = logging.FileHandler(LOG_FILE, encoding="utf-8")
_file_handler.setFormatter(_fmt)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(_console_handler)
logger.addHandler(_file_handler)

# ── Firebase ──────────────────────────────────────────────────────────────────
firebase_admin.initialize_app(credentials.Certificate("serviceAccountKey.json"))
db = firestore.client()


# ═══════════════════════════════════════════════════════════════════════════════
# Shared helpers
# ═══════════════════════════════════════════════════════════════════════════════

MAKES = [
    "Toyota", "BMW", "Ford", "Mercedes", "Mercedes-Benz", "Audi",
    "VW", "Volkswagen", "Nissan", "Honda", "Hyundai", "Kia", "Mazda",
    "Isuzu", "Chevrolet", "Renault", "Suzuki", "Jeep", "Volvo",
    "Land Rover", "Lexus", "Porsche", "Mini", "Peugeot", "Mitsubishi",
    "Subaru", "Fiat", "Jaguar", "Haval", "Chery", "Mahindra", "Opel",
    "Alfa Romeo",
]


def extract_year(title: str = "") -> int | None:
    m = re.search(r"\b(19|20)\d{2}\b", title)
    return int(m.group()) if m else None


def extract_make(title: str = "") -> str | None:
    for make in MAKES:
        if make.lower() in title.lower():
            return make
    return None


def extract_model(title: str = "") -> str | None:
    if not title:
        return None
    parts = title.strip().split()
    if re.match(r"^(19|20)\d{2}$", parts[0]):
        parts.pop(0)
    make = extract_make(title)
    if make:
        for word in make.split():
            if parts and parts[0].lower() == word.lower():
                parts.pop(0)
    return parts[0] if parts else None


def parse_price(p) -> int | None:
    if not p:
        return None
    if isinstance(p, (int, float)):
        return int(p)
    cleaned = re.sub(r"[^\d]", "", str(p))
    return int(cleaned) if cleaned else None


def parse_mileage(m) -> int | None:
    if not m:
        return None
    cleaned = re.sub(r"[^\d]", "", str(m))
    return int(cleaned) if cleaned else None


def parse_engine_size(e) -> int | None:
    if not e:
        return None
    cleaned = re.sub(r"[^\d]", "", str(e))
    return int(cleaned) if cleaned else None


def today_sast() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")


def encode_label(label: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", label)


# ═══════════════════════════════════════════════════════════════════════════════
# Canonical car schema
# ═══════════════════════════════════════════════════════════════════════════════

def build_canonical_car(item: dict, run_id: str) -> dict:
    """Convert a raw scraped dict (any site) into the canonical Firestore schema."""
    title       = item.get("title", "")
    mileage     = item.get("mileage")
    color       = item.get("color")
    engine_size = item.get("engineSize")
    images      = item.get("imageUrls", [])
    branch      = item.get("branch")
    nav_url     = item.get("navigationUrl")
    stock_id    = item.get("stock_id")
    scraped_date = datetime.now(UTC).strftime("%d-%m-%y")

    return {
        "id":          stock_id or "",
        "externalId":  stock_id or None,

        "title":       title,
        "description": item.get("description"),

        "make":    item.get("make") or extract_make(title),
        "model":   item.get("model") or extract_model(title),
        "variant": item.get("variant"),

        "year":     item.get("year") or extract_year(title) or None,
        "price":    parse_price(item.get("price")),
        "currency": "ZAR",

        "bodyType":     item.get("bodyType"),
        "fuelType":     item.get("fuelType"),
        "transmission": item.get("transmission"),

        "drivetrain":  None,
        "engineSize":  parse_engine_size(engine_size),
        "enginePower": None,
        "cylinders":   None,
        "doors":       item.get("doors"),
        "seats":       None,

        "mileage":     parse_mileage(mileage),
        "mileageUnit": "KM" if mileage and "km" in str(mileage).lower() else None,

        "condition":       item.get("condition", "Used"),
        "serviceHistory":  None,
        "accidentHistory": None,
        "ownersCount":     None,

        "color":         color,
        "interiorColor": None,
        "exteriorColor": color,
        "paintType":     None,
        "upholstery":    None,

        "features":        item.get("features", []),
        "safetyFeatures":  [],
        "comfortFeatures": [],
        "techFeatures":    [],

        "fuelConsumption": None,
        "fuelEfficiency":  None,
        "range":           None,
        "emissionClass":   None,

        "location":    branch or item.get("location") or "South Africa",
        "city":        item.get("city"),
        "province":    item.get("province"),
        "country":     "South Africa",
        "coordinates": None,

        "dealershipName": item.get("dealerName") or branch,
        "sellerType":     item.get("sellerType", "Dealer"),

        "priceType":           "Fixed",
        "priceNegotiable":     None,
        "priceHistory":        None,
        "marketValueEstimate": None,

        "images":     images,
        "imageCount": len(images),

        "videoUrl":   None,
        "has360View": False,

        "sourceUrl":     nav_url,
        "navigationUrl": nav_url,

        "listingSource": item.get("listingSource", "unknown"),
        "targetLabel":   item.get("targetLabel"),

        "runId": run_id,

        "scrapedAt":   firestore.SERVER_TIMESTAMP,
        "scrapedDate": scraped_date,
        "createdAt":   datetime.now(UTC).isoformat(),
        "updatedAt":   None,
        "listedAt":    None,

        "popularityScore": None,
        "clickCount":      0,
        "viewCount":       0,
        "conversionScore": None,
        "boostScore":      None,
        "freshnessScore":  None,

        "dealScore":  None,
        "aiSummary":  None,
        "aiTags":     [],
        "riskFlags":  [],

        "priceInsight":       None,
        "recommendedUseCase": None,

        "category":    "car",
        "subCategory": None,
        "vehicleType": "car",
        "segment":     None,
        "usageType":   None,

        "raw": item,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# Firestore helpers
# ═══════════════════════════════════════════════════════════════════════════════

def get_targets() -> list[dict]:
    doc = db.collection("scrape_config").document("car_scrape_targets").get()
    if not doc.exists:
        logger.error("❌ scrape_config/car_scrape_targets not found in Firestore.")
        return []
    targets = doc.to_dict().get("targets", [])
    enabled = [t for t in targets if t.get("enabled", True)]
    logger.info(f"📋 Loaded {len(enabled)} enabled target(s) from Firestore.")
    return enabled


def get_start_page(label: str) -> int | None:
    ref = db.collection("scrape_progress").document(encode_label(label))
    doc = ref.get()
    if not doc.exists:
        return 1
    data = doc.to_dict()
    if data.get("exhausted"):
        logger.info(f"⏭️  '{label}' already exhausted — skipping.")
        return None
    return data.get("lastPageScraped", 0) + 1


def save_progress(label: str, last_page_scraped: int, exhausted: bool):
    db.collection("scrape_progress").document(encode_label(label)).set({
        "label":           label,
        "lastPageScraped": last_page_scraped,
        "exhausted":       exhausted,
        "date":            today_sast(),
        "updatedAt":       firestore.SERVER_TIMESTAMP,
    })
    logger.info(
        f"📌 Progress: '{label}' | lastPage={last_page_scraped} | exhausted={exhausted}"
    )


def save_cars_to_firestore(cars: list[dict], run_id: str):
    if not cars:
        return
    batch = db.batch()
    count = saved = 0
    for item in cars:
        doc_ref = db.collection("cars").document()
        car     = build_canonical_car(item, run_id)
        if not car["id"]:
            car["id"] = doc_ref.id
        batch.set(doc_ref, car)
        count += 1
        saved += 1
        if count == 500:
            batch.commit()
            batch = db.batch()
            count = 0
    if count > 0:
        batch.commit()
    logger.info(f"✅ Saved {saved} car(s) to Firestore.")


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    run_start = datetime.now()
    run_id    = str(uuid.uuid4())

    logger.info("=" * 70)
    logger.info("🚦 RUN STARTED")
    logger.info(f"   Run ID   : {run_id}")
    logger.info(f"   Start    : {run_start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"   Log file : {LOG_FILE}")
    logger.info("=" * 70)

    targets = get_targets()
    if not targets:
        logger.error("❌ No enabled targets. Exiting.")
        return

    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
    driver = webdriver.Chrome(options=options)

    total_cars_saved  = 0
    targets_completed = 0
    targets_skipped   = 0
    targets_failed    = 0

    try:
        for target in targets:
            label     = target.get("label", "unknown")
            base_url  = target.get("url", "")
            site      = target.get("site", "carsza")
            max_pages = int(target.get("maxPages", 3))

            logger.info("-" * 70)
            logger.info(f"🎯 TARGET: '{label}' | site={site} | maxPages={max_pages}")

            if not base_url:
                logger.warning(f"⚠️ No URL for target '{label}' — skipping.")
                targets_skipped += 1
                continue

            adapter = get_adapter(site, driver)
            if not adapter:
                targets_failed += 1
                continue

            start_page = get_start_page(label)
            if start_page is None:
                logger.info(f"⏭️  Skipping '{label}' (already exhausted today).")
                targets_skipped += 1
                continue

            end_page = start_page + max_pages - 1
            logger.info(f"   Pages    : {start_page}–{end_page}")

            last_page_scraped = start_page - 1
            exhausted         = False
            cars_batch        = []

            for page_number in range(start_page, end_page + 1):
                cars_on_page, has_results = adapter.scrape_listing_page(base_url, page_number)

                if not has_results:
                    exhausted = True
                    logger.info(f"🏁 '{label}' exhausted at page {page_number}")
                    break

                for car in cars_on_page:
                    try:
                        enriched = adapter.scrape_detail_page(car)
                        enriched["targetLabel"] = label
                        cars_batch.append(enriched)
                        logger.info(
                            f"   ✅ {enriched.get('stock_id', '?')} | page {page_number}"
                        )
                    except Exception as e:
                        logger.warning(
                            f"   ⚠️ Detail failed for {car.get('navigationUrl')}: {e}"
                        )

                last_page_scraped = page_number

            save_cars_to_firestore(cars_batch, run_id)
            save_progress(label, last_page_scraped, exhausted)

            total_cars_saved  += len(cars_batch)
            targets_completed += 1
            logger.info(
                f"   ✔ Done | cars={len(cars_batch)} | "
                f"lastPage={last_page_scraped} | exhausted={exhausted}"
            )

    finally:
        driver.quit()

        run_end     = datetime.now()
        elapsed_str = str(run_end - run_start).split(".")[0]

        logger.info("=" * 70)
        logger.info("🏁 RUN FINISHED")
        logger.info(f"   Run ID     : {run_id}")
        logger.info(f"   Start      : {run_start.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   End        : {run_end.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"   Duration   : {elapsed_str}")
        logger.info(f"   Cars saved : {total_cars_saved}")
        logger.info(f"   Targets ✔  : {targets_completed}")
        logger.info(f"   Targets ⏭  : {targets_skipped}")
        logger.info(f"   Targets ✗  : {targets_failed}")
        logger.info(f"   Log file   : {LOG_FILE}")
        logger.info("=" * 70)


if __name__ == "__main__":
    main()
