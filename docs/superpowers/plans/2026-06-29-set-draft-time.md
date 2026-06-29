# 設置選秀時間功能實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 LINE Bot `#設置` 選單中的「設置選秀時間」功能，讓白名單使用者能經由 60 秒的對話 Session 輸入任何格式的選秀時間（如 20260701 11:00），並藉由 LLM 解析為標準時間並物理隔離儲存於 `data/league/<LEAGUE_ID>/settings.json` 中，並同時重整 `#選秀` 指令的倒數顯示格式。

**Architecture:**
1. 重構 `src/config.py`，動態解析並載入對應 `LEAGUE_ID` 目錄下的 `settings.json`，覆蓋 `DRAFT_DATE` 與 `next_season_start_date` 設定。
2. 擴充 `session_manager.py` 支援不同類型的 Session。新增 `SetDraftTimeHandler` 以開啟「設置選秀時間」Session。
3. 在 `LLMAgent` 中新增 `parse_draft_date` 並在 `IntentRouter.route` 中攔截改選秀時間會話，利用 LLM 將使用者的發言格式化後寫入 `settings.json`。
4. 重構 `MiscHandler`，相容 `YYYY-MM-DD HH:MM` 格式，遷移開季時間快取至 `settings.json`，並優化選秀指令回覆格式。

**Tech Stack:** Python, pytest, google-genai, line-bot-sdk-python

---

### Task 1: 更新配置加載器以支援自訂 `settings.json`

**Files:**
- Modify: `src/config.py`
- Test: `tests/test_config_split.py`

- [ ] **Step 1: 撰寫配置覆蓋測試**

在 `tests/test_config_split.py` 中新增一個測試，驗證當聯盟 `settings.json` 存在時，自訂的 `DRAFT_DATE` 與 `next_season_start_date` 能成功覆寫環境變數。

```python
import os
import json
import pytest
from src.config import load_config

def test_load_config_settings_override(tmp_path):
    # Mock data/security/league_config.json 傳回 18457
    from src.utils.path_utils import BASE_DIR
    security_dir = os.path.join(BASE_DIR, "data", "security")
    os.makedirs(security_dir, exist_ok=True)
    config_path = os.path.join(security_dir, "league_config.json")
    
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({"LEAGUE_ID": "18457"}, f)
        
    # 建立 data/league/18457/settings.json
    league_dir = os.path.join(BASE_DIR, "data", "league", "18457")
    os.makedirs(league_dir, exist_ok=True)
    settings_file = os.path.join(league_dir, "settings.json")
    
    with open(settings_file, "w", encoding="utf-8") as sf:
        json.dump({
            "LEAGUE_ID": "18457",
            "DRAFT_DATE": "2026-10-15 20:00",
            "next_season_start_date": "2026-10-20 08:00"
        }, sf)
        
    try:
        config = load_config()
        assert config["LEAGUE_ID"] == "18457"
        assert config["DRAFT_DATE"] == "2026-10-15 20:00"
        assert config["NEXT_SEASON_START_DATE"] == "2026-10-20 08:00"
    finally:
        # 清理測試檔案
        if os.path.exists(settings_file):
            os.remove(settings_file)
```

- [ ] **Step 2: 執行測試並確認失敗**

運行：`.venv\Scripts\python -m pytest tests/test_config_split.py::test_load_config_settings_override -v`
Expected: FAIL (AssertionError)

- [ ] **Step 3: 實作 config.py 的 settings.json 解析邏輯**

在 `src/config.py` 的 `load_config()` 方法中，讀取完 `LEAGUE_ID` 後，加入讀取 `settings.json` 的邏輯：

```python
    # 讀取 data/league/<LEAGUE_ID>/settings.json
    draft_date = os.getenv("DRAFT_DATE")
    next_season_start = os.getenv("NEXT_SEASON_START_DATE")
    
    if league_id:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        settings_file = os.path.join(base_dir, "data", "league", league_id, "settings.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as sf:
                    settings_data = json.load(sf)
                    if "DRAFT_DATE" in settings_data:
                        draft_date = settings_data["DRAFT_DATE"]
                    if "next_season_start_date" in settings_data:
                        next_season_start = settings_data["next_season_start_date"]
            except Exception:
                pass
```

並更新 `load_config` 回傳的字典，確保對應至 `DRAFT_DATE` 與 `NEXT_SEASON_START_DATE`：
```python
        "NEXT_SEASON_START_DATE": next_season_start,
        "DRAFT_DATE": draft_date,
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/test_config_split.py::test_load_config_settings_override -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/config.py tests/test_config_split.py
git commit -m "feat: override config DRAFT_DATE and NEXT_SEASON_START_DATE from league settings.json"
```

---

### Task 2: 擴充對話會話管理器 (Session Manager)

**Files:**
- Modify: `src/utils/session_manager.py`
- Create: `tests/test_session_manager.py`

- [ ] **Step 1: 撰寫選秀會話與通用 Session 的測試**

建立 `tests/test_session_manager.py`：

```python
import time
from src.utils.session_manager import (
    set_nickname_session, get_nickname_session, clear_nickname_session,
    set_draft_session, get_draft_session, clear_draft_session
)

def test_sessions_type_isolation():
    user_id = "U12345"
    
    # 測試設定並讀取選秀時間會話
    set_draft_session(user_id, duration_sec=2)
    draft_session = get_draft_session(user_id)
    assert draft_session is not None
    assert draft_session["type"] == "draft_time"
    
    # 驗證暱稱會話回傳為空
    assert get_nickname_session(user_id) is None
    
    # 測試清除選秀時間會話
    clear_draft_session(user_id)
    assert get_draft_session(user_id) is None
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/test_session_manager.py -v`
Expected: FAIL (ImportError or AttributeError)

- [ ] **Step 3: 實作通用型會話管理**

修改 `src/utils/session_manager.py`，引入多類型 Session 分流：

```python
import time

_sessions = {}  # 格式: { user_id: { "type": str, "expire_at": float, ... } }

def set_nickname_session(user_id: str, team_id: str, duration_sec: int = 60) -> None:
    _sessions[user_id] = {
        "type": "nickname",
        "team_id": team_id,
        "expire_at": time.time() + duration_sec
    }

def get_nickname_session(user_id: str) -> dict | None:
    session = _sessions.get(user_id)
    if not session or session.get("type") != "nickname":
        return None
    if time.time() > session["expire_at"]:
        del _sessions[user_id]
        return None
    return session

def clear_nickname_session(user_id: str) -> None:
    if user_id in _sessions and _sessions[user_id].get("type") == "nickname":
        del _sessions[user_id]

def set_draft_session(user_id: str, duration_sec: int = 60) -> None:
    _sessions[user_id] = {
        "type": "draft_time",
        "expire_at": time.time() + duration_sec
    }

def get_draft_session(user_id: str) -> dict | None:
    session = _sessions.get(user_id)
    if not session or session.get("type") != "draft_time":
        return None
    if time.time() > session["expire_at"]:
        del _sessions[user_id]
        return None
    return session

def clear_draft_session(user_id: str) -> None:
    if user_id in _sessions and _sessions[user_id].get("type") == "draft_time":
        del _sessions[user_id]
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/test_session_manager.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/utils/session_manager.py tests/test_session_manager.py
git commit -m "feat: generalize session_manager to support draft_time and nickname sessions"
```

---

### Task 3: 實作新指令處理器 `SetDraftTimeHandler`

**Files:**
- Create: `src/handlers/set_draft_time_handler.py`
- Create: `tests/handlers/test_set_draft_time_handler.py`

- [ ] **Step 1: 撰寫 SetDraftTimeHandler 的測試**

建立 `tests/handlers/test_set_draft_time_handler.py`：

```python
import pytest
from unittest.mock import MagicMock, patch
from src.handlers.set_draft_time_handler import SetDraftTimeHandler

def test_set_draft_time_handler_execute_no_league_id():
    handler = SetDraftTimeHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#設置選秀時間"
    config = MagicMock()
    
    with patch("src.handlers.set_draft_time_handler.load_config", return_value={"LEAGUE_ID": None}):
        handler.execute(event, config)
        handler.reply_text.assert_called_once_with(
            event, config, "⚠️ 聯賽 ID 尚未配置，無法設定選秀時間。"
        )

def test_set_draft_time_handler_execute_success():
    handler = SetDraftTimeHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.source.user_id = "U12345"
    event.message.text = "#設置選秀時間"
    config = MagicMock()
    
    with patch("src.handlers.set_draft_time_handler.load_config", return_value={"LEAGUE_ID": "18457", "DRAFT_DATE": None}), \
         patch("src.handlers.set_draft_time_handler.set_draft_session") as mock_set_session:
        handler.execute(event, config)
        mock_set_session.assert_called_once_with("U12345", 60)
        handler.reply_text.assert_called_once_with(
            event, config, "👉 請在 60 秒內直接輸入新的選秀時間："
        )
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/handlers/test_set_draft_time_handler.py -v`
Expected: FAIL (ImportError)

- [ ] **Step 3: 建立 SetDraftTimeHandler 類別**

建立 `src/handlers/set_draft_time_handler.py`：

```python
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.utils.session_manager import set_draft_session

class SetDraftTimeHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        self.exclude_from_llm = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#設置選秀時間"
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        
        if not league_id:
            self.reply_text(event, configuration, "⚠️ 聯賽 ID 尚未配置，無法設定選秀時間。")
            return
            
        user_id = event.source.user_id if event.source and hasattr(event.source, "user_id") else None
        if not user_id:
            return
            
        set_draft_session(user_id, 60)
        self.reply_text(event, configuration, "👉 請在 60 秒內直接輸入新的選秀時間：")

    @property
    def instruction_desc(self) -> str:
        return "#設置選秀時間 : (限白名單) 設定選秀剩餘倒數時間"
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/handlers/test_set_draft_time_handler.py -v`
Expected: PASS

- [ ] **Step 5: 註冊 Handler 到 Dispatcher**

在 `bot.py` 中導入並註冊 `SetDraftTimeHandler`：
在 `bot.py:91-92` 加一行：
```python
from src.handlers.set_draft_time_handler import SetDraftTimeHandler
dispatcher.register(SetDraftTimeHandler())
```

- [ ] **Step 6: 執行測試並提交**

運行：`.venv\Scripts\python -m pytest tests/handlers/test_set_draft_time_handler.py -v`
Expected: PASS

```bash
git add src/handlers/set_draft_time_handler.py tests/handlers/test_set_draft_time_handler.py bot.py
git commit -m "feat: implement SetDraftTimeHandler and register it to dispatcher"
```

---

### Task 4: 啟用設置選單的按鈕 (Settings Menu)

**Files:**
- Modify: `src/handlers/settings_handler.py`
- Modify: `tests/handlers/test_settings_handler.py`

- [ ] **Step 1: 修正 SettingsHandler 的單元測試**

修改 `tests/handlers/test_settings_handler.py`，使其預期「設置選秀時間」按鈕對應至 `#設置選秀時間`，而不是 "即將推出"：

```diff
-        ("設置選秀時間 (即將推出)", ""),
+        ("設置選秀時間", "#設置選秀時間"),
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/handlers/test_settings_handler.py -v`
Expected: FAIL

- [ ] **Step 3: 啟用按鈕連線**

修改 `src/handlers/settings_handler.py` 中 `buttons` 的配對陣列：

```python
            buttons = [
                ("設置選秀時間", "#設置選秀時間"),
                ("設置玩家暱稱", "#設置玩家暱稱"),
                (None, None),
                ("更換聯盟ID (即將推出)", ""),
                ("移除聯盟ID (即將推出)", "")
            ]
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/handlers/test_settings_handler.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/handlers/settings_handler.py tests/handlers/test_settings_handler.py
git commit -m "feat: enable set draft time button in settings card"
```

---

### Task 5: 在 `LLMAgent` 新增時間格式解析器

**Files:**
- Modify: `src/llm/llm_agent.py`
- Modify: `tests/test_llm_agent.py`

- [ ] **Step 1: 撰寫 LLM 時間解析測試**

在 `tests/test_llm_agent.py` 中新增 `test_parse_draft_date_success`：

```python
def test_parse_draft_date_success():
    agent = LLMAgent()
    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "success": True,
        "formatted_date": "2026-07-01 11:00"
    }
    agent.provider = mock_provider
    
    res = agent.parse_draft_date("20260701 11:00")
    assert res == {"success": True, "formatted_date": "2026-07-01 11:00"}
    mock_provider.generate_json.assert_called_once()
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/test_llm_agent.py -v`
Expected: FAIL (AttributeError: 'LLMAgent' object has no attribute 'parse_draft_date')

- [ ] **Step 3: 實作 parse_draft_date 方法**

在 `src/llm/llm_agent.py` 中新增 `parse_draft_date` 方法：

```python
    def parse_draft_date(self, text: str) -> dict:
        """使用 LLM 將任意自然語言描述的時間轉換為標準的 YYYY-MM-DD HH:MM 格式。"""
        if not self.provider:
            return {"success": False, "formatted_date": None}
            
        prompt = (
            f"請將使用者輸入的日期/時間描述：'{text}' 轉換為標準的日期時間格式 'YYYY-MM-DD HH:MM'。\n"
            "規則：\n"
            "1. 必須精準推估出年、月、日、時、分。如果沒有提供年份，請以今年或最合理的未來年份推估。不需包含秒數。\n"
            "2. 嚴格回傳 JSON 格式，包含兩個欄位：\n"
            "   - 'formatted_date': 格式化後的字串，例如 '2026-07-01 11:00'；若完全無法解析出合理的日期時間，則填入 null。\n"
            "   - 'success': 布林值，代表是否成功解析出精確的日期時間。"
        )
        try:
            return self.provider.generate_json(prompt, temperature=0.1)
        except Exception as e:
            import logging
            logging.error(f"[LLM] 解析選秀時間失敗: {e}")
            return {"success": False, "formatted_date": None}
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/test_llm_agent.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/llm/llm_agent.py tests/test_llm_agent.py
git commit -m "feat: implement parse_draft_date in LLMAgent using generate_json"
```

---

### Task 6: 路由攔截與設定檔存取 (Intent Router Interception)

**Files:**
- Modify: `src/handlers/intent_router.py`
- Modify: `tests/test_intent_router.py`

- [ ] **Step 1: 撰寫選秀會話攔截測試**

在 `tests/test_intent_router.py` 中新增以下測試：

```python
from unittest.mock import MagicMock, patch
from src.handlers.intent_router import IntentRouter

def test_intent_router_intercept_draft_session_success():
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    event = MagicMock()
    event.source.user_id = "U12345"
    event.message.text = "10月15日晚上8點"
    config = MagicMock()
    
    # 模擬 Session 存在
    mock_session = {"type": "draft_time", "expire_at": 9999999999.0}
    
    # 模擬 LLM 解析成功
    router.llm_agent = MagicMock()
    router.llm_agent.parse_draft_date.return_value = {
        "success": True,
        "formatted_date": "2026-10-15 20:00"
    }
    
    with patch("src.handlers.intent_router.get_draft_session", return_value=mock_session), \
         patch("src.handlers.intent_router.clear_draft_session") as mock_clear, \
         patch.object(router, "_update_league_settings") as mock_update, \
         patch.object(router, "reply_text") as mock_reply:
         
        router.route(event, config)
        
        router.llm_agent.parse_draft_date.assert_called_with("10月15日晚上8點")
        mock_update.assert_called_with({"DRAFT_DATE": "2026-10-15 20:00"})
        mock_clear.assert_called_with("U12345")
        mock_reply.assert_called_with(event, config, "✅ 成功將選秀時間修改為：2026-10-15 20:00")
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/test_intent_router.py -v`
Expected: FAIL (AttributeError or mock assertions fail)

- [ ] **Step 3: 實作設定檔寫入輔助方法**

在 `src/handlers/intent_router.py` 中，實作 `_update_league_settings` 用以將資料寫入對應的 `settings.json` 中：

```python
    def _update_league_settings(self, new_settings: dict) -> None:
        """更新當前聯賽的 settings.json。"""
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            return
            
        from src.utils.path_utils import BASE_DIR
        settings_path = os.path.join(BASE_DIR, "data", "league", league_id, "settings.json")
        
        settings = {}
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                settings = {}
                
        settings.update(new_settings)
        settings["LEAGUE_ID"] = league_id
        
        try:
            os.makedirs(os.path.dirname(settings_path), exist_ok=True)
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logging.error(f"[IntentRouter] 寫入 settings.json 失敗: {e}")
```

- [ ] **Step 4: 實作會話路由攔截**

在 `src/handlers/intent_router.py` 導入對應方法：
```python
from src.utils.session_manager import (
    get_nickname_session, clear_nickname_session,
    get_draft_session, clear_draft_session
)
```

並修改 `IntentRouter.route()` 方法，將其插在暱稱會話檢測之後：

```python
        # 1. 檢測暱稱 Session
        if user_id:
            session = get_nickname_session(user_id)
            if session:
                if user_text.startswith("#"):
                    clear_nickname_session(user_id)
                else:
                    team_id = session["team_id"]
                    self._update_team_nickname(team_id, user_text)
                    clear_nickname_session(user_id)
                    self.reply_text(event, configuration, f"✅ 成功將暱稱修改為：{user_text}")
                    return

            # 2. 檢測選秀時間 Session (新增)
            draft_session = get_draft_session(user_id)
            if draft_session:
                if user_text.startswith("#"):
                    clear_draft_session(user_id)
                else:
                    res = self.llm_agent.parse_draft_date(user_text)
                    if res.get("success") and res.get("formatted_date"):
                        formatted_date = res["formatted_date"]
                        self._update_league_settings({"DRAFT_DATE": formatted_date})
                        clear_draft_session(user_id)
                        self.reply_text(event, configuration, f"✅ 成功將選秀時間修改為：{formatted_date}")
                        return
                    else:
                        self.reply_text(
                            event, 
                            configuration, 
                            "⚠️ 無法辨識您輸入的時間，請試著換個方式輸入（例如 10月15日晚上8點，或發送任意 # 指令以取消）："
                        )
                        return
```

- [ ] **Step 5: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/test_intent_router.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add src/handlers/intent_router.py tests/test_intent_router.py
git commit -m "feat: intercept and process draft time setup sessions in IntentRouter using LLMAgent"
```

---

### Task 7: 倒數時間解析相容與開季快取遷移

**Files:**
- Modify: `src/handlers/misc_handler.py`
- Modify: `tests/test_misc_handler.py`
- Modify: `tests/handlers/test_misc_handler_season.py`

- [ ] **Step 1: 撰寫開季快取位置遷移測試**

修改 `tests/handlers/test_misc_handler_season.py` 中 `test_misc_handler_season_start_flow_llm_search`：
* 把原本 `mock_save` 改為測試是否呼叫寫入 `settings.json` 的方法。
* 不過在此處，因為 `MiscHandler` 是直接讀寫 `settings.json`，我們需要確保 `_handle_season_start` 的實作呼叫了對應檔案的寫入。
* 由於我們已手動提供寫入快取的方法（在 `MiscHandler` 內或使用統一的 JSON 寫入），我們改為 mock `save_league_metadata` 或更新其輔助方法以寫入 `settings.json`。

Wait, in `src/utils/cache_utils.py`:
```python
def save_league_metadata(data: dict) -> None:
    ...
```
我們可以直接在 `MiscHandler` 中修改 `_handle_season_start` 中寫入 `next_season_start_date` 的目標，將其寫入 `settings.json` 中而非 `metadata.json` 中。
讓我們先看一下 `_handle_season_start` 中的這段代碼：
```python
            if res.get("success") and res.get("start_date"):
                target_time_str = res["start_date"]
                meta["next_season_start_date"] = target_time_str
                save_league_metadata(meta)
```
為了完全避開 `metadata.json`，我們可以更新 `_handle_season_start` 去把 `next_season_start_date` 寫入 `settings.json`：
```python
                # 寫入 settings.json 中
                self._update_settings_file({"next_season_start_date": target_time_str})
```
並在 `MiscHandler` 內部新增輔助方法 `_update_settings_file`：
```python
    def _update_settings_file(self, new_data: dict) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            return
        from src.utils.path_utils import BASE_DIR
        settings_path = os.path.join(BASE_DIR, "data", "league", league_id, "settings.json")
        
        settings = {}
        if os.path.exists(settings_path):
            try:
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json.load(f)
            except Exception:
                settings = {}
        settings.update(new_data)
        settings["LEAGUE_ID"] = league_id
        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, ensure_ascii=False, indent=2)
        except Exception:
            pass
```

在 `tests/handlers/test_misc_handler_season.py` 中更新測試：

```python
@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.LLMAgent")
def test_misc_handler_season_start_flow_llm_search_with_settings(mock_agent_class, mock_load_meta):
    handler = MiscHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#開季"
    config = MagicMock()
    
    meta = {}
    mock_load_meta.return_value = meta
    
    mock_agent = MagicMock()
    mock_agent.search_nba_season_start.return_value = {
        "success": True,
        "start_date": "2026-10-20 08:00:00"
    }
    mock_agent_class.return_value = mock_agent
    
    with patch.object(handler, "_calculate_countdown", return_value="15 天 1 小時 0 分鐘"), \
         patch.object(handler, "_update_settings_file") as mock_save:
         
        handler.execute(event, config)
        mock_save.assert_called_once_with({"next_season_start_date": "2026-10-20 08:00:00"})
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/handlers/test_misc_handler_season.py -v`
Expected: FAIL

- [ ] **Step 3: 實作相容性解析與 `settings.json` 開季快取載入與寫入**

在 `src/handlers/misc_handler.py` 中：
* 修改 `_calculate_countdown` 支援無秒與有秒的格式相容：
  ```python
      def _calculate_countdown(self, target_time_str: str) -> str:
          taipei_tz = pytz.timezone("Asia/Taipei")
          now_taipei = datetime.now(taipei_tz)
          
          try:
              target_dt_naive = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
          except ValueError:
              target_dt_naive = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M")
              
          target_dt = taipei_tz.localize(target_dt_naive)
  ```
* 新增 `_update_settings_file` 輔助方法：
  ```python
      def _update_settings_file(self, new_data: dict) -> None:
          config = load_config()
          league_id = config.get("LEAGUE_ID")
          if not league_id:
              return
          from src.utils.path_utils import BASE_DIR
          settings_path = os.path.join(BASE_DIR, "data", "league", league_id, "settings.json")
          
          settings = {}
          if os.path.exists(settings_path):
              try:
                  with open(settings_path, "r", encoding="utf-8") as f:
                      settings = json.load(f)
              except Exception:
                  settings = {}
          settings.update(new_data)
          settings["LEAGUE_ID"] = league_id
          try:
              with open(settings_path, "w", encoding="utf-8") as f:
                  json.dump(settings, f, ensure_ascii=False, indent=2)
          except Exception as e:
              logging.error(f"[MiscHandler] 寫入 settings.json 失敗: {e}")
  ```
* 修改 `_handle_season_start`，優先讀取 `settings.json`（已藉由 `load_config()["NEXT_SEASON_START_DATE"]` 加載於 `config` 中），並移除對 `metadata.json` 寫入 `next_season_start_date` 的依賴：
  ```python
      def _handle_season_start(self, event: MessageEvent, configuration: Configuration) -> None:
          config = load_config()
          today_pacific = get_pacific_date()
          target_time_str = config.get("NEXT_SEASON_START_DATE")
          
          # 1. 如果從 config.get("NEXT_SEASON_START_DATE") (即 settings.json) 讀到值
          if target_time_str:
              pass
          else:
              # 2. 檢查目前 Yahoo metadata 中繼資料的 start_date
              meta = load_league_metadata() or {}
              meta_start = meta.get("start_date")
              if meta_start and meta_start > today_pacific:
                  target_time_str = f"{meta_start} 08:00:00"
                  
          # 3. 啟動 LLM 網路搜尋
          if not target_time_str:
              logging.info("[MiscHandler] 啟動 LLM 搜尋新賽季開始時間...")
              agent = LLMAgent()
              current_year = datetime.now().year
              nba_year = current_year if datetime.now().month < 10 else current_year + 1
              
              res = agent.search_nba_season_start(nba_year)
              if res.get("success") and res.get("start_date"):
                  target_time_str = res["start_date"]
                  self._update_settings_file({"next_season_start_date": target_time_str})
                  logging.info(f"[MiscHandler] 成功將 LLM 搜尋到的開季時間寫入 settings.json: {target_time_str}")
  ```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/handlers/test_misc_handler_season.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/handlers/misc_handler.py tests/handlers/test_misc_handler_season.py
git commit -m "feat: migrate next_season_start_date cache to settings.json and make countdown parsing backward compatible"
```

---

### Task 8: 重寫選秀時間倒數回覆格式

**Files:**
- Modify: `src/handlers/misc_handler.py`
- Modify: `tests/test_misc_handler.py`

- [ ] **Step 1: 更新選秀指令倒數回覆的測試**

修改 `tests/test_misc_handler.py` 中 `test_execute_draft` 方法：
* 更新 `DRAFT_DATE` 設定值格式為 `2026-10-15 10:00`。
* 驗證其預期回傳值是否為包含目標日期與剩餘時間的格式。

```python
    # 2. Offseason, and DRAFT_DATE set -> reply countdown
    mock_get_pacific.return_value = "2026-05-29"
    mock_load_config.return_value = {"DRAFT_DATE": "2026-10-15 10:00"}
    
    with patch.object(handler, "_calculate_countdown", return_value="139 天 7 小時 0 分鐘") as mock_calc:
        handler.execute(mock_event, mock_config)
        mock_calc.assert_called_with("2026-10-15 10:00")
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert reply_req.messages[0].text == "⚔️ 聯盟選秀時間已設定為：\n👉 2026年10月15日 10:00\n⚔️ 距離聯盟選秀開始還有：\n👉 139 天 7 小時 0 分鐘"
```

- [ ] **Step 2: 執行測試確認失敗**

運行：`.venv\Scripts\python -m pytest tests/test_misc_handler.py::test_execute_draft -v`
Expected: FAIL

- [ ] **Step 3: 重構選秀顯示格式**

修改 `src/handlers/misc_handler.py` 的 `_handle_draft_countdown` 方法：

```python
    def _handle_draft_countdown(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        target_time_str = config.get("DRAFT_DATE")
        if not target_time_str:
            logging.info("DRAFT_DATE not configured, ignoring")
            return
        
        formatted_date = target_time_str
        try:
            # 支援 YYYY-MM-DD HH:MM:SS 與 YYYY-MM-DD HH:MM
            time_parts = target_time_str.split()[-1].split(":")
            if len(time_parts) == 3:
                dt = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
            else:
                dt = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M")
            formatted_date = f"{dt.year}年{dt.month}月{dt.day}日 {dt.hour:02d}:{dt.minute:02d}"
        except Exception:
            pass
            
        countdown_text = self._calculate_countdown(target_time_str)
        if countdown_text == "已經到達！":
            self.reply_text(event, configuration, "⚔️ 聯盟選秀已經結束囉！")
        else:
            reply_content = (
                f"⚔️ 聯盟選秀時間已設定為：\n"
                f"👉 {formatted_date}\n"
                f"⚔️ 距離聯盟選秀開始還有：\n"
                f"👉 {countdown_text}"
            )
            self.reply_text(event, configuration, reply_content)
```

- [ ] **Step 4: 執行測試確認通過**

運行：`.venv\Scripts\python -m pytest tests/test_misc_handler.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add src/handlers/misc_handler.py tests/test_misc_handler.py
git commit -m "feat: output both draft date and countdown in a friendly format for #選秀 command"
```
