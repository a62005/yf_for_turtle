# Custom Team Names and Team Stats Design

## 1. Overview
This design outlines two new features for the Yahoo Fantasy NBA Scraper:
1. **Custom Team Names**: Allows the user to override dynamic team names from the Yahoo Fantasy API with static, custom team names locally.
2. **Team Stats API**: Fetches team-level statistics (e.g., PTS, REB) and saves them in an independent JSON output.

## 2. Architecture & Components

### 2.1 Custom Team Names (team_mapping.json)
*   **Data Structure**: A JSON dictionary stored at the project root (`team_mapping.json`).
*   **Format**: Keys are the static Yahoo `team_id` (string), and values are the custom names (string).
    *   *Example*: `{"1": "A01", "2": "B01"}`
*   **Integration**:
    *   In `src/fetcher.py`, `YahooFantasyFetcher` will attempt to load `team_mapping.json` upon initialization.
    *   When processing teams in `fetch_league_data` and the new `fetch_team_stats`, the fetcher will check if `str(team.team_id)` exists in the mapping.
    *   If a match is found, the custom name is used. If not, it falls back to the API-provided `team.name`.

### 2.2 Team Stats API
*   **New Method**: Add `fetch_team_stats(league_id: str) -> dict` in `src/fetcher.py`.
*   **Data Flow**:
    *   The method instantiates the league and iterates through `league.teams()`.
    *   For each team, it accesses `team.team_standings` or `team.stats` (depending on the `yahoofantasy` library capabilities) to extract available stats.
    *   Applies the custom team name logic.
    *   Returns a dictionary: `{"team_stats": [{"name": "Custom Name", "stats": {...}}, ...]}`.
*   **Storage**:
    *   In `main.py`, a separate call to `fetch_team_stats` will be made.
    *   The data will be passed to `storage.save()`, appending a `_stats` suffix to the identifier to ensure it saves as a distinct file (e.g., `2026-05-14_10-00-00_nba.l.12345_stats.json`).

## 3. Error Handling
*   **Missing Mapping File**: If `team_mapping.json` does not exist, the code will gracefully default to using original API names without crashing.
*   **Invalid JSON**: If `team_mapping.json` is malformed, it will be logged as an error and fallback to API names.
*   **Missing Stats**: If a particular team is missing stats from the API, it will default to an empty dictionary `{}` for that team's stats.

## 4. Testing
*   Update `tests/test_fetcher.py` to mock `team_mapping.json` and ensure names are replaced correctly.
*   Add a test for `fetch_team_stats` to verify the structure of the returned stats.
*   Update `tests/test_storage.py` if necessary to ensure `_stats` files are saved properly.
