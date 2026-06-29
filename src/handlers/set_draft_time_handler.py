from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.utils.session_manager import set_draft_time_session

class SetDraftTimeHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        self.exclude_from_llm = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#設置選秀時間"
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        
        if not league_id:
            self.reply_text(event, configuration, "⚠️ 聯賽 ID 尚未配置，無法設定選秀時間。")
            return
            
        user_id = event.source.user_id
        set_draft_time_session(user_id, True, duration_sec=60)
        
        self.reply_text(
            event, 
            configuration, 
            "👉 請在 60 秒內直接輸入新的選秀時間（格式：YYYY-MM-DD HH:MM）：\n例如：2026-10-15 19:30"
        )

    @property
    def instruction_desc(self) -> str:
        return "#設置選秀時間 : (限白名單) 調整聯盟的選秀時間"
