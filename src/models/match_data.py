"""
Match Data — 从 Flashscore 抓取世界杯赛程/赛果/热身赛数据

数据源: https://www.flashscore.com/football/world/world-championship/
数据格式: cjs.initialFeeds — 自定义 ÷/¬ 分隔格式

抓取策略:
  - fixtures  → 赛程（未开始的比赛）
  - results   → 赛果（已完成的世界杯正赛）
  - friendly  → 热身赛（各队热身赛）

影响模型的方式:
  - 赛果/热身赛 → 更新 team_scoring 中的 form_score
  - 赛程/赛果   → 冠军概率动态调整（已出线/已淘汰/近期状态）
"""

from __future__ import annotations
import re
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any

# ──────────────────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────────────────

def _unix_to_local(unix_ts: str, tz_hours: int = -5) -> datetime:
    """Unix时间戳 → 指定时区的本地日期时间（世界杯举办地 UTC-5/-7/-8）"""
    try:
        ts = int(unix_ts)
        utc = datetime.fromtimestamp(ts, tz=timezone.utc)
        return utc + timedelta(hours=tz_hours)
    except (ValueError, OSError):
        return datetime(2026, 6, 1)  # fallback


def _parse_flashscore_chunk(chunk: str) -> Dict[str, str]:
    """
    解析单个 Flashscore 数据块。
    格式: key1÷value1¬key2÷value2¬...
    值内部可能包含 ÷ 字符，解析时从最后一个 ÷ 分割。
    """
    result: Dict[str, str] = {}
    # 先按 ¬ 分割
    parts = chunk.split("¬")
    for part in parts:
        if "÷" not in part:
            continue
        # 从最后一个 ÷ 分割（值内部可能有 ÷）
        idx = part.rfind("÷")
        key = part[:idx]
        val = part[idx + 1:]
        if key:
            result[key] = val
    return result


def _parse_initial_feeds(raw: str) -> List[Dict[str, str]]:
    """把 Flashscore initialFeeds 原始字符串解析为记录列表。"""
    records = []
    # 按 ¬~ 分割主要块（~ 后面跟着 AA÷ 标记的是记录开始）
    segments = raw.split("¬~")
    for seg in segments:
        # 跳过不含 AA÷ 的元数据段
        if "AA÷" not in seg:
            continue
        # 找到 AA÷ 的位置，取其后面作为记录内容
        aa_idx = seg.find("AA÷")
        rec = seg[aa_idx:]
        parsed = _parse_flashscore_chunk(rec)
        if parsed.get("AA"):
            records.append(parsed)
    return records


def _team_normalize(name: str) -> str:
    """
    将各种数据源的队名统一映射为模型标准名称。

    模型标准名称遵循 elo_cache 和 wc2026_squads_wikipedia.json 的约定：
    - elo_cache 键名
    - wc2026_squads_wikipedia.json 国家键名

    队名标准化规则（经核实）：
    - "Cape Verde"（非 "Cape Verde Islands"）
    - "Curaçao"（非 "Curacao"）
    - "Iran"（Wikipedia 用 "IR Iran"）
    - "South Korea"（非 "Korea Republic"）
    - "USA"（非 "United States"）
    """
    MAP = {
        # Flashscore → 模型标准
        "United States": "USA",
        "Korea Republic": "South Korea",
        "DR Congo": "DR Congo",
        "D.R. Congo": "DR Congo",
        "China": "China PR",
        "Bosnia & Herzegovina": "Bosnia and Herzegovina",
        "Bosnia-Herzegovina": "Bosnia and Herzegovina",
        "Ivory Coast": "Ivory Coast",
        "Curacao": "Curaçao",
        "Trinidad & Tobago": "Trinidad and Tobago",
        "Northern Ireland": "Northern Ireland",
        "Korea DPR": "Korea DPR",
        "Brunei": "Brunei",
        "Chinese Taipei": "Chinese Taipei",
        "São Paulo": "São Paulo",
        "NY Red Bulls": "New York Red Bulls",
        "Shandong Luneng": "Shandong Taishan",
        "Shanghai SIPG": "Shanghai SIPG",
        "Beijing Guoan": "Beijing Guoan",
        # Wikipedia → 模型标准（IR Iran 是 Wikipedia 的标准写法）
        "IR Iran": "Iran",
    }
    return MAP.get(name, name)


# ──────────────────────────────────────────────────────────────────────────────
# 核心解析类
# ──────────────────────────────────────────────────────────────────────────────

class FlashscoreParser:
    """解析 Flashscore cjs.initialFeeds 数据"""

    # 已知的非世界杯赛事（资格赛等）
    NON_WC_LEAGUES = [
        "qualification", "qualif", "promotion", "play-off", "playoff",
        "intercontinental", "baraj", "relegation", " группы", "группа",
    ]

    def __init__(self, fixtures_raw: str = "", results_raw: str = "", friendly_raw: str = ""):
        self.fixtures_raw = fixtures_raw
        self.results_raw = results_raw
        self.friendly_raw = friendly_raw

    def parse_fixtures(self) -> List[Dict[str, Any]]:
        """解析赛程数据"""
        records = _parse_initial_feeds(self.fixtures_raw)
        matches = []
        for r in records:
            match = self._parse_match_record(r, is_result=False)
            if match:
                matches.append(match)
        return matches

    def parse_results(self) -> List[Dict[str, Any]]:
        """解析赛果数据（仅世界杯正赛）"""
        records = _parse_initial_feeds(self.results_raw)
        matches = []
        for r in records:
            # 过滤掉非世界杯正赛的记录
            league = r.get("ZA", "")
            if any(bad in league.lower() for bad in self.NON_WC_LEAGUES):
                # intercontinental playoff（最终资格赛）和 promotion 包含在世界杯内
                if "qualification" in league.lower() or "promotion" in league.lower() or "intercontinental" in league.lower():
                    match = self._parse_match_record(r, is_result=True)
                    if match:
                        matches.append(match)
                continue
            match = self._parse_match_record(r, is_result=True)
            if match:
                matches.append(match)
        return matches

    def parse_friendlies(self) -> List[Dict[str, Any]]:
        """解析热身赛数据"""
        records = _parse_initial_feeds(self.friendly_raw)
        matches = []
        for r in records:
            match = self._parse_match_record(r, is_result=True)
            if match:
                matches.append(match)
        return matches

    def _parse_match_record(self, r: Dict[str, str], is_result: bool) -> Optional[Dict[str, Any]]:
        """从单条记录中提取比赛信息"""
        try:
            # 队名：优先用完整名称字段
            team_a = r.get("CX") or r.get("AE") or ""
            team_b = r.get("AF") or r.get("WN") or ""

            if not team_a or not team_b:
                return None

            # 跳过俱乐部赛事
            skip_prefixes = ("Stoke", "Arsenal", "Man Utd", "Liverpool", "Chelsea",
                             "Real Madrid", "Barcelona", "Bayern", "Juventus",
                             "PSG", "Man City", "Tottenham", "AC Milan", "Inter",
                             "Shandong", "Shanghai", "Beijing", "New York")
            if any(team_a.startswith(p) or team_b.startswith(p) for p in skip_prefixes):
                return None

            # 时间戳
            unix_ts = r.get("ADE") or r.get("AD") or ""
            dt = _unix_to_local(unix_ts)

            # 比分
            score_a: Optional[int] = None
            score_b: Optional[int] = None
            if is_result:
                try:
                    score_a = int(r.get("AG", ""))
                    score_b = int(r.get("AT", ""))
                except ValueError:
                    pass
                # 需要重新检查格式
                pass

            # 轮次
            round_name = r.get("ER") or ""

            # World Cup 2026 小组赛格式: "Group A", "Group B" etc
            is_group = round_name.lower().startswith("group")

            return {
                "id": r.get("AA", ""),
                "datetime": dt.strftime("%Y-%m-%d %H:%M"),
                "date": dt.strftime("%m.%d"),
                "time": dt.strftime("%H:%M"),
                "team_a": _team_normalize(team_a),
                "team_b": _team_normalize(team_b),
                "score_a": score_a,
                "score_b": score_b,
                "round": round_name,
                "is_group": is_group,
                "is_wc": True,
            }
        except Exception:
            return None


# ──────────────────────────────────────────────────────────────────────────────
# 主抓取类（使用外部浏览器获取数据）
# ──────────────────────────────────────────────────────────────────────────────

class MatchDataFetcher:
    """
    从 Flashscore 抓取世界杯相关比赛数据。
    通过调用 _fetch_from_browser() 由外部（subagent）注入数据。
    本地运行时通过 _load_cached() 读取缓存。
    """

    def __init__(self, cache_path: str = "data/match_cache.json"):
        self.cache_path = cache_path
        self.fixtures: List[Dict[str, Any]] = []
        self.results: List[Dict[str, Any]] = []
        self.friendly_results: List[Dict[str, Any]] = []
        self.updated_at: Optional[str] = None

    # ── 缓存 ──────────────────────────────────────────────────────────────────

    def save_cache(self) -> None:
        """保存到本地缓存"""
        import os
        os.makedirs(os.path.dirname(self.cache_path), exist_ok=True)
        data = {
            "updated_at": datetime.now().isoformat(),
            "fixtures": self.fixtures,
            "results": self.results,
            "friendly_results": self.friendly_results,
        }
        with open(self.cache_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_cache(self) -> bool:
        """加载本地缓存，返回是否成功"""
        import os
        if not os.path.exists(self.cache_path):
            return False
        try:
            with open(self.cache_path, encoding="utf-8") as f:
                data = json.load(f)
            self.fixtures = data.get("fixtures", [])
            self.results = data.get("results", [])
            self.friendly_results = data.get("friendly_results", [])
            self.updated_at = data.get("updated_at", "")
            return True
        except Exception:
            return False

    # ── 数据解析 ─────────────────────────────────────────────────────────────

    def parse_feeds(self, fixtures_raw: str, results_raw: str, friendly_raw: str = "") -> None:
        """解析 Flashscore 原始数据"""
        parser = FlashscoreParser(fixtures_raw, results_raw, friendly_raw)
        self.fixtures = parser.parse_fixtures()
        self.results = parser.parse_results()
        self.friendly_results = parser.parse_friendlies()
        self.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.save_cache()

    # ── 查询接口 ─────────────────────────────────────────────────────────────

    def get_upcoming(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取未来 N 天内的赛程"""
        now = datetime.now()
        cutoff = now + timedelta(days=days)
        upcoming = []
        for m in self.fixtures:
            try:
                dt = datetime.strptime(m["datetime"], "%Y-%m-%d %H:%M")
                if now <= dt <= cutoff:
                    upcoming.append(m)
            except ValueError:
                continue
        upcoming.sort(key=lambda x: x["datetime"])
        return upcoming[:20]  # 最多20场

    def get_recent_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近赛果"""
        results = sorted(self.results, key=lambda x: x["datetime"], reverse=True)
        return results[:limit]

    def get_friendly_results(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取热身赛赛果"""
        return sorted(self.friendly_results, key=lambda x: x["datetime"], reverse=True)[:limit]

    def get_match_for_team(self, team: str) -> List[Dict[str, Any]]:
        """获取某队所有比赛（赛程+赛果）"""
        team = _team_normalize(team)
        all_matches = []
        for m in self.fixtures + self.results:
            if m["team_a"] == team or m["team_b"] == team:
                all_matches.append(m)
        return sorted(all_matches, key=lambda x: x["datetime"], reverse=True)

    # ── 导出给 mobile_ui.py ─────────────────────────────────────────────────

    def export_for_ui(self) -> Dict[str, Any]:
        """导出适合 JSON 序列化的数据结构"""
        return {
            "updated_at": self.updated_at or "",
            "upcoming": self.get_upcoming(7),
            "recent_results": self.get_recent_results(8),
            "friendly_results": self.get_friendly_results(8),
        }


# ── 公开入口 ──────────────────────────────────────────────────────────────
import os

CACHE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data", "match_cache.json"
)


def load_match_data() -> tuple:
    """
    加载比赛数据（赛程 + 赛果 + 热身赛）。

    优先级：
      1. 读取 data/match_cache.json（由 build_match_cache.py 预先抓取）
      2. 空列表兜底

    返回: (fixtures, results, friendly_results)
    """
    if os.path.exists(CACHE_PATH):
        try:
            with open(CACHE_PATH, encoding="utf-8") as f:
                data = json.load(f)
            return (
                data.get("fixtures", []),
                data.get("results", []),
                data.get("friendly_results", []),
            )
        except (json.JSONDecodeError, IOError):
            pass
    return [], [], []
