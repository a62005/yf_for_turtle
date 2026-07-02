# 已授權用戶綁定新聯盟免授權實作計劃 (User Token Reuse Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 當用戶擁有 A、B 兩個聯盟，當綁定 A 聯盟成功後，在別的群組綁定 B 聯盟時，能直接複用 A 聯盟的憑證而免去重複進行網頁授權。

**Architecture:** 在 `SetLeagueIdHandler` 中建立 `YahooFantasyFetcher` 前，讀取 `league_roles.json` 尋找當前 `user_id` 作為 manager 的其他已授權聯盟。若有，則將該聯盟目錄下的 `oauth2.json` 與 `.yahoofantasy` 憑證複製到新聯盟目錄，再進行 fetcher 初始化與同步驗證。

**Tech Stack:** Python 3.14, pytest, unittest.mock

---

### Task 1: 新增單元測試驗證憑證複用

**Files:**
- Modify: `tests/handlers/test_settings_and_setup.py`

- [ ] **Step 1: 新增測試 `test_set_league_id_reuses_existing_user_token`**

在 `tests/handlers/test_settings_and_setup.py` 中新增一個單元測試，模擬用戶擁有 `nba.l.11111` 且有憑證，當該用戶嘗試綁定 `mlb.l.22222` 時，自動複製憑證：

```python
def test_set_league_id_reuses_existing_user_token(mocker):
    from src.config import current_chat_id
    import json
    
    handler = SetLeagueIdHandler()
    handler.reply_text = mocker.MagicMock()
    event = mocker.MagicMock()
    event.message.text = "#設置聯盟ID mlb 22222"
    event.source.user_id = "user_abc"
    config = mocker.MagicMock()
    
    # 模擬讀取 league_roles.json 與 chat_league_mapping.json 的讀寫
    written_mapping = {}
    def mock_open_io(path, mode="r", *args, **kwargs):
        import io
        class MockFile(io.StringIO):
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                nonlocal written_mapping
                val = self.getvalue()
                if val and "chat_league_mapping.json" in str(path): 
                    written_mapping = json.loads(val)
        
        path_str = str(path).replace("\\", "/")
        if "chat_league_mapping.json" in path_str:
            if "r" in mode:
                return MockFile('{}')
            return MockFile()
        elif "league_roles.json" in path_str:
            return MockFile('{"nba.l.11111": {"manager": "user_abc", "whitelist": {}}}')
        return open(path, mode, *args, **kwargs)

    token = current_chat_id.set("group_1")
    try:
        mock_exists = mocker.patch("os.path.exists", side_effect=lambda p: "nba.l.11111" in str(p) or "league_roles.json" in str(p))
        mock_makedirs = mocker.patch("os.makedirs")
        mock_copy = mocker.patch("shutil.copy2")
        mocker.patch("src.handlers.set_league_id_handler.open", side_effect=mock_open_io)
        
        # Mock fetcher 與 sync_season_metadata 使其判定同步成功
        mocker.patch("src.handlers.set_league_id_handler.YahooFantasyFetcher")
        mocker.patch("src.handlers.set_league_id_handler.sync_season_metadata")
        
        handler.execute(event, config)
        
        # 驗證憑證是否有被從 nba.l.11111 拷貝到 mlb.l.22222
        mock_copy.assert_any_call(
            mocker.ANY,  # nba.l.11111/oauth2.json
            mocker.ANY   # mlb.l.22222/oauth2.json
        )
        mock_copy.assert_any_call(
            mocker.ANY,  # nba.l.11111/.yahoofantasy
            mocker.ANY   # mlb.l.22222/.yahoofantasy
        )
        handler.reply_text.assert_called_once_with(event, config, "✅ 成功將此聊天室綁定至聯賽 ID：mlb.l.22222")
    finally:
        current_chat_id.reset(token)
```

- [ ] **Step 2: 執行測試並驗證失敗**

執行以下命令：
`.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py -k test_set_league_id_reuses_existing_user_token -v`
預期結果：FAIL (因為尚未實作複製邏輯，`mock_copy` 的 `assert_any_call` 會失敗)。

---

### Task 2: 實作憑證複用邏輯

**Files:**
- Modify: `src/handlers/set_league_id_handler.py`

- [ ] **Step 1: 修改 `SetLeagueIdHandler.execute` 加入複用憑證邏輯**

在建立 `YahooFantasyFetcher` 之前（約第 185 行），加入利用 `user_id` 尋找其他聯盟並複製憑證的邏輯：

```python
        # 憑證智慧複用：如果新聯盟目錄下尚未有憑證，則嘗試尋找此用戶已授權的其他聯盟憑證
        target_dir = get_league_dir(target_id)
        spec_oauth_path = os.path.join(target_dir, "oauth2.json")
        spec_yf_path = os.path.join(target_dir, ".yahoofantasy")
        
        if user_id and (not os.path.exists(spec_oauth_path) or not os.path.exists(spec_yf_path)):
            from src.utils.security import security_manager
            roles = security_manager._load_json(security_manager.league_roles_path, {})
            user_leagues = []
            for lid, ldata in roles.items():
                if isinstance(ldata, dict) and ldata.get("manager") == user_id:
                    if lid != target_id:
                        user_leagues.append(lid)
            
            for prev_lid in user_leagues:
                prev_dir = get_league_dir(prev_lid)
                prev_oauth = os.path.join(prev_dir, "oauth2.json")
                prev_yf = os.path.join(prev_dir, ".yahoofantasy")
                
                if os.path.exists(prev_oauth) and os.path.exists(prev_yf):
                    os.makedirs(target_dir, exist_ok=True)
                    import shutil
                    shutil.copy2(prev_oauth, spec_oauth_path)
                    shutil.copy2(prev_yf, spec_yf_path)
                    logging.info(f"[SetLeagueIdHandler] 成功將用戶 {user_id} 在聯賽 {prev_lid} 的授權憑證複製到新聯賽 {target_id}")
                    break
```

- [ ] **Step 2: 執行測試並驗證成功**

執行 Task 1 中的單元測試命令，驗證其是否通過。

---

### Task 3: 驗證與提交

- [ ] **Step 1: 執行完整測試套件**

執行命令：
`.venv\Scripts\python -m pytest`
驗證全專案測試無迴歸錯誤。

- [ ] **Step 2: 新功能分支提交變更**

在提交變更前，先以 `git branch --show-current` 驗證當前分支不為 `dev` 或 `master`：
1. `git add src/handlers/set_league_id_handler.py tests/handlers/test_settings_and_setup.py`
2. `git commit -m "feat: implement smart user token reuse across leagues for set league command"`
