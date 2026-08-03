import logging
import re
import os
import json
import time
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, FlexMessage, FlexContainer
from src.handlers.dispatcher import CommandDispatcher
from src.llm.llm_agent import LLMAgent
from src.config import load_config
from src.utils.session_manager import get_active_session, clear_active_session
from src.utils.path_utils import get_league_team_mapping_path

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
        # 0.7 攔截白名單成員管理指令
        from src.utils.security import security_manager
        
        if user_text == "#新增白名單成員":
            is_manager = False
            if user_id:
                if security_manager.is_super_admin(user_id):
                    is_manager = True
                else:
                    config = load_config()
                    league_id = config.get("LEAGUE_ID")
                    if league_id and security_manager.is_league_manager(user_id, league_id):
                        is_manager = True
            if is_manager:
                from src.utils.session_manager import register_session, AddWhitelistSession
                register_session(AddWhitelistSession(user_id, duration_sec=60))
                self.reply_text(event, configuration, "請在 60 秒內輸入欲新增的白名單成員 LINE ID（例如：U123456...），或輸入 # 取消：")
            return

        if user_text == "#移除白名單成員":
            is_manager = False
            if user_id:
                if security_manager.is_super_admin(user_id):
                    is_manager = True
                else:
                    config = load_config()
                    league_id = config.get("LEAGUE_ID")
                    if league_id and security_manager.is_league_manager(user_id, league_id):
                        is_manager = True
            if is_manager:
                config = load_config()
                league_id = config.get("LEAGUE_ID")
                roles = security_manager._load_json(security_manager.league_roles_path, {})
                league_data = roles.get(league_id) or {} if league_id else {}
                whitelist = league_data.get("whitelist", {})
                if not whitelist:
                    self.reply_text(event, configuration, "ℹ️ 目前此聯盟無任何白名單成員。")
                else:
                    from src.visualizer.flex_builder import build_button_menu_card
                    buttons = []
                    for target_id, name in whitelist.items():
                        buttons.append((name, f"#確切移除白名單 {target_id}"))
                    flex_dict = build_button_menu_card("移除白名單成員", "請選擇欲移除的成員：", buttons)
                    self.reply_flex(event, configuration, "移除白名單成員選單", flex_dict)
            return

        if user_text.startswith("#確切移除白名單 "):
            is_manager = False
            if user_id:
                if security_manager.is_super_admin(user_id):
                    is_manager = True
                else:
                    config = load_config()
                    league_id = config.get("LEAGUE_ID")
                    if league_id and security_manager.is_league_manager(user_id, league_id):
                        is_manager = True
            if is_manager:
                target_id = user_text[len("#確切移除白名單 "):].strip()
                config = load_config()
                league_id = config.get("LEAGUE_ID")
                if league_id:
                    roles = security_manager._load_json(security_manager.league_roles_path, {})
                    league_data = roles.get(league_id) or {}
                    whitelist = league_data.get("whitelist", {})
                    display_name = whitelist.get(target_id, target_id)
                    
                    security_manager.remove_from_league_whitelist(league_id, target_id)
                    self.reply_text(event, configuration, f"✅ 成功將成員 {display_name} 移出白名單。")
            return

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
        result = self.llm_agent.analyze_intent(text, dispatcher=self.dispatcher)
        
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

    def _update_team_nickname(self, team_id: str, new_nickname: str) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            return
        mapping_path = get_league_team_mapping_path(league_id)
        
        mapping = {}
        if os.path.exists(mapping_path):
            try:
                with open(mapping_path, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
            except Exception:
                mapping = {}
                
        mapping[str(team_id)] = new_nickname
        
        try:
            os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
            with open(mapping_path, "w", encoding="utf-8") as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
        except Exception as e:
            import logging
            logging.error(f"[IntentRouter] 寫入暱稱對應檔失敗: {e}")

    def _update_league_settings(self, new_settings: dict) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            return
            
        from src.utils.path_utils import get_league_dir
        league_dir = get_league_dir(league_id)
        settings_path = os.path.join(league_dir, "settings.json")
        
        settings = {}
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                settings = {}
                
        settings.update(new_settings)
        
        try:
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            import logging
            logging.error(f"[IntentRouter] 寫入設定檔 settings.json 失敗: {e}")

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
