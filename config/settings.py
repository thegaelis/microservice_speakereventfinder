import os
from dotenv import load_dotenv

# Load environment variables early
load_dotenv()

# App settings
JSON_SORT_KEYS = False
DEBUG = os.getenv("DEBUG", "true").lower() == "true"
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8345"))

# External services
FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# Search settings
SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", "5"))
SEARCH_TIMEOUT_SEC = int(os.getenv("SEARCH_TIMEOUT_SEC", "25"))
SEARCH_PROVIDERS = [
    # Each provider entry describes a search intent. All are executed concurrently.
    {
        "name": "general",
        "query": lambda speaker: f'upcoming events, conferences, and speaking schedule for "{speaker}" this year and next year',
    },
    {
        "name": "eventbrite",
        "query": lambda speaker: f'site:eventbrite.com {speaker} upcoming speaker event conference',
    },
    {
        "name": "meetup",
        "query": lambda speaker: f'site:meetup.com {speaker} event talk speaker',
    },
]
