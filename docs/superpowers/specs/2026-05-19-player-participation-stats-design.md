# Player Participation Stats Design Specification

## Overview
Add two new metrics to the visualization output to help league members track active rosters and remaining schedules:
1. **Today Player**: Number of players in starting positions for the current day.
2. **Game Player**: Ratio of games played to total games scheduled for the week.

These columns will appear as the leftmost tables in the generated images.

## Data Extraction (Fetcher)
- **Today Player**: 
    - API: `teams/roster;date={YYYY-MM-DD}` (Batch request for all teams).
    - Logic: Count players where `selected_position` is not in `['BN', 'IL', 'IL+', 'NA']`.
- **Game Player**:
    - API: `league/scoreboard;week={week}`.
    - Logic: Extract `completed_games`, `live_games`, and `remaining_games` from the `<team_remaining_games>` node.
    - Calculation: `Played = Completed + Live`, `Total = Played + Remaining`. Format as `"Played / Total"`.

## Data Processing & Sorting (Processor)
- **Insertion**: Both metrics will be inserted at the beginning of the `categories` list in `process_stats_for_visual`.
- **Sorting (Today Player)**: Descending by player count.
- **Sorting (Game Player)**: 
    1. Primary: Played games (Descending).
    2. Secondary: Total games (Descending).

## Visualization (Renderer/Templates)
- **Position**: Leftmost column.
- **Styling**: Use a light blue background for these specific columns to distinguish them from standard stat categories.
- **Alignment**: Maintain fixed row heights (28px) as established in previous fixes.

## Component Changes
- `src/fetcher.py`: Add `fetch_batch_rosters` and update `_parse_remaining_games` logic.
- `src/visualizer/processor.py`: Add new categories and implement composite sorting logic.
- `main.py`: Update the execution flow to fetch and merge these new data points before visualization.
