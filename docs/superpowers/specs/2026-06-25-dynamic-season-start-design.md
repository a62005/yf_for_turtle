# 動態開季時間偵測與 LLM 搜尋設計文件

此設計文件定義了 Yahoo Fantasy NBA LINE Bot 移除硬編碼的開季時間（`NEXT_SEASON_START_DATE`），改為結合 Yahoo API 偵測與 LLM 網路搜尋（Google Search Grounding）動態取得開季日期的架構與實作規格。

## 1. 需求背景與目標

目前系統中，開季時間與選秀時間是硬編碼於 `league.env` 檔案中的 `NEXT_SEASON_START_DATE` 環境變數。這種方式在賽季交替、跨年份時需要手動修改設定，維護成本較高。

為了實現「逐步移除硬編碼的 League 資訊」，我們需要：
1.  **移除環境變數**：從 `league.env` 中刪除 `NEXT_SEASON_START_DATE`。
2.  **三階段動態獲取**：
    *   **階段一**：讀取快取 `data/league_metadata.json` 裡的 `next_season_start_date`。
    *   **階段二**：若無快取，但當前 metadata 的 `start_date` 已經是未來的日期（代表已配置新賽季的 `LEAGUE_ID`），則直接將其作為開季時間。
    *   **階段三**：若以上皆無，代表處於休賽季且尚未更換為新 `LEAGUE_ID`。此時嘗試向 Yahoo API 查詢新賽季開賽日期；若 API 尚未提供，則啟動 **LLM 網路搜尋 (Google Search Grounding)** 尋找最新賽季的開季日期，並將其寫回 `league_metadata.json` 進行快取。
    *   **階段四**：若所有管道皆無法取得，則回覆「`🏀 無法獲取新賽季開季時間`」。
3.  **倒數條件優化**：只要當前時間小於開季日期，即允許 `#開季` 指令進行倒數，不受 `is_offseason` 限制。

---

## 2. 核心架構與類別擴充

### 2.1 GeminiProvider 擴充 (啟用 Google 搜尋工具)
修改 `src/llm/gemini.py`，擴充支援 Google 搜尋與 Grounding 功能的 JSON 產生器：

```python
    def generate_json_with_search(self, prompt: str, system_instruction: str = None) -> dict:
        """啟用 Google 搜尋 Grounding 來動態擷取最新的網路資訊，並返回 JSON 格式。"""
        config = {
            "temperature": 0.0,  # 降低溫度以取得精確的事實與日期
            "response_mime_type": "application/json",
            "tools": [{"google_search": {}}]  # 啟用 Google 搜尋
        }
        if system_instruction:
            config["system_instruction"] = system_instruction
            
        client = self._get_client()
        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config
        )
        return json.loads(response.text.strip())
```

### 2.2 LLMAgent 新增開季時間搜尋方法
修改 `src/llm/llm_agent.py`，新增一個呼叫網路搜尋的專屬 API：

```python
    def search_nba_season_start(self, year: int) -> dict:
        """使用 LLM 結合 Google 搜尋，查詢特定年份新賽季的 NBA 官方開季日期。"""
        if not self.provider or not hasattr(self.provider, "generate_json_with_search"):
            return {"success": False, "start_date": None}
            
        prompt = (
            f"請搜尋網路，找出 NBA {year}-{str(year+1)[2:]} 新賽季（或下一個即將開始的賽季）官方公佈的開季日期與時間。"
            "請嚴格回傳 JSON 格式，欄位包含：\n"
            "- 'start_date': 字串，格式必須為 'YYYY-MM-DD HH:MM:SS' (例如 '2026-10-20 08:00:00'，時間若無精確公佈請使用上午8點 '08:00:00')。\n"
            "- 'success': 布林值，代表是否找到該球季精確的官方開季日期。"
        )
        
        try:
            result = self.provider.generate_json_with_search(prompt)
            return result
        except Exception as e:
            logging.error(f"[LLM] 搜尋開季日期失敗: {e}")
            return {"success": False, "start_date": None}
```

---

## 3. 指令處理器優化：`MiscHandler`

修改 `src/handlers/misc_handler.py` 的邏輯：

### 3.1 觸發條件調整
在 `execute` 方法中，移除 `#開季` 的 `is_offseason` 嚴格過濾：
```python
        if user_text == "#開季":
            self._handle_season_start(event, configuration)
```

### 3.2 `_handle_season_start` 實作細節
```python
    def _handle_season_start(self, event: MessageEvent, configuration: Configuration) -> None:
        meta = load_league_metadata() or {}
        today_pacific = get_pacific_date()
        target_time_str = None
        
        # 1. 優先檢查快取中是否有 next_season_start_date
        if "next_season_start_date" in meta:
            target_time_str = meta["next_season_start_date"]
            
        # 2. 檢查目前中繼資料的 start_date 是否為未來的日期（代表已配置新賽季的 LEAGUE_ID）
        if not target_time_str:
            meta_start = meta.get("start_date")
            if meta_start and meta_start > today_pacific:
                target_time_str = f"{meta_start} 08:00:00"
                
        # 3. 啟動 API / LLM 網路搜尋
        if not target_time_str:
            # 嘗試使用 Yahoo API 讀取最新 Game 資訊 (省略具體實作，本處視為嘗試後失敗的 Fallback 流程)
            # 若無，則啟動 LLM 搜尋
            logging.info("[MiscHandler] 啟動 LLM 搜尋新賽季開始時間...")
            from src.llm.llm_agent import LLMAgent
            agent = LLMAgent()
            
            # 推估新賽季的年份：若當前月份大於等於10月，新賽季在明年，否則在今年
            from datetime import datetime
            current_year = datetime.now().year
            nba_year = current_year if datetime.now().month < 10 else current_year + 1
            
            res = agent.search_nba_season_start(nba_year)
            if res.get("success") and res.get("start_date"):
                target_time_str = res["start_date"]
                meta["next_season_start_date"] = target_time_str
                from src.utils.cache_utils import save_league_metadata
                save_league_metadata(meta)
                logging.info(f"[MiscHandler] 成功將 LLM 搜尋到的開季時間寫入快取: {target_time_str}")
                
        # 4. 回覆或倒數
        if not target_time_str:
            self.reply_text(event, configuration, "🏀 無法獲取新賽季開季時間")
            return
            
        countdown_text = self._calculate_countdown(target_time_str)
        if countdown_text == "已經到達！":
            self.reply_text(event, configuration, "🏀 新賽季已經開打囉！")
        else:
            reply_content = f"🏀 距離新賽季開季還有：\n👉 {countdown_text}"
            self.reply_text(event, configuration, reply_content)
```

---

## 4. 測試與驗證策略

使用 `pytest` 撰寫測試以驗證新機制的正確性：
1.  **LLM 搜尋測試**：
    *   撰寫 `tests/test_llm_search.py`，模擬 `GeminiProvider` 的 `generate_json_with_search` 方法回傳 Mock 的搜尋結果 JSON（`{"success": True, "start_date": "2026-10-20 08:00:00"}`），驗證 `LLMAgent.search_nba_season_start` 能正確接收並回傳結果。
2.  **開季指令倒數測試**：
    *   撰寫或修改 `tests/test_misc_handler.py`，模擬當 `league_metadata` 中存有 `next_season_start_date` 時，呼叫 `#開季` 指令是否能正確計算時間並產生倒數回覆。
    *   模擬當 API 與 LLM 皆搜尋失敗時，驗證 `#開季` 應正確回覆「🏀 無法獲取新賽季開季時間」。
