import re
import os
import logging
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, Configuration
from .base_handler import BaseHandler

from src.config import load_config
from src.cache_utils import load_league_metadata
from src.fetcher import YahooFantasyFetcher
from src.utils.gemini_parser import parse_player_nickname
from src.utils.player_cache import get_cached_player, set_cached_player

YAHOO_NS = {'ns': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}

class PlayerHandler(BaseHandler):
    def __init__(self):
        self.pattern = re.compile(r"^#球員\s+(.+)$")

    def can_handle(self, user_text: str) -> bool:
        return self.pattern.match(user_text) is not None

    def calculate_target_date(self, current_tw_dt=None, is_offseason=False, end_date=None) -> str:
        if is_offseason:
            return end_date or "2026-04-12"
        
        if current_tw_dt is None:
            tw_tz = pytz.timezone("Asia/Taipei")
            current_tw_dt = datetime.now(tw_tz)
            
        tw_date = current_tw_dt.date()
        tw_hour = current_tw_dt.hour
        
        if tw_hour >= 7:
            target_dt = tw_date - timedelta(days=1)
        else:
            target_dt = tw_date - timedelta(days=2)
            
        return target_dt.strftime("%Y-%m-%d")

    def format_player_stats(self, player_info: dict, stats: dict) -> str:
        # Helper to safely format percentages
        def to_percent_str(val):
            try:
                return f"{float(val) * 100:.1f}%"
            except (ValueError, TypeError):
                return "0.0%"

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

        header = (
            f"{player_info.get('english_name', 'Unknown')}"
            f" ({player_info.get('chinese_name', '未知')})\n"
            f"{player_info.get('team', 'Unknown')}#{player_info.get('jersey_number', '0')}\n"
            f"-----------------------"
        )

        lines = [
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

        return header + "\n" + "\n".join(lines)

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        nickname = match.group(1).strip()
        config = load_config()
        league_id = config["LEAGUE_ID"]
        meta = load_league_metadata()
        today_pacific = datetime.now(pytz.timezone("US/Pacific")).strftime("%Y-%m-%d")
        is_offseason = meta.get('end_date') and today_pacific > meta['end_date']

        # 1. Check cache
        player_info = get_cached_player(nickname)
        
        # 2. Cache Miss: LLM parse + Yahoo Search
        if not player_info:
            llm_res = parse_player_nickname(nickname, api_key=config.get("GEMINI_API_KEY"))
            if not llm_res.get("is_known_player"):
                self.reply_text(event, configuration, f"找不到現役球員「{nickname}」，請嘗試輸入更清晰的名字或別稱。")
                return
            
            english_name = llm_res["english_name"]
            
            # Retrieve player key from Yahoo search
            fetcher = YahooFantasyFetcher(client_id=config.get("YAHOO_CLIENT_ID"), client_secret=config.get("YAHOO_CLIENT_SECRET"))
            url = f"league/nba.l.{league_id}/players;search={english_name}"
            try:
                xml_data = fetcher.ctx.make_request(url)
                root = ET.fromstring(xml_data)
                player_node = root.find('.//ns:player', YAHOO_NS)
                if player_node is None:
                    self.reply_text(event, configuration, f"AI 識別為 {english_name}，但當前 Yahoo 聯盟中找不到該球員數據。")
                    return
                
                player_key = player_node.find('ns:player_key', YAHOO_NS).text
                uniform_node = player_node.find('ns:uniform_number', YAHOO_NS)
                jersey_number = uniform_node.text if uniform_node is not None else llm_res.get("jersey_number", "0")
                
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
        target_date = self.calculate_target_date(is_offseason=is_offseason, end_date=meta.get('end_date'))
        
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
                s_id = node.find('ns:stat_id', YAHOO_NS).text
                s_val = node.find('ns:value', YAHOO_NS).text
                # Import standard map translation
                from src.constants.stat_map import translate_stat_id
                label = translate_stat_id(s_id)
                stats_dict[label] = s_val
                
            # Guard: if no game played (MIN or PTS is 0 or stat_id not present)
            minutes = stats_dict.get("stat_0", "0") # stat_0 is typically MIN in Yahoo
            pts = stats_dict.get("PTS", "0")
            
            if minutes == "0" and pts == "0":
                self.reply_text(event, configuration, f"{player_info['english_name']} 於 {target_date} 今日無比賽數據。")
                return
            
            reply_text = self.format_player_stats(player_info, stats_dict)
            self.reply_text(event, configuration, reply_text)
        except Exception as e:
            logging.error(f"Yahoo fetch stats failed: {e}")
            self.reply_text(event, configuration, f"獲取球員統計數據失敗: {str(e)}")

    def reply_text(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=text)]
                )
            )
