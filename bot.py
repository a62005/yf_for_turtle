import os
import sys
import psutil
import logging
import subprocess
import base64
import json
from flask import Flask, request, abort, send_from_directory
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, SetWebhookEndpointRequest
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
from pyngrok import ngrok
from src.config import load_config
from src.fetcher import YahooFantasyFetcher
from src.cache_utils import save_league_metadata
from src.utils.token_utils import is_token_processed

# Import our new handlers
from src.handlers.dispatcher import CommandDispatcher
from src.handlers.stats_handler import StatsHandler

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

# Initialize Dispatcher
dispatcher = CommandDispatcher()
dispatcher.register(StatsHandler())

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

@app.route("/pubsub-worker", methods=['POST'])
def pubsub_worker():
    envelope = request.get_json()
    if not envelope:
        return 'Bad Request: no JSON provided', 400

    pubsub_message = envelope.get('message')
    if not pubsub_message or not pubsub_message.get('data'):
        return 'Bad Request: invalid Pub/Sub message format', 400

    try:
        data_str = base64.b64decode(pubsub_message['data']).decode('utf-8')
        payload = json.loads(data_str)
        logging.info(f"[PUBSUB] 收到背景任務: {payload}")
        
        # Trigger main.py just like the subprocess does, but blockingly or in a sub-process
        # Since this is a Cloud Run worker route, we can just run the subprocess and let Cloud Run bill for it
        env = os.environ.copy()
        if "target_date" in payload:
            env["TEST_DATE"] = payload["target_date"]
        if "target_week" in payload and payload["target_week"]:
            env["TEST_WEEK"] = str(payload["target_week"])
        env["MODE"] = "combined"
        
        project_root = os.path.dirname(os.path.abspath(__file__))
        proc = subprocess.Popen([sys.executable, os.path.join(project_root, "main.py")], env=env)
        proc.wait() # Block until done so Cloud Run knows the task is active
        
        return 'OK', 200
    except Exception as e:
        logging.error(f"[PUBSUB] 任務執行失敗: {e}")
        return f'Error: {str(e)}', 500

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
    
    if user_text.startswith("#"):
        dispatcher.handle(event, configuration)

if __name__ == "__main__":
    cleanup_port(5001)
    config = load_config()
    fetcher = YahooFantasyFetcher(client_id=config.get("YAHOO_CLIENT_ID"), client_secret=config.get("YAHOO_CLIENT_SECRET"))
    try:
        from src.utils.season_utils import sync_season_metadata
        sync_season_metadata(fetcher, config["LEAGUE_ID"])
    except Exception as e:
        logging.error(f"[SYSTEM] 賽季資料同步失敗: {e}")

    port = 5001

    if config.get("NGROK_AUTHTOKEN"):
        logging.info("NGROK_AUTHTOKEN found. Starting automated setup...")
        try:
            public_url = setup_ngrok(config["NGROK_AUTHTOKEN"], port)
            SERVER_URL = public_url
            os.environ['SERVER_URL'] = public_url # Pass down to subprocesses
            logging.info(f"ngrok tunnel opened at: {public_url}")
            update_line_webhook(configuration, public_url)
        except Exception as e:
            logging.error(f"ngrok setup failed: {e}")
            logging.info("Falling back to manual SERVER_URL.")
    else:
        logging.info("No NGROK_AUTHTOKEN found. Using existing SERVER_URL.")

    app.run(host="0.0.0.0", port=port)
