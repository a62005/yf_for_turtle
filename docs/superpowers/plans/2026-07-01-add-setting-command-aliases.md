# 2026-07-01 新增設置指令別名實現計劃 (Add Setting Command Aliases Implementation Plan)

本計劃旨在為系統設置選單（原本的 `#設置` 指令）新增別名支援，包含 `#設定`、`#Setting`、`#setting`，並確保在系統尚未綁定聯賽 ID 時這些指令也能被正確處理。

---

## 實作任務明細

### Task 1: 新增與更新測試案例

**Files:**
- Modify: `tests/handlers/test_settings_and_setup.py`
- Modify: `tests/test_intent_router.py`

- [ ] **Step 1: 在 `test_settings_and_setup.py` 中為別名新增測試**

新增測試 `test_settings_handler_aliases`，以 TDD 模式測試各別名是否能成功觸發：

```python
def test_settings_handler_aliases():
    handler = SettingsHandler()
    assert handler.can_handle("#設定") is True
    assert handler.can_handle("#Setting") is True
    assert handler.can_handle("#setting") is True
    assert handler.can_handle("#設置") is True
    assert handler.can_handle("#其他") is False
```

- [ ] **Step 2: 在 `test_intent_router.py` 中測試未綁定時的別名放行**

在 `tests/test_intent_router.py` 中新增 `test_intent_router_should_process_setting_aliases`，模擬當 `LEAGUE_ID` 未綁定時，別名仍被放行：

```python
def test_intent_router_should_process_setting_aliases(mocker):
    # Setup intent router
    from src.handlers.intent_router import IntentRouter
    from src.handlers.dispatcher import CommandDispatcher
    dispatcher = mocker.MagicMock(spec=CommandDispatcher)
    router = IntentRouter(dispatcher)
    
    # Mock configuration to return empty LEAGUE_ID
    mocker.patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": None})
    
    # Test each alias
    for cmd in ["#設定", "#Setting", "#setting", "#設置"]:
        event = mocker.MagicMock()
        event.message.text = cmd
        event.source.user_id = "user_123"
        
        # Should return True since it is in allowed list
        assert router.should_process(event, mocker.MagicMock()) is True
```

- [ ] **Step 3: 執行 pytest 驗證測試失敗**

執行：
`.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py tests/test_intent_router.py -v`
預期：測試 FAIL（因為尚未修改代碼）。

---

### Task 2: 實作別名與放行邏輯

**Files:**
- Modify: `src/handlers/settings_handler.py:13-14`
- Modify: `src/handlers/intent_router.py:57`

- [ ] **Step 1: 修改 SettingsHandler.can_handle**

在 [src/handlers/settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py) 中，將 `can_handle` 擴展為支援新別名：

```python
    def can_handle(self, user_text: str) -> bool:
        cmd = user_text.strip()
        return cmd in ("#設置", "#設定", "#Setting", "#setting")
```

- [ ] **Step 2: 修改 IntentRouter.should_process**

在 [src/handlers/intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/intent_router.py) 中，擴展 `is_allowed_cmd` 放行：

```python
            is_allowed_cmd = (
                user_text in ("#設置", "#設定", "#Setting", "#setting") or 
                user_text == "#我的ID" or 
                user_text.startswith("#設置聯盟ID")
            )
```

- [ ] **Step 3: 執行單元測試驗證通過**

執行：
`.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py tests/test_intent_router.py -v`
預期：PASS。

- [ ] **Step 4: 執行全專案測試**

執行：
`.venv\Scripts\python -m pytest`
確保 260 個測試全部通過。

- [ ] **Step 5: Git commit**

```bash
git add src/handlers/settings_handler.py src/handlers/intent_router.py tests/handlers/test_settings_and_setup.py tests/test_intent_router.py
git commit -m "feat: add setting command aliases #設定, #Setting, #setting"
```
