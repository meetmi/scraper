"""
Adapter: cars.co.za  (Mantine UI build)

Confirmed DOM structure (from live card HTML, 2025):
  • Each listing card is an  <a class="mantine-Card-root …">  — the card IS the link
  • data-cy test-hooks are present on all key spec elements (most stable selectors)
  • Pagination: append &P=N  (or ?P=N if no existing query string)

Card selector  :  a.mantine-Card-root
Field selectors (relative to card):
  title        →  h3.cy-result-title
  variant      →  [data-cy="cy-result-variant"]
  price        →  h3.vehicle-price
  year         →  [data-cy="vehicle-spec-year"] span
  mileage      →  [data-cy="vehicle-spec-mileage"] span
  transmission →  [data-cy="vehicle-spec-transmission"] span
  fuel type    →  [data-cy="vehicle-spec-fuel-type"] span
  main image   →  img.VehicleCard_mainImage__xjSlM
  thumbnails   →  div.VehicleCard_thumbs__iM8Co img
  nav URL      →  the card's own href attribute
"""

import os
import re
import time
import logging

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .base import SiteAdapter

logger = logging.getLogger(__name__)

BASE = "https://www.cars.co.za"
CARD_SEL = "a.mantine-Card-root"


# ── Low-level helpers (module-level so they're reusable) ─────────────────────

def _attr(el, *attrs) -> str | None:
    """Return the first non-empty attribute value from el."""
    for a in attrs:
        try:
            v = el.get_attribute(a)
            if v and v.strip():
                return v.strip()
        except Exception:
            pass
    return None


def _text(root, selector: str) -> str | None:
    """Return stripped text of the first matching element, or None."""
    try:
        el = root.find_element(By.CSS_SELECTOR, selector)
        t  = el.text.strip()
        return t if t else None
    except Exception:
        return None


def _attr_from_sel(root, selector: str, *attrs) -> str | None:
    """Find element by selector inside root, then return first non-empty attr."""
    try:
        el = root.find_element(By.CSS_SELECTOR, selector)
        return _attr(el, *attrs)
    except Exception:
        return None


def _scroll(driver, times: int = 4, gap: float = 1.0):
    for _ in range(times):
        driver.execute_script("window.scrollBy(0, 1200);")
        time.sleep(gap)
    driver.execute_script("window.scrollTo(0, 0);")
    time.sleep(0.8)


def _dump_html(driver, page_number: int):
    """Save rendered page source to logs/ for selector debugging."""
    try:
        os.makedirs("logs", exist_ok=True)
        fname = f"logs/carsza_debug_page{page_number}.html"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info(f"[CZA] 💾 HTML dumped → {fname}  (open to inspect real selectors)")
    except Exception as e:
        logger.warning(f"[CZA] Could not dump HTML: {e}")


def _build_spec_map(driver) -> dict:
    """
    Scrape the entire detail page for label→value pairs.
    Handles: dt/dd lists, table rows (th/td or td/td),
    paired sibling divs with class*='label'/'value',
    and data-cy spec elements.
    Returns {lowercase_label: value}.
    """
    spec_map = {}

    # Pattern 1: <dt>label</dt><dd>value</dd>
    try:
        for dt in driver.find_elements(By.TAG_NAME, "dt"):
            try:
                dd  = dt.find_element(By.XPATH, "following-sibling::dd[1]")
                key = dt.text.strip().lower().rstrip(":")
                val = dd.text.strip()
                if key and val:
                    spec_map[key] = val
            except Exception:
                pass
    except Exception:
        pass

    # Pattern 2: table rows — <tr><th>label</th><td>value</td></tr>
    #                      or <tr><td>label</td><td>value</td></tr>
    try:
        for row in driver.find_elements(By.TAG_NAME, "tr"):
            cells = row.find_elements(By.XPATH, "th | td")
            if len(cells) >= 2:
                key = cells[0].text.strip().lower().rstrip(":")
                val = cells[1].text.strip()
                if key and val:
                    spec_map[key] = val
    except Exception:
        pass

    # Pattern 3: paired sibling divs with class*='label' / class*='value'
    try:
        for lbl_el in driver.find_elements(
            By.CSS_SELECTOR,
            "[class*='label'], [class*='Label'], [class*='key']"
        ):
            try:
                val_el = lbl_el.find_element(
                    By.XPATH,
                    "following-sibling::*["
                    "contains(@class,'value') or "
                    "contains(@class,'Value') or "
                    "contains(@class,'val')][1]"
                )
                key = lbl_el.text.strip().lower().rstrip(":")
                val = val_el.text.strip()
                if key and val:
                    spec_map[key] = val
            except Exception:
                pass
    except Exception:
        pass

    # Pattern 4: data-cy spec elements (also present on detail page)
    CY_MAP = {
        "vehicle-spec-year":         "year",
        "vehicle-spec-mileage":      "mileage",
        "vehicle-spec-transmission": "transmission",
        "vehicle-spec-fuel-type":    "fuel type",
    }
    for cy_val, label in CY_MAP.items():
        try:
            el  = driver.find_element(By.CSS_SELECTOR, f'[data-cy="{cy_val}"] span')
            val = el.text.strip()
            if val and label not in spec_map:
                spec_map[label] = val
        except Exception:
            pass

    return spec_map


# ── Adapter class ─────────────────────────────────────────────────────────────

class CarsDotCoZaAdapter(SiteAdapter):
    site_name = "carsza"

    # ── Listing page ──────────────────────────────────────────────────────────

    def scrape_listing_page(self, base_url: str, page_number: int):
        # Build URL — strip any existing P= param then re-append
        clean = re.sub(r"[&?]P=\d+", "", base_url).rstrip("&")
        sep   = "&" if "?" in clean else "?"
        url   = f"{clean}{sep}P={page_number}" if page_number > 1 else clean

        logger.info(f"[CZA] 📄 Page {page_number}: {url}")
        self.driver.get(url)

        # Wait for at least one card
        try:
            WebDriverWait(self.driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, CARD_SEL))
            )
        except Exception:
            logger.warning(f"[CZA] ⏳ Cards did not appear within 25 s on page {page_number}.")
            _dump_html(self.driver, page_number)
            return [], False

        # Extra settle time for React hydration + lazy images
        time.sleep(3)
        _scroll(self.driver, times=4, gap=1.0)

        cards = self.driver.find_elements(By.CSS_SELECTOR, CARD_SEL)
        if not cards:
            logger.warning(f"[CZA] ❌ No cards on page {page_number} after scroll.")
            _dump_html(self.driver, page_number)
            return [], False

        logger.info(f"[CZA] ✔ {len(cards)} cards found on page {page_number}")

        cars = []
        for card in cards:
            try:
                # Nav URL — the card itself is the <a>
                nav_url = _attr(card, "href")
                if not nav_url:
                    logger.debug("[CZA] Card has no href — skipping.")
                    continue
                if not nav_url.startswith("http"):
                    nav_url = BASE + nav_url

                # stock_id from numeric segment in URL path
                stock_id = None
                m = re.search(r"/(\d{6,})/", nav_url)
                if m:
                    stock_id = m.group(1)

                # Core listing fields via stable data-cy hooks
                title        = _text(card, "h3.cy-result-title")
                variant      = _text(card, '[data-cy="cy-result-variant"]')
                price        = _text(card, "h3.vehicle-price")
                year_str     = _text(card, '[data-cy="vehicle-spec-year"] span')
                mileage      = _text(card, '[data-cy="vehicle-spec-mileage"] span')
                transmission = _text(card, '[data-cy="vehicle-spec-transmission"] span')
                fuel_type    = _text(card, '[data-cy="vehicle-spec-fuel-type"] span')

                # Images — main + thumbnails
                image_urls = []
                main_img = _attr_from_sel(
                    card, "img.VehicleCard_mainImage__xjSlM", "src", "data-src"
                )
                if main_img:
                    image_urls.append(main_img)
                for thumb in card.find_elements(
                    By.CSS_SELECTOR, "div.VehicleCard_thumbs__iM8Co img"
                ):
                    src = _attr(thumb, "src", "data-src")
                    if src and src not in image_urls:
                        image_urls.append(src)

                # Parse year to int
                year = None
                if year_str:
                    ym = re.search(r"\b(19|20)\d{2}\b", year_str)
                    year = int(ym.group()) if ym else None

                logger.debug(
                    f"[CZA] card: id={stock_id} title={title!r} "
                    f"price={price!r} mileage={mileage!r} year={year}"
                )

                cars.append({
                    "stock_id":      stock_id,
                    "navigationUrl": nav_url,
                    "title":         title or "",
                    "variant":       variant,
                    "price":         price,
                    "year":          year,
                    "mileage":       mileage,
                    "transmission":  transmission,
                    "fuelType":      fuel_type,
                    "imageUrls":     image_urls,
                    "sourcePage":    page_number,
                    "listingSource": "carsza",
                })

            except Exception as e:
                logger.warning(f"[CZA] ⚠️ Card parse error: {e}")

        logger.info(f"[CZA] ✅ Extracted {len(cars)} cars from page {page_number}")
        return cars, True

    # ── Detail page ───────────────────────────────────────────────────────────

    def scrape_detail_page(self, car: dict) -> dict:
        url = car.get("navigationUrl")
        if not url:
            return car

        logger.info(f"[CZA] 🔎 Detail: {url}")
        self.driver.get(url)

        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                    "dl, table, "
                    "[class*='spec'], [class*='Spec'], "
                    "[class*='detail'], [class*='Detail'], "
                    "[data-cy]"
                ))
            )
        except Exception:
            logger.warning(f"[CZA] ⚠️ Detail page slow for {car.get('stock_id')} — reading anyway.")

        time.sleep(2)

        # Price fallback
        if not car.get("price"):
            car["price"] = (
                _text(self.driver, "h3.vehicle-price")
                or _text(self.driver, "[class*='price']")
            )

        # Build flat spec map and pull fields
        spec_map = _build_spec_map(self.driver)
        logger.debug(f"[CZA] spec_map ({len(spec_map)} keys): {list(spec_map.keys())[:20]}")

        def gs(*labels):
            for lbl in labels:
                val = spec_map.get(lbl.lower())
                if val:
                    return val
            return None

        car.update({
            "transmission": car.get("transmission") or gs("transmission", "gearbox"),
            "fuelType":     car.get("fuelType")     or gs("fuel type", "fuel"),
            "bodyType":     gs("body type", "body"),
            "color":        gs("colour", "color", "exterior colour", "exterior color"),
            "engineSize":   gs("engine size", "engine capacity", "displacement", "cc"),
            "mileage":      car.get("mileage")       or gs("mileage", "km", "odometer"),
            "doors":        gs("doors", "number of doors"),
            "variant":      car.get("variant")       or gs("variant", "derivative"),
            "dealerName":   gs("dealer", "seller", "dealership", "dealer name"),
            "province":     gs("province", "region"),
            "city":         gs("city", "town", "location"),
            "year":         car.get("year")          or gs("year", "model year"),
            "make":         gs("make"),
            "model":        gs("model"),
            "condition":    gs("condition") or "Used",
        })

        # Extra images from detail gallery
        if len(car.get("imageUrls", [])) < 2:
            imgs = []
            for img in self.driver.find_elements(By.TAG_NAME, "img"):
                src = _attr(img, "src", "data-src")
                if src and src.startswith("http") and "img-ik.cars.co.za" in src and src not in imgs:
                    imgs.append(src)
            if imgs:
                car["imageUrls"] = imgs

        return car
