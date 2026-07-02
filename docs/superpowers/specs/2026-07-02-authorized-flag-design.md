# 2026-07-02 親自授權標記設計文件 (Authorized Flag Design Spec)

## 1. 背景與目標
在實作了跨聯賽憑證智慧複用功能後，系統會透過用戶的 LINE `user_id` 在 `league_roles.json` 中尋找其擁有的其他聯賽目錄並複製憑證。
然而，這會產生以下臨界問題：
1. 用戶 A 授權並綁定了聯賽 A，聯賽 A 目錄下留有用戶 A 的憑證。
2. 用戶 A 解綁了聯賽 A。
3. 用戶 B 綁定了聯賽 A。因為聯賽 A 目錄下已存在憑證，系統會直接跳過授權網頁並將聯賽 A 的擁有者更新為用戶 B。
4. 當用戶 B 隨後綁定全新的聯賽 B 時，系統發現用戶 B 擁有的聯賽 A 目錄下有憑證，便將聯賽 A（實際屬於用戶 A）的憑證複製到聯賽 B。
5. 由於用戶 A 無權限存取聯賽 B，導致聯賽 B 同步失敗並拋出權限錯誤。

本設計之目標為：
- 在 `league_roles.json` 中引入一個 `"authorized": true` 的狀態欄位，用以標記該聯賽的憑證是否是由該管理員**親自進行網頁授權**取得的。
- 只有當用戶**親自授權**的聯賽憑證，才允許在綁定新聯賽時被複製與複用。
- 如果用戶是透過現有憑證免授權綁定的，該聯賽將不會獲得該標記，從而避免其憑證被錯誤傳播給其他聯賽。

---

## 2. 系統架構與設計方案

### A. 權限資料結構調整
在 `league_roles.json` 中，聯賽的資料結構如下調整：
```json
{
  "nba.l.12345": {
    "manager": "USER_LINE_ID",
    "whitelist": {},
    "authorized": true
  }
}
```

### B. 修改的模組與邏輯
1. **[src/utils/security.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/security.py)**：
   * 在 `SecurityManager` 中新增 `set_league_authorized(self, league_id: str, authorized: bool)` 方法，用以更新該聯賽的親自授權狀態。
2. **[src/utils/oauth_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/oauth_handler.py)**：
   * 在 OAuth 回呼成功，即 `handle_oauth_callback` 完成憑證儲存並同步成功時，調用 `security_manager.set_league_authorized(league_id, True)`。
3. **[src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py)**：
   * 用戶輸入指令進行綁定時，若為免授權的直接綁定成功，呼叫 `security_manager.set_league_authorized(target_id, False)`。
   * 搜尋要複用的憑證聯賽時，新增過濾條件：除了 `manager == user_id` 外，該聯賽的 `"authorized"` 欄位必須為 `True`。

---

## 3. 改動檔案明細
- **[src/utils/security.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/security.py)**：新增授權狀態讀寫與標記管理方法。
- **[src/utils/oauth_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/oauth_handler.py)**：授權成功後寫入授權標記為 `True`。
- **[src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py)**：複用憑證時加入親自授權條件過濾，且免授權綁定成功時標記為 `False`。

---

## 4. 測試驗證計劃
- **單元測試**：
  * 更新 `tests/handlers/test_settings_and_setup.py` 中的 `test_set_league_id_reuses_existing_user_token`：
    * 模擬 `league_roles.json` 中 `nba.l.11111` 的 `"authorized": true`，確認會被成功複製。
  * 新增測試 `test_set_league_id_does_not_reuse_unauthorized_token`：
    * 模擬 `nba.l.11111` 的 `"authorized": false`。
    * 用戶嘗試設置新聯賽 `mlb.l.22222`。
    * 斷言 `shutil.copy2` 未被調用，且拋出 `LeaguePermissionError` 以引導網頁授權。
