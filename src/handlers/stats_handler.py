import re
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler

class StatsHandler(BaseHandler):
    def __init__(self):
        self.combined_pattern = re.compile(r"^#戰績$")
        self.daily_pattern = re.compile(r"^#當天戰績$")
        self.weekly_pattern = re.compile(r"^#當週戰績$")
        self.specific_week_pattern = re.compile(r"^#戰績W(\d+)$", re.IGNORECASE)
        self.specific_date_pattern = re.compile(r"^#戰績(\d{8})$")

    def parse_command(self, user_text: str) -> tuple[str | None, str | int | None]:
        if self.combined_pattern.match(user_text):
            return "combined", None
        elif self.daily_pattern.match(user_text):
            return "daily", None
        elif self.weekly_pattern.match(user_text):
            return "weekly", None
        
        m_week = self.specific_week_pattern.match(user_text)
        if m_week:
            return "specific_week", int(m_week.group(1))
            
        m_date = self.specific_date_pattern.match(user_text)
        if m_date:
            raw_date = m_date.group(1)
            return "specific_date", f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            
        return None, None

    def can_handle(self, user_text: str) -> bool:
        cmd_type, _ = self.parse_command(user_text)
        return cmd_type is not None

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        pass # To be implemented in next task
