#!/usr/bin/env bash
# run-digest.sh - RSS Morning Digest runner
# Called by cron at 7am daily

set -e

cd /home/kyle/rss-digest

# Load environment variables
set -a
source .env
set +a

# Run the digest (logging handled by Python script itself)
/home/kyle/rss-digest/venv/bin/python /home/kyle/rss-digest/src/digest.py "$@"
