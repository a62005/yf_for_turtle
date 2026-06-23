# NBA Fantasy - 玩家隊伍傷兵名單查詢實作計畫 (Injury List Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 Yahoo Fantasy NBA Line Bot 新增 `#傷兵 <玩家名稱>` 指令，以獲取該玩家隊伍中所有受傷球員，並以專屬顏色標籤區分嚴重度的 Flex Message 回覆，未配對到玩家時靜默忽略。

**Architecture:** 新增 `InjuryHandler` 用於阻斷、比對與讀取 Yahoo API 成員名單並進行篩選；利用狀態碼（O, INJ, DTD, GTD）映射至 Flex Message 專屬標籤顏色；對接現有 LLM 意圖路由進行自動轉化。

**Tech Stack:** Python 3, Pytest, line-bot-sdk, yahoofantasy

---

### Task 1: 建立 `InjuryHandler` 架構骨架

**Files:**
- Create: `src/handlers/injury_handler.py`

- [ ] **Step 1: 建立 Handler 類別骨架**

建立 `src/handlers/injury_handler.py` 檔案並填入以下內容，此時 `execute` 方法僅留存空實作，並定義基本匹配與描述屬性：

```python
import re
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler

class InjuryHandler(BaseHandler):
    def __init__(self):
        # 匹配 #傷兵 加上後續參數
        self.pattern = re.compile(r"^#傷兵\s*(.+)?$")

    @property
    def instruction_desc(self) -> str:
        return """
- #傷兵 <玩家名稱>：查詢我們聯盟中特定玩家隊伍目前的傷兵名單（例如：#傷兵 韋哥）。
        """

    def can_handle(self, user_text: str) -> bool:
        return bool(self.pattern.match(user_text))

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        # 暫時留空，後續實作核心邏輯
        pass
```

- [ ] **Step 2: 提交代碼**

```bash
git add src/handlers/injury_handler.py
git commit -m "feat: create injury handler skeleton"
```

---

### Task 2: 撰寫 `InjuryHandler` 單元測試

**Files:**
- Create: `tests/handlers/test_injury_handler.py`

- [ ] **Step 1: 撰寫測試案例**

建立 `tests/handlers/test_injury_handler.py` 用以驗證指令匹配、無效參數/無參數時的忽略機制，以及 Mock 模擬 API 回傳傷兵名單時所產生的 Flex Message JSON 結構。

```python
import pytest
from unittest.mock import MagicMock, patch
from src.handlers.injury_handler import InjuryHandler

# 模擬 Yahoo API 物件結構
class MockPlayer:
    def __init__(self, name, status=None, team_abbr="GSW", injury_note=None, display_pos="PG"):
        self.name = type('Name', (), {'full': name})()
        self.status = status
        self.status_full = "Out" if status == "O" else "Game Time Decision"
        self.editorial_team_abbr = team_abbr
        self.injury_note = injury_note
        self.display_position = display_pos

class MockRoster:
    def __init__(self, players):
        self.players = players

class MockTeam:
    def __init__(self, name, team_id, players):
        self.name = name
        self.id = team_id
        self.team_key = f"nba.l.12345.t.{team_id}"
        self._players = players
    def roster(self):
        return MockRoster(self._players)

class MockLeague:
    def __init__(self, teams):
        self._teams = teams
    def teams(self):
        return self._teams

def test_injury_handler_can_handle():
    handler = InjuryHandler()
    assert handler.can_handle("#傷兵 韋哥") is True
    assert handler.can_handle("#傷兵") is True
    assert handler.can_handle("#戰績") is False

@patch("src.handlers.injury_handler.load_config", return_value={"LEAGUE_ID": "12345"})
def test_execute_ignored_on_empty_param(mock_config):
    handler = InjuryHandler()
    event = MagicMock()
    event.message.text = "#傷兵"
    
    with patch.object(handler, "_load_team_mapping", return_value={"1": "韋哥"}):
        # 測試空值直接返回，不會嘗試連線 API
        with patch("src.handlers.injury_handler.YahooFantasyFetcher") as mock_fetcher:
            handler.execute(event, MagicMock())
            mock_fetcher.assert_not_called()

@patch("src.handlers.injury_handler.load_config", return_value={"LEAGUE_ID": "12345"})
def test_execute_ignored_on_unmatched_player(mock_config):
    handler = InjuryHandler()
    event = MagicMock()
    event.message.text = "#傷兵 找不到的玩家"
    
    with patch.object(handler, "_load_team_mapping", return_value={"1": "韋哥"}):
        with patch("src.handlers.injury_handler.YahooFantasyFetcher") as mock_fetcher:
            handler.execute(event, MagicMock())
            mock_fetcher.assert_not_called()

@patch("src.handlers.injury_handler.load_config", return_value={"LEAGUE_ID": "12345"})
def test_execute_success_with_injuries(mock_config):
    handler = InjuryHandler()
    event = MagicMock()
    event.message.text = "#傷兵 韋哥"
    
    # 模擬 韋哥 擁有兩位球員，一傷一健康
    players = [
        MockPlayer("Stephen Curry", status="O", team_abbr="GSW", injury_note="Knee"),
        MockPlayer("Draymond Green", status=None, team_abbr="GSW")
    ]
    mock_team = MockTeam("韋哥隊", "1", players)
    
    # Mock context 與 League 取得對應隊伍
    mock_ctx = MagicMock()
    mock_league = MockLeague([mock_team])
    
    with patch.object(handler, "_load_team_mapping", return_value={"1": "韋哥"}):
        with patch("src.handlers.injury_handler.YahooFantasyFetcher") as mock_fetcher:
            fetcher_inst = mock_fetcher.return_value
            fetcher_inst.ctx = mock_ctx
            fetcher_inst._normalize_league_id.return_value = "nba.l.12345"
            
            with patch("yahoofantasy.League", return_value=mock_league):
                with patch.object(handler, "reply_flex") as mock_reply:
                    handler.execute(event, MagicMock())
                    
                    # 驗證有發出 Flex Message 回覆
                    mock_reply.assert_called_once()
                    args = mock_reply.call_args[0]
                    alt_text = args[2]
                    flex_dict = args[3]
                    
                    assert "韋哥 的傷兵名單" in alt_text
                    assert flex_dict["header"]["contents"][0]["text"] == "🏥 韋哥 的傷兵名單"
                    
                    # 只有 Curry 應該出現在名單中
                    body_contents = flex_dict["body"]["contents"]
                    assert len(body_contents) == 1
                    assert body_contents[0]["contents"][0]["text"] == "Stephen Curry"
                    
                    # 顏色分級為深紅 (O status)
                    assert body_contents[0]["contents"][2]["contents"][0]["color"] == "#922B21"

@patch("src.handlers.injury_handler.load_config", return_value={"LEAGUE_ID": "12345"})
def test_execute_success_all_healthy(mock_config):
    handler = InjuryHandler()
    event = MagicMock()
    event.message.text = "#傷兵 韋哥"
    
    players = [
        MockPlayer("Stephen Curry", status=None, team_abbr="GSW"),
    ]
    mock_team = MockTeam("韋哥隊", "1", players)
    mock_ctx = MagicMock()
    mock_league = MockLeague([mock_team])
    
    with patch.object(handler, "_load_team_mapping", return_value={"1": "韋哥"}):
        with patch("src.handlers.injury_handler.YahooFantasyFetcher") as mock_fetcher:
            fetcher_inst = mock_fetcher.return_value
            fetcher_inst.ctx = mock_ctx
            fetcher_inst._normalize_league_id.return_value = "nba.l.12345"
            
            with patch("yahoofantasy.League", return_value=mock_league):
                with patch.object(handler, "reply_flex") as mock_reply:
                    handler.execute(event, MagicMock())
                    
                    mock_reply.assert_called_once()
                    flex_dict = mock_reply.call_args[0][3]
                    
                    # 驗證全隊健康提示文字
                    body_contents = flex_dict["body"]["contents"]
                    assert "目前全隊球員皆健康！" in body_contents[0]["text"]
```

- [ ] **Step 2: 執行測試並確認其失敗**

執行以下命令確認測試程式因邏輯未實作而失敗：
Run: `.\.venv\Scripts\pytest tests/handlers/test_injury_handler.py -v`
Expected: FAIL (AssertionError)

- [ ] **Step 3: 提交測試代碼**

```bash
git add tests/handlers/test_injury_handler.py
git commit -m "test: add tests for injury handler"
```

---

### Task 3: 實現 `InjuryHandler` 核心邏輯

**Files:**
- Modify: `src/handlers/injury_handler.py`

- [ ] **Step 1: 實作核心執行與 Flex Message 生成代碼**

修改 `src/handlers/injury_handler.py` 將 Yahoo API 讀取、傷兵篩選、顏色比對邏輯完整實作：

```python
import re
import json
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler

from src.config import load_config
from src.fetcher import YahooFantasyFetcher
import yahoofantasy

class InjuryHandler(BaseHandler):
    def __init__(self):
        self.pattern = re.compile(r"^#傷兵\s*(.+)?$")

    @property
    def instruction_desc(self) -> str:
        return """
- #傷兵 <玩家名稱>：查詢我們聯盟中特定玩家隊伍目前的傷兵名單（例如：#傷兵 韋哥）。
        """

    def can_handle(self, user_text: str) -> bool:
        return bool(self.pattern.match(user_text))

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        param = match.group(1)
        if not param:
            logging.info("[InjuryHandler] 空參數指令，直接略過")
            return

        param = param.strip()
        mapping = self._load_team_mapping()
        
        # 尋找匹配的玩家 Team ID
        target_team_id = None
        target_manager_name = None
        for tid, nickname in mapping.items():
            if param.lower() in nickname.lower() or nickname.lower() in param.lower():
                target_team_id = tid
                target_manager_name = nickname
                break
                
        if not target_team_id:
            logging.info(f"[InjuryHandler] 未匹配到聯賽玩家: '{param}'，直接略過")
            return

        logging.info(f"[InjuryHandler] 開始查詢玩家 '{target_manager_name}' (ID: {target_team_id}) 的傷兵...")
        
        config = load_config()
        fetcher = YahooFantasyFetcher(
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET")
        )
        
        league_id = fetcher._normalize_league_id(config["LEAGUE_ID"])
        league = yahoofantasy.League(fetcher.ctx, league_id)
        
        # 獲取對應隊伍
        target_team = None
        for team in league.teams():
            # 確保獲取的 team_id 為字串比對
            if str(getattr(team, "team_id", "")) == str(target_team_id):
                target_team = team
                break
                
        if not target_team:
            logging.error(f"[InjuryHandler] 無法在 Yahoo API 獲取對應的 Team ID: {target_team_id}")
            return
            
        # 篩選傷兵
        injured_players = []
        for player in target_team.roster().players:
            status = getattr(player, "status", None)
            if status and str(status).strip():
                injured_players.append(player)
                
        # 渲染 Flex Message JSON
        flex_dict = self._build_flex_message(target_manager_name, injured_players)
        
        # 發送 Flex
        self.reply_flex(event, configuration, f"🏥 {target_manager_name} 的傷兵名單", flex_dict)

    def _get_status_color(self, status: str) -> str:
        status_upper = str(status).upper()
        # O / INJ / Out (出賽成疑/確定缺陣)：深紅色 (#922B21)
        if status_upper in ("O", "INJ", "OUT"):
            return "#922B21"
        # Doubtful (極低機率出賽)：紅橘色 (#D35400)
        elif status_upper in ("DOUBTFUL", "DOU"):
            return "#D35400"
        # Questionable / DTD (可能缺陣/每日觀察)：橘色 (#E67E22)
        elif status_upper in ("QUESTIONABLE", "QUE", "DTD"):
            return "#E67E22"
        # Probable / GTD (高機率出賽/賽前決定)：黃橘色/黃色 (#F1C40F)
        elif status_upper in ("PROBABLE", "PRO", "GTD"):
            return "#F1C40F"
        # 其他狀態 (如 SSP 禁賽)：灰色 (#7F8C8D)
        else:
            return "#7F8C8D"

    def _build_flex_message(self, manager_name: str, players: list) -> dict:
        bubble = {
            "type": "bubble",
            "header": {
                "type": "box",
                "layout": "vertical",
                "backgroundColor": "#2C3E50",
                "contents": [
                    {
                        "type": "text",
                        "text": f"🏥 {manager_name} 的傷兵名單",
                        "weight": "bold",
                        "size": "lg",
                        "color": "#FFFFFF"
                    }
                ]
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": []
            }
        }
        
        body_contents = bubble["body"]["contents"]
        
        if not players:
            # 全隊健康
            body_contents.append({
                "type": "text",
                "text": "🟢 目前全隊球員皆健康！",
                "align": "center",
                "weight": "bold",
                "size": "md",
                "color": "#27AE60",
                "margin": "md"
            })
            return bubble

        # 有傷兵球員，生成列表
        for p in players:
            name = getattr(p.name, "full", "Unknown Player")
            pos = getattr(p, "display_position", "Util")
            team_abbr = getattr(p, "editorial_team_abbr", "NBA")
            status = getattr(p, "status", "INJ")
            injury_note = getattr(p, "injury_note", "Injured")
            
            color = self._get_status_color(status)
            
            player_row = {
                "type": "box",
                "layout": "horizontal",
                "align": "center",
                "spacing": "sm",
                "contents": [
                    # 1. 姓名
                    {
                        "type": "text",
                        "text": name,
                        "weight": "bold",
                        "size": "sm",
                        "color": "#111111",
                        "flex": 4
                    },
                    # 2. 位置與球隊
                    {
                        "type": "text",
                        "text": f"{pos} - {team_abbr}",
                        "size": "xs",
                        "color": "#555555",
                        "flex": 3
                    },
                    # 3. 傷病標籤
                    {
                        "type": "box",
                        "layout": "vertical",
                        "backgroundColor": color,
                        "cornerRadius": "sm",
                        "width": "42px",
                        "height": "20px",
                        "justifyContent": "center",
                        "alignItems": "center",
                        "contents": [
                            {
                                "type": "text",
                                "text": str(status),
                                "color": "#FFFFFF",
                                "size": "xxs",
                                "weight": "bold",
                                "align": "center"
                            }
                        ],
                        "flex": 0
                    },
                    # 4. 傷病細節
                    {
                        "type": "text",
                        "text": injury_note,
                        "size": "xxs",
                        "color": "#777777",
                        "align": "end",
                        "flex": 2
                    }
                ]
            }
            body_contents.append(player_row)
            
        return bubble
```

- [ ] **Step 2: 重新運行單元測試確認通過**

Run: `.\.venv\Scripts\pytest tests/handlers/test_injury_handler.py -v`
Expected: PASS

- [ ] **Step 3: 提交程式代碼**

```bash
git add src/handlers/injury_handler.py
git commit -m "feat: implement InjuryHandler logic and color styling"
```

---

### Task 4: 註冊 `InjuryHandler` 至 Dispatcher

**Files:**
- Modify: `bot.py:72-80`

- [ ] **Step 1: 在 `bot.py` 中引入並註冊 `InjuryHandler`**

打開 `bot.py` 檔案，在文件頭部引入 `InjuryHandler`，並將其註冊至 `CommandDispatcher`：

```python
# 修改 bot.py
# 尋找以下引入段落：
from src.handlers.football_handler import FootballHandler
# 在其下方加入：
from src.handlers.injury_handler import InjuryHandler

# 尋找註冊 handler 的段落：
# dispatcher.register(FootballHandler())
# 在其下方加入：
dispatcher.register(InjuryHandler())
```

- [ ] **Step 2: 執行測試並驗證系統指令包含新指令**

我們可以執行 dispatcher 的指令獲取測試，以確保新的 Handler 已經成功載入並可輸出正確指令說明：
Run: `.\.venv\Scripts\pytest tests/test_dispatcher_instruction.py -v`
Expected: PASS

- [ ] **Step 3: 提交修改**

```bash
git add bot.py
git commit -m "feat: register InjuryHandler in bot.py"
```

---

### Task 5: 驗證意圖路由 (Intent Router) 與 LLM 轉化

**Files:**
- Modify: `tests/test_intent_router.py`

- [ ] **Step 1: 新增 LLM 路由測試案例**

我們在 `tests/test_intent_router.py` 尾部加上對 `#傷兵` 自然語言意圖對應至標準指令的驗證，以確保意圖路由功能正常發揮：

```python
# 在 tests/test_intent_router.py 末尾添加

@patch('src.llm.llm_agent.LLMAgent.analyze_intent')
def test_router_converts_injury_command_and_dispatches(mock_analyze):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 模擬使用者發問：看韋哥傷兵
    event = create_mock_event("幫我看一下韋哥有誰受傷", chat_type="user")
    mock_analyze.return_value = {"is_command": True, "command_text": "#傷兵 韋哥", "reply_text": None}
    
    config = Configuration()
    config.access_token = "dummy_access_token"
    
    router.route(event, config)
    mock_analyze.assert_called_once()
    # 確保成功轉交 dispatcher 處理，且其內容被置換為 "#傷兵 韋哥"
    dispatcher.handle.assert_called_once_with(event, config)
    assert event.message.text == "#傷兵 韋哥"
```

- [ ] **Step 2: 執行所有測試並確保無 regressions**

Run: `.\.venv\Scripts\pytest -v`
Expected: ALL PASS

- [ ] **Step 3: 提交修改**

```bash
git add tests/test_intent_router.py
git commit -m "test: add integration test for injury command LLM routing"
```
