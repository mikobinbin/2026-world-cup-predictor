"""
世界杯冠军预测看板 / World Cup 2026 Champion Predictor Dashboard

用法 / Usage:
    streamlit run src/dashboard/leaderboard.py
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
import os
import json
import random
from datetime import datetime

# ── 全局随机种子（确保结果可复现）─────────────────────────────────────────
RANDOM_SEED = 42
random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# ── 项目路径 ──────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, ROOT)

from src.models.player_scoring import Player, Squad
from src.models.team_scoring import score_all_teams, ModelWeights
from src.models.mystic_factor import MysticFactorEngine, generate_mystic_report
from scripts.elo_scraper import get_all_team_elos, save_elo_cache, load_elo_cache

# ── 常量 ──────────────────────────────────────────────
WIKI_DATA = os.path.join(ROOT, "data", "wc2026_players_processed.json")

QUALIFIED_TEAMS = [
    "Argentina", "Brazil", "Uruguay", "Colombia", "Ecuador", "Paraguay",
    "France", "Germany", "Spain", "England", "Portugal", "Netherlands",
    "Belgium", "Croatia", "Switzerland", "Austria", "Czech Republic", "Turkey", "Sweden",
    "Morocco", "Senegal", "Algeria", "Egypt", "Ghana", "Ivory Coast", "Tunisia", "DR Congo", "Cape Verde",
    "Japan", "South Korea", "Iran", "Iraq", "Qatar", "Saudi Arabia", "Australia",
    "Uzbekistan", "Jordan",
    "USA", "Mexico", "Canada", "Panama", "Curaçao", "Haiti", "New Zealand",
    "Norway", "South Africa", "Bosnia and Herzegovina", "Scotland",
]

HOST_COUNTRY = "USA"
DEFENDING_CHAMPION = "Argentina"

# ── 标签翻译映射 ──────────────────────────────────────────────
FACTOR_LABELS = {
    "elo":         "Elo Anchoring / Elo锚点",
    "age":         "Age Structure / 年龄结构",
    "experience":  "Tournament Exp. / 大赛经验",
    "form":        "Recent Form / 近期状态",
    "coaching":    "Coaching / 教练因素",
    "mystic":      "Mystic / 玄学因子",
}

MYSTIC_MODE_LABELS = {
    "conservative": "🟢 Conservative / 保守",
    "aggressive":   "🟡 Aggressive / 激进",
    "mystical":     "🔮 Mystical / 玄学",
}


@st.cache_data
def load_wiki_data():
    if not os.path.exists(WIKI_DATA):
        return {}
    with open(WIKI_DATA, encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_elo_data():
    cache_path = os.path.join(ROOT, "data", "elo_cache_2026.json")
    elos = load_elo_cache(cache_path)
    if elos is None:
        elos = get_all_team_elos(QUALIFIED_TEAMS)
        save_elo_cache(elos, cache_path)
    return elos


def normalize_position(pos: str) -> str:
    pos = pos.strip().upper()
    if "GK" in pos:
        return "GK"
    if "DF" in pos or "BACK" in pos or "DEFENDER" in pos:
        return "DF"
    if "MF" in pos or "MIDFIELDER" in pos:
        return "MF"
    if "FW" in pos or "FORWARD" in pos or "STRIKER" in pos or "WINGER" in pos:
        return "FW"
    return "MF"


def infer_tournaments(caps: int, age: int):
    if age >= 25 and caps >= 10:
        return ["2022"]
    if age >= 23 and caps >= 20:
        return ["2022"]
    if age >= 22 and caps >= 30:
        return ["2022"]
    return []


def estimate_mv(pos: str, caps: int, age: int) -> float:
    base = {"GK": 8, "DF": 12, "MF": 15, "FW": 20}.get(pos, 10)
    caps_factor = min(2.0, caps / 30 + 0.5)
    age_factor = 1.5 if 27 <= age <= 29 else (1.2 if 24 <= age <= 26 else (0.8 if age > 31 else 0.9))
    return round(base * caps_factor * age_factor, 1)


def build_squads(wiki_data: dict, elos: dict):
    teams = wiki_data.get("teams", {})
    squads = {}
    sample_count = 0

    for country in QUALIFIED_TEAMS:
        elo = elos.get(country, 1650.0)

        if country in teams:
            players_raw = teams[country].get("players", [])
            players = []
            for p in players_raw:
                age = p.get("age")
                if not age:
                    continue
                caps = p.get("caps", 0)
                pos = normalize_position(p.get("position", "MF"))
                tournaments = infer_tournaments(caps, age)
                mv = estimate_mv(pos, caps, age)
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

            # 同样用哈希固定 coaching_factor
            coach_hash = hash(country) % 1000 / 1000.0
            coaching_factor = 0.4 + coach_hash * 0.5

            if players:
                squads[country] = Squad(
                    country=country, players=players, elo=elo,
                    recent_win_rate=0.3 + (elo - 1500) / 1000 * 0.5,
                    coaching_factor=coaching_factor,
                    tournament_history=["2022"] if country == "Argentina" else [],
                )
                continue

        sample_count += 1
        _build_sample(country, elo, squads)

    return squads, sample_count


def _build_sample(country: str, elo: float, squads: dict):
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

    # 以 country name 的哈希为种子，确保每队 coaching_factor 固定不变
    coach_hash = hash(country) % 1000 / 1000.0  # 0.0 ~ 0.999
    coaching_factor = 0.4 + coach_hash * 0.5     # 0.4 ~ 0.9

    squads[country] = Squad(
        country=country, players=players, elo=elo,
        recent_win_rate=0.3 + (elo - 1500) / 1000 * 0.5,
        coaching_factor=coaching_factor,
        tournament_history=["2022"] if country in [DEFENDING_CHAMPION] else [],
    )


@st.cache_data
def run_predictions(squads: dict, mystic_mode: str):
    weights = ModelWeights()
    squad_list = list(squads.values())
    results = score_all_teams(
        squad_list, weights=weights, mystic_mode=mystic_mode,
        host_team=HOST_COUNTRY, defending_champ=DEFENDING_CHAMPION,
    )
    return results, squads


# ── Streamlit 页面 / Page Config ─────────────────────────────────────────
st.set_page_config(
    page_title="🏆 2026 World Cup Champion Predictor / 世界杯冠军预测",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 自定义CSS ────────────────────────────────────────────────────────────
css_path = os.path.join(ROOT, "assets", "custom.css")
if os.path.exists(css_path):
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── 侧边栏 / Sidebar ──────────────────────────────────────────────────────
st.sidebar.header("⚙️ Control Panel / 控制面板")
mystic_mode = st.sidebar.selectbox(
    "Mystic Mode / 玄学模式",
    ["conservative", "aggressive", "mystical"],
    index=0,
    format_func=lambda x: MYSTIC_MODE_LABELS[x],
)
top_n = st.sidebar.slider("Teams to Display / 显示球队数", 5, 48, 20)

# ── 主标题 / Main Title ─────────────────────────────────────────────────────
st.title("🏆 2026 FIFA World Cup Champion Predictor / 2026美加墨世界杯冠军预测")
st.caption(
    f"Data Sources: Wikipedia Real Squads + FiveThirtyEight Elo | "
    f"Mode: {MYSTIC_MODE_LABELS[mystic_mode].split(' / ')[0]} / 模式: {mystic_mode}"
)

# ── 全局缓存（session 级）────────────────────────────────────────────────────
_wiki_data = None
_squads    = None
_results   = None

def _ensure_data():
    global _wiki_data, _squads, _results
    if _results is not None:
        return _squads, _results
    _wiki_data = load_wiki_data()
    elo_data   = load_elo_data()
    _squads, sample_count = build_squads(_wiki_data, elo_data)
    _results, _squads = run_predictions(_squads, mystic_mode)
    return _squads, _results

_squads, _results = None, None

def _ensure_data():
    global _wiki_data, _squads, _results
    if _results is not None:
        return _squads, _results
    _wiki_data = load_wiki_data()
    elo_data   = load_elo_data()
    _squads, sample_count = build_squads(_wiki_data, elo_data)
    _results, _squads = run_predictions(_squads, mystic_mode)
    return _squads, _results, sample_count

squads, results, sample_count = _ensure_data()
real_count = len(squads) - sample_count
wiki_data  = _wiki_data

st.sidebar.markdown(f"**Data Coverage / 数据覆盖**: {real_count} real / 真实 / {sample_count} sample / 样本")
st.sidebar.markdown(f"**Total Teams / 总球队数**: {len(squads)}")

# ── 标签页 / Tabs ──────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🏆 Probability Ranking / 冠军概率榜",
    "📊 Factor Breakdown / 因子拆解",
    "👥 Player Matrix / 球员矩阵",
    "🔮 Mystic View / 玄学视角",
    "📋 Team Profiles / 球队画像",
    "⚔️ H2H Predictor / 对战预测",
])

# ══════════════════════════════════════════════════════════════════
# Tab 1: 冠军概率排行榜 / Champion Probability Ranking
# ══════════════════════════════════════════════════════════════════
with tab1:
    # ── Hero大数字：TOP 3 冠军概率 ──────────────────────────
    st.markdown('<div class="section-header"><h4>🏆 TOP 3 冠军概率 / Champion Probability</h4></div>', unsafe_allow_html=True)

    top3 = results[:3]
    col1, col2, col3 = st.columns([1.4, 1.2, 1.0])

    podium_data = [
        (col1, top3[0], "rank-1", "🥇 1st"),
        (col2, top3[1], "rank-2", "🥈 2nd"),
        (col3, top3[2], "rank-3", "🥉 3rd"),
    ]

    for col, r, rank_cls, rank_label in podium_data:
        sq = squads.get(r.country)
        elo_val = int(sq.elo) if sq else "—"
        trend_icon = "↑" if r.final_probability > 0.10 else ("↓" if r.final_probability < 0.04 else "—")
        trend_color = "#3FB950" if r.final_probability > 0.10 else ("#F85149" if r.final_probability < 0.04 else "#8B949E")
        with col:
            st.markdown(f"""
            <div class="hero-card {rank_cls}">
                <div class="hero-rank-badge">{rank_label}</div>
                <div class="hero-team-name">{r.country}</div>
                <div class="hero-prob">{r.final_probability*100:.1f}%</div>
                <div class="hero-prob-label">Probability</div>
                <div class="hero-elo">Elo {elo_val} · <span style="color:{trend_color}">{trend_icon}</span></div>
            </div>
            """, unsafe_allow_html=True)

    # ── 概率进度条列表 ──────────────────────────────────────
    st.markdown("")
    st.markdown('<div class="section-header"><h4>📊 All Teams Probability Bar / 全球队概率排行</h4></div>', unsafe_allow_html=True)

    bar_cols = st.columns([1, 1])
    display_teams = results[:min(top_n, 24)]
    half = len(display_teams) // 2 + len(display_teams) % 2

    for idx, r in enumerate(display_teams):
        col = bar_cols[idx % 2]
        with col:
            pct = r.final_probability * 100
            prob_float = r.final_probability
            # Color tier
            if prob_float >= 0.10:
                tier_cls = "high"
            elif prob_float >= 0.04:
                tier_cls = "medium"
            else:
                tier_cls = "low"
            bar_width = max(pct, 0.5)  # minimum visible bar

            st.markdown(f"""
            <div class="prob-bar-container">
                <div class="prob-bar-header">
                    <span class="prob-bar-team">{r.country}</span>
                    <span class="prob-bar-value">{pct:.1f}%</span>
                </div>
                <div class="prob-bar-track">
                    <div class="prob-bar-fill {tier_cls}" style="width: {bar_width:.1f}%"></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

    # ── 数据表格（简化版）─────────────────────────────────────
    st.markdown("")
    st.markdown('<div class="section-header"><h4>📋 Full Ranking Table / 完整排行榜</h4></div>', unsafe_allow_html=True)

    df_prob = pd.DataFrame([{
        "#": i + 1,
        "Team / 球队": r.country,
        "Prob%": f"{r.final_probability * 100:.1f}%",
        "Elo": f"{r.elo_score * 100:+.0f}",
        "Age": f"{r.age_score * 100:+.0f}",
        "Exp": f"{r.experience_score * 100:+.0f}",
        "Form": f"{r.form_score * 100:+.0f}",
        "Coach": f"{r.coaching_score * 100:+.0f}",
        "Mystic": f"{r.mystic_score * 100:+.0f}",
    } for i, r in enumerate(results[:top_n])])

    st.dataframe(
        df_prob,
        hide_index=True,
        use_container_width=True,
        height=38 * (min(top_n, 20) + 1),
    )

# ══════════════════════════════════════════════════════════════════
# Tab 2: 因子拆解 / Factor Breakdown
# ══════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("📊 Factor Breakdown / 因子拆解 — Each Factor's Contribution / 各因子贡献")

    team_options = [r.country for r in results[:20]]
    selected = st.selectbox("Select Team / 选择球队", team_options)
    result = next(r for r in results if r.country == selected)

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.markdown(f"### {result.country}")
        st.metric("Final Probability / 最终概率", f"{result.final_probability * 100:.2f}%")
        st.caption(f"CI / 置信区间: {result.confidence_interval[0]*100:.1f}% – {result.confidence_interval[1]*100:.1f}%")
        st.caption(result.narrative)

    with col_right:
        factors = {
            "Elo Anchoring / Elo锚点":     result.elo_score * 100,
            "Age Structure / 年龄结构":    result.age_score * 100,
            "Tournament Exp. / 大赛经验": result.experience_score * 100,
            "Recent Form / 近期状态":       result.form_score * 100,
            "Coaching / 教练因素":          result.coaching_score * 100,
            "Mystic / 玄学因子":            result.mystic_score * 100,
        }
        fig_df = pd.DataFrame({
            "Factor / 因子":    list(factors.keys()),
            "Contribution% / 贡献%": list(factors.values()),
        }).set_index("Factor / 因子")
        st.bar_chart(fig_df[["Contribution% / 贡献%"]], color="#4ECDC4")

    st.divider()

    # TOP10 热力图 / TOP10 Heatmap
    st.subheader("TOP10 Teams Factor Heatmap / TOP10球队因子热力图")
    heat_data = pd.DataFrame({
        r.country: {
            "Elo Anchoring / Elo锚点":     r.elo_score * 100,
            "Age Structure / 年龄结构":    r.age_score * 100,
            "Tournament Exp. / 大赛经验": r.experience_score * 100,
            "Recent Form / 近期状态":      r.form_score * 100,
            "Coaching / 教练因素":          r.coaching_score * 100,
        }
        for r in results[:10]
    }).T
    st.dataframe(
        heat_data.style.background_gradient(cmap="RdYlGn", axis=1),
        width='stretch',
        height=300,
    )

# ══════════════════════════════════════════════════════════════════
# Tab 3: 球员矩阵 / Player Matrix
# ══════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("👥 Player Matrix / 球员矩阵")

    wiki_teams = wiki_data.get("teams", {})
    team_list = [t for t in QUALIFIED_TEAMS if t in squads]

    sel_team = st.selectbox("Select Team / 选择球队", team_list)
    sq = squads.get(sel_team)

    if sq:
        st.markdown(
            f"**Elo: {sq.elo:.0f}** | "
            f"**Players / 球员数: {len(sq.players)}** | "
            f"**Maturity Index / 成熟度指数: {sq.get_squad_maturity_index():.3f}**"
        )

        player_rows = []
        for p in sq.players:
            player_rows.append({
                "Name / 姓名":           p.name,
                "Pos / 位置":            p.position,
                "Age / 年龄":            p.age,
                "Age Bucket / 年龄段":   p.get_age_bucket(),
                "Caps / 出场":          p.national_caps,
                "Goals / 进球":         p.national_goals,
                "Score / 评分":          round(p.calculate_player_score(), 1),
                "WC Exp / 世界杯":       "✅" if p.tournaments else "❌",
                "Club / 俱乐部":         p.club,
            })
        player_rows.sort(key=lambda x: -x["Score / 评分"])

        st.dataframe(
            pd.DataFrame(player_rows),
            hide_index=True,
            width='stretch',
            height=min(600, 38 * (len(player_rows) + 2)),
        )

        # 年龄 / 位置分布
        col_a, col_b = st.columns(2)
        with col_a:
            st.subheader("Age Distribution / 年龄分布")
            age_dist = sq.get_age_distribution()
            st.bar_chart(
                pd.DataFrame.from_dict(age_dist, orient="index", columns=["Count / 人数"]),
                color="#9b59b6",
            )
        with col_b:
            st.subheader("Position Distribution / 位置分布")
            pos_dist = {}
            for p in sq.players:
                pos_dist[p.position] = pos_dist.get(p.position, 0) + 1
            st.bar_chart(
                pd.DataFrame.from_dict(pos_dist, orient="index", columns=["Count / 人数"]),
                color="#3498db",
            )
    else:
        st.info("No data available for this team / 暂无该球队数据")

# ══════════════════════════════════════════════════════════════════
# Tab 4: 玄学视角 / Mystic View
# ══════════════════════════════════════════════════════════════════
with tab4:
    st.markdown('<div class="section-header"><h4>🔮 Mystic View / 玄学视角 — 承认数据盲区的系统性修正</h4></div>', unsafe_allow_html=True)

    # ── 准备MysticFactorEngine输入数据 ──────────────────
    engine = MysticFactorEngine()
    mystic_teams = []
    for r in results:
        sq = squads.get(r.country)
        if not sq:
            continue
        ages = [p.age for p in sq.players]
        avg_age = sum(ages) / len(ages) if ages else 27.0
        exp_count = sum(1 for p in sq.players if p.national_caps >= 30)
        exp_ratio = exp_count / len(sq.players) if sq.players else 0.0
        mystic_teams.append({
            "country": r.country,
            "elo": sq.elo,
            "prob": r.final_probability,
            "avg_age": avg_age,
            "exp_ratio": exp_ratio,
            "is_host": (r.country == HOST_COUNTRY),
            "is_defending": (r.country == DEFENDING_CHAMPION),
            "is_first_tournament": (exp_ratio < 0.1),
        })

    mystic_results = engine.analyze(mystic_teams, stage="tournament")

    # ── 三大机制摘要卡（紧凑双语版）─────────────────────────
    st.markdown("##### 三大机制 / Three Mechanisms")
    mech_col1, mech_col2, mech_col3 = st.columns(3)

    mechanisms = [
        ("🎰", "彩票悖论 / Lottery Paradox",
         "• 热门被情绪买高 → 赔率压低 → 模型逆向降权\n• 冷门被忽视 → 赔率偏高 → 模型向上抬权\n• Favorites overpriced by sentiment → model adjusts down\n• Underdogs ignored → model adjusts up"),
        ("⚡", "小组赛惊险 / Group Stage Volatility",
         "• 强队需求是出线，不是全胜\n• 小组赛输一场≠淘汰，顺位仍可晋级\n• Strong teams only need to qualify — not win every match\n• One group-stage loss ≠ elimination"),
        ("🎲", "淘汰赛冥冥中 / Knockout Fate",
         "• 单场定胜负，运气/伤病/裁判放大\n• 弱队有更多机会制造冷门\n• Single-game elimination amplifies luck & randomness\n• Underdogs have real upset chances in knockout rounds"),
    ]

    for col, (icon, title, text) in zip([mech_col1, mech_col2, mech_col3], mechanisms):
        with col:
            st.markdown(f"""
            <div style="
                background:#1C2128;
                border:1px solid #30363D;
                border-left:3px solid #D4AF37;
                border-radius:8px;
                padding:10px 12px;
                margin-bottom:8px;
            ">
                <div style="display:flex;align-items:center;gap:8px;margin-bottom:6px">
                    <span style="font-size:1.1rem">{icon}</span>
                    <span style="font-weight:700;color:#E6EDF3;font-size:0.8rem">{title}</span>
                </div>
                <div style="color:#8B949E;font-size:0.68rem;line-height:1.5;white-space:pre-line">{text}</div>
            </div>
            """, unsafe_allow_html=True)

    st.divider()

    # ── 全球队概览表（精简列）─────────────────────────────
    st.markdown("##### 全球队玄学总览 / All-Team Overview")
    tao_signal_map = {
        "⚠️「反者道之动」": "⚠️反者",
        "🌊「柔弱胜刚强」": "🌊柔克刚",
        "🔴「道法自然」违反": "🔴违自然",
        "💧「上善若水」显现": "💧上善水",
        "➖ 道德经无明显信号": "➖中性",
    }
    full_overview = []
    for mr in mystic_results:
        total_shift = (
            mr.contrarian_shift + mr.group_stage_volatility
            + mr.knockout_uncertainty + mr.favorite_curse
        )
        shift_emoji = "📈" if total_shift > 0.005 else ("📉" if total_shift < -0.005 else "➖")
        tao_sig = tao_signal_map.get(mr.tao.tao_recommendation, "➖")
        hex_name = mr.iching.hexagram[0] + mr.iching.hexagram[1]
        zen_level = f"第{mr.zen.wisdom_level}境"
        betting_short = mr.zen.final_recommendation.split("—")[0].strip() if "—" in mr.zen.final_recommendation else mr.zen.final_recommendation

        full_overview.append({
            "Team": mr.country,
            "Elo": int(mr.elo),
            "Logical": f"{mr.logical_prob:.1%}",
            "Mystic": f"{mr.mystic_prob:.1%}",
            "Shift": f"{total_shift*100:+.2f}%",
            "T": shift_emoji,
            "Zen": zen_level,
            "Tao": tao_sig,
            "IChing": hex_name,
            "Verdict": betting_short,
            "Conf": f"{mr.confidence:.0f}%",
        })

    st.dataframe(
        pd.DataFrame(full_overview),
        use_container_width=True,
        hide_index=True,
        height=min(420, 20 * 35),
    )
    st.caption("T=Trend趋势 | Zen=三重境界 | Tao=道德经 | IChing=易经卦象 | Verdict=第三境建议")

    st.divider()

    # ── 队伍详细分析（折叠面板）──────────────────────────
    st.markdown("##### 队伍详细分析 / Team Deep Dive")

    # 框架说明折叠
    with st.expander("📖 四维哲学框架说明 / Philosophy Framework"):
        st.markdown("""
| 维度 | 核心含义 |
|---|---|
| **需求因 vs 情绪因** | 需求=不得不做，长期有益。情绪=可做可不做，做了短期愉悦、长期痛苦 |
| **求内 vs 求外** | 求内=知道自己是谁，不依赖外部条件。求外=依赖主场/对手失误 |
| **冥冥中有一股力量** | 数据里不存在：VAR误判、点球不进、门框、绝杀 |
| **强势方诅咒** | 越强责任越大，大热倒灶的本质是强势方压力下做出情绪性决策 |
        """)

    # 队伍选择
    mystic_countries = [mr.country for mr in mystic_results[:30]]
    selected_mystic = st.selectbox(
        "🔍 Select Team / 选择球队",
        options=mystic_countries,
        index=0,
    )

    selected_mr = next((mr for mr in mystic_results if mr.country == selected_mystic), None)
    if selected_mr:
        # ── 核心数据行 ────────────────────────────────────
        prob_delta = (selected_mr.mystic_prob - selected_mr.logical_prob) * 100
        delta_str = f"{prob_delta:+.1f}%" if abs(prob_delta) > 0.05 else "~0%"

        st.markdown(f"""
        <div style="display:flex;gap:12px;margin:12px 0;flex-wrap:wrap">
            <div style="flex:1;min-width:120px;background:#1C2128;border:1px solid #D4AF37;border-radius:10px;padding:14px;text-align:center">
                <div style="color:#8B949E;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em">逻辑概率</div>
                <div style="color:#E6EDF3;font-size:1.4rem;font-weight:700">{selected_mr.logical_prob:.1%}</div>
            </div>
            <div style="flex:1;min-width:120px;background:#1C2128;border:1px solid #D4AF37;border-radius:10px;padding:14px;text-align:center">
                <div style="color:#8B949E;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em">玄学修正后</div>
                <div style="color:#D4AF37;font-size:1.4rem;font-weight:700">{selected_mr.mystic_prob:.1%}</div>
            </div>
            <div style="flex:1;min-width:120px;background:#1C2128;border:1px solid #30363D;border-radius:10px;padding:14px;text-align:center">
                <div style="color:#8B949E;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em">修正幅度</div>
                <div style="color:#58A6FF;font-size:1.4rem;font-weight:700">{delta_str}</div>
            </div>
            <div style="flex:1;min-width:120px;background:#1C2128;border:1px solid #30363D;border-radius:10px;padding:14px;text-align:center">
                <div style="color:#8B949E;font-size:0.7rem;text-transform:uppercase;letter-spacing:0.08em">置信度</div>
                <div style="color:#E6EDF3;font-size:1.4rem;font-weight:700">{selected_mr.confidence:.0f}%</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── 四项修正来源 ──────────────────────────────────
        shifts = [
            ("🎰 彩票悖论", selected_mr.contrarian_shift, "情绪因"),
            ("⚡ 小组赛波动", selected_mr.group_stage_volatility, "需求因"),
            ("🎲 淘汰赛弹性", selected_mr.knockout_uncertainty, "冥冥中"),
            ("💀 强势方诅咒", selected_mr.favorite_curse, "压力因"),
        ]

        shift_items = "".join(
            f"<div style='flex:1;min-width:140px;background:#1C2128;border:1px solid #30363D;border-radius:8px;padding:10px'>"
            f"<div style='font-size:0.75rem;color:#8B949E'>{label}</div>"
            f"<div style='color:{'#3FB950' if s > 0 else '#F85149' if s < 0 else '#8B949E'};font-size:1.1rem;font-weight:700'>{s*100:+.2f}%</div>"
            f"</div>"
            for label, s, _ in shifts if abs(s) > 0.0001
        )
        if shift_items:
            st.markdown(f"<div style='display:flex;gap:10px;flex-wrap:wrap;margin-bottom:12px'>{shift_items}</div>", unsafe_allow_html=True)

        # ── 折叠分析面板 ──────────────────────────────────
        with st.expander("🌄 三重境界 / Zen — 看山是山（点击展开）"):
            zen = selected_mr.zen
            st.markdown(f"""
**第一境：看山是山**（数据原始呈现）
> {zen.raw_echo}

**第二境：看山不是山**（偏差分析）
> {zen.bias_echo}

**智慧层次：第{zen.wisdom_level}境** — {zen.wisdom_note}

**第三境：看山还是山**（回归本质）
> {zen.team_essence}：{zen.essence_echo}

**最终建议：{zen.final_recommendation}**
            """)

        with st.expander("📜 道德经 / Tao — 四句真言（点击展开）"):
            tao = selected_mr.tao
            st.markdown(f"""
| 主题 | 信号 | 说明 |
|---|---|---|
| **反者道之动** | {tao.reversal_risk:.0%}风险 | {tao.reversal_insight[:100]} |
| **柔弱胜刚强** | {tao.softness_power:.0%}柔力 | {tao.softness_insight[:100]} |
| **道法自然** | {tao.natural_flow} | {tao.natural_insight[:100]} |
| **上善若水** | {tao.water_score:.0%}水德 | {tao.water_insight[:100]} |

**道德经信号：{tao.tao_recommendation}**
            """)

        with st.expander("🔥 易经 / IChing — 卦象分析（点击展开）"):
            ich = selected_mr.iching
            st.markdown(f"""
**{ich.hexagram[0]}卦 {ich.hexagram[1]}** — 起卦依据：{ich.hexagram_source}

> **处境：** {ich.situation}

> **课题：** {ich.challenge}

> **机遇：** {ich.opportunity}

> **变化：** {ich.transformation}

---

⚠️ {ich.hexagram_warning}
            """)

        with st.expander("🧭 四维哲学 / Four Dimensions — 需求·内外·冥冥·诅咒（点击展开）"):
            dim_col1, dim_col2 = st.columns(2)
            with dim_col1:
                for dim in selected_mr.philosophy_dimensions[:2]:
                    in_tag = "✓已量化" if dim.in_model else "○定性参考"
                    st.markdown(f"**[{dim.dimension}]** **{dim.direction}** ({in_tag})")
                    st.caption(dim.insight[:100])
            with dim_col2:
                for dim in selected_mr.philosophy_dimensions[2:]:
                    in_tag = "✓已量化" if dim.in_model else "○定性参考"
                    st.markdown(f"**[{dim.dimension}]** **{dim.direction}** ({in_tag})")
                    st.caption(dim.insight[:100])

# ══════════════════════════════════════════════════════════════════
# Tab 5: 球队画像 / Team Profiles
# ══════════════════════════════════════════════════════════════════
with tab5:
    st.subheader("📋 Team Profiles / 球队画像")

    # ── 球队选择 / Team Selector ──────────────────────────────────────
    # 按概率排序，热门球队在前
    team_options = [r.country for r in results]
    selected = st.selectbox(
        "Select a team / 选择球队",
        options=team_options,
        index=0,
        format_func=lambda x: next(
            f"{x} ({r.final_probability:.1%})" for r in results if r.country == x
        ),
    )

    # ── 画像数据 / Profile Data ───────────────────────────────────────
    # 世界杯历史（手动维护，每队一段）
    WC_HISTORY = {
        "Brazil": {
            "best": "5次冠军（1958/1962/1970/1994/2002）",
            "appearances": "22届世界杯，缺席仅2届",
            "legacy": "世界杯历史最佳球队，没有之一",
        },
        "France": {
            "best": "2次冠军（1998/2018）",
            "appearances": "16届世界杯",
            "legacy": "2018年班底仍在当打之年，2022年亚军",
        },
        "Argentina": {
            "best": "3次决赛（1978/1986冠军，2022冠军）",
            "appearances": "18届世界杯",
            "legacy": "2022年封王，梅西时代画上句号，仍是顶级强队",
        },
        "England": {
            "best": "1次冠军（1966）",
            "appearances": "17届世界杯",
            "legacy": "2022年四强，点球魔咒尚未完全破解",
        },
        "Germany": {
            "best": "4次冠军（1954/1974/1990/2014）",
            "appearances": "20届世界杯",
            "legacy": "2022年小组赛出局，迎来新生代重建",
        },
        "Portugal": {
            "best": "1次四强（2006），从未进决赛",
            "appearances": "8届世界杯",
            "legacy": "C罗最后一届，葡萄牙黄金一代最后机会",
        },
        "Netherlands": {
            "best": "3次亚军（1974/1978/2010）",
            "appearances": "11届世界杯",
            "legacy": "无冕之王，2022年未晋级",
        },
        "Spain": {
            "best": "1次冠军（2010）",
            "appearances": "16届世界杯",
            "legacy": "2008-2012王朝后沉寂，2022年止步16强",
        },
        "Croatia": {
            "best": "2次半决赛（2018亚军，2022季军）",
            "appearances": "6届世界杯",
            "legacy": "莫德里奇最后一届，中生代接过旗帜",
        },
        "Belgium": {
            "best": "3次四强（1986/2018/2022? 待定）",
            "appearances": "14届世界杯",
            "legacy": "黄金一代逐渐淡出，2022年止步小组赛",
        },
        "Italy": {
            "best": "4次冠军（1934/1938/1982/2006）",
            "appearances": "18届世界杯",
            "legacy": "2022年未晋级，连续缺席两届世界杯",
        },
        "Uruguay": {
            "best": "2次冠军（1930/1950）",
            "appearances": "14届世界杯",
            "legacy": "两代神锋领衔，南美劲旅",
        },
        "Mexico": {
            "best": "2次八强（1970/1986）",
            "appearances": "18届世界杯",
            "legacy": "中北美老大，主场优势加持",
        },
        "Japan": {
            "best": "3次十六强（2002/2010/2022）",
            "appearances": "7届世界杯",
            "legacy": "亚洲最强，2022年逆转德国/西班牙",
        },
        "South Korea": {
            "best": "4强（2002，主办国）",
            "appearances": "11届世界杯",
            "legacy": "2002年争议四强，此后最好成绩16强",
        },
        "USA": {
            "best": "4强（1930），近年止步16强",
            "appearances": "11届世界杯",
            "legacy": "2026年主办国，美职联球员为主",
        },
        "Morocco": {
            "best": "4强（2022，首支非洲球队进四强）",
            "appearances": "6届世界杯",
            "legacy": "2022年最大黑马，摩洛哥足球黄金期",
        },
        "Senegal": {
            "best": "8强（2002）",
            "appearances": "3届世界杯",
            "legacy": "马内领衔，非洲新势力",
        },
        "Portugal": {
            "best": "4强（2006）",
            "appearances": "8届世界杯",
            "legacy": "C罗最后一届，全队为他而战",
        },
        "England": {
            "best": "冠军（1966）",
            "appearances": "17届世界杯",
            "legacy": "本届纸面前锋最强，防线老化是隐患",
        },
    }

    # 踢法风格
    TEAM_STYLE = {
        "Brazil": "技术流+速度型反击，内马尔不在仍有多位爆破手，中场控制力历史级别",
        "France": "4231防守反击，姆巴佩居左格列兹曼居中，防线老化但门将稳定",
        "Argentina": "4141保守控球，中场绞杀+梅西后撤组织，定位球是杀手锏",
        "England": "433高位压迫，边路爆点丰富，但中卫转身慢是命门",
        "Germany": "4231传控重建，阿森纳/拜仁帮主导，年轻风暴值得期待",
        "Portugal": "433边路传中，B费前插+莱奥爆破，C罗仍是精神领袖",
        "Croatia": "4231中场绞杀，莫德里奇节拍器，防守强硬但锋线效率一般",
        "Belgium": "3421菱形中场，德布劳内核心，防线换血期不够稳定",
        "Spain": "433tiki-taka复兴，青年军冲击力强，大赛经验欠缺",
        "Netherlands": "433控球型中卫压上，防线最强一环",
        "Italy": "352防守体系，中后场链式防守，反击靠边翼卫",
        "Mexico": "433技术流，脚下灵活但防守高空球弱势",
        "Japan": "4231战术执行强，2022已证明能赢德国/西班牙",
        "South Korea": "4231跑动压迫，孙兴慜单核驱动",
        "USA": "433主场跑动积极，美职联强度存疑",
        "Morocco": "4141防守严密，2022黑马血统，齐耶赫+马兹拉维双核",
        "Senegal": "4231防守反击，马内+门迪组合，非洲杯冠军底蕴",
    }

    # 有趣事实
    TEAM_FACTS = {
        "Brazil": "💡 巴西是唯一一支参加过每一届世界杯的球队（1930年起）",
        "France": "💡 1998年和2018年两次主场作战均夺冠——2026年呢？",
        "Argentina": "💡 马拉多纳1986年夺冠那届，贝利赛前说：'这场我只希望阿根廷赢'",
        "England": "💡 英格兰从未在大赛点球大战赢过德国（3战3败）",
        "Germany": "💡 德国在世界杯从未连续小组出局——2022年破了纪录",
        "Portugal": "💡 C罗连续5届世界杯进球——历史唯一",
        "Croatia": "💡 克罗地亚2018年是历史最好成绩——本届是莫德里奇最后一届",
        "Belgium": "💡 比利时'黄金一代'从未进过世界杯决赛，本届是最后机会",
        "Spain": "💡 2010年夺冠班底已全部退出，现在全是U25球员",
        "Italy": "💡 意大利连续缺席2018和2022两届世界杯——足球荒漠",
        "Netherlands": "💡 荷兰是世界杯历史上最著名的'无冕之王'，3进决赛3次亚军",
        "Mexico": "💡 墨西哥1970和1986两次主办世界杯，2026三国联合主办",
        "Japan": "💡 日本2022年成为首支击败德国和西班牙的亚洲球队",
        "South Korea": "💡 2002年韩国是首个打进世界杯4强的亚洲球队",
        "USA": "💡 美国1994年主办世界杯后，足球（soccer）才开始普及",
        "Morocco": "💡 摩洛哥2022年是首支打进世界杯4强的非洲/阿拉伯球队",
        "Senegal": "💡 塞内加尔2022年成为首支在卡塔尔赢球的非洲球队",
    }

    # ── 渲染画像 / Render Profile ─────────────────────────────────────
    result = next((r for r in results if r.country == selected), None)
    sq = squads.get(selected)
    if result and sq:
        prob = result.final_probability
        elo = sq.elo

        # 概率色条
        if prob > 0.20:
            prob_color = "🟢"
        elif prob > 0.05:
            prob_color = "🟡"
        elif prob > 0.02:
            prob_color = "🟠"
        else:
            prob_color = "🔴"

        # ── 头部卡片 ──────────────────────────────────────────────────
        header_col1, header_col2 = st.columns([3, 1])
        with header_col1:
            st.markdown(f"## {selected}")
            # 历史best
            hist = WC_HISTORY.get(selected, {})
            if hist:
                st.caption(f"🏆 Best: {hist.get('best', 'N/A')}")
                st.caption(f"📅 Appearances: {hist.get('appearances', 'N/A')}")
        with header_col2:
            st.markdown(f"## {prob_color} {prob:.1%}")
            st.caption("Champion Probability")

        st.divider()

        # ── 左列：球员 + 数据 ─────────────────────────────────────────
        col_left, col_right = st.columns([1, 1])

        with col_left:
            st.markdown("### 👥 Key Players / 关键球员")
            players_sorted = sorted(sq.players, key=lambda p: p.calculate_player_score(), reverse=True)
            top5 = players_sorted[:5]
            player_data = []
            for p in top5:
                score = p.calculate_player_score()
                age_emoji = "🧒" if p.age < 23 else ("🧓" if p.age > 32 else "⚽")
                caps_str = f"{p.national_caps}场" if p.national_caps > 0 else "—"
                goals_str = f"{p.national_goals}球" if p.national_goals > 0 else ""
                player_data.append({
                    "Player / 球员": p.name,
                    "Pos": p.position,
                    "Age": f"{age_emoji}{p.age}",
                    "Caps": caps_str,
                    "Goals": goals_str,
                    "Score": f"{score:.1f}",
                })
            st.dataframe(
                pd.DataFrame(player_data),
                use_container_width=True,
                hide_index=True,
            )

        with col_right:
            st.markdown("### 📊 Squad Stats / 阵容数据")
            # 从球员列表计算所有统计数据
            ages = [p.age for p in sq.players]
            avg_age = sum(ages) / len(ages) if ages else 0.0
            maturity = sq.get_squad_maturity_index()
            exp_count = sum(1 for p in sq.players if p.national_caps >= 30)
            peak_count = sum(1 for p in sq.players if 27 <= p.age <= 29)
            youth_count = sum(1 for p in sq.players if p.age < 23)

            st.metric("Avg Age / 平均年龄", f"{avg_age:.1f}岁",
                      delta="黄金年龄" if 26 <= avg_age <= 29 else ("偏老" if avg_age > 30 else "偏年轻"))
            st.metric("Maturity Index / 成熟度", f"{maturity:.3f}",
                      delta="优秀" if maturity > 0.7 else ("一般" if maturity > 0.5 else "年轻"))
            st.metric("Experienced (30+ caps) / 老将", f"{exp_count}人")
            st.metric("Peak Age (27-29) / 巅峰球员", f"{peak_count}人")
            st.metric("Youth (<23) / 年轻球员", f"{youth_count}人")
            st.metric("Elo Rating", f"{elo:.0f}",
                      delta="顶级" if elo > 1850 else ("强队" if elo > 1750 else "中游"))

            # 阵容深度：主力11人 vs 替補12-26人评分差距
            depth = sq.get_squad_depth()
            depth_label = "⬆️ 深度极好" if depth["depth_score"] > 0.75 \
                else ("✅ 深度良好" if depth["depth_score"] > 0.5 \
                else ("⚠️ 深度一般" if depth["depth_score"] > 0.25 else "🔴 深度薄弱"))
            st.metric(
                "Squad Depth / 阵容深度",
                f"{depth['depth_score']:.2f}",
                delta=f"先发均{depth['avg_starting']:.0f} / 替補均{depth['avg_bench']:.0f} / 差{depth['gap']:.0f}分 {depth_label}"
            )

        st.divider()

        # ── 中间：世界杯历史 + 踢法风格 ───────────────────────────────
        col_hist, col_style = st.columns([1, 1])

        with col_hist:
            st.markdown("### 🏆 World Cup Legacy / 世界杯履历")
            if hist:
                st.info(f"**Best Result / 最佳成绩：** {hist.get('best', 'N/A')}")
                st.info(f"**Appearances / 参赛次数：** {hist.get('appearances', 'N/A')}")
                st.markdown(f"_{hist.get('legacy', '')}_")
            else:
                st.warning("暂无数据 / No data available")

        with col_style:
            st.markdown("### 🎯 Playing Style / 踢法风格")
            style = TEAM_STYLE.get(selected, "数据不足，暂无风格描述")
            st.markdown(style)

        st.divider()

        # ── 底部：有趣事实 + 因子拆解 ─────────────────────────────────
        col_fact, col_factors = st.columns([1, 1])

        with col_fact:
            st.markdown("### 💡 Fun Fact / 有趣事实")
            fact = TEAM_FACTS.get(selected, "暂无有趣事实")
            st.success(fact)

        with col_factors:
            st.markdown("### 📈 Factor Breakdown / 因子拆解")
            factors = {
                "Elo锚点": f"{result.elo_score * 100:+.2f}%",
                "年龄结构": f"{result.age_score * 100:+.2f}%",
                "大赛经验": f"{result.experience_score * 100:+.2f}%",
                "近期状态": f"{result.form_score * 100:+.2f}%",
                "教练因素": f"{result.coaching_score * 100:+.2f}%",
                "玄学因子": f"{result.mystic_score * 100:+.2f}%",
            }
            for k, v in factors.items():
                delta_val = float(v.replace("%", "").replace("+", ""))
                st.metric(k, v, delta="正向" if delta_val > 0 else ("负向" if delta_val < 0 else "中性"))

        st.divider()

        # ── Narrative ─────────────────────────────────────────────────
        st.markdown("### 📝 Scouting Report / 球探报告")
        st.markdown(f"_{result.narrative}_")

        st.caption(
            f"Generated / 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
            f"Mode: {mystic_mode} | "
            f"{'📊 Real Wikipedia data / 真实数据' if sq.country in wiki_data else '🎲 Sample data / 样本数据'}"
        )

st.divider()
st.caption(
    f"Generated / 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | "
    f"Data Coverage / 数据覆盖: {real_count}/{len(squads)} teams with real squads / 队真实阵容"
)


# ══════════════════════════════════════════════════════════════════
# Tab 6: 对战预测 / H2H Match Predictor
# ══════════════════════════════════════════════════════════════════
with tab6:
    st.subheader("⚔️ H2H Match Predictor / 对战预测")

    # ── 历史交锋记录（手动维护主要对阵）────────────────────────────────
    H2H_RECORDS = {
        ("Argentina", "Brazil"):     {"total": 114, "W_A": 41, "D": 26, "W_B": 47, "note": "南美经典对决，巴西总体占优"},
        ("Argentina", "France"):     {"total": 12,  "W_A": 5,  "D": 3,  "W_B": 4,  "note": "2022决赛重演，阿根廷点球险胜"},
        ("Brazil",    "France"):     {"total": 18,  "W_A": 6,  "D": 4,  "W_B": 8,  "note": "2006决赛，法国加时胜"},
        ("France",    "Germany"):    {"total": 31,  "W_A": 13, "D": 4,  "W_B": 14, "note": "欧洲强强对话，大赛多次相遇"},
        ("England",   "Germany"):    {"total": 32,  "W_A": 13, "D": 5,  "W_B": 14, "note": "经典大战，点球3战3败"},
        ("England",   "France"):     {"total": 31,  "W_A": 7,  "D": 7,  "W_B": 17, "note": "法国近期大赛占优"},
        ("Germany",   "Spain"):      {"total": 25,  "W_A": 8,  "D": 6,  "W_B": 11, "note": "传控vs力量，各有胜负"},
        ("Portugal",  "Spain"):      {"total": 37,  "W_A": 18, "D": 8,  "W_B": 11, "note": "伊比利亚德比，葡萄牙总胜多"},
        ("Brazil",    "Germany"):    {"total": 23,  "W_A": 9,  "D": 5,  "W_B": 9,  "note": "2014半决赛1-7成为经典"},
        ("Argentina", "Germany"):    {"total": 20,  "W_A": 8,  "D": 4,  "W_B": 8,  "note": "3次决赛，2022马拉多纳主场夺冠"},
        ("Croatia",   "England"):    {"total": 8,   "W_A": 2,  "D": 3,  "W_B": 3,  "note": "2018世界杯半决赛，克罗地亚加时胜"},
        ("Uruguay",   "Brazil"):     {"total": 76,  "W_A": 31, "D": 18, "W_B": 27, "note": "南美最激烈对决之一"},
        ("Netherlands","Germany"):   {"total": 45,  "W_A": 14, "D": 15, "W_B": 16, "note": "欧洲老牌劲旅对抗"},
        ("Italy",     "Germany"):    {"total": 37,  "W_A": 15, "D": 13, "W_B": 9,  "note": "欧洲杯决赛多次交锋"},
        ("Spain",     "France"):      {"total": 36,  "W_A": 16, "D": 7,  "W_B": 13, "note": "2012欧洲杯决赛，西班牙大胜"},
        ("Belgium",   "France"):      {"total": 18,  "W_A": 5,  "D": 4,  "W_B": 9,  "note": "法国近期总杯赛表现更佳"},
        ("England",   "Brazil"):      {"total": 27,  "W_A": 9,  "D": 5,  "W_B": 13, "note": "2002小组赛后未在大赛相遇"},
        ("Portugal",  "Argentina"):  {"total": 7,   "W_A": 2,  "D": 1,  "W_B": 4,  "note": "2014世界杯小组赛，最近一次2018"},
    }

    # ── 战术风格描述 ────────────────────────────────────────────────
    H2H_TACTICAL = {
        ("Brazil",     "France"):     "桑巴艺术 vs 法式精密 / 边路突击 vs 中路渗透",
        ("Argentina",   "France"):     "潘帕斯激情 vs 欧洲铁军 / 梅西自由人 vs 整体压迫",
        ("Argentina",   "Brazil"):     "南美双雄巅峰对话 / 艺术流 vs 技术流",
        ("France",      "Germany"):    "个人能力 vs 整体执行 / 前场压迫 vs 快速反击",
        ("England",     "Germany"):   "边路传中 vs 德国坦克 / 速度 vs 身体对抗",
        ("Portugal",    "Spain"):      "C罗单打 vs 整体传控 / 个人英雄 vs 体系足球",
        ("Brazil",      "Germany"):   "进攻艺术 vs 纪律铁军 / 2014 1-7仍记忆犹新",
    }

    # ── 队名标准化（处理不同称呼）───────────────────────────────────
    team_name_map = {}
    for r in results:
        team_name_map[r.country] = r.country
        # 处理常见的不同称呼
        if r.country == "South Korea": team_name_map["Korea Republic"] = r.country
        if r.country == "Iran": team_name_map["IR Iran"] = r.country

    # ── 选择两支对战球队 ────────────────────────────────────────────
    col_a, col_b = st.columns(2)
    team_options = [r.country for r in results]

    with col_a:
        st.markdown("#### 🔵 Team A / 球队A")
        team_a = st.selectbox(
            "Select Team A",
            options=team_options,
            index=0,
            format_func=lambda x: f"{x} ({next(r.final_probability for r in results if r.country == x):.1%})",
            key="h2h_team_a",
        )

    with col_b:
        st.markdown("#### 🔴 Team B / 球队B")
        team_b = st.selectbox(
            "Select Team B",
            options=team_options,
            index=min(1, len(team_options) - 1),
            format_func=lambda x: f"{x} ({next(r.final_probability for r in results if r.country == x):.1%})",
            key="h2h_team_b",
        )

    if team_a == team_b:
        st.warning("⚠️ 请选择两支不同的球队 / Please select two different teams")
        st.stop()

    # ── 获取两队数据 ────────────────────────────────────────────────
    result_a = next((r for r in results if r.country == team_a), None)
    result_b = next((r for r in results if r.country == team_b), None)
    sq_a = squads.get(team_a)
    sq_b = squads.get(team_b)

    if not result_a or not result_b:
        st.error("数据缺失，请重试 / Data not available")
        st.stop()

    # ══════════════════════════════════════════════════════════════
    # 第一行：H2H 概率 + 历史交锋
    # ══════════════════════════════════════════════════════════════

    # 计算 H2H 胜率（基于 Elo 差异 + 阵容差距）
    elo_diff = (sq_a.elo if sq_a else 1700) - (sq_b.elo if sq_b else 1700)
    # Elo胜率（核心预测因子，85%权重）
    elo_prob_a = 1 / (1 + 10 ** (-elo_diff / 400))
    # 阵容深度差距（主力11人 vs 替補12-26人质量差，10%权重）
    if sq_a and sq_b:
        depth_a = sq_a.get_squad_depth()["depth_score"]
        depth_b = sq_b.get_squad_depth()["depth_score"]
        depth_diff = (depth_a - depth_b) * 0.05  # 深度优势微调
    else:
        depth_diff = 0.0
    # H2H历史记录权重压到3%以下——仅作信息注释，不作预测输入
    # （球员名单已完全不同，历史数据本质是噪音）
    h2h_constant = 0.03
    h2h_prob_a = max(0.05, min(0.95, elo_prob_a * 0.85 + depth_diff + h2h_constant))
    h2h_prob_b = 1 - h2h_prob_a
    # 平局概率（基于实力接近程度）
    draw_prob = max(0.05, min(0.30, 0.25 - abs(elo_diff) / 2000))

    row1_col1, row1_col2 = st.columns([1, 1])

    with row1_col1:
        st.markdown("#### 🎯 H2H Win Probability / 对战胜率")
        # 概率条
        bar_a = h2h_prob_a * 100
        bar_b = h2h_prob_b * 100
        st.progress(bar_a / 100, text=f"{team_a}: {bar_a:.1f}%")
        st.progress(bar_b / 100, text=f"{team_b}: {bar_b:.1f}%")

        # 详细胜平负
        col_wa, col_dr, col_wb = st.columns(3)
        col_wa.metric(f"Win / {team_a[:8]}", f"{h2h_prob_a:.1%}")
        col_dr.metric("Draw / 平局", f"{draw_prob:.1%}")
        col_wb.metric(f"Win / {team_b[:8]}", f"{h2h_prob_b:.1%}")

        # ── 历史交锋 ────────────────────────────────────────────────
        h2h_key = (team_a, team_b)
        h2h_key_rev = (team_b, team_a)
        record = H2H_RECORDS.get(h2h_key) or H2H_RECORDS.get(h2h_key_rev)

        st.markdown("##### 📜 Historical Record / 历史交锋（仅供参考）")
        st.caption("⚠️ 注：世界杯间隔4年，球员名单已大面积更迭，历史战绩仅作文化背景参考，不作为预测依据")
        if record:
            # 确认方向
            is_rev = (h2h_key_rev == list(H2H_RECORDS.keys())[[k[0] for k in H2H_RECORDS.keys()].index(team_b) if team_b in [k[0] for k in H2H_RECORDS.keys()] else 0])
            # 找一下方向
            if h2h_key in H2H_RECORDS:
                w_a, w_b = record["W_A"], record["W_B"]
                d = record["D"]
            else:
                w_a, w_b = record["W_B"], record["W_A"]
                d = record["D"]

            h2h_col1, h2h_col2, h2h_col3 = st.columns(3)
            h2h_col1.metric(f"{team_a[:8]} Wins", f"{w_a}胜")
            h2h_col2.metric("Draws / 平局", f"{d}场")
            h2h_col3.metric(f"{team_b[:8]} Wins", f"{w_b}胜")
            st.caption(f"共 {record['total']} 场 | {record['note']}")
        else:
            st.info(f"暂无 {team_a} vs {team_b} 历史交锋数据")

    with row1_col2:
        st.markdown("#### ⚖️ Factor Comparison / 因子对比")

        factors = [
            ("Elo锚点",    result_a.elo_score,      result_b.elo_score),
            ("年龄结构",   result_a.age_score,       result_b.age_score),
            ("大赛经验",   result_a.experience_score, result_b.experience_score),
            ("近期状态",   result_a.form_score,       result_b.form_score),
            ("教练因素",   result_a.coaching_score,  result_b.coaching_score),
            ("玄学因子",   result_a.mystic_score,     result_b.mystic_score),
        ]

        # 因子对比柱状图
        factor_names = [f[0] for f in factors]
        a_vals = [f[1] * 100 for f in factors]
        b_vals = [f[2] * 100 for f in factors]

        comp_df = pd.DataFrame({
            team_a: pd.Series(a_vals, index=factor_names),
            team_b: pd.Series(b_vals, index=factor_names),
        })
        st.bar_chart(comp_df, width='stretch', stack=False)

        # 每项因子胜负标注
        factor_results = []
        for name, va, vb in factors:
            winner = "◀ A" if va > vb else ("B ▶" if vb > va else "═ 平")
            factor_results.append({"Factor / 因子": name, f"A ({team_a[:6]})": f"{va:+.2f}%", f"B ({team_b[:6]})": f"{vb:+.2f}%", "Winner / 优势": winner})

        st.dataframe(
            pd.DataFrame(factor_results),
            use_container_width=True,
            hide_index=True,
        )

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # 第二行：关键球员对位 + 战术对比
    # ══════════════════════════════════════════════════════════════

    row2_col1, row2_col2 = st.columns([1, 1])

    with row2_col1:
        st.markdown("#### 👥 Key Player Matchups / 关键球员对位")

        if sq_a and sq_b:
            def get_top_by_pos(sq, pos_filter):
                return sorted(
                    [p for p in sq.players if pos_filter in p.position],
                    key=lambda p: p.calculate_player_score(),
                    reverse=True,
                )[:3]

            positions = [("GK", "Goalkeeper"), ("DF", "Defender"), ("MF", "Midfielder"), ("FW", "Forward")]
            matchup_data = []

            for pos_code, pos_name in positions:
                top_a = get_top_by_pos(sq_a, pos_code)
                top_b = get_top_by_pos(sq_b, pos_code)
                max_len = max(len(top_a), len(top_b))

                for i in range(max_len):
                    pa = top_a[i] if i < len(top_a) else None
                    pb = top_b[i] if i < len(top_b) else None

                    score_a = pa.calculate_player_score() if pa else 0
                    score_b = pb.calculate_player_score() if pb else 0
                    winner_tag = ""
                    if pa and pb:
                        winner_tag = "◀ A" if score_a > score_b else ("B ▶" if score_b > score_a else "═")

                    matchup_data.append({
                        "Position": pos_name,
                        team_a[:10]: f"{pa.name if pa else '—'} ({score_a:.0f})" if pa else "—",
                        "": winner_tag,
                        team_b[:10]: f"{pb.name if pb else '—'} ({score_b:.0f})" if pb else "—",
                    })

            st.dataframe(
                pd.DataFrame(matchup_data),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "": st.column_config.TextColumn(width="small"),
                },
            )
        else:
            st.warning("阵容数据缺失 / Squad data unavailable")

    with row2_col2:
        st.markdown("#### 🎯 Tactical Comparison / 战术对比")

        # 阵容成熟度对比
        if sq_a and sq_b:
            ages_a = [p.age for p in sq_a.players]
            ages_b = [p.age for p in sq_b.players]
            avg_a = sum(ages_a) / len(ages_a)
            avg_b = sum(ages_b) / len(ages_b)
            exp_a = sum(1 for p in sq_a.players if p.national_caps >= 30)
            exp_b = sum(1 for p in sq_b.players if p.national_caps >= 30)

            tac_col1, tac_col2 = st.columns(2)
            tac_col1.metric("Avg Age / 平均年龄", f"{team_a[:8]}: {avg_a:.1f}岁", delta=f"{'偏老' if avg_a > 29 else ('黄金' if 26 <= avg_a <= 29 else '偏年轻')}")
            tac_col2.metric("Avg Age / 平均年龄", f"{team_b[:8]}: {avg_b:.1f}岁", delta=f"{'偏老' if avg_b > 29 else ('黄金' if 26 <= avg_b <= 29 else '偏年轻')}")
            tac_col1.metric("Experienced / 老将(30+)", f"{team_a[:8]}: {exp_a}人")
            tac_col2.metric("Experienced / 老将(30+)", f"{team_b[:8]}: {exp_b}人")

            # 阵容深度对比
            depth_a = len(sq_a.players)
            depth_b = len(sq_b.players)
            tac_col1.metric("Squad Size / 阵容人数", f"{team_a[:8]}: {depth_a}人")
            tac_col2.metric("Squad Size / 阵容人数", f"{team_b[:8]}: {depth_b}人")

            # 战术兼容提示
            st.markdown("##### 💡 Tactical Insight / 战术洞察")
            tactical = H2H_TACTICAL.get(h2h_key) or H2H_TACTICAL.get(h2h_key_rev) or "两队风格对比暂无详细数据"
            st.info(tactical)

            # 综合分析
            advantages = []
            if avg_a < avg_b - 1:
                advantages.append(f"{team_a}更年轻，体力充沛")
            if avg_b < avg_a - 1:
                advantages.append(f"{team_b}更年轻，体力充沛")
            if exp_a > exp_b + 2:
                advantages.append(f"{team_a}大赛经验丰富")
            if exp_b > exp_a + 2:
                advantages.append(f"{team_b}大赛经验丰富")
            if result_a.final_probability > result_b.final_probability * 1.3:
                advantages.append(f"{team_a}整体纸面实力更强")

            if advantages:
                st.success("**优势分析：**\n" + "\n".join(f"• {a}" for a in advantages))
        else:
            st.warning("战术数据缺失 / Tactical data unavailable")

    st.divider()

    # ══════════════════════════════════════════════════════════════
    # 第三行：Narrative H2H 报告
    # ══════════════════════════════════════════════════════════════

    st.markdown("#### 📝 H2H Analysis Report / 对战分析报告")

    # 生成简短分析文字
    prob_a_pct = h2h_prob_a * 100
    prob_b_pct = h2h_prob_b * 100
    elo_gap = abs(elo_diff)

    if prob_a_pct > 60:
        favorite_a = f"{team_a}明显占优"
    elif prob_b_pct > 60:
        favorite_a = f"{team_b}明显占优"
    else:
        favorite_a = "两队势均力敌"

    if elo_gap < 50:
        elo_comment = "Elo实力极为接近，任何结果都可能"
    elif elo_diff > 0:
        elo_comment = f"{team_a}在Elo评分上领先{elo_gap:.0f}分"
    else:
        elo_comment = f"{team_b}在Elo评分上领先{elo_gap:.0f}分"

    narrative_parts = [
        f"**总评：** {favorite_a}，{elo_comment}。",
    ]

    if record:
        if h2h_key in H2H_RECORDS:
            w_ratio_a = record["W_A"] / max(1, record["total"])
            w_ratio_b = record["W_B"] / max(1, record["total"])
        else:
            w_ratio_a = record["W_B"] / max(1, record["total"])
            w_ratio_b = record["W_A"] / max(1, record["total"])

        if w_ratio_a > w_ratio_b + 0.1:
            narrative_parts.append(f"历史交锋中{team_a}占优（{record['note']}）。")
        elif w_ratio_b > w_ratio_a + 0.1:
            narrative_parts.append(f"历史交锋中{team_b}占优（{record['note']}）。")
        else:
            narrative_parts.append(f"历史交锋记录接近（{record['note']}）。")

    if sq_a and sq_b:
        if avg_a < 26 and avg_b > 29:
            narrative_parts.append(f"{team_a}阵容年轻，面对老练的{team_b}可能以体能和冲劲取胜。")
        elif avg_b < 26 and avg_a > 29:
            narrative_parts.append(f"{team_b}阵容年轻，面对老练的{team_a}可能以体能和冲劲取胜。")

    narrative_parts.append(f"综合评估：{team_a}胜率{prob_a_pct:.0f}% | 平局{draw_prob*100:.0f}% | {team_b}胜率{prob_b_pct:.0f}%")

    st.markdown(" ".join(narrative_parts))

    st.caption(
        f"H2H Analysis | {team_a} vs {team_b} | "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
