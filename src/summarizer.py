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

    # Rate limiting settings (override in subclasses)
    requests_per_minute = 60  # Default: no real limit
    retry_max = 3
    
    def __init__(self):
        self._last_request_time = 0
        self._min_interval = 60.0 / self.requests_per_minute

    def _rate_limit(self):
        """Sleep if needed to respect rate limits."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            sleep_time = self._min_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.1f}s")
            time.sleep(sleep_time)
        self._last_request_time = time.time()

    @abstractmethod
    def _call_api(self, title: str, summary: str) -> str:
        """Make the actual API call. Override in subclasses."""
        pass

    def summarize(self, title: str, summary: str) -> str:
        """Summarize a single article with rate limiting and retry."""
        for attempt in range(self.retry_max):
            try:
                self._rate_limit()
                return self._call_api(title, summary)
            except Exception as e:
                error_str = str(e)
                
                # Handle rate limit errors with retry
                if "429" in error_str or "quota" in error_str.lower():
                    # Try to extract retry delay from error
                    retry_delay = 15  # Default
                    if "retry in" in error_str.lower():
                        try:
                            # Extract number from "retry in X.XXs"
                            import re
                            match = re.search(r'retry in (\d+\.?\d*)', error_str.lower())
                            if match:
                                retry_delay = float(match.group(1)) + 1
                        except:
                            pass
                    
                    if attempt < self.retry_max - 1:
                        logger.warning(f"Rate limited, waiting {retry_delay:.0f}s (attempt {attempt + 1}/{self.retry_max})")
                        time.sleep(retry_delay)
                        continue
                
                # Non-retryable error or max retries exceeded
                raise
        
        raise Exception("Max retries exceeded")
    
    def summarize_batch(self, articles: list) -> list:
        """Summarize a batch of articles, adding 'ai_summary' field."""
        total = len(articles)
        estimated_minutes = total * 60 / self.requests_per_minute / 60
        logger.info(f"Starting to summarize {total} articles...")
        logger.info(f"Rate limit: {self.requests_per_minute} req/min (estimated time: {estimated_minutes:.1f} min)")
        
        success_count = 0
        error_count = 0
        
        for i, article in enumerate(articles, 1):
            logger.info(f"Progress: {i}/{total}")
            logger.info(f"Summarizing: {article['title'][:50]}...")
            
            try:
                ai_summary = self.summarize(
                    title=article['title'],
                    summary=article.get('summary', ''),
                )
                article['ai_summary'] = ai_summary
                success_count += 1
            except Exception as e:
                logger.error(f"Error summarizing article: {e}")
                # Fallback to original summary
                article['ai_summary'] = article.get('summary', 'No summary available.')
                error_count += 1
        
        logger.info(f"✓ Completed: {success_count} summarized, {error_count} fallbacks")
        return articles


# ============================================================
# ANTHROPIC (CLAUDE) PROVIDER
# ============================================================

class AnthropicSummarizer(BaseSummarizer):
    """Summarizer using Anthropic Claude API."""
    
    requests_per_minute = 50  # Conservative limit for Anthropic
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        super().__init__()
        logger.info(f"Initialized Anthropic summarizer with model: {model}")
    
    def _call_api(self, title: str, summary: str) -> str:
        prompt = f"Article title: {title}\n\nArticle summary: {summary}"
        
        response = self.client.messages.create(
            model=self.model,
            max_tokens=200,
            system=self.SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        
        return response.content[0].text.strip()


# ============================================================
# GEMINI (GOOGLE) PROVIDER
# ============================================================

class GeminiSummarizer(BaseSummarizer):
    """Summarizer using Google Gemini API (free tier available).
    
    Free tier limits (as of Dec 2025):
    - 5 requests per minute (RPM) for gemini-2.5-flash
    - 1000 requests per day (RPD)
    """
    
    requests_per_minute = 5  # Gemini free tier limit
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=self.SYSTEM_PROMPT,
        )
        self.model_name = model
        super().__init__()
        logger.info(f"Initialized Gemini summarizer with model: {model}")
        logger.info(f"Free tier rate limit: {self.requests_per_minute} RPM (~12s between requests)")
    
    def _call_api(self, title: str, summary: str) -> str:
        prompt = f"Article title: {title}\n\nArticle summary: {summary}"
        
        response = self.model.generate_content(prompt)
        
        return response.text.strip()


# ============================================================
# FACTORY FUNCTION
# ============================================================

def create_summarizer(
    provider: str = "anthropic",
    api_key: str = None,
    model: str = None,
) -> BaseSummarizer:
    """
    Factory function to create the appropriate summarizer.
    
    Args:
        provider: 'anthropic' or 'gemini'
        api_key: API key for the chosen provider
        model: Optional model override (uses defaults if not specified)
    
    Returns:
        Configured summarizer instance
    """
    provider = provider.lower().strip()
    
    if provider == "anthropic":
        kwargs = {"api_key": api_key}
        if model:
            kwargs["model"] = model
        return AnthropicSummarizer(**kwargs)
    
    elif provider == "gemini":
        kwargs = {"api_key": api_key}
        if model:
            kwargs["model"] = model
        return GeminiSummarizer(**kwargs)
    
    else:
        raise ValueError(f"Unknown provider: {provider}. Use 'anthropic' or 'gemini'.")

