# Player Participation Stats Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add "Today Player" count to daily stats and "Game Player" (Played/Total) ratio to weekly stats, appearing as the leftmost columns in the visualization.

**Architecture:** 
1.  **Fetcher**: Add batch API methods for Roster and Scoreboard.
2.  **Processor**: Insert new categories at the start of the list and implement multi-level sorting.
3.  **Renderer**: Update CSS for distinctive styling and Jinja2 logic for conditional classes.
4.  **Main**: Coordinate data fetching and merging.

**Tech Stack:** Python, yahoofantasy, Jinja2, Playwright.

---

### Task 1: Fetcher Batch Methods

**Files:**
- Modify: `src/fetcher.py`

- [ ] **Step 1: Add `fetch_batch_rosters` method**
Add a method to fetch all rosters for a given date in one call.
```python
    def fetch_batch_rosters(self, league_id: str, date_str: str) -> dict:
        """Fetch non-bench player counts for all teams in the league for a specific date."""
        if not league_id.startswith('nba.l.'): league_id = f"nba.l.{league_id}"
        # Fetching rosters for all teams via batch request
        url = f"teams/roster;date={date_str}"
        data = self.ctx.make_request(url, league=league_id)
        
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
                    # Non-starting positions to exclude
                    if pos not in ['BN', 'IL', 'IL+', 'NA']:
                        active_count += 1
                roster_counts[team_id] = active_count
        except Exception as e:
            import logging
            logging.error(f"Error parsing batch rosters: {e}")
        return roster_counts
```

- [ ] **Step 2: Add `fetch_league_scoreboard` method**
Add a method to fetch scoreboard data for game counts.
```python
    def fetch_league_scoreboard(self, league_id: str, week: int) -> dict:
        """Fetch played and total game counts for all teams from the scoreboard."""
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
                rem_games_node = team.find('.//ns:team_remaining_games/ns:total', ns)
                if rem_games_node is not None:
                    completed = int(rem_games_node.find('ns:completed_games', ns).text or 0)
                    live = int(rem_games_node.find('ns:live_games', ns).text or 0)
                    remaining = int(rem_games_node.find('ns:remaining_games', ns).text or 0)
                    played = completed + live
                    total = played + remaining
                    game_counts[team_id] = {"played": played, "total": total}
        except Exception as e:
            import logging
            logging.error(f"Error parsing scoreboard games: {e}")
        return game_counts
```

- [ ] **Step 3: Commit Fetcher changes**
```bash
git add src/fetcher.py
git commit -m "feat: add batch roster and scoreboard game fetching"
```

---

### Task 2: Advanced Processing & Sorting

**Files:**
- Modify: `src/visualizer/processor.py`

- [ ] **Step 1: Implement `process_stats_for_visual` with new metrics**
Update the function to include `Today Player` and `Game Player` with specific sorting logic.
```python
def process_stats_for_visual(data: dict) -> list:
    team_stats = data.get("team_stats", [])
    if not team_stats:
        return []

    # Prepare categories list
    categories = []
    
    # Check for Game Player data
    if any("GP_PLAYED" in t["stats"] for t in team_stats):
        # Add composite sort key: Played * 1000 + Total
        for t in team_stats:
            played = t["stats"].get("GP_PLAYED", 0)
            total = t["stats"].get("GP_TOTAL", 0)
            t["stats"]["GP_SORT_KEY"] = (played * 1000) + total
            t["stats"]["Game Player"] = f"{played} / {total}"
        
        categories.append({"label": "Game Player", "data_key": "Game Player", "sort_key": "GP_SORT_KEY", "reverse": True})

    # Check for Today Player data
    if any("Today Player" in t["stats"] for t in team_stats):
        categories.append({"label": "Today Player", "data_key": "Today Player", "sort_key": "Today Player", "reverse": True})

    # Standard categories
    categories += [
        {"label": "FG", "data_key": "FGM/FGA", "sort_key": "FG%", "reverse": True},
        {"label": "FG%", "data_key": "FG%", "sort_key": "FG%", "reverse": True},
        {"label": "FT", "data_key": "FTM/FTA", "sort_key": "FT%", "reverse": True},
        {"label": "FT%", "data_key": "FT%", "sort_key": "FT%", "reverse": True},
        {"label": "3PT", "data_key": "3PTM", "sort_key": "3PTM", "reverse": True},
        {"label": "PTS", "data_key": "PTS", "sort_key": "PTS", "reverse": True},
        {"label": "REB", "data_key": "REB", "sort_key": "REB", "reverse": True},
        {"label": "AST", "data_key": "AST", "sort_key": "AST", "reverse": True},
        {"label": "ST", "data_key": "ST", "sort_key": "ST", "reverse": True},
        {"label": "BLK", "data_key": "BLK", "sort_key": "BLK", "reverse": True},
        {"label": "TO", "data_key": "TO", "sort_key": "TO", "reverse": False},
    ]

    result = []
    for cat in categories:
        def sort_key_func(team):
            val = team["stats"].get(cat["sort_key"], 0)
            if isinstance(val, (int, float)):
                return val
            # Handle percentage strings if necessary
            try: return float(str(val).strip('%'))
            except: return 0

        sorted_teams = sorted(team_stats, key=sort_key_func, reverse=cat["reverse"])
        
        rows = []
        for t in sorted_teams:
            rows.append({
                "name": t["name"],
                "value": t["stats"].get(cat["data_key"], "-")
            })
        result.append({"label": cat["label"], "rows": rows})
    return result
```

- [ ] **Step 2: Commit Processor changes**
```bash
git add src/visualizer/processor.py
git commit -m "feat: implement participation metrics processing and sorting"
```

---

### Task 3: Visualization Enhancement

**Files:**
- Modify: `src/visualizer/templates/stats_table.html`

- [ ] **Step 1: Add distinctive CSS classes**
Add `.status-cell` for the new columns.
```html
<style>
    /* ... existing styles ... */
    .category-table td.status-cell {
        background-color: #e6f3ff; /* Light blue for participation stats */
        font-weight: bold;
    }
</style>
```

- [ ] **Step 2: Update Jinja2 loop for value cells**
Apply the `status-cell` class conditionally based on the category label.
```html
<!-- Inside daily loop -->
<td class="value-cell {% if cat.label == 'Today Player' %}status-cell{% endif %}">{{ row.value }}</td>

<!-- Inside weekly loop -->
<td class="value-cell {% if cat.label == 'Game Player' %}status-cell{% endif %}">{{ row.value }}</td>
```

- [ ] **Step 3: Commit Template changes**
```bash
git add src/visualizer/templates/stats_table.html
git commit -m "feat: add light blue styling for status columns"
```

---

### Task 4: Main Logic Integration

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Add helper for team ID mapping**
Update `YahooFantasyFetcher` to provide a way to find team names by ID during merging.
```python
# In src/fetcher.py
    def get_team_name(self, team_id: str, default_name: str = "Unknown") -> str:
        return self.team_mapping.get(str(team_id), default_name)
```

- [ ] **Step 2: Update Weekly Stats fetching in main.py**
```python
        # 3. Weekly Stats
        logging.info(f"Fetching weekly stats for Week {current_week}...")
        weekly_stats = fetcher.fetch_weekly_stats(league_id, current_week)
        game_counts = fetcher.fetch_league_scoreboard(league_id, current_week)
        
        # Merge Game Player data
        for t in weekly_stats.get("team_stats", []):
            # We need team_id to match. fetcher._parse_teams_from_content should be updated 
            # to include team_id in the stats dict temporarily or keep it in the list
```

- [ ] **Step 3: Update `fetcher.py` to preserve team_id**
Modify `_parse_teams_from_content` to include `team_id` in the returned list.
```python
    # In src/fetcher.py -> _parse_teams_from_content
    # ...
    team_stats_data.append({
        "team_id": team_id, # ADD THIS LINE
        "name": team_name,
        "stats": self._parse_stats(t)
    })
```

- [ ] **Step 4: Complete Main integration**
Finalize the merge logic in `main.py`.
```python
        # 4. Daily Stats
        today_str = test_date if test_date else get_pacific_date()
        logging.info(f"Fetching daily stats for {today_str}...")
        daily_stats = fetcher.fetch_daily_stats(league_id, today_str)
        roster_counts = fetcher.fetch_batch_rosters(league_id, today_str)
        
        for t in daily_stats.get("team_stats", []):
            tid = t.get("team_id")
            if tid in roster_counts:
                t["stats"]["Today Player"] = roster_counts[tid]
        
        # Similar for weekly...
```

- [ ] **Step 5: Final Execution & Verification**
Run: `TEST_DATE=2026-04-05 TEST_WEEK=23 python3 main.py`
Verify: `data/images/2026-04-05_combined.png` has the new columns with blue backgrounds.

- [ ] **Step 6: Commit Main changes**
```bash
git add main.py src/fetcher.py
git commit -m "feat: integrate participation data merge logic in main flow"
```
