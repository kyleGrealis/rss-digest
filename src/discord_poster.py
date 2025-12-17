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

    def _create_embed(
        self, 
        article: Dict, 
        rank: int, 
        with_image: bool = False, 
        with_summary: bool = True
    ) -> Dict:
        """
        Create a single Discord embed dictionary for an article.

        Args:
            article: The article dictionary.
            rank: The rank of the article.
            with_image: Whether to include the article's embed image.
            with_summary: Whether to include the article's summary.
        """
        embed = {
            "title": f"{rank}. {article['title']}",
            "url": article['link'],
            "color": self.embed_color,
            "fields": [
                {"name": "Source", "value": article['source'], "inline": True},
                {"name": "Score", "value": str(article.get('relevance_score', 'N/A')), "inline": True}
            ],
            "footer": {
                "text": (
                    f"Published: {article['published'].strftime('%Y-%m-%d %H:%M')}" 
                    if article.get('published') else "Published: N/A"
                )
            }
        }

        if with_summary:
            summary = article.get('ai_summary', article.get('summary', 'No summary available.'))
            # Generous truncation, as this is now only used for posts with 5 embeds
            if len(summary) > 1024:
                summary = summary[:1021] + "..."
            embed["description"] = summary

        if with_image and self.embed_images_enabled and article.get('image_url'):
            embed["image"] = {"url": article['image_url']}

        return embed

    def _send_webhook(self, payload: Dict, error_message: str) -> bool:
        """Helper to send a webhook and handle errors."""
        resp = requests.post(self.webhook_url, json=payload)
        if resp.status_code >= 400:
            logger.error(f"{error_message}: {resp.status_code} - {resp.text}")
            # Log the failing payload for debugging, but be careful with secrets
            # For now, just logging the content keys to see what was sent
            logger.debug(f"Failing payload keys: {payload.keys()}")
            return False
        return True

    def post_digest(self, articles: List[Dict], digest_title: str) -> bool:
        """
        Post a digest of articles to Discord in a tiered, 4-post format.
        """
        logger.info(f"Posting digest with {len(articles)} articles to Discord.")
        
        # --- Post 1: Header Message ---
        timestamp = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
        header_content = {
            "content": (
                f"**{digest_title}**\n"
                f"*{timestamp}*\n"
                f"*Found {len(articles)} relevant articles*\n"
                f"{'-' * 40}"
            )
        }
        if not self._send_webhook(header_content, "Failed to post digest header"):
            return False
        time.sleep(1)

        # --- Post 2: "Must Reads" (1-5) ---
        top_5 = articles[:5]
        if top_5:
            embeds = [
                self._create_embed(a, i + 1, with_image=True, with_summary=True) 
                for i, a in enumerate(top_5)
            ]
            payload = {"content": "**🔥 Must Reads**", "embeds": embeds}
            if not self._send_webhook(payload, "Failed to post Must Reads (1-5)"):
                return False
            time.sleep(2)

        # --- Post 3: "Good Reads" (6-10) ---
        next_5 = articles[5:10]
        if next_5:
            embeds = [
                self._create_embed(a, i + 6, with_image=False, with_summary=True)
                for i, a in enumerate(next_5)
            ]
            payload = {"content": "**☕️ Good Reads**", "embeds": embeds}
            if not self._send_webhook(payload, "Failed to post Good Reads (6-10)"):
                return False
            time.sleep(2)

        # --- Post 4: "Also Noteworthy" (11-20) ---
        final_10 = articles[10:20]
        if final_10:
            embeds = [
                self._create_embed(a, i + 11, with_image=False, with_summary=False)
                for i, a in enumerate(final_10)
            ]
            payload = {"content": "**📰 Also Noteworthy**", "embeds": embeds}
            if not self._send_webhook(payload, "Failed to post Also Noteworthy (11-20)"):
                return False
            time.sleep(1)

        logger.info("✓ Successfully posted tiered digest.")
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