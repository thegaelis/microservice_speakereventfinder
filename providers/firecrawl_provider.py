from typing import List, Dict
import logging
import time
from clients.factory import ClientFactory
from config import settings

logger = logging.getLogger(__name__)

def search_firecrawl(query: str) -> List[Dict]:
    fc = ClientFactory.firecrawl()
    if not fc:
        return []
    # Use Firecrawl Search with configured options
    params = {
        "pageOptions": {
            "fetchPageContent": True,
            "limit": settings.SEARCH_LIMIT,
        }
    }
    t0 = time.perf_counter()
    try:
        logger.info("Provider call: firecrawl query='%s' params=%s", query, params)
        print(f"[PROVIDER] Firecrawl CALL query='{query}' params={params}", flush=True)
        data = fc.search(query=query, params=params)
        dt = round((time.perf_counter() - t0) * 1000, 2)
        logger.info("Provider result: firecrawl query='%s' count=%d in %sms", query, len(data or []), dt)
        print(f"[PROVIDER] Firecrawl RESULT count={len(data or [])} in {dt}ms", flush=True)
        return data
    except Exception as e:
        dt = round((time.perf_counter() - t0) * 1000, 2)
        logger.exception("Provider error: firecrawl query='%s' in %sms err=%s", query, dt, e)
        print(f"[PROVIDER] Firecrawl ERROR query='{query}' in {dt}ms err={e}", flush=True)
        return []
