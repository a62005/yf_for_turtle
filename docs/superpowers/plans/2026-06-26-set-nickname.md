# 設置玩家暱稱功能實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 LINE Bot `#設置` 選單中的「設置玩家暱稱」功能，包含初次設置聯賽時以官方預設暱稱初始化 `team_mapping.json`，並透過 60 秒的對話 Session 讓用戶能直接發送文字以修改暱稱。

**Architecture:** 
1. 新增 `src/utils/session_manager.py` 作為全域會話管理器，解耦處理器（Handler）與意圖路由器（IntentRouter）。
2. 在 `SetLeagueIdHandler` 中，當設定聯盟 ID 且對應檔案不存在時，調用 Yahoo API 取得官方隊伍名寫入。
3. 實作 `SetNicknameHandler` 以處理暱稱按鈕列表及發送修改引導；並在 `IntentRouter` 最前端加入對話攔截，讀取 Session 來更新暱稱。

**Tech Stack:** Python 3.14, line-bot-sdk-python v3, pytest

---

### Task 1: 官方暱稱初始化優化

**Files:**
- Modify: `src/handlers/set_league_id_handler.py`
- Test: `tests/handlers/test_settings_and_setup.py`

- [ ] **Step 1: 撰寫預期失敗的測試**
  修改 [test_settings_and_setup.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/handlers/test_settings_and_setup.py)，在 `test_set_league_id_handler_success` 測試中引入對 `yahoofantasy.League` 的 patch 模擬。
  
  在 [test_settings_and_setup.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/handlers/test_settings_and_setup.py) 中，將 `test_set_league_id_handler_success` 替換為以下內容：
  ```python
  def test_set_league_id_handler_success():
      handler = SetLeagueIdHandler()
      handler.reply_text = MagicMock()
      
      event = MagicMock()
      event.message.text = "#設置聯盟ID 12345"
      config = MagicMock()
      
      mock_team = MagicMock()
      mock_team.team_id = "1"
      mock_team.name = "官方測試隊伍"
      
      mock_league = MagicMock()
      mock_league.teams.return_value = [mock_team]
      
      with patch("src.handlers.set_league_id_handler.sync_season_metadata") as mock_sync, \
           patch("src.handlers.set_league_id_handler.open", mock_open()) as mock_file, \
           patch("src.handlers.set_league_id_handler.os.path.exists", return_value=False), \
           patch("yahoofantasy.League", return_value=mock_league) as mock_league_cls:
          handler.execute(event, config)
          
          mock_sync.assert_called_once()
          mock_league_cls.assert_called_once()
          handler.reply_text.assert_called_once_with(
              event, 
              config, 
              "✅ 聯盟 ID 設置成功，並已完成賽季資訊同步！"
          )
  ```

- [ ] **Step 2: 執行測試並驗證失敗**
  執行單元測試：
  Run: `.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py::test_set_league_id_handler_success -v`
  Expected: FAIL (AssertionError: mock_league_cls.assert_called_once() 未被呼叫)

- [ ] **Step 3: 實作官方暱稱初始化邏輯**
  修改 [set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py#L54-L60)，在 `execute` 方法寫入對應檔的邏輯中，呼叫 API 取得官方隊伍：
  
  ```python
              # 初始化該聯賽的空對應檔
              mapping_path = get_league_team_mapping_path(target_id)
              if not os.path.exists(mapping_path):
                  os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
                  
                  # 取得官方預設隊伍名稱並建立對應
                  default_mapping = {}
                  try:
                      import yahoofantasy
                      normalized_id = fetcher._normalize_league_id(target_id)
                      league = yahoofantasy.League(fetcher.ctx, normalized_id)
                      for team in league.teams():
                          team_id = str(getattr(team, "team_id", ""))
                          team_name = str(getattr(team, "name", ""))
                          if team_id and team_name:
                              default_mapping[team_id] = team_name
                  except Exception as ex:
                      logging.error(f"[SetLeagueIdHandler] 無法取得官方暱稱，將初始化為空對應: {ex}")
                  
                  with open(mapping_path, "w", encoding="utf-8") as mf:
                      json.dump(default_mapping, mf, ensure_ascii=False, indent=2)
  ```

- [ ] **Step 4: 執行測試確認通過**
  Run: `.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py::test_set_league_id_handler_success -v`
  Expected: PASS

- [ ] **Step 5: 提交變更**
  ```bash
  git add src/handlers/set_league_id_handler.py tests/handlers/test_settings_and_setup.py
  git commit -m "feat: initialize team_mapping.json with official Yahoo team names on setup"
  ```

---

### Task 2: 設置選單按鈕啟用

**Files:**
- Modify: `src/handlers/settings_handler.py`
- Test: `tests/handlers/test_settings_handler.py`

- [ ] **Step 1: 撰寫驗證選單按鈕的測試**
  修改 [test_settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/handlers/test_settings_handler.py)，增加對暱稱設定按鈕文字與指令的斷言。
  
  將 [test_settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/handlers/test_settings_handler.py#L9-L21) 的 `test_settings_handler_execute` 替換為以下內容：
  ```python
  def test_settings_handler_execute():
      handler = SettingsHandler()
      handler.reply_flex = MagicMock()
  
      event = MagicMock()
      config = MagicMock()
  
      with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}):
          handler.execute(event, config)
          handler.reply_flex.assert_called_once()
          args, kwargs = handler.reply_flex.call_args
          assert "設置選單" in args[2]
          
          # 驗證「設置玩家暱稱」已啟用，且對應指令為 #設置玩家暱稱
          flex_card = args[3]
          buttons_box = flex_card["body"]["contents"][1]
          btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
          assert "設置玩家暱稱" in btn_labels
          assert "設置玩家暱稱 (即將推出)" not in btn_labels
          
          nickname_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "設置玩家暱稱"][0]
          assert nickname_btn["action"]["text"] == "#設置玩家暱稱"
  ```

- [ ] **Step 2: 執行測試並驗證失敗**
  Run: `.venv\Scripts\python -m pytest tests/handlers/test_settings_handler.py::test_settings_handler_execute -v`
  Expected: FAIL (AssertionError: '設置玩家暱稱' not in btn_labels)

- [ ] **Step 3: 啟用設置選單的暱稱設定按鈕**
  修改 [settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py#L26-L32)，移除 `(即將推出)` 並綁定指令：
  ```python
              buttons = [
                  ("設置選秀時間 (即將推出)", ""),
                  ("設置玩家暱稱", "#設置玩家暱稱"),
                  (None, None),
                  ("更換聯盟ID (即將推出)", ""),
                  ("移除聯盟ID (即將推出)", "")
              ]
  ```

- [ ] **Step 4: 執行測試確認通過**
  Run: `.venv\Scripts\python -m pytest tests/handlers/test_settings_handler.py::test_settings_handler_execute -v`
  Expected: PASS

- [ ] **Step 5: 提交變更**
  ```bash
  git add src/handlers/settings_handler.py tests/handlers/test_settings_handler.py
  git commit -m "feat: enable player nickname button and route to #設置玩家暱稱 in SettingsHandler"
  ```

---

### Task 3: 實作會話管理器與 SetNicknameHandler

**Files:**
- Create: `src/utils/session_manager.py`
- Create: `src/handlers/set_nickname_handler.py`
- Modify: `bot.py`
- Test: `tests/handlers/test_set_nickname_handler.py`

- [ ] **Step 1: 建立全域會話管理器**
  新增 [session_manager.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/session_manager.py) 檔案：
  ```python
  import time
  
  _sessions = {}  # 格式: { user_id: { "team_id": str, "expire_at": float } }
  
  def set_nickname_session(user_id: str, team_id: str, duration_sec: int = 60) -> None:
      _sessions[user_id] = {
          "team_id": team_id,
          "expire_at": time.time() + duration_sec
      }
  
  def get_nickname_session(user_id: str) -> dict | None:
      session = _sessions.get(user_id)
      if not session:
          return None
      if time.time() > session["expire_at"]:
          del _sessions[user_id]
          return None
      return session
  
  def clear_nickname_session(user_id: str) -> None:
      if user_id in _sessions:
          del _sessions[user_id]
  ```

- [ ] **Step 2: 撰寫 SetNicknameHandler 的單元測試**
  新建 [test_set_nickname_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/handlers/test_set_nickname_handler.py) 檔案，驗證對暱稱設定相關指令的處理：
  ```python
  import os
  import json
  from unittest.mock import MagicMock, patch, mock_open
  from src.handlers.set_nickname_handler import SetNicknameHandler
  from src.utils.session_manager import get_nickname_session
  
  def test_set_nickname_handler_can_handle():
      handler = SetNicknameHandler()
      assert handler.can_handle("#設置玩家暱稱") is True
      assert handler.can_handle("#設置暱稱_隊伍 1") is True
      assert handler.can_handle("#設置") is False
  
  def test_set_nickname_handler_menu_flow():
      handler = SetNicknameHandler()
      handler.reply_flex = MagicMock()
      
      event = MagicMock()
      event.message.text = "#設置玩家暱稱"
      config = MagicMock()
      
      mock_mapping = {"1": "小明", "2": "陳威"}
      
      with patch("src.handlers.set_nickname_handler.load_config", return_value={"LEAGUE_ID": "123"}), \
           patch("src.handlers.set_nickname_handler.os.path.exists", return_value=True), \
           patch("src.handlers.set_nickname_handler.open", mock_open(read_data=json.dumps(mock_mapping))):
          handler.execute(event, config)
          handler.reply_flex.assert_called_once()
          args, kwargs = handler.reply_flex.call_args
          assert "設定玩家暱稱" in args[2]
          flex_dict = args[3]
          buttons = flex_dict["body"]["contents"][1]["contents"]
          assert len(buttons) == 2
          assert buttons[0]["action"]["label"] == "小明"
          assert buttons[0]["action"]["text"] == "#設置暱稱_隊伍 1"
  
  def test_set_nickname_handler_select_team_flow():
      handler = SetNicknameHandler()
      handler.reply_text = MagicMock()
      
      event = MagicMock()
      event.source.user_id = "user_abc"
      event.message.text = "#設置暱稱_隊伍 1"
      config = MagicMock()
      
      mock_mapping = {"1": "小明", "2": "陳威"}
      
      with patch("src.handlers.set_nickname_handler.load_config", return_value={"LEAGUE_ID": "123"}), \
           patch("src.handlers.set_nickname_handler.os.path.exists", return_value=True), \
           patch("src.handlers.set_nickname_handler.open", mock_open(read_data=json.dumps(mock_mapping))):
          handler.execute(event, config)
          handler.reply_text.assert_called_once_with(
              event, config, "👉 請在 60 秒內直接輸入 小明 的新暱稱："
          )
          session = get_nickname_session("user_abc")
          assert session is not None
          assert session["team_id"] == "1"
  ```

- [ ] **Step 3: 執行測試並驗證失敗**
  Run: `.venv\Scripts\python -m pytest tests/handlers/test_set_nickname_handler.py -v`
  Expected: FAIL (ModuleNotFoundError: No module named 'src.handlers.set_nickname_handler')

- [ ] **Step 4: 實作 SetNicknameHandler**
  新建 [set_nickname_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_nickname_handler.py) 檔案：
  ```python
  import re
  import os
  import json
  import logging
  from linebot.v3.webhooks import MessageEvent
  from linebot.v3.messaging import Configuration
  from src.handlers.base_handler import BaseHandler
  from src.config import load_config
  from src.utils.path_utils import get_league_team_mapping_path
  from src.visualizer.flex_builder import build_button_menu_card
  from src.utils.session_manager import set_nickname_session
  
  class SetNicknameHandler(BaseHandler):
      def __init__(self):
          super().__init__()
          self.requires_whitelist = True
          
      def can_handle(self, user_text: str) -> bool:
          text = user_text.strip()
          return text == "#設置玩家暱稱" or text.startswith("#設置暱稱_隊伍")
          
      def execute(self, event: MessageEvent, configuration: Configuration) -> None:
          user_text = event.message.text.strip()
          config = load_config()
          league_id = config.get("LEAGUE_ID")
          
          if not league_id:
              self.reply_text(event, configuration, "⚠️ 聯賽 ID 尚未配置，無法設定玩家暱稱。")
              return
              
          mapping_path = get_league_team_mapping_path(league_id)
          
          # 若 mapping 檔不存在，先進行預設初始化
          if not os.path.exists(mapping_path):
              os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
              default_mapping = {}
              try:
                  import yahoofantasy
                  from src.fetcher import YahooFantasyFetcher
                  fetcher = YahooFantasyFetcher(
                      client_id=config.get("YAHOO_CLIENT_ID"),
                      client_secret=config.get("YAHOO_CLIENT_SECRET")
                  )
                  league = yahoofantasy.League(fetcher.ctx, fetcher._normalize_league_id(league_id))
                  for team in league.teams():
                      team_id = str(getattr(team, "team_id", ""))
                      team_name = str(getattr(team, "name", ""))
                      if team_id and team_name:
                          default_mapping[team_id] = team_name
              except Exception as ex:
                  logging.error(f"[SetNicknameHandler] 初始化官方暱稱失敗: {ex}")
              
              with open(mapping_path, "w", encoding="utf-8") as mf:
                  json.dump(default_mapping, mf, ensure_ascii=False, indent=2)
                  
          # 讀取當前 mapping 資訊
          try:
              with open(mapping_path, "r", encoding="utf-8") as mf:
                  mapping = json.load(mf)
          except Exception as e:
              logging.error(f"[SetNicknameHandler] 讀取對應檔失敗: {e}")
              mapping = {}
              
          if user_text == "#設置玩家暱稱":
              buttons = []
              for team_id, nickname in mapping.items():
                  buttons.append((nickname, f"#設置暱稱_隊伍 {team_id}"))
              
              flex_dict = build_button_menu_card("設定玩家暱稱", None, buttons)
              self.reply_flex(event, configuration, "設定玩家暱稱", flex_dict)
              
          elif user_text.startswith("#設置暱稱_隊伍"):
              match = re.match(r"^#設置暱稱_隊伍\s+(\d+)$", user_text)
              if not match:
                  self.reply_text(event, configuration, "⚠️ 指令格式錯誤。")
                  return
              
              team_id = match.group(1)
              curr_name = mapping.get(team_id, f"Team {team_id}")
              
              # 註冊 60 秒的改名 Session 狀態
              user_id = event.source.user_id
              set_nickname_session(user_id, team_id, duration_sec=60)
              
              self.reply_text(event, configuration, f"👉 請在 60 秒內直接輸入 {curr_name} 的新暱稱：")
  
      @property
      def instruction_desc(self) -> str:
          return "#設置玩家暱稱 : (限白名單) 調整玩家在 Bot 中的顯示暱稱"
  ```

- [ ] **Step 5: 註冊 Handler 於 bot.py**
  修改 [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py)：
  * 導入處理器（約在第 32 行）：
    ```python
    from src.handlers.set_nickname_handler import SetNicknameHandler
    ```
  * 在 Dispatcher 中註冊（約在第 90 行）：
    ```python
    dispatcher.register(SetNicknameHandler())
    ```

- [ ] **Step 6: 執行測試確認通過**
  Run: `.venv\Scripts\python -m pytest tests/handlers/test_set_nickname_handler.py -v`
  Expected: PASS

- [ ] **Step 7: 提交變更**
  ```bash
  git add src/utils/session_manager.py src/handlers/set_nickname_handler.py bot.py tests/handlers/test_set_nickname_handler.py
  git commit -m "feat: implement session_manager and SetNicknameHandler with setup flows"
  ```

---

### Task 4: IntentRouter 路由攔截與 Session 管理

**Files:**
- Modify: `src/handlers/intent_router.py`
- Test: `tests/test_intent_router.py`

- [ ] **Step 1: 撰寫攔截機制的單元測試**
  修改 [test_intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_intent_router.py)，增加會話攔截與指令覆蓋取消測試。
  
  在 [test_intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_intent_router.py) 尾部加上以下內容：
  ```python
  def test_intent_router_nickname_session_interception():
      from src.handlers.dispatcher import CommandDispatcher
      from src.handlers.intent_router import IntentRouter
      from src.utils.session_manager import set_nickname_session, get_nickname_session
      
      dispatcher = CommandDispatcher()
      router = IntentRouter(dispatcher)
      
      event = MagicMock()
      event.source.user_id = "user_test_intercept"
      event.message.text = "韋哥的新暱稱"
      config = MagicMock()
      
      # 設置 60 秒的有效會話
      set_nickname_session("user_test_intercept", "1", duration_sec=60)
      
      mock_mapping = {"1": "小明"}
      
      with patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": "123"}), \
           patch("src.handlers.intent_router.get_league_team_mapping_path", return_value="dummy_path"), \
           patch("src.handlers.intent_router.os.path.exists", return_value=True), \
           patch("src.handlers.intent_router.open", mock_open(read_data=json.dumps(mock_mapping))) as m_file, \
           patch.object(router, "reply_text") as mock_reply:
          
          router.route(event, config)
          
          # 驗證會話被清空
          assert get_nickname_session("user_test_intercept") is None
          # 驗證寫入新暱稱
          m_file().write.assert_called_once()
          # 驗證回覆
          mock_reply.assert_called_once_with(event, config, "✅ 成功將暱稱修改為：韋哥的新暱稱")
  
  def test_intent_router_nickname_session_reset_by_command():
      from src.handlers.dispatcher import CommandDispatcher
      from src.handlers.intent_router import IntentRouter
      from src.utils.session_manager import set_nickname_session, get_nickname_session
      
      dispatcher = CommandDispatcher()
      dispatcher.dispatch = MagicMock()
      router = IntentRouter(dispatcher)
      
      event = MagicMock()
      event.source.user_id = "user_test_reset"
      event.message.text = "#對戰"
      config = MagicMock()
      
      set_nickname_session("user_test_reset", "1", duration_sec=60)
      
      with patch.object(router, "should_process", return_value=True):
          router.route(event, config)
          # 標準指令將會話清除
          assert get_nickname_session("user_test_reset") is None
          # 正常分發指令
          dispatcher.dispatch.assert_called_once()
  ```

- [ ] **Step 2: 執行測試並驗證失敗**
  Run: `.venv\Scripts\python -m pytest tests/test_intent_router.py -k "nickname_session" -v`
  Expected: FAIL (AssertionError: get_nickname_session 還存在，代表未攔截)

- [ ] **Step 3: 實作 IntentRouter 攔截機制與暱稱更新**
  修改 [intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/intent_router.py)：
  * 導入 `session_manager` 必要函數與路徑模組（約在第 6 行）：
    ```python
    import time
    from src.utils.session_manager import get_nickname_session, clear_nickname_session
    from src.utils.path_utils import get_league_team_mapping_path
    ```
  * 在 `route` 方法的最開頭進行攔截（約在第 50 行，於 `user_text = event.message.text.strip()` 之後）：
    ```python
        user_id = getattr(event.source, "user_id", None)
        if user_id:
            session = get_nickname_session(user_id)
            if session:
                # 用戶發送標準指令 (# 開頭) 則主動重置會話，不進行攔截
                if user_text.startswith("#"):
                    clear_nickname_session(user_id)
                else:
                    team_id = session["team_id"]
                    self._update_team_nickname(team_id, user_text)
                    clear_nickname_session(user_id)
                    self.reply_text(event, configuration, f"✅ 成功將暱稱修改為：{user_text}")
                    return
    ```
  * 在 `IntentRouter` 類別內新增 `_update_team_nickname` 輔助方法：
    ```python
      def _update_team_nickname(self, team_id: str, new_nickname: str) -> None:
          config = load_config()
          league_id = config.get("LEAGUE_ID")
          if not league_id:
              return
          mapping_path = get_league_team_mapping_path(league_id)
          
          mapping = {}
          if os.path.exists(mapping_path):
              try:
                  with open(mapping_path, "r", encoding="utf-8") as f:
                      mapping = json.load(f)
              except Exception:
                  mapping = {}
                  
          mapping[str(team_id)] = new_nickname
          
          try:
              os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
              with open(mapping_path, "w", encoding="utf-8") as f:
                  json.dump(mapping, f, ensure_ascii=False, indent=2)
          except Exception as e:
              import logging
              logging.error(f"[IntentRouter] 寫入暱稱對應檔失敗: {e}")
    ```

- [ ] **Step 4: 執行測試確認通過**
  Run: `.venv\Scripts\python -m pytest tests/test_intent_router.py -k "nickname_session" -v`
  Expected: PASS

- [ ] **Step 5: 提交變更**
  ```bash
  git add src/handlers/intent_router.py tests/test_intent_router.py
  git commit -m "feat: implement nickname input interception and session routing in IntentRouter"
  ```

---

### Task 5: 整合測試與驗證

- [ ] **Step 1: 執行完整測試套件**
  在專案根目錄下，執行完整的測試，確認沒有任何 regression 錯誤。
  Run: `.venv\Scripts\python -m pytest`
  Expected: All 198 tests passed.

- [ ] **Step 2: 提交最終變更**
  ```bash
  git status
  # 確認工作目錄乾淨
  ```
