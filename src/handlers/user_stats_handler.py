import re
import os
import json
import logging
from datetime import datetime, timedelta
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, Configuration, FlexMessage, FlexContainer
from .base_handler import BaseHandler

from src.config import load_config
from src.cache_utils import load_league_metadata
from src.fetcher import YahooFantasyFetcher
from src.utils.time_utils import get_fantasy_week

class UserStatsHandler(BaseHandler):
    def __init__(self):
        self.pattern = re.compile(r"^#玩家(?:\s+(.+))?$")

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
        return nickname in mapping.values()

    def format_user_stats(self, player_info: dict, daily_stats: dict, weekly_stats: dict, date_str: str, week_str: str) -> dict:
        def to_percent_str(val):
            try:
                f_val = float(val)
                if f_val == 0.0:
                    return "-"
                return f"{f_val * 100:.1f}%"
            except (ValueError, TypeError):
                return "-"

        def build_stat_rows(stats):
            # Prioritize composite FGM/FGA value
            fgm_a = stats.get("FGM/FGA")
            if not fgm_a:
                fgm = stats.get("stat_4")
                fga = stats.get("stat_3")
                if fgm is not None and fga is not None:
                    fgm_a = f"{fgm}/{fga}" if fga != "0" else "0/0"
                else:
                    fgm_a = "0/0"
            fg_pct = to_percent_str(stats.get("FG%", "0.0"))

            # Prioritize composite FTM/FTA value
            ftm_a = stats.get("FTM/FTA")
            if not ftm_a:
                ftm = stats.get("stat_7")
                fta = stats.get("stat_6")
                if ftm is not None and fta is not None:
                    ftm_a = f"{ftm}/{fta}" if fta != "0" else "0/0"
                else:
                    ftm_a = "0/0"
            ft_pct = to_percent_str(stats.get("FT%", "0.0"))

            pm3 = stats.get("3PTM", "0")
            pts = stats.get("PTS", "0")
            reb = stats.get("REB", "0")
            ast = stats.get("AST", "0")
            stl = stats.get("ST", "0")
            blk = stats.get("BLK", "0")
            to = stats.get("TO", "0")

            raw_stats = [
                ("FGM/A", fgm_a), ("FG%", fg_pct), ("FTM/A", ftm_a), ("FT%", ft_pct),
                ("3PM", pm3), ("PTS", pts), ("REB", reb), ("AST", ast),
                ("STL", stl), ("BLK", blk), ("TO", to)
            ]
            rows = []
            for label, val in raw_stats:
                rows.append({
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": label, "color": "#666666", "size": "sm"},
                        {"type": "text", "text": val, "align": "end", "weight": "bold", "color": "#111111", "size": "sm"}
                    ]
                })
            return rows

        daily_rows = build_stat_rows(daily_stats)
        weekly_rows = build_stat_rows(weekly_stats)

        # 組裝白底極簡雙層卡片字典
        return {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    # 1. 玩家資訊標頭
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": player_info["manager_name"], "weight": "bold", "size": "xl", "color": "#111111"},
                            {"type": "text", "text": player_info["official_name"], "size": "sm", "color": "#555555"}
                        ]
                    },
                    # 2. 當日日期標頭
                    {
                        "type": "text",
                        "text": date_str,
                        "weight": "bold",
                        "size": "md",
                        "color": "#111111",
                        "margin": "md"
                    },
                    # 3. 當日數據
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": daily_rows
                    },
                    # 4. 精緻分隔線
                    {
                        "type": "separator",
                        "color": "#EAEAEA"
                    },
                    # 5. 當週週數標頭
                    {
                        "type": "text",
                        "text": f"W{week_str}",
                        "weight": "bold",
                        "size": "md",
                        "color": "#111111",
                        "margin": "md"
                    },
                    # 6. 當週數據
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": weekly_rows
                    }
                ]
            }
        }

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        nickname_raw = match.group(1)
        nickname = nickname_raw.strip() if nickname_raw else ""
        
        if not nickname:
            self.reply_player_list(event, configuration, is_matchup=False)
            return

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
        
        from src.utils.time_utils import get_target_date
        target_date = get_target_date(is_offseason=is_offseason, end_date=meta.get('end_date'))
        
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
            
            flex_dict = self.format_user_stats(
                player_info, 
                res_daily["stats"], 
                res_weekly["stats"], 
                target_date, 
                str(target_week)
            )
            self.reply_flex(event, configuration, f"玩家 {nickname} 數據統計", flex_dict)
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
