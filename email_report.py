#!/usr/bin/env python3
"""Send scan results via Gmail SMTP.

Configuration (environment variables, or a git-ignored .env file next to
this script):
    GMAIL_ADDRESS       sender Gmail address
    GMAIL_APP_PASSWORD  app password from https://myaccount.google.com/apppasswords
    SCANNER_RECIPIENTS  comma-separated recipients (defaults to GMAIL_ADDRESS)
"""

import argparse
import html as html_mod
import os
import re
import smtplib
import sys
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path


def load_dotenv():
    """Load KEY=VALUE pairs from a .env file next to this script.

    Real environment variables take precedence over .env entries.
    """
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def markdown_to_html(text):
    """Convert basic markdown to HTML for email rendering."""
    lines = html_mod.escape(text).split("\n")
    out = []
    for line in lines:
        # ## headings → <h2>, ### → <h3>, etc (strip ### from ratings)
        m = re.match(r"^(#{1,4})\s+(.*)", line)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level} style='margin:0.8em 0 0.3em'>{m.group(2)}</h{level}>")
            continue
        # **bold**
        line = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", line)
        # bare URLs → clickable links
        line = re.sub(r"(https?://\S+)", r'<a href="\1">\1</a>', line)
        out.append(line)
    body = "<br>\n".join(out)
    return f"<div style='font-family:sans-serif;font-size:14px;line-height:1.6'>{body}</div>"


def main():
    parser = argparse.ArgumentParser(description="Email scan results via Gmail SMTP")
    parser.add_argument("--file", help="Read results from file instead of stdin")
    parser.add_argument("--to", action="append", default=[], help="Recipient override (can repeat)")
    parser.add_argument("--subject", help="Subject line (default: Reading Scanner — <date>)")
    args = parser.parse_args()

    load_dotenv()

    sender = os.environ.get("GMAIL_ADDRESS")
    if not sender:
        print("Error: GMAIL_ADDRESS environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    password = os.environ.get("GMAIL_APP_PASSWORD")
    if not password:
        print("Error: GMAIL_APP_PASSWORD environment variable is not set.", file=sys.stderr)
        print("Generate one at https://myaccount.google.com/apppasswords", file=sys.stderr)
        sys.exit(1)

    default_recipients = [
        r.strip() for r in os.environ.get("SCANNER_RECIPIENTS", "").split(",") if r.strip()
    ]
    recipients = args.to or default_recipients or [sender]

    if args.file:
        with open(args.file) as f:
            body = f.read()
    else:
        if sys.stdin.isatty():
            print("Error: No input. Pipe scan results or use --file.", file=sys.stderr)
            sys.exit(1)
        body = sys.stdin.read()

    if not body.strip():
        print("Error: Empty input — nothing to send.", file=sys.stderr)
        sys.exit(1)

    date_str = datetime.now().strftime("%Y-%m-%d")
    subject = args.subject or f"Reading Scanner — {date_str}"

    body_html = markdown_to_html(body)
    msg = MIMEText(body_html, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = ", ".join(recipients)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipients, msg.as_string())
        print(f"Sent to {', '.join(recipients)}")
    except smtplib.SMTPAuthenticationError:
        print("Error: Gmail authentication failed. Check GMAIL_APP_PASSWORD.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error sending email: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
