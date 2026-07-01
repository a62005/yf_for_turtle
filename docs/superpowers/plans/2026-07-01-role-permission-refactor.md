# 聯盟級別角色管理與白名單權限控制實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 重構 LINE Bot 的權限控制，將全域白名單改為聯盟級別的管理員與白名單，實作新增管理員/白名單成員的分步問答對話會話，以及 Flex 列表點擊移除成員之功能。

**Architecture:** 
1. 升級 `SecurityManager`，支援全域管理員名單 (`data/security/managers.json`) 與聯盟級別角色檔案 (`data/security/league_roles.json`)。
2. 擴充 `BaseHandler` 與 `CommandDispatcher`，引入 `requires_manager` 權限層級並實作按聯賽 ID 與使用者 ID 對應的驗證攔截。
3. 重構 `SettingsHandler` 面板，對管理員/成員呈現差異化選單，並在 `intent_router.py` 中處理對話會話引導與點擊移除行為。

**Tech Stack:** Python, Line Bot SDK v3, Pytest

---

### Task 1: 升級 `SecurityManager` 及其單元測試

**Files:**
- Modify: `src/utils/security.py` (實作管理員與聯盟級別角色判定)
- Test: `tests/test_security.py` (撰寫全新的角色判定與異動測試)

- [ ] **Step 1: 撰寫預期失敗的角色與異動判定測試**

在 `tests/test_security.py` 中新增以下測試：
```python
def test_league_role_security_flow(tmp_path):
    admin_file = tmp_path / "super_admin.json"
    managers_file = tmp_path / "managers.json"
    roles_file = tmp_path / "league_roles.json"
    
    with open(admin_file, "w", encoding="utf-8") as f:
        import json
        json.dump({"super_admin": "Uadmin123"}, f)
        
    from src.utils.security import SecurityManager
    sm = SecurityManager(str(admin_file), str(managers_file), str(roles_file))
    
    # 測試全域管理員判定
    assert sm.is_manager("Uadmin123") is True # 超級管理員自動為管理員
    assert sm.is_manager("Umanager456") is False
    
    # 新增管理員並重新測試
    assert sm.add_manager("Umanager456", "小明") is True
    assert sm.is_manager("Umanager456") is True
    
    # 測試聯盟管理員判定
    assert sm.is_league_manager("Uadmin123", "nba.l.123") is True # 超級管理員自動為聯盟管理員
    assert sm.is_league_manager("Umanager456", "nba.l.123") is False
    
    # 設定聯盟經理並測試
    assert sm.set_league_owner("nba.l.123", "Umanager456") is True
    assert sm.is_league_manager("Umanager456", "nba.l.123") is True
    
    # 測試聯盟白名單成員判定
    assert sm.is_league_whitelisted("Uadmin123", "nba.l.123") is True # 超級管理員自動為白名單成員
    assert sm.is_league_whitelisted("Umanager456", "nba.l.123") is True # 聯盟管理員自動為白名單成員
    assert sm.is_league_whitelisted("Uuser789", "nba.l.123") is False
    
    # 新增成員到該聯盟的白名單
    assert sm.add_to_league_whitelist("nba.l.123", "Uuser789", "大雄") is True
    assert sm.is_league_whitelisted("Uuser789", "nba.l.123") is True
    
    # 移除白名單成員
    assert sm.remove_from_league_whitelist("nba.l.123", "Uuser789") is True
    assert sm.is_league_whitelisted("Uuser789", "nba.l.123") is False
```

- [ ] **Step 2: 執行測試並驗證其失敗**

Run: `pytest tests/test_security.py -v`
Expected: FAIL (因為 `SecurityManager` 尚未實作這些方法)

- [ ] **Step 3: 升級 `SecurityManager` 實作**

修改 `src/utils/security.py`，完整實作角色判定與 Key-Value 寫入：
```python
import os
import json
import logging

class SecurityManager:
    def __init__(self, super_admin_path: str = "data/security/super_admin.json",
                 managers_path: str = "data/security/managers.json",
                 league_roles_path: str = "data/security/league_roles.json"):
        self.super_admin_path = super_admin_path
        self.managers_path = managers_path
        self.league_roles_path = league_roles_path

    def _load_json(self, path: str, default: dict) -> dict:
        if not os.path.exists(path):
            os.makedirs(os.path.dirname(path), exist_ok=True)
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(default, f, indent=2, ensure_ascii=False)
            except Exception as e:
                logging.error(f"[SecurityManager] 寫入預設檔案失敗 {path}: {e}")
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"[SecurityManager] 讀取檔案失敗 {path}: {e}")
            return default

    def _save_json(self, path: str, data: dict) -> bool:
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            logging.error(f"[SecurityManager] 儲存檔案失敗 {path}: {e}")
            return False

    def is_super_admin(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        data = self._load_json(self.super_admin_path, {"super_admin": ""})
        return data.get("super_admin") == user_id

    def is_manager(self, user_id: str | None) -> bool:
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        data = self._load_json(self.managers_path, {"managers": {}})
        return user_id in data.get("managers", {})

    def is_league_manager(self, user_id: str | None, league_id: str | None) -> bool:
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        if not league_id:
            return False
        data = self._load_json(self.league_roles_path, {})
        league_data = data.get(league_id) or {}
        return league_data.get("manager") == user_id

    def is_league_whitelisted(self, user_id: str | None, league_id: str | None) -> bool:
        if not user_id:
            return False
        if self.is_super_admin(user_id):
            return True
        if not league_id:
            return False
        if self.is_league_manager(user_id, league_id):
            return True
        data = self._load_json(self.league_roles_path, {})
        league_data = data.get(league_id) or {}
        return user_id in league_data.get("whitelist", {})

    def is_whitelisted(self, user_id: str | None) -> bool:
        # 相容舊版全域白名單判定，預設使用當前正處理之 League ID
        from src.config import load_config
        league_id = load_config().get("LEAGUE_ID")
        return self.is_league_whitelisted(user_id, league_id)

    def add_manager(self, user_id: str, name: str) -> bool:
        data = self._load_json(self.managers_path, {"managers": {}})
        managers = data.setdefault("managers", {})
        managers[user_id] = name
        return self._save_json(self.managers_path, data)

    def set_league_owner(self, league_id: str, manager_id: str) -> bool:
        data = self._load_json(self.league_roles_path, {})
        league_data = data.setdefault(league_id, {"manager": "", "whitelist": {}})
        league_data["manager"] = manager_id
        return self._save_json(self.league_roles_path, data)

    def add_to_league_whitelist(self, league_id: str, user_id: str, name: str) -> bool:
        data = self._load_json(self.league_roles_path, {})
        league_data = data.setdefault(league_id, {"manager": "", "whitelist": {}})
        whitelist = league_data.setdefault("whitelist", {})
        whitelist[user_id] = name
        return self._save_json(self.league_roles_path, data)

    def remove_from_league_whitelist(self, league_id: str, user_id: str) -> bool:
        data = self._load_json(self.league_roles_path, {})
        if league_id in data and "whitelist" in data[league_id]:
            if user_id in data[league_id]["whitelist"]:
                del data[league_id]["whitelist"][user_id]
                return self._save_json(self.league_roles_path, data)
        return True

security_manager = SecurityManager()
```

- [ ] **Step 4: 執行測試並驗證通過**

Run: `pytest tests/test_security.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/utils/security.py tests/test_security.py
git commit -m "feat: upgrade SecurityManager to support managers.json and league_roles.json"
```

---

### Task 2: 重構 `BaseHandler` 與 `CommandDispatcher` 權限攔截

**Files:**
- Modify: `src/handlers/base_handler.py` (新增屬性)
- Modify: `src/handlers/dispatcher.py` (實作聯盟級別權限驗證攔截)
- Test: `tests/test_dispatcher_instruction.py` (或新增 `tests/test_dispatcher_auth.py` 驗證權限攔截邏輯)

- [ ] **Step 1: 撰寫預期失敗的分派器權限測試**

建立 `tests/test_dispatcher_auth.py`：
```python
import pytest
from unittest.mock import MagicMock, patch
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from linebot.v3.messaging import Configuration

def test_dispatcher_auth_interception():
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.base_handler import BaseHandler
    
    class DummyManagerHandler(BaseHandler):
        def __init__(self):
            super().__init__()
            self.requires_manager = True
        def can_handle(self, text): return text == "#測試管理員"
        def execute(self, event, config): event.executed = True
        
    class DummyWhitelistHandler(BaseHandler):
        def __init__(self):
            super().__init__()
            self.requires_whitelist = True
        def can_handle(self, text): return text == "#測試白名單"
        def execute(self, event, config): event.executed = True

    dispatcher = CommandDispatcher()
    h_mgr = DummyManagerHandler()
    h_wl = DummyWhitelistHandler()
    dispatcher.register(h_mgr)
    dispatcher.register(h_wl)

    # 模擬 Event
    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock(spec=TextMessageContent)
    event.message.text = "#測試管理員"
    event.source = MagicMock()
    event.source.user_id = "Uuser999"
    event.executed = False
    
    # 情境 1: 管理員指令，調用者無權限，應該被攔截且不執行
    with patch("src.utils.security.security_manager.is_manager", return_value=False), \
         patch("src.utils.security.security_manager.is_league_manager", return_value=False):
        dispatcher.handle(event, MagicMock(spec=Configuration))
        assert event.executed is False

    # 情境 2: 管理員指令，調用者有全域管理員權限，應該被執行
    event.executed = False
    with patch("src.utils.security.security_manager.is_manager", return_value=True), \
         patch("src.utils.security.security_manager.is_league_manager", return_value=True):
        dispatcher.handle(event, MagicMock(spec=Configuration))
        assert event.executed is True
```

- [ ] **Step 2: 執行測試並驗證其失敗**

Run: `pytest tests/test_dispatcher_auth.py -v`
Expected: FAIL (因為 `BaseHandler` 還沒有 `requires_manager`，且分派器無此驗證)

- [ ] **Step 3: 修改 `BaseHandler` 與 `CommandDispatcher` 實作**

在 `src/handlers/base_handler.py` 新增屬性：
```python
# 約第 15 行
        self.requires_super_admin: bool = False
        self.requires_manager: bool = False  # 新增
        self.requires_whitelist: bool = False
```

在 `src/handlers/dispatcher.py` 修改 `handle` 權限比對區段：
```python
                    # 1. 超級管理員權限檢查
                    if getattr(handler, 'requires_super_admin', False):
                        if not security_manager.is_super_admin(user_id):
                            logging.info(f"[Dispatcher] 使用者 {user_id} 嘗試執行 {handler.__class__.__name__}，因非超級管理員被安靜攔截")
                            return

                    # 2. 聯盟管理員權限檢查
                    if getattr(handler, 'requires_manager', False):
                        from src.config import load_config
                        league_id = load_config().get("LEAGUE_ID")
                        if league_id:
                            if not security_manager.is_league_manager(user_id, league_id):
                                logging.info(f"[Dispatcher] 使用者 {user_id} 嘗試執行 {handler.__class__.__name__}，因非聯盟 {league_id} 管理員被安靜攔截")
                                return
                        else:
                            if not security_manager.is_manager(user_id):
                                logging.info(f"[Dispatcher] 使用者 {user_id} 嘗試執行 {handler.__class__.__name__}，因非全域管理員被安靜攔截")
                                return

                    # 3. 聯盟白名單權限檢查
                    if getattr(handler, 'requires_whitelist', False):
                        from src.config import load_config
                        league_id = load_config().get("LEAGUE_ID")
                        if not security_manager.is_league_whitelisted(user_id, league_id):
                            logging.info(f"[Dispatcher] 使用者 {user_id} 嘗試執行 {handler.__class__.__name__}，因非聯盟 {league_id} 白名單成員被安靜攔截")
                            return
```

- [ ] **Step 4: 執行測試並驗證通過**

Run: `pytest tests/test_dispatcher_auth.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/handlers/base_handler.py src/handlers/dispatcher.py tests/test_dispatcher_auth.py
git commit -m "feat: implement requires_manager validation in CommandDispatcher"
```

---

### Task 3: 實作超級管理員新增管理員對話會話與 `SuperAdminHandler` 重構

**Files:**
- Modify: `src/utils/session_manager.py` (新增管理員設定之 session 狀態 helper)
- Modify: `src/handlers/super_admin_handler.py` (重構為觸發 `#新增管理員` 對話)
- Modify: `src/handlers/intent_router.py` (攔截 `add_manager` 步驟並轉化處理)
- Test: `tests/test_session_manager.py` (測試 session helper 的正確性)

- [ ] **Step 1: 新增 `session_manager` 對話狀態的單元測試**

在 `tests/test_session_manager.py` 中加入：
```python
def test_add_manager_and_whitelist_sessions():
    from src.utils.session_manager import (
        set_session, get_session, clear_session
    )
    # 測試 add_manager 會話步驟
    set_session("U123", "add_manager", {"step": 1})
    assert get_session("U123", "add_manager") == {"step": 1}
    clear_session("U123", "add_manager")
    assert get_session("U123", "add_manager") is None
```

- [ ] **Step 2: 執行測試並驗證通過**

Run: `pytest tests/test_session_manager.py -v`
Expected: PASS

- [ ] **Step 3: 修改 `src/utils/session_manager.py` 加入 helper**

在 `src/utils/session_manager.py` 底部新增：
```python
def set_add_manager_session(user_id: str, step: int, data: dict = None, duration_sec: int = 60) -> None:
    session_data = {"step": step}
    if data:
        session_data.update(data)
    set_session(user_id, "add_manager", session_data, duration_sec)

def get_add_manager_session(user_id: str) -> dict | None:
    return get_session(user_id, "add_manager")

def clear_add_manager_session(user_id: str) -> None:
    clear_session(user_id, "add_manager")

def set_add_whitelist_session(user_id: str, step: int, data: dict = None, duration_sec: int = 60) -> None:
    session_data = {"step": step}
    if data:
        session_data.update(data)
    set_session(user_id, "add_whitelist_member", session_data, duration_sec)

def get_add_whitelist_session(user_id: str) -> dict | None:
    return get_session(user_id, "add_whitelist_member")

def clear_add_whitelist_session(user_id: str) -> None:
    clear_session(user_id, "add_whitelist_member")
```

- [ ] **Step 4: 重構 `src/handlers/super_admin_handler.py`**

將 `#新增白名單` 改為觸發問答的 `#新增管理員`，重寫 `SuperAdminHandler`：
```python
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from src.handlers.base_handler import BaseHandler
from src.utils.session_manager import set_add_manager_session

class SuperAdminHandler(BaseHandler):
    def __init__(self):
        super().__init__()
        self.requires_super_admin = True
        self.exclude_from_llm = True
        
    def can_handle(self, user_text: str) -> bool:
        return user_text.strip() == "#新增管理員"
        
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_id = getattr(event.source, "user_id", None)
        if not user_id:
            self.reply_text(event, configuration, "⚠️ 無法獲取您的 User ID。")
            return
            
        # 開啟兩階段引導會話的第一步
        set_add_manager_session(user_id, step=1, duration_sec=60)
        self.reply_text(event, configuration, "請在 60 秒內輸入欲新增的管理員 LINE ID（例如：U123456...），或輸入 # 取消：")

    @property
    def instruction_desc(self) -> str:
        return "#新增管理員 : (限超級管理員) 指派並新增一名全域管理員"
```

- [ ] **Step 5: 修改 `src/handlers/intent_router.py` 以攔截問答步驟**

在 `src/handlers/intent_router.py` 的 `should_process` 與 `route` 中攔截 `add_manager` 的步驟。
修改 `should_process` 中判定 active session 的部分：
```python
            from src.utils.session_manager import get_add_manager_session, get_add_whitelist_session
            if (get_nickname_session(user_id) or 
                get_draft_time_session(user_id) or 
                get_league_id_session(user_id) or 
                get_prize_session(user_id) or 
                get_season_start_time_session(user_id) or
                get_add_manager_session(user_id) or
                get_add_whitelist_session(user_id)):
                is_active_session = True
```
在 `route` 中加入 `add_manager` 的邏輯處理：
```python
        user_id = getattr(event.source, "user_id", None)
        if user_id:
            # 攔截新增管理員會話
            from src.utils.session_manager import get_add_manager_session, clear_add_manager_session, set_add_manager_session
            from src.utils.security import security_manager
            
            manager_session = get_add_manager_session(user_id)
            if manager_session:
                if user_text.startswith("#") and user_text != "#":
                    clear_add_manager_session(user_id)
                elif user_text == "#":
                    clear_add_manager_session(user_id)
                    self.reply_text(event, configuration, "已取消新增管理員。")
                    return
                else:
                    step = manager_session.get("step")
                    if step == 1:
                        target_id = user_text.strip()
                        if not re.match(r"^U[a-fA-F0-9]{32}$", target_id):
                            self.reply_text(event, configuration, "⚠️ LINE ID 格式錯誤，長度應為 33 碼且以 U 開頭。請重新輸入，或輸入 # 取消：")
                        else:
                            set_add_manager_session(user_id, step=2, data={"target_id": target_id}, duration_sec=60)
                            self.reply_text(event, configuration, "請在 60 秒內輸入該管理員的方便識別名稱（例如：小明），或輸入 # 取消：")
                        return
                    elif step == 2:
                        target_id = manager_session.get("target_id")
                        display_name = user_text.strip()
                        if not display_name:
                            self.reply_text(event, configuration, "⚠️ 名稱不能為空。請重新輸入，或輸入 # 取消：")
                        else:
                            if security_manager.add_manager(target_id, display_name):
                                self.reply_text(event, configuration, f"✅ 成功將管理員 {display_name} ({target_id}) 加入全域管理員名單。")
                            else:
                                self.reply_text(event, configuration, "⚠️ 寫入管理員名單失敗，請檢查系統日誌。")
                            clear_add_manager_session(user_id)
                        return
```

- [ ] **Step 6: 提交變更**

```bash
git add src/utils/session_manager.py src/handlers/super_admin_handler.py src/handlers/intent_router.py
git commit -m "feat: implement step-by-step add_manager wizard flow"
```

---

### Task 4: 修改 `SetLeagueIdHandler` 管理員保護限制

**Files:**
- Modify: `src/handlers/set_league_id_handler.py` (設定綁定時之管理員檢查與設定對應)

- [ ] **Step 1: 重寫 `SetLeagueIdHandler` 綁定驗證與所有權寫入邏輯**

修改 `src/handlers/set_league_id_handler.py`，將 `self.requires_whitelist` 調整為 `self.requires_manager`，並加入聯盟 ID 的管理員所有權判定：
```python
# 約第 16 行
        self.requires_manager = True  # 原為 requires_whitelist
```

在 `execute` 寫入設定檔前（約第 198 行起），確認此 `target_id` (聯盟 ID) 是否已被其他人管理：
```python
        # 同步成功，寫入對應關係
        from src.utils.security import security_manager
        
        # 1. 檢查這個聯盟是否已經被其他人註冊
        data = security_manager._load_json(security_manager.league_roles_path, {})
        existing_owner = data.get(target_id, {}).get("manager")
        if existing_owner and existing_owner != user_id and not security_manager.is_super_admin(user_id):
            self.reply_text(event, configuration, f"⚠️ 設置失敗，該聯盟 ID ({target_id}) 已由其他管理員管理。")
            return
            
        try:
            self._update_league_id(target_id)
            
            # 設定這個管理員為聯盟負責人
            security_manager.set_league_owner(target_id, user_id)
```

並更新說明文字描述：
```python
    @property
    def instruction_desc(self) -> str:
        return "#設置聯盟ID <ID> : (限管理員) 設置並同步指定之 Yahoo 聯盟 ID"
```

- [ ] **Step 2: 提交變更**

```bash
git add src/handlers/set_league_id_handler.py
git commit -m "feat: restrict #設置聯盟ID to managers and enforce league ID ownership"
```

---

### Task 5: 升級 `SettingsHandler` 差異化選單呈現

**Files:**
- Modify: `src/handlers/settings_handler.py` (區分管理員與白名單之按鈕)

- [ ] **Step 1: 修改 `#設置` 面板渲染邏輯**

修改 `src/handlers/settings_handler.py` 的 `execute` 方法，取得當前使用者 ID 與對應的聯盟權限：
```python
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        user_id = getattr(event.source, "user_id", None)
        
        from src.utils.security import security_manager
        is_manager = security_manager.is_league_manager(user_id, league_id) if league_id else security_manager.is_manager(user_id)
        
        if not league_id:
            title = "系統初始化設置"
            subtitle = None
            if is_manager:
                buttons = [("設置聯盟 ID", "#設置聯盟ID ")]
            else:
                buttons = [] # 非管理員沒有任何按鈕
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
                ("設置獎金", "#設置獎金")
            ])
            
            # 只有管理員看得見「新增/移除白名單成員」與「解綁」
            if is_manager:
                buttons.extend([
                    (None, None), # 分隔線
                    ("新增白名單成員", "#新增白名單成員"),
                    ("移除白名單成員", "#移除白名單成員"),
                    (None, None), # 分隔線
                    ("移除聯盟ID", "#移除聯盟ID")
                ])
            
        flex_dict = build_button_menu_card(title, subtitle, buttons)
        self.reply_flex(event, configuration, "設置選單", flex_dict)
```

- [ ] **Step 2: 提交變更**

```bash
git add src/handlers/settings_handler.py
git commit -m "feat: render dynamic settings menu based on user roles"
```

---

### Task 6: 實作新增白名單成員對話與 Flex 移除白名單成員

**Files:**
- Modify: `src/handlers/intent_router.py` (攔截新增/移除白名單對話與確切移除指令)

- [ ] **Step 1: 在 `intent_router.py` 實作 `#新增白名單成員` 會話與 `#移除白名單成員` Flex 清單**

修改 `src/handlers/intent_router.py`：
1. 攔截 `#新增白名單成員` 主指令，並開啟 `add_whitelist_member` 兩階段對話。
2. 攔截 `add_whitelist_member` 分步輸入。
3. 攔截 `#移除白名單成員` 指令，渲染所有成員的 Flex 點擊按鈕列表。
4. 攔截 `#確切移除白名單 <LINE_ID>` 執行實際刪除。

在 `route` 方法頂端（約第 117 行起），新增攔截點：
```python
        user_id = getattr(event.source, "user_id", None)
        if user_id:
            from src.utils.security import security_manager
            config = load_config()
            league_id = config.get("LEAGUE_ID")
            
            # 0. 攔截主觸發指令
            if user_text == "#新增白名單成員":
                if not security_manager.is_league_manager(user_id, league_id):
                    return # 權限不足，直接無視
                from src.utils.session_manager import set_add_whitelist_session
                set_add_whitelist_session(user_id, step=1, duration_sec=60)
                self.reply_text(event, configuration, "請在 60 秒內輸入欲新增的白名單成員 LINE ID（例如：U123456...），或輸入 # 取消：")
                return

            if user_text == "#移除白名單成員":
                if not security_manager.is_league_manager(user_id, league_id):
                    return
                # 取得目前白名單列表並生成 Flex
                roles = security_manager._load_json(security_manager.league_roles_path, {})
                whitelist = roles.get(league_id, {}).get("whitelist", {})
                
                if not whitelist:
                    self.reply_text(event, configuration, "ℹ️ 目前此聯盟無任何白名單成員。")
                    return
                    
                # 建立按鈕選單 (最多列出 10 個，方便操作)
                buttons = []
                for wl_id, wl_name in whitelist.items():
                    buttons.append((f"移除 {wl_name} ({wl_id[:8]}...)", f"#確切移除白名單 {wl_id}"))
                
                from src.visualizer.flex_builder import build_button_menu_card
                flex_dict = build_button_menu_card("移除白名單成員", "請選擇要移除的成員", buttons)
                
                with ApiClient(configuration) as api_client:
                    from linebot.v3.messaging import MessagingApi, ReplyMessageRequest, FlexMessage, FlexContainer
                    MessagingApi(api_client).reply_message(
                        ReplyMessageRequest(
                            reply_token=event.reply_token,
                            messages=[FlexMessage(alt_text="移除成員清單", contents=FlexContainer.from_dict(flex_dict))]
                        )
                    )
                return

            if user_text.startswith("#確切移除白名單"):
                if not security_manager.is_league_manager(user_id, league_id):
                    return
                parts = user_text.split()
                if len(parts) < 2:
                    self.reply_text(event, configuration, "⚠️ 指令格式錯誤。")
                    return
                target_id = parts[1].strip()
                # 讀取原本的名稱
                roles = security_manager._load_json(security_manager.league_roles_path, {})
                wl_name = roles.get(league_id, {}).get("whitelist", {}).get(target_id, "未知成員")
                
                if security_manager.remove_from_league_whitelist(league_id, target_id):
                    self.reply_text(event, configuration, f"✅ 成功將成員 {wl_name} ({target_id}) 移出白名單。")
                else:
                    self.reply_text(event, configuration, "⚠️ 移除失敗。")
                return

            # 攔截新增白名單會話
            from src.utils.session_manager import get_add_whitelist_session, clear_add_whitelist_session, set_add_whitelist_session
            wl_session = get_add_whitelist_session(user_id)
            if wl_session:
                if user_text.startswith("#") and user_text != "#":
                    clear_add_whitelist_session(user_id)
                elif user_text == "#":
                    clear_add_whitelist_session(user_id)
                    self.reply_text(event, configuration, "已取消新增成員。")
                    return
                else:
                    step = wl_session.get("step")
                    if step == 1:
                        target_id = user_text.strip()
                        if not re.match(r"^U[a-fA-F0-9]{32}$", target_id):
                            self.reply_text(event, configuration, "⚠️ LINE ID 格式錯誤，長度應為 33 碼且以 U 開頭。請重新輸入，或輸入 # 取消：")
                        else:
                            set_add_whitelist_session(user_id, step=2, data={"target_id": target_id}, duration_sec=60)
                            self.reply_text(event, configuration, "請在 60 秒內輸入該成員的方便識別名稱（例如：大雄），或輸入 # 取消：")
                        return
                    elif step == 2:
                        target_id = wl_session.get("target_id")
                        display_name = user_text.strip()
                        if not display_name:
                            self.reply_text(event, configuration, "⚠️ 名稱不能為空。請重新輸入，或輸入 # 取消：")
                        else:
                            if security_manager.add_to_league_whitelist(league_id, target_id, display_name):
                                self.reply_text(event, configuration, f"✅ 成功將成員 {display_name} ({target_id}) 加入此聯盟的白名單成員。")
                            else:
                                self.reply_text(event, configuration, "⚠️ 寫入白名單成員失敗，請檢查系統日誌。")
                            clear_add_whitelist_session(user_id)
                        return
```

- [ ] **Step 2: 提交變更**

```bash
git add src/handlers/intent_router.py
git commit -m "feat: implement whitelist member addition dialog and Flex click-to-delete flows"
```

---

### Task 7: 系統整合與完整測試驗證

- [ ] **Step 1: 執行所有的 pytest 單元測試以確保沒有 regression**

Run: `pytest`
Expected: ALL PASS

- [ ] **Step 2: 提交變更**

```bash
git status
```
*(確認無任何未追蹤或未提交的程式異動)*
