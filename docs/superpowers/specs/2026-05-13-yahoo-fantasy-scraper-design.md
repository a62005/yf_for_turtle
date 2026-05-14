# Yahoo Fantasy NBA Scraper Design Specification

## Overview
A Python application to fetch Yahoo Fantasy NBA league data (teams and player stats) using the `yahoofantasy` package. Data will be saved in JSON format, designed modularly to allow easy migration to a database in the future. The project will be under Git version control.

## Architecture & Components
- **`main.py`**: The entry point. Coordinates fetching and storing.
- **`config.py`**: Handles environment variables (API keys, League ID).
- **`fetcher.py`**: Encapsulates Yahoo API interactions using the `yahoofantasy` package.
- **`storage.py`**: Defines a generic storage interface with a concrete `JsonStorage` class for currently saving JSON files to the `data/` directory.
- **`.env`**: Stores sensitive credentials (ignored by Git).
- **`requirements.txt`**: Project dependencies.
- **`GEMINI.md`**: AI Agent instructions file. Provides context, architecture rules, and setup steps so any AI agent analyzing this repo in the future understands how to build, run, and modify it.

## Data Flow
1. **Authentication**: `yahoofantasy` handles OAuth 2.0 (requires initial manual auth or cached `oauth2.json`).
2. **Data Extraction**: `fetcher.py` retrieves the specified League's teams, rosters, and player stats.
3. **Transformation**: Extracted objects are mapped into standard Python dictionaries.
4. **Loading**: `storage.py` writes the data to a timestamped JSON file (e.g., `data/YYYY-MM-DD_league_data.json`).

## Scheduling
The script is a one-off execution application. It is intended to be executed periodically (e.g., daily) using the OS's built-in task scheduler (Windows Task Scheduler or Linux Cron).

## Version Control
Git repository with a standard Python `.gitignore` to prevent committing `data/`, `.env`, `oauth2.json`, and `__pycache__/`.
