import logging
import re
import os
import json
import time
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from src.handlers.dispatcher import CommandDispatcher
from src.llm.llm_agent import LLMAgent
from src.config import load_config
from src.utils.session_manager import (
    get_nickname_session, 
    clear_nickname_session,
    get_draft_time_session,
    clear_draft_time_session
)
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
        user_text = event.message.text.strip() if event.message and hasattr(event.message, 'text') else ""
        if not user_text:
            return False

        # 多聯盟未綁定防護：若 league_id 未設定，僅放行指定設定指令或活動會話
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            user_id = getattr(event.source, "user_id", None)
            is_active_session = False
            if user_id:
                if get_nickname_session(user_id) or get_draft_time_session(user_id):
                    is_active_session = True
            
            is_allowed_cmd = (user_text == "#設置" or user_text == "#我的ID" or user_text.startswith("#設置聯盟ID"))
            if not (is_allowed_cmd or is_active_session):
                return False

        # 1. 指令優先
        if user_text.startswith("#"):
            return True

        # 2. 單聊必定處理
        if event.source.type == "user":
            return True

        # 3. 活動中 Session 優先（在群組也不需要被 @提及）
        user_id = getattr(event.source, "user_id", None)
        if user_id:
            if get_nickname_session(user_id) or get_draft_time_session(user_id):
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
            # 1. 攔截選秀時間會話
            draft_session = get_draft_time_session(user_id)
            if draft_session:
                if user_text.startswith("#"):
                    clear_draft_time_session(user_id)
                else:
                    parsed = self.llm_agent.parse_draft_date(user_text)
                    if parsed.get("success") and parsed.get("date"):
                        date_val = parsed["date"]
                        self._update_league_settings({"DRAFT_DATE": date_val})
                        clear_draft_time_session(user_id)
                        self.reply_text(event, configuration, f"✅ 成功將選秀時間修改為：{date_val}")
                    else:
                        self.reply_text(
                            event, 
                            configuration, 
                            "⚠️ 無法解析您輸入的時間格式，請重新輸入（例如：2026-10-15 19:30），或輸入 # 取消"
                        )
                    return

            # 2. 攔截暱稱設定會話
            session = get_nickname_session(user_id)
            if session:
                # 用戶發送標準指令 (# 開頭) 則主動重置會話，不進行攔截
                if user_text.startswith("#"):
                    clear_nickname_session(user_id)
                else:
                    team_id = session["team_id"]
                    self._update_team_nickname(team_id, user_text)
                    clear_nickname_session(user_id)
                    self.reply_text(event, configuration, f"✅ 成功將暱稱修改為：{user_text}")
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
        commands_desc = self.dispatcher.get_all_instruction_descs()
        mapping = self._load_team_mapping()
        players_list = ", ".join(mapping.values()) if mapping else ""
        
        # Load league metadata to provide dynamic temporal context to LLM
        temporal_context = ""
        try:
            from src.utils.cache_utils import load_league_metadata
            from src.utils.time_utils import get_pacific_date
            
            meta = load_league_metadata()
            today_str = get_pacific_date()
            current_week = meta.get("date_to_week", {}).get(today_str)
            end_week = meta.get("end_week")
            
            parts = [f"今天的太平洋時間日期為：{today_str}。"]
            if current_week:
                parts.append(f"目前聯賽進行到第 {current_week} 週。")
            if end_week:
                parts.append(f"聯賽的最後一週（例行賽結束週）為第 {end_week} 週。")
            temporal_context = "".join(parts)
        except Exception as te:
            logging.error(f"[IntentRouter] 獲取時間/週數上下文失敗: {te}")
            
        result = self.llm_agent.analyze_intent(text, commands_desc, players_list, temporal_context)
        
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
