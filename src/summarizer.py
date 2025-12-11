"""
Article Summarizer

Uses Anthropic's Claude API to generate concise summaries of articles.
Each article gets a 2-3 sentence summary explaining what it's about.
"""

import anthropic
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class ArticleSummarizer:
    """Summarizes articles using Claude API."""
    
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        """
        Initialize the summarizer.
        
        Args:
            api_key: Anthropic API key
            model: Claude model to use (Sonnet 4 is efficient for this)
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
    
    def summarize_article(self, article: Dict) -> Dict:
        """
        Summarize a single article.
        
        Args:
            article: Dict with 'title', 'summary', 'link', 'source'
            
        Returns:
            Same dict with added 'ai_summary' field
        """
        logger.info(f"Summarizing: {article['title'][:50]}...")
        
        try:
            # Build the prompt
            prompt = self._build_prompt(article)
            
            # Call Claude API
            message = self.client.messages.create(
                model=self.model,
                max_tokens=200,  # Short summaries = fewer tokens = cheaper
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract the summary from Claude's response
            summary = message.content[0].text.strip()
            
            # Add it to the article dict
            article['ai_summary'] = summary
            logger.info(f"✓ Summarized successfully")
            
            return article
            
        except Exception as e:
            logger.error(f"Error summarizing article: {e}")
            # Fallback to original summary if API fails
            article['ai_summary'] = article.get('summary', 'No summary available')
            return article
    
    def summarize_batch(self, articles: List[Dict]) -> List[Dict]:
        """
        Summarize multiple articles.
        
        Args:
            articles: List of article dicts
            
        Returns:
            Same list with 'ai_summary' added to each
        """
        logger.info(f"Starting to summarize {len(articles)} articles...")
        
        summarized = []
        for i, article in enumerate(articles, 1):
            logger.info(f"Progress: {i}/{len(articles)}")
            summarized_article = self.summarize_article(article)
            summarized.append(summarized_article)
        
        logger.info(f"✓ Completed summarizing {len(summarized)} articles")
        return summarized
    
    def _build_prompt(self, article: Dict) -> str:
        """
        Build the prompt for Claude.
        
        We give Claude the article title and existing summary,
        and ask for a concise 2-3 sentence summary.
        """
        title = article.get('title', 'Unknown')
        original_summary = article.get('summary', '')
        
        # Clean up HTML tags if present (RSS summaries often have them)
        import re
        original_summary = re.sub(r'<[^>]+>', '', original_summary)
        
        prompt = f"""Here's an article from an RSS feed:

Title: {title}

Original description: {original_summary}

Please write a clear, concise 2-3 sentence summary that explains:
1. What the article is about
2. Why it might be interesting

Be direct and informative. No preamble like "This article discusses..." - just start with the content."""

        return prompt
