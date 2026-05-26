import re
import os
import sys
import psutil
import logging
import subprocess
from datetime import datetime, timedelta
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
from .base_handler import BaseHandler

# Required project imports
from src.config import load_config
from src.cache_utils import load_league_metadata, is_empty_data, save_league_metadata
from src.utils.time_utils import get_pacific_date, get_fantasy_week
from src.fetcher import YahooFantasyFetcher
from src.utils.job_tracker import JobTracker

def get_tw_hour():
    tw_tz = pytz.timezone("Asia/Taipei")
    return datetime.now(tw_tz).hour

class StatsHandler(BaseHandler):
    def __init__(self):
        self.combined_pattern = re.compile(r"^#戰績$")
        self.yesterday_pattern = re.compile(r"^#戰績昨天$")
        self.last_week_pattern = re.compile(r"^#戰績上週$")
        self.specific_week_pattern = re.compile(r"^#戰績W(\d+)$", re.IGNORECASE)
        self.specific_date_pattern = re.compile(r"^#戰績(\d{8})$")

    def parse_command(self, user_text: str) -> tuple[str | None, str | int | None]:
        if self.combined_pattern.match(user_text):
            return "combined", None
        elif self.yesterday_pattern.match(user_text):
            return "yesterday", None
        elif self.last_week_pattern.match(user_text):
            return "last_week", None

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

    def _get_week_end_date(self, week: int) -> str | None:
        meta = load_league_metadata()
        week_str = str(week)
        if "week_dates" in meta and week_str in meta["week_dates"]:
            return meta["week_dates"][week_str]
        
        config = load_config()
        fetcher = YahooFantasyFetcher(config["LEAGUE_ID"])
        end_date = fetcher.fetch_week_end_date(config["LEAGUE_ID"], week)
        
        if end_date:
            if "week_dates" not in meta:
                meta["week_dates"] = {}
            meta["week_dates"][week_str] = end_date
            save_league_metadata(meta)
        return end_date

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        cmd_type, cmd_val = self.parse_command(user_text)
        
        if not cmd_type:
            return
            
        config = load_config()
        meta = load_league_metadata()
        today_pacific = get_pacific_date()
        today_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(today_pacific, "%Y-%m-%d"))
        
        is_offseason = meta.get('end_date') and today_pacific > meta['end_date']
        
        # Calculate target_date and target_week based on cmd_type
        target_date = None
        target_week = None
        
        start_date = meta.get('start_date') or config.get("DEFAULT_SEASON_START", "2025-10-21")
        date_to_week = meta.get("date_to_week", {})
        
        if cmd_type == "specific_date":
            target_date = cmd_val
            target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(target_date, "%Y-%m-%d"))
            target_week = date_to_week.get(target_date) or get_fantasy_week(start_date, target_dt)
        elif cmd_type == "specific_week":
            target_week = cmd_val
        elif cmd_type == "yesterday":
            target_dt = today_dt - timedelta(days=1)
            target_date = target_dt.strftime("%Y-%m-%d")
            target_week = date_to_week.get(target_date) or get_fantasy_week(start_date, target_dt)
        elif cmd_type == "last_week":
            current_week = date_to_week.get(today_pacific) or get_fantasy_week(start_date, today_dt)
            target_week = max(1, current_week - 1)
        elif cmd_type == "combined":
            # Default #戰績 logic
            target_date = today_pacific
            if is_offseason:
                logging.info(f"[SYSTEM] 休賽季導向: {today_pacific} > {meta['end_date']}")
                target_date = meta['end_date']
            target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(target_date, "%Y-%m-%d"))
            target_week = date_to_week.get(target_date) or get_fantasy_week(start_date, target_dt)
            if meta.get('end_week') and target_week > meta['end_week']:
                target_week = meta['end_week']
                
        # Validate week limits (fix for out-of-bounds bug)
        if target_week is not None and meta.get('end_week'):
            if target_week > meta['end_week'] or target_week < 1:
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當週戰績")]))
                return
                
        # Lazy load date for week queries if date isn't set yet
        if not target_date and target_week:
            fetched_date = self._get_week_end_date(target_week)
            if not fetched_date:
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當週戰績")]))
                return
            target_date = fetched_date

        # Future date guard
        if cmd_type != "specific_week" and cmd_type != "last_week" and target_date > today_pacific:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="我不是未來人，無法提供未來數據")]))
            return

        # Past date guard
        if meta.get('start_date') and target_date < meta['start_date']:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當天數據")]))
            return

        # Unified image cache key
        img_filename = f"{target_date}_combined.png"
        cache_key = f"{target_date}_combined"

        # The rest is the same standard cache checking/execution
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        img_path = os.path.join(project_root, "data", "images", img_filename)
        
        if os.path.exists(img_path):
            logging.info(f"[CACHE] 命中圖片快取: {img_filename}")
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
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當天數據")]))
            return

        is_current = cmd_type == "combined"
        if is_current and not is_offseason and get_tw_hour() < 14:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="請於 14:00 後再進行查詢。")]))
            return
            
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        tracker = JobTracker(mode=config.get("STORAGE_TYPE", "local"), bucket_name=bucket_name)
        
        user_id = event.source.user_id if hasattr(event.source, 'user_id') else "unknown"
        is_new_job = tracker.add_job(cache_key, user_id)
        
        if not is_new_job:
            logging.info(f"[TRACKER] 任務正在執行中，加入等待名單: {cache_key}")
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="數據更新中，稍後將主動通知您")]))
            return

        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="數據更新中，請稍候...")]))
        
        task_mode = config.get("TASK_MODE", "subprocess")
        
        if task_mode == "pubsub":
            import json
            from google.cloud import pubsub_v1
            publisher = pubsub_v1.PublisherClient()
            project_id = os.getenv("GCP_PROJECT_ID")
            topic_id = os.getenv("PUBSUB_TOPIC_NAME")
            topic_path = publisher.topic_path(project_id, topic_id)
            
            payload = json.dumps({
                "target_date": target_date,
                "target_week": target_week,
                "cache_key": cache_key
            }).encode("utf-8")
            
            publisher.publish(topic_path, data=payload)
            logging.info(f"[TASK] 啟動背景更新任務 (Pub/Sub)")
        else:
            env = os.environ.copy()
            env["TEST_DATE"] = target_date
            if target_week:
                env["TEST_WEEK"] = str(target_week)
            env["MODE"] = "combined" 
            env["CACHE_KEY"] = cache_key
            
            logging.info(f"[TASK] 啟動背景更新任務 (main.py)，模式: combined")
            subprocess.Popen([sys.executable, os.path.join(project_root, "main.py")], env=env)
