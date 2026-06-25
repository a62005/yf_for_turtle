from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler

class SettingsHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#設置"
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        settings_text = (
            "⚙️ 系統設置清單 ⚙️\n\n"
            "目前可用的設定項目與系統資訊：\n"
            "1. 數據更新狀態：已啟用自動快取\n"
            "2. 當前聯盟 ID (LEAGUE_ID)：請參閱環境設定\n"
            "3. LLM 助理狀態：已連線 (Gemini 3.5 Flash)\n\n"
            "※ 本指令僅供白名單成員存取。"
        )
        self.reply_text(event, configuration, settings_text)

    @property
    def instruction_desc(self) -> str:
        return "#設置 : (限白名單) 顯示系統設置清單"
