from typing import List, Dict, Tuple


def _norm(s: str) -> str:
    return (s or "").strip().lower()


def _key(e: Dict) -> Tuple[str, str, str]:
    return (
        _norm(e.get("event_name")),
        _norm(e.get("date")),
        _norm(e.get("location")),
    )


def dedupe_events(events: List[Dict]) -> List[Dict]:
    seen = {}
    for e in events:
        k = _key(e)
        if k not in seen:
            seen[k] = e
        else:
            # Merge speakers and prefer non-empty url/location
            existing = seen[k]
            sp = set(existing.get("speakers") or []) | set(e.get("speakers") or [])
            existing["speakers"] = sorted(list(sp))
            if not existing.get("url") and e.get("url"):
                existing["url"] = e["url"]
            if not existing.get("location") and e.get("location"):
                existing["location"] = e["location"]
    return list(seen.values())
