# 設置獎金功能實作計畫 (Set Prize Feature Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為白名單管理員在 LINE Bot 中新增一個可以在 `#設置` 選單中點擊，並透過上傳圖片來設定/更新聯盟獎金的功能。

**Architecture:** 
1. 在 [settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py) 增加一個按鈕。
2. 擴充 [session_manager.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/session_manager.py) 以新增快取會話支援。
3. 建立 [set_prize_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_prize_handler.py) 用於啟動會話、刪除舊的 `bonus`/`bouns` 開頭圖檔，並將新圖片寫入為 `bonus.jpg`。
4. 擴充 [intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/intent_router.py) 攔截使用者在會話中的文字，並路由傳入的圖片至 Handler。
5. 在 [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py) 註冊新處理器，並掛載 `ImageMessageContent` 監聽。

**Tech Stack:** Python, Flask, line-bot-sdk-python (v3), pytest

---

### Task 1: 擴充 Session Manager

**Files:**
* Modify: [src/utils/session_manager.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/session_manager.py)
* Test: [tests/test_session_manager.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_session_manager.py)

- [ ] **Step 1: Write the failing test**

在 [tests/test_session_manager.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_session_manager.py) 的末尾新增以下測試：

```python
def test_prize_session():
    # 測試獎金設定會話的設定、讀取與清除
    user_id = "user_prize_test"
    
    # 測試設定與讀取
    from src.utils.session_manager import set_prize_session, get_prize_session, clear_prize_session
    set_prize_session(user_id, duration_sec=10)
    data = get_prize_session(user_id)
    assert data == {"active": True}
    
    # 測試清除
    clear_prize_session(user_id)
    assert get_prize_session(user_id) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_session_manager.py -k test_prize_session -v`
Expected: FAIL (ImportError: cannot import name 'set_prize_session')

- [ ] **Step 3: Write minimal implementation**

在 [src/utils/session_manager.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/session_manager.py) 的末尾新增以下方法：

```python
def set_prize_session(user_id: str, duration_sec: int = 60) -> None:
    set_session(user_id, "set_prize", {"active": True}, duration_sec)

def get_prize_session(user_id: str) -> any | None:
    return get_session(user_id, "set_prize")

def clear_prize_session(user_id: str) -> None:
    clear_session(user_id, "set_prize")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_session_manager.py -k test_prize_session -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/session_manager.py tests/test_session_manager.py
git commit -m "feat: add set_prize session helper to session_manager"
```

---

### Task 2: 擴充 CommandDispatcher 獲取已註冊處理器方法

**Files:**
* Modify: [src/handlers/dispatcher.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/dispatcher.py)
* Test: [tests/handlers/test_dispatcher.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/handlers/test_dispatcher.py)

- [ ] **Step 1: Write the failing test**

在 [tests/handlers/test_dispatcher.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/handlers/test_dispatcher.py) 末尾新增：

```python
def test_dispatcher_get_handler():
    dispatcher = CommandDispatcher()
    handler = MockHandler(True)
    dispatcher.register(handler)
    
    assert dispatcher.get_handler(MockHandler) is handler
    assert dispatcher.get_handler(BaseHandler) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/handlers/test_dispatcher.py -k test_dispatcher_get_handler -v`
Expected: FAIL (AttributeError: 'CommandDispatcher' object has no attribute 'get_handler')

- [ ] **Step 3: Write minimal implementation**

在 [src/handlers/dispatcher.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/dispatcher.py) 中新增 `get_handler` 方法：

```python
    def get_handler(self, handler_class):
        """根據 Class 獲取已註冊的 Handler 實例"""
        for h in self._handlers:
            if isinstance(h, handler_class):
                return h
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/handlers/test_dispatcher.py -k test_dispatcher_get_handler -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/handlers/dispatcher.py tests/handlers/test_dispatcher.py
git commit -m "feat: add get_handler helper to CommandDispatcher"
```

---

### Task 3: 建立 SetPrizeHandler 模組

**Files:**
* Create: `src/handlers/set_prize_handler.py`
* Create: `tests/handlers/test_set_prize_handler.py`

- [ ] **Step 1: Write the failing test**

建立新檔案 [tests/handlers/test_set_prize_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/handlers/test_set_prize_handler.py)：

```python
import os
import shutil
import pytest
from unittest.mock import MagicMock, patch
from src.handlers.set_prize_handler import SetPrizeHandler
from src.utils.session_manager import get_prize_session, clear_prize_session

def test_set_prize_handler_can_handle():
    handler = SetPrizeHandler()
    assert handler.can_handle("#設置獎金") is True
    assert handler.can_handle("設置獎金") is False

def test_set_prize_handler_execute_no_league_id():
    handler = SetPrizeHandler()
    event = MagicMock()
    event.source.user_id = "user1"
    config = MagicMock()
    
    with patch("src.handlers.set_prize_handler.load_config", return_value={}), \
         patch.object(handler, "reply_text") as mock_reply:
        handler.execute(event, config)
        mock_reply.assert_called_once_with(event, config, "⚠️ 請先執行 #設置 以綁定聯賽 ID。")

def test_set_prize_handler_execute_success():
    handler = SetPrizeHandler()
    event = MagicMock()
    event.source.user_id = "user1"
    config = MagicMock()
    
    with patch("src.handlers.set_prize_handler.load_config", return_value={"LEAGUE_ID": "nba_123"}), \
         patch.object(handler, "reply_text") as mock_reply:
        handler.execute(event, config)
        mock_reply.assert_called_once_with(event, config, "👉 請在 60 秒內直接傳送新的獎金圖片：")
        assert get_prize_session("user1") is not None
        clear_prize_session("user1")

def test_set_prize_handler_handle_image():
    handler = SetPrizeHandler()
    event = MagicMock()
    event.source.user_id = "user1"
    config = MagicMock()
    
    test_dir = "tests/temp_data/league/nba/123/image"
    os.makedirs(test_dir, exist_ok=True)
    with open(os.path.join(test_dir, "bouns.png"), "w") as f:
        f.write("old")
    with open(os.path.join(test_dir, "bonus.png"), "w") as f:
        f.write("old")
        
    try:
        with patch("src.handlers.set_prize_handler.load_config", return_value={"LEAGUE_ID": "nba_123"}), \
             patch("src.handlers.set_prize_handler.parse_league_id", return_value=("nba", "123")), \
             patch("src.handlers.set_prize_handler.DATA_DIR", "tests/temp_data"), \
             patch.object(handler, "reply_text") as mock_reply:
            
            handler.handle_image(event, config, b"fake_image_bytes")
            
            assert not os.path.exists(os.path.join(test_dir, "bouns.png"))
            assert not os.path.exists(os.path.join(test_dir, "bonus.png"))
            
            new_file_path = os.path.join(test_dir, "bonus.jpg")
            assert os.path.exists(new_file_path)
            with open(new_file_path, "rb") as f:
                assert f.read() == b"fake_image_bytes"
                
            mock_reply.assert_called_once_with(event, config, "✅ 成功設定獎金圖片！")
    finally:
        shutil.rmtree("tests/temp_data", ignore_errors=True)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/handlers/test_set_prize_handler.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'src.handlers.set_prize_handler')

- [ ] **Step 3: Write minimal implementation**

建立新檔案 [src/handlers/set_prize_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_prize_handler.py)：

```python
import os
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.config import load_config
from src.utils.session_manager import set_prize_session, clear_prize_session

class SetPrizeHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        self.exclude_from_llm = True

    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#設置獎金"

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            self.reply_text(event, configuration, "⚠️ 請先執行 #設置 以綁定聯賽 ID。")
            return

        user_id = getattr(event.source, "user_id", None)
        if not user_id:
            return

        set_prize_session(user_id, duration_sec=60)
        self.reply_text(event, configuration, "👉 請在 60 秒內直接傳送新的獎金圖片：")

    def handle_image(self, event: MessageEvent, configuration: Configuration, image_bytes: bytes) -> None:
        user_id = getattr(event.source, "user_id", None)
        if not user_id:
            return

        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            clear_prize_session(user_id)
            self.reply_text(event, configuration, "⚠️ 聯賽 ID 尚未綁定。")
            return

        from src.utils.path_utils import parse_league_id, DATA_DIR
        try:
            sport, raw_id = parse_league_id(league_id)
            image_dir = os.path.join(DATA_DIR, "league", sport, raw_id, "image")
            os.makedirs(image_dir, exist_ok=True)

            # 清除舊的獎金圖檔（避免多個舊副檔名干擾）
            if os.path.exists(image_dir):
                for f in os.listdir(image_dir):
                    base, ext = os.path.splitext(f.lower())
                    if base in ("bouns", "bonus"):
                        try:
                            os.remove(os.path.join(image_dir, f))
                        except Exception as e:
                            logging.warning(f"Failed to remove old prize file {f}: {e}")

            target_path = os.path.join(image_dir, "bonus.jpg")
            with open(target_path, "wb") as f:
                f.write(image_bytes)

            clear_prize_session(user_id)
            self.reply_text(event, configuration, "✅ 成功設定獎金圖片！")
        except Exception as e:
            logging.error(f"[SetPrizeHandler] 儲存獎金圖片失敗: {e}")
            clear_prize_session(user_id)
            self.reply_text(event, configuration, "⚠️ 儲存圖片時發生錯誤，請稍後重試。")

    @property
    def instruction_desc(self) -> str:
        return "#設置獎金 : (限白名單) 調整聯盟的獎金圖片"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/handlers/test_set_prize_handler.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/handlers/set_prize_handler.py tests/handlers/test_set_prize_handler.py
git commit -m "feat: implement SetPrizeHandler and add unit tests"
```

---

### Task 4: 擴充 IntentRouter 以支援文字攔截與圖片路由

**Files:**
* Modify: [src/handlers/intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/intent_router.py)
* Test: [tests/test_intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_intent_router.py)

- [ ] **Step 1: Write the failing test**

在 [tests/test_intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_intent_router.py) 的末尾新增：

```python
def test_intent_router_prize_session_text_interception():
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.utils.session_manager import set_prize_session, get_prize_session
    
    dispatcher = CommandDispatcher()
    router = IntentRouter(dispatcher)
    
    event = MagicMock()
    event.source.user_id = "user_prize_text"
    event.source.type = "user"
    event.message.text = "普通文字訊息"
    config = MagicMock()
    
    set_prize_session("user_prize_text", duration_sec=60)
    
    with patch.object(router, "reply_text") as mock_reply:
        router.route(event, config)
        assert get_prize_session("user_prize_text") is not None
        mock_reply.assert_called_once_with(
            event, config, "⚠️ 設置獎金模式中，請傳送獎金圖片，或輸入 # 取消設定。"
        )
        
    event.message.text = "#"
    with patch.object(router, "reply_text") as mock_reply:
        router.route(event, config)
        assert get_prize_session("user_prize_text") is None
        mock_reply.assert_called_once_with(event, config, "已取消設定。")

def test_intent_router_route_image():
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.utils.session_manager import set_prize_session, clear_prize_session
    from src.handlers.set_prize_handler import SetPrizeHandler
    
    dispatcher = CommandDispatcher()
    mock_handler = MagicMock(spec=SetPrizeHandler)
    dispatcher.register(mock_handler)
    
    router = IntentRouter(dispatcher)
    
    event = MagicMock()
    event.source.user_id = "user_prize_image"
    event.message.id = "image_msg_123"
    config = MagicMock()
    
    set_prize_session("user_prize_image", duration_sec=60)
    
    with patch("src.handlers.intent_router.ApiClient"), \
         patch("src.handlers.intent_router.MessagingApiBlob") as mock_blob_class:
        
        mock_blob = MagicMock()
        mock_blob.get_message_content.return_value = b"image_data"
        mock_blob_class.return_value = mock_blob
        
        router.route_image(event, config)
        
        mock_blob.get_message_content.assert_called_once_with("image_msg_123")
        mock_handler.handle_image.assert_called_once_with(event, config, b"image_data")
        
    clear_prize_session("user_prize_image")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_intent_router.py -k prize -v`
Expected: FAIL (AttributeError: 'IntentRouter' object has no attribute 'route_image')

- [ ] **Step 3: Write minimal implementation**

修改 [src/handlers/intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/intent_router.py)：

1. 在 `route` 方法攔截 `set_prize` 的文字輸入，放置於約第 130 行的 `league_session` 檢查之後：
```python
            # 4. 攔截獎金設定會話的文字輸入
            from src.utils.session_manager import get_prize_session, clear_prize_session
            prize_session = get_prize_session(user_id)
            if prize_session:
                if user_text.startswith("#"):
                    clear_prize_session(user_id)
                    if user_text == "#":
                        self.reply_text(event, configuration, "已取消設定。")
                        return
                    # 如果是其他指令 (例如 #對戰)，清除會話後繼續往下路由
                else:
                    self.reply_text(event, configuration, "⚠️ 設置獎金模式中，請傳送獎金圖片，或輸入 # 取消設定。")
                    return
```

2. 同時，在 `should_process` 方法中（約第 53 行與第 71 行），在 session 判定列表加入 `get_prize_session(user_id)`：
```python
# 修改前：
# if get_nickname_session(user_id) or get_draft_time_session(user_id) or get_league_id_session(user_id):
# 修改後：
            from src.utils.session_manager import get_prize_session
            if get_nickname_session(user_id) or get_draft_time_session(user_id) or get_league_id_session(user_id) or get_prize_session(user_id):
```

3. 新增 `route_image` 方法：
```python
    def route_image(self, event: MessageEvent, configuration: Configuration) -> None:
        """路由圖片訊息事件"""
        user_id = getattr(event.source, "user_id", None)
        if not user_id:
            return

        from src.utils.session_manager import get_prize_session
        if get_prize_session(user_id):
            from src.handlers.set_prize_handler import SetPrizeHandler
            handler = self.dispatcher.get_handler(SetPrizeHandler)
            if handler:
                try:
                    from linebot.v3.messaging import MessagingApiBlob
                    with ApiClient(configuration) as api_client:
                        blob_api = MessagingApiBlob(api_client)
                        image_bytes = blob_api.get_message_content(event.message.id)
                    
                    handler.handle_image(event, configuration, image_bytes)
                except Exception as e:
                    logging.error(f"[IntentRouter] 下載圖片或處理失敗: {e}")
                    self.reply_text(event, configuration, "⚠️ 圖片下載或儲存失敗，請稍後重試。")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_intent_router.py -k prize -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/handlers/intent_router.py tests/test_intent_router.py
git commit -m "feat: support prize session text interception and image routing in IntentRouter"
```

---

### Task 5: 調整 SettingsHandler 與 bot.py 註冊

**Files:**
* Modify: [src/handlers/settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py)
* Modify: [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py)
* Test: [tests/handlers/test_settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/handlers/test_settings_handler.py)

- [ ] **Step 1: Write the failing test**

修改 [tests/handlers/test_settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/handlers/test_settings_handler.py)，在 `test_settings_handler_execute_offseason` 測試的結尾，新增按鈕渲染順序的驗證：

```python
        # 驗證「設置獎金」按鈕存在，且位置在「設置玩家暱稱」之下，分隔線之上
        btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
        assert "設置獎金" in btn_labels
        
        contents = buttons_box["contents"]
        idx_nickname = -1
        idx_prize = -1
        idx_separator = -1
        
        for idx, item in enumerate(contents):
            if item.get("type") == "button":
                label = item["action"].get("label")
                if label == "設置玩家暱稱":
                    idx_nickname = idx
                elif label == "設置獎金":
                    idx_prize = idx
            elif item.get("type") == "separator":
                idx_separator = idx
                
        assert idx_nickname != -1
        assert idx_prize != -1
        assert idx_separator != -1
        assert idx_nickname < idx_prize < idx_separator
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/handlers/test_settings_handler.py -v`
Expected: FAIL (AssertionError: assert '設置獎金' in btn_labels)

- [ ] **Step 3: Write minimal implementation**

1. 修改 [src/handlers/settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py)，在 `execute` 方法中：
```python
# 修改前：
#             buttons = [
#                 (draft_button_label, draft_button_action),
#                 ("設置玩家暱稱", "#設置玩家暱稱"),
#                 (None, None),
#                 ("更換聯盟ID (即將推出)", ""),
#                 ("移除聯盟ID", "#移除聯盟ID")
#             ]
# 修改後：
            buttons = [
                (draft_button_label, draft_button_action),
                ("設置玩家暱稱", "#設置玩家暱稱"),
                ("設置獎金", "#設置獎金"),
                (None, None),
                ("更換聯盟ID (即將推出)", ""),
                ("移除聯盟ID", "#移除聯盟ID")
            ]
```

2. 修改 [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py)：
   - 頂部匯入 `ImageMessageContent` 與 `SetPrizeHandler`：
     ```python
     # 尋找從 linebot.v3.webhooks 匯入 TextMessageContent 的地方，改為：
     from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent
     
     # 匯入 SetPrizeHandler
     from src.handlers.set_prize_handler import SetPrizeHandler
     ```
   - 在 dispatcher 註冊區塊新增 `SetPrizeHandler()`：
     ```python
     # 約第 60 行
     dispatcher.register(SetNicknameHandler())
     dispatcher.register(SetDraftTimeHandler())
     dispatcher.register(SetPrizeHandler()) # 新增此行
     ```
   - 於 `handle_message` 之下新增 `ImageMessageContent` 監聽器：
     ```python
     @handler.add(MessageEvent, message=ImageMessageContent)
     def handle_image_message(event):
         user_id = None
         if hasattr(event, "source") and event.source:
             user_id = getattr(event.source, "user_id", None)
                 
         if not user_id:
             return
             
         token = current_chat_id.set(user_id)
         try:
             if is_token_processed(event.reply_token):
                 return
         
             # 僅在處於設置獎金的狀態時進行圖片事件處理
             from src.utils.session_manager import get_prize_session
             if get_prize_session(user_id):
                 intent_router.route_image(event, configuration)
         finally:
             current_chat_id.reset(token)
     ```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest`
Expected: ALL TESTS PASS

- [ ] **Step 5: Commit**

```bash
git add bot.py src/handlers/settings_handler.py tests/handlers/test_settings_handler.py
git commit -m "feat: register SetPrizeHandler, add Flex button, and enable LINE ImageMessage listening"
```
