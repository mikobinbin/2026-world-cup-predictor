"""
世界杯冠军预测 — 移动端 Gradio 版
World Cup 2026 Champion Predictor Mobile UI (Gradio)

用法:
    cd ~/Desktop/world_cup_predictor
    python3 -m src.dashboard.gradio_mobile

移动端访问: http://localhost:7861
"""

import sys
import os
import json
import random
from datetime import datetime

# ── 项目路径 ──────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

import gradio as gr
from gradio.components import Markdown, Dataset

from src.models.player_scoring import Player, Squad
from src.models.team_scoring import score_all_teams, ModelWeights
from src.models.mystic_factor import MysticFactorEngine
from src.models.ucl_final_mentality import (
    compute_country_ucl_mentality_bonus,
    compute_final_mentality_signal,
)
from scripts.elo_scraper import load_elo_cache
from scripts.ingest_wikipedia_squads import normalize_position
import sys
sys.path.insert(0, str(ROOT))
# 少量辅助函数从 leaderboard 复制过来（保持逻辑一致）
def _infer_tournaments(caps: int, age: int):
    if age >= 25 and caps >= 10:
        return ["2022"]
    if age >= 23 and caps >= 20:
        return ["2022"]
    if age >= 22 and caps >= 30:
        return ["2022"]
    return []

def _estimate_mv(pos: str, caps: int, age: int) -> float:
    base = {"GK": 8, "DF": 12, "MF": 15, "FW": 20}.get(pos, 10)
    caps_factor = min(2.0, caps / 30 + 0.5)
    age_factor = 1.5 if 27 <= age <= 29 else (1.2 if 24 <= age <= 26 else (0.8 if age > 31 else 0.9))
    return round(base * caps_factor * age_factor, 1)

# ── 种子 ──────────────────────────────────────────────
RANDOM_SEED = 42
random.seed(RANDOM_SEED)

# ── 数据路径 ──────────────────────────────────────────────
WIKI_DATA = os.path.join(ROOT, "data", "wc2026_players_processed.json")
ELO_CACHE = os.path.join(ROOT, "data", "elo_cache_2026.json")

QUALIFIED_TEAMS = [
    "Argentina", "Brazil", "Uruguay", "Colombia", "Ecuador", "Paraguay",
    "France", "Germany", "Spain", "England", "Portugal", "Netherlands",
    "Italy", "Belgium", "Croatia", "Switzerland", "Austria", "Poland",
    "Ukraine", "Romania", "Czech Republic", "Turkey", "Serbia", "Sweden",
    "Morocco", "Senegal", "Algeria", "Nigeria", "Egypt", "Cameroon",
    "Ghana", "Ivory Coast", "Tunisia", "DR Congo", "Cape Verde",
    "Japan", "South Korea", "Iran", "Qatar", "Saudi Arabia", "Australia",
    "Uzbekistan", "Jordan",
    "USA", "Mexico", "Canada", "Panama", "Costa Rica", "Honduras", "Jamaica", "Haiti",
    "New Zealand",
]

HOST_COUNTRY = "USA"
DEFENDING_CHAMPION = "Argentina"

# ── Emoji/Flag 映射 ──────────────────────────────────────────────
FLAG = {
    "Brazil": "🇧🇷", "Argentina": "🇦🇷", "France": "🇫🇷", "England": "🏴󠁧󠁢󠁥󠁮󠁧󠁿",
    "Germany": "🇩🇪", "Spain": "🇪🇸", "Portugal": "🇵🇹", "Netherlands": "🇳🇱",
    "Italy": "🇮🇹", "Belgium": "🇧🇪", "Croatia": "🇭🇷", "Switzerland": "🇨🇭",
    "Uruguay": "🇺🇾", "Colombia": "🇨🇴", "Mexico": "🇲🇽", "USA": "🇺🇸",
    "Japan": "🇯🇵", "South Korea": "🇰🇷", "Australia": "🇦🇺", "Iran": "🇮🇷",
    "Morocco": "🇲🇦", "Senegal": "🇸🇳", "Nigeria": "🇳🇬", "Egypt": "🇪🇬",
    "Poland": "🇵🇱", "Austria": "🇦🇹", "Ukraine": "🇺🇦", "Romania": "🇷🇴",
    "Czech Republic": "🇨🇿", "Turkey": "🇹🇷", "Serbia": "🇷🇸", "Sweden": "🇸🇪",
    "Ecuador": "🇪🇨", "Paraguay": "🇵🇾", "Saudi Arabia": "🇸🇦", "Qatar": "🇶🇦",
    "Ivory Coast": "🇨🇮", "Ghana": "🇬🇭", "Cameroon": "🇨🇲", "Tunisia": "🇹🇳",
    "Algeria": "🇩🇿", "DR Congo": "🇨🇩", "Cape Verde": "🇨🇻",
    "Uzbekistan": "🇺🇿", "Jordan": "🇯🇴", "Panama": "🇵🇦",
    "Costa Rica": "🇨🇷", "Honduras": "🇭🇳", "Jamaica": "🇯🇲", "Haiti": "🇭🇹",
    "Canada": "🇨🇦", "New Zealand": "🇳🇿",
    "Georgia": "🇬🇪",
}


# ── 数据加载 ──────────────────────────────────────────────
_cached_results = None


def _build_sample(country: str, elo: float):
    """构建样本球队（无真实阵容时）"""
    exp_level = "high" if elo > 1850 else ("medium" if elo > 1750 else "low")
    params = {
        "high":   {"mean": 27, "std": 4,  "exp_ratio": 0.7},
        "medium": {"mean": 26, "std": 5,  "exp_ratio": 0.4},
        "low":    {"mean": 25, "std": 5,  "exp_ratio": 0.2},
    }[exp_level]

    positions = ['GK', 'CB', 'CB', 'LB', 'RB', 'DM', 'CM', 'CM', 'AM', 'LW', 'RW', 'ST']
    players = []
    for i in range(23):
        age = max(18, min(38, int(random.gauss(params["mean"], params["std"]))))
        has_exp = random.random() < params["exp_ratio"]
        players.append(Player(
            name=f"P{i+1}_{country[:3]}",
            age=age,
            position=random.choice(positions),
            club="Club",
            market_value=max(0.5, random.uniform(5, 60)),
            national_caps=random.randint(0, 100) if has_exp else random.randint(0, 20),
            national_goals=random.randint(0, 30) if has_exp else random.randint(0, 5),
            tournaments=["2022"] if has_exp else [],
        ))

    coach_hash = hash(country) % 1000 / 1000.0
    coaching_factor = 0.4 + coach_hash * 0.5

    return Squad(
        country=country, players=players, elo=elo,
        recent_win_rate=0.3 + (elo - 1500) / 1000 * 0.5,
        coaching_factor=coaching_factor,
        tournament_history=["2022"] if country == DEFENDING_CHAMPION else [],
    )


def load_all_data():
    """加载所有数据，返回 (results, elo_dict)"""
    global _cached_results
    if _cached_results is not None:
        return _cached_results

    # 1. Wiki data
    wiki_data = {}
    if os.path.exists(WIKI_DATA):
        with open(WIKI_DATA, encoding="utf-8") as f:
            wiki_data = json.load(f)

    # 2. Elo data
    elo_dict = load_elo_cache(ELO_CACHE)
    if elo_dict is None:
        elo_dict = {}

    # 3. Build squads
    teams_data = wiki_data.get("teams", {})
    squads = {}
    for country in QUALIFIED_TEAMS:
        elo = elo_dict.get(country, 1650.0)

        if country in teams_data:
            players_raw = teams_data[country].get("players", [])
            players = []
            for p in players_raw:
                age = p.get("age")
                if not age:
                    continue
                caps = p.get("caps", 0)
                pos = normalize_position(p.get("position", "MF"))
                tournaments = _infer_tournaments(caps, age)
                mv = _estimate_mv(pos, caps, age)
                players.append(Player(
                    name=p["name"],
                    age=age,
                    position=pos,
                    club=p.get("club", "Unknown"),
                    market_value=mv,
                    national_goals=p.get("goals", 0),
                    national_caps=caps,
                    tournaments=tournaments,
                ))

            players.sort(key=lambda x: x.national_caps, reverse=True)
            players = players[:26]

            coach_hash = hash(country) % 1000 / 1000.0
            coaching_factor = 0.4 + coach_hash * 0.5

            if players:
                squads[country] = Squad(
                    country=country, players=players, elo=elo,
                    recent_win_rate=0.3 + (elo - 1500) / 1000 * 0.5,
                    coaching_factor=coaching_factor,
                    tournament_history=["2022"] if country == DEFENDING_CHAMPION else [],
                )
                continue

        # Sample squad
        squads[country] = _build_sample(country, elo)

    # 4. Score all teams
    weights = ModelWeights()
    squad_list = list(squads.values())
    scored = score_all_teams(
        squad_list, weights=weights,
        host_team=HOST_COUNTRY, defending_champ=DEFENDING_CHAMPION,
    )

    # 5. Run MysticFactor
    engine = MysticFactorEngine()
    mystic_teams = []
    for t in scored:
        mystic_teams.append({
            "country": t.country,
            "elo": t.elo_score if hasattr(t, 'elo_score') else (squads[t.country].elo if t.country in squads else 1700),
            "prob": t.final_probability,
            "avg_age": sum(p.age for p in squads[t.country].players) / len(squads[t.country].players) if squads[t.country].players else 27.0,
            "exp_ratio": sum(1 for p in squads[t.country].players if p.national_caps >= 30) / len(squads[t.country].players) if squads[t.country].players else 0,
            "is_host": (t.country == HOST_COUNTRY),
            "is_defending": (t.country == DEFENDING_CHAMPION),
            "is_first_tournament": (t.final_probability < 0.01),
        })

    mystic_results = engine.analyze(mystic_teams, stage="tournament")
    mystic_map = {r.country: r for r in mystic_results}

    # 6. Merge results
    results = []
    for t in scored:
        r = mystic_map.get(t.country)
        results.append({
            "country": t.country,
            "elo": squads[t.country].elo if t.country in squads else 1700,
            "prob": t.final_probability,
            "final_prob": r.mystic_prob if r else t.final_probability,
            "shift": (r.mystic_prob - t.final_probability) if r else 0,
            "logical_prob": t.final_probability,
            "verdict": r.verdict if r else "—",
            "zen": r.zen.final_recommendation if r else "—",
            "tao": r.tao.tao_recommendation if r else "—",
            "iching": "".join(r.iching.hexagram[:2]) if r else "—",
            "iching_warning": r.iching.hexagram_warning if r else "",
            "confidence": r.confidence if r else 0.5,
            "contrarian": r.contrarian_shift if r else 0,
            "fav_curse": r.favorite_curse if r else 0,
            "gs_vol": r.group_stage_volatility if r else 0,
            "knock_unc": r.knockout_uncertainty if r else 0,
        })

    results.sort(key=lambda x: x["final_prob"], reverse=True)
    _cached_results = (results, elo_dict)
    return results, elo_dict


def get_ucl_card(country: str) -> str:
    """生成单个球队的欧冠心态卡片"""
    bonus = compute_country_ucl_mentality_bonus(country)
    signals = bonus.get("signals", [])
    flag = FLAG.get(country, "🏳️")

    if not signals:
        return f"## {flag} {country}\n\n暂无欧冠决赛心态数据\n"

    lines = [
        f"## {flag} {country} — 欧冠决赛心态信号\n",
        f"**球员样本：** {bonus['signal_count']}人",
        f"**平均心态分：** {bonus['mentality_avg']:+.2f}",
        f"**世界杯概率修正：** {bonus['wc_total_adjustment']:+.2f}%\n",
    ]

    for sig in signals:
        tier_icon = {
            "BREAKTHROUGH": "🌟",
            "UNDERPRESSURE": "😰",
            "DOUBTING": "🤔",
            "SELF_DOUBT": "💭",
            "COLLAPSE": "💀",
        }.get(str(sig.tier).split(".")[-1].upper(), "❓")

        lines.append(
            f"### {tier_icon} {sig.player_name}\n"
            f"心态分：**{sig.mentality_score:+.2f}** | "
            f"表现Z：{sig.performance_z:+.1f} | "
            f"关键行动Z：{sig.key_action_z:+.1f}\n\n"
            f"最似框架：**{sig.nearest_framework}**\n\n"
            f"{sig.narrative[:120]}...\n\n"
            f"世界杯修正：{sig.wc_verdict}\n\n"
            f"---"
        )

    return "\n".join(lines)


# ── UI 构建 ──────────────────────────────────────────────
def build_ui():
    with gr.Blocks(
        title="🏆 世界杯预测",
        theme=gr.themes.Soft(
            primary_hue="yellow",
            secondary_hue="gray",
            neutral_hue="gray",
            text_size=gr.themes.sizes.text_lg,
        ).set(
            body_background_fill="#0d0d0f",
            body_text_color="#e6edf3",
            block_background_fill="#161b22",
            block_border_color="#30363d",
            block_label_background_fill="#1c2128",
            block_label_text_color="#d4af37",
            button_primary_background_fill="#d4af37",
            button_primary_text_color="#0d0d0f",
            button_secondary_background_fill="#21262d",
            button_secondary_text_color="#e6edf3",
            input_background_fill="#161b22",
            input_border_color="#30363d",
        ),
        css="""
        .gradio-container { max-width: 100% !important; padding: 0 !important; }
        .main { padding: 8px !important; }
        h1, h2, h3 { color: #d4af37 !important; }
        .team-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 12px;
            padding: 14px 16px;
            margin-bottom: 8px;
        }
        .prob-big { font-size: 2rem; font-weight: 700; color: #d4af37; }
        .prob-shift { font-size: 1rem; }
        .shift-up { color: #3fb950; }
        .shift-down { color: #f85149; }
        .shift-flat { color: #8b949e; }
        .elo-tag { background: #21262d; border-radius: 6px; padding: 2px 8px; font-size: 0.85rem; }
        .verdict-badge {
            display: inline-block;
            border-radius: 20px;
            padding: 2px 10px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        .verdict-up { background: #1f3a1f; color: #3fb950; }
        .verdict-down { background: #3a1f1f; color: #f85149; }
        .verdict-flat { background: #2a2a2a; color: #8b949e; }
        .factor-row { display: flex; justify-content: space-between; padding: 4px 0; border-bottom: 1px solid #21262d; }
        .section-header { color: #d4af37; font-size: 1.1rem; font-weight: 700; margin: 12px 0 6px; }
        .player-signal {
            background: #1c2128;
            border-left: 3px solid #d4af37;
            padding: 10px 12px;
            margin: 8px 0;
            border-radius: 0 8px 8px 0;
        }
        .mind-score { font-size: 1.4rem; font-weight: 700; }
        .mind-pos { color: #3fb950; }
        .mind-neg { color: #f85149; }
        .mind-neu { color: #8b949e; }
        """,
    ) as demo:
        gr.Markdown(
            "<div style='text-align:center;padding:12px 0 4px'>"
            "<h1 style='color:#d4af37;margin:0'>🏆 世界杯冠军预测</h1>"
            "<p style='color:#8b949e;margin:4px 0 0'>2026美加墨 · 玄学+数据双轨分析</p>"
            "<p style='color:#4d5566;font-size:0.85rem'>含欧冠决赛心态信号 · 更新于 "
            + datetime.now().strftime("%m-%d %H:%M") + "</p>"
            "</div>",
            elem_classes=["main"],
        )

        results, _ = load_all_data()
        team_names = [r["country"] for r in results]

        with gr.Tabs():
            # ── Tab 1: 冠军榜 ──────────────────────────────────────────
            with gr.TabItem("🏆 冠军概率榜"):
                gr.Markdown("<p class='section-header'>TOP 10 夺冠概率</p>", elem_classes=["main"])

                top10 = results[:10]
                with gr.Column():
                    for r in top10:
                        flag = FLAG.get(r["country"], "🏳️")
                        shift = r["shift"]
                        shift_cls = (
                            "shift-up" if shift > 0.005
                            else "shift-down" if shift < -0.005
                            else "shift-flat"
                        )
                        shift_str = f"{shift*100:+.1f}%" if abs(shift) > 0.005 else "~0%"

                        # verdict badge
                        if "加持" in r["verdict"]:
                            v_cls, v_txt = "verdict-up", "⬆️ 加持"
                        elif "压制" in r["verdict"]:
                            v_cls, v_txt = "verdict-down", "⬇️ 压制"
                        else:
                            v_cls, v_txt = "verdict-flat", "➖ 中性"

                        with gr.Group():
                            html = (
                                f"<div class='team-card'>"
                                f"<div style='display:flex;align-items:center;gap:10px;margin-bottom:6px'>"
                                f"<span style='font-size:1.6rem'>{flag}</span>"
                                f"<div style='flex:1'>"
                                f"<div style='font-weight:700;font-size:1.1rem'>{r['country']}</div>"
                                f"<span class='elo-tag'>Elo {int(r['elo'])}</span>"
                                f"</div>"
                                f"<div style='text-align:right'>"
                                f"<div class='prob-big'>{r['final_prob']:.1%}</div>"
                                f"<div class='prob-shift {shift_cls}'>{shift_str}</div>"
                                f"</div>"
                                f"</div>"
                                f"<div style='display:flex;gap:6px;flex-wrap:wrap;margin-top:4px'>"
                                f"<span class='verdict-badge {v_cls}'>{v_txt}</span>"
                                f"<span style='color:#8b949e;font-size:0.8rem'>置信度 {r['confidence']:.0%}</span>"
                                f"<span style='color:#d4af37;font-size:0.8rem'>卦象 {r['iching']}</span>"
                                f"</div>"
                                f"</div>"
                            )
                            gr.HTML(html)

            # ── Tab 2: 球队详情 ──────────────────────────────────────────
            with gr.TabItem("🔍 球队详情"):
                gr.Markdown("<p class='section-header'>选择球队</p>", elem_classes=["main"])

                team_select = gr.Dropdown(
                    choices=team_names,
                    value="France",
                    label="球队 / Team",
                    info="选择一支球队查看完整玄学分析",
                )

                detail_output = gr.Markdown("", elem_classes=["main"])

                def on_select_team(country):
                    r = next((x for x in results if x["country"] == country), None)
                    if not r:
                        return "**未找到数据**"

                    flag = FLAG.get(country, "🏳️")
                    shift = r["shift"]
                    shift_cls = (
                        "shift-up" if shift > 0.005
                        else "shift-down" if shift < -0.005
                        else "shift-flat"
                    )
                    shift_str = f"{shift*100:+.1f}%" if abs(shift) > 0.005 else "~0%"

                    # UCL data
                    ucl = compute_country_ucl_mentality_bonus(country)
                    ucl_info = ""
                    if ucl["signal_count"] > 0:
                        mind = ucl["mentality_avg"]
                        mind_cls = "mind-pos" if mind > 0.1 else "mind-neg" if mind < -0.1 else "mind-neu"
                        ucl_info = (
                            f"\n\n**⚡ 欧冠心态信号**\n"
                            f"- 球员样本：{ucl['signal_count']}人\n"
                            f"- 平均心态分：<span class='mind-score {mind_cls}'>{mind:+.2f}</span>\n"
                            f"- 世界杯概率修正：<span class='{mind_cls}'>{ucl['wc_total_adjustment']:+.2f}%</span>\n"
                        )

                    # Factor breakdown
                    factors = [
                        ("🎰 彩票悖论", r["contrarian"]),
                        ("⚡ 小组赛波动", r["gs_vol"]),
                        ("🎲 淘汰赛弹性", r["knock_unc"]),
                        ("💀 强势方诅咒", r["fav_curse"]),
                    ]
                    factor_rows = "\n".join(
                        f"| {name} | {v:+.3f} |"
                        for name, v in factors
                    )

                    return (
                        f"## {flag} {country}\n\n"
                        f"| | |\n"
                        f"|---|---|\n"
                        f"| 逻辑概率 | **{r['logical_prob']:.1%}** |\n"
                        f"| 玄学修正后 | **{r['final_prob']:.1%}** |\n"
                        f"| 修正幅度 | <span class='{shift_cls}'>{shift_str}</span> |\n"
                        f"| 置信度 | {r['confidence']:.0%} |\n"
                        f"| 卦象 | {r['iching']} |\n"
                        f"|  verdict  | {r['verdict']} |\n"
                        f"| Zen建议 | {r['zen'][:40]}... |\n"
                        f"| Tao建议 | {r['tao'][:40]} |\n"
                        f"{ucl_info}\n\n"
                        f"### 修正因子拆解\n\n"
                        f"| 因子 | 偏移量 |\n"
                        f"|---|---|\n"
                        f"{factor_rows}\n\n"
                        f"*{r['iching_warning']}*"
                    )

                team_select.change(
                    fn=on_select_team,
                    inputs=[team_select],
                    outputs=[detail_output],
                )
                # 初始加载
                on_select_team("France")

            # ── Tab 3: 欧冠心态信号 ──────────────────────────────────────────
            with gr.TabItem("⚡ 欧冠信号"):
                gr.Markdown(
                    "<p class='section-header'>欧冠决赛 → 世界杯心态映射</p>",
                    elem_classes=["main"],
                )
                gr.Markdown(
                    "基于2024-25赛季欧冠淘汰赛关键动作，"
                    "对照2014巴西1-7（心理崩溃型）和2018法国（顺势爆发型）框架，"
                    "量化球员在世界杯决赛圈的心态信号。\n",
                    elem_classes=["main"],
                )

                ucl_countries = ["France", "England", "Argentina", "Italy", "Georgia", "Portugal"]
                ucl_select = gr.Dropdown(
                    choices=ucl_countries,
                    value="France",
                    label="选择球队 / Select Country",
                )
                ucl_output = gr.Markdown("", elem_classes=["main"])

                def on_select_ucl(country):
                    return get_ucl_card(country)

                ucl_select.change(
                    fn=on_select_ucl,
                    inputs=[ucl_select],
                    outputs=[ucl_output],
                )
                on_select_ucl("France")

            # ── Tab 4: 完整排行 ──────────────────────────────────────────
            with gr.TabItem("📊 完整排行"):
                gr.Markdown("<p class='section-header'>全部球队概率排行</p>", elem_classes=["main"])

                all_rows = []
                for r in results:
                    flag = FLAG.get(r["country"], "🏳️")
                    shift = r["shift"]
                    shift_str = f"{shift*100:+.1f}%" if abs(shift) > 0.005 else "~0%"
                    all_rows.append(
                        f"| {flag} {r['country']} | {r['elo']:.0f} | "
                        f"{r['logical_prob']:.1%} | {r['final_prob']:.1%} | {shift_str} | "
                        f"{r['iching']} | {r['verdict'].split()[0] if r['verdict'] else '—'} |"
                    )

                table = (
                    "| # | 球队 | Elo | 逻辑 | 玄学 | 偏移 | 卦象 | 判定 |\n"
                    + "|---|------|-----|------|------|------|------|------|\n"
                    + "\n".join(all_rows)
                )
                gr.Markdown(table, elem_classes=["main"])

        # ── 页脚 ──────────────────────────────────────────
        gr.Markdown(
            "<p style='text-align:center;color:#4d5566;font-size:0.8rem;padding:16px 0 8px'>"
            "数据来源：Wikipedia真实阵容 + FiveThirtyEight Elo | "
            "玄学模块：道德经 · 易经 · 三重境界 · 欧冠心态信号 | "
            "⚠️ 预测仅供参考，不构成投注建议"
            "</p>",
            elem_classes=["main"],
        )

    return demo


if __name__ == "__main__":
    print("🚀 启动移动端看板...")
    print("   本地访问: http://localhost:7861")
    print("   局域网访问: http://$(ipconfig getifaddr en0):7861")
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7861,
        share=True,
        show_error=True,
    )
