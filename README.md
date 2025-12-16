# RSS Morning Digest

Automated RSS feed curation system that delivers a personalized morning digest to Discord. Uses Claude AI to summarize articles and ranks them by relevance of interests.

## 🎯 What It Does

Every morning at 7am, this system:
1. 📡 Fetches articles from configured RSS feeds
2. 🤖 Summarizes each article with Claude AI (2-3 sentences)
3. 📊 Ranks articles by relevance to interests
4. 💬 Delivers a three-tier digest to personal Discord channel:
   - **Top 5**: Individual messages with full summaries and embeds
   - **Next 5**: Grouped message with summaries
   - **Next 10**: Quick headlines with links

## 🚀 Features

- ✅ AI-powered summarization (Anthropic Claude Sonnet 4)
- ✅ Personalized ranking based on your interests
- ✅ Clean Discord formatting with embeds
- ✅ Configurable RSS feed sources
- ✅ Automated daily delivery via cron
- ✅ Minimal resource usage (~50-100MB when running, 0MB idle)
- ✅ Version-controlled configuration
- ✅ Comprehensive logging

## 📋 Requirements

- Python 3.11+
- Anthropic API key ([get one here](https://console.anthropic.com/))
- Discord webhook URL ([setup guide](https://support.discord.com/hc/en-us/articles/228383668-Intro-to-Webhooks))
- Linux system with cron (tested on Debian 12 / Raspberry Pi 5)

## 🔧 Installation

### 1. Clone the repository
```bash
git clone https://github.com/kyleGrealis/rss-digest.git
cd rss-digest
```

### 2. Set up Python environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure secrets
```bash
cp .env.example .env
micro .env
# Add your ANTHROPIC_API_KEY and DISCORD_WEBHOOK_URL
```

### 4. Configure feeds and interests
```bash
cp config.example.yml config.yml
micro config.yml
# Add your RSS feeds and personal interests
```

### 5. Test it manually
```bash
# Load environment variables
set -a; source .env; set +a

# Run test
python test_fetcher.py
```

### 6. Set up cron automation
```bash
crontab -e
# Add this line for 7am daily execution:
0 7 * * * cd /home/pi/rss-digest && /home/pi/rss-digest/venv/bin/python /home/pi/rss-digest/src/digest.py >> /home/pi/rss-digest/logs/digest.log 2>&1
```

## 📁 Project Structure
```
rss-digest/
├── src/
│   ├── feed_fetcher.py       # RSS feed parsing
│   ├── summarizer.py         # Claude AI summarization
│   ├── ranker.py             # Article relevance scoring
│   ├── discord_poster.py     # Discord webhook posting
│   └── digest.py             # Main orchestrator
├── config.yml                # RSS feeds & interests (gitignored)
├── .env                      # API keys (gitignored)
├── requirements.txt          # Python dependencies
├── test_fetcher.py           # End-to-end test script
└── logs/                     # Execution logs (gitignored)
```

## ⚙️ Configuration

### RSS Feeds (`config.yml`)
```yaml
feeds:
  - url: "https://www.r-bloggers.com/feed/"
    name: "R-Bloggers"
  - url: "https://example.com/rss"
    name: "Tech News"
```

### Interests (`config.yml`)
Articles are ranked based on keyword matching against interests:
```yaml
interests:
  - "R programming"
  - "biostatistics"
  - "machine learning"
  - "data visualization"
```

### Digest Settings (`config.yml`)
```yaml
digest:
  max_age_hours: 24        # Only articles from last 24 hours
  top_articles: 20         # Total articles to include
  title: "📰 Morning RSS Digest"
```

## 🧪 Testing

Run the test script to validate the full pipeline:
```bash
source venv/bin/activate
set -a; source .env; set +a
python test_fetcher.py
```

This will:
1. Fetch articles from configured feeds
2. Summarize the first 2-3 with Claude
3. Post to Discord channel
4. Show logs and validation

## 📊 Example Output

**Discord Channel:**
```
📰 Morning RSS Digest
Wednesday, December 10, 2025 at 07:00 AM
Found 20 articles

[5 individual messages with full summaries and embeds]
[1 message with next 5 articles and summaries]
[1 message with final 10 headlines]
```

## 🐛 Troubleshooting

### No articles appearing
- Check `logs/digest.log` for errors
- Verify RSS feed URLs are valid
- Ensure articles are within `max_age_hours` window

### Discord webhook not working
- Test webhook manually: `python -c "from src.discord_poster import DiscordPoster; DiscordPoster('YOUR_WEBHOOK').test_webhook()"`
- Verify webhook URL in `.env`
- Check Discord channel permissions

### API errors
- Verify `ANTHROPIC_API_KEY` in `.env`
- Check API usage limits at [console.anthropic.com](https://console.anthropic.com/)
- Review logs for specific error messages

### Cron not running
- Check cron logs: `grep CRON /var/log/syslog`
- Verify paths are absolute in crontab
- Ensure environment variables are set in cron job

## 🔐 Security Notes

- Never commit `.env` or `config.yml` (they're gitignored)
- Keep Anthropic API key private
- Discord webhook URLs should be treated as secrets
- Review `.gitignore` before making repo public

## 🏗️ Architecture Philosophy

This project follows the **"boring technology" principle**:
- ✅ Simple Python scripts (no frameworks)
- ✅ Cron for scheduling (no always-running services)
- ✅ Stateless execution (fresh start each run)
- ✅ Minimal dependencies (5 packages)
- ✅ Easy to understand and debug
- ✅ Low resource usage (0MB when idle)

## 📈 Roadmap

- [x] RSS feed fetching
- [x] Claude AI summarization
- [x] Discord webhook posting
- [x] Article ranking by interests
- [x] Main orchestrator script
- [x] Cron automation
- [x] Multi-tier Discord formatting
- [ ] Optional: MCP wrapper for interactive queries

## 🤝 Contributing

This is a personal automation project, but feel free to:
- Fork it for your own use
- Submit bug reports
- Suggest improvements
- Share your config tweaks

## 📜 License

MIT License - Use it however you want!

## 🙏 Acknowledgments

- Built with [Anthropic Claude](https://www.anthropic.com/)
- RSS parsing via [feedparser](https://feedparser.readthedocs.io/)
- Inspired by the need for a personalized morning digest without the noise

---

**Status:** ✅ Core pipeline working • 🔨 Ranking & orchestration in progress

**Last Updated:** December 10, 2025
