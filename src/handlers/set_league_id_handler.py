import re
import os
import json
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.fetcher import YahooFantasyFetcher, LeaguePermissionError
from src.utils.season_utils import sync_season_metadata
from src.utils.path_utils import get_league_team_mapping_path

class SetLeagueIdHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        self.exclude_from_llm = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip().startswith("#設置聯盟ID")
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        
        if user_text == "#設置聯盟ID":
            user_id = getattr(event.source, "user_id", None)
            if user_id:
                from src.utils.session_manager import set_league_id_session
                set_league_id_session(user_id, duration_sec=60)
                self.reply_text(event, configuration, "👉 請在 60 秒內直接輸入新的 Yahoo 聯盟 ID：")
            else:
                self.reply_text(event, configuration, "⚠️ 無法獲取您的 User ID，請重新嘗試。")
            return
            
        match = re.match(r"^#設置聯盟ID\s+(\d+)$", user_text)
        if not match:
            self.reply_text(event, configuration, "格式錯誤，請使用：#設置聯盟ID <純數字_ID>")
            return
            
        target_id = match.group(1)
        config = load_config()
        
        # 建立 Fetcher 並嘗試同步賽季資訊以驗證 ID 效力
        fetcher = YahooFantasyFetcher(
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET"),
            league_id=target_id
        )
        
        try:
            sync_season_metadata(fetcher, target_id)
        except LeaguePermissionError:
            self.reply_text(
                event,
                configuration,
                "⚠️ 設置失敗，機器人 Yahoo 帳號目前無權限存取此聯盟。請確保已將機器人的 Yahoo 帳號邀請為該聯盟的成員或 Co-manager。"
            )
            return
        except Exception as e:
            logging.error(f"[SetLeagueIdHandler] 驗證聯盟同步失敗 {target_id}: {e}")
            self.reply_text(event, configuration, "⚠️ 設置失敗，無法從 Yahoo 獲取該聯盟資訊，請確認 ID 是否正確。")
            return
            
        # 同步成功，寫入對應關係
        try:
            self._update_league_id(target_id)
                
            # 初始化該聯賽的空對應檔
            mapping_path = get_league_team_mapping_path(target_id)
            if not os.path.exists(mapping_path):
                os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
                
                # 取得官方預設隊伍名稱並建立對應
                default_mapping = {}
                try:
                    import yahoofantasy
                    normalized_id = fetcher._normalize_league_id(target_id)
                    league = yahoofantasy.League(fetcher.ctx, normalized_id)
                    for team in league.teams():
                        team_id = str(getattr(team, "team_id", ""))
                        team_name = str(getattr(team, "name", ""))
                        if team_id and team_name:
                            default_mapping[team_id] = team_name
                except Exception as ex:
                    logging.error(f"[SetLeagueIdHandler] 無法取得官方暱稱，將初始化為空對應: {ex}")
                
                with open(mapping_path, "w", encoding="utf-8") as mf:
                    json.dump(default_mapping, mf, ensure_ascii=False, indent=2)
                    
            self.reply_text(event, configuration, f"✅ 成功將此聊天室綁定至聯賽 ID：{target_id}")
        except Exception as fe:
            logging.error(f"[SetLeagueIdHandler] 寫入設定檔失敗: {fe}")
            self.reply_text(event, configuration, "⚠️ 設置成功但儲存設定時發生內部錯誤。")

    def _update_league_id(self, league_id: str) -> None:
        from src.config import current_chat_id
        from src.utils.path_utils import BASE_DIR
        
        chat_id = current_chat_id.get() or "default"
        security_dir = os.path.join(BASE_DIR, "data", "security")
        os.makedirs(security_dir, exist_ok=True)
        config_path = os.path.join(security_dir, "chat_league_mapping.json")
        
        mapping = {}
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
            except Exception:
                mapping = {}
                
        mapping[str(chat_id)] = str(league_id)
        
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2, ensure_ascii=False)

    @property
    def instruction_desc(self) -> str:
        return "#設置聯盟ID <ID> : (限白名單) 設置並同步指定之 Yahoo 聯盟 ID"
