"""
球员评分模型 — 核心：4年周期模型
假设：球员在世界杯的表现，与其职业年龄高度相关
  22-25岁：第一次巅峰，可能首发但不稳定
  25-28岁：黄金期，大赛经验积累中
  28-31岁：最可靠输出
  31-34岁：经验丰富但体能下滑
  34岁+：角色球员/替补奇兵
"""

from dataclasses import dataclass
from typing import Optional, List
from config import AgePeakConfig, PositionWeights

@dataclass
class Player:
    """球员数据结构"""
    name: str
    age: int
    position: str  # GK/CB/FB/DM/CM/AM/WING/ST
    club: str
    market_value: float  # 百万欧元
    national_goals: int = 0
    national_caps: int = 0
    tournaments: List[str] = None  # 参加过的世界杯 ['2018', '2022']

    def __post_init__(self):
        if self.tournaments is None:
            self.tournaments = []

    @property
    def is_first_tournament(self) -> bool:
        return len(self.tournaments) == 0

    @property
    def experience_score(self) -> float:
        """大赛经验评分"""
        n = len(self.tournaments)
        if n >= 2:
            return 0.9
        elif n == 1:
            return 0.6
        else:
            return 0.2  # 首次参赛

    def get_peak_score(self) -> float:
        """获取年龄峰值分数"""
        config = AgePeakConfig()
        return config.get_peak_score(
            self.age,
            is_first_tournament=self.is_first_tournament
        )

    def get_position_weight(self) -> float:
        """获取位置权重"""
        weights = PositionWeights()
        pos_map = {
            'GK': weights.goalkeeper,
            'CB': weights.centre_back,
            'FB': weights.full_back,
            'LB': weights.full_back,
            'RB': weights.full_back,
            'DM': weights.defensive_midfielder,
            'CM': weights.central_midfielder,
            'CAM': weights.attacking_midfielder,
            'AM': weights.attacking_midfielder,
            'WING': weights.winger,
            'LW': weights.winger,
            'RW': weights.winger,
            'ST': weights.striker,
            'CF': weights.striker,
        }
        return pos_map.get(self.position.upper(), 1.0)

    def calculate_player_score(self) -> float:
        """
        计算球员综合评分（0-100）
        = 年龄峰值 × 位置权重 × 经验系数
        """
        peak = self.get_peak_score()
        pos_weight = self.get_position_weight()
        exp = self.experience_score

        # 位置权重调整：0.8 - 1.5
        pos_factor = 0.8 + (pos_weight - 1.0) * 0.4

        # 综合评分
        raw_score = peak * pos_factor * (0.7 + 0.3 * exp)

        # 市场价值归一化（作为微调）
        # 1亿欧以上额外+2分封顶
        mv_bonus = min(2.0, self.market_value / 50)

        final = min(100, raw_score * 100 + mv_bonus)
        return round(final, 1)

    def get_age_bucket(self) -> str:
        """获取年龄区间标签"""
        if self.age < 22:
            return "新星"
        elif self.age < 25:
            return "新锐"
        elif self.age < 28:
            return "黄金"
        elif self.age < 31:
            return "巅峰"
        elif self.age < 34:
            return "老将"
        else:
            return "元老"


@dataclass
class Squad:
    """球队阵容"""
    country: str
    players: List[Player]
    elo: float = 1500.0  # FiveThirtyEight SPI评分
    recent_win_rate: float = 0.5  # 近18个月胜率
    coaching_factor: float = 0.5  # 教练因素 0-1
    tournament_history: List[str] = None  # 往届世界杯成绩

    def __post_init__(self):
        if self.tournament_history is None:
            self.tournament_history = []

    def get_squad_maturity_index(self) -> float:
        """
        阵容成熟度指数
        基于主力年龄中位数 + 黄金期球员占比
        """
        if not self.players:
            return 0.0

        ages = [p.age for p in self.players]
        median_age = sorted(ages)[len(ages) // 2]

        # 年龄中位数评分（27-29岁最优）
        if 27 <= median_age <= 29:
            age_score = 1.0
        elif 25 <= median_age < 27 or 29 < median_age <= 31:
            age_score = 0.8
        elif 23 <= median_age < 25 or 31 < median_age <= 33:
            age_score = 0.5
        else:
            age_score = 0.2

        # 黄金期球员占比（25-31岁）
        prime_count = sum(1 for p in self.players if 25 <= p.age <= 31)
        prime_ratio = prime_count / len(self.players)

        # 成熟度指数
        maturity = 0.6 * age_score + 0.4 * prime_ratio
        return round(maturity, 3)

    def get_avg_player_score(self) -> float:
        """阵容平均球员评分"""
        if not self.players:
            return 0.0
        return sum(p.calculate_player_score() for p in self.players) / len(self.players)

    def get_squad_depth(self) -> dict:
        """
        阵容深度指标。
        主力11人 vs 替補12-26人的平均评分差距。
        差距越小 → 阵容深度越好（淘汰赛换人后实力不跌）
        差距越大 → 深度越差（换人即战力下滑）
        Returns: dict with avg_starting, avg_bench, gap, depth_score (0-1, 越大越深)
        """
        if not self.players or len(self.players) < 12:
            return {"avg_starting": 0.0, "avg_bench": 0.0, "gap": 0.0, "depth_score": 0.0}

        sorted_players = sorted(self.players, key=lambda p: p.calculate_player_score(), reverse=True)
        starting = sorted_players[:11]
        bench = sorted_players[11:26]  # 12-26人

        avg_starting = sum(p.calculate_player_score() for p in starting) / len(starting)
        avg_bench = sum(p.calculate_player_score() for p in bench) / len(bench) if bench else 0.0
        gap = avg_starting - avg_bench

        # 深度评分：gap越小分数越高，gap=0时=1.0，gap≥20时=0
        # bench为0说明阵容只有先发，深度极差
        if not bench:
            depth_score = 0.0
        else:
            depth_score = max(0.0, min(1.0, 1.0 - gap / 20.0))

        return {
            "avg_starting": round(avg_starting, 1),
            "avg_bench": round(avg_bench, 1),
            "gap": round(gap, 1),
            "depth_score": round(depth_score, 3),
        }

    def get_age_distribution(self) -> dict:
        """年龄分布统计"""
        buckets = {"新星": 0, "新锐": 0, "黄金": 0, "巅峰": 0, "老将": 0, "元老": 0}
        for p in self.players:
            buckets[p.get_age_bucket()] += 1
        return buckets


def build_squad_from_data(country: str, players_data: List[dict], elo: float) -> Squad:
    """
    从原始数据构建Squad对象
    players_data: List[dict] with keys: name, age, position, club, market_value
    Wikipedia数据用 caps/goals，需兼容 national_caps/national_goals
    """
    players = []
    for d in players_data:
        # 清理位置字段（Wikipedia格式 "1GK" → "GK", "2DF" → "DF"）
        raw_pos = d.get('position', 'CM')
        import re
        pos_clean = re.sub(r'^\d+', '', raw_pos).strip()

        p = Player(
            name=d['name'],
            age=d['age'],
            position=pos_clean,
            club=d.get('club', ''),
            market_value=d.get('market_value', 10.0),
            # Wikipedia用 caps/goals；其他来源可能用 national_caps/national_goals
            national_goals=d.get('goals', d.get('national_goals', 0)),
            national_caps=d.get('caps', d.get('national_caps', 0)),
            tournaments=d.get('tournaments', []),
        )
        players.append(p)

    return Squad(
        country=country,
        players=players,
        elo=elo,
    )
