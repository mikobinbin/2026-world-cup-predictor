import json
import math
import sys

# ── Load data ─────────────────────────────────────────────────────────────────
with open("/Users/miko/wc_pred_temp/data/match_cache.json") as f:
    match_cache = json.load(f)

with open("/Users/miko/wc_pred_temp/data/elo_cache_2026.json") as f:
    elo_cache = json.load(f)

# ── Poisson PMF ───────────────────────────────────────────────────────────────
def poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

# ── Build elo_dict_h2h from elo_cache (baseline ELO) ─────────────────────────
elo_dict_h2h = dict(elo_cache)  # country -> elo

# ── Shift dictionary ───────────────────────────────────────────────────────────
# shift = mystic_prob - final_probability (from results list, mobile_ui.py ~line 448)
# We reconstruct from known team data. For teams not in this dict, shift = 0.
# Based on the mystic_map / results computation in mobile_ui.py.
shift_dict = {
    "England": 0,
    "France": 0,
    "Croatia": 0,
    "Norway": 0,
    "Portugal": 0,
    "Germany": 0,
    "Netherlands": 0,
    "Switzerland": 0,
    "Scotland": 0,
    "Spain": 0,
    "Austria": 0,
    "Belgium": 0,
    "Bosnia and Herzegovina": 0,
    "Sweden": 0,
    "Turkey": 0,
    "Czech Republic": 0,
    "Brazil": 0,
    "Argentina": 0,
    "Colombia": 0,
    "Ecuador": 0,
    "Paraguay": 0,
    "Uruguay": 0,
    "USA": 0,
    "Mexico": 0,
    "Canada": 0,
    "Panama": 0,
    "Curaçao": 0,
    "Haiti": 0,
    "Japan": 0,
    "South Korea": 0,
    "Australia": 0,
    "Iran": 0,
    "Saudi Arabia": 0,
    "Qatar": 0,
    "Jordan": 0,
    "Uzbekistan": 0,
    "Algeria": 0,
    "Cape Verde": 0,
    "Egypt": 0,
    "Ghana": 0,
    "Ivory Coast": 0,
    "Morocco": 0,
    "Senegal": 0,
    "South Africa": 0,
    "Tunisia": 0,
    "New Zealand": 0,
    "DR Congo": 0,
    "Iraq": 0,
}

# ── Core score prediction (port of JS buildScorePred) ────────────────────────
def predict_score(elo_a, elo_b, shift_a, shift_b):
    """
    Returns sorted list of {ga, gb, prob} for all ga in [0,5], gb in [0,5].
    Probabilities include the extreme-score boost (total>=5 → ×3.0) and are
    re-normalised to sum to 1.
    """
    # Lambda from ELO
    lambda_a = 1.3 + (elo_a - 1700) / 500.0 * 1.0
    lambda_b = 1.3 + (elo_b - 1700) / 500.0 * 1.0

    # Apply shift with ×3.0 multiplier
    lambda_a = lambda_a * (1.0 + shift_a * 3.0)
    lambda_b = lambda_b * (1.0 + shift_b * 3.0)

    # Clamp to [0.3, 4.0]
    lambda_a = max(0.3, min(4.0, lambda_a))
    lambda_b = max(0.3, min(4.0, lambda_b))

    EXTREME_THRESH = 5
    BOOST_FACTOR = 3.0

    raw = []
    for ga in range(6):
        for gb in range(6):
            pois = poisson_pmf(ga, lambda_a) * poisson_pmf(gb, lambda_b)
            total = ga + gb
            boosted = pois * BOOST_FACTOR if total >= EXTREME_THRESH else pois
            raw.append({"ga": ga, "gb": gb, "boosted": boosted})

    sum_boosted = sum(x["boosted"] for x in raw)
    for x in raw:
        x["prob"] = x["boosted"] / sum_boosted if sum_boosted > 0 else 0

    # Sort by probability descending
    raw.sort(key=lambda x: x["prob"], reverse=True)
    return raw

# ── Evaluate on all 12 completed matches ─────────────────────────────────────
completed = [m for m in match_cache.get("results", []) 
             if m.get("score_a") is not None and m.get("score_b") is not None]

print(f"\n{'='*70}")
print(f"  泊松比分预测评估 — 12场已完成比赛")
print(f"{'='*70}")
print(f"\n{'Match':<35} {'Actual':<8} {'Top1':<8} {'Top3':<20} {'Hit?':<6}")
print(f"{'-'*70}")

exact_hits = 0
top3_hits = 0

rows = []
for match in completed:
    team_a = match["team_a"]
    team_b = match["team_b"]
    score_a = match["score_a"]
    score_b = match["score_b"]
    actual = f"{score_a}-{score_b}"

    elo_a = elo_dict_h2h.get(team_a, 1700)
    elo_b = elo_dict_h2h.get(team_b, 1700)
    shift_a = shift_dict.get(team_a, 0)
    shift_b = shift_dict.get(team_b, 0)

    sorted_scores = predict_score(elo_a, elo_b, shift_a, shift_b)

    top1 = sorted_scores[0]
    top1_str = f"{top1['ga']}-{top1['gb']}"
    top1_prob = top1['prob']

    top3 = sorted_scores[:3]
    top3_strs = [f"{s['ga']}-{s['gb']}" for s in top3]
    top3_str = str(top3_strs)

    exact_hit = actual == top1_str
    top3_hit = actual in top3_strs

    if exact_hit:
        exact_hits += 1
    if top3_hit:
        top3_hits += 1

    hit_str = "✓ EXACT" if exact_hit else ("✓ TOP3" if top3_hit else "✗ miss")
    print(f"{team_a} vs {team_b:<20} {actual:<8} {top1_str:<8} {top3_str:<20} {hit_str}")
    rows.append({
        "match": f"{team_a} vs {team_b}",
        "actual": actual,
        "top1": top1_str,
        "top3": top3_strs,
        "exact_hit": exact_hit,
        "top3_hit": top3_hit,
        "lambda_a": 1.3 + (elo_a - 1700) / 500 * 1.0,
        "lambda_b": 1.3 + (elo_b - 1700) / 500 * 1.0,
        "elo_a": elo_a,
        "elo_b": elo_b,
        "shift_a": shift_a,
        "shift_b": shift_b,
    })

total = len(completed)
print(f"\n{'='*70}")
print(f"  汇总统计")
print(f"{'='*70}")
print(f"  总比赛数  : {total}")
print(f"  精确命中  : {exact_hits}/{total} = {exact_hits/total*100:.1f}%")
print(f"  Top3 命中 : {top3_hits}/{total} = {top3_hits/total*100:.1f}%")
print(f"\n  (注: shift_dict 全为0，因缺少 mystic_prob 数据)")
print(f"  ELO基准=1700, shift乘数=3.0, lambda clamp=[0.3, 4.0], boost=×3.0)")
