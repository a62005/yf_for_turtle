# 2026-06-16 世界盃臨時功能：足球對戰分析實作計畫 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 LINE Bot 指令 `#足球 <球隊A> <球隊B>`，在啟用環境變數開關時，利用 Gemini 3.5 Flash 進行 200 字左右的專業對戰分析。

**Architecture:**
- 修改 [src/config.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/config.py) 以讀取 `ENABLE_FOOTBALL_ANALYSIS`。
- 新建 [src/utils/football_analyzer.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/football_analyzer.py) 用於呼叫 Gemini API 進行專業足球對賽分析。
- 新建 [src/handlers/football_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/football_handler.py) 繼承 `BaseHandler` 以處理 `#足球` 指令與開關邏輯。
- 修改 [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py) 註冊新 Handler。

---

## 預計新增與修改之檔案結構
- **修改** [src/config.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/config.py) (載入開關設定)
- **新建** [src/utils/football_analyzer.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/football_analyzer.py) (對戰分析器)
- **新建** [src/handlers/football_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/football_handler.py) (指令處理器)
- **新建** [tests/test_football_analyzer.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_football_analyzer.py) (分析器單元測試)
- **新建** [tests/test_football_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_football_handler.py) (處理器單元測試)
- **修改** [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py) (註冊處理器)

---

### Task 1: 配置與 LLM 分析工具開發

**Files:**
- Modify: [src/config.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/config.py)
- Create: [src/utils/football_analyzer.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/football_analyzer.py)
- Test: [tests/test_football_analyzer.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_football_analyzer.py)

- [ ] **Step 1: 修改 `src/config.py` 載入 `ENABLE_FOOTBALL_ANALYSIS`**
  
  在 [src/config.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/config.py) 的 `load_config()` 字典中新增：
  ```python
  "ENABLE_FOOTBALL_ANALYSIS": os.getenv("ENABLE_FOOTBALL_ANALYSIS", "False").lower() in ("true", "1", "yes")
  ```

- [ ] **Step 2: 撰寫 `football_analyzer` 單元測試 (TDD 失敗測試)**
  
  建立 [tests/test_football_analyzer.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_football_analyzer.py)：
  ```python
  import pytest
  from unittest.mock import MagicMock
  from src.utils.football_analyzer import analyze_football_matchup

  def test_analyze_football_matchup_success(mocker):
      mock_model = MagicMock()
      mock_response = MagicMock()
      mock_response.text = "這是一份專業的對戰分析。巴西實力略勝一籌，但德國防守堅韌，預計會是一場激烈的對決。"
      mock_model.generate_content.return_value = mock_response
      
      mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
      
      res = analyze_football_matchup("巴西", "德國", api_key="dummy_key")
      assert "巴西" in res
      assert "德國" in res

  def test_analyze_football_matchup_missing_key():
      res = analyze_football_matchup("巴西", "德國", api_key="")
      assert "API Key" in res or "金鑰" in res or "未設定" in res
  ```

- [ ] **Step 3: 執行測試確認失敗**
  
  執行：`pytest tests/test_football_analyzer.py -v`
  期望：FAIL，顯示 `ModuleNotFoundError: No module named 'src.utils.football_analyzer'`。

- [ ] **Step 4: 實作 `src/utils/football_analyzer.py`**
  
  建立 [src/utils/football_analyzer.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/football_analyzer.py)：
  ```python
  import os
  import logging
  import google.generativeai as genai

  SYSTEM_PROMPT = """你是一個專業的足球分析員。
  請針對使用者提供的兩支足球隊伍進行專業的對戰分析。
  請遵循以下嚴格限制：
  1. 必須結合你所知道的最新足球數據與資訊進行分析（例如兩隊的實力對比、球星陣容、近期狀態等）。
  2. 不要報導或引用新聞，請完全根據你自己的專業足球知識進行獨立分析。
  3. 分析內容大約在 200 字左右，字數不可過長，使用繁體中文。
  4. 不要包含額外的 Markdown 標題或多餘的引言，直接給出分析內容。"""

  def analyze_football_matchup(team_a: str, team_b: str, api_key: str = None, model_name: str = None) -> str:
      key = api_key or os.getenv("GEMINI_API_KEY")
      model_to_use = model_name or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
      
      if not key:
          logging.error("Gemini API key is not configured for football analysis.")
          return "Gemini API 金鑰尚未設定，無法進行足球對戰分析。"
      
      try:
          genai.configure(api_key=key)
          model = genai.GenerativeModel(
              model_name=model_to_use,
              system_instruction=SYSTEM_PROMPT
          )
          
          prompt = f"請為以下兩支球隊進行對戰分析：{team_a} vs {team_b}"
          response = model.generate_content(prompt)
          return response.text.strip()
      except Exception as e:
          logging.error(f"Gemini API football analysis failed: {e}")
          return f"系統繁忙，目前無法取得 {team_a} 與 {team_b} 的分析，請稍後再試。"
  ```

- [ ] **Step 5: 執行測試確認通過**
  
  執行：`pytest tests/test_football_analyzer.py -v`
  期望：PASS。

---

### Task 2: 足球對戰指令處理器開發

**Files:**
- Create: [src/handlers/football_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/football_handler.py)
- Test: [tests/test_football_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_football_handler.py)

- [ ] **Step 6: 撰寫 `football_handler` 單元測試 (TDD 失敗測試)**
  
  建立 [tests/test_football_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_football_handler.py)：
  ```python
  import pytest
  from unittest.mock import MagicMock
  from src.handlers.football_handler import FootballHandler

  def test_can_handle_enabled_and_matching(mocker):
      # Mock load_config to return ENABLE_FOOTBALL_ANALYSIS=True
      mocker.patch("src.handlers.football_handler.load_config", return_value={"ENABLE_FOOTBALL_ANALYSIS": True})
      handler = FootballHandler()
      
      assert handler.can_handle("#足球 巴西 德國") is True
      assert handler.can_handle("#足球 巴西vs德國") is True
      assert handler.can_handle("#足球 巴西 對 德國") is True
      assert handler.can_handle("#對戰 肥儒") is False

  def test_can_handle_disabled(mocker):
      # Mock load_config to return ENABLE_FOOTBALL_ANALYSIS=False
      mocker.patch("src.handlers.football_handler.load_config", return_value={"ENABLE_FOOTBALL_ANALYSIS": False})
      handler = FootballHandler()
      
      assert handler.can_handle("#足球 巴西 德國") is False
  ```

- [ ] **Step 7: 執行測試確認失敗**
  
  執行：`pytest tests/test_football_handler.py -v`
  期望：FAIL，顯示 `ModuleNotFoundError: No module named 'src.handlers.football_handler'`。

- [ ] **Step 8: 實作 `src/handlers/football_handler.py`**
  
  建立 [src/handlers/football_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/football_handler.py)：
  ```python
  import re
  import logging
  from linebot.v3.webhooks import MessageEvent
  from linebot.v3.messaging import (
      ApiClient,
      MessagingApi,
      ReplyMessageRequest,
      TextMessage,
      Configuration
  )
  from .base_handler import BaseHandler
  from src.config import load_config
  from src.utils.football_analyzer import analyze_football_matchup

  class FootballHandler(BaseHandler):
      def __init__(self):
          # 支援空格、vs、VS、對、對戰作為兩隊的分隔符
          self.pattern = re.compile(r"^#足球\s+(\S+)\s*(?:vs|VS|對|對戰|\s)\s*(\S+)$")

      def can_handle(self, user_text: str) -> bool:
          config = load_config()
          if not config.get("ENABLE_FOOTBALL_ANALYSIS", False):
              return False
          
          user_text = user_text.strip()
          return bool(self.pattern.match(user_text))

      def execute(self, event: MessageEvent, configuration: Configuration) -> None:
          user_text = event.message.text.strip()
          match = self.pattern.match(user_text)
          if not match:
              return
          
          team_a = match.group(1)
          team_b = match.group(2)
          
          config = load_config()
          api_key = config.get("GEMINI_API_KEY")
          model_name = config.get("GEMINI_MODEL")
          
          # 由於呼叫 LLM 需要時間，我們先回傳一個「正在分析」的通知，
          # 但因為 LINE reply_token 只能使用一次，我們不能直接在 execute 內連續 reply 兩次。
          # 為了避免 API 逾時，且因為此專案是同步處理，我們直接進行 LLM 呼叫並在完成後回覆。
          # 若要避免 3 秒超時，我們必須在 3 秒內完成。Gemini 3.5 Flash 通常只需 1~2 秒。
          analysis = analyze_football_matchup(team_a, team_b, api_key=api_key, model_name=model_name)
          
          self.reply_text(event, configuration, analysis)

      def reply_text(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
          with ApiClient(configuration) as api_client:
              MessagingApi(api_client).reply_message(
                  ReplyMessageRequest(
                      reply_token=event.reply_token,
                      messages=[TextMessage(text=text)]
                  )
              )
  ```

- [ ] **Step 9: 執行測試確認通過**
  
  執行：`pytest tests/test_football_handler.py -v`
  期望：PASS。

---

### Task 3: 註冊處理器與端到端驗證

**Files:**
- Modify: [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py)

- [ ] **Step 10: 註冊 `FootballHandler`**
  
  在 [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py) 中載入並註冊 `FootballHandler`：
  ```python
  # 約第 23-24 行附近新增載入
  from src.handlers.football_handler import FootballHandler

  # 約第 73-74 行註冊
  dispatcher.register(FootballHandler())
  ```

- [ ] **Step 11: 執行專案所有測試，確保無 regressions**
  
  執行：`pytest`
  期望：所有測試案例皆 PASS。
