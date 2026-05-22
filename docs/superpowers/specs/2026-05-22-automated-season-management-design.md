# 設計規範：自動化賽季管理與日期驗證 (Automated Season Lifecycle & Date Validation)

## 1. 背景與目標
目前賽季開始日期（`SEASON_START_DATE`）採手動設定，且缺乏日期合法性檢查。當進入休賽季或使用者輸入錯誤日期時，系統行為不明確。
**目標**：
1. 自動從 Yahoo API 獲取賽季起迄時間並進行本地快取。
2. 實現智慧日期驗證，處理未來日期、過往賽季與休賽季的查詢導向。

## 2. 數據管理
*   **快取檔案**: `data/league_metadata.json`
*   **儲存欄位**:
    *   `start_date`: 賽季第一天 (YYYY-MM-DD)。
    *   `end_date`: 賽季最後一天 (YYYY-MM-DD)。
    *   `season`: 賽季年份。
    *   `last_updated`: 最後更新時間。

## 3. 邏輯分支

### 3.1 賽季中繼資料更新
*   **觸發點**: 機器人啟動時。
*   **行為**: 呼叫 API 取得 `league` 資源，更新快取檔案，並動態設定全域變數供後續使用。

### 3.2 日期驗證邏輯 (bot.py)
當收到指令時，依照 `target_date` 進行以下過濾：

| 條件 | 行為 | 回覆字串 |
| :--- | :--- | :--- |
| `target_date > 今天` | 攔截 | 「我不是未來人，無法提供未來數據」 |
| `target_date < start_date` | 攔截 | 「查無當天數據」 |
| `今天 > end_date` 且 指令為 `#戰績` | 導向 | 自動將 `target_date` 設為 `end_date` |
| `target_date > end_date` 且 `target_date <= 今天` | 攔截 | 「查無當天數據」 |
| 其他情況 | 正常執行 | (數據更新中...) |

## 4. 變更範圍
1.  **`src/fetcher.py`**: 新增 `fetch_league_metadata`。
2.  **`src/cache_utils.py`**: 新增 `load_league_metadata` 與 `save_league_metadata`。
3.  **`src/config.py`**: 移除 `SEASON_START_DATE` 的強制性檢查。
4.  **`bot.py`**:
    *   啟動時更新 Metadata 快取。
    *   在 `handle_message` 實作上述驗證矩陣。
5.  **`league.env`**: 移除 `SEASON_START_DATE` 參數。

## 5. 驗證標準
1. 刪除 `league.env` 中的日期後，機器人仍能啟動。
2. 輸入未來日期，得到「未來人」回覆。
3. 在 2026-04-05 之後輸入 `#戰績`，系統日誌顯示導向至 04-05 並產出最後一天的圖表。
