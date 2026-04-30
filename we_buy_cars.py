import time
import asyncio
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# List of your specific search URLs
SEARCH_URLS = [
    "https://www.webuycars.co.za/buy-a-car?q=%22Toyota%20Hilux%20%22&Year=[2017,2026]&Year_Gte=%222017%22",
    "https://www.webuycars.co.za/buy-a-car?q=%22Ford%20Ranger%22&Year=[2017,2026]&Year_Gte=%222017%22"
]


def scrape_wbc(driver, url):
    """Scrapes a specific WeBuyCars search URL"""
    scraped_data = []
    try:
        print(f"🔗 Navigating to: {url}")
        driver.get(url)
        time.sleep(3)

        # Injection must happen while on the site
        try:
            driver.add_cookie({"name": "webuycarssessionID", "value": "5ac3ac85-409a-45b7-ac4e-6387cabf1610"})
            driver.refresh()
            time.sleep(3)
        except Exception as e:
            print(f"ℹ️ Cookie injection skipped/failed: {e}")

        print("🖱️ Scrolling...")
        for i in range(1, 4):
            driver.execute_script("window.scrollBy(0, 1000);")
            time.sleep(2)

        cards = driver.find_elements(By.CLASS_NAME, "grid-card")
        print(f"📦 Found {len(cards)} cars on this page.")

        for card in cards:
            try:
                title = card.find_element(By.CLASS_NAME, "description").text
                price = card.find_element(By.CLASS_NAME, "price-text").text

                try:
                    nav_link = card.find_element(By.XPATH, ".//a").get_attribute("href")
                except:
                    nav_link = "N/A"

                images = card.find_elements(By.CLASS_NAME, "wbc-swiper-img")
                img_urls = [img.get_attribute("src") for img in images if img.get_attribute("src")]

                scraped_data.append({
                    "Title": title,
                    "Price": price,
                    "Navigation_URL": nav_link,
                    "Image_URLs": " | ".join(img_urls),
                    "Search_Source": url  # Helps you know which link found which car
                })
            except:
                continue

        return scraped_data

    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return []


async def main():
    # Setup Driver
    options = Options()
    options.add_argument("--headless=new")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=options)

    all_results = []

    try:
        # --- THE LOOP ---
        for target_url in SEARCH_URLS:
            results = scrape_wbc(driver, target_url)
            all_results.extend(results)
            print(f"✅ Finished URL. Current total: {len(all_results)} items.")
            time.sleep(2)  # Short breather between searches

        # If using Apify, push all data at once or inside the loop
        # for item in all_results:
        #     await Actor.push_data(item)

        print(f"🏁 Final Count: {len(all_results)} cars scraped across all links.")

    finally:
        driver.quit()


if __name__ == "__main__":
    asyncio.run(main())