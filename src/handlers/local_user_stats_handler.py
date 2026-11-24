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
from src.repositories.local_league_data_repository import LocalLeagueDataRepository
from src.utils.cache_utils import load_league_metadata
from src.utils.path_utils import get_league_daily_dir, get_league_weekly_dir, parse_league_id
from src.utils.time_utils import (
    get_pacific_date,
    get_fantasy_week,
    get_stats_rule_date,
    tw_date_to_yahoo_date,
    resolve_latest_active_tw_date,
)
from src.services.fantasy_stat_toolkit import (
    EXTRA_NBA_ORDER,
    STANDARD_NBA_KEYS,
    FantasyStatToolkit,
)
from src.visualizer.flex_builder import build_stats_list_card
from src.visualizer.processor import is_mlb_pitcher_stat
from src.visualizer.user_stats_flex_renderer import UserStatsFlexRenderer


def _get_now_tw() -> datetime:
    return datetime.now(pytz.timezone("Asia/Taipei"))


class LocalUserStatsHandler(BaseHandler):
    """
    本地端玩家數據查詢處理器：
    負責處理 '#玩家' 與 '#玩家 <玩家名稱>' 指令（僅支援當日與當週戰績數據），
    從本地端 daily 與 weekly JSON 檔案讀取數據，並組裝成與原本 API 版本完全一致的 LINE Flex Message 卡片。
    """

    def __init__(
        self,
        repository: LocalLeagueDataRepository | None = None,
        renderer: UserStatsFlexRenderer | None = None,
        stat_toolkit: FantasyStatToolkit | None = None,
    ) -> None:
        super().__init__()
        self.pattern = re.compile(r"^#玩家(?:\s+(.+))?$")
        self.repository = repository or LocalLeagueDataRepository()
        self.stat_toolkit = stat_toolkit or FantasyStatToolkit()
        self.renderer = renderer or UserStatsFlexRenderer(toolkit=self.stat_toolkit)

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
        return FantasyStatToolkit.get_stat_raw(stats, key)

    @staticmethod
    def _extract_extra_custom_keys(stats: dict) -> list[str]:
        return FantasyStatToolkit.extract_extra_custom_keys(stats)

    def format_user_stats(
        self,
        player_info: dict,
        daily_stats: dict,
        weekly_stats: dict,
        date_str: str,
        week_str: str,
        stat_categories: list = None,
    ) -> dict:
        return self.renderer.render_user_stats_card(
            player_info=player_info,
            daily_stats=daily_stats,
            weekly_stats=weekly_stats,
            date_str=date_str,
            week_str=week_str,
            stat_categories=stat_categories,
        )

    @staticmethod
    def _is_daily_payload_all_zero(data: dict) -> bool:
        """檢查一份 daily JSON 數據是否全聯盟當日出賽人數與計數數據皆為 0（無比賽日殘留檔）。"""
        return LocalLeagueDataRepository.is_daily_payload_all_zero(data)

    def _load_default_local_daily_data(self, league_id: str) -> tuple[dict | None, str | None]:
        """
        讀取預設當日的本地 daily 數據（依據 #戰績 14:00 切日規則與無比賽日回退至最後一天比賽數據，若無則退回最新一天非全 0 檔案）。
        回傳 (daily_data, display_tw_date_str)，顯示日期與 #戰績 完全同步。
        """
        return self.repository.load_default_local_daily_data(league_id, now_tw=_get_now_tw())

    def _resolve_week_for_date(self, league_id: str, date_str: str, daily_data: dict, config: dict) -> int:
        return self.repository.resolve_week_for_date(
            league_id=league_id,
            date_str=date_str,
            daily_data=daily_data,
            config=config,
            meta=load_league_metadata(league_id) or {},
        )

    def _load_matching_weekly_data(
        self,
        league_id: str,
        daily_date: str,
        target_week: int,
        config: dict,
    ) -> dict | None:
        return self.repository.load_matching_weekly_data(
            league_id=league_id,
            daily_date=daily_date,
            target_week=target_week,
            config=config,
            meta=load_league_metadata(league_id) or {},
        )

    @staticmethod
    def _find_team_entry(data: dict | None, team_id: str | None, nickname: str, mapping: dict) -> dict | None:
        return LocalLeagueDataRepository.find_team_entry(data, team_id, nickname, mapping)

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
