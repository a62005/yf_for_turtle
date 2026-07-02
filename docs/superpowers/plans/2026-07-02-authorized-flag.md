# 親自授權標記實作計劃 (Authorized Flag Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 透過 `"authorized": true/false` 標記區分親自授權的憑證，避免複製非本人親自授權的憑證。

**Architecture:**
- 在 `SecurityManager` 新增 `set_league_authorized`。
- 在 `oauth_handler.py` 成功取得憑證後調用其設為 `True`。
- 在 `set_league_id_handler.py` 免授權綁定成功後設為 `False`，並在尋找複用憑證時過濾該狀態為 `True` 的聯盟。

**Tech Stack:** Python 3.14, pytest, unittest.mock

---

### Task 1: 擴充與新增單元測試

**Files:**
- Modify: `tests/handlers/test_settings_and_setup.py`

- [ ] **Step 1: 更新 `test_set_league_id_reuses_existing_user_token` 模擬資料**

修改 `test_set_league_id_reuses_existing_user_token`，在 mock roles 及 mock `_load_json` 中加入 `"authorized": true`，以確保原有複用測試依然能通過：

```python
# league_roles 模擬回傳中加入 "authorized": True
'{"nba.l.11111": {"manager": "user_abc", "whitelist": {}, "authorized": true}}'
```

- [ ] **Step 2: 新增測試 `test_set_league_id_does_not_reuse_unauthorized_token`**

新增一個測試，模擬存在聯賽但其 `"authorized": false`（或不存在此欄位），確認此時系統拒絕複用憑證並拋出 `LeaguePermissionError`：

```python
def test_set_league_id_does_not_reuse_unauthorized_token(mocker):
    from src.config import current_chat_id
    from src.fetcher import LeaguePermissionError
    
    handler = SetLeagueIdHandler()
    handler.reply_text = mocker.MagicMock()
    event = mocker.MagicMock()
    event.message.text = "#設置聯盟ID mlb.l.22222"
    event.source.user_id = "user_abc"
    config = mocker.MagicMock()
    
    token = current_chat_id.set("group_1")
    try:
        mock_exists = mocker.patch("os.path.exists", return_value=False)
        mock_copy = mocker.patch("shutil.copy2")
        
        mocker.patch("src.utils.security.security_manager._load_json", return_value={"nba.l.11111": {"manager": "user_abc", "whitelist": {}, "authorized": False}})
        
        # 預期會因為無憑證複製而直接執行 fetcher 卻拋出無權限錯誤
        mocker.patch("src.handlers.set_league_id_handler.YahooFantasyFetcher")
        mocker.patch("src.handlers.set_league_id_handler.sync_season_metadata", side_effect=LeaguePermissionError("Permission Denied"))
        
        with pytest.raises(LeaguePermissionError):
            handler.execute(event, config)
            
        mock_copy.assert_not_called()
    finally:
        current_chat_id.reset(token)
```

- [ ] **Step 3: 執行測試並驗證失敗**

執行測試命令：
`.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py -k test_set_league_id_does_not_reuse_unauthorized_token -v`
預期結果：FAIL（因為當前程式碼尚未過濾 `"authorized": true`，仍會嘗試調用 `shutil.copy2`）。

---

### Task 2: 實作 SecurityManager 擴充

**Files:**
- Modify: `src/utils/security.py`

- [ ] **Step 1: 新增 `set_league_authorized` 方法**

修改 [src/utils/security.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/security.py#L126)，新增以下方法：

```python
    def set_league_authorized(self, league_id: str, authorized: bool) -> bool:
        data = self._load_json(self.league_roles_path, {})
        league_data = data.setdefault(league_id, {"manager": "", "whitelist": {}, "authorized": False})
        league_data["authorized"] = authorized
        return self._save_json(self.league_roles_path, data)
```

---

### Task 3: 修改 Handler 與 OAuth Callback 寫入與過濾標記

**Files:**
- Modify: `src/utils/oauth_handler.py`
- Modify: `src/handlers/set_league_id_handler.py`

- [ ] **Step 1: 修改 `oauth_handler.py` 在授權成功後將標記設為 `True`**

在 [src/utils/oauth_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/oauth_handler.py#L135) 成功同步賽季資訊後，調用 `set_league_authorized(league_id, True)`：

```python
        # 同步賽季資訊
        sync_season_metadata(fetcher, league_id)
        
        # 標記為親自授權
        from src.utils.security import security_manager
        security_manager.set_league_authorized(league_id, True)
```

- [ ] **Step 2: 修改 `set_league_id_handler.py` 的過濾與寫入邏輯**

修改 [src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py#L190)：
1. 在複製憑證過濾中，加入檢查 `ldata.get("authorized") is True`：
   ```python
   if isinstance(ldata, dict) and ldata.get("manager") == user_id and ldata.get("authorized") is True:
   ```
2. 在免授權綁定成功（約第 234 行）後，調用 `security_manager.set_league_authorized(target_id, False)`：
   ```python
           # 同步成功，寫入對應關係
           try:
               self._update_league_id(target_id, user_id)
               security_manager.set_league_authorized(target_id, False)
   ```

- [ ] **Step 3: 執行測試並驗證成功**

執行單元測試：
`.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py -k "test_set_league_id_reuses_existing_user_token or test_set_league_id_does_not_reuse_unauthorized_token" -v`
預期結果：PASS。

---

### Task 4: 驗證與提交

- [ ] **Step 1: 執行完整測試套件**

`.venv\Scripts\python -m pytest`
確保無 regression。

- [ ] **Step 2: Commit 提交變更**

在提交變更前，先以 `git branch --show-current` 驗證當前分支為 `feat/user-token-reuse` 或其他新功能分支，隨後提交變更。
