#!/usr/bin/env python3
"""
Transfermarkt 2026 World Cup Squad Data Scraper
直接从 Transfermarkt 官网抓取各参赛队大名单数据（球员姓名、年龄、位置、俱乐部、市场价、代表队出场/进球）
用法：
    python scripts/transfermarkt_scraper.py --output data/wc2026_squads.json
"""

import requests
from bs4 import BeautifulSoup
import json
import time
import re
import argparse
from typing import Optional

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# 2026世界杯48支参赛队对应 Transfermarkt 的 club_id / team_id
# 数据来源：Transfermarkt URL格式 https://www.transfermarkt.com/{team-name}/kader/verein/{team_id}/saison_id/{season}
# 2026世界杯的赛季ID通常为 2025/2026
TEAM_URLS = {
    "Argentina": ("https://www.transfermarkt.com/fifa-weltmeisterschaft-2026/startseite/pokalwettbewerb/WM26", "national"),
    # 完整48队名单（按Transfermarkt URL格式）
}

def fetch_page(url: str, retries: int = 3) -> Optional[BeautifulSoup]:
    """抓取并解析网页"""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 200:
                return BeautifulSoup(resp.text, "html.parser")
            print(f"  ⚠️ HTTP {resp.status_code} for {url} (attempt {attempt+1}/{retries})")
        except Exception as e:
            print(f"  ❌ Error: {e} (attempt {attempt+1}/{retries})")
        time.sleep(2)
    return None


def parse_national_team_squad(soup: BeautifulSoup, team_name: str) -> list:
    """解析国家队大名单页面"""
    players = []
    rows = soup.select("table.items tbody tr")
    for row in rows:
        try:
            # 号码
            number_elem = row.select_one("td.zentriert.rn_tnummer")
            number = number_elem.get_text(strip=True) if number_elem else None

            # 姓名（可能在 <a> 里）
            name_elem = row.select_one("td.hauptlink a")
            name = name_elem.get_text(strip=True) if name_elem else None

            # 位置
            pos_elem = row.select("td.hauptlink")[1] if len(row.select("td.hauptlink")) > 1 else None
            position = pos_elem.get_text(strip=True) if pos_elem else None

            # 出生日期 / 年龄
            age_elem = row.select_one("td.zentriert.alternate")
            age_text = age_elem.get_text(strip=True) if age_elem else None
            age_match = re.search(r"(\d{2})", age_text) if age_text else None
            age = int(age_match.group(1)) if age_match else None

            # 俱乐部
            club_elem = row.select_one("td.zentriert img[title]")
            club = club_elem.get("title") if club_elem else None if club_elem else None
            club = row.select("td.zentriert")[3].get_text(strip=True) if len(row.select("td.zentriert")) > 3 else None

            # 市场价
            mv_elem = row.select_one("td.rechts.hauptlink")
            market_value = mv_elem.get_text(strip=True) if mv_elem else None

            # 国际比赛场次/进球
            caps_goals_elem = row.select_one("td.zentriert:not(.hide-for-small):not(.rn_tnummer)")
            caps_text = caps_goals_elem.get_text(strip=True) if caps_goals_elem else None

            players.append({
                "name": name,
                "number": number,
                "position": position,
                "age": age,
                "club": club,
                "market_value": market_value,
                "caps_goals": caps_text,
            })
        except Exception as e:
            print(f"  ⚠️ Row parse error: {e}")
            continue
    return players


def fetch_wc2026_squads() -> dict:
    """
    抓取2026世界杯完整48队大名单
    Transfermarkt 2026世界杯主页
    """
    print("🌐 正在抓取 Transfermarkt 2026世界杯数据...")

    # 2026世界杯主页 URL
    main_url = "https://www.transfermarkt.com/fifa-weltmeisterschaft-2026/startseite/pokalwettbewerb/WM26"

    # 先从主页面找到48支参赛队链接
    all_squads = {}
    visited_urls = set()

    # 尝试直接访问各参赛队的国家队页面
    # 国家队 squad 页面格式: https://www.transfermarkt.com/{country-name}/kader/verein/{country_id}/saison_id/2025
    national_urls = {
        # 种子队/强队（从 Transfermarkt 实际 URL 规律构建）
        "Argentina": "https://www.transfermarkt.com/argentinien/kader/verein/343",
        "Brazil": "https://www.transfermarkt.com/brasilien/kader/verein/340",
        "France": "https://www.transfermarkt.com/frankreich/kader/verein/337",
        "Germany": "https://www.transfermarkt.com/deutschland/kader/verein/326",
        "Spain": "https://www.transfermarkt.com/spanien/kader/verein/368",
        "England": "https://www.transfermarkt.com/england/kader/verein/3302",
        "Portugal": "https://www.transfermarkt.com/portugal/kader/verein/325",
        "Netherlands": "https://www.transfermarkt.com/niederlande/kader/verein/342",
        "Italy": "https://www.transfermarkt.com/italien/kader/verein/357",
        "Belgium": "https://www.transfermarkt.com/belgien/kader/verein/309",
        "Croatia": "https://www.transfermarkt.com/kroatien/kader/verein/346",
        "Uruguay": "https://www.transfermarkt.com/uruguay/kader/verein/349",
        "Colombia": "https://www.transfermarkt.com/kolumbien/kader/verein/345",
        "Mexico": "https://www.transfermarkt.com/mexiko/kader/verein/3633",
        "USA": "https://www.transfermarkt.com/usa/kader/verein/3535",
        "Canada": "https://www.transfermarkt.com/kanada/kader/verein/2892",
        "Japan": "https://www.transfermarkt.com/japan/kader/verein/2820",
        "South Korea": "https://www.transfermarkt.com/suedkorea/kader/verein/2827",
        "Australia": "https://www.transfermarkt.com/australien/kader/verein/3447",
        "Morocco": "https://www.transfermarkt.com/marokko/kader/verein/3392",
        "Senegal": "https://www.transfermarkt.com/senegal/kader/verein/3504",
        "Egypt": "https://www.transfermarkt.com/aegypten/kader/verein/3437",
        "Nigeria": "https://www.transfermarkt.com/nigeria/kader/verein/3420",
        "Cameroon": "https://www.transfermarkt.com/kamerun/kader/verein/3472",
        "Ghana": "https://www.transfermarkt.com/ghana/kader/verein/3387",
        "Algeria": "https://www.transfermarkt.com/algerien/kader/verein/3433",
        "Ivory Coast": "https://www.transfermarkt.com/elfenbeinkueste/kader/verein/3438",
        "Tunisia": "https://www.transfermarkt.com/tunesien/kader/verein/3430",
        "Poland": "https://www.transfermarkt.com/polen/kader/verein/3531",
        "Ukraine": "https://www.transfermarkt.com/ukraine/kader/verein/3477",
        "Switzerland": "https://www.transfermarkt.com/schweiz/kader/verein/3533",
        "Austria": "https://www.transfermarkt.com/oesterreich/kader/verein/3498",
        "Denmark": "https://www.transfermarkt.com/daenemark/kader/verein/3304",
        "Sweden": "https://www.transfermarkt.com/schweden/kader/verein/3354",
        "Norway": "https://www.transfermarkt.com/norwegen/kader/verein/3379",
        "Serbia": "https://www.transfermarkt.com/serbien/kader/verein/3459",
        "Romania": "https://www.transfermarkt.com/rumaenien/kader/verein/3515",
        "Czech Republic": "https://www.transfermarkt.com/tschechien/kader/verein/3467",
        "Turkey": "https://www.transfermarkt.com/tuerkei/kader/verein/3268",
        "Iran": "https://www.transfermarkt.com/iran/kader/verein/3485",
        "Qatar": "https://www.transfermarkt.com/katar/kader/verein/3791",
        "Saudi Arabia": "https://www.transfermarkt.com/saudiarabien/kader/verein/3475",
        "UAE": "https://www.transfermarkt.com/vereinigte-arabische-emirate/kader/verein/3792",
        "Ecuador": "https://www.transfermarkt.com/ecuador/kader/verein/5352",
        "Peru": "https://www.transfermarkt.com/peru/kader/verein/3483",
        "Chile": "https://www.transfermarkt.com/chile/kader/verein/3445",
        "Paraguay": "https://www.transfermarkt.com/paraguay/kader/verein/3482",
        "Venezuela": "https://www.transfermarkt.com/venezuela/kader/verein/3480",
        "Panama": "https://www.transfermarkt.com/panama/kader/verein/5669",
        "Jamaica": "https://www.transfermarkt.com/jamaika/kader/verein/3444",
        "Costa Rica": "https://www.transfermarkt.com/costa-rica/kader/verein/3450",
        "Honduras": "https://www.transfermarkt.com/honduras/kader/verein/3451",
        "New Zealand": "https://www.transfermarkt.com/neuseeland/kader/verein/3462",
    }

    for team_name, url in national_urls.items():
        if url in visited_urls:
            continue
        print(f"\n📥 正在抓取 {team_name}... ({len(all_squads)+1}/48)")
        visited_urls.add(url)

        # 这个 URL 是国家队赛季总览页面，需要找 squad 链接
        soup = fetch_page(url)
        if not soup:
            print(f"  ❌ 无法获取页面")
            continue

        # 尝试解析国家队 squad 表格
        players = parse_national_team_squad(soup, team_name)
        if players:
            all_squads[team_name] = {
                "players": players,
                "source_url": url,
                "fetch_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
            print(f"  ✅ 获取 {len(players)} 名球员")
        else:
            print(f"  ⚠️ 未找到球员数据，尝试备用URL...")

        time.sleep(1.5)  # 礼貌延迟

    return all_squads


def main():
    parser = argparse.ArgumentParser(description="抓取 Transfermarkt 2026世界杯大名单")
    parser.add_argument("--output", "-o", default="data/wc2026_squads.json", help="输出JSON文件路径")
    args = parser.parse_args()

    squads = fetch_wc2026_squads()

    # 保存
    import os
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(squads, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存 {len(squads)} 支球队 / {sum(len(v['players']) for v in squads.values())} 名球员 → {args.output}")


if __name__ == "__main__":
    main()
