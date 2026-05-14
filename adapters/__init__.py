"""
Adapter registry.

To add a new site:
  1. Create  adapters/<sitename>.py  with a SiteAdapter subclass
  2. Import it here and add an entry to ADAPTERS
  3. Add  "site": "<sitename>"  to the Firestore target config

That's it — main.py never needs to change.
"""

import logging
from selenium import webdriver

from .base import SiteAdapter
from .webuycars import WeBuyCarsAdapter
from .carsza import CarsDotCoZaAdapter
from .autotrader import AutoTraderAdapter   # stub — uncomment when ready

logger = logging.getLogger(__name__)

# ── Registry ──────────────────────────────────────────────────────────────────
# key  = value of "site" field in Firestore target config
# value = adapter class (not instance)

ADAPTERS: dict[str, type[SiteAdapter]] = {
    # "webuycars": WeBuyCarsAdapter,   # muted — working but not needed right now
    "carsza":      CarsDotCoZaAdapter,
    # "autotrader":  AutoTraderAdapter,  # uncomment when implemented
}


def get_adapter(site: str, driver: webdriver.Chrome) -> SiteAdapter | None:
    cls = ADAPTERS.get(site.lower())
    if not cls:
        logger.error(
            f"❌ No adapter registered for site '{site}'. "
            f"Available: {list(ADAPTERS.keys())}"
        )
        return None
    return cls(driver)
