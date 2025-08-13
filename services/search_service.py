from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import logging
import time
from config import settings
from providers.firecrawl_provider import search_firecrawl

logger = logging.getLogger(__name__)


def _provider_queries(speaker: str) -> List[str]:
    return [entry["query"](speaker) for entry in settings.SEARCH_PROVIDERS]


def search_sources_concurrently(speaker: str) -> List[Dict]:
    queries = _provider_queries(speaker)
    results: List[Dict] = []

    logger.info("Search starting: %d queries -> %s", len(queries), queries)
    print(f"[SEARCH] Starting {len(queries)} queries: {queries}", flush=True)

    def _run_query(q: str) -> List[Dict]:
        t0 = time.perf_counter()
        try:
            print(f"[SEARCH] Firecrawl CALL query='{q}'", flush=True)
            data = search_firecrawl(q) or []
            # annotate results with minimal provenance to verify multi-source processing
            for item in data:
                item.setdefault("_meta", {})
                item["_meta"]["query"] = q
                item["_meta"]["provider"] = "firecrawl"
            dt = round((time.perf_counter() - t0) * 1000, 2)
            logger.info("Search done: provider=firecrawl query='%s' results=%d in %sms", q, len(data), dt)
            print(f"[SEARCH] Firecrawl DONE query='{q}' results={len(data)} in {dt}ms", flush=True)
            return data
        except Exception as e:
            dt = round((time.perf_counter() - t0) * 1000, 2)
            logger.exception("Search failed: provider=firecrawl query='%s' in %sms err=%s", q, dt, e)
            print(f"[SEARCH] Firecrawl ERROR query='{q}' in {dt}ms err={e}", flush=True)
            return []

    with ThreadPoolExecutor(max_workers=min(settings.MAX_WORKERS if hasattr(settings, 'MAX_WORKERS') else 8, len(queries) or 1)) as executor:
        future_map = {executor.submit(_run_query, q): q for q in queries}
        try:
            for future in as_completed(future_map, timeout=settings.SEARCH_TIMEOUT_SEC):
                q = future_map[future]
                try:
                    data = future.result()
                    if not data:
                        logger.info("No results: query='%s'", q)
                        print(f"[SEARCH] No results for query='{q}'", flush=True)
                        continue
                    results.extend(data)
                except Exception as e:
                    logger.exception("Future failed: query='%s' err=%s", q, e)
                    print(f"[SEARCH] Future failed query='{q}' err={e}", flush=True)
        except Exception as e:
            logger.exception("Search concurrency error: %s", e)
            print(f"[SEARCH] Concurrency error: {e}", flush=True)

    logger.info("Search finished: total_results=%d unique_queries=%d", len(results), len(queries))
    print(f"[SEARCH] Finished: total_results={len(results)} unique_queries={len(queries)}", flush=True)
    return results


def combine_markdown(results: List[Dict]) -> str:
    combined = []
    for r in results:
        content = r.get('markdown') or r.get('content', '')
        if content:
            combined.append(f"Source: {r.get('url', 'N/A')}\nContent: {content}\n")
    return "\n\n".join(combined)
