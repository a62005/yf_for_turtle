# 設置選單之玩家暱稱設定功能設計文件

此設計文件定義了 Yahoo Fantasy NBA LINE Bot 在 `#設置` 選單中實作「設置玩家暱稱」功能的架構與實作規格。

## 1. 需求背景與目標

當前 Bot 支援透過 `team_mapping.json` 將 Yahoo 隊伍 ID 對應到玩家的中文暱稱，以提供友善的日常查詢。為了讓系統管理員能直接在 LINE 聊天室中動態調整這些暱稱，而不需要手動登入伺服器編輯檔案，我們需要實作以下功能：

1. **官方暱稱預設初始化**：在設定聯盟 ID（`#設置聯盟ID <ID>`）且 `team_mapping.json` 不存在時，自動從 Yahoo API 抓取所有隊伍的官方名稱作為初始內容，避免產生空的對應檔。
2. **暱稱設置清單**：點擊「設置玩家暱稱」後，回覆一個 Flex 訊息，以按鈕清單列出當前所有隊伍暱稱，用戶點擊任一暱稱即可觸發修改。
3. **對話式交互修改（免指令）**：點選修改特定隊伍後，Bot 進入為期 60 秒的「等待暱稱輸入」狀態。用戶在 60 秒內直接發送任何「非指令文字」，Bot 將其攔截並直接寫入為該隊伍的新暱稱，不需再透過複雜的 `#設置暱稱 <ID> <新暱稱>` 指令。

---

## 2. 核心架構與資料流設計

### 2.1 狀態管理設計 (Session Management)
我們將在 `IntentRouter` 中引入輕量化的記憶體狀態管理：
```python
self.nickname_sessions = {}  # 格式: { user_id: { "team_id": str, "expire_at": float } }
```
當用戶點擊隊伍並發送 `#設置暱稱_隊伍 <team_id>` 時，會在 `nickname_sessions` 中寫入一筆資料，超時時間（`expire_at`）設定為當前時間加 60 秒。

### 2.2 路由攔截機制 (Router Interception)
在 `IntentRouter.route` 的最前面，我們會先檢測該發送者是否處於有效修改狀態：
* **攔截條件**：
  * 用戶在 `nickname_sessions` 中有 active session。
  * 當前時間小於 `expire_at`（未超時）。
  * 用戶發送的訊息**不是**以 `#` 開頭的標準指令。
* **處理邏輯**：
  1. 將輸入文字（`event.message.text.strip()`）作為新暱稱，更新 `team_mapping.json`。
  2. 清除該用戶的 Session 狀態。
  3. 回覆：「`✅ 成功將暱稱修改為：[新暱稱]`」。
  4. 終止後續的指令路由分發。
* **狀態重置條件**：
  * 若用戶發送的是以 `#` 開頭的標準指令，則主動清除該 Session 狀態，並讓該指令正常分發。
  * 60 秒一到，狀態在下一次查詢或背景檢查時自動失效。

---

## 3. 核心實作變更點

### 3.1 官方暱稱初始化變更 ([set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py))
當 `#設置聯盟ID` 成功且對應檔不存在時，自動連線抓取官方隊伍名：
```python
mapping_path = get_league_team_mapping_path(target_id)
if not os.path.exists(mapping_path):
    os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
    default_mapping = {}
    try:
        import yahoofantasy
        league = yahoofantasy.League(fetcher.ctx, fetcher._normalize_league_id(target_id))
        for team in league.teams():
            team_id = str(getattr(team, "team_id", ""))
            team_name = str(getattr(team, "name", ""))
            if team_id and team_name:
                default_mapping[team_id] = team_name
    except Exception as ex:
        logging.error(f"[SetLeagueIdHandler] 無法取得官方暱稱，初始化為空對應: {ex}")
    
    with open(mapping_path, "w", encoding="utf-8") as mf:
        json.dump(default_mapping, mf, ensure_ascii=False, indent=2)
```

### 3.2 設置選單入口變更 ([settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py))
將「設置玩家暱稱 (即將推出)」改為正式按鈕，並綁定發送指令為 `#設置玩家暱稱`。
```diff
             buttons = [
                 ("設置選秀時間 (即將推出)", ""),
-                ("設置玩家暱稱 (即將推出)", ""),
+                ("設置玩家暱稱", "#設置玩家暱稱"),
                 (None, None),
                 ("更換聯盟ID (即將推出)", ""),
                 ("移除聯盟ID (即將推出)", "")
             ]
```

### 3.3 新增暱稱修改處理器 ([set_nickname_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_nickname_handler.py))
實作全新 `SetNicknameHandler`，負責處理：
1. **指令 `#設置玩家暱稱`**：
   * 讀取 `team_mapping.json`（若無，自動呼叫初始化）。
   * 呼叫 `build_button_menu_card` 生成 Flex 選單，每一個按鈕顯示當前暱稱，點擊後發送 `#設置暱稱_隊伍 <team_id>`。
2. **指令 `#設置暱稱_隊伍 <team_id>`**：
   * 從 `team_mapping.json` 中讀取該隊伍名稱。
   * 向 `IntentRouter` 的 `nickname_sessions` 註冊該用戶修改狀態（60 秒有效）。
   * 回覆：「`請在 60 秒內直接輸入 <目前暱稱> 的新暱稱：`」。

### 3.4 路由中介攔截 ([intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/intent_router.py))
在 `IntentRouter.route` 方法中，優先檢查並執行對話攔截：
```python
# 取得用戶 ID
user_id = event.source.user_id
user_text = event.message.text.strip()

# 檢查是否存在有效會話
if user_id in self.nickname_sessions:
    session = self.nickname_sessions[user_id]
    if time.time() < session["expire_at"]:
        # 若是標準指令（以 # 開頭），則取消會話並繼續路由
        if user_text.startswith("#"):
            del self.nickname_sessions[user_id]
        else:
            # 攔截並寫入新暱稱
            team_id = session["team_id"]
            self._update_team_nickname(team_id, user_text)
            del self.nickname_sessions[user_id]
            self.reply_text(event, configuration, f"✅ 成功將暱稱修改為：{user_text}")
            return
    else:
        # 已超時，清除會話
        del self.nickname_sessions[user_id]
```

---

## 4. 單元測試規劃
1. **測試官方暱稱初始化**：驗證 `SetLeagueIdHandler` 成功抓取 `yahoofantasy.League` 的隊伍並正確填入對應 JSON 檔。
2. **測試暱稱選單展示**：驗證發送 `#設置玩家暱稱` 時，回傳包含當前暱稱清單的 Flex Message。
3. **測試對話攔截邏輯**：
   * 模擬發送 `#設置暱稱_隊伍 1` ➡️ 驗證 `nickname_sessions` 中已記錄會話。
   * 隨後發送非指令字串 `新測試暱稱` ➡️ 驗證 `team_mapping.json` 已被正確更新為 `新測試暱稱`，且回傳成功訊息。
   * 模擬發送 `#設置暱稱_隊伍 1` ➡️ 發送 `#對戰` 標準指令 ➡️ 驗證會話被順利取消且 `#對戰` 指令被正常分發。
   * 模擬超時 60 秒後發送文字 ➡️ 驗證會話已失效，不進行攔截。
