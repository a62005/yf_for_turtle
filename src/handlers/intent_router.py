import logging
import re
import os
import json
import time
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, FlexMessage, FlexContainer
from src.handlers.dispatcher import CommandDispatcher
from src.handlers.whitelist_handler import WhitelistHandler
from src.llm.llm_agent import LLMAgent
from src.config import load_config
from src.utils.session_manager import get_active_session, clear_active_session
from src.utils.path_utils import get_league_team_mapping_path

class IntentRouter:
    def __init__(self, dispatcher: CommandDispatcher, whitelist_handler: WhitelistHandler | None = None):
        self.dispatcher = dispatcher
        self.llm_agent = LLMAgent()
        self._bot_user_id = None
        self.whitelist_handler = whitelist_handler or WhitelistHandler(
            reply_text_fn=lambda ev, cfg, txt: self.reply_text(ev, cfg, txt),
            reply_flex_fn=lambda ev, cfg, alt, flex: self.reply_flex(ev, cfg, alt, flex),
            config_loader=lambda: load_config(),
        )

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
        if not (event.message and hasattr(event.message, 'text')):
            return False
        user_text = event.message.text.strip()
        user_id = getattr(event.source, "user_id", None)
        if not user_text:
            if user_id:
                if get_active_session(user_id):
                    return True
            return False

        # 多聯盟未綁定防護：若 league_id 未設定，僅放行指定設定指令或活動會話
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            user_id = getattr(event.source, "user_id", None)
            is_active_session = False
            if user_id:
                if get_active_session(user_id):
                    is_active_session = True
            
            from src.utils.security import security_manager
            is_whitelisted = security_manager.is_whitelisted(user_id) if user_id else False
            is_help_cmd = user_text.lower().strip() in ("#幫助", "#help", "#幫忙", "#更多")
            
            is_allowed_cmd = (
                user_text in ["#設置", "#設定", "#Setting", "#setting"] or 
                user_text == "#我的ID" or 
                user_text.startswith("#設置聯盟ID") or
                (is_whitelisted and is_help_cmd)
            )
            if not (is_allowed_cmd or is_active_session):
                return False

        # 1. 指令優先
        if user_text.startswith("#"):
            return True

        # 2. 單聊必定處理
        if event.source.type == "user":
            return True

        # 3. 活動中 Session 優先（在群組也不需要被 @提及）
        if user_id:
            if get_active_session(user_id):
                return True

        # 4. 群聊中必須被提及 (@提及)
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
        
        user_id = getattr(event.source, "user_id", None)
        if user_id:
            active_sess = get_active_session(user_id)
            if active_sess:
                from src.utils.session_manager import RemoveLeagueSession
                is_expected = isinstance(active_sess, RemoveLeagueSession) and user_text == "#確定移除聯盟ID"
                if user_text.startswith("#") and user_text != "#" and not is_expected:
                    clear_active_session(user_id)
                else:
                    should_continue = active_sess.handle_message(event, configuration, user_text, self.dispatcher)
                    if not should_continue:
                        clear_active_session(user_id)
                    return
        # 1. 優先處理標準指令
        if user_text.startswith("#"):
            has_registered_whitelist = (
                hasattr(self.dispatcher, "get_handler")
                and isinstance(self.dispatcher.get_handler(WhitelistHandler), WhitelistHandler)
            )
            if not has_registered_whitelist and self.whitelist_handler.can_handle(user_text):
                self.whitelist_handler.execute(event, configuration)
                return
            logging.info(f"[IntentRouter] 收到標準指令: {user_text}")
            self.dispatcher.handle(event, configuration)
            return

        # 2. 單聊與群組提及進行 LLM 解析
        is_private_chat = event.source.type == "user"
        is_mentioned = not is_private_chat  # 走到這代表不是指令，非單聊則必然是提及
        
        chat_type = "單聊" if is_private_chat else "群組提及"
        logging.info(f"[IntentRouter] 收到{chat_type}，開始 LLM 意圖解析: {user_text}")
        
        clean_text = self._clean_mention_text(user_text, event=event, configuration=configuration)
        self._handle_llm_flow(event, configuration, clean_text, is_mentioned)

    def _clean_mention_text(self, text: str, event: MessageEvent | None = None, configuration: Configuration | None = None) -> str:
        cleaned = text
        if event is not None and hasattr(event, "message") and hasattr(event.message, "mention") and event.message.mention:
            mentionees = getattr(event.message.mention, "mentionees", None) or []
            bot_user_id = self._get_bot_user_id(configuration) if configuration is not None else self._bot_user_id
            spans = []
            for m in mentionees:
                if getattr(m, "type", None) == "user" and (bot_user_id is None or getattr(m, "user_id", None) == bot_user_id):
                    idx = getattr(m, "index", None)
                    length = getattr(m, "length", None)
                    if isinstance(idx, int) and isinstance(length, int) and idx >= 0 and length > 0:
                        spans.append((idx, idx + length))
            if spans:
                for start, end in sorted(spans, key=lambda x: x[0], reverse=True):
                    if end <= len(cleaned):
                        cleaned = cleaned[:start] + cleaned[end:]
                cleaned = cleaned.strip()
            elif any(getattr(m, "type", None) == "user" and (bot_user_id is None or getattr(m, "user_id", None) == bot_user_id) for m in mentionees):
                cleaned = re.sub(r'^\s*@\S+\s*', '', cleaned).strip()

        cleaned = re.sub(r'(?i)@(?:bot|linebot|stinkyturtle)\s*', '', cleaned).strip()
        return cleaned

    def _is_known_league_manager(self, candidate_name: str) -> bool:
        """檢查名稱是否為本聯盟已註冊的聯賽玩家（比對 team_mapping.json 與本地最新日數據）。"""
        name_clean = str(candidate_name or "").strip()
        if not name_clean:
            return False
        name_lower = name_clean.lower()

        mapping = self._load_team_mapping()
        for val in mapping.values():
            if str(val).strip().lower() == name_lower:
                return True

        try:
            from src.handlers.local_user_stats_handler import LocalUserStatsHandler
            user_handler = self.dispatcher.get_handler(LocalUserStatsHandler) if hasattr(self.dispatcher, "get_handler") else None
            if user_handler is not None and user_handler.can_handle(f"#玩家 {name_clean}"):
                return True
        except Exception:
            pass
        return False

    def _normalize_routed_command(self, command_text: str) -> str:
        """
        防呆校驗：
        1. 若 LLM 轉出 '#玩家 <名稱>'（或 '#對戰 <名稱>'），但 <名稱> 根本不在聯賽玩家名單內（例如使用者輸入『泳池』想查 NBA 球員 Jordan Poole），
           自動將指令轉為 '#球員 <名稱>' 交由 LivePlayerHandler 解析，避免因找不到聯賽玩家而靜默。
        2. 若 <名稱> 確實存在於聯賽玩家名單內（即使與 NBA 球員撞名，如『喇叭』），則維持以聯賽玩家為主（'#玩家 <名稱>'）。
        """
        cmd = str(command_text or "").strip()
        m_user = re.match(r"^#玩家\s+(.+)$", cmd)
        if m_user:
            target_name = m_user.group(1).strip()
            if target_name and not self._is_known_league_manager(target_name):
                logging.info(
                    f"[IntentRouter] '{target_name}' 不在聯賽玩家名單內，自動將 '{cmd}' 改派為 '#球員 {target_name}'"
                )
                return f"#球員 {target_name}"
        return cmd

    def _handle_llm_flow(self, event: MessageEvent, configuration: Configuration, text: str, is_mentioned: bool = False) -> None:
        result = self.llm_agent.analyze_intent(text, dispatcher=self.dispatcher)
        
        if result.get("is_command") and result.get("command_text"):
            command_text = self._normalize_routed_command(result["command_text"])
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
            logging.info("[IntentRouter] 非標準查詢指令意圖（閒聊功能已關閉），靜默略過不回覆。")
            return

    def _load_team_mapping(self) -> dict:
        """Load and return the team mapping from json config file."""
        import os
        import json
        from src.utils.path_utils import get_league_team_mapping_path
        mapping_file = get_league_team_mapping_path()
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                import logging
                logging.error(f"Failed to load team mapping in IntentRouter: {e}")
        return {}

    def reply_text(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
        """Reply to the event with a text message."""
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=text)]
                )
            )

    def reply_flex(self, event: MessageEvent, configuration: Configuration, alt_text: str, flex_dict: dict) -> None:
        """Reply to user with a LINE Flex Message."""
        flex_container = FlexContainer.from_json(json.dumps(flex_dict))
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text=alt_text, contents=flex_container)]
                )
            )

    def route_image(self, event: MessageEvent, configuration: Configuration) -> None:
        """路由圖片訊息事件"""
        user_id = getattr(event.source, "user_id", None)
        if not user_id:
            return

        active_sess = get_active_session(user_id)
        if active_sess:
            try:
                from linebot.v3.messaging import MessagingApiBlob
                with ApiClient(configuration) as api_client:
                    blob_api = MessagingApiBlob(api_client)
                    image_bytes = blob_api.get_message_content(event.message.id)
                
                should_continue = active_sess.handle_image(event, configuration, image_bytes, self.dispatcher)
                if not should_continue:
                    clear_active_session(user_id)
            except Exception as e:
                logging.error(f"[IntentRouter] 下載圖片或處理失敗: {e}")
                self.reply_text(event, configuration, "⚠️ 圖片下載或儲存失敗，請稍後重試。")
