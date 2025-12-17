"""
Stats Logger

Logs digest statistics to a structured CSV file for later analysis.
"""

import csv
from datetime import datetime, timezone
import logging
from pathlib import Path
from typing import List, Dict

logger = logging.getLogger(__name__)

class StatsLogger:
    """Logs digest statistics to a CSV file."""

    def __init__(self, log_dir: str = "logs"):
        """
        Initialize the StatsLogger.

        Args:
            log_dir: The directory to store the log file in.
        """
        self.log_path = Path(log_dir) / "stats.csv"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_file()

    def _initialize_file(self):
        """Create the CSV and write the header if it doesn't exist."""
        if not self.log_path.exists():
            try:
                with open(self.log_path, 'w', newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow([
                        "run_timestamp_utc",
                        "final_rank",
                        "title",
                        "source",
                        "final_score",
                        "keywords_matched",
                        "url"
                    ])
            except IOError as e:
                logger.error(f"Could not initialize stats log file: {e}")

    def log_run(self, articles: List[Dict]):
        """
        Log the statistics for a completed digest run.

        Args:
            articles: The final list of ranked articles from the digest.
        """
        if not articles:
            return

        run_timestamp = datetime.now(timezone.utc).isoformat()
        
        try:
            with open(self.log_path, 'a', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                for i, article in enumerate(articles, 1):
                    # Ensure keywords is a comma-separated string
                    keywords = article.get('keywords_matched', [])
                    keywords_str = ", ".join(keywords) if isinstance(keywords, list) else ""

                    writer.writerow([
                        run_timestamp,
                        i,
                        article.get('title', 'N/A'),
                        article.get('source', 'N/A'),
                        article.get('relevance_score', 0),
                        keywords_str,
                        article.get('link', 'N/A')
                    ])
            logger.info(f"Logged stats for {len(articles)} articles to {self.log_path}")
        except IOError as e:
            logger.error(f"Could not write to stats log file: {e}")
        except Exception as e:
            logger.exception(f"An unexpected error occurred in StatsLogger: {e}")

