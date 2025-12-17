## ROADMAP AND IDEAS

### Recently Implemented (December 2025)

*   **Refactored Discord Posting UX**: Implemented a robust 4-post tiered system for Discord delivery. This ensures a clean, hierarchical presentation of articles (Must Reads, Good Reads, Also Noteworthy) while preventing Discord API size limits.
*   **Two-Tier Interest Profile**: Restructured `config.yml` interest keywords into 'Critical' (score 3) and 'Standard' (score 1) tiers, allowing for more precise control over highly relevant topics without over-biasing the digest.
*   **Structured Logging for Ranking Analytics**: Implemented `src/stats_logger.py` to record detailed data (e.g., article rank, scores, keywords matched) for every article making it into the final digest. This provides a foundational dataset for future analysis and continuous improvement of the ranking algorithm.
*   **Fixed `run-digest.sh` Argument Passing**: Ensured command-line arguments are correctly passed from the shell script to `src/digest.py`.

### Future Ideas

### 1. Enhanced Ranking Algorithms

Building on the structured logging, we can iterate on the ranking algorithm to improve relevance and diversity.

*   **Feed Diversity Score/Boost**: Implement logic to give a temporary boost to articles from feeds that haven't appeared in the digest recently. This would help combat dominance by high-volume feeds and encourage a more eclectic mix of sources. This can be informed by analyzing `stats.csv` data.
*   **Dynamic Candidate Buffer Analysis**: Utilize the structured logs (`stats.csv`) to determine the optimal size for `candidate_buffer`. By analyzing how often articles ranked from, say, 25-50 in the pre-rank make it into the final digest, we can make data-driven decisions on whether to increase or decrease the number of articles sent for AI summarization. This balances AI cost with the chance of finding more relevant articles.

### 2. Interactive Feedback Loop with Discord Reactions (Original Idea)

**The Idea:** Implement a system where users can provide direct feedback on articles posted to Discord using reactions (e.g., 👍 for "more like this," 👎 for "less of this"). This feedback would then be used to dynamically adjust keyword weights in the ranking algorithm.

**The Benefit:** The digest system would become adaptive and self-improving. Over time, it would learn your nuanced preferences, automatically fine-tuning keyword importance without requiring manual `config.yml` edits. This would lead to a highly personalized and increasingly relevant daily digest.

**How It Could Work (High-Level):**

1.  **Discord Bot/Listener:** A separate, lightweight Python script or service would run continuously, acting as a Discord bot. This bot would monitor the Discord channel where the digest is posted.
2.  **Reaction Monitoring:** The bot would listen for specific emoji reactions (e.g., 👍, 👎) on messages containing digest articles.
3.  **Feedback Capture:** When a reaction is detected on an article, the bot would:
    *   Identify the article (e.g., using its URL, which would be part of the embed).
    *   Determine the type of feedback (positive or negative).
    *   Retrieve the keywords that contributed to that article's score from the system (this might require storing article details and their contributing keywords temporarily, or re-analyzing).
4.  **Weight Adjustment Logic:**
    *   If positive feedback (👍), the weights of the keywords found in that article that belong to your `config.yml` tiers would be slightly increased in a separate `learned_weights.yml` file.
    *   If negative feedback (👎), the weights would be slightly decreased.
    *   The adjustments would be small and incremental to avoid over-correcting from a single reaction.
5.  **Dynamic Ranker Integration:** The `ArticleRanker` (or its `create_ranker_from_config` factory) would be modified to:
    *   Load the base `tiers` and `scores` from `config.yml`.
    *   Load and apply the `learned_weights.yml` to further adjust the effective score of keywords. This means a keyword's final score might be `base_score + learned_adjustment`.
6.  **Persistence:** The `learned_weights.yml` file would need to be persistent across runs of the digest script.
7.  **User Interface (Optional):** A simple command could be added to the bot (e.g., `!reset_weights`) to clear the learned weights if desired.

**Challenges/Considerations:**

*   **Discord Bot Setup:** Requires setting up a Discord Developer application and obtaining a bot token, which needs to be kept secret.
*   **Hosting:** The bot/listener would need to be running continuously, likely on a server or a persistent Docker container.
*   **Keyword Attribution:** Accurately attributing feedback to specific keywords can be complex, especially for articles with many keywords from different tiers.
*   **Algorithm Design:** Designing a robust and fair weight adjustment algorithm is crucial to avoid biases or unintended consequences.