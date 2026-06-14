#!/usr/bin/env python3
"""
Fetch Flashscore World Championship 2026 data and build match_cache.json.
Run: python3 scripts/fetch_flashscore.py

This script fetches the Flashscore tournament page HTML, extracts the
initialFeeds data (fixtures + results), and builds the local match_cache.json.
"""
import urllib.request
import re
import json
import os
import sys
from datetime import datetime

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.flashscore.com/',
}

CACHE_PATH = os.path.join(PROJECT_ROOT, 'data', 'match_cache.json')

def fetch_page(url):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=20) as resp:
        return resp.read().decode('utf-8')

def extract_feeds(html):
    """Extract cjs.initialFeeds data from HTML script tags."""
    feeds = {}
    pattern = re.compile(
        r'cjs\.initialFeeds\["([^"]+)"\]\s*=\s*\{\s*data:\s*`([^`]*)`',
        re.DOTALL
    )
    for match in pattern.finditer(html):
        key, data = match.groups()
        feeds[key] = data
    return feeds

def main():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Fetching Flashscore...")
    
    url = 'https://www.flashscore.com/football/world/world-championship/'
    html = fetch_page(url)
    feeds = extract_feeds(html)
    
    print(f"  HTML: {len(html):,} chars")
    print(f"  Feeds: {list(feeds.keys())}")
    for name, data in feeds.items():
        print(f"    {name}: {len(data):,} chars")

    if 'summary-results' not in feeds or 'summary-fixtures' not in feeds:
        print("ERROR: Missing required feeds!")
        sys.exit(1)

    from src.models.match_data import MatchDataFetcher
    
    fetcher = MatchDataFetcher(cache_path=CACHE_PATH)
    fetcher.parse_feeds(
        fixtures_raw=feeds.get('summary-fixtures', ''),
        results_raw=feeds.get('summary-results', ''),
        friendly_raw=''  # Dynamically loaded; not available from static HTML
    )
    
    print(f"\nCache built:")
    print(f"  Fixtures: {len(fetcher.fixtures)} matches")
    print(f"  Results: {len(fetcher.results)} matches")
    print(f"  Friendly results: {len(fetcher.friendly_results)} matches")
    print(f"  Updated: {fetcher.updated_at}")
    print(f"  Saved: {CACHE_PATH}")
    
    if fetcher.results:
        print("\nResults (newest first):")
        for m in sorted(fetcher.results, key=lambda x: x.get('datetime', ''), reverse=True)[:10]:
            print(f"  {m['datetime']} | {m['team_a']} vs {m['team_b']} | {m.get('score_a','?')}-{m.get('score_b','?')}")

if __name__ == '__main__':
    main()
