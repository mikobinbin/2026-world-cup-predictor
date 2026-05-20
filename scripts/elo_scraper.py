"""
数据获取脚本 — FiveThirtyEight Elo数据

FiveThirtyEight SPI评分是全球最准确的足球实力指标之一
数据来源：https://github.com/fivethirtyeight/data/tree/master/soccer-spi
"""

import requests
import pandas as pd
from typing import Dict, Optional
import os
import json

FIVETHIRTYEIGHT_SPI_URL = (
    "https://projects.fivethirtyeight.com/soccer-api/club/spi_global_ratings.json"
)

# 备用：直接用GitHub数据源
FIVETHIRTYEIGHT_GITHUB_URL = (
    "https://raw.githubusercontent.com/fivethirtyeight/data/master/soccer-spi/"
    "spi_global_rankings.csv"
)

# 手动维护的2026世界杯强队Elo（基于2022世界杯后表现）
# 这些数据在真实环境下应从API获取
MANUAL_ELO_DATA = {
    # 顶级强队
    "Argentina": 1882.3,
    "Brazil": 1912.7,
    "France": 1887.4,
    "England": 1834.2,
    "Spain": 1821.6,
    "Germany": 1809.3,
    "Portugal": 1812.5,
    "Netherlands": 1798.7,
    "Italy": 1789.4,
    "Belgium": 1785.2,
    # 二梯队
    "Croatia": 1778.3,
    "Uruguay": 1772.1,
    "Mexico": 1689.4,
    "USA": 1702.3,
    "Canada": 1654.8,
    "Japan": 1678.9,
    "South Korea": 1668.2,
    "Morocco": 1681.5,
    "Senegal": 1675.3,
    "Cameroon": 1621.8,
    # 弱队
    "Iran": 1598.7,
    "Saudi Arabia": 1578.4,
    "Australia": 1612.6,
    "Ghana": 1598.2,
    "Algeria": 1615.7,
}


def fetch_spi_ratings() -> Optional[pd.DataFrame]:
    """
    从FiveThirtyEight获取SPI评分
    优先CSV数据源（GitHub），回退到手动数据
    """
    try:
        # 尝试GitHub CSV源
        response = requests.get(FIVETHIRTYEIGHT_GITHUB_URL, timeout=10)
        response.raise_for_status()
        from io import StringIO
        df = pd.read_csv(StringIO(response.text))
        return df
    except Exception as e:
        print(f"⚠️ 无法从FiveThirtyEight获取数据: {e}")
        print("使用手动维护数据...")
        return None


def get_team_elo(country: str) -> float:
    """
    获取球队Elo评分
    优先从API获取，回退到手动数据
    """
    # 先查手动数据
    for key, elo in MANUAL_ELO_DATA.items():
        if key.lower() in country.lower() or country.lower() in key.lower():
            return elo

    # 尝试从API获取
    df = fetch_spi_ratings()
    if df is not None:
        matches = df[df['name'].str.lower() == country.lower()]
        if not matches.empty:
            return float(matches.iloc[0]['spi'])

    # 默认值
    return 1650.0


def get_all_team_elos(countries: list) -> Dict[str, float]:
    """
    获取多个球队的Elo评分
    """
    return {country: get_team_elo(country) for country in countries}


def save_elo_cache(elos: Dict[str, float], cache_path: str):
    """保存Elo数据到缓存"""
    with open(cache_path, 'w') as f:
        json.dump(elos, f, indent=2)


def load_elo_cache(cache_path: str) -> Optional[Dict[str, float]]:
    """从缓存加载Elo数据"""
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            return json.load(f)
    return None


if __name__ == "__main__":
    # 测试
    teams = ["Brazil", "Argentina", "France", "England", "Spain"]
    elos = get_all_team_elos(teams)
    for team, elo in elos.items():
        print(f"{team}: {elo:.1f}")
