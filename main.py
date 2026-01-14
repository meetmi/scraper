import time
import csv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# 1. Setup Chrome
chrome_options = Options()
chrome_options.add_argument("--start-maximized")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
chrome_options.add_argument(f'user-agent={user_agent}')

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

try:
    print("🚗 Navigating to WeBuyCars...")
    driver.get("https://www.webuycars.co.za/buy-a-car")

    # Inject session cookie for stability
    driver.add_cookie({"name": "webuycarssessionID", "value": "5ac3ac85-409a-45b7-ac4e-6387cabf1610"})

    # 2. Trigger Lazy Loading
    print("🖱️ Scrolling to load dynamic content...")
    for _ in range(4):
        driver.execute_script("window.scrollBy(0, 1000);")
        time.sleep(2)

    # 3. Targeted Extraction
    cards = driver.find_elements(By.CLASS_NAME, "grid-card")
    scraped_data = []

    print(f"📦 Found {len(cards)} cars. Extracting details...")

    for card in cards:
        try:
            # --- Extract Navigation URL ---
            # We look for the <a> tag that wraps the image or card
            try:
                # This finds the closest link element to navigate to the car page
                nav_link = card.find_element(By.XPATH, "./ancestor::a | .//a").get_attribute("href")
            except:
                nav_link = "N/A"

            # --- Extract Text Data ---
            title = card.find_element(By.CLASS_NAME, "description").text
            price = card.find_element(By.CLASS_NAME, "price-text").text

            # --- Extract ALL Image URLs from the Swiper ---
            # Using the class from your HTML snippet: wbc-swiper-img
            images = card.find_elements(By.CLASS_NAME, "wbc-swiper-img")
            img_urls = []
            for img in images:
                src = img.get_attribute("src")
                if src:
                    img_urls.append(src)

            # Combine image URLs into one string separated by |
            images_formatted = " | ".join(img_urls)

            print(f"✅ Scraped: {title}")

            scraped_data.append({
                "Title": title,
                "Price": price,
                "Navigation_URL": nav_link,
                "Image_URLs": images_formatted
            })

        except Exception as e:
            continue

    # 4. Save Results to CSV
    keys = ["Title", "Price", "Navigation_URL", "Image_URLs"]
    with open('../Documents/pythonProject/webuycars_final.csv', 'w', newline='', encoding='utf-8') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(scraped_data)

    print(f"\n🚀 SUCCESS! {len(scraped_data)} cars saved to 'webuycars_final.csv'")

finally:
    driver.quit()