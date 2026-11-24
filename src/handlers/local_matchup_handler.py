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
from src.config import load_config
from src.repositories.local_league_data_repository import LocalLeagueDataRepository, WeeklyFileEntry as WeeklyMatchupFileEntry
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
        repository: LocalLeagueDataRepository | None = None,
        comparator: FantasyStatComparator | None = None,
        renderer: MatchupFlexRenderer | None = None,
        stat_toolkit: FantasyStatToolkit | None = None,
    ) -> None:
        super().__init__()
        self.pattern = re.compile(r"^#對戰(?:\s*(.+))?$")
        self.repository = repository or LocalLeagueDataRepository()
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
        return self.repository.load_local_weekly_data(
            league_id=league_id,
            preferred_tw_date=preferred_tw_date,
            now_tw=_get_now_tw(),
        )

    def _resolve_week_number(self, league_id: str, weekly_data: dict, config: dict) -> int:
        return self.repository.resolve_week_number(
            league_id=league_id,
            weekly_data=weekly_data,
            config=config,
            meta=load_league_metadata(league_id) or {},
        )

    def _build_matchups_from_weekly_data(self, weekly_data: dict, team_mapping: dict) -> list[dict]:
        return self.repository.build_matchups_from_weekly_data(weekly_data, team_mapping)

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
        return self.repository.load_weekly_data_for_query(
            league_id=league_id,
            config=config,
            now_tw=now_tw,
            week_mode=week_mode,
            week_num=week_num,
            meta=load_league_metadata(league_id) or {},
        )

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
