import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def scrape_ads_africa(driver):
    """Scraping logic for Ads Africa category 65"""
    print("🌍 Navigating to Ads Africa...")
    driver.get("https://www.adsafrica.co.za/category/65/")

    # --- 1. HANDLE THE AGE VERIFICATION MODAL ---
    try:
        print("🛡️ Waiting for age verification modal...")
        wait = WebDriverWait(driver, 10)

        # Target the button with class 'yes' inside the age-verify div
        yes_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "#age-verify button.yes")))

        yes_button.click()
        print("✅ Age verified. Content unlocked.")
        time.sleep(2)  # Wait for blur-it class to be removed
    except Exception as e:
        print(f"ℹ️ Modal handle skipped: {e}")

    # --- 2. DATA EXTRACTION ---
    # Based on your HTML, items are rows (tr) in the table 'ItemsList'
    # with classes 'ILL_odd' or 'ILL_even'
    print("📦 Locating listings in ItemsList...")
    rows = driver.find_elements(By.CSS_SELECTOR, "#ItemsList tr.ILL_odd, #ItemsList tr.ILL_even")

    scraped_data = []

    for row in rows:
        try:
            # Find the title link
            title_element = row.find_element(By.CLASS_NAME, "list_item_title")
            title = title_element.text
            link = title_element.get_attribute("href")

            # Find the description
            try:
                desc = row.find_element(By.CLASS_NAME, "list_item_description").text
            except:
                desc = ""

            # Find the location/path
            try:
                location = row.find_element(By.CLASS_NAME, "list_item_path").text
            except:
                location = "N/A"

            # Find the thumbnail image
            try:
                img_src = row.find_element(By.CSS_SELECTOR, ".ILThumb img").get_attribute("src")
            except:
                img_src = "No Image"

            scraped_data.append({
                "Title": title,
                "Location": location,
                "Description": desc,
                "Navigation_URL": link,
                "Image_URL": img_src
            })
            print(f"✅ Scraped: {title[:30]}...")

        except Exception as e:
            continue

    return scraped_data