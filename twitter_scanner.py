#!/usr/bin/env python3
"""
Twitter/X Scanner — Fetch tweets via nitter instances for Claude Code to score.

Tries multiple nitter instances with automatic fallback. Solves PoW challenges
where needed. Passes ALL tweets to Claude Code for judgment.

Usage with Claude Code:
    python twitter_scanner.py
    python twitter_scanner.py --json
    python twitter_scanner.py --accounts "karpathy,paulg"
"""

import hashlib, json, re, sys, time, argparse, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# ── Nitter Instance Management ───────────────────────────────────────────────

# Ordered by reliability (checked against status.d420.de, Oct 2026),
# older instances kept as fallbacks. Script tries each until one works.
DEFAULT_INSTANCES = [
    "https://nitter.kareem.one",
    "https://shitter.thepixora.com",
    "https://nitter.pp.ua",
    "https://nitter.meowing.monster",
    "https://nitter.net",
    "https://xcancel.com",
    "https://nitter.poast.org",
    "https://nitter.privacyredirect.com",
    "https://nitter.catsarch.com",
    "https://nitter.tiekoetter.com",
]


# ── Nitter PoW Challenge Solver ──────────────────────────────────────────────

def solve_challenge(challenge):
    """Solve ngx_http_js_challenge_module proof-of-work."""
    byte_offset = int(challenge[0], 16)
    i = 0
    while True:
        solution = challenge + str(i)
        h = hashlib.sha1(solution.encode()).digest()
        if h[byte_offset] == 0xB0 and h[byte_offset + 1] == 0x0B:
            return solution
        i += 1

def get_pow_cookie(instance_url):
    """Fetch challenge page and solve PoW. Returns 'res' cookie value or '' if not needed."""
    try:
        req = urllib.request.Request(instance_url, headers={
            "User-Agent": USER_AGENT,
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")

        # Look for PoW challenge hash (40 hex chars)
        match = re.search(r'[A-Fa-f0-9]{40}', body)
        if match and ("challenge" in body.lower() or "verif" in body.lower() or len(body) < 5000):
            print(f"  Solving PoW challenge...", file=sys.stderr)
            solution = solve_challenge(match.group(0))
            print(f"  Challenge solved.", file=sys.stderr)
            return solution

        # No challenge detected — proceed without cookie
        return ""
    except Exception as e:
        print(f"  [warn] Failed to reach {instance_url}: {e}", file=sys.stderr)
        return None


# ── RSS Fetching ─────────────────────────────────────────────────────────────

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64; rv:138.0) Gecko/20100101 Firefox/138.0"

def is_valid_rss(content):
    """Check if content is actual RSS/Atom XML, not an error page."""
    if not content or len(content) < 100:
        return False
    if not ("<rss" in content or "<feed" in content or "<channel>" in content):
        return False
    # Reject HTML error/challenge pages that slip through
    if "<!DOCTYPE html" in content.lower() or "<html" in content.lower():
        if "<item>" not in content and "<entry>" not in content:
            return False
    # Reject xcancel "not whitelisted" responses (valid RSS but no real data)
    if "not yet whitelisted" in content.lower():
        return False
    # Trial XML parse to catch malformed responses early
    try:
        ET.fromstring(content)
        return True
    except ET.ParseError:
        return False


def fetch_rss(username, instance, pow_cookie, retries=2):
    url = f"{instance}/{username}/rss"
    headers = {"User-Agent": USER_AGENT}
    if pow_cookie:
        headers["Cookie"] = f"res={pow_cookie}"

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                content = resp.read().decode("utf-8", errors="replace")

            if is_valid_rss(content):
                return content

            # Diagnose why it failed
            if "not yet whitelisted" in content.lower():
                print(f"  [warn] @{username}: RSS reader not whitelisted (email required)", file=sys.stderr)
            elif "Verifying" in content or "challenge" in content.lower():
                print(f"  [warn] Got challenge page for @{username}, cookie may be stale", file=sys.stderr)
            elif "<!DOCTYPE" in content or "<html" in content:
                print(f"  [warn] Got HTML error page for @{username} (not RSS)", file=sys.stderr)
            elif len(content) < 200:
                print(f"  [warn] Response too short for @{username} ({len(content)} bytes)", file=sys.stderr)
            else:
                print(f"  [warn] Unrecognized response for @{username} ({len(content)} bytes)", file=sys.stderr)

            if attempt < retries - 1:
                time.sleep(2)
                continue
            return None

        except urllib.error.HTTPError as e:
            if e.code == 429:
                print(f"  [warn] Rate limited on @{username}, waiting...", file=sys.stderr)
                time.sleep(5); continue
            else:
                print(f"  [warn] HTTP {e.code} for @{username}", file=sys.stderr)
            if attempt < retries - 1: time.sleep(2)
            else: return None
        except Exception as e:
            print(f"  [warn] Error fetching @{username}: {e}", file=sys.stderr)
            if attempt < retries - 1: time.sleep(1)
            else: return None
    return None


def parse_rss(xml_content, username):
    tweets = []
    try:
        root = ET.fromstring(xml_content)
    except ET.ParseError as e:
        print(f"  [warn] XML parse error for @{username}: {e}", file=sys.stderr)
        return []

    items = root.findall(".//item")
    if not items:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = root.findall(".//atom:entry", ns)

    for item in items:
        tweet = parse_rss_item(item, username)
        if tweet:
            tweets.append(tweet)
    return tweets


def parse_rss_item(item, username):
    title_el = item.find("title")
    link_el = item.find("link")
    desc_el = item.find("description")
    pubdate_el = item.find("pubDate")

    if title_el is None:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        title_el = item.find("atom:title", ns)
        link_el = item.find("atom:link", ns)
        desc_el = item.find("atom:content", ns) or item.find("atom:summary", ns)
        pubdate_el = item.find("atom:published", ns) or item.find("atom:updated", ns)

    title = title_el.text if title_el is not None and title_el.text else ""
    description = desc_el.text if desc_el is not None and desc_el.text else ""

    if link_el is not None:
        link = link_el.text or link_el.get("href", "")
    else:
        link = ""

    text = clean_html(description) if description else title
    if not text.strip():
        return None

    pub_date = ""
    age_hours = 0
    if pubdate_el is not None and pubdate_el.text:
        pub_date = pubdate_el.text
        age_hours = parse_age(pub_date)

    # Normalize URL to x.com regardless of which instance fetched it
    twitter_url = link
    for d in ["nitter.net", "nitter.poast.org", "xcancel.com",
              "nitter.privacyredirect.com", "nitter.catsarch.com",
              "nitter.tiekoetter.com", "nuku.trabun.org", "lightbrd.com"]:
        twitter_url = twitter_url.replace(d, "x.com")

    is_retweet = text.startswith("RT @") or text.startswith("R to @")
    has_links = "http://" in text or "https://" in text
    word_count = len(text.split())

    return {
        "username": username,
        "text": text[:2000],
        "url": twitter_url,
        "nitter_url": link,
        "pub_date": pub_date,
        "age_hours": round(age_hours, 1),
        "is_retweet": is_retweet,
        "has_links": has_links,
        "word_count": word_count,
    }


def clean_html(html_text):
    text = re.sub(r'<[^>]+>', ' ', html_text)
    text = unescape(text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def parse_age(date_str):
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)
            return max(0, (datetime.now(timezone.utc) - dt).total_seconds() / 3600)
        except ValueError: continue
    return 0


# ── Config ───────────────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "nitter_instances": DEFAULT_INSTANCES,
    "accounts": [
        "JulienBek", "tvytlx", "karpathy", "garrytan",
        "andrewchen", "gregisenberg", "pmarca", "paulg", "danshipper", 
        "jeffdean", "officiallogank", "natolambert", "yuchenj_uw", "michael_chomsky",
        "hwchase17"
    ],
    "twitter_max_age_hours": 72,
    "delay_between_accounts": 2.0,
}

def load_config():
    config_path = Path(__file__).parent / "config.yaml"
    if config_path.exists() and HAS_YAML:
        with open(config_path) as f:
            raw = yaml.safe_load(f) or {}
            merged = {**DEFAULT_CONFIG, **raw}
            # If config only has one instance, prepend defaults for fallback
            if len(merged.get("nitter_instances", [])) <= 1:
                cfg_instances = merged.get("nitter_instances", [])
                # Merge: config instances first, then defaults (deduped)
                seen = set(cfg_instances)
                for inst in DEFAULT_INSTANCES:
                    if inst not in seen:
                        cfg_instances.append(inst)
                        seen.add(inst)
                merged["nitter_instances"] = cfg_instances
            return merged
    return DEFAULT_CONFIG


# ── Instance Probing ─────────────────────────────────────────────────────────

def find_working_instance(instances, test_accounts=None):
    """Try each instance until one returns valid RSS data.
    Tests multiple accounts before giving up on an instance — a single
    suspended/deleted account shouldn't disqualify a working instance."""
    if not test_accounts:
        test_accounts = ["karpathy"]

    for instance in instances:
        print(f"  Trying {instance}...", file=sys.stderr)

        pow_cookie = get_pow_cookie(instance)
        if pow_cookie is None:
            print(f"  [skip] {instance} — unreachable or PoW failed", file=sys.stderr)
            continue

        # Try multiple accounts — one bad account shouldn't skip the instance
        for acct in test_accounts:
            xml = fetch_rss(acct, instance, pow_cookie, retries=1)
            if xml and is_valid_rss(xml):
                print(f"  Using {instance} (verified with @{acct})", file=sys.stderr)
                return instance, pow_cookie

        print(f"  [skip] {instance} — no valid RSS data returned", file=sys.stderr)
        continue

    return None, None


# ── Main Pipeline ────────────────────────────────────────────────────────────

def run_scan(config):
    instances = config["nitter_instances"]
    max_age = config.get("twitter_max_age_hours", config.get("max_age_hours", 72))
    delay = config.get("delay_between_accounts", 2.0)
    accounts = config["accounts"]

    # Use up to 3 accounts for probing — if the first is suspended, try others
    probe_accounts = accounts[:3]
    instance, pow_cookie = find_working_instance(instances, test_accounts=probe_accounts)

    if instance is None:
        print("  [error] No working nitter instance found. All instances tried:", file=sys.stderr)
        for inst in instances:
            print(f"    - {inst}", file=sys.stderr)
        print("  Try again later or add new instances to config.yaml", file=sys.stderr)
        return []

    all_tweets = []
    failed_accounts = []

    for i, username in enumerate(accounts):
        print(f"  [{i+1}/{len(accounts)}] Fetching @{username}...", file=sys.stderr)
        xml_content = fetch_rss(username, instance, pow_cookie)

        if xml_content:
            tweets = parse_rss(xml_content, username)
            tweets = [t for t in tweets if t["age_hours"] <= max_age or t["age_hours"] == 0]
            all_tweets.extend(tweets)
            print(f"    → {len(tweets)} tweets", file=sys.stderr)
        else:
            failed_accounts.append(username)
            print(f"    → no data", file=sys.stderr)

        if i < len(accounts) - 1:
            time.sleep(delay)

    if failed_accounts:
        print(f"  Failed accounts: {', '.join(failed_accounts)}", file=sys.stderr)

    print(f"  Total: {len(all_tweets)} tweets from {len(accounts) - len(failed_accounts)}/{len(accounts)} accounts", file=sys.stderr)

    # Sort longer posts first — user values long quality writeups
    all_tweets.sort(key=lambda x: x["word_count"], reverse=True)
    return all_tweets


def format_for_claude(tweets, max_candidates=80):
    candidates = tweets[:max_candidates]

    lines = []
    lines.append("=" * 70)
    lines.append(f"TWITTER SCANNER — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"Tweets: {len(candidates)}")
    lines.append("=" * 70)
    lines.append("")
    lines.append("SCORING INSTRUCTIONS:")
    lines.append("")
    lines.append("Score each tweet/thread 1-10 based on the following preferences.")
    lines.append("Use your judgment — match the spirit of these preferences,")
    lines.append("including adjacent topics the user didn't explicitly name.")
    lines.append("")
    lines.append("WHAT THE USER FINDS VALUABLE:")
    lines.append("  - Founder experiences and lessons from building companies")
    lines.append("  - AI trends, AI startup ideas, AI integration into industries")
    lines.append("  - Industry veteran or VC writeups and analysis")
    lines.append("  - Problems that can be solved by tech")
    lines.append("  - Software or AI integration into hardware-heavy industries")
    lines.append("    (manufacturing, construction, logistics, etc.)")
    lines.append("  - Sector analysis and industry deep dives")
    lines.append("  - Big industry news: new initiatives, major product launches,")
    lines.append("    strategic pivots by companies")
    lines.append("  - Security breaches and other significant tech-relevant events")
    lines.append("  - Long, quality posts or writeups that develop a real argument")
    lines.append("  - Anything adjacent to the above that you judge would interest")
    lines.append("    a software engineer and aspiring tech founder")
    lines.append("")
    lines.append("WHAT THE USER DOES NOT FIND VALUABLE:")
    lines.append("  - Low-level implementation discussions")
    lines.append("  - Off-topic musings unrelated to tech/business")
    lines.append("  - Politics (unless directly impacting tech industry)")
    lines.append("  - Motivational/lifestyle content")
    lines.append("  - Self-promotional threads about the poster's own product")
    lines.append("  - Hot takes without substance")
    lines.append("  - Note: Retweets should be judged purely on content quality, same as original tweets")
    lines.append("  - Anything you perceive as irrelevant given the above")
    lines.append("")
    lines.append("EXTRA WEIGHT: Give high preference to long-form quality posts")
    lines.append("or writeups. A thoughtful 200-word thread > a pithy one-liner.")
    lines.append("")
    lines.append("Return the top 10-15 tweets ranked by your score with a")
    lines.append("one-line explanation of why each is worth reading.")
    lines.append("Include the URL for each.")
    lines.append("")
    lines.append("-" * 70)

    for i, t in enumerate(candidates, 1):
        rt_tag = " [RT]" if t["is_retweet"] else ""
        link_tag = " [has links]" if t["has_links"] else ""
        lines.append(f"\n[{i}] @{t['username']}{rt_tag}{link_tag}  ({t['word_count']} words, {t['age_hours']}h ago)")
        lines.append(f"    URL: {t['url']}")
        lines.append(f"    ---")
        text = t["text"]
        if len(text) > 500: text = text[:500] + "..."
        for line in text.split("\n"):
            lines.append(f"    {line}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


LAST_SCAN_FILE = Path(__file__).parent / ".last_twitter_scan"


def load_last_scan_time():
    """Read the last scan timestamp from disk. Returns datetime or None."""
    try:
        text = LAST_SCAN_FILE.read_text().strip()
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (FileNotFoundError, ValueError):
        return None


def save_last_scan_time():
    """Write the current UTC timestamp to the last-scan file."""
    LAST_SCAN_FILE.write_text(datetime.now(timezone.utc).isoformat())


def parse_tweet_datetime(date_str):
    """Parse a tweet's pub_date string into a timezone-aware datetime, or None."""
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z", "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ",
    ]
    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def filter_since(tweets, since_dt):
    """Remove tweets older than since_dt."""
    filtered = []
    for t in tweets:
        if not t["pub_date"]:
            filtered.append(t)  # keep tweets with no date (can't filter)
            continue
        tweet_dt = parse_tweet_datetime(t["pub_date"])
        if tweet_dt is None or tweet_dt >= since_dt:
            filtered.append(t)
    return filtered


def main():
    parser = argparse.ArgumentParser(description="Twitter Scanner for Claude Code")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--top", type=int, default=80)
    parser.add_argument("--max-age", type=int)
    parser.add_argument("--accounts", type=str, help="Comma-separated account list")
    parser.add_argument("--since", type=str, help="Only show tweets after this ISO timestamp (e.g. 2026-04-02T00:00:00Z)")
    parser.add_argument("--full", action="store_true", help="Ignore last-scan timestamp, do a full scan")
    args = parser.parse_args()

    config = load_config()
    if args.max_age: config["twitter_max_age_hours"] = args.max_age
    if args.accounts: config["accounts"] = [a.strip().lstrip("@") for a in args.accounts.split(",")]

    # Determine the "since" cutoff
    since_dt = None
    if args.since:
        since_dt = datetime.fromisoformat(args.since)
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)
    elif not args.full:
        since_dt = load_last_scan_time()

    if since_dt:
        print(f"Filtering tweets since {since_dt.isoformat()}", file=sys.stderr)

    print("Twitter Scanner starting...", file=sys.stderr)
    tweets = run_scan(config)

    # Apply since filter if we have one
    if since_dt:
        before = len(tweets)
        tweets = filter_since(tweets, since_dt)
        print(f"  Filtered: {before} → {len(tweets)} tweets (removed {before - len(tweets)} already-seen)", file=sys.stderr)

    print(f"Done. {len(tweets)} tweets fetched.\n", file=sys.stderr)

    # Save timestamp only on successful scan (at least 1 tweet)
    if tweets:
        save_last_scan_time()

    print(json.dumps(tweets[:args.top], indent=2, ensure_ascii=False) if args.json else format_for_claude(tweets, args.top))

if __name__ == "__main__":
    main()
