"""Test of feed fetcher & summarizer"""

import sys
sys.path.insert(0, 'src')

from feed_fetcher import FeedFetcher
from summarizer import ArticleSummarizer
from discord_poster import DiscordPoster
from ranker import create_default_ranker
import logging
import os

# Set up logging
logging.basicConfig(level=logging.INFO)

# Load API key from environment
api_key = os.getenv('ANTHROPIC_API_KEY')
webhook_url = os.getenv('DISCORD_WEBHOOK_URL')

if not api_key:
    print("⚠️[  ANTHROPIC_API_KEY not set!")
    sys.exit(1)

if not webhook_url:
    print("⚠️  DISCORD_WEBHOOK_URL not set!")
    sys.exit(1)

print(f"✓ API key loaded")
print(f"✓ Discord Webhook URL loaded")



# Fetch articles
feeds = [
    {'url': 'https://www.r-bloggers.com/feed/', 'name': 'R-Bloggers'},
    {'url': 'https://athleticsweekly.com/feed/', 'name': 'Athletics Weekly'}
]

print("📡 Fetching RSS feeds...\n")
fetcher = FeedFetcher(max_age_hours=48)  # Last 2 days
articles = fetcher.fetch_all_feeds(feeds)

print(f"\n🎉 Found {len(articles)} articles!\n")

# Debug: see breakdown by source
from collections import Counter
sources = Counter(a['source'] for a in articles)
print(f"📊 By source: {dict(sources)}\n")



# Summarize (adjust 3 lines down for more articles)
print("🤖 Summarizing with Claude...\n")
summarizer = ArticleSummarizer(api_key=api_key)
summarized = summarizer.summarize_batch(articles)



# Rank by relevance
print("📊 Ranking by relevance...\n")
ranker = create_default_ranker()
ranked = ranker.rank_articles(summarized, top_n=10)



# Show what got ranked
for article in ranked:
    print(f"  [{article['relevance_score']:3d}] {article['title'][:50]}")



# Post to Discord - ONE MESSAGE PER ARTICLE!
print("📤 Posting to Discord...\n")
poster = DiscordPoster(webhook_url=webhook_url)  # Create poster here now
success = poster.post_articles_individually(
    ranked, 
    title="🧪 RANKED TEST DIGEST...",
    # title="🧪 Test RSS Digest - Individual"
)

if success:
    print("\n✅ SUCCESS! Check your Discord channel!")
else:
    print("\n❌ Failed to post to Discord")
