# 設計規範：啟動優化與查詢規則調整 (Startup & Query Rule Refinement)

## 1. 背景與目標
- **Port 佔用問題**：`bot.py` 啟動時常因 5001 Port 被殘留進程佔用而失敗。
- **查詢限制過嚴**：目前所有查詢皆有 14:00 的時間限制，應在休賽季期間解除此限制。

## 2. 實作細節

### 2.1 Port 自動清理邏輯 (bot.py)
在 `if __name__ == "__main__":` 區塊最上方新增 `cleanup_port(port)`：
*   使用 `psutil` 找出佔用 5001 的 PID 並終止它。
*   此步驟為啟動前置檢查。

### 2.2 休賽季時間閘調整 (bot.py)
修改 `handle_message` 中的時間門檻檢查：
*   定義 `is_offseason = today_pacific > meta['end_date']`。
*   修改判斷式：
    ```python
    # 邏輯：在賽季內且未到 14:00 時才攔截
    if is_current and not is_offseason and get_tw_hour() < 14:
        # 回覆「請於 14:00 後查詢」
    ```

## 3. 驗證標準
1. **Port 清理**：觀察啟動日誌是否顯示自動殺掉舊進程。
2. **休賽季查詢**：在休賽季期間，任何時段查詢都不會觸發「請於 14:00 後查詢」的限制。
