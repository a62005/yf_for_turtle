# LINE Bot #玩家 <稱呼> 即時數據查詢功能實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 實作 LINE Bot 指令 `#玩家 <稱呼>`，透過反查 `team_mapping.json` 精準定位 Team ID，實時且不限時間地拉取 Yahoo API 中該隊伍的當日戰績與當週累積戰績，並以無中文名、無虛線、以等寬 Monospace 格式且富含數據日期與週數標頭的格式進行回傳，若查無登錄玩家則直接略過。

**Architecture:** 本功能基於關注點分離原則，新增 `UserStatsHandler` 指令處理器，比對精準綽號。在 `YahooFantasyFetcher` 中新增 `fetch_single_team_stats_by_url` 即時 XML 拉取與解析邏輯，數據回傳時以 Markdown 程式碼區塊 (\`\`\`) 包裹，達到全裝置完美右貼齊。

**Tech Stack:** Python, Yahoo Fantasy API (OAuth), xml.etree.ElementTree, Pytest, Pytest-mock, Line Messaging API

---

### Task 1: 實作 YahooFetcher 實時隊伍數據拉取與解析

**Files:**
- Modify: [fetcher.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/fetcher.py)
- Create: [test_fetcher_single_team.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_fetcher_single_team.py)

- [ ] **Step 1: 撰寫 XML 解析與即時拉取的單元測試**

在專案中建立 `tests/test_fetcher_single_team.py` 檔案：
```python
import pytest
from unittest.mock import MagicMock
import xml.etree.ElementTree as ET
from src.fetcher import YahooFantasyFetcher

# 模擬的 Yahoo Team Stats XML 回傳數據
MOCK_TEAM_STATS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
  <team>
    <team_key>nba.l.12345.t.1</team_key>
    <name>Vigo's Superteam</name>
    <team_stats>
      <stats>
        <stat><stat_id>4</stat_id><value>14</value></stat>
        <stat><stat_id>3</stat_id><value>24</value></stat>
        <stat><stat_id>5</stat_id><value>0.583</value></stat>
        <stat><stat_id>7</stat_id><value>3</value></stat>
        <stat><stat_id>6</stat_id><value>4</value></stat>
        <stat><stat_id>8</stat_id><value>0.750</value></stat>
        <stat><stat_id>10</stat_id><value>4</value></stat>
        <stat><stat_id>12</stat_id><value>35</value></stat>
        <stat><stat_id>15</stat_id><value>9</value></stat>
        <stat><stat_id>16</stat_id><value>12</value></stat>
        <stat><stat_id>17</stat_id><value>2</value></stat>
        <stat><stat_id>18</stat_id><value>1</value></stat>
        <stat><stat_id>19</stat_id><value>3</value></stat>
      </stats>
    </team_stats>
  </team>
</fantasy_content>
"""

def test_parse_team_stats_xml():
    fetcher = YahooFantasyFetcher(team_mapping={"1": "韋哥"})
    res = fetcher._parse_team_stats_xml(MOCK_TEAM_STATS_XML)
    
    assert res["team_name"] == "Vigo's Superteam"
    stats = res["stats"]
    assert stats["stat_4"] == "14" # FGM
    assert stats["stat_3"] == "24" # FGA
    assert stats["FG%"] == "0.583"
    assert stats["stat_7"] == "3"  # FTM
    assert stats["stat_6"] == "4"  # FTA
    assert stats["FT%"] == "0.750"
    assert stats["3PTM"] == "4"
    assert stats["PTS"] == "35"
    assert stats["REB"] == "9"
    assert stats["AST"] == "12"
    assert stats["ST"] == "2"
    assert stats["BLK"] == "1"
    assert stats["TO"] == "3"

def test_fetch_single_team_stats_by_url(mocker):
    # Mock self.ctx.make_request 回傳模擬的 XML
    fetcher = YahooFantasyFetcher(team_mapping={"1": "韋哥"})
    mock_make_request = mocker.patch.object(fetcher.ctx, "make_request", return_value=MOCK_TEAM_STATS_XML)
    
    res = fetcher.fetch_single_team_stats_by_url("nba.l.12345.t.1", "date", "2026-05-28")
    
    # 驗證是否打對了 Yahoo API Endpoint
    mock_make_request.assert_called_once_with("team/nba.l.12345.t.1/stats;type=date;date=2026-05-28")
    assert res["team_name"] == "Vigo's Superteam"
    assert res["stats"]["PTS"] == "35"
```

- [ ] **Step 2: 執行測試並確認其失敗**

在專案目錄下執行：
```powershell
$env:PYTHONPATH="C:\Users\HsiehLink\Python\yf_for_turtle"
.venv\Scripts\pytest tests/test_fetcher_single_team.py -v
```
預期結果：**FAIL** (AttributeError: 'YahooFantasyFetcher' object has no attribute '_parse_team_stats_xml')

- [ ] **Step 3: 於 `src/fetcher.py` 實作 XML 解析與拉取方法**

修改 `src/fetcher.py`，在類別最後面加上這兩個方法：
```python
    def _parse_team_stats_xml(self, xml_data: str) -> dict:
        """解析 Yahoo Team stats XML 並翻譯為 9-Cat 格式"""
        root = ET.fromstring(xml_data)
        
        # 尋找 team 節點與名稱
        team_node = root.find('.//ns:team', YAHOO_NS)
        if team_node is None:
            team_node = root # Fallback
            
        name_node = team_node.find('ns:name', YAHOO_NS)
        team_name = name_node.text if name_node is not None else "Unknown Team"
        
        stats_dict = {}
        stat_nodes = team_node.findall('.//ns:team_stats/ns:stats/ns:stat', YAHOO_NS)
        for node in stat_nodes:
            s_id = node.find('ns:stat_id', YAHOO_NS).text
            s_val = node.find('ns:value', YAHOO_NS).text
            
            # 使用我們原有的翻譯邏輯
            label = translate_stat_id(s_id)
            stats_dict[label] = s_val if s_val is not None else "0"
            
        return {
            "team_name": team_name,
            "stats": stats_dict
        }

    def fetch_single_team_stats_by_url(self, team_key: str, stat_type: str, type_val: str) -> dict:
        """實時且無快取地抓取單一隊伍在指定日期/週數的 9-Cat 數據"""
        url = f"team/{team_key}/stats;type={stat_type};{stat_type}={type_val}"
        xml_data = self.ctx.make_request(url)
        return self._parse_team_stats_xml(xml_data)
```

- [ ] **Step 4: 重新執行測試確認其通過**

執行：
```powershell
$env:PYTHONPATH="C:\Users\HsiehLink\Python\yf_for_turtle"
.venv\Scripts\pytest tests/test_fetcher_single_team.py -v
```
預期結果：**PASS** (2 passed)

- [ ] **Step 5: 提交變更**

確認分支不在 `dev` 或 `master`，然後執行：
```powershell
git add tests/test_fetcher_single_team.py src/fetcher.py
git commit -m "feat: add single team real-time stats fetching and parsing methods with unit tests"
```

---

### Task 2: 實作 UserStatsHandler 與排版輸出

**Files:**
- Create: [user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/user_stats_handler.py)
- Create: [test_user_stats_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_user_stats_handler.py)

- [ ] **Step 1: 撰寫 UserStatsHandler 單元測試**

在專案中建立 `tests/test_user_stats_handler.py`：
```python
import pytest
from unittest.mock import MagicMock
from src.handlers.user_stats_handler import UserStatsHandler

def test_user_stats_handler_can_handle(mocker):
    # Mock load_config 以提供 team_mapping 檔案配置
    mocker.patch("src.handlers.user_stats_handler.load_config", return_value={"TEAM_MAPPING_FILE": "team_mapping.json"})
    
    # Mock 讀取 team_mapping.json 的回傳內容 (模擬有 韋哥，但沒有 詹姆斯)
    mock_mapping = {"1": "韋哥", "2": "Jerry"}
    mocker.patch("src.handlers.user_stats_handler.UserStatsHandler._load_team_mapping", return_value=mock_mapping)
    
    handler = UserStatsHandler()
    
    # 測試比對
    assert handler.can_handle("#玩家 韋哥") is True
    assert handler.can_handle("#玩家 Jerry") is True
    assert handler.can_handle("#玩家 詹姆斯") is False  # 沒登錄 -> 略過
    assert handler.can_handle("#玩家") is False
    assert handler.can_handle("#球員 韋哥") is False

def test_format_user_stats():
    handler = UserStatsHandler()
    player_info = {
        "manager_name": "韋哥",
        "official_name": "Vigo's Superteam"
    }
    
    # 模擬當日數據
    daily_stats = {
        "stat_4": "14",
        "stat_3": "24",
        "FG%": "0.583",
        "stat_7": "3",
        "stat_6": "4",
        "FT%": "0.750",
        "3PTM": "4",
        "PTS": "35",
        "REB": "9",
        "AST": "12",
        "ST": "2",
        "BLK": "1",
        "TO": "3"
    }
    
    # 模擬當週累積數據
    weekly_stats = {
        "stat_4": "80",
        "stat_3": "150",
        "FG%": "0.533",
        "stat_7": "20",
        "stat_6": "25",
        "FT%": "0.800",
        "3PTM": "18",
        "PTS": "210",
        "REB": "55",
        "AST": "62",
        "ST": "12",
        "BLK": "8",
        "TO": "15"
    }
    
    formatted = handler.format_user_stats(player_info, daily_stats, weekly_stats, "2026-05-28", "24")
    
    expected = (
        "韋哥\n"
        "Vigo's Superteam\n"
        "2026-05-28\n"
        "```\n"
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
        "TO :                  3\n"
        "```\n"
        "W24\n"
        "```\n"
        "FGM/A :          80/150\n"
        "FG% :             53.3%\n"
        "FTM/A :           20/25\n"
        "FT% :             80.0%\n"
        "3PM :                18\n"
        "PTS :               210\n"
        "REB :                55\n"
        "AST :                62\n"
        "STL :                12\n"
        "BLK :                 8\n"
        "TO :                 15\n"
        "```"
    )
    assert formatted.strip() == expected.strip()
```

- [ ] **Step 2: 執行測試並確認其失敗**

執行：
```powershell
$env:PYTHONPATH="C:\Users\HsiehLink\Python\yf_for_turtle"
.venv\Scripts\pytest tests/test_user_stats_handler.py -v
```
預期結果：**FAIL** (ModuleNotFoundError: No module named 'src.handlers.user_stats_handler')

- [ ] **Step 3: 撰寫 `src/handlers/user_stats_handler.py` 實作**

建立 `src/handlers/user_stats_handler.py` 檔案：
```python
import re
import os
import json
import logging
from datetime import datetime
import pytz
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, Configuration
from .base_handler import BaseHandler

from src.config import load_config
from src.cache_utils import load_league_metadata
from src.fetcher import YahooFantasyFetcher
from src.utils.time_utils import get_fantasy_week

class UserStatsHandler(BaseHandler):
    def __init__(self):
        self.pattern = re.compile(r"^#玩家\s+(.+)$")

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
        # 精準比對是否包含此暱稱
        return nickname in mapping.values()

    def calculate_target_date(self, is_offseason=False, end_date=None) -> str:
        if is_offseason:
            return end_date or "2026-04-12"
            
        tw_tz = pytz.timezone("Asia/Taipei")
        current_tw_dt = datetime.now(tw_tz)
        tw_date = current_tw_dt.date()
        tw_hour = current_tw_dt.hour
        
        # 台北時間 07:00 跨日美西時間邏輯
        if tw_hour >= 7:
            target_dt = tw_date - timedelta(days=1)
        else:
            target_dt = tw_date - timedelta(days=2)
            
        return target_dt.strftime("%Y-%m-%d")

    def format_user_stats(self, player_info: dict, daily_stats: dict, weekly_stats: dict, date_str: str, week_str: str) -> str:
        # Helper to safely format percentages
        def to_percent_str(val):
            try:
                return f"{float(val) * 100:.1f}%"
            except (ValueError, TypeError):
                return "0.0%"

        def build_lines(stats):
            # FGM is stat_4, FGA is stat_3
            fgm = stats.get("stat_4", "0")
            fga = stats.get("stat_3", "0")
            fgm_a = f"{fgm}/{fga}" if fga != "0" else "0/0"
            fg_pct = to_percent_str(stats.get("FG%", "0.0"))

            # FTM is stat_7, FTA is stat_6
            ftm = stats.get("stat_7", "0")
            fta = stats.get("stat_6", "0")
            ftm_a = f"{ftm}/{fta}" if fta != "0" else "0/0"
            ft_pct = to_percent_str(stats.get("FT%", "0.0"))

            pm3 = stats.get("3PTM", "0")
            pts = stats.get("PTS", "0")
            reb = stats.get("REB", "0")
            ast = stats.get("AST", "0")
            stl = stats.get("ST", "0")
            blk = stats.get("BLK", "0")
            to = stats.get("TO", "0")

            return [
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

        # 1. 組裝當日區塊
        header_daily = (
            f"{player_info['manager_name']}\n"
            f"{player_info['official_name']}\n"
            f"{date_str}"
        )
        daily_lines = build_lines(daily_stats)
        daily_block = "```\n" + "\n".join(daily_lines) + "\n```"

        # 2. 組裝當週區塊
        header_weekly = f"W{week_str}"
        weekly_lines = build_lines(weekly_stats)
        weekly_block = "```\n" + "\n".join(weekly_lines) + "\n```"

        return f"{header_daily}\n{daily_block}\n{header_weekly}\n{weekly_block}"

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        nickname = match.group(1).strip()
        mapping = self._load_team_mapping()
        
        # 1. 尋找對應的 Team ID
        team_id = None
        for t_id, name in mapping.items():
            if name == nickname:
                team_id = t_id
                break
                
        if not team_id:
            return # 依照規範直接略過

        config = load_config()
        league_id = config["LEAGUE_ID"]
        meta = load_league_metadata()
        
        # 2. 計算美西日期與週數
        from datetime import datetime, timedelta
        today_pacific = datetime.now(pytz.timezone("US/Pacific")).strftime("%Y-%m-%d")
        is_offseason = meta.get('end_date') and today_pacific > meta['end_date']
        
        target_date = self.calculate_target_date(is_offseason=is_offseason, end_date=meta.get('end_date'))
        
        date_to_week = meta.get("date_to_week", {})
        target_week = date_to_week.get(target_date) or get_fantasy_week(config["SEASON_START_DATE"])
        
        if meta.get('end_week') and target_week > meta['end_week']:
            target_week = meta['end_week']
            
        team_key = f"nba.l.{league_id}.t.{team_id}"
        
        # 3. 實時抓取數據
        fetcher = YahooFantasyFetcher(
            team_mapping=mapping,
            client_id=config.get("YAHOO_CLIENT_ID"),
            client_secret=config.get("YAHOO_CLIENT_SECRET")
        )
        
        try:
            # 異步/並行或依序抓取當日與當週數據
            res_daily = fetcher.fetch_single_team_stats_by_url(team_key, "date", target_date)
            res_weekly = fetcher.fetch_single_team_stats_by_url(team_key, "week", str(target_week))
            
            official_name = res_daily.get("team_name", "Unknown Team")
            
            player_info = {
                "manager_name": nickname,
                "official_name": official_name
            }
            
            reply_text = self.format_user_stats(
                player_info, 
                res_daily["stats"], 
                res_weekly["stats"], 
                target_date, 
                str(target_week)
            )
            self.reply_text(event, configuration, reply_text)
        except Exception as e:
            # 依規範安全且安靜地退出，不打擾群組
            logging.error(f"Failed to fetch team real-time stats for manager {nickname}: {e}")

    def reply_text(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=text)]
                )
            )
```

- [ ] **Step 4: 重新執行測試確認其通過**

執行：
```powershell
$env:PYTHONPATH="C:\Users\HsiehLink\Python\yf_for_turtle"
.venv\Scripts\pytest tests/test_user_stats_handler.py -v
```
預期結果：**PASS** (2 passed)

- [ ] **Step 5: 提交變更**

執行：
```powershell
git add src/handlers/user_stats_handler.py tests/test_user_stats_handler.py
git commit -m "feat: implement UserStatsHandler for real-time team stats fetching and monospace formatting"
```

---

### Task 3: 註冊 UserStatsHandler 至 Bot 分流器

**Files:**
- Modify: [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py)

- [ ] **Step 1: 在 `bot.py` 中引入並註冊 `UserStatsHandler`**

修改 `bot.py`，於 imports 中加入 `UserStatsHandler` 並完成註冊：

```python
# 修改 bot.py 中的 imports 區塊：
# 原本為：
# from src.handlers.player_handler import PlayerHandler
# 改為：
from src.handlers.player_handler import PlayerHandler
from src.handlers.user_stats_handler import UserStatsHandler
```

```python
# 修改 bot.py 的 dispatcher 初始化區塊：
# 原本為：
# dispatcher.register(PlayerHandler())
# 改為：
dispatcher.register(PlayerHandler())
dispatcher.register(UserStatsHandler())
```

- [ ] **Step 2: 執行全部單元測試以確保合併相容性**

在全域環境中執行完整測試套件：
```powershell
python -m pytest
```
預期結果：**PASS** (83 passed, 包含新增的 2 個 test 檔案中的 4 個測試)

- [ ] **Step 3: 提交變更**

確認當前不在 `dev` 分支，執行：
```powershell
git add bot.py
git commit -m "chore: register UserStatsHandler to bot command dispatcher"
```
