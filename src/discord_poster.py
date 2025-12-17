"""
Discord Poster

Formats article digests and posts them to Discord via webhook using rich embeds.
"""

import requests
import logging
import time
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DiscordPoster:
    """Posts article digests to Discord via webhook."""

    def __init__(self, webhook_url: str, config: Dict):
        """
        Initialize the Discord poster.

        Args:
            webhook_url: Discord webhook URL.
            config: The full configuration dictionary, used for embed_images setting.
        """
        self.webhook_url = webhook_url
        self.config = config
        self.embed_images_enabled = self.config.get('digest', {}).get('embed_images', False)
        # Define a default color for embeds (e.g., a neutral blue)
        self.embed_color = 0x3498DB # Discord color code (decimal)

    def _create_embed(self, article: Dict, rank: int, with_image: bool = False) -> Dict:
        """
        Create a single Discord embed dictionary for an article.
        """
        embed = {
            "title": f"{rank}. {article['title']}",
            "url": article['link'],
            "description": article.get('ai_summary', article.get('summary', 'No summary available.')),
            "color": self.embed_color,
            "fields": [
                {
                    "name": "Source",
                    "value": article['source'],
                    "inline": True
                },
                {
                    "name": "Score",
                    "value": str(article.get('relevance_score', 'N/A')),
                    "inline": True
                }
            ],
            "footer": {
                "text": f"Published: {article['published'].strftime('%Y-%m-%d %H:%M')}"
                if article.get('published') else "Published: N/A"
            }
        }

        if with_image and self.embed_images_enabled and article.get('image_url'):
            embed["image"] = {"url": article['image_url']}

        return embed

    def post_digest(self, articles: List[Dict], digest_title: str) -> bool:
        """
        Post a digest of articles to Discord using rich embeds.
        
        The top 10 articles are sent in one message (with images if enabled).
        The next 10 articles (11-20) are sent in a second message (without images).

        Args:
            articles: List of article dictionaries.
            digest_title: The main title for the digest.
            
        Returns:
            True if successful, False otherwise.
        """
        logger.info(f"Posting digest with {len(articles)} articles to Discord via embeds.")
        
        top_10 = articles[:10]
        next_10 = articles[10:20]
        
        # --- Send Header Message ---
        timestamp = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        header_content = {
            "content": (
                f"**{digest_title}**\n"
                f"*{timestamp}*\n"
                f"*Found {len(articles)} relevant articles*\n"
                f"{'-' * 40}"
            )
        }
        resp = requests.post(self.webhook_url, json=header_content)
        if resp.status_code != 204:
            logger.error(f"Failed to post digest header: {resp.status_code} - {resp.text}")
            return False
        time.sleep(0.5) # Rate limit buffer

        # --- Send Top 10 Articles (with images if enabled) ---
        if top_10:
            top_10_embeds = [
                self._create_embed(article, i + 1, with_image=True)
                for i, article in enumerate(top_10)
            ]
            
            top_10_payload = {
                "content": "**🔥 Top 10 Articles**",
                "embeds": top_10_embeds
            }
            resp = requests.post(self.webhook_url, json=top_10_payload)
            if resp.status_code != 204:
                logger.error(f"Failed to post top 10 articles: {resp.status_code} - {resp.text}")
                return False
            time.sleep(2) # Add a 2-second delay before the next post

        # --- Send Next 10 Articles (without images) ---
        if next_10:
            next_10_embeds = [
                self._create_embed(article, i + 11, with_image=False) # Rank from 11 to 20
                for i, article in enumerate(next_10)
            ]
            
            next_10_payload = {
                "content": "**📰 More Good Reads**",
                "embeds": next_10_embeds
            }
            resp = requests.post(self.webhook_url, json=next_10_payload)
            if resp.status_code != 204:
                logger.error(f"Failed to post next 10 articles: {resp.status_code} - {resp.text}")
                return False
            time.sleep(0.5) # Rate limit buffer

        logger.info("✓ Successfully posted rich digest.")
        return True

    def test_connection(self) -> bool:
        """
        Test if the webhook URL works.
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
                logger.error(f"Webhook test failed: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Webhook test error: {e}")
            return False