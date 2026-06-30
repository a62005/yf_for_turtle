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
from src.utils.cache_utils import load_league_metadata, is_empty_data, save_league_metadata
from src.utils.time_utils import get_pacific_date, get_fantasy_week
from src.fetcher import YahooFantasyFetcher

class StatsHandler(BaseHandler):
    def __init__(self):
        self.combined_pattern = re.compile(r"^#戰績$")
        self.yesterday_pattern = re.compile(r"^#戰績昨天$")
        self.last_week_pattern = re.compile(r"^#戰績上週$")
        self.specific_week_pattern = re.compile(r"^#戰績W(\d+)$", re.IGNORECASE)
        self.specific_date_pattern = re.compile(r"^#戰績(\d{8})$")

    @property
    def instruction_desc(self) -> str:
        return """
- #戰績：查詢當天的聯賽整體戰績。
- #戰績昨天：查詢昨天的聯賽整體戰績。
- #戰績上週：查詢上週的聯賽整體戰績。
- #戰績W<週數>：查詢特定週數的戰績（例如：#戰績W5）。
- #戰績<年月日>：查詢特定日期的戰績（例如：#戰績20251120）。
        """

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
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        meta = load_league_metadata(league_id)
        week_str = str(week)
        if "week_dates" in meta and week_str in meta["week_dates"]:
            return meta["week_dates"][week_str]
        
        fetcher = YahooFantasyFetcher(
            league_id=league_id,
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET")
        )
        end_date = fetcher.fetch_week_end_date(league_id, week)
        
        if end_date:
            if "week_dates" not in meta:
                meta["week_dates"] = {}
            meta["week_dates"][week_str] = end_date
            save_league_metadata(meta, league_id)
        return end_date

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        cmd_type, cmd_val = self.parse_command(user_text)
        
        if not cmd_type:
            return
            
        config = load_config()
        meta = load_league_metadata(config.get("LEAGUE_ID"))
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
        from src.utils.path_utils import get_league_dir, get_league_image_dir, parse_league_id
        img_path = os.path.join(get_league_image_dir(), img_filename)
        
        sport, raw_id = parse_league_id(config.get("LEAGUE_ID"))
        is_mlb = (sport == "mlb")
        cache_hit = False
        img_urls_to_send = []
        
        if is_mlb:
            hitter_name = f"{target_date}_combined_hitter.png"
            pitcher_name = f"{target_date}_combined_pitcher.png"
            h_path = os.path.join(get_league_image_dir(), hitter_name)
            p_path = os.path.join(get_league_image_dir(), pitcher_name)
            if os.path.exists(h_path) and os.path.exists(p_path):
                cache_hit = True
                SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')
                https_url = SERVER_URL.replace("http://", "https://")
                if not https_url.startswith("https://"):
                    https_url = f"https://{https_url.lstrip('https://')}"
                img_urls_to_send = [
                    f"{https_url}/images/mlb/{raw_id}/{hitter_name}",
                    f"{https_url}/images/mlb/{raw_id}/{pitcher_name}"
                ]
        else:
            if os.path.exists(img_path):
                cache_hit = True
                SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')
                https_url = SERVER_URL.replace("http://", "https://")
                if not https_url.startswith("https://"):
                    https_url = f"https://{https_url.lstrip('https://')}"
                img_url = f"{https_url}/images/{sport}/{raw_id}/{img_filename}"
                img_urls_to_send = [img_url]
                
        if cache_hit:
            logging.info(f"[CACHE] 命中圖片快取")
            messages_to_send = [ImageMessage(original_content_url=url, preview_image_url=url) for url in img_urls_to_send]
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=messages_to_send))
            return

        if is_empty_data(cache_key):
            logging.info(f"[CACHE] 命中負向快取 (無數據): {cache_key}")
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當天數據")]))
            return

        is_today_query = (cmd_type == "combined")
        current_week = date_to_week.get(today_pacific) or get_fantasy_week(start_date, today_dt)
        is_current_week_query = (cmd_type == "specific_week" and target_week == current_week)

        if is_today_query or is_current_week_query:
            from src.utils.time_utils import is_game_day
            from src.utils.path_utils import parse_league_id
            sport, _ = parse_league_id(config.get("LEAGUE_ID"))
            allowed, err_msg = is_game_day(sport=sport, is_offseason=is_offseason, target_date=today_pacific)
            if not allowed:
                with ApiClient(configuration) as api_client:
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token, 
                            messages=[TextMessage(text=err_msg)]
                        )
                    )
                return
            
        lock_file = os.path.join(get_league_dir(), f"{cache_key}_fetch.lock")
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
        # Force combined mode in env if needed by main.py
        env["MODE"] = "combined" 
        
        to_source_id = None
        event_source = getattr(event, "source", None)
        if event_source:
            to_source_id = getattr(event_source, "group_id", None) or getattr(event_source, "room_id", None) or getattr(event_source, "user_id", None)
            
        if to_source_id:
            env["LINE_REPLY_TO"] = to_source_id
        
        logging.info(f"[TASK] 啟動背景更新任務 (main.py)，模式: combined，目標 ID: {to_source_id}")
        subprocess.Popen([sys.executable, os.path.join(project_root, "main.py")], env=env)
