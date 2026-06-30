import os
import json
import time
import pickle
import logging
import requests
from pydash import set_ as pydash_set
from linebot.v3.messaging import ApiClient, MessagingApi, PushMessageRequest, TextMessage, Configuration

from src.utils.path_utils import BASE_DIR, get_league_dir, get_league_team_mapping_path
from src.fetcher import YahooFantasyFetcher
from src.utils.season_utils import sync_season_metadata

HTML_TEMPLATE = """
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
        <p>聊天室已順利啟用對聯賽 <span class="badge">{league_id}</span> 的存取。</p>
        <p>現在您可以回到 LINE 聊天室開始使用所有功能！</p>
    </div>
</body>
</html>
"""

def handle_oauth_callback(
    code: str,
    chat_id: str,
    client_id: str,
    client_secret: str,
    server_url: str,
    configuration: Configuration
) -> tuple[str, int]:
    """
    Handle the OAuth token exchange and initialize league assets.
    Returns: (response_text_or_html, status_code)
    """
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
        
    # 3. 儲存聯賽憑證 (.yahoofantasy pickle 格式)
    try:
        league_cred_dir = get_league_dir(league_id)
        persist_key = league_cred_dir.replace("\\", "/").rstrip("/") + "/"
        yf_filename = f"{persist_key}.yahoofantasy"

        # 讀取現有 .yahoofantasy（若存在），在其基礎上覆寫 auth 欄位
        existing_data = {}
        if os.path.exists(yf_filename):
            try:
                with open(yf_filename, "rb") as fp:
                    existing_data = pickle.load(fp)
            except Exception:
                existing_data = {}

        access_token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")
        expires_in = float(token_data.get("expires_in", 3600))
        access_token_expires = time.time() + expires_in

        auth_payload = {
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "access_token": access_token,
            "access_token_expires": access_token_expires,
        }

        # 使用 pydash set_ 寫入 auth 欄位
        now = time.time()
        for k, v in auth_payload.items():
            existing_data = pydash_set(existing_data, f"auth.{k}", v)
            existing_data = pydash_set(existing_data, f"auth.{k}__time", now)
        existing_data = pydash_set(existing_data, "auth__time", now)

        with open(yf_filename, "wb") as fp:
            pickle.dump(existing_data, fp)

        logging.info(f"[OAUTH] 憑證已成功寫入: {yf_filename}")
    except Exception as e:
        return f"⚠️ 儲存聯賽憑證失敗: {e}", 500
        
    # 4. 初始化聯賽資料與隊伍名稱對照表
    try:
        fetcher = YahooFantasyFetcher(
            client_id=client_id,
            client_secret=client_secret,
            league_id=league_id
        )
        
        # 同步賽季資訊
        sync_season_metadata(fetcher, league_id)
        
        # 建立/初始化隊伍名稱對照表
        mapping_path = get_league_team_mapping_path(league_id)
        if not os.path.exists(mapping_path):
            os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
            default_mapping = {}
            try:
                import yahoofantasy
                normalized_id = fetcher._normalize_league_id(league_id)
                league = yahoofantasy.League(fetcher.ctx, normalized_id)
                for team in league.teams():
                    team_id = str(getattr(team, "team_id", ""))
                    team_name = str(getattr(team, "name", ""))
                    if team_id and team_name:
                        default_mapping[team_id] = team_name
            except Exception as ex:
                logging.error(f"[OAUTH] 無法取得官方暱稱，將初始化為空對應: {ex}")
            
            with open(mapping_path, "w", encoding="utf-8") as mf:
                json.dump(default_mapping, mf, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"[OAUTH] 初始化聯賽資料與對照表失敗: {e}")
        
    # 5. 主動推播 LINE 通知使用者授權成功
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            msg_text = f"✅ Yahoo 帳號授權成功！已成功啟用此聊天室對聯賽 {league_id} 的資料存取功能。"
            line_bot_api.push_message(PushMessageRequest(
                to=chat_id,
                messages=[TextMessage(text=msg_text)]
            ))
    except Exception as e:
        logging.error(f"[OAUTH] 推送成功通知失敗: {e}")
        
    # 6. 回傳 HTML 網頁
    return HTML_TEMPLATE.replace("{league_id}", league_id), 200
