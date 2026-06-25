import re
import os
import json
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.fetcher import YahooFantasyFetcher
from src.utils.season_utils import sync_season_metadata
from src.utils.path_utils import get_league_team_mapping_path

class SetLeagueIdHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip().startswith("#設置聯盟ID")
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = re.match(r"^#設置聯盟ID\s+(\d+)$", user_text)
        if not match:
            self.reply_text(event, configuration, "格式錯誤，請使用：#設置聯盟ID <純數字_ID>")
            return
            
        target_id = match.group(1)
        config = load_config()
        
        # 建立 Fetcher 並嘗試同步賽季資訊以驗證 ID 效力
        fetcher = YahooFantasyFetcher(
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET")
        )
        
        try:
            sync_season_metadata(fetcher, target_id)
        except Exception as e:
            logging.error(f"[SetLeagueIdHandler] 驗證聯盟同步失敗 {target_id}: {e}")
            self.reply_text(event, configuration, "⚠️ 設置失敗，無法從 Yahoo 獲取該聯盟資訊，請確認 ID 是否正確。")
            return
            
        # 同步成功，寫入設定檔 data/security/league_config.json
        security_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "security"))
        os.makedirs(security_dir, exist_ok=True)
        config_path = os.path.join(security_dir, "league_config.json")
        
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump({"LEAGUE_ID": target_id}, f, indent=2)
                
            # 初始化該聯賽的空對應檔
            mapping_path = get_league_team_mapping_path(target_id)
            if not os.path.exists(mapping_path):
                os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
                with open(mapping_path, "w", encoding="utf-8") as mf:
                    json.dump({}, mf)
                    
            self.reply_text(event, configuration, "✅ 聯盟 ID 設置成功，並已完成賽季資訊同步！")
        except Exception as fe:
            logging.error(f"[SetLeagueIdHandler] 寫入設定檔失敗: {fe}")
            self.reply_text(event, configuration, "⚠️ 設置成功但儲存設定時發生內部錯誤。")

    @property
    def instruction_desc(self) -> str:
        return "#設置聯盟ID <ID> : (限白名單) 設置並同步指定之 Yahoo 聯盟 ID"
