# 實時一對一對戰數據查詢 (#對戰) 實作計畫 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 `#對戰 [暱稱]` 指令，透過單次 API 請求，獲取當週 Matchup 對戰雙方數據，並渲染出終極視覺邏輯統一的極簡風對稱比分 Flex Message。

**Architecture:** 
1. 擴充 `YahooFantasyFetcher`，新增 `fetch_matchups` 方法，單次抓取當週聯賽 Scoreboard XML 並解析出所有對戰組合。
2. 建立 `MatchupHandler` 處理 `#對戰 [暱稱]` 觸發，反查 `team_id` 後從 scoreboard 中精準尋找其當週 matchup。
3. 實作 9-Cat 勝負判定（TO 越小越好，其餘越大越好），統計即時總比分，並將命中率為 0 或空值者轉為 `-`。
4. 渲染三層 Header（暱稱 VS、Fantasy 官方隊名、比分）與 Body 11 行指標數據的 Flex Message，其中比分與 Body 指標之領先方一律黑色較大，落後方一律灰色較小，輔助列正常顯示。
5. 註冊至 `CommandDispatcher` 並以 pytest 完成完整單元測試。

**Tech Stack:** Python 3.10+, yahoofantasy SDK, linebot SDK v3, pytest, pytz.

---

## 檔案架構與職責設計 (File Structure & Decomposition)

本次實作將修改與建立以下檔案，確保高內聚、低耦合且職責明確：
1.  **[src/fetcher.py](file:///Users/yilin/Python/yf_for_turtle/src/fetcher.py) (修改)**:
    *   **職責**：新增 `fetch_matchups`，單次拉取 Yahoo Scoreboard API 並精準解析 matchups 樹狀 XML 結構，將數據打包成乾淨的 Python 字典格式回傳，並在 API 層先做好 FGM/A 與 FTM/A 的拼接。
2.  **[src/handlers/matchup_handler.py](file:///Users/yilin/Python/yf_for_turtle/src/handlers/matchup_handler.py) (新建)**:
    *   **職責**：專責處理 `#對戰` 指令的生命週期、暱稱反查、雙方角色錨定、9-Cat 指標勝負判定、零值轉 `-`、以及終極視覺對稱 Flex Message JSON 字典組裝。
3.  **[bot.py](file:///Users/yilin/Python/yf_for_turtle/bot.py) (修改)**:
    *   **職責**：導入並向 `CommandDispatcher` 註冊新建立的 `MatchupHandler`。
4.  **[tests/test_fetcher_matchup.py](file:///Users/yilin/Python/yf_for_turtle/tests/test_fetcher_matchup.py) (新建)**:
    *   **職責**：以 Mock XML 測試 `fetcher.fetch_matchups` 是否能正確解析 XML 中的 matchups 以及指標值。
5.  **[tests/test_matchup_handler.py](file:///Users/yilin/Python/yf_for_turtle/tests/test_matchup_handler.py) (新建)**:
    *   **職責**：以 TDD 精神測試 `MatchupHandler` 的指令匹配、暱稱反查、雙方勝負統計、領先大黑/落後小灰樣式標記、零值 `-` 轉換以及產出的 Flex Message bubble 是否結構完整。

---

## 實作任務清單 (Tasks Checklist)

### Task 1: 實作 Scoreboard API 解析功能

**Files:**
*   Modify: `src/fetcher.py`
*   Create: `tests/test_fetcher_matchup.py`

- [ ] **Step 1: 撰寫失敗的單元測試 (TDD)**
    在 `tests/test_fetcher_matchup.py` 寫入測試，模擬 Scoreboard API XML 的回傳，並調用尚未實作的 `fetch_matchups`。

```python
import pytest
from src.fetcher import YahooFantasyFetcher

def test_fetch_matchups_parsing(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    
    mock_xml = """<?xml version="1.0" encoding="UTF-8"?>
    <fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league>
        <scoreboard>
          <matchups>
            <matchup>
              <teams>
                <team>
                  <team_id>1</team_id>
                  <name>Vigo's Superteam</name>
                  <team_stats>
                    <stats>
                      <stat><stat_id>4</stat_id><value>180</value></stat>
                      <stat><stat_id>3</stat_id><value>350</value></stat>
                      <stat><stat_id>5</stat_id><value>0.514</value></stat>
                      <stat><stat_id>7</stat_id><value>20</value></stat>
                      <stat><stat_id>6</stat_id><value>25</value></stat>
                      <stat><stat_id>8</stat_id><value>0.800</value></stat>
                      <stat><stat_id>10</stat_id><value>35</value></stat>
                      <stat><stat_id>12</stat_id><value>450</value></stat>
                      <stat><stat_id>15</stat_id><value>110</value></stat>
                      <stat><stat_id>16</stat_id><value>95</value></stat>
                      <stat><stat_id>17</stat_id><value>25</value></stat>
                      <stat><stat_id>18</stat_id><value>12</value></stat>
                      <stat><stat_id>19</stat_id><value>32</value></stat>
                    </stats>
                  </team_stats>
                </team>
                <team>
                  <team_id>2</team_id>
                  <name>Jerry's Awesome</name>
                  <team_stats>
                    <stats>
                      <stat><stat_id>4</stat_id><value>165</value></stat>
                      <stat><stat_id>3</stat_id><value>340</value></stat>
                      <stat><stat_id>5</stat_id><value>0.485</value></stat>
                      <stat><stat_id>7</stat_id><value>15</value></stat>
                      <stat><stat_id>6</stat_id><value>20</value></stat>
                      <stat><stat_id>8</stat_id><value>0.750</value></stat>
                      <stat><stat_id>10</stat_id><value>42</value></stat>
                      <stat><stat_id>12</stat_id><value>410</value></stat>
                      <stat><stat_id>15</stat_id><value>125</value></stat>
                      <stat><stat_id>16</stat_id><value>80</value></stat>
                      <stat><stat_id>17</stat_id><value>20</value></stat>
                      <stat><stat_id>18</stat_id><value>18</value></stat>
                      <stat><stat_id>19</stat_id><value>38</value></stat>
                    </stats>
                  </team_stats>
                </team>
              </teams>
            </matchup>
          </matchups>
        </scoreboard>
      </league>
    </fantasy_content>
    """
    mock_ctx.make_request.return_value = mock_xml
    
    fetcher = YahooFantasyFetcher(team_mapping={"1": "韋哥", "2": "Jerry"})
    matchups = fetcher.fetch_matchups("12345", 24)
    
    assert len(matchups) == 1
    m = matchups[0]
    assert m["team1"]["team_id"] == "1"
    assert m["team1"]["name"] == "韋哥"
    assert m["team1"]["official_name"] == "Vigo's Superteam"
    assert m["team1"]["stats"]["FG%"] == "0.514"
    assert m["team1"]["stats"]["PTS"] == "450"
    assert m["team1"]["stats"]["FGM/FGA"] == "180/350"
    
    assert m["team2"]["team_id"] == "2"
    assert m["team2"]["name"] == "Jerry"
    assert m["team2"]["stats"]["FTM/FTA"] == "15/20"
```

- [ ] **Step 2: 執行測試並確認其失敗**
    執行: `pytest tests/test_fetcher_matchup.py -v`
    預期結果: FAIL (AttributeError: 'YahooFantasyFetcher' object has no attribute 'fetch_matchups')

- [ ] **Step 3: 在 `src/fetcher.py` 實作 `fetch_matchups` 方法**
    在 `src/fetcher.py` 底部新增以下實作：

```python
    def fetch_matchups(self, league_id: str, week: int) -> list:
        """Fetch matchups with detailed team stats for a specific week from the scoreboard."""
        league_id = self._normalize_league_id(league_id)
        url = f"league/{league_id}/scoreboard;week={week}"
        
        matchups_data = []
        try:
            data = self.ctx.make_request(url)
            root = ET.fromstring(data)
            
            for matchup in self._find_all_nodes(root, './/ns:matchup'):
                teams = []
                for team in self._find_all_nodes(matchup, './/ns:team'):
                    team_id_node = self._find_node(team, 'ns:team_id')
                    if team_id_node is None:
                        continue
                    team_id = team_id_node.text
                    
                    # Name node
                    name_node = self._find_node(team, 'ns:name')
                    official_name = name_node.text if name_node is not None else "Unknown Team"
                    team_name = self.get_team_name(team_id, official_name)
                    
                    # Parse stats
                    stats_dict = {}
                    stat_nodes = self._find_all_nodes(team, './/ns:team_stats/ns:stats/ns:stat')
                    for node in stat_nodes:
                        s_id_node = self._find_node(node, 'ns:stat_id')
                        s_val_node = self._find_node(node, 'ns:value')
                        if s_id_node is not None and s_id_node.text:
                            s_id = s_id_node.text
                            s_val = s_val_node.text if s_val_node is not None else "0"
                            label = translate_stat_id(s_id)
                            stats_dict[label] = s_val if s_val is not None else "0"
                    
                    # 拼接出手數與分母輔助項
                    if "FGM/FGA" not in stats_dict:
                        fgm = stats_dict.get("stat_4")
                        fga = stats_dict.get("stat_3")
                        if fgm is not None and fga is not None:
                            stats_dict["FGM/FGA"] = f"{fgm}/{fga}" if fga != "0" else "0/0"
                    if "FTM/FTA" not in stats_dict:
                        ftm = stats_dict.get("stat_7")
                        fta = stats_dict.get("stat_6")
                        if ftm is not None and fta is not None:
                            stats_dict["FTM/FTA"] = f"{ftm}/{fta}" if fta != "0" else "0/0"
                    
                    teams.append({
                        "team_id": team_id,
                        "name": team_name,
                        "official_name": official_name,
                        "stats": stats_dict
                    })
                
                if len(teams) == 2:
                    matchups_data.append({
                        "team1": teams[0],
                        "team2": teams[1]
                    })
        except Exception as e:
            logging.error(f"Error parsing matchups: {e}")
        return matchups_data
```

- [ ] **Step 4: 執行測試並確認通過**
    執行: `pytest tests/test_fetcher_matchup.py -v`
    預期結果: PASS

- [ ] **Step 5: 提交至 Git**
    執行:
    ```bash
    git add src/fetcher.py tests/test_fetcher_matchup.py
    git commit -m "feat: implement fetch_matchups in YahooFantasyFetcher with XML parser and unit tests"
    ```

---

### Task 2: 實作 MatchupHandler 的比對與勝負統計邏輯

**Files:**
*   Create: `src/handlers/matchup_handler.py`
*   Create: `tests/test_matchup_handler.py`

- [ ] **Step 1: 撰寫比對邏輯與零值轉換的失敗測試 (TDD)**
    在 `tests/test_matchup_handler.py` 寫入測試，特別測試：
    1. `can_handle` 暱稱匹配。
    2. 比分大小判定（TO 越少越好，其餘越大越好）。
    3. 空值或 `0.0`/`0` 的命中率會被優雅轉成 `-`。
    4. 正確統計比分並標註勝負狀態。

```python
import pytest
from src.handlers.matchup_handler import MatchupHandler

def test_matchup_handler_can_handle(mocker):
    mocker.patch("src.handlers.matchup_handler.load_config", return_value={"TEAM_MAPPING_FILE": "team_mapping.json"})
    mocker.patch.object(MatchupHandler, "_load_team_mapping", return_value={"1": "韋哥", "2": "Jerry"})
    
    handler = MatchupHandler()
    assert handler.can_handle("#對戰 韋哥") is True
    assert handler.can_handle("#對戰 Jerry") is True
    assert handler.can_handle("#對戰 詹姆斯") is False # 沒登錄 -> 略過
    assert handler.can_handle("#對戰") is False

def test_matchup_compare_logic():
    handler = MatchupHandler()
    
    # 測試 TO 越小越好，其餘越大越好，零值轉 "-"
    my_stats = {
        "FG%": "0.514", "FGM/FGA": "180/350", "FT%": "0.0", "FTM/FTA": "0/0",
        "3PTM": "35", "PTS": "450", "REB": "110", "AST": "95", "STL": "25", "BLK": "12", "TO": "32"
    }
    opp_stats = {
        "FG%": "0.485", "FGM/FGA": "165/340", "FT%": "0.750", "FTM/FTA": "15/20",
        "3PTM": "42", "PTS": "410", "REB": "125", "AST": "80", "STL": "20", "BLK": "18", "TO": "38"
    }
    
    comp_res = handler.compare_stats(my_stats, opp_stats)
    
    # 驗證 9-Cat 勝負 (韋哥贏：FG%, PTS, AST, STL, TO；落後：FT%, 3PTM, REB, BLK -> 比分 5:4)
    assert comp_res["wins"] == 5
    assert comp_res["losses"] == 4
    assert comp_res["ties"] == 0
    
    # 驗證單一指標的勝負標記
    # FG%: 我方贏 (51.4% > 48.5%)
    assert comp_res["details"]["FG%"]["status"] == "my_win"
    assert comp_res["details"]["FG%"]["my_val"] == "51.4%"
    assert comp_res["details"]["FG%"]["opp_val"] == "48.5%"
    
    # FT%: 我方為 0 顯示為 "-"，落後
    assert comp_res["details"]["FT%"]["status"] == "opp_win"
    assert comp_res["details"]["FT%"]["my_val"] == "-"
    assert comp_res["details"]["FT%"]["opp_val"] == "75.0%"
    
    # TO: 我方 32 < 38 贏
    assert comp_res["details"]["TO"]["status"] == "my_win"
    
    # FGM/A: 輔助行，不用標註較優方，無 status
    assert "status" not in comp_res["details"]["FGM/A"]
    assert comp_res["details"]["FGM/A"]["my_val"] == "180/350"
```

- [ ] **Step 2: 執行測試並確認其失敗**
    執行: `pytest tests/test_matchup_handler.py::test_matchup_compare_logic -v`
    預期結果: FAIL (ModuleNotFoundError: No module named 'src.handlers.matchup_handler')

- [ ] **Step 3: 實作 `MatchupHandler` 的比對邏輯**
    建立 `src/handlers/matchup_handler.py`，寫入基礎 Handler 框架與 `compare_stats` 函式：

```python
import re
import os
import json
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, FlexMessage, FlexContainer, TextMessage, Configuration
from .base_handler import BaseHandler
from src.config import load_config
from src.cache_utils import load_league_metadata
from src.fetcher import YahooFantasyFetcher

class MatchupHandler(BaseHandler):
    def __init__(self):
        self.pattern = re.compile(r"^#對戰\s+(.+)$")

    def _load_team_mapping(self) -> dict:
        config = load_config()
        mapping_file = config.get("TEAM_MAPPING_FILE", "team_mapping.json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load team mapping: {e}")
        return {}

    def can_handle(self, user_text: str) -> bool:
        match = self.pattern.match(user_text)
        if not match:
            return False
        nickname = match.group(1).strip()
        mapping = self._load_team_mapping()
        return nickname in mapping.values()

    def to_percent_str(self, val) -> str:
        try:
            f_val = float(val)
            if f_val == 0.0:
                return "-"
            return f"{f_val * 100:.1f}%"
        except (ValueError, TypeError):
            return "-"

    def to_val_str(self, val) -> str:
        if val is None or str(val) == "0" or str(val) == "0.0":
            return "-"
        return str(val)

    def compare_stats(self, my_stats: dict, opp_stats: dict) -> dict:
        """比對 9-Cat 數據並統計比分"""
        cats_to_compare = [
            ("FG%", True), ("FT%", True), ("3PTM", True), ("PTS", True), 
            ("REB", True), ("AST", True), ("ST", True), ("BLK", True), ("TO", False)
        ]
        
        wins, losses, ties = 0, 0, 0
        details = {}

        # 1. 處理輔助行 (FGM/A, FTM/A) - 不進行比對
        details["FGM/A"] = {
            "my_val": self.to_val_str(my_stats.get("FGM/FGA")),
            "opp_val": self.to_val_str(opp_stats.get("FGM/FGA"))
        }
        details["FTM/A"] = {
            "my_val": self.to_val_str(my_stats.get("FTM/FTA")),
            "opp_val": self.to_val_str(opp_stats.get("FTM/FTA"))
        }

        # 2. 處理 9-Cat 指標比對
        for cat, is_larger_better in cats_to_compare:
            my_raw = my_stats.get(cat)
            opp_raw = opp_stats.get(cat)

            # 轉換為百分比或數值字串
            if cat in ["FG%", "FT%"]:
                my_val_str = self.to_percent_str(my_raw)
                opp_val_str = self.to_percent_str(opp_raw)
            else:
                my_val_str = self.to_val_str(my_raw)
                opp_val_str = self.to_val_str(opp_raw)

            # 安全轉換為 float 作為比較數值
            try:
                my_num = float(my_raw) if my_raw is not None else 0.0
            except ValueError:
                my_num = 0.0
            try:
                opp_num = float(opp_raw) if opp_raw is not None else 0.0
            except ValueError:
                opp_num = 0.0

            # 勝負判定
            if my_num == opp_num:
                status = "tie"
                ties += 1
            elif is_larger_better:
                if my_num > opp_num:
                    status = "my_win"
                    wins += 1
                else:
                    status = "opp_win"
                    losses += 1
            else:  # TO (越小越好)
                # 若雙方都為 0 則為平手
                if my_num == 0.0 and opp_num == 0.0:
                    status = "tie"
                    ties += 1
                elif my_num == 0.0: # 某一方無失誤為極優 (或剛開賽沒數據，此處依常規處理)
                    status = "my_win"
                    wins += 1
                elif opp_num == 0.0:
                    status = "opp_win"
                    losses += 1
                elif my_num < opp_num:
                    status = "my_win"
                    wins += 1
                else:
                    status = "opp_win"
                    losses += 1

            details[cat] = {
                "status": status,
                "my_val": my_val_str,
                "opp_val": opp_val_str
            }

        return {
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "details": details
        }
```

- [ ] **Step 4: 執行測試確認通過**
    執行: `pytest tests/test_matchup_handler.py::test_matchup_compare_logic -v`
    預期結果: PASS

- [ ] **Step 5: 提交至 Git**
    執行:
    ```bash
    git add src/handlers/matchup_handler.py tests/test_matchup_handler.py
    git commit -m "feat: implement matchup comparison and zero-to-dash translation in MatchupHandler"
    ```

---

### Task 3: 實作 Flex Message 卡片樣式排版與渲染

**Files:**
*   Modify: `src/handlers/matchup_handler.py`
*   Modify: `tests/test_matchup_handler.py`

- [ ] **Step 1: 撰寫 Flex Message 生成之失敗單元測試 (TDD)**
    在 `tests/test_matchup_handler.py` 寫入新測試，驗證三層 Header 與 Body 指標「領先大黑、落後小灰」的 JSON 結構。

```python
def test_format_matchup_stats():
    handler = MatchupHandler()
    
    player_info = {
        "my_nickname": "韋哥",
        "my_official": "Vigo's Superteam",
        "opp_nickname": "Jerry",
        "opp_official": "Jerry's Awesome"
    }
    
    # 模擬已經比對完的數據
    comp_res = {
        "wins": 5, "losses": 4, "ties": 0,
        "details": {
            "FGM/A": {"my_val": "180/350", "opp_val": "165/340"},
            "FTM/A": {"my_val": "-", "opp_val": "15/20"},
            "FG%": {"status": "my_win", "my_val": "51.4%", "opp_val": "48.5%"},
            "FT%": {"status": "opp_win", "my_val": "-", "opp_val": "75.0%"},
            "3PTM": {"status": "opp_win", "my_val": "35", "opp_val": "42"},
            "PTS": {"status": "my_win", "my_val": "450", "opp_val": "410"},
            "REB": {"status": "opp_win", "my_val": "110", "opp_val": "125"},
            "AST": {"status": "my_win", "my_val": "95", "opp_val": "80"},
            "ST": {"status": "my_win", "my_val": "25", "opp_val": "20"},
            "BLK": {"status": "opp_win", "my_val": "12", "opp_val": "18"},
            "TO": {"status": "my_win", "my_val": "32", "opp_val": "38"}
        }
    }
    
    bubble = handler.format_matchup_stats(player_info, comp_res, 24)
    
    assert isinstance(bubble, dict)
    assert bubble["type"] == "bubble"
    
    body = bubble["body"]["contents"]
    
    # 驗證 Header 第一層：中文暱稱 (韋哥 VS Jerry)
    header_box = body[1] # 根據實際的 HTML/Flex 位置 (第一個通常是 WEEK 24)
    assert header_box["contents"][0]["text"] == "韋哥"
    assert header_box["contents"][1]["text"] == "VS"
    assert header_box["contents"][2]["text"] == "Jerry"
    
    # 驗證 Header 第二層：官方隊名
    team_name_box = body[2]
    assert team_name_box["contents"][0]["text"] == "Vigo's Superteam"
    assert team_name_box["contents"][2]["text"] == "Jerry's Awesome"
    
    # 驗證 Header 第三層：比分對決 (5:4，領先大黑 24px/bold/#111111，落後小灰 16px/regular/#aaaaaa)
    score_box = body[3]
    assert score_box["contents"][0]["text"] == "5"
    assert score_box["contents"][0]["size"] == "xl" # 24px對應 xl
    assert score_box["contents"][0]["color"] == "#111111"
    assert score_box["contents"][2]["text"] == "4"
    assert score_box["contents"][2]["size"] == "md" # 16px對應 md
    assert score_box["contents"][2]["color"] == "#aaaaaa"
    
    # 驗證 Body 11 行指標 (如 FG%，我方贏 -> 我方大黑，對手小灰)
    fg_row = body[6] # 根據行數索引
    assert fg_row["contents"][0]["text"] == "51.4%"
    assert fg_row["contents"][0]["weight"] == "bold"
    assert fg_row["contents"][0]["size"] == "md"
    assert fg_row["contents"][0]["color"] == "#111111"
    
    assert fg_row["contents"][1]["text"] == "FG%"
    
    assert fg_row["contents"][2]["text"] == "48.5%"
    assert fg_row["contents"][2]["weight"] == "regular"
    assert fg_row["contents"][2]["size"] == "xs"
    assert fg_row["contents"][2]["color"] == "#aaaaaa"
```

- [ ] **Step 2: 執行測試並確認其失敗**
    執行: `pytest tests/test_matchup_handler.py::test_format_matchup_stats -v`
    預期結果: FAIL (AttributeError: 'MatchupHandler' object has no attribute 'format_matchup_stats')

- [ ] **Step 3: 實作 `format_matchup_stats` 渲染方法**
    在 `src/handlers/matchup_handler.py` 中新增 `format_matchup_stats` 實作：

```python
    def format_matchup_stats(self, player_info: dict, comp_res: dict, week_str: str) -> dict:
        """組裝 11 行無 Footer 極簡風對稱 Flex Message 卡片"""
        details = comp_res["details"]
        wins = comp_res["wins"]
        losses = comp_res["losses"]

        # 1. 決定 Header 第三層比分的視覺樣式 (領先大黑，落後小灰)
        if wins > losses:
            my_score_style = {"size": "xl", "weight": "bold", "color": "#111111"}
            opp_score_style = {"size": "md", "weight": "regular", "color": "#aaaaaa"}
        elif wins < losses:
            my_score_style = {"size": "md", "weight": "regular", "color": "#aaaaaa"}
            opp_score_style = {"size": "xl", "weight": "bold", "color": "#111111"}
        else:
            my_score_style = {"size": "xl", "weight": "bold", "color": "#111111"}
            opp_score_style = {"size": "xl", "weight": "bold", "color": "#111111"}

        # 2. 建立 11 行指標數據的輔助渲染函式
        def build_row(label, is_aux=False):
            data = details[label]
            my_val = data["my_val"]
            opp_val = data["opp_val"]

            if is_aux:
                # 輔助指標：不受規則影響，統一常規灰色 13px
                return {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": my_val, "align": "start", "size": "sm", "color": "#777777"},
                        {"type": "text", "text": label, "align": "center", "size": "xs", "color": "#bbbbbb", "weight": "bold"},
                        {"type": "text", "text": opp_val, "align": "end", "size": "sm", "color": "#777777"}
                    ]
                }
            
            # 正式 9-Cat：領先黑色較大 (15px bold #111111)，落後灰色較小 (12px regular #aaaaaa)
            status = data.get("status")
            if status == "my_win":
                my_style = {"weight": "bold", "size": "md", "color": "#111111"}
                opp_style = {"weight": "regular", "size": "xs", "color": "#aaaaaa"}
            elif status == "opp_win":
                my_style = {"weight": "regular", "size": "xs", "color": "#aaaaaa"}
                opp_style = {"weight": "bold", "size": "md", "color": "#111111"}
            else: # 平手
                my_style = {"weight": "regular", "size": "sm", "color": "#555555"}
                opp_style = {"weight": "regular", "size": "sm", "color": "#555555"}

            # 將 ST 翻譯為 LINE 顯示的簡寫 STL
            display_label = "STL" if label == "ST" else label

            return {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {"type": "text", "text": my_val, "align": "start", "weight": my_style["weight"], "size": my_style["size"], "color": my_style["color"]},
                    {"type": "text", "text": display_label, "align": "center", "size": "xs", "color": "#bbbbbb", "weight": "bold"},
                    {"type": "text", "text": opp_val, "align": "end", "weight": opp_style["weight"], "size": opp_style["size"], "color": opp_style["color"]}
                ]
            }

        # 3. 依序建立 11 行指標數據的 rows
        rows = [
            build_row("FGM/A", is_aux=True),
            build_row("FG%"),
            build_row("FTM/A", is_aux=True),
            build_row("FT%"),
            build_row("3PTM"),
            build_row("PTS"),
            build_row("REB"),
            build_row("AST"),
            build_row("ST"),
            build_row("BLK"),
            build_row("TO")
        ]

        # 4. 組裝完整 bubble dictionary (無 Footer 設計，更加乾淨)
        return {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    # 週次標題
                    {
                        "type": "text",
                        "text": f"WEEK {week_str} MATCHUP",
                        "weight": "bold",
                        "size": "xxs",
                        "color": "#cccccc",
                        "align": "center",
                        "margin": "xs"
                    },
                    # 【第一層】玩家中文暱稱 VS (最大粗體)
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": player_info["my_nickname"], "weight": "bold", "size": "xl", "color": "#111111"},
                            {"type": "text", "text": "VS", "align": "center", "weight": "bold", "size": "sm", "color": "#aaaaaa"},
                            {"type": "text", "text": player_info["opp_nickname"], "weight": "bold", "size": "xl", "color": "#111111", "align": "end"}
                        ]
                    },
                    # 【第二層】Fantasy 官方隊名 (較小灰色，無 VS)
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": player_info["my_official"], "size": "xxs", "color": "#999999"},
                            {"type": "text", "text": " ", "size": "xxs"},
                            {"type": "text", "text": player_info["opp_official"], "size": "xxs", "color": "#999999", "align": "end"}
                        ]
                    },
                    # 【第三層】即時比分對決 (領先大黑，落後小灰)
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": str(wins), "align": "end", "weight": my_score_style["weight"], "size": my_score_style["size"], "color": my_score_style["color"]},
                            {"type": "text", "text": ":", "align": "center", "weight": "bold", "size": "md", "color": "#cccccc"},
                            {"type": "text", "text": str(losses), "align": "start", "weight": opp_score_style["weight"], "size": opp_score_style["size"], "color": opp_score_style["color"]}
                        ]
                    },
                    # 精緻對齊線
                    {
                        "type": "separator",
                        "color": "#eeeeee"
                    },
                    # 11 行指標 rows
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": rows
                    }
                ]
            }
        }
```

- [ ] **Step 4: 執行測試並確認通過**
    執行: `pytest tests/test_matchup_handler.py::test_format_matchup_stats -v`
    預期結果: PASS

- [ ] **Step 5: 提交至 Git**
    執行:
    ```bash
    git add src/handlers/matchup_handler.py tests/test_matchup_handler.py
    git commit -m "feat: implement format_matchup_stats with 3-layer header and 11-row layout in MatchupHandler"
    ```

---

### Task 4: 整合並進行實地功能驗證

**Files:**
*   Modify: `bot.py`
*   Modify: `src/handlers/matchup_handler.py`
*   Create: `tests/test_matchup_handler.py`

- [ ] **Step 1: 撰寫 MatchupHandler.execute 生命週期測試**
    在 `tests/test_matchup_handler.py` 寫入最終的生命週期 execute 測試，驗證完整 execute 中能正確反查對手、抓取 API、並 reply Flex Message。

```python
def test_matchup_handler_execute_flow(mocker):
    # Mock config, time_utils, yahoofantasy Context 與 fetcher
    mocker.patch("src.handlers.matchup_handler.load_config", return_value={
        "LEAGUE_ID": "12345",
        "TEAM_MAPPING_FILE": "team_mapping.json"
    })
    mocker.patch("src.handlers.matchup_handler.load_league_metadata", return_value={
        "start_date": "2025-10-21",
        "end_date": "2026-04-12",
        "date_to_week": {"2026-05-28": 24}
    })
    
    mocker.patch("src.handlers.matchup_handler.datetime")
    import datetime
    from datetime import datetime as dt
    # US/Pacific 2026-05-28
    mock_now = mocker.patch("src.handlers.matchup_handler.datetime")
    mock_now.now.return_value = dt(2026, 5, 28, 12, 0)
    
    # Mock Yahoo API 回傳 matchups
    mock_matchups = [
        {
            "team1": {
                "team_id": "1", "name": "韋哥", "official_name": "Vigo's Superteam",
                "stats": {"FG%": "0.514", "FGM/FGA": "180/350", "FT%": "0.0", "FTM/FTA": "0/0", "3PTM": "35", "PTS": "450", "REB": "110", "AST": "95", "STL": "25", "BLK": "12", "TO": "32"}
            },
            "team2": {
                "team_id": "2", "name": "Jerry", "official_name": "Jerry's Awesome",
                "stats": {"FG%": "0.485", "FGM/FGA": "165/340", "FT%": "0.750", "FTM/FTA": "15/20", "3PTM": "42", "PTS": "410", "REB": "125", "AST": "80", "STL": "20", "BLK": "18", "TO": "38"}
            }
        }
    ]
    mock_fetcher = mocker.patch("src.handlers.matchup_handler.YahooFantasyFetcher")
    mock_fetcher.return_value.fetch_matchups.return_value = mock_matchups
    
    handler = MatchupHandler()
    mocker.patch.object(handler, "_load_team_mapping", return_value={"1": "韋哥", "2": "Jerry"})
    
    # Mock LINE API 回覆
    mock_reply = mocker.patch.object(handler, "reply_flex")
    
    mock_event = mocker.MagicMock()
    mock_event.message.text = "#對戰 韋哥"
    mock_event.reply_token = "reply_token_123"
    
    handler.execute(mock_event, mocker.MagicMock())
    
    # 斷言 reply_flex 確實被呼叫，且帶有對戰資訊
    mock_reply.assert_called_once()
    args = mock_reply.call_args[0]
    assert args[0] == mock_event
    assert "韋哥 VS Jerry" in args[2] # alt_text
    assert isinstance(args[3], dict) # flex_dict
```

- [ ] **Step 2: 執行測試確認其失敗**
    執行: `pytest tests/test_matchup_handler.py::test_matchup_handler_execute_flow -v`
    預期結果: FAIL (AttributeError: 'MatchupHandler' object has no attribute 'execute')

- [ ] **Step 3: 在 `src/handlers/matchup_handler.py` 實作 `execute` 生命週期**
    在 `src/handlers/matchup_handler.py` 中寫入 `execute` 與 `reply_flex` 的完整實作：

```python
    def reply_flex(self, event: MessageEvent, configuration: Configuration, alt_text: str, flex_dict: dict) -> None:
        flex_container = FlexContainer.from_json(json.dumps(flex_dict))
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text=alt_text, contents=flex_container)]
                )
            )

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        nickname = match.group(1).strip()
        mapping = self._load_team_mapping()
        
        # 1. 尋找我方 Team ID
        my_team_id = None
        for t_id, name in mapping.items():
            if name == nickname:
                my_team_id = t_id
                break
                
        if not my_team_id:
            return

        config = load_config()
        league_id = config["LEAGUE_ID"]
        meta = load_league_metadata()
        
        # 2. 計算美西日期與當週週數
        import pytz
        from datetime import datetime
        today_pacific = datetime.now(pytz.timezone("US/Pacific")).strftime("%Y-%m-%d")
        
        from src.utils.time_utils import get_target_date, get_fantasy_week
        is_offseason = meta.get('end_date') and today_pacific > meta['end_date']
        target_date = get_target_date(is_offseason=is_offseason, end_date=meta.get('end_date'))
        
        date_to_week = meta.get("date_to_week", {})
        target_week = date_to_week.get(target_date) or get_fantasy_week(config["SEASON_START_DATE"])
        
        if meta.get('end_week') and target_week > meta['end_week']:
            target_week = meta['end_week']

        # 3. 呼叫單次 Scoreboard API 請求
        fetcher = YahooFantasyFetcher(
            team_mapping=mapping,
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET")
        )
        
        try:
            matchups = fetcher.fetch_matchups(league_id, target_week)
            
            # 4. 在記憶體中匹配該玩家的 Matchup
            target_matchup = None
            is_team1 = True
            for m in matchups:
                if m["team1"]["team_id"] == my_team_id:
                    target_matchup = m
                    is_team1 = True
                    break
                elif m["team2"]["team_id"] == my_team_id:
                    target_matchup = m
                    is_team1 = False
                    break
            
            if not target_matchup:
                logging.error(f"Matchup not found for team {my_team_id} in week {target_week}")
                return
            
            # 5. 錨定角色 (My Team 必在左側，Opponent 必在右側)
            if is_team1:
                my_team_data = target_matchup["team1"]
                opp_team_data = target_matchup["team2"]
            else:
                my_team_data = target_matchup["team2"]
                opp_team_data = target_matchup["team1"]
                
            player_info = {
                "my_nickname": nickname,
                "my_official": my_team_data["official_name"],
                "opp_nickname": opp_team_data["name"],
                "opp_official": opp_team_data["official_name"]
            }
            
            # 6. 指標勝負判定
            comp_res = self.compare_stats(my_team_data["stats"], opp_team_data["stats"])
            
            # 7. 組裝並回傳 Flex Message
            flex_dict = self.format_matchup_stats(player_info, comp_res, str(target_week))
            
            alt_text = f"{player_info['my_nickname']} VS {player_info['opp_nickname']} 對戰比分"
            self.reply_flex(event, configuration, alt_text, flex_dict)
            
        except Exception as e:
            # 依規範安全且安靜地退出
            logging.error(f"Failed to execute matchup query for manager {nickname}: {e}")
```

- [ ] **Step 4: 執行完整測試確認通過**
    執行: `pytest tests/test_matchup_handler.py -v`
    預期結果: ALL PASS (所有 3 個測試案例均通過！)

- [ ] **Step 5: 提交至 Git**
    執行:
    ```bash
    git add src/handlers/matchup_handler.py tests/test_matchup_handler.py
    git commit -m "feat: complete MatchupHandler integration, execute life-cycle and all pytest cases"
    ```

---

### Task 5: 註冊 Handler 並進行整體功能聯調

**Files:**
*   Modify: `bot.py`

- [ ] **Step 1: 在 `bot.py` 中註冊 `MatchupHandler`**
    在 `bot.py` 的第 21 行與第 69 行附近進行修改，加入 `MatchupHandler`：

```python
# 修改前 (約第 21 行):
from src.handlers.user_stats_handler import UserStatsHandler

# 修改後:
from src.handlers.user_stats_handler import UserStatsHandler
from src.handlers.matchup_handler import MatchupHandler
```

```python
# 修改前 (約第 69 行):
dispatcher.register(UserStatsHandler())

# 修改後:
dispatcher.register(UserStatsHandler())
dispatcher.register(MatchupHandler())
```

- [ ] **Step 2: 執行全專案自動化測試**
    執行: `pytest -v`
    預期結果: 全專案所有測試（包含新增與舊有測試）全數順利通過！

- [ ] **Step 3: 提交至 Git**
    執行:
    ```bash
    git add bot.py
    git commit -m "feat: register MatchupHandler into CommandDispatcher for LINE bot integration"
    ```

---

## 實作計畫自我審查 (Self-Review)

1.  **規格書覆蓋率 (Spec Coverage)**：
    *   單次 Scoreboard API 請求 ──► 已規劃於 Task 1 及 Task 4。
    *   三層 Header（中文暱稱、官方隊名、領先大黑落後小灰比分）──► 已規劃於 Task 3。
    *   Body 11 行指標大黑小灰對稱排版 ──► 已規劃於 Task 3。
    *   命中率為 0 顯示 `-` ──► 已規劃於 Task 2（`to_percent_str`）。
    *   輔助行 `FGM/A` 與 `FTM/A` 不參與比對 ──► 已規劃於 Task 2 與 Task 3。
    *   安靜安全退出機制 ──► 已規劃於 Task 2 與 Task 4。
2.  **暫位符檢查 (Placeholder Scan)**：
    *   無任何 "TBD", "TODO", "implement later" 等紅旗字樣。
    *   所有 API 解析程式碼、指標判定、對稱 Flex Message 組裝結構均已完全在計畫中展開。
3.  **類型與簽章一致性 (Type Consistency)**：
    *   `fetch_matchups` 傳回之 dict 鍵名與 `MatchupHandler.execute` 中所接收之格式百分之百吻合。
    *   所有指標判定結果之勝負狀態（`my_win`, `opp_win`, `tie`）於 Task 2 定義，並在 Task 3 的樣式渲染中精準使用。
