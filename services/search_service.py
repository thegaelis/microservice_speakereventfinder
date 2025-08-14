# Search service for concurrent source searching
# Implements efficient multi-threaded search across multiple providers
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
import logging
import time
from config import settings
from providers.firecrawl_provider import search_firecrawl

logger = logging.getLogger(__name__)


def search_sources_concurrently(speaker: str, event_type: str = None) -> List[Dict]:
    # Search multiple sources concurrently for speaker events
    # Args:
    #   speaker: Name of the speaker to search for
    #   event_type: Filter by event type ("online" or "in-person")
    # Returns:
    #   List of raw search results from all providers
    
    queries = _generate_search_queries(speaker, event_type)
    results: List[Dict] = []

    search_strategy = "targeted" if (event_type and settings.ENABLE_TARGETED_SEARCH) else "general"
    logger.info("Search starting: %d queries -> %s (strategy: %s)", len(queries), queries, search_strategy)
    print(f"[SEARCH] Starting {len(queries)} queries: {queries} (strategy: {search_strategy})", flush=True)

    # Execute searches in parallel using thread pool
    with ThreadPoolExecutor(max_workers=min(settings.MAX_WORKERS, len(queries) or 1)) as executor:
        future_map = {executor.submit(_execute_single_search, q): q for q in queries}
        
        try:
            # Collect results as they complete
            for future in as_completed(future_map, timeout=settings.SEARCH_TIMEOUT_SEC):
                query = future_map[future]
                try:
                    data = future.result()
                    if data:
                        results.extend(data)
                    else:
                        logger.info("No results: query='%s'", query)
                except Exception as e:
                    logger.exception("Query failed: query='%s' err=%s", query, e)
                    print(f"[SEARCH] Query FAILED query='{query}' err={e}", flush=True)
                    
        except Exception as e:
            logger.exception("Search timeout or error: %s", e)
            print(f"[SEARCH] TIMEOUT or ERROR: {e}", flush=True)

    logger.info("Search finished: total_results=%d unique_queries=%d", len(results), len(set(future_map.values())))
    print(f"[SEARCH] Finished: total_results={len(results)} unique_queries={len(set(future_map.values()))}", flush=True)
    return results


def _generate_search_queries(speaker: str, event_type: str = None) -> List[str]:
    # Generate targeted search queries based on event type
    if event_type and settings.ENABLE_TARGETED_SEARCH:
        # Use targeted queries when event_type is specified
        return [entry["query_with_type"](speaker, event_type) for entry in settings.SEARCH_PROVIDERS if "query_with_type" in entry]
    else:
        # Use general queries
        return [entry["query"](speaker) for entry in settings.SEARCH_PROVIDERS]


def _execute_single_search(query: str) -> List[Dict]:
    # Execute a single search query and return results with metadata
    start_time = time.perf_counter()
    
    try:
        print(f"[SEARCH] Firecrawl CALL query='{query}'", flush=True)
        
        # Execute search using Firecrawl provider
        data = search_firecrawl(query) or []
        
        # Add metadata for provenance tracking
        for item in data:
            item.setdefault("_meta", {})
            item["_meta"]["query"] = query
            item["_meta"]["provider"] = "firecrawl"
        
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.info("Search done: provider=firecrawl query='%s' results=%d in %sms", query, len(data), elapsed_ms)
        print(f"[SEARCH] Firecrawl DONE query='{query}' results={len(data)} in {elapsed_ms}ms", flush=True)
        
        return data
        
    except Exception as e:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        logger.exception("Search failed: provider=firecrawl query='%s' in %sms err=%s", query, elapsed_ms, e)
        print(f"[SEARCH] Firecrawl ERROR query='{query}' in {elapsed_ms}ms err={e}", flush=True)
        return []


def simple_combine_markdown(raw_results: List[Dict]) -> str:
    # Simple combination of all markdown content from search results
    content = []
    for result in results:
        md = result.get("markdown") or ""
        if not md.strip():
            continue
        query = result.get("_meta", {}).get("query", "N/A")
        content.append(f"Source: {query}")
        content.append(f"Content: {md}")
        content.append("---")
    return "\n".join(content)


def smart_combine_markdown(results: List[Dict], max_chars: int = None, speaker_name: str = None) -> str:
    # Intelligent content combination with accuracy-focused truncation
    # Optimized for OpenAI 128k token limit with priority-based source selection
    # Args:
    #   results: List of search results with markdown content
    #   max_chars: Maximum characters allowed in combined content
    #   speaker_name: Speaker name for prioritizing relevant content
    # Returns:
    #   Combined markdown content optimized for LLM processing
    
    if not max_chars:
        return simple_combine_markdown(results)
    
    # Sort sources by relevance and quality
    sorted_results = _prioritize_sources_by_accuracy(results, speaker_name)
    
    # Build content while respecting token limits
    content = []
    total_chars = 0
    sources_included = 0
    source_types = set()  # Track diversity of sources
    speaker_mentions = 0  # Track sources with explicit speaker mentions
    
    for result in sorted_results:
        md = result.get("markdown") or ""
        if not md.strip():
            continue
            
        query = result.get("_meta", {}).get("query", "N/A")
        source_type = query.split()[0] if " " in query else "general"
        source_block = f"Source: {query}\nContent: {md}\n---\n"
        
        # Check for explicit speaker mention
        has_speaker_mention = speaker_name and speaker_name.lower() in md.lower()
        if has_speaker_mention:
            speaker_mentions += 1
        
        # Check if adding this source would exceed limit
        if total_chars + len(source_block) > max_chars and sources_included > 0:
            # Try to include important sources with truncation
            remaining_chars = max_chars - total_chars - 400  # Reserve for truncation notice
            if remaining_chars > 3000 and (has_speaker_mention or source_type not in source_types):
                truncated_md = md[:remaining_chars] + f"\n[SOURCE TRUNCATED FOR TOKEN LIMIT - Speaker mentioned: {has_speaker_mention}]"
                content.append(f"Source: {query}")
                content.append(f"Content: {truncated_md}")
                content.append("---")
                sources_included += 1
                source_types.add(source_type)
                if has_speaker_mention:
                    speaker_mentions += 1
                break
            else:
                # Add summary of what was omitted
                omitted_sources = len(sorted_results) - sources_included
                content.append(f"\n[CONTENT OPTIMIZED FOR ACCURACY - {omitted_sources} additional sources omitted, {speaker_mentions} sources with explicit speaker mentions included]")
                break
            
        content.append(f"Source: {query}")
        content.append(f"Content: {md}")
        content.append("---")
        total_chars += len(source_block)
        sources_included += 1
        source_types.add(source_type)
    
    result = "\n".join(content)
    diversity_score = len(source_types)
    print(f"[COMBINE] Accuracy-focused truncation: {len(sorted_results)} sources → {sources_included} included, {len(result)} chars, {diversity_score} source types, {speaker_mentions} speaker mentions", flush=True)
    return result


def _prioritize_sources_by_accuracy(results: List[Dict], speaker_name: str = None) -> List[Dict]:
    # Priority scoring for source accuracy and relevance
    # Prioritization criteria:
    # 1. Explicit speaker mentions (highest priority)
    # 2. Official sites and verified platforms
    # 3. Quality indicators (speaker, presenter, keynote)
    # 4. Content recency and specificity
    
    def get_source_priority(result):
        query = result.get("_meta", {}).get("query", "").lower()
        url = result.get("url", "").lower()
        content = result.get("markdown", "").lower()
        
        priority = 0
        
        # Highest priority: explicit speaker mention in content
        if speaker_name and speaker_name.lower() in content:
            priority += 10
            
        # High priority: official sites and verified platforms
        if "official" in query or any(domain in url for domain in [".com/events", "/calendar", "/schedule"]):
            priority += 5
        elif "eventbrite" in query or "meetup" in query:
            priority += 3
        elif "speaker bureau" in query or "confirmed" in query:
            priority += 4
            
        # Medium priority: quality indicators
        if any(indicator in content for indicator in ["speaker", "presenter", "keynote", "featured"]):
            priority += 2
            
        # Bonus for recent/specific content
        if any(term in content for term in ["2025", "2026", "upcoming"]):
            priority += 1
            
        return priority
    
    # Sort by priority (highest first), then by content length (longer first)
    return sorted(results, key=lambda r: (
        -get_source_priority(r),  # Higher priority first
        -len(r.get("markdown", ""))  # Longer content first within same priority
    ))
