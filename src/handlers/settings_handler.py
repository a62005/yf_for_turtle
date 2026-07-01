from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.visualizer.flex_builder import build_button_menu_card

class SettingsHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        self.exclude_from_llm = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() in ["#設置", "#設定", "#Setting", "#setting"]
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        
        if not league_id:
            title = "系統初始化設置"
            subtitle = None
            buttons = [("設置聯盟 ID", "#設置聯盟ID ")]
        else:
            title = f"聯盟設置 (ID: {league_id})"
            subtitle = None
            
            # 判斷是否為休賽季
            from src.utils.cache_utils import load_league_metadata
            from src.utils.time_utils import get_pacific_date
            meta = load_league_metadata(league_id) or {}
            end_date = meta.get("end_date")
            today_pacific = get_pacific_date()
            is_offseason = bool(end_date and today_pacific > end_date)
            
            buttons = []
            if is_offseason:
                buttons.append(("設置選秀時間", "#設置選秀時間"))
                buttons.append(("設置開季時間", "#設置開季時間"))
                
            buttons.extend([
                ("設置玩家暱稱", "#設置玩家暱稱"),
                ("設置獎金", "#設置獎金"),
                (None, None),
                ("移除聯盟ID", "#移除聯盟ID")
            ])
            
        flex_dict = build_button_menu_card(title, subtitle, buttons)
        self.reply_flex(event, configuration, "設置選單", flex_dict)

    @property
    def instruction_desc(self) -> str:
        return "#設置 : (限白名單) 顯示系統設置選單"

