import os
import re
import json
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Any
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler
from .stats_handler import StatsHandler
from src.config import load_config
from src.utils.cache_utils import load_league_metadata
from src.utils.path_utils import get_league_weekly_dir, parse_league_id
from src.utils.time_utils import (
    get_pacific_datetime,
    get_fantasy_week,
    get_stats_rule_date,
    tw_date_to_yahoo_date,
    resolve_latest_active_tw_date,
)
from src.services.fantasy_stat_toolkit import (
    AUX_DISPLAY_NAMES,
    AUX_STAT_IDS,
    EXTRA_NBA_ORDER,
    SMALLER_IS_BETTER_STATS,
    STANDARD_NBA_KEYS,
    FantasyStatComparator,
    FantasyStatToolkit,
)
from src.visualizer.flex_builder import build_matchup_comparison_card, build_button_menu_card
from src.visualizer.matchup_flex_renderer import MatchupFlexRenderer
from src.visualizer.processor import is_mlb_pitcher_stat


@dataclass(frozen=True)
class ParsedMatchupCommand:
    is_valid: bool
    nickname: str | None = None
    week_mode: str | None = None
    week_num: int | None = None


@dataclass(frozen=True)
class WeeklyMatchupFileEntry:
    yahoo_date: str
    week: int
    payload: dict


def _get_now_tw() -> datetime:
    return datetime.now(pytz.timezone("Asia/Taipei"))


class LocalMatchupHandler(BaseHandler):
    """
    本地端對戰查詢處理器：
    負責處理 '#對戰'、'#對戰 <玩家名稱>' 與指定週次（如 'W<週數>'、'上週'）指令，
    從本地端 weekly JSON 檔案讀取當週即時對戰或歷史週結算對戰數據，
    並組裝成與原本 API 版本完全一致的 LINE Flex Message 卡片。
    """

    def __init__(
        self,
        comparator: FantasyStatComparator | None = None,
        renderer: MatchupFlexRenderer | None = None,
        stat_toolkit: FantasyStatToolkit | None = None,
    ) -> None:
        super().__init__()
        self.pattern = re.compile(r"^#對戰(?:\s*(.+))?$")
        self._stats_helper = StatsHandler()
        self.stat_toolkit = stat_toolkit or FantasyStatToolkit()
        self.comparator = comparator or FantasyStatComparator(toolkit=self.stat_toolkit)
        self.renderer = renderer or MatchupFlexRenderer(toolkit=self.stat_toolkit)

    @property
    def instruction_desc(self) -> str:
        return """
- #對戰：顯示對戰比分查詢的玩家選單。
- #對戰 <玩家名稱>：查詢特定玩家的本週對戰比分。
- #對戰 <玩家名稱> W<週數>：查詢特定玩家在指定週次的對戰比分（例如：#對戰 小謝 W1）。
- #對戰 <玩家名稱> 上週：查詢特定玩家在上週的對戰比分。
        """

    def parse_command(self, user_text: str) -> ParsedMatchupCommand:
        """
        解析 #對戰 指令。
        - week_mode: None (當週預設) | "last_week" (上週) | "specific_week" (W<n>)
        """
        text = user_text.strip()
        if not text.startswith("#對戰"):
            return ParsedMatchupCommand(is_valid=False)

        rest = text[len("#對戰"):].strip()
        if not rest:
            return ParsedMatchupCommand(is_valid=True)

        # 1. 檢查開頭是否為 W<數字> 或 上週
        m_prefix_w = re.match(r"^[wW](\d+)(?:\s+(.*))?$", rest)
        if m_prefix_w:
            nickname = (m_prefix_w.group(2) or "").strip() or None
            return ParsedMatchupCommand(
                is_valid=True,
                nickname=nickname,
                week_mode="specific_week",
                week_num=int(m_prefix_w.group(1)),
            )

        m_prefix_lw = re.match(r"^上週(?:\s+(.*))?$", rest)
        if m_prefix_lw:
            nickname = (m_prefix_lw.group(1) or "").strip() or None
            return ParsedMatchupCommand(
                is_valid=True,
                nickname=nickname,
                week_mode="last_week",
            )

        # 2. 檢查結尾是否為 W<數字> 或 上週（支援有無空白，例如 "小謝 W1"、"小謝W1"、"小謝 上週"、"小謝上週"）
        m_suffix_w = re.match(r"^(.+?)\s*[wW](\d+)$", rest)
        if m_suffix_w and not self._is_valid_nickname(rest):
            return ParsedMatchupCommand(
                is_valid=True,
                nickname=m_suffix_w.group(1).strip(),
                week_mode="specific_week",
                week_num=int(m_suffix_w.group(2)),
            )

        m_suffix_lw = re.match(r"^(.+?)\s*上週$", rest)
        if m_suffix_lw and not self._is_valid_nickname(rest):
            return ParsedMatchupCommand(
                is_valid=True,
                nickname=m_suffix_lw.group(1).strip(),
                week_mode="last_week",
            )

        return ParsedMatchupCommand(is_valid=True, nickname=rest)

    def _is_valid_nickname(self, nickname: str) -> bool:
        if not nickname:
            return False
        n_lower = nickname.lower()
        mapping = self._load_team_mapping()
        if any(str(v).lower() == n_lower for v in mapping.values()):
            return True

        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if league_id:
            weekly_data = self._load_local_weekly_data(league_id)
            if weekly_data:
                for t in weekly_data.get("team_stats", []):
                    if (
                        str(t.get("name") or "").lower() == n_lower
                        or str(t.get("official_name") or "").lower() == n_lower
                    ):
                        return True
            weekly_dir = get_league_weekly_dir(league_id)
            if os.path.exists(weekly_dir):
                for fn in sorted(os.listdir(weekly_dir), reverse=True):
                    if not fn.endswith(".json"):
                        continue
                    fpath = os.path.join(weekly_dir, fn)
                    try:
                        with open(fpath, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        for t in (data or {}).get("team_stats", []):
                            if (
                                str(t.get("name") or "").lower() == n_lower
                                or str(t.get("official_name") or "").lower() == n_lower
                            ):
                                return True
                    except Exception:
                        continue
        return False

    def can_handle(self, user_text: str) -> bool:
        parsed = self.parse_command(user_text)
        if not parsed.is_valid:
            return False
        if parsed.nickname is None:
            return True
        return self._is_valid_nickname(parsed.nickname)

    def reply_matchup_player_list(
        self,
        event: MessageEvent,
        configuration: Configuration,
        week_suffix: str | None = None,
    ) -> None:
        if not week_suffix:
            self.reply_player_list(event, configuration, is_matchup=True)
            return
        mapping = self._load_team_mapping()
        if not mapping:
            logging.warning("No team mapping found when trying to reply matchup player list.")
            return
        nicknames = []
        for name in mapping.values():
            if name not in nicknames:
                nicknames.append(name)
        title = "⚔️ 對戰比分查詢"
        subtitle = "請點擊下方玩家，將自動搜尋該數據"
        buttons = [(name, f"#對戰 {name} {week_suffix}") for name in nicknames]
        flex_dict = build_button_menu_card(title, subtitle, buttons)
        self.reply_flex(event, configuration, f"{title}選單", flex_dict)

    @staticmethod
    def _get_stat_raw(stats: dict, key: str) -> Any:
        return FantasyStatToolkit.get_stat_raw(stats, key)

    @staticmethod
    def _extract_extra_custom_keys(my_stats: dict, opp_stats: dict) -> list[str]:
        return FantasyStatToolkit.extract_extra_custom_keys(my_stats, opp_stats)

    def to_percent_str(self, val: Any) -> str:
        return self.stat_toolkit.to_percent_str(val)

    def to_val_str(self, val: Any) -> str:
        return self.stat_toolkit.to_val_str(val)

    def compare_stats(self, my_stats: dict, opp_stats: dict, stat_categories: list = None) -> dict:
        """比對數據並統計比分"""
        return self.comparator.compare_stats(my_stats, opp_stats, stat_categories=stat_categories)

    def format_matchup_stats(self, player_info: dict, comp_res: dict, week_str: str, stat_categories: list = None, is_mlb: bool = False) -> dict:
        """組裝 Matchup Flex Message 卡片"""
        return self.renderer.render_matchup_card(
            player_info=player_info,
            comp_res=comp_res,
            week_str=week_str,
            stat_categories=stat_categories,
            is_mlb=is_mlb,
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
        sport, _ = parse_league_id(league_id)
        base_tw_date = preferred_tw_date or get_stats_rule_date(now_tw)
        tw_rule_date = resolve_latest_active_tw_date(
            sport,
            base_tw_date,
            league_id=league_id,
            prefer_existing_local=True,
        )
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

    def _load_weekly_data_for_query(
        self,
        league_id: str,
        config: dict,
        now_tw: datetime,
        week_mode: str | None,
        week_num: int | None,
    ) -> tuple[dict | None, int | None, bool]:
        """
        根據查詢模式載入對應週次的 weekly JSON 數據。
        回傳: (weekly_data, resolved_week, is_historical_silent_miss)
        """
        preferred_tw_date = get_stats_rule_date(now_tw)

        if week_mode is None:
            weekly_data = self._load_local_weekly_data(
                league_id,
                preferred_tw_date=preferred_tw_date,
            )
            if not weekly_data:
                return None, None, False
            week = self._resolve_week_number(league_id, weekly_data, config)
            return weekly_data, week, False

        meta = load_league_metadata(league_id) or {}
        season_start_yahoo, season_end_yahoo, end_week, is_stale_meta = (
            self._stats_helper._get_current_season_bounds(
                league_id=league_id,
                config=config,
                meta=meta,
                now_tw=now_tw,
            )
        )

        weekly_dir = get_league_weekly_dir(league_id)
        if not os.path.exists(weekly_dir):
            return None, None, True

        weekly_entries: list[WeeklyMatchupFileEntry] = []
        for fn in sorted(os.listdir(weekly_dir)):
            if not fn.endswith(".json"):
                continue
            m = re.match(r"^(?:date_)?(\d{4}-\d{2}-\d{2})_weekly\.json$", fn)
            if not m:
                continue
            y_date = m.group(1)
            fpath = os.path.join(weekly_dir, fn)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict) or not data.get("team_stats"):
                    continue
            except Exception:
                continue

            if season_start_yahoo and y_date < season_start_yahoo:
                continue
            if season_end_yahoo and y_date > season_end_yahoo:
                continue

            w = self._stats_helper._resolve_week_for_yahoo_date(
                yahoo_date_str=y_date,
                payload=data,
                season_start_yahoo=season_start_yahoo,
                end_week=end_week,
                meta=meta,
                is_stale_meta=is_stale_meta,
            )
            if w is not None:
                weekly_entries.append(WeeklyMatchupFileEntry(yahoo_date=y_date, week=int(w), payload=data))

        if not weekly_entries:
            return None, None, True

        base_yahoo_date = tw_date_to_yahoo_date(preferred_tw_date)
        current_week = self._stats_helper._resolve_week_for_yahoo_date(
            yahoo_date_str=base_yahoo_date,
            payload=None,
            season_start_yahoo=season_start_yahoo,
            end_week=end_week,
            meta=meta,
            is_stale_meta=is_stale_meta,
        )
        if current_week is None:
            current_week = max(e.week for e in weekly_entries)

        target_week = (current_week - 1) if week_mode == "last_week" else int(week_num)
        if target_week < 1 or (end_week and target_week > end_week):
            return None, None, True

        if target_week == current_week:
            live_data = self._load_local_weekly_data(
                league_id,
                preferred_tw_date=preferred_tw_date,
            )
            if live_data:
                live_w = self._resolve_week_number(league_id, live_data, config)
                if live_w == target_week:
                    return live_data, target_week, False

        matching = [e for e in weekly_entries if e.week == target_week]
        if not matching:
            return None, None, True

        matching.sort(key=lambda x: x.yahoo_date, reverse=True)
        return matching[0].payload, target_week, False

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        try:
            user_text = event.message.text.strip()
            parsed = self.parse_command(user_text)
            if not parsed.is_valid:
                return

            nickname = parsed.nickname or ""
            week_mode = parsed.week_mode
            week_num = parsed.week_num

            if not nickname:
                week_suffix = None
                if week_mode == "specific_week" and week_num is not None:
                    week_suffix = f"W{week_num}"
                elif week_mode == "last_week":
                    week_suffix = "上週"
                self.reply_matchup_player_list(event, configuration, week_suffix=week_suffix)
                return

            config = load_config()
            league_id = config.get("LEAGUE_ID")
            if not league_id:
                logging.error("LEAGUE_ID is not configured in environment variables.")
                return

            team_mapping = self._load_team_mapping()
            now_tw = _get_now_tw()
            weekly_data, week, is_silent_miss = self._load_weekly_data_for_query(
                league_id=league_id,
                config=config,
                now_tw=now_tw,
                week_mode=week_mode,
                week_num=week_num,
            )
            if is_silent_miss:
                logging.info(f"[LocalMatchup] 本地找不到指定歷史週次 ({week_mode}={week_num}) 數據，靜默忽略。")
                return
            if not weekly_data:
                logging.warning(f"[LocalMatchup] 找不到聯盟 {league_id} 的本地 weekly 數據。")
                self.reply_text(event, configuration, "查無當週對戰數據")
                return

            matchups = self._build_matchups_from_weekly_data(weekly_data, team_mapping)
            if not matchups:
                logging.error(f"No matchups found in local data for week {week}.")
                return

            target_matchup = None
            my_is_team1 = True
            n_lower = nickname.lower()
            for m in matchups:
                t1 = m.get("team1", {})
                t2 = m.get("team2", {})
                t1_names = {str(t1.get("name") or "").lower(), str(t1.get("official_name") or "").lower()}
                t2_names = {str(t2.get("name") or "").lower(), str(t2.get("official_name") or "").lower()}
                if n_lower in t1_names:
                    target_matchup = m
                    my_is_team1 = True
                    break
                elif n_lower in t2_names:
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
