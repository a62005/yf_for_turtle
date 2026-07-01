# Yahoo Fantasy NBA/MLB Scraper AI & LINE Bot

這是一個專門為 Yahoo Fantasy 聯賽設計的實時數據爬蟲與 LINE 機器人。透過結合 Yahoo Fantasy API 與大語言模型（LLM），為群組提供極速、清爽、視覺化且對稱的極簡風實時戰績、球員、對戰數據與傷兵名單查詢。

本系統目前已全面升級為**多聯盟物理隔離架構**與**白名單管理員安全防護系統**，支援多運動項目（NBA 籃球與 MLB 棒球）以及完全的對話式選單設定。

---

## 🌟 LINE 機器人核心功能 (Core Features)

1. **自然語言意圖解析 (AI Intent Routing)**：
   * **功能**：系統搭載了 AI 意圖路由器。群組成員除了能輸入標準指令外，還可以直接傳送自然語言進行查詢（例如：「查一下 Stephen Curry 昨晚的表現」、「幫我看一下大谷這週對戰比分」）。系統會自動辨識其意圖並對應轉換為正確的標準指令。
   * **隱私與費用保護**：在**群組聊天**中，機器人只有在被 `@BOT` 提及時才會觸發 AI 解析，避免無關的群組閒聊產生 API 成本，並具備智慧型超時過期防護與異常靜默機制。
2. **實時玩家數據查詢**：
   * **指令**：`#玩家`（回傳玩家列表點選）或 `#玩家 [暱稱]`。
   * **功能**：自動拉取該玩家當前目標日期與當週的 9-Cat 數據，支援 FGM/A 與 FTM/A 實時數據解析，並回傳極致對稱的白底極簡風 Flex Message。
3. **實時一對一對戰數據查詢**：
   * **指令**：`#對戰`（回傳玩家列表點選）或 `#對戰 [暱稱]`。
   * **功能**：自動識別該玩家當週的對手，並一次性回傳雙方的 9-Cat 累計數據與即時比分。採用「領先一律黑色較大、落後一律灰色較小」的極致視覺對稱白底 Flex Message 卡片。
4. **球員實時數據查詢**：
   * **指令**：`#球員 [英文名/中文名/別稱]` (例如：`#球員 老詹`、`#球員 大谷`)。
   * **功能**：透過大語言模型強大的暱稱與別稱解析能力，精準對應至 Yahoo 聯盟中的球員，並回傳其今日最新比賽數據的極簡風 Flex Message。
5. **綜合戰績卡片生成**：
   * **指令**：`#戰績` 系列指令 (支援 `#戰績`、`#戰績昨天`、`#戰績上週`、`#戰績W[週次]`、`#戰績[年月日]`)。
   * **功能**：自動計算並生成高質感、簡約奢華亮白底風格的 9-Cat 數據對決與週次戰績渲染圖片，直接在群組回傳。
6. **傷兵名單查詢**：
   * **指令**：`#傷兵`（回傳玩家列表點選）或 `#傷兵 [暱稱]`。
   * **功能**：查詢聯盟中特定玩家目前的傷兵名單（例如處於 IL / IL+ 狀態的球員），並回傳亮白底極致簡約風格的 Flex Message 卡片。
7. **動態 Flex 幫助選單 (Carousel Help Menu)**：
   * **指令**：`#幫助`、`#help`、`#幫忙`、`#更多`。
   * **功能**：系統會自動根據**發送者的權限**，展示權限感知的 Flex 輪播卡片：
     * **一般成員**：看見「聯賽戰績板」、「玩家與對戰」、「聯賽資訊」三張卡片。
     * **白名單管理員**：額外看到第四張「管理員專區」卡片。
     * **未綁定聯盟時**：僅對白名單管理員顯示「管理員專區」卡片（並過濾隱藏「設置暱稱」按鈕），一般群組成員則保持靜默。

---

## ⚙️ 設置與部署 (Setup & Configuration)

### 1. 安裝依賴項

確保您的系統上安裝了 Python 3.10+，並在專案根目錄下執行：

```bash
pip install -r requirements.txt
```

### 2. 配置隱私環境變數 (`.env`)

複製 `.env.example` 為 `.env`（此檔案包含敏感金鑰，已被列入 `.gitignore`，**嚴禁提交至 Git**），並填寫以下欄位：

```env
# Yahoo API 隱私憑證
YAHOO_CLIENT_ID=您的Yahoo_Client_ID
YAHOO_CLIENT_SECRET=您的Yahoo_Client_Secret

# LINE 機器人密鑰
LINE_CHANNEL_SECRET=您的LINE_Channel_Secret
LINE_CHANNEL_ACCESS_TOKEN=您的LINE_Channel_Access_Token

# 大語言模型 (LLM) 設定
LLM_MODEL=gemini-2.5-flash
LLM_API_KEY=您的LLM_API_Key

# 本地伺服器的公開 URL (用於提供獎金圖片給 LINE API 下載)
SERVER_URL=https://您的ngrok域名.ngrok-free.app

# NGROK 自動 Webhook 對接 (選填，用於本地開發調試)
NGROK_AUTHTOKEN=您的Ngrok_Auth_Token

# [選填] 時令手動覆蓋 (true=強制冬令, false=強制夏令)
# IS_WINTER_TIME=true
```

---

## 🛡️ 權限與白名單安全系統

為了防止群組成員任意更動聯賽綁定與設定，系統設有白名單安全機制：
1. **超級管理員 (Super Admin)**：
   * 寫入於 `data/security/super_admin.json`：
     ```json
     { "super_admin": "您的LINE_USER_ID" }
     ```
2. **白名單成員 (Whitelisted Admins)**：
   * 寫入於 `data/security/whitelist.json`：
     ```json
     { "whitelist": ["LINE_USER_ID_1", "LINE_USER_ID_2"] }
     ```
   * 超級管理員可以在群組中透過輸入 `#新增白名單 <LINE_USER_ID>` 來動態增加管理員。一般成員可以透過 `#我的ID` 查詢自己的 LINE User ID。

---

## 📁 多聯盟物理隔離架構 (Multi-League Isolation)

系統支援在不同的 LINE 群組/對話框綁定不同的聯賽，並將所有資料儲存於 `data/league/<sport>/<raw_id>/` 底下，實現物理隔離：

```text
data/league/nba/18457/
├── team_mapping.json         # 該聯賽的玩家暱稱對應表
├── settings.json             # 該聯賽的選秀時間、開季日期等設定
├── oauth2.json               # 該聯賽獨立的 Yahoo API 授權快取
├── .yahoofantasy             # 該聯賽的 API Session 快取
├── metadata.json             # 聯賽 metadata 快取（賽季起迄日、現行週次等）
└── image/
    └── bonus.png             # 聯賽獎金圖片
```

### 憑證繼承機制
第一次部署時，必須先在根目錄下完成一次 Yahoo 登入授權，並將產生的認證檔案存於全域 `credentials/` 資料夾下。
當管理員綁定新聯賽時，系統會**自動從 `credentials/` 中複製繼承種子憑證**，免去新聯賽需要再次開啟瀏覽器進行 OAuth 登入的麻煩。

> ⚠️ **重要安全規範 (CRITICAL SECURITY)**：
> `.env`、`credentials/` 目錄、`.yahoofantasy` 目錄及 `oauth2.json` 檔案嚴禁刪除、修改或覆寫，其包含重要且私密的授權與認證數據，已被列入安全保護範圍。

---

## ⚙️ 管理員選單與對話式 Session 指令 (Admin Commands)

若您是白名單成員，可直接在群組中使用管理員專用指令：

1. **`#設置`（或 `#setting`）**：
   * 回傳高質感的設定 Flex 選單，包含「設置聯盟 ID」、「設置選秀時間」、「設置玩家暱稱」等快速操作按鈕。
2. **`#設置聯盟ID <ID>`**：
   * 綁定該群組的 Yahoo 聯盟 ID 並初始化該聯盟的物理隔離目錄。例如：`#設置聯盟ID nba.l.18457`。
3. **`#設置選秀時間`**：
   * 啟動 60 秒的對話 Session，管理員可直接在對話框輸入任何格式的選秀時間（例如：`今天下午兩點半`、`2026-10-15 19:30`）。系統會調用 LLM 自動解析為標準格式並寫入 `settings.json`。
4. **`#設置玩家暱稱`**：
   * 啟動引導式的對話 Session。系統會秀出隊伍列表，點選後在對話框直接打字，即可動態將該 Yahoo 隊伍與中文暱稱關聯並更新 `team_mapping.json`。
5. **`#移除聯盟ID`**：
   * 解除當前群組與聯賽的綁定關係，並清理該對話框的快取。

---

## 🚀 啟動服務

執行主程式以啟動 LINE Webhook 伺服器與相關 AI 服務：

```bash
python bot.py
```
