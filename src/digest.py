#!/usr/bin/env python3
"""
RSS Morning Digest - Main Orchestrator

Fetches RSS feeds, summarizes with AI (Claude or Gemini), ranks by relevance,
and posts a three-tier digest to Discord.

Usage:
    python src/digest.py                    # Normal run
    python src/digest.py --dry-run          # Full pipeline, skip Discord post
    python src/digest.py --preview          # Quick preview (no API calls)
    python src/digest.py --debug            # Verbose logging
    python src/digest.py --limit 5          # Test with 5 articles only

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
from summarizer import create_summarizer
from ranker import ArticleRanker
from discord_poster import DiscordPoster


# ============================================================
# LOGGING SETUP
# ============================================================

def setup_logging(debug: bool = False, log_file: str = None, console: bool = True):
    """Configure logging for the digest run."""
    root_logger = logging.getLogger()

    # Clear existing handlers to prevent duplicates
    root_logger.handlers = []

    level = logging.DEBUG if debug else logging.INFO
    root_logger.setLevel(level)

    # Format with timestamp
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler (only if enabled)
    if console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(fmt)
        root_logger.addHandler(console_handler)

    # File handler (if specified)
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
        config = yaml.safe_load(f)
    
    return config


def get_env_vars(config) -> dict:
    """Load required environment variables and model API configuration."""
    # AI Provider selection (default: gemini for free tier)
    # ai_provider = os.getenv('AI_PROVIDER', 'gemini').lower()
    api_config = config.get('api', {})
    ai_provider = api_config.get('provider', 'anthropic')  # will return 'gemini' or 'anthropic'
    ai_provider = ai_provider.lower().strip()

    # Get optional model override
    model = api_config.get('model')  # None if not specified
    
    # Get API keys
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    gemini_key = os.getenv('GEMINI_API_KEY')
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    
    # Validate based on provider
    missing = []
    if ai_provider == 'anthropic' and not anthropic_key:
        missing.append('ANTHROPIC_API_KEY')
    elif ai_provider == 'gemini' and not gemini_key:
        missing.append('GEMINI_API_KEY')
    if not webhook_url:
        missing.append('DISCORD_WEBHOOK_URL')
    
    if missing:
        raise EnvironmentError(
            f"Missing environment variables: {', '.join(missing)}\n"
            f"Set them in .env and run: set -a; source .env; set +a"
        )
    
    return {
        'ai_provider': ai_provider,
        'api_key': anthropic_key if ai_provider == 'anthropic' else gemini_key,
        'model': model,
        'webhook_url': webhook_url,
    }


# ============================================================
# MAIN PIPELINE
# ============================================================

def run_digest(
    config: dict,
    env_vars: dict,
    dry_run: bool = False,
    preview: bool = False,
    limit: int = None,
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
    logger.info(f"AI Provider: {env_vars['ai_provider']}")
    logger.info(f"Settings: max_age={max_age_hours}h, top={top_articles}, min_score={min_score}")
    
    # --- STEP 1: FETCH ---
    logger.info("📡 Fetching RSS feeds...")
    fetcher = FeedFetcher(max_age_hours=max_age_hours)
    articles = fetcher.fetch_all_feeds(feeds)
    
    if not articles:
        logger.warning("No articles found! Check feeds or max_age_hours setting.")
        return 0  # Not an error, just nothing to report
    
    logger.info(f"Found {len(articles)} articles")
    
    # Apply limit if specified (for testing)
    if limit and limit < len(articles):
        logger.info(f"Limiting to {limit} articles (--limit flag)")
        articles = articles[:limit]
    
    # --- STEP 2: PRE-RANK (using RSS summaries only) ---
    logger.info("📊 Pre-ranking by relevance (RSS summaries)...")

    interests = config.get('interests', {})
    ranker = ArticleRanker(
        high_priority=interests.get('high_priority', []),
        medium_priority=interests.get('medium_priority', []),
        low_priority=interests.get('low_priority', []),
        exclusions=interests.get('exclusions', []),
    )

    # Get candidate buffer - summarize more than we need to account for score changes
    candidate_buffer = digest_config.get('candidate_buffer', 35)
    candidates = ranker.rank_articles(
        articles,
        top_n=candidate_buffer,
        min_score=0,  # Allow low scores - they might improve with AI summary
    )

    if not candidates:
        logger.warning("No articles passed the pre-rank filter!")
        return 0

    # Store pre-rank positions for protection logic
    for i, article in enumerate(candidates, 1):
        article['pre_rank_position'] = i
        article['pre_rank_score'] = article.get('relevance_score', 0)

    logger.info(f"Pre-ranked to {len(candidates)} candidates for summarization")

    # --- PREVIEW MODE: Stop here (no API calls) ---
    if preview:
        logger.info("👀 PREVIEW MODE - showing pre-ranked articles (no API calls)")
        for i, article in enumerate(candidates[:top_articles], 1):
            print(
                f"  {i}. [{article.get('relevance_score', 0):3d}] "
                f"{article['source']}: {article['title'][:60]}"
            )
        return 0

    # --- STEP 3: SUMMARIZE (candidates only) ---
    logger.info(f"🤖 Summarizing {len(candidates)} candidates with AI...")
    summarizer = create_summarizer(
        provider=env_vars['ai_provider'],
        api_key=env_vars['api_key'],
        model=env_vars.get('model'),
    )
    summarized = summarizer.summarize_batch(candidates)

    logger.info(f"Summarized {len(summarized)} articles")

    # --- STEP 4: FINAL RANK (with AI summaries + protection) ---
    logger.info("📊 Final ranking with AI summaries...")

    # Protection settings from config (with defaults)
    protected_count = digest_config.get('protected_positions', 5)
    prerank_bonus_max = digest_config.get('prerank_bonus_max', 5)

    ranked = ranker.rank_articles(
        summarized,
        top_n=top_articles,
        min_score=min_score,
        protected_count=protected_count,
        prerank_bonus_max=prerank_bonus_max,
    )

    if not ranked:
        logger.warning("No articles passed the final relevance filter!")
        return 0

    logger.info(f"Final selection: {len(ranked)} articles")

    # Log rank changes for visibility
    logger.info("📈 Rank changes (pre → final):")
    for article in ranked[:top_articles]:
        pre_pos = article.get('pre_rank_position', '?')
        pre_score = article.get('pre_rank_score', 0)
        final_score = article.get('relevance_score', 0)
        final_pos = ranked.index(article) + 1

        # Determine movement indicator
        if pre_pos == final_pos:
            indicator = "➡️"
        elif pre_pos > final_pos:
            indicator = "⬆️"
        else:
            indicator = "⬇️"

        protected_tag = " 🛡️" if article.get('protected') else ""
        logger.info(
            f"  [#{pre_pos}→#{final_pos} {indicator}] "
            f"({pre_score}→{final_score} pts){protected_tag} "
            f"{article['title'][:45]}"
        )

    # --- STEP 5: POST ---
    if dry_run:
        logger.info("🏃 DRY RUN - skipping Discord post")
        logger.info("Would have posted:")
        for i, article in enumerate(ranked, 1):
            print(f"  {i}. [{article.get('relevance_score', 0)}] {article['title'][:60]}")
        return 0

    logger.info("📤 Posting to Discord...")
    poster = DiscordPoster(webhook_url=env_vars['webhook_url'])

    success = poster.post_three_tier_digest(ranked, title)

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
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help="Limit number of articles to summarize (for testing)"
    )
    parser.add_argument(
        '--preview',
        action='store_true',
        help="Quick preview: fetch and pre-rank only (no API calls)"
    )

    args = parser.parse_args()

    # Setup logging (console output only for dry-run)
    setup_logging(debug=args.debug, log_file=args.log_file, console=args.dry_run)
    logger = logging.getLogger(__name__)
    
    try:
        # Load config and env vars
        config = load_config(args.config)
        env_vars = get_env_vars(config)
        
        # Run the pipeline
        exit_code = run_digest(
            config, env_vars,
            dry_run=args.dry_run,
            preview=args.preview,
            limit=args.limit
        )
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
