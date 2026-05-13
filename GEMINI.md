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