#!/usr/bin/env python3
"""
HN Scanner — Fetch Hacker News stories for Claude Code to score.

No keyword scoring. Fetches top/best stories with metadata and passes
them ALL to Claude Code. Claude scores based on the user's communicated
preferences and intentions, not keyword matching.

Usage with Claude Code:
    python hn_scanner.py
    python hn_scanner.py --json
    python hn_scanner.py --max-age 24
"""

import json, sys, time, argparse, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

HN_API = "https://hacker-news.firebaseio.com/v0"

def fetch_json(url, retries=3):
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HN-Scanner/1.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < retries - 1: time.sleep(1)
            else:
                print(f"  [warn] Failed to fetch {url}: {e}", file=sys.stderr)
                return None

def load_config():
    config_path = Path(__file__).parent / "config.yaml"
    defaults = {"feeds": ["topstories", "beststories"], "max_stories": 150, "max_age_hours": 48}
    if config_path.exists() and HAS_YAML:
        with open(config_path) as f:
            return {**defaults, **(yaml.safe_load(f) or {})}
    return defaults

def run_scan(config):
    all_ids = []
    for feed in config["feeds"]:
        print(f"  Fetching {feed}...", file=sys.stderr)
        ids = fetch_json(f"{HN_API}/{feed}.json")
        if ids: all_ids.extend(ids)

    seen = set()
    unique_ids = [sid for sid in all_ids if not (sid in seen or seen.add(sid))]
    unique_ids = unique_ids[:config["max_stories"]]
    print(f"  Fetching {len(unique_ids)} stories...", file=sys.stderr)

    cutoff = time.time() - (config["max_age_hours"] * 3600)
    stories = []

    for i, sid in enumerate(unique_ids):
        item = fetch_json(f"{HN_API}/item/{sid}.json")
        if not item or item.get("type") != "story": continue
        if item.get("time", 0) < cutoff or item.get("dead") or item.get("deleted"): continue

        stories.append({
            "id": item["id"],
            "title": item.get("title", ""),
            "url": item.get("url", "") or f"https://news.ycombinator.com/item?id={item['id']}",
            "hn_url": f"https://news.ycombinator.com/item?id={item['id']}",
            "points": item.get("score", 0),
            "comments": item.get("descendants", 0),
            "age_hours": round((time.time() - item.get("time", 0)) / 3600, 1),
            "posted": datetime.fromtimestamp(item.get("time", 0), tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        })
        if (i + 1) % 25 == 0:
            print(f"  ...fetched {i + 1}/{len(unique_ids)}", file=sys.stderr)

    print(f"  {len(stories)} stories within {config['max_age_hours']}h window", file=sys.stderr)
    stories.sort(key=lambda x: x["points"], reverse=True)
    return stories

def format_for_claude(stories):
    lines = []
    lines.append("=" * 70)
    lines.append(f"HN SCANNER — {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"Stories: {len(stories)}")
    lines.append("=" * 70)
    lines.append("")
    lines.append("SCORING INSTRUCTIONS:")
    lines.append("")
    lines.append("Score each story 1-10 based on the following preferences.")
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
    lines.append("  - Anything adjacent to the above that you judge would interest")
    lines.append("    a software engineer and aspiring tech founder")
    lines.append("")
    lines.append("WHAT THE USER DOES NOT FIND VALUABLE:")
    lines.append("  - Low-level implementation discussions (compiler internals,")
    lines.append("    language syntax debates, config file formats, etc.)")
    lines.append("  - Off-topic musings unrelated to tech/business")
    lines.append("  - Politics (unless directly impacting tech industry)")
    lines.append("  - Anything you perceive as irrelevant given the above")
    lines.append("")
    lines.append("Return the top 10-15 stories ranked by your score with a")
    lines.append("one-line explanation of why each is worth reading.")
    lines.append("")
    lines.append("-" * 70)

    for i, s in enumerate(stories, 1):
        lines.append(f"\n[{i}] {s['title']}")
        lines.append(f"    URL: {s['url']}")
        lines.append(f"    HN:  {s['hn_url']}")
        lines.append(f"    Points: {s['points']}  |  Comments: {s['comments']}  |  Age: {s['age_hours']}h")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(description="HN Scanner for Claude Code")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--max-stories", type=int)
    parser.add_argument("--max-age", type=int)
    args = parser.parse_args()

    config = load_config()
    if args.max_stories: config["max_stories"] = args.max_stories
    if args.max_age: config["max_age_hours"] = args.max_age

    print("HN Scanner starting...", file=sys.stderr)
    stories = run_scan(config)
    print(f"Done. {len(stories)} stories ready for scoring.\n", file=sys.stderr)
    print(json.dumps(stories, indent=2) if args.json else format_for_claude(stories))

if __name__ == "__main__":
    main()
