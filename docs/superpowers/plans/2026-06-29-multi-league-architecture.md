# 多聯盟隔離與綁定架構實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作多聯盟隔離與綁定架構，讓不同的對話室（`chat_id`）能獨立綁定其聯賽 ID，並在未綁定時對非授權指令保持靜默。

**Architecture:**
1. 在 `src/config.py` 中引入 `contextvars.ContextVar` 做當前請求 `chat_id` 上下文變數。
2. 重構 `src/config.py` 的 `load_config`，從 `ContextVar` 取得 `chat_id` 並讀取對應的 `chat_league_mapping.json` 來決定 `LEAGUE_ID`。
3. 修改 `bot.py` 在 `handle_message` 事件入口中設定與重置該 `ContextVar`。
4. 修改 `IntentRouter.should_process`，在未綁定時僅允許 `#設置`、`#我的ID`、`#設置聯盟ID` 及其對話會話，其餘發言保持靜默。
5. 重構 `SetLeagueIdHandler`，將綁定對應關係寫入 `chat_league_mapping.json`，而非覆寫全域變數。
6. 修改 `YahooFantasyFetcher`，捕捉與 Yahoo Fantasy API 授權相關的 `401`/`403` 等錯誤並回覆友好提示。

**Tech Stack:** Python, contextvars, pytest

---

### Task 1: 實作 ContextVars 上下文環境與配置載入重構

**Files:**
- Modify: `src/config.py`
- Create: `tests/test_multi_league_config.py`

- [ ] **Step 1: 撰寫上下文配置測試**

建立 `tests/test_multi_league_config.py`：

```python
import os
import json
import pytest
from src.config import load_config, current_chat_id

def test_load_config_with_chat_context(tmp_path):
    from src.utils.path_utils import BASE_DIR
    mapping_dir = os.path.join(BASE_DIR, "data", "security")
    os.makedirs(mapping_dir, exist_ok=True)
    mapping_path = os.path.join(mapping_dir, "chat_league_mapping.json")
    
    # 建立測試用對應表
    mapping_data = {
        "chat_group_a": "11111",
        "chat_group_b": "22222"
    }
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(mapping_data, f)
        
    try:
        # 1. 測試無 chat_id 時
        current_chat_id.set(None)
        config = load_config()
        assert config["LEAGUE_ID"] is None
        
        # 2. 測試 chat_group_a 上下文
        token_a = current_chat_id.set("chat_group_a")
        config_a = load_config()
        assert config_a["LEAGUE_ID"] == "11111"
        current_chat_id.reset(token_a)
        
        # 3. 測試 chat_group_b 上下文
        token_b = current_chat_id.set("chat_group_b")
        config_b = load_config()
        assert config_b["LEAGUE_ID"] == "22222"
        current_chat_id.reset(token_b)
    finally:
        if os.path.exists(mapping_path):
            os.remove(mapping_path)
```

- [ ] **Step 2: 執行測試並確認失敗**

運行：`.venv\Scripts\python -m pytest tests/test_multi_league_config.py -v`
Expected: FAIL (AssertionError or ImportError)

- [ ] **Step 3: 實作 ContextVar 上下文讀取**

在 `src/config.py` 中引入 `contextvars`，並重構 `load_config`：

```python
import os
import json
from dotenv import load_dotenv
from contextvars import ContextVar

# 執行緒與協程安全隔離的當前對話 ID 上下文
current_chat_id: ContextVar[str | None] = ContextVar("current_chat_id", default=None)

def load_config() -> dict:
    dynamic_server_url = os.environ.get("SERVER_URL")
    
    load_dotenv("league.env", encoding="utf-8")
    load_dotenv(".env", override=True, encoding="utf-8")
    
    current_server_url = os.environ.get("SERVER_URL")
    if (not current_server_url or current_server_url.strip() == "") and dynamic_server_url:
        os.environ["SERVER_URL"] = dynamic_server_url
    
    chat_id = current_chat_id.get()
    league_id = None
    
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    
    # 讀取 chat_league_mapping.json 中的綁定對應
    if chat_id:
        mapping_file = os.path.join(base_dir, "data", "security", "chat_league_mapping.json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
                    league_id = mapping.get(chat_id)
            except Exception:
                pass

    mapping_file = os.getenv("TEAM_MAPPING_FILE", "team_mapping.json")
    season_start = os.getenv("SEASON_START_DATE")
    
    draft_date = os.getenv("DRAFT_DATE")
    next_season_start_date = os.getenv("NEXT_SEASON_START_DATE")
    
    lid = league_id or "default"
    settings_file = os.path.join(base_dir, "data", "league", lid, "settings.json")
    if os.path.exists(settings_file):
        try:
            with open(settings_file, "r", encoding="utf-8") as f:
                settings_data = json.load(f)
                s_draft = settings_data.get("DRAFT_DATE") or settings_data.get("draft_date")
                if s_draft:
                    draft_date = s_draft
                    os.environ["DRAFT_DATE"] = s_draft
                s_next_season = settings_data.get("NEXT_SEASON_START_DATE") or settings_data.get("next_season_start_date")
                if s_next_season:
                    next_season_start_date = s_next_season
                    os.environ["NEXT_SEASON_START_DATE"] = s_next_season
        except Exception:
            pass
    
    return {
        "LEAGUE_ID": league_id,
        "TEAM_MAPPING_FILE": mapping_file,
        "SEASON_START_DATE": season_start,
        "YAHOO_CLIENT_ID": os.getenv("YAHOO_CLIENT_ID"),
        "YAHOO_CLIENT_SECRET": os.getenv("YAHOO_CLIENT_SECRET"),
        "NGROK_AUTHTOKEN": os.getenv("NGROK_AUTHTOKEN"),
        "LINE_CHANNEL_SECRET": os.getenv("LINE_CHANNEL_SECRET"),
        "LINE_CHANNEL_ACCESS_TOKEN": os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
        "SERVER_URL": os.getenv("SERVER_URL"),
        "LLM_API_KEY": os.getenv("LLM_API_KEY"),
        "LLM_MODEL": os.getenv("LLM_MODEL"),
        "NEXT_SEASON_START_DATE": next_season_start_date,
        "DRAFT_DATE": draft_date,
        "PRIZE_IMAGE_PATH": os.getenv("PRIZE_IMAGE_PATH"),
        "ENABLE_FOOTBALL_ANALYSIS": os.getenv("ENABLE_FOOTBALL_ANALYSIS", "False").lower() in ("true", "1", "yes")
    }
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/test_multi_league_config.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/config.py tests/test_multi_league_config.py
git commit -m "feat: implement contextvar based current_chat_id isolation in load_config"
```

---

### Task 2: Webhook 入口 Context 注入實作

**Files:**
- Modify: `bot.py`
- Modify: `tests/test_bot.py`

- [ ] **Step 1: 修正現有 bot 測試**

因為 `bot.py` 的 `handle_message` 將引入 Context 注入，修改 `tests/test_bot.py` 中 `test_handle_message_success` 等測試，驗證 Context 是否正確填入與重置。

```python
def test_handle_message_context_injected():
    from bot import handle_message
    from src.config import current_chat_id
    
    event = MagicMock()
    event.reply_token = "reply_token_123"
    event.message.text = "#我的ID"
    event.source.type = "group"
    event.source.group_id = "C_group_123"
    event.timestamp = int(time.time() * 1000)
    
    # 驗證在執行中，ContextVar 被正確設定
    def check_context(*args, **kwargs):
        assert current_chat_id.get() == "C_group_123"
        
    with patch("bot.is_token_processed", return_value=False), \
         patch("bot.intent_router.should_process", return_value=True), \
         patch("bot.intent_router.route", side_effect=check_context) as mock_route:
        handle_message(event)
        mock_route.assert_called_once()
        
    # 執行完畢後 ContextVar 被重置為 None
    assert current_chat_id.get() is None
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/test_bot.py -v`
Expected: FAIL

- [ ] **Step 3: 在 Webhook 中注入 Context**

修改 `bot.py` 中的 `handle_message`：

```python
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    if is_token_processed(event.reply_token):
        return

    # 提取 chat_id 並注入 ContextVar
    chat_id = None
    if event.source:
        if event.source.type == "group":
            chat_id = event.source.group_id
        elif event.source.type == "room":
            chat_id = event.source.room_id
        elif event.source.type == "user":
            chat_id = event.source.user_id
            
    from src.config import current_chat_id
    token = current_chat_id.set(chat_id)
    
    try:
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
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/test_bot.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add bot.py tests/test_bot.py
git commit -m "feat: inject LINE chat_id context inside handle_message webhook using ContextVar"
```

---

### Task 3: 未綁定時的指令過濾與靜默防護

**Files:**
- Modify: `src/handlers/intent_router.py`
- Modify: `tests/test_intent_router.py`

- [ ] **Step 1: 撰寫未綁定靜默測試**

在 `tests/test_intent_router.py` 中新增未綁定防護的單元測試：

```python
def test_should_process_unbound_silence():
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    config = MagicMock()
    
    # 模擬為未綁定聯賽 ID
    with patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": None}):
        # 1. 未綁定時的 #設置 -> 允許
        event_settings = create_mock_event("#設置", chat_type="group")
        assert router.should_process(event_settings, config) is True
        
        # 2. 未綁定時的 #我的ID -> 允許
        event_my_id = create_mock_event("#我的ID", chat_type="group")
        assert router.should_process(event_my_id, config) is True
        
        # 3. 未綁定時的 #設置聯盟ID -> 允許
        event_set_league = create_mock_event("#設置聯盟ID 12345", chat_type="group")
        assert router.should_process(event_set_league, config) is True
        
        # 4. 未綁定時的其它指令 (如 #開季、#戰績) -> 拒絕（靜默）
        event_start = create_mock_event("#開季", chat_type="group")
        assert router.should_process(event_start, config) is False
        
        # 5. 未綁定時的普通自然語言聊天 -> 拒絕（靜默）
        event_chat = create_mock_event("哈囉機器人 @bot", chat_type="group")
        assert router.should_process(event_chat, config) is False
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/test_intent_router.py -v`
Expected: FAIL

- [ ] **Step 3: 實作未綁定過濾邏輯**

修改 `src/handlers/intent_router.py` 的 `should_process` 方法：

```python
    def should_process(self, event: MessageEvent, configuration: Configuration) -> bool:
        """Determine if the message event should be processed by the bot."""
        user_text = event.message.text.strip() if event.message and hasattr(event.message, 'text') else ""
        if not user_text:
            return False

        # 多聯盟未綁定防護
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if league_id is None:
            # 僅放行 #設置、#我的ID、#設置聯盟ID 等指令及活動中的 Session
            allowed_cmd = False
            if user_text.startswith("#"):
                clean_cmd = user_text.split()[0]
                if clean_cmd in ("#設置", "#我的ID") or clean_cmd.startswith("#設置聯盟ID"):
                    allowed_cmd = True
            
            user_id = getattr(event.source, "user_id", None)
            has_active_session = False
            if user_id:
                # 只在有對話狀態時，暫時放行 session 輸入
                if get_nickname_session(user_id) or get_draft_time_session(user_id):
                    has_active_session = True
                    
            if not allowed_cmd and not has_active_session:
                return False

        # 1. 指令優先
        if user_text.startswith("#"):
            return True

        # 2. 單聊必定處理
        if event.source.type == "user":
            return True

        # 3. 活動中 Session 優先（在群組也不需要被 @提及）
        user_id = getattr(event.source, "user_id", None)
        if user_id:
            if get_nickname_session(user_id) or get_draft_time_session(user_id):
                return True

        # 4. 群聊中必須被提及 (@提及)
        if event.source.type in ["group", "room"]:
            # 檢查官方 mention 物件
            if hasattr(event.message, "mention") and event.message.mention:
                bot_user_id = self._get_bot_user_id(configuration)
                for m in event.message.mention.mentionees:
                    if m.type == "user" and getattr(m, "user_id", None) == bot_user_id: 
                        return True
            # 備用：手動文字提及
            lower_text = user_text.lower()
            if "@bot" in lower_text or "@linebot" in lower_text:
                return True

        return False
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/test_intent_router.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/handlers/intent_router.py tests/test_intent_router.py
git commit -m "feat: ignore all commands and chats except #設置, #我的ID, #設置聯盟ID when league_id is not bound"
```

---

### Task 4: 聊天室綁定處理器重構 (SetLeagueIdHandler)

**Files:**
- Modify: `src/handlers/set_league_id_handler.py`
- Modify: `tests/handlers/test_settings_and_setup.py`

- [ ] **Step 1: 修正現有的聯盟綁定單元測試**

修改 `tests/handlers/test_settings_and_setup.py`：
* 將原本寫入全域 `league_config.json` 斷言，改為驗證寫入對應的 `chat_league_mapping.json`。

```python
def test_set_league_id_writes_to_chat_league_mapping(tmp_path):
    from src.handlers.set_league_id_handler import SetLeagueIdHandler
    from src.config import current_chat_id
    
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.source.user_id = "U_user_123"
    event.message.text = "18457"
    config = MagicMock()
    
    token = current_chat_id.set("chat_group_xyz")
    try:
        with patch("src.handlers.set_league_id_handler.get_set_league_session", return_value={"user_id": "U_user_123"}), \
             patch("src.handlers.set_league_id_handler.clear_set_league_session") as mock_clear:
             
            handler.execute(event, config)
            mock_clear.assert_called_once()
            
            # 驗證寫入 chat_league_mapping.json 的內容
            from src.utils.path_utils import BASE_DIR
            mapping_path = os.path.join(BASE_DIR, "data", "security", "chat_league_mapping.json")
            assert os.path.exists(mapping_path)
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
                assert mapping["chat_group_xyz"] == "18457"
    finally:
        current_chat_id.reset(token)
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py -v`
Expected: FAIL

- [ ] **Step 3: 實作 chat_id 與聯賽綁定寫入邏輯**

修改 `src/handlers/set_league_id_handler.py`，將 `_update_league_id` 改為更新 `chat_league_mapping.json`：

```python
    def _update_league_id(self, league_id: str) -> None:
        """更新 chat_league_mapping.json 中的對應關係。"""
        from src.config import current_chat_id
        chat_id = current_chat_id.get()
        if not chat_id:
            return
            
        from src.utils.path_utils import BASE_DIR
        import os
        import json
        
        mapping_path = os.path.join(BASE_DIR, "data", "security", "chat_league_mapping.json")
        mapping = {}
        if os.path.exists(mapping_path):
            try:
                with open(mapping_path, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
            except Exception:
                mapping = {}
                
        mapping[chat_id] = str(league_id)
        
        try:
            os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
            with open(mapping_path, "w", encoding="utf-8") as f:
                json.dump(mapping, f, ensure_ascii=False, indent=2)
        except Exception as e:
            import logging
            logging.error(f"[SetLeagueIdHandler] 寫入 chat_league_mapping.json 失敗: {e}")
```

同時，調整 `execute` 中回覆使用者成功的訊息：
```python
        # 將對應文字修改為：
        self.reply_text(event, configuration, f"✅ 成功將此聊天室綁定至聯賽 ID：{league_id}")
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/handlers/set_league_id_handler.py tests/handlers/test_settings_and_setup.py
git commit -m "feat: rewrite SetLeagueIdHandler to bind league_id to chat_id instead of global config"
```

---

### Task 5: 補漏 Yahoo API 授權異常友善捕捉

**Files:**
- Modify: `src/fetcher.py`
- Modify: `tests/test_fetcher.py`

- [ ] **Step 1: 撰寫 Yahoo API 授權異常捕捉測試**

修改 `tests/test_fetcher.py`，模擬 API 錯誤（例如私人聯盟權限拒絕拋出 HTTPError），確認 fetch 介面能拋出包裝後代表無存取權限的專用 Exception 或以 None / 錯誤標記處理。
由於現存 Handler 中獲取 API 多數透過 `YahooFantasyFetcher`，我們在 `YahooFantasyFetcher` 加入錯誤轉換：

```python
def test_fetch_league_metadata_permission_denied():
    from src.fetcher import YahooFantasyFetcher, LeaguePermissionError
    fetcher = YahooFantasyFetcher()
    
    # 模擬 make_request 拋出 401 或 403 異常
    from urllib.error import HTTPError
    mock_err = HTTPError("url", 403, "Forbidden", {}, None)
    fetcher.ctx = MagicMock()
    fetcher.ctx.make_request.side_effect = mock_err
    
    with pytest.raises(LeaguePermissionError):
        fetcher.fetch_league_metadata("67890")
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/test_fetcher.py -v`
Expected: FAIL (ImportError: cannot import name 'LeaguePermissionError')

- [ ] **Step 3: 定義並拋出 LeaguePermissionError**

在 `src/fetcher.py` 最上方定義一個專屬的例外類別，並在抓取 API 拋出 401 / 403 HTTPError 時進行包裝轉換：

```python
class LeaguePermissionError(Exception):
    """Yahoo 聯賽無授權或存取權限錯誤"""
    pass
```

並在 `YahooFantasyFetcher` 中，對 API 調用加上例外捕捉處理。如：
```python
    def fetch_league_metadata(self, league_id: str) -> dict:
        league_id = self._normalize_league_id(league_id)
        url = f"league/{league_id}"
        try:
            return self.ctx.make_request(url, league=league_id)
        except Exception as e:
            # 檢查是否為 401 或 403 錯誤
            err_msg = str(e)
            if "401" in err_msg or "403" in err_msg:
                raise LeaguePermissionError("Yahoo Fantasy API 權限拒絕") from e
            raise e
```
（同樣將此 try-except 包裝套用在 fetcher 獲取 league 的其它核心方法中）

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/test_fetcher.py -v`
Expected: PASS

- [ ] **Step 5: 更新對應 Handler 呈現友好回覆**

以 `StatsHandler` 為例，在 `execute` 被呼叫拉取 API 發生 `LeaguePermissionError` 時進行捕捉並回覆 LINE 使用者：

```python
        try:
            # 核心拉取 logic
            ...
        except LeaguePermissionError:
            self.reply_text(
                event, 
                configuration, 
                "⚠️ 機器人 Yahoo 帳號目前無權限存取此聯盟。請確保已將機器人的 Yahoo 帳號邀請為該聯盟的成員或 Co-manager。"
            )
            return
```
（在 [injury_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/injury_handler.py), [matchup_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/matchup_handler.py), [stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/stats_handler.py), [user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/user_stats_handler.py), [player_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/player_handler.py) 進行同等的例外包裝捕捉回覆）

- [ ] **Step 6: 執行測試並提交**

```bash
git add src/fetcher.py src/handlers/ tests/test_fetcher.py
git commit -m "feat: catch Yahoo API 401/403 errors and reply with a friendly permission warning"
```
