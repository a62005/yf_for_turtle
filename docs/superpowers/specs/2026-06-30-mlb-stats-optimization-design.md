# 2026-06-30 MLB 數據優化設計文件 (MLB Stats Optimization Design Spec)

## 1. 背景與目標
在 Yahoo Fantasy MLB (棒球) 聯盟中，統計數據分為**野手數據 (Hitter/Batting)** 與**投手數據 (Pitcher/Pitching)**。
目前的系統（主要針對 NBA 設計）並未區分這兩大類數據，這會導致：
1. 戰績圖片中野手與投手數據混雜在一起，難以閱讀。
2. LINE Flex Message 中所有數據扁平列出，甚至會出現同名但意義相反的指標（例如野手保送 BB 與投手保送 BB）混淆。

本優化案之目標為：
1. **圖片返回優化**：查詢戰績時，若為 MLB 聯盟，將野手數據與投手數據拆開，生成兩張獨立的圖片（野手與投手各一張），並在 LINE 中同時回覆這兩張圖片。
2. **FLEX 訊息優化**：查詢玩家數據（`#玩家`）或對戰數據（`#對戰`）時，若為 MLB 聯盟，在同一個 Flex Bubble（訊息氣泡）中，將野手與投手數據以上下兩個獨立區塊呈現，中間以分隔線與標題明顯隔開。

---

## 2. 系統架構與設計方案

### A. 投手/野手統計項目識別邏輯
在 [src/visualizer/processor.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/visualizer/processor.py) 中，新增一個輔助判斷函數 `is_mlb_pitcher_stat`。
利用 Yahoo API 的 `stat_id` 及輔助的 `sort_order` 來判斷某一統計項目是否屬於投手：
- 投手常用 `stat_id` 集合：`"26"` (ERA), `"27"` (WHIP), `"28"` (W), `"39"` (BB), `"42"` (K), `"50"` (IP), `"83"` (QS), `"89"` (SV+H) 等。
- 通用輔助項目：`Today Player` 及 `Game Player` 標記為通用 (`is_common = True`)，在投手與野手的圖表中皆保留顯示。

### B. 數據處理器修改
修改 [src/visualizer/processor.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/visualizer/processor.py) 中的 `process_stats_for_visual`：
- 若為 MLB 聯盟，對解析出的各個統計類別進行判斷，並在結果字典中寫入 `"is_pitcher": True/False` 和 `"is_common": True/False`。

### C. 圖片生成與發送優化 (`main.py` 與 `StatsHandler`)
1. **過濾與拆分**：在 [main.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/main.py) 中新增過濾函數 `split_mlb_stats`，將處理好的 `daily` 及 `weekly` 數據清單依投手/野手分組。
2. **多圖生成**：若為 MLB，分別渲染野手與投手兩套 HTML 並截圖生成兩張圖片。
   - Combined: `{today_str}_combined_hitter.png` 與 `{today_str}_combined_pitcher.png`
   - Daily: `{today_str}_daily_hitter.png` 與 `{today_str}_daily_pitcher.png`
   - Weekly: `week_{current_week}_weekly_hitter.png` 與 `week_{current_week}_weekly_pitcher.png`
3. **LINE 圖片發送**：
   - 在 [main.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/main.py) 背景任務的完成推送段，若為 MLB，發送含兩張 `ImageMessage` 的陣列。
   - 在 [src/handlers/stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/stats_handler.py) 的快取命中回覆段，若為 MLB 且野手/投手圖片皆已快取，則直接發送此兩張 `ImageMessage`。

### D. FLEX 卡片上下區分佈局
1. **玩家數據卡片 ([src/handlers/user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/user_stats_handler.py))**：
   - 識別是否為 MLB。若是，將當日與當週數據各自分成野手與投手，重組 `sections` 傳入 `build_stats_list_card`：
     1. 📅 `[日期] 野手數據`
     2. ⚾ `[日期] 投手數據`
     3. 📊 `[週數] 野手數據`
     4. 🧢 `[週數] 投手數據`
   - 修改 [src/visualizer/flex_builder.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/visualizer/flex_builder.py) 的 `build_stats_list_card`，在多個 section 渲染間插入 `_create_separator()` 分隔線。
2. **對戰數據卡片 ([src/handlers/matchup_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/matchup_handler.py))**：
   - 通用化 `compare_stats` 比對邏輯：自 `metadata.json` 中動態讀取該聯賽的 `stat_categories`（代替原本寫死的 NBA 9-Cat），依據其 `sort_order` 自動判斷勝負大小。
   - 修改 [src/visualizer/flex_builder.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/visualizer/flex_builder.py) 的 `build_matchup_comparison_card` 函數：
     - 若為 MLB，將 `comparison_rows` 拆分為 `hitter_rows` 與 `pitcher_rows`。
     - 卡片上半部顯示「⚾ 野手對決」數據，下半部加上 Separator 與「🧢 投手對決」副標題，再顯示投手比對數據，使兩者在同一個 Bubble 內上下區分。

---

## 3. 改動檔案明細
- **[src/visualizer/processor.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/visualizer/processor.py)**：新增 `is_mlb_pitcher_stat`；在 `process_stats_for_visual` 中為各項目加上投手/野手/通用標記。
- **[main.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/main.py)**：新增 `split_mlb_stats`，若是 MLB 則分別生成 hitter/pitcher 圖片，並在完成推送時發送兩張圖片。
- **[src/handlers/stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/stats_handler.py)**：修改快取判定與發送邏輯，支援同時發送兩張圖片。
- **[src/visualizer/flex_builder.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/visualizer/flex_builder.py)**：在 `build_stats_list_card` 的 sections 間加入分隔線；重構 `build_matchup_comparison_card` 以在 MLB 下支援野手/投手區塊的分隔與上下排版。
- **[src/handlers/user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/user_stats_handler.py)**：若是 MLB，將當日與當週數據拆為投手/野手兩組（共四組 sections）傳入。
- **[src/handlers/matchup_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/matchup_handler.py)**：動態載入統計項目進行戰績比對；重組對戰數據列為野手與投手兩組，傳入優化後的 `build_matchup_comparison_card`。

---

## 4. 測試驗證計劃
- **單元測試與整合測試**：
  - 執行 `pytest` 確認現有 NBA 查詢邏輯未被破壞。
  - 為 `is_mlb_pitcher_stat` 撰寫測試用例，驗證常用 MLB 投手與野手項目的分類正確性。
  - Mock Yahoo API 數據，針對 `UserStatsHandler` 和 `MatchupHandler` 傳入 MLB 數據，驗證 Flex Message JSON 結構正確性（包含 Separator 與相應的標題）。
  - 測試 `main.py` 在 MLB 模式下是否順利在 `data/league/mlb/{league_id}/image/` 下生成雙圖（野手與投手各一張）。
