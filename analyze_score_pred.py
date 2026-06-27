#!/usr/bin/env python3
"""分析并测试 buildScorePred 算法"""

import math
import json

# Load data
with open('/Users/miko/wc_pred_temp/data/elo_cache_2026.json') as f:
    elo_cache = json.load(f)

with open('/Users/miko/wc_pred_temp/data/match_cache.json') as f:
    match_cache = json.load(f)

results = match_cache['results']

def poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def compute_lambdas(team_a, team_b, elo_dict, results_list, shift=0):
    """复制 mobile_ui.py 中的 lambda 计算逻辑"""
    elo_a_val = elo_dict.get(team_a, 1700)
    elo_b_val = elo_dict.get(team_b, 1700)
    
    shift_a, shift_b = 0, 0
    for r in results_list:
        if r.get("country") == team_a:
            shift_a = r.get("shift", 0) or 0
        if r.get("country") == team_b:
            shift_b = r.get("shift", 0) or 0
    
    lambda_a = 1.3 + (elo_a_val - 1700) / 500.0 * 1.0
    lambda_b = 1.3 + (elo_b_val - 1700) / 500.0 * 1.0
    lambda_a = lambda_a * (1 + shift_a * 3.0)
    lambda_b = lambda_b * (1 + shift_b * 3.0)
    lambda_a = max(0.3, min(4.0, lambda_a))
    lambda_b = max(0.3, min(4.0, lambda_b))
    
    return lambda_a, lambda_b

def build_score_predictions(lambda_a, lambda_b, max_goals=6, boost_threshold=5, boost_factor=3.0, extreme_threshold=7, extreme_factor=5.0):
    """生成比分预测，使用扩展网格和分段 boost"""
    raw = []
    for ga in range(max_goals):
        for gb in range(max_goals):
            p = poisson_pmf(ga, lambda_a) * poisson_pmf(gb, lambda_b)
            total = ga + gb
            # 分段 boost
            if total >= extreme_threshold:
                boosted = p * extreme_factor
            elif total >= boost_threshold:
                boosted = p * boost_factor
            else:
                boosted = p
            raw.append({"ga": ga, "gb": gb, "prob": boosted, "total": total, "base_prob": p})
    
    total_prob = sum(x["prob"] for x in raw)
    for x in raw:
        x["prob"] = x["prob"] / total_prob if total_prob > 0 else 0
    
    sorted_scores = sorted(raw, key=lambda x: x["prob"], reverse=True)
    return sorted_scores

# ============ 第一步：分析 Germany vs Curaçao ============
print("=" * 70)
print("第一步：Germany vs Curaçao 详细分析")
print("=" * 70)

team_a, team_b = "Germany", "Curaçao"
lambda_a, lambda_b = compute_lambdas(team_a, team_b, elo_cache, results)
print(f"\nGermany ELO: {elo_cache.get('Germany')}")
print(f"Curaçao ELO: {elo_cache.get('Curaçao')}")
print(f"λ_A = {lambda_a:.4f}, λ_B = {lambda_b:.4f}")

# 0-5 网格 (现有逻辑)
print("\n--- 0-5 网格下的 total≥5 比分 ---")
sorted_05 = build_score_predictions(lambda_a, lambda_b, max_goals=6, boost_threshold=5, boost_factor=3.0)
for s in sorted_05:
    if s['total'] >= 5:
        print(f"  {s['ga']}-{s['gb']} (total={s['total']}): base={s['base_prob']:.6f}, boosted={s['prob']:.6f}")

print("\n--- 0-5 网格 Top3 预测 ---")
for i, s in enumerate(sorted_05[:3]):
    print(f"  #{i+1}: {s['ga']}-{s['gb']} (prob={s['prob']:.4f}, total={s['total']})")

# 找到 7-1 在 0-5 网格中的位置
for i, s in enumerate(sorted_05):
    if s['ga'] == 7 and s['gb'] == 1:
        print(f"\n  7-1 在 0-5 网格中排名: #{i+1}, base prob={s['base_prob']:.8f}, boosted={s['prob']:.8f}")
        break

# ============ 第二步：扩展到 0-8 网格 ============
print("\n" + "=" * 70)
print("第二步：0-8 网格扩展测试")
print("=" * 70)

# 原始 boost (3.0 for total>=5)
print("\n--- 0-8 网格 (boost=3.0 for total>=5) ---")
sorted_08_3 = build_score_predictions(lambda_a, lambda_b, max_goals=9, boost_threshold=5, boost_factor=3.0)
print("Top3 预测:")
for i, s in enumerate(sorted_08_3[:3]):
    print(f"  #{i+1}: {s['ga']}-{s['gb']} (prob={s['prob']:.4f}, total={s['total']})")

# 找到 7-1 在 0-8 网格中的位置
for i, s in enumerate(sorted_08_3):
    if s['ga'] == 7 and s['gb'] == 1:
        print(f"\n  7-1 在 0-8 网格中排名: #{i+1}, base prob={s['base_prob']:.8f}, boosted={s['prob']:.8f}")
        # 需要多少 boost 才能进入 Top3?
        top3_min_prob = sorted_08_3[2]['prob']
        needed_boost = top3_min_prob / s['base_prob'] if s['base_prob'] > 0 else float('inf')
        print(f"  Top3 最低概率: {top3_min_prob:.8f}")
        print(f"  需要 boost 到 {needed_boost:.1f}x 才能进入 Top3")
        break

# 新 boost (5.0 for total>=7)
print("\n--- 0-8 网格 (boost=5.0 for total>=7, 3.0 for total>=5) ---")
sorted_08_5 = build_score_predictions(lambda_a, lambda_b, max_goals=9, boost_threshold=5, boost_factor=3.0, extreme_threshold=7, extreme_factor=5.0)
print("Top3 预测:")
for i, s in enumerate(sorted_08_5[:3]):
    print(f"  #{i+1}: {s['ga']}-{s['gb']} (prob={s['prob']:.4f}, total={s['total']})")

# 找到 7-1 在新逻辑下的位置
for i, s in enumerate(sorted_08_5):
    if s['ga'] == 7 and s['gb'] == 1:
        print(f"\n  7-1 在新逻辑下排名: #{i+1}, boosted={s['prob']:.8f}")
        break

# ============ 第三步：12 场全数据集测试 ============
print("\n" + "=" * 70)
print("第三步：12 场全数据集测试")
print("=" * 70)

# 旧逻辑 (0-5 网格, boost=3.0 for total>=5)
old_hits = 0
old_top3_hits = 0
# 新逻辑 (0-8 网格, boost=5.0 for total>=7, 3.0 for total>=5)
new_hits = 0
new_top3_hits = 0

for match in results:
    team_a, team_b = match['team_a'], match['team_b']
    actual = f"{match['score_a']}-{match['score_b']}"
    lambda_a, lambda_b = compute_lambdas(team_a, team_b, elo_cache, results)
    
    # 旧逻辑
    sorted_old = build_score_predictions(lambda_a, lambda_b, max_goals=6, boost_threshold=5, boost_factor=3.0)
    old_top = sorted_old[0]
    old_top3 = [f"{s['ga']}-{s['gb']}" for s in sorted_old[:3]]
    
    # 新逻辑
    sorted_new = build_score_predictions(lambda_a, lambda_b, max_goals=9, boost_threshold=5, boost_factor=3.0, extreme_threshold=7, extreme_factor=5.0)
    new_top = sorted_new[0]
    new_top3 = [f"{s['ga']}-{s['gb']}" for s in sorted_new[:3]]
    
    old_hit = (old_top['ga'] == match['score_a'] and old_top['gb'] == match['score_b'])
    old_top3_hit = actual in old_top3
    new_hit = (new_top['ga'] == match['score_a'] and new_top['gb'] == match['score_b'])
    new_top3_hit = actual in new_top3
    
    if old_hit: old_hits += 1
    if old_top3_hit: old_top3_hits += 1
    if new_hit: new_hits += 1
    if new_top3_hit: new_top3_hits += 1
    
    marker = "✓" if new_top3_hit else "✗"
    print(f"  {marker} {team_a} vs {team_b}: 实际={actual}, 旧Top1={old_top['ga']}-{old_top['gb']}, 新Top1={new_top['ga']}-{new_top['gb']}, 新Top3={new_top3}")

total = len(results)
print(f"\n--- 准确率对比 ---")
print(f"旧逻辑 (0-5 网格):")
print(f"  精确命中率: {old_hits}/{total} = {old_hits/total*100:.1f}%")
print(f"  Top3 命中率: {old_top3_hits}/{total} = {old_top3_hits/total*100:.1f}%")
print(f"新逻辑 (0-8 网格, 分段 boost):")
print(f"  精确命中率: {new_hits}/{total} = {new_hits/total*100:.1f}%")
print(f"  Top3 命中率: {new_top3_hits}/{total} = {new_top3_hits/total*100:.1f}%")

print("\n" + "=" * 70)
print("分析结论")
print("=" * 70)