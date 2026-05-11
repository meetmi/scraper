import asyncio
import csv
import time
import re

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


def build_page_urls(base_urls, max_pages):
    all_urls = []
    for base in base_urls:
        for page in range(1, max_pages + 1):
            if page == 1:
                all_urls.append(base)
            else:
                all_urls.append(f"{base}&page={page}")
    return all_urls


def scrape_wbc(driver, url):
    scraped_data = []
    try:
        print(f"🔗 Navigating to: {url}")
        driver.get(url)

        try:
            WebDriverWait(driver, 25).until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR,
                    "div[class*='Card'], div[class*='card'], .grid-card"
                ))
            )
        except Exception:
            print("⚠️ Timed out waiting for cards.")

        # Scrolling to trigger lazy loading
        for _ in range(5):
            driver.execute_script("window.scrollBy(0, 800);")
            time.sleep(1)

        cards = driver.find_elements(By.CSS_SELECTOR, ".grid-card, div[class*='Card_container']")
        print(f"📦 Found {len(cards)} cards on page")

        for card in cards:
            try:
                # ── 1. Basic Data ──
                title_el = card.find_elements(By.CLASS_NAME, "description")
                price_el = card.find_elements(By.CLASS_NAME, "price-text")

                full_title = title_el[0].text.strip() if title_el else "N/A"
                price = price_el[0].text.strip() if price_el else "N/A"

                # ── 2. Get Stock Number ──
                stock_id = "N/A"
                try:
                    # Found in the favorite button data attribute
                    stock_el = card.find_element(By.CSS_SELECTOR, "[data-stocknumber]")
                    stock_id = stock_el.get_attribute("data-stocknumber")
                except:
                    pass

                # ── 3. Build SEO Navigation URL ──
                # Logic: https://www.webuycars.co.za/buy-a-car/Make/Model/StockNumber
                nav_link = "N/A"
                if full_title != "N/A" and stock_id != "N/A":
                    parts = full_title.split()

                    # Assume title is "YEAR MAKE MODEL..." (e.g. 2026 Suzuki S-Presso)
                    # We skip the year if it's the first word
                    start_idx = 1 if parts[0].isdigit() and len(parts[0]) == 4 else 0

                    if len(parts) > start_idx + 1:
                        make = parts[start_idx]
                        # Join the rest of the string as the model and clean it
                        model_raw = " ".join(parts[start_idx + 1:])
                        model_slug = model_raw.replace(" ", "-").replace("/", "-")
                        # Remove any extra special characters
                        model_slug = re.sub(r'[^a-zA-Z0-9\-]', '', model_slug)

                        nav_link = f"https://www.webuycars.co.za/buy-a-car/{make}/{model_slug}/{stock_id}"

                # ── 4. Image Extraction ──
                try:
                    img_el = card.find_element(By.CSS_SELECTOR, "img.wbc-swiper-img, img.slider-image")
                    image_url = img_el.get_attribute("src")
                except:
                    image_url = "N/A"

                if full_title != "N/A":
                    scraped_data.append({
                        "Title": full_title,
                        "Price": price.replace("\n", " ").strip(),
                        "Navigation_URL": nav_link,
                        "Stock_ID": stock_id,
                        "Image_URL": image_url,
                        "Source_URL": url
                    })

            except Exception as e:
                continue

        return scraped_data

    except Exception as e:
        print(f"❌ Scraper error on {url}: {e}")
        return []


async def main():
    if HAS_APIFY:
        await Actor.init()
        actor_input = await Actor.get_input() or {}
        base_urls = actor_input.get("urls", BASE_SEARCH_URLS)
        max_pages = actor_input.get("max_pages", MAX_PAGES)
    else:
        print("🏠 Running locally")
        base_urls = BASE_SEARCH_URLS
        max_pages = MAX_PAGES

    urls_to_scrape = build_page_urls(base_urls, max_pages)

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    try:
        all_results = []
        for target_url in urls_to_scrape:
            results = scrape_wbc(driver, target_url)
            all_results.extend(results)

            if HAS_APIFY:
                for item in results:
                    await Actor.push_data(item)

            print(f"✅ Sub-total so far: {len(all_results)} items")
            time.sleep(2)

        if not HAS_APIFY and all_results:
            keys = all_results[0].keys()
            with open("webuycars_results.csv", "w", newline="", encoding="utf-8") as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(all_results)
            print(f"📂 Saved {len(all_results)} records to webuycars_results.csv")

    finally:
        if driver:
            driver.quit()
        if HAS_APIFY:
            await Actor.exit()


if __name__ == "__main__":
    asyncio.run(main())