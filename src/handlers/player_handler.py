import re
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, Configuration, FlexMessage, FlexContainer
from .base_handler import BaseHandler
from src.visualizer.flex_builder import build_stats_list_card

from src.config import load_config
from src.utils.cache_utils import load_league_metadata
from src.fetcher import YahooFantasyFetcher
from src.llm.prompts.player_fuzzy_search import parse_player_nickname
from src.utils.player_cache import get_cached_player, set_cached_player
from src.utils.time_utils import get_target_date
from src.constants.stat_map import translate_stat_id

YAHOO_NS = {'ns': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}

class PlayerHandler(BaseHandler):
    def __init__(self) -> None:
        self.pattern: re.Pattern[str] = re.compile(r"^#球員\s+(.+)$")

    @property
    def instruction_desc(self) -> str:
        return """
- #球員 <球員英文姓名>：查詢特定 NBA 球員的數據與分析（例如：#球員 Stephen Curry）。
- #球員昨晚 <球員英文姓名>：查詢特定 NBA 球員昨晚的表現（例如：#球員昨晚 Stephen Curry）。
        """

    def can_handle(self, user_text: str) -> bool:
        if not self.pattern.match(user_text):
            return False
        config = load_config()
        return bool(config.get("LLM_API_KEY"))

    def format_player_stats(self, player_info: dict, stats: dict, date_str: str | None = None) -> dict:
        def to_percent_str(val):
            try:
                f_val = float(val)
                if f_val == 0.0:
                    return "-"
                return f"{f_val * 100:.1f}%"
            except (ValueError, TypeError):
                return "-"

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

        sections = [
            {
                "header": date_str,
                "rows": [
                    ("FGM/A", fgm_a),
                    ("FG%", fg_pct),
                    ("FTM/A", ftm_a),
                    ("FT%", ft_pct),
                    ("3PM", pm3),
                    ("PTS", pts),
                    ("REB", reb),
                    ("AST", ast),
                    ("STL", stl),
                    ("BLK", blk),
                    ("TO", to)
                ]
            }
        ]

        return build_stats_list_card(
            title=player_info.get("english_name", "Unknown"),
            subtitle=f"{player_info.get('team', 'Unknown')}#{player_info.get('jersey_number', '0')}",
            sections=sections
        )

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        nickname = match.group(1).strip()
        config = load_config()
        league_id = config["LEAGUE_ID"]
        meta = load_league_metadata()
        sport = meta.get("sport") or league_id.split(".")[0]
        today_pacific = datetime.now(pytz.timezone("US/Pacific")).strftime("%Y-%m-%d")
        is_offseason = meta.get('end_date') and today_pacific > meta['end_date']

        # 1. Check cache
        player_info = get_cached_player(nickname)
        
        # 2. Cache Miss: LLM parse + Yahoo Search
        if not player_info:
            from src.llm.llm_agent import LLMAgent
            agent = LLMAgent()
            llm_res = agent.player_fuzzy_search(nickname, sport=sport)
            if not llm_res.get("is_known_player"):
                self.reply_text(event, configuration, f"找不到現役球員「{nickname}」，請嘗試輸入更清晰的名字或別稱。")
                return
            
            english_name = llm_res["english_name"]
            
            # Retrieve player key from Yahoo search
            fetcher = YahooFantasyFetcher(client_id=config.get("YAHOO_CLIENT_ID"), client_secret=config.get("YAHOO_CLIENT_SECRET"))
            full_league_id = league_id if ("." in league_id) else f"nba.l.{league_id}"
            url = f"league/{full_league_id}/players;search={english_name}"
            try:
                xml_data = fetcher.ctx.make_request(url)
                root = ET.fromstring(xml_data)
                player_node = root.find('.//ns:player', YAHOO_NS)
                if player_node is None:
                    self.reply_text(event, configuration, f"AI 識別為 {english_name}，但當前 Yahoo 聯盟中找不到該球員數據。")
                    return
                
                player_key_node = player_node.find('ns:player_key', YAHOO_NS)
                player_key = player_key_node.text if (player_key_node is not None and player_key_node.text is not None) else ""
                uniform_node = player_node.find('ns:uniform_number', YAHOO_NS)
                jersey_number = uniform_node.text if (uniform_node is not None and uniform_node.text is not None) else llm_res.get("jersey_number", "0")
                
                player_info = {
                    "english_name": english_name,
                    "chinese_name": llm_res["chinese_name"],
                    "team": llm_res["team"],
                    "jersey_number": jersey_number,
                    "player_key": player_key
                }
                set_cached_player(nickname, player_info)
            except Exception as e:
                logging.error(f"Yahoo Search failed: {e}")
                self.reply_text(event, configuration, f"搜尋球員 {english_name} 時發生 Yahoo API 錯誤。")
                return

        # 3. Target date calculation
        target_date = get_target_date(is_offseason=is_offseason, end_date=meta.get('end_date'))
        
        # 4. Fetch Stats by date
        fetcher = YahooFantasyFetcher(client_id=config.get("YAHOO_CLIENT_ID"), client_secret=config.get("YAHOO_CLIENT_SECRET"))
        player_key = player_info["player_key"]
        url = f"player/{player_key}/stats;type=date;date={target_date}"
        
        try:
            xml_data = fetcher.ctx.make_request(url)
            root = ET.fromstring(xml_data)
            
            # Parse stats from XML
            stats_dict = {}
            stat_nodes = root.findall('.//ns:player_stats/ns:stats/ns:stat', YAHOO_NS)
            for node in stat_nodes:
                s_id_node = node.find('ns:stat_id', YAHOO_NS)
                s_val_node = node.find('ns:value', YAHOO_NS)
                s_id = s_id_node.text if s_id_node is not None else None
                s_val = s_val_node.text if s_val_node is not None else "0"
                if s_id is not None:
                    label = translate_stat_id(s_id)
                    stats_dict[label] = s_val
                
            # Guard: if no game played (MIN or PTS is 0 or stat_id not present)
            minutes = stats_dict.get("stat_0", "0") # stat_0 is typically MIN in Yahoo
            pts = stats_dict.get("PTS", "0")
            
            if minutes == "0" and pts == "0":
                self.reply_text(event, configuration, f"{player_info['english_name']} 於 {target_date} 今日無比賽數據。")
                return
            
            flex_dict = self.format_player_stats(player_info, stats_dict, target_date)
            self.reply_flex(event, configuration, f"球員 {player_info.get('english_name', 'Unknown')} 數據", flex_dict)
        except Exception as e:
            logging.error(f"Yahoo fetch stats failed: {e}")
            self.reply_text(event, configuration, f"獲取球員統計數據失敗: {str(e)}")
