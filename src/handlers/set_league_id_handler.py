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
        user_id = getattr(event.source, "user_id", None)
        
        # 1. 收到無參數 #設置聯盟ID 時，發送包含 NBA 籃球與 MLB 棒球按鈕的 Flex Message
        if user_text == "#設置聯盟ID":
            from src.visualizer.flex_builder import build_button_menu_card
            title = "選擇要設置的運動項目"
            buttons = [
                ("NBA 籃球", "#設置聯盟ID nba"),
                ("MLB 棒球", "#設置聯盟ID mlb")
            ]
            flex_dict = build_button_menu_card(title, None, buttons)
            self.reply_flex(event, configuration, "請選擇要設置的運動項目", flex_dict)
            return

        parts = user_text.split()
        
        # 2. 收到選擇後（例如 #設置聯盟ID nba），以 session_manager 設定對話狀態，攜帶 sport，引導輸入數字 ID
        if len(parts) == 2 and parts[1].lower() in ["nba", "mlb"]:
            sport = parts[1].lower()
            if user_id:
                from src.utils.session_manager import set_session
                set_session(user_id, "set_league_id", {"sport": sport}, duration_sec=60)
                sport_name = "NBA 籃球" if sport == "nba" else "MLB 棒球"
                self.reply_text(event, configuration, f"您選擇了 {sport_name}。請在 60 秒內輸入您的聯盟 ID（純數字，例如 18457）：")
            else:
                self.reply_text(event, configuration, "⚠️ 無法獲取您的 User ID，請重新嘗試。")
            return

        # 3. 處理使用者輸入的數字 ID (互動會話中)
        session = None
        if user_id:
            from src.utils.session_manager import get_session
            session = get_session(user_id, "set_league_id")

        if session and len(parts) == 2 and parts[1].isdigit():
            sport = session.get("sport", "nba")
            target_id = f"{sport}.l.{parts[1]}"
            from src.utils.session_manager import clear_session
            clear_session(user_id, "set_league_id")
        else:
            # 4. 直接輸入參數或是其他情況
            if len(parts) < 2:
                self.reply_text(event, configuration, "⚠️ 指令格式錯誤。")
                return
            target_id = parts[1].strip()
            # 補全前綴
            if target_id.isdigit():
                target_id = f"nba.l.{target_id}"
            elif not target_id.startswith("nba.l.") and not target_id.startswith("mlb.l."):
                target_id = f"nba.l.{target_id}"
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
            raise
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
