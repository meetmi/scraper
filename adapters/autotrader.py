"""
Adapter: autotrader.co.za  (stub — not yet implemented)

To implement:
1. Find the card selector on the listing page (open DevTools → Inspector)
2. Note the pagination pattern in the URL
3. Implement scrape_listing_page and scrape_detail_page below
4. Register in adapters/__init__.py:  "autotrader": AutoTraderAdapter

Typical starting point:
  URL: https://www.autotrader.co.za/cars-for-sale?...
  Pagination: usually ?pagenumber=2 or &page=2
"""

import logging
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from .base import SiteAdapter

logger = logging.getLogger(__name__)


class AutoTraderAdapter(SiteAdapter):
    site_name = "autotrader"

    def scrape_listing_page(self, base_url: str, page_number: int):
        # TODO: implement
        # 1. Build paginated URL
        # 2. Wait for card selector
        # 3. Loop cards → extract fields → append to cars list
        # 4. Return (cars, has_results)
        raise NotImplementedError("AutoTrader adapter not yet implemented.")

    def scrape_detail_page(self, car: dict) -> dict:
        # TODO: implement
        # 1. self.driver.get(car["navigationUrl"])
        # 2. Wait for spec container
        # 3. Extract fields → car.update({...})
        # 4. Return car
        raise NotImplementedError("AutoTrader adapter not yet implemented.")
