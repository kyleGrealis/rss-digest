"""
Article Ranker

Scores and ranks articles by relevance based on a dynamic, tiered system
of keywords and penalties defined in a configuration file.
"""

import re
import logging
from typing import Dict, List, Set, Any

logger = logging.getLogger(__name__)


class ArticleRanker:
    """Ranks articles by relevance to user interests."""

    def __init__(self, tiers: List[Dict[str, Any]], exclusions: List[str], penalties: List[Dict[str, Any]]):
        """
        Initialize the ranker with dynamic lists of interest tiers and penalties.

        Args:
            tiers: A list of tier dictionaries, each with 'name', 'score', and 'keywords'.
            exclusions: A list of keywords that disqualify an article (score = 0).
            penalties: A list of penalty dictionaries, each with 'score' (negative) and 'keywords'.
        """
        self.tiers = self._normalize_config_list(tiers)
        self.exclusions = self._normalize_keywords(exclusions)
        self.penalties = self._normalize_config_list(penalties)

        tier_count = len(self.tiers)
        exclusion_count = len(self.exclusions)
        penalty_count = len(self.penalties)
        logger.info(
            f"Ranker initialized with {tier_count} tiers, {penalty_count} penalty groups, and {exclusion_count} exclusions."
        )

    def _normalize_keywords(self, keywords: List[str]) -> Set[str]:
        """Normalize keywords to lowercase for matching."""
        normalized = set()
        if keywords:
            for kw in keywords:
                normalized.add(kw.lower().strip())
        return normalized

    def _normalize_config_list(self, config_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Normalizes keywords within a list of dictionaries (like tiers or penalties)."""
        normalized_list = []
        if config_list:
            for item in config_list:
                normalized_list.append({
                    'name': item.get('name', 'Unknown'), # Name is optional for penalties
                    'score': item.get('score', 0),
                    'keywords': self._normalize_keywords(item.get('keywords', [])),
                })
        return normalized_list

    def _get_searchable_text(self, article: Dict) -> str:
        """Combine article fields into a single searchable text block."""
        parts = [
            article.get('title', ''),
            article.get('summary', ''),
            article.get('ai_summary', ''),
            article.get('source', ''),
        ]
        return ' '.join(filter(None, parts)).lower()

    def _check_exclusions(self, text: str) -> bool:
        """Check if text contains any exclusion keywords."""
        for exclusion in self.exclusions:
            if exclusion in text:
                return True
        return False

    def _count_keyword_matches(self, text: str, keywords: Set[str]) -> int:
        """
        Count how many keywords from a set appear in the text.
        Uses word boundary matching for single words and substring matching for phrases.
        """
        matches = 0
        for keyword in keywords:
            if not keyword:
                continue
            # For multi-word phrases, use simple substring matching
            if ' ' in keyword:
                if keyword in text:
                    matches += 1
            # For single words, use word boundary matching
            else:
                pattern = r'\b' + re.escape(keyword) + r'\b'
                if re.search(pattern, text):
                    matches += 1
        return matches

    def score_article(self, article: Dict) -> int:
        """
        Calculate a relevance score for a single article based on tiered keywords and penalties.
        The score is uncapped.

        Returns:
            An integer score (0 if excluded).
        """
        text = self._get_searchable_text(article)

        if self._check_exclusions(text):
            logger.debug(f"Excluded: {article.get('title', 'Unknown')[:50]}")
            return 0

        # Calculate positive score from tiers
        total_score = 0
        match_details = {}
        for tier in self.tiers:
            matches = self._count_keyword_matches(text, tier['keywords'])
            if matches > 0:
                tier_score = matches * tier['score']
                total_score += tier_score
                match_details[tier['name']] = matches
        
        # Calculate negative score from penalties
        penalty_score = 0
        penalty_details = []
        for penalty in self.penalties:
            matches = self._count_keyword_matches(text, penalty['keywords'])
            if matches > 0:
                penalty_amount = matches * penalty['score']
                penalty_score += penalty_amount
                penalty_details.append(f"Penalty:{matches}x({penalty['score']})")

        final_score = total_score + penalty_score

        if final_score > 0:
            details_str = " ".join([f"{name}:{count}" for name, count in match_details.items()])
            if penalty_details:
                details_str += " " + " ".join(penalty_details)
            logger.debug(
                f"Score {final_score} (base:{total_score}, penalty:{penalty_score}): {article.get('title', 'Unknown')[:40]} ({details_str})"
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
            articles: List of article dicts.
            top_n: Maximum number of articles to return.
            min_score: Minimum score to include (filters out irrelevant).
            protected_count: Top N pre-ranked articles guaranteed inclusion.
            prerank_bonus_max: Bonus points for #1 pre-rank (decays to 0).

        Returns:
            A list of articles sorted by score (highest first), with
            'relevance_score' added to each.
        """
        logger.info(f"Ranking {len(articles)} articles...")

        scored_articles = []
        protected_links = set() # Use a set to avoid duplicates
        excluded_count = 0
        low_score_count = 0

        for article in articles:
            score = self.score_article(article)
            pre_rank = article.get('pre_rank_position')

            # Exclusions ALWAYS override protection
            if score == 0 and self._check_exclusions(self._get_searchable_text(article)):
                excluded_count += 1
                if pre_rank and pre_rank <= protected_count:
                    logger.warning(
                        f"🛡️ Protected #{pre_rank} excluded (found exclusion keyword): "
                        f"{article.get('title', 'Unknown')[:50]}"
                    )
                continue

            # Apply pre-rank bonus if article has a pre_rank_position
            if pre_rank and prerank_bonus_max > 0:
                bonus = max(0, prerank_bonus_max - pre_rank + 1)
                if bonus > 0:
                    score += bonus
                    logger.debug(f"Pre-rank #{pre_rank} bonus: +{bonus} pts")

            article['relevance_score'] = score

            # Identify protected articles but don't add them yet
            if pre_rank and pre_rank <= protected_count:
                article['protected'] = True
                protected_links.add(article['link']) # Add link to set for tracking

            # Add to list if it meets the minimum score
            if score >= min_score:
                scored_articles.append(article)
            else:
                low_score_count += 1

        # Sort all potentially includable articles by score
        scored_articles.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Build the final list, ensuring protected articles are at the top if they
        # were not already there, and that we don't exceed top_n.
        final_list = []
        added_links = set()

        # Add protected articles that made the cut first
        for article in scored_articles:
            # Check if this article should be protected and hasn't been added
            if article.get('protected') and article['link'] in protected_links and article['link'] not in added_links:
                final_list.append(article)
                added_links.add(article['link'])
        
        # Add remaining articles until top_n is reached
        for article in scored_articles:
            if len(final_list) >= top_n:
                break
            if article['link'] not in added_links:
                final_list.append(article)
                added_links.add(article['link'])
        
        # The list is already sorted by score.
        result = final_list

        logger.info(
            f"Ranking complete: {len(result)} articles "
            f"(protected: {len([a for a in result if a.get('protected')])}, excluded: {excluded_count}, "
            f"low score: {low_score_count})"
        )

        return result

def create_ranker_from_config(config: Dict) -> ArticleRanker:
    """
    Create a ranker from a config.yml dictionary.

    Expected config structure:
        interests:
            tiers: [...] 
            exclusions: [...] 
            penalties: [...] 
    """
    interests = config.get('interests', {})
    tiers = interests.get('tiers', [])
    exclusions = interests.get('exclusions', [])
    penalties = interests.get('penalties', [])

    if not tiers:
        logger.warning("No interest tiers found in config.yml. All articles will have a score of 0.")

    return ArticleRanker(tiers=tiers, exclusions=exclusions, penalties=penalties)


# Quick test if run directly
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)

    # Mock config for testing
    test_config = {
        'interests': {
            'tiers': [
                {'name': 'High', 'score': 10, 'keywords': ['tidymodels', 'cosmic', 'kettlebell']},
                {'name': 'Medium', 'score': 5, 'keywords': ['diamond league', 'running']},
                {'name': 'Low', 'score': 1, 'keywords': ['python']},
            ],
            'exclusions': ['genomics', 'nfl', 'chatgpt is amazing'],
            'penalties': [
                {'score': -8, 'keywords': ['pop os', 'what you need to know']},
            ]
        }
    }

    # Test articles
    test_articles = [
        {'title': 'New tidymodels update brings better cross-validation', 'summary': '', 'link': '1'},
        {'title': 'ChatGPT is amazing and will replace all programmers', 'summary': '', 'link': '2'},
        {'title': 'Diamond League results: New 400m record set', 'summary': 'Exciting sprint action.', 'link': '3'},
        {'title': 'System76 announces COSMIC alpha 6 and Pop OS updates', 'summary': 'cosmic is great but pop os is also here', 'link': '5'},
        {'title': 'Kettlebell snatch technique for endurance athletes', 'summary': 'Improve your running.', 'link': '7'},
        {'title': 'What you need to know about the new Python library', 'summary': '', 'link': '8'},
    ]

    # Create ranker from mock config
    ranker = create_ranker_from_config(test_config)
    ranked = ranker.rank_articles(test_articles, top_n=10, min_score=1)

    print("\n" + "="*60)
    print("📊 RANKED ARTICLES")
    print("="*60)
    for i, article in enumerate(ranked, 1):
        print(f"{i}. [{article.get('relevance_score', 0):3d}] {article['title'][:50]}")

    print(f"\n✅ Kept {len(ranked)} of {len(test_articles)} articles")
