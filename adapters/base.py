"""
Base adapter interface.
All site adapters must subclass SiteAdapter and implement:
  - scrape_listing_page(base_url, page_number) → (list[dict], bool)
  - scrape_detail_page(car)                    → dict
"""

import time
from abc import ABC, abstractmethod
from selenium import webdriver


class SiteAdapter(ABC):
    """
    One subclass per car site.

    scrape_listing_page  → returns (cars_on_page: list[dict], has_results: bool)
    scrape_detail_page   → enriches a raw car dict in-place, returns it
    """

    site_name: str = "base"

    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver

    @abstractmethod
    def scrape_listing_page(self, base_url: str, page_number: int) -> tuple[list[dict], bool]:
        """Return (cars_on_page, has_results). has_results=False stops pagination."""
        ...

    @abstractmethod
    def scrape_detail_page(self, car: dict) -> dict:
        """Visit the detail page, enrich `car` in-place, return it."""
        ...

    def scroll_page(self, times: int = 3, gap: float = 1.2):
        for _ in range(times):
            self.driver.execute_script("window.scrollBy(0, 1200);")
            time.sleep(gap)
        self.driver.execute_script("window.scrollTo(0, 0);")
        time.sleep(1)
