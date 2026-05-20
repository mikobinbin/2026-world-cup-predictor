#!/usr/bin/env python3
"""
Wikipedia 2026 World Cup Squad Scraper
来源: https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads
抓取各参赛队已公布的大名单数据（姓名、位置、年龄、代表队出场/进球、俱乐部）

用法：
    python scripts/wikipedia_squads.py --output data/wc2026_squads_wikipedia.json
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import argparse
import time
from datetime import datetime, date
from typing import Optional

HEADERS = {"User-Agent": "WorldCupPredictorBot/1.0 (Hermes AI Agent; educational project)"}

WIKI_API = "https://en.wikipedia.org/w/api.php"


def fetch_wiki_page(title: str) -> str:
    """从 Wikipedia API 获取页面 HTML"""
    params = {"action": "parse", "page": title, "format": "json", "prop": "text"}
    r = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=30)
    data = r.json()
    return data["parse"]["text"]["*"]


def parse_age_from_dob(text: str) -> Optional[int]:
    """
    从 Wikipedia 日期字段解析年龄。
    格式: '(2001-06-24)June 24, 2001 (age 24)' 或
          '(1999-03-03)March 3, 1999 (aged 26)'
    """
    # 匹配 (age XX) 或 (aged XX)
    age_match = re.search(r"\(age\s*(\d+)\)", text) or re.search(r"\(aged\s*(\d+)\)", text)
    if age_match:
        return int(age_match.group(1))

    # 如果没有，尝试从日期计算
    dob_match = re.search(r"\((\d{4}-\d{2}-\d{2})\)", text)
    if dob_match:
        dob = datetime.strptime(dob_match.group(1), "%Y-%m-%d").date()
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        return age
    return None


def clean_position(pos: str) -> str:
    """标准化位置名称"""
    pos = pos.strip()
    mapping = {
        "GK": "GK", "Goalkeeper": "GK",
        "DF": "DF", "Defender": "DF",
        "MF": "MF", "Midfielder": "MF",
        "FW": "FW", "Forward": "FW",
    }
    return mapping.get(pos, pos)


def parse_squad_table(table: BeautifulSoup, team_name: str) -> list:
    """解析单个球队的大名单表格"""
    players = []
    rows = table.find_all("tr")[1:]  # 跳过表头行

    for row in rows:
        cells = row.find_all(["th", "td"])
        if len(cells) < 7:
            continue

        try:
            # 号码 (可能在 th 里)
            no = cells[0].get_text(strip=True)

            # 位置
            pos_raw = cells[1].get_text(strip=True)
            pos = clean_position(pos_raw)

            # 球员名
            name_link = cells[2].find("a")
            name = name_link.get_text(strip=True) if name_link else cells[2].get_text(strip=True)

            # 出生日期/年龄
            dob_text = cells[3].get_text(strip=True)
            age = parse_age_from_dob(dob_text)

            # 代表队出场/进球
            caps_text = cells[4].get_text(strip=True)
            caps = int(caps_text) if caps_text.isdigit() else 0
            goals_text = cells[5].get_text(strip=True)
            goals = int(goals_text) if goals_text.isdigit() else 0

            # 俱乐部
            club_link = cells[6].find("a")
            club = club_link.get_text(strip=True) if club_link else cells[6].get_text(strip=True)

            if name and pos:
                players.append({
                    "name": name,
                    "position": pos,
                    "number": no,
                    "age": age,
                    "caps": caps,
                    "goals": goals,
                    "club": club,
                })
        except Exception as e:
            continue

    return players


def scrape_wc2026_squads() -> dict:
    """抓取 Wikipedia 上所有已公布的 2026 世界杯大名单"""
    print("🌐 正在从 Wikipedia 获取 2026 世界杯大名单数据...")

    html = fetch_wiki_page("2026 FIFA World Cup squads")
    soup = BeautifulSoup(html, "html.parser")

    tables = soup.find_all("table", class_="wikitable")

    # 排除最后一个"Coaches representation by country"表格
    all_squads = {}
    excluded_patterns = ["coach", "representation", "referee", "official"]

    for table in tables:
        header = table.find_previous(["h2", "h3"])
        team_raw = header.get_text(strip=True) if header else ""

        # 清理超链接和 span 标签
        for tag in header.find_all(["a", "span"]) if header else []:
            tag.replace_with(tag.get_text())
        team = header.get_text(strip=True) if header else ""

        # 跳过非球队表格
        if any(p in team.lower() for p in excluded_patterns):
            continue

        players = parse_squad_table(table, team)
        if players:
            all_squads[team] = {
                "players": players,
                "count": len(players),
                "source": "Wikipedia:2026 FIFA World Cup squads",
                "fetch_date": datetime.now().strftime("%Y-%m-%d"),
            }
            print(f"  ✅ {team}: {len(players)} 名球员")

    return all_squads


def get_missing_teams(all_teams: list, found_teams: list) -> list:
    """返回尚未公布大名单的球队"""
    return [t for t in all_teams if t not in found_teams]


def main():
    parser = argparse.ArgumentParser(description="抓取 Wikipedia 2026 世界杯大名单")
    parser.add_argument("--output", "-o", default="data/wc2026_squads_wikipedia.json",
                        help="输出JSON文件路径")
    args = parser.parse_args()

    squads = scrape_wc2026_squads()

    # 保存
    import os
    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(squads, f, ensure_ascii=False, indent=2)

    total_players = sum(len(v["players"]) for v in squads.values())
    print(f"\n✅ 已保存 {len(squads)} 支球队 / {total_players} 名球员 → {args.output}")

    # 显示各队球员数统计
    print("\n📊 各队大名单人数：")
    for team, data in sorted(squads.items(), key=lambda x: -x[1]["count"]):
        print(f"  {team}: {data['count']}人")


if __name__ == "__main__":
    main()
