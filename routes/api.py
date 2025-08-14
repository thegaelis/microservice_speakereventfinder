# Event search API routes
# Simple REST API for finding speaker events
from flask import Blueprint, request, jsonify, Response, g
import json
import logging
from config import settings
from services.search_service import search_sources_concurrently
from services.extract_service import extract_events_in_batches
from utils.dedupe import dedupe_events

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)


@api_bp.route("/events", methods=["GET"])
def get_events():
    # Main endpoint: GET /api/v1/events
    # Query Parameters:
    # - speaker_name: Name of the speaker (required)
    # - event_type: Filter by "online" or "in-person" (optional)
    # - sort: Sort order "asc" or "desc" by date (optional, default: asc)
    # Returns: JSON array of events with format:
    # [{"event_name", "date", "location", "url", "speakers", "event_type"}]
    
    # Extract and validate input parameters
    speaker_name = request.args.get("speaker_name")
    event_type = request.args.get("event_type")  # "online", "in-person", or None (all)
    sort_order = request.args.get("sort", "asc")  # "asc" (default) or "desc"
    
    # Input validation following microservice best practices
    validation_error = _validate_input(speaker_name, event_type, sort_order)
    if validation_error:
        return validation_error

    logger.info("[%s] Searching events for: %s (type: %s, sort: %s)", 
                getattr(g, 'request_id', '-'), speaker_name, event_type or "all", sort_order)

    try:
        # Execute search workflow
        events = _execute_search_workflow(speaker_name, event_type, sort_order)
        
        logger.info("[%s] Final events: %d", getattr(g, 'request_id', '-'), len(events))
        print(f"[ROUTE] Final events: {len(events)}", flush=True)
        
        # Return clean JSON response
        return Response(json.dumps(events), mimetype="application/json")
        
    except Exception as e:
        logger.error("[%s] Unexpected error: %s", getattr(g, 'request_id', '-'), e, exc_info=True)
        return jsonify({"error": "internal_error"}), 500


def _validate_input(speaker_name: str, event_type: str, sort_order: str):
    # Validate input parameters and return error response if invalid
    if not speaker_name:
        return jsonify({"error": "speaker_name parameter is required"}), 400
    
    if not speaker_name.strip():
        return jsonify({"error": "speaker_name cannot be empty"}), 400
        
    if len(speaker_name) > 100:
        return jsonify({"error": "speaker_name too long (max 100 chars)"}), 400
    
    if event_type and event_type not in ["online", "in-person"]:
        return jsonify({"error": "event_type must be 'online' or 'in-person'"}), 400
        
    if sort_order not in ["asc", "desc"]:
        return jsonify({"error": "sort must be 'asc' or 'desc'"}), 400
    
    return None


def _execute_search_workflow(speaker_name: str, event_type: str, sort_order: str) -> list:
    # Execute the complete search workflow: search -> extract -> dedupe
    # Step 1: Search multiple sources concurrently
    print(f"[ROUTE] Starting search for speaker: {speaker_name}", flush=True)
    raw_results = search_sources_concurrently(speaker_name, event_type)
    logger.info("[%s] Provider raw results: count=%d", getattr(g, 'request_id', '-'), len(raw_results))
    print(f"[ROUTE] Provider raw results: count={len(raw_results)}", flush=True)
    
    if not raw_results:
        return []

    # Step 2: Extract events using batch LLM processing
    print(f"[ROUTE] Starting batch LLM extraction", flush=True)
    events = extract_events_in_batches(speaker_name, raw_results, event_type, sort_order)
    
    # Step 3: Deduplicate events across sources
    events = dedupe_events(events)
    
    return events
