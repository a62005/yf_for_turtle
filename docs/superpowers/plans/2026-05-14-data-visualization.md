# Data Visualization and Image Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create a data visualization module that converts Yahoo Fantasy NBA stats into grid-style PNG images for LINE Bot integration.

**Architecture:** 
1. **Data Processing**: Sort and group stats into 11 categories.
2. **HTML Rendering**: Generate a styled grid using Jinja2 templates.
3. **Image Capture**: Render HTML to PNG using Playwright.
4. **Integration**: Hook into `main.py`.

**Tech Stack:** Python 3, `Jinja2`, `Playwright`, `pytest`

---

### Task 1: Data Processor Logic

**Files:**
- Create: `src/visualizer/processor.py`
- Create: `tests/test_visualizer_processor.py`

- [ ] **Step 1: Write test for stat sorting and grouping**

```python
from src.visualizer.processor import process_stats_for_visual

def test_process_stats_sorting():
    raw_data = {
        "team_stats": [
            {"name": "Team A", "stats": {"PTS": 100, "FG%": 0.45, "FGM/FGA": "45/100"}},
            {"name": "Team B", "stats": {"PTS": 200, "FG%": 0.55, "FGM/FGA": "55/100"}}
        ]
    }
    processed = process_stats_for_visual(raw_data)
    # Check PTS sorting (descending)
    pts_column = next(c for c in processed if c['label'] == 'PTS')
    assert pts_column['rows'][0]['name'] == 'Team B'
```

- [ ] **Step 2: Implement sorting and grouping in `processor.py`**

```python
def process_stats_for_visual(data: dict) -> list:
    team_stats = data.get("team_stats", [])
    categories = [
        {"label": "FG", "sort_by": "FG%", "reverse": True},
        {"label": "FG%", "sort_by": "FG%", "reverse": True},
        {"label": "FT", "sort_by": "FT%", "reverse": True},
        {"label": "FT%", "sort_by": "FT%", "reverse": True},
        {"label": "3PTM", "sort_by": "3PTM", "reverse": True},
        {"label": "PTS", "sort_by": "PTS", "reverse": True},
        {"label": "REB", "sort_by": "REB", "reverse": True},
        {"label": "AST", "sort_by": "AST", "reverse": True},
        {"label": "ST", "sort_by": "ST", "reverse": True},
        {"label": "BLK", "sort_by": "BLK", "reverse": True},
        {"label": "TO", "sort_by": "TO", "reverse": False},
    ]
    
    result = []
    for cat in categories:
        # Sort teams by the specific logic
        sorted_teams = sorted(
            team_stats, 
            key=lambda x: x["stats"].get(cat["sort_by"], 0) if isinstance(x["stats"].get(cat["sort_by"]), (int, float)) else 0,
            reverse=cat["reverse"]
        )
        rows = []
        for t in sorted_teams:
            val = t["stats"].get(cat["label"], t["stats"].get(cat["sort_by"], "-"))
            rows.append({"name": t["name"], "value": val})
        result.append({"label": cat["label"], "rows": rows})
    return result
```

- [ ] **Step 3: Commit**

```bash
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git add src/visualizer/processor.py tests/test_visualizer_processor.py
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git commit -m "feat: implement data processor for visualization"
```

---

### Task 2: HTML Template and Renderer

**Files:**
- Create: `src/visualizer/templates/stats_table.html`
- Create: `src/visualizer/renderer.py`

- [ ] **Step 1: Create Jinja2 Template**

Create `src/visualizer/templates/stats_table.html` with:
- Horizontal tight alignment of all 11 stat categories.
- Zero gap grid using `border-collapse: collapse` and `margin-left: -1px`.
- Black centered text, 13px mono-spaced font.
- Merged headers for category labels.
- Simple double horizontal line separator for combined mode (no text labels).

- [ ] **Step 2: Implement Renderer**

```python
from jinja2 import Environment, FileSystemLoader
import os

def render_stats_html(daily_processed: list, weekly_processed: list = None) -> str:
    env = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(__file__), 'templates')))
    template = env.get_template('stats_table.html')
    return template.render(daily=daily_processed, weekly=weekly_processed)
```

- [ ] **Step 3: Commit**

```bash
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git add src/visualizer/renderer.py src/visualizer/templates/stats_table.html
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git commit -m "feat: add HTML template and renderer for stats grid"
```

---

### Task 3: Image Capture with Playwright

**Files:**
- Create: `src/visualizer/capturer.py`
- Modify: `requirements.txt`

- [ ] **Step 1: Add Playwright to requirements**

```text
playwright
jinja2
```

- [ ] **Step 2: Implement Capturer**

```python
from playwright.sync_api import sync_playwright
import os

def capture_html_to_png(html_content: str, output_path: str):
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content)
        # Select the main container and screenshot it
        element = page.query_selector(".stats-container")
        element.screenshot(path=output_path)
        browser.close()
```

- [ ] **Step 3: Commit**

```bash
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git add src/visualizer/capturer.py requirements.txt
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git commit -m "feat: implement image capture using playwright"
```

---

### Task 4: Integration in `main.py`

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Orchestrate visualization after data fetching**

Update `main.py` to:
1. Process the fetched JSON data.
2. Render HTML.
3. Capture images (Both combined and separate).
4. Save to `data/images/`.

- [ ] **Step 2: Commit**

```bash
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git add main.py
GIT_AUTHOR_NAME="AI Bot" GIT_AUTHOR_EMAIL="bot@example.com" GIT_COMMITTER_NAME="AI Bot" GIT_COMMITTER_EMAIL="bot@example.com" git commit -m "feat: integrate data visualization into main execution flow"
```
