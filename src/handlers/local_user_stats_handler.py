import os
import re
import json
import logging
from datetime import datetime, timedelta
from typing import Any
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler

from src.config import load_config
from src.utils.cache_utils import load_league_metadata
from src.utils.path_utils import get_league_daily_dir, get_league_weekly_dir, parse_league_id
from src.utils.time_utils import (
    get_pacific_date,
    get_fantasy_week,
    get_stats_rule_date,
    tw_date_to_yahoo_date,
    resolve_latest_active_tw_date,
)
from src.visualizer.flex_builder import build_stats_list_card
from src.visualizer.processor import is_mlb_pitcher_stat


STANDARD_NBA_KEYS = {
    "FGM/A", "FGM/FGA", "FG%", "FTM/A", "FTM/FTA", "FT%",
    "3PTM", "3PT", "3PM", "PTS", "REB", "AST", "ST", "STL", "BLK", "TO",
    "Today Player", "Game Player", "GP_PLAYED", "GP_TOTAL", "GP_SORT_KEY",
    "FG", "FT", "FGM", "FGA", "FTM", "FTA",
    "stat_3", "stat_4", "stat_6", "stat_7",
}
EXTRA_NBA_ORDER = ["3PT%", "OREB", "DREB", "A/T", "AST/TO", "A/TO", "DD", "TD"]


def _get_now_tw() -> datetime:
    return datetime.now(pytz.timezone("Asia/Taipei"))


class LocalUserStatsHandler(BaseHandler):
    """
    本地端玩家數據查詢處理器：
    負責處理 '#玩家' 與 '#玩家 <玩家名稱>' 指令（僅支援當日與當週戰績數據），
    從本地端 daily 與 weekly JSON 檔案讀取數據，並組裝成與原本 API 版本完全一致的 LINE Flex Message 卡片。
    """

    def __init__(self) -> None:
        super().__init__()
        self.pattern = re.compile(r"^#玩家(?:\s+(.+))?$")

    @property
    def instruction_desc(self) -> str:
        return """
- #玩家：列出聯賽所有玩家清單。
- #玩家 <玩家名稱>：查詢該玩家目前當日與當週的戰績數據。
        """

    def can_handle(self, user_text: str) -> bool:
        user_text = user_text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return False

        nickname_raw = match.group(1)
        if not nickname_raw:
            return True

        nickname = nickname_raw.strip()
        if not nickname:
            return True

        mapping = self._load_team_mapping()
        if nickname in mapping.values():
            return True

        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if league_id:
            daily_data, _ = self._load_default_local_daily_data(league_id)
            if daily_data:
                for t in daily_data.get("team_stats", []):
                    if t.get("name") == nickname or t.get("official_name") == nickname:
                        return True
        return False

    @staticmethod
    def _get_stat_raw(stats: dict, key: str) -> Any:
        if not isinstance(stats, dict):
            return None
        if key in stats:
            return stats[key]
        if key in ("FGM/A", "FGM/FGA"):
            val = stats.get("FGM/FGA") if "FGM/FGA" in stats else stats.get("FGM/A")
            if val is not None:
                return val
            fgm, fga = stats.get("stat_4"), stats.get("stat_3")
            if fgm is not None and fga is not None:
                return f"{fgm}/{fga}" if str(fga) != "0" else "0/0"
            return None
        if key in ("FTM/A", "FTM/FTA"):
            val = stats.get("FTM/FTA") if "FTM/FTA" in stats else stats.get("FTM/A")
            if val is not None:
                return val
            ftm, fta = stats.get("stat_7"), stats.get("stat_6")
            if ftm is not None and fta is not None:
                return f"{ftm}/{fta}" if str(fta) != "0" else "0/0"
            return None
        if key in ("3PTM", "3PT", "3PM"):
            for k in ("3PTM", "3PT", "3PM"):
                if k in stats:
                    return stats[k]
        if key in ("ST", "STL"):
            for k in ("ST", "STL"):
                if k in stats:
                    return stats[k]
        if key in ("A/T", "AST/TO", "A/TO"):
            for k in ("A/T", "AST/TO", "A/TO"):
                if k in stats:
                    return stats[k]
        return None

    @staticmethod
    def _extract_extra_custom_keys(stats: dict) -> list[str]:
        if not isinstance(stats, dict):
            return []
        extra = []
        seen_canonical = set()
        for k in sorted(stats.keys(), key=lambda x: (0, EXTRA_NBA_ORDER.index(x)) if x in EXTRA_NBA_ORDER else (1, x)):
            if k in STANDARD_NBA_KEYS or str(k).startswith("stat_"):
                continue
            canon = "A/T" if k in ("AST/TO", "A/TO") else k
            if canon not in seen_canonical:
                seen_canonical.add(canon)
                extra.append(canon)
        return extra

    def format_user_stats(
        self,
        player_info: dict,
        daily_stats: dict,
        weekly_stats: dict,
        date_str: str,
        week_str: str,
        stat_categories: list = None,
    ) -> dict:
        def to_percent_str(val):
            try:
                f_val = float(val)
                if f_val == 0.0:
                    return "-"
                return f"{f_val * 100:.1f}%"
            except (ValueError, TypeError):
                return "-"

        def fmt_val(display_name, val):
            """Format a single stat value based on its display name."""
            if val is None or str(val).strip() in ("", "-"):
                return "-"
            if display_name in ("FG%", "FT%") or "%" in display_name:
                return to_percent_str(val)
            if display_name in ("AVG", "OBP", "SLG", "OPS"):
                try:
                    num = float(val)
                    if num == 0:
                        return "-"
                    formatted = f"{num:.3f}"
                    return formatted[1:] if formatted.startswith("0.") else formatted
                except (ValueError, TypeError):
                    return str(val)
            if display_name in ("ERA", "WHIP"):
                try:
                    num = float(val)
                    return f"{num:.2f}"
                except (ValueError, TypeError):
                    return str(val)
            if display_name in ("A/T", "AST/TO", "A/TO"):
                try:
                    num = float(val)
                    if num.is_integer():
                        return str(int(num))
                    return f"{num:.2f}"
                except (ValueError, TypeError):
                    return str(val)
            if "/" in display_name:
                return str(val) if str(val) not in ("0", "None") else "-"
            try:
                return str(int(round(float(val))))
            except (ValueError, TypeError):
                return str(val)

        def build_stat_rows(stats, categories_to_use=None):
            rows = []
            cats = categories_to_use if categories_to_use is not None else stat_categories
            if cats:
                DISPLAY_ALIASES = {"FGM/FGA": "FGM/A", "FTM/FTA": "FTM/A", "3PTM": "3PM"}
                for cat in cats:
                    disp = cat["display_name"]
                    label = DISPLAY_ALIASES.get(disp, disp)
                    val = self._get_stat_raw(stats, disp)
                    rows.append((label, fmt_val(disp, val)))
            else:
                fgm_a = self._get_stat_raw(stats, "FGM/FGA") or "0/0"
                fg_pct = to_percent_str(self._get_stat_raw(stats, "FG%") or "0.0")
                ftm_a = self._get_stat_raw(stats, "FTM/FTA") or "0/0"
                ft_pct = to_percent_str(self._get_stat_raw(stats, "FT%") or "0.0")
                rows = [
                    ("FGM/A", str(fgm_a)),
                    ("FG%", fg_pct),
                    ("FTM/A", str(ftm_a)),
                    ("FT%", ft_pct),
                    ("3PM", str(self._get_stat_raw(stats, "3PTM") or "0")),
                    ("PTS", str(self._get_stat_raw(stats, "PTS") or "0")),
                    ("REB", str(self._get_stat_raw(stats, "REB") or "0")),
                    ("AST", str(self._get_stat_raw(stats, "AST") or "0")),
                    ("STL", str(self._get_stat_raw(stats, "ST") or "0")),
                    ("BLK", str(self._get_stat_raw(stats, "BLK") or "0")),
                    ("TO", str(self._get_stat_raw(stats, "TO") or "0")),
                ]
                for extra_key in self._extract_extra_custom_keys(stats):
                    raw_v = self._get_stat_raw(stats, extra_key)
                    rows.append((extra_key, fmt_val(extra_key, raw_v)))
            return rows

        has_mlb_split = False
        hitter_cats = []
        pitcher_cats = []
        if stat_categories:
            for cat in stat_categories:
                stat_id = cat.get("stat_id", "")
                disp = cat.get("display_name", "")
                if is_mlb_pitcher_stat(stat_id, disp):
                    pitcher_cats.append(cat)
                else:
                    hitter_cats.append(cat)
            if hitter_cats and pitcher_cats:
                has_mlb_split = True

        if has_mlb_split:
            daily_hitter_rows = build_stat_rows(daily_stats, hitter_cats)
            daily_pitcher_rows = build_stat_rows(daily_stats, pitcher_cats)
            weekly_hitter_rows = build_stat_rows(weekly_stats, hitter_cats)
            weekly_pitcher_rows = build_stat_rows(weekly_stats, pitcher_cats)

            sections = [
                {
                    "header": f"{date_str} (Hitter)",
                    "rows": daily_hitter_rows,
                },
                {
                    "header": f"{date_str} (Pitcher)",
                    "rows": daily_pitcher_rows,
                },
                {
                    "header": f"W{week_str} (Hitter)",
                    "rows": weekly_hitter_rows,
                },
                {
                    "header": f"W{week_str} (Pitcher)",
                    "rows": weekly_pitcher_rows,
                },
            ]
        else:
            daily_rows = build_stat_rows(daily_stats)
            weekly_rows = build_stat_rows(weekly_stats)
            sections = [
                {
                    "header": date_str,
                    "rows": daily_rows,
                },
                {
                    "header": f"W{week_str}",
                    "rows": weekly_rows,
                },
            ]

        return build_stats_list_card(
            title=player_info["manager_name"],
            subtitle=player_info["official_name"],
            sections=sections,
        )

    @staticmethod
    def _is_daily_payload_all_zero(data: dict) -> bool:
        """檢查一份 daily JSON 數據是否全聯盟當日出賽人數與計數數據皆為 0（無比賽日殘留檔）。"""
        if not isinstance(data, dict):
            return True
        teams = data.get("team_stats")
        if not isinstance(teams, list) or not teams:
            return True
        counting_keys = (
            "PTS", "REB", "AST", "ST", "STL", "BLK", "TO", "3PTM", "3PT", "3PM", "DD", "TD",
            "R", "H", "HR", "RBI", "SB", "BB", "W", "K", "QS",
        )
        for t in teams:
            st = (t.get("stats") or {}) if isinstance(t, dict) else {}
            try:
                if int(st.get("Today Player") or 0) > 0:
                    return False
            except (ValueError, TypeError):
                pass
            for ck in counting_keys:
                if ck in st:
                    try:
                        if float(st.get(ck) or 0) > 0:
                            return False
                    except (ValueError, TypeError):
                        pass
        return True

    def _load_default_local_daily_data(self, league_id: str) -> tuple[dict | None, str | None]:
        """
        讀取預設當日的本地 daily 數據（依據 #戰績 14:00 切日規則與無比賽日回退至最後一天比賽數據，若無則退回最新一天非全 0 檔案）。
        回傳 (daily_data, display_tw_date_str)，顯示日期與 #戰績 完全同步。
        """
        daily_dir = get_league_daily_dir(league_id)
        if not os.path.exists(daily_dir):
            return None, None

        sport, _ = parse_league_id(league_id)
        now_tw = _get_now_tw()
        tw_rule_date = resolve_latest_active_tw_date(
            sport,
            get_stats_rule_date(now_tw),
            league_id=league_id,
            prefer_existing_local=True,
        )
        yahoo_date = tw_date_to_yahoo_date(tw_rule_date)

        candidates = [
            (tw_rule_date, f"date_{yahoo_date}.json"),
            (tw_rule_date, f"{yahoo_date}.json"),
            (tw_rule_date, f"date_{tw_rule_date}.json"),
            (tw_rule_date, f"{tw_rule_date}.json"),
        ]
        for display_label, fname in candidates:
            fpath = os.path.join(daily_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and data.get("team_stats") and not self._is_daily_payload_all_zero(data):
                        return data, display_label
                except Exception as e:
                    logging.warning(f"[LocalUserStats] 讀取 {fpath} 失敗: {e}")

        # Fallback: 讀取本地最新一天的非全 0 daily 檔案（美西比賽日 + 1 天 = 對應之台灣戰績日期）
        dated_files = []
        for fname in os.listdir(daily_dir):
            if not fname.endswith(".json"):
                continue
            m = re.match(r"^(?:date_)?(\d{4}-\d{2}-\d{2})\.json$", fname)
            if m:
                dated_files.append((m.group(1), os.path.join(daily_dir, fname)))

        dated_files.sort(key=lambda x: x[0], reverse=True)
        for d_str, fpath in dated_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("team_stats") and not self._is_daily_payload_all_zero(data):
                    raw_d = data.get("date") or d_str
                    try:
                        tw_d = (datetime.strptime(raw_d, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
                    except Exception:
                        tw_d = raw_d
                    return data, tw_d
            except Exception:
                continue

        return None, None

    def _resolve_week_for_date(self, league_id: str, date_str: str, daily_data: dict, config: dict) -> int:
        if isinstance(daily_data, dict) and daily_data.get("week") is not None:
            try:
                return int(daily_data["week"])
            except (ValueError, TypeError):
                pass

        meta = load_league_metadata(league_id) or {}
        date_to_week = meta.get("date_to_week") or {}
        if date_str and date_str in date_to_week:
            try:
                return int(date_to_week[date_str])
            except (ValueError, TypeError):
                pass

        start_date = meta.get("start_date") or config.get("SEASON_START_DATE")
        end_date = meta.get("end_date")
        end_week = meta.get("end_week")

        next_season_raw = config.get("NEXT_SEASON_START_DATE") or meta.get("next_season_start_date")
        next_season_date = str(next_season_raw).strip()[:10] if next_season_raw else None
        if date_str and end_date and date_str > end_date:
            if next_season_date and next_season_date > end_date and date_str >= next_season_date:
                start_date = next_season_date
                end_week = None
            else:
                try:
                    days_past_end = (
                        datetime.strptime(date_str, "%Y-%m-%d") - datetime.strptime(end_date, "%Y-%m-%d")
                    ).days
                except Exception:
                    days_past_end = 0
                if days_past_end > 90:
                    daily_dir = get_league_daily_dir(league_id)
                    season_dates = []
                    if os.path.exists(daily_dir):
                        for fn in os.listdir(daily_dir):
                            m = re.match(r"^(?:date_)?(\d{4}-\d{2}-\d{2})\.json$", fn)
                            if m and m.group(1) > end_date:
                                season_dates.append(m.group(1))
                    if season_dates:
                        start_date = min(season_dates)
                        end_week = None
        elif not start_date and next_season_date and date_str and date_str >= next_season_date:
            start_date = next_season_date

        target_week = 1
        if start_date and date_str:
            try:
                target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(date_str, "%Y-%m-%d"))
                target_week = get_fantasy_week(start_date, target_dt)
            except Exception:
                try:
                    target_week = get_fantasy_week(start_date)
                except Exception:
                    target_week = 1

        if end_week and target_week > int(end_week):
            target_week = int(end_week)
        return max(1, int(target_week))

    def _load_matching_weekly_data(
        self,
        league_id: str,
        daily_date: str,
        target_week: int,
        config: dict,
    ) -> dict | None:
        weekly_dir = get_league_weekly_dir(league_id)
        if not os.path.exists(weekly_dir):
            return None

        direct_candidates = []
        if daily_date:
            yahoo_equiv = tw_date_to_yahoo_date(daily_date)
            direct_candidates.extend([
                f"date_{daily_date}_weekly.json",
                f"{daily_date}_weekly.json",
                f"date_{yahoo_equiv}_weekly.json",
                f"{yahoo_equiv}_weekly.json",
            ])
        if target_week:
            direct_candidates.append(f"week_{target_week}.json")

        for fname in direct_candidates:
            fpath = os.path.join(weekly_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and data.get("team_stats"):
                        return data
                except Exception:
                    continue

        # 搜尋同一個 target_week 的最新 weekly 檔案，或退回最新 weekly 檔案
        dated_files = []
        for fname in os.listdir(weekly_dir):
            if not fname.endswith(".json"):
                continue
            m = re.match(r"^date_(\d{4}-\d{2}-\d{2})_weekly\.json$", fname)
            if m:
                dated_files.append((m.group(1), os.path.join(weekly_dir, fname)))

        dated_files.sort(key=lambda x: x[0], reverse=True)
        latest_valid = None
        for d_str, fpath in dated_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict) or not data.get("team_stats"):
                    continue
                if latest_valid is None:
                    latest_valid = data
                file_week = self._resolve_week_for_date(league_id, d_str, data, config)
                if target_week and file_week == target_week:
                    return data
            except Exception:
                continue

        return latest_valid

    @staticmethod
    def _find_team_entry(data: dict | None, team_id: str | None, nickname: str, mapping: dict) -> dict | None:
        if not isinstance(data, dict):
            return None
        teams = data.get("team_stats") or []
        if team_id:
            for t in teams:
                if str(t.get("team_id", "")) == str(team_id):
                    return t
        for t in teams:
            t_id = str(t.get("team_id", ""))
            mapped_name = mapping.get(t_id)
            if nickname in (mapped_name, t.get("name"), t.get("official_name")):
                return t
        return None

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        try:
            user_text = event.message.text.strip()
            match = self.pattern.match(user_text)
            if not match:
                return

            nickname_raw = match.group(1)
            if not nickname_raw or not nickname_raw.strip():
                self.reply_player_list(event, configuration, is_matchup=False)
                return

            nickname = nickname_raw.strip()
            mapping = self._load_team_mapping()

            team_id = None
            for t_id, name in mapping.items():
                if name == nickname:
                    team_id = str(t_id)
                    break

            config = load_config()
            league_id = config.get("LEAGUE_ID")
            if not league_id:
                logging.error("LEAGUE_ID is not configured in environment variables.")
                return

            meta = load_league_metadata(league_id) or {}

            daily_data, resolved_date = self._load_default_local_daily_data(league_id)
            if not daily_data:
                self.reply_text(event, configuration, "查無當天數據")
                return

            daily_team = self._find_team_entry(daily_data, team_id, nickname, mapping)
            if not daily_team:
                logging.warning(f"[LocalUserStats] 在本地 daily 數據中找不到玩家: {nickname}")
                return

            if not team_id and daily_team.get("team_id"):
                team_id = str(daily_team["team_id"])

            file_date = daily_data.get("date") or resolved_date
            target_week = self._resolve_week_for_date(league_id, file_date, daily_data, config)
            weekly_data = self._load_matching_weekly_data(league_id, file_date, target_week, config)

            if weekly_data and weekly_data.get("week") is not None:
                try:
                    target_week = int(weekly_data["week"])
                except (ValueError, TypeError):
                    pass

            weekly_team = self._find_team_entry(weekly_data, team_id, nickname, mapping) if weekly_data else None
            daily_stats = dict(daily_team.get("stats") or {})
            weekly_stats = dict(weekly_team.get("stats") or {}) if weekly_team else dict(daily_stats)

            official_name = (
                daily_team.get("official_name")
                or (weekly_team.get("official_name") if weekly_team else None)
                or daily_team.get("name")
                or nickname
            )

            player_info = {
                "manager_name": nickname,
                "official_name": official_name,
            }

            display_date = resolved_date or file_date or ""
            flex_dict = self.format_user_stats(
                player_info,
                daily_stats,
                weekly_stats,
                display_date,
                str(target_week),
                stat_categories=meta.get("stat_categories"),
            )
            self.reply_flex(event, configuration, f"玩家 {nickname} 數據統計", flex_dict)
        except Exception as e:
            logging.error(f"Failed to execute LocalUserStatsHandler: {e}", exc_info=True)
            return
