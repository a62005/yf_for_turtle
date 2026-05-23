# Bot Handler Decoupling Design

## 1. 架構概述 (Architecture Overview)

為了讓系統具備高擴充性與易維護性，將 LINE Bot 的接收層與業務邏輯層進行解耦，採用三層式架構 (3-Tier Architecture) 結合命令模式 (Command Pattern) 的變體。

1. **第一層 (Entry Point)**: `bot.py`，作為系統進入點，專注於伺服器掛載與基礎條件過濾 (僅攔截 `#` 開頭的訊息)。
2. **第二層 (Dispatcher)**: `CommandDispatcher`，作為訊息路由器，負責管理與分派任務給對應的領域處理器。
3. **第三層 (Domain Handlers)**: `StatsHandler`, `PrizeHandler` 等，負責執行實際的業務邏輯。

## 2. 元件職責 (Components)

### 2.1 `bot.py`
- **職責**: 負責 Flask App 生命週期、ngrok 代理設定、LINE Webhook 驗證。
- **改動**: 移除所有正則表達式、日期邏輯、快取邏輯與子行程觸發邏輯。
- **邏輯**: 在 `handle_message` 事件中，判斷 `event.message.text.startswith("#")`，若是，則將 `event` 傳遞給 `CommandDispatcher`。

### 2.2 `src/handlers/dispatcher.py` (`CommandDispatcher`)
- **職責**: 管理註冊的 Handler，進行命令路由。
- **邏輯**: 
  - 內部維護一個 Handler 列表 (例如 `[StatsHandler(), ...]`)。
  - 提供 `handle(event, configuration)` 方法。
  - 遍歷列表，呼叫每個 Handler 的 `can_handle(text)`。
  - 若找到匹配的 Handler，則呼叫其 `execute(event, configuration)` 並結束路由。
  - 若無匹配，則忽略或可選地記錄警告。

### 2.3 `src/handlers/base_handler.py` (`BaseHandler`)
- **職責**: 定義所有 Handler 的標準介面 (Interface)。
- **方法**:
  - `can_handle(user_text: str) -> bool`: 判斷該 Handler 是否能處理此字串。
  - `execute(event, configuration) -> None`: 執行核心業務邏輯，並透過 `configuration` 建立 `ApiClient` 進行回覆。

### 2.4 `src/handlers/stats_handler.py` (`StatsHandler`)
- **職責**: 處理所有戰績相關指令 (`#戰績`, `#戰績20250101`, `#戰績W23`, `#當天戰績` 等)。
- **邏輯**: 
  - 繼承 `BaseHandler`。
  - 將原 `bot.py` 中的 `parse_command` 邏輯與正則表達式移入此處的 `can_handle` 與內部解析。
  - 在 `execute` 中實作時間閘門、快取讀取、鎖定判斷以及 `subprocess.Popen("main.py")` 背景任務觸發。
  - 直接處理 LINE API 的回覆動作。

## 3. 資料流 (Data Flow)

1. 使用者在 LINE 發送訊息 `#戰績W23`。
2. LINE Server 發送 Webhook 至 `bot.py`。
3. `bot.py` 驗證 Token 後，確認字串以 `#` 開頭，呼叫 `dispatcher.handle(event, configuration)`。
4. `CommandDispatcher` 詢問 `StatsHandler` 能否處理 `#戰績W23`。
5. `StatsHandler.can_handle()` 解析正則表達式並回傳 `True`。
6. `CommandDispatcher` 呼叫 `StatsHandler.execute(event, configuration)`。
7. `StatsHandler` 檢查快取、日期限制。若需更新，回覆「數據更新中」，並產生子行程執行 `main.py`。

## 4. 錯誤處理 (Error Handling)

- **無效指令**: 若訊息以 `#` 開頭但沒有 Handler 認領，Dispatcher 將直接 return，不中斷伺服器，避免騷擾用戶。
- **Handler 崩潰**: Dispatcher 的 `handle` 方法可加入 `try-except` 區塊，若單一 Handler 執行發生例外，可記錄 Error Log，確保 `bot.py` Webhook 仍能回應 HTTP 200 給 LINE Server。

## 5. 測試策略 (Testing)

- 確保原有的 E2E 測試 (`test_client_e2e.py`) 在重構後依然能順利攔截並產出相同的回應與背景指令。
- 新增/修改單元測試，獨立驗證 `CommandDispatcher` 的路由正確性，以及 `StatsHandler` 對各種指令的解析能力。