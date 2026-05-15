# Enhanced Weekly/Daily Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement automatic weekly/daily stats fetching with standard abbreviations (PTS, REB, BLK, etc.) and hierarchical storage.

**Architecture:** Use a dedicated translation map for stat IDs, a time utility for Pacific Time week calculations, and an enhanced fetcher to query Yahoo's scoreboard APIs for daily/weekly data.

**Tech Stack:** Python 3, `yahoofantasy`, `pytz` (for timezone), `pytest`

---

### Task 1: Setup Constants and Configuration

**Files:**
- Create: `src/constants/stat_map.py`
- Modify: `src/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Create `src/constants/stat_map.py`**

```python
STAT_MAP = {
    "12": "PTS",
    "15": "REB",
    "16": "AST",
    "17": "ST",
    "18": "BLK",
    "19": "TO",
    "5": "FG%",
    "8": "FT%",
    "11": "3PT%",
    "9004003": "FGM/FGA",
    "9007006": "FTM/FTA"
}

def translate_stat_id(stat_id: str) -> str:
    """Translate a Yahoo stat ID to a standard abbreviation."""
    return STAT_MAP.get(str(stat_id), f"stat_{stat_id}")
```

- [ ] **Step 2: Update `src/config.py` to include `SEASON_START_DATE`**

```python
import os
from dotenv import load_dotenv

def load_config() -> dict:
    load_dotenv()
    league_id = os.getenv("LEAGUE_ID")
    if not league_id:
        raise ValueError("LEAGUE_ID is not set in environment or .env file.")
    
    mapping_file = os.getenv("TEAM_MAPPING_FILE", "team_mapping.json")
    # Default to a placeholder if not set
    season_start = os.getenv("SEASON_START_DATE", "2025-10-21")
    
    return {
        "LEAGUE_ID": league_id,
        "TEAM_MAPPING_FILE": mapping_file,
        "SEASON_START_DATE": season_start
    }
```

- [ ] **Step 3: Update `.env.example`**

```text
LEAGUE_ID=your_league_id_here
TEAM_MAPPING_FILE=team_mapping.json
SEASON_START_DATE=2025-10-21
```

- [ ] **Step 4: Commit**

```bash
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git add src/constants/stat_map.py src/config.py .env.example
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git commit -m "feat: add stat mapping and season start configuration"
```

---

### Task 2: Time and Week Calculation Utilities

**Files:**
- Create: `src/utils/time_utils.py`
- Create: `tests/test_time_utils.py`

- [ ] **Step 1: Write tests for `src/utils/time_utils.py`**

```python
import pytest
from datetime import datetime
import pytz
from src.utils.time_utils import get_fantasy_week, get_pacific_date

def test_get_fantasy_week():
    start_date = "2025-10-21" # A Tuesday
    # Week 1 starts from 10-21 until next Monday 00:00 PT
    
    # Same week Sunday 23:59 PT
    dt1 = datetime(2025, 10, 26, 23, 59, 59, tzinfo=pytz.timezone("US/Pacific"))
    assert get_fantasy_week(start_date, current_dt=dt1) == 1
    
    # Next week Monday 00:00 PT
    dt2 = datetime(2025, 10, 27, 0, 0, 0, tzinfo=pytz.timezone("US/Pacific"))
    assert get_fantasy_week(start_date, current_dt=dt2) == 2

def test_get_pacific_date():
    date_str = get_pacific_date()
    assert len(date_str) == 10
    datetime.strptime(date_str, "%Y-%m-%d")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_time_utils.py`
Expected: FAIL (ModuleNotFound)

- [ ] **Step 3: Implement `src/utils/time_utils.py`**

```python
from datetime import datetime, timedelta
import pytz

def get_pacific_datetime():
    return datetime.now(pytz.timezone("US/Pacific"))

def get_pacific_date():
    return get_pacific_datetime().strftime("%Y-%m-%d")

def get_fantasy_week(start_date_str: str, current_dt=None) -> int:
    if current_dt is None:
        current_dt = get_pacific_datetime()
    
    start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
    start_dt = pytz.timezone("US/Pacific").localize(start_dt)
    
    # Find the Monday 00:00 PT of the start week
    # start_dt.weekday(): 0=Monday, 1=Tuesday...
    start_monday = start_dt - timedelta(days=start_dt.weekday())
    start_monday = start_monday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    delta = current_dt - start_monday
    week = (delta.days // 7) + 1
    return max(1, week)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_time_utils.py`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git add src/utils/time_utils.py tests/test_time_utils.py
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git commit -m "feat: add time utilities for week calculation"
```

---

### Task 3: Enhance Storage for Subdirectories

**Files:**
- Modify: `src/storage.py`

- [ ] **Step 1: Update `JsonStorage.save` to support subdirectories and overwrite**

```python
# src/storage.py modification
    def save(self, data: dict, identifier: str, sub_dir: str = "", overwrite: bool = False) -> str:
        target_dir = os.path.join(self.data_dir, sub_dir)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        if overwrite:
            filename = f"{identifier}.json"
        else:
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            filename = f"{timestamp}_{identifier}.json"
            
        filepath = os.path.join(target_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        return filepath
```

- [ ] **Step 2: Commit**

```bash
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git add src/storage.py
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git commit -m "feat: allow subdirectories and overwrite in JsonStorage"
```

---

### Task 4: Enhance Fetcher with Stat Translation and New Methods

**Files:**
- Modify: `src/fetcher.py`
- Modify: `tests/test_fetcher.py`

- [ ] **Step 1: Implement stat translation and scoreboard parsing in `src/fetcher.py`**

```python
# src/fetcher.py modifications
from src.constants.stat_map import translate_stat_id

# In YahooFantasyFetcher:
    def _parse_stats(self, team_obj) -> dict:
        """Extract and translate stats from a team object (standings or scoreboard)."""
        stats_dict = {}
        # Try team_standings
        standings = getattr(team_obj, "team_standings", None)
        if standings:
            for attr in dir(standings):
                if not attr.startswith('_') and not callable(getattr(standings, attr)):
                    val = getattr(standings, attr)
                    if hasattr(val, '__dict__') or (hasattr(val, 'ctx') and hasattr(val, 'id')):
                        for sub_attr in dir(val):
                            if not sub_attr.startswith('_') and not callable(getattr(val, sub_attr)):
                                stats_dict[f"{attr}_{sub_attr}"] = getattr(val, sub_attr)
                    else:
                        stats_dict[attr] = val
        
        # Try team_stats
        tstats = getattr(team_obj, "team_stats", None)
        if tstats and hasattr(tstats, 'stats'):
            try:
                for s in tstats.stats:
                    s_id = getattr(s, 'stat_id', None)
                    s_val = getattr(s, 'value', None)
                    if s_id is not None:
                        label = translate_stat_id(s_id)
                        stats_dict[label] = s_val
            except Exception:
                pass
        return stats_dict

    def fetch_weekly_stats(self, league_id: str, week: int) -> dict:
        if not league_id.startswith('nba.l.'): league_id = f"nba.l.{league_id}"
        league = yahoofantasy.League(self.ctx, league_id)
        # scoreboard;week=N
        data = self.ctx._load_or_fetch(f"weekly_stats.{league_id}.{week}", f"scoreboard;week={week}", league=league_id)
        return self._parse_scoreboard(data)

    def fetch_daily_stats(self, league_id: str, date_str: str) -> dict:
        if not league_id.startswith('nba.l.'): league_id = f"nba.l.{league_id}"
        league = yahoofantasy.League(self.ctx, league_id)
        # scoreboard;type=day;date=YYYY-MM-DD
        data = self.ctx._load_or_fetch(f"daily_stats.{league_id}.{date_str}", f"scoreboard;type=day;date={date_str}", league=league_id)
        return self._parse_scoreboard(data)

    def _parse_scoreboard(self, data) -> dict:
        from yahoofantasy.api.parse import as_list, from_response_object
        from yahoofantasy.resources.team import Team
        
        team_stats_data = []
        try:
            matchups = data["fantasy_content"]["league"]["scoreboard"]["matchups"]["matchup"]
            for matchup in as_list(matchups):
                for team_data in as_list(matchup["teams"]["team"]):
                    t = Team(self.ctx, None, team_data["team_id"])
                    from_response_object(t, team_data)
                    team_id = str(getattr(t, "team_id", ""))
                    team_name = self.team_mapping.get(team_id, str(getattr(t, "name", "Unknown")))
                    team_stats_data.append({
                        "name": team_name,
                        "stats": self._parse_stats(t)
                    })
        except Exception:
            pass
        return {"team_stats": team_stats_data}
```

- [ ] **Step 2: Commit**

```bash
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git add src/fetcher.py
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git commit -m "feat: implement weekly and daily stats fetching with translation"
```

---

### Task 5: Orchestration in `main.py`

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update `main.py` to orchestrate all fetches**

```python
# main.py update
from src.utils.time_utils import get_fantasy_week, get_pacific_date

# Inside main():
        # ... fetcher init ...
        
        # 1. Season Stats
        logging.info("Fetching season stats...")
        season_stats = fetcher.fetch_team_stats(league_id)
        storage.save(season_stats, "season_stats", overwrite=True)
        
        # 2. Weekly Stats
        current_week = get_fantasy_week(config["SEASON_START_DATE"])
        logging.info(f"Fetching weekly stats for Week {current_week}...")
        weekly_stats = fetcher.fetch_weekly_stats(league_id, current_week)
        storage.save(weekly_stats, f"week_{current_week}", sub_dir="weekly", overwrite=True)
        
        # 3. Daily Stats
        today_str = get_pacific_date()
        logging.info(f"Fetching daily stats for {today_str}...")
        daily_stats = fetcher.fetch_daily_stats(league_id, today_str)
        storage.save(daily_stats, today_str, sub_dir="daily", overwrite=True)
```

- [ ] **Step 2: Commit**

```bash
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git add main.py
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git commit -m "feat: orchestrate multi-level stats fetching"
```
