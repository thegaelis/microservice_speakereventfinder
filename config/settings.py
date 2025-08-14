# Microservice configuration settings
# Centralized configuration following 12-factor app principles
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Dynamic year calculation for search queries
CURRENT_YEAR = datetime.now().year
NEXT_YEAR = CURRENT_YEAR + 1

# Flask application settings
JSON_SORT_KEYS = False  # Preserve field order in JSON responses
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
HOST = os.getenv("HOST", "0.0.0.0")  # Listen on all interfaces
PORT = int(os.getenv("PORT", "8345"))

# External service API keys
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # Lightweight model for efficiency

# Search performance settings - optimized for fast response times
SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "6"))  # Results per search query
SEARCH_TIMEOUT_SEC = int(os.getenv("SEARCH_TIMEOUT_SEC", "20"))  # Total search timeout

# Token management for OpenAI API
# OpenAI limit: 128k tokens ≈ 480k chars (1 token ≈ 3.75 chars)
# Reserve 20% for prompt/response overhead: 480k * 0.8 = 384k chars for content
MAX_CONTENT_CHARS = int(os.getenv("MAX_CONTENT_CHARS", "384000"))  # Stay within 128k token limit

# Concurrency settings for multi-threading
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "6"))  # Concurrent search threads
PROVIDER_TIMEOUT_SEC = int(os.getenv("PROVIDER_TIMEOUT_SEC", "15"))  # Individual provider timeout

# Batch processing configuration for LLM optimization
LLM_BATCH_SIZE = int(os.getenv("LLM_BATCH_SIZE", "3"))  # Sources per LLM request
MAX_SOURCES_PER_BATCH = int(os.getenv("MAX_SOURCES_PER_BATCH", "10"))  # Max sources in single batch

# Feature flags
ENABLE_TARGETED_SEARCH = os.getenv("ENABLE_TARGETED_SEARCH", "true").lower() == "true"  # Event-type specific queries

SEARCH_PROVIDERS = [
    # Provider sources - optimized for accuracy with stricter queries
    # Each provider entry describes a search intent. All are executed concurrently.
    {
        "name": "general",
        "query": lambda speaker: f'"{speaker}" upcoming speaking events {CURRENT_YEAR} {NEXT_YEAR} confirmed speaker',
        "query_with_type": lambda speaker, event_type: f'"{speaker}" upcoming {event_type} speaking events {CURRENT_YEAR} {NEXT_YEAR} confirmed speaker',
    },
    {
        "name": "eventbrite",
        "query": lambda speaker: f'site:eventbrite.com "{speaker}" speaker upcoming event conference {CURRENT_YEAR} {NEXT_YEAR}',
        "query_with_type": lambda speaker, event_type: f'site:eventbrite.com "{speaker}" {event_type} speaker event conference {CURRENT_YEAR} {NEXT_YEAR}',
    },
    {
        "name": "meetup",
        "query": lambda speaker: f'site:meetup.com "{speaker}" speaker event talk {CURRENT_YEAR} {NEXT_YEAR}',
        "query_with_type": lambda speaker, event_type: f'site:meetup.com "{speaker}" {event_type} speaker event talk {CURRENT_YEAR} {NEXT_YEAR}',
    },
    {
        "name": "official_site",
        "query": lambda speaker: f'"{speaker}" official website speaking schedule events calendar {CURRENT_YEAR} {NEXT_YEAR}',
        "query_with_type": lambda speaker, event_type: f'"{speaker}" official website {event_type} speaking schedule events calendar {CURRENT_YEAR} {NEXT_YEAR}',
    },
    {
        "name": "conferences",
        "query": lambda speaker: f'"{speaker}" keynote speaker conference summit {CURRENT_YEAR} {NEXT_YEAR} confirmed',
        "query_with_type": lambda speaker, event_type: f'"{speaker}" keynote speaker {event_type} conference summit {CURRENT_YEAR} {NEXT_YEAR} confirmed',
    },
    {
        "name": "speaker_bureau",
        "query": lambda speaker: f'"{speaker}" speaker bureau speaking engagements bookings {CURRENT_YEAR} {NEXT_YEAR}',
        "query_with_type": lambda speaker, event_type: f'"{speaker}" speaker bureau {event_type} speaking engagements bookings {CURRENT_YEAR} {NEXT_YEAR}',
    },
]

# Batch processing for LLM requests - cứ 3 nguồn thì gửi chung 1 LLM request
LLM_BATCH_SIZE = int(os.getenv("LLM_BATCH_SIZE", "3"))  # Process 3 sources per LLM request
MAX_SOURCES_PER_BATCH = int(os.getenv("MAX_SOURCES_PER_BATCH", "10"))  # Maximum sources in a single batch

# Batch processing for LLM requests
BATCH_SIZE_FOR_LLM = int(os.getenv("BATCH_SIZE_FOR_LLM", "3"))  # Process 3 sources per LLM request

# Feature flag to enable targeted search
ENABLE_TARGETED_SEARCH = os.getenv("ENABLE_TARGETED_SEARCH", "true").lower() == "true"  # Enabled by default
