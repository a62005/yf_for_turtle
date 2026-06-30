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

    def format_player_stats(self, player_info: dict, stats: dict, date_str: str | None = None, stat_categories: list = None) -> dict:
        def to_percent_str(val):
            try:
                f_val = float(val)
                if f_val == 0.0:
                    return "-"
                return f"{f_val * 100:.1f}%"
            except (ValueError, TypeError):
                return "-"

        def fmt_val(display_name, val):
            if val is None or str(val).strip() in ("", "-", "0") and display_name not in ("TO",):
                pass
            if val is None or str(val).strip() in ("", "-"):
                return "-"
            if display_name in ("FG%", "FT%"):
                return to_percent_str(val)
            if display_name in ("AVG", "OBP", "SLG", "OPS"):
                try:
                    num = float(val)
                    if num == 0: return "-"
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
            if "/" in display_name:
                return str(val) if str(val) not in ("0", "None") else "-"
            try:
                return str(int(round(float(val))))
            except (ValueError, TypeError):
                return str(val)

        rows = []
        if stat_categories:
            DISPLAY_ALIASES = {"FGM/FGA": "FGM/A", "FTM/FTA": "FTM/A", "3PTM": "3PM"}
            for cat in stat_categories:
                disp = cat["display_name"]
                label = DISPLAY_ALIASES.get(disp, disp)
                val = stats.get(disp)
                rows.append((label, fmt_val(disp, val)))
        else:
            # NBA fallback
            fgm = stats.get("stat_4", "0")
            fga = stats.get("stat_3", "0")
            fgm_a = f"{fgm}/{fga}" if fga != "0" else "0/0"
            fg_pct = to_percent_str(stats.get("FG%", "0.0"))
            ftm = stats.get("stat_7", "0")
            fta = stats.get("stat_6", "0")
            ftm_a = f"{ftm}/{fta}" if fta != "0" else "0/0"
            ft_pct = to_percent_str(stats.get("FT%", "0.0"))
            
            rows = [
                ("FGM/A", fgm_a), ("FG%", fg_pct), ("FTM/A", ftm_a), ("FT%", ft_pct),
                ("3PM", stats.get("3PTM", "0")), ("PTS", stats.get("PTS", "0")),
                ("REB", stats.get("REB", "0")), ("AST", stats.get("AST", "0")),
                ("STL", stats.get("ST", "0")), ("BLK", stats.get("BLK", "0")),
                ("TO", stats.get("TO", "0"))
            ]

        sections = [
            {
                "header": date_str,
                "rows": rows
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
        meta = load_league_metadata(league_id)
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
            fetcher = YahooFantasyFetcher(
                client_id=config.get("YAHOO_CLIENT_ID"),
                client_secret=config.get("YAHOO_CLIENT_SECRET"),
                league_id=league_id
            )
            url = f"league/{league_id}/players;search={english_name}"
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
        fetcher = YahooFantasyFetcher(
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET"),
            league_id=league_id
        )
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
                    label = fetcher._translate_stat(s_id, league_id)
                    stats_dict[label] = s_val
                
            # Guard: if no game played (all stats are zero/empty/hyphen)
            def is_zero_stats(sd):
                for val in sd.values():
                    val_str = str(val).strip()
                    if val_str not in ("0", "0.0", "-", "0/0", ""):
                        return False
                return True
                
            if is_zero_stats(stats_dict):
                self.reply_text(event, configuration, f"{player_info['english_name']} 於 {target_date} 今日無比賽數據。")
                return
            
            flex_dict = self.format_player_stats(
                player_info, 
                stats_dict, 
                target_date,
                stat_categories=meta.get("stat_categories")
            )
            self.reply_flex(event, configuration, f"球員 {player_info.get('english_name', 'Unknown')} 數據", flex_dict)
        except Exception as e:
            logging.error(f"Yahoo fetch stats failed: {e}")
            self.reply_text(event, configuration, f"獲取球員統計數據失敗: {str(e)}")
