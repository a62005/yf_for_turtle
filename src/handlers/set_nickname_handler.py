import re
import os
import json
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.utils.path_utils import get_league_team_mapping_path
from src.visualizer.flex_builder import build_button_menu_card
from src.utils.session_manager import set_nickname_session

class SetNicknameHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        self.exclude_from_llm = True
        
    def can_handle(self, user_text: str) -> bool:
        text = user_text.strip()
        return text == "#設置玩家暱稱" or text.startswith("#設置暱稱_隊伍")
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        
        if not league_id:
            self.reply_text(event, configuration, "⚠️ 聯賽 ID 尚未配置，無法設定玩家暱稱。")
            return
            
        mapping_path = get_league_team_mapping_path(league_id)
        
        # 若 mapping 檔不存在，先進行預設初始化
        if not os.path.exists(mapping_path):
            os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
            default_mapping = {}
            try:
                import yahoofantasy
                from src.fetcher import YahooFantasyFetcher
                fetcher = YahooFantasyFetcher(
                    client_id=config.get("YAHOO_CLIENT_ID"),
                    client_secret=config.get("YAHOO_CLIENT_SECRET")
                )
                league = yahoofantasy.League(fetcher.ctx, fetcher._normalize_league_id(league_id))
                for team in league.teams():
                    team_id = str(getattr(team, "team_id", ""))
                    team_name = str(getattr(team, "name", ""))
                    if team_id and team_name:
                        default_mapping[team_id] = team_name
            except Exception as ex:
                logging.error(f"[SetNicknameHandler] 初始化官方暱稱失敗: {ex}")
            
            with open(mapping_path, "w", encoding="utf-8") as mf:
                json.dump(default_mapping, mf, ensure_ascii=False, indent=2)
                
        # 讀取當前 mapping 資訊
        try:
            with open(mapping_path, "r", encoding="utf-8") as mf:
                mapping = json.load(mf)
        except Exception as e:
            logging.error(f"[SetNicknameHandler] 讀取對應檔失敗: {e}")
            mapping = {}
            
        if user_text == "#設置玩家暱稱":
            buttons = []
            for team_id, nickname in mapping.items():
                buttons.append((nickname, f"#設置暱稱_隊伍 {team_id}"))
            
            flex_dict = build_button_menu_card("設定玩家暱稱", None, buttons)
            self.reply_flex(event, configuration, "設定玩家暱稱", flex_dict)
            
        elif user_text.startswith("#設置暱稱_隊伍"):
            match = re.match(r"^#設置暱稱_隊伍\s+(\d+)$", user_text)
            if not match:
                self.reply_text(event, configuration, "⚠️ 指令格式錯誤。")
                return
            
            team_id = match.group(1)
            curr_name = mapping.get(team_id, f"Team {team_id}")
            
            # 註冊 60 秒的改名 Session 狀態
            user_id = event.source.user_id
            set_nickname_session(user_id, team_id, duration_sec=60)
            
            self.reply_text(event, configuration, f"👉 請在 60 秒內直接輸入 {curr_name} 的新暱稱：")

    @property
    def instruction_desc(self) -> str:
        return "#設置玩家暱稱 : (限白名單) 調整玩家在 Bot 中的顯示暱稱"
