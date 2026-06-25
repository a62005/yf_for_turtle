from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.visualizer.flex_builder import build_button_menu_card

class SettingsHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#設置"
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        
        if not league_id:
            title = "⚙️ 系統初始化設置"
            subtitle = "目前尚未配置聯盟 ID，請先完成設置："
            buttons = [("設置聯盟 ID", "#設置聯盟ID ")]
        else:
            title = f"⚙️ 聯盟設置 (ID: {league_id})"
            subtitle = "可調整 the settings："
            buttons = [
                ("設置選秀時間 (即將推出)", ""),
                ("設置玩家暱稱 (即將推出)", ""),
                ("更換聯盟ID (即將推出)", ""),
                ("移除聯盟ID (即將推出)", "")
            ]
            
        flex_dict = build_button_menu_card(title, subtitle, buttons)
        self.reply_flex(event, configuration, "設置選單", flex_dict)

    @property
    def instruction_desc(self) -> str:
        return "#設置 : (限白名單) 顯示系統設置選單"

