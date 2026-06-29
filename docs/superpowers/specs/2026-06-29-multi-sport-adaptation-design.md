# Yahoo Fantasy Multi-Sport (NBA & MLB) Adaptation Design Spec

## 1. Context & Overview
Currently, the LINE Bot is tightly coupled with NBA basketball data (using hardcoded stat maps, 9-Cat columns, and strict NBA prefixes for API paths). If a user attempts to bind an MLB league, the system fails due to formatting, prefixing, and parsing issues.
This design spec outlines how to generalize the codebase to dynamically adapt to both **NBA** and **MLB** leagues while keeping the existing NBA visual aesthetics unchanged and minimizing hardcoded configurations.

---

## 2. Setup Flow & Directory Structure

### 2-1. LINE Flex Message Sport Selection
When a user inputs the `#設置聯盟ID` command without arguments, the Bot will respond with a LINE Flex Message to select the sport:
* **Button 1**: NBA 籃球 (sends command: `#設置聯盟ID nba`)
* **Button 2**: MLB 棒球 (sends command: `#設置聯盟ID mlb`)

Upon selecting, the Bot initiates a 60-second interactive rewrite session:
* Bot prompts: *"請輸入您的 NBA 聯盟 ID (純數字，例如 18457)："* (or MLB depending on selection).
* User inputs the numeric ID (e.g. `18457`).
* Bot normalizes the value to the fully qualified league key: `nba.l.18457` or `mlb.l.18457`.

### 2-2. Conflicted Directory Resolution (Full League Key Name)
To prevent conflicts if an NBA league and an MLB league share the same numeric ID, the directory naming convention is updated:
* Old Directory Name: `data/league/<numeric_id>/`
* **New Directory Name**: `data/league/<full_league_key>/` (e.g., `data/league/nba.l.18457/` and `data/league/mlb.l.18457/`).

The database mapping in [chat_league_mapping.json](file:///C:/Users/HsiehLink/Python/yf_for_turtle/data/security/chat_league_mapping.json) will store the full league key instead of the raw number:
```json
{
  "Ce689309ed07e6bcc4bf73264dc81fdfb": "nba.l.18457",
  "U73be9e76911a0b2d2b300d7bc907cf5c": "mlb.l.12345"
}
```

---

## 3. Dynamic Stats Categories & Formatting Heuristics

### 3-1. Settings API Caching
During league binding (`SetLeagueIdHandler`), the Bot calls Yahoo API's `league/{league_id}/settings` endpoint once to fetch all active stat categories.
It extracts:
* `stat_id`
* `display_name` (e.g. `PTS`, `AVG`, `ERA`)
* `sort_order` (`1` for high-better, `0` for low-better)

These are saved into the league's [metadata.json](file:///C:/Users/HsiehLink/Python/yf_for_turtle/data/league/nba.l.18457/metadata.json) under `stat_categories`. The global hardcoded `STAT_MAP` in [stat_map.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/constants/stat_map.py) is deprecated; all translations of stat IDs to display names are performed dynamically.

### 3-2. Visualizer Columns & Display Aliases
In [processor.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/visualizer/processor.py), columns are dynamically built from the cached `stat_categories`.
To preserve the current table headers, we implement a **Display Aliases** mapper:
```python
DISPLAY_ALIASES = {
    "FGM/FGA": "FG",
    "FTM/FTA": "FT",
    "3PTM": "3PT"
}
```
If the display name matches a key in `DISPLAY_ALIASES`, it uses the alias for the HTML table header (preserving `FG`, `FT`, `3PT`).

### 3-3. Auto-Formatting Rules (Heuristics)
For formatting raw numbers to strings:
1. **Percentages**: If the display name contains `%` (like `FG%`), multiply float values by 100 and display with `%` (e.g., `45.6%`).
2. **Baseball Rate Stats (3 Decimals)**: If display name is in `["AVG", "OBP", "SLG", "OPS"]`, format to 3 decimal places (stripping leading zero, e.g. `.285`).
3. **Baseball Pitching Rate Stats (2 Decimals)**: If display name is in `["ERA", "WHIP"]`, format to 2 decimal places (e.g. `3.45`).
4. **General Stats**: Keep as integers/strings.

---

## 4. LLM Search Scope & Prompts

The LLM prompt templates are updated to accept the active `sport` parameter:
* **Fuzzy search scope**: The system role for player matching will be dynamically changed (e.g., "你是一個精準的 NBA 籃球專家..." vs "你是一個精準的 MLB 棒球專家...").
* **Search keywords constraint**: Google search queries for nickname translation will append the sport to narrow the results:
  * NBA: `NBA "<nickname>"`
  * MLB: `MLB "<nickname>"`
* This guarantees that querying `Smith` in an MLB group only returns MLB players, avoiding sport mismatches.

---

## 5. Fallback Limitations (NBA-Only Features)

Features involving external custom scrapers or non-standard APIs are limited to NBA:
1. **ESPN Game Day Status**:
   In [time_utils.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/time_utils.py), checking game day status via ESPN scoreboard is bypassed for MLB (returns `(True, "")` by default).
2. **Season Countdowns & Injury Commands**:
   If `#開季` or `#傷兵` is invoked in an MLB group, the Bot responds:
   > `⚠️ 此功能目前僅支援 NBA 聯賽。`

---

## 6. Migration Plan
To seamlessly migrate the current user environment without losing history:
* At server startup or path lookup, the system checks if the old directory name `data/league/18457` exists.
* If it exists and the new folder `data/league/nba.l.18457` does not, it renames the directory from `18457` to `nba.l.18457` automatically (using `os.rename`).
* It updates the local `chat_league_mapping.json` keys to map to the new prefixed values.
