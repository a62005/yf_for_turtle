import os
import re
import json
import logging
from datetime import datetime
from typing import Any
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler
from src.config import load_config
from src.utils.cache_utils import load_league_metadata
from src.utils.path_utils import get_league_weekly_dir, parse_league_id
from src.utils.time_utils import (
    get_pacific_datetime,
    get_fantasy_week,
    get_stats_rule_date,
    tw_date_to_yahoo_date,
)
from src.visualizer.flex_builder import build_matchup_comparison_card
from src.visualizer.processor import is_mlb_pitcher_stat


AUX_DISPLAY_NAMES = {"FGM/A", "FGM/FGA", "FTM/A", "FTM/FTA", "H/AB"}
AUX_STAT_IDS = {"9004003", "9007006", "60"}
STANDARD_NBA_KEYS = {
    "FGM/A", "FGM/FGA", "FG%", "FTM/A", "FTM/FTA", "FT%",
    "3PTM", "3PT", "3PM", "PTS", "REB", "AST", "ST", "STL", "BLK", "TO",
    "Today Player", "Game Player", "GP_PLAYED", "GP_TOTAL", "GP_SORT_KEY",
    "FG", "FT", "FGM", "FGA", "FTM", "FTA",
    "stat_3", "stat_4", "stat_6", "stat_7",
}
EXTRA_NBA_ORDER = ["3PT%", "OREB", "DREB", "A/T", "AST/TO", "A/TO", "DD", "TD"]
SMALLER_IS_BETTER_STATS = {"TO", "ERA", "WHIP", "L", "BB/9"}


def _get_now_tw() -> datetime:
    return datetime.now(pytz.timezone("Asia/Taipei"))


class LocalMatchupHandler(BaseHandler):
    """
    本地端對戰查詢處理器：
    負責處理 '#對戰' 與 '#對戰 <玩家名稱>' 指令，從本地端 weekly JSON 檔案讀取對戰數據，
    並組裝成與原本 API 版本完全一致的 LINE Flex Message 卡片。
    """

    def __init__(self) -> None:
        super().__init__()
        self.pattern = re.compile(r"^#對戰(?:\s+(.+))?$")

    @property
    def instruction_desc(self) -> str:
        return """
- #對戰：顯示對戰比分查詢的玩家選單。
- #對戰 <玩家名稱>：查詢特定玩家的本週對戰比分。
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

        # 若 team_mapping 尚未包含該名稱，嘗試檢查本地週數據中的隊伍名稱
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if league_id:
            weekly_data = self._load_local_weekly_data(league_id)
            if weekly_data:
                for t in weekly_data.get("team_stats", []):
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
    def _extract_extra_custom_keys(my_stats: dict, opp_stats: dict) -> list[str]:
        all_keys = set()
        if isinstance(my_stats, dict):
            all_keys.update(my_stats.keys())
        if isinstance(opp_stats, dict):
            all_keys.update(opp_stats.keys())

        extra = []
        seen_canonical = set()
        for k in sorted(all_keys, key=lambda x: (0, EXTRA_NBA_ORDER.index(x)) if x in EXTRA_NBA_ORDER else (1, x)):
            if k in STANDARD_NBA_KEYS or str(k).startswith("stat_"):
                continue
            canon = "A/T" if k in ("AST/TO", "A/TO") else k
            if canon not in seen_canonical:
                seen_canonical.add(canon)
                extra.append(canon)
        return extra

    def to_percent_str(self, val: Any) -> str:
        try:
            f_val = float(val)
            if f_val == 0.0:
                return "-"
            return f"{f_val * 100:.1f}%"
        except (ValueError, TypeError):
            return "-"

    def to_val_str(self, val: Any) -> str:
        if val is None:
            return "-"
        val_str = str(val).strip()
        if val_str == "" or val_str == "-":
            return "-"

        if "/" in val_str:
            parts = val_str.split("/")
            if len(parts) == 2:
                try:
                    float(parts[0].strip())
                    float(parts[1].strip())
                    return val_str
                except ValueError:
                    return "-"

        try:
            f_val = float(val_str)
            if f_val == 0.0:
                return "0"
            if f_val.is_integer():
                return str(int(f_val))
            return val_str
        except ValueError:
            return "-"

    def compare_stats(self, my_stats: dict, opp_stats: dict, stat_categories: list = None) -> dict:
        """比對數據並統計比分"""
        if not stat_categories:
            cats_to_compare = [
                ("FG%", True), ("FT%", True), ("3PTM", True), ("PTS", True),
                ("REB", True), ("AST", True), ("ST", True), ("BLK", True), ("TO", False)
            ]
            for extra_key in self._extract_extra_custom_keys(my_stats, opp_stats):
                cats_to_compare.append((extra_key, extra_key not in SMALLER_IS_BETTER_STATS))

            wins, losses, ties = 0, 0, 0
            details = {}

            details["FGM/A"] = {
                "my_val": self.to_val_str(self._get_stat_raw(my_stats, "FGM/FGA")),
                "opp_val": self.to_val_str(self._get_stat_raw(opp_stats, "FGM/FGA"))
            }
            details["FTM/A"] = {
                "my_val": self.to_val_str(self._get_stat_raw(my_stats, "FTM/FTA")),
                "opp_val": self.to_val_str(self._get_stat_raw(opp_stats, "FTM/FTA"))
            }

            for cat, is_larger_better in cats_to_compare:
                my_raw = self._get_stat_raw(my_stats, cat)
                opp_raw = self._get_stat_raw(opp_stats, cat)

                if "%" in cat:
                    my_val_str = self.to_percent_str(my_raw)
                    opp_val_str = self.to_percent_str(opp_raw)
                else:
                    my_val_str = self.to_val_str(my_raw)
                    opp_val_str = self.to_val_str(opp_raw)

                try:
                    my_num = float(my_raw) if my_raw is not None else 0.0
                except (ValueError, TypeError):
                    my_num = 0.0
                try:
                    opp_num = float(opp_raw) if opp_raw is not None else 0.0
                except (ValueError, TypeError):
                    opp_num = 0.0

                if my_num == opp_num:
                    status = "tie"
                    ties += 1
                elif is_larger_better:
                    if my_num > opp_num:
                        status = "my_win"
                        wins += 1
                    else:
                        status = "opp_win"
                        losses += 1
                else:
                    if my_num < opp_num:
                        status = "my_win"
                        wins += 1
                    else:
                        status = "opp_win"
                        losses += 1

                details[cat] = {
                    "status": status,
                    "my_val": my_val_str,
                    "opp_val": opp_val_str
                }

            return {
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "details": details
            }
        else:
            wins, losses, ties = 0, 0, 0
            details = {}
            for cat in stat_categories:
                disp = cat["display_name"]
                sort_order = cat.get("sort_order")
                stat_id = str(cat.get("stat_id", ""))
                is_only_display = (
                    (sort_order is None)
                    or (sort_order not in [0, 1])
                    or (disp in AUX_DISPLAY_NAMES)
                    or (stat_id in AUX_STAT_IDS)
                )

                my_raw = self._get_stat_raw(my_stats, disp)
                opp_raw = self._get_stat_raw(opp_stats, disp)

                if "%" in disp:
                    my_val_str = self.to_percent_str(my_raw)
                    opp_val_str = self.to_percent_str(opp_raw)
                else:
                    my_val_str = self.to_val_str(my_raw)
                    opp_val_str = self.to_val_str(opp_raw)

                if is_only_display:
                    details[disp] = {
                        "my_val": my_val_str,
                        "opp_val": opp_val_str
                    }
                    continue

                is_larger_better = (sort_order == 1)

                try:
                    my_num = float(my_raw) if my_raw is not None else 0.0
                except (ValueError, TypeError):
                    my_num = 0.0
                try:
                    opp_num = float(opp_raw) if opp_raw is not None else 0.0
                except (ValueError, TypeError):
                    opp_num = 0.0

                if my_num == opp_num:
                    status = "tie"
                    ties += 1
                elif is_larger_better:
                    if my_num > opp_num:
                        status = "my_win"
                        wins += 1
                    else:
                        status = "opp_win"
                        losses += 1
                else:
                    if my_num < opp_num:
                        status = "my_win"
                        wins += 1
                    else:
                        status = "opp_win"
                        losses += 1

                details[disp] = {
                    "status": status,
                    "my_val": my_val_str,
                    "opp_val": opp_val_str
                }

            return {
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "details": details
            }

    def format_matchup_stats(self, player_info: dict, comp_res: dict, week_str: str, stat_categories: list = None, is_mlb: bool = False) -> dict:
        """組裝 Matchup Flex Message 卡片"""
        details = comp_res["details"]
        wins = comp_res["wins"]
        losses = comp_res["losses"]

        subtitle_dict = {
            "my_nickname": player_info["my_nickname"],
            "my_official": player_info["my_official"],
            "opp_nickname": player_info["opp_nickname"],
            "opp_official": player_info["opp_official"],
            "wins": wins,
            "losses": losses
        }

        if stat_categories:
            DISPLAY_ALIASES = {"FGM/FGA": "FGM/A", "FTM/FTA": "FTM/A"}
            comparison_rows = []
            for cat in stat_categories:
                disp = cat["display_name"]
                label = DISPLAY_ALIASES.get(disp, disp)

                my_val = details[disp]["my_val"]
                opp_val = details[disp]["opp_val"]
                status = details[disp].get("status")

                sort_order = cat.get("sort_order")
                stat_id = str(cat.get("stat_id", ""))
                is_aux = (
                    (sort_order is None)
                    or (sort_order not in [0, 1])
                    or (disp in AUX_DISPLAY_NAMES)
                    or (stat_id in AUX_STAT_IDS)
                )

                is_pitcher = is_mlb_pitcher_stat(stat_id, disp)
                comparison_rows.append((label, my_val, opp_val, status, is_aux, is_pitcher))
        else:
            comparison_rows = [
                ("FGM/A", details["FGM/A"]["my_val"], details["FGM/A"]["opp_val"], None, True, False),
                ("FG%", details["FG%"]["my_val"], details["FG%"]["opp_val"], details["FG%"]["status"], False, False),
                ("FTM/A", details["FTM/A"]["my_val"], details["FTM/A"]["opp_val"], None, True, False),
                ("FT%", details["FT%"]["my_val"], details["FT%"]["opp_val"], details["FT%"]["status"], False, False),
                ("3PTM", details["3PTM"]["my_val"], details["3PTM"]["opp_val"], details["3PTM"]["status"], False, False),
                ("PTS", details["PTS"]["my_val"], details["PTS"]["opp_val"], details["PTS"]["status"], False, False),
                ("REB", details["REB"]["my_val"], details["REB"]["opp_val"], details["REB"]["status"], False, False),
                ("AST", details["AST"]["my_val"], details["AST"]["opp_val"], details["AST"]["status"], False, False),
                ("ST", details["ST"]["my_val"], details["ST"]["opp_val"], details["ST"]["status"], False, False),
                ("BLK", details["BLK"]["my_val"], details["BLK"]["opp_val"], details["BLK"]["status"], False, False),
                ("TO", details["TO"]["my_val"], details["TO"]["opp_val"], details["TO"]["status"], False, False),
            ]
            standard_row_keys = {"FGM/A", "FG%", "FTM/A", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO"}
            for k, v in details.items():
                if k not in standard_row_keys:
                    comparison_rows.append((k, v["my_val"], v["opp_val"], v.get("status"), "status" not in v, False))

        return build_matchup_comparison_card(
            title=f"WEEK {week_str} MATCHUP",
            subtitle=subtitle_dict,
            comparison_rows=comparison_rows,
            is_mlb=is_mlb
        )

    def _load_local_weekly_data(self, league_id: str, preferred_tw_date: str = None) -> dict | None:
        """
        讀取本地端 weekly 資料夾中的當週戰績數據：
        優先依據 #戰績 時間規則尋找對應美西日期的 date_<YYYY-MM-DD>_weekly.json，
        若該日檔案尚未產生，則自動退回讀取本地最新一天的 weekly JSON 檔案。
        """
        weekly_dir = get_league_weekly_dir(league_id)
        if not os.path.exists(weekly_dir):
            return None

        now_tw = _get_now_tw()
        tw_rule_date = preferred_tw_date or get_stats_rule_date(now_tw)
        yahoo_date = tw_date_to_yahoo_date(tw_rule_date)

        candidate_names = [
            f"date_{yahoo_date}_weekly.json",
            f"date_{tw_rule_date}_weekly.json",
            f"{yahoo_date}_weekly.json",
            f"{tw_rule_date}_weekly.json",
        ]
        for fname in candidate_names:
            fpath = os.path.join(weekly_dir, fname)
            if os.path.exists(fpath):
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict) and data.get("team_stats"):
                        return data
                except Exception as e:
                    logging.warning(f"[LocalMatchup] 讀取 {fpath} 失敗: {e}")

        # Fallback: 找本地最新一天的 date_*_weekly.json
        dated_files = []
        week_files = []
        for fname in os.listdir(weekly_dir):
            if not fname.endswith(".json"):
                continue
            m = re.match(r"^date_(\d{4}-\d{2}-\d{2})_weekly\.json$", fname)
            if m:
                dated_files.append((m.group(1), os.path.join(weekly_dir, fname)))
                continue
            m_w = re.match(r"^week_(\d+)\.json$", fname)
            if m_w:
                week_files.append((int(m_w.group(1)), os.path.join(weekly_dir, fname)))

        dated_files.sort(key=lambda x: x[0], reverse=True)
        for _, fpath in dated_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("team_stats"):
                    return data
            except Exception:
                continue

        week_files.sort(key=lambda x: x[0], reverse=True)
        for w_num, fpath in week_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict) and data.get("team_stats"):
                    data.setdefault("week", w_num)
                    return data
            except Exception:
                continue

        return None

    def _resolve_week_number(self, league_id: str, weekly_data: dict, config: dict) -> int:
        if isinstance(weekly_data, dict) and weekly_data.get("week") is not None:
            try:
                return int(weekly_data["week"])
            except (ValueError, TypeError):
                pass

        meta = load_league_metadata(league_id) or {}
        data_date = (weekly_data or {}).get("date")
        date_to_week = meta.get("date_to_week") or {}
        if data_date and data_date in date_to_week:
            try:
                return int(date_to_week[data_date])
            except (ValueError, TypeError):
                pass

        start_date = meta.get("start_date") or config.get("SEASON_START_DATE")
        end_date = meta.get("end_date")
        end_week = meta.get("end_week") or 24

        current_dt = get_pacific_datetime()
        if data_date:
            try:
                current_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(data_date, "%Y-%m-%d"))
            except Exception:
                pass

        current_date_str = current_dt.strftime("%Y-%m-%d")

        # 若 metadata.json 仍停留在上一季（例如 end_date 為 2026-04-05，但目前資料日期已是 2026-10 之後的新球季），
        # 優先採用 NEXT_SEASON_START_DATE 或當季最早的本地檔案日期計算新球季週數，避免誤鎖在上一季的 end_week
        next_season_raw = config.get("NEXT_SEASON_START_DATE") or meta.get("next_season_start_date")
        next_season_date = str(next_season_raw).strip()[:10] if next_season_raw else None
        if end_date and current_date_str > end_date:
            if next_season_date and next_season_date > end_date and current_date_str >= next_season_date:
                start_date = next_season_date
                end_date = None
                end_week = None
            else:
                try:
                    days_past_end = (
                        datetime.strptime(current_date_str, "%Y-%m-%d") - datetime.strptime(end_date, "%Y-%m-%d")
                    ).days
                except Exception:
                    days_past_end = 0
                if days_past_end > 90:
                    weekly_dir = get_league_weekly_dir(league_id)
                    season_dates = []
                    if os.path.exists(weekly_dir):
                        for fn in os.listdir(weekly_dir):
                            m = re.match(r"^date_(\d{4}-\d{2}-\d{2})_weekly\.json$", fn)
                            if m and m.group(1) > end_date:
                                season_dates.append(m.group(1))
                    if season_dates:
                        start_date = min(season_dates)
                        end_date = None
                        end_week = None
                    else:
                        return int(end_week)
                else:
                    return int(end_week)
        elif not start_date and next_season_date and current_date_str >= next_season_date:
            start_date = next_season_date

        if start_date:
            try:
                week = get_fantasy_week(start_date, current_dt)
                if end_week and week > int(end_week):
                    week = int(end_week)
                return max(1, week)
            except Exception:
                pass

        return 1

    def _build_matchups_from_weekly_data(self, weekly_data: dict, team_mapping: dict) -> list[dict]:
        raw_teams = weekly_data.get("team_stats", []) or []
        enriched_teams = []
        team_by_id = {}

        for idx, t in enumerate(raw_teams, 1):
            tid = str(t.get("team_id") or idx)
            raw_name = t.get("name") or f"Team {tid}"
            official_name = t.get("official_name") or raw_name
            display_name = team_mapping.get(tid, raw_name)
            team_obj = {
                "team_id": tid,
                "name": display_name,
                "official_name": official_name,
                "stats": dict(t.get("stats") or {}),
            }
            enriched_teams.append(team_obj)
            team_by_id[tid] = team_obj

        matchups = []
        explicit_matchups = weekly_data.get("matchups")
        if isinstance(explicit_matchups, list) and explicit_matchups:
            for m in explicit_matchups:
                if not isinstance(m, dict):
                    continue
                if "team1" in m and "team2" in m and isinstance(m["team1"], dict) and isinstance(m["team2"], dict):
                    t1_raw, t2_raw = m["team1"], m["team2"]
                    t1_id = str(t1_raw.get("team_id", ""))
                    t2_id = str(t2_raw.get("team_id", ""))
                    t1 = team_by_id.get(t1_id) or {
                        "team_id": t1_id,
                        "name": team_mapping.get(t1_id, t1_raw.get("name", "Unknown")),
                        "official_name": t1_raw.get("official_name") or t1_raw.get("name", "Unknown"),
                        "stats": dict(t1_raw.get("stats") or {}),
                    }
                    t2 = team_by_id.get(t2_id) or {
                        "team_id": t2_id,
                        "name": team_mapping.get(t2_id, t2_raw.get("name", "Unknown")),
                        "official_name": t2_raw.get("official_name") or t2_raw.get("name", "Unknown"),
                        "stats": dict(t2_raw.get("stats") or {}),
                    }
                    matchups.append({"team1": t1, "team2": t2})
                else:
                    t1_id = str(m.get("team1_id", ""))
                    t2_id = str(m.get("team2_id", ""))
                    if t1_id in team_by_id and t2_id in team_by_id:
                        matchups.append({"team1": team_by_id[t1_id], "team2": team_by_id[t2_id]})

        if matchups:
            return matchups

        # Fallback: 依 team_stats 陣列順序兩兩配對
        for i in range(0, len(enriched_teams) - 1, 2):
            matchups.append({
                "team1": enriched_teams[i],
                "team2": enriched_teams[i + 1],
            })
        return matchups

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        try:
            user_text = event.message.text.strip()
            match = self.pattern.match(user_text)
            if not match:
                return

            nickname_raw = match.group(1)
            nickname = nickname_raw.strip() if nickname_raw else ""

            if not nickname:
                self.reply_player_list(event, configuration, is_matchup=True)
                return

            config = load_config()
            league_id = config.get("LEAGUE_ID")
            if not league_id:
                logging.error("LEAGUE_ID is not configured in environment variables.")
                return

            team_mapping = self._load_team_mapping()
            weekly_data = self._load_local_weekly_data(league_id)
            if not weekly_data:
                logging.warning(f"[LocalMatchup] 找不到聯盟 {league_id} 的本地 weekly 數據。")
                self.reply_text(event, configuration, "查無當週對戰數據")
                return

            week = self._resolve_week_number(league_id, weekly_data, config)
            matchups = self._build_matchups_from_weekly_data(weekly_data, team_mapping)
            if not matchups:
                logging.error(f"No matchups found in local data for week {week}.")
                return

            target_matchup = None
            my_is_team1 = True
            for m in matchups:
                t1 = m.get("team1", {})
                t2 = m.get("team2", {})
                if nickname in (t1.get("name"), t1.get("official_name")):
                    target_matchup = m
                    my_is_team1 = True
                    break
                elif nickname in (t2.get("name"), t2.get("official_name")):
                    target_matchup = m
                    my_is_team1 = False
                    break

            if not target_matchup:
                logging.error(f"No matchup found for nickname: {nickname}")
                return

            if my_is_team1:
                my_team = target_matchup["team1"]
                opp_team = target_matchup["team2"]
            else:
                my_team = target_matchup["team2"]
                opp_team = target_matchup["team1"]

            player_info = {
                "my_nickname": my_team["name"],
                "my_official": my_team["official_name"],
                "opp_nickname": opp_team["name"],
                "opp_official": opp_team["official_name"],
            }

            sport, _ = parse_league_id(league_id)
            is_mlb = (sport == "mlb")

            meta = load_league_metadata(league_id) or {}
            stat_categories = meta.get("stat_categories")

            comp_res = self.compare_stats(my_team["stats"], opp_team["stats"], stat_categories=stat_categories)
            flex_dict = self.format_matchup_stats(
                player_info,
                comp_res,
                str(week),
                stat_categories=stat_categories,
                is_mlb=is_mlb
            )

            alt_text = f"WEEK {week} MATCHUP - {player_info['my_nickname']} vs {player_info['opp_nickname']}"
            self.reply_flex(event, configuration, alt_text, flex_dict)
        except Exception as e:
            logging.error(f"Failed to execute LocalMatchupHandler: {e}", exc_info=True)
            return
