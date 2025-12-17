"""
RSS Feed Fetcher

Pulls articles from RSS feeds and extracts relevant information.
Uses feedparser library to handle various RSS/Atom formats.
"""

import feedparser
import re
from datetime import datetime, timedelta
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)


class FeedFetcher:
    """Fetches and parses RSS feeds."""
    
    def __init__(self, max_age_hours: int = 24):
        """
        Initialize the feed fetcher.
        
        Args:
            max_age_hours: Only fetch articles newer than this many hours
        """
        self.max_age_hours = max_age_hours
        self.cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
    
    def fetch_feed(self, feed_url: str, feed_name: str) -> List[Dict]:
        """
        Fetch articles from a single RSS feed.
        
        Args:
            feed_url: URL of the RSS feed
            feed_name: Human-readable name for logging
            
        Returns:
            List of article dictionaries.
        """
        logger.info(f"Fetching feed: {feed_name}")
        
        try:
            feed = feedparser.parse(feed_url)
            
            if feed.bozo:
                logger.warning(f"Feed {feed_name} has parsing issues: {feed.bozo_exception}")
            
            articles = []
            for entry in feed.entries:
                published = self._get_published_date(entry)
                
                if published and published < self.cutoff_time:
                    continue
                
                article = {
                    'title': entry.get('title', 'No title'),
                    'link': entry.get('link', ''),
                    'summary': entry.get('summary', entry.get('description', '')),
                    'published': published,
                    'source': feed_name,
                    'image_url': self._get_image_url(entry)
                }
                
                articles.append(article)
            
            logger.info(f"Found {len(articles)} recent articles from {feed_name}")
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching {feed_name}: {e}")
            return []

    def fetch_all_feeds(self, feeds: List[Dict]) -> List[Dict]:
        """
        Fetch articles from multiple RSS feeds.
        
        Args:
            feeds: List of dicts with 'url' and 'name' keys
            
        Returns:
            Combined list of all articles
        """
        all_articles = []
        
        for feed in feeds:
            articles = self.fetch_feed(feed['url'], feed['name'])
            all_articles.extend(articles)
        
        logger.info(f"Total articles fetched: {len(all_articles)}")
        return all_articles
    
    def _get_image_url(self, entry) -> str:
        """
        Extract an image URL from a feed entry.
        
        Tries various common locations for thumbnails or content images.
        """
        # Check for media:thumbnail
        if 'media_thumbnail' in entry and entry.media_thumbnail:
            return entry.media_thumbnail[0].get('url')
            
        # Check for media:content
        if 'media_content' in entry and entry.media_content:
            for item in entry.media_content:
                if item.get('medium') == 'image' and item.get('url'):
                    return item.get('url')

        # Check for enclosures (often used for images)
        if 'links' in entry:
            for link in entry.links:
                if link.get('rel') == 'enclosure' and 'image' in link.get('type', ''):
                    return link.get('href')
        
        # Check for image in content (often contains full HTML)
        if 'content' in entry and entry.content:
            for content_item in entry.content:
                if content_item.get('type') == 'text/html' or 'html' in content_item.get('type', ''):
                    html_content = content_item.get('value', '')
                    img_match = re.search(r'<img[^>]+src="([^">]+)"', html_content)
                    if img_match:
                        return img_match.group(1)

        # Last resort: check summary for an <img> tag
        summary_html = entry.get('summary', '')
        if summary_html:
            img_match = re.search(r'<img[^>]+src="([^">]+)"', summary_html)
            if img_match:
                return img_match.group(1)

        return None

    
    def _get_published_date(self, entry) -> datetime:
        """
        Extract publication date from feed entry.
        
        Different RSS feeds use different fields (published_parsed, updated_parsed, etc.)
        This tries to find the right one.
        """
        # Try different common fields
        for date_field in ['published_parsed', 'updated_parsed', 'created_parsed']:
            if hasattr(entry, date_field):
                time_tuple = getattr(entry, date_field)
                if time_tuple:
                    try:
                        return datetime(*time_tuple[:6])  # Convert time_struct to datetime
                    except:
                        pass
        
        # If no date found, assume it's recent
        return datetime.now()
