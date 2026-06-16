import re
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import (
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    Configuration
)

from .base_handler import BaseHandler
from src.config import load_config
from src.utils.football_analyzer import analyze_football_matchup

class FootballHandler(BaseHandler):
    def __init__(self):
        # 支援空格、vs、VS、對、對戰作為兩隊的分隔符
        self.pattern = re.compile(r"^#足球\s+(\S+)\s*(?:vs|VS|對|對戰|\s)\s*(\S+)$")

    def can_handle(self, user_text: str) -> bool:
        user_text = user_text.strip()
        if not self.pattern.match(user_text):
            return False
        config = load_config()
        return bool(config.get("ENABLE_FOOTBALL_ANALYSIS", False))

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        team_a = match.group(1)
        team_b = match.group(2)

        # 呼叫分析器進行對戰分析
        analysis_result = analyze_football_matchup(team_a, team_b)

        # 透過 reply_text 發送提示訊息與分析結果
        self.reply_text(
            event,
            configuration,
            f"🔍 正在為您分析 {team_a} 與 {team_b} 的對戰，請稍候...",
            analysis_result
        )

    def reply_text(self, event: MessageEvent, configuration: Configuration, *texts: str) -> None:
        messages = [TextMessage(text=t) for t in texts if t]
        if not messages:
            return
        try:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=messages
                    )
                )
        except Exception as e:
            logging.error(f"Failed to reply messages in FootballHandler: {e}")
