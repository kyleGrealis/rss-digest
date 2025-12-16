"""
Article Ranker

Scores and ranks articles by relevance to user interests.
Uses weighted keyword matching with exclusion filtering.
"""

import re
import logging
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class ArticleRanker:
    """Ranks articles by relevance to user interests."""

    def __init__(
        self,
        high_priority: List[str],
        medium_priority: List[str],
        low_priority: List[str],
        exclusions: List[str],
    ):
        """
        Initialize the ranker with interest keywords.

        Args:
            high_priority: Keywords worth 10 points each
            medium_priority: Keywords worth 5 points each
            low_priority: Keywords worth 2 points each
            exclusions: Keywords that disqualify an article (score = 0)
        """
        # Store as lowercase sets for fast matching
        self.high_priority = self._normalize_keywords(high_priority)
        self.medium_priority = self._normalize_keywords(medium_priority)
        self.low_priority = self._normalize_keywords(low_priority)
        self.exclusions = self._normalize_keywords(exclusions)

        # Scoring weights
        self.weights = {
            'high': 10,
            'medium': 5,
            'low': 2,
        }

        # Max score cap (prevents runaway scores from keyword-stuffed articles)
        self.max_score = 100

        logger.info(
            f"Ranker initialized: {len(self.high_priority)} high, "
            f"{len(self.medium_priority)} medium, {len(self.low_priority)} low, "
            f"{len(self.exclusions)} exclusions"
        )

    def _normalize_keywords(self, keywords: List[str]) -> Set[str]:
        """
        Normalize keywords to lowercase for matching.
        
        Handles both single words and phrases.
        """
        normalized = set()
        for kw in keywords:
            # Store the lowercase version
            normalized.add(kw.lower().strip())
        return normalized

    def _get_searchable_text(self, article: Dict) -> str:
        """
        Combine article fields into searchable text.
        
        Searches: title, summary, ai_summary, source
        """
        parts = [
            article.get('title', ''),
            article.get('summary', ''),
            article.get('ai_summary', ''),
            article.get('source', ''),
        ]
        return ' '.join(parts).lower()

    def _check_exclusions(self, text: str) -> bool:
        """
        Check if text contains any exclusion keywords.
        
        Returns True if article should be excluded.
        """
        for exclusion in self.exclusions:
            if exclusion in text:
                return True
        return False

    def _count_keyword_matches(self, text: str, keywords: Set[str]) -> int:
        """
        Count how many keywords from a set appear in text.
        
        Uses word boundary matching for single words,
        substring matching for phrases.
        """
        matches = 0
        for keyword in keywords:
            # For multi-word phrases, use simple substring matching
            if ' ' in keyword:
                if keyword in text:
                    matches += 1
            else:
                # For single words, use word boundary matching
                # This prevents 'R' from matching 'running'
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text):
                    matches += 1
        return matches

    def score_article(self, article: Dict) -> int:
        """
        Calculate relevance score for a single article.
        
        Returns:
            Score from 0-100 (0 = excluded or irrelevant, 100 = highly relevant)
        """
        text = self._get_searchable_text(article)

        # Check exclusions first
        if self._check_exclusions(text):
            logger.debug(f"Excluded: {article.get('title', 'Unknown')[:50]}")
            return 0

        # Count matches in each priority tier
        high_matches = self._count_keyword_matches(text, self.high_priority)
        medium_matches = self._count_keyword_matches(text, self.medium_priority)
        low_matches = self._count_keyword_matches(text, self.low_priority)

        # Calculate raw score
        raw_score = (
            high_matches * self.weights['high'] +
            medium_matches * self.weights['medium'] +
            low_matches * self.weights['low']
        )

        # Cap at max score
        final_score = min(raw_score, self.max_score)

        logger.debug(
            f"Score {final_score}: {article.get('title', 'Unknown')[:40]} "
            f"(H:{high_matches} M:{medium_matches} L:{low_matches})"
        )

        return final_score

    def rank_articles(
        self,
        articles: List[Dict],
        top_n: int = 20,
        min_score: int = 1,
        protected_count: int = 0,
        prerank_bonus_max: int = 0,
    ) -> List[Dict]:
        """
        Rank articles by relevance score.

        Args:
            articles: List of article dicts
            top_n: Maximum number of articles to return
            min_score: Minimum score to include (filters out irrelevant)
            protected_count: Top N pre-ranked articles guaranteed inclusion
                             (requires 'pre_rank_position' field on articles)
            prerank_bonus_max: Bonus points for #1 pre-rank (decays to 0)

        Returns:
            List of articles sorted by score (highest first),
            with 'relevance_score' field added to each
        """
        logger.info(f"Ranking {len(articles)} articles...")

        scored_articles = []
        protected_articles = []
        excluded_count = 0
        low_score_count = 0

        for article in articles:
            score = self.score_article(article)
            pre_rank = article.get('pre_rank_position')

            # Exclusions ALWAYS override protection
            if score == 0:
                excluded_count += 1
                if pre_rank and pre_rank <= protected_count:
                    logger.info(
                        f"⚠️ Protected #{pre_rank} excluded (found exclusion keyword): "
                        f"{article.get('title', 'Unknown')[:50]}"
                    )
                continue

            # Apply pre-rank bonus if article has pre_rank_position
            if pre_rank and prerank_bonus_max > 0:
                # #1 gets full bonus, decays linearly
                bonus = max(0, prerank_bonus_max - pre_rank + 1)
                score += bonus
                if bonus > 0:
                    logger.debug(f"Pre-rank #{pre_rank} bonus: +{bonus} pts")

            # Check if this article is protected
            is_protected = pre_rank and pre_rank <= protected_count

            if is_protected:
                # Protected articles get minimum score of 100 to guarantee inclusion
                score = max(score, 100)
                article['relevance_score'] = score
                article['protected'] = True
                protected_articles.append(article)
            elif score >= min_score:
                article['relevance_score'] = score
                scored_articles.append(article)
            else:
                low_score_count += 1

        # Combine: protected first, then regular scored articles
        all_scored = protected_articles + scored_articles

        # Sort by score (highest first)
        all_scored.sort(key=lambda x: x['relevance_score'], reverse=True)

        # Take top N
        result = all_scored[:top_n]

        logger.info(
            f"Ranking complete: {len(result)} articles "
            f"(protected: {len(protected_articles)}, excluded: {excluded_count}, "
            f"low score: {low_score_count})"
        )

        return result


# Default interest profile based on Kyle's preferences
# This can be overridden by config.yml
DEFAULT_HIGH_PRIORITY = [
    # Running & Track
    'running', '5k', '10k', 'track and field', 'track & field',
    'sprints', 'sprint', 'middle distance', '800m', '1500m', '400m',
    'diamond league', 'ncaa track', 'usatf', 'world athletics',
    'marathon training', 'race training', 'tempo run', 'interval',
    
    # R & Data Science
    'tidyverse', 'tidymodels', 'ggplot2', 'dplyr', 'shiny',
    'rstats', 'r programming', 'posit', 'rstudio', 'quarto',
    'data visualization', 'dataviz',
    
    # Linux & COSMIC
    'cosmic de', 'cosmic desktop', 'system76', 'pop!_os', 'pop os',
    'linux desktop', 'arch linux',
    
    # Kettlebells & Fitness
    'kettlebell', 'kettlebells', 'kb snatch', 'emom', 'hiit',
    'longevity', 'healthspan', 'zone 2', 'vo2max', 'vo2 max',
    
    # NCAA & Miami
    'ncaa football', 'college football', 'miami hurricanes',
    'hurricanes football', 'hurricanes basketball',
    
    # NASCAR & Motorsports
    'nascar', 'cup series', 'xfinity series',
    
    # Open Source & Privacy
    'open source', 'proton', 'protonmail', 'proton vpn',
    'privacy', 'eff', 'tailscale',
    
    # Sports Analytics
    'sports analytics', 'sports data', 'sabermetrics',
]

DEFAULT_MEDIUM_PRIORITY = [

    # Running
    'marathon',

    # F1 (high-level only)
    'formula 1', 'f1', 'norris', 'hamilton', 'mclaren',
    
    # Running Gear
    'hoka', 'garmin', 'running shoes', 'runners world',
    
    # Nutrition
    'nutrition science', 'protein', 'pescatarian',
    
    # Politics (left-leaning)
    'progressive', 'bernie sanders', 'aoc', 'medicare for all',
    'european politics', 'social democracy',
    
    # Diabetes Research (work-adjacent but interesting)
    'diabetes', 'type 2 diabetes', 'insulin resistance',
    
    # Linux General
    'linux', 'ubuntu', 'fedora', 'kde', 'gnome',
    'terminal', 'cli', 'command line',
    
    # Audiobooks
    'audiobook', 'audiobooks', 'audible',
    
    # Dataviz
    'd3.js', 'observable', 'data journalism',
    
    # Miami Marlins (minimal)
    'miami marlins', 'marlins',
    
    # Masters Running
    'masters athletics', 'over 40', 'masters running',
]

DEFAULT_LOW_PRIORITY = [
    # Sysadmin
    'sysadmin', 'devops', 'server',
    
    # Climate (occasional)
    'climate policy', 'renewable energy',
    
    # General tech
    'github', 'git',
]

DEFAULT_EXCLUSIONS = [
    # Work mode - avoid in morning digest
    'genomics', 'genomic', 'bioinformatics', 'gene expression',
    'epidemiology', 'epidemiological', 'hiv', 'opioid',
    'genome-wide', 'gwas', 'snp', 'allele',
    
    # Sports to skip
    'nfl', 'nba', 'basketball nba', 'pro football',
    
    # AI hype
    'chatgpt is amazing', 'ai will replace', 'prompt engineering secrets',
    
    # Tech not using
    'nodejs', 'node.js', 'react native', 'angular',
    
    # Other exclusions
    'meal prep', 'meal planning', 'weekly meal',
    'raspberry pi project', 'pi project ideas',
    'f1 drama', 'horner', 'grid penalty drama',
    'union strike', 'labor union',
]


def create_default_ranker() -> ArticleRanker:
    """Create a ranker with Kyle's default interest profile."""
    return ArticleRanker(
        high_priority=DEFAULT_HIGH_PRIORITY,
        medium_priority=DEFAULT_MEDIUM_PRIORITY,
        low_priority=DEFAULT_LOW_PRIORITY,
        exclusions=DEFAULT_EXCLUSIONS,
    )


def create_ranker_from_config(config: Dict) -> ArticleRanker:
    """
    Create a ranker from config.yml interests section.
    
    Expected config structure:
        interests:
            high_priority:
                - "keyword1"
                - "keyword2"
            medium_priority:
                - "keyword3"
            low_priority:
                - "keyword4"
            exclusions:
                - "keyword5"
    """
    interests = config.get('interests', {})
    
    return ArticleRanker(
        high_priority=interests.get('high_priority', DEFAULT_HIGH_PRIORITY),
        medium_priority=interests.get('medium_priority', DEFAULT_MEDIUM_PRIORITY),
        low_priority=interests.get('low_priority', DEFAULT_LOW_PRIORITY),
        exclusions=interests.get('exclusions', DEFAULT_EXCLUSIONS),
    )


# Quick test if run directly
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    
    # Test articles
    test_articles = [
        {
            'title': 'New tidymodels update brings better cross-validation',
            'summary': 'The tidymodels team released updates to rsample with improved CV.',
            'source': 'R-Bloggers',
        },
        {
            'title': 'ChatGPT is amazing and will replace all programmers',
            'summary': 'AI hype article about how ChatGPT changes everything.',
            'source': 'Tech Blog',
        },
        {
            'title': 'Diamond League results: New 400m record set',
            'summary': 'Exciting sprint action at the latest Diamond League meet.',
            'source': 'Athletics Weekly',
        },
        {
            'title': 'Genome-wide association study finds new diabetes markers',
            'summary': 'GWAS research on type 2 diabetes genetic factors.',
            'source': 'Science Daily',
        },
        {
            'title': 'System76 announces COSMIC alpha 6 release',
            'summary': 'The latest COSMIC desktop environment update is here.',
            'source': 'OMG Ubuntu',
        },
        {
            'title': 'NFL Week 15 Preview',
            'summary': 'Breaking down all the NFL matchups this weekend.',
            'source': 'ESPN',
        },
        {
            'title': 'Kettlebell snatch technique for endurance athletes',
            'summary': 'How to improve your KB snatch for better running performance.',
            'source': 'Stronger By Science',
        },
    ]
    
    ranker = create_default_ranker()
    ranked = ranker.rank_articles(test_articles, top_n=10, min_score=1)
    
    print("\n" + "="*60)
    print("📊 RANKED ARTICLES")
    print("="*60)
    for i, article in enumerate(ranked, 1):
        print(f"{i}. [{article['relevance_score']:3d}] {article['title'][:50]}")
    
    print(f"\n✅ Kept {len(ranked)} of {len(test_articles)} articles")
