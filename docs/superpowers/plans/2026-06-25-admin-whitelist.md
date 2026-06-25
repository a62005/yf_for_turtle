# 超級管理員與白名單權限控制實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 Yahoo Fantasy NBA LINE 機器人新增一個超級管理員與白名單的權限控管系統，並實作 `#我的ID`、`#新增白名單 <ID>` 以及 `#設置` 指令。

**Architecture:** 
1. 實作 `SecurityManager` 類別讀寫 `data/security/` 目錄下的 JSON 檔案。
2. 擴充 `BaseHandler` 新增權限標記，並在 `CommandDispatcher` 攔截無權限之操作並安靜阻擋。
3. 建立並註冊 `IdHandler`、`SuperAdminHandler` 與 `SettingsHandler` 處理專屬管理指令。

**Tech Stack:** Python 3, pytest, unittest.mock, linebot-sdk-v3

---

### Task 1: 實作 SecurityManager 模組

**Files:**
- Create: `src/utils/security.py`
- Create: `tests/test_security.py`

- [ ] **Step 1: 撰寫 SecurityManager 的單元測試**

在 `tests/test_security.py` 中寫入以下測試：
```python
import os
import json
import pytest
from src.utils.security import SecurityManager

def test_security_manager_basic_flow(tmp_path):
    admin_file = tmp_path / "super_admin.json"
    whitelist_file = tmp_path / "whitelist.json"
    
    # 寫入初始測試資料
    with open(admin_file, "w", encoding="utf-8") as f:
        json.dump({"super_admin": "Uadmin123"}, f)
    with open(whitelist_file, "w", encoding="utf-8") as f:
        json.dump({"whitelist": ["Uuser456"]}, f)
        
    sm = SecurityManager(str(admin_file), str(whitelist_file))
    
    # 測試超級管理員判定
    assert sm.is_super_admin("Uadmin123") is True
    assert sm.is_super_admin("Uuser456") is False
    assert sm.is_super_admin(None) is False
    
    # 測試白名單判定（超級管理員自動視為在白名單中）
    assert sm.is_whitelisted("Uadmin123") is True
    assert sm.is_whitelisted("Uuser456") is True
    assert sm.is_whitelisted("Uother789") is False
    assert sm.is_whitelisted(None) is False
    
    # 測試新增白名單
    assert sm.add_to_whitelist("Uother789") is True
    assert sm.is_whitelisted("Uother789") is True
    
    # 再次確認檔案被成功更新
    with open(whitelist_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "Uother789" in data["whitelist"]
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/test_security.py -v`
Expected: FAIL (ModuleNotFoundError 或 ImportError)

- [ ] **Step 3: 撰寫 SecurityManager 實作**

在 `src/utils/security.py` 中寫入以下程式碼：
```python
import os
import json
import logging

class SecurityManager:
    def __init__(self, super_admin_path: str = "data/security/super_admin.json", whitelist_path: str = "data/security/whitelist.json"):
        self.super_admin_path = super_admin_path
        self.whitelist_path = whitelist_path

    def _load_json(self, path: str, default: dict) -> dict:
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default, f, indent=2)
            except Exception as e:
                logging.error(f"[SecurityManager] 寫入預設檔案失敗 {path}: {e}")
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[SecurityManager] 讀取檔案失敗 {path}: {e}")
            return default

    def is_super_admin(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        data = self._load_json(self.super_admin_path, {"super_admin": ""})
        return data.get("super_admin") == user_id

    def is_whitelisted(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        data = self._load_json(self.whitelist_path, {"whitelist": []})
        return user_id in data.get("whitelist", [])

    def add_to_whitelist(self, user_id: str) -> bool:
        data = self._load_json(self.whitelist_path, {"whitelist": []})
        whitelist = data.get("whitelist", [])
        if user_id not in whitelist:
            whitelist.append(user_id)
            data["whitelist"] = whitelist
            try:
                os.makedirs(os.path.dirname(self.whitelist_path), exist_ok=True)
                with open(self.whitelist_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                return True
            except Exception as e:
                logging.error(f"[SecurityManager] 寫入白名單失敗 {self.whitelist_path}: {e}")
                return False
        return True

# 導出全域單一實例供各模組使用
security_manager = SecurityManager()
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_security.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/utils/security.py tests/test_security.py
git commit -m "feat: implement SecurityManager and security json storage logic"
```

---

### Task 2: 擴充 BaseHandler 以支援權限屬性

**Files:**
- Modify: `src/handlers/base_handler.py:10-25`
- Create: `tests/handlers/test_base_handler_security.py`

- [ ] **Step 1: 撰寫 BaseHandler 權限屬性的單元測試**

在 `tests/handlers/test_base_handler_security.py` 中寫入以下測試：
```python
from src.handlers.base_handler import BaseHandler

def test_base_handler_security_defaults():
    class DummyHandler(BaseHandler):
        def can_handle(self, text):
            return True
        def execute(self, event, config):
            pass
            
    handler = DummyHandler()
    assert hasattr(handler, "requires_super_admin")
    assert hasattr(handler, "requires_whitelist")
    assert handler.requires_super_admin is False
    assert handler.requires_whitelist is False
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/handlers/test_base_handler_security.py -v`
Expected: FAIL (AssertionError: hasattr 或是 False 失敗)

- [ ] **Step 3: 修改 BaseHandler 引入權限屬性**

在 `src/handlers/base_handler.py` 的 `BaseHandler` 類別中修改建構子 `__init__`：
```python
class BaseHandler(ABC):
    """Base interface for all bot message handlers."""
    
    def __init__(self):
        self.requires_super_admin: bool = False
        self.requires_whitelist: bool = False
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/handlers/test_base_handler_security.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/handlers/base_handler.py tests/handlers/test_base_handler_security.py
git commit -m "refactor: add permission attributes to BaseHandler interface"
```

---

### Task 3: 擴充 CommandDispatcher 權限攔截邏輯

**Files:**
- Modify: `src/handlers/dispatcher.py:1-25`
- Create: `tests/handlers/test_dispatcher_security.py`

- [ ] **Step 1: 撰寫 CommandDispatcher 權限驗證攔截的單元測試**

在 `tests/handlers/test_dispatcher_security.py` 中寫入以下測試：
```python
import pytest
from unittest.mock import MagicMock, patch
from src.handlers.dispatcher import CommandDispatcher
from src.handlers.base_handler import BaseHandler

def test_dispatcher_permission_interception():
    # 建立一個需要超級管理員權限的 Mock Handler
    class AdminOnlyHandler(BaseHandler):
        def __init__(self):
            super().__init__()
            self.requires_super_admin = True
            self.executed = False
        def can_handle(self, text):
            return text == "#admin_cmd"
        def execute(self, event, config):
            self.executed = True

    # 建立一個需要白名單權限的 Mock Handler
    class WhitelistOnlyHandler(BaseHandler):
        def __init__(self):
            super().__init__()
            self.requires_whitelist = True
            self.executed = False
        def can_handle(self, text):
            return text == "#whitelist_cmd"
        def execute(self, event, config):
            self.executed = True

    dispatcher = CommandDispatcher()
    admin_handler = AdminOnlyHandler()
    whitelist_handler = WhitelistOnlyHandler()
    dispatcher.register(admin_handler)
    dispatcher.register(whitelist_handler)

    mock_event = MagicMock()
    mock_event.source.user_id = "UordinaryUser"
    mock_config = MagicMock()

    # 使用 mock security_manager 進行驗證
    with patch("src.handlers.dispatcher.security_manager") as mock_sm:
        # 情況 A: 發送者非 admin 也非 whitelist
        mock_sm.is_super_admin.return_value = False
        mock_sm.is_whitelisted.return_value = False

        # 嘗試執行 admin 指令
        mock_event.message.text = "#admin_cmd"
        dispatcher.handle(mock_event, mock_config)
        assert not admin_handler.executed # 應該被安靜攔截，不執行

        # 嘗試執行 whitelist 指令
        mock_event.message.text = "#whitelist_cmd"
        dispatcher.handle(mock_event, mock_config)
        assert not whitelist_handler.executed # 應該被安靜攔截，不執行

        # 情況 B: 發送者是超級管理員
        mock_sm.is_super_admin.return_value = True
        mock_sm.is_whitelisted.return_value = True # admin 自然是 whitelisted

        # 執行 admin 指令
        mock_event.message.text = "#admin_cmd"
        dispatcher.handle(mock_event, mock_config)
        assert admin_handler.executed # 應該成功執行

        # 執行 whitelist 指令
        mock_event.message.text = "#whitelist_cmd"
        dispatcher.handle(mock_event, mock_config)
        assert whitelist_handler.executed # 應該成功執行
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/handlers/test_dispatcher_security.py -v`
Expected: FAIL (AssertionError: admin_handler.executed 應該為 False 卻為 True)

- [ ] **Step 3: 修改 CommandDispatcher 導入權限檢查**

修改 `src/handlers/dispatcher.py` 內容：
```python
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from typing import List
from .base_handler import BaseHandler
from src.utils.security import security_manager

class CommandDispatcher:
    def __init__(self):
        self._handlers: List[BaseHandler] = []
        
    def register(self, handler: BaseHandler) -> None:
        """Register a handler to the dispatcher."""
        self._handlers.append(handler)
        
    def handle(self, event: MessageEvent, configuration: Configuration) -> None:
        """Route the event to the appropriate handler with permission checks."""
        user_text = event.message.text.strip()
        user_id = event.source.user_id if event.source and hasattr(event.source, 'user_id') else None
        
        for handler in self._handlers:
            try:
                if handler.can_handle(user_text):
                    # 1. 超級管理員權限檢查
                    if handler.requires_super_admin:
                        if not security_manager.is_super_admin(user_id):
                            logging.info(f"[Dispatcher] 使用者 {user_id} 嘗試執行 {handler.__class__.__name__}，因非超級管理員被安靜攔截")
                            return  # 安靜攔截，不作任何回覆
                    
                    # 2. 白名單權限檢查
                    if handler.requires_whitelist:
                        if not security_manager.is_whitelisted(user_id):
                            logging.info(f"[Dispatcher] 使用者 {user_id} 嘗試執行 {handler.__class__.__name__}，因非白名單被安靜攔截")
                            return  # 安靜攔截，不作任何回覆

                    handler.execute(event, configuration)
                    return # Stop routing once a handler takes it
            except Exception as e:
                logging.error(f"[Dispatcher] Handler {handler.__class__.__name__} failed: {e}")
                
        logging.info(f"[Dispatcher] No handler found for command: {user_text}")

    def get_all_instruction_descs(self) -> str:
        """Collect and concatenate instruction descriptions from all registered handlers."""
        descs = []
        for handler in self._handlers:
            desc = handler.instruction_desc
            if desc:
                descs.append(desc.strip())
        return "\n".join(descs)
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/handlers/test_dispatcher_security.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/handlers/dispatcher.py tests/handlers/test_dispatcher_security.py
git commit -m "feat: implement permission interception in CommandDispatcher"
```

---

### Task 4: 實作並註冊 IdHandler (#我的ID)

**Files:**
- Create: `src/handlers/id_handler.py`
- Create: `tests/handlers/test_id_handler.py`
- Modify: `bot.py` (註冊此 Handler)

- [ ] **Step 1: 撰寫 IdHandler 的單元測試**

在 `tests/handlers/test_id_handler.py` 中寫入以下測試：
```python
from unittest.mock import MagicMock
from src.handlers.id_handler import IdHandler

def test_id_handler_can_handle():
    handler = IdHandler()
    assert handler.can_handle("#我的ID") is True
    assert handler.can_handle("我的ID") is False
    assert handler.can_handle("#我的ID extra") is False

def test_id_handler_execute():
    handler = IdHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.source.user_id = "Utest123456"
    config = MagicMock()
    
    handler.execute(event, config)
    handler.reply_text.assert_called_once_with(event, config, "您的 LINE ID 為: Utest123456")
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/handlers/test_id_handler.py -v`
Expected: FAIL (ImportError 或 ModuleNotFoundError)

- [ ] **Step 3: 實作 IdHandler 類別**

在 `src/handlers/id_handler.py` 中寫入以下程式碼：
```python
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler

class IdHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#我的ID"
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_id = event.source.user_id if event.source and hasattr(event.source, 'user_id') else "Unknown"
        self.reply_text(event, configuration, f"您的 LINE ID 為: {user_id}")

    @property
    def instruction_desc(self) -> str:
        return "#我的ID : 查詢您目前的 LINE User ID"
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/handlers/test_id_handler.py -v`
Expected: PASS

- [ ] **Step 5: 註冊到 bot.py**

修改 `bot.py`，導入並註冊 `IdHandler`。
在 `bot.py` 的進口區加入：
```python
from src.handlers.id_handler import IdHandler
```
並在 `dispatcher` 註冊區域加入註冊：
```python
dispatcher.register(IdHandler())
```

- [ ] **Step 6: 提交變更**

```bash
git add src/handlers/id_handler.py tests/handlers/test_id_handler.py bot.py
git commit -m "feat: add and register IdHandler for #我的ID command"
```

---

### Task 5: 實作並註冊 SuperAdminHandler (#新增白名單 <ID>)

**Files:**
- Create: `src/handlers/super_admin_handler.py`
- Create: `tests/handlers/test_super_admin_handler.py`
- Modify: `bot.py` (註冊此 Handler)

- [ ] **Step 1: 撰寫 SuperAdminHandler 的單元測試**

在 `tests/handlers/test_super_admin_handler.py` 中寫入以下測試：
```python
import pytest
from unittest.mock import MagicMock, patch
from src.handlers.super_admin_handler import SuperAdminHandler

def test_super_admin_handler_can_handle():
    handler = SuperAdminHandler()
    assert handler.can_handle("#新增白名單 U1234567890abcdef1234567890abcdef") is True
    assert handler.can_handle("#新增白名單") is True # 在 execute 處理格式錯誤
    assert handler.can_handle("新增白名單") is False

def test_super_admin_handler_execute_success():
    handler = SuperAdminHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#新增白名單 U1234567890abcdef1234567890abcdef"
    config = MagicMock()

    with patch("src.handlers.super_admin_handler.security_manager") as mock_sm:
        mock_sm.add_to_whitelist.return_value = True
        handler.execute(event, config)
        
        mock_sm.add_to_whitelist.assert_called_once_with("U1234567890abcdef1234567890abcdef")
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "成功將 ID 加入白名單：U1234567890abcdef1234567890abcdef"
        )

def test_super_admin_handler_execute_invalid_format():
    handler = SuperAdminHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#新增白名單 invalid_format_id"
    config = MagicMock()

    handler.execute(event, config)
    handler.reply_text.assert_called_once_with(
        event, 
        config, 
        "格式錯誤，請使用：#新增白名單 <LINE_ID>"
    )
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/handlers/test_super_admin_handler.py -v`
Expected: FAIL (ImportError 或 ModuleNotFoundError)

- [ ] **Step 3: 實作 SuperAdminHandler 類別**

在 `src/handlers/super_admin_handler.py` 中寫入以下程式碼：
```python
import re
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.utils.security import security_manager

class SuperAdminHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_super_admin = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip().startswith("#新增白名單")
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = re.match(r"^#新增白名單\s+(U[a-fA-F0-9]{32})$", user_text)
        if not match:
            self.reply_text(event, configuration, "格式錯誤，請使用：#新增白名單 <LINE_ID>")
            return
            
        target_id = match.group(1)
        if security_manager.add_to_whitelist(target_id):
            self.reply_text(event, configuration, f"成功將 ID 加入白名單：{target_id}")
        else:
            self.reply_text(event, configuration, f"將 ID 加入白名單失敗：{target_id}")

    @property
    def instruction_desc(self) -> str:
        return "#新增白名單 <LINE_ID> : (限超級管理員) 將指定 LINE ID 加入系統白名單"
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/handlers/test_super_admin_handler.py -v`
Expected: PASS

- [ ] **Step 5: 註冊到 bot.py**

修改 `bot.py`，導入並註冊 `SuperAdminHandler`。
在 `bot.py` 的進口區加入：
```python
from src.handlers.super_admin_handler import SuperAdminHandler
```
並在 `dispatcher` 註冊區域加入註冊：
```python
dispatcher.register(SuperAdminHandler())
```

- [ ] **Step 6: 提交變更**

```bash
git add src/handlers/super_admin_handler.py tests/handlers/test_super_admin_handler.py bot.py
git commit -m "feat: add and register SuperAdminHandler for whitelisting"
```

---

### Task 6: 實作並註冊 SettingsHandler (#設置)

**Files:**
- Create: `src/handlers/settings_handler.py`
- Create: `tests/handlers/test_settings_handler.py`
- Modify: `bot.py` (註冊此 Handler)

- [ ] **Step 1: 撰寫 SettingsHandler 的單元測試**

在 `tests/handlers/test_settings_handler.py` 中寫入以下測試：
```python
from unittest.mock import MagicMock
from src.handlers.settings_handler import SettingsHandler

def test_settings_handler_can_handle():
    handler = SettingsHandler()
    assert handler.can_handle("#設置") is True
    assert handler.can_handle("設置") is False

def test_settings_handler_execute():
    handler = SettingsHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    config = MagicMock()

    handler.execute(event, config)
    handler.reply_text.assert_called_once()
    
    # 確保回覆內容含有設置字樣
    args, kwargs = handler.reply_text.call_args
    assert "系統設置清單" in args[2]
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/handlers/test_settings_handler.py -v`
Expected: FAIL (ImportError 或 ModuleNotFoundError)

- [ ] **Step 3: 實作 SettingsHandler 類別**

在 `src/handlers/settings_handler.py` 中寫入以下程式碼：
```python
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler

class SettingsHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_whitelist = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#設置"
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        settings_text = (
            "⚙️ 系統設置清單 ⚙️\n\n"
            "目前可用的設定項目與系統資訊：\n"
            "1. 數據更新狀態：已啟用自動快取\n"
            "2. 當前聯盟 ID (LEAGUE_ID)：請參閱環境設定\n"
            "3. LLM 助理狀態：已連線 (Gemini 3.5 Flash)\n\n"
            "※ 本指令僅供白名單成員存取。"
        )
        self.reply_text(event, configuration, settings_text)

    @property
    def instruction_desc(self) -> str:
        return "#設置 : (限白名單) 顯示系統設置清單"
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/handlers/test_settings_handler.py -v`
Expected: PASS

- [ ] **Step 5: 註冊到 bot.py**

修改 `bot.py`，導入並註冊 `SettingsHandler`。
在 `bot.py` 的進口區加入：
```python
from src.handlers.settings_handler import SettingsHandler
```
並在 `dispatcher` 註冊區域加入註冊：
```python
dispatcher.register(SettingsHandler())
```

- [ ] **Step 6: 提交變更**

```bash
git add src/handlers/settings_handler.py tests/handlers/test_settings_handler.py bot.py
git commit -m "feat: add and register SettingsHandler for whitelist members"
```

---

### Task 7: 執行整體測試整合確認

**Files:**
- Test: 所有的測試

- [ ] **Step 1: 執行所有的 pytest 單元測試以確保沒有破壞現有功能**

Run: `pytest`
Expected: 所有測試皆通過 (0 failures)
