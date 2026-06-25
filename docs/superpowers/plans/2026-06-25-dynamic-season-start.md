# 動態開季時間偵測與 LLM 搜尋實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 移除 `league.env` 中硬編碼的 `NEXT_SEASON_START_DATE`，改為自動從 API 或是透過 LLM 網路搜尋 (Google Search Grounding) 動態獲取。

**Architecture:** 
1. 擴充 `BaseLLMProvider` 與 `GeminiProvider` 以支援開啟 Google 搜尋功能的內容生成 API。
2. 擴充 `LLMAgent` 以提供 `search_nba_season_start` 搜尋 NBA 官方新賽季開賽日期。
3. 修改 `MiscHandler` 的 `#開季` 觸發條件（不受 `is_offseason` 限制），並實作三階段動態尋找與快取寫入邏輯。

**Tech Stack:** Python 3, pytest, unittest.mock, google-genai

---

### Task 1: 擴充 BaseLLMProvider 與 GeminiProvider

**Files:**
- Modify: `src/llm/base.py:1-17`
- Modify: `src/llm/gemini.py:1-49`
- Create: `tests/test_llm_search.py`

- [ ] **Step 1: 撰寫 GeminiProvider 網路搜尋功能的單元測試**

在 `tests/test_llm_search.py` 中寫入以下測試：
```python
import pytest
from unittest.mock import MagicMock, patch
from src.llm.gemini import GeminiProvider

def test_gemini_provider_generate_json_with_search():
    provider = GeminiProvider(api_key="dummy_key", model_name="gemini-3.5-flash")
    
    # Mock Client 與 generate_content 方法
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"success": true, "start_date": "2026-10-20 08:00:00"}'
    mock_client.models.generate_content.return_value = mock_response
    
    with patch.object(provider, "_get_client", return_value=mock_client):
        res = provider.generate_json_with_search("test prompt")
        assert res == {"success": True, "start_date": "2026-10-20 08:00:00"}
        
        # 驗證是否有傳入 google_search 工具設定
        args, kwargs = mock_client.models.generate_content.call_args
        assert "tools" in kwargs["config"]
        assert kwargs["config"]["tools"] == [{"google_search": {}}]
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/test_llm_search.py -v`
Expected: FAIL (AttributeError: 'GeminiProvider' object has no attribute 'generate_json_with_search')

- [ ] **Step 3: 修改 BaseLLMProvider 與 GeminiProvider**

首先，在 `src/llm/base.py` 中新增 `generate_json_with_search` 方法作為預設實作（防止不支援的 Provider 出錯）：
```python
    def generate_json_with_search(self, prompt: str, system_instruction: str = None) -> dict:
        """Sends a prompt enabling Google Search and returns a parsed JSON dictionary."""
        raise NotImplementedError("This provider does not support web search grounding.")
```

接著，在 `src/llm/gemini.py` 中實作 `generate_json_with_search`：
```python
    def generate_json_with_search(self, prompt: str, system_instruction: str = None) -> dict:
        """啟用 Google 搜尋 Grounding 來動態擷取最新的網路資訊，並返回 JSON 格式。"""
        config = {
            "temperature": 0.0,
            "response_mime_type": "application/json",
            "tools": [{"google_search": {}}]
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

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_llm_search.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/llm/base.py src/llm/gemini.py tests/test_llm_search.py
git commit -m "feat: extend LLMProvider with search grounding capability"
```

---

### Task 2: 在 LLMAgent 實作 search_nba_season_start 方法

**Files:**
- Modify: `src/llm/llm_agent.py:1-76`
- Create: `tests/test_llm_agent_search.py`

- [ ] **Step 1: 撰寫 LLMAgent 搜尋 NBA 開季日期的單元測試**

在 `tests/test_llm_agent_search.py` 中寫入以下測試：
```python
import pytest
from unittest.mock import MagicMock
from src.llm.llm_agent import LLMAgent

def test_llm_agent_search_nba_season_start_success():
    agent = LLMAgent()
    
    # Mock Provider 支援搜尋且成功回傳
    mock_provider = MagicMock()
    mock_provider.generate_json_with_search.return_value = {
        "success": True, 
        "start_date": "2026-10-20 08:00:00"
    }
    agent.provider = mock_provider
    
    res = agent.search_nba_season_start(2026)
    assert res == {"success": True, "start_date": "2026-10-20 08:00:00"}
    mock_provider.generate_json_with_search.assert_called_once()

def test_llm_agent_search_nba_season_start_unsupported():
    agent = LLMAgent()
    
    # Mock Provider 不支援搜尋方法 (例如空 spec 或是沒有該屬性)
    agent.provider = MagicMock(spec=[])
    
    res = agent.search_nba_season_start(2026)
    assert res == {"success": False, "start_date": None}
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/test_llm_agent_search.py -v`
Expected: FAIL (AttributeError: 'LLMAgent' object has no attribute 'search_nba_season_start')

- [ ] **Step 3: 實作 search_nba_season_start 方法**

在 `src/llm/llm_agent.py` 的 `LLMAgent` 類別中新增以下實作：
```python
    def search_nba_season_start(self, year: int) -> dict:
        """使用 LLM 搭配 Google 搜尋，查詢特定年份/賽季的 NBA 開季日期。"""
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
            import logging
            logging.error(f"[LLM] 搜尋開季日期失敗: {e}")
            return {"success": False, "start_date": None}
```

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/test_llm_agent_search.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/llm/llm_agent.py tests/test_llm_agent_search.py
git commit -m "feat: implement search_nba_season_start in LLMAgent"
```

---

### Task 3: 修改 MiscHandler 開季搜尋與倒數邏輯

**Files:**
- Modify: `src/handlers/misc_handler.py:1-130`
- Create: `tests/handlers/test_misc_handler_season.py`

- [ ] **Step 1: 撰寫開季倒數流程的單元測試**

在 `tests/handlers/test_misc_handler_season.py` 中寫入以下測試：
```python
import pytest
from unittest.mock import MagicMock, patch
from src.handlers.misc_handler import MiscHandler

def test_misc_handler_season_start_flow_cache_hit():
    handler = MiscHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#開季"
    config = MagicMock()
    
    meta = {"next_season_start_date": "2026-10-20 08:00:00"}
    
    with patch("src.handlers.misc_handler.load_league_metadata", return_value=meta), \
         patch.object(handler, "_calculate_countdown", return_value="10 天 5 小時 30 分鐘"):
        handler.execute(event, config)
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "🏀 距離新賽季開季還有：\n👉 10 天 5 小時 30 分鐘"
        )

def test_misc_handler_season_start_flow_llm_search():
    handler = MiscHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#開季"
    config = MagicMock()
    
    meta = {}
    
    with patch("src.handlers.misc_handler.load_league_metadata", return_value=meta), \
         patch("src.handlers.misc_handler.save_league_metadata") as mock_save, \
         patch("src.handlers.misc_handler.LLMAgent") as mock_agent_class, \
         patch.object(handler, "_calculate_countdown", return_value="15 天 1 小時 0 分鐘"):
         
        mock_agent = MagicMock()
        mock_agent.search_nba_season_start.return_value = {
            "success": True, 
            "start_date": "2026-10-20 08:00:00"
        }
        mock_agent_class.return_value = mock_agent
        
        handler.execute(event, config)
        
        mock_agent.search_nba_season_start.assert_called_once()
        mock_save.assert_called_once()
        assert meta["next_season_start_date"] == "2026-10-20 08:00:00"
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "🏀 距離新賽季開季還有：\n👉 15 天 1 小時 0 分鐘"
        )

def test_misc_handler_season_start_all_failed():
    handler = MiscHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#開季"
    config = MagicMock()
    
    meta = {}
    
    with patch("src.handlers.misc_handler.load_league_metadata", return_value=meta), \
         patch("src.handlers.misc_handler.LLMAgent") as mock_agent_class:
         
        mock_agent = MagicMock()
        mock_agent.search_nba_season_start.return_value = {"success": False, "start_date": None}
        mock_agent_class.return_value = mock_agent
        
        handler.execute(event, config)
        
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "🏀 無法獲取新賽季開季時間"
        )
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/handlers/test_misc_handler_season.py -v`
Expected: FAIL (AssertionError: 倒數回覆或呼叫結果不合預期，因尚未修改邏輯)

- [ ] **Step 3: 修改 MiscHandler 邏輯**

修改 `src/handlers/misc_handler.py` 中的 `execute` 方法，解除 `#開季` 的 `is_offseason` 限制：
```python
        if user_text == "#開季":
            self._handle_season_start(event, configuration)
```

接著，重構 `_handle_season_start` 函數，實作三階段動態搜尋：
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
                
        # 3. 啟動 LLM 網路搜尋 (因 Yahoo API 在休賽季不提供未來球季)
        if not target_time_str:
            logging.info("[MiscHandler] 啟動 LLM 搜尋新賽季開始時間...")
            from src.llm.llm_agent import LLMAgent
            agent = LLMAgent()
            
            # 推估新賽季的年份：若當前月份大於等於10月，新賽季在明年，否則在今年
            current_year = datetime.now().year
            nba_year = current_year if datetime.now().month < 10 else current_year + 1
            
            res = agent.search_nba_season_start(nba_year)
            if res.get("success") and res.get("start_date"):
                target_time_str = res["start_date"]
                meta["next_season_start_date"] = target_time_str
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

- [ ] **Step 4: 執行測試確認通過**

Run: `pytest tests/handlers/test_misc_handler_season.py -v`
Expected: PASS

- [ ] **Step 5: 提交變更**

```bash
git add src/handlers/misc_handler.py tests/handlers/test_misc_handler_season.py
git commit -m "feat: implement dynamic season start countdown with LLM fallback in MiscHandler"
```

---

### Task 4: 移除硬編碼環境變數

**Files:**
- Modify: `league.env`
- Test: 全系統測試

- [ ] **Step 1: 移除環境設定中舊的變數**

編輯 `league.env`，刪除以下這一行：
```bash
NEXT_SEASON_START_DATE=2026-10-20 08:00:00
```

- [ ] **Step 2: 執行專案整體單元測試確認功能正常**

Run: `pytest`
Expected: 所有測試皆順利通過 (0 failures)

- [ ] **Step 3: 提交變更**

```bash
git add league.env
git commit -m "chore: remove NEXT_SEASON_START_DATE config from league.env"
```
