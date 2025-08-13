from flask import Blueprint, request, jsonify, Response, g
import json
import logging
from services.search_service import search_sources_concurrently, combine_markdown
from services.extract_service import extract_events
from utils.dedupe import dedupe_events

api_bp = Blueprint("api", __name__)
logger = logging.getLogger(__name__)


@api_bp.route("/events", methods=["GET"])
def get_events():
    speaker_name = request.args.get("speaker_name")
    if not speaker_name:
        return jsonify({"error": "speaker_name parameter is required"}), 400

    logger.info("[%s] Searching events for: %s", getattr(g, 'request_id', '-'), speaker_name)

    try:
        # Run provider searches concurrently
        print(f"[ROUTE] Starting search for speaker: {speaker_name}", flush=True)
        raw_results = search_sources_concurrently(speaker_name)
        logger.info("[%s] Provider raw results: count=%d", getattr(g, 'request_id', '-'), len(raw_results))
        print(f"[ROUTE] Provider raw results: count={len(raw_results)}", flush=True)
        combined_content = combine_markdown(raw_results)
        logger.info("[%s] Combined content size: %d chars", getattr(g, 'request_id', '-'), len(combined_content))
        print(f"[ROUTE] Combined content size: {len(combined_content)} chars", flush=True)
        if not combined_content.strip():
            return jsonify([])

        # Extract events with LLM
        print(f"[ROUTE] Starting LLM extraction", flush=True)
        events = extract_events(speaker_name, combined_content)
        # Dedupe and return
        events = dedupe_events(events)
        logger.info("[%s] Final events: %d", getattr(g, 'request_id', '-'), len(events))
        print(f"[ROUTE] Final events: {len(events)}", flush=True)
        return Response(json.dumps(events), mimetype="application/json")
    except Exception as e:
        logger.error("[%s] Unexpected error: %s", getattr(g, 'request_id', '-'), e, exc_info=True)
        return jsonify({"error": "internal_error"}), 500
