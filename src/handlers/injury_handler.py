import re
import json
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler

from src.config import load_config
from src.fetcher import YahooFantasyFetcher
import yahoofantasy
from src.visualizer.flex_builder import build_status_badge_list_card, get_status_color

class InjuryHandler(BaseHandler):
    def __init__(self):
        self.pattern = re.compile(r"^#傷兵\s*(.+)?$")

    @property
    def instruction_desc(self) -> str:
        return """
- #傷兵 <玩家名稱>：查詢我們聯盟中特定玩家隊伍目前的傷兵名單（例如：#傷兵 韋哥）。
        """

    def can_handle(self, user_text: str) -> bool:
        return bool(self.pattern.match(user_text))

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        league_id = None
        if configuration:
            if hasattr(configuration, "get"):
                league_id = configuration.get("LEAGUE_ID")
            else:
                league_id = getattr(configuration, "LEAGUE_ID", None)
        
        if league_id and str(league_id).startswith("mlb.l."):
            self.reply_text(event, configuration, "⚠️ 此功能目前僅支援 NBA 聯賽。")
            return

        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        param = match.group(1)
        if not param:
            logging.info("[InjuryHandler] 空參數指令，直接略過")
            return

        param = param.strip()
        mapping = self._load_team_mapping()
        
        target_team_id = None
        target_manager_name = None
        for tid, nickname in mapping.items():
            if param.lower() in nickname.lower() or nickname.lower() in param.lower():
                target_team_id = tid
                target_manager_name = nickname
                break
                
        if not target_team_id:
            logging.info(f"[InjuryHandler] 未匹配到聯賽玩家: '{param}'，直接略過")
            return

        logging.info(f"[InjuryHandler] 開始查詢玩家 '{target_manager_name}' (ID: {target_team_id}) 的傷兵...")
        
        try:
            config = load_config()
            league_id = config["LEAGUE_ID"]
            fetcher = YahooFantasyFetcher(
                client_id=config.get("YAHOO_CLIENT_ID"),
                client_secret=config.get("YAHOO_CLIENT_SECRET"),
                league_id=league_id
            )
            
            league_id = fetcher._normalize_league_id(league_id)
            league = yahoofantasy.League(fetcher.ctx, league_id)
            
            target_team = None
            for team in league.teams():
                if str(getattr(team, "team_id", "")) == str(target_team_id):
                    target_team = team
                    break
                    
            if not target_team:
                logging.error(f"[InjuryHandler] 無法在 Yahoo API 獲取對應的 Team ID: {target_team_id}")
                return
                
            injured_players = []
            for player in target_team.roster().players:
                status = getattr(player, "status", None)
                if status and str(status).strip():
                    injured_players.append(player)
        except Exception as e:
            logging.error(f"[InjuryHandler] 獲取傷兵名單時發生 Yahoo API 錯誤: {e}", exc_info=True)
            self.reply_text(event, configuration, "獲取傷兵名單失敗，請稍後再試")
            return
                
        official_name = getattr(target_team, "name", "Unknown Team")
        
        items = []
        for p in injured_players:
            player_name_obj = getattr(p, "name", None)
            full_name = getattr(player_name_obj, "full", "Unknown Player") if player_name_obj else "Unknown Player"
            abbrev_name = self._abbreviate_player_name(full_name)
            status = getattr(p, "status", "INJ")
            injury_note = getattr(p, "injury_note", "Injured")
            status_color = get_status_color(status)
            items.append((abbrev_name, injury_note, status, status_color))
            
        flex_dict = build_status_badge_list_card(target_manager_name, official_name, items)
        
        self.reply_flex(event, configuration, f"🏥 {target_manager_name} 的傷兵名單", flex_dict)

    def _abbreviate_player_name(self, full_name: str) -> str:
        parts = str(full_name).strip().split()
        if len(parts) >= 2:
            first_initial = parts[0][0]
            last_name = " ".join(parts[1:])
            return f"{first_initial}. {last_name}"
        return full_name
