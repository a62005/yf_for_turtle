import re
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.utils.security import security_manager

class SuperAdminHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_super_admin = True
        self.exclude_from_llm = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip().startswith("#新增白名單")
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = re.match(r"^#新增白名單\s+(U[a-fA-F0-9]{32})$", user_text)
        if not match:
            self.reply_text(event, configuration, "格式錯誤，請使用：#新增白名單 <LINE_ID>")
            return
            
        target_id = match.group(1)
        if security_manager.add_to_whitelist(target_id):
            self.reply_text(event, configuration, f"成功將 ID 加入白名單：{target_id}")
        else:
            self.reply_text(event, configuration, f"將 ID 加入白名單失敗：{target_id}")

    @property
    def instruction_desc(self) -> str:
        return "#新增白名單 <LINE_ID> : (限超級管理員) 將指定 LINE ID 加入系統白名單"
