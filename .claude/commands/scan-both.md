---
allowed-tools: Bash, Read, Write
description: Scan HN and Twitter for today's best reads
---

Run the reading scanners and score the results.

1. Run `python3 hn_scanner.py` and capture the output
2. Run `python3 twitter_scanner.py` and capture the output
3. Read `CLAUDE.md` for scoring guidelines
4. Score and rank ALL candidates using the scoring guidelines
5. Present a ranked reading list — top 10 from each source, with scores and a one-line reason for each
6. If `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` are set, write the ranked list to a temp file and email it: `python3 email_report.py --file <temp file>`. If they're not set, skip this step silently.

If either scanner fails (network error, nitter down), report it and continue with the other.
