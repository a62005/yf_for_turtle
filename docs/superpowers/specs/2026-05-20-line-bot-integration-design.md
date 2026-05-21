# LINE Bot Integration Design Specification

## Overview
Integrate a LINE Bot to serve generated Yahoo Fantasy NBA visualization images. The system will act as a caching layer, serving pre-generated images instantly while strictly regulating real-time data fetching to avoid incomplete game data and LINE webhook timeouts.

## System Architecture (Hybrid Mode)
1. **Flask Web Server (`bot.py`)**: 
   - Handles LINE webhook endpoints.
   - Acts as an image server (e.g., serving files from `data/images/`).
2. **Background Scheduler (External)**:
   - A cron job will execute `main.py` daily at **13:55 (Taiwan Time)** to pre-fetch data and generate images before the 14:00 query window opens.

## Command Routing
The bot will parse incoming text messages using Regex:
1. `#戰績`: Returns the combined daily and weekly stats image.
2. `#當天戰績`: Returns today's stats image.
3. `#當週戰績`: Returns the current week's stats image.
4. `#戰績W{number}` (e.g., `#戰績W2`): Returns the specific week's stats image.
5. `#戰績{YYYYMMDD}` (e.g., `#戰績20251003`): Returns the specific date's stats image.

## Caching and Fetching Logic
When a command is received, the bot executes the following decision tree:

### 1. Cache Check
- Look for the requested image in `data/images/`.
  - **If image exists**: Immediately return the image URL to the user.
- Look for a negative cache entry in `data/empty_records.json` (e.g., `{"20251003_daily": true, "week_45": true}`).
  - **If negative cache exists**: Immediately reply `查無當天數據` or `查無當週數據` (no fetch triggered).

### 2. Time & Validation Gate (If Cache Miss)
If neither the image nor a negative cache exists, determine if the request is for the **current** period or a **historical** period.

#### For Current Period (`#戰績`, `#當天戰績`, `#當週戰績`):
- Check Current Taiwan Time (UTC+8):
  - **00:00 to 14:00**: Reply text: `請於 14:00 後再進行查詢。` (Abort fetch)
  - **After 14:00**: Trigger `main.py` subprocess. 
    - *Timeout Handling*: If the fetch takes too long and risks LINE's timeout, reply text: `數據更新中，請稍候再試...`
    - *Empty Data Handling*: If fetching completes but no data is found, record it in `data/empty_records.json` and reply: `查無當天數據` or `查無當週數據`.

#### For Historical Period (`#戰績W*`, `#戰績*`):
- Time gate (14:00) does NOT apply.
- Trigger `main.py` with specific `TEST_WEEK` or `TEST_DATE` environment variables.
- Apply the same Timeout and Empty Data recording handling as above.

## Error Handling & Replies
- **Timeout**: `數據更新中，請稍候再試...`
- **No Daily Data**: `查無當天數據` (Saves to Negative Cache)
- **No Weekly Data**: `查無當週數據` (Saves to Negative Cache)
- **Early Query (00:00-14:00)**: `請於 14:00 後再進行查詢。`
