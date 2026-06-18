"""
ELO Auto-Update Script — 根据已完成比赛结果更新ELO评分

ELO公式:
  E = 1 / (1 + 10^((elo_b - elo_a) / 400))
  new_elo = elo + K * (actual - expected)
  K = 32 (世界杯级别国家队)
  actual = 1 for win, 0.5 for draw, 0 for loss
  变化量限制: max ±50 per match (防止极端波动)

用法:
    python scripts/update_elo_from_results.py

此脚本是幂等的 — 运行两次不会重复更新，
因为只有新完成的比赛（之前未被处理过）才会被应用。
"""

import os
import json
from typing import Dict, List, Tuple, Optional

# ── 路径配置 ──────────────────────────────────────────────────────────────
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MATCH_CACHE = os.path.join(ROOT, "data", "match_cache.json")
ELO_CACHE = os.path.join(ROOT, "data", "elo_cache_2026.json")
PROCESSED_MARKER = os.path.join(ROOT, "data", "elo_updates_processed.json")

# ── ELO常量 ────────────────────────────────────────────────────────────────
K_FACTOR = 32
MAX_ELO_CHANGE = 50.0
DEFAULT_ELO = 1650.0


def calculate_expected(elo_a: float, elo_b: float) -> float:
    """
    计算team_a的期望得分（基于ELO等级分公式）
    E_a = 1 / (1 + 10^((elo_b - elo_a) / 400))
    """
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


def get_actual_score(score_a: int, score_b: int) -> Tuple[float, float]:
    """
    根据比分返回actual得分
    actual_a = 1 for win, 0.5 for draw, 0 for loss
    """
    if score_a > score_b:
        return 1.0, 0.0
    elif score_a < score_b:
        return 0.0, 1.0
    else:
        return 0.5, 0.5


def clamp_elo_change(delta: float) -> float:
    """限制ELO单次变化量，防止极端波动"""
    if delta > MAX_ELO_CHANGE:
        return MAX_ELO_CHANGE
    elif delta < -MAX_ELO_CHANGE:
        return -MAX_ELO_CHANGE
    return delta


def update_elo_for_match(
    elo_a: float,
    elo_b: float,
    score_a: int,
    score_b: int
) -> Tuple[float, float]:
    """
    根据比赛结果更新两队ELO评分
    
    Args:
        elo_a: team_a当前ELO
        elo_b: team_b当前ELO
        score_a: team_a进球数
        score_b: team_b进球数
    
    Returns:
        (new_elo_a, new_elo_b)
    """
    # 计算期望得分
    expected_a = calculate_expected(elo_a, elo_b)
    expected_b = 1.0 - expected_a  # E_b = 1 - E_a

    # 计算实际得分
    actual_a, actual_b = get_actual_score(score_a, score_b)

    # 计算ELO变化
    delta_a = K_FACTOR * (actual_a - expected_a)
    delta_b = K_FACTOR * (actual_b - expected_b)

    # 限制变化量
    delta_a = clamp_elo_change(delta_a)
    delta_b = clamp_elo_change(delta_b)

    new_elo_a = elo_a + delta_a
    new_elo_b = elo_b + delta_b

    return new_elo_a, new_elo_b


def load_json(path: str) -> Optional[dict]:
    """安全加载JSON文件"""
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return None


def save_json(path: str, data: dict) -> None:
    """保存JSON文件"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_processed_matches() -> List[str]:
    """加载已处理的比赛ID列表"""
    data = load_json(PROCESSED_MARKER)
    if data:
        return data.get("processed_match_ids", [])
    return []


def save_processed_matches(match_ids: List[str]) -> None:
    """保存已处理的比赛ID列表"""
    save_json(PROCESSED_MARKER, {
        "processed_match_ids": match_ids,
        "updated_at": json.dumps(__import__("datetime").datetime.now().isoformat())
    })


def get_completed_matches(match_data: dict) -> List[dict]:
    """
    从match_cache中获取已完成比赛（score_a和score_b都有值且不为null）
    """
    completed = []
    for match in match_data.get("results", []):
        score_a = match.get("score_a")
        score_b = match.get("score_b")
        # 检查是否为已完成比赛：分数必须非null
        if score_a is not None and score_b is not None:
            completed.append(match)
    return completed


def update_elo_cache(
    elo_cache: Dict[str, float],
    completed_matches: List[dict],
    processed_ids: List[str]
) -> Tuple[Dict[str, float], List[str]]:
    """
    遍历已完成比赛，更新ELO评分
    
    Returns:
        (updated_elo_cache, new_processed_ids)
    """
    new_processed = list(processed_ids)
    updated_elo = dict(elo_cache)

    for match in completed_matches:
        match_id = match.get("id", "")
        
        # 跳过已处理的比赛（幂等保证）
        if match_id in processed_ids:
            continue

        team_a = match.get("team_a")
        team_b = match.get("team_b")
        score_a = match.get("score_a")
        score_b = match.get("score_b")

        if not all([team_a, team_b, isinstance(score_a, int), isinstance(score_b, int)]):
            continue

        # 获取当前ELO（不存在则用默认值）
        elo_a = updated_elo.get(team_a, DEFAULT_ELO)
        elo_b = updated_elo.get(team_b, DEFAULT_ELO)

        # 更新ELO
        new_elo_a, new_elo_b = update_elo_for_match(elo_a, elo_b, score_a, score_b)

        updated_elo[team_a] = new_elo_a
        updated_elo[team_b] = new_elo_b

        # 标记为已处理
        if match_id:
            new_processed.append(match_id)

        print(f"  {team_a} ({elo_a:.1f}) vs {team_b} ({elo_b:.1f}) "
              f"[{score_a}-{score_b}] → "
              f"{team_a}: {new_elo_a:.1f}, {team_b}: {new_elo_b:.1f}")

    return updated_elo, new_processed


def main():
    """主函数"""
    print("=" * 60)
    print("ELO Auto-Update from Match Results")
    print("=" * 60)

    # 1. 加载现有ELO缓存
    elo_cache = load_json(ELO_CACHE) or {}
    if not elo_cache:
        print(f"⚠️ ELO缓存为空或不存在: {ELO_CACHE}")
        print("   将使用默认ELO值初始化")
        elo_cache = {}

    # 2. 加载match_cache
    match_data = load_json(MATCH_CACHE)
    if not match_data:
        print(f"⚠️ 比赛缓存为空或不存在: {MATCH_CACHE}")
        print("   没有比赛数据需要处理")
        return

    # 3. 获取已完成比赛
    completed = get_completed_matches(match_data)
    print(f"\n📊 找到 {len(completed)} 场已完成比赛")

    if not completed:
        print("   没有需要处理的比赛")
        return

    # 4. 加载已处理的比赛ID
    processed_ids = load_processed_matches()
    print(f"📋 已有 {len(processed_ids)} 场比赛被处理过")

    # 5. 过滤出未处理的新比赛
    new_matches = [m for m in completed if m.get("id") not in processed_ids]
    print(f"🆕 本次新增 {len(new_matches)} 场需要更新ELO的比赛")

    if not new_matches:
        print("\n✅ 所有已完成比赛已被处理，ELO已是最新")
        return

    # 6. 更新ELO
    print("\n📝 ELO更新详情:")
    updated_elo, new_processed = update_elo_cache(elo_cache, completed, processed_ids)

    # 7. 保存更新后的ELO缓存
    save_json(ELO_CACHE, updated_elo)
    print(f"\n💾 已保存更新后的ELO到: {ELO_CACHE}")

    # 8. 保存已处理的比赛ID
    save_processed_matches(new_processed)
    print(f"💾 已保存处理记录到: {PROCESSED_MARKER}")

    # 9. 显示变化最大的队伍
    print("\n📈 ELO变化汇总 (top 10):")
    changes = []
    for team, new_elo in updated_elo.items():
        old_elo = elo_cache.get(team, DEFAULT_ELO)
        delta = new_elo - old_elo
        if abs(delta) > 0.1:  # 只显示有变化的
            changes.append((team, old_elo, new_elo, delta))
    changes.sort(key=lambda x: abs(x[3]), reverse=True)
    for team, old, new, delta in changes[:10]:
        sign = "+" if delta > 0 else ""
        print(f"   {team:25s} {old:7.1f} → {new:7.1f} ({sign}{delta:.1f})")

    print("\n✅ ELO更新完成!")


if __name__ == "__main__":
    main()
