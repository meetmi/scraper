import os
import csv
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

# 1. IMPORT ALL SITE MODULES
import we_buy_cars

# --- CONFIG ---
# Switch between "WBC" or "ADS_AFRICA" here
TARGET_SITE = "WBC"


def save_to_csv(data, filename):
    if not data:
        print("⚠️ No data found to save.")
        return
    current_folder = os.path.dirname(os.path.abspath(__file__))
    full_path = os.path.join(current_folder, filename)
    keys = data[0].keys()
    with open(full_path, 'w', newline='', encoding='utf-8') as f:
        dict_writer = csv.DictWriter(f, fieldnames=keys)
        dict_writer.writeheader()
        dict_writer.writerows(data)
    print(f"✅ Saved to: {full_path}")


# --- NEW STABLE SETUP ---
options = Options()
options.add_argument("--start-maximized")
options.add_argument("--disable-blink-features=AutomationControlled")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")

print(f"🚀 Launching Browser for {TARGET_SITE}...")
try:
    driver = webdriver.Chrome(options=options)
except Exception as e:
    print(f"❌ Launch Error: {e}")
    sys.exit()

# --- MAIN EXECUTION BLOCK ---
try:
    if TARGET_SITE == "WBC":
        print("🔍 Mode: WeBuyCars")
        results = we_buy_cars.scrape_wbc(driver)
        save_to_csv(results, "webuycars_final.csv")



    else:
        print("❓ Unknown site selected in CONFIG.")

except Exception as e:
    print(f"💥 An error occurred during scraping: {e}")

finally:
    print("🧹 Closing browser...")
    driver.quit()