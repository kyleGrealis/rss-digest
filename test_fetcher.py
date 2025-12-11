"""Test of feed fetcher & summarizer"""

import sys
sys.path.insert(0, 'src')

from feed_fetcher import FeedFetcher
from summarizer import ArticleSummarizer
from discord_poster import DiscordPoster
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


# Test webhook first
print("🧪 Testing Discord webhook...")
poster = DiscordPoster(webhook_url=webhook_url)
if not poster.test_webhook():
    print("❌ Webhook test failed! Check your URL.")
    sys.exit(1)

print("✓  Discord webhook test PASSED!")


# Fetch articles
feeds = [
    {'url': 'https://www.r-bloggers.com/feed/', 'name': 'R-Bloggers'},
]

print("📡 Fetching RSS feeds...\n")
fetcher = FeedFetcher(max_age_hours=48)  # Last 2 days
articles = fetcher.fetch_all_feeds(feeds)

print(f"\n🎉 Found {len(articles)} articles!\n")


# Summarize just the first 2 (to save API calls during testing)
print("🤖 Summarizing with Claude...\n")
summarizer = ArticleSummarizer(api_key=api_key)
summarized = summarizer.summarize_batch(articles[:2])  # Just first 2

# Show results
# print("\n" + "="*70)
# print("📰 SUMMARIZED ARTICLES")
# print("="*70 + "\n")
# 
# for i, article in enumerate(summarized, 1):
    # print(f"{i}. {article['title']}")
    # print(f"   Source: {article['source']}")
    # print(f"   Summary: {article['ai_summary']}")
    # print(f"   Link: {article['link']}")
    # print()


# Post to Discord!
print("📤 Posting to Discord...\n")
success = poster.post_digest(summarized, title="🧪 Test RSS Digest")

if success:
    print("\n✅ SUCCESS! Check your Discord channel!")
else:
    print("\n❌ Failed to post to Discord")
