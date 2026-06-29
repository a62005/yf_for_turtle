# 設置選選單與多聯盟目錄隔離設計文件

此設計文件定義了 Yahoo Fantasy NBA LINE Bot 實現動態配置 `LEAGUE_ID`（使用 `#設置` 與 `#設置聯盟ID`）以及將聯賽設定、快取、圖片進行多聯賽目錄隔離（`data/league/<LEAGUE_ID>/`）的架構與實作規格。

## 1. 需求背景與目標

為了能動態在 LINE 中切換與新增不同的 Yahoo Fantasy 聯賽，且不造成各聯賽快取、圖片、隊伍暱稱的互相干擾，我們需要將聯賽設定與快取完全以 `LEAGUE_ID` 為基礎進行目錄物理隔離。
同時，提供一個限白名單成員存取的 `#設置` Flex 選單，實作輕量化的動態聯盟註冊流程。

具體目標：
1.  **容錯啟動**：若無 `LEAGUE_ID` 配置，Bot 仍可正常啟動，不拋出 Crash 錯誤。
2.  **優先動態覆蓋**：優先從 `data/security/league_config.json` 加載配置覆蓋環境變數。
3.  **多聯賽目錄隔離**：所有聯賽相關資料（快取、暱稱、圖片）均儲存於 `data/league/<LEAGUE_ID>/` 中。
4.  **設置選單與驗證**：
    *   `#設置` 返回 Flex 選單。未配置聯盟 ID 時僅開放 `設置聯盟ID`；已配置時則全部按鈕設為「未開放/即將推出」（不可點擊）。
    *   `#設置聯盟ID <ID>` 動態驗證。若 Yahoo API 同步失敗則拒絕寫入。
5.  **舊快取清理**：徹底刪除舊路徑下的重疊設定檔與快取，避免新舊檔案混淆。

---

## 2. 聯賽資料目錄重構與路徑輔助

新增路徑輔助模組 `src/utils/path_utils.py`，統一輸出聯賽路徑：

```python
import os

# 專案根目錄 C:\Users\HsiehLink\Python\yf_for_turtle
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def get_league_id() -> str | None:
    """動態獲取當前配置的聯盟 ID，優先從 JSON 載入，否則從環境變數載入。"""
    from src.config import load_config
    return load_config().get("LEAGUE_ID")

def get_league_dir(league_id: str = None) -> str:
    lid = league_id or get_league_id() or "default"
    return os.path.join(BASE_DIR, "data", "league", str(lid))

def get_league_metadata_path(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "metadata.json")

def get_league_empty_records_path(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "empty_records.json")

def get_league_team_mapping_path(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "team_mapping.json")

def get_league_image_dir(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "image")

def get_league_daily_dir(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "daily")

def get_league_weekly_dir(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "weekly")
```

---

## 3. 核心實作變更點

### 3.1 容錯啟動與配置覆蓋 ([config.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/config.py))
*   `load_config()` 將嘗試讀取 `data/security/league_config.json`。若有 `LEAGUE_ID` 欄位，則覆蓋 `os.getenv("LEAGUE_ID")`。
*   若均無配置，將 `LEAGUE_ID` 設為 `None` 並回傳配置，**不拋出 ValueError**。

### 3.2 啟動流程修改 ([bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py))
在啟動 `__main__` 時，先檢查 `LEAGUE_ID`：
*   若存在，則初始化 `YahooFantasyFetcher` 與同步 `sync_season_metadata`。
*   若無，則輸出 Log 警示跳過，容許伺服器空載啟動以等待 LINE 指令設置。
*   Flask `/images/<path:filename>` 路由修改為從對應的 `get_league_image_dir()` 下讀取圖片提供下載。

### 3.3 `fetcher.py` 自訂數據快取重構 ([fetcher.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/fetcher.py))
*   **重構 `fetch_weekly_stats`**：使用 `get_league_weekly_dir()`，自訂讀寫 `week_<WEEK>.json`。
*   **重構 `fetch_daily_stats`**：使用 `get_league_daily_dir()`，自訂讀寫 `date_<DATE>.json`。
*   兩者均使用 `self.ctx.make_request(url)` 發送 API 請求，不再依賴 `_load_or_fetch` 私有快取。

### 3.4 設置指令處理器 `SettingsHandler` 變更 ([settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py))
*   權限標記：`requires_whitelist = True`
*   行為：
    *   讀取當前 `LEAGUE_ID`，並呼叫 `build_button_menu_card` 建立 Flex 選單。
    *   **無聯盟 ID**：僅顯示一個可點擊的按鈕 `設置聯盟ID`（發送 `#設置聯盟ID `）。
    *   **有聯盟 ID**：顯示多個「未開放/即將推出」之灰色、無點擊事件之按鈕（設置選秀時間、設置玩家暱稱、更換聯盟ID、移除聯盟ID）。

### 3.5 新建 `SetLeagueIdHandler` ([set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py))
*   權限標記：`requires_whitelist = True`
*   比對指令：`^#設置聯盟ID\s+(\d+)$`
*   行為：
    1.  建立臨時 Fetcher，呼叫 `sync_season_metadata(fetcher, target_id)`。
    2.  **若同步成功**：
        - 寫入 `data/security/league_config.json`。
        - 若 `data/league/<target_id>/team_mapping.json` 不存在，則初始化為 `{}`。
        - 回覆：「`✅ 聯盟 ID 設置成功，並已完成賽季資訊同步！`」
    3.  **若同步失敗**：
        - 拒絕寫入。
        - 回覆：「`⚠️ 設置失敗，無法從 Yahoo 獲取該聯盟資訊，請確認 ID 是否正確。`」

---

## 4. 舊快取清理作業

在實作計畫的首要任務中，我們將刪除以下舊位置檔案以避免混淆：
1.  `data/empty_records.json`
2.  `data/league_metadata.json`
3.  專案根目錄的 `team_mapping.json`
4.  `data/images/` 目錄下所有以 `_combined.png` 結尾的舊戰績圖片（保留靜態獎金圖 `bonus.png`）。

---

## 5. 測試策略

1.  **路徑輔助模組測試**：
    *   測試 `get_league_dir()` 等路徑能隨 `LEAGUE_ID` 的變化返回正確目錄。
2.  **容錯啟動測試**：
    *   模擬無 `LEAGUE_ID` 狀態，驗證 `load_config()` 與 `bot.py` 啟動不拋出 ValueError。
3.  **自訂快取測試**：
    *   驗證 `fetcher.fetch_weekly_stats` 能正確將結果寫入 `weekly/week_<WEEK>.json`。
4.  **設置選單與設定測試**：
    *   測試在無 `LEAGUE_ID` 下發送 `#設置`，回覆之選單是否僅有 `設置聯盟ID` 動作。
    *   測試 `#設置聯盟ID <ID>` 的同步成功與失敗之回覆斷言。
