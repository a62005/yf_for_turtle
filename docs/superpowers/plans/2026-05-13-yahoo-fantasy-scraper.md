# Yahoo Fantasy NBA Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python application to fetch Yahoo Fantasy NBA league data (teams and player stats) using the `yahoofantasy` package and save it locally as JSON.

**Architecture:** A modular Python script separated into `config`, `fetcher` (Yahoo API via wrapper), and `storage` (JSON output, extensible to DB), coordinated by `main.py`.

**Tech Stack:** Python 3, `yahoofantasy`, `pytest`, `python-dotenv`

---

### Task 1: Project Setup and AI Instructions

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `GEMINI.md`

- [ ] **Step 1: Create requirements.txt**

```text
yahoofantasy
python-dotenv
pytest
pytest-mock
```

- [ ] **Step 2: Create .gitignore**

```text
# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Data and Secrets
data/
oauth2.json
*.sqlite3

# Testing
.pytest_cache/
```

- [ ] **Step 3: Create .env.example**

```text
# Yahoo Fantasy API Configuration
# These are required if you want to use consumer key/secret, though yahoofantasy uses oauth2.json.
# LEAGUE_ID is strictly needed. Example: nba.l.12345
LEAGUE_ID=your_league_id_here
```

- [ ] **Step 4: Create GEMINI.md**

```markdown
# Yahoo Fantasy NBA Scraper AI Instructions

## Context
This project is a Python scraper for Yahoo Fantasy NBA data. It uses the `yahoofantasy` package to handle OAuth2 and API interactions.

## Architecture Rules
1. **Separation of Concerns**: `fetcher.py` handles API calls, `storage.py` handles saving data, `config.py` handles environment variables.
2. **Data Format**: Currently outputs to JSON in the `data/` directory. If changing to a database, implement a new class in `storage.py` conforming to a common interface.
3. **Authentication**: Handled via `oauth2.json` which must NOT be committed.
4. **Testing**: Use `pytest`. Run tests before committing.

## Setup Instructions
1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in `LEAGUE_ID`.
3. First run will require browser-based OAuth authorization to generate `oauth2.json`.
```

- [ ] **Step 5: Commit Setup**

```bash
git add requirements.txt .gitignore .env.example GEMINI.md
git commit -m "chore: initial project setup and AI instructions"
```

---

### Task 2: Config Module

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
import os
import pytest
from src.config import load_config

def test_load_config_missing_league_id(monkeypatch):
    monkeypatch.delenv("LEAGUE_ID", raising=False)
    with pytest.raises(ValueError, match="LEAGUE_ID is not set"):
        load_config()

def test_load_config_success(monkeypatch):
    monkeypatch.setenv("LEAGUE_ID", "nba.l.12345")
    config = load_config()
    assert config["LEAGUE_ID"] == "nba.l.12345"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL with ModuleNotFoundError for 'src.config'

- [ ] **Step 3: Write minimal implementation**

```python
# src/config.py
import os
from dotenv import load_dotenv

def load_config() -> dict:
    load_dotenv()
    league_id = os.getenv("LEAGUE_ID")
    if not league_id:
        raise ValueError("LEAGUE_ID is not set in environment or .env file.")
    
    return {
        "LEAGUE_ID": league_id
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_config.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: add config module"
```

---

### Task 3: Storage Module

**Files:**
- Create: `src/storage.py`
- Create: `tests/test_storage.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_storage.py
import os
import json
import pytest
from src.storage import JsonStorage

def test_json_storage_saves_data(tmp_path):
    # tmp_path is a pytest fixture providing a temporary directory unique to the test invocation
    data_dir = tmp_path / "data"
    storage = JsonStorage(data_dir=str(data_dir))
    
    test_data = {"teams": [{"name": "Team A"}]}
    filename = storage.save(test_data, "test_league")
    
    assert os.path.exists(filename)
    with open(filename, "r", encoding="utf-8") as f:
        saved_data = json.load(f)
    assert saved_data == test_data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_storage.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError for JsonStorage

- [ ] **Step 3: Write minimal implementation**

```python
# src/storage.py
import os
import json
from datetime import datetime
from abc import ABC, abstractmethod

class BaseStorage(ABC):
    @abstractmethod
    def save(self, data: dict, identifier: str) -> str:
        pass

class JsonStorage(BaseStorage):
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        if not os.path.exists(self.data_dir):
            os.makedirs(self.data_dir)

    def save(self, data: dict, identifier: str) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{timestamp}_{identifier}.json"
        filepath = os.path.join(self.data_dir, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
            
        return filepath
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_storage.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/storage.py tests/test_storage.py
git commit -m "feat: add json storage module"
```

---

### Task 4: Fetcher Module

**Files:**
- Create: `src/fetcher.py`
- Create: `tests/test_fetcher.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fetcher.py
import pytest
from src.fetcher import YahooFantasyFetcher

class MockPlayer:
    def __init__(self, name):
        self.name = name

class MockTeam:
    def __init__(self, name):
        self.name = name
    
    def roster(self):
        return [MockPlayer("Player 1"), MockPlayer("Player 2")]

class MockLeague:
    def teams(self):
        return [MockTeam("Team A")]

def test_fetch_league_data(mocker):
    # Mock yahoofantasy Context
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context")
    mock_ctx.return_value.get_league.return_value = MockLeague()
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_league_data("mock_league_id")
    
    assert "teams" in data
    assert len(data["teams"]) == 1
    assert data["teams"][0]["name"] == "Team A"
    assert len(data["teams"][0]["roster"]) == 2
    assert data["teams"][0]["roster"][0]["name"] == "Player 1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fetcher.py -v`
Expected: FAIL with ModuleNotFoundError or ImportError

- [ ] **Step 3: Write minimal implementation**

```python
# src/fetcher.py
import yahoofantasy

class YahooFantasyFetcher:
    def __init__(self):
        self.ctx = yahoofantasy.Context()
        
    def fetch_league_data(self, league_id: str) -> dict:
        league = self.ctx.get_league(league_id)
        teams_data = []
        
        for team in league.teams():
            team_info = {
                "name": getattr(team, "name", "Unknown"),
                "roster": []
            }
            
            for player in team.roster():
                player_info = {
                    "name": getattr(player, "name", "Unknown")
                }
                # To extend in the future: fetch stats for each player
                team_info["roster"].append(player_info)
                
            teams_data.append(team_info)
            
        return {"teams": teams_data}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fetcher.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fetcher.py tests/test_fetcher.py
git commit -m "feat: add yahoo fantasy fetcher module"
```

---

### Task 5: Main Entrypoint

**Files:**
- Create: `main.py`

- [ ] **Step 1: Write main implementation**
(Since this is the orchestration layer, we will write it and test via an integration run or a simple test)

```python
# main.py
import logging
from src.config import load_config
from src.fetcher import YahooFantasyFetcher
from src.storage import JsonStorage

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    logging.info("Starting Yahoo Fantasy Scraper...")
    
    try:
        config = load_config()
        league_id = config["LEAGUE_ID"]
        logging.info(f"Loaded config for League ID: {league_id}")
        
        fetcher = YahooFantasyFetcher()
        logging.info("Fetching data from Yahoo API...")
        data = fetcher.fetch_league_data(league_id)
        
        storage = JsonStorage()
        filepath = storage.save(data, league_id)
        logging.info(f"Successfully saved data to {filepath}")
        
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit**

```bash
git add main.py
git commit -m "feat: add main entrypoint"
```
