# NBA 球員模糊搜尋與單場數據查詢設計規格書 (Spec)

本規格書詳細記錄了如何透過 LINE Bot 指令 `#球員 <稱呼>`，利用 LLM (Gemini API) 模糊解析現役 NBA 球員，並自動串接 Yahoo Fantasy API 獲取其最新單場數據之設計。

---

## 1. 核心目標 (Goal)
- **模糊容錯**：使用者可輸入模糊綽號（如「喇叭」、「萌神」、「Curry」、「77」），透過 LLM 精準對應至現役球員官方英文名。
- **僅限現役**：嚴格過濾已退休球員，防止後續 Yahoo Fantasy API 查無當季數據。
- **當天單場數據**：回傳該球員**美西查詢當天**的實際單場數據（非賽季平均），若當天無比賽，則回覆「該球員今日無比賽數據」，不進行多日回溯。
- **時區跨日處理**：以**台北時間早上 07:00 (NBA每日開賽點)** 作為美國跨日切換點，確保 24 小時內任何時間（包含晚上 18:00）查詢都能穩定獲得正確的單場數據。
- **休賽季測試友善**：在休賽季期間直接以**賽季最後一天 (League End Date)** 作為目標日期，確保開發與測試順暢。
- **排版整齊**：指標靠左、數值靠右，在 LINE 聊天室中呈現英文 9-Cat 排版。
- **高效能與省 Token**：使用本地快取 JSON 檔案，避免重複解析相同綽號。

---

## 2. 系統架構與元件設計 (Architecture)

### A. 新增 `PlayerHandler`
- **路徑**：`src/handlers/player_handler.py` (繼承 `BaseHandler`)
- **職責**：
  1. 解析指令 `^#球員\s+(.+)$`。
  2. 檢查本地快取，存在則直接提取 `player_key`。
  3. 不存在快取則呼叫 Gemini API 進行語意解析，再透過 Yahoo API 取得 `player_key` 並寫入快取。
  4. 根據「台北時間 07:00 跨日邏輯」計算出目標美西日期。
  5. 呼叫 Yahoo API 取得該球員在目標美西日期的單場數據。
  6. 格式化輸出並發送 LINE 回覆。

### B. 快取機制 (`data/player_mapping_cache.json`)
- 用於儲存「輸入綽號 -> 官方解析資料與 ID」的對照表，避免每次查詢都消耗 LLM Token 與多次 API 往返。
- 格式範例：
  ```json
  {
    "喇叭": {
      "english_name": "LeBron James",
      "chinese_name": "勒布朗·詹姆斯",
      "team": "Los Angeles Lakers",
      "jersey_number": "23",
      "player_key": "nba.p.3704"
    }
  }
  ```

---

## 3. LLM 提示詞與 JSON Schema 設計 (Gemini API)

### A. 系統提示詞 (System Prompt)
```text
你是一個精準的 NBA 籃球專家，專門負責將使用者的模糊輸入（例如球員綽號、簡稱、中文音譯或背號加上球隊）解析為官方標準的現役球員資訊。

請遵循以下嚴格規則：
1. 僅識別真實存在的 NBA 「現役球員 (Active Players)」。如果球員已退休，請將 is_known_player 設為 false。
2. 對於常見的中文或英文綽號，你必須精準對應，例如：
   - "喇叭", "LBJ", "老漢", "詹皇" -> LeBron James
   - "咖哩", "萌神", "廚師" -> Stephen Curry
   - "死神", "KD" -> Kevin Durant
   - "字母哥" -> Giannis Antetokounmpo
   - "77", "胖虎" -> Luka Doncic
3. 如果輸入是完全無意義、非籃球球員、或非現役球員的字詞（例如 "喬丹", "科比", "哈囉", "測試"），你必須將 is_known_player 設為 false，並拒絕胡亂臆測。
4. 必須以指定的 JSON 格式回傳，不要包含 any 額外的說明、Markdown 標記或 ```json 包裹。
```

### B. 強制輸出之 Response Schema (JSON)
```json
{
  "is_known_player": true,
  "english_name": "LeBron James",
  "chinese_name": "勒布朗·詹姆斯",
  "team": "Los Angeles Lakers",
  "jersey_number": "23",
  "confidence": 1.0,
  "reason": "成功將綽號'喇叭'解析為現役球員 LeBron James"
}
```

---

## 4. 數據查詢與時區/休賽季邏輯 (精準定義「當天」)

為了精確對應 NBA 比賽在美西與台北的跨日時間差，我們使用**台北時間早上 07:00 (通常為每日首場比賽開打時間)** 作為美西日期的切換分界點。

### A. 非休賽季 (賽季中) 查詢日期計算邏輯
1. 取得當前的**台北日期**與**台北小時**（`Asia/Taipei` 時區）。
2. **判斷美西目標日期**：
   * **若台北時間在 07:00 或是 07:00 以後（Hour >= 7）**：
     * 這代表目前正在進行或剛剛完成的是該輪美西比賽。
     * 目標美西日期 = `台北日期 - 1 天`。
     * *(例如：台北時間 11/11 晚上 18:00 查詢 $\rightarrow$ 大於 07:00 $\rightarrow$ 目標美西日期為 11/10)*
     * *(例如：台北時間 11/12 早上 10:00 查詢 $\rightarrow$ 大於 07:00 $\rightarrow$ 目標美西日期為 11/11)*
   * **若台北時間在 07:00 以前（Hour < 7，例如凌晨 02:00）**：
     * 這代表今天早上的新比賽尚未開始，最新完成的依然是前一天的美西比賽。
     * 目標美西日期 = `台北日期 - 2 天`。
     * *(例如：台北時間 11/12 凌晨 02:00 查詢 $\rightarrow$ 小於 07:00 $\rightarrow$ 目標美西日期為 11/10)*
3. **無比賽處理**：
   * 用計算出的目標美西日期呼叫：`GET player/{player_key}/stats;type=date;date=YYYY-MM-DD`。
   * 如果數據中 `MIN` (出場時間) 或 `PTS` (得分) 為 0 或不存在，代表該球員在目標日期**沒有上場比賽**，系統直接回覆「該球員今日無比賽數據」，不進行多日回溯。

### B. 休賽季測試邏輯 (Off-season Override)
1. 當系統偵測目前為休賽季（即 `台北日期 > 賽季結束日期`），則直接**繞過**上述 07:00 判斷。
2. 將目標日期強制鎖定在**該賽季的最後一天 (League End Date)** 進行數據拉取，確保在休賽季期間測試時，依然能成功查詢到球員在賽季收官戰的單場真實數據。

---

## 5. LINE 訊息排版格式 (Layout)

訊息排版將全面採用英文指標，標題靠左對齊，數值靠右對齊（使用 Python 靠右對齊格式化）：

```text
LeBron James (勒布朗·詹姆斯)
Los Angeles Lakers#23
-----------------------
FGM/A :           14/24
FG% :             58.3%
FTM/A :             3/4
FT% :             75.0%
3PM :                 4
PTS :                35
REB :                 9
AST :                12
STL :                 2
BLK :                 1
TO :                  3
```

---

## 6. 驗證與測試計畫 (Verification)

### A. 自動測試 (Automated Tests)
- 撰寫單元測試覆蓋 07:00 分界邏輯，確保在台北時間 06:59 與 07:01 分別產出正確的美西查詢目標日期。
- Mock 測試休賽季覆寫行為，驗證是否正確導向 `League End Date`。
- Mock 測試 Yahoo API 當天無數據時的處理邏輯。

### B. 手動驗證 (Manual Verification)
- 於 LINE 實際輸入 `#球員 喇叭`：
  - 休賽季期間：驗證是否回傳賽季最後一日（2026-04-12 前後）LeBron James 的單場 9-Cat 數據，且格式對齊無誤。
- 輸入 `#球員 喬丹` 驗證是否會觸發「找不到此現役球員」的友善錯誤訊息。
