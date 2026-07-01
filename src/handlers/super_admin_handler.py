import re
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.utils.security import security_manager
from src.utils.session_manager import set_add_manager_session

class SuperAdminHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_super_admin = True
        self.exclude_from_llm = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#新增管理員"
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_id = event.source.user_id
        set_add_manager_session(user_id, step=1, duration_sec=60)
        self.reply_text(event, configuration, "請在 60 秒內輸入欲新增的管理員 LINE ID（例如：U123456...），或輸入 # 取消：")

    @property
    def instruction_desc(self) -> str:
        return "#新增管理員 : (限超級管理員) 指派並新增一名全域管理員"

