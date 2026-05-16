import os
import json
import time
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# ==================== CONFIGURATION ====================
BASE_URL = "https://www.adsafrica.co.za/category/65/"
TOTAL_PAGES = 200  # Set how many pages you want to scrape
OUTPUT_FILE = "reply_urls.json"  # Saved directly as reply links
PAGE_DELAY = 2.0  # Time to wait for elements to load safely
# =======================================================

def load_existing_urls(file_path):
    """Loads existing URLs from JSON file to prevent duplicates across runs."""
    if os.path.exists(file_path):
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
        except (json.JSONDecodeError, IOError):
            print(f"[!] Warning: Could not parse {file_path}. Starting fresh.")
    return []

def append_to_json(file_path, new_urls):
    """Progressively appends unique URLs to the JSON file after every page."""
    existing_urls = load_existing_urls(file_path)
    
    added_count = 0
    for url in new_urls:
        if url not in existing_urls:
            existing_urls.append(url)
            added_count += 1
            
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(existing_urls, f, indent=4, ensure_ascii=False)
        
    return added_count, len(existing_urls)

def setup_driver():
    """Initializes a headless Chrome driver with basic anti-detection styling."""
    options = Options()
    options.add_argument("--headless")  # Runs browser in the background
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def main():
    driver = setup_driver()
    print(f"[*] Target Base URL: {BASE_URL}")
    print(f"[*] Target Pages: {TOTAL_PAGES}\n")

    try:
        for page in range(1, TOTAL_PAGES + 1):
            # Construct pagination URL (Page 1 uses base, Page 2+ appends page number directory)
            if page == 1:
                current_url = BASE_URL
            else:
                current_url = f"{BASE_URL.rstrip('/')}/{page}/"
                
            print(f"[+] Scraping Page {page}/{TOTAL_PAGES}: {current_url}")
            driver.get(current_url)
            time.sleep(PAGE_DELAY)  # Allow page JS and components to resolve safely
            
            # Locate all items matching the target anchor class element
            elements = driver.find_elements(By.CLASS_NAME, "list_item_title")
            page_reply_urls = []
            
            for elem in elements:
                href = elem.get_attribute("href")
                if href:
                    # Extracts just the numeric ID from the link (e.g., '16433428' from '/item/16433428/')
                    match = re.search(r'/item/(\d+)', href)
                    if match:
                        item_id = match.group(1)
                        # Rebuild directly into the target reply URL format
                        reply_url = f"https://www.adsafrica.co.za/reply/{item_id}/"
                        page_reply_urls.append(reply_url)
            
            print(f"    -> Converted {len(page_reply_urls)} links directly to reply format.")
            
            # Save progressively to disk
            added, total = append_to_json(OUTPUT_FILE, page_reply_urls)
            print(f"    -> Progress Saved: +{added} new reply links added. (Grand Total in File: {total})")
            
    except Exception as e:
        print(f"\n[!] An error occurred during scraping: {e}")
        
    finally:
        driver.quit()
        print("\n[*] Driver closed. Process completed successfully.")

if __name__ == "__main__":
    main()