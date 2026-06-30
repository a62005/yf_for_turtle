# Multi-Sport Adaptation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generalize the LINE Bot's Yahoo Fantasy integration to support both NBA and MLB dynamically, resolving stats categories from the Yahoo settings API, handling folder prefix isolation, adapting LLM prompts, and limiting external countdown/ESPN APIs to NBA.

**Architecture:** We will transition league storage from raw numeric IDs to fully-prefixed league keys (e.g. `nba.l.18457`), load stat configurations dynamically from the Yahoo Settings API, apply heuristic-based formatting and display label aliases in the visualizer, contextualize LLM search scope by sport, and restrict ESPN APIs to NBA using simple handler bypasses.

**Tech Stack:** Python 3.14, requests, yahoofantasy SDK, pytest, jinja2.

---

## File Structure

The following files will be created or modified:
* **Modified**:
  * [src/utils/path_utils.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/path_utils.py): Modify path resolution functions (`get_league_dir`) to preserve full league key prefixes, and add a migration function `migrate_old_league_directories()`.
  * [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py): Invoke migration utility on startup.
  * [src/fetcher.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/fetcher.py): Fetch settings endpoint `league/{league_id}/settings` and cache it inside `metadata.json`; perform dynamic stat-ID translation using cache.
  * [src/visualizer/processor.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/visualizer/processor.py): Build columns dynamically from `metadata.json` stats list; map display names using `DISPLAY_ALIASES`; format values using regex-based heuristics.
  * [src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py): Implement the Flex Message prompt for sport selection, handle user inputs, and bind the normalized full key.
  * [src/llm/llm_agent.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/llm/llm_agent.py) & [src/llm/prompts/player_fuzzy_search.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/llm/prompts/player_fuzzy_search.py): Inject `sport` to customize prompt roles and google search keywords.
  * [src/utils/time_utils.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/time_utils.py): Limit ESPN game day check to NBA only.
  * [src/handlers/misc_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/misc_handler.py): Limit `#開季` countdown to NBA only.
  * [src/handlers/injury_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/injury_handler.py): Limit `#傷兵` command execution to NBA only.

---

### Task 1: Prefix Path Preservation & Folder Migration

**Files:**
* Modify: [src/utils/path_utils.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/path_utils.py)
* Modify: [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py)
* Test: Create `tests/test_path_migration.py`

- [ ] **Step 1: Write a failing test for prefixed path resolution and folder migration**

Create `tests/test_path_migration.py`:
```python
import os
import shutil
import tempfile
import json
from src.utils.path_utils import get_league_dir, migrate_old_league_directories

def test_get_league_dir_preserves_prefix():
    # Full keys should keep their names
    assert "nba.l.18457" in get_league_dir("nba.l.18457")
    assert "mlb.l.12345" in get_league_dir("mlb.l.12345")
    # Raw numeric keys default to nba.l. prefix
    assert "nba.l.999" in get_league_dir("999")

def test_migrate_old_league_directories(mocker):
    temp_data_dir = tempfile.mkdtemp()
    mocker.patch("src.utils.path_utils.DATA_DIR", temp_data_dir)
    
    # Setup old numeric folder and files
    old_folder = os.path.join(temp_data_dir, "league", "18457")
    os.makedirs(old_folder, exist_ok=True)
    test_file = os.path.join(old_folder, "test.json")
    with open(test_file, "w") as f:
        f.write("{}")
        
    # Setup old mapping file
    sec_dir = os.path.join(temp_data_dir, "security")
    os.makedirs(sec_dir, exist_ok=True)
    mapping_file = os.path.join(sec_dir, "chat_league_mapping.json")
    with open(mapping_file, "w") as f:
        json.dump({"chat1": "18457"}, f)
        
    migrate_old_league_directories()
    
    # Old folder should be renamed to nba.l.18457
    new_folder = os.path.join(temp_data_dir, "league", "nba.l.18457")
    assert os.path.exists(new_folder)
    assert not os.path.exists(old_folder)
    
    # Mapping file should be updated
    with open(mapping_file, "r") as f:
        mapping = json.load(f)
    assert mapping["chat1"] == "nba.l.18457"
    
    shutil.rmtree(temp_data_dir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_path_migration.py -v`
Expected: FAIL due to assertions or missing `migrate_old_league_directories` function.

- [ ] **Step 3: Modify `path_utils.py` and `bot.py`**

In [src/utils/path_utils.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/path_utils.py):
```python
def get_league_dir(league_id: str) -> str:
    if not league_id:
        return os.path.join(DATA_DIR, "league", "default")
    
    # Normalize key to full league key (e.g. nba.l.18457)
    lid_str = str(league_id).strip()
    if not lid_str.startswith("nba.l.") and not lid_str.startswith("mlb.l."):
        # Check if there's any prefix
        if "." in lid_str:
            normalized_id = lid_str
        else:
            normalized_id = f"nba.l.{lid_str}"
    else:
        normalized_id = lid_str
        
    return os.path.join(DATA_DIR, "league", normalized_id)
```
Add the migration helper to `path_utils.py`:
```python
def migrate_old_league_directories():
    league_base = os.path.join(DATA_DIR, "league")
    if not os.path.exists(league_base):
        return
        
    # Rename folder from raw numeric to nba.l.<number>
    for name in os.listdir(league_base):
        full_path = os.path.join(league_base, name)
        if os.path.isdir(full_path) and name.isdigit():
            new_name = f"nba.l.{name}"
            new_path = os.path.join(league_base, new_name)
            if not os.path.exists(new_path):
                try:
                    os.rename(full_path, new_path)
                    logging.info(f"[SYSTEM] 已將歷史目錄 {name} 重新命名為 {new_name}")
                except Exception as e:
                    logging.error(f"重命名目錄失敗: {e}")
                    
    # Upgrade chat_league_mapping.json keys
    mapping_file = os.path.join(DATA_DIR, "security", "chat_league_mapping.json")
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            updated = False
            for k, v in list(mapping.items()):
                v_str = str(v).strip()
                if v_str.isdigit():
                    mapping[k] = f"nba.l.{v_str}"
                    updated = True
            if updated:
                with open(mapping_file, "w", encoding="utf-8") as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=2)
                logging.info("[SYSTEM] 已成功升級對照表中的舊型聯賽 ID 格式")
        except Exception as e:
            logging.error(f"升級對照表失敗: {e}")
```

In [bot.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/bot.py):
At startup, import and run `migrate_old_league_directories()`:
```python
if __name__ == "__main__":
    cleanup_port(5001)
    from src.utils.path_utils import migrate_old_league_directories
    migrate_old_league_directories()
    
    config = load_config()
    ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_path_migration.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/utils/path_utils.py bot.py tests/test_path_migration.py
git commit -m "feat: implement path prefix preservation and directory migration"
```

---

### Task 2: Dynamic Settings Caching in Fetcher

**Files:**
* Modify: [src/fetcher.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/fetcher.py)
* Test: Create `tests/test_dynamic_settings_sync.py`

- [ ] **Step 1: Write a failing test for settings sync and dynamic stat ID translation**

Create `tests/test_dynamic_settings_sync.py`:
```python
import os
import json
import tempfile
import shutil
import pytest
import xml.etree.ElementTree as ET
from src.fetcher import YahooFantasyFetcher

mock_settings_xml = """<?xml version="1.0" encoding="UTF-8"?>
<fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
  <league>
    <settings>
      <stat_categories>
        <stats>
          <stat>
            <stat_id>12</stat_id>
            <name>Points</name>
            <display_name>PTS</display_name>
            <sort_order>1</sort_order>
          </stat>
          <stat>
            <stat_id>19</stat_id>
            <name>Turnovers</name>
            <display_name>TO</display_name>
            <sort_order>0</sort_order>
          </stat>
        </stats>
      </stat_categories>
    </settings>
  </league>
</fantasy_content>
"""

def test_fetch_and_cache_settings(mocker):
    temp_dir = tempfile.mkdtemp()
    mocker.patch("src.utils.path_utils.DATA_DIR", temp_dir)
    
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    mock_ctx.make_request.return_value = mock_settings_xml
    
    fetcher = YahooFantasyFetcher(league_id="nba.l.18457")
    fetcher.ctx = mock_ctx
    
    stats_list = fetcher.sync_league_settings("nba.l.18457")
    assert len(stats_list) == 2
    assert stats_list[0]["display_name"] == "PTS"
    assert stats_list[0]["sort_order"] == 1
    assert stats_list[1]["display_name"] == "TO"
    assert stats_list[1]["sort_order"] == 0
    
    # Check cached metadata file contains categories
    meta_file = os.path.join(temp_dir, "league", "nba.l.18457", "metadata.json")
    assert os.path.exists(meta_file)
    with open(meta_file, "r") as f:
        meta = json.load(f)
    assert "stat_categories" in meta
    assert meta["stat_categories"][0]["display_name"] == "PTS"
    
    shutil.rmtree(temp_dir)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_dynamic_settings_sync.py -v`
Expected: FAIL with `AttributeError` since `sync_league_settings` is not implemented on `YahooFantasyFetcher`.

- [ ] **Step 3: Modify `fetcher.py`**

In [src/fetcher.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/fetcher.py):
Add the `sync_league_settings` method and update `sync_season_metadata` to call it. Update the stat translation to read dynamically from cached metadata.

```python
    @handle_permission_errors
    def sync_league_settings(self, league_id: str) -> list:
        """Fetch league settings and parse all stats categories with sort orders."""
        league_id = self._normalize_league_id(league_id)
        url = f"league/{league_id}/settings"
        xml_data = self.ctx.make_request(url)
        root = ET.fromstring(xml_data)
        
        stats = []
        stat_nodes = root.findall('.//ns:stat_categories/ns:stats/ns:stat', YAHOO_NS)
        for node in stat_nodes:
            s_id_node = node.find('ns:stat_id', YAHOO_NS)
            name_node = node.find('ns:name', YAHOO_NS)
            disp_node = node.find('ns:display_name', YAHOO_NS)
            sort_node = node.find('ns:sort_order', YAHOO_NS)
            
            s_id = s_id_node.text if s_id_node is not None else None
            disp = disp_node.text if disp_node is not None else (name_node.text if name_node is not None else "")
            sort_val = int(sort_node.text) if (sort_node is not None and sort_node.text is not None) else 1
            
            if s_id:
                stats.append({
                    "stat_id": str(s_id),
                    "display_name": str(disp),
                    "sort_order": sort_val
                })
                
        # Cache it in metadata.json
        from src.utils.path_utils import get_league_dir
        raw_id = league_id
        meta_path = os.path.join(get_league_dir(raw_id), "metadata.json")
        meta = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass
        meta["stat_categories"] = stats
        os.makedirs(os.path.dirname(meta_path), exist_ok=True)
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            
        return stats
```
Modify `sync_season_metadata`:
```python
def sync_season_metadata(fetcher: YahooFantasyFetcher, league_id: str):
    ...
    # Query details and save
    meta = fetcher.fetch_league_metadata(league_id)
    # Fetch and cache settings categories
    fetcher.sync_league_settings(league_id)
```
Update `_parse_stats` inside `fetcher.py` to translate dynamically:
```python
    def _parse_stats(self, team) -> dict:
        """Parse stats dynamically matching database/metadata configurations."""
        # Load local stats categories if available
        from src.utils.path_utils import get_league_dir
        meta_path = os.path.join(get_league_dir(self.ctx._persist_key.split("/")[-2]), "metadata.json")
        stat_map = {}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    for cat in meta.get("stat_categories", []):
                        stat_map[str(cat["stat_id"])] = cat["display_name"]
            except Exception:
                pass
                
        # Fallback to hardcoded STAT_MAP if file not loaded
        if not stat_map:
            from src.constants.stat_map import STAT_MAP
            stat_map = STAT_MAP

        stats_dict = {}
        for stat in team.stats:
            stat_id = str(stat.stat_id)
            stat_name = stat_map.get(stat_id, f"stat_{stat_id}")
            stats_dict[stat_name] = stat.value
        return stats_dict
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_dynamic_settings_sync.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/fetcher.py tests/test_dynamic_settings_sync.py
git commit -m "feat: implement settings fetching and dynamic stat mappings"
```

---

### Task 3: Dynamic Visualizer Processing & Formatting Heuristics

**Files:**
* Modify: [src/visualizer/processor.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/visualizer/processor.py)
* Test: Create `tests/test_multi_sport_visualizer.py`

- [ ] **Step 1: Write a failing test for visualizer processing and formatting**

Create `tests/test_multi_sport_visualizer.py`:
```python
import json
import pytest
from src.visualizer.processor import process_stats_for_visual

def test_process_stats_for_visual_nba(mocker):
    # Mock metadata file read
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps({
        "stat_categories": [
            {"stat_id": "12", "display_name": "PTS", "sort_order": 1},
            {"stat_id": "19", "display_name": "TO", "sort_order": 0},
            {"stat_id": "5", "display_name": "FG%", "sort_order": 1},
            {"stat_id": "9004003", "display_name": "FGM/FGA", "sort_order": 1}
        ]
    })))
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("src.visualizer.processor.current_chat_id.get", return_value="chat1")
    mocker.patch("src.visualizer.processor.load_config", return_value={"LEAGUE_ID": "nba.l.18457"})
    
    sample_data = {
        "team_stats": [
            {"team_id": "1", "name": "Team A", "stats": {"PTS": "105", "TO": "12", "FG%": "0.485", "FGM/FGA": "45/90"}}
        ]
    }
    
    result = process_stats_for_visual(sample_data)
    assert len(result) > 0
    
    # Check FGM/FGA display name replaced by alias 'FG'
    fg_cat = next(c for c in result if c["label"] == "FG")
    assert fg_cat["rows"][0]["value"] == "45/90"
    
    # Check percentage formatted
    fg_pct = next(c for c in result if c["label"] == "FG%")
    assert fg_pct["rows"][0]["value"] == "48.5%"
    
    # Check sort order reverse matches settings
    to_cat = next(c for c in result if c["label"] == "TO")
    assert to_cat["reverse"] is False # Low better

def test_process_stats_for_visual_mlb(mocker):
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps({
        "stat_categories": [
            {"stat_id": "1", "display_name": "AVG", "sort_order": 1},
            {"stat_id": "2", "display_name": "ERA", "sort_order": 0},
            {"stat_id": "3", "display_name": "WHIP", "sort_order": 0}
        ]
    })))
    mocker.patch("os.path.exists", return_value=True)
    mocker.patch("src.visualizer.processor.current_chat_id.get", return_value="chat1")
    mocker.patch("src.visualizer.processor.load_config", return_value={"LEAGUE_ID": "mlb.l.12345"})
    
    sample_data = {
        "team_stats": [
            {"team_id": "1", "name": "Team A", "stats": {"AVG": "0.2854", "ERA": "3.456", "WHIP": "1.123"}}
        ]
    }
    
    result = process_stats_for_visual(sample_data)
    
    # Check AVG formatted to 3 decimals with leading zero stripped
    avg_cat = next(c for c in result if c["label"] == "AVG")
    assert avg_cat["rows"][0]["value"] == ".285"
    
    # Check ERA formatted to 2 decimals
    era_cat = next(c for c in result if c["label"] == "ERA")
    assert era_cat["rows"][0]["value"] == "3.46"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_multi_sport_visualizer.py -v`
Expected: FAIL with format deviations (since visualizer still uses hardcoded categories).

- [ ] **Step 3: Refactor `processor.py`**

In [src/visualizer/processor.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/visualizer/processor.py):
Replace categories resolution with metadata loading, display name mapping, and heuristic formatting:
```python
import os
import json
from src.config import load_config, current_chat_id
from src.utils.path_utils import get_league_dir

DISPLAY_ALIASES = {
    "FGM/FGA": "FG",
    "FTM/FTA": "FT",
    "3PTM": "3PT"
}

def process_stats_for_visual(data: dict) -> list:
    team_stats = data.get("team_stats", [])
    if not team_stats:
        return []

    # Get active league ID to read stats configuration
    config = load_config()
    league_id = config.get("LEAGUE_ID", "default")
    meta_path = os.path.join(get_league_dir(league_id), "metadata.json")
    
    stat_categories = []
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                stat_categories = meta.get("stat_categories", [])
        except Exception:
            pass

    # Build categories list dynamically
    categories = []
    
    # Check for Game Player data
    if any("GP_PLAYED" in t["stats"] for t in team_stats):
        for t in team_stats:
            played = t["stats"].get("GP_PLAYED", 0)
            total = t["stats"].get("GP_TOTAL", 0)
            t["stats"]["GP_SORT_KEY"] = (played * 1000) + total
            t["stats"]["Game Player"] = f"{played} / {total}"
        categories.append({"label": "Game Player", "data_key": "Game Player", "sort_key": "GP_SORT_KEY", "reverse": True})

    # Check for Today Player data
    if any("Today Player" in t["stats"] for t in team_stats):
        categories.append({"label": "Today Player", "data_key": "Today Player", "sort_key": "Today Player", "reverse": True})

    # Add dynamic stats categories from settings cache
    for cat in stat_categories:
        disp_name = cat["display_name"]
        label = DISPLAY_ALIASES.get(disp_name, disp_name)
        reverse_val = True if cat["sort_order"] == 1 else False
        categories.append({
            "label": label,
            "data_key": disp_name,
            "sort_key": disp_name,
            "reverse": reverse_val
        })

    # Formatting heuristics helper
    def format_val(label, val):
        if val is None or str(val).strip() in ("", "-"):
            return "-"
            
        # 1. Percentage (e.g. FG%)
        if "%" in label:
            try:
                num = float(val)
                if num == 0: return "-"
                return f"{num * 100:.1f}%"
            except (ValueError, TypeError):
                pass
                
        # 2. Baseball rate (AVG, OBP, SLG, OPS) -> 3 decimals (strip leading zero)
        if label in ["AVG", "OBP", "SLG", "OPS"]:
            try:
                num = float(val)
                formatted = f"{num:.3f}"
                if formatted.startswith("0."):
                    return formatted[1:]
                return formatted
            except (ValueError, TypeError):
                pass
                
        # 3. Baseball pitching (ERA, WHIP) -> 2 decimals
        if label in ["ERA", "WHIP"]:
            try:
                num = float(val)
                return f"{num:.2f}"
            except (ValueError, TypeError):
                pass
                
        return val

    result = []
    for cat in categories:
        def sort_key_func(team):
            val = team["stats"].get(cat["sort_key"], 0)
            if isinstance(val, (int, float)):
                return val
            try: return float(str(val).strip('%'))
            except (ValueError, TypeError): return 0

        # Sort teams according to the category rule
        sorted_teams = sorted(team_stats, key=sort_key_func, reverse=cat["reverse"])
        
        rows = []
        for rank, team in enumerate(sorted_teams, 1):
            rows.append({
                "rank": rank,
                "name": team["name"],
                "value": format_val(cat["label"], team["stats"].get(cat["data_key"]))
            })
            
        result.append({
            "label": cat["label"],
            "rows": rows
        })
        
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_multi_sport_visualizer.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/visualizer/processor.py tests/test_multi_sport_visualizer.py
git commit -m "feat: support dynamic visualizer processing with auto-formatting heuristics"
```

---

### Task 4: Interactive Sport Selection & Setup Flow

**Files:**
* Modify: [src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py)
* Test: Update `tests/handlers/test_settings_and_setup.py`

- [ ] **Step 1: Write a failing test for dynamic sport prompt and binding**

Add a test case in `tests/handlers/test_settings_and_setup.py`:
```python
def test_set_league_id_handler_prompt_sport(mocker):
    # Verify triggering #設置聯盟ID prints the Flex selection message
    from src.handlers.set_league_id_handler import SetLeagueIdHandler
    handler = SetLeagueIdHandler()
    
    mock_event = mocker.MagicMock()
    mock_event.message.text = "#設置聯盟ID"
    mock_event.source.sender_id = "user1"
    
    mock_reply = mocker.patch.object(handler, "reply_message")
    handler.execute(mock_event, {})
    
    # Assert it replies with a Flex Message (containing sports selection layout)
    args, kwargs = mock_reply.call_args
    assert args[1] is not None # Flex message object
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py -v`
Expected: FAIL since the handler directly triggers numeric prompting instead of sport selection.

- [ ] **Step 3: Modify `set_league_id_handler.py`**

In [src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py):
Modify `execute` to output sport buttons:
```python
    def execute(self, event, configuration):
        text = event.message.text.strip()
        chat_id = event.source.sender_id
        
        # 1. 初始指令，回覆運動選單 Flex
        if text == "#設置聯盟ID":
            # 建立 Flex Message 選項
            from linebot.v3.messaging import FlexMessage, FlexContainer
            bubble = {
              "type": "bubble",
              "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                  {"type": "text", "text": "請選擇要設置的運動項目：", "weight": "bold", "size": "md"},
                  {
                    "type": "box",
                    "layout": "horizontal",
                    "margin": "lg",
                    "contents": [
                      {
                        "type": "button",
                        "action": {"type": "message", "label": "NBA 籃球", "text": "#設置聯盟ID nba"},
                        "style": "primary",
                        "color": "#00B900"
                      },
                      {
                        "type": "button",
                        "action": {"type": "message", "label": "MLB 棒球", "text": "#設置聯盟ID mlb"},
                        "style": "primary",
                        "color": "#1E90FF",
                        "margin": "md"
                      }
                    ]
                  }
                ]
              }
            }
            flex = FlexMessage(alt_text="請選擇要設置的運動項目", contents=FlexContainer.from_dict(bubble))
            self.reply_message(event, flex)
            return

        # 2. 已選運動，引導使用者輸入 ID
        parts = text.split()
        if len(parts) == 2 and parts[1].lower() in ["nba", "mlb"]:
            sport = parts[1].lower()
            # 啟動 60 秒改寫對話，等待輸入數字 ID
            session_manager.set_session(chat_id, "set_league_id", {"sport": sport})
            sport_name = "NBA 籃球" if sport == "nba" else "MLB 棒球"
            self.reply_text(event, configuration, f"您選擇了 {sport_name}。請在 60 秒內輸入您的聯盟 ID（純數字，例如 18457）：")
            return
            
        # 3. 處理使用者輸入的數字 ID (互動會話中)
        session = session_manager.get_session(chat_id)
        if session and session.get("type") == "set_league_id" and text.isdigit():
            sport = session.get("data", {}).get("sport", "nba")
            target_id = f"{sport}.l.{text}"
            session_manager.clear_session(chat_id)
        else:
            # 直接輸入參數（如：#設置聯盟ID nba.l.18457）
            if len(parts) < 2:
                self.reply_text(event, configuration, "⚠️ 指令格式錯誤。")
                return
            target_id = parts[1].strip()
            # 補全前綴
            if not target_id.startswith("nba.l.") and not target_id.startswith("mlb.l."):
                target_id = f"nba.l.{target_id}"

        # 驗證聯盟與寫入資料 (後面流程保持相同，傳入完整的 target_id)
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/handlers/test_settings_and_setup.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/handlers/set_league_id_handler.py
git commit -m "feat: implement interactive sport selection for league binding"
```

---

### Task 5: LLM Sport Contextualization

**Files:**
* Modify: [src/llm/llm_agent.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/llm/llm_agent.py)
* Modify: [src/llm/prompts/player_fuzzy_search.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/llm/prompts/player_fuzzy_search.py)
* Test: Create `tests/test_llm_sport_scope.py`

- [ ] **Step 1: Write a failing test for dynamic sport prompt and Google Search keywords**

Create `tests/test_llm_sport_scope.py`:
```python
import pytest
from src.llm.llm_agent import LLMAgent

def test_player_fuzzy_search_sport_context(mocker):
    agent = LLMAgent()
    
    mock_provider = mocker.patch.object(agent, "provider")
    mock_provider.generate_json.return_value = {
        "is_known_player": True,
        "english_name": "Shohei Ohtani",
        "chinese_name": "大谷翔平",
        "team": "LAD",
        "jersey_number": "17"
    }
    
    # Fuzzy search under MLB context
    res = agent.player_fuzzy_search("大谷", sport="mlb")
    assert res["english_name"] == "Shohei Ohtani"
    
    # Check that query string containing "MLB" was sent to Google Search
    args, kwargs = mock_provider.generate_json.call_args
    prompt_text = args[0]
    assert "MLB" in prompt_text
    assert "棒球專家" in prompt_text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_llm_sport_scope.py -v`
Expected: FAIL since LLMAgent does not accept `sport` or injects "NBA" by default.

- [ ] **Step 3: Modify `llm_agent.py` and `player_fuzzy_search.py`**

In [src/llm/prompts/player_fuzzy_search.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/llm/prompts/player_fuzzy_search.py):
Change prompts to use formatting variables:
```python
def get_system_prompt(sport: str) -> str:
    sport_name = "MLB 棒球" if sport == "mlb" else "NBA 籃球"
    sport_short = "MLB" if sport == "mlb" else "NBA"
    return f"""你是一個精準的 {sport_name} 專家，專門負責將使用者的模糊輸入（例如球員綽號、簡稱、中文音譯或背號加上球隊）解析為官方標準的現役球員資訊。
1. 僅識別真實存在的 {sport_short} 「現役球員 (Active Players)」。
..."""
```

In [src/llm/llm_agent.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/llm/llm_agent.py):
Modify `player_fuzzy_search` to accept `sport: str = "nba"`:
```python
    def player_fuzzy_search(self, nickname: str, sport: str = "nba") -> dict:
        sport = str(sport).lower()
        sport_name = "MLB" if sport == "mlb" else "NBA"
        sport_desc = "MLB 棒球" if sport == "mlb" else "NBA 籃球"
        
        # 組合搜尋關鍵字
        query = f'{sport_name} "{nickname}"'
        search_results = self.google_search(query)
        
        from src.llm.prompts.player_fuzzy_search import get_system_prompt
        system_prompt = get_system_prompt(sport)
        
        prompt = f"""你是一個精準的 {sport_desc} 專家。我們在網路搜尋了「{query}」，得到以下結果：
{json.dumps(search_results, ensure_ascii=False, indent=2)}

請結合上述搜尋結果以及你的知識，解析使用者的輸入「{nickname}」是指哪位現役 {sport_name} 球員。"""
        
        return self.provider.generate_json(prompt, system_prompt)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_llm_sport_scope.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/llm/llm_agent.py src/llm/prompts/player_fuzzy_search.py tests/test_llm_sport_scope.py
git commit -m "feat: contextualize LLM search scope by active sport"
```

---

### Task 6: Fallback Limitations for MLB (ESPN & Countdown)

**Files:**
* Modify: [src/utils/time_utils.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/time_utils.py)
* Modify: [src/handlers/misc_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/misc_handler.py)
* Modify: [src/handlers/injury_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/injury_handler.py)
* Test: Create `tests/test_mlb_restrictions.py`

- [ ] **Step 1: Write a failing test for MLB countdown and ESPN status bypass**

Create `tests/test_mlb_restrictions.py`:
```python
import pytest
from src.utils.time_utils import is_game_day
from src.handlers.misc_handler import SeasonCountdownHandler
from src.handlers.injury_handler import InjuryHandler

def test_is_game_day_bypassed_for_mlb():
    # If sport is mlb, is_game_day should skip ESPN and return True
    assert is_game_day(sport="mlb") == (True, "")

def test_countdown_handler_restricts_mlb(mocker):
    handler = SeasonCountdownHandler()
    mock_event = mocker.MagicMock()
    mock_event.message.text = "#開季"
    mock_reply = mocker.patch.object(handler, "reply_text")
    
    # Under MLB configuration
    handler.execute(mock_event, {"LEAGUE_ID": "mlb.l.12345"})
    mock_reply.assert_called_with(mock_event, mocker.ANY, "⚠️ 此功能目前僅支援 NBA 聯賽。")

def test_injury_handler_restricts_mlb(mocker):
    handler = InjuryHandler()
    mock_event = mocker.MagicMock()
    mock_event.message.text = "#傷兵"
    mock_reply = mocker.patch.object(handler, "reply_text")
    
    # Under MLB configuration
    handler.execute(mock_event, {"LEAGUE_ID": "mlb.l.12345"})
    mock_reply.assert_called_with(mock_event, mocker.ANY, "⚠️ 此功能目前僅支援 NBA 聯賽。")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_mlb_restrictions.py -v`
Expected: FAIL since the countdown and injury handlers do not check for MLB, and `is_game_day` tries to query ESPN for NBA.

- [ ] **Step 3: Modify `time_utils.py`, `misc_handler.py`, and `injury_handler.py`**

In [src/utils/time_utils.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/time_utils.py):
Modify `is_game_day` to accept `sport: str = "nba"`:
```python
def is_game_day(sport: str = "nba") -> tuple[bool, str]:
    if sport != "nba":
        # Bypass for other sports
        return True, ""
        
    # Existing ESPN scoreboard lookup for NBA...
    ...
```

In [src/handlers/misc_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/misc_handler.py):
At the top of `SeasonCountdownHandler.execute`:
```python
    def execute(self, event, configuration):
        league_id = configuration.get("LEAGUE_ID", "")
        if str(league_id).startswith("mlb.l."):
            self.reply_text(event, configuration, "⚠️ 此功能目前僅支援 NBA 聯賽。")
            return
            
        # Existing NBA countdown logic...
        ...
```

In [src/handlers/injury_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/injury_handler.py):
At the top of `InjuryHandler.execute`:
```python
    def execute(self, event, configuration):
        league_id = configuration.get("LEAGUE_ID", "")
        if str(league_id).startswith("mlb.l."):
            self.reply_text(event, configuration, "⚠️ 此功能目前僅支援 NBA 聯賽。")
            return
            
        # Existing NBA injury lookup logic...
        ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_mlb_restrictions.py -v`
Expected: PASS

- [ ] **Step 5: Commit changes**

```bash
git add src/utils/time_utils.py src/handlers/misc_handler.py src/handlers/injury_handler.py tests/test_mlb_restrictions.py
git commit -m "feat: restrict ESPN status check, countdown, and injury query to NBA only"
```
