import time
import asyncio
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

try:
    from apify import Actor

    HAS_APIFY = True
except ImportError:
    HAS_APIFY = False

SEARCH_URLS = [
    "https://www.webuycars.co.za/buy-a-car?q=%22Toyota%20Hilux%20%22&Year=[2017,2026]&Year_Gte=%222017%22",
    "https://www.webuycars.co.za/buy-a-car?q=%22Ford%20Ranger%22&Year=[2017,2026]&Year_Gte=%222017%22"
]


def scrape_wbc(driver, url):
    scraped_data = []
    try:
        print(f"🔗 Navigating to: {url}")
        driver.get(url)
        time.sleep(5)  # Increased wait for site load

        print("🖱️ Scrolling...")
        for _ in range(3):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(1)

        # Finding the car container cards
        cards = driver.find_elements(By.CLASS_NAME, "grid-card")
        print(f"📦 Found {len(cards)} cards on page")

        for card in cards:
            try:
                # Use find_elements (plural) + if-check to prevent crashes if one field is missing
                title_el = card.find_elements(By.CLASS_NAME, "description")
                price_el = card.find_elements(By.CLASS_NAME, "price-text")

                title = title_el[0].text if title_el else "N/A"
                price = price_el[0].text if price_el else "N/A"

                # Link extraction
                try:
                    nav_link = card.find_element(By.TAG_NAME, "a").get_attribute("href")
                except:
                    nav_link = "N/A"

                scraped_data.append({
                    "Title": title,
                    "Price": price.replace("\n", " "),
                    "Navigation_URL": nav_link,
                    "Source_URL": url
                })
            except Exception as e:
                # If a single card fails, we print why but keep going
                print(f"⚠️ Skipping a card due to: {e}")
                continue

        return scraped_data
    except Exception as e:
        print(f"❌ Scraper error on {url}: {e}")
        return []


async def main():
    if HAS_APIFY:
        await Actor.init()
        urls_to_scrape = (await Actor.get_input() or {}).get("urls", SEARCH_URLS)
    else:
        print("🏠 Running locally")
        urls_to_scrape = SEARCH_URLS

    options = Options()
    options.add_argument("--headless=new")
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

    all_results = []

    try:
        for target_url in urls_to_scrape:
            results = scrape_wbc(driver, target_url)
            all_results.extend(results)

            if HAS_APIFY:
                for item in results:
                    await Actor.push_data(item)

            print(f"✅ Sub-total: {len(all_results)} items")

        # --- CSV SAVING LOGIC (LOCAL ONLY) ---
        if not HAS_APIFY and all_results:
            keys = all_results[0].keys()
            with open('webuycars_results.csv', 'w', newline='', encoding='utf-8') as f:
                dict_writer = csv.DictWriter(f, fieldnames=keys)
                dict_writer.writeheader()
                dict_writer.writerows(all_results)
            print(f"📂 SUCCESS: Saved {len(all_results)} items to webuycars_results.csv")
        elif not all_results:
            print("❌ No data was collected. Check your element selectors.")

    finally:
        driver.quit()
        if HAS_APIFY:
            await Actor.exit()


if __name__ == "__main__":
    asyncio.run(main())