import os
import psutil
import logging
from pyngrok import ngrok
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, SetWebhookEndpointRequest

def get_public_server_url() -> str:
    """獲取可供外部 (如 LINE 伺服器) 連線的公開 HTTPS 伺服器根網址。若環境變數未設置，自動嘗試從本機 ngrok API 探索。"""
    from src.config import load_config
    import json
    import urllib.request

    config = load_config()
    server_url = os.environ.get("SERVER_URL") or config.get("SERVER_URL")

    # 若未設置或為 localhost，嘗試從正在執行的本機 ngrok 探索公開網址
    if not server_url or "localhost" in server_url or "127.0.0.1" in server_url:
        try:
            with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1.5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for tun in data.get("tunnels", []):
                    pub = tun.get("public_url")
                    if pub and pub.startswith("https://"):
                        server_url = pub
                        break
        except Exception:
            pass

    if not server_url:
        server_url = "http://localhost:5001"

    https_url = server_url.replace("http://", "https://")
    if not https_url.startswith("https://"):
        https_url = f"https://{https_url.lstrip('https://')}"
    return https_url.rstrip("/")


def cleanup_port(port: int):
    """Find and terminate any process listening on the specified port."""
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
