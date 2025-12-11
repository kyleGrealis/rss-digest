"""
RSS Feed Fetcher

Pulls articles from RSS feeds and extracts relevant information.
Uses feedparser library to handle various RSS/Atom formats.
"""

import feedparser
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
            List of article dictionaries with keys:
            - title: Article title
            - link: Article URL
            - summary: Short description (if available)
            - published: Publication date
            - source: Feed name
        """
        logger.info(f"Fetching feed: {feed_name}")
        
        try:
            # feedparser does all the heavy lifting
            feed = feedparser.parse(feed_url)
            
            if feed.bozo:  # bozo=1 means malformed feed
                logger.warning(f"Feed {feed_name} has parsing issues: {feed.bozo_exception}")
            
            articles = []
            for entry in feed.entries:
                # Extract publication date (different feeds use different fields)
                published = self._get_published_date(entry)
                
                # Skip old articles
                if published and published < self.cutoff_time:
                    continue
                
                article = {
                    'title': entry.get('title', 'No title'),
                    'link': entry.get('link', ''),
                    'summary': entry.get('summary', entry.get('description', '')),
                    'published': published,
                    'source': feed_name
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
