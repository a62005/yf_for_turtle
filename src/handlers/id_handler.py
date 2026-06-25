from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler

class IdHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#我的ID"
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_id = event.source.user_id if event.source and hasattr(event.source, 'user_id') else "Unknown"
        self.reply_text(event, configuration, f"您的 LINE ID 為: {user_id}")

    @property
    def instruction_desc(self) -> str:
        return "#我的ID : 查詢您目前的 LINE User ID"
