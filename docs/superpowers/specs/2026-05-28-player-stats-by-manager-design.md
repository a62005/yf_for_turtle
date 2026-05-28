# 設計規格書：LINE Bot #玩家 <稱呼> 即時數據查詢功能

本規格書詳細記錄了如何透過 LINE Bot 指令 `#玩家 <稱呼>`，即時且不限時間地拉取 Yahoo Fantasy 聯盟中單一隊伍的當日數據與當週累積戰績，並以無中文名、無虛線、改含 YYYY-MM-DD 數據日期與週數的等寬格式回傳。

---

## 1. 核心需求與行為規範

1. **指令觸發與開關**：
   - 使用者發送 `#玩家 <稱呼>`（例如：`#玩家 韋哥`）。
   - **精準匹配開關**：系統在 `can_handle` 階段會精準比對 `team_mapping.json` 中已登錄的稱呼。若比對成功，則啟用此處理器；**若比對失敗或未登錄，則直接略過該訊息，Bot 不做任何回應或錯誤回覆**。
2. **即時立即查詢**：
   - 此指令不限制查詢時間（無須等到 14:00 後），為確保數據的最即時性，每次觸發皆會直接發送實時請求至 Yahoo API（不走本地 JSON 圖片快取）。
3. **排版格式要求**：
   - 移除所有中文名稱與 `-----------------------` 分隔線。
   - 數據表格必須包裹於 Markdown 等寬程式碼區塊 (\`\`\`) 中以在行動端完美靠右對齊。
   - 當日數據在上方，並包含 YYYY-MM-DD 格式數據日期。
   - 當週數據在下方，並附上週數標頭（例如 `W24`）。

---

## 2. 系統架構與核心組件

### 2.1 新增處理器組件

#### [NEW] [user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/user_stats_handler.py)
- 繼承 `BaseHandler`，負責解析 `#玩家` 指令。
- 內部比對 `team_mapping.json` 的綽號 values，確定 `team_id`。
- 調用 `YahooFantasyFetcher` 獲取數據。
- 格式化數據並回傳 LINE 訊息。

### 2.2 擴充資料抓取組件

#### [MODIFY] [fetcher.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/fetcher.py)
- 新增 `fetch_single_team_stats_by_url(self, team_key: str, stat_type: str, type_val: str) -> dict` 方法。
- 新增 `_parse_team_stats_xml(self, xml_data: str) -> dict` 用於將單一隊伍 API 回傳的 XML 解析成標準的 9-Cat 戰績 dict。

---

## 3. 數據流與 API 串接設計

### 3.1 數據流向圖
```mermaid
sequenceDiagram
    participant U as LINE 使用者
    participant H as UserStatsHandler
    participant F as YahooFantasyFetcher
    participant Y as Yahoo API (OAuth)

    U->>H: 發送 "#玩家 韋哥"
    H->>H: 讀取 team_mapping.json 反查 韋哥 -> Team ID: 1
    H->>H: 計算當前跨日美西日期 (YYYY-MM-DD) 與週數 (W24)
    
    par 1. 抓取當日數據
        H->>F: 呼召 fetch_single_team_stats_by_url(stat_type='date')
        F->>Y: 請求 team/nba.l.xxx.t.1/stats;type=date;date=YYYY-MM-DD
        Y-->>F: 回傳 XML 數據
        F-->>H: 解析並回傳 9-Cat 當日數據
    and 2. 抓取當週數據
        H->>F: 呼召 fetch_single_team_stats_by_url(stat_type='week')
        F->>Y: 請求 team/nba.l.xxx.t.1/stats;type=week;week=24
        Y-->>F: 回傳 XML 數據
        F-->>H: 解析並回傳 9-Cat 當週數據
    end

    H->>H: 組裝排版為等寬格式
    H-->>U: 回傳 LINE 訊息
```

### 3.2 Yahoo API Endpoint 與 XML 解析
- **當日數據 Endpoint**：`team/nba.l.<league_id>.t.<team_id>/stats;type=date;date=<YYYY-MM-DD>`
- **當週數據 Endpoint**：`team/nba.l.<league_id>.t.<team_id>/stats;type=week;week=<week_number>`
- **XML 解析**：
  - 提取 `<name>` 節點作為球隊的官方中文/英文取名。
  - 解析所有的 `<stat>`。利用 `translate_stat_id` 對照表，將其轉換為標準的 `PTS`, `REB`, `AST` 等標籤。
  - 將 FGM/A（ID 4/3）與 FTM/A（ID 7/6）進行拼接為字串格式。

---

## 4. 排版與組裝樣式 (Layout Details)

訊息由三個部分銜接而成：
1. **當日 Header**：
   ```text
   [玩家稱呼]
   [官方球隊名稱]
   [YYYY-MM-DD]
   ```
2. **當日數據區塊 (Wrapped in ```)**：
   ```text
   FGM/A :           14/24
   FG%   :           58.3%
   ...
   ```
3. **當週 Header 與數據區塊 (Wrapped in ```)**：
   ```text
   [WXX]
   ```
   ```text
   FGM/A :          80/150
   FG%   :           53.3%
   ...
   ```

---

## 5. 防錯與異常處理 (Error Handling)

1. **今日無比賽數據**：
   - 當日若未出賽（或 FGM/A 為 `0/0` 且得分為 `0`），**當日數據區塊仍照常顯示全 0 的表格**，下方照常且即時顯示 `WXX` 當週累積戰績，以維持排版美觀與一致性。
2. **休賽季 (Offseason) 邏輯**：
   - 當前美西日期大於賽季結束日期時，**自動指向賽季的最後一天**，確保玩家依然可以抓取歷史最後一天的當日與當週累計表現。
3. **Yahoo API 逾時或失敗**：
   - 系統將會錄下錯誤日誌，但**直接安靜退出，不發送錯誤訊息干擾 LINE 群組**。

---

## 6. 測試驗證計畫

1. **單元測試設計**：
   - 新增 `tests/test_user_stats_handler.py` 驗證：
     * 當綽號存在於 `team_mapping.json` 時，`can_handle` 應回傳 `True`；不存在時，回傳 `False`（略過訊息）。
     * 當日無出賽時，數據格式化是否為預期的全 0 對齊表格。
   - 新增 `tests/test_fetcher_single_team.py` 驗證 XML 提取球隊名稱、拼接 FGM/A 和 FTM/A 的正確性。
2. **自動化驗證指令**：
   ```powershell
   python -m pytest tests/test_user_stats_handler.py
   ```
