# 設計規範：配置管理重構 (Split Environment Config)

## 1. 背景與目標
目前專案將所有設定（包含聯盟資訊與隱私 TOKEN）統一存放於 `.env`。這導致：
1. 更新非隱私資訊（如聯盟 ID、開賽日期）時，無法透過 Git 同步給所有成員。
2. 成員必須手動修改各自的 `.env`，容易產生配置錯誤。

**目標**：將設定拆分為「聯盟公開設定」與「個人隱私設定」，在保護隱私的同時，提高配置的維護效率。

## 2. 方案架構

### 2.1 檔案拆分
*   **`league.env` (新檔案)**:
    *   **屬性**: 公開設定，**需推送到 Git**。
    *   **包含內容**: 
        *   `LEAGUE_ID`
        *   `SEASON_START_DATE`
        *   `TEAM_MAPPING_FILE`
*   **`.env` (現有檔案)**:
    *   **屬性**: 隱私資訊，**嚴禁推送到 Git** (維持在 `.gitignore`)。
    *   **包含內容**:
        *   `YAHOO_CLIENT_ID`
        *   `YAHOO_CLIENT_SECRET`
        *   `LINE_CHANNEL_SECRET`
        *   `LINE_CHANNEL_ACCESS_TOKEN`
        *   `NGROK_AUTHTOKEN`
        *   `SERVER_URL`

### 2.2 載入邏輯 (src/config.py)
修改 `load_config` 函式，執行以下步驟：
1. 呼叫 `load_dotenv("league.env")` 載入基礎設定。
2. 呼叫 `load_dotenv(".env", override=True)` 載入隱私金鑰。
3. `override=True` 允許開發者在本地 `.env` 中暫時覆蓋 `league.env` 的值而不必修改公開檔案。

## 3. 變更範圍
1.  **`src/config.py`**: 更新 `load_config` 的實作。
2.  **`.gitignore`**: 確認 `league.env` 不被忽略，而 `.env` 與 `.env.example` 維持現狀。
3.  **根目錄**:
    *   建立 `league.env`。
    *   更新 `.env` 內容（移除已移至 `league.env` 的重複項）。
    *   更新 `.env.example` 以反映新的結構。

## 4. 驗證標準
1. 執行 `main.py` 與 `bot.py` 仍能正確讀取到所有變數。
2. `git status` 顯示 `league.env` 為待追蹤檔案，而 `.env` 維持隱藏。
