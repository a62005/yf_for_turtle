import logging
import re
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from src.handlers.dispatcher import CommandDispatcher
from src.llm.llm_agent import LLMAgent

class IntentRouter:
    def __init__(self, dispatcher: CommandDispatcher):
        self.dispatcher = dispatcher
        self.llm_agent = LLMAgent()
        self._bot_user_id = None

    def _get_bot_user_id(self, configuration: Configuration) -> str | None:
        """Fetch and cache the bot's own user_id."""
        if self._bot_user_id is None:
            try:
                with ApiClient(configuration) as api_client:
                    api = MessagingApi(api_client)
                    info = api.get_bot_info()
                    self._bot_user_id = info.user_id
                    logging.info(f"[IntentRouter] 成功取得 Bot User ID: {self._bot_user_id}")
            except Exception as e:
                logging.error(f"[IntentRouter] 獲取 Bot 資訊失敗: {e}")
        return self._bot_user_id

    def should_process(self, event: MessageEvent, configuration: Configuration) -> bool:
        """Determine if the message event should be processed by the bot."""
        user_text = event.message.text.strip() if event.message and hasattr(event.message, 'text') else ""
        if not user_text:
            return False

        # 1. 指令優先
        if user_text.startswith("#"):
            return True

        # 2. 單聊必定處理
        if event.source.type == "user":
            return True

        # 3. 群聊中必須被提及 (@提及)
        if event.source.type in ["group", "room"]:
            # 檢查官方 mention 物件
            if hasattr(event.message, "mention") and event.message.mention:
                bot_user_id = self._get_bot_user_id(configuration)
                for m in event.message.mention.mentionees:
                    if m.type == "user" and getattr(m, "user_id", None) == bot_user_id: 
                        return True
            # 備用：手動文字提及
            lower_text = user_text.lower()
            if "@bot" in lower_text or "@linebot" in lower_text:
                return True

        return False

    def route(self, event: MessageEvent, configuration: Configuration) -> None:
        if not self.should_process(event, configuration):
            return

        user_text = event.message.text.strip()
        
        # 1. 優先處理標準指令
        if user_text.startswith("#"):
            logging.info(f"[IntentRouter] 收到標準指令: {user_text}")
            self.dispatcher.handle(event, configuration)
            return

        # 2. 單聊與群組提及進行 LLM 解析
        is_private_chat = event.source.type == "user"
        is_mentioned = not is_private_chat  # 走到這代表不是指令，非單聊則必然是提及
        
        chat_type = "單聊" if is_private_chat else "群組提及"
        logging.info(f"[IntentRouter] 收到{chat_type}，開始 LLM 意圖解析: {user_text}")
        
        clean_text = self._clean_mention_text(user_text)
        self._handle_llm_flow(event, configuration, clean_text, is_mentioned)

    def _clean_mention_text(self, text: str) -> str:
        return re.sub(r'(?i)@(?:bot|linebot)\s*', '', text).strip()

    def _handle_llm_flow(self, event: MessageEvent, configuration: Configuration, text: str, is_mentioned: bool = False) -> None:
        commands_desc = self.dispatcher.get_all_instruction_descs()
        result = self.llm_agent.analyze_intent(text, commands_desc)
        
        if result.get("is_command") and result.get("command_text"):
            command_text = result["command_text"]
            logging.info(f"[IntentRouter] LLM 意圖匹配成功，轉化指令: {command_text}")
            
            try:
                event.message.text = command_text
            except AttributeError:
                class TextMessageWrapper:
                    def __init__(self, original_msg, new_text):
                        self.__dict__.update(original_msg.__dict__)
                        self.text = new_text
                event.message = TextMessageWrapper(event.message, command_text)
                
            self.dispatcher.handle(event, configuration)
        else:
            if is_mentioned and result.get("error"):
                logging.info("[IntentRouter] LLM 服務未啟用或異常，且為群組提及，不回覆任何訊息。")
                return

            reply_text = result.get("reply_text") or "我現在無法理解您的意思，請試著換個方式詢問。"
            logging.info(f"[IntentRouter] LLM 生成對話回覆: {reply_text}")
            
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )
