"""
Adapter: webuycars.co.za
"""

import re
import time
import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .base import SiteAdapter

logger = logging.getLogger(__name__)


def _slugify(text: str) -> str:
    text = text.replace(" ", "-").replace("/", "-")
    return re.sub(r"[^a-zA-Z0-9\-]", "", text)


class WeBuyCarsAdapter(SiteAdapter):
    site_name = "webuycars"

    # ── Listing page ──────────────────────────────────────────────────────────

    def scrape_listing_page(self, base_url: str, page_number: int):
        sep = "&" if "?" in base_url else "?"
        url = f"{base_url}{sep}page={page_number}" if page_number > 1 else base_url

        logger.info(f"[WBC] 📄 Page {page_number}: {url}")
        self.driver.get(url)

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.CLASS_NAME, "grid-card"))
            )
        except Exception:
            logger.info(f"[WBC] 🚫 No listings on page {page_number}.")
            return [], False

        time.sleep(4)
        self.scroll_page()

        cards = self.driver.find_elements(By.CLASS_NAME, "grid-card")

        if not cards:
            return [], False

        cars = []

        for card in cards:
            try:
                title = card.find_element(
                    By.CLASS_NAME,
                    "description"
                ).text.strip()

                try:
                    price = card.find_element(
                        By.CSS_SELECTOR,
                        ".price-text span"
                    ).text.strip()
                except Exception:
                    price = None

                price_value = (
                    re.sub(r"[^\d]", "", price)
                    if price else None
                )

                stock_id = card.find_element(
                    By.CSS_SELECTOR,
                    "[data-stocknumber]"
                ).get_attribute("data-stocknumber")

                parts = title.split()

                make = parts[1] if len(parts) > 1 else "Unknown"

                model_slug = _slugify(
                    " ".join(parts[2:])
                )

                try:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView(true);",
                        card
                    )
                    time.sleep(0.3)

                except Exception:
                    pass

                image_urls = []

                for img in card.find_elements(By.TAG_NAME, "img"):

                    src = (
                        img.get_attribute("src")
                        or img.get_attribute("data-src")
                        or img.get_attribute("data-lazy")
                    )

                    if (
                        src
                        and "photos.webuycars.co.za" in src
                        and src not in image_urls
                    ):
                        image_urls.append(src)

                cars.append({
                    "title": title,
                    "stock_id": stock_id,
                    "price": price,
                    "priceValue": price_value,
                    "navigationUrl": (
                        f"https://www.webuycars.co.za/buy-a-car/"
                        f"{make}/{model_slug}/{stock_id}"
                    ),
                    "imageUrls": image_urls,
                    "sourcePage": page_number,
                    "listingSource": "webuycars",
                })

            except Exception as e:
                logger.warning(f"[WBC] ⚠️ Card parse failed: {e}")

        return cars, True

    # ── Detail page ───────────────────────────────────────────────────────────

    def scrape_detail_page(self, car: dict) -> dict:

        url = car["navigationUrl"]

        logger.info(f"[WBC] 🔎 Detail: {url}")

        self.driver.get(url)

        try:
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "//div[contains(text(), 'Make:')]"
                ))
            )

        except Exception:
            logger.warning(
                f"[WBC] ⚠️ Detail timeout for {car.get('stock_id')}"
            )

        def gv(label):
            try:
                return self.driver.find_element(
                    By.XPATH,
                    f"//div[contains(text(), '{label}')]/following-sibling::div"
                ).text.strip()

            except Exception:
                try:
                    return self.driver.find_element(
                        By.XPATH,
                        f"//*[normalize-space()='{label}']/following-sibling::*"
                    ).text.strip()

                except Exception:
                    return None

        car.update({
            "variant": gv("Variant:"),
            "registrationYear": gv("Registration Year:"),
            "mileage": gv("Mileage:"),
            "transmission": gv("Transmission:"),
            "branch": gv("Branch:"),
            "bodyType": gv("Body Type:"),
            "color": gv("Colour:"),
            "engineSize": gv("Engine Capacity:"),
            "fuelType": gv("Fuel Type:"),
        })

        return car