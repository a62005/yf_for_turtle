import os
import sys
import time
import logging
from flask import Flask, request, abort, send_from_directory
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, SetWebhookEndpointRequest
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
from dotenv import load_dotenv
from pyngrok import ngrok
from src.config import load_config, current_chat_id
from src.fetcher import YahooFantasyFetcher
from src.utils.cache_utils import save_league_metadata
from src.utils.token_utils import is_token_processed
from src.utils.bot_utils import cleanup_port, setup_ngrok, update_line_webhook
from src.utils.oauth_handler import handle_oauth_callback

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
from src.handlers.set_league_id_handler import SetLeagueIdHandler
from src.handlers.set_nickname_handler import SetNicknameHandler
from src.handlers.set_time_handler import SetTimeHandler
from src.handlers.set_prize_handler import SetPrizeHandler

# Load env
load_dotenv()
LINE_CHANNEL_SECRET = os.getenv('LINE_CHANNEL_SECRET', 'dummy_secret')
LINE_CHANNEL_ACCESS_TOKEN = os.getenv('LINE_CHANNEL_ACCESS_TOKEN', 'dummy_token')
SERVER_URL = os.getenv('SERVER_URL', 'http://localhost:5000')

app = Flask(__name__)
configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
# 抑制 Flask/Werkzeug 的 HTTP 存取 log，只保留應用程式 log
logging.getLogger("werkzeug").setLevel(logging.WARNING)

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
dispatcher.register(SetLeagueIdHandler())
dispatcher.register(SetNicknameHandler())
dispatcher.register(SetTimeHandler())
dispatcher.register(SetPrizeHandler())

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

@app.route("/images/<sport>/<raw_id>/<path:filename>")
def serve_league_image(sport, raw_id, filename):
    """Serve league images. URL: /images/<sport>/<raw_id>/<filename>"""
    from src.utils.path_utils import DATA_DIR
    image_dir = os.path.join(DATA_DIR, "league", sport, raw_id, "image")
    return send_from_directory(image_dir, filename)

@app.route("/images/<path:filename>")
def serve_image(filename):
    """Legacy fallback: serve images using context league_id."""
    from src.utils.path_utils import get_league_image_dir
    image_dir = get_league_image_dir()
    return send_from_directory(image_dir, filename)

@app.route("/oauth/callback", methods=["GET"])
def oauth_callback():
    code = request.args.get("code")
    chat_id = request.args.get("state")
    
    if not code or not chat_id:
        return "⚠️ 授權失敗：參數缺失 (Missing code or state)", 400
        
    config = load_config()
    client_id = config.get("YAHOO_CLIENT_ID")
    client_secret = config.get("YAHOO_CLIENT_SECRET")
    server_url = os.environ.get('SERVER_URL') or config.get("SERVER_URL")
    
    return handle_oauth_callback(
        code=code,
        chat_id=chat_id,
        client_id=client_id,
        client_secret=client_secret,
        server_url=server_url,
        configuration=configuration
    )

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    chat_id = None
    if hasattr(event, "source") and event.source:
        source_type = getattr(event.source, "type", None)
        if source_type == "group":
            chat_id = getattr(event.source, "group_id", None)
        elif source_type == "room":
            chat_id = getattr(event.source, "room_id", None)
        elif source_type == "user":
            chat_id = getattr(event.source, "user_id", None)
            
    token = current_chat_id.set(chat_id)
    try:
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
    finally:
        current_chat_id.reset(token)


@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image_message(event):
    chat_id = None
    user_id = None
    if hasattr(event, "source") and event.source:
        source_type = getattr(event.source, "type", None)
        if source_type == "group":
            chat_id = getattr(event.source, "group_id", None)
        elif source_type == "room":
            chat_id = getattr(event.source, "room_id", None)
        elif source_type == "user":
            chat_id = getattr(event.source, "user_id", None)
        
        user_id = getattr(event.source, "user_id", None)
            
    if not chat_id or not user_id:
        return
        
    token = current_chat_id.set(chat_id)
    try:
        if is_token_processed(event.reply_token):
            return
    
        # 僅在處於設置獎金的狀態時進行圖片事件處理
        from src.utils.session_manager import get_prize_session
        if get_prize_session(user_id):
            intent_router.route_image(event, configuration)
    finally:
        current_chat_id.reset(token)

if __name__ == "__main__":
    cleanup_port(5001)
    from src.utils.path_utils import migrate_old_league_directories
    migrate_old_league_directories()

    config = load_config()
    port = 5001

    if config.get("NGROK_AUTHTOKEN"):
        logging.info("NGROK_AUTHTOKEN found. Starting automated setup...")
        try:
            public_url = setup_ngrok(config["NGROK_AUTHTOKEN"], port)
            os.environ['SERVER_URL'] = public_url # Pass down to subprocesses
            logging.info(f"ngrok tunnel opened at: {public_url}")
            update_line_webhook(configuration, public_url)
        except Exception as e:
            logging.error(f"ngrok setup failed: {e}")
            logging.info("Falling back to manual SERVER_URL.")
    else:
        logging.info("No NGROK_AUTHTOKEN found. Using existing SERVER_URL.")

    app.run(host="0.0.0.0", port=port)
