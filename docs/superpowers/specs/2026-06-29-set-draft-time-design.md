# 設置選單之選秀時間設定功能設計文件

此設計文件定義了 Yahoo Fantasy NBA LINE Bot 在 `#設置` 選單中實作「設置選秀時間」功能的架構與實作規格。

## 1. 需求背景與目標

選秀時間（`DRAFT_DATE`）是聯盟休賽季最重要的資訊。當前系統的選秀時間儲存於全域的 `.env` 或 `league.env` 環境變數中，且無法動態修改。為了支援多聯盟隔離與對話式動態調整，我們需要實現以下目標：

1. **配置數據隔離與解耦**：將每個聯賽自訂的 `DRAFT_DATE` 與開季時間 `next_season_start_date` 統一收納至各聯盟獨立目錄的 `settings.json` 中。
2. **對話式 LLM 自適應格式解析**：點擊「設置選秀時間」後，Bot 進入 60 秒會話。用戶可以直接輸入任意格式的時間（如 `20260701 11:00` 或 `10月15日晚上8點`），Bot 透過 LLM (Gemini) 自動將其解析為精準至「分鐘」的標準格式（`YYYY-MM-DD HH:MM`），免去使用者手動輸入複雜標準格式的負擔。
3. **優化選秀指令回覆**：當使用者輸入 `#選秀` 時，比照 `#開季` 指令，同時顯示「設定的選秀時間」與「剩餘倒數時間」；若該聯盟尚未配置選秀時間，則保持安靜（不回覆）。

---

## 2. 核心架構與資料流設計

### 2.1 聯賽獨立設定檔設計
每個聯盟將新增一個專屬的 `settings.json` 檔案，用以保存使用者自訂的設定，而不與 Yahoo API 快取混雜。
* **檔案路徑**：`data/league/<LEAGUE_ID>/settings.json`
* **JSON 格式**：
  ```json
  {
    "LEAGUE_ID": "18457",
    "DRAFT_DATE": "2026-10-15 20:00",
    "next_season_start_date": "2026-10-20 08:00"
  }
  ```

### 2.2 設定加載機制 (Config Merger)
在 `src/config.py` 中，加載配置的順序將調整為：
1. 從 `data/security/league_config.json` 獲取當前 `LEAGUE_ID`。
2. 若 `LEAGUE_ID` 存在，則讀取 `data/league/<LEAGUE_ID>/settings.json`（若檔案存在）。
3. 如果讀取到自訂值，則覆蓋 `DRAFT_DATE` 與 `NEXT_SEASON_START_DATE` 的環境變數設定。

### 2.3 狀態管理設計 (Session Management)
現有的 `session_manager.py` 記憶體狀態儲存擴充為支援多種會話類型：
```python
_sessions = {}  # 格式: { user_id: { "type": str, "expire_at": float, ... } }
```
提供以下獨立的方法以管理選秀時間會話：
* `set_draft_session(user_id, duration_sec=60)`：寫入 `{"type": "draft_time", "expire_at": ...}`。
* `get_draft_session(user_id)`：取得有效的會話（超時自動清除並回傳 `None`）。
* `clear_draft_session(user_id)`：清除會話。

---

## 3. 核心實作變更點

### 3.1 設定選單入口變更 ([settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py))
將選單中的「設置選秀時間 (即將推出)」啟用：
```diff
             buttons = [
-                ("設置選秀時間 (即將推出)", ""),
+                ("設置選秀時間", "#設置選秀時間"),
                 ("設置玩家暱稱", "#設置玩家暱稱"),
```

### 3.2 新增 `SetDraftTimeHandler` ([set_draft_time_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_draft_time_handler.py))
新實作 `SetDraftTimeHandler`：
* **權限設定**：`requires_whitelist = True`, `exclude_from_llm = True`。
* **匹配條件**：`user_text == "#設置選秀時間"`。
* **執行邏輯**：
  1. 檢查 `LEAGUE_ID` 是否配置。若無，回覆：「`⚠️ 聯賽 ID 尚未配置，無法設定選秀時間。`」並結束。
  2. 讀取當前 `DRAFT_DATE`。若有設定，顯示目前時間；若無，顯示「尚未設定」。
  3. 啟動 `set_draft_session(user_id, 60)` 狀態。
  4. 回覆：「`👉 請在 60 秒內直接輸入新的選秀時間：`」。

### 3.3 LLM 時間格式解析器 ([llm_agent.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/llm/llm_agent.py))
在 `LLMAgent` 類別中新增 `parse_draft_date` 方法：
* **輸入參數**：`text: str`（使用者任意輸入的時間描述，如 `"20260701 11:00"`）。
* **Prompt 規格**：要求 LLM 僅推估至「分鐘」，解析後回傳標準的 JSON 格式：
  ```json
  {
    "success": true,
    "formatted_date": "2026-07-01 11:00"
  }
  ```
  如果年份未指定，請以今年或最合理的未來年份推估。

### 3.4 路由攔截與校驗 ([intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/intent_router.py))
在 `IntentRouter.route` 方法中，新增對選秀會話的處理：
```python
# 1. 取得 session
draft_session = get_draft_session(user_id)
if draft_session:
    if user_text.startswith("#"):
        clear_draft_session(user_id)
    else:
        # 調用 LLM 解析
        res = self.llm_agent.parse_draft_date(user_text)
        if res.get("success") and res.get("formatted_date"):
            formatted_date = res["formatted_date"]
            # 寫入 settings.json
            self._update_league_settings({"DRAFT_DATE": formatted_date})
            clear_draft_session(user_id)
            self.reply_text(event, configuration, f"✅ 成功將選秀時間修改為：{formatted_date}")
            return
        else:
            # 解析失敗，不清除 session，引導使用者重新輸入
            self.reply_text(event, configuration, "⚠️ 無法辨識您輸入的時間，請試著換個方式輸入（例如 10月15日晚上8點，或發送任意 # 指令以取消）：")
            return
```

### 3.5 倒數時間解析與顯示重構 ([misc_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/misc_handler.py))
* **向下相容格式讀取**：修改 `_calculate_countdown`，使其同時相容有秒與無秒的格式：
  ```python
  try:
      target_dt_naive = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M:%S")
  except ValueError:
      target_dt_naive = datetime.strptime(target_time_str, "%Y-%m-%d %H:%M")
  ```
* **開季時間快取位置重定向**：將 `_handle_season_start` 中讀寫 `next_season_start_date` 的目標由原本的 `metadata.json` 修改為 `settings.json`。
* **選秀回覆格式變更**：重寫 `_handle_draft_countdown`。若無 `DRAFT_DATE` 則保持安靜；若有，則回覆目標時間與倒數剩餘時間：
  ```python
  # 輸出範例
  # ⚔️ 聯盟選秀時間已設定為：
  # 👉 2026年10月15日 20:00
  # ⚔️ 距離聯盟選秀開始還有：
  # 👉 108 天 2 小時 15 分鐘
  ```

---

## 4. 單元測試規劃

1. **配置加載測試**：驗證 `load_config` 能正確讀取 `settings.json` 中的 `DRAFT_DATE` 與 `NEXT_SEASON_START_DATE` 並覆蓋環境變數。
2. **LLM 解析時間測試**：Mock LLM 回傳，驗證在輸入各種時間字串時，`parse_draft_date` 能否正確輸出標準 `YYYY-MM-DD HH:MM` 格式。
3. **Session 與交互測試**：
   * 模擬點擊 `#設置選秀時間`，確認已建立 Session。
   * 發送 `"20260701 11:00"`，驗證 LLM 解析成功，檔案寫入正確，且 Session 已被清除。
   * 模擬 LLM 解析失敗，驗證會話保持 active，且回傳格式警示訊息。
4. **選秀倒數測試**：
   * 驗證在未配置 `DRAFT_DATE` 時，不回覆任何訊息。
   * 驗證在已配置時，回傳指定格式的目標選秀時間與倒數天數。
