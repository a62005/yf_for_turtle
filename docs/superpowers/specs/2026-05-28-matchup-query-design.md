# 實時一對一對戰數據查詢 (#對戰) 設計規格書 (Spec)

本文件定義了 Yahoo Fantasy NBA Scraper AI 項目中「實時一對一對戰數據查詢（#對戰）」功能的技術設計與視覺呈現規格。

---

## 1. 功能概述 (Goal Description)

為 LINE 聯賽群組玩家提供極速、清爽、視覺對比強烈的實時當週一對一對決數據查詢。
*   **觸發指令**：`#對戰 [暱稱]` (例如：`#對戰 韋哥`)
*   **核心目標**：利用 Yahoo Scoreboard API 單次請求下載當週全聯盟對戰，自動提取該玩家與其當週對手的 9-Cat 累計數值與即時比分，回傳一個符合「領先黑色較大、落後灰色較小」終極視覺邏輯的 11 行極簡風對稱 Flex Message 卡片。

---

## 2. 需求規格 (Requirements & Scope)

1.  **週次範圍**：僅支援**當週（Current Week）**的實時對決查詢，不支援歷史週次，以保持功能的單純與極速。
2.  **暱稱比對與異常處理**：
    *   比照現有 `#玩家` 指令，使用精準中文暱稱匹配。輸入的暱稱必須完全存在於 `team_mapping.json` 中。
    *   若輸入無效暱稱，或 API 請求發生任何異常，系統會**安靜且安全地退出，不發送任何訊息**，避免洗版與干擾群組。
3.  **指標與勝負判定**：
    *   **9 個正式指標 (9-Cat)**：`FG%`, `FT%`, `3PM`, `PTS`, `REB`, `AST`, `STL`, `BLK`, `TO`。
    *   **2 個輔助指標**：`FGM/A`, `FTM/A`。
    *   **判定規則**：`TO` 為**越小越好**；其餘 8 個正式指標為**越大越好**。輔助指標不參與勝負計算。
4.  **終極視覺一致性邏輯（關鍵規格）**：
    *   **領先方一律黑色較大**：比分與細項數據中，領先的一方顯示為**粗體、黑色較大字體** (`color: #111111`, `size: "md" 或 "lg"`)。
    *   **落後方一律灰色較小**：落後的一方顯示為**常規粗細、灰色較小字體** (`color: #999999`, `size: "xs"`)。
    *   平手時雙方均以常規大字顯示。
    *   若命中率為 0，優雅地顯示為 `-`（且套用勝負的灰小字或黑大字樣式）。
    *   輔助行 `FGM/A` 與 `FTM/A` 正常顯示（13px 一般灰色 `#777777`，不進行 any 比較標註）。

---

## 3. 架構與數據流設計 (Architecture & Data Flow)

我們採用 **單次 Scoreboard API 請求 + 記憶體反查** 的高效能方案：

```
[LINE 觸發: #對戰 韋哥] 
       │
       ▼
[1. 暱稱反查] ── (team_mapping.json) ──► 獲取我方 team_id = "1"
       │
       ▼
[2. API 請求] ── (單次呼叫 Yahoo Scoreboard) ──► 獲取當週全聯賽對決 XML
       │
       ▼
[3. 記憶體匹配] ──► 遍歷所有對戰組，尋找包含 team_id = "1" 的 Matchup
       │
       ▼
[4. 數據提取與角色錨定] ──► 錨定左邊為 My Team (韋哥)，右邊為 Opponent (Jerry)
       │
       ▼
[5. 9-Cat 勝負判定] ──► 計算當前總比分 (例如 5:4) 並為 11 行指標標示領先/落後狀態
       │
       ▼
[6. 渲染 Flex Message] ──► 產出極簡無 Footer 的對稱卡片，回傳給 LINE 使用者
```

---

## 4. 模組變更設計 (Proposed Changes)

### 4.1. [src/fetcher.py](file:///Users/yilin/Python/yf_for_turtle/src/fetcher.py)
新增 `fetch_matchups(self, league_id: str, week: int) -> list` 方法：
*   **輸入**：`league_id` (聯賽 ID), `week` (週次)。
*   **功能**：發送請求至 `league/{league_id}/scoreboard;week={week}`。
*   **解析邏輯**：
    *   遍歷 `//ns:matchup` 節點。
    *   對每個 matchup 中的兩個 `team`：
        *   提取 `team_id`。
        *   提取官方隊名並對照 `team_mapping` 轉換為中文暱稱。
        *   提取其 `team_stats` 底下所有的 `stat`，使用 `translate_stat_id` 翻譯成 9-Cat 指標字典。
        *   若有 `stat_4` 與 `stat_3`，自動拼接出輔助項 `FGM/FGA`；若有 `stat_7` 與 `stat_6`，自動拼接出輔助項 `FTM/FTA`。
    *   回傳包含全聯盟對戰的列表。

### 4.2. [src/handlers/matchup_handler.py](file:///Users/yilin/Python/yf_for_turtle/src/handlers/matchup_handler.py) [NEW]
新增對戰查詢 Handler：
*   **繼承**：`BaseHandler`。
*   **指令比對**：`r"^#對戰\s+(.+)$"`，提取暱稱。
*   **功能實作**：
    *   `can_handle`：驗證暱稱是否登記在 `team_mapping.json`。
    *   `execute`：
        1.  計算目前美西日期與當週週數。
        2.  調用 `fetcher.fetch_matchups` 取得對戰列表。
        3.  尋找包含該玩家的對戰。
        4.  比對 9-Cat 數值，正確計算比分與標示領先/落後。
        5.  若命中率為 0 或為空，轉為 `-`。
        6.  將數據傳入 `format_matchup_stats` 生成符合規格的 Flex Message。
        7.  調用 `reply_flex` 回覆。
*   **安靜退出機制**：若查無暱稱或 API 失敗，僅記錄 error log 並直接 return，保持安靜。

### 4.3. [bot.py](file:///Users/yilin/Python/yf_for_turtle/bot.py)
*   導入 `MatchupHandler`。
*   在 `dispatcher` 註冊：`dispatcher.register(MatchupHandler())`。

### 4.4. 單元測試
*   [tests/test_fetcher_matchup.py](file:///Users/yilin/Python/yf_for_turtle/tests/test_fetcher_matchup.py) [NEW]：測試 `fetcher.fetch_matchups` 是否能正確發送與解析 Scoreboard XML。
*   [tests/test_matchup_handler.py](file:///Users/yilin/Python/yf_for_turtle/tests/test_matchup_handler.py) [NEW]：測試指令比對、暱稱反查、指標比對邊界值（如 TO 越少越好、空值轉 `-`、比分計算等）以及 Flex Message 的 JSON 生成是否正確。

---

## 5. Flex Message 視覺規格 (Flex Message Spec)

卡片採用白底極簡風，由 `format_matchup_stats` 函式輸出 JSON dict。其核心結構如下：

### 5.1. Header 區域 (三層設計)
*   **第一層 (暱稱列)**：使用 `horizontal` 佈局。
    *   左側：我方中文暱稱 (`weight: "bold"`, `size: "xl"`, `color: "#111111"`)。
    *   中間：`VS` (`size: "sm"`, `color: "#aaaaaa"`, `align: "center"`)。
    *   右側：對手中文暱稱 (`weight: "bold"`, `size: "xl"`, `color: "#111111"`, `align: "end"`)。
*   **第二層 (官方隊名列，無 VS)**：使用 `horizontal` 佈局。
    *   左側：我方官方隊名 (`size: "xxs"`, `color: "#999999"`)。
    *   右側：對手官方隊名 (`size: "xxs"`, `color: "#999999"`, `align: "end"`)。
*   **第三層 (比分列)**：使用 `horizontal` 佈局，置中，帶有淡灰色背景或適當邊距。
    *   左側比分：我方贏得項數。若我方領先 (如 5)，則為**大字粗體黑色** (`size: "xl"`, `weight: "bold"`, `color: "#111111"`)；若落後 (如 4)，則為**小字常規灰色** (`size: "md"`, `color: "#999999"`)；平手同為大字。
    *   中間冒號：`:` (`color: "#cccccc"`)。
    *   右側比分：對手贏得項數。同樣依勝負套用「領先黑色較大、落後灰色較小」規格。

### 5.2. Body 區域 (11 行對稱指標)
*   每一行皆為 `horizontal` 佈局：
    *   **左側我方數值**：
        *   若我方在此指標領先：**粗體黑色大字** (`weight: "bold"`, `size: "md"`, `color: "#111111"`)。
        *   若我方在此指標落後：**常規灰色小字** (`size: "xs"`, `color: "#999999"`)。
        *   平手：雙方均為常規黑色中字 (`size: "sm"`, `color: "#555555"`)。
    *   **中間指標標籤**：指標名稱（如 `PTS`, `FG%`），居中 (`size: "xs"`, `weight: "bold"`, `color: "#bbbbbb"`)。
    *   **右側對手數值**：同樣依勝負套用「領先黑色較大、落後灰色較小」規格。
*   **特殊行 (FGM/A, FTM/A)**：不套用勝負判定，雙方一律以常規灰色 (`size: "sm"`, `color: "#777777"`) 正常顯示。

---

## 6. 驗證計劃 (Verification Plan)

### 6.1. 自動化測試
執行新編寫的測試案例，驗證核心解析與比對演算法：
```bash
pytest tests/test_fetcher_matchup.py tests/test_matchup_handler.py -v
```

### 6.2. 手動測試與效果確認
1.  **暱稱對照測試**：
    *   輸入 `#對戰 韋哥`（已登記暱稱）──► 確認回傳高質感三層 Header 比分卡片。
    *   輸入 `#對戰 詹姆斯`（未登記暱稱）──► 確認系統安靜退出，無任何回覆。
2.  **視覺與排版確認**：
    *   確認 Header 第三層比分中，較大比分的一方字體確實較黑較大，較小的一方較灰較小。
    *   確認 Body 11 行中，指標較優方的字體變大加粗，落後方變灰變小。
    *   確認 `FGM/A` 與 `FTM/A` 沒有加粗，字體正常。
    *   確認若有命中率為 0 的空數據時，顯示為 `-` 且樣式正常。
