import os
import sys
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
    user_text = event.message.text.strip()
    logging.info(f"[LINE] 收到指令: {user_text}")
    
    cmd_type, cmd_val = parse_command(user_text)
                
    if not cmd_type:
        return # Ignore non-matching messages

    config = load_config()
    current_date = get_pacific_date()
    current_week = get_fantasy_week(config.get("SEASON_START_DATE", "2025-10-21"))
    
    target_date = cmd_val if cmd_type == "specific_date" else current_date
    target_week = cmd_val if cmd_type == "specific_week" else current_week
    
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
        img_url = f"{SERVER_URL}/images/{img_filename}"
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
    if is_current and get_tw_hour() < 14:
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
    config = load_config()
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

