import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

from .base_handler import BaseHandler
from .local_matchup_handler import LocalMatchupHandler
from .stats_handler import StatsHandler
from src.config import load_config
from src.utils.cache_utils import load_league_metadata
from src.utils.path_utils import get_league_weekly_dir
from src.utils.time_utils import get_stats_rule_date, tw_date_to_yahoo_date
from src.visualizer.flex_builder import build_all_play_score_card, build_button_menu_card


@dataclass(frozen=True)
class ParsedScoreCommand:
    is_valid: bool
    nickname: str | None = None
    week_mode: str | None = None
    week_num: int | None = None


@dataclass(frozen=True)
class WeeklyFileEntry:
    yahoo_date: str
    week: int
    payload: dict


def _get_now_tw() -> datetime:
    return datetime.now(pytz.timezone("Asia/Taipei"))


class LocalScoreHandler(BaseHandler):
    """
    本地端全聯盟模擬比分查詢處理器：
    負責處理 '#比分'、'#比分 <玩家名稱>' 與指定週次（如 'W<週數>'、'上週'）指令，
    從本地端 weekly JSON 檔案讀取當週即時週數據或歷史週結算數據，
    將單一玩家與聯盟內所有其他玩家逐一進行比項對決，並組裝成 LINE Flex Message 卡片。
    """

    def __init__(self) -> None:
        super().__init__()
        self._matchup_helper = LocalMatchupHandler()
        self._stats_helper = StatsHandler()

    @property
    def instruction_desc(self) -> str:
        return """
- #比分：顯示全聯盟模擬比分查詢的玩家選單。
- #比分 <玩家名稱>：查詢特定玩家本週對上全聯盟所有人的模擬比分。
- #比分 <玩家名稱> W<週數>：查詢特定玩家在指定週次對上全聯盟所有人的模擬比分（例如：#比分 小謝 W5）。
- #比分 <玩家名稱> 上週：查詢特定玩家在上週對上全聯盟所有人的模擬比分。
        """

    def parse_command(self, user_text: str) -> ParsedScoreCommand:
        """
        解析 #比分 指令。
        - week_mode: None (當週預設) | "last_week" (上週) | "specific_week" (W<n>)
        """
        text = user_text.strip()
        if not text.startswith("#比分"):
            return ParsedScoreCommand(is_valid=False)

        rest = text[len("#比分"):].strip()
        if not rest:
            return ParsedScoreCommand(is_valid=True)

        # 1. 檢查開頭是否為 W<數字> 或 上週
        m_prefix_w = re.match(r"^[wW](\d+)(?:\s+(.*))?$", rest)
        if m_prefix_w:
            nickname = (m_prefix_w.group(2) or "").strip() or None
            return ParsedScoreCommand(
                is_valid=True,
                nickname=nickname,
                week_mode="specific_week",
                week_num=int(m_prefix_w.group(1)),
            )

        m_prefix_lw = re.match(r"^上週(?:\s+(.*))?$", rest)
        if m_prefix_lw:
            nickname = (m_prefix_lw.group(1) or "").strip() or None
            return ParsedScoreCommand(
                is_valid=True,
                nickname=nickname,
                week_mode="last_week",
            )

        # 2. 檢查結尾是否為 W<數字> 或 上週（支援有無空白，例如 "小謝 W4"、"小謝W4"、"小謝 上週"、"小謝上週"）
        m_suffix_w = re.match(r"^(.+?)\s*[wW](\d+)$", rest)
        if m_suffix_w and not self._is_valid_nickname(rest):
            return ParsedScoreCommand(
                is_valid=True,
                nickname=m_suffix_w.group(1).strip(),
                week_mode="specific_week",
                week_num=int(m_suffix_w.group(2)),
            )

        m_suffix_lw = re.match(r"^(.+?)\s*上週$", rest)
        if m_suffix_lw and not self._is_valid_nickname(rest):
            return ParsedScoreCommand(
                is_valid=True,
                nickname=m_suffix_lw.group(1).strip(),
                week_mode="last_week",
            )

        return ParsedScoreCommand(is_valid=True, nickname=rest)

    def _is_valid_nickname(self, nickname: str) -> bool:
        if not nickname:
            return False
        n_lower = nickname.lower()
        mapping = self._load_team_mapping()
        if any(str(v).lower() == n_lower for v in mapping.values()):
            return True

        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            return False

        weekly_data = self._matchup_helper._load_local_weekly_data(league_id)
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

    def reply_score_player_list(
        self,
        event: MessageEvent,
        configuration: Configuration,
        week_suffix: str | None = None,
    ) -> None:
        mapping = self._load_team_mapping()
        if not mapping:
            logging.warning("No team mapping found when trying to reply score player list.")
            return

        nicknames = []
        for name in mapping.values():
            if name not in nicknames:
                nicknames.append(name)

        title = "📊 全聯盟比分查詢"
        subtitle = "請點擊下方玩家，將自動搜尋該數據"
        suffix_str = f" {week_suffix}" if week_suffix else ""
        buttons = [(name, f"#比分 {name}{suffix_str}") for name in nicknames]
        flex_dict = build_button_menu_card(title, subtitle, buttons)
        self.reply_flex(event, configuration, f"{title}選單", flex_dict)

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
            weekly_data = self._matchup_helper._load_local_weekly_data(
                league_id,
                preferred_tw_date=preferred_tw_date,
            )
            if not weekly_data:
                return None, None, False
            week = self._matchup_helper._resolve_week_number(league_id, weekly_data, config)
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

        # 掃描本地當季所有 weekly JSON 檔案與其所屬週次
        weekly_entries: list[WeeklyFileEntry] = []
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
                weekly_entries.append(WeeklyFileEntry(yahoo_date=y_date, week=int(w), payload=data))

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

        # 若指定週次即為當前週次，優先按當週即時週數據規則讀取
        if target_week == current_week:
            live_data = self._matchup_helper._load_local_weekly_data(
                league_id,
                preferred_tw_date=preferred_tw_date,
            )
            if live_data:
                live_w = self._matchup_helper._resolve_week_number(league_id, live_data, config)
                if live_w == target_week:
                    return live_data, target_week, False

        matching = [e for e in weekly_entries if e.week == target_week]
        if not matching:
            return None, None, True

        # 取該週日期最新的一天（歷史週結算日，或當週最新一天）
        matching.sort(key=lambda x: x.yahoo_date, reverse=True)
        return matching[0].payload, target_week, False

    def _enrich_teams_and_actual_opponent(
        self,
        weekly_data: dict,
        team_mapping: dict,
        target_nickname: str,
    ) -> tuple[dict | None, list[dict], str | None]:
        raw_teams = weekly_data.get("team_stats", []) or []
        enriched_teams = []
        target_team = None

        for idx, t in enumerate(raw_teams, 1):
            tid = str(t.get("team_id") or idx)
            raw_name = t.get("name") or f"Team {tid}"
            official_name = t.get("official_name") or raw_name
            display_name = team_mapping.get(tid, raw_name)
            team_obj = {
                "team_id": tid,
                "name": display_name,
                "raw_name": raw_name,
                "official_name": official_name,
                "stats": dict(t.get("stats") or {}),
                "order_index": idx,
            }
            enriched_teams.append(team_obj)
            t_names = {
                str(display_name or "").lower(),
                str(raw_name or "").lower(),
                str(official_name or "").lower(),
            }
            if target_team is None and target_nickname.lower() in t_names:
                target_team = team_obj

        if not target_team:
            return None, [], None

        actual_opp_id = None
        matchups = self._matchup_helper._build_matchups_from_weekly_data(weekly_data, team_mapping)
        my_tid = target_team["team_id"]
        for m in matchups:
            t1 = m.get("team1", {})
            t2 = m.get("team2", {})
            if str(t1.get("team_id", "")) == my_tid:
                actual_opp_id = str(t2.get("team_id", ""))
                break
            if str(t2.get("team_id", "")) == my_tid:
                actual_opp_id = str(t1.get("team_id", ""))
                break

        opponents = [t for t in enriched_teams if t["team_id"] != my_tid]
        return target_team, opponents, actual_opp_id

    def build_all_play_comparison(
        self,
        my_team: dict,
        opponents: list[dict],
        actual_opp_id: str | None,
        stat_categories: list | None = None,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        win_rows = []
        tie_rows = []
        loss_rows = []

        for opp in opponents:
            comp_res = self._matchup_helper.compare_stats(
                my_team["stats"],
                opp["stats"],
                stat_categories=stat_categories,
            )
            wins = int(comp_res["wins"])
            losses = int(comp_res["losses"])
            ties = int(comp_res["ties"])
            is_actual = bool(actual_opp_id and opp["team_id"] == actual_opp_id)
            row = {
                "opp_team_id": opp["team_id"],
                "opp_nickname": opp["name"],
                "opp_official": opp["official_name"],
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "is_actual_opponent": is_actual,
                "order_index": opp["order_index"],
            }
            if wins > losses:
                win_rows.append(row)
            elif wins < losses:
                loss_rows.append(row)
            else:
                tie_rows.append(row)

        def sort_key(r: dict) -> tuple:
            return (
                -(r["wins"] - r["losses"]),
                -r["wins"],
                r["losses"],
                not r["is_actual_opponent"],
                r["order_index"],
            )

        win_rows.sort(key=sort_key)
        tie_rows.sort(key=sort_key)
        loss_rows.sort(key=sort_key)
        return win_rows, tie_rows, loss_rows

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        try:
            user_text = event.message.text.strip()
            parsed = self.parse_command(user_text)
            if not parsed.is_valid:
                return

            nickname = parsed.nickname
            week_mode = parsed.week_mode
            week_num = parsed.week_num

            if not nickname:
                week_suffix = None
                if week_mode == "specific_week" and week_num is not None:
                    week_suffix = f"W{week_num}"
                elif week_mode == "last_week":
                    week_suffix = "上週"
                self.reply_score_player_list(event, configuration, week_suffix=week_suffix)
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
                logging.info(f"[LocalScore] 本地找不到指定歷史週次 ({week_mode}={week_num}) 數據，靜默忽略。")
                return
            if not weekly_data:
                logging.warning(f"[LocalScore] 找不到聯盟 {league_id} 的本地 weekly 數據。")
                self.reply_text(event, configuration, "查無當週對戰數據")
                return

            my_team, opponents, actual_opp_id = self._enrich_teams_and_actual_opponent(
                weekly_data,
                team_mapping,
                nickname,
            )
            if not my_team:
                logging.error(f"[LocalScore] No team found for nickname: {nickname}")
                return

            meta = load_league_metadata(league_id) or {}
            stat_categories = meta.get("stat_categories")

            win_rows, tie_rows, loss_rows = self.build_all_play_comparison(
                my_team=my_team,
                opponents=opponents,
                actual_opp_id=actual_opp_id,
                stat_categories=stat_categories,
            )

            player_info = {
                "my_nickname": my_team["name"],
                "my_official": my_team["official_name"],
            }
            flex_dict = build_all_play_score_card(
                title=f"WEEK {week} ALL-PLAY",
                player_info=player_info,
                win_rows=win_rows,
                tie_rows=tie_rows,
                loss_rows=loss_rows,
            )
            alt_text = f"WEEK {week} ALL-PLAY - {my_team['name']}"
            self.reply_flex(event, configuration, alt_text, flex_dict)
        except Exception as e:
            logging.error(f"Failed to execute LocalScoreHandler: {e}", exc_info=True)
            return
