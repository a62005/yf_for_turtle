import re
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler

class InjuryHandler(BaseHandler):
    def __init__(self):
        # 匹配 #傷兵 加上後續參數
        self.pattern = re.compile(r"^#傷兵\s*(.+)?$")

    @property
    def instruction_desc(self) -> str:
        return """
- #傷兵 <玩家名稱>：查詢我們聯盟中特定玩家隊伍目前的傷兵名單（例如：#傷兵 韋哥）。
        """

    def can_handle(self, user_text: str) -> bool:
        return bool(self.pattern.match(user_text))

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        # 暫時留空，後續實作核心邏輯
        pass
