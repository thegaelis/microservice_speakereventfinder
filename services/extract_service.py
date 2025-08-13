import json
import logging
from datetime import datetime, date
from typing import List, Dict
from collections import OrderedDict
from clients.factory import ClientFactory
from config import settings

logger = logging.getLogger(__name__)


def extract_events(speaker_name: str, combined_content: str) -> List[Dict]:
    client = ClientFactory.openai()
    if not client:
        return []

    today_str = date.today().strftime('%Y-%m-%d')
    prompt = f"""
    Based on the provided text, extract upcoming events where "{speaker_name}" is scheduled to speak.

    REQUIREMENTS:
    1. Today's date is {today_str}. Only include events on or after this date.
    2. The 'speakers' field must be an array containing at least "{speaker_name}".
    3. The 'date' field must be in YYYY-MM-DD format.
    4. If a specific date is not mentioned, do not include the event.
    5. Consolidate duplicate events from different sources into a single entry.

    Return ONLY a valid JSON object where the key is "events" and the value is a list of event objects.
    The fields in each event object MUST be in the EXACT order: event_name, date, location, url, speakers.
    If no events are found, return an empty list for the "events" key.

    CONTEXT:
    {combined_content}
    """

    try:
        # Log prompt preview (truncate to avoid huge logs)
        prompt_preview = (prompt[:1000] + "…") if len(prompt) > 1000 else prompt
        logger.info("LLM request: model=%s prompt_preview=%s", settings.OPENAI_MODEL, prompt_preview)
        print(f"[LLM] Request model={settings.OPENAI_MODEL} prompt_preview={prompt_preview}", flush=True)
        response = client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[{"role": "system", "content": prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )
        response_text = response.choices[0].message.content
        response_preview = (response_text[:500] + "…") if response_text and len(response_text) > 500 else response_text
        logger.info("LLM response: chars=%d preview=%s", len(response_text or ""), response_preview)
        print(f"[LLM] Response chars={len(response_text or '')} preview={response_preview}", flush=True)
        data = json.loads(response_text)
        events = data.get("events", [])

        # Filter for future events and enforce order
        today = date.today()
        future_events = []
        for event in events:
            try:
                event_date_str = event.get("date")
                if event_date_str:
                    event_date = datetime.strptime(event_date_str, '%Y-%m-%d').date()
                    if event_date >= today:
                        future_events.append(event)
            except Exception:
                continue

        future_events.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'))

        ordered_events = []
        for event in future_events:
            ordered_event = OrderedDict()
            ordered_event["event_name"] = event.get("event_name")
            ordered_event["date"] = event.get("date")
            ordered_event["location"] = event.get("location")
            ordered_event["url"] = event.get("url")
            ordered_event["speakers"] = event.get("speakers", [speaker_name])
            ordered_events.append(ordered_event)
        logger.info("LLM parsed events: total=%d future=%d", len(events), len(ordered_events))
        print(f"[LLM] Parsed events: total={len(events)} future={len(ordered_events)}", flush=True)
        return ordered_events
    except Exception as e:
        logger.exception("LLM extraction failed: %s", e)
        print(f"[LLM] Extraction failed: {e}", flush=True)
        return []
