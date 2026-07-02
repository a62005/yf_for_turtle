# 2026-07-02 已授權用戶綁定新聯盟免授權設計文件 (User Token Reuse Design Spec)

## 1. 背景與目標
在目前專案的設計中，當用戶要綁定一個新的聯盟 ID（執行 `#設置聯盟ID <ID>`）時：
1. 系統會先建立 `YahooFantasyFetcher` 並嘗試與 Yahoo 同步賽季資訊。
2. 同步過程中，若本地無憑證，系統會複製全域 `credentials/` 下的預設憑證（屬於機器人管理員）。
3. 如果該預設憑證無權限，則會拋出 `LeaguePermissionError`，引導用戶進行網頁授權。
4. 網頁授權成功後，該聯盟的憑證會寫入專屬的目錄中（例如 `data/league/nba.l.12345/`）。

然而，這使得一個擁有多個聯盟（如聯盟 A 與聯盟 B）的普通用戶，在不同群組綁定新聯賽時，每次都必須重新點擊連結進行瀏覽器授權。

本設計之目標為：
- 當用戶綁定新聯盟時，若該用戶**先前已經為其他聯盟授權過憑證**，系統應自動尋找並複用該憑證。
- 當憑證順利複用且擁有新聯盟存取權時，用戶將不需進行重複網頁授權，直接完成綁定。
- 若複用的憑證無權限，則無縫退回原有的網頁授權引導流程，確保向下相容性。

---

## 2. 系統架構與設計方案

### A. 憑證複製邏輯調整
在 [src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py) 的執行主入口：
- 在建立 `YahooFantasyFetcher` 之前，先判定新聯盟的目錄下是否已經有 `oauth2.json` 與 `.yahoofantasy` 憑證。
- 若無憑證且能取得目前的 LINE `user_id`：
  - 讀取聯賽權限資料檔（`league_roles.json`），尋找所有管理員 (`manager`) 為目前 `user_id` 的已綁定聯盟。
  - 對於找到的聯盟，檢查其目錄下是否存在有效的 `.yahoofantasy` 與 `oauth2.json` 憑證。
  - 若存在，則直接將該憑證複製到當前正在設置的新聯盟目錄下。
  - 完成後再初始化 `YahooFantasyFetcher`。

### B. 修改的代碼位置
修改 [src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py) 中的 `execute` 方法（約第 185 行開始）：
- 加入對 `league_roles.json` 的檢索與憑證複製邏輯。

---

## 3. 改動檔案明細
- **[src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py)**：新增已授權憑證的檢索與跨聯賽目錄複製邏輯。

---

## 4. 測試驗證計劃
- **單元測試**：
  - 在 `tests/handlers/test_settings_and_setup.py` 中新增 `test_set_league_id_reuses_existing_user_token`：
    - 模擬 `league_roles.json` 中已存在用戶先前綁定的聯賽 `nba.l.11111` 且該聯賽目錄有憑證檔案。
    - 用戶嘗試綁定新聯賽 `mlb.l.22222`。
    - 執行 `#設置聯盟ID mlb 22222` 指令，並模擬同步成功。
    - 斷言測試結束後，新聯賽 `mlb.l.22222` 的目錄下確實成功複製了來自 `nba.l.11111` 的憑證檔案。
  - 執行 pytest 驗證所有測試皆順利通過。
