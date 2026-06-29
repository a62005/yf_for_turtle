import os
import sys
import json
import psutil
import time
import logging
import subprocess
import requests
from flask import Flask, request, abort, send_from_directory, render_template_string
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, SetWebhookEndpointRequest
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from dotenv import load_dotenv
from pyngrok import ngrok
from src.config import load_config, current_chat_id
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
from src.handlers.set_league_id_handler import SetLeagueIdHandler
from src.handlers.set_nickname_handler import SetNicknameHandler
from src.handlers.set_draft_time_handler import SetDraftTimeHandler

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
dispatcher.register(SetLeagueIdHandler())
dispatcher.register(SetNicknameHandler())
dispatcher.register(SetDraftTimeHandler())

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
    server_url = config.get("SERVER_URL")
    
    # 1. 向 Yahoo 交換 Token
    token_url = "https://api.login.yahoo.com/oauth2/get_token"
    redirect_uri = f"{server_url.rstrip('/')}/oauth/callback"
    
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "code": code,
        "grant_type": "authorization_code"
    }
    
    try:
        resp = requests.post(token_url, data=payload, headers={"Content-Type": "application/x-www-form-urlencoded"})
        if resp.status_code != 200:
            return f"⚠️ Yahoo Token 交換失敗: {resp.text}", 400
        token_data = resp.json()
    except Exception as e:
        return f"⚠️ Yahoo 連線失敗: {e}", 500
        
    # 2. 獲取該 chat_id 綁定的 LEAGUE_ID
    league_id = None
    from src.utils.path_utils import BASE_DIR
    mapping_path = os.path.join(BASE_DIR, "data", "security", "chat_league_mapping.json")
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
                league_id = mapping.get(chat_id)
        except Exception:
            pass
            
    if not league_id:
        return f"⚠️ 找不到此聊天室 ({chat_id}) 所綁定的聯賽，請先執行 #設置 以確認綁定關係。", 400
        
    # 3. 寫入專屬聯賽隔離憑證
    league_cred_dir = os.path.join(BASE_DIR, "data", "league", league_id)
    os.makedirs(league_cred_dir, exist_ok=True)
    league_cred_file = os.path.join(league_cred_dir, "oauth2.json")
    
    try:
        import time
        token_data["expires_at"] = time.time() + float(token_data.get("expires_in", 3600))
        with open(league_cred_file, "w", encoding="utf-8") as f:
            json.dump(token_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return f"⚠️ 儲存聯賽憑證失敗: {e}", 500
        
    # 4. 主動推播 LINE 通知使用者授權成功
    try:
        from linebot.v3.messaging import ApiClient, MessagingApi, PushMessageRequest, TextMessage
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            msg_text = f"✅ Yahoo 帳號授權成功！已成功啟用此聊天室對聯賽 {league_id} 的資料存取功能。"
            line_bot_api.push_message(PushMessageRequest(
                to=chat_id,
                messages=[TextMessage(text=msg_text)]
            ))
    except Exception as e:
        logging.error(f"[OAUTH] 推送成功通知失敗: {e}")
        
    html_page = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>Yahoo Fantasy NBA 授權成功</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; background-color: #f6f8fa; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
            .card { background: white; padding: 40px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); text-align: center; max-width: 400px; width: 100%; }
            h2 { color: #2da44e; margin-bottom: 10px; }
            p { color: #57606a; line-height: 1.5; }
            .badge { background-color: #dafbe1; color: #1a7f37; padding: 4px 8px; border-radius: 6px; font-weight: bold; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>🎉 授權成功！</h2>
            <p>聊天室已順利啟用對聯賽 <span class="badge">{{ league_id }}</span> 的存取。</p>
            <p>現在您可以回到 LINE 聊天室開始使用所有功能！</p>
        </div>
    </body>
    </html>
    """
    return render_template_string(html_page, league_id=league_id)

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

if __name__ == "__main__":
    cleanup_port(5001)
    config = load_config()
    
    league_id = config.get("LEAGUE_ID")
    if not league_id:
        logging.info("[SYSTEM] 多聯盟架構已啟動。聯賽 ID 將在接收到 LINE 指令時依據聊天室 ID 動態載入。")
    else:
        logging.info(f"[SYSTEM] 目前配置的預設全域聯賽 ID 為: {league_id}")

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
