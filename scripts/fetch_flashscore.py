#!/usr/bin/env python3
"""
Fetch Flashscore World Championship 2026 data and build match_cache.json.
Fetches HTML, extracts cjs.initialFeeds data, parses and saves.
"""
import urllib.request
import re
import json
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
}

# Known 2026 FIFA World Cup qualified teams (48 teams)
# This list helps filter out qualification/playoff matches from Flashscore data
QUALIFIED_2026_WC_TEAMS = {
    # Hosts
    'USA', 'United States', 'Canada', 'Mexico',
    # Europe
    'Germany', 'France', 'Spain', 'England', 'Portugal', 'Belgium', 'Italy', 
    'Netherlands', 'Croatia', 'Switzerland', 'Denmark', 'Poland', 'Serbia', 
    'Ukraine', 'Wales', 'Austria', 'Czech Republic', 'Romania', 'Hungary', 
    'Slovakia', 'Sweden', 'Turkey', 'Finland', 'Norway', 'Iceland', 'Greece',
    # South America
    'Argentina', 'Brazil', 'Uruguay', 'Colombia', 'Ecuador', 'Paraguay', 
    'Peru', 'Chile', 'Bolivia', 'Venezuela',
    # Asia
    'Japan', 'South Korea', 'Iran', 'Saudi Arabia', 'Qatar', 'UAE', 
    'United Arab Emirates', 'Iraq', 'Jordan', 'Oman', 'Kuwait', 'Indonesia',
    # Africa
    'Egypt', 'Morocco', 'Algeria', 'Tunisia', 'Cameroon', 'Nigeria', 
    'Senegal', 'Ghana', 'Ivory Coast', 'South Africa', 'Zambia', 'DR Congo',
    'Mali', 'Uganda', 'Kenya', 'Tanzania', 'Mozambique', 'Equatorial Guinea',
    # North America (CONCACAF) - additional
    'Panama', 'Costa Rica', 'Jamaica', 'Honduras', 'Guatemala',
    # Oceania
    'New Zealand',
}

# Team name normalization mapping
TEAM_NAME_NORMALIZATION = {
    'USA': 'United States',
    'United States': 'USA',
    'USA': 'United States',
    'IR Iran': 'Iran',
    'South Korea': 'Korea Republic',
    'Korea Republic': 'South Korea',
    'Ivory Coast': 'Cote d\'Ivoire',
    'Cote d\'Ivoire': 'Ivory Coast',
    'Ivory Coast': 'Ivory Coast',
    'Bosnia & Herzegovina': 'Bosnia-Herzegovina',
    'Bosnia-Herzegovina': 'Bosnia & Herzegovina',
    'Bosnia': 'Bosnia & Herzegovina',
    'Czech Republic': 'Czech Republic',
    'Cape Verde Islands': 'Cape Verde',
    'Cape Verde': 'Cape Verde Islands',
    'DR Congo': 'DR Congo',
    'Democratic Republic of the Congo': 'DR Congo',
    'UAE': 'United Arab Emirates',
    'United Arab Emirates': 'UAE',
}

def normalize_team_name(name):
    """Normalize team name for consistent matching."""
    if not name:
        return name
    # First check if it's in the qualified teams set
    if name in QUALIFIED_2026_WC_TEAMS:
        return name
    # Then check normalization map
    return TEAM_NAME_NORMALIZATION.get(name, name)

def is_qualified_wc_team(team_name):
    """Check if a team is a known 2026 WC qualified team."""
    if not team_name:
        return False
    # Normalize first
    normalized = normalize_team_name(team_name)
    if normalized in QUALIFIED_2026_WC_TEAMS:
        return True
    # Also check the original name
    return team_name in QUALIFIED_2026_WC_TEAMS

def extract_initial_feeds(html):
    """Extract cjs.initialFeeds data from HTML page.
    
    Flashscore now uses structure like:
        cjs.initialFeeds["summary-results"] = { data: `...`, allEventsCount: N }
        cjs.initialFeeds["summary-fixtures"] = { data: `...`, allEventsCount: N }
    
    We need to extract the data from these specific keys.
    """
    feeds = {}
    
    # Extract summary-results
    sr_match = re.search(r'cjs\.initialFeeds\["summary-results"\]\s*=\s*\{([^}]+)\}', html, re.DOTALL)
    if sr_match:
        try:
            # Extract the data field which is in backticks
            data_match = re.search(r'data:\s*`([^`]+)`', sr_match.group(0), re.DOTALL)
            if data_match:
                feeds['summary-results'] = {'data': data_match.group(1)}
        except Exception as e:
            print(f"Error extracting summary-results: {e}")
    
    # Extract summary-fixtures
    sf_match = re.search(r'cjs\.initialFeeds\["summary-fixtures"\]\s*=\s*\{([^}]+)\}', html, re.DOTALL)
    if sf_match:
        try:
            data_match = re.search(r'data:\s*`([^`]+)`', sf_match.group(0), re.DOTALL)
            if data_match:
                feeds['summary-fixtures'] = {'data': data_match.group(1)}
        except Exception as e:
            print(f"Error extracting summary-fixtures: {e}")
    
    return feeds if feeds else None

def parse_feed_block(data_str):
    """Parse a Flashscore feed data string into match dicts."""
    if not data_str or len(data_str) < 10:
        return []
    
    matches = []
    blocks = data_str.split('¬~AA÷')
    
    for block in blocks[1:]:  # Skip first empty block
        m = {}
        
        # Extract fields
        def get(field):
            parts = block.split('¬' + field + '÷')
            if len(parts) > 1:
                return parts[1].split('¬')[0]
            return ''
        
        m['id'] = get('AA')
        ad = get('AD')
        ae = get('AE')  # home team
        af = get('AF')  # away team
        ag = get('AG')  # home score
        at = get('AT')  # away score
        er = get('ER')  # stage
        cx = get('CX')  # team name variant
        
        # Parse timestamp
        if ad:
            try:
                dt = datetime.utcfromtimestamp(int(ad))
                m['datetime'] = dt.strftime('%Y-%m-%dT%H:%M:%S')
            except:
                m['datetime'] = ad
        else:
            m['datetime'] = ''
        
        # Team names - normalize to ensure consistent matching
        # Use CX (canonical name) if available, else AE/AF
        raw_team_a = ae if ae else cx
        raw_team_b = af
        
        # Normalize team names
        m['team_a'] = normalize_team_name(raw_team_a) if raw_team_a else cx
        m['team_b'] = normalize_team_name(raw_team_b) if raw_team_b else ''
        
        # Scores - handle empty strings
        m['score_a'] = ag if ag and ag != '' else None
        m['score_b'] = at if at and at != '' else None
        m['stage'] = er
        
        # Only add if we have at least teams
        if m['team_a'] and m['team_b']:
            matches.append(m)
    
    return matches

def fetch_and_build_cache():
    """Main function to fetch data and build cache."""
    url = "https://www.flashscore.com/football/world/world-championship/"
    
    print("Fetching Flashscore page...")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='replace')
    
    print("Extracting initialFeeds...")
    feeds = extract_initial_feeds(html)
    
    if feeds is None:
        print("ERROR: Could not extract initialFeeds from page")
        return False
    
    # Parse feeds
    sr = feeds.get('summary-results', {})
    sf = feeds.get('summary-fixtures', {})
    results_data = sr.get('data', '') if isinstance(sr, dict) else ''
    fixtures_data = sf.get('data', '') if isinstance(sf, dict) else ''
    
    print(f"summary-results: {len(results_data)} chars")
    print(f"summary-fixtures: {len(fixtures_data)} chars")
    
    results = parse_feed_block(results_data)
    fixtures = parse_feed_block(fixtures_data)
    
    print(f"Parsed: {len(results)} results, {len(fixtures)} fixtures")
    
    # Merge results into fixtures (update scores for completed matches)
    results_map = {(m['team_a'], m['team_b']): m for m in results}
    merged_fixtures = []
    seen = set()
    
    for f in fixtures:
        key = (f['team_a'], f['team_b'])
        if key in results_map:
            r = results_map[key]
            # Update with actual scores
            f['score_a'] = r['score_a']
            f['score_b'] = r['score_b']
            f['stage'] = r.get('stage', f.get('stage', ''))
            # Use the result datetime (more accurate for completed matches)
            if r.get('datetime'):
                f['datetime'] = r['datetime']
        merged_fixtures.append(f)
    
    # Sort results by datetime
    results_sorted = sorted(results, key=lambda x: x.get('datetime', ''))
    fixtures_sorted = sorted(merged_fixtures, key=lambda x: x.get('datetime', ''))
    
    # Filter out qualification/intercontinental playoff (keep only WC tournament matches)
    # WC tournament stages: Round 1, Round 2, Round 3, Round of 16, Quarter-finals, Semi-finals, Third Place, Final
    wc_stages = {'Round 1', 'Round 2', 'Round 3', 'Round of 16', 'Quarter-finals', 
                  'Semi-finals', 'Third Place', 'Final'}
    
    # Build friendly_results from non-tournament matches
    friendly_results = [r for r in results 
                       if r.get('stage', '') not in wc_stages 
                       and r.get('score_a') is not None]
    
    # Build final results (only WC tournament matches that have scores)
    final_results = [r for r in results 
                     if r.get('stage', '') in wc_stages 
                     or r.get('score_a') is not None]
    
    # Also include warm-up friendlies (pre-tournament)
    # These are matches like France vs Germany on June 5, etc.
    # from the "friendly" section
    
    cache = {
        'updated_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S'),
        'results': results_sorted,
        'fixtures': fixtures_sorted,
        'friendly_results': friendly_results
    }
    
    return cache

def main():
    cache = fetch_and_build_cache()
    
    if cache:
        output_path = 'data/match_cache.json'
        with open(output_path, 'w') as f:
            json.dump(cache, f, indent=2, ensure_ascii=False)
        
        print(f"\nSaved to {output_path}")
        print(f"Results: {len(cache['results'])} matches")
        print(f"Fixtures: {len(cache['fixtures'])} matches")
        print(f"Friendly results: {len(cache.get('friendly_results', []))} matches")
        
        # Show recent results
        print("\nRecent results:")
        for m in cache['results'][-8:]:
            sa = m.get('score_a', '?')
            sb = m.get('score_b', '?')
            print(f"  {m.get('datetime','')[:16]} | {m['team_a']} {sa}-{sb} {m['team_b']} [{m.get('stage','')}]")
    else:
        print("Failed to build cache")

if __name__ == '__main__':
    main()
