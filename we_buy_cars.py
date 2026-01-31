import time
from selenium.webdriver.common.by import By


def scrape_wbc(driver):
    """Encapsulated logic for WeBuyCars"""
    scraped_data = []

    try:
        print("🔗 Debug: Navigating to URL...")
        driver.get("https://www.webuycars.co.za/buy-a-car")
        time.sleep(3)  # Wait for page load

        print("🍪 Debug: Injecting session cookie...")
        driver.add_cookie({"name": "webuycarssessionID", "value": "5ac3ac85-409a-45b7-ac4e-6387cabf1610"})
        driver.refresh()
        time.sleep(3)

        print("🖱️ Debug: Scrolling to trigger lazy-loading...")
        for i in range(1, 5):
            driver.execute_script("window.scrollBy(0, 1000);")
            print(f"   - Scroll {i}/4 complete")
            time.sleep(2)

        print("🔍 Debug: Locating car cards...")
        cards = driver.find_elements(By.CLASS_NAME, "grid-card")

        if not cards:
            print("⚠️ Debug: No cards found! Check if the CLASS_NAME has changed.")
            return []

        print(f"📦 Debug: Found {len(cards)} cars. Starting extraction...")

        for index, card in enumerate(cards):
            try:
                # Link extraction
                try:
                    nav_link = card.find_element(By.XPATH, "./ancestor::a | .//a").get_attribute("href")
                except:
                    nav_link = "N/A"

                # Text extraction
                title = card.find_element(By.CLASS_NAME, "description").text
                price = card.find_element(By.CLASS_NAME, "price-text").text

                # Image extraction
                images = card.find_elements(By.CLASS_NAME, "wbc-swiper-img")
                img_urls = [img.get_attribute("src") for img in images if img.get_attribute("src")]
                images_formatted = " | ".join(img_urls)

                scraped_data.append({
                    "Title": title,
                    "Price": price,
                    "Navigation_URL": nav_link,
                    "Image_URLs": images_formatted
                })

                if index % 5 == 0:
                    print(f"   ✅ Processed {index} cars...")

            except Exception as inner_e:
                # Skip individual cards if they fail, don't crash the whole scraper
                continue

        print(f"🏁 Debug: Extraction finished. Total: {len(scraped_data)}")
        return scraped_data

    except Exception as e:
        print(f"❌ Debug: Error inside we_buy_cars module: {e}")
        return []