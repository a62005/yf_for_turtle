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
from src.cache_utils import load_league_metadata
from src.utils.time_utils import get_pacific_date

class MiscHandler(BaseHandler):
    def __init__(self):
        self.pattern = re.compile(r"^#(?:開季|選秀|獎金|幫助|[hH][eE][lL][pP])$")

    def can_handle(self, user_text: str) -> bool:
        user_text = user_text.strip()
        return bool(self.pattern.match(user_text))

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        meta = load_league_metadata() or {}
        end_date = meta.get("end_date")
        today_pacific = get_pacific_date()
        is_offseason = bool(end_date and today_pacific > end_date)

        if user_text == "#開季":
            if is_offseason:
                self._handle_season_start(event, configuration)
            else:
                logging.info("Not offseason, ignoring #開季")
                return
        elif user_text == "#選秀":
            if is_offseason:
                self._handle_draft_countdown(event, configuration)
            else:
                logging.info("Not offseason, ignoring #選秀")
                return
        elif user_text == "#獎金":
            self._handle_prize(event, configuration)
        elif user_text.startswith("#") and user_text[1:].lower() in ("幫助", "help"):
            self._handle_help(event, configuration)

    def _calculate_countdown(self, target_time_str: str) -> str:
        taipei_tz = pytz.timezone("Asia/Taipei")
        now_taipei = datetime.now(taipei_tz)
        
        target_dt_naive = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
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
        target_time_str = config.get("NEXT_SEASON_START_DATE")
        if not target_time_str:
            logging.info("NEXT_SEASON_START_DATE not configured, ignoring")
            return
        
        countdown_text = self._calculate_countdown(target_time_str)
        reply_content = f"🏀 距離 2026-27 新賽季開季還有：\n👉 {countdown_text}"
        self.reply_text(event, configuration, reply_content)

    def _handle_draft_countdown(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        target_time_str = config.get("DRAFT_DATE")
        if not target_time_str:
            logging.info("DRAFT_DATE not configured, ignoring")
            return
        
        countdown_text = self._calculate_countdown(target_time_str)
        reply_content = f"⚔️ 距離 2026-27 聯盟選秀還有：\n👉 {countdown_text}"
        self.reply_text(event, configuration, reply_content)

    def _handle_prize(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        prize_image_path = config.get("PRIZE_IMAGE_PATH")
        if not prize_image_path:
            logging.info("PRIZE_IMAGE_PATH not configured, ignoring")
            return
            
        # Resolve path in case it is relative to the project root
        if not os.path.exists(prize_image_path):
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            resolved_path = os.path.join(project_root, prize_image_path)
            if not os.path.exists(resolved_path):
                logging.info(f"Prize image path does not exist: {prize_image_path} (resolved: {resolved_path}), ignoring")
                return
            prize_image_path = resolved_path
            
        server_url = config.get("SERVER_URL")
        if not server_url:
            logging.info("SERVER_URL not configured, ignoring")
            return
            
        server_url = server_url.rstrip("/")
        filename = os.path.basename(prize_image_path)
        
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
        logging.info("Help command triggered, but temporarily doing nothing as per specification.")

    def reply_text(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=text)]
                )
            )
