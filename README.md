# Reading Scanner

A personal reading curator built on [Claude Code](https://claude.com/claude-code). Two small Python scripts fetch candidates from Hacker News and Twitter/X; Claude scores every item against your taste and hands you (or emails you) a ranked reading list.

The design bet: **no keyword filters**. Keyword matching can't tell a founder postmortem from a syntax flamewar. Instead, the scanners collect *everything* recent and pass it to an LLM with a plain-English description of what you find valuable. The LLM is the ranking function — and you tune it by editing prose, not regexes.

## How it works

```
hn_scanner.py       ─┐
                     ├─→  all candidates + scoring rubric  ─→  Claude Code  ─→  ranked top 10-15  ─→  (optional) email
twitter_scanner.py  ─┘
```

- **`hn_scanner.py`** pulls top/best stories from the HN Firebase API with points, comments, and age.
- **`twitter_scanner.py`** fetches tweets for accounts you follow via public [nitter](https://github.com/zedeus/nitter) instances (with automatic instance fallback and proof-of-work challenge solving), and lists longer posts first.
- **`CLAUDE.md`** holds the scoring rubric — what you care about, what you don't. Edit it in plain English to retune everything.
- **`email_report.py`** (optional) sends the ranked list via Gmail SMTP.

## Quick start

Requires Python 3.10+ and [Claude Code](https://claude.com/claude-code). `pyyaml` is optional (`pip install pyyaml`) — without it the built-in defaults are used instead of `config.yaml`.

```bash
git clone <this repo> && cd <repo>
claude
```

Then, inside Claude Code:

```
/scan-hn        # Hacker News only
/scan-twitter   # Twitter/X only
/scan-both      # both, merged into one list
```

Each command runs the scanner(s), scores the results against `CLAUDE.md`, and presents a ranked reading list with a one-line reason per item.

The scanners also run standalone if you just want the raw candidates:

```bash
python3 hn_scanner.py --max-age 24          # last 24h of HN
python3 twitter_scanner.py --top 40         # top 40 tweet candidates
python3 twitter_scanner.py --json           # machine-readable output
python3 twitter_scanner.py --accounts "karpathy,paulg"
```

## Make it yours

1. **Taste** — edit the "What the user finds valuable / does NOT find valuable" sections in `CLAUDE.md`.
2. **Sources** — edit `accounts` (Twitter) and `feeds`/`max_age_hours` (HN) in `config.yaml`.

## Email delivery (optional)

Uses Gmail SMTP with an [app password](https://myaccount.google.com/apppasswords):

```bash
export GMAIL_ADDRESS="you@gmail.com"
export GMAIL_APP_PASSWORD="xxxx xxxx xxxx xxxx"
export SCANNER_RECIPIENTS="you@gmail.com,partner@example.com"   # optional, defaults to GMAIL_ADDRESS
```

Or put the same `KEY=VALUE` lines in a `.env` file next to the scripts (git-ignored; real environment variables take precedence).

```bash
python3 hn_scanner.py | python3 email_report.py
python3 email_report.py --file results.txt --subject "Morning reads"
```

When these variables are set, the `/scan-*` commands email the ranked list automatically.

## Run it every morning

Claude Code runs headless with `-p`, so the whole pipeline — scan, score, email — can run on a schedule with no terminal open. On macOS, a launchd job like this runs it daily at 8 AM:

```xml
<key>ProgramArguments</key>
<array>
    <string>/bin/zsh</string>
    <string>-lc</string>
    <string>source ~/.zshrc >/dev/null 2>&1; exec claude -p "/scan-twitter" --allowedTools "Read,Write,Bash(python3:*)"</string>
</array>
<key>WorkingDirectory</key>
<string>/path/to/this/repo</string>
<key>StartCalendarInterval</key>
<dict><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
```

On Linux, the equivalent cron line:

```cron
0 8 * * * cd /path/to/this/repo && claude -p "/scan-twitter" --allowedTools "Read,Write,Bash(python3:*)"
```

## Notes

- Nitter instances are community-run and come and go. The scanner probes the list in `config.yaml` and uses the first one that works; `delay_between_accounts` keeps request rates polite. If they're all down, try again later or add fresh instances.
- `twitter_scanner.py` remembers the last scan time in `.last_twitter_scan` and only shows new tweets since then. Use `--full` to rescan everything, or `--since <ISO timestamp>` for a custom cutoff.

## License

MIT
