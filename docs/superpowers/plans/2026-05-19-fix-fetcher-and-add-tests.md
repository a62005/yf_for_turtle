# Fix Fetcher Refactor and Add Tests Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `YahooFantasyFetcher` to normalize league IDs, reduce XML parsing duplication, and add unit tests for `fetch_batch_rosters` and `fetch_league_scoreboard`.

**Architecture:**
1. Add `_normalize_league_id` helper in `YahooFantasyFetcher`.
2. Extract common XML namespace and parsing logic.
3. Add pytest unit tests with mocking for the new fetcher methods.

**Tech Stack:** Python, pytest, pytest-mock, xml.etree.ElementTree

---

### Task 1: Refactor League ID Normalization

**Files:**
- Modify: `src/fetcher.py`

- [ ] **Step 1: Add `_normalize_league_id` method**
```python
    def _normalize_league_id(self, league_id: str) -> str:
        if league_id and not league_id.startswith('nba.l.'):
            return f"nba.l.{league_id}"
        return league_id
```

- [ ] **Step 2: Use `_normalize_league_id` in all relevant methods**
Update `fetch_league_data`, `fetch_team_stats`, `fetch_weekly_stats`, `fetch_daily_stats`, `fetch_batch_rosters`, and `fetch_league_scoreboard`.

- [ ] **Step 3: Commit**
```bash
git add src/fetcher.py
git commit -m "refactor: use _normalize_league_id helper in YahooFantasyFetcher"
```

### Task 2: Refactor XML Parsing Logic

**Files:**
- Modify: `src/fetcher.py`

- [ ] **Step 1: Extract namespace and common XML parsing logic**
Add a constant for the namespace and potentially a helper for finding nodes with namespace.

```python
YAHOO_NS = {'ns': 'http://fantasysports.yahooapis.com/fantasy/v2/base.rng'}

# ... in YahooFantasyFetcher class ...
    def _find_node(self, parent, path):
        return parent.find(path, YAHOO_NS)

    def _find_all_nodes(self, parent, path):
        return parent.findall(path, YAHOO_NS)
```

- [ ] **Step 2: Update `fetch_batch_rosters` and `fetch_league_scoreboard` to use helpers**
Clean up the redundant namespace dictionaries.

- [ ] **Step 3: Commit**
```bash
git add src/fetcher.py
git commit -m "refactor: abstract XML namespace handling in YahooFantasyFetcher"
```

### Task 3: Add Unit Tests for `fetch_batch_rosters`

**Files:**
- Modify: `tests/test_fetcher.py`

- [ ] **Step 1: Write the failing test (Red)**
Add `test_fetch_batch_rosters` with mocked XML response.

```python
def test_fetch_batch_rosters(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    xml_response = """
    <fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league>
        <teams>
          <team>
            <team_id>1</team_id>
            <roster>
              <players>
                <player>
                  <selected_position><position>PG</position></selected_position>
                </player>
                <player>
                  <selected_position><position>BN</position></selected_position>
                </player>
              </players>
            </roster>
          </team>
        </teams>
      </league>
    </fantasy_content>
    """
    mock_ctx.make_request.return_value = xml_response
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_batch_rosters("12345", "2023-11-01")
    
    assert data == {"1": 1}
```

- [ ] **Step 2: Run test to verify it fails**
Run: `pytest tests/test_fetcher.py::test_fetch_batch_rosters -v`
It should fail if logic is broken or if I haven't implemented refactor correctly. Actually, since I'm refactoring *after* implementation (which was done in a previous turn but without tests), I'll verify it passes with the current implementation.

- [ ] **Step 3: Ensure it passes (Green)**
Since the code is already there, I'm effectively adding regression tests.

- [ ] **Step 4: Commit**
```bash
git add tests/test_fetcher.py
git commit -m "test: add unit test for fetch_batch_rosters"
```

### Task 4: Add Unit Tests for `fetch_league_scoreboard`

**Files:**
- Modify: `tests/test_fetcher.py`

- [ ] **Step 1: Write the failing test (Red)**
Add `test_fetch_league_scoreboard` with mocked XML response.

```python
def test_fetch_league_scoreboard(mocker):
    mock_ctx = mocker.patch("src.fetcher.yahoofantasy.Context").return_value
    xml_response = """
    <fantasy_content xmlns="http://fantasysports.yahooapis.com/fantasy/v2/base.rng">
      <league>
        <scoreboard>
          <matchups>
            <matchup>
              <teams>
                <team>
                  <team_id>1</team_id>
                  <team_remaining_games>
                    <total>
                      <completed_games>10</completed_games>
                      <live_games>1</live_games>
                      <remaining_games>5</remaining_games>
                    </total>
                  </team_remaining_games>
                </team>
              </teams>
            </matchup>
          </matchups>
        </scoreboard>
      </league>
    </fantasy_content>
    """
    mock_ctx.make_request.return_value = xml_response
    
    fetcher = YahooFantasyFetcher()
    data = fetcher.fetch_league_scoreboard("12345", 1)
    
    assert data == {"1": {"played": 11, "total": 16}}
```

- [ ] **Step 2: Run test to verify it passes**
Run: `pytest tests/test_fetcher.py::test_fetch_league_scoreboard -v`

- [ ] **Step 3: Commit**
```bash
git add tests/test_fetcher.py
git commit -m "test: add unit test for fetch_league_scoreboard"
```

### Task 5: Final Verification

- [ ] **Step 1: Run all tests**
Run: `pytest tests/test_fetcher.py`
Expected: All tests pass.

- [ ] **Step 2: Final Commit (if needed)**
Check for any remaining linting issues.
