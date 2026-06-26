# 設置玩家暱稱功能實作計畫

此計畫定義了實作「設置玩家暱稱」功能的具體步驟，包括：在設置 League 時以官方名稱初始化暱稱檔案、在 `#設置` 選單中啟用按鈕、實作 `SetNicknameHandler` 以及在 `IntentRouter` 中管理會話狀態。

---

## Task 1: 官方暱稱初始化優化

- [ ] **Step 1: 修改 SetLeagueIdHandler 的單元測試**
  在 [test_settings_and_setup.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/handlers/test_settings_and_setup.py) 中，對 `yahoofantasy.League` 進行 mock。驗證當 `team_mapping.json` 不存在時，成功調用 API 取得官方隊伍名稱並正確寫入該對應檔。
- [ ] **Step 2: 修改 SetLeagueIdHandler 初始化邏輯**
  修改 [set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py)，利用 `yahoofantasy.League` 的 `teams()` 方法，讀取 `team_id` 與 `name`，並寫入新創立的對應檔中；同時加入 `try-except` 以防網路異常導致 crash。
- [ ] **Step 3: 執行測試驗證**
  執行該單元測試以確保初始化邏輯正確無誤。

---

## Task 2: 設置選單按鈕綁定

- [ ] **Step 1: 修改 SettingsHandler 按鈕參數**
  修改 [settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py)，將「設置玩家暱稱 (即將推出)」改為「設置玩家暱稱」，並將其 action 指令綁定為 `#設置玩家暱稱`。

---

## Task 3: 暱稱修改處理器實作 (SetNicknameHandler)

- [ ] **Step 1: 新建 SetNicknameHandler 類別**
  在 `src/handlers` 目錄下建立 [set_nickname_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_nickname_handler.py)：
  * 支援指令：`#設置玩家暱稱` 與 `#設置暱稱_隊伍`。
  * 處理 `#設置玩家暱稱`：讀取 `team_mapping.json` (若檔案不存在，先從 Yahoo API 獲取官方名稱初始化)，並呼叫 `build_button_menu_card` 列出所有暱稱按鈕（點擊發送 `#設置暱稱_隊伍 <team_id>`）。
  * 處理 `#設置暱稱_隊伍 <team_id>`：將該 `user_id` 的對話狀態寫入 `IntentRouter` 的 `nickname_sessions`（60秒超時），並提示用戶直接輸入新暱稱。
- [ ] **Step 2: 註冊處理器**
  修改 [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py)，導入並在 dispatcher 中註冊 `SetNicknameHandler`。
- [ ] **Step 3: 撰寫 SetNicknameHandler 的單元測試**
  在 `tests/handlers` 目錄下新建 `test_nickname_handler.py`，對上述兩個指令處理進行測試，驗證 Flex 輸出與狀態註冊。

---

## Task 4: IntentRouter 路由攔截與 Session 管理

- [ ] **Step 1: 初始化狀態字典**
  修改 [intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/intent_router.py) 的 `__init__`，宣告 `self.nickname_sessions = {}`。
- [ ] **Step 2: 實作路由攔截邏輯**
  修改 `IntentRouter.route`：在分發指令前，檢查 `user_id` 在 `nickname_sessions` 中是否有效且未超時：
  * 若用戶發送以 `#` 開頭的標準指令：清空會話狀態，繼續常規路由分發。
  * 若用戶發送一般文字：寫入 `team_mapping.json`，清除會話狀態，並回覆修改成功。
- [ ] **Step 3: 實作寫入 team_mapping 的輔助方法**
  在 `IntentRouter` 內實作 `_update_team_nickname(team_id, new_nickname)` 輔助函數，以便在攔截訊息時安全地更新 JSON 檔。
- [ ] **Step 4: 撰寫路由攔截的單元測試**
  修改 [test_intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_intent_router.py)，測試會話狀態攔截、超時失效、以及發送標準指令時的主動清除。

---

## Task 5: 整合測試與驗證

- [ ] **Step 1: 執行完整測試套件**
  在虛擬環境下執行 `.venv\Scripts\python -m pytest`，確認所有現有與新增的單元測試（包含 integration/tolerance 測試）全部順利通過。
