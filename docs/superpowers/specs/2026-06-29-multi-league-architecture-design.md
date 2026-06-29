# 多聯盟隔離與綁定架構設計文件

此設計文件定義了 Yahoo Fantasy NBA LINE Bot 中實作「多聯盟綁定與隔離架構」的設計與技術規格，使單一 LINE Bot 實例能被多個群組/個人聊天室獨立綁定並使用不同的聯賽資料。

## 1. 需求與目標

1. **聊天室級別綁定**：每個 LINE 群組、房間或個人對話室（以下統稱 `chat_id`）皆可獨立綁定一個 Yahoo Fantasy 聯賽 ID (`LEAGUE_ID`)。不同聊天室若綁定同一個聯賽 ID，則共享該聯賽的配置（如暱稱、選秀時間等）。
2. **未綁定安全防護（靜默）**：若聊天室尚未綁定聯賽 ID，則除了**白名單用戶的 `#設置`** 與**所有用戶的 `#我的ID`** 以外，輸入其他任何指令或發言，系統皆必須保持完全靜默，不予回覆。
3. **環境變數解耦**：不再使用全域環境變數中的 `LEAGUE_ID` 作為未綁定聊天室的預設值（即未綁定就是 `None`）。
4. **Yahoo API 無權限防護**：當 Bot 在獲取未授權的聯賽資訊（例如未將 Bot 的 Yahoo 帳號加入該私有聯賽，而導致 `YahooFantasy API 401/403` 或其他異常）時，能友善回覆錯誤提示。
5. **無破壞性重構**：現有 20 多個調用 `load_config()` 的地方必須保持不變，藉由 Python 上下文管理器實作無感知的隔離。

---

## 2. 核心架構與資料流設計

### 2.1 執行緒安全上下文管理 (ContextVars)
在 `src/config.py` 中，我們將使用 `contextvars` 儲存當前 Webhook Request 的 `chat_id` 上下文。這能讓底層的 `load_config()` 在不改變任何參數簽名的情況下，自動獲得當前對話室的脈絡資訊：

```python
from contextvars import ContextVar
current_chat_id: ContextVar[str | None] = ContextVar("current_chat_id", default=None)
```

在 [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py) 中，於事件處理入口攔截並填入：
```python
chat_id = (event.source.group_id if event.source.type == "group" 
           else event.source.room_id if event.source.type == "room" 
           else event.source.user_id)

token = current_chat_id.set(chat_id)
try:
    intent_router.route(event, configuration)
finally:
    current_chat_id.reset(token)
```

### 2.2 聊天室聯盟對應表 (`chat_league_mapping.json`)
聊天室的綁定對應表將被寫入物理磁碟以求持久化：
* **檔案路徑**：`data/security/chat_league_mapping.json`
* **資料範例**：
  ```json
  {
    "C1234567890abcdef1234567890abcdef": "18457",
    "Uabcdef1234567890abcdef1234567890": "67890"
  }
  ```

### 2.3 配置加載重構
重構 `src/config.py` 的 `load_config`：
```python
def load_config() -> dict:
    chat_id = current_chat_id.get()
    league_id = None
    
    # 1. 讀取 chat_league_mapping.json 對應
    if chat_id:
        mapping_file = os.path.join(BASE_DIR, "data", "security", "chat_league_mapping.json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    mapping = json.load(f)
                    league_id = mapping.get(chat_id)
            except Exception:
                pass

    # 2. 如果讀到了有效的 league_id，加載其 settings.json 中自訂的 DRAFT_DATE 與 next_season_start_date
    draft_date = os.getenv("DRAFT_DATE")
    next_season_start_date = os.getenv("NEXT_SEASON_START_DATE")
    
    if league_id:
        settings_file = os.path.join(BASE_DIR, "data", "league", league_id, "settings.json")
        if os.path.exists(settings_file):
            try:
                with open(settings_file, "r", encoding="utf-8") as f:
                    s_data = json.load(f)
                    draft_date = s_data.get("DRAFT_DATE") or draft_date
                    next_season_start_date = s_data.get("next_season_start_date") or next_season_start_date
            except Exception:
                pass

    return {
        "LEAGUE_ID": league_id,
        "DRAFT_DATE": draft_date,
        "NEXT_SEASON_START_DATE": next_season_start_date,
        # ... 其它環境變數 ...
    }
```

---

## 3. 路由與防護攔截規則 ([intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/intent_router.py))

### 3.1 靜默過濾邏輯
修改 `IntentRouter.should_process` 方法：
1. **未綁定狀態判定**：
   * 當 `load_config()["LEAGUE_ID"] is None`：
     * **僅放行**：用戶輸入 `#設置`、`#我的ID`，或指令字串以 `#設置聯盟ID` 開頭的請求，以及現存活動中的選秀/暱稱修改會話。
     * **靜默拒絕**：其餘所有指令（如 `#開季`、`#戰績`、`#選秀`）以及所有自然語言訊息一律直接回傳 `False`。
2. **已綁定狀態**：依原邏輯處理。

### 3.2 意圖路由調整
* 由於在未綁定時只受理 `#設置` 指令，點擊後觸發 `SettingsHandler`。
* `SettingsHandler` 偵測到 `LEAGUE_ID is None` 時，自動產生「系統初始化設置」Flex 卡片，上面僅有「設置聯盟 ID」單一按鈕。
* 用戶點擊後發送 `#設置聯盟ID` 指令，開啟對話會話，由 `SetLeagueIdHandler` 接收。

---

## 4. 聯盟綁定與異常捕捉實作

### 4.1 綁定邏輯變更 ([set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py))
`SetLeagueIdHandler` 在使用者輸入聯賽 ID 時，進行以下變更：
* 不再寫入全域 `league_config.json`，而是讀取、合併並寫入 `data/security/chat_league_mapping.json`。
* 寫入格式為：`{ current_chat_id: 新聯盟ID }`。
* 設定成功後，清除會話，回覆：「`✅ 成功將此聊天室綁定至聯賽 ID：[新聯盟ID]`」。

### 4.2 API 讀取無權限異常捕捉 ([fetcher.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/fetcher.py))
在與 Yahoo Fantasy API 串接的入口（例如 `yahoofantasy.League` 的實例化與請求處）或指令 Handler 的資料拉取處加入 Exception 捕捉：
* **捕捉異常**：若發生與 Yahoo 授權相關的 `401 Unauthorized`、`403 Forbidden` 或 `YahooFantasy` 讀取私有聯賽出錯的異常。
* **友好提示回覆**：回覆「`⚠️ 機器人 Yahoo 帳號目前無權限存取此聯盟。請確保已將機器人的 Yahoo 帳號邀請為該聯盟的成員或 Co-manager。`」而非直接崩潰或靜默。

---

## 5. 單元測試規劃

1. **上下文隔離測試**：
   * 模擬將不同的 `chat_id` 寫入 `current_chat_id`。
   * 驗證 `load_config()` 對應返回各自獨立的 `LEAGUE_ID`。
2. **未綁定靜默測試**：
   * 模擬 `LEAGUE_ID is None`。
   * 驗證輸入 `#開季`、`#戰績` 及普通自然語言時，`should_process` 均回傳 `False`。
   * 驗證輸入 `#設置`、`#我的ID` 時，`should_process` 回傳 `True`。
3. **聯盟綁定測試**：
   * 模擬在群組中呼叫 `#設置聯盟ID 99999`，驗證 `chat_league_mapping.json` 正確記錄 `{ "群組ID": "99999" }`。
4. **授權錯誤捕捉測試**：
   * 模擬 Yahoo API 回傳 401/403 授權失敗。
   * 驗證指令 Handler 能捕捉並回覆給 LINE 使用者友好的說明訊息。
