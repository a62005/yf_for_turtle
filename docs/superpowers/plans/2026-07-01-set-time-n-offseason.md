# 合併時間設定與賽季按鈕隱藏實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作手動設置開季時間功能，將選秀與開季設定合併為 SetTimeHandler，在賽季中自動隱藏這兩個按鈕，並藉由設定 `exclude_from_llm = True` 確保設定功能強制以實體 `#` 指令觸發而不經由 LLM 語意匹配。

**Architecture:** 
1. 在 `session_manager.py` 新增 `season_start_time` 的會話（Session）讀寫與清除。
2. 建立 `SetTimeHandler`，用以同時處理 `#設置選秀時間` 與 `#設置開季時間`；原 `SetDraftTimeHandler` 與其測試檔予以物理刪除。
3. 調整 `IntentRouter` 的攔截器與 `SettingsHandler` 的按鈕建構邏輯（賽季中不渲染時間按鈕、移除更換聯盟ID按鈕）。

**Tech Stack:** Python 3, Line Bot SDK v3, pytest

---

### Task 1: 擴充 `session_manager` 會話管理與編寫測試

**Files:**
- Modify: `src/utils/session_manager.py`
- Modify: `tests/test_session_manager.py`

- [ ] **Step 1: 撰寫失敗的會話單元測試**

在 `tests/test_session_manager.py` 中新增 `test_season_start_time_session` 測試案例：

```python
def test_season_start_time_session():
    from src.utils.session_manager import (
        set_season_start_time_session,
        get_season_start_time_session,
        clear_season_start_time_session,
    )
    user_id = "user_season_test"
    season_data = "2026-10-22 08:00"
    
    # 測試設定與取得
    set_season_start_time_session(user_id, season_data, duration_sec=10)
    data = get_season_start_time_session(user_id)
    assert data == season_data
    
    # 測試清除
    clear_season_start_time_session(user_id)
    assert get_season_start_time_session(user_id) is None
```

- [ ] **Step 2: 執行測試並驗證失敗**

Run: `pytest tests/test_session_manager.py -k test_season_start_time_session -v`
Expected: FAIL (ImportError: cannot import name 'set_season_start_time_session')

- [ ] **Step 3: 撰寫 minimal 實作使其通過測試**

在 `src/utils/session_manager.py` 尾部新增以下三個函式：

```python
def set_season_start_time_session(user_id: str, data: any, duration_sec: int = 60) -> None:
    set_session(user_id, "season_start_time", data, duration_sec)

def get_season_start_time_session(user_id: str) -> any | None:
    return get_session(user_id, "season_start_time")

def clear_season_start_time_session(user_id: str) -> None:
    clear_session(user_id, "season_start_time")
```

- [ ] **Step 4: 執行測試並驗證成功**

Run: `pytest tests/test_session_manager.py -v`
Expected: PASS (所有測試，包含新測試，皆成功通過)

- [ ] **Step 5: 提交變更**

```bash
git add src/utils/session_manager.py tests/test_session_manager.py
git commit -m "feat: add season_start_time session helper and tests"
```

---

### Task 2: 重構並合併時間處理器 `SetTimeHandler`

**Files:**
- Create: `src/handlers/set_time_handler.py`
- Create: `tests/handlers/test_set_time_handler.py`
- Modify: `bot.py`
- Delete: `src/handlers/set_draft_time_handler.py`
- Delete: `tests/handlers/test_set_draft_time_handler.py`

- [ ] **Step 1: 刪除舊的選秀時間 Handler 相關檔案**

```bash
git rm src/handlers/set_draft_time_handler.py tests/handlers/test_set_draft_time_handler.py
```

- [ ] **Step 2: 撰寫新的合併處理器 `SetTimeHandler` 測試**

建立 `tests/handlers/test_set_time_handler.py`：

```python
from unittest.mock import MagicMock, patch
import pytest

def test_set_time_handler_can_handle():
    from src.handlers.set_time_handler import SetTimeHandler
    handler = SetTimeHandler()
    assert handler.can_handle("#設置選秀時間") is True
    assert handler.can_handle("#設置開季時間") is True
    assert handler.can_handle("設置選秀時間") is False
    assert handler.can_handle("設置開季時間") is False

def test_set_time_handler_no_league_id():
    from src.handlers.set_time_handler import SetTimeHandler
    handler = SetTimeHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#設置選秀時間"
    event.source.user_id = "user123"
    config = MagicMock()

    with patch("src.handlers.set_time_handler.load_config", return_value={"LEAGUE_ID": None}):
        handler.execute(event, config)
        handler.reply_text.assert_called_once()
        args, kwargs = handler.reply_text.call_args
        assert "聯賽 ID 尚未配置" in args[2]

def test_set_time_handler_success_draft():
    from src.handlers.set_time_handler import SetTimeHandler
    handler = SetTimeHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#設置選秀時間"
    event.source.user_id = "user123"
    config = MagicMock()

    with patch("src.handlers.set_time_handler.load_config", return_value={"LEAGUE_ID": "12345"}):
        with patch("src.handlers.set_time_handler.set_draft_time_session") as mock_draft_session:
            handler.execute(event, config)
            mock_draft_session.assert_called_once_with("user123", True, duration_sec=60)
            handler.reply_text.assert_called_once()
            args, kwargs = handler.reply_text.call_args
            assert "請在 60 秒內直接輸入新的選秀時間" in args[2]

def test_set_time_handler_success_season():
    from src.handlers.set_time_handler import SetTimeHandler
    handler = SetTimeHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#設置開季時間"
    event.source.user_id = "user123"
    config = MagicMock()

    with patch("src.handlers.set_time_handler.load_config", return_value={"LEAGUE_ID": "12345"}):
        with patch("src.handlers.set_time_handler.set_season_start_time_session") as mock_season_session:
            handler.execute(event, config)
            mock_season_session.assert_called_once_with("user123", True, duration_sec=60)
            handler.reply_text.assert_called_once()
            args, kwargs = handler.reply_text.call_args
            assert "請在 60 秒內直接輸入新的開季時間" in args[2]
```

- [ ] **Step 3: 執行測試並驗證失敗**

Run: `pytest tests/handlers/test_set_time_handler.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'src.handlers.set_time_handler')

- [ ] **Step 4: 實作 `SetTimeHandler` 程式碼**

建立新檔案 `src/handlers/set_time_handler.py`：

```python
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.utils.session_manager import (
    set_draft_time_session,
    set_season_start_time_session,
)

class SetTimeHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        self.exclude_from_llm = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() in ["#設置選秀時間", "#設置開季時間"]
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        
        if not league_id:
            self.reply_text(event, configuration, "⚠️ 聯賽 ID 尚未配置，無法進行時間設定。")
            return
            
        user_id = event.source.user_id
        cmd = event.message.text.strip()
        
        if cmd == "#設置選秀時間":
            set_draft_time_session(user_id, True, duration_sec=60)
            self.reply_text(
                event, 
                configuration, 
                "👉 請在 60 秒內直接輸入新的選秀時間（格式：YYYY-MM-DD HH:MM）：\n例如：2026-10-15 19:30"
            )
        elif cmd == "#設置開季時間":
            set_season_start_time_session(user_id, True, duration_sec=60)
            self.reply_text(
                event, 
                configuration, 
                "👉 請在 60 秒內直接輸入新的開季時間（格式：YYYY-MM-DD HH:MM）：\n例如：2026-10-22 08:00"
            )

    @property
    def instruction_desc(self) -> str:
        return "#設置選秀時間 / #設置開季時間 : (限白名單) 調整選秀或開季時間"
```

- [ ] **Step 5: 執行測試並驗證成功**

Run: `pytest tests/handlers/test_set_time_handler.py -v`
Expected: PASS

- [ ] **Step 6: 修改 `bot.py` 替換與註冊**

在 `bot.py` 中：
* 將原先：
  ```python
  from src.handlers.set_draft_time_handler import SetDraftTimeHandler
  ```
  替換為：
  ```python
  from src.handlers.set_time_handler import SetTimeHandler
  ```
* 將原先：
  ```python
  dispatcher.register(SetDraftTimeHandler())
  ```
  替換為：
  ```python
  dispatcher.register(SetTimeHandler())
  ```

- [ ] **Step 7: 執行整體測試以確保系統沒有損壞**

Run: `pytest tests/ -v`
Expected: PASS (除了尚未重整的 settings_handler 與 intent_router 測試之外，其餘測試應皆能正常通過)

- [ ] **Step 8: 提交 Task 2 變更**

```bash
git add src/handlers/set_time_handler.py tests/handlers/test_set_time_handler.py bot.py
git commit -m "feat: merge draft and season start handlers into SetTimeHandler"
```

---

### Task 3: 調整 `IntentRouter` 的會話放行與攔截

**Files:**
- Modify: `src/handlers/intent_router.py`
- Modify: `tests/test_intent_router.py`

- [ ] **Step 1: 在 `tests/test_intent_router.py` 中撰寫開季時間會話攔截測試**

在 `tests/test_intent_router.py` 的 `test_intent_router_intercept_draft_session_failure` 之後，新增兩個測試方法：

```python
def test_intent_router_intercept_season_session_success():
    import json
    from unittest.mock import mock_open
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.utils.session_manager import set_season_start_time_session, get_season_start_time_session
    from linebot.v3.messaging import Configuration
    
    dispatcher = CommandDispatcher()
    router = IntentRouter(dispatcher)
    
    event = MagicMock()
    event.source.user_id = "user_test_season"
    event.source.type = "user"
    event.message.text = "10月22號早上8點"
    
    config = Configuration()
    config.access_token = "dummy_access_token"
    
    # 設置 60 秒的有效會話
    set_season_start_time_session("user_test_season", True, duration_sec=60)
    
    mock_settings = {"SEASON_START_DATE": "2025-01-01"}
    
    with patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": "123"}), \
         patch("src.handlers.intent_router.os.path.exists", return_value=True), \
         patch("src.handlers.intent_router.os.makedirs") as mock_makedirs, \
         patch("src.handlers.intent_router.open", mock_open(read_data=json.dumps(mock_settings))) as m_file, \
         patch.object(router.llm_agent, "parse_draft_date", return_value={"success": True, "date": "2026-10-22 08:00"}), \
         patch.object(router, "reply_text") as mock_reply:
         
        router.route(event, config)
        
        # 驗證會話被清空
        assert get_season_start_time_session("user_test_season") is None
        # 驗證寫入新設定到 settings.json
        assert m_file().write.called
        # 驗證回覆包含標準成功字串
        mock_reply.assert_called_once_with(event, config, "✅ 成功將開季時間修改為：2026-10-22 08:00")

def test_intent_router_intercept_season_session_failure():
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.utils.session_manager import set_season_start_time_session, get_season_start_time_session
    from linebot.v3.messaging import Configuration
    
    dispatcher = CommandDispatcher()
    router = IntentRouter(dispatcher)
    
    event = MagicMock()
    event.source.user_id = "user_test_season_fail"
    event.source.type = "user"
    event.message.text = "無法辨識的時間文字"
    
    config = Configuration()
    config.access_token = "dummy_access_token"
    
    set_season_start_time_session("user_test_season_fail", True, duration_sec=60)
    
    with patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": "123"}), \
         patch.object(router.llm_agent, "parse_draft_date", return_value={"success": False, "date": None}), \
         patch.object(router, "reply_text") as mock_reply:
         
        router.route(event, config)
        
        # 驗證會話依然存在 (解析失敗不清除會話)
        assert get_season_start_time_session("user_test_season_fail") is not None
        # 驗證回覆警告字串
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        assert "無法解析" in args[2] or "格式" in args[2] or "請重新輸入" in args[2]
```

- [ ] **Step 2: 執行測試並驗證失敗**

Run: `pytest tests/test_intent_router.py -k test_intent_router_intercept_season`
Expected: FAIL (會話未被攔截處理)

- [ ] **Step 3: 實作 `IntentRouter` 的 Session 處理**

修改 `src/handlers/intent_router.py`，主要改動有兩處：

1. **在 import 處引入開季時間的會話管理 API**：
   在檔案第 11-18 行間，修改為：
   ```python
   from src.utils.session_manager import (
       get_nickname_session, 
       clear_nickname_session,
       get_draft_time_session,
       clear_draft_time_session,
       get_league_id_session,
       clear_league_id_session,
       get_season_start_time_session,      # 新增此行
       clear_season_start_time_session,    # 新增此行
   )
   ```

2. **在 `should_process` 攔截判定中加入開季會話檢查**：
   在 `should_process` 方法內 (原第 54 與 82 行)，分別將：
   ```python
   if get_nickname_session(user_id) or get_draft_time_session(user_id) or get_league_id_session(user_id) or get_prize_session(user_id):
   ```
   修改為：
   ```python
   if get_nickname_session(user_id) or get_draft_time_session(user_id) or get_league_id_session(user_id) or get_prize_session(user_id) or get_season_start_time_session(user_id):
   ```

3. **在 `route` 中進行開季會話攔截與解析寫入**：
   在 `route` 方法內，攔截 `draft_session` (約原第 127 行之後)，新增對 `season_start_time` 會話的攔截區塊：
   ```python
            # 1-2. 攔截開季時間會話
            season_session = get_season_start_time_session(user_id)
            if season_session:
                if user_text.startswith("#"):
                    clear_season_start_time_session(user_id)
                else:
                    parsed = self.llm_agent.parse_draft_date(user_text)
                    if parsed.get("success") and parsed.get("date"):
                        date_val = parsed["date"]
                        self._update_league_settings({"SEASON_START_DATE": date_val})
                        clear_season_start_time_session(user_id)
                        self.reply_text(event, configuration, f"✅ 成功將開季時間修改為：{date_val}")
                    else:
                        self.reply_text(
                            event, 
                            configuration, 
                            "⚠️ 無法解析您輸入的時間格式，請重新輸入（例如：2026-10-22 08:00），或輸入 # 取消"
                        )
                    return
   ```

- [ ] **Step 4: 執行測試並驗證成功**

Run: `pytest tests/test_intent_router.py -k test_intent_router_intercept_season`
Expected: PASS

- [ ] **Step 5: 執行整個專案的 Intent Router 測試**

Run: `pytest tests/test_intent_router.py -v`
Expected: PASS

- [ ] **Step 6: 提交變更**

```bash
git add src/handlers/intent_router.py tests/test_intent_router.py
git commit -m "feat: add season_start_time session interception in IntentRouter"
```

---

### Task 4: 設定選單 `SettingsHandler` 邏輯調整與按鈕隱藏

**Files:**
- Modify: `src/handlers/settings_handler.py`
- Modify: `tests/handlers/test_settings_handler.py`

- [ ] **Step 1: 調整設定選單單元測試**

修改 `tests/handlers/test_settings_handler.py`，調整「休賽季」與「季中」的斷言邏輯：

1. **更新休賽季選單測試 `test_settings_handler_execute_offseason`**：
   * 驗證 `更換聯盟ID (即將推出)` 按鈕已不存在。
   * 驗證存在「設置選秀時間」（指令為 `#設置選秀時間`）與「設置開季時間」（指令為 `#設置開季時間`）。

   修改該測試函式末端斷言如下：
   ```python
           # 驗證在休賽季「設置選秀時間」啟用
           assert "設置選秀時間" in btn_labels
           draft_time_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "設置選秀時間"][0]
           assert draft_time_btn["action"]["text"] == "#設置選秀時間"

           # 驗證在休賽季「設置開季時間」啟用
           assert "設置開季時間" in btn_labels
           season_time_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "設置開季時間"][0]
           assert season_time_btn["action"]["text"] == "#設置開季時間"
           
           # 驗證「更換聯盟ID」已被移除
           assert "更換聯盟ID" not in [btn["action"].get("label", "") for btn in buttons_box["contents"] if btn["type"] == "button"]
   ```

2. **更新賽季中選單測試 `test_settings_handler_execute_inseason`**：
   * 驗證在非休賽季期間，設定選單內**完全不存在**任何與「設置選秀時間」及「設置開季時間」相關的按鈕。

   將 `test_settings_handler_execute_inseason` 修改為：
   ```python
   def test_settings_handler_execute_inseason():
       handler = SettingsHandler()
       handler.reply_flex = MagicMock()
   
       event = MagicMock()
       config = MagicMock()
   
       with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}), \
            patch("src.utils.cache_utils.load_league_metadata", return_value={"end_date": "2026-04-12"}), \
            patch("src.utils.time_utils.get_pacific_date", return_value="2026-04-10"):
           handler.execute(event, config)
           handler.reply_flex.assert_called_once()
           args, kwargs = handler.reply_flex.call_args
           
           flex_card = args[3]
           buttons_box = flex_card["body"]["contents"][1]
           btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
           
           # 驗證在季中，這兩個設定按鈕已被完全隱藏
           assert "設置選秀時間" not in btn_labels
           assert "設置選秀時間 (限休賽季)" not in btn_labels
           assert "設置開季時間" not in btn_labels
           assert "設置開季時間 (限休賽季)" not in btn_labels
   ```

- [ ] **Step 2: 執行測試並驗證失敗**

Run: `pytest tests/handlers/test_settings_handler.py -v`
Expected: FAIL (測試斷言失敗，季中仍然有反灰按鈕，且無設置開季時間按鈕)

- [ ] **Step 3: 修改 `SettingsHandler` 邏輯**

修改 `src/handlers/settings_handler.py` 內容如下（調整 `execute` 中 `buttons` 的生成方式，並排除更換聯盟 ID 按鈕）：

```python
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        
        if not league_id:
            title = "系統初始化設置"
            subtitle = None
            buttons = [("設置聯盟 ID", "#設置聯盟ID ")]
        else:
            title = f"聯盟設置 (ID: {league_id})"
            subtitle = None
            
            # 判斷是否為休賽季
            from src.utils.cache_utils import load_league_metadata
            from src.utils.time_utils import get_pacific_date
            meta = load_league_metadata(league_id) or {}
            end_date = meta.get("end_date")
            today_pacific = get_pacific_date()
            is_offseason = bool(end_date and today_pacific > end_date)
            
            buttons = []
            if is_offseason:
                buttons.append(("設置選秀時間", "#設置選秀時間"))
                buttons.append(("設置開季時間", "#設置開季時間"))
                
            buttons.extend([
                ("設置玩家暱稱", "#設置玩家暱稱"),
                ("設置獎金", "#設置獎金"),
                (None, None), # 分隔線
                ("移除聯盟ID", "#移除聯盟ID")
            ])
            
        flex_dict = build_button_menu_card(title, subtitle, buttons)
        self.reply_flex(event, configuration, "設置選單", flex_dict)
```

- [ ] **Step 4: 執行測試並驗證成功**

Run: `pytest tests/handlers/test_settings_handler.py -v`
Expected: PASS

- [ ] **Step 5: 執行整套專案的測試，驗證所有修改均無異常**

Run: `pytest tests/ -v`
Expected: PASS (所有測試均順利通過)

- [ ] **Step 6: 提交 Task 4 變更**

```bash
git add src/handlers/settings_handler.py tests/handlers/test_settings_handler.py
git commit -m "feat: hide setting time buttons in-season and remove change league ID option"
```
