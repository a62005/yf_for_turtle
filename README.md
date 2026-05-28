# Yahoo Fantasy NBA Scraper AI & LINE Bot

這是一個專門為 Yahoo Fantasy NBA 聯賽設計的實時數據爬蟲與 LINE 機器人。透過結合 Yahoo Fantasy API 與大語言模型（Gemini），為群組提供極速、清爽、視覺化且對稱的極簡風實時戰績、球員與玩家數據查詢。

---

## 🌟 LINE 機器人核心功能 (Core Features)

1. **實時玩家數據查詢**：
   * **指令**：`#玩家 [暱稱]` (例如：`#玩家 玩家A`)
   * **功能**：自動拉取該玩家（Manager）當前目標日期與當週的 9-Cat 數據，支援 FGM/A 與 FTM/A 實時數據解析，並回傳極致對稱的白底極簡風 Flex Message。
2. **球員實時數據查詢**：
   * **指令**：`#球員 [英文名/中文名/別稱]` (例如：`#球員 喇叭`)
   * **功能**：透過大語言模型（LLM）強大的暱稱與別稱解析能力，精準對應至 Yahoo 聯盟中的球員，並回傳其今日最新比賽數據的極簡風 Flex Message。
3. **綜合戰績卡片生成**：
   * **指令**：`#戰績` 系列指令 (支援 `#戰績`、`#戰績昨天`、`#戰績上週`、`#戰績W[週次]`、`#戰績[年月日]`)
   * **功能**：自動計算並生成高質感、簡約奢華白底風格的 9-Cat 數據對決與週次戰績渲染圖片，直接在群組回傳。

---

## ⚙️ 設置與部署 (Setup & Configuration)

### 1. 安裝依賴項
確保您的系統上安裝了 Python 3.10+，並在專案根目錄下執行：
```bash
pip install -r requirements.txt
```

### 2. 配置設定檔 (Configuration Setup)

為了兼顧安全性與便利性，專案將設定拆分為**隱私設定**、**公開設定**與**玩家暱稱映射**三部分：

#### A. 隱私環境變數 (`.env`)
複製 `.env.example` 為 `.env`（此檔案包含敏感金鑰，已被列入 `.gitignore`，**嚴禁提交至 Git**），並填寫以下隱私欄位：
```bash
# Yahoo API 隱私憑證
YAHOO_CLIENT_ID=您的Yahoo_Client_ID
YAHOO_CLIENT_SECRET=您的Yahoo_Client_Secret

# LINE 機器人密鑰
LINE_CHANNEL_SECRET=您的LINE_Channel_Secret
LINE_CHANNEL_ACCESS_TOKEN=您的LINE_Channel_Access_Token

# [選填] 大語言模型與 API 金鑰 (用於球員別稱解析)
# ※ 非必要項目，若不設置則僅停用「#球員」指令，但「#玩家」與「#戰績」等核心功能依然正常運作！
# GEMINI_API_KEY=您的Gemini_API_Key
# GEMINI_MODEL=gemini-3.5-flash

# NGROK 自動 Webhook 對接 (選填，用於本地開發調試)
NGROK_AUTHTOKEN=您的Ngrok_Auth_Token

# [選填] 時令手動覆蓋 (true=強制冬令, false=強制夏令。不設則系統會自動在本地極速判斷)
# IS_WINTER_TIME=true
```

#### B. 公開聯賽配置 (`league.env`)
編輯 `league.env`（此檔案為公開資訊，**會提交至 Git 進行版本控制**），配置您的聯盟公開資訊：
```bash
# Yahoo Fantasy 聯賽 ID (由網址獲取，例如 18457)
LEAGUE_ID=您的聯賽ID

# 玩家暱稱對應檔案路徑
TEAM_MAPPING_FILE=team_mapping.json
```

#### C. 玩家暱稱對應配置 (`team_mapping.json`)
建立或編輯專案根目錄下的 `team_mapping.json`，將 Yahoo 聯賽中的 **隊伍 ID** 與 **玩家的中文暱稱** 進行精準映射。這可以讓 LINE 群組中的使用者直接透過自己的暱稱查詢實時戰績：
```json
{
  "1": "玩家A",
  "2": "玩家B",
  "3": "玩家C",
  "4": "玩家D",
  "5": "玩家E",
  "6": "玩家F"
}
```

### 3. Yahoo OAuth2 授權認證 (Authentication)
第一次啟動時，Yahoo Fantasy SDK 需要進行瀏覽器授權以產生 `oauth2.json`。請依終端機提示的 URL 在瀏覽器中開啟並完成授權。

> ⚠️ **重要安全規範 (CRITICAL SECURITY)**：
> `.env`、`credentials/` 目錄、`.yahoofantasy` 目錄及 `oauth2.json` 檔案嚴禁刪除、修改或覆蓋，其包含重要且私密的授權與認證數據，已被列入安全保護範圍。

### 4. 啟動服務
執行主程式以啟動 LINE Webhook 伺服器：
```bash
python bot.py
```

---

## 🧪 測試驗證 (Testing)

我們擁有高水準的單元測試套件。在進行任何代碼提交前，請執行以下命令以驗證系統穩定性：
```bash
# 設置 PYTHONPATH 並執行全套單元測試
$env:PYTHONPATH="." ; .venv\Scripts\pytest
```

---

## 📅 未來規劃與 TODO (Future & TODO)

* [ ] **智慧即時比賽狀態監控（Smart Live Game Detection）**：
  * **目標**：利用 Yahoo API 中的 `team_remaining_games/total/live_games` 欄位（實時進行中場次），**取代目前 `#戰績` 所採用的「硬性 14:00/15:00 時間限制」**。
  * **邏輯設計**：
    1. 當使用者在下午查詢今日即時戰績（`combined`）時，系統會先向 API 請求 League Scoreboard。
    2. 遍歷全聯盟所有隊伍的 `live_games` 加總。
    3. **若 `live_games > 0`**：代表此時此刻仍有美西比賽正在進行中，今日戰績尚未打完，此時拒絕查詢並提示「`目前有場次正在進行中，請等候今日比賽全部結束後再行查詢。`」。
    4. **若 `live_games == 0` 且 `completed_games > 0`**：代表今日所有美西賽事已經全部打完，數據已完全更新。即使目前尚未達到下午 14:00/15:00，系統也將**直接放行並提供查詢**，極大提升使用者查詢的即時性與靈活性！
