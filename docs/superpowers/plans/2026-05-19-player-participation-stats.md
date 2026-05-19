# Player Participation Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "Today Player" count to daily stats and "Game Player" (Played/Total) ratio to weekly stats, appearing as the leftmost columns in the visualization.

**Architecture:** Use modular extension of the `YahooFantasyFetcher` to perform batch API requests, update the `Processor` to handle new sorting logic, and modify the Jinja2 template for specific styling.

**Tech Stack:** Python, yahoofantasy (Yahoo API), Jinja2, Playwright.

---

### Task 1: Extend Fetcher for Batch Data

**Files:**
- Modify: `src/fetcher.py`

- [ ] **Step 1: Add `fetch_batch_rosters` method**
Implement a method that calls `teams/roster;date={date}` and counts non-bench players for all teams.
```python
    def fetch_batch_rosters(self, league_id: str, date_str: str) -> dict:
        if not league_id.startswith('nba.l.'): league_id = f"nba.l.{league_id}"
        url = f"teams/roster;date={date_str}"
        data = self.ctx.make_request(url, league=league_id)
        # Parse XML to count active players
        roster_counts = {}
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(data)
            ns = {'ns': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}
            for team in root.findall('.//ns:team', ns):
                team_id = team.find('ns:team_id', ns).text
                active_count = 0
                for player in team.findall('.//ns:player', ns):
                    pos = player.find('.//ns:selected_position/ns:position', ns).text
                    if pos not in ['BN', 'IL', 'IL+', 'NA']:
                        active_count += 1
                roster_counts[team_id] = active_count
        except Exception as e:
            print(f"Error parsing rosters: {e}")
        return roster_counts
```

- [ ] **Step 2: Add `fetch_league_scoreboard` method**
Implement a method to get game counts from the scoreboard.
```python
    def fetch_league_scoreboard(self, league_id: str, week: int) -> dict:
        if not league_id.startswith('nba.l.'): league_id = f"nba.l.{league_id}"
        url = f"league/{league_id}/scoreboard;week={week}"
        data = self.ctx.make_request(url)
        game_counts = {}
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(data)
            ns = {'ns': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}
            for team in root.findall('.//ns:team', ns):
                team_id = team.find('ns:team_id', ns).text
                rem_games = team.find('.//ns:team_remaining_games/ns:total', ns)
                completed = int(rem_games.find('ns:completed_games', ns).text or 0)
                live = int(rem_games.find('ns:live_games', ns).text or 0)
                remaining = int(rem_games.find('ns:remaining_games', ns).text or 0)
                played = completed + live
                total = played + remaining
                game_counts[team_id] = {"played": played, "total": total}
        except Exception as e:
            print(f"Error parsing scoreboard: {e}")
        return game_counts
```

- [ ] **Step 3: Commit Fetcher changes**
```bash
git add src/fetcher.py
git commit -m "feat: add batch roster and scoreboard fetching to YahooFantasyFetcher"
```

---

### Task 2: Upgrade Processor for New Metrics

**Files:**
- Modify: `src/visualizer/processor.py`

- [ ] **Step 1: Implement composite sorting logic**
Update `process_stats_for_visual` to handle `Today Player` and `Game Player` with specific sorting rules.
```python
    # Inside categories list in process_stats_for_visual
    new_categories = []
    
    # Check if we have Game Player data
    if any("Game Player" in t["stats"] for t in team_stats):
        new_categories.append({"label": "Game Player", "data_key": "Game Player", "sort_key": "GP_SORT", "reverse": True})
    
    # Check if we have Today Player data
    if any("Today Player" in t["stats"] for t in team_stats):
        new_categories.append({"label": "Today Player", "data_key": "Today Player", "sort_key": "Today Player", "reverse": True})

    categories = new_categories + [
        {"label": "FG", "data_key": "FGM/FGA", "sort_key": "FG%", "reverse": True},
        # ... rest of categories
    ]
```

- [ ] **Step 2: Add composite sort key calculation**
Before sorting, add a helper key for `Game Player`.
```python
    for t in team_stats:
        if "GP_PLAYED" in t["stats"]:
            # Composite key: Played * 1000 + Total (to prioritize Played then Total)
            t["stats"]["GP_SORT"] = (t["stats"]["GP_PLAYED"] * 1000) + t["stats"]["GP_TOTAL"]
```

- [ ] **Step 3: Commit Processor changes**
```bash
git add src/visualizer/processor.py
git commit -m "feat: implement sorting and processing for participation metrics"
```

---

### Task 3: Update Template Styling

**Files:**
- Modify: `src/visualizer/templates/stats_table.html`

- [ ] **Step 1: Add CSS for status columns**
Add `.status-cell` class and update the table rendering to use it.
```html
    /* Inside <style> */
    .category-table td.status-cell {
        background-color: #e6f3ff; /* Light blue */
    }
```

- [ ] **Step 2: Update table row rendering**
Modify the Jinja2 loops to apply the class if the label matches.
```html
    <td class="value-cell {% if cat.label in ['Today Player', 'Game Player'] %}status-cell{% endif %}">{{ row.value }}</td>
```

- [ ] **Step 3: Commit Template changes**
```bash
git add src/visualizer/templates/stats_table.html
git commit -m "feat: add light blue styling for participation columns"
```

---

### Task 4: Integrate in Main Execution

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Update fetch and merge logic**
Call the new fetcher methods and merge data into the stats dictionaries before saving/processing.
```python
        # Daily Stats
        daily_stats = fetcher.fetch_daily_stats(league_id, today_str)
        roster_counts = fetcher.fetch_batch_rosters(league_id, today_str)
        # Merge Today Player into daily_stats
        # Need to map team_id correctly - might need a helper in fetcher
```

- [ ] **Step 2: Run verification**
Execute `python3 main.py` and verify `data/images/` contains the new columns.

- [ ] **Step 3: Commit Main changes**
```bash
git add main.py
git commit -m "feat: integrate player participation stats into main flow"
```
