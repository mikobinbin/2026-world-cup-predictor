#!/usr/bin/env python3
"""
Fetch 2026 FIFA World Cup match data from Wikipedia and build match_cache.json.
Uses HTML parsing of the Wikipedia article since wikitext doesn't contain scoreboard templates.
"""
import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html',
}
# Known 2026 FIFA World Cup qualified teams (48 teams)
# This list helps filter out qualification/playoff matches from Flashscore data
QUALIFIED_2026_WC_TEAMS = {
    # Hosts
    'USA', 'United States', 'Canada', 'Mexico',
    # Europe
    'Germany', 'France', 'Spain', 'England', 'Portugal', 'Belgium', 'Italy', 
    'Netherlands', 'Croatia', 'Switzerland', 'Denmark', 'Poland', 'Serbia', 
    'Ukraine', 'Wales', 'Austria', 'Czech Republic', 'Czechia', 'Romania', 'Hungary', 
    'Slovakia', 'Sweden', 'Turkey', 'Finland', 'Norway', 'Iceland', 'Greece',
    'Scotland', 'Bosnia and Herzegovina', 'Bosnia & Herzegovina', 'Bosnia-Herzegovina', 'Bosnia',
    # South America
    'Argentina', 'Brazil', 'Uruguay', 'Colombia', 'Ecuador', 'Paraguay', 
    'Peru', 'Chile', 'Bolivia', 'Venezuela',
    # Asia
    'Japan', 'South Korea', 'Korea Republic', 'Iran', 'Saudi Arabia', 'Qatar', 'UAE', 
    'United Arab Emirates', 'Iraq', 'Jordan', 'Oman', 'Kuwait', 'Indonesia',
    'Australia', 'Uzbekistan', 'Cape Verde', 'Cape Verde Islands',
    # Africa
    'Egypt', 'Morocco', 'Algeria', 'Tunisia', 'Cameroon', 'Nigeria', 
    'Senegal', 'Ghana', 'Ivory Coast', 'Cote d\'Ivoire', 'South Africa', 'Zambia', 'DR Congo',
    'Mali', 'Uganda', 'Kenya', 'Tanzania', 'Mozambique', 'Equatorial Guinea',
    'Haiti',
    # North America (CONCACAF) - additional
    'Panama', 'Costa Rica', 'Jamaica', 'Honduras', 'Guatemala',
    # Oceania
    'New Zealand',
    # Playoff winners / inter-confederation
    'Curaçao',
}

# Team name normalization mapping
# Maps various aliases to the MODEL STANDARD names (used in elo_cache and players data)
# Model standard: 'South Korea', 'USA', 'Iran', 'United Arab Emirates', 'Cape Verde Islands', 'Curaçao'
TEAM_NAME_NORMALIZATION = {
    # Wikipedia/Flashscore aliases → model standard
    'United States': 'USA',
    'Korea Republic': 'South Korea',
    'IR Iran': 'Iran',
    'Iran': 'Iran',
    'United Arab Emirates': 'UAE',
    'UAE': 'UAE',
    'Cape Verde Islands': 'Cape Verde Islands',
    'Cape Verde': 'Cape Verde Islands',
    'Cote d\'Ivoire': 'Ivory Coast',
    'Ivory Coast': 'Ivory Coast',
    'Bosnia & Herzegovina': 'Bosnia and Herzegovina',
    'Bosnia-Herzegovina': 'Bosnia and Herzegovina',
    'Democratic Republic of the Congo': 'DR Congo',
    'Czechia': 'Czech Republic',
    'Curacao': 'Curaçao',
    'Democratic Republic of Congo': 'DR Congo',
}

# Map country names to timezone offsets (hours)
# Based on FIFA's venue locations for 2026 WC
COUNTRY_TIMEZONES = {
    'USA': -4,  # Eastern (will vary)
    'United States': -4,
    'Canada': -4,
    'Mexico': -6,
    'Argentina': -3,
    'Brazil': -3,
    'Uruguay': -3,
    'Colombia': -5,
    'Ecuador': -5,
    'Paraguay': -4,
    'Peru': -5,
    'Chile': -4,
    'Bolivia': -4,
    'Venezuela': -4,
    'Japan': 9,
    'South Korea': 9,
    'Korea Republic': 9,
    'Iran': 3,
    'Saudi Arabia': 3,
    'Qatar': 3,
    'United Arab Emirates': 4,
    'UAE': 4,
    'Iraq': 3,
    'Jordan': 3,
    'Oman': 4,
    'Kuwait': 3,
    'Indonesia': 7,
    'Egypt': 2,
    'Morocco': 1,
    'Algeria': 1,
    'Tunisia': 1,
    'Cameroon': 1,
    'Nigeria': 1,
    'Senegal': 0,
    'Ghana': 0,
    'Ivory Coast': 0,
    'Cote d\'Ivoire': 0,
    'South Africa': 2,
    'Zambia': 2,
    'DR Congo': 2,
    'Mali': 0,
    'Uganda': 3,
    'Kenya': 3,
    'Tanzania': 3,
    'Mozambique': 2,
    'Equatorial Guinea': 1,
    'Panama': -5,
    'Costa Rica': -6,
    'Jamaica': -5,
    'Honduras': -6,
    'Guatemala': -6,
    'New Zealand': 12,
    'Germany': 2,
    'France': 2,
    'Spain': 2,
    'England': 1,
    'Portugal': 1,
    'Belgium': 2,
    'Italy': 2,
    'Netherlands': 2,
    'Croatia': 2,
    'Switzerland': 2,
    'Denmark': 2,
    'Poland': 2,
    'Serbia': 2,
    'Ukraine': 3,
    'Wales': 1,
    'Austria': 2,
    'Romania': 3,
    'Hungary': 2,
    'Slovakia': 2,
    'Sweden': 2,
    'Turkey': 3,
    'Finland': 3,
    'Norway': 2,
    'Iceland': 0,
    'Greece': 3,
    'Scotland': 0,
    'Haiti': -5,
}

# Known timezone offset from the HTML (UTC-6 for Mexico City matches, etc.)
def parse_wikipedia_datetime(date_str, time_str, tz_offset_str):
    """Parse Wikipedia date and time into UTC datetime.
    
    Args:
        date_str: e.g., "June 11, 2026"
        time_str: e.g., "1:00 p.m."
        tz_offset_str: e.g., "UTC−6" or "UTC−5"
    
    Returns:
        UTC datetime string in ISO format
    """
    try:
        # Parse date
        date_str = date_str.strip()
        time_str = time_str.strip().replace('\xa0', ' ')
        
        # Parse timezone offset
        tz_match = re.search(r'UTC([−\-])(\d+)', tz_offset_str)
        if tz_match:
            sign = -1 if tz_match.group(1) in ['−', '-'] else 1
            tz_hours = int(tz_match.group(2)) * sign
        else:
            tz_hours = 0
        
        # Parse time (handles "1:00 p.m." format)
        time_match = re.match(r'(\d+):(\d+)\s*(a\.m\.|p\.m\.)', time_str, re.IGNORECASE)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            ampm = time_match.group(3).lower()
            if ampm == 'p.m.' and hour != 12:
                hour += 12
            elif ampm == 'a.m.' and hour == 12:
                hour = 0
        else:
            hour, minute = 12, 0
        
        # Parse date
        dt = datetime.strptime(date_str, '%B %d, %Y')
        dt = dt.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        # Convert to UTC by subtracting the timezone offset
        # Wikipedia times are in local time at the venue
        utc_dt = dt - timedelta(hours=tz_hours)
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
        
        return utc_dt.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception as e:
        print(f"Error parsing datetime: {date_str} {time_str} - {e}")
        return None


def normalize_team_name(name):
    """Normalize team name for consistent matching."""
    if not name:
        return name
    # First check if it's in the qualified teams set
    if name in QUALIFIED_2026_WC_TEAMS:
        return name
    # Then check normalization map
    return TEAM_NAME_NORMALIZATION.get(name, name)


def extract_stage_from_url(score_url):
    """Extract stage from the score URL (e.g., '2026_FIFA_World_Cup_Group_A#Mexico_vs_South_Africa')."""
    if not score_url:
        return 'Unknown'
    
    url = score_url.lower()
    if 'group_a' in url:
        return 'Group A'
    elif 'group_b' in url:
        return 'Group B'
    elif 'group_c' in url:
        return 'Group C'
    elif 'group_d' in url:
        return 'Group D'
    elif 'group_e' in url:
        return 'Group E'
    elif 'group_f' in url:
        return 'Group F'
    elif 'group_g' in url:
        return 'Group G'
    elif 'group_h' in url:
        return 'Group H'
    elif 'group_i' in url:
        return 'Group I'
    elif 'group_j' in url:
        return 'Group J'
    elif 'group_k' in url:
        return 'Group K'
    elif 'group_l' in url:
        return 'Group L'
    elif 'round_of_16' in url:
        return 'Round of 16'
    elif 'quarter-final' in url:
        return 'Quarter-finals'
    elif 'semi-final' in url:
        return 'Semi-finals'
    elif 'third_place' in url:
        return 'Third Place'
    elif 'final' in url:
        return 'Final'
    else:
        return 'Unknown'


def fetch_wikipedia_matches():
    """Fetch match data from Wikipedia."""
    url = 'https://en.wikipedia.org/wiki/2026_FIFA_World_Cup'
    
    print("Fetching Wikipedia page...")
    r = requests.get(url, headers=HEADERS, timeout=30)
    r.raise_for_status()
    
    print(f"Page content length: {len(r.text)} chars")
    
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Find all footballbox divs
    boxes = soup.find_all('div', class_='footballbox')
    print(f"Found {len(boxes)} match boxes")
    
    results = []
    fixtures = []
    friendly_results = []
    
    for i, box in enumerate(boxes):
        try:
            # Extract date and time
            date_el = box.find('div', class_='fdate')
            time_el = box.find('div', class_='ftime')
            time_link = box.find('a', href=re.compile(r'UTC'))
            
            date_str = date_el.get_text(strip=True).split('(')[0].strip() if date_el else ''
            time_str = time_el.get_text(strip=True) if time_el else ''
            tz_text = time_link.get_text(strip=True) if time_link else 'UTC'
            
            # Extract teams
            home_el = box.find('th', class_='fhome')
            away_el = box.find('th', class_='faway')
            score_el = box.find('th', class_='fscore')
            
            home = home_el.get_text(strip=True) if home_el else ''
            away = away_el.get_text(strip=True) if away_el else ''
            score_text = score_el.get_text(strip=True) if score_el else ''
            
            # Get score URL for stage determination
            score_link = score_el.find('a') if score_el else None
            score_url = score_link.get('href', '') if score_link else ''
            stage = extract_stage_from_url(score_url)
            
            # Normalize team names
            home = normalize_team_name(home)
            away = normalize_team_name(away)
            
            # Parse score
            score_a = None
            score_b = None
            if score_text and '–' in score_text:
                parts = score_text.split('–')
                try:
                    score_a = int(parts[0].strip())
                    score_b = int(parts[1].strip())
                except ValueError:
                    pass
            
            # Parse datetime to UTC
            utc_datetime = parse_wikipedia_datetime(date_str, time_str, tz_text)
            
            # Create match dict
            match = {
                'id': f'match_{i+1:03d}',
                'datetime': utc_datetime or '',
                'team_a': home,
                'team_b': away,
                'score_a': score_a,
                'score_b': score_b,
                'stage': stage,
            }
            
            # Categorize: results (completed), fixtures (upcoming), friendly_results
            # Only count as WC results if BOTH teams are qualified WC teams
            team_a_qualified = home in QUALIFIED_2026_WC_TEAMS
            team_b_qualified = away in QUALIFIED_2026_WC_TEAMS
            
            if score_a is not None and score_b is not None:
                # Check if it's a friendly or actual WC match
                if team_a_qualified and team_b_qualified:
                    # Both teams qualified - it's a WC match
                    results.append(match)
                else:
                    # At least one team not qualified - it's a friendly
                    friendly_results.append(match)
            else:
                fixtures.append(match)
                
        except Exception as e:
            print(f"Error parsing match {i}: {e}")
            continue
    
    # Sort results and fixtures by datetime
    results.sort(key=lambda x: x.get('datetime', ''))
    fixtures.sort(key=lambda x: x.get('datetime', ''))
    
    return {
        'updated_at': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S'),
        'results': results,
        'fixtures': fixtures,
        'friendly_results': friendly_results,
    }


def main():
    print("=" * 60)
    print("2026 FIFA World Cup - Wikipedia Match Fetcher")
    print("=" * 60)
    
    cache = fetch_wikipedia_matches()
    
    # Save to data/match_cache.json
    output_path = 'data/match_cache.json'
    with open(output_path, 'w') as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)
    
    print(f"\nSaved to {output_path}")
    print(f"Results (completed matches): {len(cache['results'])}")
    print(f"Fixtures (upcoming matches): {len(cache['fixtures'])}")
    print(f"Friendly results: {len(cache.get('friendly_results', []))}")
    
    # Show recent results
    if cache['results']:
        print("\nCompleted matches:")
        for m in cache['results'][:15]:
            sa = m.get('score_a', '?')
            sb = m.get('score_b', '?')
            print(f"  {m.get('datetime','')[:16]} | {m['team_a']} {sa}-{sb} {m['team_b']} [{m.get('stage','')}]")
        if len(cache['results']) > 15:
            print(f"  ... and {len(cache['results']) - 15} more")
    
    # Show upcoming fixtures
    if cache['fixtures']:
        print("\nUpcoming fixtures (first 10):")
        for m in cache['fixtures'][:10]:
            print(f"  {m.get('datetime','')[:16]} | {m['team_a']} vs {m['team_b']} [{m.get('stage','')}]")
        if len(cache['fixtures']) > 10:
            print(f"  ... and {len(cache['fixtures']) - 10} more")


if __name__ == '__main__':
    main()