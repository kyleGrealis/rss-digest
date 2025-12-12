"""
RSS Feed Validator

Tests a list of RSS feed URLs and reports which ones are working.
Run this before adding feeds to your config.yml
"""

import feedparser
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Tuple


# All candidate feeds organized by category
FEEDS_TO_TEST = {
    # HIGH PRIORITY
    "Running & Track": [
        ("Athletics Weekly", "https://athleticsweekly.com/feed/"),
        ("LetsRun", "https://www.letsrun.com/feed/"),
        ("Runner's World", "https://www.runnersworld.com/rss/all.xml/"),
        ("World Athletics", "https://worldathletics.org/rss-feeds/news"),
    ],
    "R & Data Science": [
        ("R-Bloggers", "https://www.r-bloggers.com/feed/"),
        ("R Weekly", "https://rweekly.org/atom.xml"),
        ("Posit Blog", "https://posit.co/feed/"),
        ("Tidyverse Blog", "https://www.tidyverse.org/blog/index.xml"),
        ("Emil Hvitfeldt", "https://emilhvitfeldt.com/index.xml"),
        ("Albert Rapp", "https://albert-rapp.de/index.xml"),
        ("Emily Riederer", "https://emilyriederer.com/index.xml"),
    ],
    "Linux & COSMIC": [
        ("System76 Blog", "https://blog.system76.com/rss"),
        ("OMG! Ubuntu", "https://www.omgubuntu.co.uk/feed"),
        ("Phoronix", "https://www.phoronix.com/rss.php"),
        ("Linux Unplugged", "https://feeds.fireside.fm/linuxunplugged/rss"),
    ],
    "Privacy & Security": [
        ("EFF Deeplinks", "https://www.eff.org/rss/updates.xml"),
        ("Proton Blog", "https://proton.me/blog/feed"),
        ("Privacy Guides", "https://www.privacyguides.org/en/feed.xml"),
    ],
    "Open Source": [
        ("GitHub Blog", "https://github.blog/feed/"),
        ("Changelog News", "https://changelog.com/news/feed"),
    ],
    
    # MEDIUM PRIORITY
    "Motorsports": [
        ("NASCAR.com", "https://www.nascar.com/feed/"),
        ("Motorsport.com F1", "https://www.motorsport.com/rss/f1/news/"),
        ("Racer.com", "https://racer.com/feed/"),
    ],
    "Fitness & Longevity": [
        ("Peter Attia", "https://peterattiamd.com/feed/"),
        ("Stronger By Science", "https://www.strongerbyscience.com/feed/"),
        ("Examine.com", "https://examine.com/rss/"),
    ],
    "Politics": [
        ("The Guardian US", "https://www.theguardian.com/us-news/rss"),
        ("The Intercept", "https://theintercept.com/feed/?rss"),
        ("Current Affairs", "https://www.currentaffairs.org/feed"),
        ("Jacobin", "https://jacobin.com/feed/"),
    ],
    "Miami Sports": [
        ("Miami Hurricanes", "https://miamihurricanes.com/rss"),
    ],
    "Dataviz & Books": [
        ("Flowing Data", "https://flowingdata.com/feed/"),
        ("Book Riot", "https://bookriot.com/feed/"),
    ],
}


def test_feed(name: str, url: str) -> Dict:
    """
    Test a single RSS feed.
    
    Returns dict with:
        - status: 'working', 'empty', 'error', 'timeout'
        - articles: number of entries found
        - latest: date of most recent article (if available)
        - error: error message (if any)
    """
    result = {
        "name": name,
        "url": url,
        "status": "unknown",
        "articles": 0,
        "latest": None,
        "error": None,
    }
    
    try:
        # First check if URL is reachable
        response = requests.head(url, timeout=10, allow_redirects=True)
        
        # Now parse the feed
        feed = feedparser.parse(url)
        
        if feed.bozo and not feed.entries:
            result["status"] = "error"
            result["error"] = str(feed.bozo_exception)[:50]
            return result
        
        if not feed.entries:
            result["status"] = "empty"
            return result
        
        result["status"] = "working"
        result["articles"] = len(feed.entries)
        
        # Get latest article date
        if feed.entries:
            entry = feed.entries[0]
            for date_field in ['published_parsed', 'updated_parsed', 'created_parsed']:
                if hasattr(entry, date_field) and getattr(entry, date_field):
                    try:
                        dt = datetime(*getattr(entry, date_field)[:6])
                        result["latest"] = dt.strftime("%Y-%m-%d")
                        break
                    except:
                        pass
        
        return result
        
    except requests.exceptions.Timeout:
        result["status"] = "timeout"
        result["error"] = "Request timed out"
        return result
    except requests.exceptions.RequestException as e:
        result["status"] = "error"
        result["error"] = str(e)[:50]
        return result
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)[:50]
        return result


def print_results(results: List[Dict], category: str):
    """Pretty print results for a category."""
    print(f"\n{'='*60}")
    print(f"📁 {category}")
    print('='*60)
    
    for r in results:
        if r["status"] == "working":
            emoji = "✅"
            details = f"{r['articles']} articles"
            if r["latest"]:
                details += f", latest: {r['latest']}"
        elif r["status"] == "empty":
            emoji = "⚠️ "
            details = "No articles found"
        elif r["status"] == "timeout":
            emoji = "⏱️ "
            details = "Timeout"
        else:
            emoji = "❌"
            details = r["error"] or "Unknown error"
        
        print(f"{emoji} {r['name']:<25} {details}")


def main():
    print("🔍 RSS Feed Validator")
    print("Testing all candidate feeds...\n")
    
    all_results = {}
    working_feeds = []
    failed_feeds = []
    
    for category, feeds in FEEDS_TO_TEST.items():
        print(f"Testing {category}...", end=" ", flush=True)
        
        results = []
        for name, url in feeds:
            result = test_feed(name, url)
            results.append(result)
            
            if result["status"] == "working":
                working_feeds.append((category, name, url))
            else:
                failed_feeds.append((category, name, url, result["status"]))
        
        all_results[category] = results
        print("done")
    
    # Print detailed results
    for category, results in all_results.items():
        print_results(results, category)
    
    # Summary
    print(f"\n{'='*60}")
    print("📊 SUMMARY")
    print('='*60)
    print(f"✅ Working: {len(working_feeds)}")
    print(f"❌ Failed:  {len(failed_feeds)}")
    
    # Output config.yml format for working feeds
    print(f"\n{'='*60}")
    print("📝 WORKING FEEDS (config.yml format)")
    print('='*60)
    print("\nfeeds:")
    for category, name, url in working_feeds:
        print(f'  - url: "{url}"')
        print(f'    name: "{name}"')
        print()


if __name__ == "__main__":
    main()
