from collections.abc import Callable
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.utils.security import security_manager
from src.utils.session_manager import register_session, AddWhitelistSession
from src.visualizer.flex_builder import build_button_menu_card


class WhitelistHandler(BaseHandler):
    """處理聯盟白名單成員之新增、移除選單與確切移除指令。"""

    def __init__(
        self,
        reply_text_fn: Callable | None = None,
        reply_flex_fn: Callable | None = None,
        config_loader: Callable | None = None,
    ):
        super().__init__()
        self.exclude_from_llm = True
        self._reply_text_fn = reply_text_fn
        self._reply_flex_fn = reply_flex_fn
        self._config_loader = config_loader

    def _load_config(self) -> dict:
        if self._config_loader is not None:
            return self._config_loader() or {}
        from src.config import load_config
        return load_config() or {}

    def _send_text(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
        if self._reply_text_fn is not None:
            self._reply_text_fn(event, configuration, text)
        else:
            self.reply_text(event, configuration, text)

    def _send_flex(self, event: MessageEvent, configuration: Configuration, alt_text: str, flex_dict: dict) -> None:
        if self._reply_flex_fn is not None:
            self._reply_flex_fn(event, configuration, alt_text, flex_dict)
        else:
            self.reply_flex(event, configuration, alt_text, flex_dict)

    def _is_manager(self, user_id: str | None, league_id: str | None) -> bool:
        if not user_id:
            return False
        if security_manager.is_super_admin(user_id):
            return True
        return bool(league_id and security_manager.is_league_manager(user_id, league_id))

    def can_handle(self, user_text: str) -> bool:
        text = (user_text or "").strip()
        if text in ("#新增白名單成員", "#移除白名單成員"):
            return True
        if user_text and user_text.startswith("#確切移除白名單 ") and user_text[len("#確切移除白名單 "):].strip():
            return True
        return False

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = (event.message.text or "").strip()
        user_id = getattr(event.source, "user_id", None) if getattr(event, "source", None) else None
        config = self._load_config()
        league_id = config.get("LEAGUE_ID")

        if not self._is_manager(user_id, league_id):
            return

        if user_text == "#新增白名單成員":
            register_session(AddWhitelistSession(user_id, duration_sec=60))
            self._send_text(
                event,
                configuration,
                "請在 60 秒內輸入欲新增的白名單成員 LINE ID（例如：U123456...），或輸入 # 取消：",
            )
            return

        if user_text == "#移除白名單成員":
            whitelist = security_manager.get_league_whitelist(league_id)
            if not whitelist:
                self._send_text(event, configuration, "ℹ️ 目前此聯盟無任何白名單成員。")
            else:
                buttons = [(name, f"#確切移除白名單 {target_id}") for target_id, name in whitelist.items()]
                flex_dict = build_button_menu_card("移除白名單成員", "請選擇欲移除的成員：", buttons)
                self._send_flex(event, configuration, "移除白名單成員選單", flex_dict)
            return

        if user_text.startswith("#確切移除白名單 "):
            target_id = user_text[len("#確切移除白名單 "):].strip()
            if league_id and target_id:
                whitelist = security_manager.get_league_whitelist(league_id)
                display_name = whitelist.get(target_id, target_id)
                security_manager.remove_from_league_whitelist(league_id, target_id)
                self._send_text(event, configuration, f"✅ 成功將成員 {display_name} 移出白名單。")

    @property
    def instruction_desc(self) -> str:
        return "#新增白名單成員 / #移除白名單成員 : (限聯盟管理員) 管理聯盟白名單成員"
