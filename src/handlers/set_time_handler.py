from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.utils.session_manager import register_session, DraftTimeSession, SeasonStartTimeSession

class SetTimeHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        self.exclude_from_llm = True
        
    def can_handle(self, user_text: str) -> bool:
        text = user_text.strip()
        return text in ("#設置選秀時間", "#設置開季時間")
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        user_text = event.message.text.strip()
        user_id = event.source.user_id
        
        if not league_id:
            time_type = "選秀時間" if user_text == "#設置選秀時間" else "開季時間"
            self.reply_text(event, configuration, f"⚠️ 聯賽 ID 尚未配置，無法設定{time_type}。")
            return
            
        if user_text == "#設置選秀時間":
            register_session(DraftTimeSession(user_id, duration_sec=60))
            self.reply_text(
                event, 
                configuration, 
                "👉 請在 60 秒內直接輸入新的選秀時間（格式：YYYY-MM-DD HH:MM）：\n例如：2026-10-15 19:30"
            )
        elif user_text == "#設置開季時間":
            register_session(SeasonStartTimeSession(user_id, duration_sec=60))
            self.reply_text(
                event, 
                configuration, 
                "👉 請在 60 秒內直接輸入開季時間（格式：YYYY-MM-DD HH:MM）：\n例如：2026-10-22 08:00"
            )

    @property
    def instruction_desc(self) -> str:
        return "#設置選秀時間 : (限白名單) 調整聯盟的選秀時間\n#設置開季時間 : (限白名單) 調整聯盟的開季時間"
