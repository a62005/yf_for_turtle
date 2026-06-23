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
        
        # 尋找匹配的玩家 Team ID
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
        
        # 獲取對應隊伍
        target_team = None
        for team in league.teams():
            # 確保獲取的 team_id 為字串比對
            if str(getattr(team, "team_id", "")) == str(target_team_id):
                target_team = team
                break
                
        if not target_team:
            logging.error(f"[InjuryHandler] 無法在 Yahoo API 獲取對應的 Team ID: {target_team_id}")
            return
            
        # 篩選傷兵
        injured_players = []
        for player in target_team.roster().players:
            status = getattr(player, "status", None)
            if status and str(status).strip():
                injured_players.append(player)
                
        # 渲染 Flex Message JSON
        flex_dict = self._build_flex_message(target_manager_name, injured_players)
        
        # 發送 Flex
        self.reply_flex(event, configuration, f"🏥 {target_manager_name} 的傷兵名單", flex_dict)

    def _get_status_color(self, status: str) -> str:
        status_upper = str(status).upper()
        # O / INJ / Out (出賽成疑/確定缺陣)：深紅色 (#922B21)
        if status_upper in ("O", "INJ", "OUT"):
            return "#922B21"
        # Doubtful (極低機率出賽)：紅橘色 (#D35400)
        elif status_upper in ("DOUBTFUL", "DOU"):
            return "#D35400"
        # Questionable / DTD (可能缺陣/每日觀察)：橘色 (#E67E22)
        elif status_upper in ("QUESTIONABLE", "QUE", "DTD"):
            return "#E67E22"
        # Probable / GTD (高機率出賽/賽前決定)：黃橘色/黃色 (#F1C40F)
        elif status_upper in ("PROBABLE", "PRO", "GTD"):
            return "#F1C40F"
        # 其他狀態 (如 SSP 禁賽)：灰色 (#7F8C8D)
        else:
            return "#7F8C8D"

    def _build_flex_message(self, manager_name: str, players: list) -> dict:
        bubble = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#2C3E50",
                "contents": [
                    {
                        "type": "text",
                        "text": f"🏥 {manager_name} 的傷兵名單",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#FFFFFF"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": []
            }
        }
        
        body_contents = bubble["body"]["contents"]
        
        if not players:
            # 全隊健康
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
            name = getattr(p.name, "full", "Unknown Player")
            pos = getattr(p, "display_position", "Util")
            team_abbr = getattr(p, "editorial_team_abbr", "NBA")
            status = getattr(p, "status", "INJ")
            injury_note = getattr(p, "injury_note", "Injured")
            
            color = self._get_status_color(status)
            
            player_row = {
                "type": "box",
                "layout": "horizontal",
                "align": "center",
                "spacing": "sm",
                "contents": [
                    # 1. 姓名
                    {
                        "type": "text",
                        "text": name,
                        "weight": "bold",
                        "size": "sm",
                        "color": "#111111",
                        "flex": 4
                    },
                    # 2. 位置與球隊
                    {
                        "type": "text",
                        "text": f"{pos} - {team_abbr}",
                        "size": "xs",
                        "color": "#555555",
                        "flex": 3
                    },
                    # 3. 傷病標籤
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
                    },
                    # 4. 傷病細節
                    {
                        "type": "text",
                        "text": injury_note,
                        "size": "xxs",
                        "color": "#777777",
                        "align": "end",
                        "flex": 2
                    }
                ]
            }
            body_contents.append(player_row)
            
        return bubble
