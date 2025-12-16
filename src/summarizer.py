#!/usr/bin/env python3
"""
RSS Morning Digest - AI Article Summarizer

Supports multiple AI providers:
- anthropic: Claude Sonnet 4 (default, paid)
- gemini: Google Gemini 2.5 Flash (free tier available)

Set AI_PROVIDER in .env or config.yml to switch providers.
"""

import logging
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

    @abstractmethod
    def summarize(self, title: str, summary: str) -> str:
        """Summarize a single article."""
        pass
    
    def summarize_batch(self, articles: list) -> list:
        """Summarize a batch of articles, adding 'ai_summary' field."""
        logger.info(f"Starting to summarize {len(articles)} articles...")
        
        for i, article in enumerate(articles, 1):
            logger.info(f"Progress: {i}/{len(articles)}")
            logger.info(f"Summarizing: {article['title'][:50]}...")
            
            try:
                ai_summary = self.summarize(
                    title=article['title'],
                    summary=article.get('summary', ''),
                )
                article['ai_summary'] = ai_summary
            except Exception as e:
                logger.error(f"Error summarizing article: {e}")
                # Fallback to original summary
                article['ai_summary'] = article.get('summary', 'No summary available.')
        
        logger.info(f"✓ Completed summarizing {len(articles)} articles")
        return articles


# ============================================================
# ANTHROPIC (CLAUDE) PROVIDER
# ============================================================

class AnthropicSummarizer(BaseSummarizer):
    """Summarizer using Anthropic Claude API."""
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        logger.info(f"Initialized Anthropic summarizer with model: {model}")
    
    def summarize(self, title: str, summary: str) -> str:
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
    """Summarizer using Google Gemini API (free tier available)."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.5-flash"):
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model,
            system_instruction=self.SYSTEM_PROMPT,
        )
        self.model_name = model
        logger.info(f"Initialized Gemini summarizer with model: {model}")
    
    def summarize(self, title: str, summary: str) -> str:
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
        model: Optional model override
    
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


# ============================================================
# BACKWARDS COMPATIBILITY
# ============================================================

class ArticleSummarizer:
    """
    Backwards-compatible wrapper that auto-detects provider.
    
    For new code, prefer create_summarizer() directly.
    """
    
    def __init__(
        self,
        api_key: str = None,
        provider: str = None,
        gemini_api_key: str = None,
    ):
        # Determine provider
        if provider:
            self.provider = provider.lower()
        elif gemini_api_key and not api_key:
            self.provider = "gemini"
        else:
            self.provider = "anthropic"
        
        # Get the right API key
        if self.provider == "gemini":
            key = gemini_api_key or api_key
        else:
            key = api_key
        
        if not key:
            raise ValueError(f"No API key provided for {self.provider}")
        
        # Create the underlying summarizer
        self._summarizer = create_summarizer(
            provider=self.provider,
            api_key=key,
        )
        
        logger.info(f"ArticleSummarizer using provider: {self.provider}")
    
    def summarize_batch(self, articles: list) -> list:
        """Delegate to the underlying summarizer."""
        return self._summarizer.summarize_batch(articles)
