# Relative Stats Commands and Unified Image Design

## 1. Context and Goals
The current bot handles `#戰績` and specific dates/weeks, but generates separate daily and weekly images, which clutters the response. Additionally, users want to query using relative time like `#戰績昨天` and `#戰績上週`. When querying an out-of-bounds week (e.g., `#戰績W25`), the bot incorrectly falls back to the last week instead of returning an error. Finally, week-specific queries need to target the actual *last day* of that week, which requires dynamic fetching from the Yahoo API due to irregularities like All-Star breaks. To avoid repeated API calls, the queried dates must be cached.

**Goals:**
1. Unify all stat command outputs to use the "Combined" (Daily + Weekly) image exclusively.
2. Add support for `#戰績昨天` and `#戰績上週`.
3. Support `#戰績[YYYYMMDD]` and `#戰績W[Week]` using the unified combined image.
4. Dynamically fetch and **cache** the end date for specific weeks to avoid repeated API calls.
5. Fix the out-of-bounds week bug.

## 2. Architecture & Implementation Design

### 2.1. Dynamic Fetching and Caching Week End Dates (Metadata Lazy-Loading)
- **`src/fetcher.py`**: Add `fetch_week_end_date(self, league_id: str, week: int) -> str` to query `league/{league_id}/scoreboard;week={week}` and extract the week's end date.
- **`src/cache_utils.py`**: The existing `league_metadata.json` will be updated to include a `"week_dates": {}` dictionary.
- **Caching Logic**: 
  - When a week's end date is needed, the system reads `league_metadata.json`.
  - It checks `week_dates[str(week)]`.
  - **Cache Hit**: Returns the cached date immediately without calling any API.
  - **Cache Miss**: Calls `fetch_week_end_date`, updates the metadata cache dictionary with the new date, saves the file via `save_league_metadata`, and then returns the date.

### 2.2. Unified Image Generation (Handler Adjustments)
- Remove `daily_pattern` and `weekly_pattern` independent image logic from `stats_handler.py`.
- Ensure `parse_command` and `execute` route all valid stat commands to generate/fetch a combined image.
- Image naming convention will strictly be `{target_date}_combined.png`.

### 2.3. Command Behaviors
- **`#戰績[YYYYMMDD]`**: Sets `target_date` to the parsed date. Generates/fetches combined image.
- **`#戰績W[Week]`**: Uses lazy-loading to find the `week_end` date. Sets `target_date = week_end`. Generates/fetches combined image.
- **`#戰績昨天`**: Sets `target_date = today - 1 day`. Generates/fetches combined image.
- **`#戰績上週`**: Sets `target_week = current_week - 1`. Uses lazy-loading to find the `week_end` date for that week. Sets `target_date = week_end`. Generates/fetches combined image.

### 2.4. Fixing the Out-of-Bounds Week Bug
- In `stats_handler.py`, replace the fallback logic (`if calculated_week > meta['end_week']: target_week = meta['end_week']`) with a hard stop for specific week queries.
- If the requested week `> meta['end_week']` or `< 1`, immediately return the text message `"查無當週戰績"`.

## 3. Testing Strategy
- Update `test_stats_handler.py` to test the new regex patterns for `昨天` and `上週`.
- Mock `fetch_week_end_date` and `load_league_metadata`/`save_league_metadata` to test the lazy-loading and caching mechanism.
- Add tests to ensure out-of-bounds weeks return the correct text message without falling back.
