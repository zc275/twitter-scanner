# Reading Scanner (HN + Twitter)

Two scripts that fetch content from Hacker News and Twitter/X. They collect everything and hand it to you (Claude Code) for scoring. There is NO keyword filtering — you make all the judgment calls.

## Quick Start

```bash
python3 hn_scanner.py                  # Scan HN
python3 twitter_scanner.py             # Scan Twitter/X
python3 hn_scanner.py && echo "---" && python3 twitter_scanner.py  # Both
```

## How It Works

**hn_scanner.py** fetches top/best stories from the HN Firebase API, collects metadata (title, URL, points, comments, age), and outputs them all for you to score.

**twitter_scanner.py** solves the nitter.poast.org proof-of-work challenge, pulls RSS feeds for tracked accounts, parses tweets, and outputs them all for you to score. Longer posts are listed first since the user values those.

## Your Scoring Job

Score each item 1-10. Use your judgment — match the SPIRIT of these preferences, including adjacent topics not explicitly listed.

### What the user finds valuable:
- Founder experiences and lessons from building companies
- AI trends, AI startup ideas, AI integration into industries
- Industry veteran or VC writeups and analysis
- Problems that can be solved by tech
- Software or AI integration into hardware-heavy industries (manufacturing, construction, logistics, etc.)
- Sector analysis and industry deep dives
- Big industry news: new initiatives, major product launches, strategic pivots
- Security breaches and other significant tech-relevant events
- **For Twitter especially:** long, quality posts or writeups that develop a real argument

### What the user does NOT find valuable:
- Low-level implementation discussions (compiler internals, syntax debates, config formats)
- Off-topic musings unrelated to tech/business
- Politics (unless directly impacting tech industry)
- Motivational/lifestyle content, self-promotional threads, hot takes without substance
- Note: Retweets should be judged purely on content quality, same as original tweets

### User context:
Software engineer and aspiring tech founder. Things adjacent to what's listed above — that you judge would interest someone with this background — should also score highly.

## CLI Options

```bash
python3 hn_scanner.py --json                  # JSON output
python3 hn_scanner.py --max-age 24            # Last 24h only
python3 hn_scanner.py --max-stories 200       # More stories

python3 twitter_scanner.py --json             # JSON output
python3 twitter_scanner.py --max-age 48       # Last 48h only
python3 twitter_scanner.py --top 40           # Fewer candidates
python3 twitter_scanner.py --accounts "karpathy,paulg"  # Override accounts
```

## Configuration

Edit `config.yaml` to adjust accounts, age windows, and Nitter instance.

## Dependencies

- Python 3.10+
- `pyyaml` (optional — falls back to built-in defaults)

```bash
pip install pyyaml
```

## Email Delivery

`email_report.py` sends scored results to email via Gmail SMTP.

**One-time setup:**
1. Go to https://myaccount.google.com/apppasswords
2. Generate an App Password for "Mail"
3. Add to your shell profile:
   ```bash
   export GMAIL_ADDRESS="you@gmail.com"
   export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
   export SCANNER_RECIPIENTS="you@gmail.com,other@example.com"  # optional, defaults to GMAIL_ADDRESS
   ```

**Usage:**
```bash
# Pipe directly
python3 hn_scanner.py | python3 email_report.py

# Or save results first, then email
python3 email_report.py --file /tmp/scan_results.txt

# Custom recipient
python3 email_report.py --file /tmp/scan_results.txt --to someone@example.com
```

The `/scan-both`, `/scan-hn`, and `/scan-twitter` slash commands automatically
email results after scoring when `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` are set.
Recipients come from `SCANNER_RECIPIENTS` — do not pass `--to` unless the user
asks for a different recipient.
