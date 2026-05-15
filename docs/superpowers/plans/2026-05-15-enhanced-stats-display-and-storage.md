# Enhanced Stats Display and Storage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Formats percentages nicely, treats null data as 0, adds a rank column to tables, and stores data in season-specific subdirectories.

**Architecture:** Modifies fetcher to cast nulls to 0, updates the visualizer processor to string format percentage and attach ranks, tweaks HTML template to add a narrow column for rank, and reads a `SEASON` env var to modify save paths.

**Tech Stack:** Python 3, Jinja2/HTML

---

### Task 1: Update Configuration to support SEASON

**Files:**
- Modify: `src/config.py`
- Modify: `tests/test_config.py`
- Modify: `.env.example`

- [ ] **Step 1: Write the failing test for `SEASON` config**

```python
# In tests/test_config.py
import os
import pytest
from src.config import load_config

def test_load_config_with_season(monkeypatch):
    monkeypatch.setenv("LEAGUE_ID", "12345")
    monkeypatch.setenv("SEASON", "24-25")
    
    config = load_config()
    
    assert config["LEAGUE_ID"] == "12345"
    assert config["SEASON"] == "24-25"

def test_load_config_default_season(monkeypatch):
    monkeypatch.setenv("LEAGUE_ID", "12345")
    monkeypatch.delenv("SEASON", raising=False)
    
    config = load_config()
    
    assert config["SEASON"] == "default"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: FAIL, because `SEASON` is not in returned config.

- [ ] **Step 3: Update `src/config.py` and `.env.example`**

```python
# In src/config.py
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
    season = os.getenv("SEASON", "default")
    
    return {
        "LEAGUE_ID": league_id,
        "TEAM_MAPPING_FILE": mapping_file,
        "SEASON_START_DATE": season_start,
        "SEASON": season
    }
```

```env
# Append to .env.example
SEASON=24-25
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py .env.example
git commit -m "feat: add SEASON to config"
```

### Task 2: Handle Null Values in Fetcher

**Files:**
- Modify: `src/fetcher.py`
- Modify: `tests/test_fetcher.py`

- [ ] **Step 1: Write the failing test for null conversion**

```python
# In tests/test_fetcher.py
from src.fetcher import YahooFantasyFetcher

def test_get_val_null_handling():
    fetcher = YahooFantasyFetcher()
    
    assert fetcher._get_val(None) == 0
    assert fetcher._get_val("-") == 0
    assert fetcher._get_val("null") == 0
    assert fetcher._get_val("") == 0
    
    class DummyObj:
        pass
        
    dummy = DummyObj()
    setattr(dummy, "$", "-")
    assert fetcher._get_val(dummy) == 0
    
    dummy2 = DummyObj()
    setattr(dummy2, "$", "123")
    assert fetcher._get_val(dummy2) == "123"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fetcher.py -v`
Expected: FAIL

- [ ] **Step 3: Update `fetcher.py`**

```python
# In src/fetcher.py (modify the _get_val method)
    def _get_val(self, obj):
        """Helper to get a serializable value from a Yahoo API object."""
        val = obj
        if hasattr(obj, "$"):
            val = getattr(obj, "$")
        elif hasattr(obj, "__dict__"):
            val = str(obj)
            
        if val in (None, "-", "null", ""):
            return 0
            
        return val
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fetcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "fix: convert api null values to 0 in fetcher"
```

### Task 3: Format Percentages and Add Ranks in Processor

**Files:**
- Modify: `src/visualizer/processor.py`
- Modify: `tests/test_visualizer_processor.py`

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_visualizer_processor.py
from src.visualizer.processor import process_stats_for_visual

def test_process_stats_formatting_and_ranking():
    data = {
        "team_stats": [
            {"name": "Team A", "stats": {"FG%": 0.456, "FT%": 0, "PTS": 100}},
            {"name": "Team B", "stats": {"FG%": 0.501, "FT%": 0.852, "PTS": 90}}
        ]
    }
    result = process_stats_for_visual(data)
    
    fg_cat = next(cat for cat in result if cat["label"] == "FG%")
    assert fg_cat["rows"][0]["name"] == "Team B"
    assert fg_cat["rows"][0]["rank"] == 1
    assert fg_cat["rows"][0]["value"] == "50.10%"
    assert fg_cat["rows"][1]["name"] == "Team A"
    assert fg_cat["rows"][1]["rank"] == 2
    assert fg_cat["rows"][1]["value"] == "45.60%"
    
    ft_cat = next(cat for cat in result if cat["label"] == "FT%")
    assert ft_cat["rows"][1]["name"] == "Team A"
    assert ft_cat["rows"][1]["rank"] == 2
    assert ft_cat["rows"][1]["value"] == "0.00%"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_visualizer_processor.py -v`
Expected: FAIL (`rank` KeyError, and `value` is float not percentage string)

- [ ] **Step 3: Update `processor.py`**

```python
# In src/visualizer/processor.py (replace the result logic in process_stats_for_visual)
    result = []
    for cat in categories:
        def sort_key_func(team):
            val = team["stats"].get(cat["sort_key"], 0)
            try:
                return float(val)
            except (ValueError, TypeError):
                return 0

        sorted_teams = sorted(team_stats, key=sort_key_func, reverse=cat["reverse"])
        
        rows = []
        for index, t in enumerate(sorted_teams):
            raw_val = t["stats"].get(cat["data_key"], "-")
            
            display_val = raw_val
            if cat["label"] in ("FG%", "FT%"):
                try:
                    num_val = float(raw_val)
                    if num_val == 0:
                        display_val = "0.00%"
                    else:
                        display_val = f"{num_val * 100:.2f}%"
                except (ValueError, TypeError):
                    display_val = "0.00%"
                    
            rows.append({
                "rank": index + 1,
                "name": t["name"],
                "value": display_val
            })
        result.append({"label": cat["label"], "rows": rows})
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_visualizer_processor.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/visualizer/processor.py tests/test_visualizer_processor.py
git commit -m "feat: add rank to rows and format percentages in processor"
```

### Task 4: Update HTML Template for Rank Column

**Files:**
- Modify: `src/visualizer/templates/stats_table.html`
- Modify: `tests/test_visualizer_renderer.py`

- [ ] **Step 1: Write test for rank rendering**

```python
# In tests/test_visualizer_renderer.py
from src.visualizer.renderer import render_stats_html

def test_render_html_with_rank():
    data = [{"label": "PTS", "rows": [{"rank": 1, "name": "Team A", "value": 100}]}]
    html = render_stats_html(data, [])
    
    assert '<td class="rank-cell">1</td>' in html
    assert '<td colspan="3" class="header-cell">PTS</td>' in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_visualizer_renderer.py -v`
Expected: FAIL

- [ ] **Step 3: Update `stats_table.html`**

```html
<!-- In src/visualizer/templates/stats_table.html -->
<!-- Modify CSS width for category-table -->
    .category-table {
        border-collapse: collapse;
        border: 2px solid #000;
        text-align: center;
        box-sizing: border-box;
        margin-left: -2px; /* Perfect overlap for 2px borders */
        table-layout: fixed;
        width: 155px; /* Increased from 130px to accommodate rank */
    }
<!-- Add css class for rank-cell -->
    .category-table td.rank-cell {
        width: 25px;
    }
<!-- Modify header colspan -->
                    <tr class="header-row">
                        <td colspan="3" class="header-cell">{{ cat.label }}</td>
                    </tr>
<!-- Modify table rows for daily -->
                    {% for row in cat.rows %}
                        <tr>
                            <td class="rank-cell">{{ row.rank }}</td>
                            <td class="name-cell">{{ row.name }}</td>
                            <td class="value-cell">{{ row.value }}</td>
                        </tr>
                    {% endfor %}
<!-- Also modify header colspan and rows for weekly in the same way down below in the template -->
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_visualizer_renderer.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/visualizer/templates/stats_table.html tests/test_visualizer_renderer.py
git commit -m "style: add rank column to stats_table template"
```

### Task 5: Implement Season Sub-directories in `main.py`

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update `main.py`**

Modify `main.py` to read `SEASON` and nest directories appropriately.

```python
# Find and replace in main.py:
# Around line 40:
        season = config.get("SEASON", "default")
        
        # 2. Season Stats
        logging.info("Fetching season stats...")
        season_stats = fetcher.fetch_team_stats(league_id)
        season_path = storage.save(season_stats, f"{league_id}_season_stats", sub_dir=season, overwrite=True)
        logging.info(f"Successfully saved season stats to {season_path}")
        
        # 3. Weekly Stats
        # Test override:
        test_week = os.getenv("TEST_WEEK")
        current_week = int(test_week) if test_week else get_fantasy_week(config["SEASON_START_DATE"])
        
        logging.info(f"Fetching weekly stats for Week {current_week}...")
        weekly_stats = fetcher.fetch_weekly_stats(league_id, current_week)
        weekly_path = storage.save(weekly_stats, f"week_{current_week}", sub_dir=os.path.join(season, "weekly"), overwrite=True)
        logging.info(f"Successfully saved weekly stats to {weekly_path}")
        
        # 4. Daily Stats
        # Test override:
        test_date = os.getenv("TEST_DATE")
        today_str = test_date if test_date else get_pacific_date()
        
        logging.info(f"Fetching daily stats for {today_str}...")
        daily_stats = fetcher.fetch_daily_stats(league_id, today_str)
        daily_path = storage.save(daily_stats, today_str, sub_dir=os.path.join(season, "daily"), overwrite=True)
        logging.info(f"Successfully saved daily stats to {daily_path}")
        
        # 5. Visualization
        logging.info("Generating visualization images...")
        try:
            daily_processed = process_stats_for_visual(daily_stats)
            weekly_processed = process_stats_for_visual(weekly_stats)
            
            image_dir = os.path.join("data", season, "images")
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: organize data storage by season directory"
```
