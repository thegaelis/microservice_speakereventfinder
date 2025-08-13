from typing import Optional
from firecrawl import FirecrawlApp
from openai import OpenAI
from . import __init__  # noqa: F401
from config import settings


class ClientFactory:
    _firecrawl: Optional[FirecrawlApp] = None
    _openai: Optional[OpenAI] = None

    @classmethod
    def firecrawl(cls) -> Optional[FirecrawlApp]:
        if cls._firecrawl is None and settings.FIRECRAWL_API_KEY:
            cls._firecrawl = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
        return cls._firecrawl

    @classmethod
    def openai(cls) -> Optional[OpenAI]:
        if cls._openai is None and settings.OPENAI_API_KEY:
            cls._openai = OpenAI(api_key=settings.OPENAI_API_KEY)
        return cls._openai
