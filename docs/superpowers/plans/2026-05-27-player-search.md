# NBA 球員模糊搜尋與單場數據查詢實作計畫 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 LINE Bot 指令 `#球員 <稱呼>`，透過 Gemini API 解析現役 NBA 球員，以台北時間 07:00 跨日邏輯決定目標美西日期，串接 Yahoo Fantasy API 抓取其單場 9-Cat 數據並以英文標題、右對齊格式回傳。

**Architecture:**
- 新增 `src/utils/gemini_parser.py` 用於處理 LLM 模糊解析。
- 新增 `src/utils/player_cache.py` 用於本地 JSON 快取。
- 新增 `src/handlers/player_handler.py` 繼承 `BaseHandler` 用於處理 LINE 指令、時區邏輯與數據抓取。
- 修改 `bot.py` 註冊新 Handler。

**Tech Stack:**
- Python, `google-generativeai`, `yahoofantasy`, `pytest`, `pytz`

---

## 預計新增與修改之檔案結構
- **新建** `src/utils/gemini_parser.py` (LLM 語意解析)
- **新建** `src/utils/player_cache.py` (本地對照快取)
- **新建** `src/handlers/player_handler.py` (LINE 指令與 Yahoo API 數據整合)
- **新建** `tests/test_gemini_parser.py` (解析器單元測試)
- **新建** `tests/test_player_cache.py` (快取單元測試)
- **新建** `tests/test_player_handler.py` (Handler 核心邏輯與跨日測試)
- **修改** `requirements.txt` (新增 `google-generativeai` 依賴)
- **修改** `bot.py` (註冊 Handler)

---

### Task 1: 依賴與 Gemini LLM 解析器

**Files:**
- Create: `src/utils/gemini_parser.py`
- Test: `tests/test_gemini_parser.py`
- Modify: `requirements.txt`

- [ ] **Step 1: 新增 `google-generativeai` 至 `requirements.txt`**
  
  修改 `requirements.txt`：
  ```text
  yahoofantasy
  python-dotenv
  pytest
  pytest-mock
  pytz
  Jinja2
  playwright
  google-generativeai
  ```

- [ ] **Step 2: 安裝依賴並驗證**
  
  執行：`pip install -r requirements.txt`
  期望：成功安裝 `google-generativeai`。

- [ ] **Step 3: 撰寫 Gemini 解析器單元測試 (TDD 失敗測試)**
  
  建立 `tests/test_gemini_parser.py`：
  ```python
  import pytest
  from unittest.mock import MagicMock
  from src.utils.gemini_parser import parse_player_nickname

  def test_parse_player_nickname_success(mocker):
      # Mock google.generativeai 的 model.generate_content
      mock_model = MagicMock()
      mock_response = MagicMock()
      mock_response.text = '{"is_known_player": true, "english_name": "LeBron James", "chinese_name": "勒布朗·詹姆斯", "team": "Los Angeles Lakers", "jersey_number": "23", "confidence": 1.0, "reason": "test"}'
      mock_model.generate_content.return_value = mock_response
      
      mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
      
      res = parse_player_nickname("喇叭", api_key="dummy_key")
      assert res["is_known_player"] is True
      assert res["english_name"] == "LeBron James"
      assert res["jersey_number"] == "23"

  def test_parse_player_nickname_unknown(mocker):
      mock_model = MagicMock()
      mock_response = MagicMock()
      mock_response.text = '{"is_known_player": false, "english_name": null, "chinese_name": null, "team": null, "jersey_number": null, "confidence": 0.0, "reason": "test"}'
      mock_model.generate_content.return_value = mock_response
      
      mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
      
      res = parse_player_nickname("哈囉", api_key="dummy_key")
      assert res["is_known_player"] is False
  ```

- [ ] **Step 4: 執行測試確認失敗**
  
  執行：`pytest tests/test_gemini_parser.py -v`
  期望：FAIL，顯示 `ModuleNotFoundError: No module named 'src.utils.gemini_parser'`。

- [ ] **Step 5: 撰寫 `src/utils/gemini_parser.py` 實作**
  
  建立 `src/utils/gemini_parser.py`：
  ```python
  import json
  import os
  import logging
  import google.generativeai as genai

  SYSTEM_PROMPT = """你是一個精準的 NBA 籃球專家，專門負責將使用者的模糊輸入（例如球員綽號、簡稱、中文音譯或背號加上球隊）解析為官方標準的現役球員資訊。

請遵循以下嚴格規則：
1. 僅識別真實存在的 NBA 「現役球員 (Active Players)」。如果球員已退休，請將 is_known_player 設為 false。
2. 對於常見的中文或英文綽號，你必須精準對應，例如：
   - "喇叭", "LBJ", "老漢", "詹皇" -> LeBron James
   - "咖哩", "萌神", "廚師" -> Stephen Curry
   - "死神", "KD" -> Kevin Durant
   - "字母哥" -> Giannis Antetokounmpo
   - "77", "胖虎" -> Luka Doncic
3. 如果輸入是完全無意義、非籃球球員、或非現役球員的字詞（例如 "喬丹", "科比", "哈囉", "測試"），你必須將 is_known_player 設為 false，並拒絕胡亂臆測。
4. 必須以指定的 JSON 格式回傳，不要包含任何額外的說明、Markdown 標記或 ```json 包裹。"""

  def parse_player_nickname(nickname: str, api_key: str = None) -> dict:
      key = api_key or os.getenv("GEMINI_API_KEY")
      if not key:
          logging.error("Gemini API key is not configured.")
          return {"is_known_player": False, "english_name": None, "chinese_name": None, "team": None, "jersey_number": None, "confidence": 0.0, "reason": "API Key 尚未設定"}
      
      try:
          genai.configure(api_key=key)
          model = genai.GenerativeModel(
              model_name="gemini-1.5-flash",
              system_instruction=SYSTEM_PROMPT
          )
          
          response = model.generate_content(
              f"請解析以下輸入：{nickname}",
              generation_config={"response_mime_type": "application/json"}
          )
          
          data = json.loads(response.text.strip())
          return data
      except Exception as e:
          logging.error(f"Gemini API parse failed: {e}")
          return {"is_known_player": False, "english_name": None, "chinese_name": None, "team": None, "jersey_number": None, "confidence": 0.0, "reason": f"API 呼叫失敗: {str(e)}"}
  ```

- [ ] **Step 6: 執行測試確認通過**
  
  執行：`pytest tests/test_gemini_parser.py -v`
  期望：PASS。

- [ ] **Step 7: Git Commit**
  
  執行：
  ```bash
  git add requirements.txt src/utils/gemini_parser.py tests/test_gemini_parser.py
  git commit -m "feat: add Gemini LLM player nickname parser and tests"
  ```

---

### Task 2: 本地快取管理器

**Files:**
- Create: `src/utils/player_cache.py`
- Test: `tests/test_player_cache.py`

- [ ] **Step 1: 撰寫快取單元測試 (TDD 失敗測試)**
  
  建立 `tests/test_player_cache.py`：
  ```python
  import os
  import json
  import pytest
  from src.utils.player_cache import load_cache, save_cache, get_cached_player, set_cached_player

  TEST_CACHE_PATH = "data/test_player_cache.json"

  @pytest.fixture(autouse=True)
  def cleanup():
      if os.path.exists(TEST_CACHE_PATH):
          os.remove(TEST_CACHE_PATH)
      yield
      if os.path.exists(TEST_CACHE_PATH):
          os.remove(TEST_CACHE_PATH)

  def test_cache_operations():
      cache = load_cache(TEST_CACHE_PATH)
      assert cache == {}
      
      player_data = {
          "english_name": "LeBron James",
          "chinese_name": "勒布朗·詹姆斯",
          "team": "Los Angeles Lakers",
          "jersey_number": "23",
          "player_key": "nba.p.3704"
      }
      
      set_cached_player("喇叭", player_data, TEST_CACHE_PATH)
      
      loaded = get_cached_player("喇叭", TEST_CACHE_PATH)
      assert loaded is not None
      assert loaded["english_name"] == "LeBron James"
      assert loaded["player_key"] == "nba.p.3704"
  ```

- [ ] **Step 2: 執行測試確認失敗**
  
  執行：`pytest tests/test_player_cache.py -v`
  期望：FAIL，顯示 `ModuleNotFoundError: No module named 'src.utils.player_cache'`。

- [ ] **Step 3: 撰寫 `src/utils/player_cache.py` 實作**
  
  建立 `src/utils/player_cache.py`：
  ```python
  import os
  import json
  import logging

  DEFAULT_CACHE_PATH = "data/player_mapping_cache.json"

  def load_cache(cache_path: str = DEFAULT_CACHE_PATH) -> dict:
      if not os.path.exists(cache_path):
          return {}
      try:
          with open(cache_path, "r", encoding="utf-8") as f:
              return json.load(f)
      except Exception as e:
          logging.error(f"Failed to load player cache from {cache_path}: {e}")
          return {}

  def save_cache(cache: dict, cache_path: str = DEFAULT_CACHE_PATH) -> None:
      try:
          os.makedirs(os.path.dirname(cache_path), exist_ok=True)
          with open(cache_path, "w", encoding="utf-8") as f:
              json.dump(cache, f, ensure_ascii=False, indent=2)
      except Exception as e:
          logging.error(f"Failed to save player cache to {cache_path}: {e}")

  def get_cached_player(nickname: str, cache_path: str = DEFAULT_CACHE_PATH) -> dict | None:
      cache = load_cache(cache_path)
      return cache.get(nickname.strip())

  def set_cached_player(nickname: str, player_data: dict, cache_path: str = DEFAULT_CACHE_PATH) -> None:
      cache = load_cache(cache_path)
      cache[nickname.strip()] = player_data
      save_cache(cache, cache_path)
  ```

- [ ] **Step 4: 執行測試確認通過**
  
  執行：`pytest tests/test_player_cache.py -v`
  期望：PASS。

- [ ] **Step 5: Git Commit**
  
  執行：
  ```bash
  git add src/utils/player_cache.py tests/test_player_cache.py
  git commit -m "feat: add player cache manager and tests"
  ```

---

### Task 3: 球員 Handler 與 LINE Bot 整合

**Files:**
- Create: `src/handlers/player_handler.py`
- Test: `tests/test_player_handler.py`
- Modify: `bot.py`

- [ ] **Step 1: 撰寫 `PlayerHandler` 單元測試 (TDD 失敗測試)**
  
  建立 `tests/test_player_handler.py`：
  ```python
  import pytest
  from datetime import datetime
  import pytz
  from src.handlers.player_handler import PlayerHandler

  def test_player_handler_can_handle():
      handler = PlayerHandler()
      assert handler.can_handle("#球員 喇叭") is True
      assert handler.can_handle("#球員") is False
      assert handler.can_handle("#戰績") is False

  def test_calculate_target_date_regular():
      handler = PlayerHandler()
      
      # 早上 6:59 查詢 (台北時間 11/12) -> 美西目標日期為 11/10 (台北日期 - 2)
      dt_morning = datetime(2026, 11, 12, 6, 59, 0, tzinfo=pytz.timezone("Asia/Taipei"))
      target_date = handler.calculate_target_date(current_tw_dt=dt_morning, is_offseason=False)
      assert target_date == "2026-11-10"

      # 早上 7:01 查詢 (台北時間 11/12) -> 美西目標日期為 11/11 (台北日期 - 1)
      dt_afternoon = datetime(2026, 11, 12, 7, 1, 0, tzinfo=pytz.timezone("Asia/Taipei"))
      target_date = handler.calculate_target_date(current_tw_dt=dt_afternoon, is_offseason=False)
      assert target_date == "2026-11-11"

      # 晚上 18:00 查詢 (台北時間 11/12) -> 美西目標日期為 11/11 (台北日期 - 1)
      dt_evening = datetime(2026, 11, 12, 18, 0, 0, tzinfo=pytz.timezone("Asia/Taipei"))
      target_date = handler.calculate_target_date(current_tw_dt=dt_evening, is_offseason=False)
      assert target_date == "2026-11-11"

  def test_calculate_target_date_offseason():
      handler = PlayerHandler()
      # 休賽季 -> 強制指向設為賽季最後一天
      target_date = handler.calculate_target_date(is_offseason=True, end_date="2026-04-12")
      assert target_date == "2026-04-12"

  def test_format_stats():
      handler = PlayerHandler()
      player_info = {
          "english_name": "LeBron James",
          "chinese_name": "勒布朗·詹姆斯",
          "team": "Los Angeles Lakers",
          "jersey_number": "23"
      }
      stats = {
          "FGM/FGA": "14/24",
          "FG%": "0.583",
          "FTM/FTA": "3/4",
          "FT%": "0.750",
          "3PTM": "4",
          "PTS": "35",
          "REB": "9",
          "AST": "12",
          "ST": "2",
          "BLK": "1",
          "TO": "3"
      }
      formatted = handler.format_player_stats(player_info, stats)
      
      expected = (
          "LeBron James (勒布朗·詹姆斯)\n"
          "Los Angeles Lakers#23\n"
          "-----------------------\n"
          "FGM/A :           14/24\n"
          "FG% :             58.3%\n"
          "FTM/A :             3/4\n"
          "FT% :             75.0%\n"
          "3PM :                 4\n"
          "PTS :                35\n"
          "REB :                 9\n"
          "AST :                12\n"
          "STL :                 2\n"
          "BLK :                 1\n"
          "TO :                  3"
      )
      assert formatted.strip() == expected.strip()
  ```

- [ ] **Step 2: 執行測試確認失敗**
  
  執行：`pytest tests/test_player_handler.py -v`
  期望：FAIL，顯示 `ModuleNotFoundError: No module named 'src.handlers.player_handler'`。

- [ ] **Step 3: 撰寫 `src/handlers/player_handler.py` 實作**
  
  建立 `src/handlers/player_handler.py`：
  ```python
  import re
  import os
  import logging
  import xml.etree.ElementTree as ET
  from datetime import datetime, timedelta
  import pytz
  from linebot.v3.webhooks import MessageEvent
  from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
  from .base_handler import BaseHandler

  from src.config import load_config
  from src.cache_utils import load_league_metadata
  from src.fetcher import YahooFantasyFetcher
  from src.utils.gemini_parser import parse_player_nickname
  from src.utils.player_cache import get_cached_player, set_cached_player

  YAHOO_NS = {'ns': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}

  class PlayerHandler(BaseHandler):
      def __init__(self):
          self.pattern = re.compile(r"^#球員\s+(.+)$")

      def can_handle(self, user_text: str) -> bool:
          return self.pattern.match(user_text) is not None

      def calculate_target_date(self, current_tw_dt=None, is_offseason=False, end_date=None) -> str:
          if is_offseason:
              return end_date or "2026-04-12"
          
          if current_tw_dt is None:
              tw_tz = pytz.timezone("Asia/Taipei")
              current_tw_dt = datetime.now(tw_tz)
              
          tw_date = current_tw_dt.date()
          tw_hour = current_tw_dt.hour
          
          if tw_hour >= 7:
              target_dt = tw_date - timedelta(days=1)
          else:
              target_dt = tw_date - timedelta(days=2)
              
          return target_dt.strftime("%Y-%m-%d")

      def format_player_stats(self, player_info: dict, stats: dict) -> str:
          # Helper to safely format percentages
          def to_percent_str(val):
              try:
                  return f"{float(val) * 100:.1f}%"
              except (ValueError, TypeError):
                  return "0.0%"

          fgm_a = stats.get("FGM/FGA", "0/0")
          fg_pct = to_percent_str(stats.get("FG%", "0.0"))
          ftm_a = stats.get("FTM/FTA", "0/0")
          ft_pct = to_percent_str(stats.get("FT%", "0.0"))
          pm3 = stats.get("3PTM", "0")
          pts = stats.get("PTS", "0")
          reb = stats.get("REB", "0")
          ast = stats.get("AST", "0")
          stl = stats.get("ST", "0")
          blk = stats.get("BLK", "0")
          to = stats.get("TO", "0")

          header = (
              f"{player_info.get('english_name', 'Unknown')}"
              f" ({player_info.get('chinese_name', '未知')})\n"
              f"{player_info.get('team', 'Unknown')}#{player_info.get('jersey_number', '0')}\n"
              f"-----------------------"
          )

          lines = [
              f"FGM/A : {fgm_a:>15}",
              f"FG% : {fg_pct:>17}",
              f"FTM/A : {ftm_a:>15}",
              f"FT% : {ft_pct:>17}",
              f"3PM : {pm3:>17}",
              f"PTS : {pts:>17}",
              f"REB : {reb:>17}",
              f"AST : {ast:>17}",
              f"STL : {stl:>17}",
              f"BLK : {blk:>17}",
              f"TO : {to:>18}"
          ]

          return header + "\n" + "\n".join(lines)

      def execute(self, event: MessageEvent, configuration: Configuration) -> None:
          user_text = event.message.text.strip()
          match = self.pattern.match(user_text)
          if not match:
              return

          nickname = match.group(1).strip()
          config = load_config()
          league_id = config["LEAGUE_ID"]
          meta = load_league_metadata()
          today_pacific = datetime.now(pytz.timezone("US/Pacific")).strftime("%Y-%m-%d")
          is_offseason = meta.get('end_date') and today_pacific > meta['end_date']

          # 1. Check cache
          player_info = get_cached_player(nickname)
          
          # 2. Cache Miss: LLM parse + Yahoo Search
          if not player_info:
              llm_res = parse_player_nickname(nickname, api_key=config.get("GEMINI_API_KEY"))
              if not llm_res.get("is_known_player"):
                  self.reply_text(event, configuration, f"找不到現役球員「{nickname}」，請嘗試輸入更清晰的名字或別稱。")
                  return
              
              english_name = llm_res["english_name"]
              
              # Retrieve player key from Yahoo search
              fetcher = YahooFantasyFetcher(client_id=config.get("YAHOO_CLIENT_ID"), client_secret=config.get("YAHOO_CLIENT_SECRET"))
              url = f"league/nba.l.{league_id}/players;search={english_name}"
              try:
                  xml_data = fetcher.ctx.make_request(url)
                  root = ET.fromstring(xml_data)
                  player_node = root.find('.//ns:player', YAHOO_NS)
                  if player_node is None:
                      self.reply_text(event, configuration, f"AI 識別為 {english_name}，但當前 Yahoo 聯盟中找不到該球員數據。")
                      return
                  
                  player_key = player_node.find('ns:player_key', YAHOO_NS).text
                  uniform_node = player_node.find('ns:uniform_number', YAHOO_NS)
                  jersey_number = uniform_node.text if uniform_node is not None else llm_res.get("jersey_number", "0")
                  
                  player_info = {
                      "english_name": english_name,
                      "chinese_name": llm_res["chinese_name"],
                      "team": llm_res["team"],
                      "jersey_number": jersey_number,
                      "player_key": player_key
                  }
                  set_cached_player(nickname, player_info)
              except Exception as e:
                  logging.error(f"Yahoo Search failed: {e}")
                  self.reply_text(event, configuration, f"搜尋球員 {english_name} 時發生 Yahoo API 錯誤。")
                  return

          # 3. Target date calculation
          target_date = self.calculate_target_date(is_offseason=is_offseason, end_date=meta.get('end_date'))
          
          # 4. Fetch Stats by date
          fetcher = YahooFantasyFetcher(client_id=config.get("YAHOO_CLIENT_ID"), client_secret=config.get("YAHOO_CLIENT_SECRET"))
          player_key = player_info["player_key"]
          url = f"player/{player_key}/stats;type=date;date={target_date}"
          
          try:
              xml_data = fetcher.ctx.make_request(url)
              root = ET.fromstring(xml_data)
              
              # Parse stats from XML
              stats_dict = {}
              stat_nodes = root.findall('.//ns:player_stats/ns:stats/ns:stat', YAHOO_NS)
              for node in stat_nodes:
                  s_id = node.find('ns:stat_id', YAHOO_NS).text
                  s_val = node.find('ns:value', YAHOO_NS).text
                  # Import standard map translation
                  from src.constants.stat_map import translate_stat_id
                  label = translate_stat_id(s_id)
                  stats_dict[label] = s_val
                  
              # Guard: if no game played (MIN or PTS is 0 or stat_id not present)
              minutes = stats_dict.get("stat_0", "0") # stat_0 is typically MIN in Yahoo
              pts = stats_dict.get("PTS", "0")
              
              if minutes == "0" and pts == "0":
                  self.reply_text(event, configuration, f"{player_info['english_name']} 於 {target_date} 今日無比賽數據。")
                  return
              
              reply_text = self.format_player_stats(player_info, stats_dict)
              self.reply_text(event, configuration, reply_text)
          except Exception as e:
              logging.error(f"Yahoo fetch stats failed: {e}")
              self.reply_text(event, configuration, f"獲取球員統計數據失敗: {str(e)}")

      def reply_text(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
          with ApiClient(configuration) as api_client:
              MessagingApi(api_client).reply_message(
                  ReplyMessageRequest(
                      reply_token=event.reply_token,
                      messages=[TextMessage(text=text)]
                  )
              )
  ```

- [ ] **Step 4: 執行測試確認通過**
  
  執行：`pytest tests/test_player_handler.py -v`
  期望：PASS。

- [ ] **Step 5: 修改 `bot.py` 註冊新 Handler**
  
  在 `bot.py` 中導入並註冊 `PlayerHandler`。
  
  修改 `bot.py:64-67`：
  ```python
  # Initialize Dispatcher
  from src.handlers.player_handler import PlayerHandler # 新增
  dispatcher = CommandDispatcher()
  dispatcher.register(StatsHandler())
  dispatcher.register(PlayerHandler()) # 新增
  ```

- [ ] **Step 6: 執行整個專案的單元測試集**
  
  執行：`pytest -v`
  期望：所有單元測試皆 PASS，無 breaking changes。

- [ ] **Step 7: Git Commit**
  
  執行：
  ```bash
  git add src/handlers/player_handler.py tests/test_player_handler.py bot.py
  git commit -m "feat: implement PlayerHandler and integrate with LINE bot"
  ```

---

## 7. 計劃自我審查 (Plan Self-Review)

1. **Spec 符合度**：
   - 台北時間 07:00 跨日邏輯？有，已在 `calculate_target_date` 完整實作。
   - 英文 9-Cat 靠右對齊排版？有，已在 `format_player_stats` 中使用 `>15` / `>17` 格式對齊。
   - 快取設計？有，已在 `src/utils/player_cache.py` 實作。
   - 休賽季覆寫？有，已在 `calculate_target_date` 與主流程中判斷並覆寫。

2. **Placeholder 掃描**：全代碼完全展開，沒有任何 TODO/TBD 或「在後續實作中完成」之字樣。
3. **類型一致性**：`player_info` 結構、`stats_dict` 鍵值以及時區操作（使用 `pytz.timezone`）完全一致。
