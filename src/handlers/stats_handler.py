import re
import os
import sys
import psutil
import logging
import subprocess
from datetime import datetime
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
from .base_handler import BaseHandler

# Required project imports
from src.config import load_config
from src.cache_utils import load_league_metadata, is_empty_data
from src.utils.time_utils import get_pacific_date, get_fantasy_week

def get_tw_hour():
    tw_tz = pytz.timezone("Asia/Taipei")
    return datetime.now(tw_tz).hour

class StatsHandler(BaseHandler):
    def __init__(self):
        self.combined_pattern = re.compile(r"^#戰績$")
        self.daily_pattern = re.compile(r"^#當天戰績$")
        self.weekly_pattern = re.compile(r"^#當週戰績$")
        self.specific_week_pattern = re.compile(r"^#戰績W(\d+)$", re.IGNORECASE)
        self.specific_date_pattern = re.compile(r"^#戰績(\d{8})$")

    def parse_command(self, user_text: str) -> tuple[str | None, str | int | None]:
        if self.combined_pattern.match(user_text):
            return "combined", None
        elif self.daily_pattern.match(user_text):
            return "daily", None
        elif self.weekly_pattern.match(user_text):
            return "weekly", None
        
        m_week = self.specific_week_pattern.match(user_text)
        if m_week:
            return "specific_week", int(m_week.group(1))
            
        m_date = self.specific_date_pattern.match(user_text)
        if m_date:
            raw_date = m_date.group(1)
            return "specific_date", f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            
        return None, None

    def can_handle(self, user_text: str) -> bool:
        cmd_type, _ = self.parse_command(user_text)
        return cmd_type is not None

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        cmd_type, cmd_val = self.parse_command(user_text)
        
        if not cmd_type:
            return
            
        config = load_config()
        meta = load_league_metadata()
        today_pacific = get_pacific_date()
        is_offseason = meta.get('end_date') and today_pacific > meta['end_date']
        
        target_date = cmd_val if cmd_type == "specific_date" else today_pacific
        
        if cmd_type != "specific_week" and target_date > today_pacific:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="我不是未來人，無法提供未來數據")]))
            return

        if cmd_type != "specific_week" and meta.get('start_date') and target_date < meta['start_date']:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當天數據")]))
            return

        is_undated_cmd = cmd_type in ["combined", "daily", "weekly"]
        if meta.get('end_date') and today_pacific > meta['end_date'] and is_undated_cmd:
            logging.info(f"[SYSTEM] 休賽季導向: {today_pacific} > {meta['end_date']}")
            target_date = meta['end_date']
            target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(target_date, "%Y-%m-%d"))
            target_week = get_fantasy_week(meta['start_date'], target_dt)
        else:
            target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(target_date, "%Y-%m-%d"))
            calculated_week = get_fantasy_week(meta.get('start_date') or config.get("DEFAULT_SEASON_START", "2025-10-21"), target_dt)
            if meta.get('end_week') and calculated_week > meta['end_week']:
                target_week = meta['end_week']
            else:
                target_week = cmd_val if cmd_type == "specific_week" else calculated_week

        if cmd_type != "specific_week" and meta.get('end_date') and target_date > meta['end_date']:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當天數據")]))
            return
        
        if cmd_type == "combined":
            img_filename = f"{target_date}_combined.png"
            cache_key = f"{target_date}_combined"
        elif cmd_type in ["daily", "specific_date"]:
            img_filename = f"{target_date}_daily.png"
            cache_key = f"{target_date}_daily"
        else: # weekly, specific_week
            img_filename = f"week_{target_week}_weekly.png"
            cache_key = f"week_{target_week}_weekly"

        # Note: os.path.dirname is resolving from src/handlers/stats_handler.py, so we need to go up two levels to get to project root
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        img_path = os.path.join(project_root, "data", "images", img_filename)
        
        if os.path.exists(img_path):
            logging.info(f"[CACHE] 命中圖片快取: {img_filename}")
            
            # Fetch SERVER_URL from env or config if needed, here we use os.getenv to mirror bot.py behavior safely
            SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')
            https_url = SERVER_URL.replace("http://", "https://")
            if not https_url.startswith("https://"):
                https_url = f"https://{https_url.lstrip('https://')}"
                
            img_url = f"{https_url}/images/{img_filename}"
            reply_img = ImageMessage(original_content_url=img_url, preview_image_url=img_url)
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply_img]))
            return

        if is_empty_data(cache_key):
            logging.info(f"[CACHE] 命中負向快取 (無數據): {cache_key}")
            err_msg = "查無當週數據" if "weekly" in cache_key else "查無當天數據"
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=err_msg)]))
            return

        is_current = cmd_type in ["combined", "daily", "weekly"]
        if is_current and not is_offseason and get_tw_hour() < 14:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="請於 14:00 後再進行查詢。")]))
            return
            
        lock_file = os.path.join(project_root, "data", f"{cache_key}_fetch.lock")
        os.makedirs(os.path.dirname(lock_file), exist_ok=True)
        try:
            fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            logging.warning(f"[LOCK] 任務正在執行中，跳過重複請求: {cache_key}")
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="數據更新中")]))
            return

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="數據更新中，請稍候再試...")]))
        
        env = os.environ.copy()
        env["FETCH_LOCK_PATH"] = lock_file
        env["TEST_DATE"] = target_date
        env["TEST_WEEK"] = str(target_week)
        
        logging.info(f"[TASK] 啟動背景更新任務 (main.py)，模式: {cmd_type}")
        subprocess.Popen([sys.executable, os.path.join(project_root, "main.py")], env=env)
