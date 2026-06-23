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
from src.llm.prompts.world_cup_match_search import analyze_football_matchup

WORLD_CUP_TEAMS = {
    # A組
    "墨西哥", "南非", "韓國", "捷克", "南韓",
    # B組
    "加拿大", "波赫", "波士尼亞與赫塞哥維納", "波士尼亞", "卡達", "卡達", "瑞士",
    # C組
    "巴西", "摩洛哥", "海地", "蘇格蘭",
    # D組
    "美國", "巴拉圭", "澳洲", "澳大利亞", "土耳其", "土耳其",
    # E組
    "德國", "庫拉索", "象牙海岸", "科特迪瓦", "厄瓜多",
    # F組
    "荷蘭", "日本", "瑞典", "突尼西亞",
    # G組
    "比利時", "埃及", "伊朗", "紐西蘭",
    # H組
    "西班牙", "維德角", "佛得角", "沙烏地阿拉伯", "沙烏地", "沙特", "烏拉圭",
    # I組
    "法國", "塞內加爾", "伊拉克", "挪威",
    # J組
    "阿根廷", "阿爾及利亞", "奧地利", "約旦",
    # K組
    "葡萄牙", "剛果民主共和國", "民主剛果", "剛果民主", "剛果金", "剛果", "烏茲別克", "哥倫比亞",
    # L組
    "英格蘭", "克羅埃西亞", "克羅地亞", "迦納", "加納", "巴拿馬"
}

class FootballHandler(BaseHandler):
    def __init__(self):
        # 支援空格、vs、VS、對、對戰作為兩隊的分隔符
        self.pattern = re.compile(r"^#足球\s+(\S+)\s*(?:vs|VS|對|對戰|\s)\s*(\S+)$")

    def can_handle(self, user_text: str) -> bool:
        user_text = user_text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return False
            
        config = load_config()
        if not bool(config.get("ENABLE_FOOTBALL_ANALYSIS", False)):
            return False
            
        team_a = match.group(1)
        team_b = match.group(2)
        return team_a in WORLD_CUP_TEAMS and team_b in WORLD_CUP_TEAMS

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
