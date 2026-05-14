"""
Adapter: autotrader.co.za

Confirmed DOM structure (from live card HTML, 2025):
  • Cards are  <a aria-label="Listing Tile" class="b-result-tile__…">
    The hashed class suffix changes on every deploy — aria-label is the stable hook.
  • The card <a> IS the link (href is relative → prepend BASE)
  • Spec tags expose condition/mileage/transmission/fuel via the  title=""  attribute
    — far more reliable than inner text which may contain &nbsp; entities
  • Pagination: append  ?page=N  (or &page=N when other params exist)

Card selector  :  a[aria-label="Listing Tile"]
Field selectors (relative to card):
  nav URL      →  card href  (+BASE prefix if relative)
  stock_id     →  last numeric path segment of href  e.g. /car-for-sale/.../28533908
  title        →  span[class*="e-make-model-title"]
  variant      →  span[class*="e-variant-title"]
  price        →  h2[class*="e-price__"]
  spec tags    →  span[class*="b-vehicle-spec-tag"]  → title attr
                  index 0 = condition, 1 = mileage, 2 = transmission, 3 = fuel type
  dealer name  →  span[class*="e-name__"]
  location     →  span[class*="e-suburb"]
  main image   →  span[class*="e-image-container"] img  (first match, src attr)
  thumbnails   →  span[class*="e-bottom-section"] img   (src attr)
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

BASE     = "https://www.autotrader.co.za"
CARD_SEL = 'a[aria-label="Listing Tile"]'


# ── Low-level helpers ─────────────────────────────────────────────────────────

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
    """Find element by CSS selector, then return first non-empty attribute."""
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
        fname = f"logs/autotrader_debug_page{page_number}.html"
        with open(fname, "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        logger.info(f"[AT] 💾 HTML dumped → {fname}")
    except Exception as e:
        logger.warning(f"[AT] Could not dump HTML: {e}")


def _build_spec_map(driver) -> dict:
    """
    Scrape the detail page for label→value pairs.
    Handles dt/dd, table rows, and paired div siblings.
    Returns {lowercase_label: value}.
    """
    spec_map = {}

    # Pattern 1: dt/dd
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

    # Pattern 2: table rows (th/td or td/td)
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

    # Pattern 3: paired sibling divs label/value
    try:
        for lbl_el in driver.find_elements(
            By.CSS_SELECTOR,
            "[class*='label'], [class*='Label'], [class*='key'], [class*='Key']"
        ):
            try:
                val_el = lbl_el.find_element(
                    By.XPATH,
                    "following-sibling::*["
                    "contains(@class,'value') or contains(@class,'Value') or "
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

    # Pattern 4: AutoTrader-specific spec tags on detail page (same title= pattern)
    try:
        for tag in driver.find_elements(By.CSS_SELECTOR, "[class*='b-vehicle-spec-tag']"):
            title_val = _attr(tag, "title")
            text_val  = tag.text.strip()
            val       = title_val or text_val
            if val and " km" in val.lower():
                spec_map.setdefault("mileage", val)
            elif val in ("Automatic", "Manual", "Semi-Automatic", "CVT"):
                spec_map.setdefault("transmission", val)
            elif val in ("Petrol", "Diesel", "Electric", "Hybrid", "LPG"):
                spec_map.setdefault("fuel type", val)
    except Exception:
        pass

    return spec_map


# ── Adapter ───────────────────────────────────────────────────────────────────

class AutoTraderAdapter(SiteAdapter):
    site_name = "autotrader"

    # ── Listing page ──────────────────────────────────────────────────────────

    def scrape_listing_page(self, base_url: str, page_number: int):
        # Pagination: strip any existing page= param then re-append
        clean = re.sub(r"[&?]page=\d+", "", base_url).rstrip("&")
        sep   = "&" if "?" in clean else "?"
        url   = f"{clean}{sep}page={page_number}" if page_number > 1 else clean

        logger.info(f"[AT] 📄 Page {page_number}: {url}")
        self.driver.get(url)

        # Wait for at least one card
        try:
            WebDriverWait(self.driver, 25).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, CARD_SEL))
            )
        except Exception:
            logger.warning(f"[AT] ⏳ No cards within 25 s on page {page_number}.")
            _dump_html(self.driver, page_number)
            return [], False

        time.sleep(3)
        _scroll(self.driver, times=4, gap=1.0)

        cards = self.driver.find_elements(By.CSS_SELECTOR, CARD_SEL)
        if not cards:
            logger.warning(f"[AT] ❌ No cards after scroll on page {page_number}.")
            _dump_html(self.driver, page_number)
            return [], False

        logger.info(f"[AT] ✔ {len(cards)} cards on page {page_number}")

        cars = []
        for card in cards:
            try:
                # ── Nav URL ───────────────────────────────────────────────────
                href = _attr(card, "href")
                if not href:
                    logger.debug("[AT] Card has no href — skipping.")
                    continue
                nav_url = href if href.startswith("http") else BASE + href

                # ── stock_id — last numeric segment of path ───────────────────
                stock_id = None
                m = re.search(r"/(\d{5,})(?:/|$)", nav_url)
                if m:
                    stock_id = m.group(1)

                # ── Core listing fields ───────────────────────────────────────
                title   = _text(card, "[class*='e-make-model-title']")
                variant = _text(card, "[class*='e-variant-title']")
                price   = _text(card, "h2[class*='e-price__']")

                # Specs via title attribute (most reliable)
                spec_tags = card.find_elements(
                    By.CSS_SELECTOR, "[class*='b-vehicle-spec-tag']"
                )
                spec_titles = [_attr(t, "title") or t.text.strip() for t in spec_tags]

                condition    = spec_titles[0] if len(spec_titles) > 0 else None
                mileage      = spec_titles[1] if len(spec_titles) > 1 else None
                transmission = spec_titles[2] if len(spec_titles) > 2 else None
                fuel_type    = spec_titles[3] if len(spec_titles) > 3 else None

                # ── Dealer / location ─────────────────────────────────────────
                dealer_name = _text(card, "[class*='e-name__']")
                location    = _text(card, "[class*='e-suburb']")

                # Parse city/suburb (format: "Midridge Park, Midrand")
                city = None
                if location:
                    parts = [p.strip() for p in location.split(",")]
                    city  = parts[-1] if parts else location

                # ── Year from title ───────────────────────────────────────────
                year = None
                if title:
                    ym = re.search(r"\b(19|20)\d{2}\b", title)
                    year = int(ym.group()) if ym else None

                # ── Images ────────────────────────────────────────────────────
                image_urls = []

                # Main hero image
                main_img = _attr_from_sel(
                    card, "[class*='e-image-container'] img", "src", "data-src"
                )
                if main_img and main_img.startswith("http"):
                    image_urls.append(main_img)

                # Thumbnail strip at bottom of card
                try:
                    for thumb in card.find_elements(
                        By.CSS_SELECTOR, "[class*='e-bottom-section'] img"
                    ):
                        src = _attr(thumb, "src", "data-src")
                        if src and src.startswith("http") and src not in image_urls:
                            image_urls.append(src)
                except Exception:
                    pass

                logger.debug(
                    f"[AT] card: id={stock_id} title={title!r} "
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
                    "condition":     condition,
                    "dealerName":    dealer_name,
                    "city":          city,
                    "location":      location,
                    "imageUrls":     image_urls,
                    "sourcePage":    page_number,
                    "listingSource": "autotrader",
                })

            except Exception as e:
                logger.warning(f"[AT] ⚠️ Card parse error: {e}")

        logger.info(f"[AT] ✅ Extracted {len(cars)} cars from page {page_number}")
        return cars, True

    # ── Detail page ───────────────────────────────────────────────────────────

    def scrape_detail_page(self, car: dict) -> dict:
        url = car.get("navigationUrl")
        if not url:
            return car

        logger.info(f"[AT] 🔎 Detail: {url}")
        self.driver.get(url)

        try:
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,
                    "dl, table, "
                    "[class*='spec'], [class*='Spec'], "
                    "[class*='detail'], [class*='Detail'], "
                    "[class*='b-vehicle-spec']"
                ))
            )
        except Exception:
            logger.warning(f"[AT] ⚠️ Detail page slow for {car.get('stock_id')} — reading anyway.")

        time.sleep(2)

        # Price fallback
        if not car.get("price"):
            car["price"] = _text(self.driver, "h2[class*='e-price__']")

        # Build spec map and pull fields
        spec_map = _build_spec_map(self.driver)
        logger.debug(f"[AT] spec_map ({len(spec_map)} keys): {list(spec_map.keys())[:20]}")

        def gs(*labels):
            for lbl in labels:
                val = spec_map.get(lbl.lower())
                if val:
                    return val
            return None

        car.update({
            "transmission": car.get("transmission") or gs("transmission", "gearbox"),
            "fuelType":     car.get("fuelType")     or gs("fuel type", "fuel"),
            "bodyType":     gs("body type", "body style", "body"),
            "color":        gs("colour", "color", "exterior colour", "exterior color"),
            "engineSize":   gs("engine size", "engine capacity", "displacement", "cc"),
            "mileage":      car.get("mileage")       or gs("mileage", "km", "odometer"),
            "doors":        gs("doors", "number of doors"),
            "variant":      car.get("variant")       or gs("variant", "derivative"),
            "dealerName":   car.get("dealerName")    or gs("dealer", "seller", "dealership"),
            "province":     gs("province", "region"),
            "city":         car.get("city")          or gs("city", "town"),
            "year":         car.get("year")          or gs("year", "model year"),
            "make":         gs("make"),
            "model":        gs("model"),
            "condition":    car.get("condition")     or gs("condition") or "Used",
        })

        # Extra images from detail gallery
        if len(car.get("imageUrls", [])) < 2:
            imgs = []
            for img in self.driver.find_elements(By.TAG_NAME, "img"):
                src = _attr(img, "src", "data-src")
                if (
                    src
                    and src.startswith("http")
                    and "img.autotrader.co.za" in src
                    and src not in imgs
                ):
                    imgs.append(src)
            if imgs:
                car["imageUrls"] = imgs

        return car