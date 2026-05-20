"""
蒙特卡洛模拟 — 模拟32队晋级路径，计算冠军概率

方法：
1. 读取每支球队的评分
2. 模拟10000次世界杯（考虑小组赛→淘汰赛结构）
3. 统计每支球队赢得冠军的次数
4. 归一化为概率
"""

from typing import List, Dict, Tuple
import random
from dataclasses import dataclass
# TeamResult imported inside run_full_simulation to avoid circular import

@dataclass
class SimulationConfig:
    """模拟配置"""
    n_simulations: int = 10000
    knockout_randomness: float = 0.15  # 淘汰赛随机性因子
    group_randomness: float = 0.08    # 小组赛随机性因子

class MonteCarloSimulator:
    """
    蒙特卡洛世界杯模拟器

    模拟逻辑：
    - 小组赛：6组×4队，前2名出线（用评分模拟胜平负）
    - 1/8决赛：16队→8队
    - 1/4决赛：8队→4队
    - 半决赛：4队→2队
    - 决赛：2队→1队冠军
    """

    GROUP_A = ["USA", "Canada", "Mexico", "Morocco"]
    GROUP_B = ["Brazil", "France", "Germany", "Japan"]
    # ... 其他组（简化处理，实际运行从数据源读取）

    def __init__(self, config: SimulationConfig = None):
        self.config = config or SimulationConfig()

    def simulate_match(self, team_a: str, team_b: str,
                       elo_a: float, elo_b: float,
                       is_knockout: bool = False) -> str:
        """
        模拟单场比赛
        返回获胜球队名称
        """
        randomness = (
            self.config.knockout_randomness
            if is_knockout
            else self.config.group_randomness
        )

        # Elo差值转换为获胜概率
        elo_diff = elo_a - elo_b
        # 假设Elo差100分，获胜概率约60%
        prob_a = 0.5 + (elo_diff / 1000)

        # 加入随机性
        adjusted_prob = prob_a + random.uniform(-randomness, randomness)
        adjusted_prob = max(0.05, min(0.95, adjusted_prob))

        return team_a if random.random() < adjusted_prob else team_b

    def simulate_group_stage(self, teams: List[str], elos: Dict[str, float],
                             results: Dict[str, float]) -> List[str]:
        """
        模拟小组赛，返回出线球队列表（每组前2名）
        """
        standings = {t: 0 for t in teams}

        # 每组4队，互相比赛3场
        for i, t1 in enumerate(teams):
            for j, t2 in enumerate(teams):
                if i >= j:
                    continue

                winner = self.simulate_match(
                    t1, t2,
                    elos.get(t1, 1500),
                    elos.get(t2, 1500),
                    is_knockout=False
                )

                # 3分制
                if winner == t1:
                    standings[t1] += 3
                elif winner == t2:
                    standings[t2] += 3
                else:
                    # 平局（实际模拟可能产生平局，这里简化处理）
                    standings[t1] += 1
                    standings[t2] += 1

        # 排序，取前2名
        sorted_teams = sorted(standings.items(), key=lambda x: x[1], reverse=True)
        return [t[0] for t in sorted_teams[:2]]

    def simulate_tournament(self, teams: List[str],
                            elos: Dict[str, float]) -> str:
        """
        模拟完整世界杯，返回冠军球队
        """
        if len(teams) != 32:
            raise ValueError(f"需要32支球队，当前{len(teams)}支")

        # 小组赛（简化版：直接用Elo排序，每组前2名出线）
        # 实际应按组划分，这里简化为直接使用预定义结果
        qualified = self._get_group_qualifiers(elos)

        # 1/8决赛
        round_of_16 = []
        for i in range(0, 16, 2):
            winner = self.simulate_match(
                qualified[i], qualified[i+1],
                elos.get(qualified[i], 1500),
                elos.get(qualified[i+1], 1500),
                is_knockout=True
            )
            round_of_16.append(winner)

        # 1/4决赛
        quarter_finals = []
        for i in range(0, 8, 2):
            winner = self.simulate_match(
                round_of_16[i], round_of_16[i+1],
                elos.get(round_of_16[i], 1500),
                elos.get(round_of_16[i+1], 1500),
                is_knockout=True
            )
            quarter_finals.append(winner)

        # 半决赛
        semi_finals = []
        for i in range(0, 4, 2):
            winner = self.simulate_match(
                quarter_finals[i], quarter_finals[i+1],
                elos.get(quarter_finals[i], 1500),
                elos.get(quarter_finals[i+1], 1500),
                is_knockout=True
            )
            semi_finals.append(winner)

        # 决赛
        champion = self.simulate_match(
            semi_finals[0], semi_finals[1],
            elos.get(semi_finals[0], 1500),
            elos.get(semi_finals[1], 1500),
            is_knockout=True
        )

        return champion

    def _get_group_qualifiers(self, elos: Dict[str, float]) -> List[str]:
        """
        基于Elo确定小组赛出线球队
        （简化处理，实际应按真实分组）
        """
        sorted_teams = sorted(elos.items(), key=lambda x: x[1], reverse=True)

        # 前16名进入上半区，后16名进入下半区
        # 每组4队，组内Elo相近者分组
        groups = {}
        top_half = [t[0] for t in sorted_teams[:16]]
        bottom_half = [t[0] for t in sorted_teams[16:]]

        # 蛇形分配到8个组
        for i, team in enumerate(top_half):
            group_id = i % 8
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append(team)

        for i, team in enumerate(bottom_half):
            group_id = i % 8
            if group_id not in groups:
                groups[group_id] = []
            groups[group_id].append(team)

        # 每组前2名出线
        qualified = []
        for g in range(8):
            if g in groups:
                # 按Elo排序
                group_teams = sorted(
                    groups[g],
                    key=lambda t: elos.get(t, 1500),
                    reverse=True
                )
                qualified.extend(group_teams[:2])

        return qualified

    def run_simulation(self, teams: List[str],
                       elos: Dict[str, float]) -> Dict[str, int]:
        """
        运行n次模拟，返回每支球队获胜次数
        """
        wins = {t: 0 for t in teams}

        for _ in range(self.config.n_simulations):
            champion = self.simulate_tournament(teams, elos)
            wins[champion] += 1

        return wins

    def get_probabilities(self, wins: Dict[str, int],
                          n_simulations: int) -> Dict[str, float]:
        """
        将获胜次数转换为概率
        """
        return {
            team: count / n_simulations
            for team, count in wins.items()
        }


def run_full_simulation(teams: List[str],
                        elos: Dict[str, float],
                        n_simulations: int = 10000) -> Tuple[Dict[str, float], List[str]]:
    """
    完整运行接口：模拟→概率→排序
    返回：(概率字典, 冠军排行榜)
    """
    from ..models.team_scoring import TeamResult  # avoid circular import

    config = SimulationConfig(n_simulations=n_simulations)
    simulator = MonteCarloSimulator(config)

    wins = simulator.run_simulation(teams, elos)
    probs = simulator.get_probabilities(wins, n_simulations)

    # 排序
    ranking = sorted(probs.items(), key=lambda x: x[1], reverse=True)

    return probs, [t[0] for t in ranking]
