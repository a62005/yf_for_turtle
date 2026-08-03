import time
import os
import json
import logging
from abc import ABC, abstractmethod
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, FlexMessage, FlexContainer

class ConversationSession(ABC):
    def __init__(self, user_id: str, duration_sec: int = 60):
        self.user_id = user_id
        self.expire_at = time.time() + duration_sec

    def is_expired(self) -> bool:
        return time.time() > self.expire_at

    @abstractmethod
    def handle_message(self, event: MessageEvent, configuration: Configuration, user_text: str, dispatcher: any) -> bool:
        """
        處理文字訊息。
        傳回 True 代表會話繼續，False 代表會話結束（或取消），系統將會自動清除該會話。
        """
        pass

    def handle_image(self, event: MessageEvent, configuration: Configuration, image_bytes: bytes, dispatcher: any) -> bool:
        """
        處理圖片訊息。
        傳回 True 代表會話繼續，False 代表會話結束。
        """
        return True

# 全域作用中會話存儲
_sessions = {}

def register_session(session: ConversationSession) -> None:
    """註冊一個新的會話"""
    _sessions[session.user_id] = session

def get_active_session(user_id: str) -> ConversationSession | None:
    """獲取指定使用者的作用中會話（會自動清理過期會話）"""
    session = _sessions.get(user_id)
    if not session:
        return None
    if session.is_expired():
        del _sessions[user_id]
        return None
    return session

def clear_active_session(user_id: str) -> None:
    """清除指定使用者的作用中會話"""
    if user_id in _sessions:
        del _sessions[user_id]

# 輔助回覆函式
def reply_text(event: MessageEvent, configuration: Configuration, text: str) -> None:
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=text)]
            )
        )

def reply_flex(event: MessageEvent, configuration: Configuration, alt_text: str, flex_dict: dict) -> None:
    flex_container = FlexContainer.from_json(json.dumps(flex_dict))
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[FlexMessage(alt_text=alt_text, contents=flex_container)]
            )
        )

# 輔助設定寫入函式
def update_team_nickname(team_id: str, new_nickname: str) -> None:
    from src.config import load_config
    from src.utils.path_utils import get_league_team_mapping_path
    config = load_config()
    league_id = config.get("LEAGUE_ID")
    if not league_id:
        return
    mapping_path = get_league_team_mapping_path(league_id)
    
    mapping = {}
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
        except Exception:
            mapping = {}
            
    mapping[str(team_id)] = new_nickname
    
    try:
        os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(mapping, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"[SessionManager] 寫入暱稱對應檔失敗: {e}")

def update_league_settings(new_settings: dict) -> None:
    from src.config import load_config
    from src.utils.path_utils import get_league_dir
    config = load_config()
    league_id = config.get("LEAGUE_ID")
    if not league_id:
        return
        
    league_dir = get_league_dir(league_id)
    settings_path = os.path.join(league_dir, "settings.json")
    
    settings = {}
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except Exception:
            settings = {}
            
    settings.update(new_settings)
    
    try:
        os.makedirs(os.path.dirname(settings_path), exist_ok=True)
        with open(settings_path, "w", encoding="utf-8") as f:
            json.dump(settings, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"[SessionManager] 寫入設定檔 settings.json 失敗: {e}")

# 具體會話實作類別

class NicknameSession(ConversationSession):
    def __init__(self, user_id: str, team_id: str, duration_sec: int = 60):
        super().__init__(user_id, duration_sec)
        self.team_id = team_id

    def handle_message(self, event: MessageEvent, configuration: Configuration, user_text: str, dispatcher: any) -> bool:
        if user_text.startswith("#"):
            return False  # 取消會話，讓指令重新分發
            
        update_team_nickname(self.team_id, user_text)
        reply_text(event, configuration, f"✅ 成功將暱稱修改為：{user_text}")
        return False

class DraftTimeSession(ConversationSession):
    def handle_message(self, event: MessageEvent, configuration: Configuration, user_text: str, dispatcher: any) -> bool:
        if user_text.startswith("#"):
            return False
            
        from src.llm.llm_agent import LLMAgent
        llm_agent = LLMAgent()
        parsed = llm_agent.parse_draft_date(user_text)
        if parsed.get("success") and parsed.get("date"):
            date_val = parsed["date"]
            update_league_settings({"DRAFT_DATE": date_val})
            reply_text(event, configuration, f"✅ 成功將選秀時間修改為：{date_val}")
            return False
        else:
            reply_text(
                event, 
                configuration, 
                "⚠️ 無法解析您輸入的時間格式，請重新輸入（例如：2026-10-15 19:30），或輸入 # 取消"
            )
            return True

class SeasonStartTimeSession(ConversationSession):
    def handle_message(self, event: MessageEvent, configuration: Configuration, user_text: str, dispatcher: any) -> bool:
        if user_text.startswith("#"):
            return False
            
        from src.llm.llm_agent import LLMAgent
        llm_agent = LLMAgent()
        parsed = llm_agent.parse_draft_date(user_text)
        if parsed.get("success") and parsed.get("date"):
            date_val = parsed["date"]
            update_league_settings({"SEASON_START_DATE": date_val})
            reply_text(event, configuration, f"✅ 成功將開季時間修改為：{date_val}")
            return False
        else:
            reply_text(
                event, 
                configuration, 
                "⚠️ 無法解析您輸入的時間格式，請重新輸入（例如：2026-10-22 08:00），或輸入 # 取消"
            )
            return True

class LeagueIdSession(ConversationSession):
    def __init__(self, user_id: str, sport: str, duration_sec: int = 60):
        super().__init__(user_id, duration_sec)
        self.sport = sport

    def handle_message(self, event: MessageEvent, configuration: Configuration, user_text: str, dispatcher: any) -> bool:
        if user_text.startswith("#"):
            return False
            
        event.message.text = f"#設置聯盟ID {user_text}"
        dispatcher.handle(event, configuration)
        return False

class PrizeSession(ConversationSession):
    def handle_message(self, event: MessageEvent, configuration: Configuration, user_text: str, dispatcher: any) -> bool:
        if user_text == "#":
            reply_text(event, configuration, "已取消設定。")
            return False
        else:
            reply_text(event, configuration, "⚠️ 設置獎金模式中，請傳送獎金圖片，或輸入 # 取消設定。")
            return True

    def handle_image(self, event: MessageEvent, configuration: Configuration, image_bytes: bytes, dispatcher: any) -> bool:
        from src.handlers.set_prize_handler import SetPrizeHandler
        handler = dispatcher.get_handler(SetPrizeHandler)
        if handler:
            handler.handle_image(event, configuration, image_bytes)
        return False

class RemoveLeagueSession(ConversationSession):
    def handle_message(self, event: MessageEvent, configuration: Configuration, user_text: str, dispatcher: any) -> bool:
        if user_text == "#確定移除聯盟ID":
            event.message.text = "#確定移除聯盟ID"
            dispatcher.handle(event, configuration)
            return False
        return False

class AddManagerSession(ConversationSession):
    def __init__(self, user_id: str, duration_sec: int = 60):
        super().__init__(user_id, duration_sec)
        self.step = 1
        self.target_id = None

    def handle_message(self, event: MessageEvent, configuration: Configuration, user_text: str, dispatcher: any) -> bool:
        if user_text == "#":
            reply_text(event, configuration, "已取消新增管理員。")
            return False
            
        import re
        if self.step == 1:
            if not re.match(r"^U[a-fA-F0-9]{32}$", user_text):
                reply_text(
                    event, 
                    configuration, 
                    "⚠️ LINE ID 格式錯誤，必須為 U 開頭後接 32 位十六進位字元。\n請重新輸入，或輸入 # 取消："
                )
                return True
                
            self.target_id = user_text
            self.step = 2
            self.expire_at = time.time() + 60
            reply_text(event, configuration, "請在 60 秒內輸入該管理員的方便識別名稱（例如：小明），或輸入 # 取消：")
            return True
            
        elif self.step == 2:
            display_name = user_text.strip()
            if not display_name:
                reply_text(
                    event, 
                    configuration, 
                    "⚠️ 名稱不能為空，請重新輸入該管理員的方便識別名稱，或輸入 # 取消："
                )
                return True
                
            from src.utils.security import security_manager
            security_manager.add_manager(self.target_id, display_name)
            reply_text(event, configuration, f"✅ 成功將管理員 {display_name} ({self.target_id}) 加入全域管理員名單。")
            return False
            
        return False

class AddWhitelistSession(ConversationSession):
    def __init__(self, user_id: str, duration_sec: int = 60):
        super().__init__(user_id, duration_sec)
        self.step = 1
        self.target_id = None

    def handle_message(self, event: MessageEvent, configuration: Configuration, user_text: str, dispatcher: any) -> bool:
        if user_text == "#":
            reply_text(event, configuration, "已取消新增成員。")
            return False
            
        import re
        if self.step == 1:
            if not re.match(r"^U[a-fA-F0-9]{32}$", user_text):
                reply_text(
                    event, 
                    configuration, 
                    "⚠️ LINE ID 格式錯誤，必須為 U 開頭後接 32 位十六進位字元。\n請重新輸入，或輸入 # 取消："
                )
                return True
                
            self.target_id = user_text
            self.step = 2
            self.expire_at = time.time() + 60
            reply_text(event, configuration, "請在 60 秒內輸入該成員的方便識別名稱（例如：大雄），或輸入 # 取消：")
            return True
            
        elif self.step == 2:
            display_name = user_text.strip()
            if not display_name:
                reply_text(
                    event, 
                    configuration, 
                    "⚠️ 名稱不能為空，請重新輸入該成員的方便識別名稱，或輸入 # 取消："
                )
                return True
                
            from src.utils.security import security_manager
            from src.config import load_config
            config = load_config()
            league_id = config.get("LEAGUE_ID")
            if league_id:
                security_manager.add_to_league_whitelist(league_id, self.target_id, display_name)
                reply_text(event, configuration, f"✅ 成功將成員 {display_name} ({self.target_id}) 加入此聯盟的白名單成員。")
            else:
                reply_text(event, configuration, "⚠️ 尚未設置聯盟 ID，無法新增白名單成員。")
            return False
            
        return False
