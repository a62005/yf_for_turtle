# NBA Fantasy - 玩家隊伍傷兵名單查詢實作計畫 (Injury List Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 更新 Yahoo Fantasy NBA Line Bot 的 `#傷兵 <玩家名稱>` 功能。去除深色 Header 背景與 icon，改為預設白底風格；將守備位置與 NBA 球隊欄位移除；並將球員姓名縮寫化，合併受傷部位於同一列中。

**Architecture:** 
1. 實作 `abbreviate_player_name` 姓名縮寫工具函數 (首字字母 + 點 + 空格 + 姓氏，例如 `S. Curry` 或 `L. James`)。
2. 修改 `InjuryHandler` 中的 `_build_flex_message` 邏輯，取消 Flex 的 `header` 區塊，直接將姓名大字與球隊小字置於 `body` 首段做為白底 Header。
3. 採用 `spans` 將縮寫姓名與受傷部位合併（例如 `L. James - Knee`）。
4. 更新單元測試以適應全新的 Flex Message JSON 結構。

**Tech Stack:** Python 3, Pytest, line-bot-sdk, yahoofantasy

---

### Task 1: 撰寫預期失敗的單元測試

**Files:**
- Modify: `tests/handlers/test_injury_handler.py`

- [ ] **Step 1: 修改測試案例**

修改 `tests/handlers/test_injury_handler.py` 以反映全新的排版需求：
1. 驗證 Header 放置於 `body` 內容中（白底極簡風）。
2. 驗證球員人名縮寫。
3. 驗證姓名與傷勢透過 `spans` 合併。
4. 驗證移除守備位置與 NBA 球隊欄位。

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
        self.team_id = team_id
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
    
    players = [
        MockPlayer("Stephen Curry", status="O", team_abbr="GSW", injury_note="Knee"),
        MockPlayer("Draymond Green", status=None, team_abbr="GSW")
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
                    args = mock_reply.call_args[0]
                    alt_text = args[2]
                    flex_dict = args[3]
                    
                    assert "韋哥 的傷兵名單" in alt_text
                    
                    # 1. 驗證白底 Header (置於 body 的首個元件)
                    assert "header" not in flex_dict
                    body_contents = flex_dict["body"]["contents"]
                    header_box = body_contents[0]
                    assert header_box["contents"][0]["text"] == "韋哥"
                    assert header_box["contents"][1]["text"] == "韋哥隊"
                    
                    # 2. 驗證球員數據列 (Curry 應該被縮寫為 S. Curry，並與 - Knee 合併)
                    player_row = body_contents[1]
                    name_span_box = player_row["contents"][0]
                    assert name_span_box["type"] == "text"
                    assert name_span_box["contents"][0]["text"] == "S. Curry"
                    assert name_span_box["contents"][1]["text"] == " - Knee"
                    
                    # 3. 驗證狀態標籤的背景顏色 (O 為深紅)
                    status_box = player_row["contents"][1]
                    assert status_box["backgroundColor"] == "#922B21"
                    assert status_box["contents"][0]["text"] == "O"

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
                    
                    body_contents = flex_dict["body"]["contents"]
                    assert "目前全隊球員皆健康！" in body_contents[1]["text"]
```

- [ ] **Step 2: 執行測試確認失敗**

Run: `.\.venv\Scripts\pytest tests/handlers/test_injury_handler.py -v`
Expected: FAIL (AssertionError / KeyError)

- [ ] **Step 3: 提交變更**

```bash
git add tests/handlers/test_injury_handler.py
git commit -m "test: update injury handler test cases for new visual spec"
```

---

### Task 2: 實現球員人名縮寫與極簡白底 Flex Message

**Files:**
- Modify: `src/handlers/injury_handler.py`

- [ ] **Step 1: 實作新排版邏輯與 `abbreviate_player_name` 函數**

修改 `src/handlers/injury_handler.py` 實作符合規格書設計的排版邏輯：

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
        
        target_team = None
        for team in league.teams():
            if str(getattr(team, "team_id", "")) == str(target_team_id):
                target_team = team
                break
                
        if not target_team:
            logging.error(f"[InjuryHandler] 無法在 Yahoo API 獲取對應的 Team ID: {target_team_id}")
            return
            
        injured_players = []
        for player in target_team.roster().players:
            status = getattr(player, "status", None)
            if status and str(status).strip():
                injured_players.append(player)
                
        official_name = getattr(target_team, "name", "Unknown Team")
        flex_dict = self._build_flex_message(target_manager_name, official_name, injured_players)
        
        self.reply_flex(event, configuration, f"🏥 {target_manager_name} 的傷兵名單", flex_dict)

    def _abbreviate_player_name(self, full_name: str) -> str:
        parts = str(full_name).strip().split()
        if len(parts) >= 2:
            first_initial = parts[0][0]
            last_name = " ".join(parts[1:])
            return f"{first_initial}. {last_name}"
        return full_name

    def _get_status_color(self, status: str) -> str:
        status_upper = str(status).upper()
        if status_upper in ("O", "INJ", "OUT"):
            return "#922B21"
        elif status_upper in ("DOUBTFUL", "DOU"):
            return "#D35400"
        elif status_upper in ("QUESTIONABLE", "QUE", "DTD"):
            return "#E67E22"
        elif status_upper in ("PROBABLE", "PRO", "GTD"):
            return "#F1C40F"
        else:
            return "#7F8C8D"

    def _build_flex_message(self, manager_name: str, official_name: str, players: list) -> dict:
        bubble = {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    # 1. 玩家資訊標頭 (Header Box) - 置於 Body 內以達白底極簡風
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": [
                            {"type": "text", "text": manager_name, "weight": "bold", "size": "xl", "color": "#111111"},
                            {"type": "text", "text": official_name, "size": "sm", "color": "#555555"}
                        ]
                    }
                ]
            }
        }
        
        body_contents = bubble["body"]["contents"]
        
        if not players:
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
            full_name = getattr(p.name, "full", "Unknown Player")
            abbrev_name = self._abbreviate_player_name(full_name)
            
            status = getattr(p, "status", "INJ")
            injury_note = getattr(p, "injury_note", "Injured")
            
            color = self._get_status_color(status)
            
            player_row = {
                "type": "box",
                "layout": "horizontal",
                "align": "center",
                "spacing": "sm",
                "contents": [
                    # 1. 姓名縮寫 + 傷勢
                    {
                        "type": "text",
                        "contents": [
                            {"type": "span", "text": abbrev_name, "weight": "bold", "size": "sm", "color": "#111111"},
                            {"type": "span", "text": f" - {injury_note}", "size": "xxs", "color": "#777777"}
                        ],
                        "flex": 1
                    },
                    # 2. 傷病標籤
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
                    }
                ]
            }
            body_contents.append(player_row)
            
        return bubble
```

- [ ] **Step 2: 重新執行測試驗證通過**

Run: `.\.venv\Scripts\pytest -v`
Expected: ALL PASS (149 passed)

- [ ] **Step 3: 提交變更**

```bash
git add src/handlers/injury_handler.py
git commit -m "feat: simplify injury flex layout to white background and abbreviate names"
```
