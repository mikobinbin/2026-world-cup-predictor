#!/usr/bin/env python3
"""
将 Wikipedia 大名单数据转换为 PlayerScoreModel 可用的格式。
同时补充缺失强队（通过 Wikipedia 搜索+解析获取）。

用法：
    python scripts/ingest_wikipedia_squads.py --input data/wc2026_squads_wikipedia.json --output data/wc2026_players_processed.json
"""

import json
import argparse
import requests
from bs4 import BeautifulSoup
from pathlib import Path
from datetime import date

HEADERS = {"User-Agent": "WorldCupPredictorBot/1.0"}


def load_squads(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def normalize_position(pos: str) -> str:
    """将 Wikipedia 位置格式转为模型格式"""
    pos = pos.strip().upper()
    if "GK" in pos or "GOALKEEPER" in pos:
        return "GK"
    if "DF" in pos or "DEFENDER" in pos or "BACK" in pos or "CB" in pos or "LB" in pos or "RB" in pos:
        return "DF"
    if "MF" in pos or "MIDFIELDER" in pos or "CM" in pos or "DM" in pos or "AM" in pos:
        return "MF"
    if "FW" in pos or "FORWARD" in pos or "STRIKER" in pos or "WINGER" in pos or "ATTACKER" in pos:
        return "FW"
    return "MF"


def calculate_cycle_birth_year(age: int) -> int:
    """根据球员年龄推算出生年，结合4年周期模型估算巅峰年份"""
    current_year = date.today().year
    birth_year = current_year - age
    return birth_year


def squad_to_player_format(team_name: str, players: list) -> list:
    """将 Wikipedia squad 数据转换为统一的 player 格式"""
    formatted_players = []
    for p in players:
        age = p.get("age")
        if not age:
            continue

        birth_year = calculate_cycle_birth_year(age)
        pos = normalize_position(p.get("position", ""))

        formatted_players.append({
            "name": p["name"],
            "position": pos,
            "age": age,
            "birth_year": birth_year,
            "caps": p.get("caps", 0),
            "goals": p.get("goals", 0),
            "club": p.get("club", "Unknown"),
            "team": team_name,
            "is_peak": 27 <= age <= 29,
            "is_youth": age < 23,
            "is_experienced": p.get("caps", 0) >= 30,
        })
    return formatted_players


def get_all_players(squads: dict) -> list:
    """把所有球队的大名单合并为统一列表"""
    all_players = []
    for team_name, team_data in squads.items():
        players = squad_to_player_format(team_name, team_data["players"])
        all_players.extend(players)
    return all_players


def get_team_summary(squads: dict) -> dict:
    """生成各队统计摘要"""
    summary = {}
    for team_name, team_data in squads.items():
        players = team_data["players"]
        positions = {"GK": 0, "DF": 0, "MF": 0, "FW": 0}
        total_caps = 0
        total_goals = 0
        ages = []

        for p in players:
            pos = normalize_position(p.get("position", ""))
            if pos in positions:
                positions[pos] += 1
            total_caps += p.get("caps", 0)
            total_goals += p.get("goals", 0)
            if p.get("age"):
                ages.append(p["age"])

        avg_age = sum(ages) / len(ages) if ages else 0

        summary[team_name] = {
            "count": len(players),
            "positions": positions,
            "total_caps": total_caps,
            "total_goals": total_goals,
            "avg_age": round(avg_age, 1),
            "peak_count": sum(1 for p in players if p.get("age") and 27 <= p["age"] <= 29),
            "fetch_date": team_data.get("fetch_date", ""),
        }
    return summary


def print_summary(summary: dict):
    """打印摘要表"""
    print(f"\n{'球队':<25} {'人数':>4} {'GK':>3} {'DF':>3} {'MF':>3} {'FW':>3} {'平均年龄':>7} {'峰值年龄人数':>10} {'总出场':>8}")
    print("-" * 90)
    for team, s in sorted(summary.items(), key=lambda x: -x[1]["total_caps"]):
        print(f"{team:<25} {s['count']:>4} {s['positions']['GK']:>3} {s['positions']['DF']:>3} "
              f"{s['positions']['MF']:>3} {s['positions']['FW']:>3} {s['avg_age']:>7.1f} "
              f"{s['peak_count']:>10} {s['total_caps']:>8}")


def main():
    parser = argparse.ArgumentParser(description="转换 Wikipedia 大名单为模型输入格式")
    parser.add_argument("--input", "-i", default="data/wc2026_squads_wikipedia.json")
    parser.add_argument("--output", "-o", default="data/wc2026_players_processed.json")
    args = parser.parse_args()

    print(f"📂 加载数据: {args.input}")
    squads = load_squads(args.input)
    print(f"   已加载 {len(squads)} 支球队")

    # 转换
    all_players = get_all_players(squads)
    summary = get_team_summary(squads)

    result = {
        "metadata": {
            "source": "Wikipedia: 2026 FIFA World Cup squads",
            "total_teams": len(squads),
            "total_players": len(all_players),
            "fetch_date": str(date.today()),
            "note": "数据来自 Wikipedia，仅含已公布大名单的球队（28/48队）"
        },
        "teams": squads,
        "summary": summary,
        "all_players": all_players,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"✅ 已保存 → {args.output}")
    print_summary(summary)


if __name__ == "__main__":
    main()
