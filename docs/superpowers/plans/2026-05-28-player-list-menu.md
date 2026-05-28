# LINE Bot #玩家與#對戰無暱稱時顯示垂直玩家選單 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 當 LINE Bot 接收到只包含 `#玩家` 或 `#對戰`（或僅有空白）的指令時，動態渲染 `team_mapping.json` 所有玩家，回傳垂直排列的 Flex Message 按鈕選單，點擊任一玩家即自動發送對應暱稱的數據查詢。

**Architecture:** 重構 `BaseHandler` 以納入 `_load_team_mapping`、`reply_flex` 以及全新 `reply_player_list` 共用方法。修改 `UserStatsHandler` 和 `MatchupHandler` 的正則表達式，適配無暱稱的情況，並在 `execute` 中進行控制流分支路由。

**Tech Stack:** Python, pytest, LINE Bot SDK v3

---

### Task 1: 重構 BaseHandler 納入共用邏輯與玩家列表發送方法

**Files:**
- Modify: `src/handlers/base_handler.py`

- [ ] **Step 1: 編輯 `src/handlers/base_handler.py`**
  引入 LINE API 必要類別，定義並實作 `_load_team_mapping`、`reply_flex` 以及 `reply_player_list`。
  
  在 `src/handlers/base_handler.py` 寫入以下完整實作：
  ```python
  import os
  import json
  import logging
  from abc import ABC, abstractmethod
  from linebot.v3.webhooks import MessageEvent
  from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, FlexMessage, FlexContainer, Configuration
  from src.config import load_config

  class BaseHandler(ABC):
      """Base interface for all bot message handlers."""
      
      @abstractmethod
      def can_handle(self, user_text: str) -> bool:
          """Return True if this handler can process the given text."""
          pass
          
      @abstractmethod
      def execute(self, event: MessageEvent, configuration: Configuration) -> None:
          """Execute the core logic and handle LINE API replies."""
          pass

      def _load_team_mapping(self) -> dict:
          """Load and return the team mapping from json config file."""
          config = load_config()
          mapping_file = config.get("TEAM_MAPPING_FILE", "team_mapping.json")
          if os.path.exists(mapping_file):
              try:
                  with open(mapping_file, "r", encoding="utf-8") as f:
                      return json.load(f)
              except Exception as e:
                  logging.error(f"Failed to load team mapping in BaseHandler: {e}")
          return {}

      def reply_flex(self, event: MessageEvent, configuration: Configuration, alt_text: str, flex_dict: dict) -> None:
          """Reply to user with a LINE Flex Message."""
          flex_container = FlexContainer.from_json(json.dumps(flex_dict))
          with ApiClient(configuration) as api_client:
              MessagingApi(api_client).reply_message(
                  ReplyMessageRequest(
                      reply_token=event.reply_token,
                      messages=[FlexMessage(alt_text=alt_text, contents=flex_container)]
                  )
              )

      def reply_player_list(self, event: MessageEvent, configuration: Configuration, is_matchup: bool) -> None:
          """Reply with a vertical player list Flex Message."""
          mapping = self._load_team_mapping()
          if not mapping:
              logging.warning("No team mapping found when trying to reply player list.")
              return

          # Ensure nicknames are unique and preserved
          nicknames = []
          for name in mapping.values():
              if name not in nicknames:
                  nicknames.append(name)

          title = "⚔️ 對戰比分查詢" if is_matchup else "🙋‍♂️ 玩家數據查詢"
          subtitle = "請點擊下方玩家，將自動搜尋該數據"
          command_prefix = "#對戰" if is_matchup else "#玩家"

          buttons = []
          for name in nicknames:
              buttons.append({
                  "type": "button",
                  "action": {
                      "type": "message",
                      "label": name,
                      "text": f"{command_prefix} {name}"
                  },
                  "style": "secondary",
                  "height": "sm"
              })

          flex_dict = {
              "type": "bubble",
              "header": {
                "type": "box",
                "layout": "vertical",
                "spacing": "xs",
                "contents": [
                  {"type": "text", "text": title, "weight": "bold", "size": "lg", "color": "#111111"},
                  {"type": "text", "text": subtitle, "size": "xs", "color": "#777777"}
                ]
              },
              "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": buttons
              }
          }

          self.reply_flex(event, configuration, f"{title}選單", flex_dict)
  ```

- [ ] **Step 2: 執行既有測試驗證基本功能未損毀**
  執行：`pytest tests/ -v`
  預期：所有既有測試皆應能正常 PASS。

- [ ] **Step 3: Commit 暫存變更**
  執行：
  ```bash
  git add src/handlers/base_handler.py
  git commit -m "refactor: elevate shared mapping loading and flex reply to BaseHandler"
  ```

---

### Task 2: 更新與測試 UserStatsHandler 適配無暱稱指令

**Files:**
- Modify: `src/handlers/user_stats_handler.py`
- Modify: `tests/test_user_stats_handler.py`

- [ ] **Step 1: 在 `tests/test_user_stats_handler.py` 寫入 failing 測試**
  編輯 `tests/test_user_stats_handler.py`：
  - 更新第一段測試 `test_user_stats_handler_can_handle` 以加入對 `#玩家` 和 `#玩家  ` 的 `can_handle` 斷言：
    ```python
    assert handler.can_handle("#玩家") is True
    assert handler.can_handle("#玩家  ") is True
    ```
  - 新增測試 `test_execute_user_stats_no_nickname` 測試當不輸入暱稱時，會呼叫 `reply_player_list`：
    ```python
    def test_execute_user_stats_no_nickname(mocker):
        handler = UserStatsHandler()
        
        # Mock message event text
        mock_event = MagicMock()
        mock_event.message.text = "#玩家"
        
        mock_config = MagicMock()
        
        # Spy / Mock reply_player_list method
        mock_reply_player_list = mocker.patch.object(handler, "reply_player_list")
        
        handler.execute(mock_event, mock_config)
        
        mock_reply_player_list.assert_called_once_with(mock_event, mock_config, is_matchup=False)
    ```

- [ ] **Step 2: 運行測試以驗證測試失敗**
  執行：`pytest tests/test_user_stats_handler.py -v`
  預期：FAIL（`can_handle("#玩家")` 應為 False，且找不到對應行為）。

- [ ] **Step 3: 修改 `src/handlers/user_stats_handler.py` 實作**
  修改內容：
  - 將 `self.pattern` 改為 `re.compile(r"^#玩家(?:\s+(.+))?$")`。
  - 移除重複的 `_load_team_mapping` 與 `reply_flex` 方法（由 `BaseHandler` 繼承提供）。
  - 更新 `can_handle` 方法，容許無暱稱（包括暱稱去除空白後為空字串）時回傳 `True`。
  - 更新 `execute` 方法，當沒有暱稱時，調用 `self.reply_player_list(event, configuration, is_matchup=False)`，並直接 `return`。
  
  變更後 `UserStatsHandler` 前半部應如下：
  ```python
  class UserStatsHandler(BaseHandler):
      def __init__(self):
          self.pattern = re.compile(r"^#玩家(?:\s+(.+))?$")

      def can_handle(self, user_text: str) -> bool:
          user_text = user_text.strip()
          match = self.pattern.match(user_text)
          if not match:
              return False
              
          nickname_raw = match.group(1)
          if not nickname_raw:
              return True
              
          nickname = nickname_raw.strip()
          if not nickname:
              return True
              
          mapping = self._load_team_mapping()
          return nickname in mapping.values()
  ```
  `execute` 開頭如下：
  ```python
      def execute(self, event: MessageEvent, configuration: Configuration) -> None:
          user_text = event.message.text.strip()
          match = self.pattern.match(user_text)
          if not match:
              return

          nickname_raw = match.group(1)
          nickname = nickname_raw.strip() if nickname_raw else ""
          
          if not nickname:
              self.reply_player_list(event, configuration, is_matchup=False)
              return
              
          # 原有尋找 Team ID 數據邏輯...
  ```

- [ ] **Step 4: 再次運行測試驗證通過**
  執行：`pytest tests/test_user_stats_handler.py -v`
  預期：PASS。

- [ ] **Step 5: Commit 變更**
  執行：
  ```bash
  git add src/handlers/user_stats_handler.py tests/test_user_stats_handler.py
  git commit -m "feat: optimize #玩家 command to reply vertical player list when nickname is missing"
  ```

---

### Task 3: 更新與測試 MatchupHandler 適配無暱稱指令

**Files:**
- Modify: `src/handlers/matchup_handler.py`
- Modify: `tests/test_matchup_handler.py`

- [ ] **Step 1: 在 `tests/test_matchup_handler.py` 寫入 failing 測試**
  編輯 `tests/test_matchup_handler.py`：
  - 更新測試 `can_handle` 斷言以加入對 `#對戰` 和 `#對戰 ` 的驗證：
    ```python
    assert handler.can_handle("#對戰") is True
    assert handler.can_handle("#對戰 ") is True
    ```
  - 新增測試 `test_execute_matchup_no_nickname` 測試當不輸入暱稱時，會呼叫 `reply_player_list`：
    ```python
    def test_execute_matchup_no_nickname(mocker):
        handler = MatchupHandler()
        
        mock_event = MagicMock()
        mock_event.message.text = "#對戰"
        
        mock_config = MagicMock()
        mock_reply_player_list = mocker.patch.object(handler, "reply_player_list")
        
        handler.execute(mock_event, mock_config)
        
        mock_reply_player_list.assert_called_once_with(mock_event, mock_config, is_matchup=True)
    ```

- [ ] **Step 2: 運行測試以驗證測試失敗**
  執行：`pytest tests/test_matchup_handler.py -v`
  預期：FAIL（`can_handle("#對戰")` 應為 False，且找不到對應行為）。

- [ ] **Step 3: 修改 `src/handlers/matchup_handler.py` 實作**
  修改內容：
  - 將 `self.pattern` 改為 `re.compile(r"^#對戰(?:\s+(.+))?$")`。
  - 移除重複的 `_load_team_mapping` 與 `reply_flex` 方法。
  - 更新 `can_handle` 方法，容許無暱稱（包括暱稱去除空白後為空字串）時回傳 `True`。
  - 更新 `execute` 方法，當沒有暱稱時，調用 `self.reply_player_list(event, configuration, is_matchup=True)`，並直接 `return`。
  
  變更後 `MatchupHandler` 前半部與 `can_handle`：
  ```python
  class MatchupHandler(BaseHandler):
      def __init__(self):
          self.pattern = re.compile(r"^#對戰(?:\s+(.+))?$")

      def can_handle(self, user_text: str) -> bool:
          user_text = user_text.strip()
          match = self.pattern.match(user_text)
          if not match:
              return False
          
          nickname_raw = match.group(1)
          if not nickname_raw:
              return True
              
          nickname = nickname_raw.strip()
          if not nickname:
              return True
              
          mapping = self._load_team_mapping()
          return nickname in mapping.values()
  ```
  `execute` 開頭如下：
  ```python
      def execute(self, event: MessageEvent, configuration: Configuration) -> None:
          user_text = event.message.text.strip()
          match = self.pattern.match(user_text)
          if not match:
              return

          nickname_raw = match.group(1)
          nickname = nickname_raw.strip() if nickname_raw else ""
          
          if not nickname:
              self.reply_player_list(event, configuration, is_matchup=True)
              return
              
          # 原有尋找 Team ID 對戰邏輯...
  ```

- [ ] **Step 4: 再次運行測試驗證通過**
  執行：`pytest tests/test_matchup_handler.py -v`
  預期：PASS。

- [ ] **Step 5: Commit 變更**
  執行：
  ```bash
  git add src/handlers/matchup_handler.py tests/test_matchup_handler.py
  git commit -m "feat: optimize #對戰 command to reply vertical player list when nickname is missing"
  ```

---

### Task 4: 完整專案測試驗證

- [ ] **Step 1: 運行全專案測試套件**
  執行：`pytest tests/ -v`
  預期：所有單元測試皆順利通過，沒有任何 Regression。
