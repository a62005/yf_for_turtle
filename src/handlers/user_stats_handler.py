import re
import logging
from datetime import datetime
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler

from src.config import load_config
from src.utils.cache_utils import load_league_metadata
from src.fetcher import YahooFantasyFetcher
from src.utils.time_utils import get_fantasy_week
from src.visualizer.flex_builder import build_stats_list_card

class UserStatsHandler(BaseHandler):
    def __init__(self):
        self.pattern = re.compile(r"^#玩家(?:\s+(.+))?$")

    @property
    def instruction_desc(self) -> str:
        return """
- #玩家：列出聯賽所有玩家清單。
- #玩家 <玩家名稱>：查詢該玩家目前當日與當週的戰績數據。
- #玩家 <玩家名稱> <日期>：查詢該玩家在特定日期的當日戰績與該日期所屬週的週戰績數據（日期格式：YYYYMMDD，例如：#玩家 陳威 20260101）。
        """

    def _parse_nickname_and_date(self, raw_str: str) -> tuple[str, str | None]:
        parts = raw_str.strip().split()
        if len(parts) > 1:
            last_part = parts[-1]
            if re.match(r"^\d{8}$", last_part):
                date_str = f"{last_part[:4]}-{last_part[4:6]}-{last_part[6:8]}"
                nickname = " ".join(parts[:-1]).strip()
                return nickname, date_str
            elif re.match(r"^\d{4}-\d{2}-\d{2}$", last_part):
                nickname = " ".join(parts[:-1]).strip()
                return nickname, last_part
        return raw_str.strip(), None

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
            
        nickname, _ = self._parse_nickname_and_date(nickname)
        
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
            return raw_stats

        daily_rows = build_stat_rows(daily_stats)
        weekly_rows = build_stat_rows(weekly_stats)

        sections = [
            {
                "header": date_str,
                "rows": daily_rows
            },
            {
                "header": f"W{week_str}",
                "rows": weekly_rows
            }
        ]

        return build_stats_list_card(
            title=player_info["manager_name"],
            subtitle=player_info["official_name"],
            sections=sections
        )

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        nickname_raw = match.group(1)
        if not nickname_raw or not nickname_raw.strip():
            self.reply_player_list(event, configuration, is_matchup=False)
            return

        nickname, target_date = self._parse_nickname_and_date(nickname_raw)
        
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
        from src.utils.time_utils import get_pacific_date
        today_pacific = get_pacific_date()
        is_offseason = meta.get('end_date') and today_pacific > meta['end_date']
        
        if not target_date:
            from src.utils.time_utils import get_target_date
            target_date = get_target_date(is_offseason=is_offseason, end_date=meta.get('end_date'))
            
        # Future date guard
        if target_date > today_pacific:
            self.reply_text(event, configuration, "我不是未來人，無法提供未來數據")
            return
            
        # Past date guard
        if meta.get('start_date') and target_date < meta['start_date']:
            self.reply_text(event, configuration, "查無當天數據")
            return
            
        date_to_week = meta.get("date_to_week", {})
        target_week = date_to_week.get(target_date)
        
        if not target_week:
            from src.utils.time_utils import get_fantasy_week
            start_date = meta.get('start_date') or config.get("SEASON_START_DATE")
            if not start_date:
                raise ValueError("SEASON_START_DATE is not configured in metadata or environment.")
            try:
                target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(target_date, "%Y-%m-%d"))
                target_week = get_fantasy_week(start_date, target_dt)
            except Exception:
                target_week = get_fantasy_week(start_date)
        
        if meta.get('end_week') and target_week > meta['end_week']:
            target_week = meta['end_week']
        if target_week < 1:
            target_week = 1
            
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

