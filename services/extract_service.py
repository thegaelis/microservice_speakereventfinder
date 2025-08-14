# Event extraction service using LLM
# Processes search results and extracts structured event data
import json
import logging
from datetime import datetime, date
from typing import List, Dict
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, as_completed
from clients.factory import ClientFactory
from config import settings

logger = logging.getLogger(__name__)


def extract_events(speaker_name: str, combined_content: str, event_type: str = None, sort_order: str = "asc") -> List[Dict]:
    # Extract events from content using OpenAI LLM
    # Args:
    #   speaker_name: Name of the speaker to search for
    #   combined_content: Combined markdown content from search results
    #   event_type: Filter by event type ("online" or "in-person")
    #   sort_order: Sort order for events ("asc" or "desc")
    # Returns:
    #   List of structured event dictionaries
    
    client = ClientFactory.openai()
    if not client:
        logger.error("OpenAI client not available")
        return []

    # Build LLM prompt with strict validation requirements
    prompt = _build_extraction_prompt(speaker_name, combined_content, event_type, sort_order)
    
    try:
        # Call OpenAI API for event extraction
        response = _call_openai_api(client, prompt)
        
        # Parse and validate the response
        events = _parse_and_validate_response(response, speaker_name, event_type, sort_order)
        
        logger.info("LLM parsed events: future=%d", len(events))
        print(f"[LLM] Parsed events: future={len(events)}", flush=True)
        
        return events
        
    except Exception as e:
        logger.exception("LLM extraction failed: %s", e)
        print(f"[LLM] Extraction failed: {e}", flush=True)
        return []


def _build_extraction_prompt(speaker_name: str, combined_content: str, event_type: str, sort_order: str) -> str:
    # Build the LLM prompt with validation requirements
    today_str = date.today().strftime('%Y-%m-%d')
    
    # Build event type filter instruction
    event_type_filter = ""
    if event_type == "online":
        event_type_filter = "\n6. Only include ONLINE/VIRTUAL events (exclude in-person events)."
    elif event_type == "in-person":
        event_type_filter = "\n6. Only include IN-PERSON events (exclude online/virtual events)."
    
    # Truncate content if too long to fit in context
    if len(combined_content) > settings.MAX_CONTENT_CHARS:
        combined_content = combined_content[:settings.MAX_CONTENT_CHARS] + "\n\n[FALLBACK TRUNCATION - CONTENT TOO LONG]"
        print(f"[LLM] Fallback truncation to {len(combined_content)} chars", flush=True)

    prompt = f"""
    Based on the provided text, extract upcoming events where "{speaker_name}" is EXPLICITLY MENTIONED as a speaker or presenter.

    CRITICAL VALIDATION REQUIREMENTS:
    1. TODAY'S DATE: {today_str}. Only include events on or after this date.
    2. SPEAKER VERIFICATION: "{speaker_name}" must be EXPLICITLY mentioned by name as a speaker, presenter, or featured participant in the event description.
    3. DATE FORMAT: The 'date' field must be in YYYY-MM-DD format.
    4. DATE REQUIREMENT: If a specific date is not clearly mentioned, do not include the event.
    5. DUPLICATE REMOVAL: Consolidate duplicate events from different sources into a single entry.{event_type_filter}
    6. EVENT TYPE STANDARDIZATION: 
       - Use ONLY 'online' for virtual/online/remote events
       - Use ONLY 'in-person' for physical/live/venue-based events
       - Do NOT use 'virtual' - convert it to 'online'
    7. SPEAKERS FIELD: Must be an array containing at least "{speaker_name}". Example: ["Tony Robbins"] NOT "Tony Robbins"
    8. ACCURACY CHECK: Only include events where you can clearly see "{speaker_name}" mentioned in the source content.
    9. NO ASSUMPTIONS: Do not infer or assume "{speaker_name}" is speaking if not explicitly stated.

    VERIFICATION PROCESS:
    - Before including any event, confirm "{speaker_name}" is explicitly named as a speaker/presenter
    - Verify the event has a clear future date
    - Ensure all required fields have accurate information from the source
    - Standardize event_type values: virtual → online, live/physical → in-person
    - Format speakers as array: ["Speaker Name"] not "Speaker Name"

    Return ONLY a valid JSON object where the key is "events" and the value is a list of event objects.
    The fields in each event object MUST be in the EXACT order: event_name, date, location, url, speakers, event_type.
    If no events are found, return an empty list for the "events" key.

    CONTEXT:
    {combined_content}
"""
    return prompt


def _call_openai_api(client, prompt: str) -> str:
    # Call OpenAI API with the extraction prompt
    # Log prompt preview (truncate for readability)
    prompt_preview = (prompt[:1000] + "…") if len(prompt) > 1000 else prompt
    logger.info("LLM request: model=%s prompt_preview=%s", settings.OPENAI_MODEL, prompt_preview)
    print(f"[LLM] Request model={settings.OPENAI_MODEL} prompt_preview={prompt_preview}", flush=True)
    
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[{"role": "system", "content": prompt}],
        temperature=0,  # Deterministic results for consistency
        response_format={"type": "json_object"}  # Ensure JSON response
    )
    
    response_text = response.choices[0].message.content
    response_preview = (response_text[:500] + "…") if response_text and len(response_text) > 500 else response_text
    logger.info("LLM response: chars=%d preview=%s", len(response_text or ""), response_preview)
    print(f"[LLM] Response chars={len(response_text or '')} preview={response_preview}", flush=True)
    
    return response_text


def _parse_and_validate_response(response: str, speaker_name: str, event_type: str = None, sort_order: str = "asc") -> List[Dict]:
    # Parse LLM response and validate/normalize event data
    data = json.loads(response)
    events = data.get("events", [])

    # Filter for future events and normalize data
    today = date.today()
    future_events = []
    
    print(f"[LLM] Processing {len(events)} raw events, today={today}", flush=True)
    
    for event in events:
        try:
            event_date_str = event.get("date")
            if event_date_str:
                event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
                print(f"[LLM] Event date: {event_date} vs today: {today}, future: {event_date >= today}", flush=True)
                if event_date >= today:
                    # Normalize event data
                    normalized_event = _normalize_event_data(event, speaker_name)
                    future_events.append(normalized_event)
                    print(f"[LLM] Added event: {event.get('event_name')} on {event_date}", flush=True)
        except Exception as e:
            print(f"[LLM] Skipped invalid event: {e}", flush=True)
            # Skip invalid events
            continue

    # Sort events by date
    reverse_sort = (sort_order == "desc")
    future_events.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'), reverse=reverse_sort)

    # Filter by event type if specified
    if event_type:
        future_events = [event for event in future_events if event.get("event_type") == event_type]
        print(f"[LLM] Filtered by event_type='{event_type}': {len(future_events)} events", flush=True)

    # Ensure consistent field order
    ordered_events = []
    for event in future_events:
        ordered_event = OrderedDict()
        ordered_event["event_name"] = event.get("event_name")
        ordered_event["date"] = event.get("date")
        ordered_event["location"] = event.get("location")
        ordered_event["url"] = event.get("url")
        ordered_event["speakers"] = event.get("speakers", [speaker_name])
        ordered_event["event_type"] = event.get("event_type", "unknown")
        ordered_events.append(ordered_event)
    
    return ordered_events


def _normalize_event_data(event: Dict, speaker_name: str = None) -> Dict:
    # Normalize event data for consistency
    # Normalize event_type values
    event_type_raw = event.get("event_type", "").lower()
    if event_type_raw in ["virtual", "remote", "webinar"]:
        event["event_type"] = "online"
    elif event_type_raw in ["live", "physical", "venue", "conference"]:
        event["event_type"] = "in-person"
    elif event_type_raw not in ["online", "in-person"]:
        # Guess based on location if unclear
        location = event.get("location", "").lower()
        if any(word in location for word in ["virtual", "online", "zoom", "webinar", "remote"]):
            event["event_type"] = "online"
        elif any(word in location for word in ["hotel", "center", "venue", "hall", "address"]):
            event["event_type"] = "in-person"
        else:
            event["event_type"] = "online"  # Default to online if unclear

    # Normalize speakers field to always be an array
    speakers = event.get("speakers")
    if isinstance(speakers, str):
        event["speakers"] = [speakers]
    elif not isinstance(speakers, list):
        event["speakers"] = [str(speakers)] if speakers else []
    
    return event


def extract_events_in_batches(speaker_name: str, search_results: List[Dict], event_type: str = None, sort_order: str = "asc") -> List[Dict]:
    # Extract events using batch processing for optimal LLM efficiency
    # Processes search results in small batches to:
    # 1. Stay within OpenAI token limits
    # 2. Parallelize LLM requests for speed
    # 3. Provide better error isolation
    # Args:
    #   speaker_name: Name of the speaker to search for
    #   search_results: Raw search results from multiple sources
    #   event_type: Filter by event type ("online" or "in-person")
    #   sort_order: Sort order for events ("asc" or "desc")
    # Returns:
    #   List of unique, validated events
    
    if not search_results:
        return []
    
    # Create batches for parallel processing
    batches = _create_source_batches(search_results)
    print(f"[BATCH] Processing {len(search_results)} sources in {len(batches)} batches (size={settings.LLM_BATCH_SIZE})", flush=True)
    
    # Process batches concurrently using thread pool
    all_events = _process_batches_concurrently(batches, speaker_name, event_type, sort_order)
    
    # Deduplicate and sort final results
    unique_events = _deduplicate_and_sort_events(all_events, sort_order)
    
    print(f"[BATCH] Final result: {len(unique_events)} unique events from {len(all_events)} total", flush=True)
    return unique_events


def _create_source_batches(search_results: List[Dict]) -> List[List[Dict]]:
    # Create batches of sources for processing
    batch_size = settings.LLM_BATCH_SIZE
    batches = []
    
    for i in range(0, len(search_results), batch_size):
        batch = search_results[i:i + batch_size]
        # Limit sources per batch to prevent token overflow
        if len(batch) > settings.MAX_SOURCES_PER_BATCH:
            batch = batch[:settings.MAX_SOURCES_PER_BATCH]
        batches.append(batch)
    
    return batches


def _process_batches_concurrently(batches: List[List[Dict]], speaker_name: str, event_type: str, sort_order: str) -> List[Dict]:
    # Process batches concurrently using thread pool
    all_events = []
    
    def process_single_batch(batch_idx: int, batch_sources: List[Dict]) -> List[Dict]:
        # Process a single batch of sources
        from services.search_service import smart_combine_markdown
        
        # Calculate char limit per batch (distribute total limit across batches)
        batch_char_limit = settings.MAX_CONTENT_CHARS // len(batches) if len(batches) > 1 else settings.MAX_CONTENT_CHARS
        
        # Combine content for this batch with smart truncation
        batch_content = smart_combine_markdown(batch_sources, batch_char_limit, speaker_name)
        
        print(f"[BATCH {batch_idx+1}/{len(batches)}] Processing {len(batch_sources)} sources, {len(batch_content)} chars", flush=True)
        
        # Extract events from this batch using LLM
        batch_events = extract_events(speaker_name, batch_content, event_type, sort_order)
        
        print(f"[BATCH {batch_idx+1}/{len(batches)}] Extracted {len(batch_events)} events", flush=True)
        return batch_events
    
    # Use thread pool for concurrent batch processing
    with ThreadPoolExecutor(max_workers=min(3, len(batches))) as executor:
        future_to_batch = {
            executor.submit(process_single_batch, idx, batch): idx 
            for idx, batch in enumerate(batches)
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_batch):
            batch_idx = future_to_batch[future]
            try:
                batch_events = future.result()
                all_events.extend(batch_events)
            except Exception as e:
                print(f"[BATCH {batch_idx+1}] Failed: {e}", flush=True)
                logger.exception("Batch processing failed for batch %d: %s", batch_idx, e)
    
    return all_events


def _deduplicate_and_sort_events(all_events: List[Dict], sort_order: str) -> List[Dict]:
    # Remove duplicates and sort events by date
    unique_events = []
    seen_events = set()
    
    for event in all_events:
        # Create unique key based on event name, date, and speakers
        event_key = (
            event.get("event_name", "").lower().strip(),
            event.get("date", ""),
            tuple(sorted(event.get("speakers", [])))
        )
        
        if event_key not in seen_events:
            seen_events.add(event_key)
            unique_events.append(event)
    
    # Final sort by date
    reverse_sort = (sort_order == "desc")
    unique_events.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'), reverse=reverse_sort)
    
    return unique_events
