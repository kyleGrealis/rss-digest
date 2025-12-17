#!/usr/bin/env python3
"""
RSS Morning Digest - Main Orchestrator

Fetches RSS feeds, summarizes with AI, ranks by relevance, and posts a digest.

Usage:
    python src/digest.py                # Normal run
    python src/digest.py --dry-run      # Full pipeline, skip posting
    python src/digest.py --test-feeds   # Check RSS feeds and exit
    python src/digest.py --test-apis    # Check API connections and exit
    python src/digest.py --limit 5      # Test with 5 articles only
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
from summarizer import create_summarizer
from ranker import create_ranker_from_config
from discord_poster import DiscordPoster


# ============================================================ 
# LOGGING SETUP
# ============================================================ 

def setup_logging(debug: bool = False, log_file: str = None, console: bool = True):
    """Configure logging for the digest run."""
    root_logger = logging.getLogger()
    root_logger.handlers = []
    level = logging.DEBUG if debug else logging.INFO
    root_logger.setLevel(level)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(fmt)
        root_logger.addHandler(console_handler)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(fmt)
        root_logger.addHandler(file_handler)


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
        return yaml.safe_load(f)


def get_env_vars(config) -> dict:
    """Load required environment variables."""
    api_config = config.get('api', {})
    ai_provider = api_config.get('provider', 'anthropic').lower().strip()
    model = api_config.get('model')
    
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    gemini_key = os.getenv('GEMINI_API_KEY')
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    
    missing = []
    if ai_provider == 'anthropic' and not anthropic_key:
        missing.append('ANTHROPIC_API_KEY')
    elif ai_provider == 'gemini' and not gemini_key:
        missing.append('GEMINI_API_KEY')
    if not webhook_url:
        missing.append('DISCORD_WEBHOOK_URL')
    
    if missing:
        raise EnvironmentError(f"Missing environment variables: {', '.join(missing)}")
    
    return {
        'ai_provider': ai_provider,
        'api_key': anthropic_key if ai_provider == 'anthropic' else gemini_key,
        'model': model,
        'webhook_url': webhook_url,
    }

# ============================================================ 
# TEST FUNCTIONS
# ============================================================ 

def test_feeds(config: dict) -> bool:
    """Tests feed fetching and prints results."""
    logger = logging.getLogger(__name__)
    logger.info("--- TESTING FEEDS ---")
    feeds = config.get('feeds', [])
    if not feeds:
        logger.error("No feeds configured!")
        return False
    
    fetcher = FeedFetcher(max_age_hours=config.get('digest', {}).get('max_age_hours', 24))
    total_articles = 0
    all_success = True
    
    for feed in feeds:
        try:
            articles = fetcher.fetch_feed(feed['url'], feed['name'])
            logger.info(f"  [SUCCESS] {feed['name']}: Found {len(articles)} recent articles.")
            total_articles += len(articles)
        except Exception as e:
            logger.error(f"  [FAILURE] {feed['name']}: Error fetching feed - {e}")
            all_success = False
            
    logger.info(f"--- Found {total_articles} total articles across {len(feeds)} feeds. ---")
    return all_success

def test_apis(config: dict, env_vars: dict) -> bool:
    """Tests connections to AI provider and Discord."""
    logger = logging.getLogger(__name__)
    logger.info("--- TESTING API CONNECTIONS ---")
    all_success = True

    # Test AI Summarizer
    try:
        summarizer = create_summarizer(
            provider=env_vars['ai_provider'],
            api_key=env_vars['api_key'],
            model=env_vars.get('model'),
        )
        if summarizer.test_connection():
            logger.info(f"  [SUCCESS] AI Provider ({env_vars['ai_provider']}) connection is working.")
        else:
            logger.error(f"  [FAILURE] AI Provider ({env_vars['ai_provider']}) connection failed.")
            all_success = False
    except Exception as e:
        logger.error(f"  [FAILURE] Error initializing summarizer: {e}")
        all_success = False

    # Test Discord Webhook
    try:
        poster = DiscordPoster(webhook_url=env_vars['webhook_url'], config=config)
        if poster.test_webhook():
            logger.info("  [SUCCESS] Discord webhook connection is working.")
        else:
            logger.error("  [FAILURE] Discord webhook connection failed.")
            all_success = False
    except Exception as e:
        logger.error(f"  [FAILURE] Error initializing Discord poster: {e}")
        all_success = False
        
    logger.info("--- API test complete. ---")
    return all_success

# ============================================================ 
# MAIN PIPELINE
# ============================================================ 

def run_digest(config: dict, env_vars: dict, dry_run: bool = False, limit: int = None) -> int:
    """Run the full digest pipeline."""
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
    logger.info(f"AI Provider: {env_vars['ai_provider']}")
    
    # STEP 1: FETCH
    logger.info("📡 Fetching RSS feeds...")
    fetcher = FeedFetcher(max_age_hours=max_age_hours)
    articles = fetcher.fetch_all_feeds(feeds)
    if not articles:
        logger.warning("No articles found! Check feeds or max_age_hours setting.")
        return 0
    logger.info(f"Found {len(articles)} articles")
    
    if limit and limit < len(articles):
        logger.info(f"Limiting to {limit} articles for this run.")
        articles = articles[:limit]
    
    # STEP 2: PRE-RANK
    logger.info("📊 Pre-ranking by relevance...")
    ranker = create_ranker_from_config(config)
    candidate_buffer = digest_config.get('candidate_buffer', 35)
    candidates = ranker.rank_articles(articles, top_n=candidate_buffer, min_score=0)
    if not candidates:
        logger.warning("No articles passed the pre-rank filter!")
        return 0
        
    for i, article in enumerate(candidates, 1):
        article['pre_rank_position'] = i
        article['pre_rank_score'] = article.get('relevance_score', 0)
    logger.info(f"Pre-ranked to {len(candidates)} candidates for summarization")

    # STEP 3: SUMMARIZE
    logger.info(f"🤖 Summarizing {len(candidates)} candidates with AI...")
    summarizer = create_summarizer(
        provider=env_vars['ai_provider'], api_key=env_vars['api_key'], model=env_vars.get('model')
    )
    summarized = summarizer.summarize_batch(candidates)
    logger.info(f"Summarized {len(summarized)} articles")

    # STEP 4: FINAL RANK
    logger.info("📊 Final ranking with AI summaries...")
    ranking_config = config.get('ranking', {})
    ranked = ranker.rank_articles(
        summarized,
        top_n=top_articles,
        min_score=min_score,
        protected_count=ranking_config.get('protected_count', 3),
        prerank_bonus_max=ranking_config.get('prerank_bonus_max', 5),
    )
    if not ranked:
        logger.warning("No articles passed the final relevance filter!")
        return 0
    logger.info(f"Final selection: {len(ranked)} articles")

    # STEP 5: POST
    if dry_run:
        logger.info("🏃 DRY RUN - skipping Discord post. Final ranked articles:")
        for i, article in enumerate(ranked, 1):
            print(f"  {i}. [{article.get('relevance_score', 0):3d}] {article['title']}")
        return 0

    logger.info("📤 Posting to Discord...")
    poster = DiscordPoster(webhook_url=env_vars['webhook_url'], config=config)
    success = poster.post_digest(ranked, title)

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
    parser = argparse.ArgumentParser(description="RSS Morning Digest - Fetch, summarize, rank, and post.")
    parser.add_argument('--dry-run', action='store_true', help="Run full pipeline but skip posting to Discord.")
    parser.add_argument('--test-feeds', action='store_true', help="Test feed fetching and exit.")
    parser.add_argument('--test-apis', action='store_true', help="Test API connections (AI, Discord) and exit.")
    parser.add_argument('--debug', action='store_true', help="Enable debug logging.")
    parser.add_argument('--config', default='config.yml', help="Path to config file.")
    parser.add_argument('--log-file', default='logs/digest.log', help="Path to log file.")
    parser.add_argument('--limit', type=int, default=None, help="Limit number of articles to process.")
    args = parser.parse_args()

    # Handle test flags first
    if args.test_feeds:
        setup_logging(debug=args.debug, log_file=args.log_file, console=True)
        logger = logging.getLogger(__name__)
        try:
            config = load_config(args.config)
            success = test_feeds(config)
            sys.exit(0 if success else 1)
        except Exception as e:
            logger.exception(f"An error occurred during feed testing: {e}")
            sys.exit(1)

    if args.test_apis:
        setup_logging(debug=args.debug, log_file=args.log_file, console=True)
        logger = logging.getLogger(__name__)
        try:
            config = load_config(args.config)
            env_vars = get_env_vars(config)
            success = test_apis(config, env_vars)
            sys.exit(0 if success else 1)
        except Exception as e:
            logger.exception(f"An error occurred during API testing: {e}")
            sys.exit(1)

    # Setup logging for normal run or dry-run
    console_output = args.dry_run
    setup_logging(debug=args.debug, log_file=args.log_file, console=console_output)
    logger = logging.getLogger(__name__)
    
    try:
        config = load_config(args.config)
        env_vars = get_env_vars(config)
        
        exit_code = run_digest(config, env_vars, dry_run=args.dry_run, limit=args.limit)
        sys.exit(exit_code)
        
    except (FileNotFoundError, EnvironmentError) as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(130)
    except Exception as e:
        logger.exception(f"An unexpected error occurred: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()