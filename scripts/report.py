#!/usr/bin/env python3
"""
世界杯冠军预测报告生成器

用法：
    python -m world_cup_predictor.report --year 2026
    python -m world_cup_predictor.report --year 2026 --mystic aggressive
    python -m world_cup_predictor.report --year 2026 --top 5
"""

import argparse
import sys
import os
import json
import random
from typing import List, Dict, Optional

# 添加项目根目录
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.models.player_scoring import Player, Squad, build_squad_from_data
from src.models.team_scoring import score_all_teams, ModelWeights
from src.models.mystic_factor import generate_mystic_report
from scripts.elo_scraper import get_all_team_elos, save_elo_cache, load_elo_cache

# 2026世界杯完整48支参赛队（全部已确认）
QUALIFIED_TEAMS = [
    # 南美（6队）
    "Argentina", "Brazil", "Uruguay", "Colombia", "Ecuador", "Paraguay",
    # 欧洲（16队）
    "France", "Germany", "Spain", "England", "Portugal", "Netherlands",
    "Italy", "Belgium", "Croatia", "Switzerland", "Austria", "Poland",
    "Ukraine", "Romania", "Czech Republic", "Turkey", "Serbia", "Sweden",
    # 非洲（9队）
    "Morocco", "Senegal", "Algeria", "Nigeria", "Egypt", "Cameroon",
    "Ghana", "Ivory Coast", "Tunisia", "DR Congo", "Cape Verde",
    # 亚洲（8队）
    "Japan", "South Korea", "Iran", "Qatar", "Saudi Arabia", "Australia",
    "Uzbekistan", "Jordan",
    # 中北美（8队）
    "USA", "Mexico", "Canada", "Panama", "Costa Rica", "Honduras", "Jamaica", "Haiti",
    # 大洋洲（1队）
    "New Zealand",
]

# 主机国（2026美加墨）
HOST_COUNTRY = "USA"  # 美国是名义主办国之一

# 卫冕冠军
DEFENDING_CHAMPION = "Argentina"

# Wikipedia 数据路径
WIKI_DATA_PATH = os.path.join(
    os.path.dirname(__file__), '..', 'data', 'wc2026_players_processed.json'
)


def load_wikipedia_squads() -> dict:
    """加载 Wikipedia 真实大名单数据"""
    if not os.path.exists(WIKI_DATA_PATH):
        return {}
    with open(WIKI_DATA_PATH, encoding="utf-8") as f:
        return json.load(f)


def infer_wc_participation(caps: int, age: int) -> List[str]:
    """
    根据球员年龄和代表队出场数推断其世界杯经历
    2026年球员，参加过上届2022世界杯的条件：
      - 2022年时年龄 >= 18（2004年之前出生）
      - 2022年时年龄 <= 35（1987年之后出生）
      - 有足够出场（通常打过几场预选赛）
    """
    if age < 18 or age > 35:
        return []
    # 简单推断：25岁以上且有一定出场数，很可能有2022经验
    if age >= 25 and caps >= 10:
        return ["2022"]
    if age >= 23 and caps >= 20:
        return ["2022"]
    if age >= 22 and caps >= 30:
        return ["2022"]
    return []


def estimate_market_value(position: str, caps: int, age: int) -> float:
    """
    根据位置、出场、年龄估算市场价（百万欧元）
    Wikipedia 没有市场价数据，用代理指标估算
    """
    base = {
        "GK": 8, "DF": 12, "MF": 15, "FW": 20
    }.get(position, 10)

    # 出场加成
    caps_factor = min(2.0, caps / 30 + 0.5)

    # 年龄巅峰加成（27-29岁最高）
    age_factor = 1.0
    if 27 <= age <= 29:
        age_factor = 1.5
    elif 24 <= age <= 26:
        age_factor = 1.2
    elif age > 31:
        age_factor = 0.8
    elif age < 23:
        age_factor = 0.9

    return round(base * caps_factor * age_factor, 1)


def normalize_position_wiki(pos: str) -> str:
    """将 Wikipedia 位置格式转为模型格式"""
    pos = pos.strip().upper()
    if "GK" in pos:
        return "GK"
    if "DF" in pos or "BACK" in pos or "DEFENDER" in pos:
        return "DF"
    if "MF" in pos or "MIDFIELDER" in pos or "MIDDLE" in pos:
        return "MF"
    if "FW" in pos or "FORWARD" in pos or "STRIKER" in pos or "WINGER" in pos:
        return "FW"
    return "MF"


def create_squad_from_wikipedia(country: str, wiki_data: dict, elo: float) -> Optional[Squad]:
    """
    从 Wikipedia 真实数据构建 Squad
    注意：限26人（世界杯最终名单上限）
    """
    players_raw = wiki_data.get("players", [])
    if not players_raw:
        return None

    players = []
    for p in players_raw:
        age = p.get("age")
        if not age:
            continue

        caps = p.get("caps", 0)
        pos = normalize_position_wiki(p.get("position", "MF"))
        tournaments = infer_wc_participation(caps, age)
        mv = estimate_market_value(pos, caps, age)

        player = Player(
            name=p["name"],
            age=age,
            position=pos,
            club=p.get("club", "Unknown"),
            market_value=mv,
            national_goals=p.get("goals", 0),
            national_caps=caps,
            tournaments=tournaments,
        )
        players.append(player)

    if not players:
        return None

    # 限26人：世界杯最终名单上限
    # 按 代表队出场数 降序排列，取前26人（优先保留主力）
    players.sort(key=lambda p: p.national_caps, reverse=True)
    players = players[:26]

    recent_win_rate = 0.3 + (elo - 1500) / 1000 * 0.5
    coaching_factor = random.uniform(0.4, 0.9)

    return Squad(
        country=country,
        players=players,
        elo=elo,
        recent_win_rate=recent_win_rate,
        coaching_factor=coaching_factor,
        tournament_history=["2022"] if country == "Argentina" else [],
    )


def create_sample_squad(country: str, elo: float) -> Squad:
    """
    创建示例阵容
    真实场景：从Transfermarkt API或数据集获取真实数据
    当前：基于Elo估算阵容质量，Elo越高的队经验越丰富
    """
    import random

    # 基于Elo估算球队实力等级
    if elo > 1850:
        player_count = 23
        avg_market_value = 50  # 百万欧
        experience_level = "high"  # 多名球员有大赛经验
    elif elo > 1750:
        player_count = 23
        avg_market_value = 25
        experience_level = "medium"
    else:
        player_count = 23
        avg_market_value = 10
        experience_level = "low"

    positions = ['GK', 'CB', 'CB', 'LB', 'RB', 'DM', 'CM', 'CM', 'AM', 'LW', 'RW', 'ST']

    # 基于实力等级设置年龄/经验分布
    age_params = {
        "high": {"mean": 27, "std": 4, "exp_ratio": 0.7},   # 强队：经验多
        "medium": {"mean": 26, "std": 5, "exp_ratio": 0.4},
        "low": {"mean": 25, "std": 5, "exp_ratio": 0.2},
    }[experience_level]

    players = []
    for i in range(player_count):
        # 估算年龄（正态分布）
        age = max(18, min(38, int(random.gauss(age_params["mean"], age_params["std"]))))
        pos = random.choice(positions)

        # 大赛经验：强队70%有经验，弱队20%
        has_exp = random.random() < age_params["exp_ratio"]
        tournaments = ["2022"] if has_exp else []

        p = Player(
            name=f"Player_{i+1}_{country[:3]}",
            age=age,
            position=pos,
            club="Club",
            market_value=max(0.5, avg_market_value * random.uniform(0.1, 2.0)),
            national_caps=random.randint(0, 100) if has_exp else random.randint(0, 20),
            national_goals=random.randint(0, 30) if has_exp else random.randint(0, 5),
            tournaments=tournaments,
        )
        players.append(p)

    # 估算近期胜率（基于Elo）
    recent_win_rate = 0.3 + (elo - 1500) / 1000 * 0.5

    # 估算教练因素
    coaching_factor = random.uniform(0.4, 0.9)

    return Squad(
        country=country,
        players=players,
        elo=elo,
        recent_win_rate=recent_win_rate,
        coaching_factor=coaching_factor,
        tournament_history=["2022"],
    )


def generate_report(year: int = 2026,
                    mystic_mode: str = "conservative",
                    top_n: int = 32,
                    output_file: str = None) -> str:
    """
    生成完整预测报告
    """
    print(f"""
╔══════════════════════════════════════════════════════╗
║     🏆 {year} 美加墨世界杯冠军预测报告                  ║
║        预测模式: {mystic_mode:<10}                           ║
╠══════════════════════════════════════════════════════╣
""")

    # 1. 获取Elo数据
    cache_path = os.path.join(
        os.path.dirname(__file__),
        '..', 'data', f'elo_cache_{year}.json'
    )
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)

    elos = load_elo_cache(cache_path)
    if elos is None:
        print("📊 获取球队Elo数据...")
        elos = get_all_team_elos(QUALIFIED_TEAMS)
        save_elo_cache(elos, cache_path)
        print(f"✅ 已缓存Elo数据，共{len(elos)}支球队")
    else:
        print(f"✅ 从缓存加载Elo数据，共{len(elos)}支球队")

    # 2. 构建球队阵容（优先 Wikipedia 真实数据，回退样本数据）
    print("🔨 构建球队阵容...")
    wiki_squads_data = load_wikipedia_squads()
    wiki_teams = wiki_squads_data.get("teams", {})

    squads = []
    real_count = 0
    sample_count = 0
    for country in QUALIFIED_TEAMS:
        elo = elos.get(country, 1650.0)

        # 优先用 Wikipedia 真实数据
        if country in wiki_teams:
            squad = create_squad_from_wikipedia(country, wiki_teams[country], elo)
            if squad:
                squads.append(squad)
                real_count += 1
                continue

        # 回退到样本数据
        squad = create_sample_squad(country, elo)
        squads.append(squad)
        sample_count += 1

    print(f"✅ 已构建{len(squads)}支球队阵容（真实数据: {real_count}队，样本数据: {sample_count}队）")
    print(f"   📊 Wikipedia 数据覆盖：{real_count}/{len(QUALIFIED_TEAMS)} 队")

    # 3. 评分
    print("📈 正在评分...")
    weights = ModelWeights()
    results = score_all_teams(
        squads,
        weights=weights,
        mystic_mode=mystic_mode,
        host_team=HOST_COUNTRY,
        defending_champ=DEFENDING_CHAMPION,
    )

    # 4. 输出报告
    report_lines = []
    report_lines.append(f"""
╔══════════════════════════════════════════════════════╗
║     🏆 {year} 美加墨世界杯冠军预测报告                  ║
║        玄学模式: {mystic_mode:<10}                           ║
║        生成时间: 2026-05-20                            ║
╠══════════════════════════════════════════════════════╣
║                  冠军概率排行榜                       ║
╠══════════════════════════════════════════════════════╣
""")

    for i, r in enumerate(results[:top_n], 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, f" {i:>2}")
        prob_pct = r.final_probability * 100
        bar_len = min(50, int(prob_pct * 2))
        bar = "█" * bar_len + "░" * (50 - bar_len)

        report_lines.append(f"{medal} {r.country:<14} {prob_pct:>5.1f}%  {bar}")

    report_lines.append("""
╠══════════════════════════════════════════════════════╣
║                  TOP3 因子拆解                       ║
╠══════════════════════════════════════════════════════╣
""")

    for i, r in enumerate(results[:3], 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i)
        report_lines.append(f"""
{medal} {r.country}
├─ Elo锚点：        {r.elo_score:+.2%}
├─ 年龄结构：       {r.age_score:+.2%}
├─ 大赛经验：       {r.experience_score:+.2%}
├─ 近期状态：       {r.form_score:+.2%}
├─ 教练因素：       {r.coaching_score:+.2%}
├─ 玄学因子：       {r.mystic_score:+.2%}
├─ 置信区间：       [{r.confidence_interval[0]:.1%}, {r.confidence_interval[1]:.1%}]
└─ {r.narrative}
""")

    report_lines.append("""
╠══════════════════════════════════════════════════════╣
║                  🔮 玄学视角                          ║
╠══════════════════════════════════════════════════════╣
""")

    for country in [r.country for r in results[:3]]:
        mystic = generate_mystic_report(country, mode=mystic_mode)
        report_lines.append(mystic)

    report_lines.append("""
╠══════════════════════════════════════════════════════╣
║                  使用说明                            ║
╠══════════════════════════════════════════════════════╣
║  本预测基于以下因子加权：                            ║
║  • Elo锚点 35% — FiveThirtyEight SPI评分            ║
║  • 年龄结构 20% — 球员职业黄金期模型                 ║
║  • 大赛经验 15% — 世界杯/洲际杯经历                 ║
║  • 近期状态 15% — 近18个月国家队表现                ║
║  • 教练因素 10% — 大赛执教能力评估                   ║
║  • 玄学因子  5% — 不可量化因素                      ║
║                                                      ║
║  ⚠️ 注意：本预测仅供娱乐，不构成投资建议             ║
║     世界杯是地球上最不可预测的体育赛事               ║
╚══════════════════════════════════════════════════════╝
""")

    report = "\n".join(report_lines)
    print(report)

    if output_file:
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(report)
        print(f"\n✅ 报告已保存至: {output_file}")

    return report


def main():
    parser = argparse.ArgumentParser(description="世界杯冠军预测报告生成器")
    parser.add_argument('--year', type=int, default=2026, help='世界杯年份')
    parser.add_argument(
        '--mystic',
        type=str,
        default='conservative',
        choices=['conservative', 'aggressive', 'mystical'],
        help='玄学模式'
    )
    parser.add_argument('--top', type=int, default=10, help='显示前N名')
    parser.add_argument('--output', type=str, default=None, help='输出文件路径')

    args = parser.parse_args()
    generate_report(
        year=args.year,
        mystic_mode=args.mystic,
        top_n=args.top,
        output_file=args.output,
    )


if __name__ == "__main__":
    main()
