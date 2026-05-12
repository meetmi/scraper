import asyncio
import re
import time
import logging
import uuid
from datetime import datetime, UTC

import firebase_admin
from firebase_admin import credentials, firestore
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ── Logging ───────────────────────────────────────────────────────────────────
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(handler)

# ── Firebase init ─────────────────────────────────────────────────────────────
# 👇 Point this to your Firebase service account JSON key file
SERVICE_ACCOUNT_PATH = "serviceAccountKey.json"

firebase_admin.initialize_app(credentials.Certificate(SERVICE_ACCOUNT_PATH))
db = firestore.client()

# ── Helpers (unchanged) ───────────────────────────────────────────────────────
def slugify(text):
    text = text.replace(" ", "-").replace("/", "-")
    return re.sub(r'[^a-zA-Z0-9\-]', '', text)


def extract_year(title=""):
    match = re.search(r'\b(19|20)\d{2}\b', title)
    return int(match.group()) if match else None


MAKES = [
    "Toyota", "BMW", "Ford", "Mercedes", "Mercedes-Benz", "Audi",
    "VW", "Volkswagen", "Nissan", "Honda", "Hyundai", "Kia", "Mazda",
    "Isuzu", "Chevrolet", "Renault", "Suzuki", "Jeep", "Volvo",
    "Land Rover", "Lexus", "Porsche", "Mini", "Peugeot", "Mitsubishi",
    "Subaru", "Fiat", "Jaguar", "Haval", "Chery", "Mahindra", "Opel",
    "Alfa Romeo",
]


def extract_make(title=""):
    for make in MAKES:
        if make.lower() in title.lower():
            return make
    return None


def extract_model(title=""):
    if not title:
        return None
    parts = title.strip().split()
    if re.match(r'^(19|20)\d{2}$', parts[0]):
        parts.pop(0)
    make = extract_make(title)
    if make:
        for word in make.split():
            if parts and parts[0].lower() == word.lower():
                parts.pop(0)
    return parts[0] if parts else None


def parse_price(p):
    if not p:
        return None
    if isinstance(p, (int, float)):
        return int(p)
    cleaned = re.sub(r'[^\d]', '', str(p))
    return int(cleaned) if cleaned else None


def parse_mileage(m):
    if not m:
        return None
    cleaned = re.sub(r'[^\d]', '', str(m))
    return int(cleaned) if cleaned else None


def parse_engine_size(e):
    if not e:
        return None
    cleaned = re.sub(r'[^\d]', '', str(e))
    return int(cleaned) if cleaned else None


def today_sast():
    return datetime.now(UTC).strftime("%Y-%m-%d")


def encode_label(label: str) -> str:
    """Mirrors encodeLabel from cloudRunController.js"""
    return re.sub(r'[^a-zA-Z0-9_-]', '_', label)


# ── Firebase: read targets ────────────────────────────────────────────────────
def get_targets():
    doc = db.collection("scrape_config").document("car_scrape_targets").get()
    if not doc.exists:
        logger.error("❌ No scrape_config/car_scrape_targets doc found in Firestore.")
        return []
    targets = doc.to_dict().get("targets", [])
    enabled = [t for t in targets if t.get("enabled", True)]
    logger.info(f"📋 Loaded {len(enabled)} enabled targets from Firestore.")
    return enabled


# ── Firebase: read progress ───────────────────────────────────────────────────
def get_start_page(label: str) -> int:
    """Check scrape_progress to resume from where we left off."""
    ref = db.collection("scrape_progress").document(encode_label(label))
    doc = ref.get()
    if not doc.exists:
        return 1
    data = doc.to_dict()
    if data.get("exhausted"):
        logger.info(f"⏭️  '{label}' already exhausted — skipping.")
        return None  # signal to skip
    last = data.get("lastPageScraped", 0)
    return last + 1


# ── Firebase: save progress ───────────────────────────────────────────────────
def save_progress(label: str, last_page_scraped: int, exhausted: bool):
    ref = db.collection("scrape_progress").document(encode_label(label))
    ref.set({
        "label": label,
        "lastPageScraped": last_page_scraped,
        "exhausted": exhausted,
        "date": today_sast(),
        "updatedAt": firestore.SERVER_TIMESTAMP,
    })
    logger.info(f"📌 Progress saved: '{label}' | lastPage={last_page_scraped} | exhausted={exhausted}")


# ── Firebase: save cars in batches ────────────────────────────────────────────
def save_cars_to_firestore(cars: list, run_id: str):
    if not cars:
        return
    batch = db.batch()
    count = 0
    saved = 0
    scraped_date = datetime.now(UTC).strftime("%d-%m-%y")

    for item in cars:
        doc_ref = db.collection("cars").document()

        title        = item.get("title")
        mileage      = item.get("mileage")
        transmission = item.get("transmission")
        fuel_type    = item.get("fuelType")
        color        = item.get("color")
        body_type    = item.get("bodyType")
        engine_size  = item.get("engineSize")
        nav_url      = item.get("navigationUrl")
        stock_id     = item.get("stock_id")
        images       = item.get("imageUrls", [])
        branch       = item.get("branch")

        year  = extract_year(title or "") or None
        make  = extract_make(title or "")
        model = extract_model(title or "")

        car = {
            "id":          stock_id or doc_ref.id,
            "externalId":  stock_id or None,

            "title":       title,
            "description": item.get("description"),

            "make":    make,
            "model":   model,
            "variant": item.get("variant"),

            "year":     year,
            "price":    parse_price(item.get("price")),
            "currency": "ZAR",

            "bodyType":     body_type,
            "fuelType":     fuel_type,
            "transmission": transmission,

            "drivetrain":  None,
            "engineSize":  parse_engine_size(engine_size),
            "enginePower": None,
            "cylinders":   None,
            "doors":       None,
            "seats":       None,

            "mileage":     parse_mileage(mileage),
            "mileageUnit": "KM" if mileage and "km" in str(mileage).lower() else None,

            "condition":       "Used",
            "serviceHistory":  None,
            "accidentHistory": None,
            "ownersCount":     None,

            "color":         color,
            "interiorColor": None,
            "exteriorColor": color,
            "paintType":     None,
            "upholstery":    None,

            "features":        [],
            "safetyFeatures":  [],
            "comfortFeatures": [],
            "techFeatures":    [],

            "fuelConsumption": None,
            "fuelEfficiency":  None,
            "range":           None,
            "emissionClass":   None,

            "location":      branch or "South Africa",
            "city":          None,
            "province":      None,
            "country":       "South Africa",
            "coordinates":   None,

            "dealershipName": branch,
            "sellerType":     "Dealer",

            "priceType":         "Fixed",
            "priceNegotiable":   None,
            "priceHistory":      None,
            "marketValueEstimate": None,

            "images":     images,
            "imageCount": len(images),

            "videoUrl":   None,
            "has360View": False,

            "sourceUrl":     nav_url,
            "navigationUrl": nav_url,

            "listingSource": "webuycars",
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

            "priceInsight":        None,
            "recommendedUseCase":  None,

            "category":    "car",
            "subCategory": None,
            "vehicleType": "car",
            "segment":     None,
            "usageType":   None,

            "raw": item,
        }

        batch.set(doc_ref, car)
        count += 1
        saved += 1

        if count == 500:
            batch.commit()
            batch = db.batch()
            count = 0

    if count > 0:
        batch.commit()

    logger.info(f"✅ Saved {saved} cars to Firestore.")


# ── Selenium: detail page ─────────────────────────────────────────────────────
def get_detail_value(driver, label):
    try:
        xpath = f"//div[contains(text(), '{label}')]/following-sibling::div"
        return driver.find_element(By.XPATH, xpath).text.strip()
    except:
        try:
            xpath = f"//*[normalize-space()='{label}']/following-sibling::*"
            return driver.find_element(By.XPATH, xpath).text.strip()
        except:
            return None


def scrape_car_details(driver, car_obj):
    nav_url = car_obj['navigationUrl']
    logger.info(f"🔎 Deep scraping: {nav_url}")

    driver.get(nav_url)
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Make:')]"))
        )
    except:
        logger.warning(f"⚠️ Detail page timeout for stock {car_obj.get('stock_id')}")

    car_obj.update({
        "variant":          get_detail_value(driver, "Variant:"),
        "registrationYear": get_detail_value(driver, "Registration Year:"),
        "mileage":          get_detail_value(driver, "Mileage:"),
        "transmission":     get_detail_value(driver, "Transmission:"),
        "branch":           get_detail_value(driver, "Branch:"),
        "bodyType":         get_detail_value(driver, "Body Type:"),
        "color":            get_detail_value(driver, "Colour:"),
        "engineSize":       get_detail_value(driver, "Engine Capacity:"),
        "fuelType":         get_detail_value(driver, "Fuel Type:"),
        "scrapedAt":        datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    })
    return car_obj


# ── Selenium: listing page ────────────────────────────────────────────────────
def scrape_page(driver, base_url, page_number):
    separator = "&" if "?" in base_url else "?"
    url = f"{base_url}{separator}page={page_number}" if page_number > 1 else base_url

    logger.info(f"📄 Page {page_number}: {url}")
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CLASS_NAME, "grid-card"))
        )
    except:
        logger.info(f"🚫 No listings on page {page_number} — URL exhausted.")
        return [], False

    time.sleep(4)
    for _ in range(3):
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(1.2)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(1)

    cards = driver.find_elements(By.CLASS_NAME, "grid-card")
    if not cards:
        return [], False

    cars = []
    for card in cards:
        try:
            title    = card.find_element(By.CLASS_NAME, "description").text.strip()
            stock_id = card.find_element(
                By.CSS_SELECTOR, "[data-stocknumber]"
            ).get_attribute("data-stocknumber")

            parts      = title.split()
            make       = parts[1] if len(parts) > 1 else "Unknown"
            model_slug = slugify(" ".join(parts[2:]))

            try:
                driver.execute_script("arguments[0].scrollIntoView(true);", card)
                time.sleep(0.3)
            except:
                pass

            image_urls = []
            try:
                for img in card.find_elements(By.TAG_NAME, "img"):
                    src = (
                        img.get_attribute("src")
                        or img.get_attribute("data-src")
                        or img.get_attribute("data-lazy")
                    )
                    if src and "photos.webuycars.co.za" in src and src not in image_urls:
                        image_urls.append(src)
            except Exception as e:
                logger.warning(f"⚠️ Image extraction failed: {e}")

            cars.append({
                "title":         title,
                "stock_id":      stock_id,
                "navigationUrl": f"https://www.webuycars.co.za/buy-a-car/{make}/{model_slug}/{stock_id}",
                "imageUrls":     image_urls,
                "sourcePage":    page_number,
            })

        except Exception as e:
            logger.warning(f"⚠️ Card parse failed: {e}")
            continue

    return cars, True


# ── Main ──────────────────────────────────────────────────────────────────────
def main():
    targets = get_targets()
    if not targets:
        logger.error("❌ No enabled targets found. Exiting.")
        return

    run_id = str(uuid.uuid4())
    logger.info(f"🆔 Run ID: {run_id}")

    options = ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)

    try:
        for target in targets:
            label    = target.get("label", "unknown")
            base_url = target.get("url", "")
            max_pages = int(target.get("maxPages", 3))

            if not base_url:
                logger.warning(f"⚠️ No URL for target '{label}' — skipping.")
                continue

            # Resume from last saved progress
            start_page = get_start_page(label)
            if start_page is None:
                logger.info(f"⏭️  Skipping '{label}' (already exhausted today).")
                continue

            logger.info(f"🚀 '{label}' | pages {start_page}–{start_page + max_pages - 1}")

            last_page_scraped = start_page - 1
            exhausted = False
            cars_batch = []

            for page_number in range(start_page, start_page + max_pages):
                cars_on_page, has_results = scrape_page(driver, base_url, page_number)

                if not has_results:
                    exhausted = True
                    logger.info(f"🏁 '{label}' exhausted at page {page_number}")
                    break

                for car in cars_on_page:
                    full_data = scrape_car_details(driver, car)
                    full_data["targetLabel"] = label
                    cars_batch.append(full_data)
                    logger.info(f"✅ {full_data['stock_id']} | page {page_number}")

                last_page_scraped = page_number

            # Save all cars for this target
            save_cars_to_firestore(cars_batch, run_id)

            # Save progress marker
            save_progress(label, last_page_scraped, exhausted)

    finally:
        driver.quit()
        logger.info("🏁 Scraper finished.")


if __name__ == "__main__":
    main()
