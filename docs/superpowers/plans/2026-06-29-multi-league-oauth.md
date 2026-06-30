# 多聯盟 Web-based Yahoo OAuth 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 Web-based Yahoo OAuth 授權與隔離，讓使用者可直接透過手機 LINE 點擊網頁連結完成聯賽權限授權，並獨立隔離各聯賽的憑證 `oauth2.json`。

**Architecture:**
1. 修改 `src/fetcher.py` 讓 `YahooFantasyFetcher` 初始化時動態將 `persist_key` 指向 `data/league/<LEAGUE_ID>/` 目錄，若不存在則繼承複製全域憑證。
2. 調整 `LeaguePermissionError` 的捕捉引導，在拋出權限拒絕時回覆內含 Yahoo 授權網址的超連結（含帶有 `state=chat_id` 參數）。
3. 在 `bot.py` 中註冊 GET `/oauth/callback` 端點，用以接收授權 code、與 Yahoo 交換 token、寫入指定聯賽目錄，並對 LINE 聊天室發送主動推播（Push Message）成功通知。

**Tech Stack:** Python, Flask, requests, yahoofantasy

---

### Task 1: 實作聯賽憑證動態路徑隔離與繼承

**Files:**
- Modify: `src/fetcher.py`
- Modify: `src/utils/path_utils.py`
- Create: `tests/test_oauth_path_isolation.py`

- [ ] **Step 1: 撰寫動態隔離測試**

建立 `tests/test_oauth_path_isolation.py` 檔案：

```python
import os
import shutil
import pytest
from unittest.mock import MagicMock
from src.fetcher import YahooFantasyFetcher
from src.utils.path_utils import BASE_DIR

def test_fetcher_oauth_path_isolation_and_fallback(tmp_path):
    # 1. 模擬全域憑證存在
    global_dir = os.path.join(BASE_DIR, "credentials")
    os.makedirs(global_dir, exist_ok=True)
    global_cred = os.path.join(global_dir, "oauth2.json")
    
    with open(global_cred, "w", encoding="utf-8") as f:
        f.write('{"test_token": "global"}')
        
    try:
        # 2. 實例化帶有 league_id 的 fetcher
        league_id = "88888"
        league_cred_dir = os.path.join(BASE_DIR, "data", "league", league_id)
        league_cred_file = os.path.join(league_cred_dir, "oauth2.json")
        
        # 移除舊有聯賽憑證以驗證繼承
        if os.path.exists(league_cred_file):
            os.remove(league_cred_file)
            
        fetcher = YahooFantasyFetcher(client_id="id", client_secret="secret", league_id=league_id)
        
        # 驗證 Context persist_key 是否指向聯賽獨立目錄
        expected_dir = f"data/league/{league_id}/"
        assert fetcher.ctx.persist_key == expected_dir
        
        # 驗證聯賽獨立目錄下是否正確繼承複製了全域憑證
        assert os.path.exists(league_cred_file)
        with open(league_cred_file, "r", encoding="utf-8") as f:
            content = f.read()
            assert "global" in content
            
    finally:
        # 清除測試檔案
        if os.path.exists(global_cred):
            os.remove(global_cred)
        shutil.rmtree(os.path.join(BASE_DIR, "data", "league", "88888"), ignore_errors=True)
```

- [ ] **Step 2: 執行測試並確認失敗**

運行：`.venv\Scripts\python -m pytest tests/test_oauth_path_isolation.py -v`
Expected: FAIL (TypeError or AssertionError)

- [ ] **Step 3: 實作憑證隔離與繼承**

修改 `src/fetcher.py`，使 `YahooFantasyFetcher` 初始化方法接收 `league_id`，並實作動態憑證路徑解析：

```python
    def __init__(self, team_mapping: dict = None, client_id: str = None, client_secret: str = None, league_id: str = None):
        persist_key = "credentials/"
        
        # 多聯盟憑證隔離與繼承
        if league_id:
            from src.utils.path_utils import BASE_DIR
            import shutil
            
            # 定義聯賽專屬憑證目錄
            league_cred_dir = os.path.join(BASE_DIR, "data", "league", league_id)
            os.makedirs(league_cred_dir, exist_ok=True)
            
            # 聯賽專屬憑證物理路徑
            league_cred_file = os.path.join(league_cred_dir, "oauth2.json")
            global_cred_file = os.path.join(BASE_DIR, "credentials", "oauth2.json")
            
            # 如果聯賽憑證不存在但全域憑證存在，則複製繼承
            if not os.path.exists(league_cred_file) and os.path.exists(global_cred_file):
                try:
                    shutil.copy2(global_cred_file, league_cred_file)
                    logging.info(f"[YAHOO] 聯賽 {league_id} 憑證繼承複製自全域憑證")
                except Exception as e:
                    logging.error(f"[YAHOO] 繼承複製全域憑證至聯賽 {league_id} 失敗: {e}")
                    
            persist_key = f"data/league/{league_id}/"
            
        self.ctx = yahoofantasy.Context(
            persist_key=persist_key,
            client_id=client_id,
            client_secret=client_secret
        )
        self.team_mapping = team_mapping or {}
```

同時，修正在 `src/handlers/set_league_id_handler.py` 中實例化 `YahooFantasyFetcher` 的地方，傳入當前的 `target_id` 作為 `league_id` 參數。

- [ ] **Step 4: 執行測試並確認通過**

運行：`.venv\Scripts\python -m pytest tests/test_oauth_path_isolation.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/fetcher.py src/handlers/set_league_id_handler.py tests/test_oauth_path_isolation.py
git commit -m "feat: implement league-level credentials directory isolation and inheritance"
```

---

### Task 2: 權限拒絕時的授權超連結回覆引導

**Files:**
- Modify: `src/handlers/base_handler.py`
- Modify: `tests/handlers/test_base_handler_security.py`

- [ ] **Step 1: 修改測試以包含授權連結斷言**

修改 `tests/handlers/test_base_handler_security.py` 中的 `test_base_handler_permission_error_handling`：
* 驗證當 Handler 執行拋出 `LeaguePermissionError` 時，回覆訊息中包含有效的 `api.login.yahoo.com` 以及 `oauth/callback` 授權網址。

```python
def test_base_handler_permission_error_handling():
    from src.handlers.base_handler import BaseHandler
    from src.fetcher import LeaguePermissionError
    from src.config import current_chat_id
    
    class DummyHandler(BaseHandler):
        def can_handle(self, text): return True
        def execute(self, event, config):
            raise LeaguePermissionError("Permission Denied")
            
    handler = DummyHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.source.type = "group"
    event.source.group_id = "C_dummy_group"
    config = {
        "YAHOO_CLIENT_ID": "client_123",
        "SERVER_URL": "https://dummy.ngrok.io"
    }
    
    token = current_chat_id.set("C_dummy_group")
    try:
        handler.execute(event, config)
        handler.reply_text.assert_called_once()
        reply_content = handler.reply_text.call_args[0][2]
        
        # 驗證包含授權提示與正確的 Redirect 網址
        assert "無權限存取此聯盟" in reply_content
        assert "api.login.yahoo.com" in reply_content
        assert "client_123" in reply_content
        assert "C_dummy_group" in reply_content  # state 攜帶 chat_id
        assert "https://dummy.ngrok.io/oauth/callback" in reply_content
    finally:
        current_chat_id.reset(token)
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/handlers/test_base_handler_security.py -v`
Expected: FAIL

- [ ] **Step 3: 實作動態授權網址生成**

修改 `src/handlers/base_handler.py` 中的 `wrapped_execute`：

```python
        original_execute = self.execute
        def wrapped_execute(event, configuration):
            try:
                original_execute(event, configuration)
            except Exception as e:
                from src.fetcher import LeaguePermissionError
                if isinstance(e, LeaguePermissionError) or e.__class__.__name__ == "LeaguePermissionError":
                    from src.config import current_chat_id, load_config
                    cfg = load_config()
                    client_id = cfg.get("YAHOO_CLIENT_ID") or ""
                    server_url = cfg.get("SERVER_URL") or ""
                    chat_id = current_chat_id.get() or ""
                    
                    redirect_uri = f"{server_url.rstrip('/')}/oauth/callback"
                    
                    auth_url = (
                        "https://api.login.yahoo.com/oauth2/request_auth"
                        f"?client_id={client_id}"
                        f"&redirect_uri={redirect_uri}"
                        f"&response_type=code"
                        f"&state={chat_id}"
                    )
                    
                    msg = (
                        "⚠️ 機器人 Yahoo 帳號目前無權限存取此聯盟。\n"
                        "請聯絡白名單成員點擊以下連結進行 Yahoo 帳號授權以啟用此聯賽：\n"
                        f"👉 {auth_url}"
                    )
                    
                    self.reply_text(event, configuration, msg)
                else:
                    raise
        self.execute = wrapped_execute
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/handlers/test_base_handler_security.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/handlers/base_handler.py tests/handlers/test_base_handler_security.py
git commit -m "feat: generate custom Yahoo authorization URL with chat_id in state on LeaguePermissionError"
```

---

### Task 3: Webhook Endpoint 實作與 Token 交換

**Files:**
- Modify: `bot.py`
- Create: `tests/test_oauth_endpoint.py`

- [ ] **Step 1: 撰寫 Web OAuth Endpoint 測試**

建立 `tests/test_oauth_endpoint.py` 測試檔案：

```python
import json
import pytest
from unittest.mock import MagicMock, patch

@pytest.fixture
def mock_app():
    from bot import app
    app.config["TESTING"] = True
    return app.test_client()

def test_oauth_callback_success(mock_app):
    # 模擬 chat_league_mapping.json 的讀寫
    mapping_data = {"C_test_group": "77777"}
    
    # Mock Token 交換回傳值
    mock_token_payload = {
        "access_token": "mock_access_token_123",
        "refresh_token": "mock_refresh_token_456",
        "expires_in": 3600,
        "token_type": "bearer"
    }
    
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = mock_token_payload
    
    # 攔截對應的檔案儲存
    written_files = {}
    def mock_write(path, mode="r", *args, **kwargs):
        from io import StringIO
        class MockFile(StringIO):
            def __exit__(self, exc_type, exc_val, exc_tb):
                nonlocal written_files
                written_files[path] = self.getvalue()
                super().__exit__(exc_type, exc_val, exc_tb)
        return MockFile()
        
    with patch("bot.load_config", return_value={"YAHOO_CLIENT_ID": "client", "YAHOO_CLIENT_SECRET": "secret", "SERVER_URL": "http://127.0.0.1"}), \
         patch("bot.requests.post", return_value=mock_response) as mock_post, \
         patch("bot.open", side_effect=mock_write), \
         patch("bot.os.path.exists", return_value=True), \
         patch("bot.json.load", return_value=mapping_data), \
         patch("bot.os.makedirs") as mock_makedirs, \
         patch("bot.MessagingApi") as mock_api_cls:
         
        # 發送 GET 請求
        res = mock_app.get("/oauth/callback?code=code_123&state=C_test_group")
        
        # 驗證響應
        assert res.status_code == 200
        assert "授權成功" in res.get_data(as_text=True)
        
        # 驗證 POST 請求參數
        mock_post.assert_called_once()
        post_kwargs = mock_post.call_args[1]
        assert post_kwargs["data"]["code"] == "code_123"
        
        # 驗證有寫入正確聯賽目錄 (77777)
        matching_file_found = False
        for filepath, data in written_files.items():
            if "77777" in filepath and "oauth2.json" in filepath:
                matching_file_found = True
                assert "mock_access_token_123" in data
        assert matching_file_found
        
        # 驗證是否對群組調用 Push Message 推播成功訊息
        mock_api_cls.assert_called_once()
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/test_oauth_endpoint.py -v`
Expected: FAIL (404 Not Found)

- [ ] **Step 3: 實作 `/oauth/callback` 接收端點**

修改 `bot.py` 檔案，引入 `requests` 並實作路由：

```python
import requests
from flask import render_template_string

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
        # 計算過期戳記
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
        
    # 5. 回傳精美的網頁響應
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
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/test_oauth_endpoint.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add bot.py tests/test_oauth_endpoint.py
git commit -m "feat: implement GET /oauth/callback Flask route to handle Yahoo token exchange and LINE push message notification"
```
