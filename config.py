"""
World Cup Champion Predictor — Configuration
用户可在此调整各因子的权重，以及玄学因子的模式
"""

from dataclasses import dataclass, field
from typing import Dict

# ==================== 模型权重配置 ====================

@dataclass
class ModelWeights:
    """各因子权重配置 — 可手动调整"""
    elo: float = 0.30          # Elo评分锚点（从0.35下调，让经验因素更大）
    age_structure: float = 0.20 # 年龄结构
    tournament_exp: float = 0.25 # 大赛经验（从0.15上调，区分预选赛型和淘汰赛型）
    recent_form: float = 0.15   # 近期状态
    coaching: float = 0.10     # 教练因素
    mystic: float = 0.05       # 玄学因子

# ==================== 玄学因子模式 ====================

@dataclass
class MysticConfig:
    """玄学因子配置"""
    mode: str = "conservative"  # conservative | aggressive | mystical
    # 强势方诅咒 — 夺冠热门往往承受更大心理压力
    favorite_curse: float = -0.05
    # 主场/美洲buff — 2026美洲举办
    host_advantage: float = 0.08
    # 新星崛起buff — 年轻球队打破旧秩序
    new_force_bonus: float = 0.06
    # 运气成分 — 不可预测的上限
    luck_ceiling: float = 0.10

MYSTIC_CONFIGS: Dict[str, MysticConfig] = {
    "conservative": MysticConfig(
        mode="conservative",
        favorite_curse=-0.03,
        host_advantage=0.05,
        new_force_bonus=0.04,
        luck_ceiling=0.05,
    ),
    "aggressive": MysticConfig(
        mode="aggressive",
        favorite_curse=-0.08,
        host_advantage=0.12,
        new_force_bonus=0.10,
        luck_ceiling=0.15,
    ),
    "mystical": MysticConfig(
        mode="mystical",
        favorite_curse=-0.10,
        host_advantage=0.15,
        new_force_bonus=0.15,
        luck_ceiling=0.25,  # 玄学模式：运气成分最大化
    ),
}

# ==================== 年龄峰值配置 ====================

@dataclass
class AgePeakConfig:
    """球员年龄峰值配置"""
    # 年龄 → 峰值系数（0-1）
    # 22以下：潜力股，稳定性低
    # 22-25：上升期
    # 25-28：黄金期
    # 28-31：巅峰尾巴
    # 31-34：经验老将
    # 34+：替补/角色球员

    def get_peak_score(self, age: int, is_first_tournament: bool = False) -> float:
        if age < 18:
            return 0.1
        elif age < 22:
            base = 0.3 + (age - 18) * 0.05
            return base if not is_first_tournament else base * 0.7  # 首次参赛打折
        elif age < 25:
            return 0.6 + (age - 22) * 0.10
        elif age < 28:
            return 0.9 + (age - 25) * 0.03  # 黄金期，微涨
        elif age < 31:
            return 0.95 - (age - 28) * 0.05  # 缓慢下滑
        elif age < 34:
            return 0.75 - (age - 31) * 0.05
        elif age < 38:
            return max(0.4, 0.60 - (age - 34) * 0.07)
        else:
            return max(0.15, 0.50 - (age - 38) * 0.05)

# ==================== 位置权重 ====================

@dataclass
class PositionWeights:
    """各位置对球队成绩的影响权重"""
    goalkeeper: float = 1.0
    centre_back: float = 1.0
    full_back: float = 0.9
    defensive_midfielder: float = 1.1
    central_midfielder: float = 1.2
    attacking_midfielder: float = 1.3
    winger: float = 1.2
    striker: float = 1.5  # 进球最重要

POSITION_WEIGHTS = PositionWeights()

# ==================== 大赛经验配置 ====================

@dataclass
class ExperienceConfig:
    """大赛经验系数（缩小量级，防止因子膨胀Elo）
    
    2026-05-30 校准：加大决赛/四强档差距，使有淘汰赛历史成就的球队
    （西班牙、葡萄牙）能压过预选赛型高ELO球队（瑞士、哥伦比亚）。
    """
    world_cup_finals: float = 0.06   # 上届进入决赛（+6%，从0.03上调）
    world_cup_semi: float = 0.04     # 上届进入四强（+4%，从0.02上调）
    world_cup_quarter: float = 0.02  # 上届进入八强（+2%，从0.01上调）
    world_cup_group: float = 0.005   # 仅参加小组赛
    euro_copa_win: float = 0.05      # 近年获得欧洲杯/美洲杯（+5%，从0.03上调）
    no_experience: float = 0.0       # 首次参赛

# ==================== 默认球队数据 ====================

# 2026世界杯已知参赛队（截至2026年3月已确认）
# 这是示例数据，实际运行时会从数据源获取
QUALIFIED_TEAMS = [
    "Argentina", "Brazil", "France", "Germany", "Spain",
    "England", "Portugal", "Netherlands", "Italy", "Belgium",
    "Croatia", "Uruguay", "Mexico", "USA", "Canada",
    "Japan", "South Korea", "Iran", "Saudi Arabia", "Australia",
    "Morocco", "Senegal", "Cameroon", "Ghana", "Algeria",
    # ... 32队完整名单待预选赛结束后更新
]

# 种子队（基于近年表现，预计）
SEED_TEAMS = [
    "Brazil", "Argentina", "France", "England", "Spain",
    "Germany", "Portugal", "Netherlands", "Italy", "Belgium",
]
