"""
Discord Poster

Formats article digests and posts them to Discord via webhook.
Creates readable messages with emojis and formatting.
"""

import requests
import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


class DiscordPoster:
    """Posts article digests to Discord via webhook."""
    
    def __init__(self, webhook_url: str):
        """
        Initialize the Discord poster.
        
        Args:
            webhook_url: Discord webhook URL
        """
        self.webhook_url = webhook_url
    
    def post_digest(self, articles: List[Dict], title: str = "📰 Morning RSS Digest") -> bool:
        """
        Post a digest of articles to Discord.
        
        Args:
            articles: List of article dicts with 'title', 'ai_summary', 'link', 'source'
            title: Title for the digest message
            
        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Posting digest with {len(articles)} articles to Discord")
        
        try:
            # Build the message
            message = self._format_digest(articles, title)
            
            # Discord has a 2000 character limit per message
            # If too long, we'll split into multiple messages
            if len(message) > 2000:
                logger.warning(f"Message is {len(message)} chars, splitting...")
                return self._post_long_digest(articles, title)
            
            # Post to Discord
            response = requests.post(
                self.webhook_url,
                json={"content": message},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 204:  # Discord returns 204 on success
                logger.info("✓ Successfully posted to Discord")
                return True
            else:
                logger.error(f"Discord returned status {response.status_code}: {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error posting to Discord: {e}")
            return False

    def post_articles_individually(
        self, 
        articles: List[Dict],
         title: str = "📰 Morning RSS Digest",
         test_webhook: bool = False
    ) -> bool:
        """
        Post each article as a separate message (embed stays with article).
        
        Args:
            articles: List of article dicts
            title: Title for the digest
            
        Returns:
            True if all successful, False otherwise
        """
        logger.info(f"Posting {len(articles)} articles individually to Discord")

        # Only test webhook if requested
        if test_webhook:
            if not self.test_webhook():
                logger.error("Webhook test failed!")
                return False
        
        # Post header first
        timestamp = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        header = f"**{title}**\n*{timestamp}*\n*Found {len(articles)} articles*\n"
        
        response = requests.post(self.webhook_url, json={"content": header})
        if response.status_code != 204:
            logger.error("Failed to post header")
            return False
        
        # Post each article individually
        for i, article in enumerate(articles, 1):
            message = f"**{i}. {article['title']}**\n"
            message += f"*Source: {article['source']}*\n"
            message += f"{article['ai_summary']}\n"
            message += f"🔗 {article['link']}"
            
            response = requests.post(self.webhook_url, json={"content": message})
            
            if response.status_code != 204:
                logger.error(f"Failed to post article {i}")
                return False
        
        logger.info("✓ Posted all articles individually")
        return True
    
    def _format_digest(self, articles: List[Dict], title: str) -> str:
        """
        Format articles into a Discord message.
        
        Discord supports basic markdown formatting.
        """
        # Start with title and timestamp
        timestamp = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        message = f"**{title}**\n"
        message += f"*{timestamp}*\n"
        message += f"*Found {len(articles)} articles*\n\n"
        message += "─" * 50 + "\n\n"
        
        # Add each article
        for i, article in enumerate(articles, 1):
            message += f"**{i}. {article['title']}**\n"
            message += f"*Source: {article['source']}*\n"
            message += f"{article['ai_summary']}\n"
            message += f"🔗 {article['link']}\n\n"
        
        return message
    
    def _post_long_digest(self, articles: List[Dict], title: str) -> bool:
        """
        Post a digest that's too long for one message.
        
        Splits into multiple messages.
        """
        # Post title message first
        timestamp = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        header = f"**{title}**\n*{timestamp}*\n*Found {len(articles)} articles*\n"
        
        response = requests.post(
            self.webhook_url,
            json={"content": header}
        )
        
        if response.status_code != 204:
            logger.error("Failed to post header message")
            return False
        
        # Post articles in batches of 3
        batch_size = 3
        for i in range(0, len(articles), batch_size):
            batch = articles[i:i+batch_size]
            message = ""
            
            for j, article in enumerate(batch, i+1):
                message += f"**{j}. {article['title']}**\n"
                message += f"*Source: {article['source']}*\n"
                message += f"{article['ai_summary']}\n"
                message += f"🔗 {article['link']}\n\n"
            
            response = requests.post(
                self.webhook_url,
                json={"content": message}
            )
            
            if response.status_code != 204:
                logger.error(f"Failed to post batch {i//batch_size + 1}")
                return False
        
        logger.info("✓ Posted long digest in multiple messages")
        return True
    
    def test_webhook(self) -> bool:
        """
        Test if the webhook URL works.
        
        Returns:
            True if webhook is valid, False otherwise
        """
        try:
            response = requests.post(
                self.webhook_url,
                json={"content": "🧪 Test message from rss-digest bot!"},
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 204:
                logger.info("✓ Webhook is working!")
                return True
            else:
                logger.error(f"Webhook test failed: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Webhook test error: {e}")
            return False
