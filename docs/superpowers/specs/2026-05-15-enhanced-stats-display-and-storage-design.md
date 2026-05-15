# Enhanced Stats Display and Storage Design

## 1. Overview
This feature introduces formatting improvements for shooting percentages, handles API data anomalies (e.g., null values), introduces a visual ranking column in the output tables, and adds a configuration-driven season hierarchy for better data file management across different years.

## 2. Requirements & Constraints
- **Null Value Handling**: Any null or invalid value (`null`, `"-"`, `"null"`) from the Yahoo API must be explicitly stored and treated as `0` in the intermediate JSON data.
- **Percentage Formatting**: Fields representing percentages (specifically `FG%` and `FT%`) must be displayed in `12.3%` format instead of `0.123`. A value of `0` should be displayed as `0.00%`.
- **Ranking Column**: In the rendered HTML/image tables, a new column displaying the rank (`1` to `12`) must be added to the leftmost side of each statistic category table. The column width should be minimal.
- **Season Hierarchy**: The storage layer must organize JSON files into season-specific directories (e.g., `data/24-25/`). The season year string will be sourced from an environment variable (`SEASON`).

## 3. Architecture & Data Flow

### 3.1 `fetcher.py` (Data Ingestion)
- Modify `_get_val` to intercept empty or null-like values (`None`, `"null"`, `"-"`, `""`) and convert them to the integer `0`.
- This ensures data remains clean and mathematical operations (such as sorting in `processor.py`) continue to function without crashing on `NoneType` or string comparisons.

### 3.2 `processor.py` (Data Formatting & Ranking)
- **Formatting**: Within the category processing loop, check if the current category is `FG%` or `FT%`. If so, read the float value and format it using Python string formatting (`f"{val * 100:.2f}%"` or similar logic). If the value is `0` or `0.0`, output `"0.00%"`.
- **Ranking**: During the sorted loop that assigns team rows for a given category, include the current loop index (+1) to inject a `rank` key into the `rows` dictionaries alongside `name` and `value`.

### 3.3 HTML Template (`stats_table.html`)
- Adjust the table structure to include a new `td` for the rank.
- Set a minimal width class for this rank cell, reducing overall width consumption while providing clarity. 

### 3.4 Configuration & Storage (`config.py` & `storage.py`)
- **Config**: Expose a new `SEASON` variable sourced from `.env` in `src/config.py`.
- **Main Workflow**: Pass `SEASON` as the `sub_dir` parameter when invoking `storage.save()`.
- **Storage**: `JsonStorage.save` already utilizes `sub_dir` to append to the root `data_dir` and constructs the full path. The changes in `main.py` driving this are sufficient.

## 4. Testing
- Verify that `fetcher.py` cleanly outputs `0` for intentionally injected `None` or `"-"` API mocked responses.
- Check generated HTML tables to visually confirm the new column, its width, and the correct sequence from 1 to 12.
- Verify `FG%` and `FT%` columns show correct percentage formats with `%` signs.
- Ensure that upon execution, JSON files correctly appear in `data/<SEASON>/` instead of the top-level `data/` directory.