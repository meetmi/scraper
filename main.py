import asyncio
import csv
import time
import re
import os
from datetime import datetime, UTC

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from webdriver_manager.chrome import ChromeDriverManager

try:
    from apify import Actor

    HAS_APIFY = True
except ImportError:
    HAS_APIFY = False

BASE_SEARCH_URLS = [
    "https://www.webuycars.co.za/buy-a-car?q=%22Toyota%20Hilux%20%22&Year=[2017,2026]&Year_Gte=%222017%22",
    "https://www.webuycars.co.za/buy-a-car?q=%22Ford%20Ranger%22&Year=[2017,2026]&Year_Gte=%222017%22"
]
MAX_PAGES = 1
OUTPUT_FILE = "webuycars_deep_results.csv"


def slugify(text):
    text = text.replace(" ", "-").replace("/", "-")
    return re.sub(r'[^a-zA-Z0-9\-]', '', text)


def get_detail_value(driver, label):
    """
    Targets the specific layout found in WBC detail pages.
    Looks for a div containing the label and gets the following sibling or parent's child.
    """
    try:
        # Strategy 1: Standard label-value pair
        xpath = f"//div[contains(text(), '{label}')]/following-sibling::div"
        element = driver.find_element(By.XPATH, xpath)
        return element.text.strip()
    except:
        try:
            # Strategy 2: Label inside a span or different div level
            xpath = f"//*[normalize-space()='{label}']/following-sibling::*"
            element = driver.find_element(By.XPATH, xpath)
            return element.text.strip()
        except:
            return None


async def scrape_car_details(driver, car_obj):
    nav_url = car_obj['navigationUrl']
    print(f"🔍 Deep Scraping Specs: {nav_url}")

    driver.get(nav_url)
    try:
        # Wait specifically for the specs container to appear
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//div[contains(text(), 'Make:')]")))
    except:
        pass

    # Map the exact fields provided in your example
    car_obj.update({
        "variant": get_detail_value(driver, "Variant:"),
        "registrationYear": get_detail_value(driver, "Registration Year:"),
        "mileage": get_detail_value(driver, "Mileage:"),
        "transmission": get_detail_value(driver, "Transmission:"),
        "branch": get_detail_value(driver, "Branch:"),
        "seats": get_detail_value(driver, "No of Seats:"),
        "doors": get_detail_value(driver, "No of Doors:"),
        "bodyType": get_detail_value(driver, "Body Type:"),
        "color": get_detail_value(driver, "Colour:"),
        "serviceHistory": get_detail_value(driver, "Vehicle Service History:"),
        "fuelConsumption": get_detail_value(driver, "Fuel Consumption:"),
        "engineSize": get_detail_value(driver, "Engine Capacity:"),
        "fuelTank": get_detail_value(driver, "Fuel Tank Capacity:"),
        "fuelType": get_detail_value(driver, "Fuel Type:"),
        "kilowatts": get_detail_value(driver, "Kilowatts:"),
        "gears": get_detail_value(driver, "Gears:"),
        "drive": get_detail_value(driver, "Drive:"),
        "scrapedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "scrapedDate": datetime.now().strftime("%d-%m-%y"),
    })
    return car_obj


async def get_all_car_links(driver, url):
    print(f"🔗 Gathering links from: {url}")
    driver.get(url)

    try:
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, "grid-card")))
    except:
        return []

    # Scroll once to trigger card loading
    driver.execute_script("window.scrollTo(0, 1000);")
    time.sleep(2)

    cards = driver.find_elements(By.CLASS_NAME, "grid-card")
    cars_found = []

    for card in cards:
        try:
            title = card.find_element(By.CLASS_NAME, "description").text.strip()
            price = card.find_element(By.CLASS_NAME, "price-text").text.strip()
            stock_id = card.find_element(By.CSS_SELECTOR, "[data-stocknumber]").get_attribute("data-stocknumber")

            # Basic parsing for URL construction
            parts = title.split()
            make = parts[1] if len(parts) > 1 else "Unknown"
            model_parts = parts[2:]
            model_slug = slugify(" ".join(model_parts))

            nav_link = f"https://www.webuycars.co.za/buy-a-car/{make}/{model_slug}/{stock_id}"

            # Images
            img_els = card.find_elements(By.TAG_NAME, "img")
            images = list(
                set([img.get_attribute("src") for img in img_els if "photobooth" in (img.get_attribute("src") or "")]))

            cars_found.append({
                "title": title,
                "price": price,
                "stock_id": stock_id,
                "navigationUrl": nav_link,
                "images": images,
                "imageCount": len(images),
                "sourceUrl": url,
                "createdAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                # Placeholders for deep-scrape fields
                "variant": None, "registrationYear": None, "mileage": None,
                "transmission": None, "branch": None, "seats": None,
                "doors": None, "bodyType": None, "color": None,
                "serviceHistory": None, "fuelConsumption": None,
                "engineSize": None, "fuelType": None
            })
        except:
            continue

    return cars_found


async def main():
    if HAS_APIFY:
        await Actor.init()
        actor_input = await Actor.get_input() or {}
        base_urls = actor_input.get("urls", BASE_SEARCH_URLS)
        max_pages = actor_input.get("max_pages", MAX_PAGES)
    else:
        base_urls, max_pages = BASE_SEARCH_URLS, MAX_PAGES

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    # 1. Collect Links
    all_summaries = []
    for base in base_urls:
        for page in range(1, max_pages + 1):
            target = f"{base}&page={page}" if page > 1 else base
            all_summaries.extend(await get_all_car_links(driver, target))

    # 2. Deep Scrape and Append to CSV immediately
    file_exists = os.path.isfile(OUTPUT_FILE)
    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8") as f:
        writer = None
        for car in all_summaries:
            full_data = await scrape_car_details(driver, car)

            if writer is None:
                writer = csv.DictWriter(f, fieldnames=full_data.keys())
                if not file_exists:
                    writer.writeheader()
                    file_exists = True

            writer.writerow(full_data)
            f.flush()

            if HAS_APIFY:
                await Actor.push_data(full_data)

            print(f"✅ Progress: Saved {full_data['stock_id']} from {full_data['branch']}")
            time.sleep(1)

    driver.quit()
    if HAS_APIFY: await Actor.exit()


if __name__ == "__main__":
    asyncio.run(main())