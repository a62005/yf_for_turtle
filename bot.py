import os
import sys
import psutil
import logging
import re
import subprocess
from datetime import datetime
import pytz
from flask import Flask, request, abort, send_from_directory
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage, SetWebhookEndpointRequest
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
from pyngrok import ngrok
from src.cache_utils import is_empty_data
from src.utils.time_utils import get_pacific_date, get_fantasy_week
from src.config import load_config
from src.fetcher import YahooFantasyFetcher
from src.cache_utils import is_empty_data, save_league_metadata, load_league_metadata
from src.utils.token_utils import is_token_processed

def cleanup_port(port):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conns in proc.connections(kind='inet'):
                if conns.laddr.port == port:
                    logging.info(f"[SYSTEM] 發現佔用 Port {port} 的進程 (PID: {proc.pid})，正在關閉...")
                    proc.terminate()
                    proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            pass

def get_tw_hour():
    tw_tz = pytz.timezone("Asia/Taipei")
    return datetime.now(tw_tz).hour

def setup_ngrok(authtoken: str, port: int) -> str:
    """Start ngrok tunnel and return the public URL."""
    ngrok.set_auth_token(authtoken)
    tunnel = ngrok.connect(port)
    return tunnel.public_url

def update_line_webhook(configuration: Configuration, url: str):
    """Update the LINE Messaging API Webhook URL."""
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        endpoint = f"{url}/callback"
        set_webhook_request = SetWebhookEndpointRequest(endpoint=endpoint)
        try:
            line_bot_api.set_webhook_endpoint(set_webhook_request)
            # Verify connectivity
            line_bot_api.test_webhook_endpoint()
            logging.info(f"Successfully updated LINE Webhook URL to: {endpoint}")
        except Exception as e:
            logging.error(f"Failed to update LINE Webhook: {e}")

# Load env
load_dotenv()
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'dummy_secret')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'dummy_token')
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')

app = Flask(__name__)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Regex patterns
combined_pattern = re.compile(r"^#戰績$")
daily_pattern = re.compile(r"^#當天戰績$")
weekly_pattern = re.compile(r"^#當週戰績$")
specific_week_pattern = re.compile(r"^#戰績W(\d+)$", re.IGNORECASE)
specific_date_pattern = re.compile(r"^#戰績(\d{8})$")

def parse_command(user_text: str) -> tuple[str | None, str | int | None]:
    cmd_type = None
    cmd_val = None
    
    if combined_pattern.match(user_text):
        cmd_type = "combined"
    elif daily_pattern.match(user_text):
        cmd_type = "daily"
    elif weekly_pattern.match(user_text):
        cmd_type = "weekly"
    else:
        m_week = specific_week_pattern.match(user_text)
        if m_week:
            cmd_type = "specific_week"
            cmd_val = int(m_week.group(1))
        else:
            m_date = specific_date_pattern.match(user_text)
            if m_date:
                cmd_type = "specific_date"
                raw_date = m_date.group(1)
                cmd_val = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
                
    return cmd_type, cmd_val

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    logging.info(f"Request body: {body}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@app.route("/images/<path:filename>")
def serve_image(filename):
    image_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "images")
    return send_from_directory(image_dir, filename)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    if is_token_processed(event.reply_token):
        return

    user_text = event.message.text.strip()
    logging.info(f"[LINE] 收到指令: {user_text}")
    
    cmd_type, cmd_val = parse_command(user_text)
                
    if not cmd_type:
        return # Ignore non-matching messages

    config = load_config()
    meta = load_league_metadata()
    today_pacific = get_pacific_date()
    is_offseason = meta.get('end_date') and today_pacific > meta['end_date']
    
    target_date = cmd_val if cmd_type == "specific_date" else today_pacific
    
    # 未來攔截
    if target_date > today_pacific:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="我不是未來人，無法提供未來數據")]))
        return

    # 賽季前攔截
    if meta.get('start_date') and target_date < meta['start_date']:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當天數據")]))
        return

    # 休賽季導向
    is_undated_cmd = cmd_type in ["combined", "daily", "weekly"]
    if meta.get('end_date') and today_pacific > meta['end_date'] and is_undated_cmd:
        logging.info(f"[SYSTEM] 休賽季導向: {today_pacific} > {meta['end_date']}")
        target_date = meta['end_date']
        target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(target_date, "%Y-%m-%d"))
        target_week = get_fantasy_week(meta['start_date'], target_dt)
    else:
        target_dt = pytz.timezone("US/Pacific").localize(datetime.strptime(target_date, "%Y-%m-%d"))
        target_week = cmd_val if cmd_type == "specific_week" else get_fantasy_week(meta.get('start_date', config.get("DEFAULT_SEASON_START", "2025-10-21")), target_dt)

    # 賽季後攔截
    if meta.get('end_date') and target_date > meta['end_date']:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="查無當天數據")]))
        return
    
    # Determine expected filenames and cache keys based on command
    if cmd_type == "combined":
        img_filename = f"{target_date}_combined.png"
        cache_key = f"{target_date}_combined"
    elif cmd_type in ["daily", "specific_date"]:
        img_filename = f"{target_date}_daily.png"
        cache_key = f"{target_date}_daily"
    else: # weekly, specific_week
        img_filename = f"week_{target_week}_weekly.png"
        cache_key = f"week_{target_week}_weekly"

    img_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "images", img_filename)
    
    # Step 1: Check standard cache (Image exists)
    if os.path.exists(img_path):
        logging.info(f"[CACHE] 命中圖片快取: {img_filename}")
        
        # 強制使用 HTTPS (LINE Bot 要求)
        https_url = SERVER_URL.replace("http://", "https://")
        if not https_url.startswith("https://"):
            https_url = f"https://{https_url.lstrip('https://')}"
            
        img_url = f"{https_url}/images/{img_filename}"
        reply_img = ImageMessage(original_content_url=img_url, preview_image_url=img_url)
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply_img]))
        return

    # Step 1.5: Check negative cache
    if is_empty_data(cache_key):
        logging.info(f"[CACHE] 命中負向快取 (無數據): {cache_key}")
        err_msg = "查無當週數據" if "weekly" in cache_key else "查無當天數據"
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=err_msg)]))
        return

    # Step 2: Time Gate for current period
    is_current = cmd_type in ["combined", "daily", "weekly"]
    if is_current and not is_offseason and get_tw_hour() < 14:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="請於 14:00 後再進行查詢。")]))
        return
        
    # Step 2.5: Check lock to prevent cache stampede
    lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", f"{cache_key}_fetch.lock")
    os.makedirs(os.path.dirname(lock_file), exist_ok=True)
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        logging.warning(f"[LOCK] 任務正在執行中，跳過重複請求: {cache_key}")
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="數據更新中")]))
        return

    # Step 3: Trigger main.py fetch
    with ApiClient(configuration) as api_client:
        MessagingApi(api_client).reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text="數據更新中，請稍候再試...")]))
    
    # Spawn subprocess
    env = os.environ.copy()
    env["FETCH_LOCK_PATH"] = lock_file
    if cmd_type == "specific_date":
        env["TEST_DATE"] = target_date
    elif cmd_type == "specific_week":
        env["TEST_WEEK"] = str(target_week)
    
    logging.info(f"[TASK] 啟動背景更新任務 (main.py)，模式: {cmd_type}")
    subprocess.Popen([sys.executable, "main.py"], env=env)
if __name__ == "__main__":
    cleanup_port(5001)
    config = load_config()
    fetcher = YahooFantasyFetcher(client_id=config.get("YAHOO_CLIENT_ID"), client_secret=config.get("YAHOO_CLIENT_SECRET"))
    try:
        logging.info("[SYSTEM] 同步賽季中繼資料...")
        meta = fetcher.fetch_league_metadata(config["LEAGUE_ID"])
        save_league_metadata(meta)
    except Exception as e:
        logging.error(f"[SYSTEM] 賽季資料同步失敗: {e}")

    port = 5001

    # Logic to decide mode
    # If NGROK_AUTHTOKEN exists, assume local automation mode
    if config.get("NGROK_AUTHTOKEN"):
        logging.info("NGROK_AUTHTOKEN found. Starting automated setup...")
        try:
            public_url = setup_ngrok(config["NGROK_AUTHTOKEN"], port)
            # Override global SERVER_URL
            SERVER_URL = public_url
            logging.info(f"ngrok tunnel opened at: {public_url}")

            # Sync with LINE
            update_line_webhook(configuration, public_url)
        except Exception as e:
            logging.error(f"ngrok setup failed: {e}")
            logging.info("Falling back to manual SERVER_URL.")
    else:
        logging.info("No NGROK_AUTHTOKEN found. Using existing SERVER_URL.")

    app.run(host="0.0.0.0", port=port)

