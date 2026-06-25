import os
import sys
import psutil
import time
import logging
import subprocess
from flask import Flask, request, abort, send_from_directory
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, SetWebhookEndpointRequest
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
from pyngrok import ngrok
from src.config import load_config
from src.fetcher import YahooFantasyFetcher
from src.utils.cache_utils import save_league_metadata
from src.utils.token_utils import is_token_processed

from src.handlers.dispatcher import CommandDispatcher
from src.handlers.stats_handler import StatsHandler
from src.handlers.player_handler import PlayerHandler
from src.handlers.user_stats_handler import UserStatsHandler
from src.handlers.matchup_handler import MatchupHandler
from src.handlers.misc_handler import MiscHandler
from src.handlers.intent_router import IntentRouter
from src.handlers.football_handler import FootballHandler
from src.handlers.injury_handler import InjuryHandler
from src.handlers.id_handler import IdHandler
from src.handlers.super_admin_handler import SuperAdminHandler
from src.handlers.settings_handler import SettingsHandler

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
dispatcher.register(IdHandler())
dispatcher.register(StatsHandler())
dispatcher.register(PlayerHandler())
dispatcher.register(UserStatsHandler())
dispatcher.register(MatchupHandler())
dispatcher.register(MiscHandler())
dispatcher.register(FootballHandler())
dispatcher.register(InjuryHandler())
dispatcher.register(SuperAdminHandler())
dispatcher.register(SettingsHandler())

# Initialize IntentRouter
intent_router = IntentRouter(dispatcher)


@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    logging.debug(f"Request body: {body}")

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

    # 先判斷這則訊息是否需要處理，若非指令、非單聊且群聊無 @提及，則直接略過，不執行延遲檢測
    if not intent_router.should_process(event, configuration):
        return

    # Webhook 超時防護，防止處理過期或 LINE 重試發送的延遲訊息打擾用戶
    now_ms = int(time.time() * 1000)
    event_time_ms = getattr(event, "timestamp", None)
    if event_time_ms:
        delay_sec = (now_ms - event_time_ms) / 1000.0
        max_delay = 10.0
            
        if delay_sec > max_delay:
            logging.warning(
                f"[LINE] 指令 '{event.message.text.strip()}' 延遲過大 ({delay_sec:.2f} 秒 > {max_delay} 秒)，自動略過處理以避免打擾用戶。"
            )
            return

    # 交由 intent_router 進行意圖路由與過濾
    intent_router.route(event, configuration)

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
