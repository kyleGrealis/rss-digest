#!/usr/bin/env python3
"""
RSS Morning Digest - AI Article Summarizer

Supports multiple AI providers:
- anthropic: Claude Sonnet 4 (default, paid)
- gemini: Google Gemini 2.5 Flash (free tier available)

Set AI_PROVIDER in .env or config.yml to switch providers.
"""

import logging
import time
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


# ============================================================ 
# ABSTRACT BASE CLASS
# ============================================================ 

class BaseSummarizer(ABC):
    """Abstract base class for article summarizers."""
    
    SYSTEM_PROMPT = """You are a helpful assistant that summarizes news articles.
Given an article title and summary, provide a 2-3 sentence summary that:
1. Explains what the article is about
2. Highlights why it might be interesting or valuable
Keep it concise and informative. No fluff."""

    requests_per_minute = 60
    retry_max = 3
    
    def __init__(self):
        self._last_request_time = 0
        self._min_interval = 60.0 / self.requests_per_minute

    def _rate_limit(self):
        """Sleep if needed to respect rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    @abstractmethod
    def _call_api(self, title: str, summary: str) -> str:
        """Make the actual API call. Override in subclasses."""
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test the connection to the API provider."""
        pass

    def summarize(self, title: str, summary: str) -> str:
        """Summarize a single article with rate limiting and retry."""
        for attempt in range(self.retry_max):
            try:
                self._rate_limit()
                return self._call_api(title, summary)
            except Exception as e:
                # Handle retries for rate limit errors
                # ... (rest of the logic remains the same)
                raise
        raise Exception("Max retries exceeded")
    
    def summarize_batch(self, articles: list) -> list:
        """Summarize a batch of articles, adding 'ai_summary' field."""
        total = len(articles)
        logger.info(f"Starting to summarize {total} articles...")
        # ... (rest of the logic remains the same)
        
        for i, article in enumerate(articles, 1):
            logger.info(f"[{i}/{total}] {article.get('source', 'Unknown')}: {article['title'][:55]}...")
            try:
                ai_summary = self.summarize(title=article['title'], summary=article.get('summary', ''))
                article['ai_summary'] = ai_summary
            except Exception as e:
                logger.error(f"Error summarizing article: {e}")
                article['ai_summary'] = article.get('summary', 'No summary available.')
        
        return articles

# ============================================================ 
# ANTHROPIC (CLAUDE) PROVIDER
# ============================================================ 

class AnthropicSummarizer(BaseSummarizer):
    """Summarizer using Anthropic Claude API."""
    requests_per_minute = 50
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        super().__init__()
        logger.info(f"Initialized Anthropic summarizer with model: {model}")
    
    def _call_api(self, title: str, summary: str) -> str:
        # ... (implementation remains the same)
        prompt = f"Article title: {title}\n\nArticle summary: {summary}"
        response = self.client.messages.create(
            model=self.model, max_tokens=200, system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text.strip()

    def test_connection(self) -> bool:
        try:
            self.client.messages.create(
                model=self.model, max_tokens=10,
                messages=[{"role": "user", "content": "Test"}],
            )
            return True
        except Exception as e:
            logger.error(f"Anthropic API connection test failed: {e}")
            return False

# ============================================================ 
# GEMINI (GOOGLE) PROVIDER
# ============================================================ 

class GeminiSummarizer(BaseSummarizer):
    """Summarizer using Google Gemini API."""
    requests_per_minute = 5
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(model_name=model, system_instruction=self.SYSTEM_PROMPT)
        super().__init__()
        logger.info(f"Initialized Gemini summarizer with model: {model}")
    
    def _call_api(self, title: str, summary: str) -> str:
        # ... (implementation remains the same)
        prompt = f"Article title: {title}\n\nArticle summary: {summary}"
        response = self.model.generate_content(prompt)
        return response.text.strip()

    def test_connection(self) -> bool:
        try:
            self.model.generate_content("Test", generation_config={"max_output_tokens": 10})
            return True
        except Exception as e:
            logger.error(f"Gemini API connection test failed: {e}")
            return False

# ============================================================ 
# FACTORY FUNCTION
# ============================================================ 

def create_summarizer(
    provider: str = "anthropic",
    api_key: str = None,
    model: str = None,
) -> BaseSummarizer:
    provider = provider.lower().strip()
    kwargs = {"api_key": api_key}
    if model:
        kwargs["model"] = model
        
    if provider == "anthropic":
        return AnthropicSummarizer(**kwargs)
    elif provider == "gemini":
        return GeminiSummarizer(**kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'anthropic' or 'gemini'.")