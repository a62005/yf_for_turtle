import re
import os
import json
import logging
from datetime import datetime, timedelta
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, Configuration
from .base_handler import BaseHandler

from src.config import load_config
from src.cache_utils import load_league_metadata
from src.fetcher import YahooFantasyFetcher
from src.utils.time_utils import get_fantasy_week

class UserStatsHandler(BaseHandler):
    def __init__(self):
        self.pattern = re.compile(r"^#玩家\s+(.+)$")

    def _load_team_mapping(self) -> dict:
        config = load_config()
        mapping_file = config.get("TEAM_MAPPING_FILE", "team_mapping.json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load team mapping: {e}")
        return {}

    def can_handle(self, user_text: str) -> bool:
        match = self.pattern.match(user_text)
        if not match:
            return False
            
        nickname = match.group(1).strip()
        mapping = self._load_team_mapping()
        # 精準比對是否包含此暱稱
        return nickname in mapping.values()

    def calculate_target_date(self, is_offseason=False, end_date=None) -> str:
        if is_offseason:
            return end_date or "2026-04-12"
            
        tw_tz = pytz.timezone("Asia/Taipei")
        current_tw_dt = datetime.now(tw_tz)
        tw_date = current_tw_dt.date()
        tw_hour = current_tw_dt.hour
        
        # 台北時間 07:00 跨日美西時間邏輯
        if tw_hour >= 7:
            target_dt = tw_date - timedelta(days=1)
        else:
            target_dt = tw_date - timedelta(days=2)
            
        return target_dt.strftime("%Y-%m-%d")

    def format_user_stats(self, player_info: dict, daily_stats: dict, weekly_stats: dict, date_str: str, week_str: str) -> str:
        # Helper to safely format percentages
        def to_percent_str(val):
            try:
                return f"{float(val) * 100:.1f}%"
            except (ValueError, TypeError):
                return "0.0%"

        def build_lines(stats):
            # FGM is stat_4, FGA is stat_3
            fgm = stats.get("stat_4", "0")
            fga = stats.get("stat_3", "0")
            fgm_a = f"{fgm}/{fga}" if fga != "0" else "0/0"
            fg_pct = to_percent_str(stats.get("FG%", "0.0"))

            # FTM is stat_7, FTA is stat_6
            ftm = stats.get("stat_7", "0")
            fta = stats.get("stat_6", "0")
            ftm_a = f"{ftm}/{fta}" if fta != "0" else "0/0"
            ft_pct = to_percent_str(stats.get("FT%", "0.0"))

            pm3 = stats.get("3PTM", "0")
            pts = stats.get("PTS", "0")
            reb = stats.get("REB", "0")
            ast = stats.get("AST", "0")
            stl = stats.get("ST", "0")
            blk = stats.get("BLK", "0")
            to = stats.get("TO", "0")

            return [
                f"FGM/A : {fgm_a:>15}",
                f"FG% : {fg_pct:>17}",
                f"FTM/A : {ftm_a:>15}",
                f"FT% : {ft_pct:>17}",
                f"3PM : {pm3:>17}",
                f"PTS : {pts:>17}",
                f"REB : {reb:>17}",
                f"AST : {ast:>17}",
                f"STL : {stl:>17}",
                f"BLK : {blk:>17}",
                f"TO : {to:>18}"
            ]

        # 1. 組裝當日區塊
        header_daily = (
            f"{player_info['manager_name']}\n"
            f"{player_info['official_name']}\n"
            f"{date_str}"
        )
        daily_lines = build_lines(daily_stats)
        daily_block = "```\n" + "\n".join(daily_lines) + "\n```"

        # 2. 組裝當週區塊
        header_weekly = f"W{week_str}"
        weekly_lines = build_lines(weekly_stats)
        weekly_block = "```\n" + "\n".join(weekly_lines) + "\n```"

        return f"{header_daily}\n{daily_block}\n{header_weekly}\n{weekly_block}"

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        nickname = match.group(1).strip()
        mapping = self._load_team_mapping()
        
        # 1. 尋找對應的 Team ID
        team_id = None
        for t_id, name in mapping.items():
            if name == nickname:
                team_id = t_id
                break
                
        if not team_id:
            return # 依照規範直接略過

        config = load_config()
        league_id = config["LEAGUE_ID"]
        meta = load_league_metadata()
        
        # 2. 計算美西日期與週數
        from datetime import datetime, timedelta
        today_pacific = datetime.now(pytz.timezone("US/Pacific")).strftime("%Y-%m-%d")
        is_offseason = meta.get('end_date') and today_pacific > meta['end_date']
        
        target_date = self.calculate_target_date(is_offseason=is_offseason, end_date=meta.get('end_date'))
        
        date_to_week = meta.get("date_to_week", {})
        target_week = date_to_week.get(target_date) or get_fantasy_week(config["SEASON_START_DATE"])
        
        if meta.get('end_week') and target_week > meta['end_week']:
            target_week = meta['end_week']
            
        team_key = f"nba.l.{league_id}.t.{team_id}"
        
        # 3. 實時抓取數據
        fetcher = YahooFantasyFetcher(
            team_mapping=mapping,
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET")
        )
        
        try:
            # 異步/並行或依序抓取當日與當週數據
            res_daily = fetcher.fetch_single_team_stats_by_url(team_key, "date", target_date)
            res_weekly = fetcher.fetch_single_team_stats_by_url(team_key, "week", str(target_week))
            
            official_name = res_daily.get("team_name", "Unknown Team")
            
            player_info = {
                "manager_name": nickname,
                "official_name": official_name
            }
            
            reply_text = self.format_user_stats(
                player_info, 
                res_daily["stats"], 
                res_weekly["stats"], 
                target_date, 
                str(target_week)
            )
            self.reply_text(event, configuration, reply_text)
        except Exception as e:
            # 依規範安全且安靜地退出，不打擾群組
            logging.error(f"Failed to fetch team real-time stats for manager {nickname}: {e}")

    def reply_text(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=text)]
                )
            )
