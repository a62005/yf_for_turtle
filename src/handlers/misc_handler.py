import re
import os
import logging
from datetime import datetime
import pytz

from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import (
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    ImageMessage,
    Configuration
)

from .base_handler import BaseHandler
from src.config import load_config
from src.utils.cache_utils import load_league_metadata, save_league_metadata
from src.utils.time_utils import get_pacific_date
from src.llm.llm_agent import LLMAgent

class MiscHandler(BaseHandler):
    def __init__(self):
        self.pattern = re.compile(r"^#(?:開季|選秀|獎金|幫助|[hH][eE][lL][pP])$")

    @property
    def instruction_desc(self) -> str:
        return """
- #運勢：測試運勢或運氣。
        """

    def can_handle(self, user_text: str) -> bool:
        user_text = user_text.strip()
        return bool(self.pattern.match(user_text))

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        league_id = None
        if configuration:
            if hasattr(configuration, "get"):
                league_id = configuration.get("LEAGUE_ID")
            else:
                league_id = getattr(configuration, "LEAGUE_ID", None)
        
        if league_id and str(league_id).startswith("mlb.l."):
            self.reply_text(event, configuration, "⚠️ 此功能目前僅支援 NBA 聯賽。")
            return

        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        meta = load_league_metadata() or {}
        end_date = meta.get("end_date")
        today_pacific = get_pacific_date()
        is_offseason = bool(end_date and today_pacific > end_date)

        if user_text in ("#開季", "#選秀"):
            if not is_offseason:
                logging.info(f"Not offseason, ignoring {user_text}")
                return

        if user_text == "#開季":
            self._handle_season_start(event, configuration)
        elif user_text == "#選秀":
            self._handle_draft_countdown(event, configuration)
        elif user_text == "#獎金":
            self._handle_prize(event, configuration)
        elif user_text.startswith("#") and user_text[1:].lower() in ("幫助", "help"):
            self._handle_help(event, configuration)

    def _calculate_countdown(self, target_time_str: str) -> str:
        taipei_tz = pytz.timezone("Asia/Taipei")
        now_taipei = datetime.now(taipei_tz)
        
        try:
            target_dt_naive = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            target_dt_naive = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M")
            
        target_dt = taipei_tz.localize(target_dt_naive)
        
        if now_taipei >= target_dt:
            return "已經到達！"
        
        diff = target_dt - now_taipei
        
        days = diff.days
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        return f"{days} 天 {hours} 小時 {minutes} 分鐘"

    def _handle_season_start(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        today_pacific = get_pacific_date()
        target_time_str = None
        
        # a. 優先讀取自訂的開季日期 NEXT_SEASON_START_DATE (來自 settings.json)
        next_season_val = config.get("NEXT_SEASON_START_DATE")
        if next_season_val and isinstance(next_season_val, str) and next_season_val.strip() != "":
            target_time_str = next_season_val
            
        # b. 若無，則退回讀取 metadata.json 中的 next_season_start_date 或 start_date
        meta = None
        if not target_time_str:
            meta = load_league_metadata() or {}
            if "next_season_start_date" in meta:
                target_time_str = meta["next_season_start_date"]
            else:
                meta_start = meta.get("start_date")
                if meta_start and meta_start > today_pacific:
                    target_time_str = f"{meta_start} 08:00:00"
                
        # c. 若都無，啟動 LLM 網路搜尋，搜尋成功後將開季日期以 {"next_season_start_date": start_date} 寫入 settings.json
        if not target_time_str:
            logging.info("[MiscHandler] 啟動 LLM 搜尋新賽季開始時間...")
            agent = LLMAgent()
            
            # 推估新賽季的年份：若當前月份大於等於10月，新賽季在明年，否則在今年
            current_year = datetime.now().year
            nba_year = current_year if datetime.now().month < 10 else current_year + 1
            
            res = agent.search_nba_season_start(nba_year)
            if res.get("success") and res.get("start_date"):
                target_time_str = res["start_date"]
                self._update_settings_file({"next_season_start_date": target_time_str})
                logging.info(f"[MiscHandler] 成功將 LLM 搜尋到的開季時間寫入 settings.json: {target_time_str}")
                
        # 4. 回覆或倒數
        if not target_time_str:
            self.reply_text(event, configuration, "🏀 無法獲取新賽季開季時間")
            return
            
        countdown_text = self._calculate_countdown(target_time_str)
        if countdown_text == "已經到達！":
            self.reply_text(event, configuration, "🏀 新賽季已經開打囉！")
        else:
            formatted_date = target_time_str
            try:
                dt = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
                formatted_date = f"{dt.year}年{dt.month}月{dt.day}日"
            except Exception:
                try:
                    dt = datetime.strptime(target_time_str.split()[0], "%Y-%m-%d")
                    formatted_date = f"{dt.year}年{dt.month}月{dt.day}日"
                except Exception:
                    pass
            
            reply_content = (
                f"🏀 新賽季即將開始以下時間開打：\n"
                f"👉 {formatted_date}\n"
                f"🏀 距離新賽季開季還有：\n"
                f"👉 {countdown_text}"
            )
            self.reply_text(event, configuration, reply_content)

    def _update_settings_file(self, new_data: dict) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            return
            
        from src.utils.path_utils import get_league_dir
        import json
        
        league_dir = get_league_dir(league_id)
        settings_path = os.path.join(league_dir, "settings.json")
        
        settings = {}
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                settings = {}
                
        settings.update(new_data)
        
        try:
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"[MiscHandler] 寫入設定檔 settings.json 失敗: {e}")

    def _handle_draft_countdown(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        target_time_str = config.get("DRAFT_DATE")
        if not target_time_str or not isinstance(target_time_str, str) or target_time_str.strip() == "":
            logging.info("DRAFT_DATE not configured, ignoring")
            return
        
        target_time_str = target_time_str.strip()
        countdown_text = self._calculate_countdown(target_time_str)
        if countdown_text == "已經到達！":
            self.reply_text(event, configuration, "⚔️ 聯盟選秀已經結束囉！")
            return
            
        formatted_date = target_time_str
        try:
            dt = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
            formatted_date = f"{dt.year}年{dt.month}月{dt.day}日 {dt.hour:02d}:{dt.minute:02d}"
        except ValueError:
            try:
                dt = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M")
                formatted_date = f"{dt.year}年{dt.month}月{dt.day}日 {dt.hour:02d}:{dt.minute:02d}"
            except Exception:
                pass
                
        reply_content = (
            "⚔️ 聯盟選秀即將開始以下時間舉行：\n"
            f"👉 {formatted_date}\n"
            "⚔️ 距離聯盟選秀還有：\n"
            f"👉 {countdown_text}"
        )
        self.reply_text(event, configuration, reply_content)

    def _handle_prize(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        prize_image_path = config.get("PRIZE_IMAGE_PATH") or "data/images/bonus.png"
        
        from src.utils.path_utils import get_league_image_dir
        league_img_dir = get_league_image_dir()
        filename = os.path.basename(prize_image_path)
        img_path = os.path.join(league_img_dir, filename)
        
        if not os.path.exists(img_path):
            if os.path.exists(prize_image_path):
                img_path = prize_image_path
            else:
                project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                resolved_path = os.path.join(project_root, prize_image_path)
                if os.path.exists(resolved_path):
                    img_path = resolved_path
                else:
                    default_bonus = os.path.join(project_root, "data", "images", "bonus.png")
                    if os.path.exists(default_bonus):
                        img_path = default_bonus
                    else:
                        logging.info("Prize image path does not exist anywhere, ignoring")
                        return
                        
        server_url = config.get("SERVER_URL")
        if not server_url:
            logging.info("SERVER_URL not configured, ignoring")
            return
            
        server_url = server_url.rstrip("/")
        
        if server_url.startswith("http://"):
            server_url = server_url.replace("http://", "https://")
        elif not server_url.startswith("https://"):
            server_url = f"https://{server_url}"
            
        img_url = f"{server_url}/images/{filename}"
        
        reply_img = ImageMessage(original_content_url=img_url, preview_image_url=img_url)
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[reply_img]
                )
            )

    def _handle_help(self, event: MessageEvent, configuration: Configuration) -> None:
        default_help = (
            "👋 您好！歡迎使用聯賽數據助手。\n\n"
            "【常用指令】\n"
            "● #戰績 ：查詢當日聯賽綜合戰績\n"
            "● #對戰 肥儒 ：查詢指定玩家當週即時 9-Cat 對決\n"
            "● #玩家 肥儒 ：查詢指定玩家今日累積數據與排名\n"
            "● #球員 老詹 ：查詢指定球員今日即時比賽表現\n\n"
            "※ 提示：輸入「#幫助」可獲取完整的指令複製清單。"
        )
        
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        help_file_path = os.path.join(project_root, "data", "help.txt")
        
        reply_content = default_help
        try:
            if os.path.exists(help_file_path):
                with open(help_file_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        reply_content = content
            else:
                logging.warning(f"Help file not found at {help_file_path}, using fallback.")
        except Exception as e:
            logging.error(f"Failed to read help file at {help_file_path}: {e}, using fallback.")
            
        self.reply_text(event, configuration, reply_content)

    def reply_text(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=text)]
                )
            )


SeasonCountdownHandler = MiscHandler

