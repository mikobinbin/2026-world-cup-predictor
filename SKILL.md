---
name: world-cup-predictor
description: 世界杯冠军预测系统 — 基于球员成长周期模型、球队Elo评分、玄学因子的综合预测框架。预测2026年美加墨世界杯冠军，同时输出球队排行榜、球员系数矩阵、可视化看板。
trigger: 当用户询问世界杯预测、冠军预测、世界杯AI分析、球队实力评估时触发。
author: Miko & Hermes
version: 0.1.0
tags: [world-cup, football, soccer, prediction, monte-carlo, elo-rating]
---

# World Cup Champion Predictor 🏆

## 核心功能

1. **球员模块** — 4年周期模型，追踪球员成长曲线预测当打之年
2. **球队模块** — Elo锚点 + 年龄结构 + 大赛经验 + 近期状态
3. **玄学模块** — 不可量化因子的哲学建模
4. **蒙特卡洛模拟** — 32队晋级路径概率模拟
5. **动态画板** — 球队/球员系数可视化看板

---

## 使用方式

```bash
# 方式1：生成分析报告
python -m world_cup_predictor.report --year 2026

# 方式2：启动交互式看板
python -m world_cup_predictor.dashboard

# 方式3：仅计算冠军概率
python -m world_cup_predictor predict --top 5
```

---

## 数据来源

| 数据 | 来源 | 优先级 | 状态 |
|------|------|--------|------|
| 球队Elo评分 | FiveThirtyEight SPI (GitHub CSV) | ⭐⭐⭐ 必选 | ✅ 已验证 |
| 球员阵容数据 | **Wikipedia 2026世界杯大名单** | ⭐⭐⭐ 重要 | ✅ 已接入 |
| 预选赛战绩 | FiveThirtyEight SPI | ⭐⭐ 重要 | ✅ 已在Elo中 |
| 球员职业轨迹 | Wikipedia推断 + 估算 | ⭐⭐ 重要 | ✅ 已接入 |
| 世界杯参赛经历 | Wikipedia推断 | ⭐⭐ 重要 | ✅ 自动推断 |

> **Wikipedia 数据接入**：28支球队 / 913名球员真实数据（截至2026-05-19）
> 来源：`https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_squads`
> 覆盖：巴西、法国、阿根廷、克罗地亚、葡萄牙、比利时、日本、韩国等
> ⚠️ 未覆盖球队（名单尚未公布）：德国、英格兰、西班牙、意大利、荷兰等 → 回退到样本数据

### 数据获取脚本

```bash
# 1. 抓取 Wikipedia 大名单（主要数据源）
python scripts/wikipedia_squads.py --output data/wc2026_squads_wikipedia.json

# 2. 处理并转换为模型格式
python scripts/ingest_wikipedia_squads.py --input data/wc2026_squads_wikipedia.json --output data/wc2026_players_processed.json

# 3. 生成预测报告
python scripts/report.py --year 2026 --top 12 --mystic conservative --output /tmp/wc2026_report.txt
```

---

## 模型权重（可配置）

| 因子 | 默认权重 | 说明 |
|------|---------|------|
| Elo锚点 | 35% | FiveThirtyEight SPI评分 |
| 年龄结构 | 20% | 主力年龄中位数与黄金期匹配度 |
| 大赛经验 | 15% | 首发有世界杯经验球员占比 |
| 近期状态 | 15% | 近18个月胜率 |
| 教练因素 | 10% | 大赛执教成绩 |
| 玄学因子 | 5% | 不可量化因子 |

---

## 文件结构
```
world-cup-predictor/
├── SKILL.md              ← 本文件
├── config.py             ← 模型权重配置（年龄峰值、位置权重、玄学模式）
├── scripts/
│   ├── report.py             ← 预测报告生成器（含Wikipedia数据集成）
│   ├── elo_scraper.py        ← FiveThirtyEight SPI数据
│   ├── wikipedia_squads.py   ← Wikipedia大名单抓取 ⭐新增
│   └── ingest_wikipedia_squads.py ← 数据清洗与模型格式转换 ⭐新增
├── src/
│   ├── models/
│   │   ├── player_scoring.py     ← 球员评分模型（4年周期）
│   │   ├── team_scoring.py       ← 球队评分模型
│   │   └── mystic_factor.py      ← 玄学因子
│   └── simulation/
│       └── monte_carlo.py        ← 蒙特卡洛模拟
└── data/
    ├── wc2026_squads_wikipedia.json    ← Wikipedia原始数据
    └── wc2026_players_processed.json   ← 处理后数据
```

---

## 配置

运行前需在 `~/.hermes/.env` 或项目根目录 `.env` 设置：

```bash
# Transfermarkt（可选，用于球员详细数据）
TRANSFERMARKT_COOKIE=your_cookie_here

# 玄学因子模式（conservative/aggressive/mystical）
MYSTIC_MODE=conservative
```

---

## 输出示例

```
🏆 2026世界杯冠军预测

🥇 巴西        22.3%  [██████████████████░░░░]
🥈 法国        18.7%  [████████████████░░░░░░]
🥉 阿根廷      15.1%  [██████████████░░░░░░░░░]
4   英格兰      11.2%  [██████████░░░░░░░░░░░░]
5   西班牙       9.8%  [█████████░░░░░░░░░░░░░]
...
```

---

## Known Issues & Solutions (Build Experience)

### FiveThirtyEight API Redirect Issue
- `projects.fivethirtyeight.com/soccer-api/club/spi_global_ratings.json` 会301重定向
- **Solution**: 用GitHub CSV源 `raw.githubusercontent.com/fivethirtyeight/data/master/soccer-spi/spi_global_rankings.csv`

### Circular Import: monte_carlo ↔ team_scoring
- `simulation/monte_carlo.py` 顶层导入 `TeamResult` 会造成循环依赖
- **Solution**: 将导入语句移到函数内部（延迟导入）

### Monte Carlo RandomState 必须放在循环外（致命 Bug）
- **症状**：Japan 100% 夺冠，其他全 0%
- **根因**：`np.random.RandomState(42)` 放在 `for _ in range(n):` 循环内部 → 每次迭代 seed 相同，10,000 次全走同一路径
- **正确写法**：
```python
rng = np.random.RandomState(42)  # ← 循环外设一次
for _ in range(n):
    path = _simulate_tournament_path(team_list, elo_arr, rng=rng)  # ← 传入 rng
    wins[path] += 1
```

### Wikipedia 数据字段名与代码不匹配（致命 Bug，会静默失败）
- Wikipedia 原始数据字段名：`caps`（非 `national_caps`）、`goals`（非 `national_goals`）、位置带数字前缀如 `"1GK"`、`"2DF"`
- 症状：Brazil 有 12 名老将（caps≥30），但经验计算返回 0（因为 `national_caps` 字段全为 0）
- **排查方法**：`sum(1 for p in squad.players if p.national_caps >= 30)` 返回 0 → 检查字段名映射
- **正确做法**：`build_squad_from_data` 必须做两层兼容：
  1. 位置清理：`re.sub(r'^\d+', '', pos)` → `"1GK"` → `"GK"`
  2. 字段兼容：`d.get('caps', d.get('national_caps', 0))`
  3. 经验 fallback：有 `tournaments` 字段 → 优先用；无则用 `caps >= 30` 作为代理

### H2H 历史战绩不适合作为预测输入（逻辑缺陷）
- 世界杯间隔4年，球员名单大面积更迭——2014 Brazil vs Germany 1-7 惨案，只有 Thiago Silva 还在
- 历史交锋记录应该作为"信息注释"，不是"预测权重"
- **正确做法**：H2H 胜率作为常数项（≤3%），Elo 主导（≥85%），另加阵容深度因子（10%）

### 因子加成的量级控制（防止 Elo 膨胀）
- `total_mod` 上限必须 clamp 到 ±12%，否则强队 Elo 轻易破 2000 → 概率 35%+
- `ExperienceConfig` 各档值要小（0.03/0.02/0.01），经验权重 15% 下实际影响 ±2% 以内

### coaching_factor 必须固定随机种子
- 用 `random.uniform(0.4, 0.9)` 每次结果不同
- **正确做法**：`hash(country) % 1000 / 1000.0` → 每队固定值，0.4~0.9

### Narrative 生成逻辑缺陷
- 卫冕冠军/近3届进过4强的队永远不说"缺乏顶级大赛历练"
- 修复：有 `tournament_history` 含 '2022'/'2018'/'Final'/'Semi' 时跳过该判断

### Elo→概率曲线校准（五届世界杯冠军为锚）
```
elo=1950 → 18%  （2018法国/2022阿根廷级别）
elo=1882 →  7%  （四强门槛）
elo=1750 →  2.5%（16强门槛）
公式：C=1.5e-7, K=150, p=C*exp(elo/K)
```

### Transfermarkt 反爬严格
- Transfermarkt 和 worldfootball.net 均有强反爬（Cloudflare + 404假页面）
- **Solution**: 改用 Wikipedia `2026 FIFA World Cup squads` 页面，数据质量相当且无反爬

### Wikipedia Squad 数据补充规则
- 限26人（世界杯最终名单上限），按代表队出场数降序取前26人
- 世界杯经验通过年龄+出场数推断（25岁+/10场以上 → 有2022经验）
- 市场价通过位置+出场+年龄估算（Wikipedia无市场价字段）

### Variable Naming Bug
- 定义常量 `DEFENDING_CHAMPION`，调用写成 `DEFENDING_CHAMP`
- **Prevention**: 统一命名规范，或用枚举类

---

## Known Limitations

1. ⚠️ 2026年世界杯阵容尚未全部公布（截至2026-05-19，约28/48队已公布）
2. ⚠️ 伤病、状态等动态因素无法提前预测
3. ⚠️ 玄学因子是哲学建模，不代表真实因果关系
4. ⚠️ Wikipedia 无球员市场价字段，用位置+出场+年龄估算，与真实身价有差距
5. ⚠️ 阿根廷/墨西哥等队的55人扩展名单已裁至26人，优先保留高出场球员，可能漏掉新星
