import logging
from .factory import LLMProviderFactory
from .prompts.intent_router_prompt import SYSTEM_PROMPT

class LLMAgent:
    def __init__(self):
        try:
            self.provider = LLMProviderFactory.get_provider()
        except ValueError as e:
            logging.warning(f"[LLM] 警告：{e} LLM 功能將無法正常運作。")
            self.provider = None

        self.system_prompt = SYSTEM_PROMPT

    def analyze_intent(self, text: str, commands_desc: str, players_list: str = "", temporal_context: str = "") -> dict:
        if not self.provider:
            return {
                "is_command": False, 
                "command_text": None, 
                "reply_text": "系統目前未配置 AI 金鑰，無法為您服務。",
                "error": True
            }

        formatted_system = (
            self.system_prompt
            .replace("{commands_desc}", commands_desc)
            .replace("{players_list}", players_list)
            .replace("{temporal_context}", temporal_context)
        )
        try:
            return self.provider.generate_json(text, system_instruction=formatted_system, temperature=0.2)
        except Exception as e:
            logging.error(f"[LLM] 意圖解析失敗: {e}")
            from .agnes import AgnesProvider
            if isinstance(self.provider, AgnesProvider):
                return {
                    "is_command": False, 
                    "command_text": None, 
                    "reply_text": "我的大腦暫時離線了，請確認 Agnes AI 服務是否正常！",
                    "error": True
                }
            else:
                return {
                    "is_command": False, 
                    "command_text": None, 
                    "reply_text": "我的大腦暫時離線了，請稍後再試！",
                    "error": True
                }
