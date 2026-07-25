---
allowed-tools: Bash, Read, Write
description: Scan Hacker News only for today's best reads
---

Run only the HN scanner and score the results.

1. Run `python3 hn_scanner.py` and capture the output
2. Read `CLAUDE.md` for scoring guidelines
3. Score and rank the candidates using the scoring guidelines
4. Present a ranked reading list — top 10-15 stories, with scores and a one-line reason for each
5. If `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` are set, write the ranked list to a temp file and email it: `python3 email_report.py --file <temp file>`. If they're not set, skip this step silently.
