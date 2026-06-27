"""
Feature Attribution — 因子贡献归因分析

将每支球队的冠军概率分解为各因子的绝对贡献，
以标准相加模型（Additive Attribution）计算每个因子对最终概率的贡献。

核心方法：Counterfactual Attribution
对于每个因子 f：
  1. 计算 baseline 概率（只用 Elo，不加任何因子加成）
  2. 逐步加入每个因子，观察概率变化
  3. 将概率变化的差值归因到该因子

更精确的方法：SHAP-style additive feature attribution
  φ_f = Σ (impact_of_f_being_present / num_factors)

本实现采用简化的 Counterfactual Chain：
  P_final = P(Elo) + Δ_age + Δ_exp + Δ_form + Δ_coaching + Δ_mystic + Δ calibration

每个 Δ 是因子相对于 Elo-only baseline 的独立贡献。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional
import math


@dataclass
class FactorAttribution:
    """单个因子的贡献归因"""
    factor_name: str        # 'elo', 'age', 'exp', 'form', 'coaching', 'mystic', 'calibration'
    factor_label: str       # 中文显示名
    contribution: float    # 对概率的绝对贡献（可正可负）
    contribution_pct: float  # 贡献占总变化的百分比
    explanation: str       # 解释性文字

    def to_dict(self) -> Dict:
        return {
            "factor": self.factor_name,
            "label": self.factor_label,
            "contribution": round(self.contribution, 4),
            "contribution_pct": round(self.contribution_pct, 2),
            "explanation": self.explanation,
        }


@dataclass
class TeamAttribution:
    """整支球队的因子归因结果"""
    country: str
    final_probability: float
    elo_baseline: float     # 只有 Elo 时的基准概率
    total_adjustment: float  # 所有因子带来的总调整量
    attributions: List[FactorAttribution]

    def to_dict(self) -> Dict:
        return {
            "country": self.country,
            "final_probability": round(self.final_probability, 4),
            "elo_baseline": round(self.elo_baseline, 4),
            "total_adjustment": round(self.total_adjustment, 4),
            "attributions": [a.to_dict() for a in self.attributions],
        }


class FeatureAttributor:
    """
    因子贡献归因分析器。

    方法：Counterfactual Chain
    将最终概率分解为：
      P_final = P_elo + Δ_age + Δ_exp + Δ_form + Δ_coaching + Δ_mystic + Δ_calibration

    其中每个 Δ 是该因子相对于 Elo-only baseline 的独立贡献。
    归一化后各因子贡献之和 = 总调整量。
    """

    # 因子中文名映射
    FACTOR_LABELS = {
        "elo": "Elo锚点",
        "age": "年龄结构",
        "exp": "大赛经验",
        "form": "近期状态",
        "coaching": "教练因素",
        "mystic": "玄学因子",
        "calibration": "历史校准",
    }

    # 因子权重（用于归因计算，与 ModelWeights 一致）
    DEFAULT_WEIGHTS = {
        "elo": 0.30,
        "age": 0.20,
        "exp": 0.25,
        "form": 0.15,
        "coaching": 0.10,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS

    def _elo_to_prob(self, elo: float) -> float:
        """将 Elo 转换为冠军概率（与 team_scoring.py 逻辑一致）"""
        K = 300.0
        C = 2.05e-4
        p = C * math.exp(elo / K)
        return max(0.0001, min(0.20, p))

    def attribute_team(self,
                      elo: float,
                      age_score: float,
                      exp_score: float,
                      form_score: float,
                      coaching_score: float,
                      mystic_score: float,
                      final_probability: float,
                      country: str = "",
                      has_wc_history: bool = False) -> TeamAttribution:
        """
        对单支球队进行因子归因。

        因子分数说明（来自 team_scoring.py）：
          age_score:      -0.06 ~ +0.08   （相对于 Elo 的 % 调整）
          exp_score:      -0.02 ~ +0.10   （大赛经验加成）
          form_score:     -0.05 ~ +0.05   （近期状态）
          coaching_score: -0.05 ~ +0.05   （教练因素）
          mystic_score:   -0.10 ~ +0.15   （玄学因子）

        ELO_POINTS_PER_MOD = 3000：每+1% mod = +3000 Elo点
        Elo每+100点约胜率+10%，但映射到概率是非线性的（logistic）
        """

        # 1. Elo-only 基准概率
        elo_baseline = self._elo_to_prob(elo)

        # 2. 各因子的 Elo 等效贡献（转换为概率单位）
        # 年龄结构
        age_elo_delta = age_score * 3000  # 年龄因子对应的 Elo 调整
        age_prob_delta = self._elo_to_prob(elo + age_elo_delta) - elo_baseline

        # 大赛经验
        exp_elo_delta = exp_score * 3000
        exp_prob_delta = self._elo_to_prob(elo + exp_elo_delta) - elo_baseline

        # 近期状态
        form_elo_delta = form_score * 3000
        form_prob_delta = self._elo_to_prob(elo + form_elo_delta) - elo_baseline

        # 教练因素
        coaching_elo_delta = coaching_score * 3000
        coaching_prob_delta = self._elo_to_prob(elo + coaching_elo_delta) - elo_baseline

        # 玄学因子（已经是概率量级，直接用）
        mystic_prob_delta = mystic_score * 0.01  # mystic_score 是 ±0.1 量级

        # 历史校准调整（没有 Elo 代理，直接取残差）
        # final = elo_baseline + sum(all_factor_prob_deltas) + calibration + residual
        sum_delta = age_prob_delta + exp_prob_delta + form_prob_delta + coaching_prob_delta + mystic_prob_delta
        calibration_prob_delta = final_probability - elo_baseline - sum_delta

        # 限制校准项在合理范围
        calibration_prob_delta = max(-0.05, min(0.05, calibration_prob_delta))

        # 3. 收集所有归因项
        raw_attributions = [
            ("age", age_prob_delta, "年龄结构影响球队成熟度和稳定性"),
            ("exp", exp_prob_delta, "大赛经验决定淘汰赛抗压能力"),
            ("form", form_prob_delta, "近期状态反映球队当前竞技水平"),
            ("coaching", coaching_prob_delta, "教练战术水平和大赛指挥能力"),
            ("mystic", mystic_prob_delta, "玄学因子：主场/卫冕/易经/道德经等"),
            ("calibration", calibration_prob_delta, "历史校准：2026年世界杯特定调整"),
        ]

        # 过滤掉贡献过小的项（<0.001）
        significant_attributions = [(f, d) for f, d, _ in raw_attributions if abs(d) > 0.001]

        # 4. 归一化：确保所有归因之和 = total_adjustment
        total_adjustment = final_probability - elo_baseline
        total_raw = sum(d for _, d in significant_attributions)

        attributions = []
        for factor_name, raw_delta in significant_attributions:
            # 归一化：按比例分配
            if total_raw != 0:
                normalized_delta = raw_delta * (total_adjustment / total_raw)
            else:
                normalized_delta = 0.0

            pct = (normalized_delta / abs(total_adjustment) * 100) if total_adjustment != 0 else 0

            # 生成解释
            label = self.FACTOR_LABELS[factor_name]
            if normalized_delta > 0.001:
                direction = "正向贡献"
                detail = self._get_factor_detail(factor_name, normalized_delta)
            elif normalized_delta < -0.001:
                direction = "负向拖累"
                detail = self._get_factor_detail(factor_name, normalized_delta)
            else:
                direction = "中性"
                detail = "对概率无显著影响"

            explanation = f"{label} {direction} {detail}"

            attributions.append(FactorAttribution(
                factor_name=factor_name,
                factor_label=label,
                contribution=normalized_delta,
                contribution_pct=pct,
                explanation=explanation,
            ))

        # 按 |contribution| 降序排列
        attributions.sort(key=lambda a: abs(a.contribution), reverse=True)

        return TeamAttribution(
            country=country,
            final_probability=final_probability,
            elo_baseline=elo_baseline,
            total_adjustment=total_adjustment,
            attributions=attributions,
        )

    def _get_factor_detail(self, factor: str, delta: float) -> str:
        """生成因子贡献的详细说明"""
        delta_pct = delta * 100  # 转换为百分比
        sign = "+" if delta > 0 else ""

        if factor == "age":
            if delta > 0:
                return f"阵容年龄结构优秀({sign}{delta_pct:.2f}%)"
            else:
                return f"年龄结构偏年轻或偏老({sign}{delta_pct:.2f}%)"
        elif factor == "exp":
            if delta > 0:
                return f"有丰富的大赛淘汰赛经验({sign}{delta_pct:.2f}%)"
            else:
                return f"缺乏顶级大赛正赛经验({sign}{delta_pct:.2f}%)"
        elif factor == "form":
            if delta > 0:
                return f"近期胜率高，状态出色({sign}{delta_pct:.2f}%)"
            else:
                return f"近期战绩一般，状态低迷({sign}{delta_pct:.2f}%)"
        elif factor == "coaching":
            if delta > 0:
                return f"教练经验丰富，战术素养高({sign}{delta_pct:.2f}%)"
            else:
                return f"教练执教能力有待验证({sign}{delta_pct:.2f}%)"
        elif factor == "mystic":
            if delta > 0:
                return f"受主场/新星/易经等正向玄学加持({sign}{delta_pct:.2f}%)"
            else:
                return f"受热门诅咒等负向玄学影响({sign}{delta_pct:.2f}%)"
        elif factor == "calibration":
            if delta > 0:
                return f"历史数据和2026特定调整正向({sign}{delta_pct:.2f}%)"
            else:
                return f"历史数据和2026特定调整负向({sign}{delta_pct:.2f}%)"
        return f"({sign}{delta_pct:.2f}%)"


def attribute_all_teams(team_results: List[Dict]) -> List[Dict]:
    """
    对所有球队运行因子归因，返回可序列化的结果。
    team_results: 来自 score_all_teams() 的结果序列化版本
    """
    attributor = FeatureAttributor()
    results = []

    for t in team_results:
        # 从原始数据字典提取各因子分数
        elo = t.get("elo", 1700)
        age_score = t.get("age_score", 0)
        exp_score = t.get("exp_score", 0)
        form_score = t.get("form_score", 0)
        coaching_score = t.get("coaching_score", 0)
        mystic_score = t.get("mystic_score", 0)
        final_prob = t.get("final_prob", t.get("final_probability", 0.03))
        country = t.get("country", "Unknown")

        attr = attributor.attribute_team(
            elo=elo,
            age_score=age_score,
            exp_score=exp_score,
            form_score=form_score,
            coaching_score=coaching_score,
            mystic_score=mystic_score,
            final_probability=final_prob,
            country=country,
        )
        results.append(attr.to_dict())

    return results
