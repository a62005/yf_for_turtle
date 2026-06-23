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

    def route(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip() if event.message and hasattr(event.message, 'text') else ""
        if not user_text:
            return

        # 1. 優先處理標準指令
        if user_text.startswith("#"):
            logging.info(f"[IntentRouter] 收到標準指令: {user_text}")
            self.dispatcher.handle(event, configuration)
            return

        # 2. 判斷是否為單聊
        is_private_chat = event.source.type == "user"
        
        # 3. 判斷群聊中的 @提及 (僅當 @機器人本尊 時觸發，排除 @其他人 與 @ALL)
        is_mentioned = False
        if event.source.type in ["group", "room"]:
            # 檢查 LINE 官方 mention 物件
            if hasattr(event.message, "mention") and event.message.mention:
                bot_user_id = self._get_bot_user_id(configuration)
                mentionees = event.message.mention.mentionees
                for m in mentionees:
                    if m.type == "user" and getattr(m, "user_id", None) == bot_user_id: 
                        is_mentioned = True
                    elif m.type == "all":
                        pass
            
            # 備用：檢查文字中手動輸入包含 @bot 等字樣
            lower_text = user_text.lower()
            if "@bot" in lower_text or "@linebot" in lower_text:
                is_mentioned = True

        # 4. 路由分流
        if is_private_chat or is_mentioned:
            chat_type = "單聊" if is_private_chat else "群組提及"
            logging.info(f"[IntentRouter] 收到{chat_type}，開始 LLM 意圖解析: {user_text}")
            
            clean_text = self._clean_mention_text(user_text)
            self._handle_llm_flow(event, configuration, clean_text)
        else:
            # 群組閒聊直接忽略，不留 Log
            pass

    def _clean_mention_text(self, text: str) -> str:
        return re.sub(r'(?i)@(?:bot|linebot)\s*', '', text).strip()

    def _handle_llm_flow(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
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
            reply_text = result.get("reply_text") or "我現在無法理解您的意思，請試著換個方式詢問。"
            logging.info(f"[IntentRouter] LLM 生成對話回覆: {reply_text}")
            
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )
