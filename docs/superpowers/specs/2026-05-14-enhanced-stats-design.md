# Enhanced Weekly/Daily Stats and Localized Naming Design

## 1. Overview
This design enhances the Yahoo Fantasy NBA Scraper with the following capabilities:
1.  **Multi-level Stats Fetching**: Adds support for Season, Weekly, and Daily team-level performance data.
2.  **Automatic Week Calculation**: Calculates the current fantasy week based on a user-provided season start date, respecting the Sunday midnight PT transition (Monday 4 PM TST).
3.  **Localized Stat Names**: Translates Yahoo's `stat_id` into Traditional Chinese basketball terminology (e.g., "火鍋", "抄截").
4.  **Hierarchical Storage**: Organizes output into dedicated directories for season, weekly, and daily data with specific update rules (overwrite vs. independent).

## 2. Architecture & Components

### 2.1 Configuration (`src/config.py` & `.env`)
*   Add `SEASON_START_DATE`: The start date of Week 1 in `YYYY-MM-DD` format.
*   The system will use this to calculate the `week_number` for API queries and file naming.

### 2.2 Time & Week Management (`src/utils/time_utils.py`)
*   **Logic**: Convert current system time to Pacific Time (PT).
*   **Transition**: A week starts on Monday at 00:00:00 PT.
*   **Function**: `get_fantasy_week(start_date: str) -> int` and `get_query_date() -> str`.

### 2.3 Stat Translation (`src/constants/stat_map.py`)
*   A comprehensive mapping of NBA `stat_id` to standard basketball abbreviations.
    *   `12`: "PTS", `15`: "REB", `16`: "AST", `17`: "ST", `18`: "BLK", `19`: "TO"
    *   `5`: "FG%", `8`: "FT%", `11`: "3PT%"
    *   `9004003`: "FGM/FGA", `9007006`: "FTM/FTA"
*   Includes formatting logic for ratios (e.g., "FGM/FGA").

### 2.4 Enhanced Fetcher (`src/fetcher.py`)
*   **`fetch_season_stats()`**: Current implementation, using `league.standings()`. Overwrites `season_stats.json`.
*   **`fetch_weekly_stats(week: int)`**: Queries `scoreboard;week=N`. Stores in `data/weekly/week_N.json` (overwrites).
*   **`fetch_daily_stats(date: str)`**: Queries `scoreboard;type=day;date=YYYY-MM-DD`. Stores in `data/daily/YYYY_MM_DD.json` (new file per day).
*   **Translation Layer**: All methods will pass raw `stat_id` through the mapping before returning data.

### 2.5 Storage Refactor (`src/storage.py`)
*   Support subdirectories (`weekly/`, `daily/`).
*   Ensure filenames are predictable (e.g., `season_stats.json`, `week_18.json`, `2026-05-14.json`).

## 3. Data Flow
1.  `main.py` loads config.
2.  `time_utils` determines current PT date and week number.
3.  `fetcher` makes three calls (Season, Week, Day).
4.  Data is translated into Chinese keys.
5.  `storage` saves them to their respective locations.

## 4. Error Handling
*   **Off-season**: If the current date is before the season start, the system should log a warning and skip weekly/daily fetching.
*   **Missing API Data**: If Yahoo returns empty for a specific day/week, log it and move to the next.

## 5. Testing
*   Unit tests for `time_utils` to verify week calculation.
*   Mock API responses to verify translation of `stat_id`.
*   Storage tests for correct pathing.
