# Yahoo Fantasy NBA - 智慧即時比賽狀態監控設計規格書 (Match Status Monitor Specification)

- **日期**: 2026-06-24
- **作者**: Antigravity AI
- **狀態**: 草案 (Draft)

---

## 1. 功能概述 (Feature Overview)
本功能旨在改良原本戰績查詢中的「靜態時間限制阻擋（夏令 14:00 後允許 / 冬令 15:00 後允許）」，升級為 **「智慧即時比賽狀態監控」**：
1. 當用戶查詢「本日」或「當前進行週」的聯賽戰績時，自動透過外部公開的 ESPN Scoreboard API 即時查詢當日 NBA 所有比賽狀態。
2. 根據當日比賽的進行狀況（未開始、進行中、部分結束、全部結束、無賽事）實施動態阻擋或放行。
3. 若外部 API 發生連線異常或無法判定，自動降級退回原本的靜態時間阻擋邏輯。
4. **快取優化**：若今日戰績圖片已生成並存在於本地快取中，則直接放行並回傳，不再發送網路 API 請求。

---

## 2. 判定邏輯設計 (Decision Tree Design)

### 2.1 適用範圍與阻擋豁免
此動態阻擋規則**僅適用**於：
* 用戶查詢本日戰績（即 `#戰績`，`cmd_type == "combined"`）。
* 用戶查詢當前進行中的週數戰績（如目前為第 10 週，查詢 `#戰績W10`）。

**以下情況不予阻擋（直接放行）**：
* 歷史查詢：查詢昨天的戰績（`#戰績昨天`）、上週的戰績（`#戰績上週`）、或過去特定日期或週數的戰績。
* 即時數據與個人數據：玩家對戰查詢（`#對戰 玩家`）、玩家個人數據（`#玩家 玩家`）、球員數據查詢（`#球員 球員`）與傷兵查詢（`#傷兵 玩家`）。

### 2.2 賽事狀態統計與決策
對於需阻擋的查詢，系統會先取得查詢目標美西日期（`target_date`，格式為 `YYYYMMDD`），並請求 ESPN API：
`https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates=YYYYMMDD`

解析回傳數據中所有賽事的 `status.type.state`：
* **`pre`**：比賽尚未開始
* **`in`**：比賽進行中
* **`post`**：比賽已結束

統計當日總場次 $N_{total}$，以及處於各狀態的場次數量 $N_{pre}$、$N_{in}$、$N_{post}$。判定決策樹如下：

```
                    [ 檢查 ESPN API 資料 ]
                              |
                      N_total == 0 ?
                     /              \
                   (是)             (否)
                   /                  \
             【 放行 】              N_in > 0 ?
                                    /         \
                                  (是)        (否)
                                  /             \
                       【 阻擋：進行中 】     N_pre > 0 ?
                       "目前仍有比賽正在進行"   /         \
                                             (是)        (否)
                                             /             \
                                        N_post > 0 ?     【 放行 】
                                        /          \    (全數比賽結束)
                                      (是)         (否)
                                      /              \
                          【 阻擋：跨時段未完 】  【 阻擋：尚未開始 】
                            "今日比賽尚未全部結束，  "今日比賽尚未開始"
                            請在所有比賽結束後再
                                進行查詢"
```

---

## 3. 系統架構與實作修改 (System Architecture & Modifications)

### 3.1 `src/utils/time_utils.py`
* **新增與修改函數**：
  * 修改 `is_stats_query_allowed(is_offseason, target_date)`：
    * 接受 `target_date` 參數。
    * 若當日為休賽季（`is_offseason`），直接回傳 `(True, "")`。
    * 優先呼叫 `check_nba_game_status(target_date)`。
    * 若該函數回傳決策結果，直接回傳對應的 `(allowed, err_msg)`。
    * 若該函數因異常拋出錯誤（回傳 `None`），自動執行時令判定退回時間阻擋：
      * 夏令時間 14:00 後放行，冬令時間 15:00 後放行。若不滿足，回傳 `(False, "請於 {allow_hour}:00 後再進行查詢。")`。

  * 新增 `check_nba_game_status(date_str: str) -> tuple[bool, str] | None`：
    * 將 `date_str`（格式 `YYYY-MM-DD`）轉換為 `YYYYMMDD` 格式。
    * 發送請求至 ESPN NBA Scoreboard API。設定 Timeout 為 3 秒以防止卡頓。
    * 解析 JSON 中的 `events` 列表。
    * 依據上述決策樹進行比對，回傳 `(allowed, err_msg)`。
    * 若遭遇網路異常、解析異常，則記錄 `logging.warning` 並回傳 `None`（交由上層進行時間備援）。

### 3.2 `src/handlers/stats_handler.py`
* **判斷條件擴展**：
  * 系統原先只在 `cmd_type == "combined"` 時呼叫 `is_stats_query_allowed`。
  * 修改為：
    ```python
    # 判斷是否為本日或當前進行中的週數
    is_today_query = cmd_type == "combined"
    
    current_week = date_to_week.get(today_pacific) or get_fantasy_week(start_date, today_dt)
    is_current_week_query = (cmd_type == "specific_week" and target_week == current_week)
    
    if is_today_query or is_current_week_query:
        from src.utils.time_utils import is_stats_query_allowed
        allowed, err_msg = is_stats_query_allowed(is_offseason=is_offseason, target_date=target_date)
        if not allowed:
            # 阻擋並回覆 err_msg
            return
    ```
  * *註：圖片快取檢查位於此判斷之前，因此已產生圖片的查詢會被自然放行，不受此處影響。*

---

## 4. 測試計畫 (Testing Plan)

1. **`tests/test_time_utils.py`**：
   * 測試 `check_nba_game_status` 對於不同 ESPN JSON 模擬回傳的決策結果：
     * `events` 為空時放行。
     * 存在 `in` 狀態比賽時阻擋，提示「目前仍有比賽正在進行」。
     * 全為 `pre` 狀態比賽時阻擋，提示「今日比賽尚未開始」。
     * 混合 `pre` 與 `post` 狀態比賽時阻擋，提示「今日比賽尚未全部結束，請在所有比賽結束後再進行查詢」。
     * 全為 `post` 狀態時放行。
   * 測試 ESPN API 異常拋出例外時，`is_stats_query_allowed` 能否正確降級至時段比對邏輯。

2. **`tests/handlers/test_stats_handler.py`**：
   * 驗證當前週數戰績查詢（例如 `#戰績W10`）在賽事未完結時，會正確觸發動態阻擋並顯示提示。
   * 驗證歷史週數查詢（例如 `#戰績W9`）或歷史日期查詢，即使在比賽進行中也不會觸發阻擋。
