#!/usr/bin/env python3
"""
RSS Morning Digest - Main Orchestrator

Fetches RSS feeds, summarizes with Claude, ranks by relevance,
and posts a three-tier digest to Discord.

Usage:
    python src/digest.py              # Normal run
    python src/digest.py --dry-run    # Fetch & rank, but don't post
    python src/digest.py --debug      # Verbose logging

Designed to run via cron at 7am daily.
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import yaml

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from feed_fetcher import FeedFetcher
from summarizer import ArticleSummarizer
from ranker import ArticleRanker
from discord_poster import DiscordPoster


# ============================================================
# LOGGING SETUP
# ============================================================

def setup_logging(debug: bool = False, log_file: str = None):
    """Configure logging for the digest run."""
    level = logging.DEBUG if debug else logging.INFO
    
    # Format with timestamp
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"
    
    handlers = [logging.StreamHandler(sys.stdout)]
    
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file))
    
    logging.basicConfig(
        level=level,
        format=fmt,
        datefmt=datefmt,
        handlers=handlers,
    )


# ============================================================
# CONFIG LOADING
# ============================================================

def load_config(config_path: str = "config.yml") -> dict:
    """Load configuration from YAML file."""
    path = Path(config_path)
    
    if not path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Copy config.example.yml to config.yml and customize it."
        )
    
    with open(path, 'r') as f:
        config = yaml.safe_load(f)
    
    return config


def get_env_vars() -> dict:
    """Load required environment variables."""
    api_key = os.getenv('ANTHROPIC_API_KEY')
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    
    missing = []
    if not api_key:
        missing.append('ANTHROPIC_API_KEY')
    if not webhook_url:
        missing.append('DISCORD_WEBHOOK_URL')
    
    if missing:
        raise EnvironmentError(
            f"Missing environment variables: {', '.join(missing)}\n"
            f"Set them in .env and run: set -a; source .env; set +a"
        )
    
    return {
        'api_key': api_key,
        'webhook_url': webhook_url,
    }


# ============================================================
# THREE-TIER DISCORD POSTING
# ============================================================

def post_three_tier_digest(
    poster: DiscordPoster,
    articles: list,
    title: str,
) -> bool:
    """
    Post articles in three tiers:
    - Tier 1 (Top 5): Individual messages with full summaries
    - Tier 2 (Next 5): Single message with summaries
    - Tier 3 (Next 10): Single message with headlines only
    
    Returns True if all posts succeeded.
    """
    import requests
    import time
    
    logger = logging.getLogger(__name__)
    
    # Split into tiers
    tier1 = articles[:5]      # Top 5: individual messages
    tier2 = articles[5:10]    # Next 5: grouped with summaries
    tier3 = articles[10:20]   # Next 10: headlines only
    
    logger.info(f"Posting digest: {len(tier1)} top, {len(tier2)} mid, {len(tier3)} quick")
    
    # --- HEADER ---
    timestamp = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
    header = (
        f"**{title}**\n"
        f"*{timestamp}*\n"
        f"*Found {len(articles)} relevant articles*\n"
        f"{'─' * 40}"
    )
    
    resp = requests.post(poster.webhook_url, json={"content": header})
    if resp.status_code != 204:
        logger.error(f"Failed to post header: {resp.status_code}")
        return False
    time.sleep(0.5)  # Rate limit buffer
    
    # --- TIER 1: Individual messages ---
    if tier1:
        tier1_header = "**🔥 TOP ARTICLES**"
        requests.post(poster.webhook_url, json={"content": tier1_header})
        time.sleep(0.3)
        
        for i, article in enumerate(tier1, 1):
            score = article.get('relevance_score', 0)
            msg = (
                f"**{i}. {article['title']}**\n"
                f"*{article['source']}* • Score: {score}\n"
                f"{article.get('ai_summary', '')}\n"
                f"🔗 {article['link']}"
            )
            resp = requests.post(poster.webhook_url, json={"content": msg})
            if resp.status_code != 204:
                logger.error(f"Failed to post tier 1 article {i}")
                return False
            time.sleep(0.5)
    
    # --- TIER 2: Grouped with summaries ---
    if tier2:
        tier2_msg = "**📰 MORE GOOD READS**\n\n"
        for i, article in enumerate(tier2, 6):
            score = article.get('relevance_score', 0)
            tier2_msg += (
                f"**{i}. {article['title']}**\n"
                f"*{article['source']}* • Score: {score}\n"
                f"{article.get('ai_summary', '')}\n"
                f"🔗 {article['link']}\n\n"
            )
        
        # Discord 2000 char limit - split if needed
        if len(tier2_msg) > 1900:
            # Post in chunks
            chunks = [tier2_msg[i:i+1900] for i in range(0, len(tier2_msg), 1900)]
            for chunk in chunks:
                resp = requests.post(poster.webhook_url, json={"content": chunk})
                if resp.status_code != 204:
                    logger.error("Failed to post tier 2 chunk")
                    return False
                time.sleep(0.5)
        else:
            resp = requests.post(poster.webhook_url, json={"content": tier2_msg})
            if resp.status_code != 204:
                logger.error("Failed to post tier 2")
                return False
        time.sleep(0.5)
    
    # --- TIER 3: Headlines only ---
    if tier3:
        tier3_msg = "**📋 QUICK HEADLINES**\n\n"
        for i, article in enumerate(tier3, 11):
            tier3_msg += f"{i}. [{article['source']}] {article['title']}\n{article['link']}\n\n"
        
        if len(tier3_msg) > 1900:
            chunks = [tier3_msg[i:i+1900] for i in range(0, len(tier3_msg), 1900)]
            for chunk in chunks:
                resp = requests.post(poster.webhook_url, json={"content": chunk})
                if resp.status_code != 204:
                    logger.error("Failed to post tier 3 chunk")
                    return False
                time.sleep(0.5)
        else:
            resp = requests.post(poster.webhook_url, json={"content": tier3_msg})
            if resp.status_code != 204:
                logger.error("Failed to post tier 3")
                return False
    
    logger.info("✓ Successfully posted three-tier digest")
    return True


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_digest(
    config: dict,
    env_vars: dict,
    dry_run: bool = False,
) -> int:
    """
    Run the full digest pipeline.
    
    Returns:
        0 on success, 1 on failure
    """
    logger = logging.getLogger(__name__)
    
    digest_config = config.get('digest', {})
    max_age_hours = digest_config.get('max_age_hours', 24)
    top_articles = digest_config.get('top_articles', 20)
    min_score = digest_config.get('min_score', 1)
    title = digest_config.get('title', "📰 Morning RSS Digest")
    
    feeds = config.get('feeds', [])
    if not feeds:
        logger.error("No feeds configured!")
        return 1
    
    logger.info(f"Starting digest run with {len(feeds)} feeds")
    logger.info(f"Settings: max_age={max_age_hours}h, top={top_articles}, min_score={min_score}")
    
    # --- STEP 1: FETCH ---
    logger.info("📡 Fetching RSS feeds...")
    fetcher = FeedFetcher(max_age_hours=max_age_hours)
    articles = fetcher.fetch_all_feeds(feeds)
    
    if not articles:
        logger.warning("No articles found! Check feeds or max_age_hours setting.")
        return 0  # Not an error, just nothing to report
    
    logger.info(f"Found {len(articles)} articles")
    
    # --- STEP 2: SUMMARIZE ---
    logger.info("🤖 Summarizing articles with Claude...")
    summarizer = ArticleSummarizer(api_key=env_vars['api_key'])
    summarized = summarizer.summarize_batch(articles)
    
    logger.info(f"Summarized {len(summarized)} articles")
    
    # --- STEP 3: RANK ---
    logger.info("📊 Ranking by relevance...")
    
    interests = config.get('interests', {})
    ranker = ArticleRanker(
        high_priority=interests.get('high_priority', []),
        medium_priority=interests.get('medium_priority', []),
        low_priority=interests.get('low_priority', []),
        exclusions=interests.get('exclusions', []),
    )
    
    ranked = ranker.rank_articles(
        summarized,
        top_n=top_articles,
        min_score=min_score,
    )
    
    if not ranked:
        logger.warning("No articles passed the relevance filter!")
        return 0
    
    logger.info(f"Ranked {len(ranked)} articles")
    
    # Show top articles in log
    for article in ranked[:5]:
        logger.info(
            f"  [{article.get('relevance_score', 0):3d}] "
            f"{article['source']}: {article['title'][:50]}"
        )
    
    # --- STEP 4: POST ---
    if dry_run:
        logger.info("🏃 DRY RUN - skipping Discord post")
        logger.info("Would have posted:")
        for i, article in enumerate(ranked, 1):
            print(f"  {i}. [{article.get('relevance_score', 0)}] {article['title'][:60]}")
        return 0
    
    logger.info("📤 Posting to Discord...")
    poster = DiscordPoster(webhook_url=env_vars['webhook_url'])
    
    success = post_three_tier_digest(poster, ranked, title)
    
    if success:
        logger.info("✅ Digest complete!")
        return 0
    else:
        logger.error("❌ Failed to post digest")
        return 1


# ============================================================
# CLI ENTRY POINT
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="RSS Morning Digest - Fetch, summarize, rank, and post"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help="Fetch and rank, but don't post to Discord"
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help="Enable debug logging"
    )
    parser.add_argument(
        '--config',
        default='config.yml',
        help="Path to config file (default: config.yml)"
    )
    parser.add_argument(
        '--log-file',
        default='logs/digest.log',
        help="Path to log file (default: logs/digest.log)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(debug=args.debug, log_file=args.log_file)
    logger = logging.getLogger(__name__)
    
    try:
        # Load config and env vars
        config = load_config(args.config)
        env_vars = get_env_vars()
        
        # Run the pipeline
        exit_code = run_digest(config, env_vars, dry_run=args.dry_run)
        sys.exit(exit_code)
        
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except EnvironmentError as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
