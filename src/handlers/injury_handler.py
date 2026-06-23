import re
import json
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler

from src.config import load_config
from src.fetcher import YahooFantasyFetcher
import yahoofantasy

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
        
        config = load_config()
        fetcher = YahooFantasyFetcher(
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET")
        )
        
        league_id = fetcher._normalize_league_id(config["LEAGUE_ID"])
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
                
        official_name = getattr(target_team, "name", "Unknown Team")
        flex_dict = self._build_flex_message(target_manager_name, official_name, injured_players)
        
        self.reply_flex(event, configuration, f"🏥 {target_manager_name} 的傷兵名單", flex_dict)

    def _abbreviate_player_name(self, full_name: str) -> str:
        parts = str(full_name).strip().split()
        if len(parts) >= 2:
            first_initial = parts[0][0]
            last_name = " ".join(parts[1:])
            return f"{first_initial}. {last_name}"
        return full_name

    def _get_status_color(self, status: str) -> str:
        status_upper = str(status).upper()
        if status_upper in ("O", "INJ", "OUT"):
            return "#922B21"
        elif status_upper in ("DOUBTFUL", "DOU"):
            return "#D35400"
        elif status_upper in ("QUESTIONABLE", "QUE", "DTD"):
            return "#E67E22"
        elif status_upper in ("PROBABLE", "PRO", "GTD"):
            return "#F1C40F"
        else:
            return "#7F8C8D"

    def _build_flex_message(self, manager_name: str, official_name: str, players: list) -> dict:
        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    # 1. 玩家資訊標頭 (Header Box) - 置於 Body 內以達白底極簡風
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": manager_name, "weight": "bold", "size": "xl", "color": "#111111"},
                            {"type": "text", "text": official_name, "size": "sm", "color": "#555555"}
                        ]
                    }
                ]
            }
        }
        
        body_contents = bubble["body"]["contents"]
        
        if not players:
            body_contents.append({
                "type": "text",
                "text": "🟢 目前全隊球員皆健康！",
                "align": "center",
                "weight": "bold",
                "size": "md",
                "color": "#27AE60",
                "margin": "md"
            })
            return bubble

        # 有傷兵球員，生成列表
        for p in players:
            full_name = getattr(p.name, "full", "Unknown Player")
            abbrev_name = self._abbreviate_player_name(full_name)
            
            status = getattr(p, "status", "INJ")
            injury_note = getattr(p, "injury_note", "Injured")
            
            color = self._get_status_color(status)
            
            player_row = {
                "type": "box",
                "layout": "horizontal",
                "align": "center",
                "spacing": "sm",
                "contents": [
                    # 1. 姓名縮寫 + 傷勢
                    {
                        "type": "text",
                        "contents": [
                            {"type": "span", "text": abbrev_name, "weight": "bold", "size": "sm", "color": "#111111"},
                            {"type": "span", "text": f" - {injury_note}", "size": "xxs", "color": "#777777"}
                        ],
                        "flex": 1
                    },
                    # 2. 傷病標籤
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": color,
                        "cornerRadius": "sm",
                        "width": "42px",
                        "height": "20px",
                        "justifyContent": "center",
                        "alignItems": "center",
                        "contents": [
                            {
                                "type": "text",
                                "text": str(status),
                                "color": "#FFFFFF",
                                "size": "xxs",
                                "weight": "bold",
                                "align": "center"
                            }
                        ],
                        "flex": 0
                    }
                ]
            }
            body_contents.append(player_row)
            
        return bubble
